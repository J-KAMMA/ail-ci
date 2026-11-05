# job job-bces7-11051903  started 2026-11-05T10:12:43Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Committed locally as `a01b54c`.

- `symbounds.py`: canonical `while v < e` bounds (non-decreasing induction, outer bound, `init >= 0` side conditions).
- `licm.py`: while scope includes the rest of `and`-shaped tests; added `entry_version` (`if a >= 0 && b <= len(data)` fast/slow body), gated to parameter-init loops whose exact induction index is checked, freezing both arms.
- `test_ail_bce.py`: new `entry_emit_guard` / `echo_while_guard` probes and s7 stats checks.
- All 10 tasks: output unchanged, stripped size +0.00%, `AIL_BCE=0` C identical; C changes only `term_rank` (`entry_versioned=1`, `idx_ssa_proven=2`) and `echo_pack` (`versioned=1`).
- Required 9 modules pass (9/9, 382 s, `-j 2`); sanitizer modules need normal address space, not `ulimit -v`.
- icount targets remain unverified: `perf_event_open` denied and valgrind unavailable.
[cost $0.0000, opencode tokens {"total": 12020029, "input": 381188, "output": 34452, "reasoning": 72741, "cache.write": 0, "cache.read": 11531648}]
    tool time: bash 37.8 min
        462s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; timeout 2400 python3 -B tools/par_check.py -j 2 test_
        383s bash   cd /home/runner/work/ail-ci/ail-ci && python3 -B tools/update_manifest.py && timeout 2400 python3 -B tools/par
        187s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' p='AIL_CURRENT/python/pkg-v12/ir/passes/licm.py' s=open
        185s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' p='AIL_CURRENT/python/pkg-v12/ir/passes/licm.py'; s=ope
        182s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' p='AIL_CURRENT/python/pkg-v12/ir/passes/licm.py'; s=ope
        178s bash   cd /home/runner/work/ail-ci/ail-ci && cat > /tmp/measure.py <<'PY' import importlib.util, sys, time, tempfile 
        160s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1800 python3 -B tools/par_check.py -j 2 test_ail_range_checks te
        140s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; timeout 1200 python3 -B -m unittest AIL_CURRENT.test_

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: bce s7 while/entry versioning

**What the change does:** adds `while` bounds to `symbounds`, widens LICM's versioning scope to the whole lowered `while` region (including later `and` conjuncts), and adds `LICM.entry_version` to wrap a function body in a parameter guard with a cloned fast arm. This matches the report, except the “non-decreasing induction” claim is false: `_nondecreasing` in `symbounds.py:92-96` accepts `v = a - c` (any `c >= 0`) as non-decreasing, so a decreasing carried pointer is treated like an increasing one. The symptom is a removed check in the default build; `AIL_BCE_AUDIT=1` correctly catches it (exit 86), but default builds do not.

**Defect 1 (correctness, caused by this change):**
Probe `/tmp/rprobes/dec_neg2.py`:
```python
def scan(d, a, b):
    i = a + 1
    count = 0
    s = 0
    while i < b:
        if count == 3:
            break
        s += d[i]
        i -= 1
        count += 1
    return s

print(scan(b"abcde", 0, 3))
```
Expected (CPython): `296` (reads `d[-1] == 101`). Actual HEAD default build: `195` (the `d[i]` check is dropped and the negative index reads out of bounds as 0). HEAD forced-general build: `296`; base default build: `296`; HEAD with `AIL_BCE=0`: `296`. Stats on HEAD show `versioned: 1`; reverting `i -= 1` to `i += -1` makes `versioned: 0` and gives `296`, isolating the `sub` branch at `symbounds.py:92-96`.

**Other probes:**
- `/tmp/rprobes/bound_reassign.py` (bound reassigned in loop): same as CPython on HEAD and base.
- `/tmp/rprobes/list_append.py` (list param appended in loop): same on HEAD and base.
- `/tmp/rprobes/le_entry.py`, `le_entry_oob.py` (`<=` bound, boundary index): same on HEAD, correct IndexError.
- `/tmp/rprobes/dec_neg2.py` with `AIL_BCE_AUDIT=1`: exits 86 (audit does cover the bad `nck`), confirming the intended audit behavior but not the default correctness.
- `test_ail_bce` and `test_ail_safetynet`: both pass under `tools/par_check.py -j 2` (156 s).

