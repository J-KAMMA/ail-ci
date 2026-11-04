Lane: crate

# crate1: three small Rust crates used from Python syntax, the same on CPython and as an AIL binary

Time budget: 80 minutes. Commit and push after each sub-step.

**Number this moves:** example programs in `examples/crate/` that call a Rust crate through
`AIL_CURRENT/ail_cargo.py`. CPython runs them through ctypes on the cdylib, and the AIL binary links the staticlib.
Both must print the same stdout with the same exit status. This number goes from 0 to 3. For each example, also
report the AIL binary's bytes and its wall time against the same program run by `python3` (median of 3). This is
the roadmap's crate-FFI item ("replace Rust": use a crate you already have).

Base: `origin/integ`. Files you may create or edit, and no others:
- `examples/crate/` (new)
- `AIL_CURRENT/test_ail_examples_crate.py` and `AIL_CURRENT/tests.d/test_ail_examples_crate.txt` (new)
- `AIL_CURRENT/ail_cargo.py`, only to fix a defect these examples hit, with a regression case added to
  `AIL_CURRENT/test_ail_cargo.py`
- the manifest files that `tools/update_manifest.py` writes

Do not edit `ail_bindgen.py`, `ail_ffi.py` or `ail_ffi_lower.py`; another lane owns them. Write any defect you find
in them in `examples/crate/README.md`, with a reproducer.

Read first: the docstring of `AIL_CURRENT/ail_cargo.py` (the usage, the `Cargo.toml` requirements and the output
files), `AIL_CURRENT/test_ail_cargo.py` (how it runs cargo offline and passes `--header`), and `docs/FFI.md`.

## Sub-steps

1. **First crate end to end (20 min).** Create `examples/crate/fnvhash/`. It holds:
   - `Cargo.toml`, with `crate-type = ["cdylib", "staticlib"]`, `[profile.release] panic = "abort"` and no
     dependencies;
   - `src/lib.rs`, with `#[no_mangle] pub extern "C" fn fnv1a64(p: *const u8, n: usize) -> u64`;
   - `fnvhash.h`, written by hand, because cbindgen may be missing;
   - `main.py`, which imports `fnvhash_ffi` and prints the hash of 5 byte strings: the empty one, `b"a"`, a 1 MB
     buffer, and two more. Results at or above 2**63 must print as CPython prints them (exact u64).
   Add `examples/crate/.gitignore` with `target/` and `out/`. Build with
   `python3 AIL_CURRENT/ail_cargo.py build examples/crate/fnvhash -o examples/crate/fnvhash/out --header examples/crate/fnvhash/fnvhash.h`.
   Copy `main.py` into `out/`, run it with `python3`, then compile it with `ail_chatgpt.py compile` and run the
   binary. Compare the two runs. Commit, push, and open the PR.
2. **Two more crates (20 min).**
   - `textstat`: `fn stats(p: *const u8, n: usize, out: *mut u64) -> i32` writes the line, word and UTF-8 character
     counts into `out[0..3]`. It returns `-1` on invalid UTF-8, which the stub maps to an exception
     (`--check stats=negative:ValueError`). `main.py` feeds it 4 inputs, one of them invalid UTF-8, and prints the
     counts or the exception text.
   - `rle`: `fn rle_encode(src: *const u8, n: usize, dst: *mut u8, cap: usize) -> isize` returns the length written,
     or `-1` when `cap` is too small. `main.py` encodes 3 inputs and prints a round trip, using a Python decoder in
     the same file. One call uses a buffer that is too small and prints the error.
   Use the stub forms `docs/FFI.md` documents (`bytes`, `bytearray`, `length(...)`, `ptr(c_uint64)`). Commit and
   push.
3. **Test (20 min).** Write `AIL_CURRENT/test_ail_examples_crate.py`. For each crate it runs `ail_cargo.py build`
   into a temporary directory, runs `main.py` under `python3` and as the AIL binary, and requires equal stdout and
   exit status. It skips, naming the missing tool, when `cargo` or a C compiler is missing, as `test_ail_cargo.py`
   does. Cargo must run `--offline`: these crates have no dependencies. Register the test and run it. Commit and
   push.
4. **Numbers (15 min).** Write `examples/crate/README.md`. It explains how to build and run one crate, step by step.
   It has a table with one row per crate: AIL binary bytes, AIL wall time and `python3` wall time (median of 3) on a
   10 MB input made by a small generator in the same directory, plus a note that the same functions can also be
   written in plain Python. Commit, push, and wait for CI.

## Done-check

- 3/3 examples match CPython in the test.
- The README table is filled.
- `git diff --stat origin/integ` lists only the allowed files.
- The 20 shards pass.

## Stop rule

Stop and report if `cargo build --offline` cannot build a crate with no dependencies on the runner; give the error.
Also stop if a stub form the examples need is refused by `ail_bindgen.py`/`ail_ffi`; write the finding with the
exact text and go on with the other crates. Stop when 80 minutes pass. Push what is done first.

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
