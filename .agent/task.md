**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
All checks done. Here is my review.

**What the change really does (one line):** adds a lab-only census harness (`lab/pyproof/report.py`) with a fixed 55-program list, recorded `results.jsonl`, generated `RESULTS.md`, five reproducers, a unit test and manifest entries — it touches no compiler or runtime file.

**Claims checked**

| claim | verdict |
|---|---|
| Buckets include general fallbacks; ranking import 6, list 3, int64 3, dict 2, None 2 | verified mechanically (`bucket_counts` on the jsonl reproduces exactly) |
| all 15 general rows now record `strict_path: refused` | verified |
| `programs.txt` and `results.jsonl` both 55 rows, same order | verified |
| int64 reproducer is 3 lines and refuses on both builds | verified via `cmp.sh` |
| 5 reproducers show their bucket via `report.py` | verified (3 refused/general, 2 refused/refused, each maps to its bucket) |
| `test_ail_pyproof_report.py` 4 tests OK | verified |
| `test_ail_pyproof_report` + `test_ail_safetynet` pass | verified (`par_check -j 2`: both ok, 180 s) |
| manifest `--check` rc 0; diff confined | verified |
| typed 24/55, general 15, refused 16, wrong 0, geomean 6.32x | **counts/geomean match the file, but the data is wrong — see defect 1** |
| `ticket_audit` genuine timeout | unverified |

Nothing compiled can change: the diff contains no compiler/runtime file, so there is no "unused feature" C-output probe to run.

**Defects**

1. **Six crate rows are not refusals — the census dropped the lab's build step.** `report.py` copies only sibling `*.py` and never runs `ail_cargo.py build`, so the generated `*_ffi.py` and static library are absent. With the lab's own runner:
   - `examples/crate/rle/main.py`: default compile rc 0, **no** general-path note, AIL run rc 0, stdout == CPython. Census says `refused` / `import of 'rle_ffi' is not available`.
   - `examples/crate/textstat/main.py`: same (typed, matches). Census says `refused`.
   - `examples/crate/fnvhash/main.py`: compiles typed rc 0, but the default binary exits 1 with `OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints)` while CPython exits 0 and prints five exact big ints. Under the task's rule this is a **`wrong` row** (silent/loud difference) that must be reported at the top with a reproducer; with the lab's `--exact-int` it matches.
   Consequence: the #1 bucket (`import of 'X' is not available`, alone 6) is an artifact, the typed share is understated by at least 2 (24 → 26), `refused` is inflated, and the claimed `wrong 0` is false. Root cause: `census_one` never runs CPython for a refused row, so an oracle failure (missing generated module) is indistinguishable from a language refusal. The three `bench.py` rows import the same FFI and are likely affected too (I did not rebuild them individually).

2. **Base provenance is wrong.** `integ_sha()` silently falls back to `HEAD`; the recorded `0aa7d3c07be…` is the worker's own census commit, not `integ` (no `origin/integ`/`integ` ref exists; the real base is `work` = `803122d…`). `RESULTS.md` prints `Base: integ 0aa7d3c…`. The README discloses the fallback, but the generated report still mislabels the base.

**Pre-existing:** none (no compiler/runtime file changed, so no probe can differ on the base).

**Unverified:** `ticket_audit`/`scar_life` timeout claim; `test_ail_files` and `test_ail_corpus_findings3`; the three crate `bench.py` rows; a full 55-row re-run (I re-ran 4 rows plus the 3 crate mains); speed impact (no hot code touched).

VERDICT: FIX
1. Six crate rows misclassified. Probe (existing): `examples/crate/rle/main.py` and `examples/crate/textstat/main.py` — expected default compile rc 0 on the typed path and stdout == CPython (verified via `AIL_CURRENT/test_ail_examples_crate.py`); actual census `refused` / `import of 'rle_ffi' is not available`. Probe: `examples/crate/fnvhash/main.py` — expected `wrong` (typed build, AIL exits 1 `OverflowError: integer overflow in +` vs CPython exit 0 with exact values), or matching with `--exact-int`; actual `refused` with the import text. Fix: run `ail_cargo.py build` for the crate rows (and their `bench.py` input), and run CPython for every row so a missing artifact cannot masquerade as a refusal.
2. `RESULTS.md` reports `Base: integ 0aa7d3c…`, which is `HEAD`, not `integ` (actual base `work` = `803122d…`). Expected the base ref/sha; actual the worker's own commit.
[commandcode stop=end_turn turns=37 out_tokens=36276]


