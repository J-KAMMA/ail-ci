# job job-std_decimal-11020505  started 2026-11-01T20:06:48Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed both review defects and committed `e538fec`.

- `Decimal(d.as_tuple())` now round-trips: `Decimal.__init__` accepts `_DecTuple` (`prelude_decimal.py:947`).
- `reversed()` now dispatches a user class's `__reversed__` on the general path. The hook is installed only for programs whose classes define it, so a class program without `__reversed__` keeps byte-identical generated C (verified against `96dee2d`).

Probes (`cmp.sh`, g + d builds):
- `dec_reversed`, `dec_reversed_user`, `dec_routes`, `dec_rev_routes`: exact match.
- `dec_roundtrip`, `dec_tuple_types`: exact match except `isinstance(t, tuple)` is `False` (documented: `_DecTuple` is a class like the namedtuple prelude); `Decimal(t)` itself matches.
- Exact-int mode: same result.
- `class_tuple`: still a named compile-time refusal, as before.

Tests on the final code: `test_ail_std_decimal`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_stdtop1`, `test_ail_bytearray_decimal`, `test_ail_dunders` — 7 modules, 0 failed. `tools/update_manifest.py --check` exits 0.
[cost $0.0000, opencode tokens {"total": 7845394, "input": 238520, "output": 13668, "reasoning": 18166, "cache.write": 0, "cache.read": 7575040}]
    tool time: bash 29.8 min, edit 0.0 min
        532s bash   python3 tools/par_check.py -j 2 test_ail_std_decimal test_ail_safetynet test_ail_files test_ail_corpus_finding
        433s bash   python3 tools/par_check.py -j 2 test_ail_safetynet test_ail_files test_ail_corpus_findings3 test_ail_stdtop1 t
        333s bash   python3 tools/par_check.py -j 2 test_ail_std_decimal 2>&1 | tail -40
        155s bash   for p in dec_roundtrip dec_reversed dec_reversed_user dec_tuple_types dec_routes dec_rev_routes; do echo "====
        120s bash   for p in dec_roundtrip dec_reversed dec_reversed_user dec_tuple_types; do echo "===== $p"; bash ~/tools/cmp.sh
         53s bash   REPO=$PWD d=$(mktemp -d /tmp/exactXXXX) for p in dec_reversed dec_roundtrip dec_tuple_types; do   cp /tmp/prob
         49s bash   REPO=$PWD for p in class_plain dec_routes; do   for tag in base head; do     d=/tmp/cc_${tag}_${p}; rm -rf $d;
         49s bash   cat > /tmp/probes/class_plain.py <<'EOF' class P:     def __init__(self, x):         self.x = x     def __repr

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review report

**What the change really does.** `e538fec` makes `Decimal.__init__` accept the `_DecTuple` returned by `as_tuple()` (so `Decimal(d.as_tuple())` round-trips), and patches the general-path runtime so `ail_iter_reversed` asks an instance's `__reversed__` first; the hook is installed only when a class in the program defines `__reversed__`. Manifest/docs updated.

**Verified**
- Review defect 1 fixed: `r_roundtrip.py` now prints `False` then `1.2345`, `-0.00`, `NaN` (exit 0), versus base's `TypeError: conversion from _DecTuple to Decimal is not supported`. Round-trip through a function argument, list item, attribute, dict value, plain tuple/list, NaN/inf/sNaN, negative zero and 30-digit coefficients all match CPython (`r_round2`, `r_round_routes`, `r_dec_tuple_bool`).
- Review defect 2 fixed: `r_tuple.py` matches CPython on g and d; base fails `'_DecTuple' object is not reversible`.
- User `__reversed__` works, including inheritance, generators, raising methods and `next()` (`r_rev_user`, `r_rev_more`).
- Worker probes `dec_reversed`, `dec_reversed_user`, `dec_routes`, `dec_rev_routes`, `dec_tuple_types`, `class_plain` rerun: exact match (or only the documented `isinstance` line). `class_tuple` is still a named compile-time refusal.
- Exact-int mode matches for the round-trip and reversed probes.
- `class_plain` (class program without `__reversed__`) has byte-identical `program.c` on HEAD and base. All 10 `lab/compare` tasks have byte-identical generated C for the `.ail` sources; the 7 that build `.py` also match.
- `test_ail_std_decimal`, `test_ail_dunders`, `test_ail_safetynet`: 3 modules, 0 failed. `update_manifest.py --check` exits 0.
- Report claims check out; the `isinstance` caveat is stated honestly. No false claim found.

**Pre-existing (identical on base, not blocking)**
- `isinstance(d.as_tuple(), tuple)` is `False` in AIL, `True` in CPython; base also printed `False` (before failing).
- `reversed()` on a class defining only `__len__`/`__getitem__` (sequence fallback) still fails; base fails too.
- A class whose `__reversed__` returns a non-iterator (e.g. a list) returns that object silently instead of CPython's `TypeError: __reversed__ returned non-iterator`; base raised `not reversible`, so the CPython mismatch predates this change.

**Notes / Unverified**
- Decimal-importing programs' C also gains the `NotImplemented` runtime support because `_DecTuple` is now always retained by the prelude pruner; behaviour probes still match CPython. Not a correctness defect, but it is extra C for every decimal program.
- Did not rerun `test_ail_stdtop1`, `test_ail_bytearray_decimal`, `test_ail_files`, `test_ail_corpus_findings3`, and did not run instruction counts (non-decimal class-program C is byte-identical, so no hot-path change expected).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2037877, "input": 73710, "output": 9149, "reasoning": 20682, "cache.write": 0, "cache.read": 1934336}]
    tool time: bash 21.2 min
        336s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_std_deci
        231s bash   cat > /tmp/lccheck.sh <<'EOF' #!/bin/bash t=$1 H=/home/runner/work/ail-ci/ail-ci B=/tmp/base D=/tmp/lc/$t rm -
        151s bash   cd /tmp/probes && for p in dec_reversed dec_reversed_user dec_routes dec_rev_routes dec_roundtrip dec_tuple_ty
        138s bash   cd /tmp/rprobes && cat > r_dec_ni.py <<'EOF' from decimal import Decimal class A:     def __add__(self, o): re
        114s bash   cd /tmp/rprobes && for p in r_round2 r_round_routes r_rev_more r_round_err; do echo "===== $p HEAD"; bash ~/to
         78s bash   cd /tmp/rprobes && for p in r_roundtrip r_tuple r_rev_user r_rev_wrong r_rev_no; do echo "===== $p HEAD"; bash
         76s bash   cd /tmp/rprobes && for p in r_roundtrip r_rev_user r_rev_wrong r_tuple; do echo "===== $p BASE"; bash ~/tools/
         36s bash   cd /tmp && d=cmpUbay; echo PY; cat $d/py.out; echo G; cat $d/g.out; echo DIFF; cat $d/diff_g.txt; echo ----BAS

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-01T22:26:49Z
