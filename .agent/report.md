# job job-pyreachs2_rr1-11062251  started 2026-11-06T14:02:29Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
I'll start by checking the repository state and the previous run's branch and log.
[commandcode stop=max_turns turns=250 out_tokens=118502]

## review 0
[model commandcode/deepseek-v4.1-flash]
Review complete. Findings below.

## What the change really does

Only **two** of the five listed changes are in `work..HEAD`: (a) `heapq.nsmallest/nlargest(k, listname)` lowered to `sorted(xs)[:k]` / `sorted(xs, reverse=True)[:k]` (`_heapq_select`, wired into `_call`, `_stmt`, `_iter_plan`, `_seq`, `_call_user_func`, plus the heapq name sets in `ail_syntax`, `_IMPLICIT_LIB`, `shadowing`), and (b) `xs.extend(reversed(src))` in `_method`, plus general-path `bytes/bytearray.__reversed__` in `prelude_bytes`. Stepped slices, `del name` and heapq-on-subscript were already in the base tree (`_stepped_slice_temp`, `ast.Delete` at 24262 in `/tmp/base`), so the DEVLOG statement is accurate.

## Defects

1. **`heapq.nsmallest` on a list *parameter* emits invalid C instead of refusing by name.** Probe `/tmp/rprobes/t5_param.py` (`def pick(k, xs): return heapq.nsmallest(k, xs)`), expected CPython `[1, 2]\n[3, 1, 2]`; actual: strict build fails with `program.c:4007: error: incompatible types when initializing type 'int64_t' ... using type 'ail_list'`. Variant `t5c_paramlocal.py` (`top = heapq.nsmallest(k, xs); return top[0]`) gives `error: cannot convert to a pointer type` / `'v_top_len' undeclared`. On `/tmp/base` the same program is a clean named refusal (`import of 'heapq' with a function that is not built in`), so the change caused it. Cause: the new `_param_kinds` line adds `node.args[1].id` to the `array` set, so the parameter is typed `array`, while `_heapq_select` returns an `ail_list` temp.
2. **`xs.extend(reversed(src))` with a list-of-str source is dead code.** Probe `t3c_slist_self.py` (`words: list[str]; words.extend(reversed(words))`), expected `['b', 'a', 'a', 'b']`; actual named refusal `'words' is a slist; only an array, a list, ... are walked as flat sequences here`. The new `declared == SLIST and kind == SLIST` branch calls `_seq` on an slist name, which `_seq` cannot walk, so the branch can never succeed. Same for `words.extend(reversed(w2))` (`t3_ext_rev.py:20`). The task explicitly lists list sources for `extend(reversed(...))`.
3. **`for w in heapq.nsmallest(k, words)` is refused with a misleading diagnostic** (`t2b_ns_for.py`, expected `b\na`): `'w' is a str and is being assigned an int`. The int-list form works (`t1_ns.py` typed-OK), so the DEVLOG claim that the select is "wired through ... the for-loop ... paths" holds only for int lists.

No silent wrong output was found; everything that built typed matched CPython.

## Verified / false claims

