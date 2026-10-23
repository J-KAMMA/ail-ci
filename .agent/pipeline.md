# job job-fuzz42-10231159  started 2026-10-23T03:00:08Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `d20202c` on `job-fuzz42-10231159`.

**Bug fixed:** general-path `abs(bool)` kept the BOOL tag, so `abs(False)`/`abs(True)` printed `False`/`True` instead of CPython’s `0`/`1`. Routing the plain call and the builtin-as-`map`/`key=` wrapper through `ail_bi_abs` fixes it.

**Probes** (`bash ~/tools/cmp.sh <probe> $PWD`):
- `b01_arith.py`: before, line 6 differed (`-1 0 False True` vs `-1 0 0 1`); after, both builds same.
- `abs_bool.py`: literal, variable, negative, float/int, list item, dict value, argument, comparison/not/bool/all/any, `map(abs, ...)`, `sum(bool, start)` — both builds same.
- `abs_bool_attr.py`: attribute and dict-of-object value paths — both builds same.
- `b02`–`b07`: all same on both builds.
- Other differences seen, not silent: `b08`/`b09` hit AIL’s declared 64-bit `integer overflow` on `1 << 100` / `10 ** 100`; `b10` was refused at build for `memoryview`/handle-list support.

**Tests on final commit:** `test_ail_fuzz42`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. `tools/update_manifest.py --check` exits 0.
[cost $0.0000, opencode tokens {"total": 4771920, "input": 142174, "output": 14335, "reasoning": 14067, "cache.write": 0, "cache.read": 4601344}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review

**Diff** (`d20202c`): general-path `abs()` (plain call + builtin-as-`key=`/`map` wrapper) now calls `ail_bi_abs` instead of an inline lowering that returned non-negative values unchanged. Test `test_ail_fuzz42.py` added and pinned; docs/manifest updated.

**Probes** (`/tmp/rprobes`, HEAD vs `/tmp/base`):

- `p1b_abs_bool_noclass.py`: base forced-general printed `False True` / `True False`; HEAD both builds match CPython (`0 1` / `1 0`). **Fix reproduced and verified.**
- `p2_abs_containers.py`, `p5_abs_wrappers.py`, `p9_abs_aliasing.py`: bools through list item, dict value, argument, attribute, alias, `map`/`sorted(key=abs)`, and `__abs__` instance all match HEAD/base.
- `p3_abs_wrongtypes.py`, `p3b_abs_none.py`, `p3c_abs_list.py`: base printed `x`/`None`/`[]` and exited 0; HEAD raises the CPython `TypeError` and exits 1. An improvement, not a regression.
- `p6_bool_area.py`: `True+True`, bool sums, `bool(0.0)`/`-0.0`/empty containers/`None`, `int(True)`, chained comparisons, bool indexing, bit ops all match CPython on both builds.
- `p7_no_abs.py`: `--debug-dir` `program.c` byte-identical HEAD vs base (507,796 bytes); `native_report.json` differs only in temp paths.
- `p10_fraction_abs.py` (Fraction `__abs__`) matches both; `p11`/`p12` refusals identical to base.

**Tests**: `test_ail_fuzz42`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4/4 pass, 249s. `update_manifest.py --check` exits 0.

**Claims**: all verified except `b02`–`b07` individually (not run; `p6` covers the same constructs) and `b10` (I saw equivalent refusals in `p11`/`p12`). The “float/int both builds same” claim holds for the shipped probe; it does not cover the pre-existing typed-path `abs(-0.0)` case below.

**Speed**: `tools/icount.c` cannot run here (`perf_event_open: Permission denied`, paranoid=4). Forced-general gdev `g02_004`, `g22_022`, `g03_036` build and produce identical output before/after; the change only replaces an inline sequence with a call to a `static inline` helper on `abs`.

**Pre-existing** (identical on base, not blocking):
- Default/typed path `abs(-0.0)` prints `-0.0` vs CPython `0.0` (`p4`).
- `abs(-2**63)` hits the declared 64-bit integer overflow on both builds (`p8`).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1781949, "input": 60237, "output": 8876, "reasoning": 17732, "cache.write": 0, "cache.read": 1695104}]

FINAL VERDICT: ACCEPT  2026-10-23T03:31:33Z
