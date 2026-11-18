"""The hold: every entry of the install manifests, its purpose group and the profiles that carry it."""

import json
import tomllib
from collections.abc import Callable, Iterable
from importlib import resources
from typing import NamedTuple

# Each manifest, the key of its entry list and the key of an entry's name.
MANIFESTS = {
    "scoop": ("scoop-packages.json", "scoops", "package"),
    "cargo": ("cargo-tools.json", "crates", "crate"),
    "bun": ("bun-tools.json", "packages", "package"),
    "uv": ("uv-tools.json", "tools", "tool"),
}


class Entry(NamedTuple):
    """One installable thing, as a manifest names it."""

    name: str
    manifest: str
    group: str
    description: str
    os: str | None
    bucket: str | None = None


class Catalog(NamedTuple):
    """All entries, the declared groups with their purpose, and each profile's groups."""

    entries: tuple[Entry, ...]
    groups: dict[str, str]
    profiles: dict[str, tuple[str, ...]]


def _packaged(name: str) -> str:
    return (resources.files("launchpad") / name).read_text(encoding="utf-8")


def load(read: Callable[[str], str] = _packaged) -> Catalog:
    """The catalog launchpad ships; `read` returns a file's text by its path inside the package."""
    entries = tuple(
        Entry(
            name=raw[name_key],
            manifest=manifest,
            group=raw.get("group", ""),
            description=raw.get("description") or "",
            os=raw.get("os"),
            bucket=raw.get("bucket"),
        )
        for manifest, (file, list_key, name_key) in MANIFESTS.items()
        for raw in json.loads(read(f"manifests/{file}"))[list_key]
    )
    config = tomllib.loads(read("profiles.toml"))
    profiles = {name: tuple(profile["groups"]) for name, profile in config.get("profiles", {}).items()}
    return Catalog(entries, dict(config["groups"]), profiles)


def profiles_of(catalog: Catalog, group: str) -> tuple[str, ...]:
    """The profiles whose list names this group."""
    return tuple(name for name, groups in catalog.profiles.items() if group in groups)


def find(catalog: Catalog, term: str) -> tuple[Entry, ...]:
    """Entries whose name contains the term, ignoring case; an exact name alone when there is one."""
    wanted = term.lower()
    exact = tuple(entry for entry in catalog.entries if entry.name.lower() == wanted)
    return exact or tuple(entry for entry in catalog.entries if wanted in entry.name.lower())


def in_groups(catalog: Catalog, groups: Iterable[str]) -> tuple[Entry, ...]:
    """Entries of the given groups, in manifest order."""
    chosen = set(groups)
    return tuple(entry for entry in catalog.entries if entry.group in chosen)
