# Python Module Framework

A clean, declarative framework for building modular Python applications with standardized patterns for configuration, logging, dependencies, and component lifecycles.

## Features

- **Declarative Configuration**: Define configuration parameters with validation, typing, and documentation
- **Dependency Injection**: Define required dependencies with clear interface expectations
- **Component Model**: Break modules into logical components with managed lifecycles
- **Standardized Logging**: Consistent logging with level-based filtering and prefix support
- **Graceful Lifecycle Management**: Clean startup, running, and shutdown sequences
- **Self-documenting Code**: Configuration and dependencies are clearly declared

## Getting Started

1. Copy the `module_base.py` file into your project
2. Create your modules by extending `BaseModule`
3. Define configuration and dependencies using the declarative syntax
4. Break your module into components using `BaseComponent`

## Example Module

```python
#!/usr/bin/env python3
"""
example_module.py - Example Module Using the Framework
"""

import asyncio
from module_base import (
    BaseModule, BaseComponent, LogLevel, ConfigParam, Dependency,
    ModuleError, ConfigError, OperationError, run_module
)

class ExampleModule(BaseModule):
    """A simple example module."""
    
    # Declare configuration parameters
    CONFIG_PARAMS = [
        ConfigParam(
            name="interval",
            default=5,
            description="Processing interval in seconds",
            type=int,
            validators=[lambda x: x > 0]
        ),
        ConfigParam(
            name="max_items",
            default=100,
            description="Maximum number of items to process",
            type=int
        )
    ]
    
    # Declare dependencies
    DEPENDENCIES = [
        Dependency(
            name="storage",
            description="Storage service for persisting data",
            required=True,
            methods={"save", "load"}
        )
    ]
    
    def __init__(self, config=None, dependencies=None, logger=None):
        """Initialize the module."""
        super().__init__(config, dependencies, logger)
        
        # Get dependencies
        self.storage = self.dependencies["storage"]
        
        # Create components
        self.processor = ProcessorComponent("processor", self)
        
        # Register components
        self.components = {
            "processor": self.processor
        }
    
    async def run(self):
        """Run the module."""
        await self._log(LogLevel.INFO, "Example module running")
        await super().run()


class ProcessorComponent(BaseComponent):
    """Component that processes items."""
    
    async def run(self):
        """Process items periodically."""
        await super().run()
        
        try:
            while self.parent.running:
                await self._log(LogLevel.INFO, "Processing items...")
                # Process items using configured values
                max_items = self.parent.config["max_items"]
                await self._log(LogLevel.INFO, f"Processed {max_items} items")
                
                # Use parent's dependency
                await self.parent.storage.save({"processed": max_items})
                
                # Wait until next processing cycle
                await asyncio.sleep(self.parent.config["interval"])
        except asyncio.CancelledError:
            await self._log(LogLevel.INFO, "Processor stopped")

if __name__ == "__main__":
    # Mock storage for testing
    class MockStorage:
        async def save(self, data):
            print(f"Saving data: {data}")
        async def load(self, key):
            return {"data": key}
    
    # Run the module
    asyncio.run(
        run_module(
            ExampleModule,
            config={"interval": 2},
            dependencies={"storage": MockStorage()},
            log_level="VERBOSE"
        )
    )
```

## Framework Structure

- **BaseModule**: The foundation class for all modules
- **BaseComponent**: Building blocks that make up a module
- **ConfigParam**: Declarative configuration parameter definition
- **Dependency**: Declarative dependency definition
- **LogLevel**: Standard logging levels
- **run_module()**: Helper function for running a module's full lifecycle

## Best Practices

1. **Clear Module Boundaries**: Each module should handle a specific domain or functionality
2. **Component Composition**: Break complex modules into focused components
3. **Explicit Dependencies**: Always declare the dependencies a module requires
4. **Validation First**: Validate configuration and dependencies early
5. **Clean Lifecycles**: Ensure proper initialization and cleanup

## Using in Larger Projects

For larger projects:

1. Place `module_base.py` in a common utilities directory
2. Import it into each module
3. Use the framework to standardize configuration and logging across all components
4. Consider extending the framework with project-specific base classes

## License

MIT License

## Contributing

Contributions welcome! Please feel free to submit a Pull Request.