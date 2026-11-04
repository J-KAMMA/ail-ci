# job job-rbdecexact2_rr1-11050423  started 2026-11-04T19:23:48Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. I verified the review's two flagged failures against the current tree and fixed the remaining defect.

**What was wrong:** `test_ail_int64_default` was the only red module in the full suite. Two assertions expected the exact overflow stderr, but prelude raise sites now append the documented `  raised near file:line` line (`test_ail_debug.py`), and the general path does not print it. The failures reproduced on the base, so no compiler/runtime change was warranted — the test was stale.

**Fix:** added `without_site()` (same convention as `test_ail_c169.py`) and applied it to the boundary message check, the `int()` text check, and the typed/general agreement check. No behaviour change.

**Tests (final tree):**
- `test_ail_int64_default` ok 575.6s (previously 11/13)
- `test_ail_safetynet` ok 153.9s
- `test_ail_files` ok 84.6s
- `test_ail_corpus_findings3` ok 175.6s
- `python3 tools/update_manifest.py` run, `--check` exit 0

**Probes** (`bash ~/tools/cmp.sh`, both builds):
- `p_basic` (in-range int ops) — same stdout both builds
- `p_frac`, `p_decimal` — same stdout both builds
- `p_roprop` — `AttributeError ... has no setter`, exit 1 both
- `p_logb` — refused by name both builds (`decimal.Decimal.logb is not supported`)
- `p_intoverflow` — declared int64 stop, exit 1 both
- `p_lcm` — declared int64 stop at the `math.lcm` boundary, exit 1 both

Committed as `a22a608`. `.agent/pipeline.md` left untracked.
[commandcode stop=end_turn turns=33 out_tokens=14450]

## review 0
[model commandcode/deepseek-v4.1-flash]
All checks are done. Here is my review.

## What the change really does
`a22a608` is **test-only plus records**: it adds `without_site()` to `test_ail_int64_default.py` and uses it in (a) the boundary-loop overflow-message check, (b) the typed-vs-general agreement check, (c) the runtime `int()` text check; plus a DEVLOG entry and the regenerated `manifest.d/91.txt` hash. No compiler, runtime, prelude or prelude-exact change. This matches the report.

## Probes (`bash ~/tools/cmp.sh`, /tmp/rprobes, g=general, d=default)
| probe | content | result |
|---|---|---|
| `r1_intovf` | `int(str(k)+"123…")` past int64 | g: message only, exit 1; d: message + `  raised near p.ail:2`, exit 1; stdout empty — declared int64 stop |
| `r2_lcm` | runtime `math.lcm` past int64 | g: `integer overflow in *`; d: same + site at prelude line 19; exit 1 — declared stop |
| `r3_ok` | in-range ops, divmod, lcm/gcd, sum | stdout == CPython, both builds, exit 0 |
| `r4_frac` | Decimal/Fraction arithmetic | stdout == CPython, both builds |
| `r5_nouse` | list/dict/loop only | stdout == CPython; `--debug-dir` `program.c` **byte-identical** to /tmp/base; `exact_depth` count 0 |
| `r6_listitem` | overflow value via list item → dict → attribute | both builds exit 1, message identical, no crash (no site line here — lowering-dependent) |
| `r7_roprop` | property with no setter | both builds `AttributeError: property 'x' of 'C' object has no setter`, exit 1 == CPython |
| `r8_logb` | `Decimal.logb()` | both builds refuse **by name**: `not in the subset: decimal.Decimal.logb is not supported` |

`r3_ok` `program.c` also byte-identical to base; `native_report.json` differs only in temp paths.

## Tests (HEAD, `par_check -j 2`)
- `test_ail_int64_default` **ok 577.3 s** (report: 575.6 s)
- `test_ail_safetynet` **ok 194.8 s**
- `python3 tools/update_manifest.py --check` exit 0; `sha256` of the test file matches `manifest.d/91.txt`; trailer present; only `.agent/pipeline.md` untracked.

## Claims
- Old failures were the stale exact-stderr assertions: **verified** — `r1`'s d-stderr carries the extra site line, so the pre-fix `assertEqual(ran[2], 'OverflowError…\n')` cannot pass; `without_site` strips exactly that line.
- "prelude raise sites append the line, general path does not": **verified** (`r1`, `r2`; `test_ail_debug_flush.py` docstring says the release default path prints it).
- "no compiler/runtime behaviour changed": **verified** by the diff and identical `program.c`.
- Test times: int64/safetynet **verified**; `test_ail_files`, `test_ail_corpus_findings3` **unverified** (not re-run — test-only change cannot touch them; the job required only the edited module + safetynet).
- "Failures reproduced on the base": **unverified literally** (repo is shallow; `work` is the root, no older worktree), but since only the test file changed, the old assertion fails identically by construction, and the diff is exactly the assertion that no longer matches.
- Probes in the worker table: **verified** by equivalents `r1–r8`.

## Pre-existing (identical at `work`, not blocking)
- Non-debug default builds print `  raised near file:line`, while `test_ail_debug.py`'s docstring says stderr is bare without `--debug`; `test_ail_debug_flush.py` expects the line, so the docs disagree. Unchanged by this commit.
- General path prints no site line (documented).
- Subclass shadowing an inherited property with a plain method still reads the property (not re-probed this round; review 1 saw it identical on base).

Speed: no compiler/runtime code changed, so instruction counts cannot move; icount is unnecessary (non-users' C is byte-identical).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=32 out_tokens=16377]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-04T21:16:57Z
