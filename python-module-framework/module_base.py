#!/usr/bin/env python3
"""
module_base.py - Core Module Architecture Framework

This is the foundation of the modular Python framework, providing
standardized patterns for configuration, logging, dependency management,
and component lifecycles.

Features:
- Declarative configuration with validation
- Dependency injection with interface validation
- Component-based architecture
- Standardized logging
- Clean lifecycle management (init, run, stop, cleanup)
- All your base are belong to us!
"""

#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~
# Imports
#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~

import asyncio
import enum
import inspect
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Union, List, Callable, Type, TypeVar, Set
from typing import Pattern, get_type_hints, cast, Generator

#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~
# Type Definitions
#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~

class LogLevel(str, enum.Enum):
    """Standard log levels used across all modules."""
    VERBOSE = 'VERBOSE'
    INFO = 'INFO'
    WARNING = 'WARNING'
    ERROR = 'ERROR'
    
    @classmethod
    def from_string(cls, level_str: str) -> 'LogLevel':
        """Convert string to LogLevel, defaulting to INFO for unknown values."""
        try:
            return cls[level_str.upper()]
        except (KeyError, AttributeError):
            return cls.INFO
    
    @classmethod
    def default(cls) -> 'LogLevel':
        """Get default log level for this module."""
        return cls.INFO

# Type for validator functions
ValidatorType = Callable[[Any], bool]

#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~
# Validators
#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~

class Validator:
    """Helper class with common validators for configuration parameters."""
    
    @staticmethod
    def positive(value: Union[int, float]) -> bool:
        """Validate that a number is positive (> 0)."""
        return value > 0
    
    @staticmethod
    def non_negative(value: Union[int, float]) -> bool:
        """Validate that a number is non-negative (>= 0)."""
        return value >= 0
    
    @staticmethod
    def port_number(value: int) -> bool:
        """Validate that a number is a valid port (1-65535)."""
        return isinstance(value, int) and 1 <= value <= 65535
    
    @staticmethod
    def in_range(min_val: Union[int, float], max_val: Union[int, float]) -> ValidatorType:
        """Create a validator that checks if a value is within a range."""
        return lambda x: min_val <= x <= max_val
    
    @staticmethod
    def one_of(valid_values: List[Any]) -> ValidatorType:
        """Create a validator that checks if a value is one of a set of valid values."""
        return lambda x: x in valid_values
    
    @staticmethod
    def matches(pattern: Union[str, Pattern]) -> ValidatorType:
        """Create a validator that checks if a string matches a regex pattern."""
        if isinstance(pattern, str):
            compiled_pattern = re.compile(pattern)
        else:
            compiled_pattern = pattern
            
        return lambda x: (isinstance(x, str) and 
                         compiled_pattern.match(x) is not None)
    
    @staticmethod
    def ip_address(value: str) -> bool:
        """Validate that a string is an IP address."""
        pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        if not re.match(pattern, value):
            return False
            
        # Check each octet is in valid range
        for octet in value.split('.'):
            if not (0 <= int(octet) <= 255):
                return False
                
        return True
    
    @staticmethod
    def hostname(value: str) -> bool:
        """Validate that a string is a valid hostname."""
        # Simple hostname validation - RFC 1123
        pattern = r'^(([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9])\.)*([A-Za-z0-9]|[A-Za-z0-9][A-Za-z0-9\-]*[A-Za-z0-9])$'
        return isinstance(value, str) and re.match(pattern, value) is not None
    
    @staticmethod
    def email(value: str) -> bool:
        """Validate that a string is an email address."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return isinstance(value, str) and re.match(pattern, value) is not None
    
    @staticmethod
    def url(value: str) -> bool:
        """Validate that a string is a URL."""
        pattern = r'^(http|https)://[a-zA-Z0-9]+([\-\.]{1}[a-zA-Z0-9]+)*\.[a-zA-Z]{2,5}(:[0-9]{1,5})?(\/.*)?$'
        return isinstance(value, str) and re.match(pattern, value) is not None
    
    @staticmethod
    def length(min_len: int = 0, max_len: Optional[int] = None) -> ValidatorType:
        """Create a validator that checks string length."""
        def validate_length(value):
            if not hasattr(value, '__len__'):
                return False
            if max_len is not None:
                return min_len <= len(value) <= max_len
            return min_len <= len(value)
        return validate_length

#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~
# Configuration & Dependency Declarations
#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~

@dataclass
class ConfigParam:
    """
    Explicit declaration of a configuration parameter.
    
    This provides a standardized way to define expected configuration
    parameters with validation, documentation, and defaults.
    """
    name: str
    default: Any
    description: str
    type: Type = None
    required: bool = False
    validators: List[ValidatorType] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate and setup after initialization."""
        # Infer type from default value if not provided
        if self.type is None and self.default is not None:
            self.type = type(self.default)
    
    def validate(self, value: Any) -> Any:
        """
        Validate and possibly convert a value.
        
        Args:
            value: The value to validate
            
        Returns:
            The validated and possibly converted value
            
        Raises:
            ValueError: If validation fails
        """
        # Handle missing values
        if value is None:
            if self.required:
                raise ValueError(f"Missing required parameter '{self.name}'")
            return self.default
            
        # Type conversion if needed
        if self.type and not isinstance(value, self.type):
            try:
                value = self.type(value)
            except (ValueError, TypeError):
                raise ValueError(
                    f"Parameter '{self.name}' should be of type {self.type.__name__}, "
                    f"got {type(value).__name__}"
                )
                
        # Custom validators
        for i, validator in enumerate(self.validators):
            if not validator(value):
                raise ValueError(
                    f"Parameter '{self.name}' failed validation "
                    f"(validator {i+1}): value={value}"
                )
                
        return value


