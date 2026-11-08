# job job-rbwedge4-11090021  started 2026-11-08T15:29:45Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Re-applied `job-wedge4-11082211` on `job-rbwedge4-11090021`; committed as `9336c935`.

- Code/test hunks applied unchanged; workflow hunk was already present byte-for-byte. `tools/diff_ids.py` does not exist on this tree, so only `update_manifest.py` ran (`--check` clean).
- Records: re-apply DEVLOG entries in both logs, accepted entries kept, one DIFFERENCES row `C?-job-rbwedge4-11090021-1`.
- Probes (`/tmp/probes/w4_*`, hybrid + `cmp.sh` g/d): 7 probes, all hybrid outputs match CPython.
  - `w4_methods`, `w4_params`, `w4_returns`, `w4_dispatch`: same stdout on hybrid and both standalone builds.
  - `w4_field_override`, `w4_nonlocal_base`, `w4_widths`: hybrid matches CPython; standalone refused by name (`attribute access hooks`, `multiple inheritance`, `int64 constant expression out of range`).
- Final-commit tests, `-j 2`: `test_ail_cpython_hybrid` (16), `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed, 220 s.

Untracked `.agent/pipeline.md` was left untouched.
[cost $0.0000, opencode tokens {"total": 1766150, "input": 73000, "output": 11058, "reasoning": 8108, "cache.write": 0, "cache.read": 1673984}]
    tool time: bash 9.4 min, edit 0.0 min, read 0.0 min
        291s bash   python3 tools/par_check.py -j 2 test_ail_cpython_hybrid test_ail_safetynet test_ail_files test_ail_corpus_find
        221s bash   python3 tools/par_check.py -j 2 test_ail_cpython_hybrid test_ail_safetynet test_ail_files test_ail_corpus_find
         17s bash   cat > /tmp/probes/run_hybrid.sh <<'EOF' #!/bin/bash wt=$1; shift for src in "$@"; do   name=$(basename "$src" 
         15s bash   for p in /tmp/probes/w4_*.py; do echo "=== $(basename $p)"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | grep -E 'cp
          8s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-wedge4-11082211 2>&1 | tail -5 && git log --oneline -3 FET
          4s bash   bash ~/tools/cmp.sh /tmp/probes/w4_dispatch.py "$PWD" 2>&1 | tail -30
          3s bash   python3 - <<'EOF' p='/tmp/probes/w4_dispatch.py' s=open(p).read() s=s.split("class Patch:")[0] s += """ inst =
          2s bash   bash /tmp/probes/run_hybrid.sh "$PWD" /tmp/probes/w4_dispatch.py 2>&1 | tail -12

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: re-apply of `job-wedge4-11082211`

**What the change really does.** It is a faithful re-application of the accepted wedge4 change: plain-class field-only methods are lifted to typed kernels through a C wrapper that reads/writes `self.<field>` with `PyObject_GetAttrString`/`SetAttrString`; `self.m(...)` calls, field-overriding subclasses, non-local MRO bases and non-provable writes refuse by name; `and`/`or` return-kind inference is added, plus the `__thread` trap flag linkage and `PyUnicode_IS_ASCII`. This matches the report.

**Diff/claim checks**
- Code/test hunks byte-identical to `git diff fe64ce0d FETCH_HEAD` (verified by diffing both patch texts): verified.
- `.github/workflows/agent-worker.yml` hunk already present (work vs FETCH_HEAD empty): verified.
- `tools/diff_ids.py` absent; `tools/update_manifest.py --check` exits 0: verified.
- DEVLOG entries and one DIFFERENCES row present; commit `9336c935` on branch: verified.
- Worker probes `w4_*` rerun on HEAD: all `HYBRID same stdout`; accelerated/rejected lists as reported: verified.
- Non-feature program (`program.c`) from `/tmp/base` worktree vs HEAD with `--debug-dir`: byte-identical (only temp paths differ in `native_report.json`): verified.
- `test_ail_cpython_hybrid` (16 tests) and `test_ail_safetynet` on HEAD, `-j 2`: 0 failed. `test_ail_files` / `test_ail_corpus_findings3` not run (review scope): unverified.

**Probes written** (`/tmp/rprobes/`): `r1_fields`, `r3_writekind`, `r4_sub`, `r5_alias`, `r6_none`, `r8b`, `r11_fallback`, `r13_alias`, `r15_index`, `r18_misc`, `r20/r21_collide`, `r23_absbool`, `r24_id`. All hybrid outputs match CPython except the identity probe below. `cmp.sh` general/default builds match or refuse by name (`C114`).

**Defect 1 — the method wrapper changes a field's object identity when CPython does not store it.**
`_method_wrapper_lines` unconditionally `PyObject_SetAttrString`s every static write field after the call, even on paths where the body never executed the store. It recreates the value with `PyLong_FromLongLong`/`PyFloat_FromDouble`, so an untouched attribute becomes a new object. The existing `id_any`/C102 guard only looks at candidate results/params, not at method fields.

Probe `/tmp/rprobes/r12_identity.py` (minimal form):

```python
class C:
    def __init__(self, n: int) -> None:
        self.n = n
    def maybe(self, flag: bool) -> int:
        if flag:
            self.n = self.n
        return 0
