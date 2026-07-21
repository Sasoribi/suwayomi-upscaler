"""Upscale worker with GPU serialization and engine dispatch."""
import logging
import tempfile
from io import BytesIO

from gevent.lock import BoundedSemaphore
from PIL import Image

from upscaler.cache import Cache
from upscaler.config import Config
from upscaler.engines import get_engine, UpscaleEngine

logger = logging.getLogger(__name__)

gpu_lock = BoundedSemaphore(1)
fetch_semaphore = BoundedSemaphore(Config.FETCH_CONCURRENCY)


class Worker:
    def __init__(self, engine: UpscaleEngine | None = None, cache: Cache | None = None):
        self.engine = engine or get_engine(Config.UPSCALE_ENGINE)
        self.cache = cache or Cache()

    def process(self, url: str, image_data: bytes) -> bytes:
        import time as _time
        _start = _time.time()

        cached = self.cache.get(url)
        if cached is not None:
            logger.debug("Cache hit for %s (%.0fms)", url[:80], (_time.time() - _start) * 1000)
            return cached

        if self._should_skip(image_data):
            logger.debug("Resolution above threshold, passing through %s", url[:80])
            return image_data

        if not self.engine.validate():
            logger.warning("Engine %s not available, passing through", self.engine.name)
            return image_data

        in_mb = len(image_data) / (1024 * 1024)
        logger.info("🎨 Upscaling %s [%.2fMB] with %s",
                     url[:80], in_mb, self.engine.name)

        with tempfile.NamedTemporaryFile(suffix=".png") as infile, \
             tempfile.NamedTemporaryFile(suffix=".png") as outfile:
            infile.write(image_data)
            infile.flush()

            with gpu_lock:
                success = self.engine.upscale(
                    infile.name, outfile.name,
                    scale=Config.UPSCALE_SCALE,
                    timeout=self.engine.default_timeout,
                )

            if not success:
                elapsed = _time.time() - _start
                logger.warning("❌ Upscale failed for %s after %.1fs, passing through",
                               url[:80], elapsed)
                return image_data

            outfile.seek(0)
            result = outfile.read()

        elapsed = _time.time() - _start
        out_mb = len(result) / (1024 * 1024)
        ratio = len(result) / len(image_data)
        logger.info("✅ Upscale complete for %s [%.2fMB → %.2fMB, %.1fx, %.1fs]",
                     url[:80], in_mb, out_mb, ratio, elapsed)

        self.cache.put(url, result)
        return result

    def _should_skip(self, data: bytes) -> bool:
        if Config.UPSCALE_THRESHOLD <= 0:
            return False

        try:
            with Image.open(BytesIO(data)) as img:
                return img.width >= Config.UPSCALE_THRESHOLD or img.height >= Config.UPSCALE_THRESHOLD
        except Exception:
            return True
