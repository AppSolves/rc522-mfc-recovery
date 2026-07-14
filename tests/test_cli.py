from typer.testing import CliRunner

from rc522_mfc.cli import app

runner = CliRunner()


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "0.1.0"


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "0.1.0"


def test_help_lists_recovery_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "recover" in result.stdout
    assert "inspect" in result.stdout
    assert "export" in result.stdout


def test_recover_help_mentions_skip_dictionary() -> None:
    result = runner.invoke(app, ["recover", "--help"])
    assert result.exit_code == 0
    assert "--skip-dictionary" in result.stdout
