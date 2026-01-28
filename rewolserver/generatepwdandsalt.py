import hashlib
import base64
import os

def generate_salt():
    """Generate a random salt"""
    return base64.b64encode(os.urandom(32)).decode('utf-8')

def hash_password(password, salt):
    """Hash password with salt using SHA256"""
    salt_bytes = base64.b64decode(salt)
    password_bytes = password.encode('utf-8')
    hashed = hashlib.pbkdf2_hmac('sha256', password_bytes, salt_bytes, 600000)
    return base64.b64encode(hashed).decode('utf-8')

# Ask for password from CLI
password = input("Enter password to hash: ")

# Generate random salt and hash
salt = generate_salt()
hashed_password = hash_password(password, salt)

print("Salt (base64):", salt)
print("Password Hash (base64):", hashed_password)
# print("Original password:", password)