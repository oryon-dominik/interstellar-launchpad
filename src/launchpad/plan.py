"""What a fresh machine needs, step by step. Pure data: nothing here runs or reads the disk."""

import re
from collections.abc import Sequence
from pathlib import Path
from typing import NamedTuple

from launchpad import catalog

DOTFILES_REPOSITORY = "oryon-dominik/dotfiles"
CUSTOMERS = Path("C:/dev/customers")


class Step(NamedTuple):
    """One command the launchpad runs, and the probe whose success makes it unnecessary."""

    title: str
    command: tuple[str, ...]
    skip_if: tuple[str, ...] = ()


class Profile(NamedTuple):
    """Who the machine is for."""

    name: str
    summary: str


class Customer(NamedTuple):
    """Whose machine it is: the directory under C:/dev/customers, and their GitHub organisation if any."""

    name: str
    organisation: str | None = None


PROFILES = (
    Profile("civilian", "the essentials: browser, media, PDF, screenshots, GIMP, Rust, uv — no account needed"),
    Profile("crew", "the full workstation — signs in to GitHub, then hands over to the dotfiles"),
    Profile("customer", "one customer's machine — its groups from profiles.toml, their repositories by token"),
)

# Read hidden and handed to gh on stdin: a token typed as an argument stays in the shell history.
CUSTOMER_SIGN_IN = (
    "$token = Read-Host 'GitHub token for the customer repositories' -AsSecureString; "
    "[Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($token))"
    " | gh auth login --hostname github.com --git-protocol https --with-token"
)

# Civilian picks, beyond the toolchains every profile shares: scoop package, bucket where needed,
# and the command that proves it is there however it was installed.
SCOOP_APPLICATIONS = (
    ("7zip", "7z"),
    ("pwsh", "pwsh"),
    ("extras/googlechrome", "chrome"),
    ("extras/vlc", "vlc"),
    ("extras/okular", "okular"),
    ("extras/flameshot", "flameshot"),
    ("extras/gimp", "gimp"),
)
APT_APPLICATIONS = ("vlc", "okular", "flameshot", "gimp")
# Google publishes Chrome for Linux as a .deb, for amd64 only.
CHROME_DEB = "https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb"
# The Windows Terminal that comes with Windows, and the id it gives its generated PowerShell 7 profile
# (measured 2026-11-12).
INBOX_TERMINAL_SETTINGS = (
    r"$env:LOCALAPPDATA\Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState\settings.json"
)
POWERSHELL_7_PROFILE = "{574e775e-4f2a-5b96-ac1e-a2962a402336}"


