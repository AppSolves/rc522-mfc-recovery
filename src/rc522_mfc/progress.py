from __future__ import annotations

from dataclasses import dataclass

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)


@dataclass(slots=True)
class ProgressUpdate:
    kind: str
    message: str
    completed: int | None = None
    total: int | None = None


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
            TaskProgressColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            TextColumn("{task.fields[detail]}", justify="left"),
            console=console,
            expand=True,
            transient=False,
        )
        self._overall_task: TaskID | None = None
        self._stage_task: TaskID | None = None
        self._overall_label = overall_label
        self._overall_total = overall_total

    def __enter__(self) -> WorkflowProgressDisplay:
        self.progress.start()
        self._overall_task = self.progress.add_task(
            self._overall_label,
            total=self._overall_total,
            completed=0,
            detail="",
        )
        self._stage_task = self.progress.add_task(
            "Preparing workflow",
            total=None,
            detail="Waiting for reader",
        )
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
        self._set_detail(update.message)

    def handle_line(self, line: str) -> None:
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("RC522_JSON:"):
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
            )

    def _update_overall(self, update: ProgressUpdate) -> None:
        if self._overall_task is None:
            return
        completed = float(update.completed or 0)
        total = float(update.total or self._overall_total or 1)
        detail = f"{int(completed)}/{int(total)} complete"
        self.progress.update(
            self._overall_task,
            description=update.message or self._overall_label,
            total=total,
            completed=completed,
            detail=detail,
        )

    def _update_stage(self, update: ProgressUpdate) -> None:
        if self._stage_task is None:
            return
        detail = ""
        if update.completed is not None and update.total:
            detail = f"{update.completed}/{update.total}"
        self.progress.update(
            self._stage_task,
            description=update.message,
            total=update.total,
            completed=update.completed,
            detail=detail,
        )

    def _set_detail(self, detail: str) -> None:
        if self._stage_task is None:
            return
        trimmed = detail if len(detail) <= 96 else f"{detail[:93]}..."
        self.progress.update(self._stage_task, detail=trimmed)
