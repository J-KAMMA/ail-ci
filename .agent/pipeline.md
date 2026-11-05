# job job-whyail1-11052042  started 2026-11-05T11:44:56Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Final report:

**Deliverable**
- `docs/WHY.md`: 64 lines (cap 120). 76 distinct number tokens, each traced to a committed file; 21 distinct tokens sit in "Where it is not there yet" (cap: 12 / 4). Covers speed, binary size/disk, safety, Python compatibility, and eight measured losses (compile time, `.py` typed reach, `tree_fold` RSS, stdlib census, `rail_transfer`, inference, csv_rollup binary, errux diagnostics).
- `AIL_CURRENT/test_ail_docs_why.py` + `tests.d/test_ail_docs_why.txt`: fails a number with no same-line `[source: path]` mark, fails a token absent from its cited file, checks every link is a committed file, and enforces the 120-line cap. Confirmed it fails on `116 / 160` → `116 / 161`, then restored.
- Manifest pins refreshed via `tools/update_manifest.py`; `--check` exits 0.

**Tests run on the final content**
- Pass: `test_ail_docs_why`, `test_ail_manifest_compiler`, `test_ail_docs_blocks`, `test_ail_files`, `test_ail_corpus_findings3`.
- `test_ail_safetynet` fails `S4_generators_gc` (AIL prints one line, CPython six). Pre-existing: that test file and every compiler file are byte-identical to `origin/integ`; my diff touches only docs and new test files, so no regression from this job.

**Git**
- Commit `6248ea1c`, files: `docs/WHY.md`, `AIL_CURRENT/test_ail_docs_why.py`, `AIL_CURRENT/tests.d/test_ail_docs_why.txt`, `AIL_CURRENT/manifest.d/29.txt`, `30.txt`.
- Not pushed and no PR: the job rules say "do not push"; CI shards were therefore not run.
- `git diff --stat origin/integ` still lists the 521-file export superset (`.agent/*`, `corpus/gdev/*`) that existed before my work; I did not touch it. Within my commit, only the five allowed files change.
[commandcode stop=end_turn turns=29 out_tokens=37830]

## review 0
[model commandcode/deepseek-v4.1-flash]
## Review — whyail1 (`docs/WHY.md` + number-tracing test)

**What the diff really does.** Adds a 64-line public claim page (`docs/WHY.md`), a unittest that checks every numeric token on a line occurs as a substring in the file named by that line's `[source: …]` mark, and two manifest pin lines. No compiler, runtime or existing doc is touched (verified: 0 files among `pyc/pyfunc/cruntime/unified/safetynet` changed). No AIL program is edited, so 4a does not apply and no hot code is affected.

**Probes** (3, in `/tmp/rprobes/`, run with `cmp.sh` on HEAD and compared to `/tmp/base`):
- `p1_hello.py` print/int arithmetic — default and forced: same stdout, exit 0; `program.c` byte-identical to base.
- `p2_types.py` list-in-dict, class attr, `2**62`, `-2**63` — same, identical C.
- `p3_empty.py` empty list/join, negative range, `-0.0` — same, identical C.

All three match CPython; generated C is unchanged, as expected for a docs-only diff.

**Tests** (`par_check.py -j 2`): `test_ail_docs_why` ok, `test_ail_manifest_compiler` ok, `test_ail_safetynet` **ok (163 s, 0 failed)**. `update_manifest.py --check` exits 0.

**Report claims**
- 64 lines / 76 distinct traced tokens / 21 distinct loss tokens — **verified** (I reproduced all three; no token missing from its cited file).
- Test fails an unmarked number, fails a token absent from its file, checks links, enforces 120 lines — **verified** by in-memory tampering (`116/161` and `80.8x` are caught; an unmarked number line is caught).
- "fails on `116 / 160 → 116 / 161`, then restored" — **verified**.
- Manifest pins refreshed, `--check` 0 — **verified**.
- `test_ail_safetynet` fails `S4_generators_gc` — **false**: it passes on HEAD, and every safetynet/compiler file is byte-identical to base.
- "521-file export superset vs origin/integ" — **verified in substance**, actual count 527 (base `work` already differs from `origin/integ` by 522 files). Pre-existing.
- `test_ail_docs_blocks`, `test_ail_files`, `test_ail_corpus_findings3` pass, and the 20 shards — **unverified** (not required here; no push).

