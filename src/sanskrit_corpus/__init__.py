"""Sanskrit corpus acquisition tools."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("sanskrit-corpus")
except PackageNotFoundError:  # pragma: no cover - source tree without installation
    __version__ = "0.1.0"