@dataclass
class Dependency:
    """
    Explicit declaration of a required dependency.
    
    This provides a standardized way to define required external dependencies
    with documentation and interface expectations.
    """
    name: str
    description: str
    required: bool = True
    methods: Set[str] = field(default_factory=set)
    attributes: Set[str] = field(default_factory=set)
    
    def validate(self, dependency: Any) -> bool:
        """
        Validate that a dependency meets requirements.
        
        Args:
            dependency: The dependency object to validate
            
        Returns:
            True if valid
            
        Raises:
            ValueError: If dependency doesn't meet requirements
        """
        # Check required methods
        for method in self.methods:
            if not hasattr(dependency, method) or not callable(getattr(dependency, method)):
                raise ValueError(
                    f"Dependency '{self.name}' missing required method '{method}'"
                )
                
        # Check required attributes
        for attr in self.attributes:
            if not hasattr(dependency, attr):
                raise ValueError(
                    f"Dependency '{self.name}' missing required attribute '{attr}'"
                )
                
        return True

#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~
# Helper Classes
#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~

class ConsoleLogger:
    """Standard console logger used when no logger is provided."""
    
    def __init__(self, min_level: LogLevel = LogLevel.default(), prefix: str = None):
        self.min_level = min_level
        # Use caller's module name if no prefix
        if prefix is None:
            frame = inspect.currentframe()
            try:
                frame = frame.f_back
                module = Path(frame.f_globals['__file__']).stem
                prefix = module
            except (AttributeError, KeyError):
                prefix = "unknown"
            finally:
                del frame  # Avoid reference cycles
        
        self.prefix = f"[{prefix}] " if prefix else ""
        
    def _should_log(self, level: LogLevel) -> bool:
        """Check if this level should be logged."""
        level_values = {
            LogLevel.VERBOSE: 0,
            LogLevel.INFO: 1,
            LogLevel.WARNING: 2,
            LogLevel.ERROR: 3
        }
        return level_values.get(level, 0) >= level_values.get(self.min_level, 1)
    
    async def log(self, level: LogLevel, message: str):
        """Log a message if level is sufficient."""
        if self._should_log(level):
            print(f"{self.prefix}[{level.value}] {message}", file=sys.stderr)
    
    async def verbose(self, message: str):
        """Log at VERBOSE level."""
        if self._should_log(LogLevel.VERBOSE):
            await self.log(LogLevel.VERBOSE, message)
    
    async def info(self, message: str):
        """Log at INFO level."""
        if self._should_log(LogLevel.INFO):
            await self.log(LogLevel.INFO, message)
    
    async def warning(self, message: str):
        """Log at WARNING level."""
        if self._should_log(LogLevel.WARNING):
            await self.log(LogLevel.WARNING, message)
    
    async def error(self, message: str):
        """Log at ERROR level."""
        if self._should_log(LogLevel.ERROR):
            await self.log(LogLevel.ERROR, message)

