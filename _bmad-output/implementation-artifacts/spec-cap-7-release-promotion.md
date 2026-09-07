---
title: 'CAP-7 Release Promotion'
type: 'feature'
created: '2026-09-07'
status: 'done'
review_loop_iteration: 1
context:
  - '{project-root}/AGENTS.md'
  - '{project-root}/_bmad-output/specs/spec-production-readiness/SPEC.md'
  - '{project-root}/_bmad-output/specs/spec-production-readiness/acceptance-criteria.md'
baseline_commit: 'bbdcdd337c9e967327e54c4fa60d019c9588b030'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The project has version metadata and CI image publication, but no safe, repeatable operation for promoting a 0.x patch, minor, or eventual major release.

**Approach:** Add a small local release command that calculates the next version from `pyproject.toml`, runs required validation before mutation, updates metadata, commits it, and creates a matching annotated tag without pushing.

## Boundaries & Constraints

**Always:** Accept exactly `patch`, `minor`, or `major`; calculate SemVer (`0.1.0` → `0.1.1`, `0.2.0`, or `1.0.0`); use `pyproject.toml` as the sole version source; require a clean tree including untracked files; refuse existing `vX.Y.Z` tags; preserve Python 3.12 compatibility; keep release operations local and credential-free.

**Ask First:** Changing the version source, adopting a third-party release dependency, changing commit/tag messages, or making the command push or publish automatically.

**Never:** Modify application runtime behavior, create tags during normal tests, push to a remote, overwrite an existing tag, or silently clean unrelated working-tree changes.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Promotion | Current `X.Y.Z`, `patch\|minor\|major` | Correct next version | Unsupported value fails before mutation |
| Dirty tree | Tracked or untracked change | No file, commit, or tag mutation | Explain clean-tree requirement |
| Existing tag | Target `vX.Y.Z` already exists | No mutation | Refuse overwrite |
| Failed gates | Test/compile command fails | Version remains unchanged; no release commit/tag | Report failing gate |
| Success | Clean tree, gates pass, target absent | Update version, commit, annotated tag | Never push |

</frozen-after-approval>

## Code Map

- `pyproject.toml:7` — authoritative project version (`0.1.0`).
- `Makefile:1-55` — existing `test` and `compile` gates; add a release entry point without changing their semantics.
- `.github/workflows/docker-build.yaml:1-86` — tags `v*` trigger image publication; release tags must match metadata.
- `README.md:80-103` — current CI/image guidance; add standalone release, rollback, and tag instructions.
- `tests/` — pytest suite; release tests should use temporary Git fixtures or mocked subprocesses and never mutate this repository.
- `_bmad-output/specs/spec-production-readiness/acceptance-criteria.md:49-58` — authoritative AC-7.1 through AC-7.8.

## Tasks & Acceptance

**Execution:**
- [x] `scripts/release.py` — implement pure promotion calculation and guarded local release orchestration.
- [x] `Makefile` — expose `make release PROMOTION=patch|minor|major`.
- [x] `tests/test_release.py` — cover increments, invalid input, dirty trees, existing tags, failed gates, annotated tags, and no-push behavior in isolated fixtures.
- [x] `README.md` — document 0.x patch/minor usage, major-to-1.0 policy, local-tag boundary, publication, release notes, and rollback.

**Acceptance Criteria:**
- Given a supported promotion, when the command runs from a clean tree and gates pass, then metadata, release commit, and annotated matching tag agree.
- Given an unsupported promotion, dirty tree, or existing target tag, when promotion starts, then it fails before mutation.
- Given a failed validation gate, when promotion starts, then version metadata, commits, and tags remain unchanged.
- Given any successful promotion, when inspecting subprocesses and remotes, then no push or credential-bearing operation occurred.
- Given the project is pre-1.0, when documented guidance is followed, then patch/minor are normal and major explicitly yields `1.0.0`.

## Design Notes

Keep the calculator pure and use standard-library TOML/text handling appropriate to the existing Python floor. Treat Git as an external boundary behind subprocess helpers so tests can use temporary repositories. A failed post-edit commit/tag operation should restore the version file where practical, but must never reset unrelated user changes.

## Verification

**Commands:**
- `make test` — complete suite passes.
- `make compile` — package compiles.
- `python scripts/release.py --help` — documents supported promotion values without mutating the tree.

## Review

The mandatory blind, edge-case, and verification-gap reviews completed. The
release entry point now quotes the Make promotion argument, rechecks the tree
after validation, isolates version staging, restores pre-commit failures, and
preserves a consistent version commit when tag creation fails. Existing-tag
tests also assert that no mutating Git command runs. Broader parser hardening,
ignored-file policy, and post-tag verification are deferred because they are
not required to safely ship this small local promotion workflow.

## Suggested Review Order

**Release transaction**

- Pure promotion and guarded version/tag transaction.
  [`release.py:18`](../../scripts/release.py#L18)

- Validation gates run before metadata mutation.
  [`release.py:47`](../../scripts/release.py#L47)

- Commit and tag failure handling preserves consistency.
  [`release.py:68`](../../scripts/release.py#L68)

**Project integration**

- Public Make entry point restricts promotion argument handling.
  [`Makefile:46`](../../Makefile#L46)

- Operator release and rollback procedure.
  [`README.md:87`](../../README.md#L87)

**Verification**

- Isolated tests cover SemVer, Git guards, gates, and no-push behavior.
  [`test_release.py:10`](../../tests/test_release.py#L10)
