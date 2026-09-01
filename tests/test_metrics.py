"""Tests for Shelly /device/all_status to Prometheus metric mapping."""

from __future__ import annotations

from exporter.metrics import (
    BATTERY,
    DEVICE_INFO,
    DEVICE_ONLINE,
    DEVICES_TOTAL,
    HUMIDITY,
    LAST_SCRAPE_SUCCESS,
    RELAY_CURRENT,
    RELAY_ENERGY_TOTAL,
    RELAY_OUTPUT,
    RELAY_POWER,
    RELAY_VOLTAGE,
    SHELLY_UP,
    TEMPERATURE,
    WIFI_RSSI,
    update_metrics,
)


def _value(gauge, *labels) -> float | None:
    if labels:
        return gauge.labels(*labels)._value.get()
    return gauge._value.get()


class TestUpdateMetricsGen1:
    """Gen1 devices report relays/meters/emeters as top-level arrays."""

    DEVICE_ID = "aabbccddeeff"

    DEVICES_STATUS = {
        "aabbccddeeff": {
            "_dev_info": {"id": "aabbccddeeff", "gen": "G1", "code": "SHPLG-S", "online": True},
            "relays": [{"ison": True}],
            "meters": [{"power": 42.5, "total": 12345.0}],
            "tmp": {"tC": 35.2},
            "wifi_sta": {"rssi": -60},
        }
    }

    def test_device_info_and_online(self) -> None:
        update_metrics(self.DEVICES_STATUS)
        assert _value(DEVICE_INFO, self.DEVICE_ID, "SHPLG-S", "G1") == 1.0
        assert _value(DEVICE_ONLINE, self.DEVICE_ID) == 1.0

    def test_relay_output_and_power(self) -> None:
        update_metrics(self.DEVICES_STATUS)
        assert _value(RELAY_OUTPUT, self.DEVICE_ID, "0") == 1.0
        assert _value(RELAY_POWER, self.DEVICE_ID, "0") == 42.5
        assert _value(RELAY_ENERGY_TOTAL, self.DEVICE_ID, "0") == 12345.0

    def test_temperature_and_wifi(self) -> None:
        update_metrics(self.DEVICES_STATUS)
        assert _value(TEMPERATURE, self.DEVICE_ID, "0") == 35.2
        assert _value(WIFI_RSSI, self.DEVICE_ID) == -60.0

    def test_marks_up_and_devices_total(self) -> None:
        update_metrics(self.DEVICES_STATUS)
        assert _value(SHELLY_UP) == 1.0
        assert _value(DEVICES_TOTAL) == 1.0
        assert _value(LAST_SCRAPE_SUCCESS) is not None


class TestUpdateMetricsGen2:
    """Gen2+ devices report component data as "<component>:<channel>" keys."""

    DEVICE_ID = "b48a0a1cd978"

    DEVICES_STATUS = {
        "b48a0a1cd978": {
            "_dev_info": {"id": "b48a0a1cd978", "gen": "G2", "code": "SNSW-001P16EU", "online": True},
            "switch:0": {
                "output": True,
                "apower": 15.3,
                "voltage": 230.1,
                "current": 0.07,
                "aenergy": {"total": 999.4},
                "temperature": {"tC": 41.0},
            },
            # A separate add-on sensor (distinct channel from the switch's internal
            # "temperature" reading) so the two do not collide on the same label set.
            "temperature:100": {"tC": 21.5},
            "humidity:0": {"rh": 55.2},
            "devicepower:0": {"battery": {"percent": 87}},
            "wifi": {"rssi": -50},
        }
    }

    def test_switch_component(self) -> None:
        update_metrics(self.DEVICES_STATUS)
        assert _value(RELAY_OUTPUT, self.DEVICE_ID, "0") == 1.0
        assert _value(RELAY_POWER, self.DEVICE_ID, "0") == 15.3
        assert _value(RELAY_VOLTAGE, self.DEVICE_ID, "0") == 230.1
        assert _value(RELAY_CURRENT, self.DEVICE_ID, "0") == 0.07
        assert _value(RELAY_ENERGY_TOTAL, self.DEVICE_ID, "0") == 999.4
        assert _value(TEMPERATURE, self.DEVICE_ID, "0") == 41.0

    def test_environment_sensors(self) -> None:
        update_metrics(self.DEVICES_STATUS)
        assert _value(TEMPERATURE, self.DEVICE_ID, "100") == 21.5
        assert _value(HUMIDITY, self.DEVICE_ID, "0") == 55.2
        assert _value(BATTERY, self.DEVICE_ID) == 87.0
        assert _value(WIFI_RSSI, self.DEVICE_ID) == -50.0


class TestUpdateMetricsMissingFields:
    """Devices/fields absent from the response must not raise and must be skipped."""

    def test_empty_devices_status_still_marks_up(self) -> None:
        update_metrics({})
        assert _value(SHELLY_UP) == 1.0
        assert _value(DEVICES_TOTAL) == 0.0

    def test_offline_device_reports_zero(self) -> None:
        update_metrics(
            {
                "offline-device": {
                    "_dev_info": {"id": "offline-device", "gen": "G2", "code": "SNSW-001P16EU", "online": False},
                }
            }
        )
        assert _value(DEVICE_ONLINE, "offline-device") == 0.0

    def test_non_dict_device_payload_is_skipped(self) -> None:
        update_metrics({"weird": "not-a-dict"})
        assert _value(DEVICES_TOTAL) == 1.0
