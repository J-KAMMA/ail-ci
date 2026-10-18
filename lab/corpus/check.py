#!/usr/bin/env python3
"""Differential check of the generated programs: CPython 3.12 (oracle) versus AIL, default and AIL_IR=1.

    python3 check.py --ail /path/to/ail_chatgpt.py [--models a,b] [--modes default,ir] [--budget SECONDS]

Everything runs one process at a time. For every programs/<model>/tNNN.py the program is compiled once per
mode and run on tasks/tNNN/in0..in2.txt. Results are appended to results/results.jsonl (one record per
program x mode x input; a refused compile is one record with input = -1). Finished (model, task, mode)
triples are skipped on a re-run. DIFF, crash and timeout records get a directory under findings/.

Classes (as in lab/fuzz/run.py):
  same       stdout and exit code equal
  refused    AIL named a compile-time refusal (compiler exit 3)
  overflow   AIL raised OverflowError where CPython grew a big int; declared 64-bit int, stdout is a prefix
  limit      AIL stopped on a character above U+FFFF (declared limit of the 16-bit string runtime), stdout a prefix
  DIFF       a silent difference in stdout or exit code (a bug)
  crash      the compiler failed other than by refusal, or the binary died on a signal (a bug)
  timeout    the compiled program (or compiler) hit the time limit
  skipped    CPython itself timed out, was nondeterministic across hash seeds, or printed too much
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import re
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODES = {"default": {}, "ir": {"AIL_IR": "1"}}
CAP = 1 << 20


def run_proc(cmd, timeout, env=None, cwd=None, stdin=b""):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, env=env, cwd=cwd, input=stdin)
        return r.returncode, r.stdout, r.stderr, False
    except subprocess.TimeoutExpired as e:
        return None, e.stdout or b"", e.stderr or b"", True


def scrub(s):
    return re.sub(r"/(home|Users|mnt/c/Users)/[^/\s]+/", "/home/user/", s)


def text(b):
    return scrub(b[:CAP].decode("utf-8", "replace"))


def first_diff(a, b):
    al, bl = a.splitlines(), b.splitlines()
    for i in range(max(len(al), len(bl))):
        x = al[i] if i < len(al) else "<end>"
        y = bl[i] if i < len(bl) else "<end>"
        if x != y:
            return "line %d: cpython=%r ail=%r" % (i + 1, x[:80], y[:80])
    return "no line difference"


def classify(cpy, ail):
    c_rc, c_out, c_err, _ = cpy
    a_rc, a_out, a_err, a_to = ail
    if a_to:
        return "timeout", "run timed out"
    if a_rc is not None and (a_rc < 0 or a_rc >= 128):
        return "crash", "binary died with status %d" % a_rc
    if a_rc == c_rc and a_out == c_out:
        return "same", ""
    if (((a_rc == 1) or (a_rc == 3 and b"limit: int_overflow" in a_err)) and
            (b"OverflowError" in a_err or b"overflow" in a_err.lower()) and c_out.startswith(a_out)):
        return "overflow", "AIL OverflowError, CPython rc=%s" % c_rc
    if a_rc == 1 and b"above U+FFFF" in a_err and c_out.startswith(a_out):
        return "limit", "declared: non-BMP character on stdin (16-bit runtime)"
    if a_rc != c_rc:
        return "DIFF", "exit code cpython=%s ail=%s; %s" % (c_rc, a_rc, first_diff(text(c_out), text(a_out)))
    return "DIFF", first_diff(text(c_out), text(a_out))


def save_finding(root, key, rec, src, inp, cpy, ail, cmsg, mode):
    d = root / "findings" / key
    d.mkdir(parents=True, exist_ok=True)
    (d / "prog.py").write_text(src, encoding="utf-8")
    (d / "input.txt").write_text(inp, encoding="utf-8")
    (d / "cpython.stdout").write_text(text(cpy[1]), encoding="utf-8")
    (d / "cpython.stderr").write_text(text(cpy[2]), encoding="utf-8")
    if ail:
        (d / "ail.stdout").write_text(text(ail[1]), encoding="utf-8")
        (d / "ail.stderr").write_text(text(ail[2]), encoding="utf-8")
    else:
        (d / "compile.stderr").write_text(text(cmsg), encoding="utf-8")
    (d / "info.json").write_text(json.dumps(rec, indent=1), encoding="utf-8")
    (d / "reproduce.sh").write_text(
        "#!/bin/sh\n# from this directory; AIL=/path/to/ail_chatgpt.py\ncp prog.py prog.ail\n%spython3 \"$AIL\" compile prog.ail --syntax python -o prog_ail && ./prog_ail < input.txt\n"
        "python3 prog.py < input.txt\n" % ("AIL_IR=1 " if mode == "ir" else ""), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ail", required=True)
    ap.add_argument("--models", default="")
    ap.add_argument("--modes", default="default,ir")
    ap.add_argument("--timeout", type=float, default=10)
    ap.add_argument("--compile-timeout", type=float, default=240)
    ap.add_argument("--budget", type=float, default=0)
    ap.add_argument("--out", default=str(HERE / "results"))
    ap.add_argument("--python", default=sys.executable)
    a = ap.parse_args()
    modes = a.modes.split(",")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    resf = out / "results.jsonl"
    done = set()
    if resf.exists():
        for line in resf.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            done.add((r["model"], r["task"], r["mode"], r.get("final", False)))
    finished = {(m, t, md) for (m, t, md, f) in done if f}
    models = a.models.split(",") if a.models else sorted(p.name for p in (HERE / "programs").iterdir() if p.is_dir())
    t0 = time.time()
    tmp = Path(tempfile.mkdtemp(prefix="corpus-"))
    base_env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONHASHSEED="0")
    base_env.pop("AIL_IR", None)
    with open(resf, "a", encoding="utf-8") as jl:
        def emit(rec):
            for key in ("reason", "detail"):
                if key in rec:
                    rec[key] = scrub(rec[key])
            jl.write(json.dumps(rec, ensure_ascii=False) + "\n")
            jl.flush()
        for model in models:
            for prog in sorted((HERE / "programs" / model).glob("t*.py")):
                tid = prog.stem
                if all((model, tid, md) in finished for md in modes):
                    continue
                if a.budget and time.time() - t0 > a.budget:
                    shutil.rmtree(tmp, ignore_errors=True)
                    return
                src = prog.read_text(encoding="utf-8")
                work = tmp / (model + "-" + tid)
                work.mkdir(exist_ok=True)
                (work / "prog.py").write_text(src, encoding="utf-8")
                (work / "prog.ail").write_text(src, encoding="utf-8")
                inputs = [(HERE / "tasks" / tid / ("in%d.txt" % k)).read_bytes() for k in range(3)]
                # oracle: CPython 3.12, two hash seeds; differing outputs mean the program is nondeterministic
                oracle = []
                for k, inp in enumerate(inputs):
                    r1 = run_proc([a.python, str(work / "prog.py")], a.timeout, env=base_env, stdin=inp)
                    r2 = run_proc([a.python, str(work / "prog.py")], a.timeout, env=dict(base_env, PYTHONHASHSEED="1"), stdin=inp)
                    skip = None
                    if r1[3]:
                        skip = "cpython timeout"
                    elif len(r1[1]) > CAP:
                        skip = "oversized output"
                    elif (r1[0], r1[1]) != (r2[0], r2[1]):
                        skip = "nondeterministic (hash seed)"
                    oracle.append((r1, skip))
                cpy_failed_all = all(o[0][0] != 0 for o in oracle)
                for mode in modes:
                    if (model, tid, mode) in finished:
                        continue
                    menv = dict(base_env, **MODES[mode])
                    exe = work / ("exe-" + mode)
                    t1 = time.time()
                    crc, cout, cerr, cto = run_proc(
                        [a.python, "-B", a.ail, "compile", str(work / "prog.ail"), "--syntax", "python", "-o", str(exe)],
                        a.compile_timeout, env=menv)
                    meta = {"model": model, "task": tid, "mode": mode, "cpython_failed_all": cpy_failed_all}
                    if cto or crc != 0:
                        msg = (cerr + b"\n" + cout).decode("utf-8", "replace").strip().splitlines()
                        if cto:
                            rec = dict(meta, input=-1, cls="timeout", reason="compiler timed out")
                        elif crc == 3:
                            subs = [l for l in msg if "not in the subset" in l or "refused" in l]
                            rec = dict(meta, input=-1, cls="refused", reason=(subs[0] if subs else (msg[-1] if msg else ""))[:400],
                                       detail="\n".join(msg[-6:])[:1200])
                        else:
                            errs = [l for l in msg if "error" in l.lower()] or msg or [""]
                            rec = dict(meta, input=-1, cls="crash", reason="compiler rc=%s: %s" % (crc, errs[0].split("program.c:")[-1][:200]))
                            save_finding(out.parent, "%s-%s-%s-compile" % (model, tid, mode), rec, src, inputs[0].decode("utf-8", "replace"),
                                         oracle[0][0], None, cerr + cout, mode)
                        rec["final"] = True
                        rec["ms"] = int((time.time() - t1) * 1000)
                        emit(rec)
                        continue
                    for k, inp in enumerate(inputs):
                        cpy, skip = oracle[k]
                        rec = dict(meta, input=k)
                        if skip:
                            rec.update(cls="skipped", reason=skip)
                        else:
                            ail = run_proc([str(exe)], a.timeout, env=menv, stdin=inp)
                            rec["cls"], rec["reason"] = classify(cpy, ail)
                            rec["cpython_rc"], rec["ail_rc"] = cpy[0], ail[0]
                            if rec["cls"] in ("DIFF", "crash", "timeout"):
                                save_finding(out.parent, "%s-%s-%s-in%d-%s" % (model, tid, mode, k, rec["cls"]), rec, src,
                                             inp.decode("utf-8", "replace"), cpy, ail, b"", mode)
                        rec["final"] = k == 2
                        rec["ms"] = int((time.time() - t1) * 1000)
                        emit(rec)
                shutil.rmtree(work, ignore_errors=True)
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
