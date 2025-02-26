#!/usr/bin/env python3
"""
system_info_module.py - System Information Monitor

A simple example module that demonstrates the framework by collecting
and reporting system information (CPU, memory, disk usage, etc.).
"""

#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~
# Imports
#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~

import asyncio
import json
import os
import platform
import socket
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

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
# Exceptions
#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~

class SystemInfoError(ModuleError):
    """Base exception for system info errors."""
    pass

class CollectionError(SystemInfoError):
    """Error during system information collection."""
    pass

#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~
# Module Implementation
#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~

class SystemInfoModule(BaseModule):
    """
    System information monitoring module.
    
    Collects various system metrics and statistics to demonstrate
    the module framework's capabilities.
    """
    
    # Define configuration parameters
    CONFIG_PARAMS = [
        ConfigParam(
            name="collection_interval",
            default=5,
            description="Interval between data collections in seconds",
            validators=[Validator.positive]
        ),
        ConfigParam(
            name="output_file",
            default="system_info.json",
            description="File to write system information to",
            validators=[Validator.length(min_len=1)]
        ),
        ConfigParam(
            name="report_cpu",
            default=True,
            description="Whether to report CPU information",
            type=bool
        ),
        ConfigParam(
            name="report_memory",
            default=True,
            description="Whether to report memory information",
            type=bool
        ),
        ConfigParam(
            name="report_disk",
            default=True,
            description="Whether to report disk information",
            type=bool
        ),
        ConfigParam(
            name="report_network",
            default=True,
            description="Whether to report network information",
            type=bool
        )
    ]
    
    # No required dependencies
    DEPENDENCIES = []
    
    def __init__(
        self, 
        config=None,
        dependencies=None,
        logger=None,
        log_level=None
    ):
        """Initialize the system info module."""
        super().__init__(config, dependencies, logger, log_level)
        
        # Initialize state
        self.last_collection = None
        self.current_info = {}
        
        # Create components
        self.cpu_collector = CpuCollectorComponent("cpu_collector", self)
        self.memory_collector = MemoryCollectorComponent("memory_collector", self)
        self.disk_collector = DiskCollectorComponent("disk_collector", self)
        self.network_collector = NetworkCollectorComponent("network_collector", self)
        self.report_writer = ReportWriterComponent("report_writer", self)
        
        # Register components
        self.components = {
            "cpu_collector": self.cpu_collector,
            "memory_collector": self.memory_collector,
            "disk_collector": self.disk_collector,
            "network_collector": self.network_collector,
            "report_writer": self.report_writer
        }
    
    async def run(self):
        """Run the system info module."""
        await self._log(LogLevel.INFO, f"Starting system info collection every {self.config['collection_interval']}s")
        
        # Add basic system information that doesn't change
        self.current_info["system"] = {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
            "psutil_available": PSUTIL_AVAILABLE
        }
        
        # Start the base implementation (which starts components)
        await super().run()
        
        # The super method handles the main loop and component management
    
    def get_current_info(self) -> Dict[str, Any]:
        """Get the current system information."""
        # Add timestamp to the info
        self.current_info["timestamp"] = datetime.now().isoformat()
        self.current_info["uptime"] = self.get_uptime()
        return self.current_info

#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~
# Component Implementations
#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~

class CpuCollectorComponent(BaseComponent):
    """Component for collecting CPU information."""
    
    async def init(self):
        """Initialize the CPU collector."""
        await super().init()
        self.enabled = self.parent.config["report_cpu"]
        if not self.enabled:
            await self._log(LogLevel.INFO, "CPU collection disabled")
    
    async def run(self):
        """Run the CPU collector."""
        await super().run()  # Log component start
        
        try:
            while self.parent.running:
                if self.enabled:
                    try:
                        await self._collect_cpu_info()
                    except Exception as e:
                        await self._log(LogLevel.ERROR, f"Error collecting CPU info: {e}")
                
                # Wait for next collection
                await asyncio.sleep(self.parent.config["collection_interval"])
        except asyncio.CancelledError:
            await self._log(LogLevel.INFO, "CPU collector stopped")
    
    async def _collect_cpu_info(self):
        """Collect CPU information."""
        cpu_info = {}
        
        if PSUTIL_AVAILABLE:
            # Collect detailed CPU info with psutil
            cpu_info["percent"] = psutil.cpu_percent(interval=0.1)
            cpu_info["count"] = {
                "physical": psutil.cpu_count(logical=False),
                "logical": psutil.cpu_count(logical=True)
            }
            cpu_info["frequency"] = {}
            if hasattr(psutil, "cpu_freq") and psutil.cpu_freq():
                freq = psutil.cpu_freq()
                cpu_info["frequency"] = {
                    "current": freq.current,
                    "min": freq.min,
                    "max": freq.max
                }
            
            # Get per-CPU usage
            cpu_info["per_cpu"] = psutil.cpu_percent(interval=0.1, percpu=True)
            
            # Get load averages on Unix-like systems
            if hasattr(psutil, "getloadavg"):
                cpu_info["load_avg"] = list(psutil.getloadavg())
        else:
            # Basic CPU info without psutil
            cpu_info["count"] = os.cpu_count()
        
        # Update module's current info
        self.parent.current_info["cpu"] = cpu_info
        
        await self._log(LogLevel.VERBOSE, f"Collected CPU info: {len(cpu_info)} metrics")


