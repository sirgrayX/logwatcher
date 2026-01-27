import sys
import os

# ====================================================
# 1. НАСТРОЙКА ПУТЕЙ - ДО ЛЮБЫХ ИМПОРТОВ!
# ====================================================

# Получаем абсолютные пути
current_file = os.path.abspath(__file__)  # tests/conftest.py
current_dir = os.path.dirname(current_file)  # tests/
project_root = os.path.dirname(current_dir)  # корень проекта (logwatcher/)
src_path = os.path.join(project_root, "src")

# Отладочная информация
print("=" * 60)
print("CONFTEST DEBUG INFO:")
print(f"Current file: {current_file}")
print(f"Current dir: {current_dir}")
print(f"Project root: {project_root}")
print(f"SRC path: {src_path}")
print(f"SRC exists: {os.path.exists(src_path)}")
print("=" * 60)

# Добавляем src в путь ДО любого импорта
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# ====================================================
# 2. НАСТРОЙКА ЛОГГИНГА
# ====================================================
import logging
logging.basicConfig(level=logging.WARNING)  # Уменьшаем шум тестов

# ====================================================
# 3. ТЕПЕРЬ ИМПОРТИРУЕМ ВСЁ ОСТАЛЬНОЕ
# ====================================================
import pytest
import tempfile
import time
from pathlib import Path
from typing import Generator, Optional

# ====================================================
# 4. ФИКСТУРЫ
# ====================================================

@pytest.fixture
def temp_log_file() -> Generator[Path, None, None]:
    """
    Создаёт временный лог-файл для тестов.
    Автоматически удаляется после теста.
    """
    with tempfile.NamedTemporaryFile(
        mode='w', 
        suffix='.log', 
        delete=False,
        encoding='utf-8'
    ) as f:
        f.write("""ERROR: Initial error 1
WARN: Initial warning 1
INFO: Initial info 1
DEBUG: Initial debug 1
""")
        temp_path = Path(f.name)
    
    yield temp_path
    
    # Удаляем после теста
    if temp_path.exists():
        try:
            temp_path.unlink()
        except (PermissionError, OSError):
            # Игнорируем ошибки удаления на Windows
            pass


@pytest.fixture
def watcher_config():
    """
    Возвращает конфигурацию для быстрого тестирования.
    """
    # Импортируем ТУТ, после настройки путей
    from logwatcher.watcher import WatcherConfig
    
    return WatcherConfig(
        check_interval=0.05,  # Быстро для тестов
        follow_rotation=False,
        collect_stats=True,
        max_retries=1,
        restart_on_error=False  # Отключаем для тестов
    )


@pytest.fixture
def basic_watcher(temp_log_file, watcher_config):
    """
    Создаёт базовый LogWatcher для тестов.
    """
    # Импортируем ТУТ, после настройки путей
    from logwatcher.watcher import LogWatcher
    
    watcher = LogWatcher(
        filename=temp_log_file,
        min_level="INFO",
        use_colors=False,
        config=watcher_config
    )
    
    return watcher


@pytest.fixture
def mock_watcher():
    """
    Создаёт мок-объект LogWatcher для тестов.
    """
    from unittest.mock import MagicMock
    from logwatcher.watcher import LogWatcher
    
    mock = MagicMock(spec=LogWatcher)
    mock.filename = Path("/tmp/test.log")
    mock.min_level = "ERROR"
    mock.use_colors = False
    mock.is_running.return_value = False
    mock.lines_processed = 0
    mock.errors_found = 0
    
    return mock


# ====================================================
# 5. ДОПОЛНИТЕЛЬНЫЕ ФИКСТУРЫ
# ====================================================

@pytest.fixture
def sample_log_lines():
    """
    Возвращает примеры строк логов для тестирования парсинга.
    """
    return [
        "ERROR: Database connection failed",
        "[WARN] Disk space is low",
        "INFO: User logged in successfully",
        "DEBUG: Processing request ID 12345",
        "Some random message without level",
    ]


@pytest.fixture
def running_watcher(basic_watcher):
    """
    Создаёт запущенный watcher для интеграционных тестов.
    """
    import threading
    
    # Запускаем в фоновом потоке
    def run():
        basic_watcher.start()
    
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    
    # Даём время на запуск
    time.sleep(0.1)
    
    yield basic_watcher
    
    # Останавливаем после теста
    basic_watcher.stop()
    time.sleep(0.1)


# ====================================================
# 6. ХУКИ pytest
# ====================================================

def pytest_sessionstart(session):
    """
    Вызывается в начале сессии тестирования.
    """
    print("\n" + "=" * 60)
    print("НАЧАЛО ТЕСТИРОВАНИЯ")
    print("=" * 60)


def pytest_sessionfinish(session, exitstatus):
    """
    Вызывается в конце сессии тестирования.
    """
    print("\n" + "=" * 60)
    print(f"ТЕСТИРОВАНИЕ ЗАВЕРШЕНО. Статус: {exitstatus}")
    print("=" * 60)


# ====================================================
# 7. ПРОВЕРКА ИМПОРТА ПРИ ЗАГРУЗКЕ
# ====================================================

# Проверяем что импорты работают
try:
    from logwatcher.watcher import LogWatcher, WatcherConfig
    from logwatcher.formatter import ColorFormatter
    from logwatcher.logger import get_logger
    
    print("✅ Все импорты работают корректно")
    
except ImportError as e:
    print(f"❌ Ошибка импорта при загрузке conftest.py: {e}")
    print(f"Текущий sys.path: {sys.path}")
    raise