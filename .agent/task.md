Lane: shfiles

# shfiles1: self-hosting prep, which compiler source files build as AIL programs today (measurement only)

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** the count of compiler source files that AIL builds whole, as a program, in the default mode.
After 0.1 the owner wants the compiler rewritten in AIL (self-hosting). `lab/selfhost/CENSUS.md` already counts
**functions** accepted by the typed path (21 of 3159). Nobody has counted **files**: which files build at all
(typed or general), and what the first refusal is for the rest. Today the number is unknown. The target is the
number itself, with the top refusal buckets, so the self-hosting plan can pick its first files. No compiler file is
edited.

Base: `origin/integ`. Files you may create or edit, and no others (all new):
- `tools/selfhost_files.py`
- `lab/selfhost/files.json` and `lab/selfhost/FILES.md`
- `AIL_CURRENT/test_ail_selfhost_files.py` and `AIL_CURRENT/tests.d/test_ail_selfhost_files.txt` (one line:
  `test_ail_selfhost_files`)
- the manifest files that `tools/update_manifest.py` writes

Do not edit `lab/selfhost/CENSUS.md`, `census.json`, `hot.json` or `hot_functions.py`.

## Sub-steps

1. **The tool (20 min).** Write `tools/selfhost_files.py`. For each file in the scope of `lab/selfhost/CENSUS.md`
   (`AIL_CURRENT/python/pkg-v12/*.py`, `AIL_CURRENT/ail_chatgpt.py`, `AIL_CURRENT/ail_syntax.py`,
   `AIL_CURRENT/ail_modules.py`; skip `test_*.py`), copy the file and its sibling directory into a temporary
   directory, and run `python3 -B AIL_CURRENT/ail_chatgpt.py compile <file> -o <tmp>/out` with `AIL_NO_CACHE=1`,
   `ulimit -v 1500000`, a 60 s timeout, at most 2 at a time. Record per file: `lines`, `result` (`typed`, `general`,
   `refused`, `timeout`, `crash`), `seconds`, and the first refusal line with names and numbers kept. Copy the
   bucket method of `lab/stdcensus/report.py` (refusal text with names replaced by placeholders). `--limit N` and
   `--only a.py,b.py` options keep runs short. Write `lab/selfhost/files.json` (`schema: ail.selfhost_files/1`, with
   the base commit and the date). Smoke-run on 5 files. Commit, push, and open the PR against `integ`.
2. **The run (20 min).** Run the whole scope. If the first 20 files project to more than 30 minutes, run the
   smallest 100 files by line count plus the 15 largest, and write which files were skipped and why. Do not run a
   built binary: these files are libraries, and building is the measure. Commit and push the JSON.
3. **Report and test (20 min).** Write `lab/selfhost/FILES.md`: the totals (files, built typed, built general,
   refused, timeout, crash), the share of lines in built files, the 10 largest refusal buckets with their counts and
   one example file each, and the 10 smallest refused files with their first refusal (the cheapest next steps). Write
   `AIL_CURRENT/test_ail_selfhost_files.py`: it checks that `files.json` parses, has the schema, that every file it
   names exists, and that the totals in `FILES.md` equal the counts in the JSON. It does not compile anything.
   Register it (Appendix A rule 6). Commit, push, and wait for CI.

## Done-check

- `lab/selfhost/files.json` has one row per file in scope, or a written reason for each skipped file.
- `FILES.md` gives the totals and the 10 buckets, and its numbers equal the JSON.
- `python3 AIL_CURRENT/test_ail_selfhost_files.py` passes; the 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop and report if a compile uses more than 1.5 GB or hangs WSL, if a built file's compile writes outside its
temporary directory, or if the tool cannot tell a refusal from a crash. Stop when 60 minutes pass. Push what is done
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