class MemoryCollectorComponent(BaseComponent):
    """Component for collecting memory information."""
    
    async def init(self):
        """Initialize the memory collector."""
        await super().init()
        self.enabled = self.parent.config["report_memory"]
        if not self.enabled:
            await self._log(LogLevel.INFO, "Memory collection disabled")
    
    async def run(self):
        """Run the memory collector."""
        await super().run()  # Log component start
        
        try:
            while self.parent.running:
                if self.enabled:
                    try:
                        await self._collect_memory_info()
                    except Exception as e:
                        await self._log(LogLevel.ERROR, f"Error collecting memory info: {e}")
                
                # Wait for next collection
                await asyncio.sleep(self.parent.config["collection_interval"])
        except asyncio.CancelledError:
            await self._log(LogLevel.INFO, "Memory collector stopped")
    
    async def _collect_memory_info(self):
        """Collect memory information."""
        memory_info = {}
        
        if PSUTIL_AVAILABLE:
            # Virtual memory
            virtual = psutil.virtual_memory()
            memory_info["virtual"] = {
                "total": virtual.total,
                "available": virtual.available,
                "percent": virtual.percent,
                "used": virtual.used,
                "free": virtual.free
            }
            
            # Swap memory
            swap = psutil.swap_memory()
            memory_info["swap"] = {
                "total": swap.total,
                "used": swap.used,
                "free": swap.free,
                "percent": swap.percent
            }
        else:
            # Basic memory info without psutil
            memory_info["note"] = "psutil not available, limited memory information"
        
        # Update module's current info
        self.parent.current_info["memory"] = memory_info
        
        await self._log(LogLevel.VERBOSE, "Collected memory information")


class DiskCollectorComponent(BaseComponent):
    """Component for collecting disk information."""
    
    async def init(self):
        """Initialize the disk collector."""
        await super().init()
        self.enabled = self.parent.config["report_disk"]
        if not self.enabled:
            await self._log(LogLevel.INFO, "Disk collection disabled")
    
    async def run(self):
        """Run the disk collector."""
        await super().run()  # Log component start
        
        try:
            while self.parent.running:
                if self.enabled:
                    try:
                        await self._collect_disk_info()
                    except Exception as e:
                        await self._log(LogLevel.ERROR, f"Error collecting disk info: {e}")
                
                # Wait for next collection
                await asyncio.sleep(self.parent.config["collection_interval"])
        except asyncio.CancelledError:
            await self._log(LogLevel.INFO, "Disk collector stopped")
    
    async def _collect_disk_info(self):
        """Collect disk information."""
        disk_info = {}
        
        if PSUTIL_AVAILABLE:
            # Get disk partitions
            partitions = []
            for partition in psutil.disk_partitions():
                part_info = {
                    "device": partition.device,
                    "mountpoint": partition.mountpoint,
                    "fstype": partition.fstype
                }
                
                # Get usage info if accessible
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    part_info["usage"] = {
                        "total": usage.total,
                        "used": usage.used,
                        "free": usage.free,
                        "percent": usage.percent
                    }
                except (PermissionError, OSError):
                    part_info["usage"] = "Error accessing usage info"
                
                partitions.append(part_info)
            
            disk_info["partitions"] = partitions
            
            # Get disk I/O if available
            try:
                io = psutil.disk_io_counters()
                disk_info["io"] = {
                    "read_count": io.read_count,
                    "write_count": io.write_count,
                    "read_bytes": io.read_bytes,
                    "write_bytes": io.write_bytes,
                    "read_time": io.read_time,
                    "write_time": io.write_time
                }
            except Exception as e:
                disk_info["io"] = f"Error getting disk I/O: {e}"
        else:
            # Basic disk info without psutil
            disk_info["note"] = "psutil not available, limited disk information"
            
            # Try to get some basic info
            if os.name == 'posix':
                try:
                    df = os.popen("df -h /").read().strip().split('\n')[1].split()
                    disk_info["root"] = {
                        "filesystem": df[0],
                        "size": df[1],
                        "used": df[2],
                        "available": df[3],
                        "percent": df[4]
                    }
                except:
                    disk_info["root"] = "Error getting disk info"
        
        # Update module's current info
        self.parent.current_info["disk"] = disk_info
        
        await self._log(LogLevel.VERBOSE, "Collected disk information")


