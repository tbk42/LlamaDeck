from __future__ import annotations

import threading
import uuid
from typing import Any, Callable

_tasks: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


def create_task(task_type: str) -> str:
    task_id = str(uuid.uuid4())
    with _lock:
        _tasks[task_id] = {
            "id": task_id,
            "type": task_type,
            "status": "pending",
            "result": None,
            "error": None,
        }
    return task_id


def get_task(task_id: str) -> dict[str, Any] | None:
    with _lock:
        t = _tasks.get(task_id)
        if t is None:
            return None
        return dict(t)


def run_task(task_id: str, fn: Callable, *args: Any, **kwargs: Any) -> None:
    with _lock:
        if task_id in _tasks:
            _tasks[task_id]["status"] = "running"
    try:
        result = fn(*args, **kwargs)
        with _lock:
            if task_id in _tasks:
                _tasks[task_id]["status"] = "completed"
                _tasks[task_id]["result"] = result
    except Exception as e:
        with _lock:
            if task_id in _tasks:
                _tasks[task_id]["status"] = "failed"
                _tasks[task_id]["error"] = str(e)


def start_background(task_type: str, fn: Callable, *args: Any, **kwargs: Any) -> str:
    task_id = create_task(task_type)
    t = threading.Thread(target=run_task, args=(task_id, fn, *args), kwargs=kwargs, daemon=True)
    t.start()
    return task_id