--- ORIGINAL TASK ---
Lane: pyproof

# pyproof1: a typed-reach census of every plain-Python program in the repository, with ranked blockers

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** the roadmap P1 measure ("the `.py` sources reach the typed path"), taken over every plain
Python program the repository already has, not only the 10 compare-lab tasks. Today each lab reports its own
programs in its own format (`lab/pyperf/RESULTS.md`, `examples/apps/`, `examples/mdlite` or wherever appmd1 put it,
`examples/tutorial_project/`, `lab/compare/src/*/main.py`, `lab/compare_cand/src/*/main.py`), so no one knows the
total typed share or which refusal blocks most programs. The target: one reproducible report with N programs (expect
40-60), each `typed`, `general`, `refused` or `wrong`, the first reason, the default-build speed against CPython where
it builds, and blocker buckets ranked by how many programs each would move to typed. Like `lab/stdcensus`, but for
user-style programs. No compiler file is edited.

Base: `origin/integ`. Files you may create or edit, and no others (all new):
- `lab/pyproof/report.py`, `lab/pyproof/programs.txt` (the fixed list), `lab/pyproof/results.jsonl`,
  `lab/pyproof/RESULTS.md`, `lab/pyproof/README.md`
- `lab/pyproof/repro/*.py` (one reproducer per top bucket)
- `AIL_CURRENT/test_ail_pyproof_report.py` and `AIL_CURRENT/tests.d/test_ail_pyproof_report.txt` (one line:
  `test_ail_pyproof_report`)
- the manifest files that `tools/update_manifest.py` writes

## Sub-steps

1. **The list (15 min).** Find every plain-Python program (no `.ail`, not a `typed.py`, not a test module, has a
   `__main__` path or top-level code that prints) under `examples/`, `lab/pyperf/`, `lab/compare/src/`,
   `lab/compare_cand/src/`, and the docs example dirs (`AIL_CURRENT/language_examples/quickstart/`,
   `examples/tutorial_project/`). For each, note how it gets its input (none, stdin file, argv) from the lab's own
   runner or test. Write `programs.txt`: path, input spec, one per line, fixed order. Commit, push, and open the PR
   against `integ`.
2. **The runner (25 min).** `lab/pyproof/report.py` (model: `lab/stdcensus/report.py`): for each program, build with
   `--strict` (typed or the refusal text), then with the default command (typed, general with the `note:` reason,
   or refused); run the default binary on the input and compare stdout and exit status with `python3` (`wrong` if
   exit 0 and output differs); time both (median of 3, small inputs: at most 2 s per CPython run); at most 2 builds at
   a time, `ulimit -v 1500000`, `AIL_NO_CACHE=1`, 120 s timeout per build. It writes `results.jsonl` and renders
   `RESULTS.md`: counts, one row per program, and buckets (refusal text with names, numbers and paths replaced by
   placeholders), each with `alone` (programs whose only reason is this bucket) and `listed`. Commit and push.
3. **Run and reproducers (25 min).** Run the full census. For the top 3 buckets by `alone`, write a reproducer of
   3-15 lines in `repro/` that shows the same refusal or fallback, and check it does. Any `wrong` row is reported at
   the top of `RESULTS.md` with its reproducer. Commit and push.
