import pytest
from argon2 import PasswordHasher
from pydantic import ValidationError

from app.schemas.auth import AuthLoginRequest
from app.services.auth import AuthConfigurationError, AuthService


def test_login_request_normalizes_key_and_rejects_invalid_length():
    assert AuthLoginRequest(access_key="b2 3456-789c").access_key == "B23456789C"
    with pytest.raises(ValidationError):
        AuthLoginRequest(access_key="B234567890")


def test_argon2_phc_salt_matches_hex_column():
    phc_hash = PasswordHasher().hash("B23456789C")
    salt_hex = AuthService._encoded_salt_hex(phc_hash)
    assert len(salt_hex) == 32
    assert salt_hex == AuthService._encoded_salt_hex(phc_hash)


def test_argon2_phc_invalid_salt_is_a_configuration_error():
    with pytest.raises(AuthConfigurationError):
        AuthService._encoded_salt_hex("$argon2id$v=19$m=65536,t=3,p=4$%%%$hash")


def test_fingerprint_requires_external_secret(monkeypatch):
    monkeypatch.delenv("LOGIN_FP_SECRET", raising=False)
    with pytest.raises(AuthConfigurationError, match="LOGIN_FP_SECRET"):
        AuthService._fp("source", "203.0.113.10")


def test_fingerprints_are_domain_separated(monkeypatch):
    monkeypatch.setenv("LOGIN_FP_SECRET", "unit-test-secret")
    assert AuthService._fp("identifier", "203.0.113.10") != AuthService._fp(
        "source", "203.0.113.10"
    )
