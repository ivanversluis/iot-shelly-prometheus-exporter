from __future__ import annotations

import logging
from typing import Any

import requests

from .config import ShellyConfig

log = logging.getLogger(__name__)

_AUTH_ERROR_STATUS_CODES = (401, 403)


class ShellyAuthError(RuntimeError):
    """Raised when Shelly Cloud rejects the configured auth key."""


class ShellyRateLimitError(RuntimeError):
    """Raised when Shelly Cloud responds with a rate-limit error (HTTP 429)."""


def _looks_like_auth_error(errors: Any) -> bool:
    text = str(errors).lower()
    return "auth" in text or "unauthorized" in text or "token" in text


def fetch_all_devices(config: ShellyConfig) -> dict[str, Any]:
    """Fetch the current status of every device on the account in a single request.

    Uses the Shelly Cloud `/device/all_status` endpoint, which returns all devices
    owned by the account in one call. This avoids needing to know device ids up
    front, unlike the newer `/v2/devices/api/get` endpoint which requires an
    explicit (and capped at 10) list of ids per request. The auth key is never
    logged.
    """
    url = f"{config.server_uri}/device/all_status"
    response = requests.get(
        url,
        params={"auth_key": config.auth_key, "show_info": "true", "no_shared": "true"},
        timeout=config.request_timeout,
    )

    if response.status_code in _AUTH_ERROR_STATUS_CODES:
        raise ShellyAuthError(f"Shelly Cloud rejected the configured auth key (HTTP {response.status_code})")
    if response.status_code == 429:
        raise ShellyRateLimitError("Shelly Cloud rate limit exceeded (HTTP 429)")
    response.raise_for_status()

    log.info("GET /device/all_status %d", response.status_code)

    payload = response.json()

    if not payload.get("isok"):
        errors = payload.get("errors")
        if _looks_like_auth_error(errors):
            raise ShellyAuthError(f"Shelly Cloud API rejected the auth key: {errors}")
        raise RuntimeError(f"Shelly Cloud API returned an error: {errors}")

    devices_status = payload.get("data", {}).get("devices_status")
    if not isinstance(devices_status, dict):
        raise RuntimeError(f"Unexpected Shelly Cloud response shape: {type(devices_status)!r}")
    return devices_status
