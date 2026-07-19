"""
Project file manager for QIF. Handles secure encryption/decryption of project state.
"""

import base64
import hashlib
import json
from cryptography.fernet import Fernet, InvalidToken

# Salt and passphrase for key derivation
_SECRET_SALT = b"QIF_Project_File_Security_Salt_2026"
_PASSPHRASE = b"QuickImageFormatting_SecureProjectKey_987654321"


def _get_fernet_key() -> bytes:
    """Derive a 32-byte URL-safe base64 key from static salt and passphrase."""
    return base64.urlsafe_b64encode(hashlib.sha256(_SECRET_SALT + _PASSPHRASE).digest())


def encrypt_project_data(data: dict) -> bytes:
    """Serialize the project state dict to JSON and encrypt using Fernet (AES-128/HMAC-SHA256)."""
    json_bytes = json.dumps(data).encode("utf-8")
    f = Fernet(_get_fernet_key())
    return f.encrypt(json_bytes)


def decrypt_project_data(encrypted_data: bytes) -> dict:
    """Decrypt the project data using Fernet and deserialize JSON.

    Raises:
        InvalidToken: If data is tampered, corrupted, or uses an invalid signature/key.
        json.JSONDecodeError: If JSON parsing fails.
    """
    f = Fernet(_get_fernet_key())
    decrypted_bytes = f.decrypt(encrypted_data)
    return json.loads(decrypted_bytes.decode("utf-8"))
