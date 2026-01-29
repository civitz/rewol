import argparse
import requests
from flask import Flask, request, Response, render_template, jsonify
import yaml
import hashlib
import base64
import logging
from logging.handlers import RotatingFileHandler
import re
import threading
import time
from datetime import datetime, timedelta

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Add rotating file handler
file_handler = RotatingFileHandler(
    "rewol.log",
    maxBytes=10 * 1024 * 1024,  # 10 MB
    backupCount=1,
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
)
app.logger.addHandler(file_handler)


def load_config(config_path="config.yaml"):
    """Load configuration from YAML file"""
    try:
        with open(config_path, "r") as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        app.logger.error(f"Config file not found: {config_path}")
        raise
    except yaml.YAMLError as e:
        app.logger.error(f"Error parsing config file {config_path}: {e}")
        raise


# Configuration variables (will be set in main())
BACKENDS = []
SERVICE_PASSWORD = ""
SERVICE_SALT = ""
SERVICE_PORT = 11000


class ProxyStatusCache:
    """Thread-safe cache for proxy status information"""

    def __init__(self):
        self.lock = threading.Lock()
        self.cache = {}
        self.last_updated = None

    def replace_all(self, new_data):
        """Completely replace cache with new data (full replacement strategy)"""
        with self.lock:
            # Add timestamp to each host for debugging
            for host_name, host_data in new_data.items():
                host_data["last_checked"] = datetime.now()

            # Full replacement - discard all old data
            self.cache = new_data.copy()
            self.last_updated = datetime.now()

    def get_all(self):
        """Get all cached proxy status data"""
        with self.lock:
            return {"hosts": self.cache.copy(), "last_updated": self.last_updated}

    def is_stale(self, max_age_seconds=30):
        """Check if cache is stale"""
        with self.lock:
            if self.last_updated is None:
                return True
            return (datetime.now() - self.last_updated) > timedelta(
                seconds=max_age_seconds
            )


class BackgroundMonitorThread:
    """Background thread for continuous proxy monitoring"""

    def __init__(self, backends, cache):
        self.backends = backends
        self.cache = cache
        self.running = False
        self.thread = None
        self.monitor_interval = 5  # Check proxies every 5 seconds
        self.logger = app.logger

    def _check_proxy_status(self, backend):
        """Check status of a single proxy backend"""
        try:
            url = f"http://{backend['address']}/status"
            response = requests.get(url, timeout=3)

            if response.status_code == 200:
                hosts = parse_prometheus_metrics(response.text)
                # Add backend info to each host
                result = {}
                for host_name, host_data in hosts.items():
                    host_data["backend_name"] = backend["host"]
                    host_data["backend_address"] = backend["address"]
                    host_data["backend_password"] = backend["password"]
                    host_data["name"] = host_name
                    host_data["is_proxy_down"] = False
                    result[host_name] = host_data
                return result
            else:
                self.logger.warning(
                    f"Backend {backend['host']} returned status {response.status_code}"
                )
                return None
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error connecting to backend {backend['host']}: {e}")
            return None

    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            start_time = time.time()
            new_cache_data = {}

            # Check all backends sequentially
            for backend in self.backends:
                status = self._check_proxy_status(backend)
                if status:
                    new_cache_data.update(status)
                else:
                    # Add placeholder for down backend
                    host_name = f"{backend['host']} (proxy down)"
                    new_cache_data[host_name] = {
                        "name": host_name,
                        "status": 0,
                        "backend_name": backend["host"],
                        "backend_address": backend["address"],
                        "backend_password": backend["password"],
                        "is_proxy_down": True,
                    }

            # Replace all cache data atomically
            self.cache.replace_all(new_cache_data)

            # Sleep for remaining interval time
            elapsed = time.time() - start_time
            sleep_time = max(0, self.monitor_interval - elapsed)
            time.sleep(sleep_time)

    def start(self):
        """Start the monitoring thread"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.thread.start()
            self.logger.info("Background monitoring thread started")

    def stop(self):
        """Stop the monitoring thread"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
            if self.thread.is_alive():
                self.logger.warning("Monitoring thread did not stop gracefully")
            else:
                self.logger.info("Background monitoring thread stopped")


def verify_password(input_password, stored_hash, salt):
    """Verify password using PBKDF2 HMAC SHA256"""
    try:
        # Decode the base64 salt
        salt_bytes = base64.b64decode(salt)

        # Create the hash using PBKDF2 with 600000 iterations
        password_bytes = input_password.encode("utf-8")
        hashed = hashlib.pbkdf2_hmac("sha256", password_bytes, salt_bytes, 600000)

        # Encode the result as base64 for comparison
        hashed_b64 = base64.b64encode(hashed).decode("utf-8")

        # Compare with stored hash
        return hashed_b64 == stored_hash
    except Exception as e:
        app.logger.error(f"Password verification error: {e}")
        return False


