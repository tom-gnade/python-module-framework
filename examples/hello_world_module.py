#!/usr/bin/env python3
"""
hello_world_module.py - Minimal Example Module

A simple "Hello World" example showing the minimal implementation
of a module using the framework.
"""

#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~
# Imports
#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~

import asyncio
from datetime import datetime

# Import the module framework
try:
    from python_module_framework import (
        BaseModule, BaseComponent, LogLevel, ConfigParam, ...
    )
except ImportError:
    # Try local import for standalone usage
    try:
        from module_base import (
            BaseModule, BaseComponent, LogLevel, ConfigParam, ...
        )
    except ImportError:
        raise RuntimeError(
            "Fatal error: python_module_framework package or module_base.py is required."
            "Please install the package or ensure module_base.py is in your PYTHONPATH."
        )

#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~
# Module Implementation
#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~

class HelloWorldModule(BaseModule):
    """
    A minimal 'Hello World' module implementation.
    
    This demonstrates the most basic usage of the framework.
    """
    
    # Define configuration parameters
    CONFIG_PARAMS = [
        ConfigParam(
            name="message",
            default="Hello, World!",
            description="Message to display"
        ),
        ConfigParam(
            name="interval",
            default=1.0,
            description="Interval between messages in seconds"
        ),
        ConfigParam(
            name="count",
            default=5,
            description="Number of messages to display (0 for infinite)"
        )
    ]
    
    # No dependencies required
    DEPENDENCIES = []
    
    def __init__(
        self, 
        config=None,
        dependencies=None,
        logger=None,
        log_level=None
    ):
        """Initialize the Hello World module."""
        super().__init__(config, dependencies, logger, log_level)
        
        # Create a greeter component
        self.greeter = GreeterComponent("greeter", self)
        
        # Register components
        self.components = {
            "greeter": self.greeter
        }
    
    async def run(self):
        """Run the Hello World module."""
        await self._log(LogLevel.INFO, "Starting Hello World module")
        
        # Start the base implementation (which starts components)
        await super().run()

#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~
# Component Implementation
#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~

class GreeterComponent(BaseComponent):
    """Component that displays greeting messages."""
    
    async def run(self):
        """Run the greeter component."""
        await super().run()  # Log component start
        
        message = self.parent.config["message"]
        interval = self.parent.config["interval"]
        count = self.parent.config["count"]
        
        try:
            if count == 0:
                # Infinite loop
                while self.parent.running:
                    await self._display_message(message)
                    await asyncio.sleep(interval)
            else:
                # Fixed number of iterations
                for i in range(count):
                    if not self.parent.running:
                        break
                    await self._display_message(f"{message} ({i+1}/{count})")
                    await asyncio.sleep(interval)
                
                await self._log(LogLevel.INFO, "Completed all messages")
        except asyncio.CancelledError:
            await self._log(LogLevel.INFO, "Greeter component cancelled")
    
    async def _display_message(self, message: str):
        """Display a message with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_message = f"[{timestamp}] {message}"
        
        # Log the message
        await self._log(LogLevel.INFO, full_message)
        
        # Print to console (this is what makes it a "Hello World")
        print(full_message)

#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~
# Module Interface  
#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~

async def main():
    """Run the Hello World module as a standalone program."""
    config = {
        "message": "Hello from Python Module Framework!",
        "interval": 1.0,
        "count": 5
    }
    
    await run_module(
        HelloWorldModule,
        config=config,
        log_level="VERBOSE"
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nHello World module stopped")
    except Exception as e:
        print(f"Error running Hello World module: {e}")