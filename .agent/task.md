Lane: shfixpt

# shfixpt1: self-hosting prep, a design for the byte-identical fixpoint check, with a determinism probe of today's C

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** the share of programs whose generated C is byte-identical across repeated builds. The
self-hosting check is a fixpoint: stage 1 (the AIL-written compiler run by CPython) and stage 2 (that compiler built
by AIL) must emit byte-identical C for the same input, and so must stage 2 on its own source. That check is useless if
today's compiler already emits different C for the same program from run to run (hash seeds, set order, temporary
paths, timestamps). Today nobody has measured it. The target is the measured share over 30 programs, and a design
doc. No compiler file is edited.

Base: `origin/integ`. Files you may create or edit, and no others (all new):
- `tools/c_determinism.py`
- `lab/selfhost/DETERMINISM.md`
- `docs/design/SELFHOST_FIXPOINT.md`
- `AIL_CURRENT/test_ail_c_determinism.py` and `AIL_CURRENT/tests.d/test_ail_c_determinism.txt` (one line:
  `test_ail_c_determinism`)
- the manifest files that `tools/update_manifest.py` writes

## Sub-steps

1. **The probe (20 min).** Write `tools/c_determinism.py`. For each of 30 programs (10 from `lab/stdlib/`, 10 from
   `examples/`, 10 compare-lab sources, both typed and general builds), build 3 times with `--debug-dir` and
   `AIL_NO_CACHE=1`, varying `PYTHONHASHSEED` (0, 1, random), the output directory, and the working directory.
   Compare the `program.c` files byte for byte. For a difference, record the first differing line in each and a
   class: hash order, absolute path, temporary name, time, counter, other. Use `ulimit -v 1500000`, at most 2 builds
   at a time. Commit, push, and open the PR against `integ`.
2. **The numbers (10 min).** Run it. Write `lab/selfhost/DETERMINISM.md`: identical count out of 30 (and out of 60
   builds pairs), each class with its count and one example diff of 3 lines or less, and the file that likely emits
   it (found with `grep`, not fixed). Commit and push.
3. **The design (20 min).** Write `docs/design/SELFHOST_FIXPOINT.md`, under 250 lines:
   - stages 0-2 and what is compared at each step (generated C bytes, not binaries);
   - the seed: which C is committed, how it is regenerated, and how CI proves the committed seed equals what stage 2
     emits;
   - the determinism rules the compiler must keep, each linked to a class found in step 2;
   - a first fixpoint on one small module (pick a leaf module with no refusals if `lab/selfhost/CENSUS.md` names
     one), the commands, and the expected cost in CI minutes;
   - what the check does when a diff appears (fail with the first differing line, never update the seed silently);
   - open questions for the owner, as a short list.
4. **Test (10 min).** Write `AIL_CURRENT/test_ail_c_determinism.py`: it builds 3 small programs twice each with
   different `PYTHONHASHSEED` values and asserts identical `program.c` only for the programs that `DETERMINISM.md`
   lists as identical (a ratchet); it skips without a C compiler. Register it (Appendix A rule 6). Commit, push, and
   wait for CI.

## Done-check

- `DETERMINISM.md` gives the identical count out of 30 and every difference class.
- `docs/design/SELFHOST_FIXPOINT.md` exists and covers the six points above.
- `python3 AIL_CURRENT/test_ail_c_determinism.py` passes; the 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Do not fix any nondeterminism: record it. Stop and report if two builds of the same program give different stdout
when run (that is a wrong-output bug: commit the repro in `DETERMINISM.md` first). Stop when 60 minutes pass. Push what
is done first.

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
8. Never edit `AIL_CURRENT/ail_chatgpt.py`, `AIL_CURRENT/ail_syntax.py`, `packaging/ail_lang/cli.py`, or these files
   in `AIL_CURRENT/python/pkg-v12/`: `pyfunc.py`, `pyc.py`, `cruntime.py`, `pyboxed2.py`, `unified.py`, `optlib.py`,
   `ir/*`, `parallel.py`, `typedpar.py`, `buildcache.py`, `stubcalls.py`. Other lanes own them. Do not edit
   `DEVLOG.md` either: put your notes in the files this task names. Edit only the files this task names, plus the
   manifest files that `tools/update_manifest.py` writes.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`. `DIR/program.c` is
  the generated C. `--strict` means the typed path or a refusal. `-o` must not exist yet. A fallback to the general
  path prints `note: ... built on the general path ...` on stderr.
- AIL is Python syntax plus optional annotations. Ints are int64, and overflow stops loudly.
- Modules in `AIL_CURRENT/stdlib/*.py` are standard modules shipped as AIL source. `AIL_CURRENT/ail_modules.py`
  (`BUNDLED_DIR`, line ~85) searches them after the program's own directory and `AIL_PATH`. Examples:
  `AIL_CURRENT/stdlib/shlex.py` and its test `AIL_CURRENT/test_ail_std_shlex.py`.
- CPython 3.12 is the oracle: compare stdout and the exit status, and stderr where a task says so.

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
