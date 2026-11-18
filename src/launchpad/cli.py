"""The interactive launch: pick a profile, show the plan, run it step by step."""

import argparse
import shlex
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from launchpad import catalog, plan
from launchpad.adapters import shell

BANNER = """
  launchpad — from a bare shell to a working toolchain
"""


def launch(
    steps: Sequence[plan.Step],
    *,
    run: Callable[[Sequence[str]], int],
    succeeds: Callable[[Sequence[str]], bool],
    say: Callable[[str], None],
) -> int:
    """Run the steps in order, skip what is already there, stop at the first failure."""
    for number, step in enumerate(steps, start=1):
        prefix = f"[{number}/{len(steps)}] {step.title}"
        if step.skip_if and succeeds(step.skip_if):
            say(f"{prefix} — already there")
            continue
        say(f"{prefix} …")
        if code := run(step.command):
            say(f"{prefix} failed with exit code {code}.")
            say(f"  command: {shlex.join(step.command)}")
            say("  Fix the cause and run the launchpad again — every finished step is skipped.")
            return code
    return 0


def ask_customer(*, ask: Callable[[str], str]) -> plan.Customer:
    """Ask for the customer's name until it is answered, then for their GitHub organisation, which may be empty."""

    def answer(prompt: str) -> str:
        while not (given := ask(prompt).strip()):
            pass
        return given

    return plan.Customer(
        answer("Customer name (its directory under C:/dev/customers): "),
        ask("The customer's GitHub organisation (empty: none): ").strip() or None,
    )


def choose_profile(*, ask: Callable[[str], str], say: Callable[[str], None]) -> plan.Profile:
    """Ask until the answer names a profile, by number or by name."""
    for number, profile in enumerate(plan.PROFILES, start=1):
        say(f"  {number}) {profile.name:<9} {profile.summary}")
    while True:
        answer = ask("Who is this machine for? ").strip().lower()
        for number, profile in enumerate(plan.PROFILES, start=1):
            if answer in (str(number), profile.name):
                return profile
        say(f"  '{answer}' is none of them — answer with a number or a name.")


def show_manifest(argv: Sequence[str], *, say: Callable[[str], None] = print) -> int:
    """`launchpad manifest`: where each thing lies — its manifest, its group, the profiles that carry it."""
    parser = argparse.ArgumentParser(
        prog="launchpad manifest", description="Where each installable thing lies, and who gets it."
    )
    parser.add_argument("term", nargs="?", help="a name or part of one, e.g. ripgrep or git")
    parser.add_argument("--group", help="list one group's entries")
    parser.add_argument("--profile", help="list everything a profile gets")
    arguments = parser.parse_args(argv)
    hold = catalog.load()

    if arguments.term:
        entries = catalog.find(hold, arguments.term)
    elif arguments.group:
        if arguments.group not in hold.groups:
            say(f"No group {arguments.group!r} — known: {', '.join(hold.groups)}")
            return 1
        entries = catalog.in_groups(hold, [arguments.group])
    elif arguments.profile:
        if arguments.profile not in hold.profiles:
            say(f"No profile {arguments.profile!r} in profiles.toml — known: {', '.join(hold.profiles)}")
            return 1
        entries = catalog.in_groups(hold, hold.profiles[arguments.profile])
    else:
        for group, purpose in hold.groups.items():
            count = len(catalog.in_groups(hold, [group]))
            carriers = ", ".join(catalog.profiles_of(hold, group)) or "-"
            say(f"  {group:<22} {count:>3}  {carriers:<12} {purpose}")
        return 0

    if not entries:
        say(f"Nothing in the manifests matches {arguments.term!r}.")
        return 1
    for entry in entries:
        carriers = ", ".join(catalog.profiles_of(hold, entry.group)) or "-"
        system = f" ({entry.os} only)" if entry.os else ""
        say(f"  {entry.name:<32} {entry.manifest:<6} {entry.group:<22} {carriers}{system}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point of the `launchpad` command."""
    arguments_given = list(sys.argv[1:] if argv is None else argv)
    if arguments_given[:1] == ["manifest"]:
        return show_manifest(arguments_given[1:])
    parser = argparse.ArgumentParser(
        prog="launchpad",
        description=BANNER.strip(),
        epilog="launchpad manifest [name] [--group G] [--profile P] shows where each installable thing lies.",
    )
    parser.add_argument("profile", nargs="?", choices=[profile.name for profile in plan.PROFILES])
    parser.add_argument("--yes", action="store_true", help="run the plan without asking first")
    parser.add_argument(
        "--customer", help="customer profile: the customer's name, its directory under C:/dev/customers"
    )
    parser.add_argument("--organisation", help="customer profile: the customer's GitHub organisation, if any")
    arguments = parser.parse_args(arguments_given)

    print(BANNER)
    if shell.is_administrator():
        print("Run this as your normal user, not as Administrator — scoop installs per user and refuses elevation.")
        return 1
    home = Path.home()
    if arguments.profile:
        profile = next(profile for profile in plan.PROFILES if profile.name == arguments.profile)
    else:
        profile = choose_profile(ask=input, say=print)
    customer = None
    if profile.name == "customer":
        if arguments.customer:
            customer = plan.Customer(arguments.customer, arguments.organisation)
        else:
            customer = ask_customer(ask=input)
    hold = catalog.load()
    software = catalog.in_groups(hold, hold.profiles.get(profile.name, ()))
    try:
        steps = plan.steps(
            profile=profile.name, system=shell.system(), home=home, customer=customer, software=software
        )
    except ValueError as refusal:
        print(refusal)
        return 1

    print(f"\nThe {profile.name} plan:")
    for number, step in enumerate(steps, start=1):
        print(f"  {number:>2}. {step.title}")
    if not arguments.yes and input("\nLaunch? [Y/n] ").strip().lower() not in ("", "y", "yes"):
        print("Nothing launched.")
        return 0

    shell.prepare_environment(home=home)
    code = launch(steps, run=shell.run, succeeds=shell.succeeds, say=print)
    if code == 0:
        print("\nAll systems go. Open a new terminal — it picks up everything installed here.")
    return code
