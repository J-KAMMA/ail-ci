# job job-fuzz48-10231203  started 2026-10-23T03:04:25Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed one silent wrong answer: `range == range` compared by identity in the OBJ2 runtime. It now compares length, then start/step, with all empty ranges equal (`cruntime.py:14403`).

Commits: `c024d56` (fix + `test_ail_fuzz48`), `6d81716` (CI shard).

Probes (`bash ~/tools/cmp.sh`, both builds):
- Same as CPython: p01, p04, p06, p08, p09, p13, p14, p15, p16, p17.
- Fixed and now same: p13/p14/p16/p17 cover empty, negative, huge/int64 edges, aliasing, args, list items, dict values, attributes, nested lists.
- Other differences seen, pre-existing: range slicing (p02, TypeError), `.start/.stop/.step` (p07, p10), unhashable range (p03), 1-/3-arg `zip` refused (p05), `reversed(range).__class__.__name__` is `iterator` vs `range_iterator` (p11), `range(1.5)` internal OOM (p12).

Tests on HEAD `6d81716`: `test_ail_fuzz48`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. `update_manifest.py --check` and `ci_shards.py --check` pass. No DIFFERENCES/DEVLOG files exist in this export, so no records were added.
[cost $0.0000, opencode tokens {"total": 4488882, "input": 130530, "output": 14511, "reasoning": 11553, "cache.write": 0, "cache.read": 4332288}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: fuzz48 — range equality

**Diff read.** Single behaviour change: `ail_obj_eq_raw` now handles `AIL_T_RANGE` via new `ail__range_eq` (`cruntime.py:14406`). Plus `test_ail_fuzz48`, manifest, check-list and CI shard. No compiler/codegen change.

**Probes** (`~/tools/cmp.sh`, HEAD and `/tmp/base`, both builds):

| probe | covers | HEAD |
|---|---|---|
| p1_eq_basic | equal / unequal / negative step | **mismatch line 5** |
| p2_empty | 9×9 empty-range pairs | same |
| p3_neg | negative steps, same-sequence different-step | same |
| p4_flow | args, list item, dict value, attribute, nested list/tuple, `in` | same |
| p5_huge | ±int64 edges, extreme steps | same |
| p6_misc | self/`!=`, range vs list/tuple/int/str/None, reversed, zip, enumerate | same |
| p7_noeq | programs not using range equality | same |
| p8b_len1 | len-1 equality via all paths | **mismatch** |
| p9/p9b/p10/p11 | slicing, `.start`, 3-arg zip, `reversed` class, `range(1.5)`, step 0, int64 min literal | pre-existing |

### Defect 1 — new range-equality rule is not CPython's (missing `len == 1` case)
Probe:
```python
def main():
    print(range(0, 1, 2) == range(0, 1, 1))
main()
```
Expected (CPython 3.12): `True` — Actual (HEAD, both builds): `False`. CPython's algorithm is: equal length; if length 0 → equal; equal start; **if length 1 → equal**; else equal step (`Objects/rangeobject.c:range_equals`). The added `ail__range_eq` skips the length-1 rule, so all six comparisons in p8b_len1 (direct, `in`, `count`, dict value, attribute, nested list/tuple) return the opposite of CPython. This is within the feature the task asked to fix; the new test's `RANGE_EQ`/`RANGE_OPS` do not include it. Fix: after the start check, `if (an == 1) return 1;`. (Observed output is identical on base, which also lacked range equality, but the newly added rule is what is wrong.)

### Pre-existing (base == HEAD, do not block)
`range` slicing refused (TypeError); `.start/.stop/.step` refused; 3-arg `zip` refused; `reversed(range()).__class__.__name__` differs; `range(1.5)` handling; ranges unhashable. `range(0,5,0)` is accepted where CPython raises `ValueError` (base too); only the post-construction `==` result changed (False→True), on an invalid program.

### Claims
- Range equality by identity fixed for length ≥2 / empty: **verified**.
- "Compares length, then start/step; all empty equal": **false/incomplete** (len-1 rule missing).
- Other differences listed as pre-existing: **verified pre-existing**.
- Tests on HEAD: fuzz48 + safetynet + files + corpus_findings3, 4 modules, 0 failed: **verified**.
- `update_manifest.py --check`, `ci_shards.py --check`: **verified** (rc 0). No DIFFERENCES/DEVLOG in export: **verified**.
- Speed: **unverified** — `perf_event_open` denied (`paranoid=4`); change is one added switch case and an O(1) compare, no hot-path concern.
- C of a non-range-equality program changes by 11 lines (embedded runtime only); no output difference.

VERDICT: FIX
1. `ail__range_eq` omits CPython's length-1 shortcut. Probe `print(range(0,1,2) == range(0,1,1))`: expected `True`, actual `False` (both builds); add the case to `test_ail_fuzz48`.
[cost $0.0000, opencode tokens {"total": 1618535, "input": 55765, "output": 9734, "reasoning": 14732, "cache.write": 0, "cache.read": 1538304}]

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed the remaining range-equality defect and committed as `2f7a120`.

- `ail__range_eq` now follows CPython: equal length → empty is equal; otherwise equal start; then a length-1 range is equal regardless of step; longer ranges require equal steps.
- Added length-1 cases to `RANGE_EQ` in `test_ail_fuzz48.py`, including different steps, negative steps, different starts, and huge starts.

Probes (`bash ~/tools/cmp.sh`, both builds, all same as CPython):
- `/tmp/probes/len1.py` — direct, args, attribute, list item, dict value, nested list/tuple, `in`/`count`, empty and len-2 controls.
- `/tmp/probes/len1_nested.py` — nested containers, dict equality, loop variable.
- `/tmp/probes/len1_huge.py` — int64-edge length-1 ranges.
- `/tmp/probes/len_ge2.py` — empty and length ≥2 regression checks.

Tests on final commit: `test_ail_fuzz48`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. `update_manifest.py --check` and `ci_shards.py --check` pass. No `DIFFERENCES`/`DEVLOG` files exist in this export, so none were added.
[cost $0.0000, opencode tokens {"total": 375784, "input": 19474, "output": 3678, "reasoning": 1912, "cache.write": 0, "cache.read": 350720}]

## review 1
[model opencode/deepseek-v4.1-flash-free]
**Review of fuzz48 range-equality fix**

**Change.** `ail_obj_eq_raw` now handles `AIL_T_RANGE` via `ail__range_eq`: equal count, empty ranges equal, then equal start, length-1 equal regardless of step, longer ranges require equal step. Test/shard/manifest wiring added.

**Probes** (`~/tools/cmp.sh`, both builds, HEAD; base where noted):
- `rq_bound.py` — length 0/1/2, negative steps, empty with differing starts/steps: same as CPython on both builds; base differs (the defect).
- `rq_huge.py` — int64-edge starts/stops/steps, counts > `INT64_MAX`: same.
- `rq_paths.py` — args, list item, dict value, attribute, tuple, nested list, `in`/`count`, non-range comparisons: same.
- `rq_matrix.py` — all pairs from starts/stops `-4..4`, steps `±1..3` (486 ranges): same.
- `rq_ops.py` — range len/index/reversed/zip/enumerate controls: same except pre-existing item below.
- `rq_step0.py`, `rq_norange.py` — see pre-existing/notes.
- Worker's `/tmp/probes/len1*.py`, `len_ge2.py`: all same as CPython.

**Tests on HEAD.** `test_ail_fuzz48`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 0 failed. `update_manifest.py --check` and `ci_shards.py --check` pass.

**Claims.** All verified: commit `2f7a120`, semantics, added length-1 cases, four test modules, manifest/shard checks, absence of DIFFERENCES/DEVLOG files, worker probes.

**Pre-existing (same on base, non-blocking).**
- `enumerate([1,2,3], 9223372036854775806)` wraps past `INT64_MAX`; CPython prints `9223372036854775808`, AIL prints `-9223372036854775808`.
- `range(0,5,0)` is accepted (prints `made ...` and compares) where CPython raises `ValueError` at construction.

**Notes/speed.** `perf_event_open` is denied here, so `tools/icount.c` could not run. For `g03_004` and `g11_024` the generated C differs only by the unused inline helper and one switch label; binary sizes are unchanged, so no hot-path effect is expected. A no-range default-build program's C is byte-identical; the general path gains only the same dead helper.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1445437, "input": 69671, "output": 7771, "reasoning": 15803, "cache.write": 0, "cache.read": 1352192}]

FINAL VERDICT: ACCEPT  2026-10-23T03:58:14Z
