**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode/deepseek-v4.1-flash-free]
## Review: ff-icefuzz change (`work..4054bb3`)

**What the diff really does:** It redefines a silent difference as *AIL exits 0 and stdout differs, regardless of CPython's exit status*, writes a reproducer for silent findings, runs minimisation even after a silent stop, and regenerates `RESULTS.md` from a run that stops at seed 699. Only `lab/icefuzz/*` is touched; no compiler/runtime change.

**Probes run (all under /tmp/rprobes or /tmp):**
- `crashes/crash-01-traceback-name_ref.py`: HEAD compile exits 1, `KeyError: 'ops'`; base identical. CPython exits 1 with `NameError`.
- `crashes/silent-01-seed699.py` (`stdin=/dev/null`): CPython rc 1, empty stdout; AIL rc 0, prints `bytes 0` + sha. Identical on base.
- Deleted reproducer content (`global name; NotImplemented='local'; print(NotImplemented)`): CPython rc 0 `local`; AIL rc 0 `NotImplemented`; identical on HEAD and base.
- `_run_cpython('1/0')` and `_run_cpython('raise SystemExit(1)')` both return `True` (should be discarded).
- Full documented command rerun: 703 classified (374 matching, 31 different, 273 refused, 25 internal), stopped at seed 699, elapsed 509 s; regenerated crash files byte-identical to HEAD.
- Seeds 699/385/0/1744 generate identically twice (mutator determinism holds).
- `tools/update_manifest.py --check` rc 0. `test_ail_safetynet`: 1 module, 0 failed.

**Report claims:** silent definition, silent-reproducer writing, minimisation-after-stop, crash-01 KeyError, manifest, safetynet and "not pushed" are verified. The 701 vs 372/31/273/25 counts are only approximately reproducible (rerun 703/374 due to the stop racing in-flight seeds). "seed 385 recorded as a real exit-status difference" is mechanically true but CPython fails with `NameError`, so it is not a valid oracle comparison. "plain/a unchanged" is unverified (no such probes exist).

**Pre-existing (same on `/tmp/base`, not caused by this change):** AIL's acceptance of `read('65536')`, the `NotImplemented`-global silent difference, and the `name_ref` compiler traceback.

### Defects

1. **The mutator accepts CPython-failing mutants, contrary to "run in CPython … else discard".**
   Probe: `python3 -c "import sys;sys.path.insert(0,'lab/icefuzz');import mutate;print(mutate._run_cpython('1/0'))"`
   Expected: `False` (discard); actual: `True`. Consequence: the filed crash reproducer and seed 699 both exit 1 in CPython, so the lab's findings are on programs CPython rejects, not "odd but valid" programs.

2. **The new silent rule stops the run on a CPython error.** `silent = (not loud and ail[1] != cpy[1])` dropped the old `cpy[0] == 0` condition. Probe: `silent-01-seed699.py` → expected not a silent wrong-output comparison (CPython rc 1, TypeError); actual `silent:true`, run stops at seed 699 after only 701 (rerun 703) mutants. The done-check "2000 mutants classified" is not met, and the change itself caused this (old code required CPython rc 0).

3. **The genuine silent difference found earlier was deleted.** Seed 1744 (both rc 0; CPython `keyword if True`, AIL `missing NotImplemented`) had `crashes/silent-01-notimplemented-global.py`, which 4054bb3 removes; the final `RESULTS.md`/`crashes/` no longer file it. Probe: the deleted 5‑line program above; expected it remains filed as the first silent difference; actual: file absent, only the CPython-error case is filed.

