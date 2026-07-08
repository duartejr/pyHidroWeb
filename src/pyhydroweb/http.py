"""Low-level HTTP helpers for the ANA HidroWebService.

Python translation of the request helpers in hydroDataBR's ``R/ana-auth.R``
(hydrostat/hydroDataBR, MIT).  Sensitive material (tokens, passwords,
CPF/CNPJ) is redacted from error messages before they are raised.
"""

from __future__ import annotations

import re
from typing import Dict, Optional
from urllib.parse import quote

import requests

from .exceptions import ApiRequestError

#: Base URL of the authenticated ANA HidroWebService.
AUTH_BASE_URL = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas"

#: Base URL of the legacy (unauthenticated) ANA SOAP/asmx service.
LEGACY_BASE_URL = "https://telemetriaws1.ana.gov.br/ServiceANA.asmx"

# Stronger than hydroDataBR's original: also consumes a separator and the
# following token, so "Bearer abc123" or "senha: xyz" never leak the value.
_SENSITIVE_PATTERN = re.compile(
    r"(?i)(authorization|bearer|token|senha|password|cpf|cnpj|identificador)"
    r"[^,;\s]*(?:[\s:=]+[^,;\s]+){0,2}"
)


def redact_sensitive(text: str) -> str:
    """Replace credential-looking substrings with ``<redacted>``."""
    if not text:
        return text
    return _SENSITIVE_PATTERN.sub("<redacted>", text)


def build_url(base_url: str, path: str = "", query: Optional[Dict] = None) -> str:
    """Join base URL, path and query string, URL-encoding names and values.

    ``None``/empty query values are dropped, matching hydroDataBR's
    ``ana_build_url``.
    """
    base_url = re.sub(r"/+$", "", str(base_url))
    path = str(path or "")
    if path and not path.startswith("/"):
        path = "/" + path
    url = base_url + path
    if not query:
        return url
    parts = []
    for name, value in query.items():
        if value is None:
            continue
        value_text = str(value)
        if not value_text:
            continue
        parts.append(f"{quote(str(name), safe='')}={quote(value_text, safe='')}")
    if not parts:
        return url
    return url + "?" + "&".join(parts)


def perform_get(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 60,
) -> Dict:
    """Perform a GET request and return ``{"status", "body", "content_type"}``.

    Does not raise on non-2xx status codes — callers inspect ``status`` and
    build redacted error messages themselves (mirrors ``ana_perform_get``).
    Network-level failures raise :class:`ApiRequestError` with a redacted
    message.
    """
    clean_headers = {
        str(k): str(v) for k, v in (headers or {}).items() if v is not None
    }
    try:
        response = requests.get(url, headers=clean_headers, timeout=timeout)
    except requests.RequestException as exc:
        raise ApiRequestError(
            f"ANA request failed: {redact_sensitive(str(exc))}"
        ) from None
    return {
        "status": response.status_code,
        "body": response.text,
        "content_type": response.headers.get("Content-Type", ""),
    }


def error_message_for_response(status: int, body: str, context: str) -> str:
    """Build a safe error message: body truncated to 240 chars and redacted."""
    snippet = re.sub(r"[\r\n]+", " ", (body or "")[:240])
    snippet = redact_sensitive(snippet)
    message = f"{context} HTTP status: {status}."
    if snippet.strip():
        message += f" Response body: {snippet}"
    return message
