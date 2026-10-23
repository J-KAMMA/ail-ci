# job job-fuzz81-10231552  started 2026-10-23T06:53:17Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
**Done** — commit `95ad742` on `job-fuzz81-10231552`.

- Fixed runtime `KeyError` to store the raw key in `args` via new `ail_raise_key`; applied to dict get/pop/del, `popitem`, `set.remove`, `set.pop`, and the general-path augmented lookup.
- Added `AIL_CURRENT/test_ail_fuzz81.py` with 2 tests covering key types/sources and exception hierarchy.
- First diff: `h5.py` (`e.args` was `("'x'",)` instead of `('x',)`); `h7.py` showed the same root cause for repr/int keys.
- 15 probes run on final tree: `h4`, `h5`, `h5a`, `h5b`, `h6`, `h7`, `h8`, `h9b`, `h10`, `h11`, `h12` match CPython on both builds; `h1`, `h2`, `h3`, `h9` refused by name (`LookupError`, `ArithmeticError`, `BaseException`). No remaining diffs seen.
- Final-commit tests: `test_ail_fuzz81`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed, 148s. Manifest check clean.

No `DEVLOG`/`DIFFERENCES` files exist in this CI mirror, so none were added.
[cost $0.0000, opencode tokens {"total": 6583756, "input": 825215, "output": 20501, "reasoning": 18872, "cache.write": 0, "cache.read": 5719168}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review job-fuzz81-10231552 (`95ad742`)

**Change.** New `ail_raise_key` stores the raw key as `KeyError.args[0]` (message remains `repr(key)`) for dict get/pop/del, general-path augmented get, `popitem`, `set.remove`, `set.pop`; new `test_ail_fuzz81.py`; manifest updated.

**Probes** (HEAD, general + default builds; all match CPython unless noted):
- r1 key types str/int/float/bool/None/tuple/empty/newline; r13 tabs/quotes/unicode/-0.0/1e300 plus `args[0] is k`; r16 nan/inf/2**62+1 — match.
- r2 key via argument/list item/attribute/dict value; r9 mutation during iteration; r11 `d[k] += 1`; r12 non-raising get/pop/setdefault/discard — match.
- r3 empty `popitem()`/`set.pop()` — match (base differs).
- r4 hierarchy/tuple catches; r22 bare and `raise e` re-raise — match.
- r5 `except LookupError`, r6 `except ArithmeticError` — refused by name (acceptable).
- r7 IndexError; r8 explicit `raise KeyError(...)` — match.
- r10 plain program: `--debug-dir` `program.c` byte-identical to base.
- Worker probes h1–h12 rerun: h4/h5/h5a/h5b/h6/h7/h8/h9b/h10/h11/h12 match; h1/h2/h3/h9 refused by name. Base h5 shows exactly `("'x'",)` vs `('x',)`.

**Pre-existing (identical on `/tmp/base`).** Typed tuple-keyed containers lowered via `tuplegen.Table` still raise `KeyError(repr-string)`: r19/r20 (`dict[tuple[int,int],int]` get; `set[tuple[int,int]].remove`) print `('(1, 2)',)` vs CPython `((1, 2),)`. Not caused by this change; untyped tuple keys (r17/r18) are fixed.

**Tests.** On HEAD: `test_ail_fuzz81`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_exc_str` — 0 failed. `update_manifest.py --check` rc 0.

**Report claims.** All verified (fix scope, base diffs, 15 probes, tests, manifest, no DEVLOG/DIFFERENCES files) except “No remaining diffs seen”, false only for the pre-existing tuple-table case above.

**Speed.** `icount` unavailable here (`perf_event_open: Permission denied`). Generated-C diff for a dict program is limited to the error branches/helper; hot lookup path unchanged. Nit: stale comment at `cruntime.py:16649` still says structured `.args` is out of scope.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 4964184, "input": 197512, "output": 16709, "reasoning": 35851, "cache.write": 0, "cache.read": 4714112}]

FINAL VERDICT: ACCEPT  2026-10-23T07:37:32Z
