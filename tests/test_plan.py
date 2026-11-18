"""The plan names the right steps for each profile and system, in an order that stands on itself."""

import shutil
import subprocess
from pathlib import Path

import pytest

from launchpad import catalog, plan

HOME = Path("/home/pioneer")


def titles(steps: list[plan.Step]) -> list[str]:
    return [step.title for step in steps]


@pytest.mark.parametrize("system", ["windows", "linux"])
@pytest.mark.parametrize("profile", ["civilian", "crew"])
def test_every_profile_has_a_plan_on_every_known_system(profile, system):
    assert plan.steps(profile=profile, system=system, home=HOME)


def test_civilian_windows_installs_the_named_applications_after_scoop_and_its_bucket():
    names = titles(plan.steps(profile="civilian", system="windows", home=HOME))
    assert names.index("scoop") < names.index("scoop: git") < names.index("scoop bucket: extras")
    assert names.index("scoop bucket: extras") < names.index("scoop: gimp")
    assert {"scoop: pwsh", "scoop: gimp", "scoop: rustup-gnu", "rust: stable toolchain"} <= set(names)
    assert {"scoop: vlc", "scoop: okular", "scoop: googlechrome", "scoop: flameshot"} <= set(names)


def test_a_scoop_application_is_probed_by_its_command_so_an_msi_install_counts():
    pwsh = next(step for step in plan.steps(profile="civilian", system="windows", home=HOME) if "pwsh" in step.title)
    assert pwsh.command[-1] == "scoop install pwsh"
    assert "Get-Command pwsh" in pwsh.skip_if[-1]


def test_an_application_registered_under_app_paths_counts_as_installed():
    """A system-wide Chrome is not on PATH; Windows knows it under App Paths."""
    chrome = next(s for s in plan.steps(profile="civilian", system="windows", home=HOME) if "chrome" in s.title)
    assert r"App Paths\chrome.exe" in chrome.skip_if[-1]


def test_civilian_linux_needs_a_compiler_for_cargo_and_brings_the_applications():
    apt = plan.steps(profile="civilian", system="linux", home=HOME)[0]
    assert {"build-essential", "gimp", "vlc", "okular", "flameshot"} <= set(apt.skip_if)


def test_chrome_on_linux_comes_from_google_after_apt_and_only_where_google_builds_it():
    names = titles(plan.steps(profile="civilian", system="linux", home=HOME))
    chrome = plan.steps(profile="civilian", system="linux", home=HOME)[names.index("google chrome")]
    assert names.index("google chrome") > 0
    assert "dpkg --print-architecture" in chrome.command[-1]
    assert chrome.skip_if == ("google-chrome", "--version")


def test_the_execution_policy_is_set_without_a_process_scope_override():
    policy = plan.steps(profile="civilian", system="windows", home=HOME)[0]
    assert "Bypass" not in policy.command


@pytest.mark.parametrize("system", ["windows", "linux"])
def test_crew_signs_in_before_it_clones_and_hands_over_last(system):
    names = titles(plan.steps(profile="crew", system=system, home=HOME))
    assert names.index("GitHub sign-in") < names.index("clone the dotfiles") == len(names) - 2


@pytest.mark.parametrize(
    ("system", "installer"), [("windows", "install/bootstrap.ps1"), ("linux", "install/ubuntu/install.sh")]
)
def test_crew_hands_over_to_the_dotfiles_installer_inside_the_clone(system, installer):
    handover = plan.steps(profile="crew", system=system, home=HOME)[-1]
    assert Path(handover.command[-1]) == HOME / ".dotfiles" / installer


def test_an_unknown_system_is_refused_by_name():
    with pytest.raises(ValueError, match="darwin"):
        plan.steps(profile="civilian", system="darwin", home=HOME)


def test_an_unknown_profile_is_refused_by_name():
    with pytest.raises(ValueError, match="captain"):
        plan.steps(profile="captain", system="linux", home=HOME)


def test_windows_rust_builds_without_the_microsoft_build_tools():
    commands = [step.command for step in plan.steps(profile="civilian", system="windows", home=HOME)]
    assert any("scoop install rustup-gnu" in " ".join(command) for command in commands)


CUSTOMER = plan.Customer(name="example", organisation="example-org")


def customer_software() -> tuple[catalog.Entry, ...]:
    hold = catalog.load()
    return catalog.in_groups(hold, hold.profiles["customer"])


def customer_steps(customer: plan.Customer = CUSTOMER) -> list[plan.Step]:
    return plan.steps(profile="customer", system="windows", home=HOME, customer=customer, software=customer_software())


