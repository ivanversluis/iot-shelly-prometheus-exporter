from __future__ import annotations

import logging
from typing import Any

import requests

from .config import ShellyConfig

log = logging.getLogger(__name__)


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
    response.raise_for_status()
    payload = response.json()

    if not payload.get("isok"):
        raise RuntimeError(f"Shelly Cloud API returned an error: {payload.get('errors')}")

    devices_status = payload.get("data", {}).get("devices_status")
    if not isinstance(devices_status, dict):
        raise RuntimeError(f"Unexpected Shelly Cloud response shape: {type(devices_status)!r}")
    return devices_status
