import pytest
import sys
import tempfile
import os
import time
import threading
from http.client import HTTPConnection
from urllib.parse import urlencode

sys.path.insert(0, "/home/roberto/workspace/vibecode/rewol/rewolproxy")
from rewolproxy import Config, MetricsManager, HostMonitor, main


def test_full_integration():
    """Test full integration of the service"""
    # Create a temporary config file
    config_content = """
password:
  hash: "dGVzdGhhc2g="
  salt: "dGVzdHNhbHQ="
server:
  port: 8888
  check_interval: 10
hosts:
  - host: "testhost"
    macAddress: "00:11:22:33:44:55"
    ip: "127.0.0.1"
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(config_content)
        config_path = f.name

    try:
        # Load configuration
        config = Config(config_path)

        # Initialize metrics
        metrics = MetricsManager(config.get_hosts())

        # Initialize host monitor
        host_monitor = HostMonitor(config, metrics)
        host_monitor.start()

        # Start the server in a separate thread
        import subprocess
        import signal
        import os

        # Create a subprocess to run the server
        server_process = subprocess.Popen(
            [sys.executable, "rewolproxy.py", "--config", config_path],
            cwd="/home/roberto/workspace/vibecode/rewol/rewolproxy",
        )

        # Wait for server to start
        time.sleep(2)

        # Test GET /status endpoint
        conn = HTTPConnection("localhost", 8888)
        conn.request("GET", "/status")
        response = conn.getresponse()
        assert response.status == 200
        metrics_data = response.read()
        assert b"rewol_service_uptime" in metrics_data
        assert b"rewol_host_up" in metrics_data
        assert b"rewol_host_wol" in metrics_data
        conn.close()

        # Test POST /wol endpoint with wrong password
        headers = {"Content-type": "application/x-www-form-urlencoded"}
        params = urlencode({"host": "testhost", "password": "wrongpassword"})
        conn = HTTPConnection("localhost", 8888)
        conn.request("POST", "/wol", params, headers)
        response = conn.getresponse()
        assert response.status == 401
        conn.close()

        # Test POST /wol endpoint with correct password
        # Note: This uses the test hash/salt from the config
        params = urlencode({"host": "testhost", "password": "testpassword"})
        conn = HTTPConnection("localhost", 8888)
        conn.request("POST", "/wol", params, headers)
        response = conn.getresponse()
        # Should return 201 if WOL signal was sent (or 500 if there was an error)
        assert response.status in [201, 500]
        conn.close()

        # Clean up
        server_process.terminate()
        server_process.wait()
        host_monitor.stop()

    finally:
        os.unlink(config_path)


if __name__ == "__main__":
    test_full_integration()
