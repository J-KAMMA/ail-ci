# job job-fuzz70-10231500  started 2026-10-23T06:01:42Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `1c9b491` on `job-fuzz70-10231500`.

**Found:** first diff was `assert cond, message` with non-string messages. General path stored `str(msg)` in `e.args` (`assert False, ("a", 1)` gave `args == ("('a', 1)",)` instead of `(('a', 1),)`). Default build also failed earlier asserts because a mixed-mode typed clone of an asserting helper raised where the boxed `try` could not catch it.

**Fix:** general path now raises with `ail2x_raise_builtin`, keeping the original message object in `args`; functions containing `assert` are kept out of mixed-mode typed clones. Typed-only builds still refuse tuple messages by name.

**Probes:** 27 programs in `/tmp/probes` (nested returns, `while True`/break, sys.exit 0/3/7/4, try/finally, assert scalars/tuples/lists/dicts/sets/None/custom objects, values via arguments/list items/attributes/dict values). All 27 match CPython on both builds, including the previously failing `p06`, `p15`, `p17`, `p19`–`p23`. No remaining differences observed.

**Tests:** `test_ail_fuzz70`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed (212s), run on final commit. Manifest and CI shard checks pass. DEVLOG and DIFFERENCES records added.
[cost $0.0000, opencode tokens {"total": 7596350, "input": 290940, "output": 14487, "reasoning": 17835, "cache.write": 0, "cache.read": 7273088}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
Reviewed `1c9b491` (general-path `AssertionError.args`, bounding asserting helpers out of mixed-mode clones, typed tuple refusal).

**Probes** (all via `bash ~/tools/cmp.sh … <wt>`, general `g` + default `d`):
- New probes `r01`–`r23`: messages via argument/list item/attribute/dict value/default/closure; tuple/list/dict/set/None/bool/int/float/str/custom `__str__`/`__repr__`; top-level and nested asserts; try/finally; mixed helper; exits `0`, `-1`(255), `3`, `4`, `7`, `10**9`, `None`, `"bye"`. All match CPython on both builds, apart from the pre-existing rows below.
- Re-ran all 27 `/tmp/probes`: 27/27 match, including the formerly failing `p06`, `p15`, `p17`, `p19`–`p23`. Base `p17`/`p06` default builds do crash/misattribute args; HEAD matches.
- No-feature `r08`: generated `program.c` byte-identical to `/tmp/base` in both builds.
- Mixed clone: base `p17` produced a 176 KB `program_mix0.c`; HEAD produces none and catches the helper’s assert correctly.
- Tests: `test_ail_fuzz70`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass (`-j 2`, 212 s). Manifest and `ci_shards.py --check` pass.

**Claims:** commit/branch verified; general-path object-in-`args` fix verified; mixed-clone avoidance verified; typed tuple refusal verified (but the new `ast.Tuple` branch is shadowed by an earlier lowering; it is effectively dead, though the outcome is still a named refusal); 27-probe claim verified; 4-module test claim verified.

**Pre-existing (identical on `/tmp/base`, not blocking):**
- `--strict`: `assert False, 42` gives `e.args == ('42',)` instead of `(42,)`.
- Assert message text is computed eagerly, so mutating a list/dict message after the assert leaves `str(e)` stale.
- Int messages outside int64 range (e.g. `10**30`) abort with `integer overflow`; internal `KeyError` still shows `("'b'",)`.

**Speed:** `tools/icount.c` cannot run here (`perf_event_open: Permission denied`). The gdev programs with asserts (`g08`, `g09`, `g10`, `g07`, `g21`) have no mixed typed units on either side; generated C is identical (`g08`, `g10`) or only gains the ~5 KB exception runtime (`g07`, `g09`). No measured regression.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 3457021, "input": 257931, "output": 13996, "reasoning": 27334, "cache.write": 0, "cache.read": 3157760}]

FINAL VERDICT: ACCEPT  2026-10-23T06:41:28Z
