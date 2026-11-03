Lane: ffi

**C FFI (roadmap P4): four real-library examples that run the same on CPython and as an AIL binary.** `ail_ffi`
already declares C functions as Python stubs: ctypes runs them on CPython, and `ail build` turns them into direct C
calls. The unit tests cover each feature, but there is no user-facing example of a whole small program against a real
library. This job writes four, proves each one byte-equal to CPython, and fixes any FFI defect the examples hit.

# ffiex1: zlib, libm, libc and sqlite3 examples, checked against CPython

Time budget: 80 minutes. Commit and push after each sub-step.

**Number this moves:** real-library example programs whose `ail` binary prints the same bytes, with the same exit
status, as `python3`: from 0 to 4.

Base: `origin/integ`.

## The four examples (new directory `examples/ffi/`)

1. `zlib_check.py`: `crc32` and `adler32` of three byte strings, then a `compress2` / `uncompress` round trip. Use
   `bytearray` output buffers and a `ptr(c_ulong)` out-length. Print the checksums and `round trip ok`.
2. `libm_math.py`: `cbrt`, `hypot`, `fma`, and `frexp` with a `ptr(c_int)` out-exponent, on 6 values including
   `-0.0`, `inf` and a subnormal. Print with `repr()`.
3. `libc_text.py`: `strlen` (via `c_char_p`), `strtol` with base 16 and 36 on 4 strings, and `toupper` over a
   `bytearray`. Include a value at int64's edge and one beyond it. Beyond int64, `strtol` saturates and sets `ERANGE`:
   use `errno=True` and print the `OSError` text.
4. `sqlite_count.py`: use an owned `Handle("sqlite3", free="sqlite3_close")` on an in-memory database. Create a
   table, insert 1,000 rows in one transaction with `sqlite3_exec`, then read `SELECT count(*), sum(v)` through
   `sqlite3_prepare_v2` / `sqlite3_step` / `sqlite3_column_int64` / `sqlite3_finalize`. Print the two numbers.

Each file runs with `python3 FILE` and builds with `ail_chatgpt.py compile FILE -o OUT`. Read the `ail_ffi.py`
docstring (lines 1-60) for the annotation table before writing them.

## Sub-steps

1. **Examples 1-2 (20 min).** Write them, run both ways, compare the bytes. Write
   `AIL_CURRENT/test_ail_ffi_examples.py`. It builds each example, runs it, and compares with `python3`. It skips an
   example, with a reason, when its header or library is missing (`zlib.h`, `sqlite3.h`). Register it in `tests.d`,
   update the manifest, run `--check`. Commit, push, open the PR.
2. **Examples 3-4 (25 min).** Same procedure. Commit, push.
3. **Defects (20 min).** If an example differs from CPython or is refused although the docstring says it is
   supported, reduce it to a minimal stub. Fix it in `AIL_CURRENT/ail_ffi.py` or `AIL_CURRENT/ail_ffi_lower.py`
   only, and add the case to the new test. If the fix needs another file, do not fix it: keep the example in a form
   that works, and list the defect in the report with the reduced program. Run `test_ail_ffi`,
   `test_ail_ffi_handles` and `test_ail_ffi_f3a`. Commit, push.
4. **Docs (15 min).** Write `docs/FFI.md`: one short section per example (what it shows and the stub lines that
   matter), how to build it, and what is not supported yet (copy the limits from the `ail_ffi.py` docstring; do not
   invent any). Link it from `docs/tutorial.md` section 6 with one line. Commit, push.

## Done-check

- 4/4 examples print identical bytes and exit status on both sides on the runner, or a skip names the missing system
  header.
- The new test, `test_ail_ffi`, `test_ail_ffi_handles` and `test_ail_safetynet` pass.
- All 20 shards pass.

## Stop rule

Stop if any of these happens. Then push what is green and report.

- A fix needs a file other than `ail_ffi.py`, `ail_ffi_lower.py`, the new test, `examples/ffi/` and the docs.
- Installing a system package would be needed. Skip that example and say so.
- Any existing compare-lab `program.c` changes.
- 80 minutes pass.

## Appendix A: standing rules

1. No regressions: a program that built and matched CPython before must still do so in the default build.
2. Probe ints beyond int64 wherever ints come from text or arithmetic; run probes in the default build and with
   `AIL_UNIFIED_FORCE=1`, compare both with `python3`.
3. Push early, open the PR against `integ`, wait for all 20 `shard` checks (`gh pr checks <n> -R J-KAMMA/ail-ci`, at most
   once every 10 minutes). Report only when all pass, or say which fail and why.
4. Branch from `integ` (or one unmerged PR at most).
5. Memory: wrap heavy runs in `ulimit -v 1500000`; `tools/par_check.py -j 2` at most; leave no background jobs.
6. New test module: `AIL_CURRENT/tests.d/<module>.txt` if the directory exists, else `ail_check.py` MODULES; `git add`,
   `tools/update_manifest.py`, then `--check`.
7. Never print credentials, run a broad pkill, merge PRs, change repository settings, cancel runs, or edit
   `.github/workflows`.

## Appendix B: repository facts

- `AIL_CURRENT/ail_ffi.py` (878 lines): `extern`, `length`, the `c_*` types, `ptr`/`cptr`, `Handle`, `errno=True`.
  Its CPython side uses ctypes. `AIL_CURRENT/ail_ffi_lower.py` lowers the stubs to C adapters, which include the
  header and check the prototype.
- Existing tests: `test_ail_ffi.py` (for example `test_libc_libm_and_zlib`, `test_handles`, `test_out_parameters`),
  `test_ail_ffi_handles.py`, `test_ail_ffi_callbacks.py`, `test_ail_ffi_f3a.py`, `test_ail_ffi_f3b.py`. Copy their
  build and run helpers.
- `docs/tutorial.md` section 6, "Calling C (FFI)", has a `<!-- sample: ffi -->` sample, which `test_ail_tutorial.py`
  checks.
- `--no-ffi` refuses all declarations. A `uint64` result above int64 is a loud stop on the legacy emitter (owner
  decision: exact u64 FFI with an argument range check).

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
