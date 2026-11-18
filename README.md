# launchpad

One public command takes a fresh machine from a bare shell to a working toolchain.

[![prek](https://img.shields.io/badge/prek-enabled-orange?logo=rust&logoColor=white)](https://github.com/j178/prek)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://docs.astral.sh/ruff/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://docs.astral.sh/uv/)
[![python](https://img.shields.io/badge/Python-3.14+-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/oryon-dominik/interstellar-launchpad/blob/trunk/LICENSE)

A launchpad is where a rocket stands before lift-off. This one sends a machine off with a
working toolchain.

## Launch

**Windows** — open any PowerShell, even the old blue one, as your normal user:

```powershell
irm https://raw.githubusercontent.com/oryon-dominik/interstellar-launchpad/trunk/install.ps1 | iex
```

**Linux** — any shell with `curl` or `wget`:

```shell
wget -qO- https://raw.githubusercontent.com/oryon-dominik/interstellar-launchpad/trunk/install.sh | sh
```

The launchpad asks who the machine is for, shows its plan and asks before it starts.

New to this, on a fresh Windows 11? [A fresh Windows 11, ready to use](documentation/civilian.md)
walks through setup without a Microsoft account and the first launch, step by step.

| Profile | Windows | Linux (apt) |
|---|---|---|
| `civilian` | Scoop, git, 7-Zip, PowerShell 7, Chrome, VLC, Okular, Flameshot, GIMP, Rust (GNU toolchain), uv | git, curl, build tools, VLC, Okular, Flameshot, GIMP, Chrome (amd64), Rust, uv |
| `crew` | Scoop, git, GitHub CLI — then GitHub sign-in, the dotfiles, and their own installer | git, GitHub CLI — then the same |
| `customer` | the groups `profiles.toml` gives it (`launchpad manifest --profile customer`): git and GitHub CLI, PowerShell 7 (the Windows Terminal opens it), VS Code, Chrome, Rust with just, ripgrep, bat and zoxide, bun with the coding agents, the uv tools — then a token sign-in and every repository of the customer the token reads | — |

`crew` signs in to GitHub with a device code: a code appears in the terminal, and you confirm
it in any browser with your second factor. The SSH key it offers to upload is what every
later clone uses.

`customer` is for a machine that stands in one customer's network. It asks whose machine it is
(`--customer` and `--organisation` answer up front) and never signs in through the browser —
that would hand the machine every repository of the account. It asks for the customer's token
instead, hidden, and clones into `C:/dev/customers/<customer>/` every repository the token reads:
of the customer's GitHub organisation if one is named, otherwise everything but the account's
own. Nothing private comes along: no dotfiles, no token for them. The credential settings go to
`~/.gitconfig.user`.

Windows PowerShell reads scripts without byte order mark in the system code page, and the
dotfiles are UTF-8. Before `crew` hands over to them, the launchpad checks that Windows uses UTF-8
(*Beta: Unicode UTF-8* in the system locale) and says how to switch it on if not.

Run it again whenever you like — every step that is already done is skipped, and a failed step
names the command that failed.

## How it works

`install.ps1` and `install.sh` are stage 0: they install [uv](https://docs.astral.sh/uv/) and
run this repository's source archive with `uvx`. uv brings its own Python, so a fresh machine
needs nothing else. From there one Python program does the work on every system:

- `src/launchpad/plan.py` — what each profile needs, as an ordered list of steps; pure data
- `src/launchpad/adapters/shell.py` — runs the steps; the only module that touches processes
- `src/launchpad/cli.py` — the questions, and the run that skips what is done
- `src/launchpad/catalog.py` — the manifests and `profiles.toml`, read as one list

A step is a command and a probe: when the probe succeeds, the step is skipped.

## Manifests and groups

Everything that can be installed is listed once, in `src/launchpad/manifests/`, one manifest per
lane: `scoop-packages.json`, `cargo-tools.json`, `bun-tools.json`, `uv-tools.json`. The dotfiles read
the same files from this checkout (`INTERSTELLAR_LAUNCHPAD`). uv itself is in none of them: stage 0
installs it with uv's own installer.

Every entry carries a `group` that says what it is for, as a verb: `keep-the-logbook`,
`scan-the-hold`, `brief-the-copilots`. Who gets a group is decided in one place,
`src/launchpad/profiles.toml`, which also declares each group's purpose:

```toml
[profiles.customer]
groups = ["keep-the-logbook", "man-the-bridge", "scan-the-hold", "write-code", "browse-the-web", ...]
```

A customer's machine never gets `probe-defenses` or `take-remote-control`. A crew machine gets
everything a customer's machine gets, and those two groups only when asked for. Tests hold both lines.

To see where something lies and who gets it:

```shell
launchpad manifest                     # every group: how many entries, which profiles, what for
launchpad manifest ripgrep             # its lane, group and profiles
launchpad manifest --group seal-secrets
launchpad manifest --profile customer  # everything a customer's machine gets
```

From a checkout: `uv run launchpad manifest …`. To add something, put it into the manifest of its
lane with a `group` that `profiles.toml` declares; the tests refuse an entry without one.

## Working on it

```shell
just install   # dependencies, hooks
just test
just lint
```

To try a change before it is pushed, build the archive and point stage 0 at it:

```shell
git archive --format=zip --prefix=launchpad/ --output launchpad.zip HEAD
LAUNCHPAD_SOURCE=$PWD/launchpad.zip sh install.sh
```
