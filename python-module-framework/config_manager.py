#!/usr/bin/env python3
"""
config_manager.py - Configuration Management

Provides a centralized configuration system that reads from JSON files
and handles configuration validation, defaults, and access.

Features:
- Configuration file loading and validation
- Environment variable overrides
- Hierarchical configuration access
- Configuration change notifications
- Default values for missing parameters
"""

#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~
# Imports
#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Type, TypeVar, Generic, Callable

try:
    # Optional integration with module_base
    from module_base import ConfigError
except ImportError:
    # Define our own ConfigError if module_base not available
    class ConfigError(Exception):
        """Configuration-related errors."""
        pass

#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~
# Type Definitions
#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~

# Type for configuration objects
ConfigDict = Dict[str, Any]

# Type variable for config value
T = TypeVar('T')

#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~
# Configuration Manager
#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~

class ConfigManager:
    """
    Configuration manager that handles loading, validation, and access to
    configuration values from files or environment variables.
    """
    
    def __init__(
        self, 
        config_file: Optional[Union[str, Path]] = None,
        env_prefix: str = '',
        default_config: Optional[ConfigDict] = None
    ):
        """
        Initialize configuration manager.
        
        Args:
            config_file: Path to JSON configuration file (optional)
            env_prefix: Prefix for environment variables (e.g., 'APP_')
            default_config: Default configuration values
        """
        self.env_prefix = env_prefix
        self.config: ConfigDict = default_config or {}
        self.listeners: List[Callable[[str, Any], None]] = []
        
        # Load configuration file if provided
        if config_file:
            self.load_config_file(config_file)
            
        # Apply environment variable overrides
        self._apply_env_overrides()
    
    def load_config_file(self, config_file: Union[str, Path]) -> None:
        """
        Load configuration from a JSON file.
        
        Args:
            config_file: Path to configuration file
            
        Raises:
            ConfigError: If file reading or parsing fails
        """
        try:
            with open(config_file, 'r') as f:
                file_config = json.load(f)
                
            # Update configuration with file values
            self._update_config(file_config)
            
        except FileNotFoundError:
            raise ConfigError(f"Configuration file not found: {config_file}")
        except json.JSONDecodeError as e:
            raise ConfigError(f"Invalid JSON in configuration file: {e}")
        except Exception as e:
            raise ConfigError(f"Error loading configuration: {e}")
    
    def _update_config(self, new_config: ConfigDict) -> None:
        """
        Update configuration with new values and notify listeners.
        
        Args:
            new_config: New configuration values
        """
        # Track changes for notifications
        changes = {}
        
        # Update configuration
        for key, value in new_config.items():
            if key not in self.config or self.config[key] != value:
                self.config[key] = value
                changes[key] = value
        
        # Notify listeners of changes
        for key, value in changes.items():
            for listener in self.listeners:
                listener(key, value)
    
    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides to configuration."""
        if not self.env_prefix:
            return
            
        # Find environment variables with matching prefix
        for env_key, env_value in os.environ.items():
            if env_key.startswith(self.env_prefix):
                # Convert environment key to config key
                config_key = env_key[len(self.env_prefix):].lower()
                
                # Try to parse as JSON for structured values
                try:
                    value = json.loads(env_value)
                except json.JSONDecodeError:
                    # Not valid JSON, use as string
                    value = env_value
                
                # Update configuration
                self.config[config_key] = value
    
    def get(self, key: str, default: T = None) -> Union[Any, T]:
        """
        Get configuration value by key.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        # Handle nested keys using dot notation
        if '.' in key:
            parts = key.split('.')
            value = self.config
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    return default
            return value
            
        return self.config.get(key, default)
    
    def get_int(self, key: str, default: Optional[int] = None) -> Optional[int]:
        """Get configuration value as integer."""
        value = self.get(key, default)
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    def get_float(self, key: str, default: Optional[float] = None) -> Optional[float]:
        """Get configuration value as float."""
        value = self.get(key, default)
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    def get_bool(self, key: str, default: Optional[bool] = None) -> Optional[bool]:
        """
        Get configuration value as boolean.
        
        Treats strings like 'true', 'yes', '1' as True
        and 'false', 'no', '0' as False.
        """
        value = self.get(key, default)
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.lower() in ('true', 'yes', '1', 'y')
        return bool(value)
    
    def get_list(self, key: str, default: Optional[List[Any]] = None) -> Optional[List[Any]]:
        """Get configuration value as list."""
        value = self.get(key, default)
        if value is None:
            return default
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                # Try to parse as JSON array
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                # Split by commas if not valid JSON
                return [item.strip() for item in value.split(',')]
        return [value]  # Wrap single value in list
    
    def get_dict(self, key: str, default: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Get configuration value as dictionary."""
        value = self.get(key, default)
        if value is None:
            return default
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                # Try to parse as JSON object
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass
        return default
    
    def set(self, key: str, value: Any) -> None:
        """
        Set configuration value.
        
        Args:
            key: Configuration key
            value: Configuration value
        """
        if '.' in key:
            # Handle nested keys
            parts = key.split('.')
            config = self.config
            
            # Navigate to the parent of the key
            for part in parts[:-1]:
                if part not in config:
                    config[part] = {}
                elif not isinstance(config[part], dict):
                    config[part] = {}
                config = config[part]
            
            # Set the value at the leaf
            config[parts[-1]] = value
            
            # Notify listeners
            for listener in self.listeners:
                listener(key, value)
        else:
            # Simple key
            self.config[key] = value
            
            # Notify listeners
            for listener in self.listeners:
                listener(key, value)
    
    def add_listener(self, listener: Callable[[str, Any], None]) -> None:
        """
        Add a listener for configuration changes.
        
        Args:
            listener: Callback function that receives (key, value)
        """
        if listener not in self.listeners:
            self.listeners.append(listener)
    
    def remove_listener(self, listener: Callable[[str, Any], None]) -> None:
        """
        Remove a configuration change listener.
        
        Args:
            listener: Callback function to remove
        """
        if listener in self.listeners:
            self.listeners.remove(listener)
    
    def get_all(self) -> ConfigDict:
        """Get a copy of the entire configuration."""
        return dict(self.config)
    
    def clear(self) -> None:
        """Clear all configuration values."""
        self.config.clear()
    
    def save_to_file(self, filepath: Union[str, Path]) -> None:
        """
        Save current configuration to a JSON file.
        
        Args:
            filepath: Path to save configuration
            
        Raises:
            ConfigError: If file writing fails
        """
        try:
            with open(filepath, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            raise ConfigError(f"Error saving configuration: {e}")

#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~
# Configuration Value Class
#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~

class ConfigValue(Generic[T]):
    """
    Typed configuration value with validation.
    
    This class provides type safety and validation for configuration values.
    """
    
    def __init__(
        self, 
        config_manager: ConfigManager,
        key: str,
        default: T,
        validator: Optional[Callable[[T], bool]] = None
    ):
        """
        Initialize configuration value.
        
        Args:
            config_manager: ConfigManager instance
            key: Configuration key
            default: Default value
            validator: Optional validation function
        """
        self.config_manager = config_manager
        self.key = key
        self.default = default
        self.validator = validator
        
    def get(self) -> T:
        """Get the configuration value."""
        value = self.config_manager.get(self.key, self.default)
        
        # Type conversion based on default value
        if value is not None and self.default is not None:
            try:
                value_type = type(self.default)
                value = value_type(value)
            except (ValueError, TypeError):
                # If conversion fails, use default
                value = self.default
                
        # Validation
        if self.validator and value is not None:
            if not self.validator(value):
                # If validation fails, use default
                value = self.default
                
        return value
        
    def set(self, value: T) -> None:
        """Set the configuration value."""
        # Validation
        if self.validator and not self.validator(value):
            raise ValueError(f"Invalid value for {self.key}: {value}")
            
        self.config_manager.set(self.key, value)

#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~
# Helper Functions
#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~

def create_config_manager(
    config_file: Optional[Union[str, Path]] = None,
    env_prefix: str = '',
    default_config: Optional[ConfigDict] = None
) -> ConfigManager:
    """
    Create a ConfigManager with error handling.
    
    Args:
        config_file: Path to configuration file
        env_prefix: Prefix for environment variables
        default_config: Default configuration values
        
    Returns:
        Initialized ConfigManager
    """
    try:
        return ConfigManager(config_file, env_prefix, default_config)
    except ConfigError as e:
        # Print error and create with just defaults
        print(f"Configuration error: {e}", file=sys.stderr)
        return ConfigManager(env_prefix=env_prefix, default_config=default_config)
    except Exception as e:
        # Fall back to defaults
        print(f"Unexpected error creating config manager: {e}", file=sys.stderr)
        return ConfigManager(default_config=default_config or {})


def find_config_file(
    file_name: str = 'config.json',
    search_paths: Optional[List[Union[str, Path]]] = None
) -> Optional[Path]:
    """
    Find a configuration file in search paths.
    
    Args:
        file_name: Name of configuration file
        search_paths: List of paths to search (defaults to common locations)
        
    Returns:
        Path to configuration file or None if not found
    """
    if search_paths is None:
        # Default search paths
        search_paths = [
            Path.cwd(),  # Current directory
            Path.home(),  # User's home directory
            Path('/etc'),  # System config directory
        ]
        
        # Add application directory
        app_dir = Path(sys.argv[0]).resolve().parent
        if app_dir not in search_paths:
            search_paths.insert(0, app_dir)
            
    # Search for the file
    for path in search_paths:
        config_path = Path(path) / file_name
        if config_path.is_file():
            return config_path
            
    return None


#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~
# Example Usage
#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~

if __name__ == '__main__':
    # Example default configuration
    default_config = {
        'app': {
            'name': 'Example App',
            'version': '1.0.0',
            'log_level': 'info'
        },
        'server': {
            'host': 'localhost',
            'port': 8080,
            'debug': False
        }
    }
    
    # Try to find config file
    config_file = find_config_file('example_config.json')
    
    # Create config manager
    config = create_config_manager(
        config_file=config_file,
        env_prefix='EXAMPLE_',
        default_config=default_config
    )
    
    # Access configuration values
    app_name = config.get('app.name')
    server_port = config.get_int('server.port')
    debug_mode = config.get_bool('server.debug')
    
    print(f"App: {app_name}")
    print(f"Server Port: {server_port}")
    print(f"Debug Mode: {debug_mode}")
    
    # Typed configuration values
    port_config = ConfigValue(config, 'server.port', 8080, lambda x: 1024 <= x <= 65535)
    port = port_config.get()
    
    # Monitor configuration changes
    def config_changed(key, value):
        print(f"Configuration changed: {key} = {value}")
    
    config.add_listener(config_changed)
    
    # Modify configuration
    config.set('server.port', 9000)
    
    # Save configuration to file
    if config_file:
        config.save_to_file(config_file)
    else:
        config.save_to_file('example_config.json')