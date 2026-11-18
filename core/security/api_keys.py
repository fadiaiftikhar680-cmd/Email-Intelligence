"""
API Key Generation, Hashing, and Verification.
Fulfills Part 5.2 and Part 8.5.
"""
import hashlib
import secrets


KEY_PREFIX = "eip"


def generate_api_key() -> tuple[str, str, str]:
    """
    Generates a cryptographically secure API key.
    Format: eip_<prefix8>_<secret32>
    Returns (full_key, prefix, key_hash).
    Only the prefix and key_hash are stored in the database.
    """
    prefix_rnd = secrets.token_hex(4)  # 8 hex characters
    secret_rnd = secrets.token_urlsafe(32)  # 32 bytes url-safe base64

    prefix = f"{KEY_PREFIX}_{prefix_rnd}"
    full_key = f"{prefix}_{secret_rnd}"
    key_hash = hash_api_key(full_key)

    return full_key, prefix, key_hash


def hash_api_key(full_key: str) -> str:
    """
    Returns the SHA-256 digest of the full API key.
    """
    return hashlib.sha256(full_key.encode("utf-8")).hexdigest()

