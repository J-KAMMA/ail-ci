#!/usr/bin/env python3
"""Self-hosting step 0: rank the compiler modules for the AIL rewrite (measurement only).

Joins, per module of the full import graph reachable from ``compile``:

- ``lab/selfhost/deps.json`` (shdeps1): lines, layer, cycle id, eager imports;
- ``lab/profile/CTIME_FE.json`` (ctimes1): pooled module own time over the 10 compare tasks,
  and its share of the pooled cold wall;
- ``lab/selfhost/files.json`` (shfiles1): the whole-file build result and first refusal;
- ``lab/selfhost/hot.json``: the names of the module's functions among the 30 hottest;
- the module source itself: the count of ``ast.`` uses and of ``os.environ`` reads.

Rank: modules of 1500 lines or less, not marked "later", whose eager imports are all standard
library or already ranked (an import inside the module's own import cycle counts as satisfied, since a
cycle is ported as one unit); at each step the eligible module with the highest own-time share is
taken next (ties by name).  Nothing is compiled and no compiler file is read for anything but text.

    python3 tools/selfhost_port_order.py [--inputs DIR] [--out lab/selfhost/port_order.json]

``--inputs`` names a directory that holds deps.json, files.json and CTIME_FE.json when those are
not yet on the base (they live on the unmerged shdeps1/shfiles1/ctimes1 branches).
"""
import argparse
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA = "ail.selfhost_port_order/1"
MAX_LINES = 1500
LATER = ("pyfunc", "cruntime", "pyboxed2", "ail_chatgpt")
COLUMNS = ("lines", "layer", "cycle", "own_s", "own_share", "build", "first_refusal",
           "ast_uses", "environ_reads", "hot")
AST_RE = re.compile(r"\bast\.")
ENV_RE = re.compile(r"\bos\.environ\b")