4. **Test (15 min).** `AIL_CURRENT/test_ail_pyproof_report.py` runs `report.py` on a fixture list of 3 tiny programs
   (one typed, one general, one refused, written in the test's temp dir) and checks the jsonl fields and the bucket
   counts. It does not run the full census. Register it (Appendix A rule 6). Commit, push, and wait for CI.

## Done-check

- `RESULTS.md` lists every program in `programs.txt` with a result, and the counts add up.
- The headline line: `typed T / N, general G, refused R, wrong W` and the geomean speed-up over CPython of the
  programs that build.
- At least 3 ranked buckets, each with a working reproducer.
- `python3 AIL_CURRENT/test_ail_pyproof_report.py` passes.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only files under `lab/pyproof/` and the test files above.

## Stop rule

Do not change any program to make it build. A `wrong` result is a silent difference: write its reproducer first,
then go on. If the full census would take more than 30 minutes, cut each program's input, say so in `README.md`, and
keep the list complete. Stop when 80 minutes pass. Push what is done first.

## Appendix A: standing rules (from agent-brief-rules.md)

1. No regressions: a program that built and matched CPython before must still do so in the default build. A loud
   stop is allowed only where the value cannot be computed.
2. Probe ints beyond int64 wherever ints come from text or arithmetic; run probes in the default build and with
   `AIL_UNIFIED_FORCE=1`, compare both with `python3`.
3. Push early, open the PR against `integ`, wait for all 20 `shard` checks (`gh pr checks <n> -R J-KAMMA/ail-ci`, at most
   once every 10 minutes). Report only when all pass, or say which fail and why.
4. Branch from `integ` (or one unmerged PR at most).
5. Memory: wrap heavy runs in `ulimit -v 1500000`; `tools/par_check.py -j 2` at most; leave no background jobs.
6. New test module: `AIL_CURRENT/tests.d/<module>.txt` if the directory exists, else `ail_check.py` MODULES; `git add`,
   `tools/update_manifest.py`, then `tools/update_manifest.py --check`.
7. Never print credentials, run a broad pkill, merge PRs, change repository settings, cancel runs, tag, publish, or edit
   `.github/workflows`.
8. Never edit `AIL_CURRENT/ail_chatgpt.py`, `AIL_CURRENT/ail_syntax.py`, `AIL_CURRENT/python/pkg-v12/pyfunc.py`,
   `pyc.py`, `cruntime.py`, `unified.py`, `buildcache.py`, `pyboxed2.py`, `ir/emit_c.py`, or
   `packaging/ail_lang/cli.py`. Other lanes own them. Do not edit `DEVLOG.md` either: put your notes in the files
   this task names. Edit only the files this task names, plus the manifest files that `tools/update_manifest.py`
   writes.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT --syntax python [--strict] [--debug-dir DIR]`.
  `--strict` means the typed path or a refusal. `-o` must not exist yet. A fallback to the general path prints
  `note: ... built on the general path ...` on stderr.
- `lab/stdcensus/report.py` and `lab/stdcensus/RESULTS.md` are the model for the jsonl, the table and the buckets.
- `lab/compare/run_task.py` and `lab/compare/tasks/<t>/gen.py` (`cases(rng)`) produce the compare-lab inputs.
- CPython 3.12 is the oracle: compare stdout and the exit status.

**Rules for every job.**
- **Load:** you are one of up to five agents on a 16 GB PC. Keep local parallelism at 2 (`-j 2`) and never run the whole suite; the full suite runs on CI after merge.
- **Commits:** commit with explicit `git add` on your branch. Messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- **Forbidden:** push, stash, rebase, reset, and deletion outside /tmp.
- **Records:**
  - New DIFFERENCES rows use placeholder ids `C?-<your branch>-N`.
  - Add a DEVLOG entry at the top with today's date.
  - Register a new test module: if `AIL_CURRENT/tests.d/` exists, add `AIL_CURRENT/tests.d/<module>.txt` containing the module
    name and do NOT edit the tuple in `ail_check.py`; otherwise append it to the `MODULES` tuple.
  - `git add` new files, run `python3 tools/update_manifest.py`, then `--check`. Do not hand-edit `MANIFEST.json` or `manifest.d/`.
- **Required tests:** the targeted modules for what you touch, plus test_ail_safetynet, test_ail_files and test_ail_corpus_findings3. Run them on your final commit, not an earlier one.
- **Mandatory self-check before you report.** A reviewer will repeat it, and past reports were wrong about half the time.
  1. Write probe programs in /tmp/probes/ for every behaviour you changed. Cover the boundaries your implementation implies, not only the example: types, widths, empty, negative, aliasing, values reaching the code through an argument, a list item, an attribute and a dict value, and both builds.
  2. Run each probe with `bash ~/tools/cmp.sh /tmp/probes/<p>.py $PWD`.
  3. Every probe must match CPython or be refused by name.
  4. List the probes and their results in the report.
- **Never claim something works unless a probe or test you ran shows it.** If you did not verify something, say so.
- **Tokens:** use grep -n, narrow reads, and `tail` on long logs.
- **Budget:** stop at the budget note, leaving a committed, consistent state.
- **Report:** keep it brief, with numbers.
- Test data: email addresses only on example.com / example.org (the public export audit rejects any other domain).

**Work in few steps** (each step costs model time):
- Write all probe programs first, then run them together with one command, for example a loop over `bash ~/tools/cmp.sh`, instead of one command per program.
- Search only inside the repository (`grep -rn ... AIL_CURRENT tools`), never across `/home` or `/tmp`.
- Read a file once, using a range that is large enough, instead of many small reads.
- Do not re-run a test that already passed unless you changed code since.

**Where you run:** a GitHub Actions runner (4 cores). Commit your work on the current branch; do not push.
