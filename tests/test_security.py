"""Unit tests for cryptographic security primitives.

Verifies:
- Deterministic canonical JSON serialization.
- SHA-256 payload hashing and tamper detection.
- Ed25519 keypair generation, signing, and asymmetric verification.
"""

import pytest
from backend.core.security import (
    canonical_json_dumps,
    compute_payload_hash,
    generate_ed25519_keypair,
    sign_payload_hash,
    verify_signature,
)


def test_canonical_json_deterministic_ordering():
    """Verify that dictionaries with different key orders serialize identically."""
    dict_a = {"z": 1, "a": 2, "m": {"b": 3, "a": 4}}
    dict_b = {"a": 2, "m": {"a": 4, "b": 3}, "z": 1}

    serialized_a = canonical_json_dumps(dict_a)
    serialized_b = canonical_json_dumps(dict_b)

    assert serialized_a == serialized_b
    assert serialized_a == '{"a":2,"m":{"a":4,"b":3},"z":1}'


def test_payload_hash_tamper_detection():
    """Verify that any modification to payload data changes the SHA-256 digest."""
    payload_original = {
        "learner_id": "L-12345",
        "course_id": "C-999",
        "score": 85.5,
        "completion_date": "2026-05-15",
    }
    payload_tampered = {
        "learner_id": "L-12345",
        "course_id": "C-999",
        "score": 85.6,  # subtle alteration
        "completion_date": "2026-05-15",
    }

    hash_original = compute_payload_hash(payload_original)
    hash_tampered = compute_payload_hash(payload_tampered)

    assert hash_original != hash_tampered
    assert len(hash_original) == 64  # standard SHA-256 hex string


def test_ed25519_keypair_generation_and_verification():
    """Verify Ed25519 asymmetric signature validity and tamper detection."""
    priv_pem, pub_pem = generate_ed25519_keypair()

    assert "BEGIN PRIVATE KEY" in priv_pem
    assert "BEGIN PUBLIC KEY" in pub_pem

    payload = {"credential_id": "CRD-2026-000001", "grade": "DISTINCTION"}
    payload_hash = compute_payload_hash(payload)

    # 1. Sign payload hash
    signature = sign_payload_hash(priv_pem, payload_hash)
    assert isinstance(signature, str)
    assert len(signature) > 0

    # 2. Verify with correct public key and matching hash
    assert verify_signature(pub_pem, payload_hash, signature) is True

    # 3. Verify that tampered hash fails
    fake_hash = compute_payload_hash({"credential_id": "CRD-2026-000001", "grade": "FAIL"})
    assert verify_signature(pub_pem, fake_hash, signature) is False

    # 4. Verify that signature with a different public key fails
    _, other_pub_pem = generate_ed25519_keypair()
    assert verify_signature(other_pub_pem, payload_hash, signature) is False

    # 5. Verify that malformed base64 signature fails gracefully
    assert verify_signature(pub_pem, payload_hash, "invalid_base64_sig") is False
