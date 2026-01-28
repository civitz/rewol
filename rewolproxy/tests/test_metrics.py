import pytest
import sys

sys.path.insert(0, "/home/roberto/workspace/vibecode/rewol/rewolproxy")
from rewolproxy import MetricsManager


def test_metrics_initialization():
    """Test metrics manager initialization"""
    hosts = [
        {"host": "test1", "macAddress": "00:11:22:33:44:55", "ip": "192.168.1.100"},
        {"host": "test2", "macAddress": "AA:BB:CC:DD:EE:FF", "ip": "192.168.1.200"},
    ]

    metrics = MetricsManager(hosts)

    # Test that metrics are initialized
    assert metrics.service_uptime._value.get() == 0
    assert metrics.host_up.labels(host="test1")._value.get() == 0
    assert metrics.host_up.labels(host="test2")._value.get() == 0
    assert metrics.host_wol.labels(host="test1")._value.get() == 0
    assert metrics.host_wol.labels(host="test2")._value.get() == 0


def test_metrics_updates():
    """Test metrics updates"""
    hosts = [
        {"host": "test1", "macAddress": "00:11:22:33:44:55", "ip": "192.168.1.100"}
    ]
    metrics = MetricsManager(hosts)

    # Test service uptime update
    metrics.update_service_uptime()
    assert metrics.service_uptime._value.get() >= 0

    # Test host status update
    metrics.update_host_status("test1", True)
    assert metrics.host_up.labels(host="test1")._value.get() == 1

    metrics.update_host_status("test1", False)
    assert metrics.host_up.labels(host="test1")._value.get() == 0

    # Test WOL counter increment
    metrics.increment_wol_counter("test1")
    assert metrics.host_wol.labels(host="test1")._value.get() == 1

    metrics.increment_wol_counter("test1")
    assert metrics.host_wol.labels(host="test1")._value.get() == 2


def test_metrics_output():
    """Test metrics output format"""
    hosts = [
        {"host": "test1", "macAddress": "00:11:22:33:44:55", "ip": "192.168.1.100"}
    ]
    metrics = MetricsManager(hosts)

    # Get metrics output
    output = metrics.get_metrics()

    # Check that output contains expected metric names
    assert b"rewol_service_uptime" in output
    assert b"rewol_host_up" in output
    assert b"rewol_host_wol" in output
    assert b'host="test1"' in output
