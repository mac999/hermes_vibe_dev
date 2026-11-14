import argparse
import csv
import os
import sys
from datetime import date

from todo import storage
from todo.models import Task


def parse_due(text):
    try:
        if len(text) != 10:
            raise ValueError
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def today():
    env = os.environ.get("TODO_TODAY")
    return date.fromisoformat(env) if env else date.today()


def line(t):
    mark = "x" if t.done else " "
    s = f"[{mark}] {t.id}: {t.title}"
    return s + (f" (due {t.due})" if t.due else "")


def cmd_add(args):
    due = None
    if args.due is not None:
        due = parse_due(args.due)
        if due is None:
            print(f"invalid due date: {args.due}", file=sys.stderr)
            return 2
    tasks = storage.load()
    next_id = max((t.id for t in tasks), default=0) + 1
    tasks.append(Task(id=next_id, title=args.title, due=due))
    storage.save(tasks)
    print(f"added {next_id}")
    return 0


def cmd_list(args):
    now = today()
    for t in sorted(storage.load(), key=lambda t: t.id):
        if args.open and t.done:
            continue
        if args.overdue and (t.done or not t.due or date.fromisoformat(t.due) >= now):
            continue
        print(line(t))
    return 0


def cmd_done(args):
    tasks = storage.load()
    for t in tasks:
        if t.id == args.id:
            t.done = True
            storage.save(tasks)
            print(f"done {t.id}")
            return 0
    print(f"no such task: {args.id}", file=sys.stderr)
    return 1


def cmd_export(args):
    tasks = sorted(storage.load(), key=lambda t: t.id)
    if args.status == "open":
        tasks = [t for t in tasks if not t.done]
    elif args.status == "done":
        tasks = [t for t in tasks if t.done]
    out = open(args.out, "w", encoding="utf-8", newline="") if args.out else sys.stdout
    try:
        if args.format == "csv":
            w = csv.writer(out)
            w.writerow(["id", "title", "done", "due"])
            for t in tasks:
                w.writerow([t.id, t.title, "true" if t.done else "false", t.due or ""])
        else:
            out.write("| id | title | done | due |\n|---|---|---|---|\n")
            for t in tasks:
                title = t.title.replace("|", "\\|")
                out.write(f"| {t.id} | {title} | {'x' if t.done else ''} | {t.due or ''} |\n")
    finally:
        if args.out:
            out.close()
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="todo")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add")
    a.add_argument("title")
    a.add_argument("--due")
    a.set_defaults(func=cmd_add)

    ls = sub.add_parser("list")
    ls.add_argument("--open", action="store_true", help="only unfinished tasks")
    ls.add_argument("--overdue", action="store_true")
    ls.set_defaults(func=cmd_list)

    d = sub.add_parser("done")
    d.add_argument("id", type=int)
    d.set_defaults(func=cmd_done)

    e = sub.add_parser("export")
    e.add_argument("--format", choices=["csv", "md"], default="csv")
    e.add_argument("--status", choices=["open", "done", "all"], default="all")
    e.add_argument("--out")
    e.set_defaults(func=cmd_export)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)
