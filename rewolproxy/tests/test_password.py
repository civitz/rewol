import pytest
import sys

sys.path.insert(0, "/home/roberto/workspace/vibecode/rewol/rewolproxy")
from rewolproxy import verify_password
import base64
import hashlib


def test_password_verification():
    """Test password verification with correct and incorrect passwords"""
    # Create a test password and generate its hash
    test_password = "securepassword123"
    salt = base64.b64encode(b"testsalt").decode("utf-8")

    # Generate the expected hash
    salt_bytes = base64.b64decode(salt)
    password_bytes = test_password.encode("utf-8")
    hashed = hashlib.pbkdf2_hmac("sha256", password_bytes, salt_bytes, 600000)
    expected_hash = base64.b64encode(hashed).decode("utf-8")

    # Test correct password
    assert verify_password(test_password, expected_hash, salt) == True

    # Test incorrect password
    assert verify_password("wrongpassword", expected_hash, salt) == False

    # Test empty password
    assert verify_password("", expected_hash, salt) == False


def test_password_verification_edge_cases():
    """Test password verification edge cases"""
    # Test with invalid base64 salt
    assert verify_password("any", "anyhash", "invalidsalt!") == False

    # Test with empty hash
    assert verify_password("any", "", "dGVzdHNhbHQ=") == False

    # Test with None values (should handle gracefully)
    assert verify_password(None, "hash", "salt") == False
    assert verify_password("password", None, "salt") == False
    assert verify_password("password", "hash", None) == False
