"""Real-CUGAN engine — best quality for manga, built-in seam suppression via -c 1."""
from upscaler.engines.base import UpscaleEngine


class RealCUGANEngine(UpscaleEngine):
    BINARY = "realcugan-ncnn-vulkan"

    @property
    def name(self) -> str:
        return "realcugan"

    @property
    def default_timeout(self) -> int:
        return 60

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
                "-g", "0",
            ],
            timeout=timeout or self.default_timeout,
        )
        return ok
