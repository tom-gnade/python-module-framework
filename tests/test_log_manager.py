#!/usr/bin/env python3
"""
Tests for the log_manager.py functionality.

These tests verify the proper operation of:
- LogManager class
- ComponentLogger class
- Log level filtering
- Log event formatting
- Queue priority handling
"""

import asyncio
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest import mock

import pytest

# Add parent directory to sys.path to allow importing the framework
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from python_module_framework import (
        LogManager, ComponentLogger, LogLevel, LogEvent, LoggingError,
        create_log_manager, get_component_logger
    )
except ImportError:
    # Try direct import for development
    from log_manager import (
        LogManager, ComponentLogger, LogLevel, LogEvent, LoggingError,
        create_log_manager, get_component_logger
    )

#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~
# Test Classes & Fixtures
#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~

class CaptureOutput:
    """Context manager for capturing stdout/stderr for testing."""
    
    def __init__(self, stream='stderr'):
        self.stream = stream
        self.captured_output = []
        self._original_write = None
        self._original_stream = None
    
    def __enter__(self):
        if self.stream == 'stdout':
            self._original_stream = sys.stdout
            self._original_write = sys.stdout.write
        else:
            self._original_stream = sys.stderr
            self._original_write = sys.stderr.write
            
        def capture_write(text):
            self.captured_output.append(text)
            return len(text)
            
        if self.stream == 'stdout':
            sys.stdout.write = capture_write
        else:
            sys.stderr.write = capture_write
            
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.stream == 'stdout':
            sys.stdout.write = self._original_write
            sys.stdout = self._original_stream
        else:
            sys.stderr.write = self._original_write
            sys.stderr = self._original_stream
    
    def get_output(self):
        return ''.join(self.captured_output)

