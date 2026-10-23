"""Replace placeholder difference ids (`C?-<branch>-N`) with the next free C numbers.

The per-job exports add their rows without knowing which C ids the merged branch will use.
Run after merging a job branch:

    python3 tools/diff_ids.py [--check] [FILE ...]

Without arguments the ledger files under docs/spec/ (and the older root spelling) are used.
Each distinct placeholder gets the next number after the largest `C<number>` already present,
in first-appearance order across the files.  `--check` exits 1 when a placeholder remains.
"""
from pathlib import Path
import re
import sys

REPO = Path(__file__).resolve().parents[1]
DEFAULT = (
    REPO / "docs/spec/DIFFERENCES.md",
    REPO / "docs/spec/DEVLOG.md",
    REPO / "DIFFERENCES.md",
    REPO / "DEVLOG.md",
    REPO / "AIL_CURRENT/docs/spec/DIFFERENCES.md",
    REPO / "AIL_CURRENT/docs/spec/DEVLOG.md",
)
PLACEHOLDER = re.compile(r"C\?-[A-Za-z0-9_.-]+")
REAL = re.compile(r"\bC(\d+)\b")


def main(argv):
    check = "--check" in argv
    names = [Path(name) for name in argv if not name.startswith("--")]
    paths = names or [path for path in DEFAULT if path.is_file()]
    texts = {path: path.read_text(encoding="utf-8") for path in paths}
    used = [int(m.group(1)) for text in texts.values() for m in REAL.finditer(text)]
    next_id = max(used, default=0) + 1
    mapping = {}
    for text in texts.values():
        for match in PLACEHOLDER.finditer(text):
            if match.group(0) not in mapping:
                mapping[match.group(0)] = "C%d" % next_id
                next_id += 1
    if check:
        for path, text in texts.items():
            for match in PLACEHOLDER.finditer(text):
                print("%s: placeholder %s" % (path.relative_to(REPO), match.group(0)))
        return 1 if mapping else 0
    for old, new in mapping.items():
        print("%s -> %s" % (old, new))
    for path, text in texts.items():
        updated = PLACEHOLDER.sub(lambda m: mapping[m.group(0)], text)
        if updated != text:
            path.write_text(updated, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
