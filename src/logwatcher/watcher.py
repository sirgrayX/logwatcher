import os
import time
from pathlib import Path
from typing import Optional
from enum import Enum
from dataclasses import dataclass
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
            min_level: str = "ERROR",
            use_colors: bool = True,
            config: Optional[WatcherConfig] = None
    ) -> None:
        """
        :param filename: Путь к файлу для мониторинга
        :param min_level: Минимальный уровень логирования (ERROR, WARN, INFO, DEBUG)
        :param use_colors: Использовать цветной вывод
        :param config: Конфигурация мониторинга (опционально)
        """
        self.filename = Path(filename)
        self.min_level = min_level
        self.use_colors = use_colors


        self.config = config or WatcherConfig()
        self.config.validate()

        self._state = WatcherState.STOPPED
        self._file = None
        self._inode = None
        self._stop_requested = False

        self.formatter = ColorFormatter(use_colors=use_colors)
        
        # статистика обработки
        self.stats = {
            "start_time" : None,
            "total_lines" : 0,
            "lines_by_level" : {
                "ERROR" : 0,
                "WARN"  : 0,
                "INFO"  : 0,
                "DEBUG" : 0
            },
            "rotations_detected" : 0,
            "errors_occurred" : 0,
            "last_activity" : None
        }

        self._retry_count = 0

        logger.debug(f"Создан LogWatcher для файла {self.filename}")

    def _open_file(self) -> None:
        if self._file and not self._file.closed:
            self._file.close()
            logger.debug("Закрыт предыдущий файловый дескриптор")
        try:
            self._file = open(self.filename, 'r', encoding='utf-8', errors='ignore')
            self._file.seek(0, os.SEEK_END)
            self._inode = os.stat(self.filename).st_ino

            logger.debug(f"Файл {self.filename} открыт: {self._inode}")
        except Exception as e:
            logger.error(f"Ошибка открытия файла {self.filename}: {e}")
            raise

    def _update_stats(self, level: str) -> None:
        """Обновляет статистику мониторинга"""
        self.stats["total_lines"] += 1
        if level in self.stats['lines_by_level']:
            self.stats['lines_by_level'][level] += 1
        self.stats['last_activity'] = time.time()
    
    def _check_rotation(self) -> bool:
        try:
            current_inode = os.stat(self.filename).st_ino
            return current_inode != self._inode
        except FileNotFoundError:
            logger.error(f"Файл {self.filename} временно отсутствует.")
            return False
    
    def _process_line(self, line: str) -> None:
        try:
            detected_level, message = self.formatter.extract_level(line)
            if self.formatter.should_show(detected_level, self.min_level):
                formatted_line = self.formatter(detected_level, message)
                print(formatted_line)

                # обновить статистику при обработке строки файла
                self._update_stats(detected_level)

        except Exception as e:
            logger.error(f"Ошибка обработки строки: {e}", exc_info=True)
            self.stats['errors_occurred'] += 1


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
        self.stats['errors_occurred'] += 1
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
        
        # self._running = True
        self._state = WatcherState.RUNNING
        self._stop_requested = False
        self.stats['start_time'] = time.time()

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
                        self.stats['rotations_detected'] += 1
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

        if self.stats['start_time']:
            duration_time = time.time() - self.stats['start_time']
            logger.info("Мониторинг остановлен. Длительность: %.1f сек", duration_time)

            if self.config.collect_stats:
                self._log_stats()


    def get_stats(self) -> dict:
        """
        Возвращает статистику мониторинга.
        
        Returns:
            Словарь со статистикой
        """
        stats = self.stats.copy()
        
        # Добавляем вычисляемые поля
        if stats["start_time"]:
            stats["duration"] = time.time() - stats["start_time"]
        
        stats["state"] = self._state.value
        stats["config"] = {
            "check_interval": self.config.check_interval,
            "follow_rotation": self.config.follow_rotation,
        }
        
        return stats

    def _log_stats(self) -> None:
        """Логирует статистику."""
        stats = self.get_stats()
        
        logger.info("=== Статистика мониторинга ===")
        logger.info("Всего строк: %d", stats["total_lines"])
        logger.info("По уровням:")
        for level, count in stats["lines_by_level"].items():
            if count > 0:
                logger.info("  %s: %d", level, count)
        
        if stats["rotations_detected"] > 0:
            logger.info("Ротаций обнаружено: %d", stats["rotations_detected"])
        
        if stats["errors_occurred"] > 0:
            logger.info("Ошибок произошло: %d", stats["errors_occurred"])
        
        if "duration" in stats:
            logger.info("Длительность: %.1f сек", stats["duration"])



    def is_running(self) -> bool:
        """
        Проверяет, работает ли мониторинг
        """
        return self._state == WatcherState.RUNNING
    
