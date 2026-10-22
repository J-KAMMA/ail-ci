#!/usr/bin/env python3
"""Replace placeholder difference ids (C?-...) in the record files with C-series ids.

Placeholders are numbered in order of first appearance, starting after the largest
real C-number already present.  Run from the repository root:

    python3 tools/diff_ids.py [--check]

--check exits 1 when a placeholder remains; it changes nothing.
"""
import re
import sys
from pathlib import Path

FILES = [
    Path("DIFFERENCES.md"),
    Path("docs/spec/DIFFERENCES.md"),
    Path("DEVLOG.md"),
    Path("docs/spec/DEVLOG.md"),
]

PLACEHOLDER = re.compile(r"C\?-[A-Za-z0-9_-]+")
REAL_ID = re.compile(r"\bC(\d+)\b")


def main():
    check = "--check" in sys.argv[1:]
    present = [p for p in FILES if p.exists()]
    texts = {p: p.read_text(encoding="utf-8") for p in present}

    placeholders = []
    for p in present:
        for m in PLACEHOLDER.finditer(texts[p]):
            if m.group(0) not in placeholders:
                placeholders.append(m.group(0))

    if check:
        if placeholders:
            print("placeholders left: " + ", ".join(placeholders))
            return 1
        return 0

    if not placeholders:
        return 0

    used = {int(n) for p in present for n in REAL_ID.findall(texts[p])}
    next_id = max(used, default=0) + 1
    mapping = {}
    for token in placeholders:
        while next_id in used:
            next_id += 1
        mapping[token] = f"C{next_id}"
        used.add(next_id)
        next_id += 1

    for p in present:
        text = texts[p]
        for token, real in mapping.items():
            text = text.replace(token, real)
        p.write_text(text, encoding="utf-8")
        print(f"updated {p}")
    for token, real in mapping.items():
        print(f"{token} -> {real}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
