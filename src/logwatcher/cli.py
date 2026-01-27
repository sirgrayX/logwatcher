import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

from .watcher import LogWatcher, WatcherConfig
from .formatter import ColorFormatter
from .logger import get_logger

logger = get_logger()


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Monitor log files in real-time",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /var/log/syslog
  %(prog)s app.log --level WARN --no-colors
  %(prog)s nginx.log --level INFO --stats
  %(prog)s access.log --interval 0.5 --no-colors

Using LogWatcher class directly in Python code:
  from logwatcher.watcher import LogWatcher, WatcherConfig
  config = WatcherConfig(check_interval=0.5)
  watcher = LogWatcher("app.log", min_level="WARN", config=config)
  watcher.start()
        """
    )

    parser.add_argument(
        "file",
        type=Path,
        help='Log file to watch (path)'
    )

    parser.add_argument(
        "-l", "--level",
        choices=list(ColorFormatter.COLORS.keys()),
        default="ERROR",
        help="Minimum log level to show (default: %(default)s)"
    )

    parser.add_argument(
        "--no-colors",
        action="store_false",
        dest="use_colors",
        default=True,
        help="Disable colored output"
    )

    parser.add_argument(
        "--stats",
        action="store_true",
        default=False,
        help="Show statistics after stopping"
    )

    parser.add_argument(
        "-i", "--interval",
        type=float,
        default=0.1,
        help="Check interval in seconds (default: 0.1)"
    )

    parser.add_argument(
        "--follow-rotation",
        action='store_true',
        default=True,
        help="Follow log rotation (default: True)"
    )

    parser.add_argument(
        "-v","--version",
        action="version",
        version="LogWatcher 1.0"
    )

    return parser.parse_args(args)

def validate_args(args: argparse.Namespace) -> bool:
    if not args.file.exists():
        logger.error(f"File not found: {args.file}")
        return False

    if not args.file.is_file():
        logger.error(f"Not a file: {args.file}")
        return False
    
    if args.interval <= 0:
        logger.error("Inteval must be positive")
        return False
    
    return True

def create_watcher(args: argparse.Namespace) -> LogWatcher:
    """
    Фабричный метод для создания LogWatcher.
    
    :param args: распарсенные аргументы командной строки
    :type args: argparse.Namespace
    :return: Настроенный экземляр LogWatcher.
    """

    config = WatcherConfig(
        check_interval=args.interval,
        follow_rotation=args.follow_rotation,
        collect_stats=args.stats or logger.isEnabledFor(logging.INFO)
    )

    watcher = LogWatcher(
            filename=args.file,
            min_level=args.level,
            use_colors=args.use_colors,
            config=config
        )
    
    # logger.info(f"Создан LogWacher для файла: {args.file}")
    return watcher

def main(args: Optional[List[str]] = None) -> int:
    try:
        parsed_args = parse_args(args)

        if not validate_args(parsed_args):
            return 1

        watcher = create_watcher(parsed_args)

        logger.info("Starting LogWatcher")
        logger.info("File: %s", parsed_args.file)
        logger.info("Level: %s and above", parsed_args.level)
        logger.info("Check interval: %.3fs", parsed_args.interval)
        logger.info("Follow rotation: %s", parsed_args.follow_rotation)

        watcher.start()
        if parsed_args.stats:
            stats = watcher.get_stats()
            logger.info("=== Monitoring Statistics ===")
            logger.info("Lines processed: %d", stats["total_lines"])
            logger.info("Errors found: %d", stats["lines_by_level"]["ERROR"])
            if "duration" in stats:
                logger.info("Duration: %.1f seconds", stats["duration"])

        return 0

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except FileNotFoundError as e:
        logger.error(f"File error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
