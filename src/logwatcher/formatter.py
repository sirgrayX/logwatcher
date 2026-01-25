from typing import Dict, ClassVar, Any, Literal

class ColorFormatter:

    COLORS: ClassVar[Dict[str, str]] = {
        "ERROR" : "\033[91m", # красный
        "WARN" : "\033[93m",  # жёлтый
        "INFO" : "\033[92m",  # зелёный
        "DEBUG" : "\033[94m"  # синий
    }

    RESET: ClassVar[str] = "\033[0m"

    LEVEL_PRIORITY: ClassVar[Dict[str, int]] = {
        'DEBUG': 0,
        'INFO' : 1,
        'WARN' : 2,
        'ERROR': 3
    }

    def __init__(self, use_colors=True):
        self.use_colors = use_colors

    def __call__(self, level, message):
        if self.use_colors and level in self.COLORS:
            color = self.COLORS[level]
            return f"{color}[{level}] {message}{self.RESET}"
        return f"[{level}] {message}"

    def extract_level(self, line) -> tuple[str, Any] | tuple[Literal['INFO'], Any]:
        """
        Пытается найти уровень лога в строке.
        Возвращает (уровень, сообщение).
        """

        line_upper = line.upper()

        for level in self.COLORS:
            if level in line_upper:
                start_idx = line_upper.find(level)
                message = line_upper[start_idx + len(level):].lstrip(' :[]')
                return level, message
        return "INFO", line
    
    def should_show(self, detected_level : str, min_level: str = "DEBUG") -> bool:
        detected_lvl_priority = self.LEVEL_PRIORITY.get(detected_level, 0)
        min_lvl_priority = self.LEVEL_PRIORITY.get(min_level, 3)
        return True if detected_lvl_priority >= min_lvl_priority else False