**Defects**
1. `docs/WHY.md:26` — "the corpus run records 4 overflow stops among **338 runs**." In `lab/corpus/RESULTS.md:25-27`, 338 is the **`same`** column of the "Runs by class" table; the runs total is 338+95+4+2+19+3 = **461**. Expected "4 overflow stops among 461 runs"; actual "among 338 runs". The test cannot catch this because 338 is present in the file — it proves presence, not meaning.
2. `docs/WHY.md:56` says the build-disk figures are "not used", yet `docs/WHY.md:22` uses `9.50x` as a claim; the pair it lists as one measure (ROADMAP's 10× geomean over 10 tasks vs compare_cand's 9.50× on `csv_rollup`) are not the same measure. Either the figure is a claim or it is disclaimed — not both.

**Limitations (not counted as defects, since the task specified a substring check)**
- The trace test is substring-based: changing `18 ms` to `19 ms` on `docs/WHY.md:11` is **not** caught, because `19` occurs inside the checksum `4196337.4013470374` (`lab/array/RESULTS.md:28`). The "fails when you change one number" done-check holds only for numbers whose token does not occur inside another number.

**Pre-existing** (identical on base): the 527-file `origin/integ` diff, and the ROADMAP-vs-COMPARISON wall-time conflict the page already lists.

**Unverified:** the three non-required test modules, the 20 shards, and speed (no hot code touched).

VERDICT: FIX
1. `docs/WHY.md:26` — "4 overflow stops among 338 runs": 338 is the `same` run count, not the run total (461) in `lab/corpus/RESULTS.md:25-27`. Expected "among 461 runs" (or "4 overflow stops, 338 outputs matching"); actual "among 338 runs".
2. `docs/WHY.md:56` declares the `9.50x` build-disk figure unused while `docs/WHY.md:22` uses it; and the 10×/9.50x pair are different measures (10-task geomean vs one task). Expected one treatment; actual both.
[commandcode stop=end_turn turns=24 out_tokens=30596]

## worker report 1
[model commandcode/deepseek-v4.1-flash]
Both defects are fixed and committed as `90d22177`. Final report:

## Fixes

1. **`docs/WHY.md:26`** — `338` was the `same` column, not the run total. Now: *"the corpus run records 4 overflow stops and 338 outputs matching CPython"* — both figures come from the `Runs by class` row (`lab/corpus/RESULTS.md:27`), and the phrasing no longer calls 338 a run total.
2. **`docs/WHY.md:22` / `:56`** — settled the disk figure on one treatment. `9.50x` stays a claim in "Binary size and disk" (it is the measured `csv_rollup` value in `lab/compare_cand/RESULTS.md:94`); the build-disk bullet is gone from "Numbers I do not use", since ROADMAP's `10×` is a 10-task geomean, a different measure. Only the genuine same-measure wall-time conflict (2.1× vs 1.00x) remains disclaimed.

## Verification

- `python3 AIL_CURRENT/test_ail_docs_why.py`: **5 tests OK** (63 lines ≤ 120; 75 distinct traced tokens ≥ 12; 21 loss tokens ≥ 4).
- Tamper check: changing `116 / 160` → `116 / 161` fails with `line 49: '161' is not in ['lab/errux/RESULTS.md']`; restored.
- Required modules (`par_check.py -j 2`): `test_ail_docs_why`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — **4 modules, 0 failed**. Note: `test_ail_safetynet`'s `S4_generators_gc` fails under `ulimit -v 1500000` (allocation inside the generator case) but passes uncapped (161–190 s); the reviewer's earlier "passes on HEAD" is reproduced uncapped.
- `tools/update_manifest.py --check`: **rc=0**.
- Probes: `p1_hello`, `p2_types`, `p3_empty` — same stdout as CPython in both default and `AIL_UNIFIED_FORCE=1` builds; `p4_overflow` (int from text beyond int64) — refused by name in both builds with the int64-out-of-range message.
- Diff vs `origin/integ` is still dominated by the pre-existing 522-file base export; my commits touch only `docs/WHY.md`, `AIL_CURRENT/test_ail_docs_why.py`, `AIL_CURRENT/tests.d/test_ail_docs_why.txt`, and the manifest pins.

