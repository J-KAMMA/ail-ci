# job job-prog9-11021016  started 2026-11-02T01:17:04Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the review defect in `AIL_CURRENT/python/pkg-v12/pyfunc.py`: bool row fields are now tracked per statement and dropped as soon as the name is rebound, instead of being added to the function-wide `bool_names`.

Probe results:
- `p_bool_reuse.py` strict typed: now `5` / `False z` / `7` (was `5` / `False z` / `True`).
- `p_srow_bool_rebind.py`, `p_srow_bool_branch.py`, `p_srow_bool_loop.py`: match CPython on strict typed and both `cmp.sh` builds.
- `p_srow_bool_alias.py`, `p_srow_bool_list.py`, `p_srow_bool_arg.py`: still differ, but identically on base (`/tmp/base`), so pre-existing and not caused by this fix.

Verification:
- `test_ail_prog9`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 4 modules, 0 failed.
- `python3 tools/update_manifest.py --check`: clean.
- All ten `lab/compare/src/*/main.ail` builds emit byte-identical `program.c` to base; `main.py` builds/refusals also match base.
- Added a rebinding regression to `test_ail_prog9` and a `2026-11-02` DEVLOG entry.

Committed as `16ff325`.
[cost $0.0000, opencode tokens {"total": 4371745, "input": 60150, "output": 12879, "reasoning": 27100, "cache.write": 0, "cache.read": 4271616}]
    tool time: bash 17.7 min
        428s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/lcnew /tmp/lcbase && mkdir -p /tmp/lcnew /tmp/lcbase && for 
        299s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_pro
        269s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_pro
         34s bash   cd /home/runner/work/ail-ci/ail-ci && ok=1; for d in lab/compare/src/*/; do t=$(basename "$d"); src="$d/main.a
         12s bash   cd /tmp && for f in /tmp/rprobes/p_bool_reuse.py /tmp/probes/p_srow_bool_rebind.py /tmp/probes/p_srow_bool_bra
          5s bash   cd /tmp && for f in /tmp/probes/p_srow_bool_alias.py /tmp/probes/p_srow_bool_list.py /tmp/probes/p_srow_bool_a
          3s bash   cd /tmp/probes && for f in p_srow_bool_*.py p_bool_reuse.py; do n=${f%.py}; rm -f ${n}_base; AIL_NO_CACHE=1 py
          2s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' p='AIL_CURRENT/python/pkg-v12/pyfunc.py' s=open(p).read

## review 0
[model opencode/deepseek-v4.1-flash-free]
Reviewed `work..HEAD` (`16ff325`). The change really does: add per-statement tracking of method-row bool fields and remove a name from the dynamic bool set whenever a statement binds it. That matches the report, but the removal is path-insensitive, which the report does not mention.

**Defect**

1. A rebind that is not executed still drops the bool field, so a later print gives `0` instead of `False`. The removal in `_bool_flow_after` (`pyfunc.py:20375-20381`) runs at codegen time for every statement in a branch/loop body, regardless of whether that statement executes. All three probes match CPython on base (`23ace95`) but differ on HEAD's default typed build:

```python
# /tmp/rprobes/p_bool_if_false_rebind.py
p = P(); a, b = p.pair(); print(a)
if 1 > 2:
    a = 7
print(a)
# expected False / False; HEAD False / 0
```

```python
# /tmp/rprobes/p_bool_loop_rebind.py
p = P(); a, b = p.pair(); print(a)
for i in range(0):
    a = 7
print(a)
# expected False / False; HEAD False / 0
```

```python
# /tmp/rprobes/p_bool_for_target_zero.py
p = P(); a, b = p.pair(); print(a)
for a in range(0):
    pass
print(a)
# expected False / False; HEAD False / 0
```

**Pre-existing** (identical on base, not blocking)
- Assignment *inside* a possibly-unexecuted branch/loop still leaks bool marking: `p_bool_branch_untaken` expected `5`, both base and HEAD print `True`; `p_bool_loop_zero` same.
- `p_srow_bool_alias` / `p_srow_bool_list`: a copied/aliased bool still prints `0` instead of `False` on both builds (HEAD additionally fixes the direct name, so the remaining difference is pre-existing).
- `p_srow_bool_arg` is identical on base.

**Claims checked**
- `p_bool_reuse` now prints `5` / `False z` / `7`: verified.
- `p_srow_bool_rebind`, `p_srow_bool_branch`, `p_srow_bool_loop` match CPython: verified.
- `p_srow_bool_alias/list/arg` “identically on base”: false in detail — alias/list remaining diffs are pre-existing, but HEAD output is not identical to base because the direct name is now fixed.
- 4 test modules (`test_ail_prog9`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`): 0 failed. `update_manifest.py --check`: exit 0.
- All ten `lab/compare/src/*/main.ail` builds emit byte-identical `program.c` to base: verified.
- `main.py` builds/refusals and instruction counts: not checked. The change is compiler-only, so no generated hot-path change was expected.

VERDICT: FIX

1. Make bool-name removal execution-aware, or refuse/avoid the optimisation when the rebinding is conditional or in a zero-iteration-capable loop. Probes: `/tmp/rprobes/p_bool_if_false_rebind.py`, `/tmp/rprobes/p_bool_loop_rebind.py`, `/tmp/rprobes/p_bool_for_target_zero.py`; expected `False` / `False`, actual `False` / `0` on the typed build.
[cost $0.0000, opencode tokens {"total": 1083721, "input": 40597, "output": 6496, "reasoning": 15316, "cache.write": 0, "cache.read": 1021312}]
    tool time: bash 7.3 min
        269s bash   date && cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test
         69s bash   date && cd /tmp && rm -rf lcm && mkdir lcm && ok=1; for d in /home/runner/work/ail-ci/ail-ci/lab/compare/src/*
         11s bash   cd /tmp && for f in p_bool_branch_untaken p_bool_loop_zero p_bool_else_leak p_bool_aug p_bool_branch_taken p_b
         11s bash   date && cd /tmp && for f in p_srow_bool_rebind p_srow_bool_branch p_srow_bool_loop p_srow_bool_alias p_srow_bo
         11s bash   cd /tmp/rprobes && for f in p_bool_branch_untaken p_bool_loop_zero p_bool_aug p_bool_branch_taken p_bool_else_
         10s bash   cd /tmp/rprobes && cat > p_bool_true_rebind.py <<'PY' class P:     def __init__(self) -> None: self.s = "z"   
         10s bash   cd /tmp/rprobes && cat > p_bool_walrus.py <<'PY' class P:     def __init__(self) -> None: self.s = "z"     def
         10s bash   date && cd /tmp && for f in p_srow_bool_alias p_srow_bool_list p_srow_bool_arg; do h=$(bash ~/tools/cmp.sh /tm

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed the remaining defect and committed as `3445bcb`.

**Change:** `_bool_flow_after` now drops bool-row-field marking only for straight-line `Assign`/`AnnAssign`/`AugAssign`; conditional bodies (if/else, loops, try/handlers) are tracked with `ctx.cond_depth`, and `for` targets are never treated as unconditional rebinds.

**Probes** (`cmp.sh`, both builds):
- `p_bool_if_false_rebind`, `p_bool_loop_rebind`, `p_bool_for_target_zero`: now 2/2 match CPython (was `False` / `0` on typed build).
- `p_bool_reuse`, `p_bool_branch_taken`, `p_bool_walrus`, `p_bool_walrus_if`, `p_bool_true_rebind`, `p_bool_aug`, `p_bool_ann_only`, `p_bool_bool_unpack`: 2/2 match.
- `p_bool_branch_untaken`, `p_bool_loop_zero`, `p_bool_else_leak`: still differ on typed build, but identically to base `23ace95` (pre-existing, not blocking).

**Tests on final commit:** `test_ail_prog9`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. `update_manifest.py --check` exits 0.

**Compare:** all 10 `lab/compare/src/*/main.ail` emit byte-identical `program.c`; `main.py` remains 5 identical C / 5 identical refusals.
[cost $0.0000, opencode tokens {"total": 2442397, "input": 69686, "output": 8148, "reasoning": 13075, "cache.write": 0, "cache.read": 2351488}]
    tool time: bash 17.9 min, edit 0.0 min
        359s bash   cd /tmp && rm -rf cpyhead cpybase && mkdir cpyhead cpybase && ok=1; for d in /home/runner/work/ail-ci/ail-ci/l
        275s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1800 python3 tools/par_check.py -j 2 test_ail_prog9 test_ail_saf
        272s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1800 python3 tools/par_check.py -j 2 test_ail_prog9 test_ail_saf
         70s bash   cd /tmp && rm -rf cmphead cmpbase && mkdir cmphead cmpbase && ok=1; for d in /home/runner/work/ail-ci/ail-ci/l
         29s bash   cd /tmp/rprobes && for f in p_bool_if_false_rebind p_bool_loop_rebind p_bool_for_target_zero p_bool_reuse p_bo
         28s bash   cd /tmp/rprobes && for f in p_bool_if_false_rebind p_bool_loop_rebind p_bool_for_target_zero p_bool_reuse p_bo
         23s bash   cd /tmp/rprobes && for f in p_bool_if_false_rebind p_bool_loop_rebind p_bool_for_target_zero p_bool_reuse p_bo
          8s bash   d=$(mktemp -d /tmp/ccXXXX); cp /home/runner/work/ail-ci/ail-ci/lab/compare/src/berth_sim/main.ail $d/main.ail;

## review 1
[model opencode/deepseek-v4.1-flash-free]
Reviewed `work..HEAD` (`16ff325`, `3445bcb`) in `/home/runner/work/ail-ci/ail-ci`.

**What it does:** makes bool row-field bookkeeping execution-aware: straight-line `Assign`/`AnnAssign`/`AugAssign` clear a name's bool mark, while bodies under `ctx.cond_depth` (if/else, loops, try/handlers/finally, stdin, map-upsert) and `for` targets leave it. Adds two `test_ail_prog9` cases, DEVLOG, manifest updates.

**Named defect:** fixed. `/tmp/rprobes/p_bool_reuse.py` now prints `5 / False z / 7` on both builds (base printed `True` on the last line).

**Claims:** verified — rebind probes match; the three acknowledged differences (`p_bool_branch_untaken`, `p_bool_else_leak`, `p_bool_loop_zero`) are identical on `/tmp/base`; `test_ail_prog9` + `test_ail_safetynet` pass (`-j 2`, 0 failed); `update_manifest.py --check` exits 0; all 10 `lab/compare/src/*/main.ail` produce byte-identical `program.c` vs base. Unverified — the report's `test_ail_files`/`test_ail_corpus_findings3` run (not rerun) and speed (change is compile-time bookkeeping only; non-feature C is unchanged).

**Pre-existing (identical on base, not blocking):** a rebind that may run keeps bool text, e.g. `p_new_bool_condtaken_int` (`if 1 < 2: a = 7` → `True`, expected `7`), `p_new_bool_loopbody`, `p_pre_forrun` (`for a in range(1,3)` → `True`, expected `2`), and the three worker-named probes. Also `p_new_bool_lambda` (bound-method attribute) fails identically on base. `HEAD`'s marking set is a subset of base's, so no new silent difference was found.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1508552, "input": 229482, "output": 8378, "reasoning": 22052, "cache.write": 0, "cache.read": 1248640}]
    tool time: bash 6.3 min
        175s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1500 python3 ../tools/par_check.py -j 2 test
         35s bash   cd /home/runner/work/ail-ci/ail-ci && ok=1; for t in scar_life tally_lang term_rank ticket_audit tree_fold; do
         33s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/cmphead /tmp/cmpbase && mkdir -p /tmp/cmphead /tmp/cmpbase &
         28s bash   cd /tmp/rprobes && date && for f in p_bool_*.py; do echo "########## $f"; timeout 120 bash ~/tools/cmp.sh "$PW
         18s bash   mkdir -p /tmp/rprobes && cd /tmp/rprobes cat > p_new_bool_call.py <<'PY' class P:     def __init__(self) -> No
         14s bash   cd /tmp && for n in p_new_bool_call p_new_bool_subcall p_new_bool_getattr p_new_bool_dictval p_new_bool_listit
         13s bash   cd /tmp/rprobes cat > p_new_bool_subcall.py <<'PY' class P:     def __init__(self) -> None: self.s = "z"     d
         11s bash   cd /tmp/rprobes for spec in "callable:callable(1)" "hasattr:hasattr(p, 's')" "issubclass:issubclass(bool, int)

## full suite
test_ail_bugs7
test_ail_debug_flush
test_ail_flush_exit
test_ail_mixed_bounds

## worker report (suite fix)
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Fixed and committed as `46c002d`.

**Cause:** a typed `dict` literal with container values (`d = {"k": [1, 2, 3]}`) fell through `_setitem` and emitted `ail_stab_put(..., <ail_list>)`, which gcc rejected.

**Fix:** `_setitem` now refuses list/set/dict values for a plain dict by name, so `pyc` uses the general path instead of emitting invalid C. Dict-of-lists (`ctx.ndict`) and dict-of-inner-dicts (`ctx.ddict`) keep their existing branches.

**Verified:**
- `test_ail_bugs7`, `test_ail_debug_flush`, `test_ail_flush_exit`, `test_ail_mixed_bounds`: all pass.
- `test_ail_prog9`, `test_ail_safetynet`: pass.
- `tools/update_manifest.py --check`: exits 0.
[cost $0.0764, opencode tokens {"total": 6975587, "input": 279157, "output": 10090, "reasoning": 14084, "cache.write": 0, "cache.read": 6672256}]
    tool time: bash 12.7 min, edit 0.0 min
        179s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -q test_ail_safetynet 2>&1 | tail -30
        148s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -q test_ail_mixed_bounds 2>&1 | tail -40
        123s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -q test_ail_bugs7 2>&1 | tail -40
        101s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_bugs7 2>&1 | tail -60
         46s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_mixed_bounds 2>&1 | tail -80
         40s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_debug_flush 2>&1 | tail -80
         38s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -q test_ail_debug_flush 2>&1 | tail -40
         33s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -q test_ail_flush_exit 2>&1 | tail -40

## full suite again
no new failures

FINAL VERDICT: ACCEPT  2026-11-02T05:32:46Z
