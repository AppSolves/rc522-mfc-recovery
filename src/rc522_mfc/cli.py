from __future__ import annotations

import shutil
import subprocess
import sys
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from typer.core import TyperGroup

from . import __version__
from .branding import print_badge
from .exporters import export_csv, export_json, export_mct_keys
from .models import KeyRecord, KeyType, NonceType, RecoveryState, parse_known_key, parse_sector_expression
from .native import NativeTool
from .paths import ToolPaths
from .progress import ProgressUpdate, WorkflowProgressDisplay
from .solver import HardnestedSolver
from .state import StateStore
from .workflow import RecoveryOptions, RecoveryWorkflow


class RootGroup(TyperGroup):
    def format_help(
        self,
        ctx: Any,
        formatter: Any,
    ) -> None:
        print_badge(console)
        super().format_help(ctx, formatter)


app = typer.Typer(
    name="rc522-mfc",
    help="MIFARE Classic key recovery with a Raspberry Pi and an MFRC522 reader.",
    cls=RootGroup,
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,
    context_settings={"help_option_names": ["--help", "-h", "/?"]},
)
console = Console()


class NonceOverride(StrEnum):
    WEAK = "weak"
    HARD = "hard"
    STATIC = "static"


def version_callback(value: bool) -> None:
    if value:
        console.print(__version__)
        raise typer.Exit()


@app.callback()
def root_callback(
    version_flag: Annotated[
        bool | None,
        typer.Option(
            "--version",
            callback=version_callback,
            is_eager=True,
            help="Print the CLI version and exit.",
        ),
    ] = None,
) -> None:
    """Read-only MIFARE Classic recovery for Raspberry Pi and MFRC522."""
    del version_flag


def repository_root() -> Path:
    candidate = Path(__file__).resolve().parents[2]
    if (candidate / "pyproject.toml").is_file():
        return candidate
    raise RuntimeError("setup is available from a source checkout only")


def normalize_uid_argument(uid: str) -> str:
    cleaned = uid.strip().upper()
    if not cleaned:
        raise ValueError("UID is required")
    if any(character not in "0123456789ABCDEF" for character in cleaned):
        raise ValueError(
            "UID must contain hexadecimal characters only; for supported 4-byte "
            "cards this is usually 8 hex characters, for example DEADBEEF"
        )
    if len(cleaned) != 8:
        raise ValueError(
            f"UID must contain exactly 8 hexadecimal characters for supported 4-byte cards; got {cleaned!r}"
        )
    return cleaned


def load_saved_state(paths: ToolPaths, uid: str) -> tuple[str, StateStore, RecoveryState]:
    normalized_uid = normalize_uid_argument(uid)
    store = StateStore(paths.card_dir(normalized_uid))
    if not store.path.exists():
        raise RuntimeError(
            f"no saved recovery state exists for UID {normalized_uid}.\n"
            f"Expected state file: {store.path}\n"
            "Run `rc522-mfc recover ...` first, or confirm the full UID with `rc522-mfc inspect`."
        )
    return normalized_uid, store, store.load()


def print_key_table(state: RecoveryState) -> None:
    def render_key(record: KeyRecord | None) -> str:
        if record is None:
            return "[dim]????????????[/dim]"
        if record.verified:
            return record.value
        return f"[red]{record.value}[/red] [dim](unverified)[/dim]"

    def render_source(prefix: str, record: KeyRecord | None) -> str:
        if record is None:
            return ""
        suffix = "" if record.verified else " unverified"
        return f"{prefix}:{record.source}{suffix}"

    table = Table(title=f"Key map for UID {state.card.uid}")
    table.add_column("Sector", justify="right")
    table.add_column("Key A")
    table.add_column("Key B")
    table.add_column("Sources")
    for sector in range(16):
        key_a = state.get(sector, KeyType.A)
        key_b = state.get(sector, KeyType.B)
        sources = ", ".join(
            part
            for part in (
                render_source("A", key_a),
                render_source("B", key_b),
            )
            if part
        )
        table.add_row(
            str(sector),
            render_key(key_a),
            render_key(key_b),
            sources,
        )
    console.print(table)


