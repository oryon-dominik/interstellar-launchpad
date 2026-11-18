"""The install manifests travel with launchpad and carry nothing that points inside the fleet."""

import json
import re
import tomllib
from importlib import resources

import pytest

# Each manifest and the key of its entry list.
MANIFESTS = {
    "scoop-packages.json": "scoops",
    "cargo-tools.json": "crates",
    "bun-tools.json": "packages",
    "uv-tools.json": "tools",
}
# Mission identifiers, machine names and paths into the dotfiles stay out of a file that may go public.
INTERNAL = re.compile(r"\b(directive|anomaly|radar|blueprint|job)-[0-9a-f]{6}\b|APOLLON|SERENITY|install/|common/")


@pytest.mark.parametrize("name", MANIFESTS)
def test_every_manifest_lies_in_the_package_and_parses(name):
    text = (resources.files("launchpad") / "manifests" / name).read_text(encoding="utf-8")
    assert json.loads(text)


@pytest.mark.parametrize("name", MANIFESTS)
def test_no_manifest_names_missions_machines_or_dotfiles_paths(name):
    text = (resources.files("launchpad") / "manifests" / name).read_text(encoding="utf-8")
    assert INTERNAL.findall(text) == []


def profiles() -> dict:
    return tomllib.loads((resources.files("launchpad") / "profiles.toml").read_text(encoding="utf-8"))


def groups_in_manifests() -> list[str]:
    return [
        entry.get("group")
        for name, key in MANIFESTS.items()
        for entry in json.loads((resources.files("launchpad") / "manifests" / name).read_text(encoding="utf-8"))[key]
    ]


def test_every_manifest_entry_carries_a_declared_group():
    declared = set(profiles()["groups"])
    assert [group for group in groups_in_manifests() if group not in declared] == []


def test_every_declared_group_holds_at_least_one_entry():
    assert set(profiles()["groups"]) - set(groups_in_manifests()) == set()


def test_profiles_assign_only_declared_groups():
    config = profiles()
    for profile in config["profiles"].values():
        assert set(profile["groups"]) <= set(config["groups"])


def test_a_customer_machine_gets_no_offensive_tools_and_no_remote_control():
    assert {"probe-defenses", "take-remote-control"}.isdisjoint(profiles()["profiles"]["customer"]["groups"])


def test_a_crew_machine_gets_everything_a_customer_machine_gets():
    crew = profiles()["profiles"]["crew"]["groups"]
    assert set(profiles()["profiles"]["customer"]["groups"]) - set(crew) == set()


def test_offensive_tools_and_remote_control_reach_a_crew_machine_only_when_asked_for():
    assert {"probe-defenses", "take-remote-control"}.isdisjoint(profiles()["profiles"]["crew"]["groups"])


def test_the_rust_toolchain_and_the_crates_that_install_crates_form_a_group_of_their_own():
    entries = [
        entry
        for name, key in MANIFESTS.items()
        for entry in json.loads((resources.files("launchpad") / "manifests" / name).read_text(encoding="utf-8"))[key]
    ]
    rustup = next(entry["group"] for entry in entries if entry.get("package") == "rustup")
    members = [entry.get("package") or entry.get("crate") for entry in entries if entry["group"] == rustup]
    assert members == ["rustup", *(entry["crate"] for entry in entries if entry.get("bootstrap"))]
