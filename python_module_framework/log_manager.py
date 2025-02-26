#!/usr/bin/env python3
"""
log_manager.py - Logging Management

Provides an asynchronous logging system with priority queues and standardized 
log level management. Can be used independently or with the module framework.

Features:
- Non-blocking async logging with priority queues
- Log rotation and archiving
- Level-based filtering
- Structured logging support (JSON)
- Console and file outputs
- Component-level logging
"""

#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~
# Imports
#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~

import asyncio
import datetime
import enum
import inspect
import json
import os
import shutil
import sys
import time
import traceback
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Set, Callable, TextIO

try:
    # Optional integration with module_base
    from module_base import LogLevel
except ImportError:
    # Define our own LogLevel if module_base not available
    class LogLevel(str, enum.Enum):
        """Standard log levels."""
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

#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~
# Log Event Class
#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~

@dataclass
class LogEvent:
    """Container for log event data with metadata."""
    level: LogLevel
    message: str
    timestamp: float = field(default_factory=time.time)
    service: str = "service"
    component: str = "unknown"
    module: str = "unknown"
    function: str = "unknown"
    thread_id: Optional[int] = None
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert log event to dictionary for structured logging."""
        result = asdict(self)
        result['level'] = self.level.value
        result['timestamp_iso'] = datetime.datetime.fromtimestamp(
            self.timestamp
        ).isoformat()
        return result
    
    def to_str(self, fmt: str = None) -> str:
        """Format log event as string using format string."""
        if fmt is None:
            fmt = "[{timestamp}] [{service}] [{component}] [{level}] {message}"
            
        # Default timestamp format
        timestamp_str = datetime.datetime.fromtimestamp(
            self.timestamp
        ).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        return fmt.format(
            timestamp=timestamp_str,
            service=self.service,
            component=self.component,
            module=self.module,
            function=self.function,
            level=self.level.value,
            message=self.message,
            **self.context
        )

#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~
# Exceptions
#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~

class LoggingError(Exception):
    """Base exception for logging errors."""
    pass

class LogFileError(LoggingError):
    """Error related to log file operations."""
    pass

class LogQueueError(LoggingError):
    """Error related to log queue operations."""
    pass

#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~
# Log Manager
#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~

class LogManager:
    """
    Asynchronous log manager with priority queues and multiple outputs.
    
    Features:
    - Non-blocking logging
    - Priority queues for different log levels
    - Log rotation and archiving
    - Multiple output formats (text, JSON)
    - Multiple output destinations (console, file)
    """
    
    def __init__(
        self,
        service_name: str = "service",
        log_level: Union[str, LogLevel] = LogLevel.INFO,
        log_dir: Optional[Union[str, Path]] = None,
        log_file: Optional[Union[str, Path]] = None,
        max_size: int = 10 * 1024 * 1024,  # 10 MB
        backup_count: int = 5,
        json_format: bool = False,
        console_output: bool = True,
        log_format: Optional[str] = None,
        date_format: str = "%Y-%m-%d %H:%M:%S"
    ):
        """
        Initialize log manager.
        
        Args:
            service_name: Name of the service for log identification
            log_level: Minimum log level to record
            log_dir: Directory for log files
            log_file: Log file name (defaults to service_name.log)
            max_size: Maximum log file size in bytes before rotation
            backup_count: Number of backup files to keep
            json_format: Whether to log in JSON format
            console_output: Whether to output logs to console
            log_format: Format string for log messages
            date_format: Format string for timestamps
        """
        self.service_name = service_name
        self.log_level = LogLevel.from_string(log_level) if isinstance(log_level, str) else log_level
        self.json_format = json_format
        self.console_output = console_output
        self.max_size = max_size
        self.backup_count = backup_count
        
        # Set up log format
        self.log_format = log_format
        if self.log_format is None:
            self.log_format = "[{timestamp}] [{service}] [{component}] [{level}] {message}"
        self.date_format = date_format
        
        # Set up log file
        self.log_dir = Path(log_dir) if log_dir else Path.cwd() / "logs"
        self.log_file = None
        if log_file:
            self.log_file = Path(log_file)
        elif log_dir:
            self.log_file = self.log_dir / f"{service_name}.log"
            
        # Create log directory if it doesn't exist
        if self.log_file:
            os.makedirs(self.log_dir, exist_ok=True)
            self.archive_dir = self.log_dir / "archive"
            os.makedirs(self.archive_dir, exist_ok=True)
        
        # Initialize queues with reasonable size limits
        self.high_priority_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self.low_priority_queue: asyncio.Queue = asyncio.Queue(maxsize=9000)
        
        # Initialize worker tasks
        self._tasks: List[asyncio.Task] = []
        self._shutdown_flag = asyncio.Event()
        self._file_handle: Optional[TextIO] = None
    
    async def start(self) -> None:
        """Start log processing workers."""
        if self._tasks:
            # Already started
            return
            
        # Open log file if needed
        if self.log_file:
            try:
                self._file_handle = open(self.log_file, 'a', encoding='utf-8')
            except Exception as e:
                raise LogFileError(f"Failed to open log file: {e}")
        
        # Start worker tasks
        self._tasks = [
            asyncio.create_task(self._process_high_priority()),
            asyncio.create_task(self._process_low_priority()),
            asyncio.create_task(self._monitor_log_file()),
        ]
        
        # Log startup
        await self.log(
            LogLevel.INFO,
            f"Log manager started - Level: {self.log_level.value}, "
            f"JSON: {self.json_format}, File: {self.log_file}"
        )
    
    async def stop(self) -> None:
        """Stop log processing and clean up resources."""
        if not self._tasks:
            # Already stopped
            return
            
        # Set shutdown flag and wait for queues to drain
        self._shutdown_flag.set()
        
        # Wait for high priority queue to drain
        try:
            await asyncio.wait_for(self.high_priority_queue.join(), timeout=2.0)
        except asyncio.TimeoutError:
            # Continue shutdown even if timeout
            pass
            
        # Cancel worker tasks
        for task in self._tasks:
            task.cancel()
            
        # Wait for tasks to complete
        try:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        except asyncio.CancelledError:
            pass
        
        # Close file handle
        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None
            
        # Clear task list
        self._tasks = []
    
    async def _process_high_priority(self) -> None:
        """Process high priority log events (WARNING, ERROR)."""
        while not self._shutdown_flag.is_set():
            try:
                # Get next log event with timeout
                log_event = await asyncio.wait_for(
                    self.high_priority_queue.get(),
                    timeout=0.5
                )
                
                # Process event
                await self._write_log_event(log_event)
                
                # Mark as done
                self.high_priority_queue.task_done()
                
            except asyncio.TimeoutError:
                # No new events, continue
                continue
            except asyncio.CancelledError:
                # Task cancelled, exit
                break
            except Exception as e:
                # Log processing error to stderr
                print(f"Error processing high priority log: {e}", file=sys.stderr)
                
                # Sleep briefly to avoid tight loop
                await asyncio.sleep(0.1)
    
    async def _process_low_priority(self) -> None:
        """Process low priority log events (INFO, VERBOSE)."""
        while not self._shutdown_flag.is_set():
            try:
                # Get next log event with timeout
                log_event = await asyncio.wait_for(
                    self.low_priority_queue.get(),
                    timeout=0.5
                )
                
                # Process event
                await self._write_log_event(log_event)
                
                # Mark as done
                self.low_priority_queue.task_done()
                
            except asyncio.TimeoutError:
                # No new events, continue
                continue
            except asyncio.CancelledError:
                # Task cancelled, exit
                break
            except Exception as e:
                # Log processing error to stderr
                print(f"Error processing low priority log: {e}", file=sys.stderr)
                
                # Sleep briefly to avoid tight loop
                await asyncio.sleep(0.1)
    
    async def _monitor_log_file(self) -> None:
        """Monitor log file size and rotate if needed."""
        if not self.log_file:
            # No log file to monitor
            return
            
        while not self._shutdown_flag.is_set():
            try:
                # Check file size
                if self.log_file.exists() and self.log_file.stat().st_size > self.max_size:
                    await self._rotate_logs()
                    
                # Sleep before next check
                await asyncio.sleep(10)
                
            except asyncio.CancelledError:
                # Task cancelled, exit
                break
            except Exception as e:
                # Log error to stderr
                print(f"Error monitoring log file: {e}", file=sys.stderr)
                
                # Sleep briefly to avoid tight loop
                await asyncio.sleep(1)
    
    async def _rotate_logs(self) -> None:
        """Rotate log files."""
        if not self.log_file or not self._file_handle:
            return
            
        try:
            # Close current file
            self._file_handle.close()
            
            # Rotate backup files
            for i in range(self.backup_count - 1, 0, -1):
                source = self.archive_dir / f"{self.log_file.stem}.{i}{self.log_file.suffix}"
                target = self.archive_dir / f"{self.log_file.stem}.{i+1}{self.log_file.suffix}"
                
                if source.exists():
                    if target.exists():
                        target.unlink()
                    source.rename(target)
            
            # Move current log to backup
            backup_file = self.archive_dir / f"{self.log_file.stem}.1{self.log_file.suffix}"
            if backup_file.exists():
                backup_file.unlink()
            shutil.copy2(self.log_file, backup_file)
            
            # Truncate current log file
            with open(self.log_file, 'w') as f:
                pass
                
            # Reopen log file
            self._file_handle = open(self.log_file, 'a', encoding='utf-8')
            
            # Log rotation message
            timestamp = datetime.datetime.now().strftime(self.date_format)
            rotation_message = f"[{timestamp}] [{self.service_name}] [log_manager] [INFO] Log file rotated"
            
            # Write to file directly
            print(rotation_message, file=self._file_handle, flush=True)
            
            # Write to console if enabled
            if self.console_output:
                print(rotation_message, file=sys.stderr)
                
        except Exception as e:
            # Log error to stderr
            print(f"Error rotating logs: {e}", file=sys.stderr)
            
            # Try to reopen log file
            try:
                if not self._file_handle or self._file_handle.closed:
                    self._file_handle = open(self.log_file, 'a', encoding='utf-8')
            except Exception as reopen_error:
                print(f"Failed to reopen log file: {reopen_error}", file=sys.stderr)
    
    async def _write_log_event(self, event: LogEvent) -> None:
        """Write log event to configured outputs."""
        try:
            # Format the log message
            if self.json_format:
                log_message = json.dumps(event.to_dict())
            else:
                log_message = event.to_str(self.log_format)
                
            # Write to file if configured
            if self._file_handle:
                print(log_message, file=self._file_handle, flush=True)
                
            # Write to console if enabled
            if self.console_output:
                print(log_message, file=sys.stderr)
                
        except Exception as e:
            # Last resort error logging
            print(f"Error writing log event: {e}", file=sys.stderr)
    
    def _should_log(self, level: LogLevel) -> bool:
        """Check if a log level should be logged."""
        level_values = {
            LogLevel.VERBOSE: 0,
            LogLevel.INFO: 1,
            LogLevel.WARNING: 2,
            LogLevel.ERROR: 3
        }
        return level_values.get(level, 0) >= level_values.get(self.log_level, 1)
    
    async def log(
        self,
        level: LogLevel,
        message: str,
        component: str = "log_manager",
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log a message with the specified level.
        
        Args:
            level: Log level
            message: Log message
            component: Component name
            context: Additional context data
        """
        # Check log level first (optimization)
        if not self._should_log(level):
            return
            
        # Get caller information
        frame = inspect.currentframe()
        try:
            frame = frame.f_back
            module = frame.f_globals.get('__name__', 'unknown')
            function = frame.f_code.co_name
        except (AttributeError, KeyError):
            module = 'unknown'
            function = 'unknown'
        finally:
            del frame  # Avoid reference cycles
        
        # Create log event
        event = LogEvent(
            level=level,
            message=message,
            service=self.service_name,
            component=component,
            module=module,
            function=function,
            context=context or {}
        )
        
        # Determine queue based on priority
        if level in (LogLevel.ERROR, LogLevel.WARNING):
            # High priority logs
            try:
                self.high_priority_queue.put_nowait(event)
            except asyncio.QueueFull:
                # Log to stderr if queue is full
                print(f"High priority log queue full! {event.to_str()}", file=sys.stderr)
        else:
            # Low priority logs
            try:
                self.low_priority_queue.put_nowait(event)
            except asyncio.QueueFull:
                # Drop low priority logs if queue is full
                pass
    
    async def verbose(self, message: str, component: str = "log_manager", context: Optional[Dict[str, Any]] = None) -> None:
        """Log at VERBOSE level."""
        await self.log(LogLevel.VERBOSE, message, component, context)
        
    async def info(self, message: str, component: str = "log_manager", context: Optional[Dict[str, Any]] = None) -> None:
        """Log at INFO level."""
        await self.log(LogLevel.INFO, message, component, context)
        
    async def warning(self, message: str, component: str = "log_manager", context: Optional[Dict[str, Any]] = None) -> None:
        """Log at WARNING level."""
        await self.log(LogLevel.WARNING, message, component, context)
        
    async def error(self, message: str, component: str = "log_manager", context: Optional[Dict[str, Any]] = None) -> None:
        """Log at ERROR level."""
        await self.log(LogLevel.ERROR, message, component, context)
    
    async def exception(self, exc: Exception, message: str = None, component: str = "log_manager") -> None:
        """Log an exception with traceback."""
        if message is None:
            message = f"Exception: {str(exc)}"
        else:
            message = f"{message}: {str(exc)}"
            
        # Get traceback
        tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
        tb_str = ''.join(tb)
        
        # Log with exception details
        context = {
            'exception_type': exc.__class__.__name__,
            'traceback': tb_str
        }
        
        await self.error(message, component, context)

#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~
# Component Logger
#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~

class ComponentLogger:
    """Logger for a specific component that delegates to a log manager."""
    
    def __init__(self, log_manager: LogManager, component_name: str):
        """
        Initialize component logger.
        
        Args:
            log_manager: Parent log manager
            component_name: Name of component for logging
        """
        self.log_manager = log_manager
        self.component_name = component_name
    
    async def log(self, level: LogLevel, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log at the specified level."""
        await self.log_manager.log(level, message, self.component_name, context)
        
    async def verbose(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log at VERBOSE level."""
        if self.log_manager._should_log(LogLevel.VERBOSE):
            await self.log(LogLevel.VERBOSE, message, context)
        
    async def info(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log at INFO level."""
        if self.log_manager._should_log(LogLevel.INFO):
            await self.log(LogLevel.INFO, message, context)
        
    async def warning(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log at WARNING level."""
        if self.log_manager._should_log(LogLevel.WARNING):
            await self.log(LogLevel.WARNING, message, context)
        
    async def error(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log at ERROR level."""
        if self.log_manager._should_log(LogLevel.ERROR):
            await self.log(LogLevel.ERROR, message, context)
            
    async def exception(self, exc: Exception, message: str = None) -> None:
        """Log an exception with traceback."""
        await self.log_manager.exception(exc, message, self.component_name)
    
    def _should_log(self, level: LogLevel) -> bool:
        """Check if a log level should be logged."""
        return self.log_manager._should_log(level)

#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~
# Helper Functions
#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~

def create_log_manager(
    service_name: str = "service",
    log_level: Union[str, LogLevel] = LogLevel.INFO,
    log_dir: Optional[Union[str, Path]] = None,
    log_file: Optional[Union[str, Path]] = None,
    json_format: bool = False,
    console_output: bool = True
) -> LogManager:
    """
    Create a log manager with standard settings.
    
    Args:
        service_name: Service name for logging
        log_level: Minimum log level
        log_dir: Log directory
        log_file: Log file name
        json_format: Whether to use JSON format
        console_output: Whether to output to console
        
    Returns:
        Configured LogManager instance
    """
    return LogManager(
        service_name=service_name,
        log_level=log_level,
        log_dir=log_dir,
        log_file=log_file,
        json_format=json_format,
        console_output=console_output
    )

async def get_component_logger(
    log_manager: LogManager,
    component_name: str
) -> ComponentLogger:
    """
    Get a logger for a specific component.
    
    Args:
        log_manager: Parent log manager
        component_name: Component name for logging
        
    Returns:
        ComponentLogger instance
    """
    return ComponentLogger(log_manager, component_name)

#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~
# Example Usage
#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~

async def example_usage():
    """Demonstrate log manager usage."""
    # Create log manager
    log_manager = create_log_manager(
        service_name="example",
        log_level="VERBOSE",
        log_dir="logs",
        console_output=True
    )
    
    # Start log manager
    await log_manager.start()
    
    try:
        # Log directly with log manager
        await log_manager.info("Log manager initialized")
        
        # Get component logger
        db_logger = await get_component_logger(log_manager, "database")
        
        # Log with component logger
        await db_logger.info("Database connection established")
        await db_logger.warning("Connection pool running low")
        
        # Log with context data
        await db_logger.info(
            "Query executed",
            context={
                'query_time_ms': 15,
                'rows_affected': 42
            }
        )
        
        # Log exception
        try:
            result = 1 / 0
        except Exception as e:
            await db_logger.exception(e, "Error during calculation")
        
    finally:
        # Ensure log manager is stopped
        await log_manager.stop()

if __name__ == "__main__":
    asyncio.run(example_usage())