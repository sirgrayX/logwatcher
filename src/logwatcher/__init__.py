from .formatter import ColorFormatter
from .watcher import LogWatcher, WatcherConfig, WatcherState
from .cli import main
from .logger import get_logger
from .models import (
    LogEntry, 
    LogParser, 
    OutputHandler, 
    RegexLogParser,
    ConsoleHandler,
    JsonFileHandler,
    StatsCollector,
    Event,
    SystemEvent,
    FileRotationEvent,
    FileErrorEvent,
    WatcherStateEvent,

)

__version__ = "0.3.0"
__author__ = "sirgrayX"

__all__ = [
    "ColorFormatter",
    "LogWatcher",
    "WatcherConfig",
    "main",
    "get_logger",
    "LogEntry",
    "LogParser",
    "OutputHandler",
    "RegexLogParser",
    "ConsoleHandler",
    "JsonFileHandler",
    "StatsCollector",
    "Event",
    "SystemEvent",
    "FileRotationEvent",
    "FileErrorEvent",
    "WatcherStateEvent"
]