#!/usr/bin/env python3
"""
Test script to verify that the max_retries configuration is working correctly
"""

import sys
import os
import time
import tempfile
from unittest.mock import patch, MagicMock

# Add the rewolserver module to path
sys.path.insert(0, "/home/roberto/workspace/vibecode/rewol/rewolserver")

import rewol


def test_configurable_max_retries():
    """Test that max_retries can be configured"""
    print("Testing configurable max retries...")

    # Create a temporary config file with custom max_retries
    config_content = """
backends:
  - host: "Test Proxy"
    address: "127.0.0.1:9999"
    password: "test123"

service:
  password: "+gZLX5PKEmzZ5IrV2wuqZX9FGo7MGd+6cAwlB7vieWk="
  salt: "I8NsnxI3GHQQhPUNEvlAFPJsXtJTac3VhAjGs82bhE4="
  port: 11000
  max_retries: 5  # Custom retry count for testing
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(config_content)
        config_path = f.name

    try:
        # Load the configuration
        config = rewol.load_config(config_path)

        # Verify the max_retries is read correctly
        max_retries = config.get("service", {}).get("max_retries", 3)
        assert max_retries == 5, f"Expected max_retries=5, got {max_retries}"

        # Create cache and monitor with the custom retry count
        cache = rewol.ProxyStatusCache()
        backends = config.get("backends", [])
        monitor = rewol.BackgroundMonitorThread(backends, cache, 5, max_retries)

        # Verify the monitor has the correct retry count
        assert monitor.max_retries == 5, (
            f"Expected monitor.max_retries=5, got {monitor.max_retries}"
        )

        print("✓ Configurable max retries test passed")
        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        os.unlink(config_path)


def test_default_max_retries():
    """Test that default max_retries is used when not specified"""
    print("Testing default max retries...")

    # Create a temporary config file without max_retries
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

        # Verify the default max_retries is used
        max_retries = config.get("service", {}).get("max_retries", 3)
        assert max_retries == 3, f"Expected default max_retries=3, got {max_retries}"

        # Create cache and monitor with the default retry count
        cache = rewol.ProxyStatusCache()
        backends = config.get("backends", [])
        monitor = rewol.BackgroundMonitorThread(backends, cache, 5, max_retries)

        # Verify the monitor has the default retry count
        assert monitor.max_retries == 3, (
            f"Expected monitor.max_retries=3, got {monitor.max_retries}"
        )

        print("✓ Default max retries test passed")
        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        os.unlink(config_path)


def test_retry_logic():
    """Test that the retry logic works correctly"""
    print("Testing retry logic...")

    # Create a simple test to verify retry behavior
    cache = rewol.ProxyStatusCache()
    backends = [
        {
            "host": "Test Proxy",
            "address": "127.0.0.1:9999",  # Non-existent
            "password": "test123",
        }
    ]

    # Create monitor with max_retries=2
    monitor = rewol.BackgroundMonitorThread(backends, cache, 5, 2)

    # Mock the requests.get to fail consistently
    with patch("requests.get") as mock_get:
        mock_get.side_effect = Exception("Connection failed")

        # Call _check_proxy_status and verify it retries
        result = monitor._check_proxy_status(backends[0])

        # Should be None (failure) but should have tried 2 times
        assert result is None, "Expected None result for failed request"
        assert mock_get.call_count == 2, (
            f"Expected 2 retry attempts, got {mock_get.call_count}"
        )

    print("✓ Retry logic test passed")
    return True


def run_all_tests():
    """Run all retry tests"""
    print("Running retry configuration tests...\n")

    try:
        success1 = test_configurable_max_retries()
        success2 = test_default_max_retries()
        success3 = test_retry_logic()

        if success1 and success2 and success3:
            print("\n🎉 All retry tests passed!")
            return True
        else:
            print("\n❌ Some tests failed")
            return False

    except Exception as e:
        print(f"\n❌ Test execution failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
