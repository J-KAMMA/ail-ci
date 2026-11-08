# job job-rbwedge4-11090123  started 2026-11-08T16:29:00Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. The remaining defect was the NaN-identity hole in lifted float-field methods.

**Fix** (`AIL_CURRENT/ail_cpython_hybrid.py`): the method plan now applies the standalone C117 gate. When `unified.nan_capable(tree)` is true (a NaN/inf can be made), any method that reads or writes a `float` field, takes a `float` parameter, or returns `float` is refused with the named reason `the program can make a NaN, so a float field would lose its identity`. `int`-only methods still lift and finite-float programs still accelerate. Added regression test `test_nan_float_field_method_stays_in_cpython`; DIFFERENCES row `C?-job-rbwedge4-11090123-1` and a DEVLOG entry.

**Probes** (hybrid build vs CPython; `bash ~/tools/cmp.sh` default/general also run):
- `p15_nan_containers` — same stdout; `C.get` refused by the NaN reason.
- `p13_nan_set` — same; refused by name.
- `p_nan_param` (NaN via argument), `p_nan_write` (method writes NaN) — same; refused by name.
- `p_nan_listfield` — same; refused (not wired).
- `p_finite_float` — same; `C.get` still accelerated.
- `p_is_int` — same; still refused by `is` (`C114`).
- Standalone g/d builds: all `same stdout` or refused by name.

**Checks**: `update_manifest.py --check` passes (only the test-file pin changed); `tools/diff_ids.py` does not exist here. Final commit `48814c9`.

**Tests on the final commit** (`-j 2`): `test_ail_cpython_hybrid`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed, 174 s.
[commandcode stop=end_turn turns=42 out_tokens=18477]

## review 0
[model commandcode/deepseek-v4.1-flash]
## Review of `job-rbwedge4-11090123` (commit `48814c9`)

**What the diff really does.** In `ail_cpython_hybrid.build()` it computes `unified.nan_capable(tree)` and, when true, refuses every liftable method kernel that reads/writes a `float` field or whose selected clone has a `float` parameter or return; plus a regression test, DEVLOG row, DIFFERENCES row and the manifest pin. It applies only the C117 scan, not the C118 "NaN the scan cannot see" rule that the standalone path uses.

**Probes (hybrid build; `bash ~/tools/cmp.sh` also run)**

| probe | HEAD hybrid | base hybrid | standalone g/d (HEAD) |
|---|---|---|---|
| p15_nan_containers | same, `C.get` refused (NaN) | False×4 (defect) | same |
| p13_nan_set | same, refused | False | same |
| p_nan_write (writes float field) | same, refused | — | same |
| p_nan_param (float param) | same, refused | — | same |
| p_nan_listfield | same, refused "not wired" | — | same |
| p_is_int | same, refused "compares numbers with `is`" | — | same |
| p_finite / p_intfield / p_boolfield | same; `C.get`/`D.get`/`B.get` accelerated | — | same |
| p_nofeature | C byte-identical to `/tmp/base` (`program.c` md5 `c7b0977…`) | — | same |
| **p_nan_arith** | **DIFF False False False, `C.get` accelerated** | same DIFF | same stdout |
| **p_nan_split** | **DIFF False, `C.get` accelerated** | same DIFF | same stdout |

**Defect (fix incomplete).** The guard only fires when `nan_capable` can see a NaN token. A NaN made by arithmetic on an overflow, or parsed from data, is invisible to it — exactly the case the standalone path's C118 `float_search_risk` covers (both probes are `same stdout` on g/d). The lifted float method still boxes a fresh NaN, so container membership silently flips:

`/tmp/rprobes/p_nan_arith.py`
```python
class C:
    def __init__(self, f: float): self.f = f
    def get(self) -> float: return self.f
x = 1e308 * 10.0
n = x - x
c = C(n)
print(c.get() in {c.f}); print(c.get() in [c.f]); print(c.get() in (c.f,))
```
CPython `True True True`; HEAD hybrid `False False False`, report `acc ['C.get']` (base identical, so the class of defect predates this commit but is the defect the task asked to close).

