# Shelly Prometheus Exporter — Design

> Manifests created for the `homelabs` cluster (2026-09-01); image published to GHCR. Awaiting a Flux push/reconcile.

## Fit with homelabs

This exporter follows the same repository/deployment pattern documented in
`iot-goodwe-prometheus-exporter/docs/DESIGN.md` under "Generic future-exporter pattern", which was
written specifically as the checklist for this exporter. Unlike the DSMR P1 and GoodWe exporters,
this exporter does not talk to a device on the local network — it talks to the **Shelly Cloud
Control API** over the internet, so there is no local device IP/CIDR to manage and no NetworkPolicy
egress rule to a LAN host.

**Current status:** Kubernetes manifests exist under
`infra/home-exporters/shelly-prometheus-exporter/` in `homelabs` (Deployment, Service, ConfigMap,
ExternalSecret, NetworkPolicy), plus a Prometheus scrape job and Grafana dashboard. See
"Remaining rollout work" below for what's left.

## Why the `/device/all_status` endpoint

The Shelly Cloud Control API "Communication v2.0-beta" `Get device(s) state` endpoint
(`POST /v2/devices/api/get`) requires an explicit list of device ids (1–10 per call), so it cannot
list devices without already knowing their ids. Instead, this exporter uses
`GET /device/all_status?show_info=true&no_shared=true`, which returns every device on the account
— across Gen1, Gen2+ and virtual/thermostat generations — in a single request, keyed by an
internal id with a `_dev_info` block giving the device's real id, generation (`G1`, `G2`, `V1`,
...), model code, and online status. This matches the requirement to "retrieve all Shelly devices
in a single request".

Authentication is the classic `auth_key` query parameter (not OAuth), matching the `cloud-key` +
`server` values already stored in Vault (see below) rather than requiring an OAuth
authorization-code flow.

The API is rate-limited to 1 request/second account-wide; polling all devices in one call every
`POLL_INTERVAL` seconds (default 30s) stays well within that limit regardless of how many devices
are on the account.

## Secret handling (Vault-backed in Kubernetes; plain env vars for local runs)

A Vault secret exists at:

```text
Vault path:  infra/home-exporters/iot-shelly-prometheus-exporter
Keys:        cloud-key   (the Shelly Cloud authorization key)
             server      (e.g. https://shelly-213-eu.shelly.cloud)
```

In Kubernetes, `infra/home-exporters/shelly-prometheus-exporter/shelly-prometheus-exporter-externalsecret.yaml`
maps these to the exporter's env vars via an `ExternalSecret`:

```text
SHELLY_AUTH_KEY    <- cloud-key
SHELLY_SERVER_URI  <- server
```

For local/WSL runs outside the cluster, export the same two values as plain environment variables
(see [README.md](../README.md#local-run)).

`SHELLY_AUTH_KEY` is never logged — only the request URL path and non-secret params would appear in
debug logs, and `requests` does not log query parameters at INFO level in this exporter.

## Metrics design

Because Gen1 and Gen2+ Shelly devices report status in structurally different shapes, `metrics.py`
dispatches per-device based on `_dev_info.gen`:

- **Gen1** (`gen == "G1"`): component data is in top-level arrays — `relays[]` (`ison`),
  `meters[]` (`power`, `total`), `emeters[]` (`power`, `voltage`, `current`, `total`), plus
  `tmp.tC`, `bat.value`, `wifi_sta.rssi`.
- **Gen2+** (anything else, e.g. `G2`, `V1`): component data is in top-level keys shaped like
  `"<component>:<channel>"` (e.g. `switch:0`, `pm1:0`, `temperature:0`, `humidity:0`,
  `devicepower:0`), matched with a regex. `switch`/`pm1` components map to the same
  `shelly_relay_*` metrics as Gen1 relays/meters for a consistent PromQL query surface across
  generations, plus `wifi.rssi` for online device Wi-Fi strength.

All per-component metrics carry `device_id` (the hex Shelly device id from `_dev_info.id`, not the
internal response map key, which is documented as inconsistent) and, where applicable, `channel`.
`shelly_device_info{device_id, code, gen}` is a metadata gauge (always `1`) so PromQL joins can
resolve a human-readable model code / generation for any `device_id`.

Missing/`None` fields are silently skipped (`_set()`), so devices without a given sensor (e.g. no
battery, no humidity) simply never populate that gauge rather than reporting `0`.

Only `switch`, `pm1`, `cover` (id captured, not yet parsed), `temperature`, `humidity`, and
`devicepower` components are recognized today — this is the common set for relay/plug/power-meter
and environment-sensor Shelly devices. Cover (roller shutter) position/state is a TODO.

## Remaining rollout work (from the goodwe DESIGN.md checklist)

- [x] Create `iot-shelly-prometheus-exporter` repository.
- [x] `exporter/` structure adapted (`config.py`, `shelly_client.py`, `metrics.py`).
- [x] `.github/workflows/docker-build.yaml` copied (image name auto-derived from `github.repository`).
- [x] `Dockerfile`, `pyproject.toml`, `requirements.txt` copied.
- [x] Shelly `cloud-key`/`server` already stored in Vault at `infra/home-exporters/iot-shelly-prometheus-exporter`.
- [x] Wire `SHELLY_AUTH_KEY`/`SHELLY_SERVER_URI` through an `ExternalSecret` (`infra/home-exporters/shelly-prometheus-exporter/shelly-prometheus-exporter-externalsecret.yaml`).
- [x] Create `infra/home-exporters/shelly-prometheus-exporter/` manifests in `homelabs` (no local IP/CIDR needed — egress is to the public Shelly Cloud API via a `0.0.0.0/0` except-RFC1918 NetworkPolicy rule on port 443).
- [x] Add `home-exporters/shelly-prometheus-exporter/` to `infra/kustomization.yaml`.
- [x] Add a static scrape job to `infra/observability/prometheus/configmap.yaml`.
- [x] Add a Grafana dashboard configmap under `infra/observability/grafana/` (`dashboard-shelly-configmap.yaml`, uid `shelly-devices`).
- [ ] Push exporter code; wait for GHCR action to publish the image. *(image already published per user confirmation: `ghcr.io/ivanversluis/iot-shelly-prometheus-exporter`.)*
- [ ] Push homelabs manifests; wait for Flux to reconcile.
