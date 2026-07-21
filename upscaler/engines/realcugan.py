"""Real-CUGAN engine — best quality for manga, built-in seam suppression via -c 1."""
import os
import shutil
from pathlib import Path

from upscaler.engines.base import UpscaleEngine


class RealCUGANEngine(UpscaleEngine):
    BINARY = "realcugan-ncnn-vulkan"
    # models-pro = higher quality denoise, recommended for manga
    DEFAULT_MODEL = "models-pro"

    @property
    def name(self) -> str:
        return "realcugan"

    @property
    def default_timeout(self) -> int:
        return 45

    def _find_model(self) -> str:
        if os.getenv("REALCUGAN_MODEL_PATH"):
            return os.getenv("REALCUGAN_MODEL_PATH")

        binary = shutil.which(self.BINARY)
        if binary:
            real = Path(binary).resolve()
            candidate = real.parent / self.DEFAULT_MODEL
            if candidate.is_dir():
                return str(candidate)

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
                "-c", "1",
                "-m", self._find_model(),
                "-g", "0",
            ],
            timeout=timeout or self.default_timeout,
        )
        return ok
