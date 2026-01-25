import logging
import sys
from pathlib import Path
from typing import Optional

_global_logger: Optional[logging.Logger] = None

def setup_basic_logger(level:str = "INFO") -> logging.Logger:
    """
    Создаёт и настраивает базовый логгер.

    Агрументы:
        level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Возвращает:
        Настроенный объект логгера
    """

    logger = logging.getLogger('logwatcher')
    level_num = getattr(logging, level.upper())
    logger.setLevel(level_num)

    if not logger.handlers:
        console_handler = logging.StreamHandler(sys.stdout)

        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S' 
        )
        console_handler.setFormatter(formatter)
        console_handler.setLevel(level_num)
        logger.addHandler(console_handler)
    
    return logger


def get_logger() -> logging.Logger:
    """
    Получает глобальный логгер.
    Если логгер ещё не создан, создаёт его с настройками по умолчанию.

    Возвращает:
        Глобальный объект логгера.
    """

    global _global_logger

    if _global_logger is None:
        _global_logger = setup_basic_logger()

    return _global_logger

