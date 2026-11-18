import os

from launchpad.adapters import shell


def recorded_by(values):
    """A stand-in for the user's recorded environment."""
    return values.get


def test_a_directory_recorded_for_new_shells_reaches_the_next_step(monkeypatch):
    monkeypatch.setenv("PATH", "first")
    shell.adopt_user_environment(recorded=recorded_by({"Path": f"first{os.pathsep}second"}))
    assert os.environ["PATH"] == f"first{os.pathsep}second"


def test_scoop_rust_homes_reach_the_next_step(monkeypatch):
    monkeypatch.delenv("CARGO_HOME", raising=False)
    monkeypatch.delenv("RUSTUP_HOME", raising=False)
    shell.adopt_user_environment(recorded=recorded_by({"CARGO_HOME": "cargo", "RUSTUP_HOME": "rustup"}))
    assert (os.environ["CARGO_HOME"], os.environ["RUSTUP_HOME"]) == ("cargo", "rustup")


def test_a_home_set_in_this_process_stays(monkeypatch):
    monkeypatch.setenv("CARGO_HOME", "chosen")
    shell.adopt_user_environment(recorded=recorded_by({"CARGO_HOME": "recorded"}))
    assert os.environ["CARGO_HOME"] == "chosen"


def test_powershell_module_paths_are_not_adopted(monkeypatch):
    monkeypatch.delenv("PSModulePath", raising=False)
    shell.adopt_user_environment(recorded=recorded_by({"PSModulePath": "pwsh-modules"}))
    assert "PSModulePath" not in os.environ


def test_every_windows_command_sees_what_the_step_before_recorded(monkeypatch):
    adopted = []
    monkeypatch.setattr(shell, "system", lambda: "windows")
    monkeypatch.setattr(shell, "adopt_user_environment", lambda: adopted.append(True))
    monkeypatch.setattr(shell.shutil, "which", lambda command: None)
    assert shell.run(("rustup", "--version")) == shell.NOT_FOUND
    assert adopted == [True]
