from rich.text import Text
from typer.testing import CliRunner

from rc522_mfc.branding import banner_text
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


def test_banner_resource_available() -> None:
    banner = banner_text()
    assert "RC522" in banner
    assert "MIFARE Classic" in banner


def test_help_lists_recovery_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "recover" in result.stdout
    assert "inspect" in result.stdout
    assert "export" in result.stdout


def test_recover_help_mentions_skip_dictionary() -> None:
    result = runner.invoke(app, ["recover", "--help"])
    assert result.exit_code == 0, result.output
    output = Text.from_ansi(result.output).plain
    assert "--skip-dictionary" in output


def test_short_help_aliases_work() -> None:
    assert runner.invoke(app, ["-h"]).exit_code == 0
    assert runner.invoke(app, ["/?"]).exit_code == 0
    assert runner.invoke(app, ["recover", "-h"]).exit_code == 0
    assert runner.invoke(app, ["recover", "/?"]).exit_code == 0


def test_status_rejects_short_uid_with_helpful_message() -> None:
    result = runner.invoke(app, ["status", "F"])
    assert result.exit_code == 1
    assert result.exception is not None
    assert "exactly 8 hexadecimal characters" in str(result.exception)


def test_status_reports_missing_state_helpfully() -> None:
    result = runner.invoke(app, ["status", "DEADBEEF"])
    assert result.exit_code == 1
    assert result.exception is not None
    assert "no saved recovery state exists for UID DEADBEEF" in str(result.exception)
    assert "rc522-mfc recover" in str(result.exception)
