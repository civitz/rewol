This is the remote proxy server for rewol.
It should be installed on a machine with direct access to machines that need to be started via WOL.

It should be a very simple python service, on one file called rewolproxy.py .

The script should start an http (not https) server with two services:
- a GET /status API that responds with an HTTP 200 and a prometheus response that contains the following metrics:
    + rewol_service_uptime of the service itself as millisecond gauge metric
    + rewol_host_up gauge metric, with an "host" label for each known host, that shows 1 if host is up
    + rewol_host_wol gauge metric, with an "host" label for each known host, that adds 1 each time the WOL signal is sent to the host

- a POST /wol API with a "host" and "password" parameters that
    + verifies the password against the one in configuration (or returns 401 unauthorized)
    + verifies the existence of the host in the configuration (or returns 404 not found)
    + responds with an HTTP 201 after launching the WOL to the corresponding host
    + updates the rewol_host_wol metric


Example code to check the hash:
```python
def verify_password(input_password, stored_hash, salt):
    # Decode the base64 salt
    salt_bytes = base64.b64decode(salt)
    
    # Create the hash using PBKDF2 with 600000 iterations
    password_bytes = input_password.encode('utf-8')
    hashed = hashlib.pbkdf2_hmac('sha256', password_bytes, salt_bytes, 600000)
    
    # Encode the result as base64 for comparison
    hashed_b64 = base64.b64encode(hashed).decode('utf-8')
    
    # Compare with stored hash
    return hashed_b64 == stored_hash
```

The script should periodically check for the known hosts to be up or not and update the rewol_host_up metric.
The periodic check should be in a background thread.
The periodic check should do a ping with a configurable timeout

It should accept the following YAML configurations in config.yaml:

- a password hash that should be checked with the configuration
- the TCP port to serve on
- the check interval for the periodic ping check
- a list of hosts with the following fields:
    + host, which is the label that must be used in the metrics and the POST API
    + macAddress, which is the mac address of the machine for the WOL
    + ip, which is the IP of the host, once it will be on

The configuration should be assumed to be in current directory, or can be overridden with --config={path to file}

Provide a config.sample.yaml file with hypotetical values.

Write tests using pytest with test files in the tests/ directory.

Use virtualenv and pyproject.toml to track dependencies.

You should also write a sample systemd service to run the service in a rewolproxy.sample.service file.