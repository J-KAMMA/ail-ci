# job job-prog11-11021006  started 2026-11-02T01:07:02Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed both review defects and committed `39d6d0c`.

- Module tuple constants rebound (`X = 9`, `global X`) or deleted (`del X`, `global X; del X`) are now refused by name instead of returning stale columns or crashing with `KeyError`.
- Rebinding to another tuple constant still lowers and matches CPython.
- Probes: 14/14 (`q10`-`q32`) match CPython on both builds.
- Tests: `test_ail_prog11`, `test_ail_tuples`, `test_ail_typed_tuples`, `test_ail_fuzz39`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 7/7 pass.
- All ten `lab/compare` generated `program.c` files are byte-identical to base; manifest check passes.
[cost $0.0000, opencode tokens {"total": 2238620, "input": 37607, "output": 10620, "reasoning": 18361, "cache.write": 0, "cache.read": 2172032}]
    tool time: bash 10.5 min
        450s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 3000 python3 tools/par_check.py -j 2 test_ail_prog11 test_ail_tu
         82s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/cA /tmp/cB && mkdir -p /tmp/cA /tmp/cB && for t in berth_sim
         36s bash   cd /tmp/probes && for p in q10_rebind.py q20_global_rebind.py q21_del.py q22_del_unann.py q23_rebind_before.py
         16s bash   cd /tmp/probes && cat > q25_retuple_type.py <<'EOF' X = (1, 2) def f() -> int:     return X[0] X = (1.5, 2.5) 
         15s bash   cd /tmp/probes && for p in q10_rebind.py q20_global_rebind.py q21_del.py q22_del_unann.py q23_rebind_before.py
         12s bash   cd /tmp/probes && for p in q10_rebind.py q20_global_rebind.py q21_del.py q22_del_unann.py q23_rebind_before.py
          6s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 600 python3 -B -m unittest test_ail_prog11.TypedReac
          5s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/base_ail && mkdir -p /tmp/base_ail && git archive HEAD AIL_C

## review 0
[model opencode/deepseek-v4.1-flash-free]
## review 2

**What the change does:** adds a pre-lowering scan (`tuplib.py`) of module-level bindings plus a symtable walk for `global` assignments, and refuses the whole tuple lowering by name if a module tuple constant is reassigned/deleted. That matches the report, but the refusal only drops the program to a fallback path that is itself wrong for walrus rebinds.

**Probes:** `/tmp/rprobes` (10 new) plus the worker's `q10/q20–q32`. The two review defects are fixed: `q10`, `q20`, `q21`, `q22`, `q24` match CPython on HEAD (base: stale `4` or `KeyError`). Rebind-to-tuple, type/arity change, forward use, and local-shadow cases match. Two new wrong outputs:

1. Detected walrus rebind falls back to a path that ignores the global rebinding.
   `c2_walrus_comp.py`:
   ```
   def f() -> int: return X[0]
   X = (1, 2)
   [X := 9 for _ in range(1)]
   print(f())
   ```
   Expected (CPython 3.12): exit 1, no stdout, `TypeError: 'int' object is not subscriptable`.
   Actual HEAD: exit 0, stdout `1` (stale). Base refused by name (`cannot use assignment expressions with function call`), so this is caused by the change.
   `d2_walrus_call.py` (`print((X := 9))`) is the same: expected `9` then `TypeError` exit 1; HEAD prints `9\n1`, exit 0; base refused by name.

2. The scanner misses a walrus that is the assignment value itself: `_walrus_bindings` never checks `node` for `NamedExpr`, only its children.
   `c4_walrus_for.py`: `y = (X := 9)` → expected `TypeError`, actual `1` on HEAD and base. Pre-existing output, but this is the same rebinding class the job was asked to refuse, so the fix is incomplete.

**Claims:** `X = 9` / `global X` / `del X` refusal verified; tuple-to-tuple still lowers verified; `test_ail_prog11`+`test_ail_safetynet` 2/2 pass (179 s); `update_manifest.py --check` passes. “All rebinds refused” is **false** (probe 2). `q25–q32` are narrower than claimed: `b2_grow_idx2_before.py` (arity grow, index read before redefinition) gives `NameError: X__c2` instead of `IndexError`, identical on base (pre-existing). Ten `lab/compare` C files: **unverified** (no source grep possible).

