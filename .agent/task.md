Lane: toml

# toml1: `import tomllib` as a bundled AIL package (`AIL_CURRENT/stdlib/tomllib/`), so CLI tools can read TOML config

Time budget: 80 minutes. Commit and push after each sub-step.

**Number this moves:** programs in `lab/stdlib/tomllib/` that build in the default mode and print what CPython prints,
with the same exit status. On `integ` today it is 0/12. A probe on 2026-11-04 copied CPython 3.12's `tomllib`
package next to a program and built it; the first refusal was
`not in the subset: a required keyword-only parameter recursive in def set (this cut requires every keyword-only
parameter to have a default)`, followed by notes about `None` stored in a container and a tuple element type. The
target is at least 8/12. Reading a config file is what the roadmap's P4 niche (small CLI and data tools) needs most
after argument parsing (`getopt1`).

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/stdlib/tomllib/__init__.py`, `_parser.py`, `_re.py`, `_types.py` (new)
- `lab/stdlib/tomllib/*.py` (12 programs) and `lab/stdlib/tomllib/RESULTS.md` (new)
- `AIL_CURRENT/test_ail_std_tomllib.py` (new) and `AIL_CURRENT/tests.d/test_ail_std_tomllib.txt` (new, one line:
  `test_ail_std_tomllib`)
- the manifest files that `tools/update_manifest.py` writes

## Sub-steps

1. **Programs and baseline (15 min).** Write 12 programs in `lab/stdlib/tomllib/`, each 15-40 lines of ordinary
   Python 3.12. Each passes a TOML string written in the program to `tomllib.loads` (no files needed), then prints the
   result with `print()` and selected fields. Together they cover: key/value pairs with every scalar type (basic and
   literal strings, multi-line strings with escapes and line-ending backslashes, ints in decimal, hex `0x`, octal
   `0o`, binary `0b` and with `_`, floats with exponent, `inf`, `nan`, booleans); tables, dotted keys, inline tables,
   arrays of tables `[[x]]`, nested arrays; offset date-times, local date-times, dates and times (they print as
   `datetime` objects); `parse_float=decimal.Decimal` only if `decimal` builds (else use `parse_float=float` and say
   so); a CLI config loader that merges defaults with the parsed table; `tomllib.load` from `io.BytesIO`; errors caught
   as `except tomllib.TOMLDecodeError as e:` and printed with `str(e)` (a duplicate key, an unclosed string, an invalid
   value); and an int beyond int64 (`x = 99999999999999999999`): print what CPython prints, or let the program stop
   loudly. Build each with the default command; record typed, general or refused, with the first refusal line, in
   `RESULTS.md` under "Before (integ <short sha>)". Commit, push, and open the PR against `integ`.
2. **The package (30 min).** Copy CPython 3.12's `Lib/tomllib/` files (find them with
   `python3 -c "import tomllib, os; print(os.path.dirname(tomllib.__file__))"`) into `AIL_CURRENT/stdlib/tomllib/`.
   Then make them build, one refusal at a time, rewriting only what the compiler refuses and keeping the behaviour:
   for example give each required keyword-only parameter (`recursive` in `Flags.set`, and others) a default and pass
   it at every call; replace `None` stored in a container by a sentinel object; annotate tuple elements. Keep a list
   of every rewrite, with the refusal text it answers, in the docstring of `__init__.py`. Every error message must
   stay CPython's (the `TOMLDecodeError` texts include the line and column). Commit and push after each 3 rewrites.
3. **Make the programs pass (20 min).** Build all 12 again in the default build and with `AIL_UNIFIED_FORCE=1`. Fix the
   package, never the programs, until at least 8 build and match. A refusal that needs a compiler file goes into
   `RESULTS.md` as a follow-up with the exact refusal text, ranked by how many programs it blocks. Record the build
   time of one program (median of 3, `AIL_NO_CACHE=1`) against a hello-world build. Commit and push.
4. **Test (15 min).** Write `AIL_CURRENT/test_ail_std_tomllib.py`, copying the structure of
   `AIL_CURRENT/test_ail_std_shlex.py`: it builds every passing program and compares stdout and the exit status with
   `python3`, in both builds, and skips when there is no C compiler. Register it (Appendix A rule 6) and run
   `python3 tools/par_check.py -j 2 test_ail_std_tomllib`. Fill `RESULTS.md` under "After". Commit, push, and wait for
   CI.

## Done-check

- `python3 AIL_CURRENT/test_ail_std_tomllib.py` passes.
- At least 8 of the 12 programs build and match CPython in both builds.
- `RESULTS.md` has the before/after table, the build-time row, and the ranked follow-ups.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop and report if a bundled package directory is not picked up by `import tomllib`; give the exact message. Also
stop if fewer than 5 programs can pass without editing a compiler file: push the package as far as it builds and
the ranked list of blocking refusals (that list is the deliverable then). Stop when 80 minutes pass. Push what is
done first.

## Appendix A: standing rules (Follow C:\Users\bluec\ail-work\agent-brief-rules.md)

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
   `pyc.py`, `buildcache.py`, `pyboxed2.py`, `cruntime.py`, or `packaging/ail_lang/cli.py`. Other lanes own them. Do not
   edit `DEVLOG.md` either: put your notes in the files this task names. Edit only the files this task names, plus the
   manifest files that `tools/update_manifest.py` writes.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`. `DIR/program.c` is
  the generated C. `--strict` means the typed path or a refusal. `-o` must not exist yet. A fallback to the general
  path prints `note: ... built on the general path ...` on stderr.
- AIL is Python syntax plus optional annotations. Ints are int64, and overflow stops loudly.
- Modules in `AIL_CURRENT/stdlib/` are standard modules shipped as AIL source; a package is a directory with an
  `__init__.py`. `AIL_CURRENT/ail_modules.py` (`BUNDLED_DIR`, line ~85) searches them after the program's own directory
  and `AIL_PATH`. Examples: `AIL_CURRENT/stdlib/shlex.py` and its test `AIL_CURRENT/test_ail_std_shlex.py`.
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
