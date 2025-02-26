"""
Test suite for the Python Module Framework.

This package contains tests for all components of the framework:
- module_base.py: Core module architecture
- log_manager.py: Logging system
- config_manager.py: Configuration management
"""

# Import test modules to make them discoverable
from .test_module_base import TestLogLevel, TestConfigParam, TestDependencyClass
from .test_module_base import TestBaseModule, TestBaseComponent, TestValidators, TestHelperFunctions

from .test_log_manager import TestLogEvent, TestLogManager, TestComponentLogger, TestHelperFunctions as LogHelperFunctions

from .test_config_manager import TestConfigManager, TestConfigValue, TestHelperFunctions as ConfigHelperFunctions

# Define what's available via import *
__all__ = [
    # module_base tests
    "TestLogLevel",
    "TestConfigParam", 
    "TestDependencyClass", 
    "TestBaseModule", 
    "TestBaseComponent", 
    "TestValidators",
    
    # log_manager tests
    "TestLogEvent",
    "TestLogManager",
    "TestComponentLogger",
    
    # config_manager tests
    "TestConfigManager",
    "TestConfigValue"
]