def line_sink(line: str) -> None:
    if line.startswith("RC522_JSON:"):
        return
    console.print(line, markup=False, highlight=False)


def run_setup(*, force: bool = False, skip_apt: bool = False) -> int:
    script = repository_root() / "scripts" / "bootstrap.sh"
    command = [str(script)]
    if force:
        command.append("--force")
    if skip_apt:
        command.append("--skip-apt")
    console.print(Panel.fit("This command may ask for sudo.", title="Setup"))
    return subprocess.call(command)


def ensure_toolchain(*, require_pm3: bool) -> ToolPaths:
    paths = ToolPaths.discover()
    missing: list[str] = []
    if not paths.native.is_file():
        missing.append(f"native helper ({paths.native})")
    if require_pm3:
        try:
            HardnestedSolver(paths.pm3).ensure_ready()
        except RuntimeError as error:
            missing.append(f"offline PM3 solver ({error})")
    if not missing:
        return paths

    details = "\n".join(f"  • {item}" for item in missing)
    can_offer_setup = sys.stdin.isatty()
    if can_offer_setup:
        console.print(
            Panel.fit(
                f"The following components are missing:\n{details}",
                title="Toolchain incomplete",
                border_style="yellow",
            )
        )
        if typer.confirm("Run the setup command now?", default=True):
            if run_setup() != 0:
                raise RuntimeError("setup failed")
            paths = ToolPaths.discover()
            if paths.native.is_file() and (not require_pm3 or _pm3_solver_ready(paths.pm3)):
                return paths

    raise RuntimeError(
        f"required components are missing; run `rc522-mfc setup` from the source checkout:\n{details}"
    )


def _pm3_solver_ready(pm3: Path) -> bool:
    try:
        HardnestedSolver(pm3).ensure_ready()
    except RuntimeError:
        return False
    return True


@app.command()
def version() -> None:
    """Print the CLI version."""
    console.print(__version__)


@app.command()
def setup(
    force: Annotated[
        bool,
        typer.Option("--force", help="Rebuild dependencies even when already installed."),
    ] = False,
    skip_apt: Annotated[
        bool,
        typer.Option("--skip-apt", help="Do not install Debian packages."),
    ] = False,
) -> None:
    """Install system dependencies, WiringPi, the native helper, and the offline solver."""
    raise typer.Exit(run_setup(force=force, skip_apt=skip_apt))


@app.command()
def doctor() -> None:
    """Check the OS, SPI device, dependencies, and MFRC522 communication."""
    paths = ToolPaths.discover()
    table = Table(title="RC522 MFC doctor")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Details")

    gpio_path = shutil.which("gpio")
    try:
        HardnestedSolver(paths.pm3).ensure_ready()
        pm3_okay = True
        pm3_details = str(paths.pm3)
    except RuntimeError as error:
        pm3_okay = False
        pm3_details = str(error)

    checks: list[tuple[str, bool, str]] = [
        ("SPI device", Path("/dev/spidev0.0").exists(), "/dev/spidev0.0"),
        ("WiringPi", gpio_path is not None, gpio_path or "not found"),
        ("Native helper", paths.native.is_file(), str(paths.native)),
        ("PM3 solver", pm3_okay, pm3_details),
    ]

    if paths.native.is_file():
        try:
            payload = NativeTool(paths.native).reader_version()
            version_hex = str(payload.get("version_hex", ""))
            checks.append(
                (
                    "MFRC522",
                    version_hex not in {"00", "FF", ""},
                    f"VersionReg 0x{version_hex}",
                )
            )
        except Exception as error:
            checks.append(("MFRC522", False, str(error)))

    failed = False
    for name, okay, details in checks:
        failed |= not okay
        table.add_row(name, "[green]OK[/green]" if okay else "[red]FAIL[/red]", details)
    console.print(table)
    if failed:
        raise typer.Exit(1)