def step_titled(steps: list[plan.Step], title: str) -> plan.Step:
    return next(step for step in steps if step.title == title)


def test_customer_signs_in_with_a_token_never_through_the_browser():
    """A browser sign-in hands the machine the whole personal account, not the customer's repositories."""
    sign_in = step_titled(customer_steps(), "GitHub sign-in with the customer token")
    assert "--with-token" in sign_in.command[-1]
    assert "--web" not in " ".join(sign_in.command)
    assert "-AsSecureString" in sign_in.command[-1]


def test_customer_clones_what_the_token_reads_of_the_organisation_into_the_customer_directory():
    """A token reads more than the customer's repositories — the account's own public ones too."""
    clone = step_titled(customer_steps(), "clone the repositories of example-org")
    assert "/user/repos" in clone.command[-1]
    assert "'example-org/*'" in clone.command[-1]
    assert str(Path("C:/dev/customers/example")) in clone.command[-1]


def test_customer_without_an_organisation_clones_everything_the_token_reads_but_the_own_account():
    """Not every customer has an organisation; the account's own repositories are never theirs."""
    clone = step_titled(customer_steps(plan.Customer("example")), "clone the repositories the token reads")
    assert "gh api /user --jq .login" in clone.command[-1]
    assert "-notlike" in clone.command[-1]


def test_customer_git_credentials_live_in_a_file_of_their_own_included_from_the_gitconfig():
    credentials = step_titled(customer_steps(), "git asks gh for GitHub")
    assert str(HOME / ".gitconfig.user") in credentials.command[-1]
    assert "include.path" in credentials.command[-1]
    assert "!gh auth git-credential" in credentials.command[-1]
    assert credentials.skip_if[:3] == ("git", "config", "--file")


def test_customer_signs_in_before_it_clones():
    names = titles(customer_steps())
    assert names.index("GitHub sign-in with the customer token") < names.index("clone the repositories of example-org")


def test_customer_brings_editor_browser_shell_and_the_rust_tools_from_its_groups():
    names = set(titles(customer_steps()))
    assert {"scoop: vscode", "scoop: googlechrome", "scoop: pwsh", "scoop: gh"} <= names
    assert {"cargo: just", "cargo: ripgrep", "cargo: bat", "cargo: zoxide"} <= names


def test_customer_brings_nothing_private():
    """A customer's machine stands in their network: no dotfiles, and so no token for them."""
    commands = " ".join(" ".join(step.command) for step in customer_steps())
    assert ".dotfiles" not in commands
    assert plan.DOTFILES_REPOSITORY not in commands


def test_each_lane_comes_after_the_runtime_it_needs():
    names = titles(customer_steps())
    first_crate = next(index for index, name in enumerate(names) if name.startswith("cargo: "))
    assert names.index("rust: stable toolchain") < names.index("scoop: cargo-binstall") < first_crate
    first_package = next(index for index, name in enumerate(names) if name.startswith("bun: "))
    assert names.index("scoop: bun") < first_package


def test_entries_for_another_system_stay_out():
    """jless and the cargo starship are built for posix; Windows takes starship from scoop."""
    names = titles(customer_steps())
    assert "cargo: jless" not in names
    assert "cargo: starship" not in names
    assert "scoop: starship" in names


def test_a_bucket_beyond_main_and_extras_is_added_before_its_package():
    names = titles(customer_steps())
    assert names.index("scoop bucket: versions") < names.index("scoop: firefox-nightly")


ENTRIES = (
    catalog.Entry("git", "scoop", "keep-the-logbook", "", None, "main"),
    catalog.Entry("ripgrep", "cargo", "scan-the-hold", "", None),
    catalog.Entry("@openai/codex", "bun", "brief-the-copilots", "", None),
    catalog.Entry("rembg[cpu,cli]", "uv", "cut-transmissions", "", None),
)


def test_every_lane_asks_its_own_package_manager_whether_an_entry_is_there():
    steps = {
        step.title: step
        for step in plan.steps(profile="customer", system="windows", home=HOME, customer=CUSTOMER, software=ENTRIES)
    }
    assert "scoop prefix git" in steps["scoop: git"].skip_if[-1]
    assert steps["cargo: ripgrep"].command == ("cargo", "binstall", "--no-confirm", "ripgrep")
    assert "(cargo install --list) -match '^ripgrep v'" in steps["cargo: ripgrep"].skip_if[-1]
    assert "(bun pm ls --global)" in steps["bun: @openai/codex"].skip_if[-1]
    assert "(uv tool list) -match '^rembg v'" in steps["uv: rembg[cpu,cli]"].skip_if[-1]
    assert "scoop: bun" in steps


