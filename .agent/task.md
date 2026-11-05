Lane: stdnturl

# nturl2path1: `import nturl2path` in compiled programs, shipped as AIL source (`AIL_CURRENT/stdlib/nturl2path.py`)

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** programs in `lab/stdlib/nturl2path/` that build in the default mode and print what CPython
prints, with the same exit status. Today it is 0/10: the stdlib census records `nturl2path` as refused
(`import urllib at the top of the file, not inside a function or block`), and AIL has no model or bundled file for it.
The target is at least 9/10. The module is two pure string functions, so it is a cheap win.

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/stdlib/nturl2path.py` (new)
- `lab/stdlib/nturl2path/*.py` (10 new programs) and `lab/stdlib/nturl2path/RESULTS.md` (new)
- `AIL_CURRENT/test_ail_std_nturl2path.py` (new) and `AIL_CURRENT/tests.d/test_ail_std_nturl2path.txt` (new, one
  line: `test_ail_std_nturl2path`)
- the manifest files that `tools/update_manifest.py` writes

Models: `AIL_CURRENT/stdlib/getopt.py` and `AIL_CURRENT/test_ail_std_getopt.py`.

## Sub-steps

1. **Programs and baseline (15 min).** Write 10 programs in `lab/stdlib/nturl2path/`, each 10-25 lines, each printing
   `repr()` of several results. Together they cover:
   - `url2pathname`: `"///C|/foo/bar/spam.foo"`, `"///C:/foo/bar"`, `"//host/share/x.txt"`, `"/foo/bar"`,
     `"C|/x"`, percent escapes such as `%20` and `%C3%A9`, and an empty string;
   - `pathname2url`: `"C:\\foo\\bar\\spam.foo"`, `"C:"`, `"\\\\host\\share\\x"`, a relative path, a path with spaces
     and non-ASCII letters;
   - each `OSError` that CPython raises (`Bad URL: ...`, `Bad path: ...`), caught and printed as `str(e)`;
   - a round trip `url2pathname(pathname2url(p)) == p` over a list of 8 paths.
   Build each and record typed, general or refused with the first refusal line in `RESULTS.md` under "Before".
   Commit, push, and open the PR against `integ`.
2. **The module (15 min).** Write `AIL_CURRENT/stdlib/nturl2path.py` from CPython 3.12's `Lib/nturl2path.py`. The
   function-level `import urllib.parse` is refused: move it to the top of the file, and keep the behaviour. If
   `urllib.parse.quote`/`unquote` are refused on the general path, add annotations so the functions stay typed
   (`url: str`, `-> str`). Every error text must be exactly CPython's. Commit and push.
3. **Make the programs pass (15 min).** Fix the module, never the programs, until at least 9 build and match. A
   refusal that needs a compiler file goes into `RESULTS.md` with its exact text. Commit and push.
4. **Test (15 min).** Write `AIL_CURRENT/test_ail_std_nturl2path.py` like `test_ail_std_getopt.py`: build every
   passing program, compare stdout and the exit status with `python3`, in the default build and with
   `AIL_UNIFIED_FORCE=1`; skip without a C compiler. Register it (Appendix A rule 6), run it, and fill `RESULTS.md`
   under "After". Commit, push, and wait for CI.

## Done-check

- `python3 AIL_CURRENT/test_ail_std_nturl2path.py` passes.
- At least 9 of the 10 programs build and match CPython in both builds.
- `RESULTS.md` has the before/after table.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop at once and report if any program builds and prints output different from CPython (silent wrong output): commit
the program and both outputs in `RESULTS.md` first. Also stop if a bundled `nturl2path.py` is not picked up, or if
fewer than 5 programs can pass without editing a compiler file. Stop when 60 minutes pass. Push what is done first.

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