`/tmp/rprobes/p_nan_split.py`
```python
s = 'n' + 'an'
n = float(s)
c = C(n); d = {c.f: 1}
print(c.get() in d)
```
CPython `True`; HEAD hybrid `False`, `C.get` accelerated.

Fix direction: gate the method plan on the same condition the standalone path uses for a float container search (`float_search_risk`), or refuse float-touching methods whenever a float container search exists, not only on `nan_capable`.

**Claim check.** Guard added as described: verified. Float field/param/return refusal: verified (p15, p13, p_nan_write, p_nan_param); list-field method refused for a different reason ("not wired") but still CPython: verified. `int` methods and finite floats still accelerate: verified. Regression test present and passes: verified. DIFFERENCES row/DEVLOG present: verified. `p_is_int` still refused: verified. `update_manifest.py --check` = 0 and `tools/diff_ids.py` absent: verified. Test claim 2/4: `test_ail_cpython_hybrid test_ail_safetynet -j 2` → 2 modules, 0 failed, 86 s.

**Pre-existing (does not block).** p_nan_arith/p_nan_split are identical on `/tmp/base`; I still count them because they are the same defect and its named fix direction.

**Unverified.** `test_ail_files`, `test_ail_corpus_findings3` (not rerun per no-wider-suite rule); instruction counts (change is build-time/hybrid-only; standalone C unchanged).

VERDICT: FIX
1. NaN identity still lost in lifted float-field methods when the NaN is not visible to `nan_capable`: `/tmp/rprobes/p_nan_arith.py` expected `True True True`, actual `False False False` (hybrid, `C.get` accelerated); `/tmp/rprobes/p_nan_split.py` expected `True`, actual `False`. Standalone g/d builds handle both correctly via C118, so the method plan must apply the same gate.
[commandcode stop=end_turn turns=26 out_tokens=23317]

## worker report 1
[model commandcode/deepseek-v4.1-flash]
## Report

**Defects fixed (commit `9adf8c8`)**

1. *NaN identity still lost when the NaN is invisible to `nan_capable`* (`p_nan_arith`, `p_nan_split`) — fixed. The method plan now refuses any method that reads/writes a `float` field or takes/returns `float` when the program performs a container search (`in`/`not in`, non-constant `==`/`!=`, `count`/`index`/`remove`/`get`/`pop`/`setdefault`/`discard`, non-constant subscript), with the named reason `the program searches a container, so a float field would lose a NaN's identity`. This is needed because `unified.float_search_risk` scans a function plan and never fires for module-level class code (confirmed with `AIL_UNIFIED_STATS`).

**Before → after**
- `p_nan_arith.py`: `False False False`, `C.get` accelerated → **same stdout**, `C.get` refused by name.
- `p_nan_split.py`: `False`, `C.get` accelerated → **same stdout**, refused by name.
- `p15_nan_containers.py` / `p13_nan_set.py`: already fixed (NaN reason), unchanged.

**Probes (all hybrid builds match CPython; `bash ~/tools/cmp.sh` g/d match or refuse by name)**
`p_nan_arith`, `p_nan_split`, `p_nan_subscript`, `p_nan_count`, `p_nan_argument`, `p_nan_alias`, `p_nan_empty`, `p_nan_negative`, `p_nan_container_eq`, `p_nan_write_arith`, `p_nan_listfield`, `p15_nan_containers`, `p13_nan_set`, `p_nan_param`, `p_nan_write`, `p_attr_nan`, `p_finite_search`, `p_finite_float`, `p_intfield_search` (still accelerates `D.get`), `p_boolfield` (still accelerates `B.get`), `p_nofeature`. Standalone g/d: all `same stdout`; `p_is_int` refuses by name (`C114`). Pre-existing and untouched: standalone `tuple == tuple` holding a NaN raises `ValueError` in `tuplegen` (both builds), never reached by the hybrid.

