from .formatter import ColorFormatter
from .watcher import LogWatcher, WatcherConfig
from .cli import main
from .logger import get_logger

__version__ = "0.2.0"
__author__ = "sirgrayX"

__all__ = [
    "ColorFormatter",
    "LogWatcher",
    "WatcherConfig",
    "main",
    "get_logger",
]