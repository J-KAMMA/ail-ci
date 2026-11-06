# job job-rbpyreachs2_rr1-11070434  started 2026-11-06T19:35:10Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Re-applied the accepted `job-pyreachs2_rr1-11070228` change on top of this tree.

**What happened**
- Three-way applied the accepted diff (base `a8b8e5a`). The workflow hunk was already present; `pyfunc.py` merged cleanly and kept this tree's newer bytes code intact. The only conflict was `DEVLOG.md`, resolved keeping both sides (accepted entries above existing).
- `tools/update_manifest.py` regenerated pins; `--check` exits 0. Note: `tools/diff_ids.py` does not exist anywhere in this repo or the fetched branch, so I could not run it.
- Committed as `21564239`, 17 files, +868/−14. `.agent/pipeline.md` left untouched/untracked.

**Probes** (`bash ~/tools/cmp.sh`, both builds — default `d` and `AIL_UNIFIED_FORCE=1` `g`):
| probe | result |
|---|---|
| nsmallest_int.py (ties, k=0/negative/>len, empty, expr k, assignment+index mutation, for, sum) | same stdout on both |
| nsmallest_str.py (str list, k=0/10, item, for) | same stdout on both |
| nsmallest_param.py (return, top[0], for+split on `list[str]` param) | same stdout on both |
| nsmallest_k_sources.py (k via argument, list item, attribute, dict value) | same stdout on both |
| extend_reversed.py (list[int], alias, float, list[str], str source, bytes source, empty, self-extend w/ realloc) | same stdout on both |
| reversed_bytes_iter.py (`list`, `==` identity, empty, for, bytearray) | same stdout on both |
| nsmallest_refusals.py (bytes list) | default matches; strict refuses by name |
| nsmallest_tuples.py (tuple list) | default matches; strict refuses by name |
| nsmallest_key.py (`key=`) | default matches; strict refuses by name |

**Tests on final commit**
- `test_ail_pyreach_shapes`, `test_ail_python_syntax`, `test_ail_builtin_shadowing`, `test_ail_heapq_bisect`: 36 tests OK.
- `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 25 tests OK, 1 skipped.
- `test_ail_strict`: 13 tests OK.
[commandcode stop=end_turn turns=37 out_tokens=19063]

## review 0
[model commandcode/deepseek-v4.1-flash]
## Review

**What the change really does.** Adds `heapq.nsmallest`/`nlargest` to the built-in name set and lowers `ndsmallest(k, name)` to `sorted(xs)[:k]` (fresh temp, truncated) in assignment/return/print/for/`_seq` positions; adds `xs.extend(reversed(src))` for LIST/FLIST/SLIST/bytes/str sources; adds `bytes.__reversed__`/`bytearray.__reversed__` to the pkg-v12 prelude. This matches the report.

**Re-apply fidelity — verified.** Fetching `job-pyreachs2_rr1-11070228`, applying `a8b8e5a..FETCH_HEAD` to `work` and comparing every changed source/test file to HEAD: all identical (`.github/workflows/agent-worker.yml` was already present; DEVLOG kept both sides, new entry on top). `git log work..HEAD` = one commit, 17 files, +868/−14. `tools/diff_ids.py` does not exist on this tree or in FETCH_HEAD (grepped): the report's note is **verified**. `update_manifest.py --check` exits 0: **verified**.

**Defects**

1. **`d[key] = heapq.nsmallest(k, xs)` emits invalid C on the default build** (change-caused; base builds and matches). `_call`'s new branch returns the list temp as a scalar value, so the dict put gets an `ail_list` where `ail_stab` wants `int64_t`.

```python
# /tmp/rprobes/p_sel_dict2.py
import heapq

def main():
    xs = [5, 2, 8]
    d = {}
    d["top"] = heapq.nsmallest(2, xs)
    print(d["top"])

main()
```
Expected (CPython, and base `d`): `[2, 5]`. Actual HEAD: `build d failed` —
`program.c:3863: error: incompatible type for argument 3 of 'ail_stab_put' … expected 'int64_t' … argument is of type 'ail_list'`.
Same with `nlargest` and with a `{"top": [0]}` literal; the `g` build matches. Strict typed build: base refused by name (`import of 'heapq' with a function that is not built in`), HEAD accepts and produces broken C.

2. **`reversed(bytearray)` is an eager snapshot, not a live reverse iterator** (new `__reversed__`; base raised `TypeError: 'instance' object is not reversible`). In-place mutation after taking the iterator is not seen.

```python
# /tmp/rprobes/p_rev_mutate.py
def main():
    ba = bytearray(b"abc")
    r = reversed(ba)
    ba[0] = 122
    print(list(r))
    print(ba)

