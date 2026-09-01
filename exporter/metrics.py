from __future__ import annotations

import logging
import re
import time
from typing import Any

from prometheus_client import Counter, Gauge, start_http_server

from .config import ShellyConfig
from .shelly_client import fetch_all_devices

log = logging.getLogger(__name__)

# Gen2+ devices report component data as top-level "<component>:<channel>" keys.
_COMPONENT_RE = re.compile(r"^(switch|pm1|cover|temperature|humidity|devicepower):(\d+)$")

SHELLY_UP = Gauge("shelly_up", "1 when the last Shelly Cloud scrape succeeded, 0 otherwise.")
DEVICES_TOTAL = Gauge(
    "shelly_devices_total",
    "Number of devices returned by the last successful scrape.",
)
DEVICE_INFO = Gauge(
    "shelly_device_info",
    "Shelly device metadata. Value is always 1 for each known device.",
    ["device_id", "code", "gen"],
)
DEVICE_ONLINE = Gauge(
    "shelly_device_online",
    "1 if Shelly Cloud reports the device as online, 0 otherwise.",
    ["device_id"],
)
RELAY_OUTPUT = Gauge(
    "shelly_relay_output",
    "1 if the relay/switch output is on, 0 otherwise.",
    ["device_id", "channel"],
)
RELAY_POWER = Gauge(
    "shelly_relay_power_watts",
    "Instantaneous relay/switch power in watts.",
    ["device_id", "channel"],
)
RELAY_VOLTAGE = Gauge(
    "shelly_relay_voltage_volts",
    "Relay/switch input voltage in volts.",
    ["device_id", "channel"],
)
RELAY_CURRENT = Gauge(
    "shelly_relay_current_amps",
    "Relay/switch current in amps.",
    ["device_id", "channel"],
)
RELAY_ENERGY_TOTAL = Gauge(
    "shelly_relay_energy_watthours_total",
    "Cumulative relay/switch energy in watt-hours, as reported by the device.",
    ["device_id", "channel"],
)
TEMPERATURE = Gauge(
    "shelly_temperature_celsius",
    "Sensor or device temperature in degrees Celsius.",
    ["device_id", "channel"],
)
HUMIDITY = Gauge(
    "shelly_humidity_percent",
    "Relative humidity in percent.",
    ["device_id", "channel"],
)
BATTERY = Gauge("shelly_battery_percent", "Battery level in percent.", ["device_id"])
WIFI_RSSI = Gauge("shelly_wifi_rssi_dbm", "Wi-Fi signal strength in dBm.", ["device_id"])
LAST_SCRAPE = Gauge(
    "shelly_last_scrape_timestamp",
    "Unix timestamp (seconds) of the last scrape attempt.",
)
LAST_SCRAPE_SUCCESS = Gauge(
    "shelly_last_scrape_success_timestamp",
    "Unix timestamp (seconds) of the last successful scrape.",
)
SCRAPE_ERRORS = Counter(
    "shelly_scrape_errors_total",
    "Total number of failed Shelly Cloud scrape attempts.",
)


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _set(gauge: Gauge, value: Any, *labels: str) -> None:
    numeric = _as_float(value)
    if numeric is None:
        return
    gauge.labels(*labels).set(numeric)


def _update_gen1(device_id: str, payload: dict[str, Any]) -> None:
    """Gen1 devices report component data as top-level arrays (relays/meters/emeters/...)."""
    for idx, relay in enumerate(payload.get("relays") or []):
        RELAY_OUTPUT.labels(device_id, str(idx)).set(1 if relay.get("ison") else 0)

    for idx, meter in enumerate(payload.get("meters") or []):
        channel = str(idx)
        _set(RELAY_POWER, meter.get("power"), device_id, channel)
        _set(RELAY_ENERGY_TOTAL, meter.get("total"), device_id, channel)

    for idx, emeter in enumerate(payload.get("emeters") or []):
        channel = str(idx)
        _set(RELAY_POWER, emeter.get("power"), device_id, channel)
        _set(RELAY_VOLTAGE, emeter.get("voltage"), device_id, channel)
        _set(RELAY_CURRENT, emeter.get("current"), device_id, channel)
        _set(RELAY_ENERGY_TOTAL, emeter.get("total"), device_id, channel)

    _set(TEMPERATURE, (payload.get("tmp") or {}).get("tC"), device_id, "0")
    _set(BATTERY, (payload.get("bat") or {}).get("value"), device_id)
    _set(WIFI_RSSI, (payload.get("wifi_sta") or {}).get("rssi"), device_id)


