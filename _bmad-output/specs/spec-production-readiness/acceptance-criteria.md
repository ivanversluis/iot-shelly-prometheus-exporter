# Story Acceptance Criteria

## Story 1 — Isolate automated test state

- **AC-1.1:** Tests can create exporter metrics in an isolated `CollectorRegistry`; repeated construction and arbitrary test order do not produce duplicate-timeseries errors or inherit samples.
- **AC-1.2:** A test can execute exactly one poll attempt with fake fetch, clock, and wait behavior; it performs no real sleep or network call.
- **AC-1.3:** Existing Gen1, Gen2+, missing-field, configuration, authentication, rate-limit, and response-shape behavior remains covered and passing.

## Story 2 — Validate runtime configuration

- **AC-2.1:** Startup rejects a missing or empty authorization key without echoing it.
- **AC-2.2:** Server URI accepts an absolute HTTPS URL with a host and optional trailing slash; it rejects other schemes, embedded credentials, query strings, fragments, and missing hosts.
- **AC-2.3:** Request timeout must be greater than zero, polling interval must be an integer of at least one second, and metrics port must be within `1..65535`.
- **AC-2.4:** Log level accepts documented standard levels case-insensitively and rejects unknown values.
- **AC-2.5:** Invalid configuration exits non-zero before binding the metrics port or contacting Shelly Cloud; valid documented defaults remain unchanged.

## Story 3 — Harden failures and credential-safe diagnostics

- **AC-3.1:** A successful poll still issues exactly one `GET /device/all_status` with `show_info=true`, `no_shared=true`, the configured timeout, and no per-device calls.
- **AC-3.2:** Authentication, rate-limit, timeout, connection, other HTTP, malformed JSON, invalid response shape, and unexpected processing failures each set `shelly_up` to zero and increment `shelly_scrape_errors_total` once without terminating the process.
- **AC-3.3:** No failure triggers a retry within the same poll cycle. The next attempt waits at least `POLL_INTERVAL`; a valid longer HTTP `Retry-After` controls the 429 delay, while malformed or shorter values do not shorten it.
- **AC-3.4:** A successful poll sets `shelly_up` to one and updates both attempt and success timestamps; a failed poll updates only the attempt timestamp and leaves last-success unchanged.
- **AC-3.5:** Captured logs for every failure contain an actionable category but contain neither a fake authorization key nor a full auth-bearing URL, request parameters, response body, configuration representation, or unsafe exception text.

## Story 4 — Make metric lifecycle accurate and compatible

- **AC-4.1:** A contract test asserts every existing public metric name, label-key set, unit suffix, and the Gen1/Gen2+ shared relay mapping.
- **AC-4.2:** All exported device labels continue to use `_dev_info.id`; outer response-map keys never become `device_id` values.
- **AC-4.3:** After a successful complete response, devices, components, fields, and obsolete `code`/`gen` metadata combinations absent from that response are absent from the next Prometheus exposition.
- **AC-4.4:** Missing and non-numeric values are not emitted as zero. If previously present, their old labelled child is retired after the successful response.
- **AC-4.5:** Failed polls do not retire last-known device samples; failure and data age remain observable through `shelly_up`, `shelly_scrape_errors_total`, and the success timestamp.
- **AC-4.6:** README and design documentation explicitly describe the successful-removal and failed-retention semantics before release.

## Story 5 — Harden the container boundary

- **AC-5.1:** `.dockerignore` excludes `.env`, `.git`, `.venv`, local data, caches, coverage output, tests, and planning artifacts not needed at runtime.
- **AC-5.2:** The image contains only required runtime application and dependency content and does not contain a planted fake secret.
- **AC-5.3:** The running container reports UID/GID `1000:1000`, requires neither root nor a writable home, and serves `/metrics` on the configured port using fake unreachable Shelly settings.
- **AC-5.4:** Sending SIGTERM stops the container without a traceback and within ten seconds.

## Story 6 — Upgrade CI quality and security gates

- **AC-6.1:** Pull requests run compile, lint/format verification, the Python 3.12 test suite, and coverage with a minimum total of 85 percent.
- **AC-6.2:** Pull requests audit Python dependencies for known vulnerabilities under a documented severity/failure policy.
- **AC-6.3:** Pull requests build the container, scan it under a documented severity/failure policy, and run the non-root fake-credential smoke checks from AC-5.
- **AC-6.4:** Pull-request jobs never authenticate to or push to GHCR; publication remains limited to authorized default-branch and version-tag events.
- **AC-6.5:** A dependency change that leaves `pyproject.toml` and `requirements.txt` inconsistent fails CI.

## Story 7 — Establish release and version discipline

- **AC-7.1:** Release promotion accepts exactly `patch`, `minor`, or `major`; unsupported or missing promotion types fail without changing version metadata or creating a tag.
- **AC-7.2:** From version `X.Y.Z`, patch produces `X.Y.(Z+1)`, minor produces `X.(Y+1).0`, and major produces `(X+1).0.0`. Thus `0.1.0` can promote to `0.1.1`, `0.2.0`, or `1.0.0` respectively.
- **AC-7.3:** Promotion requires a clean working tree, calculates from the version in `pyproject.toml`, and refuses to overwrite an existing release tag.
- **AC-7.4:** All AC-6 validation gates pass before promotion creates a version commit and annotated `vX.Y.Z` Git tag; the tag points to the commit containing the matching `pyproject.toml` version.
- **AC-7.5:** Promotion creates no version commit or tag when validation fails and never pushes a commit or tag to a remote implicitly.
- **AC-7.6:** A successful published release provides immutable version and commit-SHA image tags; `latest` is updated only from the default branch according to the documented policy.
- **AC-7.7:** Release notes state metric compatibility, configuration changes, operator actions, and known limitations; verification and rollback use an immutable image tag without credential disclosure.
- **AC-7.8:** This production-readiness milestone uses patch or minor promotion and remains `0.x`; major promotion is available for a later explicit `1.0.0` decision.

## Story 8 — Reconcile operator documentation

- **AC-8.1:** README accurately states that pull requests validate and build without pushing and describes every supported configuration validation rule.
- **AC-8.2:** Documentation explains failure categories, retry timing, last-known sample retention on failed polls, sample retirement on successful polls, and the metrics operators use to detect failure and age.
- **AC-8.3:** Local and container examples do not place real credentials in committed files, captured command output, image layers, or Docker build context.
- **AC-8.4:** A new user can run the exporter locally or in a container and configure Prometheus using only this repository's documentation and generic environment-secret guidance.
- **AC-8.5:** Primary setup and operations guidance does not require or assume the author's `homelabs` repository, Vault hierarchy, cluster names, manifests, dashboards, or rollout state.
- **AC-8.6:** Personal production usage is limited to a concise optional reference or link to `homelabs`; no personal deployment checklist is presented as project setup.
- **AC-8.7:** Documentation names the patch/minor/major promotion behavior, local-tag safety boundary, publication process, rollback procedure, and exact local commands that mirror CI gates.