**Tests (on the final commit, `-j 2`)**
`test_ail_cpython_hybrid` 18 OK (37 s), `test_ail_safetynet` 5 OK (87 s), `test_ail_files` 18 OK/1 skipped (67 s), `test_ail_corpus_findings3` 2 OK (151 s). New regression test `test_nan_made_by_arithmetic_keeps_float_methods_in_cpython` passes.

`python3 tools/update_manifest.py` ran; `--check` exit 0. DEVLOG entry and DIFFERENCES row `C?-job-rbwedge4-11090123-2` added. `.agent/pipeline.md` left untracked.
[commandcode stop=end_turn turns=70 out_tokens=39164]

## review 1
[model commandcode/deepseek-v4.1-flash]
## Review: `job-rbwedge4-11090123`

**What the diff really does.** Extends the hybrid method-plan refusal: `build()` now calls `unified.nan_capable(tree)` and a new syntactic `_searches_a_container(tree)` (`in`/`not in`, non-constant `==`/`!=`, `count/index/remove/get/pop/setdefault/discard`, non-constant subscript); when either fires, a method that reads/writes a `float` field or has a `float` param/return is refused by name. Records/tests only. Matches the report.

**Claim check**
- p15/p13 (review defect) fixed: verified — HEAD hybrid `True True True True` = CPython; base hybrid `False ×4`.
- `p_nan_arith`/`p_nan_split`: verified (`same stdout`, `C.get` refused with the container reason).
- All 19 probes in `/tmp/probes` + p13/p15: verified `same stdout`, int methods still `accelerated`, `p_is_int` refused `C114`.
- Tests on HEAD, `-j 2`: `test_ail_cpython_hybrid` 37.9s ok, `test_ail_safetynet` 89.4s ok, 0 failed.
- `update_manifest.py --check` exit 0; `tools/diff_ids.py` absent; DEVLOG/DIFFERENCES rows present.
- No-feature hybrid artifacts HEAD vs base: identical (only path strings differ).
- Wrong claim in the last review, not the worker: `/tmp/base` (= `work`, `cedbed6`) **does** lift methods and prints the same wrong `False`/`2`; review 1's "base hybrid: methods not lifted" does not reproduce.

**Defects caused by this change**: none — the change only adds refusals, so output is always CPython's; two new regression tests pass.

**Pre-existing (identical on base, do not block)**: the search whitelist misses identity-sensitive container mutation, so a NaN made by arithmetic (invisible to `nan_capable`) still loses identity in the hybrid:
- `/tmp/rprobes/p_a_setadd.py` `s.add(c.val())` → CPython `1`, base & HEAD `2`
- `p_c_setupdate.py` `s.update({c.val()})` → `1` vs `2`
- `p_d_ior.py` `s |= {c.val()}` → `1` vs `2`
- `p_b_dictupdate.py` `d.update({c.val(): 2})` → `1 [2]` vs `2 [1, 2]`
- `p_j_nanarg.py` float param/return `ident`, only `s.add` → `1` vs `2`
(`add/update/|=`, `dict.fromkeys`, `set()`/`dict()` constructors are not in `_SEARCH_ATTRS`; g/d builds give the correct value.) A follow-up job should widen the search detection.

**Unverified**: g/d builds for probes other than p_a/p_b/p_nofeature2/p15 (the four ran `same stdout`); instruction counts (the diff is build-time hybrid planning only — no g/d or bench path); `test_ail_files`/`test_ail_corpus_findings3` (not rerun, per no-wider-suite rule).

**Nit**: DIFFERENCES row `…-1` still says a finite-float program "keeps accelerating" citing `p_finite_float`, which the later container guard now refuses (its dict membership). Historical row, no behavioural effect.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=34 out_tokens=29896]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-08T18:25:01Z
