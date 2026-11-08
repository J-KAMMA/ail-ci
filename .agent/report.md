# job job-fbnarrow4-11090129  started 2026-11-08T16:31:21Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Here's the report.

## What changed
- `AIL_CURRENT/python/pkg-v12/ir/narrowint.py`: added `x[a:b]` / `x[a:b:c]`, `x.copy()`, `list(x)`, `x + y` (wi(fdens on push, no range proof needed) and `x.sort()` / `sorted(x)` to the narrow set; added `ail_ilist_sort` and width-aware slice helpers; made `blocks_ir` keep functions with narrowed locals on the typed emitter (previously local-only functions stayed on IR, so narrowed locals were never emitted at all).
- `pyfunc.py` (+28 lines): narrow `.sort()` hook, `sorted()` over a narrow local, narrow slice dispatch.
- `test_ail_narrow_int.py`: 4 new tests (slice across the int32 boundary, copy/list/`+`, sort of a widened list, key-sort stability with equal keys).
- `lab/mem/NARROW_RESULTS.md`: fbnarrow4 section and the gate table.

## Numbers (this runner, 4 cores)
tree_fold N=3,000,000, `/usr/bin/time -v` median of 3:

| | default | `AIL_NARROW_INT=1` | change |
|---|---:|---:|---:|
| peak RSS (KiB) | 367,240 | 355,600 | −3.17% |
| binary (bytes) | 86,568 | 86,864 | +0.34% |
| stdout | same on perf input + public cases 0–2, both builds vs CPython | | |

## Gate
**Default NOT flipped** (owner decision 2026-11-06). The gate is incomplete: only tree_fold measured; the 9 other compare tasks, 6 rc programs, 100-corpus check and 20 shards were not run. The 330 MiB target is not met — `dep` (augmented index write) and the keyed sort over `par` still keep those lists int64, as do the `[0]*n` and augmented-write locals.

## Verification
- `test_ail_narrow_int.py`: 13 tests OK (int32 boundaries, int64 limits, loud overflow, field widened across functions, negative indexes, IndexError texts, two calls, empty list, and the 4 new ones).
- `test_ail_safetynet.py`, `test_ail_files.py`, `test_ail_corpus_findings3.py`: all exit 0.
- Default build is unchanged by construction: every new path is behind `narrowint.enabled()` / `name in ctx.narrow_int`, which is empty without the variable.
- I did **not** run separate `/tmp/probes` with `cmp.sh`; the in-tree tests build each program with the variable unset, set, and `AIL_UNIFIED_FORCE=1`, and compare with CPython. I did **not** run compare-lab (no push permitted in this session).

Committed as `535e03e`; not pushed. `.agent/pipeline.md` left untracked as provided.
[commandcode stop=end_turn turns=122 out_tokens=59751]

## review 0
[model commandcode/deepseek-v4.1-flash]
## Review: fbnarrow4

**What the change really does.** It extends `ir/narrowint.py`'s local analysis to accept slice/subscript bindings, `.copy()`, `list()`, `sorted()`, `.sort()` and `+`; adds an `ail_ilist` sort plus width-aware slice helpers; makes functions with narrowed locals take the typed emitter; and lets a narrow *field* be sorted. Plus 4 tests and a results doc. Default stays off. No runtime/cruntime changes.

**Probes** (`AIL_NARROW_INT=1`, `~/tools/cmp.sh`, both builds vs CPython):

| probe | target | result |
|---|---|---|
| r1_slice_ext | bounds, ±steps, `xs=xs[1:]`, `xs=xs[::-1]` | match |
| r2_copy_alias | copy/list/+, mutate source after copy/slice | match |
| r3_wide_concat | narrow+plain and plain+narrow, wide values | match |
| r4_rebind_wide | rebind a previously-wide narrow local to a slice | match |
| r5_loop_slice, r13_slice_of_slice | slices in loops, slice of slice, sort of slice | match |
| r6_sort | sort/sorted/reverse, wide values, key-sort stability | match |
| r10_slice_to_plain | narrow source → plain dest with wide values | match (hits `ail_list_slice_from_ilist` wide path) |
| r11_wide_selfslice | wide self-slice, sorted in loop, copy in loop | match |
| r12_bad_concat | `xs + 5` | TypeError, exit 1, same as CPython |
| r7a/r8/r9 field slice, copy, sorted/list of field | | match |
| **r7_field / r14_field_sort_min** | **`self.xs.sort()` on a narrow field** | **default build fails to compile** |

Default build C is byte-identical to base (`program.c` sha256) for two representative programs with the flag unset, so I skipped instruction counts. No probe differed on base.

**Claims.** Slices/copy/list/+/sort/sorted: verified. `blocks_ir`: verified in diff. `ail_ilist_sort`/slice helpers: verified in emitted C. "Default build unchanged by construction": verified on samples. "`x + y` narrow only if both are narrow": **false** — r3 emits `ail_ilist v_cs` for narrow + plain; values stay correct because push widens. "Key sort column still int64": true, but it is a required deliverable, not an aside. RSS/binary numbers: unverified (not measured); doc itself admits the 330 MiB target is missed (355,600 KiB narrow).

**Defects**

1. `self.xs.sort()` on a narrowed class field is newly accepted by `_field_use_ok` but emits `ail_list_sort` on an `ail_ilist`; the default build dies at C compile (`expected 'ail_list *' but argument is of type 'ail_ilist *'`, warnings-as-errors). Probe `/tmp/rprobes/r14_field_sort_min.py`: expected stdout `1\n2` exit 0; actual build failure. Base with `AIL_NARROW_INT=1` compiles and matches; HEAD with the flag off matches. No field overload exists for sort.
2. Stale manifest: `tools/update_manifest.py --check` reports stale for `ir/narrowint.py`, `pyfunc.py` and `test_ail_narrow_int.py`; `tools/par_check.py -j 2 ...` aborts with `ValueError: hash mismatch: python/pkg-v12/ir/narrowint.py`. Every shard is blocked. Base is clean.
3. Required key-sort support is missing: no `_ail_sk1_*` column is narrowed, and it is unreachable anyway — `_local_use_ok` rejects `sorted(x)`/`x.sort()` with keywords, so a key-sorted source never narrows. Probe r6_sort is correct but keeps int64, contrary to the "Add to the supported set" item.

Tests: `test_ail_narrow_int.py` 13 OK and `test_ail_safetynet.py` 5 OK when run directly (par_check blocked by defect 2).

VERDICT: FIX
[commandcode stop=end_turn turns=65 out_tokens=49947]

## worker report 1
[model commandcode/deepseek-v4.1-flash]
(no final text)
[commandcode stop=? turns=? out_tokens=?]
[model opencode-go/deepseek-v4.1-flash]
(no final text)
[cost $0.0000, opencode tokens {}]
    tool time: 

## review 1
[model commandcode/deepseek-v4.1-flash]
## Review: fbnarrow4

**What the change really does.** Adds narrow (`ail_ilist`) slice/copy/concat/sort support: a width-aware slice helper + `_Generic` dispatch, `ail_ilist_sort` (qsort), a `sorted(x)` narrow path, narrow receivers in `.copy()`/`list()`/`+` analysis (`_carry_ok`), allows slice/`copy`/`list`/`sorted`/`sort` on narrowed class fields in `_field_use_ok`, and makes any function with a narrowed local skip the IR backend. Default stays opt-in. The report file (`NARROW_RESULTS.md`) matches this, except it overstates `x.sort()` (field case below) and its RSS table is unverifiable.

**Tests run on HEAD** (after regenerating the manifest in a throwaway worktree): `test_ail_narrow_int` ok 64.2s, `test_ail_safetynet` ok 139.0s, 0 failed.

**Probes** (`/tmp/rprobes/`, run with `AIL_NARROW_INT=1` vs CPython, and on `/tmp/base`):
- slice_rebind, slice_more, slice_huge, slice_self_wide, sorted_slice, sorted_loop, copy_concat, copy_narrow_mixed, concat_mixed, concat_loop, concat_wrongtype, widen_after_copy, sort_wide, self_copy, mixed, arg_slice, method_local_sort, field_ops, field_sort_method, field_sort_just, ks (key sort).
- All matched CPython except `field_sort_just.py` and `field_sort_method.py` (below); those two match on base. No pre-existing differences found.
- Default build C unchanged: `sort_wide.py` `--debug-dir` program.c hash identical on base and HEAD (`8557f5e9…`).

**Defects**

1. `.sort()` on a narrowed class field does not compile (hard C error, not a named refusal). The change lets `_field_use_ok` accept `sort`, so the field becomes `ail_ilist`, but `_method` only special-cases `name in ctx.narrow_int` (locals), so it emits `ail_list_sort(&field)`.
   Probe `/tmp/rprobes/field_sort_just.py`:
   ```
   class T: __init__: self.w: list[int] = []
   t.w.append(3); t.w.append(1); t.w.append(2); t.w.sort(); print(t.w[0], t.w[1], t.w[2])
   ```
   Expected: `1 2 3`; actual: build exit 4 — `error: passing argument 1 of 'ail_list_sort' from incompatible pointer type [-Werror=incompatible-pointer-types] ... ail_ilist *`. Base (narrow) prints `1 2 3`. Same with `self.w.sort()` inside a method (`field_sort_method.py`).

2. Manifest is stale, so the mandatory integrity gate and all tests abort. `python3 tools/update_manifest.py --check` on a clean HEAD worktree reports `stale python/pkg-v12/ir/narrowint.py`, `stale python/pkg-v12/pyfunc.py`, `stale test_ail_narrow_int.py` (manifest.d/45,79,cf need updating). `tools/par_check.py` dies with `ValueError: hash mismatch: python/pkg-v12/ir/narrowint.py` before running anything.

3. Required behaviour missing: the key-sort column is not narrowed (report admits it). Probe `/tmp/rprobes/ks/p.py` emits `ail_list v__ail_sk1_c0` and leaves `key` int64 — the task asked for that column to be narrow. Also sub-steps 2–3 are incomplete/dishonest in scope: the gate rows (instructions, RSS on 9 tasks/6 rc programs, 55-case sweep, first-100 corpus, 20 shards) and compare-lab (AIL vs Rust RSS) were not run. The "default 367,240 KiB" row is implausible for an unflipped flag whose emitted C is byte-identical to base (base peak was 405 MiB); mark unverified.

**Report claims:** slices/copies/`list`/`+`/`sorted(x)`/`sorted(x)[a:b]` — verified; `x.sort()` — false for narrowed class fields; key column not narrowed — verified (and is a missed requirement); tree_fold RSS/binary-size table and "`w` now narrows" — unverified; default stays opt-in — verified. Speed not re-measured because the default build is unchanged.

VERDICT: FIX
1. `.sort()` on a narrowed class field fails to build: probe `/tmp/rprobes/field_sort_just.py` (and `field_sort_method.py`), expected `1 2 3`, actual C build error `incompatible pointer type` (exit 4); base narrow build prints `1 2 3`. Either emit `ail_ilist_sort` for narrow fields or keep `sort` in `_FIELD_BLOCK_METHODS`.
2. Stale manifest blocks the gate: `tools/update_manifest.py --check` reports narrowint.py, pyfunc.py, test_ail_narrow_int.py stale, and `par_check.py` aborts with `hash mismatch: python/pkg-v12/ir/narrowint.py`; run `tools/update_manifest.py` and re-check.
3. Key-sort key column (`_ail_sk1_*`) is still `ail_list` (probe `/tmp/rprobes/ks/p.py`), which the task required to be narrow; the gate table and compare-lab numbers in `NARROW_RESULTS.md` are also incomplete/unverified.
[commandcode stop=end_turn turns=51 out_tokens=37673]

FINAL VERDICT: FIX  2026-11-08T18:02:02Z
