"""
Test suite for background monitoring functionality
"""

import pytest
import sys
import os
import time
import threading
from datetime import datetime, timedelta

# Add the rewolserver module to path
sys.path.insert(0, "/home/roberto/workspace/vibecode/rewol/rewolserver")

import rewol


def test_cache_initialization():
    """Test ProxyStatusCache initialization"""
    cache = rewol.ProxyStatusCache()

    # Initial state should be empty
    data = cache.get_all()
    assert data["hosts"] == {}
    assert data["last_updated"] is None

    # Cache should not be stale initially
    assert cache.is_stale(30) is True  # None timestamp is considered stale


def test_cache_replacement():
    """Test cache replacement behavior"""
    cache = rewol.ProxyStatusCache()

    # Add initial data
    initial_data = {
        "host1": {"name": "host1", "status": 1, "backend_name": "Proxy1"},
        "host2": {"name": "host2", "status": 0, "backend_name": "Proxy1"},
    }
    cache.replace_all(initial_data)

    # Verify initial data
    data = cache.get_all()
    assert len(data["hosts"]) == 2
    assert "host1" in data["hosts"]
    assert "host2" in data["hosts"]
    assert data["hosts"]["host1"]["status"] == 1
    assert data["hosts"]["host2"]["status"] == 0

    # Replace with different data
    new_data = {"host3": {"name": "host3", "status": 1, "backend_name": "Proxy2"}}
    cache.replace_all(new_data)

    # Verify replacement - old hosts should be gone
    data = cache.get_all()
    assert len(data["hosts"]) == 1
    assert "host1" not in data["hosts"]
    assert "host2" not in data["hosts"]
    assert "host3" in data["hosts"]
    assert data["hosts"]["host3"]["status"] == 1


def test_cache_staleness():
    """Test cache staleness detection (monitoring health check)"""
    cache = rewol.ProxyStatusCache()

    # Cache should be stale when never updated (monitoring not started)
    assert cache.is_stale(30) is True

    # Add data and check staleness
    test_data = {"host1": {"name": "host1", "status": 1}}
    cache.replace_all(test_data)

    # With replacement strategy, cache is fresh immediately after update
    # This checks if monitoring is working (updating regularly)
    assert cache.is_stale(1) is False

    # Very short threshold should make it appear stale
    # This simulates checking if monitoring updated very recently
    assert cache.is_stale(1) is False  # Just updated, should be fresh

    # Wait a bit and check again
    time.sleep(2)
    assert cache.is_stale(1) is True  # Now older than 1 second, should be stale


def test_cache_thread_safety():
    """Test thread-safe cache operations"""
    cache = rewol.ProxyStatusCache()
    results = []

    def update_cache(thread_id):
        """Each thread builds its own data and does a single replacement"""
        thread_data = {}
        for i in range(5):
            thread_data[f"host_{thread_id}_{i}"] = {
                "status": 1,
                "name": f"host_{thread_id}_{i}",
                "thread_id": thread_id,
            }

        # Simulate some processing time
        time.sleep(0.01 * thread_id)

        # Do the replacement
        cache.replace_all(thread_data)

        # Record what this thread wrote
        results.append((thread_id, len(thread_data)))

    # Create multiple threads updating cache simultaneously
    threads = []
    for thread_id in range(3):
        thread = threading.Thread(target=update_cache, args=(thread_id,))
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    # With replacement strategy, final cache should contain data from the last thread to complete
    final_data = cache.get_all()

    # Should have 5 hosts (one thread's worth of data)
    assert len(final_data["hosts"]) == 5

    # All hosts should be from the same thread
    thread_ids = set(
        host_data.get("thread_id", -1) for host_data in final_data["hosts"].values()
    )
    assert len(thread_ids) == 1


def test_monitor_thread_creation():
    """Test BackgroundMonitorThread creation"""
    mock_backends = [
        {"host": "test-proxy", "address": "127.0.0.1:9999", "password": "test"}
    ]

    cache = rewol.ProxyStatusCache()
    monitor = rewol.BackgroundMonitorThread(mock_backends, cache)

    # Verify monitor properties
    assert monitor.backends == mock_backends
    assert monitor.cache == cache
    assert not monitor.running
    assert monitor.monitor_interval == 5


def test_api_endpoint():
    """Test API endpoint functionality"""
    test_client = rewol.app.test_client()

    # Test API endpoint
    response = test_client.get("/api/status")
    assert response.status_code == 200

    data = response.get_json()
    assert data["success"] is True
    assert "hosts" in data
    assert "last_updated" in data
    assert "cache_info" in data


def test_monitoring_integration():
    """Test full monitoring integration"""
    # Create mock backends that will fail (for testing)
    mock_backends = [
        {
            "host": "Test Proxy",
            "address": "127.0.0.1:9999",  # Non-existent
            "password": "test123",
        }
    ]

    cache = rewol.ProxyStatusCache()
    monitor = rewol.BackgroundMonitorThread(mock_backends, cache)

    # Start monitoring
    monitor.start()
    assert monitor.running is True

    # Wait for one monitoring cycle
    time.sleep(6)  # 5s interval + buffer

    # Check cache state
    data = cache.get_all()
    assert len(data["hosts"]) > 0  # Should have placeholder for down backend

    # Stop monitoring
    monitor.stop()
    assert monitor.running is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
