"""Reproducible task board built with portable PSX components."""
from dataclasses import dataclass

from psx import App, Button, Fragment, Text, component, use_state


@dataclass(frozen=True)
class Task:
    identifier: int
    title: str
    completed: bool = False


INITIAL_TASKS = (
    Task(1, "Read the Velto guide"),
    Task(2, "Run the behavior tests"),
    Task(3, "Inspect native backend options"),
)


@component
def TaskBoard():
    tasks, set_tasks = use_state(INITIAL_TASKS)

    def toggle(identifier: int) -> None:
        set_tasks(lambda previous: tuple(
            Task(task.identifier, task.title, not task.completed)
            if task.identifier == identifier else task
            for task in previous
        ))

    def clear_completed() -> None:
        set_tasks(lambda previous: tuple(task for task in previous if not task.completed))

    remaining = sum(not task.completed for task in tasks)
    rows = [
        Fragment(
            Text(f"{'[x]' if task.completed else '[ ]'} {task.title}"),
            Button("Toggle", on_click=lambda identifier=task.identifier: toggle(identifier)),
            key=task.identifier,
        )
        for task in tasks
    ]
    return Fragment(
        Text("Velto Task Board"),
        Text(f"Remaining: {remaining}"),
        *rows,
        Button("Clear completed", on_click=clear_completed),
    )


def create_app() -> App:
    return App(TaskBoard(), renderer="headless")


def main() -> int:
    app = create_app()
    try:
        root = app.mount()
        for child in root.children:
            if child.type == "Text":
                print(child.props["value"])
        return 0
    finally:
        app.unmount()


if __name__ == "__main__":
    raise SystemExit(main())
