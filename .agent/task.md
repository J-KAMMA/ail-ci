Lane: ffi

# bindgen1: `ail_bindgen.py` on real system headers (zlib.h, math.h), measured and widened

Time budget: 80 minutes. Commit and push after each sub-step.

**Number this moves:** the share of a real library's exported functions for which `ail_bindgen.py`, run on the
library's own installed header, writes an `@extern` stub that the compiler accepts. There are two libraries:
- zlib: `zlib.h`, with the functions listed by `nm -D --defined-only` on `libz.so.1`;
- libm: `math.h`, with its `double` functions.

Neither share is measured today. `ail_bindgen.py` skips preprocessor lines, and zlib.h declares its functions
through macros (`ZEXTERN`, `ZEXPORT`, `OF(...)`, `z_streamp`), so the expected result is few stubs. Target:
**≥ 90 %** for both libraries. Also two example programs in `examples/ffi/bindgen/` that use only generated stubs
and print exactly what CPython prints. This is roadmap P4, C FFI.

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/ail_bindgen.py`
- `examples/ffi/bindgen/` (new directory: `measure.py`, `README.md`, the example programs)
- `AIL_CURRENT/test_ail_bindgen_headers.py` and `AIL_CURRENT/tests.d/test_ail_bindgen_headers.txt` (new)
- the manifest files that `tools/update_manifest.py` writes

Read only: `AIL_CURRENT/ail_ffi.py`, `AIL_CURRENT/ail_ffi_lower.py`, `docs/FFI.md`, `examples/ffi/*.py`,
`AIL_CURRENT/test_ail_ffi_examples.py`. If you find a defect in `ail_ffi*.py`, write it in the README as a finding,
with a reproducer. Do not fix it here.

## Sub-steps

1. **Measure (20 min).** Write `examples/ffi/bindgen/measure.py`. It has two parts.
   - **Find the denominator.** For zlib, it is the exported `T` symbols of `libz.so.1` that also appear in
     `zlib.h`. For libm, it is the `math.h` functions with only `double` parameters and a `double` result (`sin`,
     `pow`, `fma`, ...). List these with a regex over `cc -E` output, and keep only names that `nm -D` shows in
     `libm.so.6`.
   - **Count stubs that are emitted and accepted.** Run `ail_bindgen.py` on the header. Count the stubs it writes,
     then count those the compiler accepts. To learn what "accepted" means, read how the compiler checks a stub
     against the header (grep `header=` in `ail_ffi_lower.py`). If the check runs only for functions that a program
     calls, generate one probe program per stub that calls it once with simple values (`0`, `1.0`, `b""`, a
     `bytearray(64)`). Then count the probes that build. Calls that would crash are fine to build without running.
   Print a table: library, denominator, emitted, accepted, and the top skip reasons with counts. Commit the script
   and its first output in `README.md` under "Before". Commit, push, and open the PR.
2. **Preprocess first (20 min).** Add the option `--cpp` to `ail_bindgen.py`. It runs `$PIPE_CC` (or `cc`) with
   `-E` and `-dD` off, plus the `-I` and `-D` options it was given. From the output it keeps only the lines whose
   `# N "file"` line markers point at the target header, and parses those. Leave the default (no `--cpp`)
   unchanged: its existing tests must pass unchanged. Run `measure.py` again. Commit and push.
3. **Fix the biggest skip reasons (20 min).** Work from the table, the biggest first. Likely reasons:
   - qualifiers (`const`, `restrict`, `__restrict`);
   - attributes (`__attribute__((...))`, `__THROW`, `__nonnull`);
   - typedef'd integer types (`z_size_t`, `uLong`, `uInt`, `Bytef *`, `voidpf`), mapped by resolving the typedef
     in the preprocessed text;
   - `struct` pointers (`z_streamp`), which keep the existing `trust=True` rule.
   Callbacks and variadics stay skipped and listed. Run `measure.py` after each fix. Commit and push.
4. **Examples and test (20 min).** Write two programs in `examples/ffi/bindgen/`.
   - `zlib_gen.py` imports stubs written by `ail_bindgen.py --cpp` from `zlib.h` into `zlib_gen_ffi.py`. Commit
     that generated file, with the command that made it in its first line. The program calls `zlibVersion`,
     `crc32`, `adler32`, `compressBound`, `compress2` and `uncompress`. Print the version only as
     `version.split(".")[0]`, so that it is stable across runners.
   - `libm_gen.py` uses stubs from `math.h` in the same way. It calls 8 functions on values that include `-0.0`,
     `inf`, `nan` and `5e-324`, and prints them with `repr()`.
   Write `AIL_CURRENT/test_ail_bindgen_headers.py`. It runs each example under `python3` and as the compiled
   program, and requires the same stdout and exit status. It also checks that `ail_bindgen.py --cpp` still writes
   at least one stub for each function the examples use. It skips, naming the reason, when there is no `zlib.h`,
   no `libz` or no C compiler. Register the test. Write the "After" table into `README.md`. Commit, push, and wait
   for CI.

## Done-check

- `measure.py` shows ≥ 90 % accepted for zlib and for libm's double functions, or the README says exactly which
  functions are missing and why.
- Both examples match CPython.
- The existing `ail_bindgen` tests pass unchanged: `AIL_CURRENT/test_ail_cargo.py` and
  `AIL_CURRENT/test_ail_cratebridge.py`.
- The 20 shards pass.

## Stop rule

Stop and report if the compiler's header check cannot be run per stub (say how you tried), if `--cpp` breaks an
existing test and you cannot fix it in 15 minutes, or when 80 minutes pass. Push what is done first.

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