- `nsmallest/nlargest` = `sorted[:k]` incl. ties, `k<=0`, `k>len`, negative `k`, statement/loop reuse, `len`, `sum`, inline `for` over ints, source left unsorted, result independent of later source mutation — verified (`t1_ns.py` typed-OK; `p1_ns_edge.py` both builds).
- "list[int] and list[str]" — int verified; str works for value/statement but not for `for` (#3). Lists of tuples refused by name (task asked for them) — named refusal, acceptable under the stop rule.
- `extend(reversed(src))` for `list[int]` incl. self-extend with reallocation (200 elems), bytes source, empty source, alias — verified (`t3a2.py`, `p2_extend_rev.py` both builds identical to CPython). `list[str]` receiver from `list[str]` source — **false** (#2). FLIST receiver works only when annotated; `fs = []` refused.
- "general path's `reversed(bytes)` now matches CPython" — true for `list(reversed(b))` (`p7_rev_list.py`); false for `next(reversed(b))` (`p9_nextbytes.py`: `TypeError: 'list' object is not an iterator`).
- Stepped slice / `del` / heap-subscript pre-existing: confirmed in `/tmp/base`; the new test module's assertions for them pass.
- All ten `.ail` twins generate byte-identical C (checked all 10 with `--debug-dir` vs `/tmp/base`). `lab/compare/src/berth_sim/main.py` builds `--strict` with no blocker (verified).
- Tests: `test_ail_pyreach_shapes`, `test_ail_python_syntax`, `test_ail_safetynet` — `ok`, 0 failed (293 s).

## Pre-existing

- `next(reversed(<bytes>))` differs from CPython on both base and HEAD (base: `'instance' object is not reversible`).
- Python programs on the general path (e.g. `base64_codec.py`, `binary_buffer.py`) get different C than base because the embedded prelude gained `__reversed__`; their output is unchanged.

## Unverified

- The generated-repr (`_ail_lrepr_*`) argument path for `nsmallest` (no probe reached it).
- Speed/icount: not measured; the change adds only new shapes and leaves all ten `.ail` twins' C identical.
- `nlargest` on an annotated `list[str]` (`t2_ns_str.py` refused at the `for` line before reaching it).

VERDICT: FIX
1. `heapq.nsmallest(k, xs)` where `xs` is a function parameter emits invalid C (gcc `incompatible types ... 'int64_t' ... 'ail_list'`, and `'v_top_len' undeclared` in the local-bound variant) instead of compiling or refusing by name; base refused by name. Probe `t5_param.py` / `t5c_paramlocal.py`, expected `[1, 2]` / `1` from CPython.
2. `xs.extend(reversed(src))` for list-of-str receivers/sources always refuses (`'words' is a slist; only an array, ...`); the new SLIST/SLIST branch is unreachable because `_seq` cannot walk an slist. Probe `t3c_slist_self.py`, expected `['b', 'a', 'a', 'b']`.
3. `for w in heapq.nsmallest(k, words)` on a list of str is refused with the wrong reason (`'w' is a str and is being assigned an int`). Probe `t2b_ns_for.py`, expected `b\na`.
[commandcode stop=end_turn turns=58 out_tokens=37686]

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
I have enough to judge. Writing the report now.

## Review: pyreach s2 re-run

**What the diff really does:** it only adds F5a's *tail*: `heapq.nsmallest`/`nlargest` on a list name lowered to a sorted temp truncated to `k` (wired into value/statement/for/return/generated-repr paths), `xs.extend(reversed(src))` walks, `__reversed__` for the general-path `bytes`/`bytearray` prelude, plus name-list entries (`ail_syntax`, `pyboxed2`, `shadowing`) and a test module. Stepped slices, `del` and heap-on-subscript are *not* in this diff — they are already in the base (the DEVLOG says so, and I verified base behaviour). That matches the report's description except that the task text's "2 None blockers" for berth_sim is stale: `--strict` builds berth_sim cleanly on HEAD (and on the base).

**Probes** (in `/tmp/rprobes`, each run with `cmp.sh` on HEAD and the failing ones on `/tmp/base_rev`): p1/p2/p10/p12/p13/p17/p18/p20/p21/p22 nsmallest/nlargest edges (k<0, 0, >len, ties, params, returns, for, unicode, self-assign, mutation) — all match CPython on both builds; p5 k from dict/list-item/expression — match; p28 `key=` and p31 non-name source — named refusals; p6/p19 extend(reversed) list/float/str receivers, self-extend, bytes source, multibyte, parameter receiver — match; p8 + 3 `.ail` twins (`berth_sim`, `tree_fold`, `ledger_bin`) — generated C byte-identical to base; p15 slices unchanged.

### Defects

1. **Manifest pin is stale → `par_check` cannot run.** Probe: `python3 tools/update_manifest.py --check` → `stale test_ail_pyreach_shapes.py`; `tools/par_check.py -j 2 test_ail_pyreach_shapes …` → `ValueError: hash mismatch: test_ail_pyreach_shapes.py` (base: check passes). Expected: clean check and the modules run. Actual: preflight aborts before any test. (The tests do pass when invoked directly: pyreach_shapes 14 OK, python_syntax 10 OK, safetynet 5 OK.)

2. **`heapq.nsmallest` on a list of bytes makes C that does not compile; the default build no longer falls back.** Probe p33:
   ```python
   import heapq
   def main():
       bs = [b"b", b"a"]
       top = heapq.nsmallest(1, bs)
       print(len(top))
   main()
   ```
   Expected (CPython and base): `1`. Actual HEAD: `build d failed` — `program.c: error: incompatible types when assigning to type 'ail_list' from type 'ail_blist'` (`ail_list_free(&v_top); v_top = v__t3;`). Cause: `_etypes`/`_etype` accept a BLIST source, `_sorted_into_temp` builds an `ail_blist` temp, but `_stmt_inner`'s select branch maps every kind other than LIST/FLIST/SLIST to `ail_list_free`/`ail_list`. Base built this program and matched. (Same program with the select inlined is also not refused by name.)

3. **`reversed(bytes)` on the new prelude is a list, so iterator identity is silently wrong.** Probe p7/p25: `print(reversed(b"") == reversed(b""))` → CPython `False`, HEAD (both builds) `True`; base refused with `TypeError: 'instance' object is not reversible`. Cause: `prelude_bytes.__reversed__` returns `out` (a list). `next(reversed(b))` consequently raises `'list' object is not an iterator` (both were errors on base, so that one is merely a changed message). Minor, but it is a silent CPython difference in a shape the change newly accepts.

### Claims
Verified: nsmallest/nlargest on int and str list names incl. `k<=0`, `k>len`, ties, params, returns, `for` (p1,p2,p10,p13,p17,p18,p20,p22,p27); `key=`/non-name refusal (p28,p31); `extend(reversed(...))` for LIST/FLIST/SLIST receivers and list/str/bytes sources incl. multibyte and self-extend (p6,p19); `list(reversed(b))`/`for v in reversed(b)` under `AIL_UNIFIED_FORCE=1` (p24); berth_sim `--strict` clean; `.ail` C byte-identical for 3 twins; no-feature Python program C identical.
False: "probes all match CPython on the default and unified builds" (defects 2 and 3); the task's "berth_sim → 2 None blockers" (it is 0).
Unverified: the remaining seven `.ail` twins; `codegen_diff.py --pins` does not exist in this tree (the manifest check is the only pin evidence); no icount run — the generated C is unchanged for every non-feature program, so the runtime cannot have slowed.

Pre-existing (identical on base): a decimal via `int(input())` beyond int64 raises `OverflowError` on the typed path (same for a plain `print(int(input()))` program on both trees); `next(reversed(...))` was never supported.

VERDICT: FIX
1. Run `python3 tools/update_manifest.py` and commit — `--check` now reports `stale test_ail_pyreach_shapes.py` and `par_check` preflight aborts (`hash mismatch`).
2. `heapq.nsmallest/nlargest` of a list-of-bytes local: probe `bs=[b"b",b"a"]; top=heapq.nsmallest(1,bs); print(len(top))` — expected `1` (CPython and base), actual C compile error (`ail_list` vs `ail_blist`) and no default build. Handle BLIST in `_stmt_inner`'s select branch or refuse it by name.
3. `print(reversed(b"") == reversed(b""))` — expected `False`, actual `True` (both builds) because `prelude_bytes.__reversed__` returns a list; return an iterator or refuse the shape by name.
[commandcode stop=end_turn turns=45 out_tokens=46016]

FINAL VERDICT: FIX  2026-11-06T17:06:55Z
