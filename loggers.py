"""
Logging configuration module.
Provides unified logging functionality with multiple log levels and output formats.
"""

import os
import sys
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path


class ColoredFormatter(logging.Formatter):
    """Colored log formatter."""

    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # cyan
        'INFO': '\033[32m',       # green
        'WARNING': '\033[33m',    # yellow
        'ERROR': '\033[31m',      # red
        'CRITICAL': '\033[35m',   # purple
        'RESET': '\033[0m'        # reset
    }
    
    def format(self, record):
        # Get color
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']

        # Format record
        formatted = super().format(record)

        # Add color if output to terminal
        if hasattr(sys.stderr, 'isatty') and sys.stderr.isatty():
            return f"{color}{formatted}{reset}"
        return formatted


class LoggerManager:
    """Logger manager."""

    def __init__(self, logs_dir: str = "logs", base_name: str = "app"):
        self.logs_dir = Path(logs_dir)
        self.base_name = base_name
        self._loggers: Dict[str, logging.Logger] = {}

        # Create logs directory
        self._ensure_logs_directory()

        # Set up default logger configuration
        self._setup_default_logger()

    def _ensure_logs_directory(self):
        """Ensure logs directory exists."""
        self.logs_dir.mkdir(exist_ok=True)

        # Create subdirectories
        (self.logs_dir / "debug").mkdir(exist_ok=True)
        (self.logs_dir / "info").mkdir(exist_ok=True)
        (self.logs_dir / "error").mkdir(exist_ok=True)

    def _setup_default_logger(self):
        """Set up default logger."""
        # Remove all existing handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Set root log level
        root_logger.setLevel(logging.DEBUG)

    def get_logger(self, name: str, level: int = logging.INFO) -> logging.Logger:
        """Get logger by name."""
        if name in self._loggers:
            return self._loggers[name]

        logger = logging.getLogger(name)
        logger.setLevel(level)

        # Clear existing handlers
        logger.handlers.clear()

        # Add console handler
        console_handler = self._create_console_handler()
        logger.addHandler(console_handler)

        # Add file handler
        file_handler = self._create_file_handler(name, level)
        logger.addHandler(file_handler)

        # Add error file handler
        if level <= logging.ERROR:
            error_handler = self._create_error_handler(name)
            logger.addHandler(error_handler)

        # Prevent duplicate logs
        logger.propagate = False

        self._loggers[name] = logger
        return logger

    def _create_console_handler(self) -> logging.StreamHandler:
        """Create console handler."""
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)

        # Use colored formatter
        formatter = ColoredFormatter(
            fmt='%(asctime)s | %(name)s | %(levelname)s | %(filename)s:%(lineno)d | %(funcName)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)

        return handler

    def _create_file_handler(self, name: str, level: int) -> logging.FileHandler:
        """Create file handler."""
        timestamp = datetime.now().strftime("%Y%m%d")

        # Choose directory based on log level
        if level <= logging.DEBUG:
            log_dir = self.logs_dir / "debug"
        elif level <= logging.INFO:
            log_dir = self.logs_dir / "info"
        else:
            log_dir = self.logs_dir / "error"

        log_file = log_dir / f"{name}_{timestamp}.log"

        handler = logging.FileHandler(log_file, encoding='utf-8')
        handler.setLevel(level)

        # Detailed file format
        formatter = logging.Formatter(
            fmt='%(asctime)s | %(name)s | %(levelname)s | %(filename)s:%(lineno)d | %(funcName)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)

        return handler

    def _create_error_handler(self, name: str) -> logging.FileHandler:
        """Create error file handler."""
        timestamp = datetime.now().strftime("%Y%m%d")
        error_file = self.logs_dir / "error" / f"{name}_error_{timestamp}.log"

        handler = logging.FileHandler(error_file, encoding='utf-8')
        handler.setLevel(logging.ERROR)

        # Detailed error log format
        formatter = logging.Formatter(
            fmt='%(asctime)s | %(name)s | %(levelname)s | %(filename)s:%(lineno)d | %(funcName)s | %(message)s\n%(exc_info)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)

        return handler

    def create_problem_logger(self, problem_type: str) -> logging.Logger:
        """Create logger for specific problem type."""
        logger_name = f"problem.{problem_type}"
        return self.get_logger(logger_name, logging.DEBUG)

    def create_generator_logger(self) -> logging.Logger:
        """Create generator logger."""
        return self.get_logger("generator", logging.INFO)

    def create_proof_tree_logger(self) -> logging.Logger:
        """Create proof tree logger."""
        return self.get_logger("proof_tree", logging.DEBUG)

    def create_rules_logger(self) -> logging.Logger:
        """Create rules engine logger."""
        return self.get_logger("rules", logging.DEBUG)

    def log_problem_generation(self, problem_type: str, success: bool,
                             details: Optional[Dict[str, Any]] = None):
        """Log problem generation."""
        logger = self.create_problem_logger(problem_type)

        if success:
            logger.info(f"Successfully generated {problem_type} problem")
            if details:
                logger.debug(f"Problem details: {details}")
        else:
            logger.error(f"Failed to generate {problem_type} problem")
            if details:
                logger.error(f"Error details: {details}")

    def log_performance(self, operation: str, duration: float,
                       context: Optional[Dict[str, Any]] = None):
        """Log performance metrics."""
        logger = self.get_logger("performance", logging.INFO)

        logger.info(f"Operation '{operation}' took: {duration:.4f}s")
        if context:
            logger.debug(f"Context info: {context}")

    def cleanup_old_logs(self, days: int = 7):
        """Clean up old log files."""
        import time

        logger = self.get_logger("cleanup", logging.INFO)
        cutoff_time = time.time() - (days * 24 * 60 * 60)

        removed_count = 0
        for log_file in self.logs_dir.rglob("*.log"):
            if log_file.stat().st_mtime < cutoff_time:
                try:
                    log_file.unlink()
                    removed_count += 1
                except OSError as e:
                    logger.warning(f"Failed to delete log file {log_file}: {e}")

        logger.info(f"Cleaned up {removed_count} old log files")


# Global logger manager instance
_logger_manager = LoggerManager()

# Convenience functions
def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Convenience function to get a logger."""
    return _logger_manager.get_logger(name, level)

def get_problem_logger(problem_type: str) -> logging.Logger:
    """Convenience function to get a problem logger."""
    return _logger_manager.create_problem_logger(problem_type)

def get_generator_logger() -> logging.Logger:
    """Convenience function to get a generator logger."""
    return _logger_manager.create_generator_logger()

def get_proof_tree_logger() -> logging.Logger:
    """Convenience function to get a proof tree logger."""
    return _logger_manager.create_proof_tree_logger()

def get_rules_logger() -> logging.Logger:
    """Convenience function to get a rules logger."""
    return _logger_manager.create_rules_logger()

def log_problem_generation(problem_type: str, success: bool,
                          details: Optional[Dict[str, Any]] = None):
    """Convenience function to log problem generation."""
    _logger_manager.log_problem_generation(problem_type, success, details)

def log_performance(operation: str, duration: float,
                   context: Optional[Dict[str, Any]] = None):
    """Convenience function to log performance."""
    _logger_manager.log_performance(operation, duration, context)

def cleanup_old_logs(days: int = 7):
    """Convenience function to clean up old logs."""
    _logger_manager.cleanup_old_logs(days)


# Performance monitoring decorator
import functools
import time

def log_execution_time(logger_name: str = "performance"):
    """Decorator to log function execution time."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger(logger_name)
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                logger.info(f"Function {func.__name__} completed in {duration:.4f}s")
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"Function {func.__name__} failed in {duration:.4f}s, error: {e}")
                raise

        return wrapper
    return decorator


# Exception logging decorator
def log_exception(logger_name: str = "error"):
    """Decorator to log exceptions."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger(logger_name)

            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.exception(f"Function {func.__name__} raised exception: {e}")
                raise

        return wrapper
    return decorator


if __name__ == "__main__":
    """Test logging functionality."""
    print("=== Logging System Test ===")

    # Test basic logging
    logger = get_logger("test")
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")

    # Test problem generation logging
    log_problem_generation("set_union", True, {"entities": 5, "answer": 10})
    log_problem_generation("bag_operations", False, {"error": "invalid parameter"})

    # Test performance logging
    log_performance("problem generation", 0.123, {"problem_type": "set_union"})

    # Test decorators
    @log_execution_time()
    @log_exception()
    def test_function():
        time.sleep(0.1)
        return "Test complete"

    result = test_function()
    print(f"Function result: {result}")

    print("Log files have been generated in logs/ directory")
