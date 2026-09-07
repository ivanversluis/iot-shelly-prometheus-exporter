from __future__ import annotations

import subprocess

import pytest

from scripts import release


@pytest.mark.parametrize(
    ("version", "promotion", "expected"),
    [("0.1.0", "patch", "0.1.1"), ("0.1.0", "minor", "0.2.0"), ("0.1.0", "major", "1.0.0")],
)
def test_next_version(version, promotion, expected):
    assert release.next_version(version, promotion) == expected


def test_next_version_rejects_unsupported_values():
    with pytest.raises(ValueError):
        release.next_version("0.1.0", "foo")
    with pytest.raises(ValueError):
        release.next_version("not-semver", "patch")


def test_dirty_tree_fails_before_gates_or_mutation(monkeypatch):
    calls = []

    def fake_run(*args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, " M file\n", "")

    monkeypatch.setattr(release, "_run", fake_run)
    with pytest.raises(RuntimeError, match="clean"):
        release.promote("patch")
    assert calls == [("git", "status", "--porcelain")]


def test_existing_tag_fails_before_gates(monkeypatch):
    calls = []

    def fake_run(*args, **kwargs):
        calls.append(args)
        if args[:3] == ("git", "rev-parse", "--verify"):
            return subprocess.CompletedProcess(args, 0, "commit", "")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(release, "_run", fake_run)
    with pytest.raises(RuntimeError, match="already exists"):
        release.promote("patch")
    assert not any(args[:2] == ("make", "test") for args in calls)
    assert not any(args[:2] in (("git", "add"), ("git", "commit"), ("git", "tag")) for args in calls)


def test_failed_gate_does_not_edit_metadata(monkeypatch, tmp_path):
    original_path = release.PYPROJECT
    release.PYPROJECT = tmp_path / "pyproject.toml"
    release.PYPROJECT.write_text('[project]\nversion = "0.1.0"\n', encoding="utf-8")

    def fake_run(*args, **kwargs):
        if args[:2] == ("git", "status") or args[:2] == ("git", "rev-parse"):
            return subprocess.CompletedProcess(args, 1 if args[:2] == ("git", "rev-parse") else 0, "", "")
        return subprocess.CompletedProcess(args, 1, "", "tests failed")

    monkeypatch.setattr(release, "_run", fake_run)
    try:
        with pytest.raises(RuntimeError, match="validation gate"):
            release.promote("patch")
        assert 'version = "0.1.0"' in release.PYPROJECT.read_text(encoding="utf-8")
    finally:
        release.PYPROJECT = original_path


def test_gate_mutation_aborts_before_version_edit(monkeypatch, tmp_path):
    original_path = release.PYPROJECT
    release.PYPROJECT = tmp_path / "pyproject.toml"
    release.PYPROJECT.write_text('[project]\nversion = "0.1.0"\n', encoding="utf-8")
    status_calls = 0

    def fake_run(*args, **kwargs):
        nonlocal status_calls
        if args[:2] == ("git", "status"):
            status_calls += 1
            return subprocess.CompletedProcess(args, 0, "" if status_calls == 1 else "?? generated\n", "")
        if args[:2] == ("git", "rev-parse"):
            return subprocess.CompletedProcess(args, 1, "", "")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(release, "_run", fake_run)
    try:
        with pytest.raises(RuntimeError, match="changed the working tree"):
            release.promote("patch")
        assert 'version = "0.1.0"' in release.PYPROJECT.read_text(encoding="utf-8")
    finally:
        release.PYPROJECT = original_path


def test_commit_failure_restores_file_and_unstages_only_version(monkeypatch, tmp_path):
    original_path = release.PYPROJECT
    release.PYPROJECT = tmp_path / "pyproject.toml"
    release.PYPROJECT.write_text('[project]\nversion = "0.1.0"\n', encoding="utf-8")
    calls = []

    def fake_run(*args, **kwargs):
        calls.append(args)
        if args[:2] == ("git", "rev-parse"):
            return subprocess.CompletedProcess(args, 1, "", "")
        if args[:2] == ("git", "commit"):
            raise subprocess.CalledProcessError(1, args)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(release, "_run", fake_run)
    try:
        with pytest.raises(subprocess.CalledProcessError):
            release.promote("patch")
        assert 'version = "0.1.0"' in release.PYPROJECT.read_text(encoding="utf-8")
        assert ("git", "restore", "--staged", "--", "pyproject.toml") in calls
    finally:
        release.PYPROJECT = original_path


def test_tag_failure_keeps_committed_version(monkeypatch, tmp_path):
    original_path = release.PYPROJECT
    release.PYPROJECT = tmp_path / "pyproject.toml"
    release.PYPROJECT.write_text('[project]\nversion = "0.1.0"\n', encoding="utf-8")

    def fake_run(*args, **kwargs):
        if args[:2] == ("git", "rev-parse"):
            return subprocess.CompletedProcess(args, 1, "", "")
        if args[:2] == ("git", "tag"):
            raise subprocess.CalledProcessError(1, args)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(release, "_run", fake_run)
    try:
        with pytest.raises(RuntimeError, match="release commit 0.1.1 was created"):
            release.promote("patch")
        assert 'version = "0.1.1"' in release.PYPROJECT.read_text(encoding="utf-8")
    finally:
        release.PYPROJECT = original_path


def test_success_commits_and_creates_annotated_tag(monkeypatch, tmp_path):
    original_path = release.PYPROJECT
    release.PYPROJECT = tmp_path / "pyproject.toml"
    release.PYPROJECT.write_text('[project]\nversion = "0.1.0"\n', encoding="utf-8")
    calls = []

    def fake_run(*args, **kwargs):
        calls.append(args)
        if args[:2] == ("git", "rev-parse"):
            return subprocess.CompletedProcess(args, 1, "", "")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(release, "_run", fake_run)
    try:
        assert release.promote("patch") == "0.1.1"
        assert 'version = "0.1.1"' in release.PYPROJECT.read_text(encoding="utf-8")
        assert ("git", "commit", "-m", "chore: release 0.1.1") in calls
        assert ("git", "tag", "-a", "v0.1.1", "-m", "Release 0.1.1") in calls
        assert not any(args and args[0] == "git" and "push" in args for args in calls)
    finally:
        release.PYPROJECT = original_path
