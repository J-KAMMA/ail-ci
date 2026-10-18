#!/usr/bin/env python3
"""Record a hand-minimised reproduction under findings/min/<slug>/ (programs, input, both outputs).

    python3 mkmin.py --ail /path/to/ail_chatgpt.py SLUG prog.py input.txt "note" [--from-finding DIR]

Compiles in both modes and stores the outcome of each next to CPython's.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run(cmd, inp=b"", env=None):
    r = subprocess.run(cmd, capture_output=True, input=inp, env=env, timeout=300)
    return r.returncode, r.stdout, r.stderr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ail", required=True)
    ap.add_argument("--from-finding", default="")
    ap.add_argument("slug")
    ap.add_argument("prog")
    ap.add_argument("input")
    ap.add_argument("note")
    a = ap.parse_args()
    out = HERE / "findings" / "min" / a.slug
    out.mkdir(parents=True, exist_ok=True)
    src = Path(a.prog).read_bytes()
    inp = Path(a.input).read_bytes()
    (out / "prog.py").write_bytes(src)
    (out / "input.txt").write_bytes(inp)
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONHASHSEED="0")
    env.pop("AIL_IR", None)
    c = run([sys.executable, str(out / "prog.py")], inp, env)
    (out / "cpython.stdout").write_bytes(c[1])
    info = {"note": a.note, "from": a.from_finding, "cpython_rc": c[0]}
    with tempfile.TemporaryDirectory() as tmp:
        for mode in ("default", "ir"):
            menv = dict(env, **({"AIL_IR": "1"} if mode == "ir" else {}))
            (Path(tmp) / "p.ail").write_bytes(src)
            exe = Path(tmp) / ("exe-" + mode)
            r = run([sys.executable, "-B", a.ail, "compile", str(Path(tmp) / "p.ail"), "--syntax", "python", "-o", str(exe)], b"", menv)
            if r[0] != 0:
                (out / ("compile-%s.stderr" % mode)).write_bytes(r[2] + r[1])
                info[mode] = "compile rc=%s" % r[0]
                continue
            x = run([str(exe)], inp, menv)
            (out / ("ail-%s.stdout" % mode)).write_bytes(x[1])
            (out / ("ail-%s.stderr" % mode)).write_bytes(x[2])
            info[mode] = "run rc=%s, stdout %s" % (x[0], "equal" if x[1] == c[1] and x[0] == c[0] else "DIFFERS")
    (out / "info.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    (out / "reproduce.sh").write_text(
        "#!/bin/sh\n# from this directory; AIL=/path/to/ail_chatgpt.py; set AIL_IR=1 for the IR path\ncp prog.py prog.ail\n"
        "python3 \"$AIL\" compile prog.ail --syntax python -o prog_ail && ./prog_ail < input.txt\npython3 prog.py < input.txt\n", encoding="utf-8")
    print(a.slug, info)


if __name__ == "__main__":
    main()
