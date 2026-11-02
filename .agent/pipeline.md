# job job-rbprog20-11021830  started 2026-11-02T09:33:26Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed as `0ee1226` on `job-rbprog20-11021830`.

- Re-applied prog20: tuple-key `min`/`max` lowering (kept the tree's lexicographic component implementation, added a direct dict walk so str keys keep their kind), nested-tuple `enumerate` for both tuple-instance and `srowtypes` row lists, plus `test_ail_prog20`, its `tests.d` registration, DEVLOG entry, and `lab/progfix/prog20.md`.
- `python3 tools/diff_ids.py` is absent from this tree; `tools/update_manifest.py` ran and `--check` returns 0.
- Required tests on the final commit: 64 tests, 1 skipped, all pass (`test_ail_prog20`, `test_ail_tuples`, `test_ail_bugs7`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`); `test_ail_prog5` (7) and `test_ail_prog10` (2) also pass.
- Probes, all matching CPython on both `cmp.sh` builds: `p_tuplekey.py`, `p_tuplekey_edges.py`, `p_enum_tuple.py`, `p_enum_append.py`, `p_min_empty.py`. The first four plus `p_min_empty` build on the typed path; `p_tuplekey_edges.py` falls back to the general path.
[cost $0.0000, opencode tokens {"total": 8796060, "input": 321433, "output": 21025, "reasoning": 24034, "cache.write": 0, "cache.read": 8429568}]
    tool time: bash 24.5 min
        724s bash   rm -f /tmp/test_rc.txt run2() { for t in "$@"; do (cd AIL_CURRENT && python3 "test_$t.py" > "/tmp/test_$t.log"
        280s bash   rm -f /tmp/test_rc_final.txt run2() { for t in "$@"; do (cd AIL_CURRENT && python3 "test_$t.py" > "/tmp/testf_
         39s bash   python3 - <<'PY' from pathlib import Path p=Path('/tmp/probes/p_tuplekey.py') s=p.read_text() s=s.replace(''' 
         38s bash   mv /tmp/probes/p_tuplekey.py /tmp/probes/p_tuplekey_edges.py python3 - <<'PY' import sys sys.path.insert(0, 'A
         33s bash   python3 - <<'PY' from pathlib import Path p=Path('/tmp/probes/p_tuplekey.py') s=p.read_text() s=s.replace('''d
         30s bash   for p in /tmp/probes/p_tuplekey.py /tmp/probes/p_tuplekey_edges.py /tmp/probes/p_enum_tuple.py /tmp/probes/p_e
         29s bash   for p in /tmp/probes/p_tuplekey.py /tmp/probes/p_enum_tuple.py /tmp/probes/p_enum_append.py; do echo "===== $p
         21s bash   for p in /tmp/probes/p_tuplekey.py /tmp/probes/p_enum_tuple.py /tmp/probes/p_enum_append.py; do d=$(mktemp -d 

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Change**: re-applies prog20: `iterlower.py` adds a direct dict walk for tuple-returning `min`/`max` keys (keeping the tree's lexicographic sequence path), and `pyfunc.py` adds nested-tuple `enumerate` targets, plus `test_ail_prog20`, its `tests.d` entry, `lab/progfix/prog20.md`, manifest rows and DEVLOG. This matches the report, except one unintended DEVLOG line.

**Probes** (all under `/tmp/rprobes/`, both `cmp.sh` builds unless noted):
- `p_tk1`, `p_tk3`, `p_tk5`, `p_tk6`: tuple-key dict min/max, ties, 1/3 fields, int keys, empty + default, near-int64, INT64_MIN. `p_tk3`/`p_tk5` typed, match CPython.
- `p_tk2`, `p_tk7`: invalid/typed-refused shapes fall to the general path; match CPython.
- `p_enum1`, `p_enum2`, `p_enum_srow2`, `p_enum_three`, `p_enum_one`, `p_enum_call`, `p_enum_dup`, `p_enum_live`, `p_enum_big`, `p_enum_rebind_src`, `p_enum_olist_rebind_src`, `p_enum_srow_live`: starts 1/0/negative/large, empty, rebinding index/start/source, append during iteration, 1/2/3 fields, call source; typed where expected, all match CPython.
- `p_enum_dup_str`: duplicate index/str field is refused by name and matches via the general path.
- `p_tk_seq_typed` and `p_nonfeature`: generated C is byte-identical to `/tmp/base` (only path metadata in `native_report.json` differs).
- Worker's five `/tmp/probes/` all build and match CPython on both builds.

**Claims**: commit/branch verified; diff contents verified; `tools/diff_ids.py` absent verified; `update_manifest.py --check` returns 0 verified; `test_ail_prog20` + `test_ail_safetynet` pass (2 modules, 0 failed). `test_ail_tuples`, `test_ail_bugs7`, `test_ail_files`, `test_ail_corpus_findings3`, and the worker's `test_ail_prog5`/`test_ail_prog10` runs were not repeated.

**Pre-existing**: `p_tk6` (`-INT64_MIN` key field) raises AIL's int64 overflow instead of CPython's arbitrary-precision result on both HEAD and `/tmp/base`; identical on base, not caused by this change.

**Unverified**: the `ctx.srowtypes` branch of `_for_enumerate_start`; in this tree the earlier lowering pass rewrites the nested target and the srow marker returned `{}` in the actual pipeline, so I could not construct a program that reaches it.

**Defect**
1. `DEVLOG.md:34-36`: the new DEVLOG entry is followed by an unintended duplicate, bodyless `## 2026-11-01 -- tcc dev-build measurement...` heading (the real entry is at `DEVLOG.md:223`), and there is no blank line between the new entry and that duplicate. Expected: the prog20 entry, a blank line, then the existing `## 2026-11-01 -- prog5 ...`; actual: an orphan duplicate tcc heading was added. This violates “change nothing else”.

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 7764431, "input": 358953, "output": 17477, "reasoning": 35425, "cache.write": 0, "cache.read": 7352576}]
    tool time: bash 5.3 min
        185s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_prog20 test_ail_safetynet 2>&1 | tail -20; date
         26s bash   for p in p_tuplekey p_enum_tuple; do (bash ~/tools/cmp.sh /tmp/probes/$p.py /home/runner/work/_temp/w2 > /tmp/
         19s bash   cat > /tmp/rprobes/p_tk7.py <<'PY' def main() -> None:     d: dict[str, int] = {"b": 2, "a": 1}     print(min(
         13s bash   d=$(mktemp -d /tmp/typedXXXX); for p in p_tk1 p_tk2 p_enum1 p_enum2 p_enum_edge p_nonfeature; do cp /tmp/rprob
         10s bash   cat > /tmp/rprobes/p_enum_dup_str.py <<'PY' def main() -> None:     rows = [("p", 1), ("q", 2)]     for x, (x,
          9s bash   python3 - <<'PY' from pathlib import Path p=Path('/tmp/rprobes/p_enum_srow.py') s=p.read_text() s=s.replace(''
          9s bash   cat > /tmp/rprobes/p_tk3.py <<'PY' def best(d: dict[str, int]) -> str:     return min(d, key=lambda c: (-d[c],
          8s bash   for p in p_tk1 p_tk2; do (bash ~/tools/cmp.sh /tmp/rprobes/$p.py /home/runner/work/_temp/w2 > /tmp/rprobes/$p.

## worker report 1
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Fixed the sole defect and committed as `27d9506` (only `DEVLOG.md` changed: removed the orphan duplicate tcc heading and restored the blank line).

- Probes: 57 run via `cmp.sh`; all prog20-relevant probes (tuple-key min/max, enumerate tuple targets, edges, aliasing, typed/general) match CPython on both builds. The 14 non-matching logs are stale unrelated Fraction/Decimal/enum probes or the known pre-existing `p_tk6` int64 overflow; `p_tk_v1/v2/v6/v7` were confirmed identical on `/tmp/base`.
- Tests on final commit: `test_ail_prog20`, `test_ail_tuples`, `test_ail_bugs7`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 6 modules, 0 failed.
- `tools/diff_ids.py` absent; `tools/update_manifest.py --check` exits 0.
[cost $0.0082, opencode tokens {"total": 272986, "input": 31000, "output": 2009, "reasoning": 2665, "cache.write": 0, "cache.read": 237312}]
    tool time: bash 21.9 min, edit 0.0 min
        746s bash   mkdir -p /tmp/probe_results2; cd /home/runner/work/_temp/w2; printf '%s\n' /tmp/probes/*.py /tmp/rprobes/*.py 
        538s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_prog20 test_ail_tuple
         31s bash   for p in p_tk_v1 p_tk_v2 p_tk_v6 p_tk_v7; do echo "=== base $p"; bash ~/tools/cmp.sh /tmp/probes/$p.py /tmp/ba
          1s bash   cd /home/runner/work/_temp/w2 && test -f tools/diff_ids.py && python3 tools/diff_ids.py || echo "diff_ids.py a
          0s bash   cd /home/runner/work/_temp/w2 && git status && git log --oneline -5
          0s bash   cd /home/runner/work/_temp/w2 && git show --stat --oneline HEAD && echo --- && sed -n '33,38p' DEVLOG.md && ec
          0s bash   cd /home/runner/work/_temp/w2 && git add DEVLOG.md && git commit -m "job rbprog20: remove duplicate DEVLOG hea
          0s bash   cd /home/runner/work/_temp/w2 && git show --stat --oneline HEAD && echo --- && ls tools/diff_ids.py 2>&1; ls A

## review 1
[model opencode-go/deepseek-v4.1-flash]
**Review of `work..HEAD` (0ee1226 + 27d9506)**

What the change really does: re-applies prog20 — adds a dict-source tuple-key `min`/`max` lowering in `iterlower.keyed` (using the tree's existing `apply_components`) and nested-tuple `enumerate` targets in `pyfunc.py` (olist tuple instances and `srowtypes`), plus `test_ail_prog20`, its `tests.d` registration, `lab/progfix/prog20.md`, DEVLOG and manifest. The `pyfunc.py` hunks are byte-identical to the accepted job; the `iterlower.py` dict branch is a rewrite on top of the tree's newer `apply_components` (short-circuits lexicographically, first tie wins), semantically equivalent. 27d9506 indeed only removes the orphan duplicate tcc DEVLOG heading.

Probes in `/tmp/rprobes` via `cmp.sh` (both `g` and `d` builds):
- `r_dictkey`, `r_dictkey_order`, `r_seqkey`: dict/list tuple keys, ties, negatives, 3 fields, `key=d.get`, default, empty/ValueError, arg/list-item/attribute/dict-value — same stdout/exit as CPython.
- `r_enum_tuple2`, `r_enum_srow`: nested tuple target over tuple list/slice/append/argument and split-row lists, start 1/0/negative/rebound, index/field rebinding, empty, continue/else — same stdout/exit.
- `r_dupname`, `r_dictmut`, `r_listmut`, `r_enum_big`: duplicate names, dict/list mutation during iteration, near-int64 start — same stdout/exit.
- `r_plain` (no feature): `program.c` from `--debug-dir` is byte-identical to `/tmp/base` (report JSON differs only in temp paths).
- `r_posonly`: named compile refusal on both builds (acceptable).
- `g05_006`, `g18_002`: general path on base, typed on HEAD; stdout/exit match CPython.

Tests on HEAD (`par_check.py -j 2`): `test_ail_prog20` ok, `test_ail_safetynet` ok, `test_ail_tuples` ok, `test_ail_bugs7` ok — 0 failed. `update_manifest.py --check` exits 0; `tools/diff_ids.py` is absent as reported.

Claims: final commit only DEVLOG — verified. Manifest check / missing `diff_ids.py` — verified. g05_006/g18_002 typed — verified. 6-module test claim — 4 verified, `test_ail_files`/`test_ail_corpus_findings3` not re-run. “57 probes” claim — unverified (own probes used). Report only describes the last commit, not the reapply in 0ee1226 (incomplete, not false).

Pre-existing: `r_dictkey2`/its `full.py` variant hangs the compiler >150 s on **both** HEAD and `/tmp/base`; identical on base, so not caused by this change.

Unverified: `p_tk6` int64-overflow claim; speed — `tools/icount.c` builds but `perf_event_open` is permission-denied here.

VERDICT: ACCEPT
[cost $0.0521, opencode tokens {"total": 2269575, "input": 182853, "output": 11800, "reasoning": 19114, "cache.write": 0, "cache.read": 2055808}]
    tool time: bash 29.0 min
        400s bash   cd /tmp/iso && rm -f e_full_h e_full_b && echo "HEAD"; timeout 200 env AIL_NO_CACHE=1 AIL_QUIET_FALLBACK=1 pyt
        300s bash   cd /tmp/rprobes && cat > r_dictkey2.py <<'PY' def main() -> None:     di: dict[int, int] = {3: 9, 1: 9, 2: 4} 
        228s bash   date; cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pro
        211s bash   date; cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_tup
        150s bash   cd /tmp/iso && cp /tmp/rprobes/r_dictkey2.py full.py && rm -f e_full_h e_full_b && ( /usr/bin/time -f 'head %e
         90s bash   cd /tmp && rm -rf hchk && mkdir hchk && cp /tmp/rprobes/r_dictkey2.py hchk/p.ail && cd hchk && timeout 90 env 
         59s bash   cd /tmp/tq && for g in g05_006 g18_002; do cp /home/runner/work/_temp/w2/lab/census/programs/gdev/$g.py p.ail;
         57s bash   cd /tmp && rm -rf spd && mkdir -p spd/head spd/base && for g in g05_006 g18_002; do for w in head base; do if 

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-02T12:37:48Z