def _update_gen2(device_id: str, payload: dict[str, Any]) -> None:
    """Gen2+ devices report component data as `"<component>:<channel>"` keys."""
    for key, value in payload.items():
        match = _COMPONENT_RE.match(key)
        if not match or not isinstance(value, dict):
            continue
        component, channel = match.group(1), match.group(2)

        if component in ("switch", "pm1"):
            if "output" in value:
                RELAY_OUTPUT.labels(device_id, channel).set(1 if value.get("output") else 0)
            _set(RELAY_POWER, value.get("apower"), device_id, channel)
            _set(RELAY_VOLTAGE, value.get("voltage"), device_id, channel)
            _set(RELAY_CURRENT, value.get("current"), device_id, channel)
            _set(RELAY_ENERGY_TOTAL, (value.get("aenergy") or {}).get("total"), device_id, channel)
            temperature = value.get("temperature")
            if isinstance(temperature, dict):
                _set(TEMPERATURE, temperature.get("tC"), device_id, channel)
        elif component == "temperature":
            _set(TEMPERATURE, value.get("tC"), device_id, channel)
        elif component == "humidity":
            _set(HUMIDITY, value.get("rh"), device_id, channel)
        elif component == "devicepower":
            _set(BATTERY, (value.get("battery") or {}).get("percent"), device_id)

    _set(WIFI_RSSI, (payload.get("wifi") or {}).get("rssi"), device_id)


def update_metrics(devices_status: dict[str, Any]) -> None:
    """Update all Prometheus metrics from a `/device/all_status` response."""
    for payload in devices_status.values():
        if not isinstance(payload, dict):
            continue

        dev_info = payload.get("_dev_info") or {}
        device_id = str(dev_info.get("id") or "unknown")
        code = str(dev_info.get("code") or "unknown")
        gen = str(dev_info.get("gen") or "unknown")

        DEVICE_INFO.labels(device_id, code, gen).set(1)
        DEVICE_ONLINE.labels(device_id).set(1 if dev_info.get("online") else 0)

        if gen == "G1":
            _update_gen1(device_id, payload)
        else:
            _update_gen2(device_id, payload)

    DEVICES_TOTAL.set(len(devices_status))
    now = time.time()
    SHELLY_UP.set(1)
    LAST_SCRAPE.set(now)
    LAST_SCRAPE_SUCCESS.set(now)


def poll_loop(config: ShellyConfig) -> None:
    """Main loop: fetch all device statuses from Shelly Cloud and update metrics."""
    SHELLY_UP.set(0)

    while True:
        LAST_SCRAPE.set(time.time())
        try:
            devices_status = fetch_all_devices(config)
            update_metrics(devices_status)
            log.debug("Updated Shelly metrics from %d devices", len(devices_status))
        except Exception:
            SCRAPE_ERRORS.inc()
            SHELLY_UP.set(0)
            log.exception("Shelly Cloud scrape failed")

        time.sleep(config.poll_interval)


def main() -> None:
    """Entrypoint: configure logging, start HTTP server, begin polling."""
    config = ShellyConfig.from_env()

    logging.basicConfig(
        level=config.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    start_http_server(config.metrics_port)
    log.info("Shelly Cloud Prometheus exporter listening on port %d", config.metrics_port)
    poll_loop(config)
