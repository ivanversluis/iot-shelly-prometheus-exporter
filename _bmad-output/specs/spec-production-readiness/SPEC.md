---
id: SPEC-production-readiness
companions:
  - evidence.md
  - acceptance-criteria.md
sources: []
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability — consult them only if you need narrative rationale or prose color this contract intentionally omits.

# Shelly Exporter Production Readiness

## Why

The existing exporter provides useful Shelly Cloud metrics and passes its current tests, but production operation still depends on permissive configuration, potentially credential-bearing exception text, incomplete failure-path coverage, persistent stale samples, an unrestricted Docker build context, and release checks that do not yet prove an image is safe and reproducible. This milestone gives the maintainer a small, testable hardening boundary without redesigning the exporter or expanding its device feature set.

## Capabilities

- **CAP-1**
  - **intent:** An operator receives an immediate, credential-safe startup error when runtime configuration is unusable.
  - **success:** Automated tests accept every documented valid setting and reject missing credentials or invalid endpoint shape, timeout, polling interval, port, and log level according to AC-2.

- **CAP-2**
  - **intent:** The exporter reports Shelly Cloud failures accurately and schedules later attempts without crashing or violating the account rate limit.
  - **success:** Deterministic tests cover authentication, rate limiting, timeout, connection, HTTP, JSON, and response-shape failures and prove the state and scheduling rules in AC-3.

- **CAP-3**
  - **intent:** Operators can diagnose failures without exposing the Shelly authorization key or other auth-bearing request data.
  - **success:** Captured logs and raised public-facing errors contain failure category and safe endpoint context but never the fake secrets or auth-bearing data enumerated in AC-3.

- **CAP-4**
  - **intent:** Prometheus consumers retain the published query contract while samples accurately reflect the latest successful complete Shelly response.
  - **success:** Contract tests preserve all existing metric identities and generation mappings, remove vanished samples only after successful scrapes, and preserve last-known samples on failed polls according to AC-4.

- **CAP-5**
  - **intent:** Maintainers can change configuration, polling, error handling, and metrics with deterministic automated regression protection.
  - **success:** The suite performs no live network calls or sleeps, has isolated collector state, passes on Python 3.12, and reports at least 85 percent total coverage according to AC-1 and AC-6.

- **CAP-6**
  - **intent:** The published container excludes local secrets and development material and operates correctly as the established non-root user.
  - **success:** Build-context checks, image inspection, startup probing, and termination checks satisfy AC-5 without using real credentials.

- **CAP-7**
  - **intent:** A maintainer can promote a patch, minor, or major release whose project metadata and annotated Git tag agree, after all production gates pass.
  - **success:** CI enforces AC-6 on pull requests, and the release operation calculates the requested SemVer increment, validates it, creates the matching local tag without implicitly pushing, and satisfies AC-7.

- **CAP-8**
  - **intent:** Any maintainer or operator can configure, validate, release, deploy, and troubleshoot the exporter without access to the author's personal infrastructure.
  - **success:** Standalone-first documentation passes AC-8, no longer contradicts CI, and limits the personal `homelabs` deployment to an optional reference.

## Constraints

- Preserve published `shelly_*` names, label keys and meanings, unit suffixes, `_dev_info.id` device identity, and the shared Gen1/Gen2+ `shelly_relay_*` query surface unless an explicit migration is approved.
- Use one `GET /device/all_status` request with `show_info=true` and `no_shared=true` per poll cycle; do not add per-device fan-out or intra-cycle retries, and respect the account-wide one-request-per-second limit.
- Never use real Shelly or Vault credentials in automated tests, fixtures, examples, logs, committed files, or Docker build contexts.
- Retain Python 3.12 compatibility and the container's numeric non-root `1000:1000`, no-home runtime.
- Keep runtime dependencies synchronized between `pyproject.toml` and `requirements.txt`; Make, CI, and Docker consume `requirements.txt`.
- Keep the exporter, build, CI, release flow, and primary documentation independent of the author's `homelabs` repository, cluster, Vault paths, dashboards, and deployment configuration.
- Keep the implementation proportionate to a single-account exporter; prefer standard-library or existing-dependency solutions unless a new dependency removes more risk than it adds.

## Non-goals

- Add support for new Shelly components, including the existing cover-position TODO.
- Replace classic `auth_key` authentication with OAuth or communicate directly with LAN devices.
- Add a web UI, persistent database, shared cache, high-availability coordination, or distributed rate limiter.
- Build or maintain deployment-specific dashboards, secrets, network policies, or Kubernetes topology inside this repository.
- Guarantee availability of the third-party Shelly Cloud service.

## Success signal

A pull request can demonstrate every acceptance criterion without a real Shelly credential, and a version-consistent image built from the accepted commit serves the unchanged metric contract as UID/GID 1000, survives representative Cloud failures without leaking the fake key, and terminates cleanly. A maintainer can then select patch, minor, or major promotion and obtain a matching local version commit and annotated Git tag, while standalone documentation lets an operator deploy and diagnose without reading source code or using the author's infrastructure.

## Assumptions

- One exporter instance serves one Shelly account; multi-instance coordination is unnecessary for this milestone.
- An 85 percent total coverage floor is proportionate once poll-loop and failure-path tests are added.
- The production-readiness milestone remains pre-1.0 and therefore uses patch or minor promotion; major promotion is implemented now for a later `1.0.0` release.