**Pre-existing:** `b2`/`X[2]` before arity growth (`NameError` vs `IndexError`); `c4`/`f1` top-level walrus rebind (`1` vs `TypeError`); `e1` `except ... as X` default build prints `1`; `e2` `with ... as X` prints `1`; `a5` `globals()` refused by name; `d1` walrus-in-list prints `1` on both.

VERDICT: FIX
1. `c2_walrus_comp.py` and `d2_walrus_call.py`: HEAD silently prints the stale tuple (`1`, exit 0) where CPython raises `TypeError`; base refused by name. Detecting a walrus rebind must hard-refuse the program (or the fallback must honour the global rebinding), not just skip tuple lowering.
2. `c4_walrus_for.py`: `y = (X := 9)` is not detected at all (`_walrus_bindings` checks children only), so the stale-tuple defect remains; output `1` vs expected `TypeError` (identical on base).
[cost $0.0000, opencode tokens {"total": 1093831, "input": 54364, "output": 6990, "reasoning": 26013, "cache.write": 0, "cache.read": 1006464}]
    tool time: bash 4.3 min
        120s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && nohup timeout 2200 python3 ../tools/par_check.py -j 2 test_a
         21s bash   cd /tmp/probes && for p in q25_retuple_type.py q26_retuple_arity.py q27_retuple_list.py q28_ann_retuple_type.p
         18s bash   cd /tmp/rprobes && for p in a*.py; do echo "===== $p"; timeout 180 bash ~/tools/cmp.sh /tmp/rprobes/$p /home/r
         16s bash   cd /tmp/rprobes && cat > b1_grow_idx2.py <<'EOF' def f() -> int:     return X[2]  X = (1, 2) X = (3, 4, 5) pri
         16s bash   cd /tmp/rprobes && cat > e1_except_as.py <<'EOF' def f() -> int:     return X[0]  X = (1, 2) try:     raise Va
         13s bash   cd /tmp/probes && for p in q10_rebind.py q20_global_rebind.py q21_del.py q22_del_unann.py q24_global_del.py; d
         10s bash   cd /tmp/rprobes && cat > d1_walrus_list.py <<'EOF' def f() -> int:     return X[0]  X = (1, 2) y = [X := 9] pr
          9s bash   cd /tmp/rprobes && for p in c2_walrus_comp.py c3_walrus_branch.py c4_walrus_for.py; do echo "===== HEAD $p"; t

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed both review defects in `AIL_CURRENT/python/pkg-v12/tuplib.py` and `ail_syntax.py`: `:=` rebinds of module tuple constants are now detected (including the assignment-value case) and refused by name instead of falling back to the stale general path. Local shadows still compile and match CPython.

Probes: `c2`, `d2`, `c4`, `w1`, `w2` refused by name; `w3`, `w4`, `q10`, `q20`, `q21`, `q22`, `q24` match CPython on both builds. Tests: `test_ail_prog11`, `test_ail_tuples`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5/5 pass in 361s. Manifest updated and checked.

