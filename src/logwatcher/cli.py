import sys
from pathlib import Path
from typing import Optional, List
import argparse

# Fix для относительных импортов при прямом запуске
if __name__ == "__main__" and __package__ is None:
    # Добавляем текущую директорию в путь
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    __package__ = "src.logwatcher"


from .watcher import watch_file
from .logger import get_logger

logger = get_logger()


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Monitor log files in real-time",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s /var/log/syslog
    %(prog)s app.log --level WARN
    %(prog)s /var/log/nginx/access.log --level ERROR
        """
    )

    parser.add_argument(
        "file",
        type=Path,
        help='Log file to watch'
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
        "-i", "--interval",
        type=float,
        default=0.1,
        help="Check interval in seconds (default: %(default)s)"
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0"
    )

    return parser.parse_args(args)

def validate_args(args: argparse.Namespace) -> bool:
    if not args.file.exists():
        logger.error(f"Файл не найден {args.file}")
        return False

    if not args.file.is_file():
        logger.error(f"{args.file} не является файлом")
        return False

    if args.interval < 0:
        logger.error("Интервал должен быть больше нуля")
        return False

    return True


def main(args: Optional[List[str]] = None) -> int:
    try:
        parsed_args = parser.parse_args()

        if not validate_args(parsed_args):
            return 1

        logger.info("Запуск logwatcher")
        logger.info(f"Файл: {parsed_args.file}")
        logger.info(f"Уровень: {parsed_args.level}")
        logger.info(f"Цвета: {'включены' if parsed_args.use_colors else 'выключены'}")

        watch_file(
            filaname=parsed_args.file,
            min_level=parsed_args.level,
            use_colors=file.use_colors
        )

        return 0

    except KeyboardInterrupt:
        loggger.info("Прервано пользователем")
        return 130
    except Exception e:
        logger.error(f"Непредвиденная ошибка: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    main()