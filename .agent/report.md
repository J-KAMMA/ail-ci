# job job-pre19-10240254  started 2026-10-23T17:55:17Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the first still-differing case, `maxi`: `del a[2**63 - 1]`. It fits after subtracting, but both builds evaluated `2**63` first and trapped `integer overflow`. The same cause affected `negmin`, `powhuge` and constant slice bounds (`slicebig`). `pyfront.refuse_unrepresentable_delete_bounds` now evaluates constant index/slice bounds exactly, including intermediates, and refuses the `del` by name on both paths.

Commit: `204dfe3`.

Probes (both builds):
- Refused by name: `maxi`, `maxi_bool`, `negmin`, `powhuge`, `q14`, `cancel`, `slicebig`, `stepbig`, `nested`, `attr`, `dictval`, `alias`, `strtype`, `bytearray_type`, `emptylist` — 15/15.
- Match CPython: `inrange`, `dyn_inrange` (argument/list-item/attribute/dict value), `belowmax`, `maxi_literal` — 4/4.

Tests on final commit: `test_ail_pre19`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed (210s). `update_manifest.py --check` rc 0. `ci_shards.py --check` still rc 1 for pre-existing unassigned `test_ail_fuzz20`/`test_ail_fuzz22` (same before this change).

`q26`, `q39`, `argbig`, and the bool/list-item default-build segfaults remain pre-existing and untouched.
[cost $0.0000, opencode tokens {"total": 4630333, "input": 239270, "output": 17843, "reasoning": 16868, "cache.write": 0, "cache.read": 4356352}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review of `204dfe3` (pre19)

**Change:** `pyfront.refuse_unrepresentable_delete_bounds` evaluates constant delete bounds exactly and refuses overflow at compile time; wired into both the typed (`pyfunc`) and general (`pyboxed2`) paths, plus new `test_ail_pre19`, manifest/shard/DEVLOG updates.

**Probes (both builds, `cmp.sh`):**
- `maxi` (`del a[2**63-1]`): HEAD refuses by name on both paths; base trapped `integer overflow` → target case fixed.
- `cancel` (`2**63-2**63`), huge slice step, `2**63//4`, `(2**63)>>1`: HEAD refuses by name; base trapped. Over-refusal of representable *final* bounds, but a named refusal is acceptable.
- `unreachable` (`del` after `return`): base matched CPython, HEAD refuses by name. Allowed, though it refuses dead code.
- In-range index/slice, plain `del`, no-`del` program, and values via argument/list-item/attribute/dict value: match CPython, both builds.
- `del a[2**63-1][0]` (overflow in target value) and bound via a variable: same difference on base and HEAD → pre-existing.
- bool index, float index, `2**-1`: default-build segfault, identical on base → pre-existing.

**C unchanged:** `--debug-dir` `program.c` byte-identical base vs HEAD for `g00_000` and a plain-`del` probe, both paths (only path/cwd metadata differs). No runtime/hot-code impact.

**Tests:** `test_ail_pre19` + `test_ail_safetynet` = 2 modules, 0 failed (87s). `update_manifest.py --check` rc 0; `ci_shards.py --check` rc 1 for the same pre-existing `test_ail_fuzz20`/`test_ail_fuzz22` on base.

**Claims:** commit, cause, both-path named refusal, slice-bound cases, and in-range/dynamic matches verified. `test_ail_files`/`test_ail_corpus_findings3`, `q26`/`q39`/`argbig`, and `n01`–`n03` not re-run → unverified.

**Pre-existing:** dynamic-bound case, reverse-nested delete, and the default-build bool/float/negative-pow segfaults are unchanged from base.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 489701, "input": 35032, "output": 3878, "reasoning": 19687, "cache.write": 0, "cache.read": 431104}]

FINAL VERDICT: ACCEPT  2026-10-23T18:15:30Z
