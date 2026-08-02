"""Checks on manifest.json that hassfest also enforces.

hassfest only runs in CI, so a malformed manifest is not visible locally until a
push fails. These mirror the rules cheaply enough to catch it before committing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

MANIFEST = json.loads(
    (
        Path(__file__).resolve().parent.parent
        / "custom_components"
        / "adaptive_cover"
        / "manifest.json"
    ).read_text(encoding="utf-8")
)


def test_keys_are_sorted_the_way_hassfest_wants():
    """domain, name, then every remaining key in alphabetical order."""
    keys = list(MANIFEST)
    rest = sorted(k for k in keys if k not in ("domain", "name"))
    assert keys == ["domain", "name", *rest]


def test_required_keys_present():
    for key in ("domain", "name", "documentation", "codeowners", "version"):
        assert MANIFEST.get(key), f"missing or empty manifest key: {key}"


def test_version_is_three_numeric_parts():
    parts = MANIFEST["version"].split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)


@pytest.mark.parametrize("key", ["dependencies", "after_dependencies"])
def test_dependency_lists_are_sorted_and_unique(key):
    values = MANIFEST.get(key, [])
    assert values == sorted(values)
    assert len(values) == len(set(values))


def test_only_sun_is_a_hard_dependency():
    """The other domains are only read from, which needs no hard dependency."""
    assert MANIFEST["dependencies"] == ["sun"]