c = C(1000000)
r = c.n
c.maybe(False)
print(c.n is r)
```

Expected (CPython 3.12): `True`. Actual hybrid: `False`. Base hybrid (`/tmp/base`, no method kernels): `True`. The standalone general/default builds refuse the program by name (`C114`); the hybrid silently differs. An unconditional `def always(self): self.n = self.n` also gives `False` vs CPython `True` (`c.n is saved`).

**Non-blocking observation.** Kernel names are built only from class + method names (`__ail_hybrid_method_<C>_<M>`), so `class A_B: def C` and `class A: def B_C` collide and the extension fails to link; likewise a method named `B__get_x` collides with `B`'s field kernel for `x`. The build catches this, reports a `no extension: ... redefinition/multiple definition` note and runs pure CPython, so output and exit status still match (probes `r20/r21`). This is a missed acceleration, not a wrong result.

VERDICT: FIX
1. Method wrapper writes every statically-written field unconditionally, so a method path that never stores the field still replaces the attribute object; `c.n is saved` changes from CPython's `True` to `False` (probe `r12_identity.py`, also `r13_alias.py`: `d.x is d.y` `False` vs `True`). Base hybrid matches CPython, so the change causes it. Fix by having each field kernel report whether the store executed (and skipping `SetAttr` otherwise, or reusing the original object), or by refusing a method whose field store is not executed on every path / refusing the program when numeric `is` is present as the existing C102/C114 guard already does for top-level candidates.
[cost $0.0000, opencode tokens {"total": 3014556, "input": 109231, "output": 12971, "reasoning": 46146, "cache.write": 0, "cache.read": 2846208}]
    tool time: bash 3.6 min
        104s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 600 python3 tools/par_check.py -j 2 test_ail_cpython_hybrid test
         17s bash   cd /home/runner/work/ail-ci/ail-ci && grep -c "    def test_" AIL_CURRENT/test_ail_cpython_hybrid.py; bash /tm
         16s bash   cat > /tmp/rprobes/r4_sub.py <<'PY' class Base:     def __init__(self, n: int) -> None:         self.n = n    
          9s bash   cd /tmp/rprobes && for p in r1_fields.py r6_none.py r8b.py; do echo "=== $p"; bash ~/tools/cmp.sh "$p" /home/r
          7s bash   cat > /tmp/rprobes/r18_misc.py <<'PY' class C:     def __init__(self, s: str, xs: list[float], n: int) -> None
          6s bash   cd /tmp/rprobes && cat > r9a.py <<'PY' BIG = int('1180591620717411303424') class C:     def __init__(self, n: 
          6s bash   cd /tmp/rprobes && cat > r8a.py <<'PY' class C:     def __init__(self, n: int) -> None:         self.n = n    
          5s bash   cd /home/runner/work/ail-ci/ail-ci && (git worktree add /tmp/base work >/tmp/wt.log 2>&1 && echo worktree-ok |

## worker report 1
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Fixed the reviewer's defect and committed as `3bace59b`.

**Defect fix.** The hybrid method wrapper wrote every statically-written field back as a fresh box even when the store never ran (or for `self.n = self.n`), so `c.n is saved` was `False` where CPython gives `True`. I extended the existing C102 identity guard to lifted methods: if the program has a numeric `is`/`is not`, every plain-class method stays in CPython with the named reason `the program compares numbers with \`is\``, and no method kernel is emitted. Top-level functions keep the existing per-candidate guard, so unrelated top-level int functions still accelerate.

**Probes** (`/tmp/probes/`, run on final commit):
- `r12_identity` (untouched store, executed `self.n = self.n`): hybrid same, g/d refused by name `C114`.
- `r13_alias` (alias then store, read-only return): hybrid same, g/d `C114`.
- `r22_accel` (conditional/unconditional int/bool/float writes; still accelerated `C.always`,`C.maybe`): hybrid same, g/d same stdout.
- `r23_toplevel_is` (method refused, top-level `add1` still accelerated): hybrid same, g/d `C114`.
- `r24_readonly_is` (`get() is c.n`): hybrid same, g/d `C114`.
- `r25_bool_float_is` (bool/float fields): hybrid same, g/d same stdout.

