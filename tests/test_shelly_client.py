"""Tests for Shelly Cloud config parsing and the /device/all_status client."""

from __future__ import annotations

import os
import subprocess
import sys
import traceback
from typing import Any

import pytest

import exporter.metrics as metrics_module
import exporter.shelly_client as client_module
from exporter.config import ShellyConfig
from exporter.shelly_client import ShellyAuthError, ShellyRateLimitError, fetch_all_devices


class TestShellyConfigFromEnv:
    @staticmethod
    def _set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SHELLY_AUTH_KEY", "test-key")
        monkeypatch.setenv("SHELLY_SERVER_URI", "https://shelly-213-eu.shelly.cloud")

    @pytest.mark.parametrize("auth_key", [None, "", " ", "\t\r\n"])
    def test_rejects_missing_empty_or_whitespace_auth_key(
        self, monkeypatch: pytest.MonkeyPatch, auth_key: str | None
    ) -> None:
        monkeypatch.setenv("SHELLY_SERVER_URI", "https://shelly-213-eu.shelly.cloud")
        if auth_key is None:
            monkeypatch.delenv("SHELLY_AUTH_KEY", raising=False)
        else:
            monkeypatch.setenv("SHELLY_AUTH_KEY", auth_key)

        with pytest.raises(RuntimeError, match="^SHELLY_AUTH_KEY is required$") as raised:
            ShellyConfig.from_env()
        assert str(raised.value) == "SHELLY_AUTH_KEY is required"

    def test_requires_server_uri(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._set_required_env(monkeypatch)
        monkeypatch.delenv("SHELLY_SERVER_URI", raising=False)
        with pytest.raises(RuntimeError, match="SHELLY_SERVER_URI is required"):
            ShellyConfig.from_env()

    @pytest.mark.parametrize(
        ("server_uri", "expected"),
        [
            ("https://shelly-213-eu.shelly.cloud", "https://shelly-213-eu.shelly.cloud"),
            ("https://shelly-213-eu.shelly.cloud/", "https://shelly-213-eu.shelly.cloud"),
            ("https://localhost:8443/", "https://localhost:8443"),
            ("https://[2001:db8::1]:443/", "https://[2001:db8::1]:443"),
        ],
    )
    def test_accepts_https_origins(
        self, monkeypatch: pytest.MonkeyPatch, server_uri: str, expected: str
    ) -> None:
        self._set_required_env(monkeypatch)
        monkeypatch.setenv("SHELLY_SERVER_URI", server_uri)
        config = ShellyConfig.from_env()
        assert config.server_uri == expected
        assert config.auth_key == "test-key"

    @pytest.mark.parametrize(
        "server_uri",
        [
            "http://example.com",
            "example.com",
            "https:///missing-host",
            "https://user:password@example.com",
            "https://example.com/path",
            "https://example.com//",
            "https://example.com?",
            "https://example.com?token=planted-query-secret",
            "https://example.com#fragment",
            "https://example.com:invalid-port",
            "https://example.com:0",
            "https://example.com:70000",
            "https://example.com:",
            "https://-",
            "https://.",
            "https://[not-an-ipv6-address]",
            "https://example\\.com",
            "https://example.com/ planted-uri-secret",
            "https://example.com/\x1fplanted-uri-secret",
        ],
    )
    def test_rejects_unsafe_or_malformed_server_uri_without_echoing_it(
        self, monkeypatch: pytest.MonkeyPatch, server_uri: str
    ) -> None:
        self._set_required_env(monkeypatch)
        monkeypatch.setenv("SHELLY_SERVER_URI", server_uri)

        with pytest.raises(RuntimeError) as raised:
            ShellyConfig.from_env()
        assert server_uri not in str(raised.value)
        assert "planted" not in str(raised.value)
        assert "planted" not in "".join(traceback.format_exception(raised.value))

    def test_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._set_required_env(monkeypatch)
        for var in ("SHELLY_REQUEST_TIMEOUT", "POLL_INTERVAL", "METRICS_PORT", "LOG_LEVEL"):
            monkeypatch.delenv(var, raising=False)
        config = ShellyConfig.from_env()
        assert config.request_timeout == 10
        assert config.poll_interval == 30
        assert config.metrics_port == 9100
        assert config.log_level == "INFO"

    def test_overrides(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._set_required_env(monkeypatch)
        monkeypatch.setenv("SHELLY_REQUEST_TIMEOUT", "5")
        monkeypatch.setenv("POLL_INTERVAL", "60")
        monkeypatch.setenv("METRICS_PORT", "9200")
        monkeypatch.setenv("LOG_LEVEL", "debug")
        config = ShellyConfig.from_env()
        assert config.request_timeout == 5
        assert config.poll_interval == 60
        assert config.metrics_port == 9200
        assert config.log_level == "DEBUG"

    @pytest.mark.parametrize(
        ("variable", "value"),
        [
            ("SHELLY_REQUEST_TIMEOUT", "1"),
            ("POLL_INTERVAL", "1"),
            ("METRICS_PORT", "1"),
            ("METRICS_PORT", "65535"),
        ],
    )
    def test_accepts_numeric_boundaries(
        self, monkeypatch: pytest.MonkeyPatch, variable: str, value: str
    ) -> None:
        self._set_required_env(monkeypatch)
        monkeypatch.setenv(variable, value)
        config = ShellyConfig.from_env()
        field = {
            "SHELLY_REQUEST_TIMEOUT": "request_timeout",
            "POLL_INTERVAL": "poll_interval",
            "METRICS_PORT": "metrics_port",
        }[variable]
        assert getattr(config, field) == int(value)

    @pytest.mark.parametrize(
        ("variable", "value"),
        [
            ("SHELLY_REQUEST_TIMEOUT", "0"),
            ("SHELLY_REQUEST_TIMEOUT", "-1"),
            ("SHELLY_REQUEST_TIMEOUT", "0.5"),
            ("POLL_INTERVAL", "0"),
            ("POLL_INTERVAL", "-1"),
            ("POLL_INTERVAL", "planted-numeric-secret"),
            ("METRICS_PORT", "0"),
            ("METRICS_PORT", "65536"),
            ("METRICS_PORT", ""),
        ],
    )
    def test_rejects_invalid_numeric_values_without_echoing_them(
        self, monkeypatch: pytest.MonkeyPatch, variable: str, value: str
    ) -> None:
        self._set_required_env(monkeypatch)
        monkeypatch.setenv(variable, value)

        with pytest.raises(RuntimeError) as raised:
            ShellyConfig.from_env()
        assert variable in str(raised.value)
        assert str(raised.value) in {
            f"{variable} must be an integer",
            f"{variable} must be at least 1",
            f"{variable} must be between 1 and 65535",
        }
        assert "planted" not in "".join(traceback.format_exception(raised.value))

    @pytest.mark.parametrize("log_level", ["debug", "INFO", "Warning", "error", "CRITICAL"])
    def test_accepts_canonical_log_levels_case_insensitively(
        self, monkeypatch: pytest.MonkeyPatch, log_level: str
    ) -> None:
        self._set_required_env(monkeypatch)
        monkeypatch.setenv("LOG_LEVEL", log_level)
        assert ShellyConfig.from_env().log_level == log_level.upper()

    @pytest.mark.parametrize("log_level", ["", "WARN", "FATAL", "NOTSET", "verbose"])
    def test_rejects_empty_alias_and_unknown_log_levels_without_echoing_them(
        self, monkeypatch: pytest.MonkeyPatch, log_level: str
    ) -> None:
        self._set_required_env(monkeypatch)
        monkeypatch.setenv("LOG_LEVEL", log_level)

        with pytest.raises(RuntimeError) as raised:
            ShellyConfig.from_env()
        assert str(raised.value) == "LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR, or CRITICAL"

    def test_direct_construction_remains_unvalidated(self) -> None:
        config = ShellyConfig(auth_key="", server_uri="http://direct-construction")
        assert config.auth_key == ""
        assert config.server_uri == "http://direct-construction"

    def test_invalid_configuration_prevents_bind_and_poll(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._set_required_env(monkeypatch)
        monkeypatch.setenv("METRICS_PORT", "0")
        calls: list[str] = []
        monkeypatch.setattr(metrics_module, "start_http_server", lambda port: calls.append("bind"))
        monkeypatch.setattr(metrics_module, "poll_loop", lambda config: calls.append("poll"))

        with pytest.raises(RuntimeError, match="METRICS_PORT"):
            metrics_module.main()
        assert calls == []

    def test_invalid_configuration_exits_process_without_echoing_secret(self) -> None:
        environment = os.environ.copy()
        for variable in (
            "SHELLY_REQUEST_TIMEOUT",
            "POLL_INTERVAL",
            "METRICS_PORT",
            "LOG_LEVEL",
        ):
            environment.pop(variable, None)
        environment.update(
            {
                "SHELLY_AUTH_KEY": "planted-process-secret",
                "SHELLY_SERVER_URI": "https://example.com",
                "METRICS_PORT": "0",
            }
        )

        result = subprocess.run(
            [sys.executable, "-m", "exporter"],
            cwd=os.path.dirname(os.path.dirname(__file__)),
            env=environment,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        assert result.returncode != 0
        assert "METRICS_PORT" in result.stderr
        assert "planted-process-secret" not in result.stderr


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
