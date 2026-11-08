"""Run the probe under CPython with a type print after every case line.

Reads `expect.json` and `probe.py` / `general.py`, writes an instrumented copy to a temporary
directory, runs it with `python3`, and checks each printed `type(name).__name__` against the
`oracle` field. The `expected` field is what the language server's hover must show (null means it
must show nothing). Prints a summary and exits nonzero on a mismatch.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPECT = HERE / "expect.json"


def instrument(sources, cases):
    by_file = {}
    for case in cases:
        by_file.setdefault(case["file"], []).append(case)
    result = {}
    for name, text in sources.items():
        lines = text.splitlines()
        additions = {}
        for case in by_file.get(name, []):
            index = case["line"]
            if index < 0 or index >= len(lines):
                raise SystemExit("case line %d is outside %s" % (index + 1, name))
            line = lines[index]
            indent = line[:len(line) - len(line.lstrip())]
            marker = "ORACLE %s:%d %s" % (name, index + 1, case["name"])
            additions.setdefault(index, []).append(
                '%sprint(%r, type(%s).__name__)' % (indent, marker, case["name"]))
        for index in sorted(additions, reverse=True):
            lines[index + 1:index + 1] = additions[index]
        result[name] = "\n".join(lines) + "\n"
    return result


def main():
    expect = json.loads(EXPECT.read_text(encoding="utf-8"))
    sources = {name: (HERE / name).read_text(encoding="utf-8") for name in expect["files"]}
    instrumented = instrument(sources, expect["cases"])
    output = {}
    with tempfile.TemporaryDirectory(prefix="ail-hover-oracle-") as directory:
        for name, text in instrumented.items():
            (Path(directory) / name).write_text(text, encoding="utf-8")
        for name in expect["files"]:
            done = subprocess.run([sys.executable, str(Path(directory) / name)],
                                  capture_output=True, text=True, timeout=120)
            if done.returncode != 0:
                raise SystemExit("%s failed under CPython:\n%s" % (name, done.stderr))
            for line in done.stdout.splitlines():
                if line.startswith("ORACLE "):
                    marker, kind = line.rsplit(" ", 1)
                    output[marker] = kind
    wrong = 0
    shown = 0
    for case in expect["cases"]:
        marker = "ORACLE %s:%d %s" % (case["file"], case["line"] + 1, case["name"])
        actual = output.get(marker)
        if actual != case["oracle"]:
            wrong += 1
            print("MISMATCH %s: CPython says %r, expect.json says %r"
                  % (marker, actual, case["oracle"]))
        if case["expected"] is not None:
            shown += 1
    print("oracle: %d cases, %d must be shown, %d CPython mismatches"
          % (len(expect["cases"]), shown, wrong))
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main())
