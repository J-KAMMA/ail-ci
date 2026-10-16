#!/usr/bin/env python3
"""Build the self-contained prompt for one (variant, task), or all of them.

  python3 lab/syntax/make_prompt.py pep484 caesar            # print one prompt
  python3 lab/syntax/make_prompt.py --all OUTDIR [--model M]  # write OUTDIR/<variant>/<task>.md
                                                               # (supported variants only)
The prompt holds the shared rules, the variant's syntax notes and the task statement. Nothing else.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def read(*parts):
    with open(os.path.join(HERE, *parts), encoding="utf-8") as fh:
        return fh.read().rstrip() + "\n"


def build(variants, variant, task):
    notes = read(variants[variant]["prompt"])
    return (read("prompts", "_common.md") + "\n" + notes + "\nTASK:\n\n"
            + read("tasks", task, "statement.md"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("variant", nargs="?")
    ap.add_argument("task", nargs="?")
    ap.add_argument("--all", metavar="OUTDIR")
    a = ap.parse_args()
    variants = json.loads(read("variants.json"))
    tasks = sorted(t for t in os.listdir(os.path.join(HERE, "tasks"))
                   if os.path.isfile(os.path.join(HERE, "tasks", t, "statement.md")))
    if a.all:
        n = 0
        for v, info in variants.items():
            if info["status"] != "supported":
                continue
            os.makedirs(os.path.join(a.all, v), exist_ok=True)
            for t in tasks:
                with open(os.path.join(a.all, v, t + ".md"), "w", encoding="utf-8") as fh:
                    fh.write(build(variants, v, t))
                n += 1
        print(f"wrote {n} prompts under {a.all}")
        return
    if not (a.variant in variants and a.task in tasks):
        sys.exit("usage: make_prompt.py VARIANT TASK | --all OUTDIR\n  variants: "
                 + ", ".join(variants) + "\n  tasks: " + ", ".join(tasks))
    sys.stdout.write(build(variants, a.variant, a.task))


if __name__ == "__main__":
    main()