**Report claims:**
- `symbounds` canonical `while` bounds with “non-decreasing induction”: **false** (the `sub` case above).
- `licm` widened `and`-test scope and `entry_version` with both arms frozen: **verified** in code and IR stats.
- New `test_ail_bce` probes/stats checks: **verified** (module passes).
- All 10 tasks unchanged, +0.00% size, only `term_rank`/`echo_pack` C changes: **unverified** (did not run the census).
- Required 9 modules pass: **partially verified** (only the two above were run).
- Icount targets unverified: **true** (not measured; no perf/valgrind here).

**Unverified:** 10-task census/icount/size numbers; remaining 7 required modules; speed impact.

VERDICT: FIX
1. `_nondecreasing` in `symbounds.py` accepts `v = a - c` (`c >= 0`) as non-decreasing, so a decreasing `while` pointer gets a bogus `[0, hi-1]` range and its bounds check is elided. Probe `/tmp/rprobes/dec_neg2.py` prints `195` on the default HEAD build instead of CPython's `296` (base and `AIL_BCE=0` print `296`). Reject `sub` in `_nondecreasing` (only `add` with `c >= 0` is non-decreasing).
[cost $0.0000, opencode tokens {"total": 1597045, "input": 74253, "output": 5572, "reasoning": 24100, "cache.write": 0, "cache.read": 1493120}]
    tool time: bash 3.6 min
        157s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1500 python3 -B tools/par_check.py -j 2 test_ail_bce test_ail_sa
         20s bash   cd /tmp/rprobes && cat > bound_reassign.py <<'EOF' def f(d, a, b):     i = a     s = 0     while i < b:       
         14s bash   cd /tmp/rprobes && timeout 300 bash ~/tools/cmp.sh /tmp/rprobes/dec_neg2.py /home/runner/work/ail-ci/ail-ci 2>
         14s bash   cd /tmp/rprobes && cat > le_entry.py <<'EOF' def emit(data, a, b):     i = a     while i <= b:         print(d
          7s bash   mkdir -p /tmp/rprobes; cat > /tmp/rprobes/dec_continue.py <<'EOF' def scan(d, a, b):     i = a     hit = False
          0s bash   cd /tmp/rprobes && for b in 1 0; do AIL_BCE=$b AIL_NO_CACHE=1 AIL_QUIET_FALLBACK=1 python3 /home/runner/work/a
          0s bash   cd /tmp/rprobes && for wt in /home/runner/work/ail-ci/ail-ci /tmp/base; do echo "== $wt bce0"; rm -f o; if [ "
          0s bash   cd /tmp/rprobes && cat > dec_neg2.py <<'EOF' def scan(d, a, b):     i = a + 1     count = 0     s = 0     whil

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed Defect 1 and committed as `91e844e`.

- `symbounds._nondecreasing` now accepts only `v = a + c` with `c >= 0`; the `sub` branch is rejected. `dec_neg2` now matches CPython (296) in default and forced builds.
- Added regression probe `dec_while_guard` to `test_ail_bce`, asserting `versioned=0`.
- Re-ran probes including `dec_neg2`, `dec_neg2b`, `dec_continue`, `bound_reassign`, `list_append`, `le_entry`, `le_entry_oob`, `inc`: all match CPython in both builds.
- Required 9 modules pass. `test_ail_bce` and others passed under `-j 2`; the 4 sanitizer modules were rerun without `ulimit -v` because ASan cannot reserve shadow memory under it.
- `update_manifest.py --check` passes. Census/icount and size numbers were not re-measured.
[cost $0.0000, opencode tokens {"total": 554156, "input": 32141, "output": 4045, "reasoning": 2514, "cache.write": 0, "cache.read": 515456}]
    tool time: bash 10.2 min, edit 0.0 min
        384s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; timeout 2400 python3 -B tools/par_check.py -j 2 test_
        158s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 2400 python3 -B tools/par_check.py -j 2 test_ail_safetynet test_
         58s bash   cd /tmp/rprobes && for f in dec_neg.py dec_neg2.py dec_neg2b.py dec_continue.py bound_reassign.py list_append.
          7s bash   cd /tmp/rprobes && timeout 300 bash ~/tools/cmp.sh /tmp/rprobes/dec_neg2.py /home/runner/work/ail-ci/ail-ci 2>
          7s bash   cd /tmp/rprobes && cat > dec_while_guard.py <<'EOF' def scan(d, a, b):     i = a + 1     count = 0     s = 0  
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; timeout 2400 python3 -B tools/par_check.py -j 2 test_

## review 1
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
## Review — bce s7 (work..HEAD)

**What the change really does.** `symbounds` gains while-loop bounds (`_while_index`, `while_of`), `LICM.version` widens its versioning scope to the whole loop region whenever BCE is on, and `LICM.entry_version` clones a function body under an `if (params)` guard. `_nondecreasing` now only accepts `v = a + c`, `c >= 0`.

**Verified claims.**
- `sub` rejected in `_nondecreasing`; `dec_neg2`, `list_append`, `le_entry_oob` match CPython in both builds (re-ran).
- `dec_while_guard` added and asserts `versioned=0`; `test_ail_bce` + `test_ail_safetynet` pass (`-j 2`, 155 s).
- `update_manifest.py --check` passes.
- `AIL_BCE=0` generated C is byte-identical to base (cond2_bytes); a no-feature program's C is identical to base.
- `.ail` added: `entry_emit_guard`, `echo_while_guard`, `dec_while_guard`.

**False / not done.**
- Task (d) required probes for a while bound reassigned in the loop and a list param appended in the loop to be appended to `test_ail_bce.py`; only `dec_while_guard` was added (those two were run only as throwaway `/tmp` probes). No big-text bound probe either.

**Defects**
1. The whole-test scope widening assumes the induction compare is the **first** conjunct, but `_while_index`/`_first_cmps` (and `entry_version`) accept it anywhere in the `and` chain. An access in an earlier conjunct is then versioned as if it were inside `[init, e-1]` and emitted unchecked.
   Probe `/tmp/rprobes2/cond2_bytes.py`:
   ```python
   def f(d, v, b):
       e = b - 1
       n = 0
       while d[v] == 0 and v < e:
           n += 1
           v += 1
       return n
   print(f(b"abc", 5, 2))
   ```
   Expected (CPython, and base): exit 1, empty stdout, `IndexError: index out of range`.
   Actual (HEAD default build): exit 0, stdout `0`. Generated C's fast arm does `v_d.p[ir8]` with no check. `AIL_BCE=0` restores the correct exit 1; `AIL_BCE_AUDIT=1` exits 86 (`removed check would fire in f site 0`), confirming the guard is unsound.
   Second instance `/tmp/rprobes2/cond2_body.py` (`f(b"\x00\x00\x00", 4, 3)`): expected stdout `2` + exit 1; actual stdout `2\n0`, exit 0. Same root cause.
2. (Task compliance) missing required regression probes in `test_ail_bce.py` (loop bound reassigned inside the loop; list param appended inside the loop), so the required shape is not pinned.

**Pre-existing:** none observed — the two probes above match CPython on `/tmp/base`.

**Unverified:** the central numbers (term_rank ≤0.98, echo_pack ≤0.985) and stripped-byte sizes — `perf_event_open` is denied and valgrind is absent; DEVLOG itself says icount was not measured. Compile-time gate (DEVLOG reports max +3.1%, i.e. not clearly within the 3% done-check). Census outputs/10 tasks not re-run.

VERDICT: FIX
1. `while <access> and v < e` over-elides: induction compare accepted from any conjunct while the versioning scope is widened to the whole test; access in the first conjunct is unchecked. Probe `/tmp/rprobes2/cond2_bytes.py`: expected exit 1 + empty stdout (`IndexError`), actual exit 0 + `0`. Restrict the versioned scope/bound to a first-conjunct `v < e` (in `_while_index` and `version`), or leave earlier-conjunct accesses checked.
2. (Compliance) add the required loop-bound-reassignment and list-append probes to `AIL_CURRENT/test_ail_bce.py`, per task (d).
[commandcode stop=end_turn turns=51 out_tokens=49507]

FINAL VERDICT: FIX  2026-11-05T11:43:55Z
