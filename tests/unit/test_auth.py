"""Tests for pyhydroweb.auth and pyhydroweb.http."""

import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest

from pyhydroweb.auth import (
    AnaToken,
    ana_authenticate,
    request_json,
    resolve_credentials,
)
from pyhydroweb.exceptions import (
    ApiRequestError,
    AuthenticationError,
    TokenExpiredError,
)
from pyhydroweb.http import build_url, redact_sensitive


class TestBuildUrl:
    def test_basic_join(self):
        assert build_url("https://x/y/", "z") == "https://x/y/z"

    def test_query_encoding_with_accents(self):
        url = build_url("https://x", "/r", {"Código da Estação": "123"})
        assert "C%C3%B3digo%20da%20Esta%C3%A7%C3%A3o=123" in url

    def test_empty_query_values_dropped(self):
        url = build_url("https://x", "/r", {"a": None, "b": "", "c": "1"})
        assert url == "https://x/r?c=1"


class TestRedaction:
    def test_redacts_sensitive_words(self):
        text = "Authorization: Bearer abc123, senha=xyz"
        redacted = redact_sensitive(text)
        assert "abc123" not in redacted
        assert "xyz" not in redacted
        assert "<redacted>" in redacted


class TestAnaToken:
    def _token(self, expires_in=3600):
        now = datetime.now()
        return AnaToken(
            token="secret-token-value",
            created_at=now,
            expires_at=now + timedelta(seconds=expires_in),
        )

    def test_repr_hides_token(self):
        token = self._token()
        assert "secret-token-value" not in repr(token)
        assert "<hidden>" in repr(token)
        assert "secret-token-value" not in str(token)

    def test_expiry_with_safety_margin(self):
        assert self._token(expires_in=30).is_expired()
        assert not self._token(expires_in=3600).is_expired()


class TestResolveCredentials:
    def test_args_take_precedence(self, monkeypatch):
        monkeypatch.setenv("ANA_HIDROWEBSERVICE_IDENTIFIER", "env-id")
        resolved = resolve_credentials("arg-id", "arg-pw")
        assert resolved["identifier"] == "arg-id"

    def test_env_fallback(self, monkeypatch):
        monkeypatch.setenv("ANA_HIDROWEBSERVICE_IDENTIFIER", "env-id")
        monkeypatch.setenv("ANA_HIDROWEBSERVICE_PASSWORD", "env-pw")
        resolved = resolve_credentials()
        assert resolved == {"identifier": "env-id", "password": "env-pw"}

    def test_portuguese_aliases(self):
        resolved = resolve_credentials(identificador="id", senha="pw")
        assert resolved == {"identifier": "id", "password": "pw"}


def _response(status=200, body=""):
    return {"status": status, "body": body, "content_type": "application/json"}


class TestAnaAuthenticate:
    def test_missing_credentials(self, monkeypatch):
        for name in (
            "ANA_HIDROWEBSERVICE_IDENTIFIER",
            "ANA_HIDROWEBSERVICE_PASSWORD",
            "ANA_HIDRO_IDENTIFICADOR",
            "ANA_HIDRO_SENHA",
        ):
            monkeypatch.delenv(name, raising=False)
        with pytest.raises(AuthenticationError):
            ana_authenticate()

    @patch("pyhydroweb.auth.perform_get")
    def test_successful_auth(self, mock_get):
        mock_get.return_value = _response(
            200, json.dumps({"items": {"tokenautenticacao": "tok"}})
        )
        token = ana_authenticate("id", "pw")
        assert isinstance(token, AnaToken)
        assert token.token == "tok"
        headers = mock_get.call_args.kwargs["headers"]
        assert headers["Identificador"] == "id"
        assert headers["Senha"] == "pw"
        assert mock_get.call_args.kwargs["url"].endswith("/OAUth/v1")

    @patch("pyhydroweb.auth.perform_get")
    def test_http_error_status(self, mock_get):
        mock_get.return_value = _response(401, "denied")
        with pytest.raises(AuthenticationError) as excinfo:
            ana_authenticate("id", "pw", max_attempts=1)
        assert "401" in str(excinfo.value)

    @patch("pyhydroweb.auth.time.sleep")
    @patch("pyhydroweb.auth.perform_get")
    def test_retries_then_succeeds(self, mock_get, mock_sleep):
        mock_get.side_effect = [
            _response(500, "oops"),
            _response(200, json.dumps({"token": "tok"})),
        ]
        token = ana_authenticate("id", "pw", max_attempts=3)
        assert token.token == "tok"
        assert mock_get.call_count == 2


class TestRequestJson:
    @patch("pyhydroweb.auth.perform_get")
    def test_bearer_header_and_parse(self, mock_get):
        mock_get.return_value = _response(200, json.dumps({"items": [1, 2]}))
        now = datetime.now()
        token = AnaToken("tok", now, now + timedelta(hours=1))
        parsed = request_json("/HidroInventarioEstacoes/v1", token=token)
        assert parsed == {"items": [1, 2]}
        headers = mock_get.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer tok"

    def test_expired_token_refused(self):
        now = datetime.now()
        token = AnaToken("tok", now, now - timedelta(seconds=1))
        with pytest.raises(TokenExpiredError):
            request_json("/x", token=token)

    @patch("pyhydroweb.auth.perform_get")
    def test_error_body_redacted_and_truncated(self, mock_get):
        long_body = "token=SECRETVALUE " + "x" * 500
        mock_get.return_value = _response(500, long_body)
        with pytest.raises(ApiRequestError) as excinfo:
            request_json("/x")
        message = str(excinfo.value)
        assert "SECRETVALUE" not in message
        assert len(message) < 400
