#!/usr/bin/env python3
"""
Tests for the core module_base.py functionality.

These tests verify the proper operation of:
- BaseModule and BaseComponent classes
- Configuration parameter handling
- Dependency management
- Component lifecycle management
- Validation functions
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any, Set, Optional
from unittest import mock

import pytest

# Add parent directory to sys.path to allow importing the framework
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from python_module_framework import (
        BaseModule, BaseComponent, LogLevel, ConfigParam, Dependency,
        ModuleError, ConfigError, DependencyError, OperationError, Validator
    )
except ImportError:
    # Try direct import for development
    from module_base import (
        BaseModule, BaseComponent, LogLevel, ConfigParam, Dependency,
        ModuleError, ConfigError, DependencyError, OperationError, Validator
    )

#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~
# Test Classes
#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~

class MockLogger:
    """Mock logger for testing."""
    
    def __init__(self):
        self.logs = []
        self.min_level = LogLevel.VERBOSE
    
    def _should_log(self, level: LogLevel) -> bool:
        """Always return True for tests."""
        return True
    
    async def log(self, level: LogLevel, message: str):
        """Log the message."""
        self.logs.append((level, message))
    
    async def verbose(self, message: str):
        """Log verbose message."""
        await self.log(LogLevel.VERBOSE, message)
    
    async def info(self, message: str):
        """Log info message."""
        await self.log(LogLevel.INFO, message)
    
    async def warning(self, message: str):
        """Log warning message."""
        await self.log(LogLevel.WARNING, message)
    
    async def error(self, message: str):
        """Log error message."""
        await self.log(LogLevel.ERROR, message)

class TestDependency:
    """Test dependency with required methods."""
    
    def __init__(self, data=None):
        self.data = data or {}
        self.calls = []
    
    async def get(self, key):
        """Get a value."""
        self.calls.append(('get', key))
        return self.data.get(key)
    
    async def save(self, data):
        """Save data."""
        self.calls.append(('save', data))
        self.data.update(data)
        return True

class TestModule(BaseModule):
    """Test module for test cases."""
    
    CONFIG_PARAMS = [
        ConfigParam(
            name="test_param",
            default="default_value",
            description="Test parameter"
        ),
        ConfigParam(
            name="test_number",
            default=42,
            description="Test number parameter",
            validators=[Validator.positive]
        ),
        ConfigParam(
            name="required_param",
            default=None,
            description="Required parameter",
            required=True
        )
    ]
    
    DEPENDENCIES = [
        Dependency(
            name="test_dependency",
            description="Test dependency",
            required=True,
            methods={"get", "save"}
        ),
        Dependency(
            name="optional_dependency",
            description="Optional dependency",
            required=False,
            methods={"process"}
        )
    ]
    
    def __init__(self, config=None, dependencies=None, logger=None, log_level=None):
        """Initialize test module."""
        super().__init__(config, dependencies, logger, log_level)
        
        # Create a test component
        self.test_component = TestComponent("test_component", self)
        
        # Register components
        self.components = {
            "test_component": self.test_component
        }
        
        # Track initialization for testing
        self.initialized = False
        self.run_called = False
        self.stop_called = False
        self.cleanup_called = False
    
    async def init(self):
        """Initialize the module."""
        await super().init()
        self.initialized = True
    
    async def run(self):
        """Run the module."""
        await super().run()
        self.run_called = True
    
    async def stop(self):
        """Stop the module."""
        await super().stop()
        self.stop_called = True
    
    async def cleanup(self):
        """Clean up resources."""
        await super().cleanup()
        self.cleanup_called = True

class TestComponent(BaseComponent):
    """Test component for test cases."""
    
    def __init__(self, name, parent_module):
        """Initialize test component."""
        super().__init__(name, parent_module)
        
        # Track lifecycle for testing
        self.initialized = False
        self.run_called = False
        self.stop_called = False
        self.cleanup_called = False
        
        # Custom state for testing
        self.counter = 0
    
    async def init(self):
        """Initialize the component."""
        await super().init()
        self.initialized = True
    
    async def run(self):
        """Run the component."""
        await super().run()
        self.run_called = True
        
        # Simulate some activity
        try:
            while self.parent.running:
                self.counter += 1
                await asyncio.sleep(0.01)  # Short sleep for tests
        except asyncio.CancelledError:
            pass
    
    async def stop(self):
        """Stop the component."""
        await super().stop()
        self.stop_called = True
    
    async def cleanup(self):
        """Clean up resources."""
        await super().cleanup()
        self.cleanup_called = True

#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~
# Test Cases
#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~

class TestLogLevel:
    """Test cases for LogLevel enum."""
    
    def test_log_level_values(self):
        """Test that log levels have correct values."""
        assert LogLevel.VERBOSE == "VERBOSE"
        assert LogLevel.INFO == "INFO"
        assert LogLevel.WARNING == "WARNING"
        assert LogLevel.ERROR == "ERROR"
    
    def test_from_string(self):
        """Test conversion from string to LogLevel."""
        assert LogLevel.from_string("VERBOSE") == LogLevel.VERBOSE
        assert LogLevel.from_string("verbose") == LogLevel.VERBOSE
        assert LogLevel.from_string("INFO") == LogLevel.INFO
        assert LogLevel.from_string("warning") == LogLevel.WARNING
        assert LogLevel.from_string("ERROR") == LogLevel.ERROR
        
        # Invalid values should default to INFO
        assert LogLevel.from_string("invalid") == LogLevel.INFO
        assert LogLevel.from_string("") == LogLevel.INFO
        assert LogLevel.from_string(None) == LogLevel.INFO
    
    def test_default(self):
        """Test default log level."""
        assert LogLevel.default() == LogLevel.INFO

class TestConfigParam:
    """Test cases for ConfigParam class."""
    
    def test_init(self):
        """Test initialization and defaults."""
        param = ConfigParam(
            name="test",
            default="default",
            description="Test parameter"
        )
        
        assert param.name == "test"
        assert param.default == "default"
        assert param.description == "Test parameter"
        assert param.type == str  # Inferred from default
        assert not param.required
        assert param.validators == []
    
    def test_validate_success(self):
        """Test successful validation."""
        param = ConfigParam(
            name="test_num",
            default=10,
            description="Test number",
            validators=[Validator.positive]
        )
        
        # Test with valid values
        assert param.validate(20) == 20
        assert param.validate("30") == 30  # Type conversion
        
        # Test default value
        assert param.validate(None) == 10
    
    def test_validate_failure(self):
        """Test validation failures."""
        param = ConfigParam(
            name="test_num",
            default=10,
            description="Test number",
            validators=[Validator.positive],
            required=True
        )
        
        # Test required parameter
        with pytest.raises(ValueError):
            param.validate(None)
        
        # Test validation failure
        with pytest.raises(ValueError):
            param.validate(-5)
        
        # Test type conversion failure
        with pytest.raises(ValueError):
            param.validate("not_a_number")

class TestDependencyClass:
    """Test cases for Dependency class."""
    
    def test_init(self):
        """Test initialization and defaults."""
        dep = Dependency(
            name="test",
            description="Test dependency"
        )
        
        assert dep.name == "test"
        assert dep.description == "Test dependency"
        assert dep.required is True
        assert dep.methods == set()
        assert dep.attributes == set()
    
    def test_validate_success(self):
        """Test successful validation."""
        dep = Dependency(
            name="storage",
            description="Storage service",
            methods={"save", "load"},
            attributes={"version"}
        )
        
        class Storage:
            version = "1.0"
            
            def save(self, data):
                pass
                
            def load(self, key):
                pass
        
        # Should not raise
        assert dep.validate(Storage())
    
    def test_validate_failure(self):
        """Test validation failures."""
        dep = Dependency(
            name="storage",
            description="Storage service",
            methods={"save", "load"},
            attributes={"version"}
        )
        
        class MissingMethod:
            version = "1.0"
            
            def save(self, data):
                pass
                
            # load is missing
        
        class MissingAttribute:
            # version is missing
            
            def save(self, data):
                pass
                
            def load(self, key):
                pass
        
        # Test missing method
        with pytest.raises(ValueError):
            dep.validate(MissingMethod())
        
        # Test missing attribute
        with pytest.raises(ValueError):
            dep.validate(MissingAttribute())

class TestBaseModule:
    """Test cases for BaseModule class."""
    
    def test_init_defaults(self):
        """Test initialization with defaults."""
        module = TestModule()
        
        # Check initialization
        assert module.module_name == "TestModule"
        assert "test_component" in module.components
        
        # Check default config values
        assert module.config["test_param"] == "default_value"
        assert module.config["test_number"] == 42
        
        # Required param should still have None as default
        assert module.config["required_param"] is None
    
    def test_init_with_config(self):
        """Test initialization with config dictionary."""
        config = {
            "test_param": "custom_value",
            "test_number": 100,
            "required_param": "provided"
        }
        
        module = TestModule(config=config)
        
        # Check custom config values
        assert module.config["test_param"] == "custom_value"
        assert module.config["test_number"] == 100
        assert module.config["required_param"] == "provided"
    
    def test_init_with_config_section(self):
        """Test initialization with config section."""
        config = {
            "TestModule": {
                "test_param": "section_value",
                "test_number": 200,
                "required_param": "provided"
            }
        }
        
        module = TestModule(config=config, module_id="TestModule")
        
        # Check config values from section
        assert module.config["test_param"] == "section_value"
        assert module.config["test_number"] == 200
        assert module.config["required_param"] == "provided"
    
    def test_init_with_logger(self):
        """Test initialization with custom logger."""
        logger = MockLogger()
        module = TestModule(logger=logger)
        
        # Check logger was set
        assert module.logger is logger
    
    def test_dependency_validation(self):
        """Test dependency validation."""
        # Missing required dependency
        with pytest.raises(DependencyError):
            TestModule(dependencies={})
        
        # Valid dependencies
        dependencies = {
            "test_dependency": TestDependency()
        }
        
        module = TestModule(
            config={"required_param": "value"}, 
            dependencies=dependencies
        )
        
        # Check dependency was stored
        assert module.dependencies["test_dependency"] is dependencies["test_dependency"]
    
    @pytest.mark.asyncio
    async def test_lifecycle(self):
        """Test complete module lifecycle."""
        logger = MockLogger()
        module = TestModule(
            config={"required_param": "value"},
            dependencies={"test_dependency": TestDependency()},
            logger=logger
        )
        
        # Check initial state
        assert not module.initialized
        assert not module.run_called
        assert not module.stop_called
        assert not module.cleanup_called
        
        # Run lifecycle
        await module.init()
        assert module.initialized
        assert module.test_component.initialized
        
        # Start running for a short time
        module.running = True
        run_task = asyncio.create_task(module.run())
        
        # Let it run briefly
        await asyncio.sleep(0.05)
        
        # Stop and cleanup
        await module.stop()
        await module.cleanup()
        await run_task
        
        # Check final state
        assert module.initialized
        assert module.run_called
        assert module.stop_called
        assert module.cleanup_called
        
        # Check component lifecycle
        assert module.test_component.initialized
        assert module.test_component.run_called
        assert module.test_component.stop_called
        assert module.test_component.cleanup_called
        
        # Component should have run for a bit
        assert module.test_component.counter > 0
    
    @pytest.mark.asyncio
    async def test_logging(self):
        """Test module logging."""
        logger = MockLogger()
        module = TestModule(
            config={"required_param": "value"},
            dependencies={"test_dependency": TestDependency()},
            logger=logger
        )
        
        # Log messages at different levels
        await module._log(LogLevel.VERBOSE, "Verbose message")
        await module._log(LogLevel.INFO, "Info message")
        await module._log(LogLevel.WARNING, "Warning message")
        await module._log(LogLevel.ERROR, "Error message")
        
        # Check log messages
        assert len(logger.logs) == 4
        assert logger.logs[0] == (LogLevel.VERBOSE, "Verbose message")
        assert logger.logs[1] == (LogLevel.INFO, "Info message")
        assert logger.logs[2] == (LogLevel.WARNING, "Warning message")
        assert logger.logs[3] == (LogLevel.ERROR, "Error message")

class TestBaseComponent:
    """Test cases for BaseComponent class."""
    
    @pytest.mark.asyncio
    async def test_component_lifecycle(self):
        """Test component lifecycle."""
        logger = MockLogger()
        module = TestModule(
            config={"required_param": "value"},
            dependencies={"test_dependency": TestDependency()},
            logger=logger
        )
        
        component = module.test_component
        
        # Check initial state
        assert not component.initialized
        assert not component.run_called
        assert not component.stop_called
        assert not component.cleanup_called
        
        # Run lifecycle
        await component.init()
        assert component.initialized
        
        # Start running
        module.running = True
        run_task = asyncio.create_task(component.run())
        
        # Let it run briefly
        await asyncio.sleep(0.05)
        
        # Stop and cleanup
        module.running = False
        await component.stop()
        await component.cleanup()
        await run_task
        
        # Check final state
        assert component.initialized
        assert component.run_called
        assert component.stop_called
        assert component.cleanup_called
        
        # Component should have run for a bit
        assert component.counter > 0
    
    @pytest.mark.asyncio
    async def test_component_logging(self):
        """Test component logging."""
        logger = MockLogger()
        module = TestModule(
            config={"required_param": "value"},
            dependencies={"test_dependency": TestDependency()},
            logger=logger
        )
        
        component = module.test_component
        
        # Log messages at different levels
        await component._log(LogLevel.VERBOSE, "Component verbose message")
        await component._log(LogLevel.INFO, "Component info message")
        await component._log(LogLevel.WARNING, "Component warning message")
        await component._log(LogLevel.ERROR, "Component error message")
        
        # Check log messages
        assert len(logger.logs) == 4
        assert logger.logs[0] == (LogLevel.VERBOSE, "[test_component] Component verbose message")
        assert logger.logs[1] == (LogLevel.INFO, "[test_component] Component info message")
        assert logger.logs[2] == (LogLevel.WARNING, "[test_component] Component warning message")
        assert logger.logs[3] == (LogLevel.ERROR, "[test_component] Component error message")

class TestValidators:
    """Test cases for validator functions."""
    
    def test_positive(self):
        """Test positive validator."""
        assert Validator.positive(1)
        assert Validator.positive(0.1)
        assert not Validator.positive(0)
        assert not Validator.positive(-1)
    
    def test_non_negative(self):
        """Test non_negative validator."""
        assert Validator.non_negative(1)
        assert Validator.non_negative(0)
        assert not Validator.non_negative(-1)
    
    def test_port_number(self):
        """Test port_number validator."""
        assert Validator.port_number(1024)
        assert Validator.port_number(8080)
        assert Validator.port_number(65535)
        assert not Validator.port_number(0)
        assert not Validator.port_number(65536)
        assert not Validator.port_number("8080")  # Must be int
    
    def test_in_range(self):
        """Test in_range validator."""
        validator = Validator.in_range(1, 10)
        assert validator(1)
        assert validator(5)
        assert validator(10)
        assert not validator(0)
        assert not validator(11)
    
    def test_one_of(self):
        """Test one_of validator."""
        validator = Validator.one_of(["a", "b", "c"])
        assert validator("a")
        assert validator("b")
        assert validator("c")
        assert not validator("d")
    
    def test_matches(self):
        """Test matches validator."""
        validator = Validator.matches(r"^[0-9]{3}-[0-9]{3}$")
        assert validator("123-456")
        assert not validator("12-345")
        assert not validator("123-4567")
        assert not validator("abc-def")
    
    def test_ip_address(self):
        """Test ip_address validator."""
        assert Validator.ip_address("192.168.1.1")
        assert Validator.ip_address("10.0.0.1")
        assert Validator.ip_address("127.0.0.1")
        assert not Validator.ip_address("256.256.256.256")
        assert not Validator.ip_address("1.2.3")
        assert not Validator.ip_address("hostname")
    
    def test_hostname(self):
        """Test hostname validator."""
        assert Validator.hostname("example.com")
        assert Validator.hostname("sub.example.com")
        assert Validator.hostname("localhost")
        assert not Validator.hostname("example..com")
        assert not Validator.hostname("-example.com")
    
    def test_email(self):
        """Test email validator."""
        assert Validator.email("user@example.com")
        assert Validator.email("user.name@example.co.uk")
        assert not Validator.email("user@")
        assert not Validator.email("@example.com")
        assert not Validator.email("user@example")
    
    def test_url(self):
        """Test url validator."""
        assert Validator.url("http://example.com")
        assert Validator.url("https://sub.example.com/path")
        assert not Validator.url("example.com")
        assert not Validator.url("http://")
    
    def test_length(self):
        """Test length validator."""
        min_validator = Validator.length(min_len=3)
        assert min_validator("abc")
        assert min_validator("abcdef")
        assert not min_validator("ab")
        
        range_validator = Validator.length(min_len=3, max_len=6)
        assert range_validator("abc")
        assert range_validator("abcdef")
        assert not range_validator("ab")
        assert not range_validator("abcdefg")

class TestHelperFunctions:
    """Test cases for helper functions."""
    
    @pytest.mark.asyncio
    async def test_run_module(self):
        """Test run_module helper function."""
        from module_base import run_module
        
        # Create a module with mocked functions to check call order
        mock_module = mock.MagicMock(spec=TestModule)
        mock_module.init = mock.AsyncMock()
        mock_module.run = mock.AsyncMock()
        mock_module.stop = mock.AsyncMock()
        mock_module.cleanup = mock.AsyncMock()
        
        # Mock the constructor to return our mock
        with mock.patch('test_module_base.TestModule', return_value=mock_module):
            result = await run_module(TestModule, config={"test": "value"})
            
            # Check the module was returned
            assert result is mock_module
            
            # Check lifecycle methods were called in correct order
            mock_module.init.assert_called_once()
            mock_module.run.assert_called_once()
            mock_module.stop.assert_called_once()
            mock_module.cleanup.assert_called_once()
    
    def test_load_config_from_file(self):
        """Test load_config_from_file helper function."""
        from module_base import load_config_from_file
        
        # Create a temporary config file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp:
            temp.write(json.dumps({"test": "value"}))
            temp_path = temp.name
        
        try:
            # Load the config
            config = load_config_from_file(temp_path)
            assert config == {"test": "value"}
            
            # Test with non-existent file
            with pytest.raises(ConfigError):
                load_config_from_file("non_existent_file.json")
                
            # Test with invalid JSON
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as invalid:
                invalid.write("not valid json")
                invalid_path = invalid.name
                
            with pytest.raises(ConfigError):
                load_config_from_file(invalid_path)
                
        finally:
            # Clean up temporary files
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            if 'invalid_path' in locals() and os.path.exists(invalid_path):
                os.unlink(invalid_path)
    
    def test_find_config_file(self):
        """Test find_config_file helper function."""
        from module_base import find_config_file
        
        # Create temporary config files
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create a common config file
            common_config = temp_path / "config.json"
            common_config.write_text(json.dumps({"common": "value"}))
            
            # Create a module-specific config file
            module_config = temp_path / "test_module.json"
            module_config.write_text(json.dumps({"module": "value"}))
            
            # Test finding common config
            found = find_config_file(search_paths=[temp_path])
            assert found == common_config
            
            # Test finding module-specific config
            found = find_config_file(module_id="test_module", search_paths=[temp_path])
            assert found == module_config
            
            # Test priority (module-specific should be found first)
            found = find_config_file(module_id="test_module", file_name="config.json", search_paths=[temp_path])
            assert found == module_config
            
            # Test when no config exists
            found = find_config_file(module_id="non_existent", search_paths=[temp_path])
            assert found is None