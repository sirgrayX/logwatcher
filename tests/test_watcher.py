import sys
import os

current_file = os.path.abspath(__file__)
current_dir = os.path.dirname(current_file) 
project_root = os.path.dirname(current_dir) 
src_path = os.path.join(project_root, "src")

if src_path not in sys.path:
    sys.path.insert(0, src_path)

from logwatcher.watcher import LogWatcher, WatcherConfig, WatcherState

import threading
import time
import pytest
from pathlib import Path
from unittest.mock import patch


class TestLogWatcherInitialization:
    """Тесты инициализации LogWatcher."""

    def test_init_basic(self, temp_log_file) -> None:
        """Тест простой инициализации."""
        watcher = LogWatcher(
            filename=temp_log_file,
            min_level="WARN",
            use_colors=False
        )

        assert watcher.filename == temp_log_file
        assert watcher.min_level == 'WARN'
        assert watcher.use_colors is False
        assert watcher._state == WatcherState.STOPPED
        assert watcher.config is not None

    def test_init_with_config(self, temp_log_file, watcher_config) -> None:
        """Тест инициализации с кастомной конфигурацией"""

        watcher = LogWatcher(
            filename=temp_log_file,
            config=watcher_config
        )

        assert watcher.filename == temp_log_file
        assert watcher.config == watcher_config
        assert watcher.config.follow_rotation is False

    def test_init_file_not_exists(self) -> None:
        """Тест инициализации с несуществующим файлом."""
        # несуществующий фйл
        non_existent = Path("/tmp/nonexistent_file_12345.log")
        
        watcher = LogWatcher(filename=non_existent)
        
        # инициализация должна пройти, ошибка будет при start()
        assert watcher.filename == non_existent
        assert not watcher.filename.exists()
    
    def test_config_validation(self, temp_log_file) -> None:
        """Тест валидации конфигурации."""
        with pytest.raises(ValueError, match="check_interval must be positive"):
            WatcherConfig(check_interval=-1)
        
        with pytest.raises(ValueError, match="max_retries cannot be negative"):
            WatcherConfig(max_retries=-1)


class TestLOgWatcherStateManagement:
    """Тесты урпавления состянием."""

    def test_is_running(self, basic_watcher):
        assert basic_watcher.is_running() is False

        basic_watcher._state = WatcherState.RUNNING
        assert basic_watcher.is_running() is True

        basic_watcher._state = WatcherState.PAUSED
        assert basic_watcher.is_running() is False

    def test_pause_and_resume(self, basic_watcher):
        # нельзя поставить на паузу watcher, если он не работаеь
        basic_watcher.pause()
        assert basic_watcher._state == WatcherState.STOPPED

        basic_watcher._state = WatcherState.RUNNING
        basic_watcher.pause()
        assert basic_watcher._state == WatcherState.PAUSED

        # нельзя возобновить, если не на паузе
        basic_watcher._state = WatcherState.STOPPED
        basic_watcher.resume()
        assert basic_watcher._state == WatcherState.STOPPED

        basic_watcher._state = WatcherState.PAUSED
        basic_watcher.resume()
        assert basic_watcher._state == WatcherState.RUNNING


class TestLogWatcherFileOperations:
    """Тесты операций с файлами."""

    def test_open_file_success(self, basic_watcher, temp_log_file):
        """Тест успешного открытия файла."""

        basic_watcher._open_file()

        assert basic_watcher._file is not None
        assert not basic_watcher._file.closed
        assert basic_watcher._inode is not None

        # позиционирование в конце файла
        pos = basic_watcher._file.tell()
        file_size = temp_log_file.stat().st_size
        assert pos == file_size

        basic_watcher.stop()

    def test_open_file_not_found(self, basic_watcher):
        """Тест открытия несуществующего файла"""
        basic_watcher.filename = Path("/tmp/nonexistent_98765.log")

        with pytest.raises(FileNotFoundError):
            basic_watcher._open_file()

    def test_check_rotation_no_rotation(self, basic_watcher):
        """Тест проверки ротации (без ротации)."""
        basic_watcher._open_file()
        original_inode = basic_watcher._inode
        
        result = basic_watcher._check_rotation()
        assert result is False
        assert basic_watcher._inode == original_inode
        
        basic_watcher.stop()

    def test_check_rotation_with_rotation(self, basic_watcher, temp_log_file):
        """Тест проверки ротации (с изменением файла)."""
        basic_watcher._open_file()
        # original_inode = basic_watcher._inode
        
        temp_log_file.unlink()
        temp_log_file.write_text("ERROR: New file after rotation\n")
        
        result = basic_watcher._check_rotation()
        assert result is True  # Должен обнаружить ротацию
        
        basic_watcher.stop()