def parse_prometheus_metrics(text):
    """Parse Prometheus metrics and extract host status information"""
    hosts = {}

    # Parse rewol_host_up metric
    host_up_pattern = r'rewol_host_up\{host="([^"]+)"\}\s+([01])'
    matches = re.findall(host_up_pattern, text)

    for host, status in matches:
        hosts[host] = {"status": int(status), "name": host}

    return hosts


def get_hosts_from_backend(backend):
    """Get hosts from a single backend proxy"""
    try:
        url = f"http://{backend['address']}/status"
        response = requests.get(url, timeout=5)

        if response.status_code == 200:
            hosts = parse_prometheus_metrics(response.text)
            # Add backend info to each host
            for host_name, host_data in hosts.items():
                host_data["backend_name"] = backend["host"]
                host_data["backend_address"] = backend["address"]
                host_data["backend_password"] = backend["password"]
            return hosts
        else:
            app.logger.warning(
                f"Backend {backend['host']} returned status {response.status_code}"
            )
            return None
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error connecting to backend {backend['host']}: {e}")
        return None


# Global cache instance
proxy_cache = ProxyStatusCache()
background_monitor = None


def get_all_hosts():
    """Get all hosts from cache or fallback to direct checking"""
    # Try to get from cache first
    cache_data = proxy_cache.get_all()

    if cache_data["hosts"]:
        # Return cached data as list
        return list(cache_data["hosts"].values())

    # Cache is empty (likely all backends are down), return empty list
    # The background thread will continue trying to connect
    return []


@app.route("/")
def status():
    """Main status page showing all hosts"""
    hosts = get_all_hosts()
    return render_template("status.html", hosts=hosts)


@app.route("/api/status")
def api_status():
    """API endpoint returning JSON status for JavaScript polling"""
    cache_data = proxy_cache.get_all()

    # Convert to list format expected by UI
    hosts_list = []
    for host_data in cache_data["hosts"].values():
        hosts_list.append(host_data)

    return jsonify(
        {
            "success": True,
            "hosts": hosts_list,
            "last_updated": cache_data["last_updated"].isoformat()
            if cache_data["last_updated"]
            else None,
            "cache_info": {
                "is_stale": proxy_cache.is_stale(),
                "host_count": len(cache_data["hosts"]),
            },
        }
    )


@app.route("/wol", methods=["POST"])
def send_wol():
    """Send WOL command to a specific host"""
    host_name = request.form.get("host")
    backend_address = request.form.get("backend_address")
    backend_password = request.form.get("backend_password")
    input_password = request.form.get("password")

    # Verify service password
    if not verify_password(input_password, SERVICE_PASSWORD, SERVICE_SALT):
        app.logger.warning(f"Invalid password attempt for host {host_name}")
        return {"success": False, "error": "Invalid password"}, 401

    try:
        # Send WOL request to backend
        url = f"http://{backend_address}/wol"
        response = requests.post(
            url, data={"host": host_name, "password": backend_password}, timeout=5
        )

        if response.status_code == 201:
            app.logger.info(f"Successfully sent WOL to {host_name}")
            return {"success": True, "message": "WOL command sent successfully"}
        elif response.status_code == 401:
            app.logger.error(f"Backend authentication failed for {host_name}")
            return {"success": False, "error": "Backend authentication failed"}, 401
        elif response.status_code == 404:
            app.logger.error(f"Host {host_name} not found on backend")
            return {"success": False, "error": "Host not found on backend"}, 404
        else:
            app.logger.error(
                f"Unexpected response from backend for {host_name}: {response.status_code}"
            )
            return {
                "success": False,
                "error": f"Backend error: {response.status_code}",
            }, 500

    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error sending WOL to {host_name}: {e}")
        return {"success": False, "error": f"Connection error: {str(e)}"}, 500


def main():
    """Main entry point for rewolserver"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Rewolserver - Remote Wake-on-LAN server service"
    )
    parser.add_argument(
        "--config", default="config.yaml", help="Path to configuration file"
    )
    args = parser.parse_args()

    # Load configuration using the provided path
    global \
        config, \
        BACKENDS, \
        SERVICE_PASSWORD, \
        SERVICE_SALT, \
        SERVICE_PORT, \
        background_monitor
    config = load_config(args.config)
    app.logger.info(f"Loaded configuration from {args.config}")

    # Set configuration variables
    BACKENDS = config.get("backends", [])
    SERVICE_PASSWORD = config["service"]["password"]
    SERVICE_SALT = config["service"]["salt"]
    SERVICE_PORT = config["service"]["port"]

    # Initialize background monitor
    background_monitor = BackgroundMonitorThread(BACKENDS, proxy_cache)

    # Start background monitoring thread
    background_monitor.start()

    try:
        app.run(host="0.0.0.0", port=SERVICE_PORT, debug=True)
    finally:
        # Clean up background thread on shutdown
        background_monitor.stop()


if __name__ == "__main__":
    main()
