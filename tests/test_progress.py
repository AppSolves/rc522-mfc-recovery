from io import StringIO

from rich.console import Console

from rc522_mfc.progress import ProgressUpdate, WorkflowProgressDisplay


def _display() -> WorkflowProgressDisplay:
    return WorkflowProgressDisplay(
        Console(file=StringIO(), force_terminal=True, width=120),
        overall_label="Recover selected keys",
        overall_total=32,
    )


def _stage_task(display: WorkflowProgressDisplay):
    return next(task for task in display.progress.tasks if task.id == display._stage_task)


def test_new_indeterminate_stage_does_not_inherit_completed_state() -> None:
    with _display() as display:
        display.handle_update(ProgressUpdate("stage", "Preparing", completed=1, total=1))
        display.handle_update(
            ProgressUpdate("stage", "Solving Hardnested key", detail="offline solver running")
        )

        task = _stage_task(display)
        assert task.description == "Solving Hardnested key"
        assert task.total is None
        assert task.completed == 0
        assert task.fields["detail"] == "offline solver running"


def test_same_stage_completed_decrease_resets_task() -> None:
    with _display() as display:
        display.handle_update(ProgressUpdate("stage", "Collecting", completed=10, total=20))
        original_task = display._stage_task
        display.handle_update(ProgressUpdate("stage", "Collecting", completed=2, total=20))

        task = _stage_task(display)
        assert display._stage_task != original_task
        assert task.completed == 2
        assert task.total == 20


def test_machine_progress_lines_do_not_replace_human_detail() -> None:
    with _display() as display:
        display.handle_line("human detail")
        display.handle_line('RC522_PROGRESS:{"operation":"hardnested","completed":1,"total":2}')

        assert _stage_task(display).fields["detail"] == "human detail"
