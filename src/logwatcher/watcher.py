import os
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from .formatter import ColorFormatter
from .logger import get_logger

logger = get_logger()


@dataclass
class WatcherConfig:
    """
    Конфигурация для LogWatcher
    """
    check_interval: float = 0.1
    follow_symlinks: bool = False
    buffer_size: int = 4096
    encoding: str = 'utf-8'
    errors: str = "ignore"
    restart_on_rotation: bool = True



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
        """
        self.filename = Path(filename)
        self.min_level = min_level,
        self.use_colors = use_colors,
        self.cofig = config or WatcherConfig()

        self._file = None
        self._running = False
        self._inode = None

        self.formatter = ColorFormatter(use_colors=use_colors)
        
        # статистика обработки
        self.lines_processed = 0
        self.errors_found = 0

        logger.debug(f"Создан LogWatcher для файла {self.filename}")

    def _open_file(self) -> None:
        if self._file and not self._file.closed:
            self._file.close()
            logger.debug("Закрыт предыдущий файловый дескриптор")
        
        self._file = open(self.filename, 'r', encoding='utf-8', errors='ignore')
        self._file.seek(0, os.SEEK_END)
        self._inode = os.stat(self.filename).st_ino

        logger.debug(f"Файл {self.filename} открыт: {self._inode}")

    def _check_rotation(self) -> bool:
        try:
            current_inode = os.stat(self.filename).st_ino
        except FileNotFoundError:
            logger.error(f"Файл {self.filename} временно отсутствует.")
            return False
        if current_inode != self._inode:
            logger.debug(f"Обнаружена ротация файла {self.filename}")
            return True
        return False
    
    def _process_line(self, line: str) -> None:
        try:
            detected_level, message = self.formatter.extract_level(line)
            if self.formatter.should_show(detected_level, self.min_level):
                formatted_line = self.formatter(detected_level, message)
                print(formatted_line)

                self.lines_processed += 1
                if detected_level == "ERROR":
                    self.errors_found += 1
        except Exception as e:
            logger.error(f"Ошибка обработки строки: {e}", exc_info=True)

    def start(self) -> None:
        """
        Запускает мониторинг файла
        """
        if not self.filename.exists():
            logger.error(f"Файл не найден {self.filename}")
            raise FileNotFoundError(f"{self.filename} не найден!")
        
        self._running = True

        logger.info(f"Запуск мониторинга файла {self.filename}")
        logger.info(f"Минимальный уровень {self.min_level}")
        logger.info(f"Цвета: {'включены' if self.use_colors else 'выключены'}\n")

        try:
            self._open_file()
            
            if self._check_rotation():
                logger.info("Переоткрываю файл после ротации")
                self._open_file()
            
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
            else:
                time.sleep(0.1)

        except KeyboardInterrupt:
            logger.info("Мониторинг прерван пользователем")
        except Exception as e:
            logger.error(f"Ошибка при исполнении процесса мониторинга {e}", exc_info=True)
            raise
        finally:
            self.stop()


    def stop(self) -> None:
        """
        Останавливает мониторинг файлов
        """
        if self._file and not self._file.closed:
            self._file.close()
            logger.debug(f"Файл {self.filename} закрыт.")
        self._running = False

        logger.info(
            "Мониторинг остановлен. Обработано строк: %d, ошибок найдено: %d",
            self.lines_processed,
            self.errors_found
        )

    def is_running(self) -> bool:
        """
        Проверяет, работает ли мониторинг
        """
        return self._running
    
