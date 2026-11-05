Lane: docffiq

# docffiq1: `docs/FFI_QUICK.md`, a one-page quick guide to calling C from AIL, every step checked by a test

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** steps of the FFI quick guide that a test builds and runs. `docs/FFI.md` lists four finished
examples, but a new user has no step-by-step path from "I have a C function" to "my AIL program calls it". The target
is a page of at least 8 numbered steps, each with a code block that a test builds and runs, and whose output matches
what the page shows.

Base: `origin/integ`. Files you may create or edit, and no others (all new):
- `docs/FFI_QUICK.md`
- `examples/ffi_quick/*` (the C file, header and AIL programs the steps use)
- `AIL_CURRENT/test_ail_docs_ffi_quick.py` and `AIL_CURRENT/tests.d/test_ail_docs_ffi_quick.txt` (one line:
  `test_ail_docs_ffi_quick`)
- the manifest files that `tools/update_manifest.py` writes

Do not edit `docs/FFI.md`, `examples/ffi/`, or `AIL_CURRENT/test_ail_docs_blocks.py`. Link to them. Read
`docs/FFI.md`, `examples/ffi/libm_math.py`, `examples/ffi/libc_text.py`, `examples/ffi/bindgen/README.md`, and
`AIL_CURRENT/test_ail_ffi_examples.py` first: use only the FFI forms they use. Do not invent syntax.

## Sub-steps

1. **The steps (25 min).** Write the programs in `examples/ffi_quick/`:
   1. call `sqrt` from libm (the smallest program);
   2. call a function from your own `add.c` with two int64 arguments, with the exact build command;
   3. pass and return a `double`;
   4. pass a `str` and get its length back from C;
   5. pass `bytes` and fill a buffer in C;
   6. what happens when an int argument is out of the C type's range (the range check from FFI stage 3 if it is on
      `integ`; otherwise show and say what happens today);
   7. a C function that reports an error through its return value, turned into a Python exception;
   8. generating the declarations with bindgen from a header (`examples/ffi/bindgen/README.md`).
   Run each. For steps 1-5 and 7, also run an equivalent `ctypes` program with `python3` and check the printed values
   are equal. Commit, push, and open the PR against `integ`.
2. **The page (20 min).** Write `docs/FFI_QUICK.md`: one short section per step, the code block, the command, and the
   output. Code blocks are the files in `examples/ffi_quick/` byte for byte. End with "What is not supported yet",
   linking to the same section of `docs/FFI.md` rather than repeating it. Commit and push.
3. **Test (15 min).** Write `AIL_CURRENT/test_ail_docs_ffi_quick.py`: for every step, check the page's code block
   equals the file, build it with the page's command, run it, and compare stdout with the output block on the page.
   Skip without a C compiler or without libm. Register it (Appendix A rule 6). Commit, push, and wait for CI.

## Done-check

- `docs/FFI_QUICK.md` has at least 8 steps, each with code, command and output.
- `python3 AIL_CURRENT/test_ail_docs_ffi_quick.py` passes; the 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop at once and report if an FFI call returns a value different from the `ctypes` program, or an out-of-range
argument is silently truncated: commit the repro in `examples/ffi_quick/RESULTS.md` (you may create it) first. Stop when
60 minutes pass. Push what is done first.

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
