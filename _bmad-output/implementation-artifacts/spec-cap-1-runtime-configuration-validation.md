---
title: 'CAP-1 Runtime Configuration Validation'
type: 'feature'
created: '2026-09-04'
status: 'done'
review_loop_iteration: 1
baseline_commit: '2a675889a572141407a58541dab26022d6d3f44f'
context:
  - '{project-root}/AGENTS.md'
  - '{project-root}/_bmad-output/specs/spec-production-readiness/SPEC.md'
  - '{project-root}/_bmad-output/specs/spec-production-readiness/acceptance-criteria.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Environment configuration currently rejects missing required values and non-integer numeric text, but accepts unusable URLs, unsafe bounds, whitespace-only credentials, and arbitrary log levels. Invalid startup must fail before binding the metrics port or contacting Shelly Cloud, without reflecting secret-bearing input.

**Approach:** Add strict, standard-library validation to environment-driven configuration while preserving valid defaults and normalized output. Cover boundary and startup-order behavior with focused tests and document the accepted values.

## Boundaries & Constraints

**Always:** Preserve defaults (`10`, `30`, `9100`, `INFO`), `RuntimeError` failure type, case-insensitive log input, trailing-slash normalization, direct `ShellyConfig(...)` construction, Python 3.12 compatibility, metric identity, and Shelly request behavior. Keep all validation errors value-free because rejected URLs can contain credentials.

**Ask First:** Expanding accepted URLs beyond an HTTPS origin, accepting log aliases or `NOTSET`, changing timeout from integer to float, adding dependencies, or validating direct dataclass construction.

**Never:** Log or echo credentials or rejected URI text; bind a port, start polling, or contact the network after invalid configuration; change metrics, polling, retry behavior, Docker, CI, release logic, or unrelated documentation in this story.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Defaults | Required key and HTTPS origin; optional variables unset | `10`, `30`, `9100`, `INFO` | N/A |
| Credential | Missing, empty, or whitespace-only key | Startup rejected; valid key preserved unchanged | Name variable, never value |
| Server origin | HTTPS host, optional valid port and single trailing `/` | Accepted; trailing `/` removed | N/A |
| Unsafe server | Other scheme, userinfo, query, fragment, non-root path, whitespace/control, malformed host or port | Startup rejected | Name rule, never URI |
| Numeric bounds | Timeout and poll `>=1`; port `1..65535` | Accepted at boundaries | Reject non-integer/out-of-range without raw value |
| Log level | Canonical five levels in any case | Normalize uppercase | Reject empty, alias, or unknown without raw value |
| Invalid startup | Any invalid environment configuration | Raise before metrics bind or poll | Non-zero process semantics via uncaught `RuntimeError` |

</frozen-after-approval>

## Code Map

- `exporter/config.py:7-43` — `_int_env` and `ShellyConfig.from_env()` are the complete implementation surface; validation belongs here before the immutable configuration is returned.
- `exporter/metrics.py:216-227` — `main()` already resolves configuration before logging setup, `start_http_server`, and `poll_loop`; retain this ordering.
- `tests/test_shelly_client.py:14-62` — existing environment/default/override tests and monkeypatch pattern; extend with validation tables and startup side-effect spies.
- `README.md:30-42` — runtime configuration contract and preserved defaults; document HTTPS-origin, numeric-bound, and accepted-level rules.
- `_bmad-output/specs/spec-production-readiness/acceptance-criteria.md` — AC-2.1 through AC-2.5 are the authoritative system behaviors; read-only.

## Tasks & Acceptance

**Execution:**
- [x] `exporter/config.py` — validate required values, HTTPS base origin, numeric ranges, and canonical log levels using the standard library; return normalized safe configuration.
- [x] `tests/test_shelly_client.py` — add parameterized valid, invalid, boundary, secret-redaction, and pre-side-effect startup tests while keeping HTTP mocked.
- [x] `README.md` — document accepted configuration shapes and fail-fast startup without personal credential instructions.

**Acceptance Criteria:**
- Given missing, empty, or whitespace-only auth, when configuration loads, then it raises a value-free `RuntimeError` before any bind or poll.
- Given a valid HTTPS origin with optional valid port and optional single trailing slash, when configuration loads, then it returns the normalized origin and unchanged valid key.
- Given an unsafe or malformed server URI, when configuration loads, then it raises a value-free `RuntimeError` that does not contain planted credentials or URI text.
- Given timeout, polling, and port boundary values, when configuration loads, then values within `>0`, `>=1`, and `1..65535` respectively pass and all other integer or non-integer values fail safely.
- Given `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` in any case, when configuration loads, then it normalizes uppercase; empty, aliases, and unknown levels fail safely.
- Given invalid configuration, when `main()` starts, then neither `start_http_server` nor `poll_loop` is invoked and the exception remains uncaught for non-zero process exit.
- Given the completed change, when existing tests run, then defaults, direct construction, client behavior, metrics, and request-count compatibility remain unchanged.

## Spec Change Log

## Design Notes

Use `urllib.parse.urlsplit` as validation, not normalization: reject whitespace/control characters and raw `?`/`#` delimiters first; then require HTTPS, a hostname, no userinfo/query/fragment, and path `""` or `"/"`. Access parsed hostname and port inside the safe-error boundary because malformed brackets and ports raise `ValueError`. Accept custom valid ports, localhost, and IPv6; never include the input in an error.

Keep environment validation in `from_env()` rather than `__post_init__`, preserving direct construction as the existing unit-test seam. The canonical operational levels are `DEBUG`, `INFO`, `WARNING`, `ERROR`, and `CRITICAL`; aliases and `NOTSET` are not accepted.

## Verification

**Commands:**
- `.venv/bin/pytest tests/test_shelly_client.py -v` — focused configuration and client tests pass without network access.
- `make test` — complete repository suite passes.
- `make compile` — Python package compiles successfully.

## Review

The mandatory blind, edge-case, and verification-gap reviews completed. The
implementation was tightened to reject malformed hostnames and backslashes in
server origins, and the subprocess test now derives the repository root from
its own location. Additional suggestions that expand this story (hostname
canonicalization, credential character policy, socket assertions, and broader
startup permutations) are deferred to later production-readiness stories.
