"""20GB LRU disk cache with 2-layer hex sharding."""
import hashlib
import os
import time
from pathlib import Path

from upscaler.config import Config


class Cache:
    def __init__(self, max_gb: int = Config.CACHE_MAX_GB, cache_dir: str = Config.CACHE_DIR):
        self.max_bytes = max_gb * 1024 * 1024 * 1024
        self.root = Path(cache_dir)
        self.root.mkdir(parents=True, exist_ok=True)

    def _cache_key(self, url: str) -> str:
        raw = f"{url}|{Config.UPSCALE_ENGINE}|{Config.UPSCALE_SCALE}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _shard_path(self, key: str) -> Path:
        return self.root / key[:2] / key[2:4]

    def _file_path(self, key: str) -> Path:
        return self._shard_path(key) / f"{key}.png"

    def get(self, url: str) -> bytes | None:
        key = self._cache_key(url)
        fp = self._file_path(key)
        if not fp.exists():
            return None
        os.utime(fp, (time.time(), time.time()))
        return fp.read_bytes()

    def put(self, url: str, data: bytes) -> None:
        key = self._cache_key(url)
        fp = self._file_path(key)
        fp.parent.mkdir(parents=True, exist_ok=True)
        tmp = fp.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.rename(fp)
        self._evict_if_needed()

    def _evict_if_needed(self) -> None:
        total = self._total_size()
        if total <= self.max_bytes:
            return
        files = sorted(
            (f for f in self.root.rglob("*.png") if not f.name.endswith(".tmp")),
            key=lambda f: f.stat().st_mtime,
        )
        for f in files:
            if total <= self.max_bytes * 0.9:
                break
            total -= f.stat().st_size
            f.unlink()
        self._cleanup_empty_dirs()

    def _total_size(self) -> int:
        return sum(
            f.stat().st_size
            for f in self.root.rglob("*.png")
            if not f.name.endswith(".tmp")
        )

    def _cleanup_empty_dirs(self) -> None:
        for d in sorted(self.root.rglob("*"), reverse=True):
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()

    def stats(self) -> dict:
        files = [f for f in self.root.rglob("*.png") if not f.name.endswith(".tmp")]
        return {
            "file_count": len(files),
            "total_bytes": sum(f.stat().st_size for f in files),
            "max_bytes": self.max_bytes,
            "max_gb": self.max_bytes // (1024**3),
        }
