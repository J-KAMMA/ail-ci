# job job-rbdifflib2-11050254  started 2026-11-04T17:56:41Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
All green on the final commit. Final report:

## Report

**Job:** re-applied accepted `difflib2` change onto `6f4447c0` (current tree). Commit `be6732fa` on `job-rbdifflib2-11050254`, 23 files, +1278/−7.

**What applied:** the bundled `AIL_CURRENT/stdlib/difflib.py`, `test_ail_std_difflib.py` + `tests.d/` registration, and `lab/stdlib/difflib/` (12 programs, RESULTS.md, bench) — verified byte-identical to `git diff 327abd3..FETCH_HEAD` for those paths. `.github/workflows/agent-worker.yml` (GH Models token removal) also applied.

**Conflict resolution:** the `pyfunc.py` hunk was *not* added — this tree already carries that fix in a newer shape (`_drop_text_overrides` before claim collection plus the guard inside `_override_from_site`), so both sides' intent is kept without the older helper. `manifest.d/*.txt` were not patched; regenerated with `tools/update_manifest.py` (`--check` exit 0).

**Records:** DIFFERENCES row `C?-job-rbdifflib2-11050254-1`, DEVLOG entry at top. `tools/diff_ids.py` **does not exist in this tree** (`find` found no such file), so that step could not be run.

**Tests (on commit `be6732fa`):** `test_ail_std_difflib` 2/2, `test_ail_safetynet` 5/5, `test_ail_files` 18/18 (1 skip), `test_ail_corpus_findings3` 2/2 — all OK.

**Probes** (`bash ~/tools/cmp.sh`, both builds g=`AIL_UNIFIED_FORCE=1`, d=default):
| probe | covers | g | d |
|---|---|---|---|
| p1_seqmatcher | ratios, find_longest_match, matching_blocks, opcodes, grouped(1), empty matcher, Match iter/index/eq/lt/hash/IndexError, isjunk, autojunk+bpopular | same stdout/exit | same |
| p2_diffs | unified/context (files, dates, lineterm, n=0, empty), Differ.compare, ndiff/restore tags 1&2, diff_bytes (unified, context, 8-arg custom dfunc, non-ASCII bytes), iterator `next()` then rest | same | same |
| p3_close_junk | get_close_matches (n, cutoff, duplicates, empty, n=0 ValueError), IS_LINE_JUNK (str + bytes TypeError), IS_CHARACTER_JUNK | same | same |
| p4_provenance | values through argument, list item, attribute, dict value; re-read after list mutation; `next()` on ndiff/Differ/context_diff | same | same |
| p5_htmldiff_refused | `HtmlDiff` | refused by name | refused by name |
| p6_edges | n=0/1/2/3/10, grouped n=0/−1, empty sides, restore, bytes non-ASCII repr, n=−1/cutoff=1.5 ValueErrors | same stdout/exit | same |

One probe bug found in my own code was fixed before the final run (an 8-arg `dfunc` is required; a defaults-having function is refused as a first-class value — that refusal is pre-existing and expected).
[commandcode stop=end_turn turns=47 out_tokens=20353]

## review 0
[model commandcode/deepseek-v4.1-flash]
## Review report

**What the change really does:** re-adds the accepted `difflib2` payload — bundled `AIL_CURRENT/stdlib/difflib.py`, its test module + `tests.d/` registration, the 12 `lab/stdlib/difflib/` programs/RESULTS/bench, the accepted `agent-worker.yml` token removal — and regenerates `manifest.d/`, plus the required DIFFERENCES/DEVLOG records. No compiler or runtime file is touched (the accepted `pyfunc.py` hunk is deliberately skipped).

**Fidelity.** All 17 payload files (difflib, test, tests.d, 12 lab programs, RESULTS, bench) hash-identical to `git show FETCH_HEAD:...`. `manifest --check` exit 0. `tools/diff_ids.py` indeed absent (`git ls-files`), so that step is N/A. The skipped `pyfunc.py` fix exists on the base in a newer shape (`_drop_text_overrides` at both propagation sites + the guard in `_override_from_site`, lines 32490–32534/32604/33017); `pyfunc.py` is unchanged from `work`, and `manifest.d/45.txt` was correctly not patched. Record id `C?-job-rbdifflib2-11050254-1` matches the branch-name rule; DEVLOG entry is at top, dated 2026-11-04.

**Probes** (`bash ~/tools/cmp.sh <p> $PWD`, HEAD; both `g`/`d` builds):
| probe | targets | result |
|---|---|---|
| p1_seq | empty/empty `ratio`=1.0, empty sides, `get_grouped_opcodes(0/-1/2)` repeated-call mutation of cached opcodes, aliased list `a is b`, in-place `b` mutation after caching, bytes sequences, list-of-int sequences, `isjunk` via a named function | same stdout+exit both builds |
| p2_iter | mutate list after `unified_diff()` before consuming; mutate after `Differ.compare()` before consuming; mutated `a` vs cached opcodes | same |
| p3_prov | values via argument, list item, attribute, dict value; `get_close_matches` n=0/-1/1/9, duplicates, cutoff=1.0/1.5 error text | same |
| p4_edges | unified/context empty, n=0, n=-1, `lineterm=''`, dates, `diff_bytes` non-ASCII `\xff`, 8-arg custom `dfunc` | same |
| p5_ndiff | `ndiff` tags, `restore` which=0/3/1.5/'1', `IS_LINE_JUNK` unicode ws + bytes TypeError, `IS_CHARACTER_JUNK`, Differ with charjunk | same |
| no-feature (`--debug-dir`) | plain dict/list program, HEAD vs `/tmp/base` | generated C identical except embedded temp path/cwd |

`04_unified_edges.py` refused by name (`not in the subset: a **kwargs call argument`), `12_htmldiff.py` refused by name (`module 'difflib' has no top-level name 'HtmlDiff'`), matching the report.

**Tests on `be6732fa`** (`par_check.py -j 2`): test_ail_std_difflib, test_ail_safetynet, test_ail_files, test_ail_corpus_findings3 — 4/4 modules OK, 0 failed (763 s).

**Pre-existing:** none observed — every probe matched, and non-feature C is unchanged.

**Unverified:** the report's per-test counts (2/2, 5/5, 18/18+1 skip, 2/2) — I verified module-level pass only; the `pyfunc.py` claim I checked structurally, not by running the sdkdiag tests; no instruction-count check (no compiler/runtime edit, and the non-feature C is byte-identical, so no hot path can change).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=32 out_tokens=23856]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-04T20:21:10Z
