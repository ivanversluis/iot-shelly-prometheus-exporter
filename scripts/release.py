#!/usr/bin/env python3
"""Promote the project version and create a local annotated release tag."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
VERSION_RE = re.compile(r'(?m)^(version\s*=\s*["\'])(\d+)\.(\d+)\.(\d+)(["\'])\s*$')
PROMOTIONS = ("patch", "minor", "major")


def next_version(version: str, promotion: str) -> str:
    """Return the SemVer result for a supported promotion."""
    if promotion not in PROMOTIONS:
        raise ValueError("promotion must be exactly patch, minor, or major")
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        raise ValueError(f"unsupported project version: {version!r}")
    major, minor, patch = (int(part) for part in match.groups())
    if promotion == "patch":
        patch += 1
    elif promotion == "minor":
        minor, patch = minor + 1, 0
    else:
        major, minor, patch = major + 1, 0, 0
    return f"{major}.{minor}.{patch}"


def _run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, check=check, text=True, capture_output=True)


def current_version() -> str:
    text = PYPROJECT.read_text(encoding="utf-8")
    match = VERSION_RE.search(text)
    if not match:
        raise RuntimeError("could not find a SemVer version in pyproject.toml")
    return ".".join(match.group(index) for index in (2, 3, 4))


def promote(promotion: str) -> str:
    """Run gates, update metadata, commit it, and create an annotated local tag."""
    if promotion not in PROMOTIONS:
        raise ValueError("promotion must be exactly patch, minor, or major")
    if _run("git", "status", "--porcelain").stdout:
        raise RuntimeError("working tree must be clean, including untracked files")

    old_version = current_version()
    version = next_version(old_version, promotion)
    tag = f"v{version}"
    if _run("git", "rev-parse", "--verify", f"refs/tags/{tag}", check=False).returncode == 0:
        raise RuntimeError(f"release tag {tag} already exists")

    for gate in (("make", "test"), ("make", "compile")):
        result = _run(*gate, check=False)
        if result.returncode:
            detail = (result.stderr or result.stdout).strip()
            raise RuntimeError(f"validation gate {' '.join(gate)} failed{': ' + detail if detail else ''}")
    if _run("git", "status", "--porcelain").stdout:
        raise RuntimeError("validation gates changed the working tree; release aborted")

    original = PYPROJECT.read_text(encoding="utf-8")
    updated, count = VERSION_RE.subn(lambda m: f"{m.group(1)}{version}{m.group(5)}", original, count=1)
    if count != 1:
        raise RuntimeError("could not update the project version")
    PYPROJECT.write_text(updated, encoding="utf-8")
    try:
        _run("git", "add", "--", "pyproject.toml")
        _run("git", "commit", "-m", f"chore: release {version}")
    except (OSError, subprocess.CalledProcessError):
        # Restore only the file this command changed; never reset unrelated work.
        PYPROJECT.write_text(original, encoding="utf-8")
        _run("git", "restore", "--staged", "--", "pyproject.toml", check=False)
        raise
    try:
        _run("git", "tag", "-a", tag, "-m", f"Release {version}")
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(
            f"release commit {version} was created but annotated tag {tag} failed; create the tag manually"
        ) from exc
    return version


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Promote a local release (patch, minor, or major).")
    parser.add_argument("promotion", choices=PROMOTIONS, help="SemVer promotion to apply")
    args = parser.parse_args(argv)
    try:
        version = promote(args.promotion)
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"release failed: {exc}", file=sys.stderr)
        return 1
    print(f"Created local release {version} and annotated tag v{version}; nothing was pushed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
