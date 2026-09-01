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

`SHELLY_AUTH_KEY` and `SHELLY_SERVER_URI` are required. For local testing, use the `cloud-key` and
`server` values already stored in Vault at `infra/home-exporters/iot-shelly-prometheus-exporter`.

| Variable | Default | Purpose |
|---|---:|---|
| `SHELLY_AUTH_KEY` | required | Shelly Cloud authorization key (Vault: `cloud-key`) |
| `SHELLY_SERVER_URI` | required | Shelly Cloud server, e.g. `https://shelly-213-eu.shelly.cloud` (Vault: `server`) |
| `SHELLY_REQUEST_TIMEOUT` | `10` | HTTP request timeout in seconds |
| `POLL_INTERVAL` | `30` | Poll interval in seconds |
| `METRICS_PORT` | `9100` | HTTP metrics port |
| `LOG_LEVEL` | `INFO` | Python logging level |

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
export SHELLY_AUTH_KEY="<cloud-key from Vault>"
export SHELLY_SERVER_URI="https://shelly-213-eu.shelly.cloud"
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