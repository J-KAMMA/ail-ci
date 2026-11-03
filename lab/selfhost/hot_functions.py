#!/usr/bin/env python3
"""Hotness of the compiler's own functions, joined with the typed-path census.

    python3 lab/selfhost/hot_functions.py --profiles /tmp/prof --out lab/selfhost/hot.json

Reads every ``*.prof`` under ``<profiles>/{parent,child}`` (``python3 -m cProfile`` output from the
three cold builds named on the command line), sums ``tottime`` per ``(file, def line, name)`` over
the builds, keeps the top ``--top`` functions that are census units (a top-level ``def``), and
joins each with its census verdict and first reason.  Nested functions and methods are counted
but not ranked, because the census gives them no verdict.
"""

from __future__ import annotations

import argparse
import collections
import json
import pstats
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CASES = ("chain_relax", "tree_fold", "tally_lang")


def _relative(filename, root):
    try:
        return str(Path(filename).resolve().relative_to(root))
    except (OSError, ValueError):
        return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--profiles", required=True)
    parser.add_argument("--census", default=str(ROOT / "lab/selfhost/census.json"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    census = json.loads(Path(args.census).read_text(encoding="utf-8"))
    units = {}
    for record in census["files"]:
        for fn in record["functions"]:
            units[(record["path"], fn["line"], fn["name"])] = fn
    scope = {record["path"] for record in census["files"]}

    totals = collections.Counter()
    per_build = collections.defaultdict(collections.Counter)
    for case in CASES:
        directory = Path(args.profiles) / "child" / case
        profiles = [Path(args.profiles) / "parent" / (case + ".prof")]
        profiles += sorted(directory.glob("*.prof")) if directory.is_dir() else []
        for profile in profiles:
            if not profile.is_file():
                continue
            stats = pstats.Stats(str(profile))
            for key, value in stats.stats.items():
                filename, line, name = key
                relative = _relative(filename, root)
                if relative is None or relative not in scope:
                    continue
                totals[(relative, line, name)] += value[2]
                per_build[case][(relative, line, name)] += value[2]

    ranked = []
    excluded = []
    for key, tottime in totals.most_common():
        record = {
            "file": key[0],
            "line": key[1],
            "name": key[2],
            "tottime": round(tottime, 4),
            "per_build": {case: round(per_build[case][key], 4) for case in CASES},
        }
        fn = units.get(key)
        if fn is None:
            excluded.append(record)
            continue
        record["verdict"] = fn["verdict"]
        record["reason"] = fn["reason"]
        ranked.append(record)
        if len(ranked) >= args.top:
            break

    hot = {
        "schema": "ail.selfhost_hot/1",
        "cases": list(CASES),
        "profiles": {
            case: sorted(str(path) for path in (Path(args.profiles) / "parent").glob(case + ".prof"))
            + sorted(str(path) for path in (Path(args.profiles) / "child" / case).glob("*.prof"))
            for case in CASES
        },
        "tottime_seconds": round(sum(totals.values()), 4),
        "functions": ranked,
        "not_units": excluded[:10],
        "not_units_total": len(excluded),
    }
    Path(args.out).write_text(json.dumps(hot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("ranked %d functions; %d hot names are nested functions or methods"
          % (len(ranked), len(excluded)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
