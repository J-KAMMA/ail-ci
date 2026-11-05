# job job-docmigr1-11060454  started 2026-11-05T19:59:41Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. All five review defects were still present; each is now fixed and verified with probes.

**Fixes in `docs/MIGRATING.md`**
1. Item 3 (bullet, heading, body): replaced "real C stack limit" with the fixed 50,000-frame guard in the default build.
2. Item 14 (bullet, heading): constant negative exponent gives CPython's float; only a non-constant one stops.
3. Item 11 (bullet, heading): only constant operands are refused; run-time operand is documented as a bug (`nan`), with a new sample and RESULTS Bugs row.
4. Item 16 advice: dropped `"rb"` + decode, since `bytes.decode("utf-16")` is refused too.
5. Footer: now says a fallback prints a `note:` line plus a second reason (two for `threads.py`).

**Probes (default `d` / forced-general `g` vs CPython)**
- `down(49999)`: default prints `49999`, exit 0; CPython `RecursionError`, exit 1. `down(50001)`: default `RecursionError`, exit 1 — the guard is a 50k counter.
- `print(2 ** -1)`: `0.5` exit 0 on both builds, same as CPython.
- non-constant `x=-4.0; n=0.5; x**n`: default `nan` exit 0; forced-general exit 3.
- `bytes([104,0]).decode("utf-16")`: refused both builds (`utf-8, ascii, latin-1`).
- `threads.py`: `grep -c '^note:'` = 2.

**Tests**
- `test_ail_docs_migrating`: 3 tests OK (final content).
- `par_check -j 2 test_ail_docs_migrating test_ail_safetynet test_ail_files test_ail_corpus_findings3`: 4 modules, 0 failed.
- `test_ail_safetynet` on final commit: 0 failed.
- `tools/update_manifest.py --check`: exit 0.

Committed as `e5c1485`; working tree clean apart from the harness's untracked `.agent/pipeline.md`. `origin/integ` is not present locally, so I could not run the `git diff --stat origin/integ` check; this commit touches only allowed files.
[commandcode stop=end_turn turns=22 out_tokens=16449]

## review 0
[model commandcode/deepseek-v4.1-flash]
All five review defects check out as fixed. Everything I ran matches the corrected page.

**What the change really does:** docs-only correction of five behaviour claims in `docs/MIGRATING.md`, plus a new bug sample `lab/migrating/complex_power_runtime.py` and its RESULTS "Bugs" row. No compiler/runtime source is touched — a plain program's `--debug-dir program.c` is byte-identical to `/tmp/base`.

**Probes** (`bash ~/tools/cmp.sh … $PWD`, default `d` / forced-general `g` vs CPython 3.12):

| probe | result |
|---|---|
| `rec49999` (down(49999)) | `d` prints `49999` exit 0; CPython RecursionError exit 1 |
| `rec50000` / `rec50001` | `d` RecursionError exit 1; `g` prints the value exit 0 → the default guard is a fixed ~50k counter, as the page now says |
| `rec1500` | `d` prints `1500` exit 0; CPython RecursionError → "depth between 1,000 and 50,000 succeeds here" verified |
| `const_negexp` (`2 ** -1`, `float(2) ** -1`) | `0.5`, same on both builds = CPython |
| `complex_runtime` (`x=-4.0; n=0.5; x**n`) | `d` prints `nan` exit 0; `g` exit 3 `AIL limit: complex number…` → page's "known bug" paragraph and RESULTS row verified |
| `decode_utf16` (`bytes.decode("utf-16")`) | build refused on both paths → new item-16 advice ("rb does not help") verified |
| plain program C | `program.c` identical HEAD vs `/tmp/base` |

Also verified: `threads.py` build emits exactly 2 `^note:` lines (footer claim); `tools/update_manifest.py --check` exit 0; no stale "real C stack"/"decode them yourself"/"stack limit" text remains in the page.

**Tests:** `par_check.py -j 2 test_ail_docs_migrating test_ail_safetynet` → 2 modules, 0 failed (safetynet now passes on HEAD, unlike review 1's flaky S4).

**Claims:** the five fixes are all present and match the probes — verified. "3 tests OK", "working tree clean except `.agent/pipeline.md`", `update_manifest --check` exit 0 — verified. "4 modules, 0 failed" — only 2 run per review rules, so the `test_ail_files`/`test_ail_corpus_findings3` part is unverified. "origin/integ not present locally" — verified.

**Unverified:** CI shards (nothing pushed); "does not move with the platform" is true of a counter but not directly measurable here.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=13 out_tokens=11273]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T21:32:48Z
