# job job-fz237-11070601  started 2026-11-06T21:01:47Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
## Report

**Finding did not reproduce on this tree — no changes made.**

**1. Reproducer (`/tmp/probes/fz237.py`, regenerated identically from seed 2076319083 via `lab/fuzz/gen.py`)**

`bash ~/tools/cmp.sh /tmp/probes/fz237.py $PWD`, both builds:

| build | exit | stdout |
|---|---|---|
| CPython 3.12.3 | 1 | `-0001 False / 105 / 179 / 286` |
| default (`d`) | 1 | same |
| general/unified (`g`) | 1 | same |
| `AIL_IR=1` (manual build) | 1 | same |

Diff empty for both; stderr both end in `ValueError: invalid literal for int() with base 10: 'café'`.
The repo's own runner agrees: `lab/fuzz/run.py --start 2076319083 --count 1` → default `same`, ir `same` (4 s).

**2. Cause is already fixed in this tree.** The reported signature (`ail='0.0'` = the `except ValueError` body running, then exit 0) is the try/`else` routing bug fixed by **job-fz1** (DEVLOG 2026-10-28: "an exception in a try/else clause reaches an outer handler", seed 2075200054). The fix is present in `AIL_CURRENT/python/pkg-v12/pyboxed2.py::stmt_Try` — the `else` body jumps over the handler dispatch to `tryelse`, and `test_ail_fz1.py` covers it.

**3. Probes (all match CPython on both builds)**
- `p1` — `int('café')` in `else`, bare handler
- `p2` — nested `try/finally` in `else` before the raise
- `p3` — nested `try/except/finally` in `else`, raise in `if` test
- `q1` — explicit `raise ValueError` in `else`
- `q2` — the fuzzer's exact `else` shape (`finally: print(179)` + `int('café')` comparison)
- `q3` — `KeyError` in `else` inside a function
- `fz237` — full reproducer

`test_ail_fz1`: 1 test OK (17.9 s). `test_ail_safetynet`: 5 tests OK (195.8 s).

**4. Other differences seen:** none — the full program's stdout and exit code are identical on both builds.

No files changed, nothing committed (per the "if it does not reproduce, change nothing" instruction). Pre-existing untracked `.agent/pipeline.md` left alone.
[commandcode stop=end_turn turns=30 out_tokens=17138]

FINAL VERDICT: NOCHANGE  2026-11-06T21:10:54Z  (the worker changed nothing; no review was run)
