"""
Simple test suite for background monitoring functionality
"""

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
    print("Testing cache initialization...")
    cache = rewol.ProxyStatusCache()

    # Initial state should be empty
    data = cache.get_all()
    assert data["hosts"] == {}
    assert data["last_updated"] is None

    # Cache should be considered stale when never updated (monitoring not started)
    assert cache.is_stale(30) is True
    print("✓ Cache initialization test passed")


def test_cache_replacement():
    """Test cache replacement behavior"""
    print("Testing cache replacement...")
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

    # Replace with different data
    new_data = {"host3": {"name": "host3", "status": 1, "backend_name": "Proxy2"}}
    cache.replace_all(new_data)

    # Verify replacement - old hosts should be gone
    data = cache.get_all()
    assert len(data["hosts"]) == 1
    assert "host1" not in data["hosts"]
    assert "host2" not in data["hosts"]
    assert "host3" in data["hosts"]
    print("✓ Cache replacement test passed")


def test_api_endpoint():
    """Test API endpoint functionality"""
    print("Testing API endpoint...")
    test_client = rewol.app.test_client()

    # Test API endpoint
    response = test_client.get("/api/status")
    assert response.status_code == 200

    data = response.get_json()
    assert data["success"] is True
    assert "hosts" in data
    assert "last_updated" in data
    assert "cache_info" in data
    print("✓ API endpoint test passed")


def test_monitoring_integration():
    """Test full monitoring integration"""
    print("Testing monitoring integration...")
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
    print("   Waiting for monitoring cycle to complete...")
    time.sleep(6)  # 5s interval + buffer

    # Check cache state
    data = cache.get_all()
    assert len(data["hosts"]) > 0  # Should have placeholder for down backend

    # Stop monitoring
    monitor.stop()
    assert monitor.running is False
    print("✓ Monitoring integration test passed")


def run_all_tests():
    """Run all tests"""
    print("Running background monitoring tests...\n")

    try:
        test_cache_initialization()
        test_cache_replacement()
        test_api_endpoint()
        test_monitoring_integration()

        print("\n🎉 All tests passed!")
        return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
