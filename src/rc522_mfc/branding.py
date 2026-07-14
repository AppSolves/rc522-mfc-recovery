from __future__ import annotations

from importlib.resources import files

from rich.console import Console
from rich.panel import Panel
from rich.text import Text


def banner_text() -> str:
    return files("rc522_mfc.data").joinpath("banner.txt").read_text(encoding="utf-8").rstrip()


def print_badge(console: Console) -> None:
    console.print(
        Panel(
            Text(banner_text(), style="bold cyan"),
            border_style="cyan",
            padding=(0, 1),
        )
    )
    console.line()