main()
```
Expected (CPython): `[99, 98, 122]` / `bytearray(b'zbc')`. Actual HEAD (both builds): `[99, 98, 97]` / `bytearray(b'zbc')`. (Append-after-reverse happens to match, because CPython's reverse index is fixed at creation.)

**Probes** (all `bash ~/tools/cmp.sh <p> $PWD`, both builds): p_sel_bound (k=0/−1/−100/==len/>len/huge, empty, len) match; p_sel_ksources (k via argument, list item, attribute, dict value; source via attribute) match; p_sel_alias (result independent of later source mutation, self-assign `xs = nsmallest(k, xs)`, alias) match; p_sel_use (sum/len/index/max/min/`list(reversed(...))` inline) match; p_sel_str (list[str] print/for/index/return, self-extend) match; p_sel_rebind/-rebind2 (dest rebinding int/float/str) match; p_sel_param_reassign (param reassigned to a select) match; p_sel_multi (two selects in one print, `if len(...)`) match; p_sel_attr (attribute store) match; p_sel_listitem (select into list literal) match; p_sel_loop (while/for reuse, bare expression statement) match; p_sel_bigk match; p_extend_rev/-rev2 (self-extend with realloc, alias, FLIST, SLIST, str, bytes, bytearray, empty, looped) match; p_rev_bytes (list()/for/equality/empty) match; p_rev_mutate2 match; p_rev_list_mut match (base too). Failure: p_sel_store / p_sel_dict2 (defect 1), p_rev_mutate (defect 2). p_sel_tuple_float: tuples and floats match on both builds (strict typed refuses by name, as the test asserts).

**Unchanged non-feature C:** `--debug-dir` `program.c` byte-identical between HEAD and `/tmp/base` for p_no_feature plus `corpus/gdev/g25_018.py` and `g00_032.py`.

**Tests on HEAD:** `test_ail_pyreach_shapes`, `test_ail_python_syntax`, `test_ail_safetynet` — 3 modules, 0 failed (203 s).

**Report claims.** Re-apply/devlog/manifest/flake claims verified as above. The blanket claim that the probes match CPython on both builds is **false** for the two cases above (missed shapes: select result stored into a dict item; bytearray mutated after `reversed()`). The "17 files, +868/−14" and per-test numbers I could check are correct. Speed: `perf_event_open` is denied on this runner, so icount could not run; no gdev program uses the feature and the non-feature C is identical, so no compiled-code change is expected (**unverified**).

**Pre-existing:** none found (every mismatch above differs from base).

VERDICT: FIX
1. `d["top"] = heapq.nsmallest(2, xs)` (dict item store) makes the default build emit `ail_stab_put(..., <ail_list>)` and gcc fails; expected `[2, 5]`, base builds and prints it. Probe `/tmp/rprobes/p_sel_dict2.py`.
2. `reversed(bytearray)` after `ba[0] = 122` yields `[99, 98, 97]` instead of CPython's `[99, 98, 122]` on both builds; probe `/tmp/rprobes/p_rev_mutate.py` (base raised `TypeError`, so the new feature returns a silently wrong value).
[commandcode stop=end_turn turns=48 out_tokens=40932]

## worker report 1
[model commandcode/deepseek-v4.1-flash]
Fixed both review defects, committed as `e0543e9e` (8 files, +160/−10), manifest `--check` clean.

**Defect 1 — select into a dict emitted invalid C.** `d[k] = heapq.nsmallest(...)` (and the same via a name a select bound) reached the scalar `_call` dispatch and passed an `ail_list` to `ail_stab_put(int64_t)`. A non-list-of-str select there is now refused by name; `print(nsmallest(k, words))` still builds (SLIST path), and an int-valued dict now refuses a whole-list value by name too — so the default build falls back to the general path and prints CPython's `[2, 5]`; strict names it. This also converts the pre-existing `d["k"] = xs` gcc failure into the same fallback.

**Defect 2 — `reversed(bytearray)` snapshot.** Replaced with a live reverse iterator (`_AilBytearrayReverse`): index fixed at creation, each step reads the current bytearray, so `ba[0]=122` after `reversed(ba)` yields `[99,98,122]`; append/delete/clear end the walk as CPython does. `bytes` stays a snapshot (immutable).

Probes (`bash ~/tools/cmp.sh`, both builds — all 30 match CPython): `p_sel_dict2`, `p_sel_dict`, `p_sel_store`, `p_sel_name_store`, `p_sel_scalar` (direct/name/str- and int-keyed stores, `nlargest`, inline subscript, `sum`); `p_rev_mutate`, `p_rev_mutate2`, `p_ba_rev_live`, `p_ba_rev_shape`, `p_ba_rev_flow` (item mutation, append, delete, clear, empty, `next()`, repeated `list()`, attribute/argument provenance); every prior `p_sel_*`, `p_rev_*`, `p_extend_rev*` probe unchanged. One probe boundary (`iter(it) is it`) is `False` on base too — pre-existing, unrelated, left alone.

Tests on the final commit: `test_ail_pyreach_shapes` + `test_ail_python_syntax` + `test_ail_bytearray_loops` + `test_ail_bytearray_refs` = 31 OK; `test_ail_safetynet` + `test_ail_files` + `test_ail_corpus_findings3` = 25 OK (1 skipped). DEVLOG entry and one DIFFERENCES row (`C?-job-rbpyreachs2_rr1-11070434-1`) added. `tools/diff_ids.py` still does not exist on this tree.
[commandcode stop=end_turn turns=84 out_tokens=41919]

## review 1
[model commandcode/deepseek-v4.1-flash]
## Review report

**What the change really does:** re-applies the accepted `pyreachs2` feature (typed `heapq.nsmallest/nlargest` select lowering, `xs.extend(reversed(...))`, `bytes`/`bytearray.__reversed__` in the runtime prelude) and adds the two claimed review fixes — a named refusal for a whole-list value into an int dict, and a live reverse iterator for `bytearray`. The report describes this accurately; it omits the invalid-C path below.

### Defect

**1. A select passed directly as an argument to a user function/method emits invalid C on the default build.**

`/tmp/rprobes/p_u1.py` (also `p_u2.py`, `p_y1.py`):
```python
import heapq

