import pytest
import os
import tempfile
import sys

sys.path.insert(0, "/home/roberto/workspace/vibecode/rewol/rewolproxy")
from rewolproxy import Config


def test_config_loading():
    """Test configuration loading from file"""
    config_content = """
password:
  hash: "dGVzdGhhc2g="
  salt: "dGVzdHNhbHQ="
server:
  port: 8080
  check_interval: 60
hosts:
  - host: "test1"
    macAddress: "00:11:22:33:44:55"
    ip: "192.168.1.100"
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(config_content)
        config_path = f.name

    try:
        config = Config(config_path)
        assert config.get_server_config()["port"] == 8080
        assert config.get_server_config()["check_interval"] == 60
        assert len(config.get_hosts()) == 1
        assert config.get_hosts()[0]["host"] == "test1"
    finally:
        os.unlink(config_path)


def test_config_validation():
    """Test configuration validation"""
    # Test missing required section
    config_content = """
server:
  port: 8080
  check_interval: 60
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(config_content)
        config_path = f.name

    try:
        with pytest.raises(ValueError, match="Missing required configuration section"):
            Config(config_path)
    finally:
        os.unlink(config_path)


def test_password_verification():
    """Test password verification function"""
    from rewolproxy import verify_password

    # Test with known hash/salt
    test_password = "testpassword"
    salt = "dGVzdHNhbHQ="  # base64 for "testsalt"

    # Generate hash for test
    import base64
    import hashlib

    salt_bytes = base64.b64decode(salt)
    password_bytes = test_password.encode("utf-8")
    hashed = hashlib.pbkdf2_hmac("sha256", password_bytes, salt_bytes, 600000)
    expected_hash = base64.b64encode(hashed).decode("utf-8")

    # Test verification
    assert verify_password(test_password, expected_hash, salt) == True
    assert verify_password("wrongpassword", expected_hash, salt) == False
