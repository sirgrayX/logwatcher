import os
import time
from typing import Callable
from .formatter import ColorFormatter

def tail_file(filename: str, callback: Callable[[str], None]):
    """
    Читает файл с конца и вызывает callback для новых строк

    Args:
        filename: Путь к файлу для слежения
        callback: Функция, которая вызывается для каждой новой строки
    """
    
    with open(filename, 'r', encoding='utf-8') as file:
        file.seek(0, os.SEEK_END)

        while True:
            current_position = file.tell()
            file_size = os.path.getsize(filename)

            # если файл уменьшился
            if file_size < current_position:
                file.seek(0)
            else:
                file.seek(current_position)

            line = file.readline()
            if line:
                callback(line.rstrip('\n'))
            else:
                time.sleep(0.1)

def watch_file(filename: str, level_filter: str = "ERROR"):
    formatter = ColorFormatter()

    def process_line(line: str):
        detected_level, message = formatter.extract_level(line)

        priority = {
            "ERROR" : 3, "WARN" : 2, 
            "INFO" : 1, "DEBUG" : 0
            }
        filter_priority = priority.get(level_filter.upper(), 3)
        line_priority = priority.get(detected_level, 0)

        # показываем только если уровень >= фильтра
        if line_priority >= filter_priority:
            colored_line = formatter(detected_level, message)
            print(colored_line)

    print(f"Watching {filename} for {level_filter} and above...")
    print("Press Ctrl+C to stop")
    tail_file(filename, process_line)