Lane: devcc

# devcc2: an opt-in `--cc=` dev-build C compiler that refuses every program it cannot build identically to gcc

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

Depends on devcc1 merged (its `lab/devcc/RESULTS.md` names the compiler, the refused buckets and whether an executable
is possible), and on ctimes3 merged if the hook below is in `pyc.py` (lane `ctime` edits the front end). Otherwise
stop and report.

**Owner decision 2026-11-05:** opt-in only. Release and default builds stay on gcc `-O2`; with no `--cc` flag and no
`AIL_DEVCC`, not one byte of any build changes. The opt-in output must be byte-identical to the gcc build on the
test corpus, or the mode refuses that program with a named message.

**Number this moves:** C-compile seconds of the opt-in mode against gcc `-O2` on the 10 compare tasks and on
devcc1's corpus, and the count of corpus programs the mode builds identically: target at least devcc1's (b), with 0
programs that build and differ. Price (from devcc1): gcc is 26.0% of pooled cold wall, bound 1.35x; halve devcc1's
measured compile ratio before writing a whole-build projection.

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/python/pkg-v12/devcc.py` (new): maps `--cc=tcc|mir` to the external tool (`tcc` on PATH;
  `AIL_MIR_C2M` or `c2m` on PATH), rewrites the gcc command (drops gcc-only flags), and runs the refusal scan: the
  generated-C constructs of devcc1's failing buckets (for example `__int128`, a `__builtin_*` the tool lacks, an
  attribute) refuse with `--cc=<x>: this program uses <construct> (line N of the generated C), which <x> does not build
  identically to gcc; build without --cc`;
- the one C-compile hook devcc1 names (`pyc._cc` or the command builder next to it): at most 15 lines, calling
  `devcc.py` only when the mode is on;
- `AIL_CURRENT/ail_chatgpt.py`: only the `compile` (and `run`, if it exists) argument parser, adding `--cc` (at most 10
  lines; another lane owns this file, rebase on `origin/integ` just before each push);
- `lab/devcc/RESULTS.md` (append), `AIL_CURRENT/test_ail_devcc.py` (new), `AIL_CURRENT/tests.d/test_ail_devcc.txt`
  (new);
- the manifest files that `tools/update_manifest.py` writes.
Do not vendor MIR or tcc. If devcc1 found that c2m cannot write an executable, `--cc=mir` is allowed only for a
`run`-style command and is refused for `compile -o`, with a message saying so.

## Sub-steps

1. **Mode and refusals (35 min).** Write `devcc.py`, the hook and the flag. With no flag, run the C-hash and
   executable-hash check over the 10 `typed.py`, 10 `main.py` and the first 100 sorted `lab/corpus/programs`
   (`--debug-dir`, `PYTHONHASHSEED=0`, `AIL_NO_CACHE=1`): 0 differences from the base. Commit, push, open the PR.
2. **Corpus gate (25 min).** With `--cc=<x>` on devcc1's 50 programs and the 10 tasks: every program either builds and
   gives stdout, stderr and exit status byte-identical to the gcc build, or is refused by name. Any build that
   differs is a bug in the refusal scan: add its construct to the scan. Record compile seconds (median of 3). Commit
   and push.
3. **Test (20 min).** `test_ail_devcc.py`: skips when the tool is missing; else builds 5 programs with `--cc=<x>` and
   gcc and checks identical outputs, checks one refused program's message, and checks that no flag means gcc `-O2`
   (the command line recorded by `native_diagnostics`, or the executable hash). Register it. Run it,
   `test_ail_build_cache`, `test_ail_cc_split`. Append price and achieved to `RESULTS.md`. Commit, push, wait for CI.

## Done-check

- No flag: 0 hash differences over the 120 inputs.
- With the flag: 0 programs that build and differ from gcc; built-identically count at least devcc1's (b).
- Compile-time ratio against gcc `-O2` reported for the 10 tasks.
- The listed tests and the 20 shards pass.

## Stop rule

Stop on any wrong output: a `--cc` build that prints anything different from the gcc build, or from CPython for a
program that matched before. Record it first; it must become a refusal before anything else is done. Stop if the
default build changes by one byte. Stop when 80 minutes pass. Push what is done first.

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
8. Never edit `AIL_CURRENT/ail_syntax.py`, `AIL_CURRENT/python/pkg-v12/pyfunc.py`, `cruntime.py`, `optlib.py`,
   `ir/passes/*`, `buildcache.py`, `packaging/*` or `pyproject.toml`. In `ail_chatgpt.py` and the hook file, touch
   only what this task names. Do not edit `DEVLOG.md`.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--debug-dir DIR]`. The C compile goes through
  `pyc._cc` (`python/pkg-v12/pyc.py` line ~221) and `buildcache.run_cc`; `buildcache.py` line ~291 picks `$PIPE_CC`.
- Owner decisions on compile time (2026-10-30): gcc `-O2` stays, no `-O1`, LTO rejected. 2026-11-05: a dev compiler
  only as an explicit opt-in.
- Licenses: MIR MIT, tcc LGPL-2.1 (run as an external tool only).

## Owner decision (2026-11-05)

- MIR is used as an external c2m command only. Do not vendor it.
- If c2m cannot write an executable, support --cc=mir only for the run-style command, and refuse it for compile with a named message.

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
