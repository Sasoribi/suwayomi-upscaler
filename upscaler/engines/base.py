"""Abstract base class for upscale engines."""
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path


class UpscaleEngine(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique engine identifier."""

    @abstractmethod
    def validate(self) -> bool:
        """Check that the binary is available and functional."""

    @abstractmethod
    def upscale(
        self,
        input_path: str | Path,
        output_path: str | Path,
        scale: int = 2,
        timeout: int | None = None,
    ) -> bool:
        """Run upscale. Returns True on success, False on failure."""

    @property
    @abstractmethod
    def default_timeout(self) -> int:
        """Default timeout in seconds for this engine."""

    def _run(self, cmd: list[str], timeout: int) -> tuple[bool, str]:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return result.returncode == 0, result.stderr
        except subprocess.TimeoutExpired:
            return False, "timeout"
        except FileNotFoundError:
            return False, "binary not found"