#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~
# Exceptions
#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~

class ModuleError(Exception):
    """Base exception for all module errors."""
    pass

class ConfigError(ModuleError):
    """Configuration-related errors."""
    pass

class DependencyError(ModuleError):
    """Errors related to missing or invalid dependencies."""
    pass

class OperationError(ModuleError):
    """Errors during module operation."""
    pass

#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~
# Base Classes
#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~

class BaseModule:
    """
    Base module class that all modules must extend.
    
    A module is an executable unit that coordinates components
    and manages its own lifecycle.
    
    To use this base class, define:
    1. CONFIG_PARAMS: List of ConfigParam objects defining configuration
    2. DEPENDENCIES: List of Dependency objects defining dependencies
    """
    
    # Modules must override these with their own declarations
    CONFIG_PARAMS: List[ConfigParam] = []
    DEPENDENCIES: List[Dependency] = []
    
    def __init__(
        self, 
        config: Optional[Union[Dict[str, Any], object]] = None, 
        dependencies: Optional[Dict[str, Any]] = None,
        logger: Optional[Any] = None,
        log_level: Optional[Union[str, LogLevel]] = None,
        module_id: Optional[str] = None
    ):
        """
        Initialize module with configuration independence.
        
        Args:
            config: Configuration as dict, object with attributes, or None (uses defaults)
            dependencies: Dictionary of injected dependencies
            logger: Logger instance or None (uses console logger)
            log_level: Override default log level for this instance
            module_id: Optional explicit module identifier override
        """
        # Get module name from class name
        self.module_name = self.__class__.__name__
        
        # Get module identifier (stem of filename or explicit override)
        if module_id:
            self.module_id = module_id
        else:
            try:
                # Try to get the stem of the Python file
                frame = inspect.currentframe()
                module = inspect.getmodule(frame.f_back)
                self.module_id = Path(module.__file__).stem
            except (AttributeError, TypeError):
                # Fall back to lowercase class name
                self.module_id = self.module_name.lower()
            finally:
                del frame  # Avoid reference cycles
        
        # Set up logging
        self.log_level = LogLevel.from_string(log_level) if log_level else LogLevel.default()
        self.logger = logger or ConsoleLogger(self.log_level, prefix=self.module_name)
        
        # Parse and validate configuration
        self.config = self._parse_config(config)
        
        # Store and validate dependencies
        self.dependencies = dependencies or {}
        self._validate_dependencies()
        
        # Initialize state
        self.running = False
        self.start_time = None
        
        # Initialize components dictionary
        self.components = {}
        
    def _validate_dependencies(self):
        """Check that all required dependencies are present and valid."""
        for dep_spec in self.DEPENDENCIES:
            # Check if dependency exists
            if dep_spec.name not in self.dependencies:
                if dep_spec.required:
                    raise DependencyError(f"Missing required dependency: '{dep_spec.name}' - {dep_spec.description}")
                continue
                
            # Validate dependency interface
            try:
                dep_spec.validate(self.dependencies[dep_spec.name])
            except ValueError as e:
                raise DependencyError(str(e))
        
    def _parse_config(self, config: Optional[Union[Dict[str, Any], object]]) -> Dict[str, Any]:
        """
        Parse configuration from various sources.
        
        Args:
            config: Configuration as dict, object with attributes, or None
            
        Returns:
            Dict with validated configuration values
        """
        # Start with defaults from parameter declarations
        result = {}
        config_dict = {}  # Normalized config values
        
        # Build default config from declarations
        param_map = {param.name: param for param in self.CONFIG_PARAMS}
        
        # Extract existing config
        if config is None:
            # Use defaults only
            pass
        elif isinstance(config, dict):
            # Check for section matching module identifier
            if self.module_id in config:
                # Found a section specifically for this module
                module_section = config[self.module_id]
                if isinstance(module_section, dict):
                    # Use the module section
                    config_dict = module_section
                else:
                    # Invalid section format, warn and use defaults
                    print(f"Warning: Config section '{self.module_id}' is not a dictionary, using defaults", file=sys.stderr)
            else:
                # No module section, look for parameters in root level
                for param in self.CONFIG_PARAMS:
                    if param.name in config:
                        config_dict[param.name] = config[param.name]
        else:
            # It's an object with attributes
            for param in self.CONFIG_PARAMS:
                key = param.name
                prefixed_key = f"{self.module_id}_{key}"
                module_prefixed_key = f"{self.module_name}_{key}"
                
                if hasattr(config, prefixed_key):
                    # First priority: module_id_param_name
                    config_dict[key] = getattr(config, prefixed_key)
                elif hasattr(config, module_prefixed_key):
                    # Second priority: ModuleName_param_name
                    config_dict[key] = getattr(config, module_prefixed_key)
                elif hasattr(config, key):
                    # Third priority: param_name directly
                    config_dict[key] = getattr(config, key)
                    
        # Apply validation for each parameter
        for param in self.CONFIG_PARAMS:
            value = config_dict.get(param.name, param.default)
            try:
                result[param.name] = param.validate(value)
            except ValueError as e:
                raise ConfigError(str(e))
                
        return result

    async def _log(self, level: LogLevel, message: str):
        """Log with level check for efficiency."""
        if self.logger:
            # Check if we should log at this level (optimization)
            if hasattr(self.logger, '_should_log') and not self.logger._should_log(level):
                return
                
            # Use appropriate logging method
            log_method = getattr(self.logger, level.value.lower(), None)
            if log_method:
                await log_method(message)
            else:
                # Fallback if specific level method not found
                await self.logger.log(level, message)

    async def init(self):
        """Initialize module resources."""
        await self._log(LogLevel.INFO, f"Initializing {self.module_name}")
        self.start_time = time.time()
        
        # Log configuration 
        if self.logger and hasattr(self.logger, '_should_log') and self.logger._should_log(LogLevel.VERBOSE):
            config_desc = []
            for param in self.CONFIG_PARAMS:
                value = self.config.get(param.name, param.default)
                is_default = value == param.default
                config_desc.append(
                    f"{param.name}: {value} {'(default)' if is_default else ''}"
                )
            
            if config_desc:
                await self._log(LogLevel.VERBOSE, "Configuration:")
                for line in config_desc:
                    await self._log(LogLevel.VERBOSE, f"  {line}")
        
        # Initialize components
        for name, component in self.components.items():
            if hasattr(component, 'init') and callable(component.init):
                await component.init()
    
    async def run(self):
        """Run the module's main operation."""
        await self._log(LogLevel.INFO, f"Running {self.module_name}")
        self.running = True
        
        try:
            # Start components
            tasks = []
            for name, component in self.components.items():
                if hasattr(component, 'run') and callable(component.run):
                    task = asyncio.create_task(component.run(), name=f"component_{name}")
                    tasks.append(task)
            
            # Main module loop
            while self.running:
                # Derived modules implement their logic here
                await asyncio.sleep(1)
                
        except asyncio.CancelledError:
            self.running = False
        except Exception as e:
            await self._log(LogLevel.ERROR, f"Error during operation: {e}")
            self.running = False
            raise OperationError(f"Module operation failed: {e}")
        finally:
            # Cancel component tasks
            for task in tasks:
                if not task.done():
                    task.cancel()
            
            # Wait for tasks to finish
            if tasks:
                try:
                    await asyncio.wait(tasks, timeout=5)
                except asyncio.TimeoutError:
                    await self._log(LogLevel.WARNING, "Some components didn't shut down cleanly")
            
            await self._log(LogLevel.INFO, f"Stopped {self.module_name}")

    async def stop(self):
        """Stop the module and its components."""
        await self._log(LogLevel.INFO, f"Stopping {self.module_name}")
        self.running = False
        
        # Stop components in reverse order
        for name, component in reversed(list(self.components.items())):
            if hasattr(component, 'stop') and callable(component.stop):
                try:
                    await component.stop()
                except Exception as e:
                    await self._log(LogLevel.ERROR, f"Error stopping component {name}: {e}")
        
    async def cleanup(self):
        """Release module resources."""
        await self._log(LogLevel.INFO, f"Cleaning up {self.module_name}")
        
        # Clean up components in reverse order
        for name, component in reversed(list(self.components.items())):
            if hasattr(component, 'cleanup') and callable(component.cleanup):
                try:
                    await component.cleanup()
                except Exception as e:
                    await self._log(LogLevel.ERROR, f"Error cleaning up component {name}: {e}")

    def get_uptime(self) -> float:
        """Get module uptime in seconds."""
        if self.start_time:
            return time.time() - self.start_time
        return 0.0


