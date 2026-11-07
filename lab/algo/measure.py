"""Run each lab/algo/cases/pN_{before,after}.py, compare stdout bytes and time the runs.

    python3 lab/algo/measure.py [--runs 3]

Prints one Markdown row per rule.  The pair is also linted, so a fix that did not remove the hit is
visible.
"""
import argparse
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "packaging"))
from ail_lang import perflint  # noqa: E402


def one_run(path, runs):
    done = subprocess.run([sys.executable, "-X", "utf8", "-B", str(path)], capture_output=True,
                          timeout=300)
    if done.returncode:
        raise SystemExit("%s exited %d: %s" % (path, done.returncode,
                                               done.stderr.decode("utf-8", "replace")))
    return done.stdout


def timed(path, runs):
    one_run(path, runs)
    times = []
    for _ in range(runs):
        started = time.perf_counter()
        output = one_run(path, runs)
        times.append(time.perf_counter() - started)
    return output, statistics.median(times)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()
    print("| rule | before s | after s | speed-up | output identical | before hit | after hit |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for number in range(1, 7):
        before = HERE / "cases" / ("p%d_before.py" % number)
        after = HERE / "cases" / ("p%d_after.py" % number)
        before_out, before_s = timed(before, args.runs)
        after_out, after_s = timed(after, args.runs)
        before_hits = [hit["rule"] for hit in perflint.lint_file(before)]
        after_hits = [hit["rule"] for hit in perflint.lint_file(after)]
        print("| P%d | %.3f | %.3f | %.1fx | %s | %s | %s |" % (
            number, before_s, after_s, before_s / after_s if after_s else float("inf"),
            "yes" if before_out == after_out else "NO",
            ",".join(before_hits) or "-", ",".join(after_hits) or "-"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
