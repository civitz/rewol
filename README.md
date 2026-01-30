# Rewol - Remote Wake-on-LAN System

Rewol is a two-component system for remote Wake-on-LAN (WOL) management consisting of a proxy service (`rewolproxy`) and a server service (`rewolserver`).

## Overview

The system allows you to:
- Monitor the status of multiple hosts across different networks
- Send Wake-on-LAN signals to remote hosts
- View host status through a web interface
- Collect metrics in Prometheus format

## Components

### rewolproxy

The proxy service runs on each network where you want to monitor and wake hosts. It:
- Monitors host status via ICMP ping
- Provides HTTP endpoints for status checks and WOL signals
- Exposes Prometheus metrics for monitoring
- Requires password authentication for WOL operations

### rewolserver

The server service provides a centralized web interface that:
- Aggregates status from multiple rewolproxy instances
- Provides a web UI to view all hosts
- Allows sending WOL commands through the appropriate proxy
- Handles authentication and routing

## Installation

### Prerequisites

- Python 3.7+
- Required Python packages: `pythonping`, `wakeonlan`, `prometheus_client`, `flask`, `requests`, `pyyaml`

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/rewol.git
cd rewol

# Install dependencies
pip install .
```

## Configuration

### rewolproxy Configuration

Create a `config.yaml` file for the proxy:

```yaml
password:
  hash: "your_password_hash"  # Generated using generatepwdandsalt.py
  salt: "your_salt"

server:
  port: 8000
  check_interval: 30  # seconds between host checks

hosts:
  - host: "workstation1"
    macAddress: "00:11:22:33:44:55"
    ip: "192.168.1.100"
  - host: "server1"
    macAddress: "AA:BB:CC:DD:EE:FF"
    ip: "192.168.1.200"
```

### rewolserver Configuration

Create a `config.yaml` file for the server:

```yaml
service:
  password: "your_service_password_hash"
  salt: "your_service_salt"
  port: 11000
  monitor_interval: 5  # seconds between proxy checks
  max_retries: 3      # max retries for failed proxy requests

backends:
  - host: "office-proxy"
    address: "office.example.com:8000"
    password: "office_proxy_password"
  - host: "home-proxy"
    address: "home.example.com:8000"
    password: "home_proxy_password"
```

## Running the Services

### Starting rewolproxy

```bash
cd rewolproxy
python rewolproxy.py --config config.yaml
```

### Starting rewolserver

```bash
cd rewolserver
python rewol.py --config config.yaml
```

## Usage

### Accessing the Web Interface

Once rewolserver is running, access the web interface at:
```
http://localhost:11000/
```

### API Endpoints

#### rewolproxy Endpoints

- `GET /status` - Get Prometheus metrics for all hosts
- `POST /wol` - Send WOL signal (requires password)

#### rewolserver Endpoints

- `GET /` - Web interface showing all hosts
- `GET /api/status` - JSON API for host status
- `POST /wol` - Send WOL command through appropriate proxy

## Security

- All WOL operations require password authentication (the password for the UI is the server password)
- Passwords are stored as PBKDF2-HMAC-SHA256 hashes with salt
- Use HTTPS in production for secure communication

## Monitoring

The system exposes Prometheus metrics at the `/status` endpoint of rewolproxy, including:
- Service uptime
- Host status (up/down)
- WOL signal counters

