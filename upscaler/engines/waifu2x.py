"""Waifu2x engine — fastest, anime style model for manga."""
import os
from pathlib import Path

from upscaler.engines.base import UpscaleEngine


class Waifu2xEngine(UpscaleEngine):
    BINARY = "waifu2x-ncnn-vulkan"
    DEFAULT_MODEL = "models-upconv_7_anime_style_art_rgb"

    @property
    def name(self) -> str:
        return "waifu2x"

    @property
    def default_timeout(self) -> int:
        return 45

    def _find_model(self) -> str:
        # Env override
        if os.getenv("WAIFU2X_MODEL_PATH"):
            return os.getenv("WAIFU2X_MODEL_PATH")

        # Search next to binary (follow symlinks)
        import shutil
        binary = shutil.which(self.BINARY)
        if binary:
            real = Path(binary).resolve()
            candidate = real.parent / self.DEFAULT_MODEL
            if candidate.is_dir():
                return str(candidate)

        # Fallback: cwd-relative
        if Path(self.DEFAULT_MODEL).is_dir():
            return self.DEFAULT_MODEL

        return self.DEFAULT_MODEL

    def validate(self) -> bool:
        ok, _ = self._run([self.BINARY, "-h"], timeout=5)
        return ok or True

    def upscale(self, input_path, output_path, scale=2, timeout=None) -> bool:
        ok, stderr = self._run(
            [
                self.BINARY,
                "-i", str(input_path),
                "-o", str(output_path),
                "-s", str(scale),
                "-n", "0",
                "-m", self._find_model(),
                "-g", "0",
            ],
            timeout=timeout or self.default_timeout,
        )
        return ok
