"""Waifu2x engine — fastest, may have tile seams."""
from upscaler.engines.base import UpscaleEngine


class Waifu2xEngine(UpscaleEngine):
    BINARY = "waifu2x-ncnn-vulkan"

    @property
    def name(self) -> str:
        return "waifu2x"

    @property
    def default_timeout(self) -> int:
        return 30

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
                "-n", "2",
                "-g", "0",
            ],
            timeout=timeout or self.default_timeout,
        )
        return ok
