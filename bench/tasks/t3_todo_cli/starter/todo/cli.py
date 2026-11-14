import argparse
import sys

from todo import storage
from todo.models import Task


def cmd_add(args):
    tasks = storage.load()
    next_id = max((t.id for t in tasks), default=0) + 1
    tasks.append(Task(id=next_id, title=args.title))
    storage.save(tasks)
    print(f"added {next_id}")
    return 0


def cmd_list(args):
    for t in sorted(storage.load(), key=lambda t: t.id):
        if args.open and t.done:
            continue
        mark = "x" if t.done else " "
        print(f"[{mark}] {t.id}: {t.title}")
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


def build_parser():
    p = argparse.ArgumentParser(prog="todo")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add")
    a.add_argument("title")
    a.set_defaults(func=cmd_add)

    ls = sub.add_parser("list")
    ls.add_argument("--open", action="store_true", help="only unfinished tasks")
    ls.set_defaults(func=cmd_list)

    d = sub.add_parser("done")
    d.add_argument("id", type=int)
    d.set_defaults(func=cmd_done)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)
