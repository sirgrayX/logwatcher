
from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path
import re
from re import Pattern
from typing import Optional, Any, Dict
from abc import ABC, abstractmethod

from mistune import InlineState


@dataclass(kw_only=True)
class Event(ABC):
    """
    Абстрактный базовый класс для всех событий системы.

    Все события должны:
    1. Иметь временную метку;
    2. Уметь сериализовываться в словарь/JSON;
    3. Иметь строковое представление.
    """
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.__class__.__name__,
            "timestamp": self.timestamp.isoformat(),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)
    
    @property
    def is_log_entry(self) -> bool:
        return isinstance(self, LogEntry)
    
    @property
    def is_system_event(self) -> bool:
        return isinstance(self, SystemEvent)
    
    def __str__(self) -> str:
        return f"[{self.__class__.__name__}]: {self.timestamp}"


@dataclass(kw_only=True)
class LogEntry(Event):
    """
    Data Transfer Object (DTO) для строки лога.
    Содержит только данные лога, больше ничего.

    Args:
        raw_message (str): Исходная строка лога из файла;
        parsed_message (str): Текст сообщения;
        level (str): Уровень логирования (ERROR, WARN, INFO, DEBUG);
        src (str): Источник лога (имя файла или сервиса)
    """
    raw_message: str
    level: str
    parsed_message: Optional[str] = None
    src: str = "unknown"
    
    def __post_init__(self):
        if self.parsed_message is None:
            self.parsed_message = self.raw_message
        
    def to_dict(self) -> Dict[str, Any]:
        base_dict = super().to_dict()

        base_dict.update({
            'raw_message' : self.raw_message,
            'parsed_message' : self.parsed_message,
            'level' : self.level,
            'src' : self.src
        })

        return base_dict
    
    def __str__(self) -> str:
        return f"[{self.level}]: {self.parsed_message or self.raw_message}"
    
class SystemEvent(Event):
    """Базовый класс для системных событий."""

    def __init__(self, 
                 event_type: str, 
                 data: Optional[Dict[str, Any]] = None,
                 **kwargs):
        """
        Args:
            event_type: Тип события (file_rotation, error и т.д.)
            data: Данные события
            **kwargs: Дополнительные параметры для базового класса
        """

        super().__init__(**kwargs)
        self.event_type = event_type
        self.data = data or {}

    def to_dict(self) -> Dict[str, Any]:
        base_dict = super().to_dict()
        base_dict.update({
            "event_type": self.event_type,
            "data": self.data,
        })
        return base_dict

    def __str__(self) -> str:
        """Строковое представление SystemEvent."""
        return f"[SYSTEM:{self.event_type}] {self.data}"
        

@dataclass
class FileRotationEvent(SystemEvent):
    """Событие ротации файла."""
    
    filename: str
    old_inode: Optional[int] = None
    new_inode: Optional[int] = None
    
    def __post_init__(self):
        super().__init__(
            event_type="file_rotation",
            data={
                "filename": self.filename,
                "old_inode": self.old_inode,
                "new_inode": self.new_inode
            }
        )
    
    def __str__(self) -> str:
        return f"[ROTATION] {self.filename} (inode: {self.old_inode} → {self.new_inode})"
    
@dataclass
class FileErrorEvent(SystemEvent):
    """Событие ошибки файла."""
    
    filename: str
    error: str
    
    def __post_init__(self):
        super().__init__(
            event_type="file_error",
            data={
                "filename": self.filename,
                "error": self.error
            }
        )
    
    def __str__(self) -> str:
        return f"[FILE_ERROR] {self.filename}: {self.error}"
    

@dataclass
class WatcherStateEvent(SystemEvent):
    """Событие изменения состояния watcher."""
    
    watcher_id: str
    old_state: str
    new_state: str
    
    def __post_init__(self):
        super().__init__(
            event_type="watcher_state_change",
            data={
                "watcher_id": self.watcher_id,
                "old_state": self.old_state,
                "new_state": self.new_state
            }
        )
    
    def __str__(self) -> str:
        return f"[STATE] {self.watcher_id}: {self.old_state} → {self.new_state}"


        
class LogParser(ABC):
    """Абстрактный класс парсера логов."""

    @abstractmethod
    def parse(self, line: str) -> LogEntry:
        pass

