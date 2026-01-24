__version__ = "0.1.0"
__author__ = "sirgrayX"

from .cli import main
from .watcher import tail_file

__all__ = ["main", "tail_file"]