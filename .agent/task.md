**FFI step F6: build a Rust crate for AIL in one step.** Implement exactly this step of the modules/FFI plan (new files only):

**F6. Rust crates in one step** (public, new files only: `ail_cargo.py`, `test_ail_cargo.py`; optional `ail.toml`
key in `packaging/` as a follow-up). `ail_cargo.py build CRATE_DIR -o OUT` runs
`cargo build --release --offline --lib` with `crate-type = ["cdylib","staticlib"]` and `panic=abort` checked
in `Cargo.toml` (refused by name if absent). It runs `cbindgen` if installed, else takes `--header`, then runs
`ail_bindgen.py`, and writes `OUT/libX.{so,a}`, `X.h`, `x_ffi.py` (stubs with `link("./libX.a")`) and the
`--print native-static-libs` link line. Also `ail_rsgen.py NAME.h` emits a Rust binding crate (`extern "C"`
block plus `Result`-returning wrappers over `NAME_last_error`) for direction (d). Accept (skip without cargo):
a crate with one external dependency vendored offline (`cargo vendor`) exposing slice-in/buffer-out and a
Box handle, CPython (cdylib) == AIL (staticlib). A Rust host calling an `@export` AIL library through the
generated crate equals CPython. No network access in tests.

Owner decision: cargo runs automatically with `--offline`; network access only with an explicit `--allow-network` option (off by default, never used in tests). Read `AIL_CURRENT/ail_bindgen.py`, `ail_ffi.py` and `test_ail_cratebridge*` first and follow their style. Register `test_ail_cargo` in `ail_check.py` MODULES; it skips with a clear reason when `cargo` is missing (cbindgen is optional: use `--header` when absent). Run `python3 tools/update_manifest.py`, then only `test_ail_cargo`, `test_ail_cratebridge*` and `test_ail_safetynet`, then commit.

**Rules for every job.**
- **Load:** you are one of up to five agents on a 16 GB PC. Keep local parallelism at 2 (`-j 2`) and never run the whole suite; the full suite runs on CI after merge.
- **Commits:** commit with explicit `git add` on your branch. Messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- **Forbidden:** push, stash, rebase, reset, and deletion outside /tmp.
- **Records:**
  - New DIFFERENCES rows use placeholder ids `C?-<your branch>-N`.
  - Add a DEVLOG entry at the top with today's date.
  - Run `python3 tools/update_manifest.py`, then `--check`.
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