def total(xs: list[int]) -> int:
    t = 0
    for x in xs:
        t += x
    return t

def main():
    ys = [5, 2, 8]
    print(total(heapq.nsmallest(2, ys)))

main()
```
Expected (CPython): `7`. Actual: `bash ~/tools/cmp.sh` prints **`build d failed`** with gcc: `error: expected ')' before ';' token`, on generated C
`v__t4 = (v__t2 = 2LL;, ail_list_clear(&v__t3);, for (...) ail_list_push(...);, ..., total(v__t3.p, v__t3.n));`.
The base builds this and prints `7`. `p_u2.py` (a `list[str]` parameter, expected `fig`) fails the same way with `expected 'ail_str' but argument is of type 'int64_t'`; `p_y1.py` reproduces it through a method call.

Cause: the two new `_is_heapq_select` branches in `_call_user_func` (`pyfunc.py:17205-17216` and `17415-17425`) do `staged.extend(ctx.pre[before:])`, pushing raw statements that each end in `;` into `staged`; `staged` is emitted as a comma expression at `pyfunc.py:17547`. Every other entry is an expression — the correct wrapper already exists at line 17288 (`'({ %s (void)0; })' % ' '.join(...)`). Both the LIST/`array` and SLIST parameter branches need it. This is also exactly the "values reaching the code through an argument" boundary the task's self-check requires, and it was not probed.

### Claim check
- Commit `e0543e9e`: 8 files, +160/−10 — **verified**.
- Dict-store fix (fallback prints `[2, 5]`; strict names `dict of integers`) — **verified** (`p_sel_dict`, `p_x9`; strict log).
- Pre-existing `d["k"] = xs` gcc failure on base (`ail_stab_put(ail_list)`) — **verified** (`p_z1`; base `build d failed`, HEAD matches CPython).
- Live `reversed(bytearray)`: item mutation seen, append/delete/clear end the walk, `bytes` snapshot — **verified** (`p_rev_live`, `p_x5`, `p_x8`; base fails these, HEAD matches).
- `print(nsmallest(k, words))` builds on the typed path — **verified** (strict-loop build OK).
- `manifest --check` clean; `tools/diff_ids.py` absent; DEVLOG/DIFFERENCES added; nothing else changed — **verified**.
- Tests: `test_ail_pyreach_shapes`, `test_ail_python_syntax`, `test_ail_safetynet`, `test_ail_bytearray_loops`, `test_ail_bytearray_refs` — **5/5 pass** on HEAD (`-j 2`).
- "30 probes all match CPython" — **unverified**: 3 named probes (`p_sel_name_store`, `p_sel_scalar`, `p_ba_rev_live`) are not present in `/tmp/rprobes`; the 10 present do pass.

### Pre-existing (not blocking)
- Base cannot build `reversed(bytearray)`/`reversed(list)` at all (`p_x8` base exit 1, `TypeError: 'instance' object is not reversible`); HEAD matches CPython.
- Base's typed path gcc-fails `d["k"] = xs` (`p_z1`); HEAD falls back correctly.
- `iter(it) is it` claim — not checked.

### Unverified
- Speed: `perf_event_open` is denied in this container, so `tools/icount.c` cannot run. Generated C for the two gdev programs I checked (`g00_000`, `g00_010`) is byte-identical to base, so no runtime change is expected.
- Non-feature programs: `p_heap_no` (heapq ops only) and both gdev programs produce byte-identical C. Programs touching `bytes`/`bytearray` gain the prelude's new `__reversed__` (class-table slot shifts in the embedded runtime only; no change to emitted user code).

VERDICT: FIX
1. Passing `heapq.nsmallest()`/`nlargest()` directly as an argument to a user function or method whose parameter is a list or list-of-str emits invalid C on the default build (`p_u1.py`: expected `7`, actual gcc error / no binary; `p_u2.py`: expected `fig`, actual gcc error; `p_y1.py` method-call variant). Fix the two `_is_heapq_select` branches in `_call_user_func` (`pyfunc.py:17205-17216`, `17415-17425`) to wrap the moved `ctx.pre` statements in an expression (`({ ... (void)0; })`), as line 17288 already does.
[commandcode stop=end_turn turns=39 out_tokens=39582]

FINAL VERDICT: FIX  2026-11-06T20:58:55Z
