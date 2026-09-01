from __future__ import annotations

import os
from dataclasses import dataclass


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer, got {raw!r}") from exc


@dataclass(frozen=True)
class ShellyConfig:
    auth_key: str
    server_uri: str
    request_timeout: int = 10
    poll_interval: int = 30
    metrics_port: int = 9100
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "ShellyConfig":
        auth_key = os.getenv("SHELLY_AUTH_KEY")
        if not auth_key:
            raise RuntimeError("SHELLY_AUTH_KEY is required")

        server_uri = os.getenv("SHELLY_SERVER_URI")
        if not server_uri:
            raise RuntimeError("SHELLY_SERVER_URI is required")

        return cls(
            auth_key=auth_key,
            server_uri=server_uri.rstrip("/"),
            request_timeout=_int_env("SHELLY_REQUEST_TIMEOUT", 10),
            poll_interval=_int_env("POLL_INTERVAL", 30),
            metrics_port=_int_env("METRICS_PORT", 9100),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )
