# Evidence and Recommendations

Evidence was verified on 2026-09-04 against commit `2a675889a572141407a58541dab26022d6d3f44f`. “Confirmed” describes repository behavior or a reproduced observation; “Recommended” is milestone scope, not current behavior.

## Configuration

Confirmed:

- `SHELLY_AUTH_KEY` and `SHELLY_SERVER_URI` are required; integer variables reject only non-integer text (`exporter/config.py:7-42`).
- Timeout, polling interval, and port accept zero, negative, and out-of-range integers; server URI and log level have no shape or membership validation.

Recommended:

- Require a non-empty key, an absolute HTTPS server URL with a host and without embedded credentials, query, or fragment, request timeout greater than zero, polling interval of at least one second, port `1..65535`, and a recognized logging level.
- Fail before starting the metrics server and keep validation messages free of credential values.

## Shelly communication and failures

Confirmed:

- Each poll calls `GET /device/all_status` once with `auth_key`, `show_info=true`, `no_shared=true`, and a configured timeout (`exporter/shelly_client.py:28-42`).
- HTTP 401/403 and 429 have dedicated exceptions; other HTTP, transport, JSON, shape, and unexpected errors reach broader handlers (`exporter/shelly_client.py:44-63`, `exporter/metrics.py:178-213`).
- Every failure sets `shelly_up` to zero and increments the error counter, then waits the fixed polling interval; prior device samples and the last-success timestamp remain.
- The design records an account-wide limit of one request per second (`docs/DESIGN.md:19-36`).

Recommended:

- Keep one attempt per poll cycle, classify all expected failure families, and use the configured interval for the next attempt; for HTTP 429, extend that delay when a valid `Retry-After` is longer.
- Keep prior samples on failure and use `shelly_up`, error count, and last-success age to expose staleness.

## Credential safety and logging

Confirmed:

- The authorization key is sent as a query parameter (`exporter/shelly_client.py:37-42`).
- A local reproduction with a fake marker proved that `requests` exception text can contain the complete prepared query URL. The generic `log.exception` request handler can therefore contradict the documentation claim that the key is never logged (`exporter/metrics.py:204-207`, `docs/DESIGN.md:59-60`).
- Tests already monkeypatch HTTP and use fake keys (`tests/test_shelly_client.py`).

Recommended:

- Sanitize logged exceptions and never log complete URLs, parameters, request/response objects, configuration objects, response bodies that echo authentication, or traceback text containing prepared requests.
- Add captured-log regression tests containing unmistakable fake secrets and URLs.

## Prometheus behavior

Confirmed:

- Metrics are module-global collectors in the default registry (`exporter/metrics.py:19-82`).
- Gen1 and Gen2+ data deliberately share `shelly_relay_*` names; identity comes from `_dev_info.id`, not the outer response key (`exporter/metrics.py:101-169`, `docs/DESIGN.md:62-82`).
- Missing or non-numeric fields are skipped. No collector children are removed when fields or devices disappear (`exporter/metrics.py:85-175`).
- A local two-update reproduction confirmed that a device-labelled sample remains after a later successful empty-device response.

Recommended:

- Freeze existing names, label keys, units, and generation mappings in contract tests.
- On a successful complete response, remove labelled children not present in that response, including obsolete metadata label combinations. Do not remove them after a failed poll.

## Tests

Confirmed:

- The 23 tests pass locally on Python 3.14.7; total coverage is 76 percent. CI and the container target Python 3.12.
- Client tests use mocked HTTP, but poll-loop, entrypoint, logging-redaction, stale-series removal, graceful termination, and image behavior are not covered.
- Metric tests mutate shared global collectors and can inherit series and counter values from earlier tests (`tests/test_metrics.py`).

Recommended:

- Make collector registry, fetch function, clock, and waiting behavior replaceable at test boundaries.
- Enforce deterministic no-network tests on Python 3.12 with at least 85 percent total coverage.

## Container

Confirmed:

- The image uses Python 3.12 slim, explicitly copies `requirements.txt` and `exporter/`, sets unbuffered/no-bytecode behavior, and runs as the no-home numeric user `1000:1000` (`Dockerfile`).
- No `.dockerignore` exists. Gitignored `.env`, `.venv/`, `data/`, Git metadata, caches, and BMAD material therefore enter the Docker build context even though the current Dockerfile does not copy them into a layer.
- CI builds the image but does not start or inspect it (`.github/workflows/docker-build.yaml:46-86`).

Recommended:

- Exclude secrets, VCS data, virtual environments, caches, tests, coverage output, planning artifacts, and local data from the build context while retaining explicit runtime copies.
- Smoke-test non-root identity, `/metrics`, absence of fake credentials in logs/image history, and timely SIGTERM exit.

## CI, dependencies, and releases

Confirmed:

- CI on Python 3.12 installs `requirements.txt`, compiles the package, runs tests, and builds an image; pull requests build without pushing, while main and `v*` tags can publish (`.github/workflows/docker-build.yaml`).
- CI has no lint, coverage threshold, dependency vulnerability check, container smoke test, image vulnerability check, or project-version/tag consistency check.
- Runtime dependencies are duplicated in `pyproject.toml` and `requirements.txt`; there is no lockfile. The project version is `0.1.0`, and the repository has no version tags.

Recommended:

- Gate pull requests on formatting/lint, tests, coverage, dependency audit, image build, image scan, and a fake-credential smoke test.
- Add a release-promotion operation that accepts `patch`, `minor`, or `major`, derives the next version from `pyproject.toml`, validates before creating an annotated matching `vX.Y.Z` tag, and never pushes implicitly.
- Keep this milestone on the `0.x` line. Publish immutable version and commit image tags, update `latest` only from the default branch, and provide release notes describing compatibility and operator impact.

## Documentation

Confirmed:

- README configuration and metric inventories broadly match the source.
- README says pull requests run validation only, while the workflow also builds an unpushed image (`README.md:86-93`, `.github/workflows/docker-build.yaml:46-86`).
- The design rollout checklist marks exporter publication as incomplete while its note says the image is already published (`docs/DESIGN.md:88-101`).
- README and design documentation devote substantial space to the author's sibling `homelabs` repository, Vault paths, cluster resources, and rollout state.

Recommended:

- Make the primary documentation standalone-first: explain generic local, container, Prometheus, and deployment use without requiring personal repositories, Vault paths, or cluster conventions.
- Reconcile current-state contradictions and document validation failures, retry timing, sample staleness, safe secret injection, container verification, release promotion, and rollback.
- Retain at most a concise optional link to `homelabs` as an example of a real production deployment; no sibling-repository change is part of this milestone.