class BaseComponent:
    """
    Base class for components within a module.
    
    A component is a functional portion of a module that performs
    a specific procedure or group of procedures.
    """
    
    def __init__(self, name: str, parent_module: 'BaseModule', config: Dict[str, Any] = None):
        """
        Initialize a component.
        
        Args:
            name: Component name
            parent_module: Parent module instance
            config: Component-specific configuration
        """
        self.name = name
        self.parent = parent_module
        self.config = config or {}
        # Share the logger with parent
        self.logger = parent_module.logger
        
    async def _log(self, level: LogLevel, message: str):
        """Log with component prefix."""
        if hasattr(self.parent, '_log'):
            # Use parent's logging method
            full_message = f"[{self.name}] {message}"
            await self.parent._log(level, full_message)
        
    async def init(self):
        """Initialize component."""
        await self._log(LogLevel.INFO, f"Initializing component")
    
    async def run(self):
        """Run component operation."""
        await self._log(LogLevel.INFO, f"Starting component")
        
        try:
            while self.parent.running:
                # Derived components implement their logic here
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            await self._log(LogLevel.INFO, f"Component task cancelled")
        except Exception as e:
            await self._log(LogLevel.ERROR, f"Component error: {e}")
            raise
        finally:
            await self._log(LogLevel.INFO, f"Component stopped")
    
    async def stop(self):
        """Stop component operation."""
        await self._log(LogLevel.INFO, f"Stopping component")
    
    async def cleanup(self):
        """Release component resources."""
        await self._log(LogLevel.INFO, f"Cleaning up component")

