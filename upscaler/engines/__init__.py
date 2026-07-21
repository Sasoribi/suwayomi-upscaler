"""Pluggable AI upscale engines."""
from upscaler.engines.base import UpscaleEngine
from upscaler.engines.realcugan import RealCUGANEngine
from upscaler.engines.waifu2x import Waifu2xEngine
from upscaler.engines.realesrgan import RealESRGANEngine

ENGINES: dict[str, UpscaleEngine] = {
    "realcugan": RealCUGANEngine(),
    "waifu2x": Waifu2xEngine(),
    "realesrgan": RealESRGANEngine(),
}


def get_engine(name: str) -> UpscaleEngine:
    engine = ENGINES.get(name)
    if engine is None:
        raise ValueError(f"Unknown engine: {name}. Available: {list(ENGINES.keys())}")
    return engine
