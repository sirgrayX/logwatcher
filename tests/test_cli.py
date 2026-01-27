import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

from logwatcher.cli import parse_args, validate_args, create_watcher, main


class TestCLIParsing:
    """Тесты парсинга аргументов CLI."""
    
    def test_parse_args_basic(self):
        """Тест базового парсинга аргументов."""
        test_args = ["test.log", "--level", "WARN", "--no-colors"]
        
        args = parse_args(test_args)
        
        assert args.file == Path("test.log")
        assert args.level == "WARN"
        assert args.use_colors is False
        assert args.stats is False
    
    def test_parse_args_defaults(self):
        """Тест значений по умолчанию."""
        test_args = ["test.log"]
        
        args = parse_args(test_args)
        
        assert args.level == "ERROR"  # по умолчанию
        assert args.use_colors is True
        assert args.interval == 0.1
    
    def test_parse_args_with_stats(self):
        """Тест парсинга с опцией статистики."""
        test_args = ["app.log", "--stats", "--interval", "0.5"]
        
        args = parse_args(test_args)
        
        assert args.stats is True
        assert args.interval == 0.5


class TestCLIValidation:
    """Тесты валидации аргументов CLI."""
    
    def test_validate_args_success(self, temp_log_file):
        """Тест успешной валидации."""
        class Args:
            file = temp_log_file
            interval = 0.1
        
        args = Args()
        
        result = validate_args(args)
        assert result is True
    
    def test_validate_args_file_not_found(self):
        """Тест валидации с несуществующим файлом."""
        class Args:
            file = Path("/tmp/nonexistent_12345.log")
            interval = 0.1
        
        args = Args()
        
        result = validate_args(args)
        assert result is False
    
    def test_validate_args_not_a_file(self, tmp_path):
        """Тест валидации когда путь не файл."""
        directory = tmp_path / "not_a_file"
        directory.mkdir()
        
        class Args:
            file = directory
            interval = 0.1
        
        args = Args()
        
        result = validate_args(args)
        assert result is False
    
    def test_validate_args_invalid_interval(self, temp_log_file):
        """Тест валидации с невалидным интервалом."""
        class Args:
            file = temp_log_file
            interval = -1  # невалидный
        
        args = Args()
        
        result = validate_args(args)
        assert result is False


class TestCLIFunctions:
    """Тесты функций CLI."""
    
    def test_create_watcher(self, temp_log_file):
        """Тест создания watcher через фабрику."""
        class Args:
            file = temp_log_file
            level = "WARN"
            use_colors = False
            interval = 0.2
        
        args = Args()
        
        watcher = create_watcher(args)
        
        assert watcher.filename == temp_log_file
        assert watcher.min_level == "WARN"
        assert watcher.use_colors is False
    
    @patch('logwatcher.cli.LogWatcher')
    def test_main_success(self, MockWatcher, temp_log_file):
        """Тест успешного выполнения main()."""

        mock_watcher_instance = MagicMock()
        MockWatcher.return_value = mock_watcher_instance
        
        # запуск main с тестовыми аргументами
        sys.argv = ['logwatcher', str(temp_log_file), '--level', 'INFO']
        
        with patch.object(mock_watcher_instance, 'start'):
            result = main()
        
        assert result == 0
        MockWatcher.assert_called_once()
        mock_watcher_instance.start.assert_called_once()
    
    @patch('logwatcher.cli.LogWatcher')
    def test_main_keyboard_interrupt(self, MockWatcher, temp_log_file):
        """Тест обработки KeyboardInterrupt в main()."""
        mock_watcher_instance = MagicMock()
        mock_watcher_instance.start.side_effect = KeyboardInterrupt
        MockWatcher.return_value = mock_watcher_instance
        
        sys.argv = ['logwatcher', str(temp_log_file)]
        
        result = main()
        
        assert result == 130  # Код для Ctrl+C
    
    def test_main_file_not_found(self):
        """Тест main() с несуществующим файлом."""
        sys.argv = ['logwatcher', '/tmp/nonexistent_98765.log']
        
        result = main()
        
        assert result == 1  #