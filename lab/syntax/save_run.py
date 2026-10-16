#!/usr/bin/env python3
"""Store one model reply as a submission.

  python3 lab/syntax/save_run.py MODEL VARIANT TASK [--tokens N] [--file REPLY.txt]

Reads the reply from --file (or standard input), writes
lab/syntax/runs/MODEL/VARIANT/TASK/attempt1.ail and meta.json. Refuses to overwrite an
existing attempt1.ail: the experiment counts the first try only. A Markdown code fence
in the reply is fine; the scorer strips it.
"""
import argparse
import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("variant")
    ap.add_argument("task")
    ap.add_argument("--tokens", type=int, help="output tokens reported by the tool, if known")
    ap.add_argument("--file")
    a = ap.parse_args()
    for label, value in (("model", a.model), ("variant", a.variant), ("task", a.task)):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value):
            sys.exit(f"bad {label}: use letters, digits, . _ - only")
    with open(os.path.join(HERE, "variants.json"), encoding="utf-8") as fh:
        if a.variant not in json.load(fh):
            sys.exit("unknown variant (see variants.json)")
    if not os.path.isfile(os.path.join(HERE, "tasks", a.task, "statement.md")):
        sys.exit("unknown task (see tasks/)")
    text = open(a.file, encoding="utf-8").read() if a.file else sys.stdin.read()
    d = os.path.join(HERE, "runs", a.model, a.variant, a.task)
    path = os.path.join(d, "attempt1.ail")
    if os.path.exists(path):
        sys.exit(f"{path} exists; only the first attempt counts")
    os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text if text.endswith("\n") else text + "\n")
    meta = {"model": a.model, "variant": a.variant, "task": a.task,
            "date": datetime.date.today().isoformat(), "tokens_out": a.tokens}
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
        fh.write("\n")
    print("saved", path)


if __name__ == "__main__":
    main()
