"""The launch skips what is there, stops at the first failure, and keeps asking until a profile is named."""

import pytest

from launchpad import cli, plan

FIRST = plan.Step("first", ("first",), ("probe-first",))
SECOND = plan.Step("second", ("second",))


def test_a_step_whose_probe_succeeds_is_skipped():
    ran = []
    code = cli.launch(
        [FIRST, SECOND],
        run=lambda command: ran.append(command[0]) or 0,
        succeeds=lambda probe: probe == ("probe-first",),
        say=lambda line: None,
    )
    assert (code, ran) == (0, ["second"])


def test_a_failing_step_stops_the_launch_and_returns_its_exit_code():
    ran, said = [], []
    code = cli.launch(
        [SECOND, FIRST],
        run=lambda command: ran.append(command[0]) or 3,
        succeeds=lambda probe: False,
        say=said.append,
    )
    assert (code, ran) == (3, ["second"])
    assert any("run the launchpad again" in line for line in said)


def test_a_step_without_probe_always_runs():
    ran = []
    cli.launch([SECOND], run=lambda command: ran.append(command[0]) or 0, succeeds=lambda probe: True, say=print)
    assert ran == ["second"]


def test_the_profile_question_takes_a_number_or_a_name_and_repeats_on_anything_else():
    answers = iter(["captain", " 2 "])
    assert cli.choose_profile(ask=lambda prompt: next(answers), say=lambda line: None).name == "crew"
    assert cli.choose_profile(ask=lambda prompt: "Civilian", say=lambda line: None).name == "civilian"


def test_the_customer_question_takes_name_and_organisation_and_repeats_on_empty_answers():
    answers = iter(["", "example", "example-org"])
    customer = cli.ask_customer(ask=lambda prompt: next(answers))
    assert customer == plan.Customer("example", "example-org")


def test_the_customer_question_takes_an_empty_organisation_as_none():
    answers = iter(["example", ""])
    assert cli.ask_customer(ask=lambda prompt: next(answers)) == plan.Customer("example", None)


def test_an_elevated_shell_is_refused_before_anything_is_asked(monkeypatch, capsys):
    monkeypatch.setattr(cli.shell, "is_administrator", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt: pytest.fail(f"asked {prompt!r}"))
    assert cli.main(["civilian"]) == 1
    assert "not as Administrator" in capsys.readouterr().out
