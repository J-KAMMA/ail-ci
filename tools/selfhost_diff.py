#!/usr/bin/env python3
"""The self-hosting differential runner: a reference and a candidate over one path list.

    python3 tools/selfhost_diff.py --ref "python3 selfhost/ref/tok_ref.py" \
        --cand "python3 selfhost/drv/tok_drv.py" --list LIST [--jobs 2] [--show 3] [--json OUT]

Each command is run with a list file appended as its last argument and must print, per input,
a line ``== PATH`` followed by that input's dump; a dump that is the single line
``!! refused: MESSAGE`` counts as refused.  ``--jobs N`` splits the list into N parts and runs up to
N commands at a time (reference and candidate are timed separately).  The result counts files whose
dumps are byte-identical, different, refused by the candidate, refused by the reference, or missing
from an output.  ``CORPUS.txt`` style lines (``sha256  path``) are accepted in LIST.

Exit status: 0 when no file is different or missing, 1 otherwise.
"""
import argparse
import json
import os
import shlex
import subprocess
import sys
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_list(path):
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            parts = line.split("  ", 1)
            out.append(parts[1] if len(parts) == 2 and len(parts[0]) == 64 else line)
    return out


def run_side(cmd, paths, jobs, tmp, tag, env):
    """Run cmd over paths in `jobs` parts.  Returns (dumps by path, seconds, failures).

    When a run exits non-zero, the first path of its part with no dump is the one it stopped on:
    that path gets the dump ``!! refused: exit N: <last stderr line>`` and the rest of the part
    (with the last dumped path, whose dump may be cut short) is run again."""
    dumps = {}
    fails = []
    secs = 0.0
    todo = list(paths)
    rnd = 0
    while todo:
        d, s, f, parts = run_once(cmd, todo, jobs, tmp, "%s%d_" % (tag, rnd), env)
        secs += s
        rnd += 1
        todo = []
        for part, fail in zip(parts, f):
            got = [p for p in part if p in d]
            for p in got:
                dumps[p] = d[p]
            if fail is None:
                continue
            fails.append(fail)
            left = [p for p in part if p not in d]
            if not left:
                continue
            last_line = fail.strip().split("\n")[-1][:300]
            dumps[left[0]] = ("!! refused: %s\n" % last_line).encode("utf-8")
            redo = left[1:]
            if got and got[-1] == part[part.index(left[0]) - 1]:
                redo = [got[-1]] + redo
            todo += redo
    return dumps, secs, fails


def run_once(cmd, paths, jobs, tmp, tag, env):
    parts = [paths[k::jobs] for k in range(jobs)] if jobs > 1 else [paths]
    parts = [p for p in parts if p]
    procs = []
    t0 = time.perf_counter()
    for k, part in enumerate(parts):
        if not part:
            continue
        lst = os.path.join(tmp, "%s%d.list" % (tag, k))
        out = os.path.join(tmp, "%s%d.out" % (tag, k))
        with open(lst, "w", encoding="utf-8") as f:
            f.write("\n".join(part) + "\n")
        fo = open(out, "wb")
        p = subprocess.Popen(shlex.split(cmd) + [lst], stdout=fo, stderr=subprocess.PIPE, cwd=REPO, env=env)
        procs.append((p, fo, out))
    fails = []
    outs = []
    for p, fo, out in procs:
        _, err = p.communicate()
        fo.close()
        if p.returncode != 0:
            fails.append("exit %d: %s" % (p.returncode, err.decode("utf-8", "replace").strip()[-400:]))
        else:
            fails.append(None)
        outs.append(out)
    secs = time.perf_counter() - t0
    dumps = {}
    for out in outs:
        cur = None
        buf = []
        with open(out, "rb") as f:
            for line in f:
                if line.startswith(b"== "):
                    if cur is not None:
                        dumps[cur] = b"".join(buf)
                    cur = line[3:].rstrip(b"\n").decode("utf-8", "replace")
                    buf = []
                else:
                    buf.append(line)
        if cur is not None:
            dumps[cur] = b"".join(buf)
    return dumps, secs, fails, parts


def first_diff(a, b):
    la = a.split(b"\n")
    lb = b.split(b"\n")
    for k in range(max(len(la), len(lb))):
        x = la[k] if k < len(la) else b"<missing>"
        y = lb[k] if k < len(lb) else b"<missing>"
        if x != y:
            return "token %d: ref %s | cand %s" % (k + 1, x.decode("utf-8", "replace")[:160],
                                                    y.decode("utf-8", "replace")[:160])
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--cand", required=True)
    ap.add_argument("--list", required=True)
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--show", type=int, default=5)
    ap.add_argument("--json", default="")
    args = ap.parse_args()
    paths = read_list(args.list)
    env = dict(os.environ)
    src = os.path.join(REPO, "selfhost", "src")
    env["PYTHONPATH"] = src + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env.setdefault("AIL_PATH", src)
    with tempfile.TemporaryDirectory(prefix="selfhost-diff-") as tmp:
        ref, ref_s, ref_fail = run_side(args.ref, paths, args.jobs, tmp, "ref", env)
        cand, cand_s, cand_fail = run_side(args.cand, paths, args.jobs, tmp, "cand", env)
    res = {"files": len(paths), "identical": 0, "different": 0, "refused": 0, "ref_refused": 0,
           "missing": 0, "ref_seconds": round(ref_s, 3), "cand_seconds": round(cand_s, 3),
           "different_files": [], "refused_files": [], "missing_files": [],
           "ref_failures": ref_fail, "cand_failures": cand_fail}
    for p in paths:
        a = ref.get(p)
        b = cand.get(p)
        if a is None or b is None:
            res["missing"] += 1
            res["missing_files"].append(p)
            continue
        if a.startswith(b"!! refused:"):
            res["ref_refused"] += 1
        if b.startswith(b"!! refused:") and not a.startswith(b"!! refused:"):
            res["refused"] += 1
            res["refused_files"].append({"path": p, "line": b.decode("utf-8", "replace").strip()})
            continue
        if a == b:
            res["identical"] += 1
        else:
            res["different"] += 1
            res["different_files"].append({"path": p, "first": first_diff(a, b)})
    print("files %d: identical %d, different %d, refused %d (reference refused %d), missing %d"
          % (res["files"], res["identical"], res["different"], res["refused"], res["ref_refused"],
             res["missing"]))
    print("seconds: ref %.3f, cand %.3f" % (ref_s, cand_s))
    for d in res["different_files"][:args.show]:
        print("DIFF", d["path"], d["first"])
    for d in res["refused_files"][:args.show]:
        print("REFUSED", d["path"], d["line"])
    for m in res["missing_files"][:args.show]:
        print("MISSING", m)
    for f in ref_fail + cand_fail:
        print("FAIL", f)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=1)
            f.write("\n")
    return 0 if res["different"] == 0 and res["missing"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
