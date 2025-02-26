#!/usr/bin/env python3
"""
Tests for the config_manager.py functionality.

These tests verify the proper operation of:
- ConfigManager class
- ConfigValue class
- Configuration loading from files
- Environment variable overrides
- Hierarchical configuration access
- Configuration change notifications
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest

# Add parent directory to sys.path to allow importing the framework
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from python_module_framework import (
        ConfigManager, ConfigValue, ConfigError,
        create_config_manager, find_config_file
    )
except ImportError:
    # Try direct import for development
    from config_manager import (
        ConfigManager, ConfigValue, ConfigError,
        create_config_manager, find_config_file
    )

#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~
# Fixtures
#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~

@pytest.fixture
def sample_config():
    """Sample configuration dict for testing."""
    return {
        "app": {
            "name": "Test App",
            "version": "1.0.0",
            "log_level": "info"
        },
        "server": {
            "host": "localhost",
            "port": 8080,
            "debug": False
        },
        "database": {
            "url": "postgresql://user:pass@localhost/db",
            "pool_size": 5,
            "timeout": 30.5
        }
    }

@pytest.fixture
def temp_config_file(sample_config):
    """Temporary config file with sample configuration."""
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as f:
        json.dump(sample_config, f)
        temp_path = f.name
    
    yield temp_path
    
    # Clean up
    if os.path.exists(temp_path):
        os.unlink(temp_path)

#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~
# Test Cases
#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~

class TestConfigManager:
    """Test cases for ConfigManager class."""
    
    def test_init_defaults(self):
        """Test initialization with defaults."""
        manager = ConfigManager()
        
        assert manager.env_prefix == ''
        assert manager.config == {}
        assert manager.listeners == []
    
    def test_init_with_defaults(self):
        """Test initialization with default config."""
        default_config = {"app_name": "Test App"}
        manager = ConfigManager(default_config=default_config)
        
        assert manager.config == default_config
    
    def test_load_config_file(self, temp_config_file, sample_config):
        """Test loading configuration from file."""
        manager = ConfigManager()
        manager.load_config_file(temp_config_file)
        
        assert manager.config == sample_config
    
    def test_load_config_file_not_found(self):
        """Test loading from non-existent file."""
        manager = ConfigManager()
        
        with pytest.raises(ConfigError):
            manager.load_config_file("non_existent_file.json")
    
    def test_load_config_file_invalid_json(self):
        """Test loading invalid JSON file."""
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as f:
            f.write("this is not valid json")
            temp_path = f.name
            
        manager = ConfigManager()
        
        try:
            with pytest.raises(ConfigError):
                manager.load_config_file(temp_path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_get_simple_key(self, sample_config):
        """Test getting simple top-level keys."""
        manager = ConfigManager(default_config=sample_config)
        
        # Test existing keys
        assert manager.get("app") == sample_config["app"]
        assert manager.get("server") == sample_config["server"]
        assert manager.get("database") == sample_config["database"]
        
        # Test non-existent key
        assert manager.get("non_existent") is None
        assert manager.get("non_existent", "default") == "default"
    
    def test_get_nested_key(self, sample_config):
        """Test getting nested keys with dot notation."""
        manager = ConfigManager(default_config=sample_config)
        
        # Test existing nested keys
        assert manager.get("app.name") == "Test App"
        assert manager.get("app.version") == "1.0.0"
        assert manager.get("app.log_level") == "info"
        assert manager.get("server.host") == "localhost"
        assert manager.get("server.port") == 8080
        assert manager.get("server.debug") is False
        assert manager.get("database.url") == "postgresql://user:pass@localhost/db"
        assert manager.get("database.pool_size") == 5
        assert manager.get("database.timeout") == 30.5
        
        # Test non-existent nested keys
        assert manager.get("app.non_existent") is None
        assert manager.get("app.non_existent", "default") == "default"
        assert manager.get("non_existent.key") is None
    
    def test_get_type_methods(self, sample_config):
        """Test type-specific get methods."""
        manager = ConfigManager(default_config=sample_config)
        
        # Test get_int
        assert manager.get_int("server.port") == 8080
        assert manager.get_int("app.name") is None  # Not an int
        assert manager.get_int("app.name", 100) == 100  # Default for non-int
        assert manager.get_int("non_existent", 42) == 42  # Default for missing
        
        # Test get_float
        assert manager.get_float("database.timeout") == 30.5
        assert manager.get_float("server.port") == 8080.0  # Int converted to float
        assert manager.get_float("app.name") is None  # Not a float
        assert manager.get_float("non_existent", 3.14) == 3.14  # Default
        
        # Test get_bool
        assert manager.get_bool("server.debug") is False
        assert manager.get_bool("non_existent") is None
        assert manager.get_bool("non_existent", True) is True
        
        # Test with string values that convert to bool
        manager.config["string_true"] = "true"
        manager.config["string_false"] = "false"
        manager.config["string_yes"] = "yes"
        manager.config["string_no"] = "no"
        manager.config["string_1"] = "1"
        manager.config["string_0"] = "0"
        
        assert manager.get_bool("string_true") is True
        assert manager.get_bool("string_false") is False
        assert manager.get_bool("string_yes") is True
        assert manager.get_bool("string_no") is False
        assert manager.get_bool("string_1") is True
        assert manager.get_bool("string_0") is False
    
    def test_get_list(self):
        """Test get_list method."""
        manager = ConfigManager()
        
        # List in config
        manager.config["list"] = [1, 2, 3]
        assert manager.get_list("list") == [1, 2, 3]
        
        # JSON array string
        manager.config["json_list"] = "[4, 5, 6]"
        assert manager.get_list("json_list") == [4, 5, 6]
        
        # Comma-separated string
        manager.config["csv_list"] = "a, b, c"
        assert manager.get_list("csv_list") == ["a", "b", "c"]
        
        # Single value
        manager.config["single"] = "value"
        assert manager.get_list("single") == ["value"]
        
        # Non-existent key
        assert manager.get_list("non_existent") is None
        assert manager.get_list("non_existent", [1, 2]) == [1, 2]
    
    def test_get_dict(self):
        """Test get_dict method."""
        manager = ConfigManager()
        
        # Dict in config
        manager.config["dict"] = {"a": 1, "b": 2}
        assert manager.get_dict("dict") == {"a": 1, "b": 2}
        
        # JSON object string
        manager.config["json_dict"] = '{"c": 3, "d": 4}'
        assert manager.get_dict("json_dict") == {"c": 3, "d": 4}
        
        # Non-dict value
        manager.config["non_dict"] = "value"
        assert manager.get_dict("non_dict") is None
        assert manager.get_dict("non_dict", {"default": True}) == {"default": True}
        
        # Non-existent key
        assert manager.get_dict("non_existent") is None
        assert manager.get_dict("non_existent", {"default": True}) == {"default": True}
    
    def test_set_simple_key(self):
        """Test setting simple keys."""
        manager = ConfigManager()
        
        # Set new value
        manager.set("key", "value")
        assert manager.config["key"] == "value"
        
        # Update existing value
        manager.set("key", "new_value")
        assert manager.config["key"] == "new_value"
    
    def test_set_nested_key(self):
        """Test setting nested keys with dot notation."""
        manager = ConfigManager()
        
        # Set new nested value
        manager.set("app.name", "Test App")
        assert "app" in manager.config
        assert isinstance(manager.config["app"], dict)
        assert manager.config["app"]["name"] == "Test App"
        
        # Update existing nested value
        manager.set("app.name", "New App Name")
        assert manager.config["app"]["name"] == "New App Name"
        
        # Set nested value in non-existent parent
        manager.set("new.nested.key", "value")
        assert "new" in manager.config
        assert "nested" in manager.config["new"]
        assert manager.config["new"]["nested"]["key"] == "value"
        
        # Set nested value with non-dict parent
        manager.config["string"] = "value"
        manager.set("string.key", "nested_value")
        assert isinstance(manager.config["string"], dict)
        assert manager.config["string"]["key"] == "nested_value"
    
    def test_listeners(self):
        """Test configuration change listeners."""
        manager = ConfigManager()