# job job-fuzz24-10230422  started 2026-10-22T19:23:42Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `8a04298` on `job-fuzz24-10230422`.

**Fixed:** `math.fsum` on the Python syntax ignored CPython’s non-finite bookkeeping: `fsum([inf,-inf])` returned `nan` instead of raising `ValueError`, and finite intermediate overflow returned `nan` instead of `OverflowError`. It now carries `special_sum`/`inf_sum` and raises CPython’s messages. Added `AIL_CURRENT/test_ail_fuzz24.py`.

**Verification:**
- Required tests: `test_ail_fuzz24`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed, 242s.
- Probes p01/p02 (special values, overflow, arguments/lists/dicts/attributes/alias/nesting): same stdout on both builds, matching CPython.
- Manifest `--check`: clean.

**Other differences observed** (all reproduced on base `de1397d`, so pre-existing, not fixed):
- p03: `math.fsum([1,2,3])` prints `6`/`3` instead of `6.0`/`3.0`.
- p04: huge `floor`/`ceil`/`trunc` (±1e19, ±1e300, `ceil(-2**63)`) abort or overflow instead of returning big ints.
- p05: `int()` of huge floats aborts on `g`, or raises `OverflowError` on `d`, instead of returning big ints.
- p09: float `%` signed zero differs on `g` only (`0.0 % -1.0` gives `0.0`, CPython `-0.0`).
- p10: `math.fsum` wrong-type messages differ (`must be real number` vs operand/`<` errors).
- p06/p07/p08 (`isclose`, inf/nan comparisons, `copysign`): same on both builds.

`DEVLOG`/`DIFFERENCES` are absent from both this checkout and the remote HEAD, so no record entry was added.
[cost $0.0000, opencode tokens {"total": 6225306, "input": 133032, "output": 15734, "reasoning": 21244, "cache.write": 0, "cache.read": 6055296}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review — fsum non-finite/overflow fix (`8a04298`)**

Diff inspected: only `ail_syntax.py`'s `_MATH_HELPERS['fsum']`, its manifest hashes, and the new `test_ail_fuzz24.py`/`ail_check` entry. Nothing else changed.

Probes (both `g` and `d` builds, base `/tmp/base@de1397d`):
- `p01`, `p02`, `p03`, `p04`, `p05`, `p11`, `p12`: HEAD matches CPython (incl. `fsum([inf,-inf])` → ValueError, `[1e308,1e308]` → OverflowError, empty/±0.0, argument/list/dict/attribute/alias/nesting, int/float mixes). Base differs on the special-value and overflow cases exactly as reported.
- `p06`: `fsum([1,2,3])` → `6` not `6.0`; huge-int input overflows. Identical on base → Pre-existing.
- `p07`: tuple works; iterator/set fail in helper (`len`). Identical on base → Pre-existing.
- `p09`: huge `floor`/`ceil`/`trunc`/`int` raise `integer overflow` instead of big ints; `0.0 % -1.0` signed zero. Identical on base → Pre-existing.
- `p10`: wrong-type `fsum` message differs. Base and HEAD both differ from CPython, but the text changed (base `unsupported operand type(s) for +`, HEAD `'<' not supported ...`); same stdout/exit, so still a pre-existing error-message difference, not a new silent wrong answer.
- `p08`: nan/inf `isclose` refused by name on both builds → Pre-existing.

Other checks: non-fsum program's `--debug-dir/program.c` is byte-identical to base. `update_manifest.py --check` clean. No DEVLOG/DIFFERENCES exist in HEAD or any local ref (claim verified). Tests: `test_ail_fuzz24`+`test_ail_safetynet` 0 failed (95s); `test_ail_files`+`test_ail_corpus_findings3` 0 failed (150s), consistent with the reported 242s. Speed: `perf_event_open` denied; wall time for g20_026 ×100 was 76–80ms on both builds (no regression).

Report claims: fix verified; new test verified; required tests verified; manifest clean verified; pre-existing items p03/p04/p05/p06/p07/p08/p09 verified, p10's "pre-existing" wording is slightly inaccurate (message text changed, but both builds already errored differently from CPython).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1009883, "input": 38856, "output": 8566, "reasoning": 14749, "cache.write": 0, "cache.read": 947712}]

FINAL VERDICT: ACCEPT  2026-10-22T19:45:09Z