#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~
# Helper Functions
#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~

T = TypeVar('T', bound=BaseModule)

async def run_module(module_class: Type[T], *args, **kwargs) -> T:
    """
    Helper to run a module's full lifecycle.
    
    Args:
        module_class: Module class to instantiate
        *args, **kwargs: Arguments to pass to module constructor
        
    Returns:
        The module instance
    """
    module = module_class(*args, **kwargs)
    
    try:
        await module.init()
        await module.run()
    except KeyboardInterrupt:
        print("\nShutdown requested", file=sys.stderr)
    except Exception as e:
        print(f"Module error: {e}", file=sys.stderr)
        raise
    finally:
        try:
            await module.stop()
            await module.cleanup()
        except Exception as e:
            print(f"Error during shutdown: {e}", file=sys.stderr)
    
    return module


def load_config_from_file(filepath: Union[str, Path]) -> Dict[str, Any]:
    """
    Load configuration from a JSON file.
    
    Args:
        filepath: Path to the configuration file
        
    Returns:
        Dict with configuration values
        
    Raises:
        ConfigError: If file reading or parsing fails
    """
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        raise ConfigError(f"Configuration file not found: {filepath}")
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON in configuration file: {e}")
    except Exception as e:
        raise ConfigError(f"Error loading configuration: {e}")


def find_config_file(
    module_id: Optional[str] = None,
    file_name: str = 'config.json',
    search_paths: Optional[List[Union[str, Path]]] = None
) -> Optional[Path]:
    """
    Find a configuration file in search paths.
    
    Args:
        module_id: Optional module ID to look for module-specific config
        file_name: Name of configuration file
        search_paths: List of paths to search (defaults to common locations)
        
    Returns:
        Path to configuration file or None if not found
    """
    if search_paths is None:
        # Default search paths
        search_paths = [
            Path.cwd(),              # Current directory
            Path.home(),             # User's home directory
            Path('/etc'),            # System config directory
        ]
        
        # Add application directory
        app_dir = Path(sys.argv[0]).resolve().parent
        if app_dir not in search_paths:
            search_paths.insert(0, app_dir)
            
    # Check for module-specific config first if module_id provided
    if module_id:
        module_config_name = f"{module_id}.json"
        for path in search_paths:
            module_config_path = Path(path) / module_config_name
            if module_config_path.is_file():
                return module_config_path
    
    # Then check for common config
    for path in search_paths:
        config_path = Path(path) / file_name
        if config_path.is_file():
            return config_path
            
    return None