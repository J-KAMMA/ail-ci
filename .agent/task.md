Lane: fa-devcc
Needs: devcc2 tccprobe1

# devcc3: run `--cc=tcc`'s corpus gate with a real tcc, then close the refusal scan's gaps

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** the programs that `--cc=tcc` builds identically to gcc `-O2`, and the programs it builds that
differ. The second number must be 0. devcc2 (`lab/devcc/RESULTS.md`) added the opt-in mode, but its runner had no
tcc. Its corpus gate ran against a stand-in that ran gcc, so the gate has never seen tcc. Today both numbers are
unknown. The target is 0 programs that build and differ, over the 10 compare tasks, tccprobe1's 50 programs, and the
first 100 sorted `lab/corpus/programs/*/*.py`. The identical count is reported as measured.

**Owner decision 2026-11-05:** opt-in only. With no `--cc` and no `AIL_DEVCC`, not one byte of any build changes.

## Price (speed-claims rule; write it in `lab/devcc/RESULTS.md` before any edit)

- Share: gcc is 26.0% of pooled cold wall (`lab/profile/CTIME_2026-11.md`), so the Amdahl bound is 1.35x.
- Measured before (`docs/design/TCC_DEV.md`, tcc mob `e23dabe`): the sum of the medians fell from 24.48 s to 19.56 s,
  1.25x. Halved: 1.12x on dev builds. Release builds are untouched, and run time under tcc is 1.7-8.2x slower, which
  is acceptable for an edit loop only.

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/python/pkg-v12/devcc.py`: the refusal scan and the version check only
- `lab/devcc/gate.py` (new: runs the gate and writes the table), `lab/devcc/RESULTS.md` (append)
- `AIL_CURRENT/test_ail_devcc.py` (extend: a real-tcc case that skips when `tcc` is not on `PATH`)
- the manifest files that `tools/update_manifest.py` writes

## Sub-steps

1. **Real tcc (15 min).** Install the Ubuntu `tcc` (0.9.27) and build tcc mob `e23dabe` in `~/scratch/tinycc`,
   outside the repository, as `TCC_DEV.md` section 1 did. Record both `tcc -v`. Run `--cc=tcc` on 3 tasks with each.
   Commit the price paragraph, push, and open the PR against `integ`.
2. **The gate (25 min).** `lab/devcc/gate.py` runs each of the 160 programs with `--cc=tcc`, for each tcc version, and
   with gcc `-O2`. It compares stdout, stderr and exit status, and counts identical, refused (with the message) and
   differing programs. It also times the C step (median of 3). A tcc version that devcc2's scan does not cover fails
   on a construct tccprobe1 found: unsized struct-array compound literals, unsized array declarations, or
   `__int128`. For it, add that construct to the refusal scan, or refuse that tcc version by its `tcc -v` with a
   named message (`--cc=tcc: tcc 0.9.27 cannot build this generated C; use tcc 0.9.28 or later, or build without
   --cc`). Choose the version refusal if more than half of the programs would be refused anyway. Commit and push.
3. **Verify and report (20 min).** Run the no-flag check over devcc2's 120 inputs: 0 C or executable hash
   differences. Append to `RESULTS.md`: the gate table for each version, the compile ratio against gcc `-O2`, the
   halved whole-build projection against the price above, and the stance chosen in sub-step 2. Extend the test.
   Commit, push, and wait for CI.

## Done-check

- 0 programs that build with `--cc=tcc` and differ from gcc, for each tcc version.
- 0 hash differences without the flag.
- `python3 AIL_CURRENT/test_ail_devcc.py` passes, and so do the 20 shards; the diff shows only the listed files.

## Stop rule

Wrong output that the scan cannot refuse is a stop condition. Record the program and the construct first, and
remember that the cause may be undefined behaviour that gcc hides. Stop when 60 minutes pass, and push what is done
first.

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
   `pyc.py`, `buildcache.py`, `pyboxed2.py`, `cruntime.py`, or `packaging/ail_lang/cli.py`. Other lanes own them. Do
   not edit `DEVLOG.md` either: put your notes in the files this task names. Edit only the files this task names, plus
   the manifest files that `tools/update_manifest.py` writes.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`. `DIR/program.c` is
  the generated C. `-o` must not exist yet.
- Compile-time numbers: `lab/profile/run.py` (cold builds, `--fe-profile`, `--no-profile`, `--runs N`);
  `lab/profile/CTIME_2026-11.md` (phase shares), `CTIME_FE.md` (ctimes1, function and module rows),
  `CTIME_CUT.md` (ctimes2, the price of the pyfunc predicates). Instruction counts come from `tools/icount.c`. Timing on
  this laptop is noisy, so icount judges and wall time is reported as a median of 3 on the GitHub runner.
- Byte identity: build with `--debug-dir`, `PYTHONHASHSEED=0`, `AIL_NO_CACHE=1`, `AIL_SERVER=0` and a fresh `AIL_CACHE`;
  compare `sha256(program.c)`, `sha256(executable)` and the refusal text of refused programs.
- Speed-claims rule: before any edit, write the phase share, the Amdahl bound and the projection, then halve the
  projection, because this repo's estimates overshot 2-3x (2.5x estimated, 0.88x measured). A step whose halved
  projection is under 1.03x is not built.

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