@app.command(name="inspect")
def inspect_card(
    samples: Annotated[
        int,
        typer.Option(min=16, help="Nonce samples used for classification."),
    ] = 128,
) -> None:
    """Identify the card and classify its nonce generator."""
    paths = ensure_toolchain(require_pm3=False)
    with WorkflowProgressDisplay(console, overall_label="Inspect card", overall_total=2) as progress:
        workflow = RecoveryWorkflow(paths, line_sink=progress.handle_line)
        progress.handle_update(ProgressUpdate("stage", "Identifying card", completed=0, total=1))
        card = workflow.identify()
        progress.handle_update(ProgressUpdate("overall", "Card identified", completed=1, total=2))
        progress.handle_update(
            ProgressUpdate("stage", "Sampling nonce generator", completed=0, total=samples)
        )
        nonce_type = workflow.classify_nonce(
            samples=samples,
            progress_callback=lambda native_progress: progress.handle_update(
                ProgressUpdate(
                    "stage",
                    "Sampling nonce generator",
                    completed=native_progress.completed,
                    total=native_progress.total,
                    detail=RecoveryWorkflow._native_progress_detail(
                        native_progress,
                        "samples",
                    ),
                )
            ),
        )
        progress.handle_update(ProgressUpdate("overall", "Nonce generator classified", completed=2, total=2))
        progress.finish(detail=f"classified as {nonce_type.value}")
    card.nonce_type = nonce_type
    table = Table(title="Card inspection")
    table.add_column("Field")
    table.add_column("Value")
    for key, value in (
        ("UID", card.uid),
        ("Type", card.card_type),
        ("ATQA", card.atqa),
        ("SAK", card.sak),
        ("MFRC522", f"0x{card.reader_version}"),
        ("Nonce type", nonce_type.value),
    ):
        table.add_row(key, str(value))
    console.print(table)


@app.command()
def recover(
    sectors: Annotated[
        str,
        typer.Option(help="Sector expression, for example 5-15 or 0,4,7-9."),
    ] = "0-15",
    key_types: Annotated[
        str,
        typer.Option(help="Recover A, B, or AB."),
    ] = "AB",
    known: Annotated[
        list[str] | None,
        typer.Option("--known", help="Verified seed key, for example 4:A=FFFFFFFFFFFF."),
    ] = None,
    dictionary: Annotated[
        list[Path] | None,
        typer.Option(
            "--dictionary",
            exists=True,
            dir_okay=False,
            help="Additional key dictionary. The option may be repeated.",
        ),
    ] = None,
    samples: Annotated[
        int,
        typer.Option(min=2, help="Hardnested nonce records per target key."),
    ] = 20_000,
    nonce_type: Annotated[
        NonceOverride | None,
        typer.Option(help="Override automatic nonce classification."),
    ] = None,
    no_fallback: Annotated[
        bool,
        typer.Option(
            "--no-fallback",
            help="Do not fall back to Hardnested if weak Nested fails.",
        ),
    ] = False,
    skip_dictionary: Annotated[
        bool,
        typer.Option(
            "--skip-dictionary",
            help="Skip bundled and user-provided dictionary scanning entirely.",
        ),
    ] = False,
    delete_traces: Annotated[
        bool,
        typer.Option(
            "--delete-traces",
            help="Delete raw nonce files after a verified recovery.",
        ),
    ] = False,
) -> None:
    """Recover missing keys, verify them, and reuse them across selected sectors."""
    selected_sectors = parse_sector_expression(sectors)
    selected_types = [KeyType(value) for value in dict.fromkeys(key_types.upper())]
    if not selected_types:
        raise typer.BadParameter("key types must contain A, B, or AB")
    parsed_known = [parse_known_key(value) for value in (known or [])]
    paths = ensure_toolchain(require_pm3=True)
    target_total = len(selected_sectors) * len(selected_types)
    console.print(
        Panel.fit(
            f"Sectors: {selected_sectors}\n"
            f"Keys: {''.join(value.value for value in selected_types)}\n"
            f"Hardnested samples: {samples:,}\n"
            f"Dictionary scan: {'disabled' if skip_dictionary else 'enabled'}",
            title="Recovery plan",
        )
    )
    with WorkflowProgressDisplay(
        console,
        overall_label="Recover selected keys",
        overall_total=target_total,
    ) as progress:
        workflow = RecoveryWorkflow(
            paths,
            line_sink=progress.handle_line,
            progress_sink=progress.handle_update,
        )
        state, store = workflow.recover(
            RecoveryOptions(
                sectors=selected_sectors,
                key_types=selected_types,
                known=parsed_known,
                dictionaries=dictionary or [],
                samples=samples if samples % 2 == 0 else samples + 1,
                force_nonce_type=NonceType(nonce_type.value) if nonce_type else None,
                fallback_hardnested=not no_fallback,
                keep_traces=not delete_traces,
                skip_dictionary=skip_dictionary,
            )
        )
        progress.finish(detail=f"saved state under {store.path}")
    print_key_table(state)
    console.print(f"[green]State saved to {store.path}[/green]")