def _powershell(script: str) -> tuple[str, ...]:
    """Run a script in Windows PowerShell — the one shell every Windows machine carries."""
    return ("powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script)


def _utf8_windows() -> Step:
    """Stop before the dotfiles on a Windows that would read their scripts in the wrong code page.

    Windows PowerShell 5.1 reads a script without byte order mark in the system code page. The dotfiles
    are UTF-8; under the default code page 1252 their scripts no longer parse (measured 2026-11-10).
    """
    advice = (
        "Write-Host 'This Windows reads scripts in code page' ([Text.Encoding]::Default.CodePage)"
        " '- the dotfiles need UTF-8 (65001).'; "
        "Write-Host 'Turn on intl.cpl > Administrative > Change system locale > Beta: Unicode UTF-8,"
        " restart, then launch again.'; exit 1"
    )
    return Step(
        "Windows reads scripts as UTF-8",
        _powershell(advice),
        _powershell("if ([Text.Encoding]::Default.CodePage -eq 65001) { exit 0 } else { exit 1 }"),
    )


def _scoop_install(package: str, command: str) -> Step:
    """Install a scoop package unless Windows already finds its command, however it was installed.

    PATH finds what scoop and most installers put there; a system-wide install such as Chrome's
    registers itself under App Paths instead.
    """
    _, _, name = package.rpartition("/")
    app_paths = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
    probe = (
        f"if ((Get-Command {command} -ErrorAction SilentlyContinue)"
        rf" -or (Test-Path 'HKLM:\{app_paths}\{command}.exe')"
        rf" -or (Test-Path 'HKCU:\{app_paths}\{command}.exe')) {{ exit 0 }} else {{ exit 1 }}"
    )
    return Step(f"scoop: {name}", _powershell(f"scoop install {package}"), _powershell(probe))


def _windows_base(*, extras: bool) -> list[Step]:
    """Execution policy, scoop and git — what everything after them stands on."""
    base = [
        Step(
            "execution policy RemoteSigned for this user",
            # Without -ExecutionPolicy Bypass: a process-scope override makes this cmdlet report failure.
            ("powershell", "-NoProfile", "-Command", "Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force"),
            _powershell(
                "if ((Get-ExecutionPolicy -Scope CurrentUser) -in 'RemoteSigned', 'Unrestricted', 'Bypass')"
                " { exit 0 } else { exit 1 }"
            ),
        ),
        Step(
            "scoop",
            _powershell("Invoke-RestMethod https://get.scoop.sh | Invoke-Expression"),
            _powershell("Get-Command scoop -ErrorAction Stop"),
        ),
        _scoop_install("git", "git"),
    ]
    if extras:
        base.append(
            Step(
                "scoop bucket: extras",
                _powershell("scoop bucket add extras"),
                _powershell("if (scoop bucket list | Where-Object Name -eq 'extras') { exit 0 } else { exit 1 }"),
            )
        )
    return base


def _apt_install(packages: tuple[str, ...]) -> Step:
    """Install Debian packages unless every one of them is already there."""
    return Step(
        f"apt: {' '.join(packages)}",
        ("sudo", "sh", "-c", f"apt-get update && apt-get install --yes {' '.join(packages)}"),
        ("dpkg", "--status", *packages),
    )


def _chrome_deb() -> Step:
    """Chrome from Google's .deb, where Google builds one; elsewhere the step says so and passes."""
    script = (
        '[ "$(dpkg --print-architecture)" = amd64 ] || { echo "Chrome is built for amd64 only - skipped"; exit 0; }; '
        f"curl --location --silent --show-error --fail --output /tmp/google-chrome.deb {CHROME_DEB}"
        " && sudo apt-get install --yes /tmp/google-chrome.deb && rm /tmp/google-chrome.deb"
    )
    return Step("google chrome", ("sh", "-c", script), ("google-chrome", "--version"))


def _rust(*, system: str) -> list[Step]:
    """Rust through rustup: scoop carries it on Windows, rustup.rs everywhere else.

    Windows takes the GNU toolchain: it brings its own linker, MSVC needs the Microsoft C++ Build Tools.
    It does not bring dlltool, which windows-sys needs: the dotfiles take most tools prebuilt
    through cargo-binstall instead of compiling them (measured 2026-11-11).
    """
    toolchain = Step("rust: stable toolchain", ("rustup", "default", "stable"), ("cargo", "--version"))
    if system == "windows":
        return [_scoop_install("rustup-gnu", "rustup"), toolchain]
    installer = "curl --proto '=https' --tlsv1.2 --silent --show-error --fail https://sh.rustup.rs | sh -s -- -y"
    return [Step("rust: rustup", ("sh", "-c", installer), ("rustup", "--version")), toolchain]


def _crew(*, system: str, home: Path) -> list[Step]:
    """Sign in to GitHub, clone the dotfiles, hand over to their own installer."""
    dotfiles = home / ".dotfiles"
    if system == "windows":
        tools = [_utf8_windows(), *_windows_base(extras=False), _scoop_install("gh", "gh")]
        handover = Step(
            "dotfiles bootstrap",
            (
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(dotfiles / "install/bootstrap.ps1"),
            ),
        )
    else:
        tools = [_apt_install(("git", "gh", "openssh-client"))]
        handover = Step("dotfiles install", ("sh", str(dotfiles / "install/ubuntu/install.sh")))
    return [
        *tools,
        # The device flow: a code on this screen, confirmed in any browser with GitHub's own second factor.
        # SSH, because every repository the dotfiles clone afterwards is addressed by SSH.
        Step(
            "GitHub sign-in",
            ("gh", "auth", "login", "--hostname", "github.com", "--git-protocol", "ssh", "--web"),
            ("gh", "auth", "status", "--hostname", "github.com"),
        ),
        Step(
            "clone the dotfiles",
            ("gh", "repo", "clone", DOTFILES_REPOSITORY, str(dotfiles)),
            ("git", "-C", str(dotfiles), "rev-parse", "--git-dir"),
        ),
        handover,
    ]


def _terminal_opens_pwsh(*, settings: str = INBOX_TERMINAL_SETTINGS) -> Step:
    """Make PowerShell 7 the default profile of the Windows Terminal that comes with Windows.

    It keeps its own settings; the dotfiles configure only the scoop copy. Only the default profile
    changes; every other line stays as the terminal wrote it. The file appears on the terminal's first
    start, and the step waits for that rather than inventing one.
    """
    key = '"defaultProfile"\\s*:\\s*'
    script = (
        f'$path = "{settings}"; '
        "if (-not (Test-Path $path)) { "
        "Write-Host 'Start the Windows Terminal once so it writes its settings, then launch again.'; exit 1 }; "
        f'$text = [IO.File]::ReadAllText($path) -replace \'{key}"[^"]*"\','
        f' \'"defaultProfile": "{POWERSHELL_7_PROFILE}"\'; '
        "[IO.File]::WriteAllText($path, $text)"
    )
    probe = (
        f'$path = "{settings}"; '
        f"$wanted = '{key}\"' + [regex]::Escape('{POWERSHELL_7_PROFILE}') + '\"'; "
        "if ((Test-Path $path) -and ([IO.File]::ReadAllText($path) -match $wanted)) { exit 0 } else { exit 1 }"
    )
    return Step("the Windows Terminal opens PowerShell 7", _powershell(script), _powershell(probe))


def _clone_repositories(customer: Customer) -> Step:
    """Clone every repository of the customer that the token reads, once each.

    The token also reads the account's own repositories. With an organisation only its repositories
    count; without one, everything but the account's own.
    """
    root = CUSTOMERS / customer.name
    if customer.organisation:
        title = f"clone the repositories of {customer.organisation}"
        select = f"Where-Object {{ $_ -like '{customer.organisation}/*' }}"
        source = f"of {customer.organisation}"
    else:
        title = "clone the repositories the token reads"
        select = "Where-Object { $_ -notlike ($login + '/*') }"
        source = "beyond the own account"
    script = (
        f"$root = '{root}'; New-Item -ItemType Directory -Force -Path $root | Out-Null; "
        "$login = gh api /user --jq .login; if ($LASTEXITCODE) { exit $LASTEXITCODE }; "
        f"$repositories = @(gh api --paginate /user/repos --jq '.[].full_name' | {select}); "
        "if ($LASTEXITCODE) { exit $LASTEXITCODE }; "
        "if (-not $repositories) { "
        f"Write-Host 'The token reads no repository {source}.'; exit 1 }}; "
        "foreach ($repository in $repositories) { "
        "$path = Join-Path $root ($repository -split '/')[1]; "
        "if (Test-Path $path) { continue }; "
        "gh repo clone $repository $path; if ($LASTEXITCODE) { exit $LASTEXITCODE } }"
    )
    return Step(title, _powershell(script))


def _credential_section(url: str, *lines: str) -> str:
    """A credential section of a git config file, as a PowerShell array of its lines.

    The empty helper clears every helper configured before it, Git's own credential manager among them.
    """
    return ", ".join(f"'{line}'" for line in (f'[credential "{url}"]', "    helper =", *lines))


def _git_asks_gh(user_config: Path) -> Step:
    """Let git take the GitHub sign-in from gh, written to ~/.gitconfig.user and included from ~/.gitconfig.

    A file of its own survives a ~/.gitconfig that is replaced later, as long as the new one includes it.
    """
    section = _credential_section("https://github.com", "    helper = !gh auth git-credential")
    script = (
        f"Add-Content -Path '{user_config}' -Value {section}; "
        f"git config --global --add include.path '{user_config}'; exit $LASTEXITCODE"
    )
    return Step(
        "git asks gh for GitHub",
        _powershell(script),
        ("git", "config", "--file", str(user_config), "--get", "credential.https://github.com.helper", "gh auth"),
    )


def _probe(script: str) -> tuple[str, ...]:
    """A PowerShell condition as a probe: exit 0 when it holds."""
    return _powershell(f"if ({script}) {{ exit 0 }} else {{ exit 1 }}")


def _from_manifests(software: Sequence[catalog.Entry]) -> list[Step]:
    """Install what the manifests list, lane by lane, each lane after the runtime it needs.

    Each probe asks the lane's own package manager (outputs measured 2026-11-13), because a manifest's
    `command` is no reliable name to look for: some are null, some are key strokes or a whole call.
    """
    windows = [entry for entry in software if entry.os in (None, "windows")]
    lane = {name: [entry for entry in windows if entry.manifest == name] for name in catalog.MANIFESTS}
    buckets = sorted({entry.bucket for entry in lane["scoop"]} - {None, "main", "extras"})
    steps = [
        *(
            Step(
                f"scoop bucket: {bucket}",
                _powershell(f"scoop bucket add {bucket}"),
                _probe(f"scoop bucket list | Where-Object Name -eq '{bucket}'"),
            )
            for bucket in buckets
        ),
        *(
            Step(
                f"scoop: {entry.name}",
                _powershell(
                    f"scoop install {entry.name if entry.bucket == 'main' else f'{entry.bucket}/{entry.name}'}"
                ),
                _powershell(f"scoop prefix {entry.name} *> $null; exit $LASTEXITCODE"),
            )
            for entry in lane["scoop"]
        ),
    ]
    if lane["cargo"]:
        # Prebuilt binaries where a crate publishes them; cargo-binstall compiles the rest.
        steps += [*_rust(system="windows"), _scoop_install("cargo-binstall", "cargo-binstall")]
        steps += [
            Step(
                f"cargo: {entry.name}",
                ("cargo", "binstall", "--no-confirm", entry.name),
                _probe(f"(cargo install --list) -match '^{entry.name} v'"),
            )
            for entry in lane["cargo"]
        ]
    if lane["bun"] and not any(entry.name == "bun" for entry in lane["scoop"]):
        steps.append(_scoop_install("bun", "bun"))
    steps += [
        Step(
            f"bun: {entry.name}",
            ("bun", "add", "--global", entry.name),
            _probe(f"(bun pm ls --global) -match ('\\s' + [regex]::Escape('{entry.name}') + '@')"),
        )
        for entry in lane["bun"]
    ]
    # uv itself came with stage 0, from uv's own installer.
    steps += [
        Step(
            f"uv: {entry.name}",
            ("uv", "tool", "install", entry.name),
            _probe(f"(uv tool list) -match '^{entry.name.partition('[')[0]} v'"),
        )
        for entry in lane["uv"]
    ]
    return steps


def _customer(*, home: Path, customer: Customer, software: Sequence[catalog.Entry]) -> list[Step]:
    """Install the customer profile's groups, sign in with the customer's token, clone their repositories.

    Nothing private comes along: no dotfiles, no personal sign-in — the machine
    stands in the customer's network, and a browser sign-in would hand it every repository of the
    account.
    """
    user_config = home / ".gitconfig.user"
    return [
        *_windows_base(extras=True),
        *_from_manifests(software),
        _terminal_opens_pwsh(),
        Step(
            "GitHub sign-in with the customer token",
            _powershell(CUSTOMER_SIGN_IN),
            ("gh", "auth", "status", "--hostname", "github.com"),
        ),
        _git_asks_gh(user_config),
        _clone_repositories(customer),
    ]


def steps(
    *,
    profile: str,
    system: str,
    home: Path,
    customer: Customer | None = None,
    software: Sequence[catalog.Entry] = (),
) -> list[Step]:
    """The ordered steps that take this system to the profile; the customer profile needs its customer.

    `software` is what the profile's groups hold in the manifests; the customer profile installs it.
    """
    if system not in ("windows", "linux"):
        raise ValueError(f"no plan for {system!r} — the launchpad knows windows and linux")
    match profile:
        case "civilian" if system == "windows":
            return [
                *_windows_base(extras=True),
                *(_scoop_install(*application) for application in SCOOP_APPLICATIONS),
                *_rust(system=system),
            ]
        case "civilian":
            return [
                _apt_install(("git", "curl", "build-essential", *APT_APPLICATIONS)),
                _chrome_deb(),
                *_rust(system=system),
            ]
        case "crew":
            return _crew(system=system, home=home)
        case "customer" if system != "windows":
            raise ValueError("the customer profile is built for windows")
        case "customer" if customer is None:
            raise ValueError("the customer profile needs to know the customer")
        case "customer" if not all(
            re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*", part) for part in customer if part is not None
        ):
            raise ValueError(f"{customer} — a customer name and an organisation are letters, digits and dashes")
        case "customer":
            return _customer(home=home, customer=customer, software=software)
    raise ValueError(f"no profile {profile!r} — choose one of {', '.join(p.name for p in PROFILES)}")
