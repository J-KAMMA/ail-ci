# job job-fuzz36-10230817  started 2026-10-22T23:18:30Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the general-path `KeyError` argument handling: dict/set misses stored `repr(key)` as the sole argument, so `e.args` was `("'k'",)` and `repr(e)` was `KeyError("'k'")`. The runtime now keeps the raw argument and uses `repr(key)` only as the message. Commit: `78c1358`.

Probes (all match CPython on both builds unless noted):
- `/tmp/probes/p01_key_str.py`, `p02_key_num.py` — originally differed on g, now match.
- `p06_dict_methods.py`, `p07_empty.py`, `p08_sources.py`, `p09_nested.py`, `p10_bool_none.py` — match.
- `p03_index_list.py`, `p05_int_value.py` — match, unchanged.
- `/tmp/probes-other-p04_zero.py` — still differs: g `% 0` text and float `/ 0.0`; d int `/ 0` text.

Tests on final commit: `test_ail_fuzz36` 4, `test_ail_safetynet` 5, `test_ail_files` 18 (1 skipped), `test_ail_corpus_findings3` 2 — all pass. Manifest `--check` passes. No `DIFFERENCES`/`DEVLOG` files exist in this export, so no record rows were added.
[cost $0.0000, opencode tokens {"total": 4841698, "input": 127217, "output": 13808, "reasoning": 13441, "cache.write": 0, "cache.read": 4687232}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review

**Change**: general-path `KeyError` now keeps the raw key as `args` and uses `repr(key)` only as the message, so `e.args`/`repr(e)` match CPython for dict get/pop/del, `popitem`, `set.remove`, `set.pop`, and augmented assignment (`pyboxed2.ail2_aug_probe`). No compiler semantics changed; new `test_ail_fuzz36` registered in `MODULES`, manifest updated.

**Probes** (all run with `cmp.sh` on HEAD and `/tmp/base`):
- `r01_repr`, `r02_quotes`, `r03_types`, `r04_methods`, `r05_other`, `r07_aug`, `r08_zero`, `r08b_zero`, `r09_nofeature`, `r10_alias`: match CPython on both builds on HEAD. The same probes show the old quoted-`args` bug on base (r01–r05, r07, r10).
- Worker probes `p01`–`p10` all match on HEAD; `p04_zero` still differs, identically on base.
- Non-feature program (`r09_nofeature`) behaves identically to base.

**Pre-existing (not caused by change)**:
- `p04_zero`: general path says `integer division or modulo by zero` for `% 0` and `division by zero` for float `/`; default says `float division by zero` for int `/`. Identical on base.
- Uncaught KeyError on default build prints `key error` to stderr instead of `KeyError: <repr>` (`r06_uncaught`). Identical on base.

**Tests**: `test_ail_fuzz36`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, plus `test_ail_exc_str` and `test_ail_builtin_maps` all pass on HEAD. `tools/update_manifest.py --check` passes.

**Report claims**: all verified (fix, base failure, remaining p04 difference, test passes, manifest, no DIFFERENCES/DEVLOG files). Speed: change is on the exception-raise path only; `perf_event_open` is denied in this runner, but no hot path was altered.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 4023223, "input": 97194, "output": 9200, "reasoning": 21789, "cache.write": 0, "cache.read": 3895040}]

FINAL VERDICT: ACCEPT  2026-10-22T23:46:56Z
