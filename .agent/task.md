Lane: relver

# relver1: one version everywhere, locked by a test (`ail --version`, wheel name, metadata, docs)

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** places that state the AIL version and disagree with the single source
`packaging/ail_lang/__init__.py` (`__version__ = "0.1.0.dev0"` on integ). Not measured today; one known case:
`docs/LSP.md` line ~71 shows `"version": "0.1.0"` in a sample `serverInfo` reply, while the server sends
`cli.__version__`. The target is 0 disagreements, and a test that fails when a release bump (roadmap P3: tag on
`main`, publish `ailc`) forgets one place. Version drift between `ail --version`, the wheel file name and the docs is
a classic release-day bug.

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/test_ail_version_consistency.py` (new) and `AIL_CURRENT/tests.d/test_ail_version_consistency.txt`
  (new, one line: `test_ail_version_consistency`)
- `docs/LSP.md`, `docs/INSTALL.md`, `docs/QUICKSTART.md`, `README.md`, `packaging/README.md`: only the lines that
  state a version
- `docs/RELEASING.md` (new, at most 40 lines)
- the manifest files that `tools/update_manifest.py` writes
Do not edit `packaging/ail_wheel_backend.py`, `packaging/ail_lang/cli.py`, `packaging/ail_lang/lsp.py` or
`pyproject.toml`: other lanes own them. If one of them needs a change, write it in `docs/RELEASING.md` under
"Follow-ups" with the exact line.

## Sub-steps

1. **Inventory (15 min).** `git grep -n -E '0\.1\.0|__version__|[0-9]+\.[0-9]+\.[0-9]+\.dev[0-9]+'` over the whole
   tree except `third_party/`, `lab/` result files and `DEVLOG.md`. Classify each hit: (a) reads the single source,
   (b) states the AIL version as literal text, (c) unrelated (a tool's version, a pinned dependency such as
   `ziglang==0.13.0`, a protocol version). Write the list into the first commit message body. Commit, push, and open
   the PR against `integ`.
2. **The test (30 min).** Write `AIL_CURRENT/test_ail_version_consistency.py` (model: `test_ail_packaging.py` for
   paths and skips). It reads `__version__` from `packaging/ail_lang/__init__.py` with a regex (not an import) and
   checks:
   - it is a valid PEP 440 version (`packaging.version` is not available; use the PEP 440 regex from the spec's
     appendix);
   - `pyproject.toml` has `dynamic = ["version"]` and no literal `version =` line;
   - `python3 -B -c "import sys; sys.path.insert(0, 'packaging'); import ail_lang.cli as c; c.main(['--version'])"`
     (or the documented entry point; find it) prints `ailc <version>`;
   - `ail_wheel_backend.wheel_name()` contains `-<version>-`, and `metadata_text()` has `Version: <version>`;
   - every type-(b) place from step 1 states the same version, or is written as a placeholder such as `<version>`;
   - `packaging/WHEEL_REPORT.md` is a measured report: allow its old version, but only inside a line that also
     names the report's date or commit.
   Each check is one test method, so a failure names the place. Register the test (Appendix A rule 6). Commit and
   push.
3. **Fix the docs (15 min).** Make every type-(b) place agree, preferring a placeholder in sample output (for
   `docs/LSP.md`: `"version": "<ail --version>"` or the real current value). Run the test: all green. Commit and
   push.
4. **Release note (15 min).** Write `docs/RELEASING.md`: the one file to edit for a version bump, the command that
   proves it (`python3 AIL_CURRENT/test_ail_version_consistency.py`), and that every tag and publish waits for the
   owner. Run `test_ail_packaging` and `test_ail_quickstart_docs` too. Commit, push, and wait for CI.

## Done-check

- `python3 AIL_CURRENT/test_ail_version_consistency.py` passes with at least 6 test methods.
- Changing `__version__` to `0.1.0` in a scratch copy makes exactly the expected checks fail (report the count) and
  restoring it makes them pass; do not commit the scratch change.
- 0 type-(b) disagreements remain.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop and report if `ail --version` cannot be run from the checkout without editing `cli.py`; give the error. Stop
when 80 minutes pass. Push what is done first.

## Appendix A: standing rules (from agent-brief-rules.md)

1. No regressions: a program that built and matched CPython before must still do so in the default build. A loud
   stop is allowed only where the value cannot be computed.
2. Probe ints beyond int64 wherever ints come from text or arithmetic; run probes in the default build and with
   `AIL_UNIFIED_FORCE=1`, compare both with `python3`. (This job touches no compiler code.)
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

- `packaging/ail_lang/__init__.py` holds `__version__`; `pyproject.toml` reads it as a dynamic version through
  `packaging/ail_wheel_backend.py` (`version()`, `metadata_text()`, `wheel_name()`, `build_wheel`, `build_sdist`).
- `packaging/ail_lang/cli.py` prints `ailc <version>` for `--version` (line ~341); `lsp.py` sends it as
  `serverInfo.version`.
- The PyPI name is `ailc`, the command is `ail`, the license is MIT OR Apache-2.0.

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
