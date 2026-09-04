<!-- bmad:context -->
<!-- Verified 2026-09-04 against 2a675889a572141407a58541dab26022d6d3f44f. Managed by bmad-project-context; edits inside this block are replaced on refresh. Keep anything you want preserved outside the markers. -->

## iot-shelly-prometheus-exporter

Python 3.12+ Prometheus exporter that polls all devices through the Shelly Cloud API. Design rationale and metric semantics live in `docs/DESIGN.md`; BMAD planning artifacts live under `_bmad-output/`. Kubernetes resources, Prometheus scrape configuration, and Grafana dashboards belong to the separate `homelabs` repository.

## Policy

- Treat published `shelly_*` metric names, label sets, unit suffixes, and `device_id`/`channel` meanings as an external compatibility API. Coordinate intentional breaking changes with tests, documentation, and `homelabs` PromQL/dashboard consumers.
- Never commit, print, log, or serialize `SHELLY_AUTH_KEY`, complete auth-bearing URLs, request parameters, request objects, or configuration objects. HTTP tests must use fake credentials and mocked requests, never Vault or the live Shelly API.
- Preserve the container's numeric non-root `1000:1000` and no-home runtime; do not introduce a root or writable-home requirement.
- Do not hand-edit installer-managed `_bmad/config.toml`, `_bmad/config.user.toml`, `_bmad/{core,bmm}/config.yaml`, or `.agents/skills/*/customize.toml`. Put committed team overrides in `_bmad/custom/config.toml` and personal overrides in the gitignored `_bmad/custom/config.user.toml`.

## Where things are

- Read `docs/DESIGN.md` before changing Shelly communication, authentication, generation normalization, metric identity, or missing-value behavior.
- Make deployment, scrape-job, dashboard, ExternalSecret, and NetworkPolicy changes in the sibling `homelabs` repository, not this repository.

## Running and verifying

- Before handing off Python changes, run `make test` and `make compile`; CI and the image use Python 3.12, so success only in a newer local interpreter does not establish CI parity.
- For dependency or container changes, keep the Python checks and run `make docker-build`. There is currently no `.dockerignore`; ensure the build context contains no real `.env`, credentials, or sensitive data before building.
- Prometheus collectors are module-global and use the default registry. Tests for absence, removal, or counter deltas must isolate registry/state or use unique labels and baselines; never register duplicate collector names in the same process.

## Conventions that differ from defaults

- Keep `pyproject.toml` and `requirements.txt` synchronized when changing runtime dependencies; Make, CI, and Docker install from `requirements.txt`.
- Keep each poll to one `GET /device/all_status` request with `show_info=true` and `no_shared=true`. Do not replace it with per-device fan-out or immediate retries; the Shelly account-wide limit is one request per second.
- Derive the exported device identity from `_dev_info.id`, never the outer response-map key, and preserve the shared Gen1/Gen2+ `shelly_relay_*` query surface.
- Missing fields and vanished devices currently leave prior labelled samples intact, while failed polls retain device samples and set `shelly_up` to zero. Treat cleanup, zeroing, or expiry as an explicit semantic and compatibility change.

<!-- /bmad:context -->
