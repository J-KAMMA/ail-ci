#!/usr/bin/env python3
"""Summarise results/results.jsonl and programs/*/status.jsonl into RESULTS.md.

    python3 summarize.py [--out RESULTS.md]
"""
import argparse
import collections
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORDER = ["same", "refused", "overflow", "limit", "DIFF", "crash", "timeout", "skipped"]
PREC = ["crash", "DIFF", "timeout", "limit", "overflow", "same", "skipped"]  # worst first, for run-level -> program-level


def norm_reason(r):
    r = re.sub(r"^.*?prog\.ail:\d+(:\d+)?:\s*", "", r)
    r = re.sub(r"^(note|error):\s*", "", r)
    r = r.replace("not in the subset: ", "")
    r = re.split(r" -- |; | \(the general", r)[0].strip()
    r = re.sub(r"^'[^']*' is ", "'<name>' is ", r)
    r = re.sub(r"^`?[\w.\[\]]+\.(\w+)\(\)`?:", r".\1():", r)
    r = re.sub(r"\b[\w.]+\.(\w+)\(\): (an? \w+ has no method)", r".\1(): \2", r)
    r = re.sub(r"line \d+", "line N", r)
    r = re.sub(r"prog\.ail:\d+", "", r)
    return r[:140]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "RESULTS.md"))
    a = ap.parse_args()
    recs = [json.loads(l) for l in (HERE / "results" / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    for r in recs:  # records written before the "limit" class existed
        if r["cls"] == "DIFF":
            f = HERE / "findings" / ("%s-%s-%s-in%d-DIFF" % (r["model"], r["task"], r["mode"], r["input"])) / "ail.stderr"
            if f.exists() and "above U+FFFF" in f.read_text(encoding="utf-8") and r.get("ail_rc") == 1:
                r["cls"] = "limit"
    cats = {}
    for p in (HERE / "tasks").glob("t*/task.json"):
        j = json.loads(p.read_text(encoding="utf-8"))
        cats[j["id"]] = j["category"]
    L = []
    # generation
    L += ["# Corpus results", "", "## Generation", "", "| model | tasks asked | ok | empty | no code block | timeout |", "|---|---|---|---|---|---|"]
    for d in sorted((HERE / "programs").iterdir()):
        sj = d / "status.jsonl"
        if not sj.exists():
            continue
        last = {}
        for l in sj.read_text().splitlines():  # a task asked again after a service refusal counts once, by its last attempt
            j = json.loads(l)
            last[j["task"]] = j["status"]
        c = collections.Counter(last.values())
        L.append("| %s | %d | %d | %d | %d | %d |" % (d.name, sum(c.values()), c["ok"], c["empty"], c["no-code"], c["timeout"]))
    L += ["", "About 1.5 hours into generation the free tier began answering every request with the error \"free tier can only be "
          "used from within OpenCode\" (no model reply, empty stdout, in a few seconds). Those requests are recorded as `empty` "
          "here because the first run did not tell them apart; `generate.py` now records them as blocked, waits and asks again "
          "(`--redo-empty`). The block had not lifted three-plus hours later, so the counts above are what the free tier "
          "delivered: the programs of the first ~100 (glm) and ~170 (deepseek) requests, plus a handful of genuinely empty "
          "replies among them. Nothing was done to get around the block.", ""]
    # program-level
    prog = {}  # (model, task, mode) -> class
    for r in recs:
        k = (r["model"], r["task"], r["mode"])
        prog.setdefault(k, []).append(r)
    pcls = {}
    pfail = {}
    for k, rs in prog.items():
        cl = {r["cls"] for r in rs}
        if "refused" in cl:
            pcls[k] = "refused"
        else:
            pcls[k] = next(c for c in PREC if c in cl)
        pfail[k] = rs[0].get("cpython_failed_all", False)
    models = sorted({k[0] for k in pcls})
    modes = sorted({k[2] for k in pcls})
    L += ["## Programs by class (one count per program; worst class over its three inputs)", "",
          "| model | mode | programs | " + " | ".join(ORDER) + " |", "|---|---|---|" + "---|" * len(ORDER)]
    for m in models + ["all"]:
        for md in modes:
            ks = [k for k in pcls if (m == "all" or k[0] == m) and k[2] == md]
            c = collections.Counter(pcls[k] for k in ks)
            L.append("| %s | %s | %d | " % (m, md, len(ks)) + " | ".join(str(c[x]) for x in ORDER) + " |")
    L.append("")
    L += ["## Runs by class (program x input)", "", "| mode | " + " | ".join(ORDER) + " |", "|---|" + "---|" * len(ORDER)]
    for md in modes:
        c = collections.Counter(r["cls"] for r in recs if r["mode"] == md)
        L.append("| %s | " % md + " | ".join(str(c[x]) for x in ORDER) + " |")
    L.append("")
    nfail = sum(1 for k, v in pfail.items() if v and k[2] == modes[0])
    L += ["Programs for which CPython itself exits non-zero on all three inputs (a bad program or a bad input; the "
          "comparison still counts them): %d." % nfail, ""]
    # categories
    L += ["## By category (mode %s, programs of both models)" % modes[0], "",
          "| category | programs | " + " | ".join(ORDER) + " | accepted % |", "|---|---|" + "---|" * len(ORDER) + "---|"]
    bycat = collections.defaultdict(collections.Counter)
    for k, v in pcls.items():
        if k[2] == modes[0]:
            bycat[cats.get(k[1], "?")][v] += 1
    for cat in sorted(bycat):
        c = bycat[cat]
        n = sum(c.values())
        L.append("| %s | %d | " % (cat, n) + " | ".join(str(c[x]) for x in ORDER) + " | %.0f |" % (100.0 * (n - c["refused"]) / n))
    L.append("")
    # refusals
    for md in modes:
        why = collections.defaultdict(list)
        for k, rs in prog.items():
            if k[2] == md and pcls[k] == "refused":
                why[norm_reason(rs[0]["reason"])].append(k)
        L += ["## Refusal reasons, ranked (mode %s; number of programs)" % md, "", "| n | reason | example |", "|---|---|---|"]
        for reason, ks in sorted(why.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:60]:
            ex = ks[0]
            L.append("| %d | %s | %s/%s |" % (len(ks), reason.replace("|", "\\|"), ex[0], ex[1]))
        L.append("")
    # findings
    bad = [r for r in recs if r["cls"] in ("DIFF", "crash", "timeout")]
    L += ["## Findings (DIFF, crash, timeout)", ""]
    if not bad:
        L.append("None.")
    for r in sorted(bad, key=lambda r: (r["model"], r["task"], r["mode"], r["input"])):
        L.append("- %s %s [%s] input %d: **%s** %s (see `findings/`)" % (r["model"], r["task"], r["mode"], r["input"], r["cls"], r["reason"][:160]))
    L.append("")
    Path(a.out).write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L[:60]))


if __name__ == "__main__":
    main()
