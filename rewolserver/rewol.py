import requests
from flask import Flask, request, Response, render_template
import yaml
import hashlib
import base64
import logging
from logging.handlers import RotatingFileHandler
import re

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

try:
    with open("config.yaml", "r") as file:
        config = yaml.safe_load(file)
except FileNotFoundError:
    app.logger.error("Config file not found")
    raise
except yaml.YAMLError as e:
    app.logger.error(f"Error parsing config file: {e}")
    raise

# Configuration
BACKENDS = config.get("backends", [])
SERVICE_PASSWORD = config["service"]["password"]
SERVICE_SALT = config["service"]["salt"]
SERVICE_PORT = config["service"]["port"]


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


def get_all_hosts():
    """Get all hosts from all configured backends"""
    all_hosts = []

    for backend in BACKENDS:
        hosts = get_hosts_from_backend(backend)

        if hosts is None:
            # Backend is down, add placeholder entry
            all_hosts.append(
                {
                    "name": f"{backend['host']} (proxy down)",
                    "status": 0,
                    "backend_name": backend["host"],
                    "backend_address": backend["address"],
                    "backend_password": backend["password"],
                    "is_proxy_down": True,
                }
            )
        else:
            # Add all hosts from this backend
            for host_name, host_data in hosts.items():
                host_data["name"] = host_name
                host_data["is_proxy_down"] = False
                all_hosts.append(host_data)

    return all_hosts


@app.route("/")
def status():
    """Main status page showing all hosts"""
    hosts = get_all_hosts()
    return render_template("status.html", hosts=hosts)


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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=SERVICE_PORT, debug=True)
