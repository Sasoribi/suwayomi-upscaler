"""Tests for cache module."""
import tempfile
from pathlib import Path

from upscaler.cache import Cache


class TestCache:
    def test_put_and_get(self):
        with tempfile.TemporaryDirectory() as d:
            c = Cache(max_gb=1, cache_dir=d)
            c.put("http://test/1", b"hello")
            assert c.get("http://test/1") == b"hello"

    def test_miss_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            c = Cache(max_gb=1, cache_dir=d)
            assert c.get("http://test/nonexistent") is None

    def test_different_urls_different_keys(self):
        with tempfile.TemporaryDirectory() as d:
            c = Cache(max_gb=1, cache_dir=d)
            c.put("http://a/1", b"aaa")
            c.put("http://b/1", b"bbb")
            assert c.get("http://a/1") == b"aaa"
            assert c.get("http://b/1") == b"bbb"

    def test_eviction_on_size_limit(self):
        with tempfile.TemporaryDirectory() as d:
            c = Cache(max_gb=0, cache_dir=d)
            big = b"x" * 1000
            c.put("http://test/big", big)
            assert c.get("http://test/big") is None

    def test_shard_structure(self):
        with tempfile.TemporaryDirectory() as d:
            c = Cache(max_gb=1, cache_dir=d)
            c.put("http://test/shard", b"data")
            files = list(Path(d).rglob("*.png"))
            assert len(files) == 1
            assert len(files[0].parent.parent.name) == 2
            assert len(files[0].parent.name) == 2

    def test_stats(self):
        with tempfile.TemporaryDirectory() as d:
            c = Cache(max_gb=1, cache_dir=d)
            c.put("http://a", b"1234")
            c.put("http://b", b"5678")
            s = c.stats()
            assert s["file_count"] == 2
            assert s["total_bytes"] == 8
