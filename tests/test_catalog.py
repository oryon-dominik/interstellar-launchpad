"""The catalog answers where a thing lies, which group it serves and which profiles carry it."""

import json

import pytest

from launchpad import catalog, cli

FILES = {
    "manifests/scoop-packages.json": {"scoops": [{"package": "git", "group": "keep-the-logbook", "os": None}]},
    "manifests/cargo-tools.json": {
        "crates": [
            {"crate": "ripgrep", "group": "scan-the-hold", "os": None},
            {"crate": "rustscan", "group": "probe-defenses", "os": "posix"},
        ]
    },
    "manifests/bun-tools.json": {"packages": []},
    "manifests/uv-tools.json": {"tools": [{"tool": "ruff", "group": "fuel-python"}]},
}
PROFILES = """
[groups]
keep-the-logbook = "version control"
scan-the-hold = "files"
probe-defenses = "offensive security"
fuel-python = "python"

[profiles.customer]
groups = ["keep-the-logbook", "scan-the-hold", "fuel-python"]
"""


@pytest.fixture
def hold() -> catalog.Catalog:
    """A small catalog read from stand-in files, no package needed."""
    return catalog.load(lambda path: PROFILES if path == "profiles.toml" else json.dumps(FILES[path]))


def test_every_manifest_lands_in_the_catalog_with_its_lane(hold):
    assert [(entry.name, entry.manifest) for entry in hold.entries] == [
        ("git", "scoop"),
        ("ripgrep", "cargo"),
        ("rustscan", "cargo"),
        ("ruff", "uv"),
    ]


def test_an_exact_name_wins_over_names_that_contain_it(hold):
    assert [entry.name for entry in catalog.find(hold, "GIT")] == ["git"]
    assert [entry.name for entry in catalog.find(hold, "rust")] == ["rustscan"]


def test_a_group_names_the_profiles_that_carry_it(hold):
    assert catalog.profiles_of(hold, "scan-the-hold") == ("customer",)
    assert catalog.profiles_of(hold, "probe-defenses") == ()


def test_a_profile_gets_exactly_the_entries_of_its_groups(hold):
    names = [entry.name for entry in catalog.in_groups(hold, hold.profiles["customer"])]
    assert names == ["git", "ripgrep", "ruff"]


def test_the_shipped_catalog_loads_from_the_package():
    shipped = catalog.load()
    assert shipped.entries
    assert "customer" in shipped.profiles


def test_the_command_shows_lane_group_profile_and_system(monkeypatch, hold):
    monkeypatch.setattr(catalog, "load", lambda: hold)
    lines = []
    assert cli.show_manifest(["rustscan"], say=lines.append) == 0
    assert lines[0].split() == ["rustscan", "cargo", "probe-defenses", "-", "(posix", "only)"]


@pytest.mark.parametrize("arguments", [["nothing-like-it"], ["--group", "unknown"], ["--profile", "unknown"]])
def test_the_command_fails_on_what_it_does_not_know(monkeypatch, hold, arguments):
    monkeypatch.setattr(catalog, "load", lambda: hold)
    assert cli.show_manifest(arguments, say=lambda line: None) == 1


def test_launchpad_hands_manifest_to_its_own_command(monkeypatch):
    seen = []
    monkeypatch.setattr(cli, "show_manifest", lambda argv: seen.append(list(argv)) or 0)
    assert cli.main(["manifest", "git"]) == 0
    assert seen == [["git"]]
