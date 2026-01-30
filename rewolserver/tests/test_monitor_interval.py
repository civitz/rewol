#!/usr/bin/env python3
"""
Test script to verify that the monitor_interval configuration is working correctly
"""

import sys
import os
import time
import tempfile

# Add the rewolserver module to path
sys.path.insert(0, "/home/roberto/workspace/vibecode/rewol/rewolserver")

import rewol


def test_configurable_monitor_interval():
    """Test that monitor_interval can be configured"""
    # Create a temporary config file with custom monitor_interval
    config_content = """
backends:
  - host: "Test Proxy"
    address: "127.0.0.1:9999"
    password: "test123"

service:
  password: "+gZLX5PKEmzZ5IrV2wuqZX9FGo7MGd+6cAwlB7vieWk="
  salt: "I8NsnxI3GHQQhPUNEvlAFPJsXtJTac3VhAjGs82bhE4="
  port: 11000
  monitor_interval: 2  # Custom interval for testing
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(config_content)
        config_path = f.name

    try:
        # Load the configuration
        config = rewol.load_config(config_path)

        # Verify the monitor_interval is read correctly
        monitor_interval = config.get("service", {}).get("monitor_interval", 5)
        assert monitor_interval == 2, (
            f"Expected monitor_interval=2, got {monitor_interval}"
        )

        # Create cache and monitor with the custom interval
        cache = rewol.ProxyStatusCache()
        backends = config.get("backends", [])
        monitor = rewol.BackgroundMonitorThread(backends, cache, monitor_interval)

        # Verify the monitor has the correct interval
        assert monitor.monitor_interval == 2, (
            f"Expected monitor.monitor_interval=2, got {monitor.monitor_interval}"
        )

        # Start and stop the monitor to ensure it works
        monitor.start()
        assert monitor.running is True

        # Wait a short time to ensure it's running
        time.sleep(1)

        # Stop the monitor
        monitor.stop()
        assert monitor.running is False

    finally:
        os.unlink(config_path)


def test_default_monitor_interval():
    """Test that default monitor_interval is used when not specified"""
    # Create a temporary config file without monitor_interval
    config_content = """
backends:
  - host: "Test Proxy"
    address: "127.0.0.1:9999"
    password: "test123"

service:
  password: "+gZLX5PKEmzZ5IrV2wuqZX9FGo7MGd+6cAwlB7vieWk="
  salt: "I8NsnxI3GHQQhPUNEvlAFPJsXtJTac3VhAjGs82bhE4="
  port: 11000
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(config_content)
        config_path = f.name

    try:
        # Load the configuration
        config = rewol.load_config(config_path)

        # Verify the default monitor_interval is used
        monitor_interval = config.get("service", {}).get("monitor_interval", 5)
        assert monitor_interval == 5, (
            f"Expected default monitor_interval=5, got {monitor_interval}"
        )

        # Create cache and monitor with the default interval
        cache = rewol.ProxyStatusCache()
        backends = config.get("backends", [])
        monitor = rewol.BackgroundMonitorThread(backends, cache, monitor_interval)

        # Verify the monitor has the default interval
        assert monitor.monitor_interval == 5, (
            f"Expected monitor.monitor_interval=5, got {monitor.monitor_interval}"
        )

    finally:
        os.unlink(config_path)


if __name__ == "__main__":
    # Run tests directly if executed as script
    test_configurable_monitor_interval()
    test_default_monitor_interval()
    print("All monitor interval tests passed!")