@app.command()
def status(
    uid: Annotated[str, typer.Argument(help="Four-byte card UID.")],
) -> None:
    """Show saved recovery progress for a card."""
    paths = ToolPaths.discover()
    _, _, state = load_saved_state(paths, uid)
    print_key_table(state)


@app.command()
def verify(
    uid: Annotated[str, typer.Argument(help="Four-byte card UID.")],
) -> None:
    """Authenticate every saved key against the card again."""
    paths = ensure_toolchain(require_pm3=False)
    _, store, state = load_saved_state(paths, uid)
    native = NativeTool(paths.native, line_sink=line_sink)
    failed = 0
    for record in state.all_records():
        okay = native.authenticate(
            record.sector * 4,
            record.key_type,
            record.value,
            allow_failure=True,
        )
        console.print(
            f"Sector {record.sector:2d} Key {record.key_type.value}: "
            f"{'[green]verified[/green]' if okay else '[red]failed[/red]'}"
        )
        record.verified = okay
        failed += int(not okay)
    store.save(state)
    if failed:
        raise typer.Exit(1)


@app.command(name="export")
def export_command(
    uid: Annotated[str, typer.Argument(help="Four-byte card UID.")],
    export_format: Annotated[
        str,
        typer.Option("--format", "-f", help="json, csv, keys, or dump."),
    ] = "json",
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Destination file."),
    ] = None,
) -> None:
    """Export recovered keys or a read-only 1 KiB card dump."""
    paths = ToolPaths.discover()
    _, store, state = load_saved_state(paths, uid)
    normalized_format = export_format.lower()
    suffix = {"json": ".json", "csv": ".csv", "keys": ".keys", "dump": ".bin"}.get(normalized_format)
    if suffix is None:
        raise typer.BadParameter("format must be json, csv, keys, or dump")
    destination = output or Path.cwd() / f"mfc-{state.card.uid}{suffix}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if normalized_format == "json":
        export_json(state, destination)
    elif normalized_format == "csv":
        export_csv(state, destination)
    elif normalized_format == "keys":
        export_mct_keys(state, destination)
    else:
        paths = ensure_toolchain(require_pm3=False)
        if not state.has_key_for_every_sector():
            raise RuntimeError("a full dump requires at least one verified key for every sector")
        NativeTool(paths.native, line_sink=line_sink).dump(
            state.verified_records(),
            destination,
            work_dir=store.card_dir / "tmp",
        )
    console.print(f"[green]Saved {destination}[/green]")


def main() -> None:
    try:
        app()
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        console.print(Panel.fit(str(error), title="Error", border_style="red"))
        raise SystemExit(1) from None
