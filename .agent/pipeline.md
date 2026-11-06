# job job-rbpyreachs2_rr1-11070610  started 2026-11-06T21:10:59Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. The review's single remaining defect is fixed.

**Defect checked:** only #1 (select passed straight as a call argument) remained — the two `_is_heapq_select` branches in `_call_user_func` still pushed raw `ctx.pre;` statements into `staged`. The dict-store and `reversed(bytearray)` fixes were already in the tree (review marked them verified, so I didn't redo them).

**Fix:** both branches now emit `({ ... (void)0; })` (same wrapper as the listcomp branch at `pyfunc.py:17291`). Added `test_nsmallest_passed_directly_as_a_call_argument` to `test_ail_pyreach_shapes`.

**Probes** (`bash ~/tools/cmp.sh`, both `g` and `d` builds, all CPython-identical):
- `p_u1` `list[int]` arg → `7`; `p_y1` method arg → `13`; `p_u2` `list[str]` arg (`nsmallest`+`nlargest`) → `apple`/`kiwi`
- `p_u3` two selects in one call, `k` = 0 / −3 / 9 → `0 0 15 208 20`
- `p_u4` `print(select)` int + str, dict value → `[2, 5]`, `['apple', 'fig']`
- `p_u5` method with `list[str]` param; `p_u6` callee appends to its parameter (source list untouched, len 3)
- `p_u7` select through `sum`/`len`/`[0]`/`sorted`/`min`
- `p_arg` the new test source, both builds → `7 0 15 208 apple 13`

**Tests on the final commit** (`c85ca09`): pyreach_shapes 18 OK, python_syntax 10 OK, safetynet 5 OK, files 18 OK (1 skipped), corpus_findings3 2 OK, bytearray_loops 1 OK, bytearray_refs 3 OK. `update_manifest.py --check` clean; 5 files committed, nothing else changed.

**Not verified:** performance (`perf_event_open` denied here), same as before.
[commandcode stop=end_turn turns=33 out_tokens=12193]

## review 0
[model commandcode/deepseek-v4.1-flash]
## Review report

**What the change really does:** wraps the two `_is_heapq_select` branches of `_call_user_func` (`pyfunc.py:17216`, `17424`) so the select's moved `ctx.pre` statements are emitted as `({ ... (void)0; })` instead of bare `x = 1;` inside the `staged` comma expression — exactly the wrapper the listcomp branch at `17291` already uses. Plus a regression test (`NSMALLEST_ARGUMENT`) and manifest/DEVLOG updates. That matches the report.

**Probes** (`bash ~/tools/cmp.sh <p> $PWD`, `g` and `d` builds, all CPython-identical):
- `p_a1` `list[int]` arg, k = 2 / −1 / 0 / 99, source list unchanged → OK (base: `build d failed`, `expected ')' before ';'` — defect confirmed and fixed).
- `p_a2` `list[str]` arg, k = 2, 0, len → OK.
- `p_a3` method arg, method with two list args, two selects in one call, one-element source → OK.
- `p_a4` callee mutates its parameter (append, `xs[0]=-1`) — source list untouched, length 3 → OK (no aliasing leak from the temp).
- `p_a6` select inside `+ 1`, `if` condition, ternary, `while` condition, product of two selects → OK.
- `p_k1` k through a dict value and `len(ys)-3`, empty source → OK.
- `p_a5` non-feature program (heapq ops, `bytes`/`bytearray`): `--debug-dir` `program.c` byte-identical to base (`diff -r` clean).

**Tests** on HEAD (`-j 2`): `test_ail_pyreach_shapes`, `test_ail_python_syntax`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_bytearray_loops`, `test_ail_bytearray_refs` — 7/7 ok. `update_manifest.py --check` clean.

**Claim check**
- Both branches wrapped with `({ ... (void)0; })`, same as `17291` — verified (diff, grep).
- Prior fixes still present (dict-of-int refusal at `25719`, live `__reversed__` in `prelude_bytes.py:558`) — verified.
- Regression test added; `7/0/15/208/apple/13` expected — verified (test passes).
- Probe list in report — verified (files exist; my equivalents agree).
- 7 test modules pass — verified.
- "5 files committed, nothing else changed" — verified (`git status` clean apart from pre-existing untracked `.agent/pipeline.md`).
- Performance unaffected — partially verified: generated `program.c` for `g00_000`/`g00_010` identical to base; `perf_event_open` denied, so no icount.

**Pre-existing:** nothing new. Base's failure on `p_a1` is the defect this commit fixes; base also lacks the `reversed(bytearray)` support (earlier commit in the tree).

**Unverified:** instruction counts (perf denied); compiler-only change with identical emitted C for non-feature programs, so no runtime effect expected.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=21 out_tokens=9902]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-06T22:54:44Z
