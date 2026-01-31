import os
import time
from pathlib import Path
from typing import List, Optional
from enum import Enum
from dataclasses import dataclass

from h11 import Event

from .models import LogEntry, LogParser, OutputHandler, RegexLogParser
from .formatter import ColorFormatter
from .logger import get_logger

logger = get_logger()

class WatcherState(Enum):
    """Состояния мониторинга."""
    STOPPED = 'stopped'
    RUNNING = 'running'
    PAUSED = 'paused'
    ERROR = 'error'

@dataclass
class WatcherConfig:
    """Конфигурация для LogWatcher"""
    use_colors=False,
    check_interval: float = 0.1
    follow_rotation: bool = True
    encoding: str = 'utf-8'
    buffer_size: int = 4096

    # обработка ошибок
    restart_on_error: bool = True
    max_retries: int = 3
    retry_delay: float = 0.1

    collect_stats: bool = True
    
    def validate(self) -> None:
        """Валидация конфигурации."""
        if self.check_interval <= 0:
            raise ValueError("check_interval must be positive")
        if self.max_retries < 0:
            raise ValueError("max_retries can\'t be negative")
        if self.retry_delay < 0:
            raise ValueError("retry_delay can\'t be negative")


class LogWatcher:
    """
    Класс для слежения за файлом логов.
    """

    def __init__(
            self,
            filename: str | Path,
            min_level: str = "WARN",
            parser: Optional[LogParser] = None,
            handlers: Optional[List[OutputHandler]] = None,
            config: Optional[WatcherConfig] = None
    ):
        """
        Args:
            filename (Path | str): Путь к файлу для мониторинга
            parser (LogParser): Парсер для строк логов
            handlers: Список обработчиков для уведомления
            config: Конфигурация мониторинга
        """
        self.filename = Path(filename)
        self.min_level = min_level,
        self.parser = parser or RegexLogParser()
        self.handlers = handlers or []
        self.config = config or WatcherConfig()
        self.config.validate()


        self._state = WatcherState.STOPPED
        self._file = None
        self._inode = None
        self._stop_requested = False

        self._retry_count = 0

        logger.debug(f"Создан LogWatcher для файла {self.filename}")


    def add_handler(self, handler: OutputHandler) -> None:
        """
        Добавляет обработчик в список наблюдателей.

        Args:
            handler (OutputHandler): Обработчик для добавления.
        """

        self.handlers.append(handler)
        logger.debug(f"Добавлен обработчик: {handler.__class__.__name__}")

    def remove_handler(self, handler: OutputHandler) -> None:
        """
        Удаляет обработчик из списка наблюдателей.

        Args:
            handler (OutputHandler): Обработчик для удаления.
        """

        if handler in self.handlers:
            self.handlers.remove(handler)
            logger.debug(f"Удалён обработчик: {handler.__class__.__name__}")

    def _notify_handlers(self, entry: LogEntry | Event) -> None:
        """Уведомляет все обраюотчики о новой LogEntry или Event."""

        for handler in self.handlers:
            try:
                handler.handle(entry)
            except Exception as e:
                logger.error(f"Ошибка в обработчике {handler.__class__.__name__}: {e}")

    def _process_line(self, line: str) -> None:
        """
        Обрабатывает строку лога.

        Args:
            line: строка лога для обработки.
        """

        try:
            entry: LogEntry = self.parser.parse(line)
            entry.src = str(self.filename)
            self._notify_handlers(entry)
        except Exception as e:
            logger.error(f"Ошибка обработки строки: {e}", exc_info=True)
        
    def _open_file(self) -> None:
        if self._file and not self._file.closed:
            self._file.close()
            logger.debug("Закрыт предыдущий файловый дескриптор")
        try:
            self._file = open(self.filename, 'r', encoding=WatcherConfig.encoding, errors='ignore')
            self._file.seek(0, os.SEEK_END)
            self._inode = os.stat(self.filename).st_ino

            logger.debug(f"Файл {self.filename} открыт: {self._inode}")
        except Exception as e:
            logger.error(f"Ошибка открытия файла {self.filename}: {e}")
            raise
    
    def _check_rotation(self) -> bool:
        try:
            current_inode = os.stat(self.filename).st_ino
            current_size = os.path.getsize(self.filename)

            if current_inode != self._inode:
                from .models import FileRotationEvent
                event = FileRotationEvent(
                    filename=str(self.filename),
                    old_inode=self._inode,
                    new_inode=current_inode
                )

                self._notify_handlers(event)
            return current_inode != self._inode
        except FileNotFoundError:
            logger.error(f"Файл {self.filename} временно отсутствует.")
            return False
    
    def _read_new_data(self) -> None:
        current_position = self._file.tell()
        file_size = os.path.getsize(self.filename)
            
        if current_position > file_size:
            logger.info("Файл усечен, перемещаюсь в начало")
            self._file.seek(0)
        else:
            self._file.seek(current_position)

        line = self._file.readline()
        if line:
            self._process_line(line.rstrip('\n\r'))

    def _handle_read_error(self) -> None:
        if self.config.restart_on_error:
            self._retry_count += 1
            
            if self._retry_count < self.config.max_retries:
                logger.warning("Попытка перезапуска мониторинга %d/%d через %.1f сек",
                            self._retry_count, self.config.max_retries, self.config.retry_delay)
                time.sleep(self.config.retry_delay)

                try:
                    self._open_file()
                    logger.info("Мониторинг успешно перезапущен!")
                except Exception as e:
                    logger.error(f"Не удалось перезапустить процесс мониторинга: {e}")
            else:
                logger.error(f"Достигнуто максимум попыток перезапуска: {self.config.max_retries}")
                self._state = WatcherState.ERROR
                self._stop_requested = True

    def start(self) -> None:
        """
        Запускает мониторинг файла
        """
        if not self.filename.exists():
            logger.error(f"Файл не найден {self.filename}")
            raise FileNotFoundError(f"{self.filename} не найден!")
        
        self._state = WatcherState.RUNNING
        self._stop_requested = False

        logger.info(f"Запуск мониторинга файла: {self.filename}")
        logger.info(f"Минимальный уровень: {self.min_level}")
        logger.info(f"Конфигурация: interval=%.2fs, rotation=%s",
                   self.config.check_interval, self.config.follow_rotation)

        try:
            self._open_file()
            
            while not self._stop_requested and self._state == WatcherState.RUNNING:
                try:
                    # обработка состояния паузы
                    if self._state == WatcherState.PAUSED:
                        time.sleep(self.config.check_interval)
                        continue

                    # если была ротация файла логов
                    if self.config.follow_rotation and self._check_rotation():
                        logger.info("Переоткрываю файл после ротации")
                        # self.stats['rotations_detected'] += 1
                        # добавить подсчёт ротаций файла
                        self._open_file()

                    self._read_new_data()

                    self._retry_count = 0

                except (IOError, OSError) as e:
                    logger.error(f"Ошибка чтения файла: {e}")
                    self._handle_read_error()
                time.sleep(self.config.check_interval)

        except KeyboardInterrupt:
            logger.info("Мониторинг прерван пользователем")
        except Exception as e:
            logger.error(f"Ошибка при исполнении процесса мониторинга {e}", exc_info=True)
            self._state = WatcherState.ERROR
            # добавить обработку подсчёта ошибок самой программы
            raise
        finally:
            self.stop()
    
    def pause(self) -> None:
        """Приостанавливает мониторинг, сохраняя текущую позицию в файле"""
        if self._state != WatcherState.RUNNING:
            logger.warning(f"Нельзя приостановить: состояние {self._state}")
            return
        self._state = WatcherState.PAUSED
        logger.info("Мониторинг приостановлен")

    def resume(self) -> None:
        """Возобновляет мониторинг с сохранённой позиции"""
        if self._state != WatcherState.PAUSED:
            logger.warning(f"Нельзя возобновить: состояние {self._state}")
            return
        self._state = WatcherState.RUNNING
        logger.info("Мониторинг возобновлён")

    def stop(self) -> None:
        """
        Останавливает мониторинг файлов
        """
        if self._file and not self._file.closed:
            self._file.close()
            logger.debug(f"Файл {self.filename} закрыт.")
        self._stop_requested = True
        self._state = WatcherState.STOPPED

        if 

    def is_running(self) -> bool:
        """
        Проверяет, работает ли мониторинг
        """
        return self._state == WatcherState.RUNNING
    
