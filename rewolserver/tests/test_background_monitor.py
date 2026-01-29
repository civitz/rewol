#!/usr/bin/env python3
"""
Test script for background monitoring functionality
"""

import sys
import os
import time
import threading
from unittest.mock import patch, MagicMock

# Add the rewolserver module to path
sys.path.insert(0, "/home/roberto/workspace/vibecode/rewol/rewolserver")

import rewol


def test_cache_functionality():
    """Test the ProxyStatusCache class"""
    print("Testing ProxyStatusCache...")

    cache = rewol.ProxyStatusCache()

    # Test initial state
    initial_data = cache.get_all()
    assert initial_data["hosts"] == {}, "Cache should be empty initially"
    assert initial_data["last_updated"] is None, "Last updated should be None initially"

    # Test replace_all
    test_data = {
        "host1": {"status": 1, "name": "host1"},
        "host2": {"status": 0, "name": "host2"},
    }
    cache.replace_all(test_data)

    updated_data = cache.get_all()
    assert len(updated_data["hosts"]) == 2, "Cache should have 2 hosts"
    assert updated_data["hosts"]["host1"]["status"] == 1, "Host1 status should be 1"
    assert updated_data["last_updated"] is not None, "Last updated should be set"

    print("✓ ProxyStatusCache tests passed")


def test_monitor_thread_creation():
    """Test BackgroundMonitorThread creation and basic functionality"""
    print("Testing BackgroundMonitorThread...")

    # Mock backends for testing
    mock_backends = [
        {"host": "test-proxy", "address": "127.0.0.1:9999", "password": "test"}
    ]

    cache = rewol.ProxyStatusCache()
    monitor = rewol.BackgroundMonitorThread(mock_backends, cache)

    # Test that monitor is created properly
    assert monitor.backends == mock_backends, "Backends should be set correctly"
    assert monitor.cache == cache, "Cache should be set correctly"
    assert not monitor.running, "Monitor should not be running initially"

    # Test cache replacement behavior
    test_data = {"test_host": {"name": "test_host", "status": 1}}
    cache.replace_all(test_data)
    assert len(cache.get_all()["hosts"]) == 1, (
        "Cache should have 1 host after replacement"
    )

    print("✓ BackgroundMonitorThread creation tests passed")


def test_api_endpoint():
    """Test the API endpoint structure"""
    print("Testing API endpoint...")

    # Create a test client
    test_client = rewol.app.test_client()

    # Test API endpoint
    response = test_client.get("/api/status")
    assert response.status_code == 200, "API endpoint should return 200"

    data = response.get_json()
    assert "success" in data, "Response should have success field"
    assert "hosts" in data, "Response should have hosts field"
    assert "last_updated" in data, "Response should have last_updated field"

    print("✓ API endpoint tests passed")


def test_thread_safety():
    """Test thread safety of cache operations with replacement strategy"""
    print("Testing thread safety...")

    cache = rewol.ProxyStatusCache()
    results = []  # To collect results from each thread

    def update_cache(thread_id):
        """Each thread builds its own data and does a single replacement"""
        thread_data = {}
        for i in range(10):
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

    # Should have 10 hosts (one thread's worth of data)
    assert len(final_data["hosts"]) == 10, (
        f"Cache should have 10 hosts, got {len(final_data['hosts'])}"
    )

    # All hosts should be from the same thread
    thread_ids = set(
        host_data.get("thread_id", -1) for host_data in final_data["hosts"].values()
    )
    assert len(thread_ids) == 1, (
        f"All hosts should be from one thread, got {len(thread_ids)} different thread IDs"
    )

    print("✓ Thread safety tests passed (replacement strategy)")


if __name__ == "__main__":
    print("Running background monitor tests...\n")

    try:
        test_cache_functionality()
        test_monitor_thread_creation()
        test_api_endpoint()
        test_thread_safety()

        print(
            "\n🎉 All tests passed! Background monitoring implementation is working correctly."
        )

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
