"""Upscale worker with GPU serialization and engine dispatch."""
import json
import logging
import os
import tempfile
import time
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from gevent.lock import BoundedSemaphore
from PIL import Image

from upscaler.cache import Cache
from upscaler.config import Config
from upscaler.engines import get_engine, UpscaleEngine
from upscaler.logutil import app_log

logger = logging.getLogger(__name__)

gpu_lock = BoundedSemaphore(1)
fetch_semaphore = BoundedSemaphore(Config.FETCH_CONCURRENCY)

# Audit log path (JSONL, one line per operation)
AUDIT_LOG_PATH = Path(os.getenv("AUDIT_LOG_PATH", os.path.join(
    os.getenv("CACHE_DIR", os.path.join(os.getcwd(), "cache")),
    "audit.jsonl",
)))


def _write_audit(record: dict) -> None:
    """Append one JSONL line to the audit log."""
    try:
        AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        with open(AUDIT_LOG_PATH, "a") as f:
            f.write(line + "\n")
    except Exception:
        logger.debug("Failed to write audit log", exc_info=True)


def read_audit(limit: int = 100) -> list[dict]:
    """Read the last `limit` records from audit log."""
    if not AUDIT_LOG_PATH.exists():
        return []
    records = []
    with open(AUDIT_LOG_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records[-limit:]


class Worker:
    def __init__(self, engine: UpscaleEngine | None = None, cache: Cache | None = None):
        self.engine = engine or get_engine(Config.UPSCALE_ENGINE)
        self.cache = cache or Cache()

    def process(self, url: str, image_data: bytes) -> bytes:
        _start = time.time()

        cached = self.cache.get(url)
        if cached is not None:
            logger.debug("Cache hit for %s (%.0fms)", url[:80], (time.time() - _start) * 1000)
            return cached

        in_w, in_h = self._get_dims(image_data)

        if self._should_skip(image_data, pre_dims=(in_w, in_h)):
            logger.debug("Resolution above threshold (%dx%d) >= %d, passing through %s",
                         in_w, in_h, Config.UPSCALE_THRESHOLD, url[:80])
            app_log("INFO", "↗ Skipped (over threshold)",
                    status="skip",
                    url=url[:200], engine=self.engine.name,
                    in_w=in_w, in_h=in_h,
                    size_in_mb=round(len(image_data) / (1024 * 1024), 2))
            return image_data

        if not self.engine.validate():
            logger.warning("Engine %s not available, passing through", self.engine.name)
            return image_data

        in_mb = len(image_data) / (1024 * 1024)
        logger.info("🎨 Upscaling %s [%dx%d, %.2fMB] with %s",
                     url[:80], in_w, in_h, in_mb, self.engine.name)
        app_log("INFO", "🎨 Upscaling",
                status="upscale_start",
                url=url[:200], engine=self.engine.name,
                in_w=in_w, in_h=in_h, size_in_mb=round(in_mb, 2))

        with tempfile.NamedTemporaryFile(suffix=".png") as infile, \
             tempfile.NamedTemporaryFile(suffix=".png") as outfile:
            # Convert to clean RGB PNG before feeding to engine.
            # WebP / RGBA on MoltenVK can produce pink snow artifacts.
            try:
                with Image.open(BytesIO(image_data)) as _tmp:
                    _tmp = _tmp.convert("RGB")
                    _tmp.save(infile.name, format="PNG")
            except Exception:
                infile.write(image_data)
                infile.flush()

            with gpu_lock:
                success = self.engine.upscale(
                    infile.name, outfile.name,
                    scale=Config.UPSCALE_SCALE,
                    timeout=self.engine.default_timeout,
                )

            if not success:
                elapsed = time.time() - _start
                logger.warning("❌ Upscale failed for %s [%dx%d] after %.1fs, passing through",
                               url[:80], in_w, in_h, elapsed)
                app_log("WARNING", "❌ Upscale failed",
                        status="fail",
                        url=url[:200], engine=self.engine.name,
                        in_w=in_w, in_h=in_h, elapsed=round(elapsed, 2),
                        size_in=len(image_data))
                self._audit("fail", url, in_w=in_w, in_h=in_h, elapsed=elapsed,
                            size_in=len(image_data))
                return image_data

            outfile.seek(0)
            result = outfile.read()


        elapsed = time.time() - _start
        out_w, out_h = self._get_dims(result)
        out_mb = len(result) / (1024 * 1024)
        ratio = len(result) / len(image_data)
        logger.info("✅ Upscale complete [%dx%d → %dx%d, %.2fMB → %.2fMB, %.1fx, %.1fs]",
                     in_w, in_h, out_w, out_h, in_mb, out_mb, ratio, elapsed)

        app_log("INFO", "✅ Upscale complete",
                status="ok",
                url=url[:200], engine=self.engine.name,
                in_w=in_w, in_h=in_h, size_in_mb=round(in_mb, 2),
                out_w=out_w, out_h=out_h, size_out_mb=round(out_mb, 2),
                ratio=round(ratio, 1), elapsed=round(elapsed, 2))

        self._audit("ok", url,
                    in_w=in_w, in_h=in_h, size_in=len(image_data),
                    out_w=out_w, out_h=out_h, size_out=len(result),
                    ratio=round(ratio, 1), elapsed=round(elapsed, 2))

        self.cache.put(url, result)
        return result

    @staticmethod
    def _get_dims(data: bytes) -> tuple[int, int]:
        try:
            with Image.open(BytesIO(data)) as img:
                return img.size
        except Exception:
            return (-1, -1)

    def _should_skip(self, data: bytes, pre_dims: tuple[int, int] | None = None) -> bool:
        if Config.UPSCALE_THRESHOLD <= 0:
            return False
        try:
            w, h = pre_dims or self._get_dims(data)
            return w >= Config.UPSCALE_THRESHOLD or h >= Config.UPSCALE_THRESHOLD
        except Exception:
            return True

    @staticmethod
    def _audit(status: str, url: str, **fields) -> None:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "engine": Config.UPSCALE_ENGINE,
            "url": url[:200],
        }
        record.update(fields)
        _write_audit(record)
