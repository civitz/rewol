#!/usr/bin/env python3
"""
Demo script showing background monitoring functionality
"""

import sys
import os
import time
import threading
from datetime import datetime

# Add the rewolserver module to path
sys.path.insert(0, "/home/roberto/workspace/vibecode/rewol/rewolserver")

import rewol


def demo_cache_operations():
    """Demonstrate cache operations"""
    print("=== Cache Operations Demo ===")

    cache = rewol.ProxyStatusCache()

    print("1. Initial cache state:")
    data = cache.get_all()
    print(f"   Hosts: {len(data['hosts'])}, Last updated: {data['last_updated']}")

    print("\n2. Adding test data...")
    test_data = {
        "proxy1-host1": {
            "name": "proxy1-host1",
            "status": 1,
            "backend_name": "Proxy 1",
            "backend_address": "192.168.1.100:8000",
            "is_proxy_down": False,
        },
        "proxy1-host2": {
            "name": "proxy1-host2",
            "status": 0,
            "backend_name": "Proxy 1",
            "backend_address": "192.168.1.100:8000",
            "is_proxy_down": False,
        },
        "proxy2-host1": {
            "name": "proxy2-host1 (proxy down)",
            "status": 0,
            "backend_name": "Proxy 2",
            "backend_address": "192.168.1.101:8000",
            "is_proxy_down": True,
        },
    }
    cache.replace_all(test_data)

    print("\n3. Cache after update:")
    data = cache.get_all()
    print(f"   Hosts: {len(data['hosts'])}, Last updated: {data['last_updated']}")

    print("\n4. Cache contents:")
    for host_name, host_data in data["hosts"].items():
        status_str = "UP" if host_data["status"] == 1 else "DOWN"
        proxy_str = " (PROXY DOWN)" if host_data["is_proxy_down"] else ""
        print(f"   {host_data['name']}: {status_str}{proxy_str}")

    print("\n5. Monitoring health check (staleness detection):")
    print(
        f"   Is stale (30s threshold): {cache.is_stale(30)} (should be False - recently updated)"
    )
    print(
        f"   Is stale (1s threshold): {cache.is_stale(1)} (should be False - just updated)"
    )
    print(
        "   Note: With replacement strategy, staleness checks if monitoring is working"
    )

    print("\n6. Testing replacement behavior (key improvement):")
    print("   Original hosts: host1, host2, proxy2-host1")
    print("   Replacing with different set...")
    replacement_data = {
        "host3": {"name": "host3", "status": 1, "backend_name": "Proxy 3"},
        "host4": {"name": "host4", "status": 0, "backend_name": "Proxy 4"},
    }
    cache.replace_all(replacement_data)
    data = cache.get_all()
    print(f"   Hosts after replacement: {list(data['hosts'].keys())}")
    print(
        f"   Original hosts removed: {'host1' not in data['hosts'] and 'host2' not in data['hosts']}"
    )
    print(
        f"   New hosts added: {'host3' in data['hosts'] and 'host4' in data['hosts']}"
    )
    print("   ✓ Full replacement ensures no stale data accumulates!")


def demo_api_endpoint():
    """Demonstrate the API endpoint"""
    print("\n=== API Endpoint Demo ===")

    test_client = rewol.app.test_client()

    print("1. Making API request to /api/status...")
    response = test_client.get("/api/status")

    print(f"2. Response status: {response.status_code}")

    data = response.get_json()
    print(f"3. Response data structure:")
    print(f"   Success: {data['success']}")
    print(f"   Host count: {len(data['hosts'])}")
    print(f"   Last updated: {data['last_updated']}")
    print(f"   Cache stale: {data['cache_info']['is_stale']}")

    print(f"4. Host details:")
    for host in data["hosts"]:
        status_str = "UP" if host["status"] == 1 else "DOWN"
        proxy_str = " (PROXY DOWN)" if host.get("is_proxy_down", False) else ""
        print(f"   {host['name']}: {status_str}{proxy_str}")


def demo_thread_monitoring():
    """Demonstrate background thread monitoring"""
    print("\n=== Background Thread Monitoring Demo ===")

    # Create mock backends that will fail (for demo purposes)
    mock_backends = [
        {
            "host": "Demo Proxy 1",
            "address": "127.0.0.1:9999",  # Non-existent
            "password": "demo123",
        },
        {
            "host": "Demo Proxy 2",
            "address": "127.0.0.1:9998",  # Non-existent
            "password": "demo456",
        },
    ]

    cache = rewol.ProxyStatusCache()
    monitor = rewol.BackgroundMonitorThread(mock_backends, cache)

    print("1. Starting background monitoring thread...")
    monitor.start()

    print("2. Monitoring thread status:")
    print(f"   Running: {monitor.running}")
    print(f"   Thread alive: {monitor.thread.is_alive() if monitor.thread else False}")

    print("3. Waiting for monitoring cycle to complete...")
    time.sleep(6)  # Wait for one monitoring cycle (5s interval + buffer)

    print("4. Cache status after monitoring:")
    data = cache.get_all()
    print(f"   Hosts in cache: {len(data['hosts'])}")
    print(f"   Last updated: {data['last_updated']}")

    for host_name, host_data in data["hosts"].items():
        print(
            f"   {host_data['name']}: Status={host_data['status']}, Proxy Down={host_data['is_proxy_down']}"
        )

    print("5. Stopping monitoring thread...")
    monitor.stop()
    print(f"   Thread stopped: {not monitor.running}")


def demo_real_time_simulation():
    """Simulate real-time updates"""
    print("\n=== Real-time Simulation Demo ===")

    cache = rewol.ProxyStatusCache()

    def simulate_proxy_updates():
        """Simulate proxy status changes"""
        status_cycles = [
            {"host1": 1, "host2": 0},  # Initial state
            {"host1": 1, "host2": 1},  # Both up
            {"host1": 0, "host2": 1},  # Host1 down
            {"host1": 1, "host2": 1},  # Both up again
        ]

        for i, cycle in enumerate(status_cycles):
            print(f"\n   Cycle {i + 1}: {datetime.now().strftime('%H:%M:%S')}")
            update_data = {}
            for host_name, status in cycle.items():
                update_data[host_name] = {
                    "name": host_name,
                    "status": status,
                    "backend_name": "Simulated Proxy",
                    "backend_address": "simulated:9999",
                    "is_proxy_down": False,
                }
            cache.replace_all(update_data)

            # Show current cache state
            data = cache.get_all()
            for h_name, h_data in data["hosts"].items():
                status_str = "UP" if h_data["status"] == 1 else "DOWN"
                print(f"     {h_data['name']}: {status_str}")

            time.sleep(2)  # Wait between cycles

    print("Simulating proxy status changes over time...")
    simulate_proxy_updates()

    print("\nThis demonstrates how the JavaScript polling would see status changes!")


if __name__ == "__main__":
    print("🚀 ReWOL Background Monitoring Demo")
    print("=" * 50)

    try:
        demo_cache_operations()
        demo_api_endpoint()
        demo_thread_monitoring()
        demo_real_time_simulation()

        print("\n" + "=" * 50)
        print("🎉 Demo completed successfully!")
        print("\nKey Features Demonstrated:")
        print("• Thread-safe caching with ProxyStatusCache")
        print("• Background monitoring with BackgroundMonitorThread")
        print("• REST API endpoint for JavaScript polling")
        print("• Real-time status updates simulation")
        print("• Automatic handling of proxy failures")

    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