**Unverified:** exact elapsed/counts of the worker's run (environment-dependent), and `test_ail_files`/`test_ail_corpus_findings3` (outside this review's required set).

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 1025203, "input": 77739, "output": 5044, "reasoning": 30164, "cache.write": 0, "cache.read": 912256}]
    tool time: bash 11.8 min, read 0.0 min
        510s bash   cd /home/runner/work/ail-ci/ail-ci date rm -rf /tmp/rfull /tmp/rcfull timeout 900 python3 lab/icefuzz/run.py -
        164s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 500 python3 ../tools/par_check.py -j 2 test_ail_safe
          9s bash   cd /home/runner/work/ail-ci/ail-ci rm -rf /tmp/r16 /tmp/rc16 timeout 400 python3 lab/icefuzz/run.py --seed 14 
          8s bash   cd /tmp/rprobes # Probe B: silent reproducer for wt in /home/runner/work/ail-ci/ail-ci /tmp/base; do   d=$(mkt
          4s bash   cd /home/runner/work/ail-ci/ail-ci rm -rf /tmp/r699 /tmp/rc699 timeout 300 python3 lab/icefuzz/run.py --seed 6
          3s bash   cd /home/runner/work/ail-ci/ail-ci for s in 30 63 65 89 112; do   rm -rf /tmp/rr$s /tmp/rrc$s   timeout 120 py
          3s bash   cd /home/runner/work/ail-ci/ail-ci for s in 385 1744; do   echo "=== seed $s ==="   python3 lab/icefuzz/mutate
          1s bash   cd /home/runner/work/ail-ci/ail-ci for s in 699 385 0 1744; do   a=$(python3 lab/icefuzz/mutate.py --seed $s 2


--- ORIGINAL TASK ---
Lane: ff-icefuzz

# ffice1: compiler crash fuzzing: mutated Python programs must build or be refused by name, never a traceback

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** internal compiler errors (a Python traceback from the compiler, an exit code other than 0, 2
or 3, a C compiler error on generated C, or a timeout above 60 s) per 2000 mutants. The existing fuzz labs
(`lab/fuzz`, `lab/fuzzpy`) generate well-formed programs to find output differences; nothing feeds the compiler odd
but valid programs. Today unknown. The target is the count, each distinct crash minimised and filed, and a daily
command ready for the owner to schedule.

Base: `origin/integ`. Files you may create or edit, and no others:
- `lab/icefuzz/mutate.py` (new): seeded AST mutations of corpus programs (`lab/stdlib/*/*.py`, `lab/compare/src/*.py`,
  `lab/limits/*.py`): swap operands, change literal kinds (int to str, big ints, `-0.0`, `float("nan")`), wrap in
  `try`, add a `global`, rename shadowing a builtin, nest a comprehension, insert `del`, `lambda`, `*args`, walrus,
  `match`, decorators; every mutant must parse with `ast.parse` and run in CPython 3.12 within 5 s (else discard)
- `lab/icefuzz/run.py` (new): builds each mutant under `ulimit -v 1500000` with a 60 s limit, classifies, and
  minimises each crash by deleting statements while the same crash stays (delta debugging)
- `lab/icefuzz/RESULTS.md` (new), `lab/icefuzz/crashes/*.py` (minimised reproducers)

Find and file only: no compiler change in this job. Any mutant that builds and prints output different from CPython
is a silent difference: it goes first in `RESULTS.md`, marked as such.

## Sub-steps

1. **Mutator (20 min).** With a `--seed`; the same seed gives the same mutants. Commit, push, open the PR.
2. **Runs (25 min).** 2000 mutants with `-j 2`. Classify: built and matching, built and different, refused by name,
   internal error. Group internal errors by the last traceback frame.
3. **Minimise and file (15 min).** One reproducer per group, at most 15 lines where possible, with the command and
   the traceback head.

## Done-check

- 2000 mutants classified; the count per class is in `RESULTS.md`; every crash group has a minimised reproducer that
  still crashes on `origin/integ`.

## Stop rule

Stop the run and report at once if a mutant gives silent wrong output. Stop when 60 minutes pass. Push first.

## Appendix A: standing rules (from agent-brief-rules.md)

1. No regressions: a program that built and matched CPython before must still do so in the default build. A loud
   stop is allowed only where the value cannot be computed. Never silent wrong output: stop and report the moment
   any program prints something CPython does not.
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
   `pyc.py`, `buildcache.py`, `pyboxed2.py`, or `packaging/ail_lang/cli.py`, unless this task names the file and
   the one minimal hook it may add there (owner decision 3 of 2026-11-06: only when no other running job edits that
   file). Do not edit `DEVLOG.md` either: put your notes in the files this task names. Edit only the files this task
   names, plus the manifest files that `tools/update_manifest.py` writes.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`. `DIR/program.c` is
  the generated C. `--strict` means the typed path or a refusal. `-o` must not exist yet. A fallback to the general
  path prints `note: ... built on the general path ...` on stderr.
- AIL is Python syntax plus optional annotations. Ints are int64, and overflow stops loudly. Release builds use
  gcc -O2.
- Library policy: a small spec library is written in AIL (`AIL_CURRENT/stdlib/*.py`, found by `ail_modules.py`
  `BUNDLED_DIR`); TLS, signatures and SQLite go through proven native libraries.
- Runtime-backed modules follow `AIL_CURRENT/python/pkg-v12/proclib.py` (stage G8, subprocess): a tree-to-tree pass
  plus a C core header (`ailproc_core.h`), wired by two lines in `filelib.py` (`PRIMS.update(...)` near line 66 and
  `rewrite_tree(...)` near line 152). A program that does not import the module must produce byte-identical C.
- CPython 3.12 is the oracle: compare stdout and the exit status, and stderr where a task says so.
- Speed claims: instruction counts with `tools/icount.c`, output unchanged.

## Owner decision (2026-11-06)

- Workflow (.github/workflows) changes: write the exact steps into a doc; the maintainer opens the PR and the owner approves it.

**Rules for every job.**
- **Load:** you are one of up to five agents on a 16 GB PC. Keep local parallelism at 2 (`-j 2`) and never run the whole suite; the full suite runs on CI after merge.
- **Commits:** commit with explicit `git add` on your branch. Messages end with a `Co-Authored-By:` line naming the model you actually are (Claude: `Claude Opus 5.5 <noreply@anthropic.com>` or `Claude Sonnet 5.5 <noreply@anthropic.com>`; other models: omit the line).
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
