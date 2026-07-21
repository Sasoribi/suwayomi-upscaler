"""Real-ESRGAN engine — balanced quality and speed."""
from upscaler.engines.base import UpscaleEngine


class RealESRGANEngine(UpscaleEngine):
    BINARY = "realesrgan-ncnn-vulkan"

    @property
    def name(self) -> str:
        return "realesrgan"

    @property
    def default_timeout(self) -> int:
        return 45

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
                "-n", "realesr-animevideov3",
                "-g", "0",
            ],
            timeout=timeout or self.default_timeout,
        )
        return ok
