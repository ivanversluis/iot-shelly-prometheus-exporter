"""Tests for Shelly Cloud config parsing and the /device/all_status client."""

from __future__ import annotations

from typing import Any

import pytest

import exporter.shelly_client as client_module
from exporter.config import ShellyConfig
from exporter.shelly_client import ShellyAuthError, ShellyRateLimitError, fetch_all_devices


class TestShellyConfigFromEnv:
    def test_requires_auth_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SHELLY_AUTH_KEY", raising=False)
        monkeypatch.setenv("SHELLY_SERVER_URI", "https://shelly-213-eu.shelly.cloud")
        with pytest.raises(RuntimeError, match="SHELLY_AUTH_KEY is required"):
            ShellyConfig.from_env()

    def test_requires_server_uri(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SHELLY_AUTH_KEY", "test-key")
        monkeypatch.delenv("SHELLY_SERVER_URI", raising=False)
        with pytest.raises(RuntimeError, match="SHELLY_SERVER_URI is required"):
            ShellyConfig.from_env()

    def test_strips_trailing_slash_from_server_uri(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SHELLY_AUTH_KEY", "test-key")
        monkeypatch.setenv("SHELLY_SERVER_URI", "https://shelly-213-eu.shelly.cloud/")
        config = ShellyConfig.from_env()
        assert config.server_uri == "https://shelly-213-eu.shelly.cloud"

    def test_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SHELLY_AUTH_KEY", "test-key")
        monkeypatch.setenv("SHELLY_SERVER_URI", "https://shelly-213-eu.shelly.cloud")
        for var in ("SHELLY_REQUEST_TIMEOUT", "POLL_INTERVAL", "METRICS_PORT", "LOG_LEVEL"):
            monkeypatch.delenv(var, raising=False)
        config = ShellyConfig.from_env()
        assert config.request_timeout == 10
        assert config.poll_interval == 30
        assert config.metrics_port == 9100
        assert config.log_level == "INFO"

    def test_overrides(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SHELLY_AUTH_KEY", "test-key")
        monkeypatch.setenv("SHELLY_SERVER_URI", "https://shelly-213-eu.shelly.cloud")
        monkeypatch.setenv("SHELLY_REQUEST_TIMEOUT", "5")
        monkeypatch.setenv("POLL_INTERVAL", "60")
        monkeypatch.setenv("METRICS_PORT", "9200")
        monkeypatch.setenv("LOG_LEVEL", "debug")
        config = ShellyConfig.from_env()
        assert config.request_timeout == 5
        assert config.poll_interval == 60
        assert config.metrics_port == 9200
        assert config.log_level == "DEBUG"

    def test_invalid_int_env_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SHELLY_AUTH_KEY", "test-key")
        monkeypatch.setenv("SHELLY_SERVER_URI", "https://shelly-213-eu.shelly.cloud")
        monkeypatch.setenv("POLL_INTERVAL", "not-a-number")
        with pytest.raises(RuntimeError, match="POLL_INTERVAL must be an integer"):
            ShellyConfig.from_env()


class _FakeResponse:
    def __init__(self, json_data: dict[str, Any], status_code: int = 200) -> None:
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict[str, Any]:
        return self._json_data


CONFIG = ShellyConfig(auth_key="test-key", server_uri="https://shelly-213-eu.shelly.cloud")


class TestFetchAllDevices:
    def test_returns_devices_status(self, monkeypatch: pytest.MonkeyPatch) -> None:
        devices_status = {"abc123": {"_dev_info": {"id": "abc123", "gen": "G2"}}}
        fake_response = _FakeResponse({"isok": True, "data": {"devices_status": devices_status}})

        captured: dict[str, Any] = {}

        def fake_get(url: str, params: dict[str, Any], timeout: int) -> _FakeResponse:
            captured["url"] = url
            captured["params"] = params
            captured["timeout"] = timeout
            return fake_response

        monkeypatch.setattr(client_module.requests, "get", fake_get)

        result = fetch_all_devices(CONFIG)

        assert result == devices_status
        assert captured["url"] == "https://shelly-213-eu.shelly.cloud/device/all_status"
        assert captured["params"] == {
            "auth_key": "test-key",
            "show_info": "true",
            "no_shared": "true",
        }
        assert captured["timeout"] == 10

    def test_raises_on_isok_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_response = _FakeResponse({"isok": False, "errors": ["internal server error"]})
        monkeypatch.setattr(client_module.requests, "get", lambda *a, **k: fake_response)

        with pytest.raises(RuntimeError, match="Shelly Cloud API returned an error"):
            fetch_all_devices(CONFIG)

    def test_raises_on_unexpected_shape(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_response = _FakeResponse({"isok": True, "data": {"devices_status": ["not", "a", "dict"]}})
        monkeypatch.setattr(client_module.requests, "get", lambda *a, **k: fake_response)

        with pytest.raises(RuntimeError, match="Unexpected Shelly Cloud response shape"):
            fetch_all_devices(CONFIG)

    def test_raises_shelly_auth_error_on_401(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_response = _FakeResponse({}, status_code=401)
        monkeypatch.setattr(client_module.requests, "get", lambda *a, **k: fake_response)

        with pytest.raises(ShellyAuthError, match="HTTP 401"):
            fetch_all_devices(CONFIG)

    def test_raises_shelly_auth_error_on_403(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_response = _FakeResponse({}, status_code=403)
        monkeypatch.setattr(client_module.requests, "get", lambda *a, **k: fake_response)

        with pytest.raises(ShellyAuthError, match="HTTP 403"):
            fetch_all_devices(CONFIG)

    def test_raises_shelly_auth_error_on_isok_false_auth_message(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_response = _FakeResponse({"isok": False, "errors": ["invalid auth_key"]})
        monkeypatch.setattr(client_module.requests, "get", lambda *a, **k: fake_response)

        with pytest.raises(ShellyAuthError, match="rejected the auth key"):
            fetch_all_devices(CONFIG)

    def test_raises_rate_limit_error_on_429(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_response = _FakeResponse({}, status_code=429)
        monkeypatch.setattr(client_module.requests, "get", lambda *a, **k: fake_response)

        with pytest.raises(ShellyRateLimitError, match="rate limit exceeded"):
            fetch_all_devices(CONFIG)