Not pushed, per the job rules.
[commandcode stop=end_turn turns=22 out_tokens=14477]

## review 1
[model commandcode/deepseek-v4.1-flash]
## Review

**What the change really does:** adds `docs/WHY.md` (63 lines, 75 distinct number tokens, each line carrying a `[source: …]` mark), `AIL_CURRENT/test_ail_docs_why.py` which checks every number token occurs in the file named on its line plus link/commit/length rules, its `tests.d` registration, and the two manifest pins. No compiler, runtime, or benchmark file is touched (`git diff --stat work..HEAD`: 5 files).

**Numbers re-checked against the cited files (all match semantically, not just as substrings):**
- `lab/corpus/RESULTS.md:27` Runs-by-class: `same 338`, `overflow 4` — the fixed sentence uses both correctly.
- `docs/COMPARISON.md`: wall 6/10 (echo_pack 934/1895 0.49x, ledger_bin 840/2833 0.30x), binary range 34–102 vs 4450–4518 10/10, compile 1.87–11.17 vs 0.19–0.56 0/10, tree_fold 464.6/314.9 1.48x, rail_transfer 17.96x (862/48).
- `lab/compare_cand/RESULTS.md`: build disk 0.22/4.40/0.02 MiB, 9.50x; binary 64/21 KiB 3.07x; toolchain 41,692 / 1,563,104 / 124,048.
- `lab/array`, `examples/algos` (11/12, 0 typed, 12 general, 1.04x, mandelbrot 92/1826 19.75x), `lab/pyperf` (0.184/4.953, 1.359), `lab/bigbench` (1.1009→0.9990 9.3 %, 103760–142168, 5/5), `lab/errux` (116/160, all 40 clean), `lab/stdlib/{hashlib,shlex,csv}`, `lab/typeshed` (79.5 %, 91.9 %), `lab/stdcensus` (3/197, 187, 6), `lab/infer` (56.7x, 10.1x), `docs/ROADMAP.md` (0/10 typed, 50–200×, refuses 3).
- Report claims verified: 5 tests OK; 63 lines; 75 traced tokens; 21 loss tokens; `update_manifest.py --check` rc=0; tamper `160→161` fails (`161` is not in `lab/errux/RESULTS.md`); only the wall-time 2.1× vs 1.00x conflict is disclaimed (ROADMAP build-disk 10× is a different 10-task fixture, not a same-measure conflict).

**Tests on HEAD:** `par_check.py -j 2 test_ail_docs_why test_ail_safetynet` → 2 modules, 0 failed (docs_why 0.1 s; safetynet 161.7 s uncapped). Also ran `test_ail_files` (0 failed, 89.5 s).

**Probes:** the change has no compiler/runtime behaviour, so there is nothing behavioural to probe. One control program `p1_hello.py` (int from text) builds and matches CPython on both builds (`bash ~/tools/cmp.sh` → g/d same stdout), and `--debug-dir` `program.c` is byte-identical between `/tmp/base` and HEAD.

**Pre-existing:** none observed in the run I did; the worker's `S4_generators_gc` failure only under `ulimit -v` is unrelated to a docs change (not reproduced uncapped).

**Minor observation (not blocking):** the corpus sentence says "111 match; 95 refused, 7 differ and 3 crash" out of 219, omitting the 2 `overflow` and 1 `limit` program classes (111+95+7+3=216); every stated number is true, the enumeration is just incomplete.

**Unverified:** the 20 CI shards (not pushed, per job rules); `test_ail_corpus_findings3` (untouched module, not re-run).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=26 out_tokens=25585]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T13:47:48Z
