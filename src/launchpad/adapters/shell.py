"""Runs commands on this machine — the only module that touches processes and the environment."""

import ctypes
import os
import platform
import shutil
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

NOT_FOUND = 127
# Where scoop's rustup keeps its toolchains; it records them for new shells only.
RUST_HOMES = ("CARGO_HOME", "RUSTUP_HOME")


def system() -> str:
    """The operating system as the plan names it: windows, linux, darwin."""
    return platform.system().lower()


def is_administrator() -> bool:
    """Whether this Windows process runs elevated. Scoop refuses to install from one."""
    return system() == "windows" and bool(ctypes.windll.shell32.IsUserAnAdmin())


def prepare_environment(*, home: Path) -> None:
    """Shape the environment every step inherits.

    The directories installers drop tools into go on PATH: the installers record them for new
    shells only, so without this a step would not see what the one before it installed.
    PSModulePath goes: launched from PowerShell 7, Windows PowerShell inherits its module paths
    and cannot load its own security module — Get-ExecutionPolicy is then missing (measured 2026-10-19).
    Unset, each PowerShell rebuilds its own default.
    PSExecutionPolicyPreference goes too: a shell started with -ExecutionPolicy Bypass sets it, every
    child reads it as its process scope, and Set-ExecutionPolicy for CurrentUser then writes the value
    but fails with ExecutionPolicyOverride (measured 2026-11-18).
    """
    os.environ.pop("PSModulePath", None)
    os.environ.pop("PSExecutionPolicyPreference", None)
    # Launched from C:\Windows\System32, the second step's powershell failed with WinError 5;
    # from the home directory it ran (measured 2026-11-10). Every step starts from home.
    os.chdir(home)
    scoop = Path(os.environ.get("SCOOP", home / "scoop"))
    candidates = [scoop / "shims", home / ".cargo" / "bin", home / ".local" / "bin"]
    present = os.environ.get("PATH", "").split(os.pathsep)
    added = [str(directory) for directory in candidates if str(directory) not in present]
    os.environ["PATH"] = os.pathsep.join([*added, *present])


def _recorded_for_user(name: str) -> str | None:
    """One variable of the Windows user environment, which installers write and new shells read."""
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, _ = winreg.QueryValueEx(key, name)
    except FileNotFoundError:
        return None
    return winreg.ExpandEnvironmentStrings(value)


def adopt_user_environment(*, recorded: Callable[[str], str | None] = _recorded_for_user) -> None:
    """Take over what earlier steps recorded for new shells only, so the next step sees it.

    Scoop's rustup has no shim: it records its directory and homes in the user environment.
    Only PATH and the rust homes: the user environment may hold a PSModulePath too.
    """
    present = os.environ.get("PATH", "").split(os.pathsep)
    added = [entry for entry in (recorded("Path") or "").split(os.pathsep) if entry and entry not in present]
    os.environ["PATH"] = os.pathsep.join([*present, *added])
    for name in RUST_HOMES:
        if name not in os.environ and (value := recorded(name)):
            os.environ[name] = value


def run(command: Sequence[str], *, quiet: bool = False) -> int:
    """Run a command on this terminal, so its prompts reach the person, and return its exit code."""
    if system() == "windows":
        adopt_user_environment()
    executable = shutil.which(command[0])
    if executable is None:
        return NOT_FOUND
    output = subprocess.DEVNULL if quiet else None
    # The command comes from the plan, never from input; no shell parses it.
    return subprocess.run([executable, *command[1:]], stdout=output, stderr=output, check=False).returncode  # noqa: S603


def succeeds(command: Sequence[str]) -> bool:
    """Whether a probe command exits cleanly, without showing its output."""
    return run(command, quiet=True) == 0
