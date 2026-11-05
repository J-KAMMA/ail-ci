Lane: stdchunk

# chunk1: `import chunk` in compiled programs, shipped as AIL source (`AIL_CURRENT/stdlib/chunk.py`)

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** programs in `lab/stdlib/chunk/` that build in the default mode and print what CPython prints,
with the same exit status. Today it is 0/10: the stdlib census records `chunk` as refused
(`chunk.py:68:9: a caught exception type Attribute (only builtin or user Exception subclasses are supported)`), and AIL
has no model or bundled file for it. The target is at least 8/10. `chunk` reads IFF/RIFF files (WAV, AIFF), a
typical binary-data CLI job.

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/stdlib/chunk.py` (new)
- `lab/stdlib/chunk/*.py` (10 new programs) and `lab/stdlib/chunk/RESULTS.md` (new)
- `AIL_CURRENT/test_ail_std_chunk.py` (new) and `AIL_CURRENT/tests.d/test_ail_std_chunk.txt` (new, one line:
  `test_ail_std_chunk`)
- the manifest files that `tools/update_manifest.py` writes

Models: `AIL_CURRENT/stdlib/getopt.py` and `AIL_CURRENT/test_ail_std_getopt.py`. CPython 3.12 prints a
`DeprecationWarning` for `import chunk`; compare stdout and the exit status only, and write that in the docstring.

## Sub-steps

1. **Programs and baseline (15 min).** Write 10 programs in `lab/stdlib/chunk/`, each 15-35 lines. Each builds IFF or
   RIFF bytes in the program (no `struct` needed: build the 4-byte sizes with `int.to_bytes`), writes them with
   `open(name, "wb")`, opens the file with `"rb"` and reads it with `chunk.Chunk`. Together they cover:
   - `getname()`, `getsize()`, `read()`, `read(n)`, `skip()`, `tell()`, `seek()` (whence 0, 1, 2), `close()` and
     `isatty()`;
   - big-endian (IFF) and little-endian (`bigendian=False`, RIFF) sizes; `align=True` with an odd size, and
     `align=False`; `inclheader=True`;
   - a loop that walks all chunks of a file until `EOFError`;
   - errors, printed as `type(e).__name__` and `str(e)`: a short header (`EOFError`), `read` after `close`
     (`ValueError: I/O operation on closed file`), and `seek` on a closed chunk;
   - a size field of `0xFFFFFFFF` (fits in int64, so it must print what CPython prints).
   Build each and record typed, general or refused with the first refusal line in `RESULTS.md` under "Before".
   Commit, push, and open the PR against `integ`.
2. **The module (20 min).** Write `AIL_CURRENT/stdlib/chunk.py` from CPython 3.12's `Lib/chunk.py`. Keep the class
   and every method and error text. The `except (AttributeError, OSError)` around `file.tell()` is refused: catch
   `OSError` only, or test `hasattr`, and keep the behaviour for real files (`seekable` true). If `struct.unpack_from`
   is refused, decode the sizes with `int.from_bytes`. Rewrite only what the compiler refuses. Commit and push.
3. **Make the programs pass (10 min).** Fix the module, never the programs, until at least 8 build and match. A
   refusal that needs a compiler file goes into `RESULTS.md` with its exact text. Commit and push.
4. **Test (15 min).** Write `AIL_CURRENT/test_ail_std_chunk.py` like `test_ail_std_getopt.py`: build every passing
   program, run it in a temporary directory, compare stdout and the exit status with `python3`, in the default build
   and with `AIL_UNIFIED_FORCE=1`; skip without a C compiler. Register it (Appendix A rule 6), run it, and fill
   `RESULTS.md` under "After". Commit, push, and wait for CI.

## Done-check

- `python3 AIL_CURRENT/test_ail_std_chunk.py` passes.
- At least 8 of the 10 programs build and match CPython in both builds.
- `RESULTS.md` has the before/after table.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop at once and report if any program builds and prints output different from CPython (silent wrong output): commit
the program and both outputs in `RESULTS.md` first. Also stop if a bundled `chunk.py` is not picked up, or if fewer
than 5 programs can pass without editing a compiler file. Stop when 60 minutes pass. Push what is done first.

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
