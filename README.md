# Shelly Prometheus Exporter

Prometheus exporter for Shelly devices via the **Shelly Cloud Control API**, so it works without
opening any inbound access to devices on the LAN. Intended for the `ivanversluis/homelabs`
`home-exporters` setup and publishes to GHCR as:

```text
ghcr.io/ivanversluis/iot-shelly-prometheus-exporter
```

> **Status:** manifests created under `homelabs/infra/home-exporters/shelly-prometheus-exporter/`;
> awaiting a Flux push/reconcile. See [docs/DESIGN.md](docs/DESIGN.md) for the rollout checklist.

## Architecture

```
Shelly Cloud API (HTTPS) ──> shelly_client.py ──> metrics.py ──> /metrics (Prometheus)
  /device/all_status           (single request           (Gauges/Counters,
                                for all devices)           polled every POLL_INTERVAL)
```

- `exporter/config.py` builds a `ShellyConfig` from environment variables.
- `exporter/shelly_client.py` calls the Shelly Cloud `/device/all_status` endpoint, which returns
  the status of **every** device on the account in a single request (see
  [docs/DESIGN.md](docs/DESIGN.md#why-the-deviceall_status-endpoint) for why this was chosen over
  the newer `/v2/devices/api/get` endpoint).
- `exporter/metrics.py` maps each device's status onto labelled Prometheus Gauges/Counters
  (labelled by `device_id`, and `channel` where applicable) and runs the poll loop.

## Runtime configuration

`SHELLY_AUTH_KEY` and `SHELLY_SERVER_URI` are required. Configuration is validated before the
metrics server binds or Shelly Cloud is contacted; invalid configuration terminates startup with a
credential-safe error.

| Variable | Default | Accepted values |
|---|---:|---|
| `SHELLY_AUTH_KEY` | required | Non-empty, non-whitespace Shelly Cloud authorization key |
| `SHELLY_SERVER_URI` | required | HTTPS origin with a host, optional valid port, and optional single trailing slash; credentials, paths, queries, and fragments are rejected |
| `SHELLY_REQUEST_TIMEOUT` | `10` | Integer greater than zero, in seconds |
| `POLL_INTERVAL` | `30` | Integer of at least one second |
| `METRICS_PORT` | `9100` | Integer from `1` through `65535` |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` (case-insensitive) |

## Metrics

| Metric | Labels | Description |
|--------|--------|-------------|
| `shelly_up` | — | `1` when the last Shelly Cloud scrape succeeded |
| `shelly_devices_total` | — | Number of devices returned by the last successful scrape |
| `shelly_device_info` | `device_id`, `code`, `gen` | Always `1`; identifies each known device |
| `shelly_device_online` | `device_id` | `1` if Shelly Cloud reports the device online |
| `shelly_relay_output` | `device_id`, `channel` | `1` if the relay/switch output is on |
| `shelly_relay_power_watts` | `device_id`, `channel` | Instantaneous relay/switch power |
| `shelly_relay_voltage_volts` | `device_id`, `channel` | Relay/switch input voltage |
| `shelly_relay_current_amps` | `device_id`, `channel` | Relay/switch current |
| `shelly_relay_energy_watthours_total` | `device_id`, `channel` | Cumulative energy, as reported by the device |
| `shelly_temperature_celsius` | `device_id`, `channel` | Sensor/device temperature |
| `shelly_humidity_percent` | `device_id`, `channel` | Relative humidity |
| `shelly_battery_percent` | `device_id` | Battery level |
| `shelly_wifi_rssi_dbm` | `device_id` | Wi-Fi signal strength |
| `shelly_last_scrape_timestamp` | — | Unix timestamp of the last scrape attempt |
| `shelly_last_scrape_success_timestamp` | — | Unix timestamp of the last successful scrape |
| `shelly_scrape_errors_total` | — | Total failed scrape attempts (Counter) |

Gen1 and Gen2+ devices report different underlying JSON shapes; both are normalized onto the same
`shelly_relay_*` metrics — see [docs/DESIGN.md](docs/DESIGN.md#metrics-design).

## Local run

```bash
export SHELLY_AUTH_KEY="<your Shelly Cloud authorization key>"
export SHELLY_SERVER_URI="https://<your assigned Shelly Cloud server>"
make install
make run
curl http://127.0.0.1:9100/metrics
```

## Testing

```bash
make install-dev
make test       # pytest tests/ -v
make coverage   # pytest with coverage report
```

## Releases

Release promotion is a local, credential-free operation. From a clean checkout, run the same
validation gates used by the command and choose exactly one promotion:

```bash
make test
make compile
make release PROMOTION=patch   # 0.1.0 -> 0.1.1
make release PROMOTION=minor   # 0.1.0 -> 0.2.0
make release PROMOTION=major   # 0.1.0 -> 1.0.0
```

The command reads the version only from `pyproject.toml`, refuses dirty trees and existing tags,
updates the metadata, commits it, and creates an annotated local `vX.Y.Z` tag. It never pushes;
inspect the commit and tag, then publish through the authorized default-branch/version-tag GitHub
Actions workflow. This project is still `0.x`: patch and minor releases are normal, while major is
reserved for an explicit `1.0.0` decision.

Use immutable image tags (`vX.Y.Z` or `sha-<commit>`) in deployment and release notes. Release
notes should mention metric compatibility, configuration/operator actions, and known limitations.
To roll back, deploy the previous immutable image tag; do not move or overwrite a release tag.

## Container build

The GitHub Actions workflow at `.github/workflows/docker-build.yaml` builds and pushes to GHCR on every push to `main`, on version tags (`v*`), and on `workflow_dispatch`. Pull requests run the validate step only (no push). The image is published as:

- `ghcr.io/ivanversluis/iot-shelly-prometheus-exporter:main`
- `ghcr.io/ivanversluis/iot-shelly-prometheus-exporter:latest`
- `ghcr.io/ivanversluis/iot-shelly-prometheus-exporter:<tag>`
- `ghcr.io/ivanversluis/iot-shelly-prometheus-exporter:sha-<commit>`

## Homelabs deployment

Manifests live in `homelabs/infra/home-exporters/shelly-prometheus-exporter/` (Deployment,
Service, ConfigMap, ExternalSecret, NetworkPolicy), wired into Prometheus scraping and a Grafana
dashboard (`shelly-devices`, uid `shelly-devices`). See
[docs/DESIGN.md](docs/DESIGN.md#remaining-rollout-work) for the rollout checklist — the only
remaining step is pushing the `homelabs` manifests for Flux to reconcile.
