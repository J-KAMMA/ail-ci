Lane: ff-embed

# ffembed1: AIL as a C library: `ail_embed.py` builds `lib<name>.a` and `<name>.h` from a Python module

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** example modules in `examples/embed/` that build into a static library whose exported
functions, called from a C test program, return what CPython returns when it calls the same Python functions.
Today 0: AIL builds only executables. Target 4/4. This is the "replace Rust" story in reverse: a C or Rust program
uses fast Python-syntax code without a CPython runtime.

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/ail_embed.py` (new): runs `ail_chatgpt.py compile SRC --debug-dir DIR`, reads `DIR/program.c`,
  renames `main` (`-Dmain=ail_embed_unused_main` or an equivalent), and writes a wrapper C file that exports the
  functions named in the module's `__ail_export__ = ["f", "g"]` list (plain Python, so CPython runs the same file)
- `examples/embed/*/` (4 new: `mod.py`, `test.c`, `expected.txt`), `examples/embed/README.md`
- `AIL_CURRENT/test_ail_embed.py`, `tests.d` entry

ABI (version 1, written in the README): `int <name>_init(void)`, `void <name>_shutdown(void)`; each export takes and
returns `int64_t`, `double`, `bool`, or `const char *` plus `size_t` length for `str`/`bytes` arguments; a `str`
result is written into a caller buffer (`char *out, size_t cap, size_t *len`). Every export returns `int` status
(0 ok, 1 Python exception, 2 buffer too small) and the value through an out pointer; `<name>_last_error()` gives
`"<ExcName>: <message>"`. An int64 overflow inside an export is status 1 with `OverflowError`, never a wrapped value.
Only typed-path functions can be exported: a function on the general path is refused by name.

## Sub-steps

1. **Probe the C (15 min).** Find how typed functions are named and called in `program.c`, and how runtime init and
   exit run. Write the facts in the README. Commit, push, open the PR.
2. **Tool and first example (25 min).** `ail_embed.py build mod.py -o OUT` writes `lib<name>.a`, `<name>.h`. Example
   1: `fib(n)`, `gcd(a, b)`, a sum of a parsed text line. Probe `fib(93)` (overflow: status 1).
3. **Three more and test (20 min).** A string transform, a word count over a buffer, a raising function. The test
   compiles each `test.c` with gcc -O2, links the library, and compares with `expected.txt` that CPython produced.

## Done-check

- 4/4 examples match CPython's results through the C ABI; status codes and `last_error` text as specified.
- The test passes; the 20 shards pass; only the files above changed.

## Stop rule

Stop on any wrong value through the ABI. Stop if exporting needs an edit to `ail_chatgpt.py` or `pyfunc.py`: write
the exact hook needed. Stop when 60 minutes pass. Push first.

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