class TestLogWatcherLineProcessing:
    """Тесты обработки строк."""
    
    def test_process_line_success(self, basic_watcher):
        """Тест успешной обработки строки."""
        
        with patch('builtins.print') as mock_print:
            basic_watcher._process_line("ERROR: Test error message")
        
            mock_print.assert_called_once()
            
            assert basic_watcher.stats["total_lines"] == 1
            assert basic_watcher.stats["lines_by_level"]["ERROR"] == 1

    def test_process_line_filtering(self, basic_watcher):
        """Тест фильтрации по уровню."""
        basic_watcher.min_level = "WARN"
        
        with patch('builtins.print') as mock_print:
            # INFO должен быть отфильтрован
            basic_watcher._process_line("INFO: This should not appear")
            mock_print.assert_not_called()
            
            # WARN должен пройти
            basic_watcher._process_line("WARN: This should appear")
            mock_print.assert_called_once()

    def test_process_line_error(self, basic_watcher):
        """Тест обработки ошибки в строке."""
        with patch('logwatcher.watcher.ColorFormatter.extract_level') as mock_extract:
            mock_extract.side_effect = ValueError("Test error")
            
            # обработка должна не упасть, а залогировать ошибку
            basic_watcher._process_line("INVALID: Line")
            assert basic_watcher.stats["errors_occurred"] == 1

class TestLogWatcherStatistics:
    """Тесты статистики."""
    
    def test_get_stats_basic(self, basic_watcher) -> None:
        """Тест получения базовой статистики."""
        stats = basic_watcher.get_stats()
        
        assert "total_lines" in stats
        assert "lines_by_level" in stats
        assert "state" in stats
        assert "config" in stats
        assert stats["state"] == "stopped"

    def test_get_stats_after_processing(self, basic_watcher):
        """Тест статистики после обработки строк."""
        # Обрабатываем несколько строк
        basic_watcher._process_line("ERROR: Error 1")
        basic_watcher._process_line("WARN: Warning 1")
        basic_watcher._process_line("ERROR: Error 2")
        basic_watcher._process_line("INFO: Info 1")
        
        stats = basic_watcher.get_stats()
        
        assert stats["total_lines"] == 4
        assert stats["lines_by_level"]["ERROR"] == 2
        assert stats["lines_by_level"]["WARN"] == 1
        assert stats["lines_by_level"]["INFO"] == 1
        assert stats["lines_by_level"]["DEBUG"] == 0

    def test_stats_duration(self, basic_watcher):
        """Тест вычисления длительности."""
        basic_watcher.stats["start_time"] = time.time() - 5.0  # 5 секунд назад
        
        stats = basic_watcher.get_stats()
        
        assert "duration" in stats
        assert 4.9 < stats["duration"] < 5.1  # Примерно 5 секунд


class TestLogWatcherIntegration:
    """Интеграционные тесты."""

    def test_start_stop_basic(self, basic_watcher, temp_log_file) -> None:
        """Тест базового запуска и остановки."""
        # запускаем в отдельном потоке
        def run_watcher():
            basic_watcher.start()
        
        thread = threading.Thread(target=run_watcher, daemon=True)
        thread.start()
        
        time.sleep(0.1)
        
        assert basic_watcher._state == WatcherState.RUNNING

        basic_watcher.stop()
        time.sleep(0.1)
        
        assert basic_watcher._state == WatcherState.STOPPED
        assert basic_watcher._stop_requested is True

    def test_file_monitoring(self, temp_log_file):
        """Тест мониторинга файла с добавлением данных."""
        from logwatcher.watcher import LogWatcher, WatcherConfig
        
        config = WatcherConfig(check_interval=0.01, collect_stats=False)
        watcher = LogWatcher(temp_log_file, config=config)
        
        captured_lines = []
        original_process = watcher._process_line
        
        def capture_line(line):
            captured_lines.append(line)
            # вызываем оригинальный процесс для статистики
            original_process(line)
        
        watcher._process_line = capture_line

        thread = threading.Thread(target=watcher.start, daemon=True)
        thread.start()
        time.sleep(0.05)
        
        # добавляем новые данные в файл
        with open(temp_log_file, 'a') as f:
            f.write("ERROR: Newly added error\n")
            f.write("INFO: Newly added info\n")
        
        time.sleep(0.1)
        
        watcher.stop()
        time.sleep(0.05)
        
        # проверяем что новые строки были обработаны
        assert len(captured_lines) >= 2  
        assert any("Newly added error" in line for line in captured_lines)

    def test_error_handling_with_retries(self, temp_log_file):
        """Тест обработки ошибок с повторными попытками."""
        from logwatcher.watcher import LogWatcher, WatcherConfig
        
        config = WatcherConfig(
            check_interval=0.01,
            restart_on_error=True,
            max_retries=2,
            retry_delay=0.01
        )
        
        watcher = LogWatcher(temp_log_file, config=config)
        
        # считаем количество вызовов _open_file
        open_count = 0
        original_open = watcher._open_file
        
        def counting_open():
            nonlocal open_count
            open_count += 1
            if open_count == 1:
                raise IOError("Simulated read error")
            return original_open()
        
        watcher._open_file = counting_open
        
        thread = threading.Thread(target=watcher.start, daemon=True)
        thread.start()
        
        time.sleep(0.1)
        watcher.stop()
        time.sleep(0.05)
        
        # должно быть минимум 2 попытки открытия (1 ошибка + 1 успех)
        assert open_count >= 2

if __name__ == "__main__":
    pytest.main([__file__, "-v"])