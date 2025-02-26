"""
Python Module Framework

A modular framework for building structured Python applications using
a component-based architecture with standardized patterns for configuration,
logging, dependency management, and lifecycle handling.
"""

__version__ = "0.1.0"

# Import core components for easy access
from .module_base import (
    BaseModule,
    BaseComponent,
    LogLevel,
    ConfigParam,
    Dependency,
    ModuleError,
    ConfigError,
    DependencyError,
    OperationError,
    run_module,
    Validator,
)

from .log_manager import (
    LogManager,
    ComponentLogger,
    LogEvent,
    LoggingError,
    create_log_manager,
    get_component_logger,
)

from .config_manager import (
    ConfigManager,
    ConfigValue,
    create_config_manager,
    find_config_file,
)

# Define what's available via import *
__all__ = [
    # module_base exports
    "BaseModule",
    "BaseComponent",
    "LogLevel",
    "ConfigParam",
    "Dependency",
    "ModuleError",
    "ConfigError",
    "DependencyError",
    "OperationError",
    "run_module",
    "Validator",
    
    # log_manager exports
    "LogManager",
    "ComponentLogger",
    "LogEvent",
    "LoggingError",
    "create_log_manager",
    "get_component_logger",
    
    # config_manager exports
    "ConfigManager",
    "ConfigValue",
    "create_config_manager",
    "find_config_file",
]