# job job-std_copy-11012212  started 2026-11-01T13:13:44Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed as `42195f6` on `job-std_copy-11012212`.

**Review defects**
- `__getstate__`/`__setstate__` now refused by name (joined `_COPY_PROTOCOL`).
- Runtime-assigned hooks now refused: `C.__copy__ = f`, `C.__deepcopy__: t = f`, class-body assignments, and `setattr(C, "__...__", f)`.
- Deep `set`/`frozenset` now memoises CPython's temporary reduce list; explicit memo matches `3` entries and value kinds.

**Probes** (all in `/tmp/probes`, both builds)
- `rv_state`, `rv_dynamic`, `copy_state_shallow`, `copy_class_body_assign`, `copy_dynamic_setattr`, `copy_dynamic_annassign`: named refusal.
- `rv_frozen`, `rv_frozen_vals`, `copy_set_memo2`: match CPython, including memo shape.
- `copy_normal_paths`: unchanged copy behaviour matches CPython.
- `copy_no_usage2`: no false refusal without a copy call.

**Tests / manifest**
- `test_ail_std_copy`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_genlib`: 5 modules, 0 failed (454s).
- `python3 tools/update_manifest.py --check`: rc 0.
- No `lab/compare/src` program imports module `copy`, and the copy runtime fragment is emitted only when used, so their C is unaffected.
[cost $0.0000, opencode tokens {"total": 2527502, "input": 149661, "output": 11566, "reasoning": 14915, "cache.write": 0, "cache.read": 2351360}]
    tool time: bash 9.6 min, edit 0.0 min, read 0.0 min
        456s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 2400 python3 tools/par_check.py -j 2 test_ail_std_copy t
         44s bash   cd /tmp/probes && for f in rv_state rv_dynamic rv_frozen rv_frozen_vals copy_set_memo2 copy_no_usage copy_stat
         38s bash   cd /tmp/probes && for f in rv_state rv_dynamic rv_frozen rv_frozen_vals copy_set_memo2 copy_normal_paths copy_
         21s bash   cd /tmp/probes && for f in rv_state rv_dynamic rv_frozen rv_frozen_vals; do echo "######## $f"; bash ~/tools/c
         12s bash   cd /tmp/probes && for f in rv_state rv_dynamic rv_frozen rv_frozen_vals; do echo "######## $f"; bash ~/tools/c
          4s bash   cat > /tmp/probes/copy_no_usage2.py <<'PY' class WithCopy:     pass  def alt(self):     return "special"  With
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && git status --short | head -30 && pyt
          0s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 2400 python3 tools/par_check.py -j 2 test_ail_std_copy t

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does.** Adds `__getstate__`/`__setstate__` to `_COPY_PROTOCOL` and refuses protocol hooks assigned at class-body/runtime (Assign, AnnAssign, AugAssign, literal `setattr`), and rewrites deep `set`/`frozenset` copying to create/memoise a temporary list, keep-alive it, then build the result set.

**Claims checked**
- `__getstate__`/`__setstate__` now refused by name: **verified** (`rv_state`: both builds refuse with `WithState.__getstate__`).
- Runtime hooks refused (`C.__copy__ = f`, `C.__deepcopy__: t = f`, class-body assignment, literal `setattr`): **verified** (`rv_dynamic`, `copy_class_body_assign`, `copy_dynamic_annassign`, `copy_dynamic_setattr`).
- `rv_frozen` now `3 False True`; `rv_frozen_vals` / `copy_set_memo2` match: **verified**.
- "explicit memo matches 3 entries and value kinds": **verified for count/kinds, false for aliasing** (defect below).
- No-copy programs still build/run and C unaffected: **verified** (`rv_nocopy_simple`, `copy_no_usage2`; `program.c` byte-identical HEAD vs base for the 5 buildable `lab/compare` tasks; the other 5 refuse identically on both).
- `test_ail_std_copy` **ok** (94s), `test_ail_safetynet` **ok** (168s), `update_manifest.py --check` rc 0.

**Defect**
1. The memoised temporary list and the keep-alive list are the same object, so mutating the memo's copied list also changes CPython's kept-alive original. Probe `/tmp/rprobes/rv_memo_alias.py`:
```python
import copy
def main() -> None:
    m = {}
    copy.deepcopy(frozenset({1, 2}), m)
    lists = [v for v in list(m.values()) if type(v).__name__ == "list"]
    for v in lists:
        if all(type(e).__name__ == "int" for e in v):
            v.append(9)
    for v in lists:
        for e in v:
            if type(e).__name__ == "list":
                print("nested", len(e))