@pytest.fixture
def temp_log_dir():
    """Create a temporary directory for log files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)

@pytest.fixture
async def log_manager(temp_log_dir):
    """Create and initialize a log manager for testing."""
    # Create log manager
    manager = LogManager(
        service_name="test_service",
        log_level=LogLevel.VERBOSE,
        log_dir=temp_log_dir,
        log_file=temp_log_dir / "test.log",
        max_size=1024,  # Small size for testing
        backup_count=2,
        json_format=False,
        console_output=True
    )
    
    # Start manager
    await manager.start()
    
    yield manager
    
    # Stop manager
    await manager.stop()

#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~
# Test Cases
#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~

class TestLogEvent:
    """Test cases for LogEvent class."""
    
    def test_init_defaults(self):
        """Test initialization with defaults."""
        event = LogEvent(level=LogLevel.INFO, message="Test message")
        
        assert event.level == LogLevel.INFO
        assert event.message == "Test message"
        assert event.service == "service"
        assert event.component == "unknown"
        assert event.module == "unknown"
        assert event.function == "unknown"
        assert event.timestamp > 0
        assert event.thread_id is None
        assert event.context == {}
    
    def test_init_with_values(self):
        """Test initialization with custom values."""
        timestamp = 1600000000.0
        event = LogEvent(
            level=LogLevel.WARNING,
            message="Custom message",
            timestamp=timestamp,
            service="custom_service",
            component="custom_component",
            module="custom_module",
            function="custom_function",
            thread_id=12345,
            context={"key": "value"}
        )
        
        assert event.level == LogLevel.WARNING
        assert event.message == "Custom message"
        assert event.timestamp == timestamp
        assert event.service == "custom_service"
        assert event.component == "custom_component"
        assert event.module == "custom_module"
        assert event.function == "custom_function"
        assert event.thread_id == 12345
        assert event.context == {"key": "value"}
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        timestamp = 1600000000.0
        event = LogEvent(
            level=LogLevel.WARNING,
            message="Test message",
            timestamp=timestamp
        )
        
        event_dict = event.to_dict()
        
        assert event_dict["level"] == "WARNING"
        assert event_dict["message"] == "Test message"
        assert event_dict["timestamp"] == timestamp
        assert "timestamp_iso" in event_dict
    
    def test_to_str(self):
        """Test string formatting."""
        timestamp = 1600000000.0  # 2020-09-13 12:26:40
        event = LogEvent(
            level=LogLevel.ERROR,
            message="Error message",
            timestamp=timestamp,
            service="test_service",
            component="test_component"
        )
        
        # Default format
        formatted = event.to_str()
        assert "[test_service]" in formatted
        assert "[test_component]" in formatted
        assert "[ERROR]" in formatted
        assert "Error message" in formatted
        
        # Custom format
        custom_format = "{timestamp} - {service}.{component} - {level}: {message}"
        formatted = event.to_str(custom_format)
        assert "test_service.test_component" in formatted
        assert "ERROR: Error message" in formatted


class TestLogManager:
    """Test cases for LogManager class."""
    
    def test_init(self):
        """Test initialization and defaults."""
        manager = LogManager()
        
        assert manager.service_name == "service"
        assert manager.log_level == LogLevel.INFO
        assert manager.log_dir.name == "logs"
        assert manager.log_file is None
        assert manager.json_format is False
        assert manager.console_output is True
    
    def test_init_with_params(self):
        """Test initialization with parameters."""
        log_dir = Path("/tmp/logs")
        log_file = Path("/tmp/logs/test.log")
        
        manager = LogManager(
            service_name="test",
            log_level=LogLevel.VERBOSE,
            log_dir=log_dir,
            log_file=log_file,
            max_size=2048,
            backup_count=3,
            json_format=True,
            console_output=False,
            log_format="[{level}] {message}",
            date_format="%H:%M:%S"
        )
        
        assert manager.service_name == "test"
        assert manager.log_level == LogLevel.VERBOSE
        assert manager.log_dir == log_dir
        assert manager.log_file == log_file
        assert manager.max_size == 2048
        assert manager.backup_count == 3
        assert manager.json_format is True
        assert manager.console_output is False
        assert manager.log_format == "[{level}] {message}"
        assert manager.date_format == "%H:%M:%S"
    
    @pytest.mark.asyncio
    async def test_should_log(self, log_manager):
        """Test log level filtering."""
        # VERBOSE level should filter nothing
        log_manager.log_level = LogLevel.VERBOSE
        assert log_manager._should_log(LogLevel.VERBOSE)
        assert log_manager._should_log(LogLevel.INFO)
        assert log_manager._should_log(LogLevel.WARNING)
        assert log_manager._should_log(LogLevel.ERROR)
        
        # INFO level should filter VERBOSE
        log_manager.log_level = LogLevel.INFO
        assert not log_manager._should_log(LogLevel.VERBOSE)
        assert log_manager._should_log(LogLevel.INFO)
        assert log_manager._should_log(LogLevel.WARNING)
        assert log_manager._should_log(LogLevel.ERROR)
        
        # WARNING level should filter VERBOSE and INFO
        log_manager.log_level = LogLevel.WARNING
        assert not log_manager._should_log(LogLevel.VERBOSE)
        assert not log_manager._should_log(LogLevel.INFO)
        assert log_manager._should_log(LogLevel.WARNING)
        assert log_manager._should_log(LogLevel.ERROR)
        
        # ERROR level should filter all but ERROR
        log_manager.log_level = LogLevel.ERROR
        assert not log_manager._should_log(LogLevel.VERBOSE)
        assert not log_manager._should_log(LogLevel.INFO)
        assert not log_manager._should_log(LogLevel.WARNING)
        assert log_manager._should_log(LogLevel.ERROR)
    
    @pytest.mark.asyncio
    async def test_log_methods(self, log_manager):
        """Test convenience log methods."""
        with CaptureOutput() as output:
            await log_manager.verbose("Verbose message", "test_component")
            await log_manager.info("Info message", "test_component")
            await log_manager.warning("Warning message", "test_component")
            await log_manager.error("Error message", "test_component")
            
            # Need to wait for the logs to be processed
            await asyncio.sleep(0.2)
            
            captured = output.get_output()
            assert "Verbose message" in captured
            assert "Info message" in captured
            assert "Warning message" in captured
            assert "Error message" in captured
            assert "[test_component]" in captured
    
    @pytest.mark.asyncio
    async def test_json_format(self, temp_log_dir):
        """Test JSON formatted logs."""
        # Create a log manager with JSON format
        manager = LogManager(
            service_name="json_test",
            log_level=LogLevel.INFO,
            log_dir=temp_log_dir,
            log_file=temp_log_dir / "json_test.log",
            json_format=True,
            console_output=True
        )
        
        await manager.start()
        
        with CaptureOutput() as output:
            await manager.info("JSON test message", "json_component")
            
            # Need to wait for the logs to be processed
            await asyncio.sleep(0.2)
            
            await manager.stop()
            
            captured = output.get_output()
            # Try to parse as JSON
            try:
                log_entry = json.loads(captured.strip())
                assert log_entry["message"] == "JSON test message"
                assert log_entry["component"] == "json_component"
                assert log_entry["service"] == "json_test"
                assert log_entry["level"] == "INFO"
            except json.JSONDecodeError:
                pytest.fail("JSON log output is not valid JSON")
    
    @pytest.mark.asyncio
    async def test_file_logging(self, temp_log_dir):
        """Test logging to a file."""
        # Create a log manager with file output but no console output
        manager = LogManager(
            service_name="file_test",
            log_level=LogLevel.INFO,
            log_dir=temp_log_dir,
            log_file=temp_log_dir / "file_test.log",
            json_format=False,
            console_output=False
        )
        
        await manager.start()
        
        # Log some messages
        await manager.info("File test message", "file_component")
        await manager.warning("File warning message", "file_component")
        
        # Need to wait for the logs to be processed
        await asyncio.sleep(0.2)
        
        await manager.stop()
        
        # Read the log file
        log_file = temp_log_dir / "file_test.log"
        assert log_file.exists()
        
        log_content = log_file.read_text()
        assert "File test message" in log_content
        assert "File warning message" in log_content
        assert "[file_component]" in log_content
    
    @pytest.mark.asyncio
    async def test_log_rotation(self, temp_log_dir):
        """Test log file rotation."""
        # Create a log manager with a very small max size to trigger rotation
        manager = LogManager(
            service_name="rotation_test",
            log_level=LogLevel.INFO,
            log_dir=temp_log_dir,
            log_file=temp_log_dir / "rotation_test.log",
            max_size=200,  # Very small to trigger rotation
            backup_count=2,
            json_format=False,
            console_output=False
        )
        
        await manager.start()
        
        # Log enough messages to trigger rotation
        for i in range(20):
            await manager.info(f"This is log message {i} that will fill up the log file quickly", "rotation_test")
        
        # Need to wait for the logs to be processed
        await asyncio.sleep(1.0)
        
        await manager.stop()
        
        # Check for rotated log files
        log_file = temp_log_dir / "rotation_test.log"
        archive_dir = temp_log_dir / "archive"
        
        assert log_file.exists()
        assert archive_dir.exists()
        
        # Should have at least one backup file
        backup_files = list(archive_dir.glob("rotation_test*.log*"))
        assert len(backup_files) > 0


class TestComponentLogger:
    """Test cases for ComponentLogger class."""
    
    @pytest.mark.asyncio
    async def test_component_logger(self, log_manager):
        """Test component logger initialization and usage."""
        # Get a component logger
        component_logger = await get_component_logger(log_manager, "test_component")
        
        assert component_logger.component_name == "test_component"
        assert component_logger.log_manager is log_manager
        
        # Test logging with the component logger
        with CaptureOutput() as output:
            await component_logger.info("Component info message")
            await component_logger.warning("Component warning message")
            
            # Need to wait for the logs to be processed
            await asyncio.sleep(0.2)
            
            captured = output.get_output()
            assert "Component info message" in captured
            assert "Component warning message" in captured
            assert "[test_component]" in captured
    
    @pytest.mark.asyncio
    async def test_component_logger_level_filtering(self, log_manager):
        """Test component logger respects log level filtering."""
        # Set log manager to WARNING level
        log_manager.log_level = LogLevel.WARNING
        
        # Get a component logger
        component_logger = await get_component_logger(log_manager, "filter_component")
        
        with CaptureOutput() as output:
            # These should be filtered out
            await component_logger.verbose("Component verbose message")
            await component_logger.info("Component info message")
            
            # These should pass through
            await component_logger.warning("Component warning message")
            await component_logger.error("Component error message")
            
            # Need to wait for the logs to be processed
            await asyncio.sleep(0.2)
            
            captured = output.get_output()
            assert "Component verbose message" not in captured
            assert "Component info message" not in captured
            assert "Component warning message" in captured
            assert "Component error message" in captured
    
    @pytest.mark.asyncio
    async def test_component_logger_exception(self, log_manager):
        """Test logging exceptions with component logger."""
        # Get a component logger
        component_logger = await get_component_logger(log_manager, "exception_component")
        
        # Create an exception to log
        try:
            1 / 0
        except ZeroDivisionError as e:
            exception = e
        
        with CaptureOutput() as output:
            await component_logger.exception(exception, "Exception occurred")
            
            # Need to wait for the logs to be processed
            await asyncio.sleep(0.2)
            
            captured = output.get_output()
            assert "Exception occurred: division by zero" in captured
            assert "ZeroDivisionError" in captured
            assert "Traceback" in captured


class TestHelperFunctions:
    """Test cases for helper functions in log_manager.py."""
    
    @pytest.mark.asyncio
    async def test_create_log_manager(self, temp_log_dir):
        """Test create_log_manager factory function."""
        # Create a log manager with the helper function
        manager = create_log_manager(
            service_name="helper_test",
            log_level="WARNING",
            log_dir=temp_log_dir,
            log_file=temp_log_dir / "helper_test.log",
            json_format=True,
            console_output=True
        )
        
        assert manager.service_name == "helper_test"
        assert manager.log_level == LogLevel.WARNING
        assert manager.log_dir == temp_log_dir
        assert manager.log_file == temp_log_dir / "helper_test.log"
        assert manager.json_format is True
        assert manager.console_output is True
        
        # Start and stop to clean up
        await manager.start()
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_get_component_logger_helper(self, log_manager):
        """Test get_component_logger factory function."""
        # Use the helper function to get a component logger
        component_logger = await get_component_logger(log_manager, "helper_component")
        
        assert component_logger.component_name == "helper_component"
        assert component_logger.log_manager is log_manager
        
        # Test it works
        with CaptureOutput() as output:
            await component_logger.info("Helper component message")
            
            # Need to wait for the logs to be processed
            await asyncio.sleep(0.2)
            
            captured = output.get_output()
            assert "Helper component message" in captured
            assert "[helper_component]" in captured