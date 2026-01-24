import sys
from pathlib import Path

# Fix для относительных импортов при прямом запуске
if __name__ == "__main__" and __package__ is None:
    # Добавляем текущую директорию в путь
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    __package__ = "src.logwatcher"

import argparse
from .watcher import watch_file


def main():
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
        help='Log file to watch'
    )

    parser.add_argument(
        "-l", "--level",
        choices=['ERROR', 'WARN', 'INFO', 'DEBUG'],
        default="ERROR",
        help="Minimum log level to show (default: ERROR)"
    )

    args = parser.parse_args()

    try:
        watch_file(args.file, args.level)
    except FileNotFoundError:
        print(f"❌ Error: File '{args.file}' not found")
    except KeyboardInterrupt:
        print("\n Stopped by user")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    main()