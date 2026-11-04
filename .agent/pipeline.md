# job job-prog17_rr1-11050046  started 2026-11-04T15:47:43Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. No earlier `job-prog17-*` branch existed, so I started from the export commit.

## Report

**Profiling (CPython 3.12, cProfile, own-function time to 80%)**

| Program | Hot functions | Before | After |
|---|---|---|---|
| g15_030 | main 52.4%, parse_dates 47.6% | typed | typed |
| t374 | main 92.9% | no | **typed** |
| g21_016 | main 76.5%, round_floats 19.3% | no | no (Any) |
| g02_016 | main 55.2%, int_to_roman 38.2% | main no | **typed** |
| g03_032 | main 34.7%, estimate 34.3%, bootstrap 31.0% | estimate/main no | no (stdev) |
| t394 | main 100% | no | no (Random class) |
| g05_010 | main 73.1%, tokenize 14.4% | typed | typed |
| t100 | main 100% | typed | typed |

Table and exact messages: `lab/progfix/prog17.md`.

**Compiler fixes** (`pyfunc.py`)
- `for c in reversed(<str>)`: walks backwards with `ail_str_prev_unit`; loop target pre-bound STR. Makes `g02_016` fully typed (3 hot functions now typed total).
- `enumerate(..., start=...)` in pair comprehensions/folds (start evaluated once, `ck_add`) and `list[tuple[..., str, ...]]` filled by a comprehension (`_listcomp_srows_into_temp`). Makes `t374` fully typed.
- Surfaced a pre-existing gcc error: `_inline_pair_fold` hardcoded `int64_t` for a str pair value; now uses the pair kinds.

**Follow-ups (left, exact messages recorded):** `g21_016` needs `Any`/`dict[str, Any]`; `g03_032` needs CPython-exact `statistics.stdev` fractions; `t394` needs the lowered `random.Random` class to take defaults/`*args` and a shared `self.mt`.

**Verification**
- `lab/compare`: generated `program.c` byte-identical to base for 10/10 tasks.
- Final commit `ffed8ea`: `test_ail_prog17`, `test_ail_prog16`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5/5 modules, 0 failed. Earlier targeted run (str/tuple/loop/strict modules) 10/11, the one failure being prog16's old "start is refused" case, updated and re-run green.
- Probes, all typed (`AIL_NO_GENERAL=1` rc 0) and matching CPython on both `cmp.sh` builds: `prog17_rev_str`, `prog17_rev_bounds`, `prog17_rev_str_mut`, `prog17_rev_str_g02`, `prog17_enum_start`, `prog17_enum_start_routes`, `prog17_srows_comp`; `prog17_srows_bad` refused by name (`requires a str in every str field`); overflow probe `prog17_enum_start_ovf` stops loudly (`OverflowError: integer overflow in +`), no wrap.

Committed as `402efba` and `ffed8ea`; not pushed.
[commandcode stop=end_turn turns=135 out_tokens=68397]

## review 0
[model commandcode/deepseek-v4.1-flash]
## Review — prog17 typed reach

**What the diff really does** (`AIL_CURRENT/python/pkg-v12/pyfunc.py`, 2 commits): adds a `for c in reversed(<str>)` branch to `_for` (captures the str once, walks with `ail_str_prev_unit`, one-code-point views) plus a `_promote_floats` pre-bind so the target is STR; teaches `_pair_plan` to evaluate `enumerate(..., start=)` once in an int temp and add it with overflow-checked `ck_add`; adds `_listcomp_srows_into_temp` for `list[tuple[..., str, ...]] = [pair-comp]`, with an early return in `_check_local_assignment`; and fixes `_inline_pair_fold` to type pair bindings by kind instead of `int64_t`. Same as the report says. No program or bench file was touched.

**Probes** (`/tmp/rprobes`, HEAD vs `/tmp/base`, all with `cmp.sh`, typed confirmed via `AIL_NO_GENERAL=1`):

| probe | result |
|---|---|
| `r1_rev` (empty/1-char/UTF-8 2–3 byte/slice/`.upper()`/`str(int)`/arg/list item/attr/dict value/`continue`/`break`/`ord`) | typed, both builds = CPython |
| `r2_alias` (rebind `words[0]`, `b.text`, `s` inside the reverse loop; forward loop too) | typed, = CPython |
| `r3_shadow`, `r3_shadow_list` (user-defined `reversed`) | typed, = CPython |
| `r4a` (start: literal/keyword/negative/dict-value/call-once, iterable-then-start order, empty, filter, 3-field float row, slice) | typed, = CPython |
| `r5c` (folds `sum`/`max`/`min`, with and without start, slice source, `sum(1 …)`) | typed, = CPython |
| `r7_srows2` (`list[tuple[str,str]]`, start from an attribute expression) | typed, = CPython |
| `g02_016`, `t374` | typed on HEAD, refused on base (`.upper() on a str is not built` / `a declared str-field records list requires matching rows`); both = CPython |
| no-feature program (`--debug-dir`) | `program.c` byte-identical to base |

**Pre-existing (identical on base, not defects):** `r6_srows_bad` (`list[tuple[int,str]] = [(w,w)…]` silently prints `[(a,'a')…]`), `r6_srows_bad3` (3-tuple into a 2-field annotation silently truncates), and the refusals `a pair target over Call` for `d.items()` folds, `sorted()` as a srows source, `enumerate(dict)`, `len(w)`.

**Claims:** reversed(str) typed ✔; enumerate-start + srows comprehension ✔; g02_016/t374 fully typed and CPython-equal ✔; probes/follow-ups plausible ✔; "`lab/compare` C byte-identical for 10/10" — unverified (their `reference.py` don't compile cleanly for me; I verified one no-feature program instead); the `_inline_pair_fold` kind fix ✔ by inspection + `r5c`.

**Tests:** `test_ail_prog17`, `test_ail_prog16`, `test_ail_safetynet` — 3 modules, 0 failed (`-j 2`).

**Speed:** no codegen change for programs not using the feature (identical `program.c`); speed win is the two programs moving to the typed path. No icount run.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=37 out_tokens=22652]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-04T17:48:25Z
