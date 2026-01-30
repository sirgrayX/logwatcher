
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
from re import Pattern
from typing import Optional
from abc import ABC, abstractmethod

@dataclass
class LogEntry:
    """
    Data Transfer Object (DTO) для строки лога.

    Атрибуты:
        raw (str): Исходная строка лога из файла;
        level (str): Уровень логирования (ERROR, WARN, INFO, DEBUG);
        message (str): Текст сообщения;
        timestamp (datetime): Временная метка лога;
        src (str): Источник лога (имя файла или сервиса)
    """
    raw: str
    level: str
    message: str
    timestamp: Optional[datetime] = None
    src: str = "unknown"

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        
    def to_dict(self) -> dict:
        return {
            "raw" : self.raw,
            "level" : self.level,
            "message" : self.message,
            "timestamp" : self.timestamp.isoformat() if self.timestamp else None,
            "src" : self.src
        }
        
class LogParser(ABC):
    """Абстрактный класс парсера логов."""

    @abstractmethod
    def parse(self, line: str) -> LogEntry:
        pass

class OutputHandler(ABC):
    """Абстрактный класс обработчика вывода."""

    @abstractmethod
    def handle(self, entry: LogEntry) -> None:
        """
        Обрабатывает LogEntry.
        Вызывается при получении новой строки лога.

        Args:
            entry: Объект LogEntry для обработки
        """
        pass


# классы -- наследники LogParser (паттерн Стратегия)
class RegexLogParser(LogParser):
    def __init__(self, pattern: Optional[str] = None) -> None:
        self.pattern = pattern or r"(\w+)\s*[:\[\]]\s*(.+)"
        self.compiled_pattern: Pattern = re.compile(self.pattern)

    def parse(self, line: str) -> LogEntry:
        """
        Парсит строку лога с помощью regexp.

        1. Пытаемся найти соответсвие паттерну;
        2. Если найдено - извлекаем уровень и сообщение;
        3. Если не найдено - считаем всю строку сообщением с уровенем INFO.

        Args:
            line (str): Строка для парсинга

        Returns:
            LogEntry: Объект с распарсенными данными.
        """

        line = line.strip()

        match = self.compiled_pattern.match(line)

        level = "INFO"
        message = line

        if match:
            groups = match.groups()
            if len(groups) >= 2:
                level = groups[0].upper()
                message = groups[1].strip()
            
        valid_levels = {"ERROR", "WARN", "WARNING", "INFO", "DEBUG"}

        # if level not in valid_levels:
        #     for valid_level in valid_levels:
        #         if valid_level in line.upper():
        #             level = valid_level
        #             break
        #     else:
        #         level = "INFO"

        if level not in valid_levels:
            level = next((vl for vl in valid_levels if vl in line.upper()), "INFO")
        
        return LogEntry(
            raw=line,
            level=level,
            message=message
        )
    
# классы -- наследники OutputHandler (паттерн Наблюдатель)

class ConsoleHandler(OutputHandler):
    """Обработчик для вывода в консоль."""

    def __init__(self, use_colors: bool = True):
        self.use_colors = use_colors
        from .formatter import ColorFormatter
        self.formatter = ColorFormatter(use_colors=use_colors)

    def handle(self, entry: LogEntry) -> None:
        """
        Выводит LogEntry в консоль.

        Args:
            entry: Объект LogEntry для вывода.
        """

        formatted_line = self.formatter(entry.level, entry.message)
        print(formatted_line)


class JsonFileHandler(OutputHandler):
    """Обработчик для записи логов в JSON файл."""

    def __init__(self, output_file: Path):
        self.output_file = Path(output_file)
        self._ensure_directory()

    def _ensure_directory(self) -> None:
        """Создаёт директорию для файла, если её нет."""
        self.output_file.parent.mkdir(parents=True, exist_ok=True)

    def handle(self, entry: LogEntry) -> None:
        """Записывает LogEntry в JSON файл."""

        data = entry.to_dict()

        with open(self.output_file, 'a', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
            f.write('\n') # каждая запись на новой строоке

class StatsCollector(OutputHandler):
    """Обработчик для сбора статистики."""

    def __init__(self):
        self.stats = {
            "total_lines" : 0,
            "lines_by_level" : {
                "ERROR" : 0,
                "WARN" : 0,
                "INFO" : 0,
                "DEBUG" : 0
            },
            "start_time" : None,
            "last_activity" : None
        }

    def handle(self, entry: LogEntry) -> None:
        """Обновляет статистику на основе LogEntry."""

        self.stats['total_lines'] += 1
        self.stats['lines_by_level'][entry.level] += 1
        self.stats['last_activity'] = datetime.now().isoformat()

        if self.stats["start_time"] is None:
            self.stats['start_time'] = datetime.now().isoformat()

    def get_stats(self) -> dict:
        return self.stats.copy()