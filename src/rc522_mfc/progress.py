from __future__ import annotations

from dataclasses import dataclass

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    ProgressColumn,
    SpinnerColumn,
    Task,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from rich.text import Text


@dataclass(slots=True)
class ProgressUpdate:
    kind: str
    message: str
    completed: int | None = None
    total: int | None = None
    detail: str | None = None


def _format_duration(seconds: float | None) -> str:
    if seconds is None:
        return ""
    total_seconds = max(0, int(seconds))
    minutes, second = divmod(total_seconds, 60)
    hours, minute = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minute:02d}:{second:02d}"
    return f"{minute}:{second:02d}"


class ConditionalPercentageColumn(ProgressColumn):
    def render(self, task: Task) -> Text:
        if task.total is None:
            return Text("")
        return Text(f"{task.percentage:>3.0f}%", style="progress.percentage")


class ConditionalRemainingColumn(ProgressColumn):
    max_refresh = 0.5

    def render(self, task: Task) -> Text:
        if task.total is None or not task.fields.get("show_eta", True):
            return Text("")
        remaining = task.time_remaining
        if remaining is None:
            return Text("")
        return Text(_format_duration(remaining), style="progress.remaining")


class WorkflowProgressDisplay:
    def __init__(
        self,
        console: Console,
        *,
        overall_label: str,
        overall_total: int,
    ) -> None:
        self.console = console
        self.progress = Progress(
            SpinnerColumn(style="cyan"),
            TextColumn("[bold]{task.description}"),
            BarColumn(bar_width=None),
            ConditionalPercentageColumn(),
            TimeElapsedColumn(),
            ConditionalRemainingColumn(),
            TextColumn("{task.fields[detail]}", justify="left"),
            console=console,
            expand=True,
            transient=True,
        )
        self._overall_task: TaskID | None = None
        self._stage_task: TaskID | None = None
        self._overall_label = overall_label
        self._overall_total = overall_total
        self._stage_signature: tuple[str, int | None] | None = None
        self._stage_completed: float = 0

    def __enter__(self) -> WorkflowProgressDisplay:
        self.progress.start()
        self._overall_task = self.progress.add_task(
            self._overall_label,
            total=self._overall_total,
            completed=0,
            detail="",
            show_eta=False,
        )
        self._stage_task = self.progress.add_task(
            "Preparing workflow",
            total=None,
            detail="Waiting for reader",
            show_eta=True,
        )
        self._stage_signature = ("Preparing workflow", None)
        self._stage_completed = 0
        return self

    def __exit__(self, *_args: object) -> None:
        self.progress.stop()

    def handle_update(self, update: ProgressUpdate) -> None:
        if update.kind == "overall":
            self._update_overall(update)
            return
        if update.kind == "stage":
            self._update_stage(update)
            return
        if update.kind == "event":
            self._print_event(update.message)
            return
        self._set_detail(update.message)

    def handle_line(self, line: str) -> None:
        cleaned = line.strip()
        if not cleaned or cleaned.startswith(("RC522_JSON:", "RC522_PROGRESS:")):
            return
        self._set_detail(cleaned)

    def finish(self, *, detail: str = "") -> None:
        if self._stage_task is not None:
            self.progress.update(
                self._stage_task,
                description="Workflow complete",
                total=1,
                completed=1,
                detail=detail,
                show_eta=True,
            )
            self._stage_signature = ("Workflow complete", 1)
            self._stage_completed = 1

    def _update_overall(self, update: ProgressUpdate) -> None:
        if self._overall_task is None:
            return
        completed = float(update.completed or 0)
        total = float(update.total or self._overall_total or 1)
        detail = update.detail or f"{int(completed)}/{int(total)} complete"
        self.progress.update(
            self._overall_task,
            description=self._overall_label,
            total=total,
            completed=completed,
            detail=detail,
            show_eta=False,
        )

    def _update_stage(self, update: ProgressUpdate) -> None:
        if self._stage_task is None:
            return
        signature = (update.message, update.total)
        completed = 0 if update.completed is None else update.completed
        should_reset = self._stage_signature != signature or (
            update.completed is not None and update.completed < self._stage_completed
        )
        if should_reset:
            self.progress.remove_task(self._stage_task)
            self._stage_task = self.progress.add_task(
                update.message,
                total=update.total,
                completed=completed,
                detail=self._stage_detail(update),
                show_eta=True,
            )
            self._stage_signature = signature
            self._stage_completed = float(completed or 0)
            return
        detail = self._stage_detail(update)
        self.progress.update(
            self._stage_task,
            description=update.message,
            total=update.total,
            completed=completed,
            detail=detail,
            show_eta=True,
        )
        self._stage_completed = float(completed or 0)

    @staticmethod
    def _stage_detail(update: ProgressUpdate) -> str:
        if update.detail is not None:
            return update.detail
        if update.completed is not None and update.total:
            detail = f"{update.completed}/{update.total}"
            return detail
        return ""

    def _set_detail(self, detail: str) -> None:
        if self._stage_task is None:
            return
        trimmed = detail if len(detail) <= 96 else f"{detail[:93]}..."
        self.progress.update(self._stage_task, detail=trimmed)

    def _print_event(self, message: str) -> None:
        self.progress.console.print(f"[bold green]+[/bold green] {message}", highlight=False)
        self._set_detail(message)
