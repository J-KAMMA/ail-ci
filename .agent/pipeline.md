# job job-fz239-11080433  started 2026-11-07T19:39:55Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
## Report (job-fz239-11080433)

**The reported DIFF does not reproduce on this tree — no compiler change was needed.**

- Seed `2076418519` generator output is byte-identical to the reported program (`diff` rc 0).
- `bash ~/tools/cmp.sh /tmp/probes/fz239.py $PWD`: both builds fail at **compile time with a named refusal**, `p.ail:71:13: not in the subset: a constant integer expression overflows int64 ...`.
- `lab/fuzz/run.py --start 2076418519 --count 1 --modes default,ir`: both modes class **`refused`**, not `DIFF`.
- With that line removed, the rest of the seed matches CPython on both cmp builds (`g same stdout`, `d same stdout`).

**Minimized cause:** `print(str((-9223372036854775807 << 4)))` — a constant integer shift whose exact value (`-147573952589676412912`) is outside int64. It is refused by name (`int64 constant expression out of range`, or `... overflows int64` when the expression sits inside a function). This is the same situation already recorded for `fz226` (constant subtraction beyond int64).

**Change (commit `9698d35`, 6 files, +218):** test/docs only — `AIL_CURRENT/test_ail_fz239.py` (+`tests.d` entry), a `DIFFERENCES.md` row `C?-job-fz239-11080433-1`, a `DEVLOG.md` entry, regenerated `manifest.d` (`--check` clean). No compiler or runtime file touched.

**Probes** (`bash ~/tools/cmp.sh`, both builds; test covers default + `AIL_IR=1` + `--exact-int`):

| probe | result |
|---|---|
| `fz239`, `min1`, `p1`, `p7`, `p8`, `p10`, `w1`, `w2`, `w3`, `w4`, `w5`, `p2`, `p9` (constant shift/mul/pow, module const, try/finally, function) | refused by name, both builds |
| `i1_inrange` (shift 0, `>>1`, `1<<62`, `(-2)**62`, `-2**62<<1` = INT64_MIN, `2**63-1`) | matches CPython |
| `p3`/`p4`/`p5`/`p6`, `q1`/`q2` (via argument, list item, attribute, dict value, with `finally`) | loud `OverflowError: integer overflow in <<`, exit 1, stdout a **prefix** of CPython's (declared int64 overflow, lab class `overflow`); `--exact-int` matches CPython |

**Tests on the final commit:** `test_ail_fz239`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4/4 pass in 215s (`-j 2`).

**Other differences seen:** none beyond the declared int64 overflow; the routed (non-constant) values are a loud trap with prefix stdout, so the fuzz lab classes them `overflow`, not `DIFF`.

Not verified: the full suite (deliberately not run; the integration gate does).
[commandcode stop=end_turn turns=37 out_tokens=42045]

## review 0
[model commandcode/deepseek-v4.1-flash]
## Review: job-fz239-11080433 (`9698d35`)

**What the change really does:** test/docs only. It adds `test_ail_fz239.py` (+`tests.d` entry) pinning the *pre-existing* named compile-time refusal for a constant int64 overflow, plus a `DIFFERENCES.md` row and DEVLOG entry. No compiler/runtime file is touched (diff: 6 files, +218, all test/docs/manifest). This matches the report.

**Probes** (`bash ~/tools/cmp.sh ... $PWD`, g=general, d=default):

| probe | HEAD | base (`/tmp/base`) |
|---|---|---|
| `fz239` (full seed) | both builds: named refusal `constant integer expression overflows int64` (line 71) | – |
| `min1` (`print(str((-9223372036854775807 << 4)))`) | both: `int64 constant expression out of range: -147573952589676412912` | identical |
| `inrange` (shift 0, `>>1`, `1<<62`, `(-2)**62`, `-2**62<<1`, INT64_MAX) | both `same stdout` | – |
| `arg` (shift via argument) | both: `OverflowError: integer overflow in <<`, exit 1, stdout prefix | identical |
| `routes` (attribute, list item, dict value) | both: same declared overflow, exit 1, prefix | same mechanism |
| `finally` (argument + `try/finally`) | both: declared overflow, exit 1, prefix | same |
| `plain` (no feature) | both `same stdout` | – |

**Claim checks:**
- Seed generator output byte-identical: **verified** (`diff` rc 0).
- `cmp.sh` now refuses on both builds: **verified**.
- `lab/fuzz/run.py --start 2076418519 --count 1 --modes default,ir`: **verified** — both modes `refused`, 0 DIFF.
- Routed values trap loudly with prefix stdout / `--exact-int` matches: **verified for default + `AIL_IR=1`** (as the test covers); **false for the general path**: with `AIL_UNIFIED_FORCE=1 AIL_EXACT_INT=1`, `arg` still exits 1 with `integer overflow` (d build matches). This is unchanged on `/tmp/base`, so pre-existing and out of scope.
- "No compiler/runtime touched": **verified**.
- Manifest `--check`: **verified** rc 0.

**Tests on HEAD:** `python3 ../tools/par_check.py -j 2 test_ail_fz239 test_ail_safetynet` → 2/2 ok (102 s).

**Pre-existing (not caused by this change; base shows the same):**
- General path (`AIL_UNIFIED_FORCE=1`) ignores `AIL_EXACT_INT` for runtime shift overflow, so the DIFFERENCES row's unqualified "`--exact-int` matches CPython" holds only for the default/IR builds.
- Runtime values routed into `<<` beyond int64 raise a loud `OverflowError` (exit 1, prefix stdout) instead of CPython's big-int result — declared int64 contract, fuzz lab classes it `overflow`, not DIFF.
- Untracked `.agent/pipeline.md` present in the tree (harness artifact, not the diff).

**Not checked:** full suite (deliberately not run per instructions); instruction-count speed checks (no hot-path code changed).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=11 out_tokens=9135]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-07T21:15:34Z
