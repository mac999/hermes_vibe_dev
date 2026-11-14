import json
import os
from pathlib import Path

from todo.models import Task


def data_path():
    return Path(os.environ.get("TODO_FILE", Path.home() / ".todo.json"))


def load():
    p = data_path()
    if not p.exists():
        return []
    with p.open(encoding="utf-8") as f:
        return [Task.from_dict(d) for d in json.load(f)]


def save(tasks):
    p = data_path()
    tmp = p.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump([t.to_dict() for t in tasks], f, ensure_ascii=False, indent=2)
    tmp.replace(p)
