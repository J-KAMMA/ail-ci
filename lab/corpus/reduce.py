#!/usr/bin/env python3
"""Shrink a DIFF or crash finding by deleting lines (ddmin) while the same symptom remains.

    python3 reduce.py --ail /path/to/ail_chatgpt.py findings/<dir> [--mode default|ir]

Writes findings/min/<dir>/{prog.py,input.txt,cpython.stdout,ail.stdout,ail.stderr,info.json}. The symptom
is: CPython exits 0 or 1 and prints X, while AIL either fails to build with the same message class (crash)
or builds and differs in the same way (stderr first line for a runtime failure, else a plain stdout
difference). Runs one process at a time.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run(cmd, inp=b"", env=None, timeout=20):
    try:
        r = subprocess.run(cmd, capture_output=True, input=inp, env=env, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return None, b"", b""


def sig_line(b):
    lines = [l for l in b.decode("utf-8", "replace").strip().splitlines() if l.strip()]
    errs = [l for l in lines if re.search(r"error|Error", l)]
    s = errs[0] if errs else (lines[-1] if lines else "")
    s = re.sub(r"^.*?(error:|Error:)", r"\1", s)
    s = re.sub(r"/tmp/\S*prog\.\w+:\d+(:\d+)?:?", "", s)
    s = re.sub(r"\d+", "N", s)
    return s[:90]


class Reducer:
    def __init__(self, ail, mode, workdir):
        self.ail = ail
        self.env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONHASHSEED="0")
        self.env.pop("AIL_IR", None)
        if mode == "ir":
            self.env["AIL_IR"] = "1"
        self.work = Path(workdir)
        self.tests = 0

    def outcome(self, src, inp):
        """Return a symptom signature or None when the pair shows no (DIFF/crash) symptom."""
        self.tests += 1
        (self.work / "p.py").write_text(src, encoding="utf-8")
        (self.work / "p.ail").write_text(src, encoding="utf-8")
        c = run([sys.executable, str(self.work / "p.py")], inp, self.env)
        if c[0] is None or c[0] != 0 or not c[1]:
            return None
        exe = self.work / "exe"
        if exe.exists():
            exe.unlink()
        r = run([sys.executable, "-B", self.ail, "compile", str(self.work / "p.ail"), "--syntax", "python", "-o", str(exe)], b"", self.env, 240)
        if r[0] == 3:
            return None
        if r[0] != 0:
            return "crash:" + sig_line(r[2] or r[1])
        a = run([str(exe)], inp, self.env)
        if a[0] is None:
            return None
        if a[0] == 0 and a[1] == c[1]:
            return None
        if a[0] == 1 and (b"above U+FFFF" in a[2] or b"verflow" in a[2]):
            return None
        if a[0] != 0:
            return "rc%s:%s" % (a[0], sig_line(a[2]))
        return "outdiff"

    def ddmin(self, items, test):
        n = 2
        while len(items) >= 2:
            size = max(1, len(items) // n)
            chunks = [items[i:i + size] for i in range(0, len(items), size)]
            reduced = False
            for i in range(len(chunks)):
                cand = [x for j, ch in enumerate(chunks) if j != i for x in ch]
                if cand and test(cand):
                    items, n, reduced = cand, max(n - 1, 2), True
                    break
            if not reduced:
                if n >= len(items):
                    break
                n = min(len(items), n * 2)
        return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ail", required=True)
    ap.add_argument("--mode", default="default")
    ap.add_argument("dir")
    a = ap.parse_args()
    d = Path(a.dir)
    src = (d / "prog.py").read_text(encoding="utf-8")
    inp = (d / "input.txt").read_text(encoding="utf-8").encode("utf-8")
    with tempfile.TemporaryDirectory(prefix="reduce-") as tmp:
        R = Reducer(a.ail, a.mode, tmp)
        want = R.outcome(src, inp)
        if want is None:
            print("no symptom to reduce")
            return 1
        print("symptom:", want)
        lines = src.splitlines(keepends=True)
        lines = R.ddmin(lines, lambda c: R.outcome("".join(c), inp) == want)
        src2 = "".join(lines)
        ilines = inp.decode("utf-8").splitlines(keepends=True)
        ilines = R.ddmin(ilines, lambda c: R.outcome(src2, "".join(c).encode("utf-8")) == want)
        inp2 = "".join(ilines).encode("utf-8")
        assert R.outcome(src2, inp2) == want
        out = d.parent / "min" / d.name
        out.mkdir(parents=True, exist_ok=True)
        (out / "prog.py").write_text(src2, encoding="utf-8")
        (out / "input.txt").write_bytes(inp2)
        c = run([sys.executable, str(Path(tmp) / "p.py")], inp2, R.env)
        (out / "cpython.stdout").write_bytes(c[1])
        a_ = run([str(Path(tmp) / "exe")], inp2, R.env) if (Path(tmp) / "exe").exists() else (None, b"", b"")
        (out / "ail.stdout").write_bytes(a_[1])
        (out / "ail.stderr").write_bytes(a_[2])
        (out / "info.json").write_text(json.dumps({"symptom": want, "mode": a.mode, "tests": R.tests, "source": d.name}, indent=1), encoding="utf-8")
        (out / "reproduce.sh").write_text(
            "#!/bin/sh\n# from this directory; AIL=/path/to/ail_chatgpt.py\ncp prog.py prog.ail\n%spython3 \"$AIL\" compile prog.ail --syntax python -o prog_ail && ./prog_ail < input.txt\n"
            "python3 prog.py < input.txt\n" % ("AIL_IR=1 " if a.mode == "ir" else ""), encoding="utf-8")
        print("reduced to %d lines, %d input lines, %d tests -> %s" % (len(lines), len(ilines), R.tests, out))
        print(src2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
