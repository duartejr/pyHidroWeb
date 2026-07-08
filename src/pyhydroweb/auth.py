"""Authentication against the ANA HidroWebService.

Python translation of hydroDataBR's ``R/ana-auth.R`` (hydrostat/hydroDataBR,
MIT).  Security posture preserved from the R package:

- credentials come from keyword arguments or environment variables, are never
  logged and never written to disk;
- the token object hides its value in ``repr``/``str``;
- HTTP error bodies are truncated and redacted before being raised.

Credentials must be registered with ANA beforehand (the HidroWebService
requires a personal ``Identificador``/``Senha``).
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Optional

from .exceptions import ApiRequestError, AuthenticationError, TokenExpiredError
from .http import (
    AUTH_BASE_URL,
    build_url,
    error_message_for_response,
    perform_get,
)

#: OAuth route of the authenticated service (capitalization is the ANA's own).
AUTH_PATH = "/OAUth/v1"

#: Environment variables searched for credentials, in order.
IDENTIFIER_ENV_VARS = ("ANA_HIDROWEBSERVICE_IDENTIFIER", "ANA_HIDRO_IDENTIFICADOR")
PASSWORD_ENV_VARS = ("ANA_HIDROWEBSERVICE_PASSWORD", "ANA_HIDRO_SENHA")

#: JSON fields searched for the token in the auth response, in order.
_TOKEN_FIELDS = ("tokenautenticacao", "tokenAutenticacao", "token_autenticacao", "token")

#: The service does not report a TTL; hydroDataBR assumes one hour.
TOKEN_LIFETIME_SECONDS = 60 * 60


@dataclass
class AnaToken:
    """In-memory ANA HidroWebService token. ``repr`` never shows the value."""

    token: str = field(repr=False)
    created_at: datetime
    expires_at: datetime
    base_url: str = AUTH_BASE_URL

    def is_expired(self, safety_margin_seconds: float = 60) -> bool:
        """True when the token is expired or within the safety margin of it."""
        return datetime.now() + timedelta(seconds=safety_margin_seconds) >= self.expires_at

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return (
            "<ANA HidroWebService token "
            f"created_at={self.created_at:%Y-%m-%d %H:%M:%S} "
            f"expires_at={self.expires_at:%Y-%m-%d %H:%M:%S} token=<hidden>>"
        )

    __str__ = __repr__


def _first_non_empty(*values) -> Optional[str]:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _env_value(name: str) -> Optional[str]:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return None
    return value


def resolve_credentials(
    identifier: Optional[str] = None,
    password: Optional[str] = None,
    *,
    identificador: Optional[str] = None,
    senha: Optional[str] = None,
    cpf_cnpj: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    """Resolve credentials from arguments then environment variables."""
    resolved_identifier = _first_non_empty(
        identifier,
        identificador,
        cpf_cnpj,
        *(_env_value(name) for name in IDENTIFIER_ENV_VARS),
    )
    resolved_password = _first_non_empty(
        password,
        senha,
        *(_env_value(name) for name in PASSWORD_ENV_VARS),
    )
    return {"identifier": resolved_identifier, "password": resolved_password}


def has_credentials(**kwargs) -> bool:
    """True when both identifier and password can be resolved."""
    resolved = resolve_credentials(**kwargs)
    return resolved["identifier"] is not None and resolved["password"] is not None


def _extract_token(parsed) -> Optional[str]:
    candidates = [parsed]
    if isinstance(parsed, dict) and parsed.get("items") is not None:
        items = parsed["items"]
        candidates.append(items)
        if isinstance(items, list):
            candidates.extend(item for item in items if isinstance(item, dict))
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        for fld in _TOKEN_FIELDS:
            value = candidate.get(fld)
            if value:
                return str(value)
    return None


def ana_authenticate(
    identifier: Optional[str] = None,
    password: Optional[str] = None,
    *,
    identificador: Optional[str] = None,
    senha: Optional[str] = None,
    cpf_cnpj: Optional[str] = None,
    base_url: str = AUTH_BASE_URL,
    timeout: float = 60,
    max_attempts: int = 3,
    retry_sleep_seconds: float = 1,
) -> AnaToken:
    """Authenticate on the ANA HidroWebService and return an :class:`AnaToken`.

    Credentials can be passed as arguments or through the environment
    variables ``ANA_HIDROWEBSERVICE_IDENTIFIER`` / ``ANA_HIDROWEBSERVICE_PASSWORD``
    (or the Portuguese aliases ``ANA_HIDRO_IDENTIFICADOR`` / ``ANA_HIDRO_SENHA``),
    which is safer for scripts.
    """
    resolved = resolve_credentials(
        identifier,
        password,
        identificador=identificador,
        senha=senha,
        cpf_cnpj=cpf_cnpj,
    )
    if resolved["identifier"] is None or resolved["password"] is None:
        raise AuthenticationError(
            "Provide ANA API credentials through arguments or through the "
            "environment variables ANA_HIDROWEBSERVICE_IDENTIFIER/"
            "ANA_HIDROWEBSERVICE_PASSWORD or ANA_HIDRO_IDENTIFICADOR/ANA_HIDRO_SENHA."
        )
    attempts = max(1, int(max_attempts))
    last_error: Optional[Exception] = None
    for attempt in range(1, attempts + 1):
        try:
            response = perform_get(
                url=build_url(base_url, AUTH_PATH),
                headers={
                    "Identificador": resolved["identifier"],
                    "Senha": resolved["password"],
                    "accept": "*/*",
                },
                timeout=timeout,
            )
            if not 200 <= response["status"] < 300:
                raise AuthenticationError(
                    f"ANA authentication failed. HTTP status: {response['status']}."
                )
            try:
                parsed = json.loads(response["body"])
            except (ValueError, TypeError):
                raise AuthenticationError(
                    "ANA authentication response could not be parsed as JSON."
                ) from None
            token = _extract_token(parsed)
            if not token:
                raise AuthenticationError(
                    "ANA authentication response did not contain a valid token."
                )
            now = datetime.now()
            return AnaToken(
                token=token,
                created_at=now,
                expires_at=now + timedelta(seconds=TOKEN_LIFETIME_SECONDS),
                base_url=base_url,
            )
        except (AuthenticationError, ApiRequestError) as exc:
            last_error = exc
            if attempt < attempts and retry_sleep_seconds > 0:
                time.sleep(retry_sleep_seconds)
    raise AuthenticationError(str(last_error))


def request_json(
    endpoint: str,
    query: Optional[Dict] = None,
    token: Optional[AnaToken] = None,
    base_url: str = AUTH_BASE_URL,
    timeout: float = 60,
):
    """GET a JSON route of the HidroWebService, optionally with a Bearer token.

    Mirrors ``ana_request_json``: token expiry is checked first, non-2xx
    responses raise with a truncated and redacted body, and the parsed JSON is
    returned.
    """
    headers = {"accept": "*/*"}
    if token is not None:
        if isinstance(token, AnaToken):
            if token.is_expired():
                raise TokenExpiredError(
                    "ANA token is expired or too close to expiration."
                )
            base_url = token.base_url
            token_text = token.token
        else:
            token_text = str(token)
        if not token_text:
            raise AuthenticationError("token is empty.")
        headers["Authorization"] = f"Bearer {token_text}"
    response = perform_get(
        url=build_url(base_url, endpoint, query or {}),
        headers=headers,
        timeout=timeout,
    )
    if not 200 <= response["status"] < 300:
        raise ApiRequestError(
            error_message_for_response(
                response["status"], response["body"], "ANA JSON request failed."
            )
        )
    try:
        return json.loads(response["body"])
    except (ValueError, TypeError):
        raise ApiRequestError("ANA JSON response could not be parsed.") from None
