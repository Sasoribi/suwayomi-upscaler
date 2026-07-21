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

        # Fix MoltenVK color channel inversion on Apple Silicon.
        # realcugan via MoltenVK sometimes produces BGR-order or pink-shifted
        # output. Detect and correct by swapping R↔B when the output shows
        # an unnatural color cast on what should be grayscale manga pages.
        result = self._fix_moltenvk_colors(image_data, result)

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
    def _is_grayscale(data: bytes) -> bool:
        """Check if an image is mostly grayscale (i.e. manga page, not color art)."""
        try:
            with Image.open(BytesIO(data)) as img:
                if img.mode == 'L':
                    return True  # pure grayscale — common for manga pages
                img_rgb = img.convert("RGB")
                w, h = img_rgb.size
                # Sample evenly across the image
                gray = color = 0
                for y in range(0, h, max(1, h // 20)):
                    for x in range(0, w, max(1, w // 20)):
                        r, g, b = img_rgb.getpixel((x, y))
                        if abs(r - g) < 6 and abs(g - b) < 6:
                            gray += 1
                        else:
                            color += 1
                return gray > 0 and gray / (gray + color) > 0.95
        except Exception:
            return False

    @classmethod
    def _fix_moltenvk_colors(cls, src_data: bytes, result_data: bytes) -> bytes:
        """Detect and fix MoltenVK BGR/pink cast on Apple Silicon for grayscale manga."""
        if not cls._is_grayscale(src_data):
            return result_data

        try:
            with Image.open(BytesIO(result_data)) as img:
                img = img.convert("RGB")
                w, h = img.size
                r_sum = g_sum = b_sum = n = 0
                for y in range(0, h, max(1, h // 20)):
                    for x in range(0, w, max(1, w // 20)):
                        r, g, b = img.getpixel((x, y))
                        r_sum += r; g_sum += g; b_sum += b; n += 1
                if n < 10:
                    return result_data

                avg_r = r_sum / n; avg_g = g_sum / n; avg_b = b_sum / n

                # Normal grayscale output: R ≈ G ≈ B. Skip if already balanced.
                if abs(avg_r - avg_g) < 8 and abs(avg_g - avg_b) < 8:
                    return result_data

                logger.info("🔧 Fixing MoltenVK color cast (R=%.0f G=%.0f B=%.0f) → grayscale",
                            avg_r, avg_g, avg_b)
                img = img.convert("L")
                buf = BytesIO()
                img.save(buf, format="PNG")
                return buf.getvalue()
        except Exception:
            pass
        return result_data

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
