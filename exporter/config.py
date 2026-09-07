from __future__ import annotations

import ipaddress
import os
import re
from dataclasses import dataclass
from urllib.parse import urlsplit


_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


def _int_env(name: str, default: int, *, minimum: int, maximum: int | None = None) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise RuntimeError(f"{name} must be an integer") from None

    if value < minimum or (maximum is not None and value > maximum):
        if maximum is None:
            rule = f"at least {minimum}"
        else:
            rule = f"between {minimum} and {maximum}"
        raise RuntimeError(f"{name} must be {rule}")
    return value


def _server_origin(raw: str) -> str:
    if any(
        character.isspace() or ord(character) < 32 or ord(character) == 127
        for character in raw
    ):
        raise RuntimeError("SHELLY_SERVER_URI must not contain whitespace or control characters")
    if "?" in raw or "#" in raw or "\\" in raw:
        raise RuntimeError("SHELLY_SERVER_URI must be an HTTPS origin without query or fragment")

    try:
        parsed = urlsplit(raw)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        raise RuntimeError("SHELLY_SERVER_URI must be a valid HTTPS origin") from None

    try:
        if not hostname:
            raise ValueError
        if ":" in hostname:
            ipaddress.IPv6Address(hostname)
        elif not all(
            re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
            for label in hostname.split(".")
        ):
            raise ValueError
    except ValueError:
        raise RuntimeError("SHELLY_SERVER_URI must be a valid HTTPS origin") from None

    if (
        parsed.scheme.lower() != "https"
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
        or (port is not None and port < 1)
        or (parsed.netloc.endswith(":") and port is None)
    ):
        raise RuntimeError("SHELLY_SERVER_URI must be an HTTPS origin without credentials")

    return raw[:-1] if raw.endswith("/") else raw


def _log_level() -> str:
    raw = os.getenv("LOG_LEVEL", "INFO")
    level = raw.upper()
    if level not in _LOG_LEVELS:
        raise RuntimeError("LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR, or CRITICAL")
    return level


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
        if auth_key is None or not auth_key.strip():
            raise RuntimeError("SHELLY_AUTH_KEY is required")

        server_uri = os.getenv("SHELLY_SERVER_URI")
        if not server_uri:
            raise RuntimeError("SHELLY_SERVER_URI is required")

        return cls(
            auth_key=auth_key,
            server_uri=_server_origin(server_uri),
            request_timeout=_int_env("SHELLY_REQUEST_TIMEOUT", 10, minimum=1),
            poll_interval=_int_env("POLL_INTERVAL", 30, minimum=1),
            metrics_port=_int_env("METRICS_PORT", 9100, minimum=1, maximum=65535),
            log_level=_log_level(),
        )