class NetworkCollectorComponent(BaseComponent):
    """Component for collecting network information."""
    
    async def init(self):
        """Initialize the network collector."""
        await super().init()
        self.enabled = self.parent.config["report_network"]
        if not self.enabled:
            await self._log(LogLevel.INFO, "Network collection disabled")
        
        # Store previous counters for calculating rates
        self.previous_counters = None
        self.previous_time = None
    
    async def run(self):
        """Run the network collector."""
        await super().run()  # Log component start
        
        try:
            while self.parent.running:
                if self.enabled:
                    try:
                        await self._collect_network_info()
                    except Exception as e:
                        await self._log(LogLevel.ERROR, f"Error collecting network info: {e}")
                
                # Wait for next collection
                await asyncio.sleep(self.parent.config["collection_interval"])
        except asyncio.CancelledError:
            await self._log(LogLevel.INFO, "Network collector stopped")
    
    async def _collect_network_info(self):
        """Collect network information."""
        network_info = {}
        
        if PSUTIL_AVAILABLE:
            # Get network addresses
            interfaces = {}
            for interface, addresses in psutil.net_if_addrs().items():
                interfaces[interface] = []
                for addr in addresses:
                    addr_info = {
                        "family": str(addr.family),
                        "address": addr.address,
                        "netmask": addr.netmask,
                        "broadcast": addr.broadcast if hasattr(addr, 'broadcast') else None
                    }
                    interfaces[interface].append(addr_info)
            
            network_info["interfaces"] = interfaces
            
            # Get network stats
            stats = {}
            for interface, stats_data in psutil.net_if_stats().items():
                stats[interface] = {
                    "isup": stats_data.isup,
                    "speed": stats_data.speed,
                    "mtu": stats_data.mtu
                }
            
            network_info["stats"] = stats
            
            # Get network I/O counters
            current_time = time.time()
            counters = psutil.net_io_counters(pernic=True)
            
            # Calculate rates if we have previous measurements
            if self.previous_counters and self.previous_time:
                time_diff = current_time - self.previous_time
                
                # Skip if time difference is too small
                if time_diff > 0.1:
                    rates = {}
                    for interface, counter in counters.items():
                        if interface in self.previous_counters:
                            prev = self.previous_counters[interface]
                            rates[interface] = {
                                "bytes_sent": counter.bytes_sent,
                                "bytes_recv": counter.bytes_recv,
                                "packets_sent": counter.packets_sent,
                                "packets_recv": counter.packets_recv,
                                "bytes_sent_rate": (counter.bytes_sent - prev.bytes_sent) / time_diff,
                                "bytes_recv_rate": (counter.bytes_recv - prev.bytes_recv) / time_diff,
                                "packets_sent_rate": (counter.packets_sent - prev.packets_sent) / time_diff,
                                "packets_recv_rate": (counter.packets_recv - prev.packets_recv) / time_diff
                            }
                    
                    network_info["io"] = rates
            
            # Save current counters for next time
            self.previous_counters = counters
            self.previous_time = current_time
        else:
            # Basic network info without psutil
            network_info["note"] = "psutil not available, limited network information"
            
            # Get hostname and basic info
            network_info["hostname"] = socket.gethostname()
            try:
                network_info["host_ip"] = socket.gethostbyname(socket.gethostname())
            except:
                network_info["host_ip"] = "Unknown"
        
        # Update module's current info
        self.parent.current_info["network"] = network_info
        
        await self._log(LogLevel.VERBOSE, "Collected network information")


class ReportWriterComponent(BaseComponent):
    """Component for writing system information to a file."""
    
    async def init(self):
        """Initialize the report writer."""
        await super().init()
        self.output_file = Path(self.parent.config["output_file"])
        await self._log(LogLevel.INFO, f"Will write reports to {self.output_file}")
    
    async def run(self):
        """Run the report writer."""
        await super().run()  # Log component start
        
        try:
            while self.parent.running:
                try:
                    # Get current info from parent
                    info = self.parent.get_current_info()
                    
                    # Write to file
                    await self._write_report(info)
                    
                except Exception as e:
                    await self._log(LogLevel.ERROR, f"Error writing report: {e}")
                
                # Wait for next write
                await asyncio.sleep(self.parent.config["collection_interval"])
        except asyncio.CancelledError:
            await self._log(LogLevel.INFO, "Report writer stopped")
    
    async def _write_report(self, info: Dict[str, Any]):
        """Write system information to file."""
        try:
            # Ensure output directory exists
            os.makedirs(self.output_file.parent, exist_ok=True)
            
            # Write to file atomically using a temporary file
            temp_file = self.output_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(info, f, indent=2, default=str)
            
            # Replace the original file
            temp_file.replace(self.output_file)
            
            await self._log(LogLevel.VERBOSE, f"Wrote report to {self.output_file}")
            
        except Exception as e:
            raise CollectionError(f"Failed to write report: {e}")

#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~
# Module Interface  
#-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~-+-~

async def main():
    """Run the system info module as a standalone program."""
    config = {
        "collection_interval": 5,
        "output_file": "system_info.json",
        "report_cpu": True,
        "report_memory": True,
        "report_disk": True,
        "report_network": True
    }
    
    await run_module(
        SystemInfoModule,
        config=config,
        log_level="VERBOSE"
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nSystem info module stopped")
    except Exception as e:
        print(f"Error running system info module: {e}", file=sys.stderr)