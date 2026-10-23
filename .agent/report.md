# job job-fuzz82-10231553  started 2026-10-23T06:54:22Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `32636ce`.

**Cause/fix:** `del xs[i]` in a function naming a module-level numeric list reached `ail_list_pop` on the const table from `_emit_module_consts`. Deleting the last item was silently dropped (stale list, exit 0); deleting an earlier item memmoved over const data and crashed. `AIL_CURRENT/python/pkg-v12/pyfunc.py` now refuses this by name on the typed path; the default build falls back to the general path and matches CPython. Added `AIL_CURRENT/test_ail_fuzz82.py` (2 tests).

**Probes** (`bash ~/tools/cmp.sh`, both builds):
- p01–p05, p07, p09–p17, p19–p20, p23, p25–p32: same stdout before/after.
- p24, p33, p36 (fix target): before — p24 default segfault (exit 139), p33 printed `[10, 20, 30]` vs `[10, 20]`, p36 printed `1 [7]` vs `0 []`; after — all same stdout, exit 0. Typed-only now refuses: `'xs' is a module-level constant; deleting from it would mutate it`.
- p34 float list, p35 str list: same; typed-only refused by name.
- p37 indexes via parameter/list item/attribute/dict value: same.
- p38 empty module list: same; typed-only refuses (`read before it is assigned`).
- p39 alias then delete: same; typed-only refuses del by name.
- p40 huge ±index: same (IndexError caught).
- p18 nested class, p21/p22 functions defined in top-level loops: refused by name (not silent).

**Other differences seen, not fixed:** p06 huge int is the documented 64-bit overflow behavior; p08 `global` in a nested def prints CPython `2` but AIL exits 1 with `UnboundLocalError` (loud); delete out-of-range error text differs (`list index out of range` vs CPython `list assignment index out of range`).

**Tests on HEAD:** `test_ail_fuzz82`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed (334s). Also `test_ail_modconst`, `test_ail_quirks` — 0 failed (292s). `update_manifest.py --check` passes.

**Records:** `docs/spec/DIFFERENCES.md` and `DEVLOG.md` did not exist in this export; created them with row `C?-job-fuzz82-10231553-1` and a dated entry.
[cost $0.0000, opencode tokens {"total": 8119860, "input": 687334, "output": 15402, "reasoning": 15268, "cache.write": 0, "cache.read": 7401856}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: fuzz82 module-list `del`

**Change:** typed path (`python/pkg-v12/pyfunc.py`) refuses `del <module-const>[i]`; default build falls back to the general path. Adds `test_ail_fuzz82.py`, MANIFEST pin, DEVLOG, DIFFERENCES.

**Probes** (`bash ~/tools/cmp.sh`, both builds; base = `/tmp/base`):

| Probe | HEAD | Base |
|---|---|---|
| `p01` `del a[-1]` | both match CPython | typed silently `[1,2,3]` vs `[1,2]` |
| `p02` `del a[1]` | both match | typed silently unchanged |
| `p10` index via parameter | both match | default exit 139 |
| `p13` top-level `del a[0]` | both match | default exit 139 |
| `p14` `del xs[len(xs)-1]` | both match | typed silently unchanged |
| `q11-q13` annotated `a: list[int] = [...]` | both match | default silently unchanged |
| `q27-q28` `global a; del a[i]` | typed refuses, default matches | typed compiled and silently printed unchanged |

Also covered with both builds matching CPython or a named refusal: float/str/bool lists, tuple constants, negative/out-of-range/float/str/bool/huge indexes, slices, multi-target deletes, aliases, nested defs, class methods, 1000-element lists, loop deletes, `try/finally`, index side effects.

**Pre-existing (base == HEAD, non-blocking):**
- `q14` `del a[2**63]`: both default builds trap `integer overflow`, exit 1.
- `q26` delete from empty list: stdout matches, but stderr says `list index out of range` vs CPython `list assignment index out of range`.
- `q39` `global` in nested def: CPython prints `2`; AIL exits 1 with `UnboundLocalError` (loud, as reported).

**C unchanged / speed:** `program.c` hashes identical base vs HEAD for `n01`–`n03` and gdev `g07_024`, `g08_028` (the only gdev `del`s are on locals); no hot-code change.

**Tests:** `test_ail_fuzz82`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed (258s). `test_ail_modconst` — 0 failed (173s). `update_manifest.py --check` rc 0.

**Report claims:** commit, cause, typed refusal message, fallback, tests, manifest — **verified**. “Before crashed” — **partially verified**: last/middle deletes were silent, crashes reproduced for index 0 and top-level. Exact p-number probe claims — **unverified** (their files not available), independent probes agree. Nested-global difference — **verified**.

Minor housekeeping: `python3 tools/ci_shards.py --check` reports `test_ail_fuzz82` unassigned (rc 1), but CI spreads unassigned modules and the test runs in exactly one shard; the task’s record rules did not require updating `ci_shards.json`.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 3666503, "input": 208556, "output": 14315, "reasoning": 29488, "cache.write": 0, "cache.read": 3414144}]

FINAL VERDICT: ACCEPT  2026-10-23T07:54:11Z