class OutputHandler(ABC):
    """Абстрактный класс обработчика вывода."""

    @abstractmethod
    def handle(self, 
               entry: LogEntry) -> None:
        """
        Обрабатывает LogEntry.
        Вызывается при получении новой строки лога.

        Args:
            entry (LogEntry): Объект LogEntry для обработки
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

        if level not in valid_levels:
            level = next((vl for vl in valid_levels if vl in line.upper()), "INFO")
        
        return LogEntry(
            raw_message=line,
            level=level,
            parsed_message=message
        )
    
# классы -- наследники OutputHandler (паттерн Наблюдатель)

class ConsoleHandler(OutputHandler):
    """Обработчик для вывода в консоль."""

    def __init__(self, use_colors: bool = True, min_level: str = "WARN"):
        self.min_level = min_level
        from .formatter import ColorFormatter
        self.formatter = ColorFormatter(use_colors=use_colors)

    def handle(self, entry: LogEntry) -> None:
        """
        Выводит LogEntry в консоль.

        Args:
            entry: Объект LogEntry для вывода.
        """
        if isinstance(entry, LogEntry):
            formatted_line = self.formatter(entry.level, entry.parsed_message)
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

        if isinstance(entry, LogEntry):
            data = entry.to_dict()

            with open(self.output_file, 'a', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
                f.write('\n') # каждая запись на новой строоке


class StatsCollector(OutputHandler):
    """Обработчик для сбора статистики."""

    def __init__(self):
        self.stats = {
            "log_entries" : {
                "total_lines" : 0,
                "lines_by_level" : {
                    "ERROR" : 0,
                    "WARN" : 0,
                    "INFO" : 0,
                    "DEBUG" : 0,
                },
                "by_source" : {}
            },
            "system_events" : {
                "total_events" : 0,
                "by_type" : {},
                "recent" : [] # последние для отладки
            },
            "timing" : {
                "start_time" : None,
                "last_error" : None
            }
        }

    def handle(self, entry: Event) -> None:
        if isinstance(entry, LogEntry):
            self._handle_log_entry(entry)
        elif isinstance(entry, SystemEvent):
            self._handle_system_event(entry)
        else:
            # Неизвестный тип события
            self.stats["system_events"]["by_type"].setdefault("unknown", 0)
            self.stats["system_events"]["by_type"]["unknown"] += 1

    def _handle_log_entry(self, entry: LogEntry) -> None:
        """Обрабатывает запись лога."""

        # подсчёт количества записей
        self.stats["log_entries"]["total_lines"] += 1

        # подсчёт записей конкретного вида
        level = entry.level.upper()
        if level in self.stats["log_entries"]["lines_by_level"]:
            self.stats["log_entries"]["lines_by_level"][level] += 1
        else:
            self.stats["log_entries"]["lines_by_level"][level] = 1

        # сколько записей для конкретного файла обработали
        source = entry.src
        if source not in self.stats["log_entries"]["by_source"]:
            self.stats["log_entries"]["by_source"][source] = 0
        self.stats["log_entries"]["by_source"][source] += 1


    def _handle_system_event(self, event: SystemEvent) -> None:
        """Обрабатывает системное событие."""

        self.stats["system_events"]["total_events"] += 1

        # статистика по типам событий
        event_type = event.event_type
        if event_type not in self.stats["system_events"]["by_type"]:
            self.stats["system_events"]["by_type"][event_type] = 0
        self.stats["system_events"]["by_type"][event_type] += 1

        # для отладки (последние 20 событий)
        self.stats["system_events"]["recent"].append({
            "type": event_type,
            "timestamp": event.timestamp.isoformat(),
            "data": event.data
        })

        if len(self.stats["system_events"]["recent"]) > 20:
            self.stats["system_events"]["recent"].pop(0)

        # обрабатываем тайминги
        if self.stats["timing"]["start_time"] is None:
            if isinstance(event, WatcherStateEvent):
                if event.data['new_state'] == 'running':
                    self.stats["timing"]["start_time"] = event.timestamp
        
        if isinstance(event, FileErrorEvent):
            self.stats["timing"]["last_error"] = event.timestamp

    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику."""

        import copy
        stats = copy.deepcopy(self.stats)
        
        # Добавляем вычисляемые поля
        if stats["timing"]["start_time"]:
            duration = datetime.now() - stats["timing"]["start_time"]
            stats["duration_seconds"] = duration.total_seconds()
        
        return stats