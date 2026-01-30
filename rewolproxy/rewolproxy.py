#!/usr/bin/env python3
"""
Rewolproxy - Remote Wake-on-LAN proxy service

This service provides HTTP endpoints for monitoring and triggering Wake-on-LAN
signals to configured hosts, with Prometheus metrics for monitoring.
"""

import argparse
import base64
import hashlib
import json
import logging
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import pythonping
import yaml
import wakeonlan
from prometheus_client import (
    CollectorRegistry,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("rewolproxy.log"), logging.StreamHandler()],
)
logger = logging.getLogger("rewolproxy")


class Config:
    """Configuration loader for rewolproxy"""

    def __init__(self, config_path="config.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
        self._validate_config()

    def _load_config(self):
        """Load YAML configuration file"""
        try:
            with open(self.config_path, "r") as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {self.config_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML configuration: {e}")
            raise

    def _validate_config(self):
        """Validate configuration structure"""
        required_sections = ["password", "server", "hosts"]
        for section in required_sections:
            if section not in self.config:
                raise ValueError(f"Missing required configuration section: {section}")

        # Validate password section
        if (
            "hash" not in self.config["password"]
            or "salt" not in self.config["password"]
        ):
            raise ValueError("Password configuration must include 'hash' and 'salt'")

        # Validate server section
        if (
            "port" not in self.config["server"]
            or "check_interval" not in self.config["server"]
        ):
            raise ValueError(
                "Server configuration must include 'port' and 'check_interval'"
            )

        # Validate hosts section
        if not isinstance(self.config["hosts"], list) or len(self.config["hosts"]) == 0:
            raise ValueError("Hosts configuration must be a non-empty list")

        for host in self.config["hosts"]:
            required_fields = ["host", "macAddress", "ip"]
            for field in required_fields:
                if field not in host:
                    raise ValueError(
                        f"Host configuration missing required field: {field}"
                    )

    def get_password_config(self):
        """Get password configuration"""
        return self.config["password"]

    def get_server_config(self):
        """Get server configuration"""
        return self.config["server"]

    def get_hosts(self):
        """Get hosts configuration"""
        return self.config["hosts"]


class MetricsManager:
    """Manager for Prometheus metrics"""

    def __init__(self, hosts):
        self.registry = CollectorRegistry()
        self.hosts = hosts

        # Initialize metrics
        self.service_uptime = Gauge(
            "rewol_service_uptime",
            "Service uptime in milliseconds",
            registry=self.registry,
        )

        self.host_up = Gauge(
            "rewol_host_up",
            "Host status (1=up, 0=down)",
            ["host"],
            registry=self.registry,
        )

        self.host_wol = Gauge(
            "rewol_host_wol",
            "Number of WOL signals sent",
            ["host"],
            registry=self.registry,
        )

        # Initialize host metrics
        for host in hosts:
            self.host_up.labels(host=host["host"]).set(0)
            self.host_wol.labels(host=host["host"]).set(0)

        self.start_time = time.time()

    def update_service_uptime(self):
        """Update service uptime metric"""
        uptime_ms = int((time.time() - self.start_time) * 1000)
        self.service_uptime.set(uptime_ms)

    def update_host_status(self, host_name, is_up):
        """Update host status metric"""
        self.host_up.labels(host=host_name).set(1 if is_up else 0)

    def increment_wol_counter(self, host_name):
        """Increment WOL counter for a host"""
        current_value = self.host_wol.labels(host=host_name)._value.get()
        self.host_wol.labels(host=host_name).set(current_value + 1)

    def get_metrics(self):
        """Get current metrics in Prometheus format"""
        self.update_service_uptime()
        return generate_latest(self.registry)


class HostMonitor:
    """Background thread for monitoring host status"""

    def __init__(self, config, metrics_manager):
        self.config = config
        self.metrics_manager = metrics_manager
        self.running = False
        self.thread = None

    def _ping_host(self, ip):
        """Ping a host using pythonping and return True if reachable"""
        try:
            # Use pythonping to send ICMP echo request
            response = pythonping.ping(ip, timeout=2, count=1)
            return response.success()
        except Exception as e:
            logger.error(f"Error pinging host {ip}: {e}")
            return False
        except socket.gaierror:
            # Hostname resolution failed
            return False
        except PermissionError:
            # Raw sockets require root privileges on some systems
            logger.error(
                f"Permission denied: ICMP ping requires root privileges for {ip}"
            )
            return False
        except Exception as e:
            logger.error(f"Error pinging host {ip}: {e}")
            return False

    def _monitor_loop(self):
        """Main monitoring loop"""
        check_interval = self.config.get_server_config()["check_interval"]
        hosts = self.config.get_hosts()

        while self.running:
            start_time = time.time()

            for host in hosts:
                host_name = host["host"]
                ip = host["ip"]
                is_up = self._ping_host(ip)
                self.metrics_manager.update_host_status(host_name, is_up)
                logger.debug(
                    f"Host {host_name} ({ip}) status: {'up' if is_up else 'down'}"
                )

            # Sleep for the remaining interval time
            elapsed = time.time() - start_time
            sleep_time = max(0, check_interval - elapsed)
            time.sleep(sleep_time)

    def start(self):
        """Start the monitoring thread"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.thread.start()
            logger.info("Host monitoring thread started")

    def stop(self):
        """Stop the monitoring thread"""
        self.running = False
        # Since this is a daemon thread, we don't need to join() it
        # It will be automatically terminated when the main program exits
        logger.info("Host monitoring thread stopped")


def verify_password(input_password, stored_hash, salt):
    """Verify password using PBKDF2-HMAC-SHA256"""
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
        logger.error(f"Password verification error: {e}")
        return False


class RequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for rewolproxy"""

    def __init__(
        self, *args, config=None, metrics_manager=None, host_monitor=None, **kwargs
    ):
        self.config = config
        self.metrics_manager = metrics_manager
        self.host_monitor = host_monitor
        super().__init__(*args, **kwargs)

    def _send_response(self, status_code, content, content_type="text/plain"):
        """Helper method to send HTTP responses"""
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        if isinstance(content, bytes):
            self.wfile.write(content)
        else:
            self.wfile.write(content.encode("utf-8"))

    def do_GET(self):
        """Handle GET requests"""
        parsed_url = urlparse(self.path)

        if parsed_url.path == "/status":
            # Return Prometheus metrics
            metrics = self.metrics_manager.get_metrics()
            self._send_response(200, metrics, CONTENT_TYPE_LATEST)
        else:
            self._send_response(404, "Not Found")

    def do_POST(self):
        """Handle POST requests"""
        parsed_url = urlparse(self.path)

        if parsed_url.path == "/wol":
            # Parse POST data
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length).decode("utf-8")

            try:
                params = parse_qs(post_data)
                host_name = params.get("host", [None])[0]
                password = params.get("password", [None])[0]

                if not host_name or not password:
                    self._send_response(400, "Missing host or password parameter")
                    return

                # Verify password
                password_config = self.config.get_password_config()
                if not verify_password(
                    password, password_config["hash"], password_config["salt"]
                ):
                    logger.warn("Invalid password")
                    self._send_response(401, "Unauthorized")
                    return

                # Find host in configuration
                hosts = self.config.get_hosts()
                host_found = None
                for host in hosts:
                    if host["host"] == host_name:
                        host_found = host
                        break

                if not host_found:
                    self._send_response(404, "Host not found")
                    return

                # Send WOL signal
                try:
                    interface = host_found.get("interface")  # Get optional interface
                    if interface:
                        wakeonlan.send_magic_packet(
                            host_found["macAddress"], interface=interface
                        )
                    else:
                        wakeonlan.send_magic_packet(host_found["macAddress"])
                    logger.info(
                        f"WOL signal sent to {host_name} ({host_found['macAddress']})"
                    )

                    # Update metrics
                    self.metrics_manager.increment_wol_counter(host_name)

                    self._send_response(201, "WOL signal sent successfully")
                except Exception as e:
                    logger.error(f"Error sending WOL signal: {e}")
                    self._send_response(500, "Error sending WOL signal")

            except Exception as e:
                logger.error(f"Error processing POST request: {e}")
                self._send_response(500, "Internal server error")
        else:
            self._send_response(404, "Not Found")


def main():
    """Main entry point for rewolproxy"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Rewolproxy - Remote Wake-on-LAN proxy service"
    )
    parser.add_argument(
        "--config", default="config.yaml", help="Path to configuration file"
    )
    args = parser.parse_args()

    try:
        # Load configuration
        config = Config(args.config)
        logger.info(f"Loaded configuration from {args.config}")

        # Initialize metrics
        metrics_manager = MetricsManager(config.get_hosts())

        # Initialize host monitor
        host_monitor = HostMonitor(config, metrics_manager)
        host_monitor.start()

        # Start HTTP server
        server_config = config.get_server_config()
        server_address = ("", server_config["port"])

        # Create custom request handler with dependencies
        handler_class = lambda *args, **kwargs: RequestHandler(
            *args,
            config=config,
            metrics_manager=metrics_manager,
            host_monitor=host_monitor,
            **kwargs,
        )

        httpd = HTTPServer(server_address, handler_class)
        logger.info(f"Starting server on port {server_config['port']}")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            logger.info("Server shutting down...")
            # Stop the host monitor first
            host_monitor.stop()
            # Shutdown the HTTP server
            httpd.shutdown()
            logger.info("Server shutdown complete")

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
