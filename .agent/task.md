Lane: ctime

# ctimes2: cut the largest priced front-end cost that ctimes1 picked, with byte-identical C

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

Depends on ctimes1 (merged into `integ`, or its branch `job-ctimes1-*` as your one stacked base). Read its
`lab/profile/CTIME_FE.md` first. It names one pick: a function, module or wasted attempt, its file, its share of
cold wall, its Amdahl bound and a halved projection.

**Number this moves:** cold build wall of the 10 compare tasks (`lab/compare/src/<task>/typed.py`), median of 3 on
the GitHub runner, and the compiler's own instruction count on them. Baseline: 45.82 s summed cold wall
(CTIME_2026-11.md, child front end 28.31 s of it). The target is the halved projection from `CTIME_FE.md`, and at
least 1.10x on the 3 tasks where the pick costs most. The generated C must not change by one byte.

Price before you build. Write in `lab/profile/CTIME_CUT.md`, before any compiler edit: the pick's measured share,
its Amdahl bound, the fraction of that bound you assume, and what earlier cuts achieved (ctimes1 lists them). Stop if
the halved projection is below 1.10x on every task.

Base: `origin/integ`. Files you may create or edit, and no others:
- the one file that owns the pick, if it is one of: `AIL_CURRENT/python/pkg-v12/pyc.py`,
  `AIL_CURRENT/python/pkg-v12/pymix.py`, `AIL_CURRENT/python/pkg-v12/fastwalk.py`,
  `AIL_CURRENT/python/pkg-v12/unified.py`, `AIL_CURRENT/python/pkg-v12/unified_lists.py`,
  `AIL_CURRENT/python/pkg-v12/pyfront.py`, `AIL_CURRENT/python/pkg-v12/pyboxed2.py`. Change only the functions that
  ctimes1 names, and run `git fetch` and rebase on `origin/integ` just before each push;
- `lab/profile/CTIME_CUT.md` (new), `lab/profile/ccheck.py` (new: the byte-identity check below);
- `AIL_CURRENT/test_ail_ctime_cut.py` (new) and `AIL_CURRENT/tests.d/test_ail_ctime_cut.txt` (new);
- the manifest files that `tools/update_manifest.py` writes.

Do not edit `pyfunc.py`, `cruntime.py`, `optlib.py` or `ir/passes/*`: the codegen, bce-ranges and pyreach lanes are
changing them. If ctimes1's pick lives there, do not build it: build ctimes1's best free row instead, and write the
busy one into `CTIME_CUT.md` as a follow-up for that lane with its price.

## Sub-steps

1. **Price and baseline (15 min).** Write the pricing paragraph above. Write `lab/profile/ccheck.py`: for a list of
   sources it builds each with `--debug-dir`, under `PYTHONHASHSEED=0`, `AIL_NO_CACHE=1`, a fresh `AIL_CACHE`, and
   stores `sha256(program.c)` and `sha256(executable)`. Inputs: the 10 `typed.py` and 10 `main.py` compare sources,
   the first 200 programs of `lab/corpus/programs` (sorted), and `docs/design/alias_study/trans`. Run it on the base
   and save the hashes. Also record, for the 10 `typed.py` builds, the compiler instruction count:
   `cc -O2 -w -include signal.h -include stdlib.h -o /tmp/icount tools/icount.c`, then
   `PYTHONHASHSEED=0 AIL_FE_JOBS=1 AIL_NO_CACHE=1 /tmp/icount python3 -B AIL_CURRENT/ail_chatgpt.py compile ...`
   (with `-B` removed if bytecode is wanted warm, as in CTIME_2026-11.md; use the same choice in both runs).
   Commit, push, open the PR.
2. **The cut (35 min).** Make the change. Typical shapes from earlier jobs: compute a walk once and reuse it; stop a
   typed attempt as soon as its refusal is certain, before the expensive work; memoise a pure function keyed by
   node identity within one build. Keep every result the same, including the order of anything that reaches the C
   text and every refusal message. Commit and push.
3. **Prove and measure (30 min).**
   - `ccheck.py`: all C and executable hashes equal to the base. A single difference is a failure: find it and fix
     it, or revert.
   - The refusal text of every program that is refused on the base is unchanged (`ccheck.py` stores stderr too).
   - Compiler instruction count on the 10 tasks, before and after: report each and the ratio.
   - Cold wall, median of 3, on the GitHub runner if you can run `lab/profile/run.py` there without editing a
     workflow; otherwise on the laptop with the instruction ratio as the claim.
   - Run instructions of each built program: identical executables, so state "identical hashes"; nothing to rerun.
   - `test_ail_ctime_cut.py`: builds 3 tasks and 5 corpus programs and checks the C hash against the stored base
     hashes, under `PYTHONHASHSEED` 0 and 3. Register it (Appendix A rule 6).
   - Run `test_ail_ctime`, `test_ail_fe_jobs`, `test_ail_build_cache`, `test_ail_server` and the new test.
   Fill `CTIME_CUT.md`: price, achieved, achieved over price. Commit, push, wait for CI.

## Done-check

- 0 hash differences in `ccheck.py` over all inputs (C, executable, stderr of refusals).
- Compiler instruction count lower on at least 8 of the 10 tasks and higher on none by more than 0.5%.
- Cold wall at least 1.10x faster on the 3 tasks named in the price, or the job reports the achieved number and
  why it is short.
- The listed tests and the 20 shards pass.

## Stop rule

Stop and report if the halved projection is under 1.10x everywhere, if byte identity cannot be kept, or if the change
needs a file outside the list. Stop when 80 minutes pass. Push what is done first.

## Appendix A: standing rules (from agent-brief-rules.md)

1. No regressions: a program that built and matched CPython before must still do so in the default build.
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
   `cruntime.py`, `optlib.py`, `ir/passes/*`, `buildcache.py`, or `packaging/ail_lang/cli.py`. Do not edit `DEVLOG.md`:
   put your notes in the files this task names.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`. `DIR/program.c` is
  the generated C. `-o` must not exist yet.
- Owner decisions on compile time (2026-10-30): gcc `-O2` stays, no `-O1`, LTO rejected, `-march=x86-64-v3`
  opt-in only; executable bytes may change only if stdout, exit status and run icount do not. This job keeps them
  identical, so none of that is touched.
- `AIL_FE_JOBS` (fepar2) runs the typed front end on worker processes for 8+ functions. Your change must give the
  same C at `AIL_FE_JOBS=1` and `4`; `test_ail_fe_jobs` checks it.
- Laptop wall time swings up to 3x. Use instruction counts for claims made on the laptop.

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
