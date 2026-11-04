Lane: fnmatch

# fnmatch2: `import fnmatch` as a bundled AIL module, reusing the unmerged std_fnmatch work

Time budget: 80 minutes. Commit and push after each sub-step.

**Number this moves:** programs in `lab/stdlib/fnmatch/` that build in the default mode and print what CPython prints,
with the same exit status. On `integ` today it is 0/12: `import fnmatch` is refused with
`not in the subset: fnmatch.fnmatch (not yet published in NAMES_library.json)`. The target is at least 10/12.

**Background.** The 2026-11-01 run on branch `job-std_fnmatch-11011617` wrote 12 programs and a working
implementation, `AIL_CURRENT/python/pkg-v12/prelude_fnmatch.py`. It wired that file in through `ail_syntax.py`,
`stdlib5.py` and `stdtop.py`, and it was never merged. Those files belong to other lanes, and `ail_syntax.py` must
not be edited. This job ships the same code as a bundled module, `AIL_CURRENT/stdlib/fnmatch.py`, which
`import fnmatch` finds without any compiler change (Appendix B).

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/stdlib/fnmatch.py` (new)
- `lab/stdlib/fnmatch/*` (taken from the branch, then edited)
- `AIL_CURRENT/test_ail_std_fnmatch.py` and `AIL_CURRENT/tests.d/test_ail_std_fnmatch.txt` (new)
- the manifest files that `tools/update_manifest.py` writes

Do not edit `stdlib5.py`, `stdtop.py`, `ail_syntax.py` or any other compiler file.

## Sub-steps

1. **Take the old work (10 min).**
   ```
   git fetch origin job-std_fnmatch-11011617
   B=origin/job-std_fnmatch-11011617
   git checkout $B -- lab/stdlib/fnmatch
   git show $B:AIL_CURRENT/python/pkg-v12/prelude_fnmatch.py > /tmp/prelude_fnmatch.py
   git show $B:AIL_CURRENT/test_ail_std_fnmatch.py > AIL_CURRENT/test_ail_std_fnmatch.py
   git diff $(git merge-base origin/integ $B) $B -- AIL_CURRENT/python/pkg-v12/stdtop.py
   ```
   The `stdtop.py` diff shows how the program's `fnmatch.X` names were mapped to the prelude's `_ail_fnm_*`
   functions. Write that mapping down. Build the 12 programs on `integ` and record the "Before" column in
   `lab/stdlib/fnmatch/RESULTS.md` (expected: all refused). Commit, push, and open the PR against `integ`.
2. **The module (20 min).** Create `AIL_CURRENT/stdlib/fnmatch.py` from `/tmp/prelude_fnmatch.py`. It must offer
   CPython's public names, `fnmatch(name, pat)`, `fnmatchcase(name, pat)`, `filter(names, pat)` and
   `translate(pat)`, each calling the `_ail_fnm_*` code that already works. On POSIX, `fnmatch` applies
   `os.path.normcase`, which leaves names unchanged: do the same and say so in the docstring. If the module's own
   `import re` or `import os` is refused, keep the prelude's own matcher. It does not need `re`; check this in the
   file's header comment. CPython must still run each program unchanged, with the real `fnmatch`. Commit and push.
3. **Make the programs pass (25 min).** Build all 12 again in the default mode. Fix the module, never the programs.
   `bytes_names.py` uses bytes patterns. If bytes cannot pass without a compiler change, record the exact refusal
   as a follow-up. Probe these patterns: `""`, `"*"`, `"[!]"`, `"[a-"`, `"[]]"`, `"**/*.py"`, and a 10,000-character
   name against `"*a*a*a*b"`. The last one checks that matching is not exponential: it must finish in under one
   second. Commit and push.
4. **Test and results (15 min).** Adapt `AIL_CURRENT/test_ail_std_fnmatch.py` to the bundled module. It compares
   every passing program with `python3`, in the default build and with `AIL_UNIFIED_FORCE=1`, and skips when there is
   no C compiler. Register the test (Appendix A rule 6). Fill the "After" column of `RESULTS.md`. Commit, push, and
   wait for CI.

## Done-check

- At least 10/12 programs match CPython in both builds.
- The new test passes.
- `git diff --stat origin/integ` lists only the files above; no `python/pkg-v12/` file changed.
- The 20 shards pass.

## Stop rule

Stop and report if the bundled module is not found by `import fnmatch`; give the exact message. Also stop if fewer
than 6 programs can pass without a compiler edit; name each blocking refusal. Stop when 80 minutes pass. Push what
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
8. Never edit `AIL_CURRENT/ail_chatgpt.py`, `AIL_CURRENT/ail_syntax.py`, `AIL_CURRENT/python/pkg-v12/pyfunc.py`,
   `pyc.py`, `buildcache.py`, `pyboxed2.py`, or `packaging/ail_lang/cli.py`. Other lanes own them. Do not edit
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
