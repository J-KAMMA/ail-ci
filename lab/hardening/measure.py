#!/usr/bin/env python3
"""Build the hardening corpus and measure every binary with tools/hardening_check.py.

    python3 lab/hardening/measure.py [--json OUT] [--table]

AIL programs (lab/hardening/*.py) are built in the default mode and with --strict, the same
algorithms in C (lab/hardening/*.c) with gcc -O2, and lab/compare/src/*/main.rs with the flags
lab/compare/run_task.py uses. Builds and their stdin fixtures live under a temporary directory;
nothing is written into the checkout.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AIL = REPO / "AIL_CURRENT" / "ail_chatgpt.py"
CHECK = REPO / "tools" / "hardening_check.py"
PROGRAMS = ["csv_sum", "word_count", "rec_tree", "str_build", "dict_count"]
STDIN = {"csv_sum": "input.txt", "word_count": "words.txt", "dict_count": "words.txt"}


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def fixtures(root):
    import random
    random.seed(7)
    with open(root / "input.txt", "w") as out:
        for _ in range(200):
            out.write(",".join(str(random.randint(-500, 500)) for _ in range(5)) + "\n")
        out.write(" ,7,, -8 ,9\n")
    words = ["alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta"]
    with open(root / "words.txt", "w") as out:
        for _ in range(300):
            out.write(" ".join(random.choice(words) for _ in range(6)) + "\n")


def build(root):
    built = {}
    fixtures(root)
    for name in PROGRAMS:
        default = root / ("ail-" + name)
        strict = root / ("ail-strict-" + name)
        got = run([sys.executable, "-B", str(AIL), "compile", str(HERE / (name + ".py")), "-o", str(default)])
        got_strict = run([sys.executable, "-B", str(AIL), "compile", "--strict", str(HERE / (name + ".py")),
                          "-o", str(strict)])
        built["ail/" + name] = (default, got)
        if got_strict.returncode == 0:
            built["ail-strict/" + name] = (strict, got_strict)
        cbin = root / ("c-" + name)
        built["c/" + name] = (cbin, run(["gcc", "-O2", "-o", str(cbin), str(HERE / (name + ".c"))]))
    for src in sorted((REPO / "lab" / "compare" / "src").glob("*/main.rs")):
        out = root / ("rust-" + src.parent.name)
        built["rust/" + src.parent.name] = (out, run(
            ["rustc", "-C", "opt-level=3", "--edition=2021", "-o", str(out), str(src)]))
    return built


def outputs(root, binaries):
    """Run each binary on its fixture and return the stdout hash, for the before/after check."""
    import hashlib
    got = {}
    for label, path in binaries.items():
        name = label.rsplit("/", 1)[-1]
        data = b""
        fixture = STDIN.get(name)
        if fixture:
            data = (root / fixture).read_bytes()
        result = subprocess.run([str(path)], input=data, capture_output=True)
        got[label] = {"stdout": hashlib.sha256(result.stdout).hexdigest(),
                      "bytes": len(result.stdout), "exit": result.returncode}
    return got


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json")
    parser.add_argument("--table", action="store_true")
    args = parser.parse_args()
    root = Path(tempfile.mkdtemp(prefix="hardening-"))
    try:
        built = build(root)
        ok = {label: path for label, (path, got) in built.items() if got.returncode == 0}
        failures = {label: got.stderr.strip()[-200:] for label, (_, got) in built.items() if got.returncode != 0}
        rows = [json.loads(line) for line in run([sys.executable, str(CHECK), *map(str, ok.values())]).stdout.splitlines()]
        by_path = {row["path"]: row for row in rows}
        for label, path in sorted(ok.items()):
            row = dict(by_path[str(path)])
            row["label"] = label
            rows[rows.index(by_path[str(path)])] = row
        report = {
            "gcc": run(["gcc", "--version"]).stdout.splitlines()[0],
            "readelf": run(["readelf", "--version"]).stdout.splitlines()[0],
            "rows": [r for r in rows if "label" in r],
            "outputs": outputs(root, ok),
            "failures": failures,
        }
        text = json.dumps(report, indent=1)
        if args.json:
            Path(args.json).write_text(text + "\n")
        if args.table:
            print("| binary | pie | nx | relro | canary | fortify | stripped | bytes |")
            print("|---|---|---|---|---|---|---|---|")
            for row in report["rows"]:
                print("| `%s` | %s | %s | %s | %s | %d | %s | %d |" % (
                    row["label"], row["pie"], row["nx"], row["relro"], row["canary"],
                    row["fortify"], row["stripped"], row["size"]))
        else:
            print(text)
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()
