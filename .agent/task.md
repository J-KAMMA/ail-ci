Lane: docsrun

# docsrun1: every code block in README.md, docs/FFI.md, docs/LSP.md and docs/INSTALL.md is run by a test

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** fenced code blocks in the user-facing docs that no test runs. `docs/QUICKSTART.md`
(`test_ail_quickstart_docs.py`), `docs/tutorial.md` (`test_ail_tutorial.py`) and `docs/PORTING.md` already have
tests. `README.md` (2 fence lines), `docs/FFI.md` (10), `docs/LSP.md` (14) and `docs/INSTALL.md` (14) have none
that runs their blocks, as far as `git grep` shows; check this first. The target: every block in those four files is
either run by a test (Python blocks built with AIL and compared with CPython; shell blocks run and their shown
output compared) or marked `<!-- docs-test: skip REASON -->` with a reason a reviewer can accept (needs network,
needs macOS, starts an editor). A doc example that does not work is the first thing a new user hits (release P3).

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/test_ail_docs_blocks.py` (new) and `AIL_CURRENT/tests.d/test_ail_docs_blocks.txt` (new, one line:
  `test_ail_docs_blocks`)
- `AIL_CURRENT/language_examples/docs/*` (new: example files that blocks name, if you use the QUICKSTART scheme)
- `README.md`, `docs/FFI.md`, `docs/LSP.md`, `docs/INSTALL.md`: markers, and fixes to examples that are wrong. A fix
  changes the doc to match what AIL does today; it never changes the compiler.
- `lab/docsrun/RESULTS.md` (new)
- the manifest files that `tools/update_manifest.py` writes

## Sub-steps

1. **Inventory (15 min).** List every fenced block in the four files: file, line, language tag, kind (Python
   program, Python fragment, shell command, shell output, JSON, other). Check whether `test_ail_packaging.py`,
   `test_ail_examples_hybrid.py` or any other test already runs some of them (`git grep -n` for the file names in
   `AIL_CURRENT/test_*.py`); those count as covered. Write the table into `lab/docsrun/RESULTS.md` under "Before"
   with the count of uncovered blocks. Commit, push, and open the PR against `integ`.
2. **The test (35 min).** Write `AIL_CURRENT/test_ail_docs_blocks.py` (model: `test_ail_quickstart_docs.py`):
   - a Python block that is a whole program is written to a temp dir, built with
     `ail_chatgpt.py compile --syntax python`, run, and compared with `python3` (stdout and exit status). If the doc
     shows its output in the next block, that output must match too;
   - an FFI block that needs its C side uses the file the doc names under `examples/ffi/`; skip with a reason when
     there is no C compiler;
   - a shell block of `ail ...` commands runs through the checkout (`python3 -B AIL_CURRENT/ail_chatgpt.py` or the
     `packaging/ail_lang` entry point the doc means) in a temp dir; `pip install` lines are not run;
   - an LSP JSON block is parsed with `json.loads`; a request/response pair is checked against the real server's reply
     if `packaging/ail_lang/lsp.py` can be driven over stdin in under 10 seconds, else only parsed;
   - a block marked `<!-- docs-test: skip REASON -->` is counted and listed, not run;
   - an unmarked block of an unknown kind fails the test, so new docs cannot add untested examples silently.
   Register it (Appendix A rule 6). Commit and push.
3. **Fix what fails (20 min).** For each failing block: fix the doc text (or the example file), or mark it skipped
   with a reason. Never edit a compiler file; if the compiler is wrong, mark the block
   `<!-- docs-test: skip known-bug ... -->`, and write the exact refusal or wrong output in `RESULTS.md` under
   "Follow-ups". Fill "After". Commit, push, and wait for CI.

## Done-check

- `python3 AIL_CURRENT/test_ail_docs_blocks.py` passes.
- `RESULTS.md` shows: blocks run, blocks skipped (each with a reason), blocks uncovered = 0.
- `test_ail_quickstart_docs`, `test_ail_tutorial` and `test_ail_packaging` still pass.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop and report if more than 10 blocks fail because of compiler bugs (not doc errors); list them. Stop when 80
minutes pass. Push what is done first.

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
   `pyc.py`, `cruntime.py`, `unified.py`, `buildcache.py`, `pyboxed2.py`, `ir/emit_c.py`, or
   `packaging/ail_lang/cli.py`. Other lanes own them. Do not edit `DEVLOG.md` either: put your notes in the files
   this task names. Edit only the files this task names, plus the manifest files that `tools/update_manifest.py`
   writes.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--syntax python] [--strict]`. `-o` must not exist
  yet.
- `test_ail_quickstart_docs.py` pairs each ```` ```python ```` block with an `<!-- example: NAME -->` marker and a file in
  `AIL_CURRENT/language_examples/quickstart/`; reuse that scheme or extract blocks directly, but be consistent.
- FFI examples live in `examples/ffi/`; the LSP server is `packaging/ail_lang/lsp.py`.
- CPython 3.12 is the oracle: compare stdout and the exit status.

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