**Tests on final commit, `-j 2`:** `test_ail_cpython_hybrid`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed, 220 s.

Records added: DEVLOG entries (both files) and DIFFERENCES row `C?-job-rbwedge4-11090021-2`. `python3 tools/diff_ids.py` is absent from this tree; `python3 tools/update_manifest.py --check` exits 0. Untracked `.agent/pipeline.md` was left untouched.
[commandcode stop=end_turn turns=44 out_tokens=20154]

## review 1
[model commandcode/deepseek-v4.1-flash]
## Review: `job-rbwedge4-11090021`

**What the diff really does.** Re-applies the accepted wedge4 change byte-for-byte (`ail_cpython_hybrid.py` and its test file are identical to `FETCH_HEAD` apart from the 18-line fix; the workflow hunk is already present), then adds the claimed fix: in `build()`, if `pyboxed2._mix_identity_unsafe(tree)` reports any non-trivial `is`, every liftable method gets `reason = 'the program compares numbers with \`is\`'` and no method kernel is emitted. Records/manifest updated. `tools/diff_ids.py` genuinely does not exist here.

**Claim check**
- Re-application faithful (file compare vs `FETCH_HEAD`): verified.
- `r12/r13/r23/r24` hybrid same, g/d refused by name `C114`: verified.
- `r22/r25` hybrid same, g/d same stdout (`C.always`,`C.maybe` still accelerated): verified.
- Top-level `add1` still accelerated while method refused (`r23`): verified.
- Guard is described as "numeric `is`", but `unified._identity_compares` also fires for `c.get() is c.s` (str operands) — broader than reported, safe (probe `p1_str_ident`: method refused).
- `update_manifest.py --check` = 0; `tools/diff_ids.py` absent: verified.
- Tests: I ran `test_ail_cpython_hybrid test_ail_safetynet -j 2` on HEAD → 2 modules, 0 failed, 105 s. The other two modules claimed (`test_ail_files`, `test_ail_corpus_findings3`) I did not rerun.
- `/tmp/rprobes/p6_no_feature.py` generated C (`--debug-dir`) is byte-identical HEAD vs `/tmp/base` (md5 `0b25a2…`).
- The fix adds **no regression test** to `test_ail_cpython_hybrid.py` (no `is`/NaN case).

## Defect

**1. A lifted float-field method loses NaN identity, so container membership changes.** The guard only covers `is`; a float field returned through a lifted method is a fresh NaN box, and `in` (`list`/`tuple`/`set`/`dict`, which compare identity first) then answers differently.

`/tmp/rprobes/p15_nan_containers.py`:
```python
class C:
    def __init__(self, f: float):
        self.f = f
    def get(self) -> float:
        return self.f

n = float('nan')
c = C(n)
d = {c.f: 'x'}
print(c.get() in d)
print(c.get() in [c.f])
print(c.get() in (c.f,))
```
CPython: `True True True` — HEAD hybrid: `False False False` (`C.get` accelerated, no `rejected` reason). On `/tmp/base` hybrid the same probe prints `True True True` (methods not lifted), so the change caused it. Same with `/tmp/rprobes/p13_nan_set.py` (`print(c.get() in {c.f})`: `True` vs `False`). Default g/d builds are unaffected (`same stdout`).

Fix direction: extend the C102-style guard to the method plan — when `unified` sees a container search with a float (or the program can build a NaN), refuse a method that reads/returns a `float` field, not only when an `is` exists.

## Pre-existing (does not block)
- Top-level analogue `/tmp/rprobes/p14_top_nan.py` (`getf(n) in {n}`) prints `False` vs CPython `True` on **both** `/tmp/base` and HEAD hybrid — same NaN-boxing limitation without methods.
- `/tmp/rprobes/p1_str_ident.py` g/d builds print `False` vs CPython `True` on both base and HEAD (str `is` identity on the standalone builds).

## Unverified
- `test_ail_files`, `test_ail_corpus_findings3` (not rerun, per no-wider-suite rule).
- Instruction-count/bench comparison: not run; the fix only removes acceleration on `is` programs, and the re-applied kernels are the accepted ones. No speed regression observed indirectly (`p7_basic` methods still accelerate).

VERDICT: FIX
1. NaN identity lost through lifted float-field methods: `/tmp/rprobes/p15_nan_containers.py` prints `False False False` on the hybrid build where CPython prints `True True True` (base hybrid matches); same in `/tmp/rprobes/p13_nan_set.py` (`True` vs `False`). The `is`-only guard does not cover container identity.
[commandcode stop=end_turn turns=57 out_tokens=31851]

FINAL VERDICT: FIX  2026-11-08T16:19:06Z