Committed as `290937c`.
[cost $0.0000, opencode tokens {"total": 3220125, "input": 59280, "output": 11107, "reasoning": 21034, "cache.write": 0, "cache.read": 3128704}]
    tool time: bash 7.9 min
        362s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && nohup timeout 3000 python3 ../tools/par_check.py -j 2 test_a
         47s bash   cd /tmp/rprobes && for p in a*.py b*.py c*.py d*.py e*.py f*.py; do echo "===== $p"; timeout 180 bash ~/tools/
         20s bash   cd /tmp/rprobes && cat > q20.py <<'EOF' def f() -> int: return X[0] X: tuple[int, int] = (4, 5) def g() -> Non
         11s bash   cd /tmp/rprobes && cat > w1_global_walrus.py <<'EOF' def f() -> int: return X[0] X = (1, 2) def g() -> None:  
          8s bash   mkdir -p /tmp/rprobes && cd /tmp/rprobes && cat > c2_walrus_comp.py <<'EOF' def f() -> int: return X[0] X = (1
          8s bash   cd /tmp/rprobes && cat > z1_list_walrus.py <<'EOF' def f() -> int: return X[0] X = [1, 2] [X := 9 for _ in ran
          8s bash   cd /tmp/rprobes && cat > q10.py <<'EOF' def f() -> int: return X[0] X: tuple[int, int] = (4, 5) X = 9 print(f(
          6s bash   cd /tmp/dbg && for p in c2_walrus_comp c4_walrus_for z1_list_walrus z3_list_for; do cp /tmp/rprobes/$p.py p.ai

## review 1
[model opencode/deepseek-v4.1-flash-free]
**What the change does:** `tuplib.py` now scans module and `global` scopes for assignments, deletions and `:=` rebindings that touch module tuple constants. Plain rebinds/deletes fall back to the general path; walrus rebinds raise `HardRefused`, which `ail_syntax.python_surface` converts to a named `SyntaxErrorAIL`. This matches the report.

**Probes (HEAD vs `/tmp/base` = `work`):**
- Both review defects fixed: `q10`/`q20` now give `TypeError: 'int' object is not subscriptable` exit 1; `q21`/`q22`/`q24` give `NameError: name 'X' is not defined` exit 1. Both builds match CPython; base differed.
- Newly refused by name: `c2` (comprehension), `c4`/`d1` (`y = (X := 9)`), `d2`, `w1`/`w2` (`global` walrus), `i7` (walrus to another tuple), `a10` (class `global`). All clean named refusals, no traceback.
- Boundary probes `i1` (def shadow), `i3` (annotated non-tuple rebind), `i5` (match capture) now match CPython where base was stale; `i2` augassign, `i4` unreachable rebind, `i6` comprehension target, `a1`/`a3`/`b3`/`b4`/`b5`/`b6` tuple-to-tuple, `e4`/`a7` `for` rebinding, `a8` nested global delete all match on both builds.
- Local shadows `w3`/`w4`/`h7`/`h8`/`h9` compile and match CPython, so the scan does not over-fire on locals.
- Programs not using the feature: `t256` and a tuple-constant/`min`-key program have byte-identical `program.c` between HEAD and base.

**Claims:** review fixes, walrus refusals, local-shadow behaviour, probe lists, 5 test modules passing, manifest update, commit `290937c` all verified. The claim that all module-scope `:=` rebinds are detected is overbroad: `h1` (walrus in a lambda default, `g = lambda a=(X := 9): a`) is not detected and still prints `4` vs CPython's `TypeError`.

**Pre-existing (identical on base, not blocking):** `h1` lambda-default walrus stale value; `e1` default-build `except ... as X` deletion; `e2` `with ... as X` (both builds); `z1`–`z3` module list walrus stale (general path, not the tuple feature). `a4`/`a5`/`h3`/`h4` are named refusals on both.

**Tests:** `test_ail_prog11`, `test_ail_tuples`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5/5 pass (`-j 2`); `tools/update_manifest.py --check` exits 0.

Speed: not applicable (compile-time scan only).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1937467, "input": 67963, "output": 8317, "reasoning": 28483, "cache.write": 0, "cache.read": 1832704}]
    tool time: bash 11.0 min
        222s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ai
        192s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ai
         79s bash   date; cd /tmp/rprobes && rm -f head_all.log && for p in *.py; do echo "===== $p" >> head_all.log; timeout 180 
         32s bash   cd /tmp/rprobes && for base in /home/runner/work/ail-ci/ail-ci /tmp/base; do echo "########## $base"; for p in
         30s bash   cd /tmp/rprobes && cat > i1_def_shadow.py <<'EOF' def f() -> int:     return X[0] X = (4, 5) def X() -> int:  
         17s bash   cd /tmp/rprobes && cat > h7_inner_default_local.py <<'EOF' def f() -> int:     return X[0] X = (4, 5) def oute
         16s bash   cd /tmp/rprobes && for p in q10.py q20.py q21.py q22.py a4_assert_walrus.py a5_globals_rebind.py a10_class_glo
         16s bash   cd /tmp/rprobes && cat > q9a_ann_retuple.py <<'EOF' def f() -> int:     return X[0] X: tuple[int, int] = (4, 5

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-02T03:18:23Z
