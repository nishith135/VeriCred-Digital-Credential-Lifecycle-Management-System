"""Cryptographic security primitives for credential integrity and authenticity.

Implements:
1. Deterministic canonical JSON serialization.
2. SHA-256 payload hashing for tamper detection.
3. Ed25519 asymmetric key generation, signing, and signature verification.
"""

import base64
import hashlib
import json
from typing import Any, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519


def canonical_json_dumps(payload: dict[str, Any]) -> str:
    """Serialize a dictionary to deterministic canonical JSON.

    Ensures all keys are sorted recursively and whitespace separators
    are strictly compact (',', ':'), preventing whitespace or ordering
    differences from altering the cryptographic digest.
    """

    def _sort_element(element: Any) -> Any:
        if isinstance(element, dict):
            return {k: _sort_element(element[k]) for k in sorted(element.keys())}
        if isinstance(element, list):
            return [_sort_element(item) for item in element]
        return element

    sorted_payload = _sort_element(payload)
    return json.dumps(sorted_payload, separators=(",", ":"), ensure_ascii=False)


def compute_payload_hash(payload: dict[str, Any]) -> str:
    """Compute the SHA-256 hexadecimal digest of a canonicalized payload dictionary."""
    canonical_str = canonical_json_dumps(payload)
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


def generate_ed25519_keypair() -> Tuple[str, str]:
    """Generate an Ed25519 asymmetric keypair using OS entropy."""
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    return private_pem, public_pem


def generate_deterministic_ed25519_keypair(seed_material: bytes) -> Tuple[str, str]:
    """Generate a deterministic Ed25519 asymmetric keypair derived from seed bytes.

    Args:
        seed_material: Arbitrary length byte sequence, hashed via SHA-256 to exactly 32 bytes.

    Returns:
        Tuple[str, str]: (private_key_pem, public_key_pem) formatted as UTF-8 strings.
    """
    raw_32_bytes = hashlib.sha256(seed_material).digest()
    private_key = ed25519.Ed25519PrivateKey.from_private_bytes(raw_32_bytes)
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    return private_pem, public_pem


def sign_payload_hash(private_key_pem: str, payload_hash: str) -> str:
    """Sign a payload hash using the issuer's Ed25519 private key.

    Args:
        private_key_pem: PEM-encoded Ed25519 private key.
        payload_hash: Hexadecimal string of the SHA-256 payload digest.

    Returns:
        Base64-encoded signature string.
    """
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode("utf-8"),
        password=None,
    )
    if not isinstance(private_key, ed25519.Ed25519PrivateKey):
        raise ValueError("Provided key is not an Ed25519 private key")

    # Sign the raw UTF-8 bytes of the hash string
    signature_bytes = private_key.sign(payload_hash.encode("utf-8"))
    return base64.b64encode(signature_bytes).decode("utf-8")


def verify_signature(public_key_pem: str, payload_hash: str, signature_b64: str) -> bool:
    """Verify an Ed25519 signature against a payload hash.

    Args:
        public_key_pem: PEM-encoded Ed25519 public key.
        payload_hash: Hexadecimal string of the SHA-256 payload digest.
        signature_b64: Base64-encoded signature string.

    Returns:
        True if the signature is valid; False otherwise.
    """
    try:
        public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
        if not isinstance(public_key, ed25519.Ed25519PublicKey):
            return False

        signature_bytes = base64.b64decode(signature_b64.encode("utf-8"))
        public_key.verify(signature_bytes, payload_hash.encode("utf-8"))
        return True
    except (InvalidSignature, ValueError, Exception):
        return False
