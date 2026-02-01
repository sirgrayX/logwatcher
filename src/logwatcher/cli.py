import argparse
from ast import parse
import sys
import signal

from pathlib import Path
from typing import List, Optional

from .models import ConsoleHandler, RegexLogParser

from .watcher import LogWatcher, WatcherConfig

from .logger import get_logger

logger = get_logger()

def setup_arg_parser() -> argparse.ArgumentParser:
    """Настраивает парсер аргументов командной строки."""

    parser = argparse.ArgumentParser(
        description="LogWatcher - инструмент для мониторинга логов в реальном времени",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  %(prog)s /var/log/app.log
  %(prog)s /var/log/app.log --min-level ERROR
  %(prog)s /var/log/app.log --no-colors --interval 0.5 --json-output
  %(prog)s /var/log/app.log --stats --follow-rotation
        """
    )

    parser.add_argument(
        "filename",
        type=str,
        help="Путь к файлу логов для мониторинга"
    )

    parser.add_argument(
        "--min-level",
        "-l",
        choices=["DEBUG", "INFO", "WARN", "ERROR"],
        default="WARN",
        help="Минимальный уровень логов для отображения (по умолчанию: WARN)"
    )

    parser.add_argument(
        "--no-colors",
        action="store_true",
        help="Отлючить цветной вывод"
    )

    parser.add_argument(
        "--interval",
        "-i",
        type=float,
        default=0.1,
        help="Интервал проверки файла в секундах (по умолчанию: 0.1)"
    )

    parser.add_argument(
        "--follow_rotation",
        "-f",
        action="store_true",
        help="Отслеживать ротацию файла логов"
    )

    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Сохранять логи в JSON формате"
    )

    parser.add_argument(
        "--output-file",
        "-o",
        type=str,
        default="./logwatcher_output.json",
        help="Файл для сохранения JSON логов (по умолчанию: ./logwatcher_output.json)"
    )

    parser.add_argument(
        "--stats",
        "-s",
        action="store_true",
        help="Собирать и выводить статистику при завершении"
    )

    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Максимальное количество попыток перезапуска при ошибках"
    )

    parser.add_argument(
        "--encoding",
        "-e",
        type=str,
        default="utf-8",
        help="Кодировка файла логов (по умолчанию: utf-8)"
    )

    return parser

def validate_args(args: argparse.Namespace) -> None:
    """Валидирует аргументы командной строки."""
    
    if args.interval <= 0:
        raise ValueError("Интервал проверки должен быть положительным числом")
    
    if args.max_retries < 0:
        raise ValueError("Количество попыток не может быть отрицательным")
    
    log_file = Path(args.filename)
    if not log_file.exists():
        raise FileNotFoundError(f"Файл логов не найден: {args.filename}")
    
    if not log_file.is_file():
        raise ValueError(f"Указанный путь не является файлом: {args.filename}")


def create_watcher_config(args: argparse.Namespace) -> WatcherConfig:
    """Создаёт конфигурацию для LogWatcher на основе аргументов."""

    global logger
    logger = get_logger()

    return WatcherConfig(
        min_level=args.min_level,
        use_colors=not args.no_colors,
        check_interval=args.interval,
        follow_rotation=args.follow_rotation,
        use_json=args.json_output,
        json_output_file=args.output_file,
        encoding=args.encoding,
        collect_stats=args.stats,
        max_retries=args.max_retries,
    )

def setup_signal_handlers(watcher: LogWatcher) -> None:
    """Настраивает обработчики сигналов для graceful shutdown."""
    
    def signal_handler(signum, frame):
        logger.info(f"Получен сигнал {signum}, завершение работы...")
        watcher.stop()
    
    signal.signal(signal.SIGINT, signal_handler)   
    signal.signal(signal.SIGTERM, signal_handler) 

def print_stats(stats: dict) -> None:
    """Выводит статистику в читаемом формате."""
    
    print("\n" + "="*50)
    print("СТАТИСТИКА LOGWATCHER")
    print("="*50)
    
    if "log_entries" in stats:
        log_stats = stats["log_entries"]
        print(f"Всего записей: {log_stats.get('total_lines', 0)}")
        
        print("По уровням:")
        for level, count in log_stats.get('lines_by_level', {}).items():
            if count > 0:
                print(f"  {level}: {count}")
        
        if log_stats.get('by_source'):
            print("По источникам:")
            for source, count in log_stats['by_source'].items():
                print(f"  {source}: {count}")
    
    if "system_events" in stats:
        sys_stats = stats["system_events"]
        print(f"\nСистемных событий: {sys_stats.get('total_events', 0)}")
        
        if sys_stats.get('by_type'):
            print("Типы событий:")
            for event_type, count in sys_stats['by_type'].items():
                print(f"  {event_type}: {count}")
    
    if "duration_seconds" in stats:
        print(f"\nОбщее время работы: {stats['duration_seconds']:.2f} секунд")
    
    print("="*50)

def run_monitoring(args: argparse.Namespace) -> int:
    """
    Основная функция запуска мониторинга.
    
    Возвращает:
        Код завершения (0 - успех, 1 - ошибка)
    """
    try:
        config = create_watcher_config(args)
        parser = RegexLogParser()
        
        watcher = LogWatcher(
            filename=args.filename,
            parser=parser,
            config=config
        )

        logger.info(f"Запуск мониторинга файла: {args.filename}")
        logger.info(f"Минимальный уровень: {args.min_level}")
        if args.follow_rotation:
            logger.info("Отслеживание ротации: ВКЛЮЧЕНО")
            
        if args.json_output:
            from .models import JsonFileHandler
            json_handler = JsonFileHandler(Path(args.output_file))
            watcher.add_handler(json_handler)
            logger.info(f"JSON вывод будет сохранён в: {args.output_file}")
        
        setup_signal_handlers(watcher)
        
        watcher.start()
        
        if args.stats:
            stats = watcher.get_stats()
            if stats:
                print_stats(stats)
            else:
                logger.warning("Статистика недоступна")
        
        logger.info("Мониторинг завершён")
        return 0
        
    except KeyboardInterrupt:
        logger.info("Мониторинг прерван пользователем")
        return 0
    except FileNotFoundError as e:
        logger.error(f"Ошибка файла: {e}")
        return 1
    except ValueError as e:
        logger.error(f"Ошибка конфигурации: {e}")
        return 1
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}", exc_info=True)
        return 1



def main(args: Optional[List[str]] = None) -> int:
    parser = setup_arg_parser()

    try:
        parsed_args = parser.parse_args(args)
        validate_args(parsed_args)
        return run_monitoring(parsed_args)
    except SystemExit:
        raise
    except Exception as e:
        logger.error(f"Ошибка при запуске: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())