import argparse
import sys
from pathlib import Path
from typing import List, Optional


from .watcher import LogWatcher
from .formatter import ColorFormatter
from .logger import get_logger

logger = get_logger('DEBUG')


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Monitor log files in real-time",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s /var/log/syslog
    %(prog)s app.log --level WARN --no-colors
    %(prog)s /var/log/nginx/access.log --level ERROR
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
        "--version",
        action="version",
        version="%(prog)s 0.1.0"
    )

    parser.add_argument(
        "--interval",
        type=float,
        default=0.1,
        help="Check interval in seconds (default: 0.1)"
    )

    return parser.parse_args(args)

def validate_args(args: argparse.Namespace) -> bool:
    if not args.file.exists():
        logger.error(f"Файл не найден {args.file}")
        return False

    if not args.file.is_file():
        logger.error(f"{args.file} не является файлом")
        return False

    return True

def create_watcher(args: argparse.Namespace) -> LogWatcher:
    watcher = LogWatcher(
            filename=args.file,
            min_level=args.level,
            use_colors=args.use_colors
        )
    # logger.info(f"Создан LogWacher для файла: {args.file}")
    return watcher



def main(args: Optional[List[str]] = None) -> int:
    try:
        parsed_args = parse_args(args)

        if not validate_args(parsed_args):
            return 1

        watcher = create_watcher(parsed_args)
        watcher.start()

        if parsed_args.stats:
            logger.info("Статистика мониторинга:")
            logger.info(f"   Обработано строк: {watcher.lines_processed}")
            logger.info(f"   Найдено ошибок: {watcher.errors_found}")

        return 0

    except KeyboardInterrupt:
        logger.info("Прервано пользователем")
        return 130
    except Exception as e:
        logger.error(f"Непредвиденная ошибка: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())