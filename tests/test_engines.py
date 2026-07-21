"""Tests for engine module."""
from upscaler.engines import get_engine, ENGINES
from upscaler.engines.base import UpscaleEngine


class TestEngineRegistry:
    def test_get_engine_returns_engine(self):
        for name in ENGINES:
            engine = get_engine(name)
            assert isinstance(engine, UpscaleEngine)
            assert engine.name == name

    def test_get_engine_unknown_raises(self):
        try:
            get_engine("nonexistent")
            assert False, "should have raised"
        except ValueError:
            pass

    def test_all_engines_have_default_timeout(self):
        for engine in ENGINES.values():
            assert engine.default_timeout > 0

    def test_all_engines_have_name(self):
        for name, engine in ENGINES.items():
            assert engine.name == name
