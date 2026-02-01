from typing import Dict, ClassVar, Any, Literal

class ColorFormatter:

    COLORS: ClassVar[Dict[str, str]] = {
        "ERROR" : "\033[91m", # красный
        "WARN" : "\033[93m",  # жёлтый
        "INFO" : "\033[92m",  # зелёный
        "DEBUG" : "\033[94m"  # синий
    }

    RESET: ClassVar[str] = "\033[0m"

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