def test_a_plan_that_runs_the_dotfiles_first_asks_for_a_utf8_windows():
    """Windows PowerShell 5.1 reads a script without BOM in the system code page; the dotfiles are UTF-8."""
    first = plan.steps(profile="crew", system="windows", home=HOME)[0]
    assert "65001" in first.skip_if[-1]


def test_customer_needs_to_know_whose_machine_it_is():
    with pytest.raises(ValueError, match="customer"):
        plan.steps(profile="customer", system="windows", home=HOME)


@pytest.mark.parametrize("customer", [plan.Customer("../etc", "org"), plan.Customer("example", "org'; Remove-Item")])
def test_customer_names_that_would_leave_the_directory_or_the_script_are_refused(customer):
    with pytest.raises(ValueError, match="name"):
        plan.steps(profile="customer", system="windows", home=HOME, customer=customer)


def test_customer_is_built_for_windows_and_says_so():
    with pytest.raises(ValueError, match="windows"):
        plan.steps(profile="customer", system="linux", home=HOME, customer=CUSTOMER)


@pytest.mark.skipif(shutil.which("powershell") is None, reason="Windows PowerShell is Windows only")
@pytest.mark.parametrize("profile", ["civilian", "crew", "customer"])
def test_every_windows_script_parses_in_windows_powershell_through_its_real_command_line(profile):
    """Quotes inside a -Command argument survive two parsers; a leading exit runs nothing of the script."""
    customers = (CUSTOMER, plan.Customer("example"))
    steps = [
        step
        for customer in customers
        for step in plan.steps(
            profile=profile, system="windows", home=HOME, customer=customer, software=customer_software()
        )
    ]
    for step in steps:
        for command in (step.command, step.skip_if):
            if command[:1] == ("powershell",) and "-Command" in command:
                script = command[command.index("-Command") + 1]
                # The command comes from the plan under test, and the leading exit keeps it from running.
                head = command[: command.index("-Command") + 1]
                result = subprocess.run([*head, f"exit 7; {script}"], check=False)  # noqa: S603
                assert result.returncode == 7, f"{step.title}: {script}"


def test_customer_terminal_opens_powershell_7_once_powershell_7_is_there():
    names = titles(customer_steps())
    assert names.index("scoop: pwsh") < names.index("the Windows Terminal opens PowerShell 7")


SETTINGS = """{
    "$help": "https://aka.ms/terminal-documentation",
    "defaultProfile": "{61c54bbd-c2c6-5271-96e7-009a87ff44bf}",
    "profiles": {"list": [{"guid": "{574e775e-4f2a-5b96-ac1e-a2962a402336}", "name": "PowerShell"}]}
}
"""


@pytest.mark.skipif(shutil.which("powershell") is None, reason="Windows PowerShell is Windows only")
def test_the_terminal_step_changes_the_default_profile_and_nothing_else(tmp_path):
    """The terminal writes its settings itself; the step must leave every other line as it was."""
    settings = tmp_path / "settings.json"
    settings.write_text(SETTINGS, encoding="utf-8", newline="\n")
    step = plan._terminal_opens_pwsh(settings=str(settings))
    assert subprocess.run(step.skip_if, check=False).returncode == 1  # noqa: S603 — the plan under test
    assert subprocess.run(step.command, check=False).returncode == 0  # noqa: S603 — the plan under test
    expected = SETTINGS.replace("61c54bbd-c2c6-5271-96e7-009a87ff44bf", "574e775e-4f2a-5b96-ac1e-a2962a402336")
    assert settings.read_bytes() == expected.encode()
    assert subprocess.run(step.skip_if, check=False).returncode == 0  # noqa: S603 — the plan under test


@pytest.mark.skipif(shutil.which("powershell") is None, reason="Windows PowerShell is Windows only")
def test_the_terminal_step_asks_for_one_start_where_the_terminal_has_not_written_its_settings(tmp_path):
    step = plan._terminal_opens_pwsh(settings=str(tmp_path / "settings.json"))
    result = subprocess.run(step.command, check=False, capture_output=True, text=True)  # noqa: S603 — the plan under test
    assert result.returncode == 1
    assert "Start the Windows Terminal once" in result.stdout
    assert not (tmp_path / "settings.json").exists()