def find(name, inputs, defaults):
    cands = []
    if inputs:
        cands.append(os.path.join(inputs, name))
    cands += [os.path.join(REPO, d, name) for d in defaults]
    for c in cands:
        if os.path.exists(c):
            return c
    sys.exit("missing input: %s (looked in %s)" % (name, ", ".join(cands)))


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def base_commit():
    try:
        return subprocess.check_output(["git", "-C", REPO, "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return ""


def profile_modules(ctime):
    """Pooled own seconds per profile module name, and the pooled cold wall."""
    pooled = {}
    wall = 0.0
    for r in ctime["results"]:
        view = r.get("profile_view") or r["profile"]
        for k, v in view.get("modules", {}).items():
            pooled[k] = pooled.get(k, 0.0) + v
        wall += r["plain_summary"]["wall"]["median"]
    return pooled, wall


def corpus_paths():
    """S376: 10 compare typed.py, 10 compare main.py, the first 200 sorted corpus programs, and the
    156 compiler files of the lab/selfhost/CENSUS.md scope (census.json)."""
    import glob
    def rel(ps):
        return sorted(os.path.relpath(p, REPO).replace(os.sep, "/") for p in ps)
    typed = rel(glob.glob(os.path.join(REPO, "lab/compare/src/*/typed.py")))
    mains = rel(glob.glob(os.path.join(REPO, "lab/compare/src/*/main.py")))
    progs = rel(glob.glob(os.path.join(REPO, "lab/corpus/programs/*/*.py")))[:200]
    census = [f["path"] for f in load(os.path.join(REPO, "lab/selfhost/census.json"))["files"]]
    paths = sorted(set(typed + mains + progs + census))
    return paths


def write_corpus(out):
    import hashlib
    lines = []
    for p in corpus_paths():
        with open(os.path.join(REPO, p), "rb") as f:
            lines.append("%s  %s\n" % (hashlib.sha256(f.read()).hexdigest(), p))
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.writelines(lines)
    print("wrote %d corpus entries to %s" % (len(lines), os.path.relpath(out, REPO)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", action="store_true", help="also write selfhost/CORPUS.txt (S376)")
    ap.add_argument("--inputs", default="")
    ap.add_argument("--out", default=os.path.join(REPO, "lab", "selfhost", "port_order.json"))
    args = ap.parse_args()
    if args.corpus:
        os.makedirs(os.path.join(REPO, "selfhost"), exist_ok=True)
        write_corpus(os.path.join(REPO, "selfhost", "CORPUS.txt"))

    deps_p = find("deps.json", args.inputs, ["lab/selfhost"])
    files_p = find("files.json", args.inputs, ["lab/selfhost"])
    ctime_p = find("CTIME_FE.json", args.inputs, ["lab/profile"])
    hot_p = find("hot.json", "", ["lab/selfhost"])
    deps, files, ctime, hot = load(deps_p), load(files_p), load(ctime_p), load(hot_p)

    full = deps["graphs"]["full"]
    cycle_of = {}
    for i, comp in enumerate(full["cycles"]):
        for m in comp:
            cycle_of[m] = i
    by_path = {f["path"]: f for f in files["files"]}
    hot_by_file = {}
    for h in hot["functions"]:
        hot_by_file.setdefault(h["file"], []).append(h["name"])
    pooled, wall = profile_modules(ctime)
    # profile rows use the last dotted component ("ir" for ir/ir.py, "lower" for ir/lower.py).
    short_count = {}
    for m in deps["modules"]:
        s = m["name"].split(".")[-1]
        short_count[s] = short_count.get(s, 0) + 1

    rows = {}
    for m in deps["modules"]:
        name = m["name"]
        path = m["path"]
        try:
            with open(os.path.join(REPO, path), encoding="utf-8") as f:
                text = f.read()
        except OSError:
            text = ""
        short = name.split(".")[-1]
        own = pooled.get(short, 0.0) if short_count[short] == 1 else pooled.get(name, 0.0)
        if name == "ir" or (name == "ir.ir"):
            own = pooled.get("ir", 0.0) if name == "ir.ir" else 0.0
        fr = by_path.get(path, {})
        rows[name] = {
            "module": name,
            "path": path,
            "lines": m["lines"],
            "layer": m["layer_full"],
            "cycle": cycle_of.get(name),
            "own_s": round(own, 4),
            "own_share": round(own / wall, 5) if wall else 0.0,
            "build": fr.get("result", "not in scope"),
            "first_refusal": fr.get("first_refusal", ""),
            "ast_uses": len(AST_RE.findall(text)),
            "environ_reads": len(ENV_RE.findall(text)),
            "hot": sorted(set(hot_by_file.get(path, []))),
            "eager": sorted(m["eager"]),
            "later": short in LATER and name in LATER,
        }

    ranked = []
    done = set()
    pool = {n for n, r in rows.items() if r["lines"] <= MAX_LINES and not r["later"]}
    while True:
        ok = [n for n in pool if n not in done and all(
            e in done or (rows[n]["cycle"] is not None and rows.get(e, {}).get("cycle") == rows[n]["cycle"])
            for e in rows[n]["eager"])]
        if not ok:
            break
        ok.sort(key=lambda n: (-rows[n]["own_share"], -rows[n]["own_s"], n))
        n = ok[0]
        done.add(n)
        rows[n]["rank"] = len(ranked) + 1
        ranked.append(n)
    blocked = sorted(n for n in pool if n not in done)
    later = sorted(n for n, r in rows.items() if r["later"])
    too_big = sorted(n for n, r in rows.items() if r["lines"] > MAX_LINES and not r["later"])
    fe_lines = sum(r["lines"] for r in rows.values())
    later_lines = sum(rows[n]["lines"] for n in later)
    later_own = sum(rows[n]["own_s"] for n in later)
    total_own = sum(r["own_s"] for r in rows.values())

    out = {
        "schema": SCHEMA,
        "base_commit": base_commit(),
        "inputs": {
            "deps": {"file": os.path.relpath(deps_p, REPO) if deps_p.startswith(REPO) else os.path.basename(deps_p),
                     "base_commit": deps.get("base_commit", "")},
            "files": {"file": os.path.basename(files_p), "base_commit": files.get("base", "")},
            "ctime": {"file": os.path.basename(ctime_p), "date": ctime.get("date", ""),
                      "pooled_cold_wall_s": round(wall, 4)},
            "hot": {"file": "lab/selfhost/hot.json"},
        },
        "rule": "lines <= %d, not later, eager imports all stdlib or already ranked (same-cycle imports "
                "count as satisfied); "
                "highest own-time share first, ties by name" % MAX_LINES,
        "columns": list(COLUMNS),
        "ranked": [rows[n] for n in ranked],
        "later": [rows[n] for n in later],
        "later_summary": {"modules": later, "lines": later_lines,
                          "share_of_fe_lines": round(later_lines / fe_lines, 4) if fe_lines else 0,
                          "own_s": round(later_own, 4),
                          "share_of_fe_own": round(later_own / total_own, 4) if total_own else 0},
        "over_limit": [rows[n] for n in too_big],
        "blocked": [rows[n] for n in blocked],
        "counts": {"modules": len(rows), "ranked": len(ranked), "later": len(later),
                   "over_limit": len(too_big), "blocked": len(blocked), "fe_lines": fe_lines,
                   "fe_own_s": round(total_own, 4)},
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, sort_keys=False)
        f.write("\n")
    print("ranked %d of %d modules; later %d; over %d lines %d; blocked %d"
          % (len(ranked), len(rows), len(later), MAX_LINES, len(too_big), len(blocked)))
    for r in out["ranked"][:10]:
        print("%3d %-28s %5d L%s own %.3fs %.2f%% %s" % (r["rank"], r["module"], r["lines"], r["layer"],
                                                         r["own_s"], 100 * r["own_share"], r["build"]))


if __name__ == "__main__":
    main()
