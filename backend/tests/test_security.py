import pytest
from backend.security import redact_secrets
from backend.auth import verify_password_constant_time


def test_secret_redaction_anthropic_key():
    fake_key = "sk-ant-api03-abcdef1234567890abcdef1234567890"
    raw_text = f"Error: Failed with key {fake_key} in Claude client"
    redacted = redact_secrets(raw_text)
    assert fake_key not in redacted
    assert "[REDACTED]" in redacted


def test_secret_redaction_gemini_key():
    fake_key = "AIzaSyD1234567890abcdef1234567890123"
    raw_text = f"Google API error with key={fake_key}"
    redacted = redact_secrets(raw_text)
    assert fake_key not in redacted
    assert "[REDACTED]" in redacted


def test_secret_redaction_github_token():
    fake_token = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"
    raw_text = f"Authenticated via {fake_token}"
    redacted = redact_secrets(raw_text)
    assert fake_token not in redacted
    assert "[REDACTED]" in redacted


def test_secret_redaction_bearer_token():
    bearer = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.doNotLeakThis"
    raw_text = f"Headers: Authorization: {bearer}"
    redacted = redact_secrets(raw_text)
    assert "doNotLeakThis" not in redacted
    assert "[REDACTED]" in redacted


def test_secret_redaction_dict_and_list():
    data = {
        "user": "test_user",
        "api_key": "sk-ant-api03-abcdef1234567890abcdef1234567890",
        "nested": [
            "ghp_1234567890abcdefghijklmnopqrstuvwxyz",
            "normal string"
        ]
    }
    redacted = redact_secrets(data)
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["nested"][0] == "[REDACTED]"
    assert redacted["nested"][1] == "normal string"


def test_password_constant_time_verification():
    assert verify_password_constant_time("forge-dev-secret") is True
    assert verify_password_constant_time("wrong-password") is False
    assert verify_password_constant_time("") is False