main()
```
CPython expected `nested 2`; HEAD general and default builds print `nested 3` (base printed nothing). CPython keeps the *original* reduce list in the keep-alive list and the *copied* list in the memo; the implementation uses one list for both. Fix needs two distinct lists.

**Pre-existing** (identical on base): `setattr(SomeClass, name, f)` with a non-literal name fails with `NotImplementedError: setattr() on a 'type' value ...` (`rv_setattr_var`), so that dynamic-hook path is not a copy regression.

**Unverified.** Instruction-count/speed (the change only affects deep-copying sets/frozensets, no hot path touched); `test_ail_files` / `test_ail_corpus_findings3` and `test_ail_genlib` (worker-reported pass, not rerun).

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 1333984, "input": 60735, "output": 6512, "reasoning": 22193, "cache.write": 0, "cache.read": 1244544}]
    tool time: bash 13.0 min
        380s bash   cd /home/runner/work/ail-ci/ail-ci && date && rm -rf /tmp/dbghead /tmp/dbgbase && mkdir -p /tmp/dbghead /tmp/d
        169s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 900 python3 tools/par_check.py -j 2 test_ail_safetynet 2
        120s bash   cd /home/runner/work/ail-ci/ail-ci && date && nohup python3 tools/par_check.py -j 2 test_ail_std_copy test_ail
         27s bash   cd /tmp/rprobes && date && for f in rv_state rv_dynamic rv_frozen rv_frozen_ident rv_frozen_nested rv_set_shar
         20s bash   cd /tmp/rprobes && cp /tmp/probes/rv_frozen_vals.py /tmp/probes/copy_set_memo2.py . && cat > rv_memo_mutate.py
         16s bash   cd /tmp/rprobes && date && for f in rv_state rv_dynamic rv_frozen; do echo "######## $f BASE"; timeout 150 bas
         11s bash   cd /tmp/rprobes && cat > rv_dictset.py <<'PY' import copy  class C:     pass  def alt(self):     return "speci
         10s bash   cd /tmp/rprobes && cat > rv_memo_alias.py <<'PY' import copy  def main() -> None:     m = {}     copy.deepcopy

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed the remaining review defect: the deep copier now uses two distinct lists for `set`/`frozenset` (original reduce list kept alive, copied list memoised), matching CPython aliasing.

- Probe `rv_memo_alias`: now `nested 2` on both builds (was `nested 3`).
- `rv_frozen`, `rv_frozen_vals`, `rv_memo_vals`, `rv_memo_mutate`: match CPython on both builds.
- `rv_state`, `rv_dynamic`: still refused by name on both builds.
- Added the alias regression to `test_ail_std_copy`.
- Tests: `test_ail_std_copy`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4/4 pass, 0 failed.
- `update_manifest.py --check` rc 0.

Committed as `e478479`.
[cost $0.0000, opencode tokens {"total": 1083889, "input": 50306, "output": 5281, "reasoning": 7502, "cache.write": 0, "cache.read": 1020800}]
    tool time: bash 13.4 min
        357s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 2400 python3 tools/par_check.py -j 2 test_ail_std_copy t
        357s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 2400 python3 tools/par_check.py -j 2 test_ail_std_copy t
         54s bash   cd /tmp && for f in rv_memo_alias rv_frozen rv_frozen_ident rv_frozen_nested rv_frozen_vals rv_memo_vals rv_me
         27s bash   cd /tmp && for f in rv_memo_alias rv_frozen rv_frozen_vals rv_memo_vals rv_memo_mutate rv_state rv_dynamic; do
          5s bash   cd /tmp && bash ~/tools/cmp.sh /tmp/rprobes/rv_memo_alias.py /home/runner/work/ail-ci/ail-ci 2>&1 | tail -30
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py 2>&1 | tail -30; git status --short
          0s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 2400 python3 tools/par_check.py -j 2 test_ail_std_copy t

## review 1
[model opencode/deepseek-v4.1-flash-free]
**What the change really does.** `work..HEAD` (3 commits) adds `__getstate__`/`__setstate__` and runtime-assigned hooks to the named copy-protocol refusal, and rewrites set/frozenset deepcopy to follow CPython's reduce shape: an original element list (kept alive) plus a separate deep-copied list memoised under the original's id, then the result memoised under the set's id. The named last commit (`e478479`) only separates the one list that previously served both roles; the two hook defects were fixed in `42195f6` in the same branch.

**Claims checked**
- `rv_memo_alias` prints `nested 2` on general and default: **verified**.
- `rv_frozen`, `rv_frozen_vals`, `rv_memo_vals`, `rv_memo_mutate` match CPython both builds: **verified**.
- `rv_state`, `rv_dynamic` refused by name both builds: **verified**.
- Alias regression added to `test_ail_std_copy`: **verified** in diff.
- 4 named modules pass, 0 failed: **verified** (`356s`, -j 2).
- `update_manifest.py --check` rc 0: **verified**.
- Report is accurate for its commit; it omits that the branch also fixes the two earlier hook defects (not a false claim).

**Own probes** (cmp.sh, general + default)
- `r2_repeat`, `r2_types`, `r2_shared`, `r2_dictval`, `r2_paths`, `r2_order`, `r2_nohooks`, `r2_inst_alias`: same stdout as CPython; memo order now `['list','list','frozenset']` as CPython.
- `r2_cycle`, `r2_cycle2`: set/back-reference semantics now match CPython (`False False` etc.); base was wrong (`True`, refs preserved). Memo counts still short only by instance-dict entries (below).
- `r2_dicthook`, `r2_typehook`, `r2_setattrvar`: exotic dynamic-hook forms refused or fail identically on base; not caused here.
- Non-copy `program.c` byte-identical base/head; `lab/compare/berth_sim` `program.c` identical (`0cf247…`).

**Pre-existing (non-blocking)**
- Instance deepcopy never memoises/keep-alives the state `__dict__`: `r2_plain_inst` CPython `4/5` vs base and head `3/4` (identical on base). This is the remaining gap in `r2_inst` (head 7 vs CPython 9), `r2_cycle` (5 vs 6) and `r2_cycle2` (6 vs 7); the set change actually reduced those gaps.
- `id()` and class-level `setattr` unsupported (`rv_frozen_ident`, `r2_setattrvar`) on both base and head.

**Unverified.** Speed/icount (copy is not in the gdev hot path); diffs of all 10 compare C files (grep shows no `copy` use; spot-checked one); wider suite intentionally not run.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1411427, "input": 64134, "output": 7687, "reasoning": 29782, "cache.write": 0, "cache.read": 1309824}]
    tool time: bash 9.4 min
        357s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 2400 python3 ../tools/par_check.py -j 2 test
         42s bash   cd /tmp/rprobes && for f in r2_shared r2_types r2_nohooks r2_dictval r2_order r2_plain_inst; do echo "########
         38s bash   cd /tmp/rprobes && for f in rv_state rv_dynamic rv_frozen rv_frozen_vals rv_frozen_ident rv_frozen_nested rv_m
         23s bash   cd /tmp && rm -rf dbgcmp2 && mkdir -p dbgcmp2 && for wt in /tmp/base /home/runner/work/ail-ci/ail-ci; do tag=$
         16s bash   cd /tmp/rprobes && echo "### BASE r2_plain_inst"; timeout 150 bash ~/tools/cmp.sh r2_plain_inst.py /tmp/base 2
         16s bash   cd /tmp/rprobes && for f in r2_cycle r2_repeat r2_inst; do echo "######## $f"; timeout 150 bash ~/tools/cmp.sh
         16s bash   cd /tmp/rprobes && for f in r2_cycle r2_inst r2_repeat; do echo "######## BASE $f"; timeout 150 bash ~/tools/c
         11s bash   cd /tmp/rprobes && cat > r2_keeporder.py <<'PY' import copy  class Box:     def __init__(self, n):         sel

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-01T15:29:05Z
