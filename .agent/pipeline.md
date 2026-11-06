# job job-fz235-11062253  started 2026-11-06T13:54:39Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
**Report — fz235 (branch `job-fz235-11062253`, commit `2723cdd`)**

**Not reproducible on this tree; no code changed.** The difference is the fz1 defect (seed `2075200054`, fixed 2026-10-28), resurfacing under seed `2076311105`: an `IndexError` raised by `'q q'[3]` in a `try`'s `else` clause was caught by that same `try`'s `except IndexError`, which printed the extra `4 4 0` and let AIL exit 0. Current builds propagate it through `finally` (`242`), matching CPython's exit 1. `test_ail_fz1.py` already pins this.

**Why the literal program can't show it:** both builds refuse it by name at compile time — its dead `except ValueError:` branch holds two out-of-int64 constants (`v12[-8 * 4611686018427387904]`, `-9223372036854775807 - 82`).

**Probes** (`cmp.sh`, both builds; all match stdout+exit):
- `/tmp/probes/fz235.py` — refused by name on both builds (as above).
- `fz235b.py`, `fz235c.py` — full program with the two dead constants in range: matches (16 lines, exit 1).
- original text built with `AIL_EXACT_INT=1` — matches on `g` and `d` (16 lines, exit 1).
- `q1`–`q4` — `raise` in `else` (matching/non-matching type), raise from a call, `'abc'[7]` in `else`: match.
- `r1`–`r5` — runtime `IndexError`/`KeyError`/`ZeroDivisionError` in `else` from an argument, a list item, an attribute, a dict value, and inside a `while`: match.
- `p1`–`p3` — out-of-range positive/negative string index, literal and variable: match.

**Other differences seen:** stderr only — default build prints `KeyError: key error` where CPython prints `KeyError: 'missing'` (general build prints `'missing'`); stdout and exit codes identical.

**Tests:** `test_ail_fz1`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 26 tests, OK (1 skip). `tools/update_manifest.py` run, `--check` passes.
[commandcode stop=end_turn turns=26 out_tokens=21743]

## review 0
[model commandcode/deepseek-v4.1-flash]
Started 14:12, now 14:21 — within budget. All checks are done.

**What the change really does:** adds one DEVLOG.md entry (23 lines) and no code, no tests, no manifest changes. So no runtime/C semantics can change; the review reduces to whether "does not reproduce; change nothing" is correct.

**Probes** (`bash ~/tools/cmp.sh ... $PWD`, g + d builds; IR spot-checked with `AIL_IR=1`):

| probe | construct | CPython | HEAD g/d |
|---|---|---|---|
| `fz235.py` (task program) | original | exit 1 | both refuse by name: `int64 index out of range: -36893488147419103232` |
| `fz235.py` + `AIL_EXACT_INT=1`, g/d/IR | original, refusal bypassed | 16 lines, exit 1 | 16 lines, exit 1, same |
| `q1` | `IndexError` in `else`, same-try `except IndexError` | `fin`, exit 1 | same |
| `q2` | index error in `else` from a list argument | exit 1, "fin" | same |
| `q3` | in `else`, from an attribute (`o.b.v[5]`) | exit 1 | same |
| `q4` | in `else`, from a dict value (`d["k"][4]`) | exit 1 | same |
| `q5` | `else` in a `while`, slice copy then mutate, non-matching handler | exit 1 | same |
| `q6` | error in inner `else` caught by *enclosing* try | exit 0 | same |
| `q7` | `raise` in `else` inside a loop, `finally` each step | exit 0 | same |
| `q8` | `'q q'[3]`-shaped string-index in `else` of a try with `except IndexError`, in a `while` | exit 1 | same (both builds, and IR) |

**Base comparison:** all probes identical on `/tmp/base` (work cddbf05); a non-feature program's `--debug-dir` `program.c`/`program_mix0.c` are byte-identical HEAD vs base (only temp paths in `native_report.json` differ). The reported `4 4 0` line is exactly the `except IndexError` branch, which current builds do not enter — fz1 (seed `2075200054`, fixed 2026-10-28, pinned by `test_ail_fz1.py`) is confirmed in DEVLOG.

**Tests:** `test_ail_fz1` + `test_ail_safetynet` on HEAD: 2 modules, 0 failed. No test module added/edited by the change.

**Claims:** (1) not reproducible / no code changed — verified; (2) cause = fz1 fix — verified behaviourally and by record; (3) two out-of-int64 constants — verified (compiler reports the first, at `v12[-8 * 4611686018427387904]`); (4) all named probes match — verified independently; (5) "other difference: default build prints `KeyError: key error`" — **false for my probes**: `{}["missing"]`, `raise KeyError("m1")` (caught and uncaught) all print `KeyError: 'missing'`/`'m1'` on both builds, identical to CPython. Non-blocking (stderr only, and pre-existing since the change is docs-only).

**Pre-existing:** none that blocks; the int64 refusal is a by-design named refusal, acceptable per the rules. **Unverified:** full suite (not run by design); speed (docs-only change, no hot code touched).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=31 out_tokens=13913]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-06T15:35:58Z
