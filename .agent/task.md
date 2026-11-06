Lane: ff-crate

# ffcrate2: crate FFI beyond scalars: Rust-owned objects as `Handle`, strings out, callbacks, a vendored dependency

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** examples in `examples/crate/` that call a Rust crate and print the same as CPython running the
same `main.py` through ctypes. crate1 made it 3 (scalars and byte buffers). Target 7. For each new example also
record AIL binary bytes and wall time against `python3` (median of 3).

Base: `origin/integ` (crate1 and rbcrate1 are merged). Files you may create or edit, and no others:
- `examples/crate/<name>/` for 4 new crates (`Cargo.toml`, `src/lib.rs`, a hand-written `.h`, `main.py`)
- `examples/crate/README.md`, `AIL_CURRENT/test_ail_examples_crate.py`
- `AIL_CURRENT/ail_cargo.py`, only to fix a defect these examples hit, with a regression case in
  `AIL_CURRENT/test_ail_cargo.py`

Do not edit `ail_bindgen.py`, `ail_ffi.py` or `ail_ffi_lower.py`. A defect there goes into the README with a
reproducer.

## Sub-steps

1. **Handle (15 min).** `wordbag`: `wordbag_new() -> *mut Bag`, `wordbag_add(b, p, n)`, `wordbag_count(b, p, n) ->
   u64`, `wordbag_free(b)`, used through `Handle(name, free=...)` (docs/FFI.md). Probe a count fed with a u64 above
   2**63 from Rust: print what CPython prints (exact u64) or stop loudly. Commit, push, open the PR.
2. **String out and callback (25 min).** `slugify(p, n, out, cap) -> isize` (caller buffer, -needed size when too
   small), and `walk(n, cb)` calling a module-level `def` for each step.
3. **A vendored dependency (20 min).** A crate that depends on a small pure-Rust crate already in `~/.cargo/registry`
   or vendored under `examples/crate/<name>/vendor/`. If none is available offline, stop this step and report:
   fetching from crates.io is an owner decision. Never pass `--allow-network`.

## Done-check

- 7 examples match CPython; bytes and time are in the README; the test passes; the 20 shards pass.

## Stop rule

Stop on any output difference, a double free (run each example once under `valgrind` if present), or a callback
that runs after its call returned. Stop when 60 minutes pass. Push first.

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
