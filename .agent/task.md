Lane: notice

> Redo of relnotice1, a 0.1 release blocker. It was ACCEPTED, but its re-apply (rbrelnotice1) conflicted twice and was dropped, so integ still lacks it. Redo it from scratch on the CURRENT origin/integ: many new files have landed since (stdlib modules, docs, examples), so the notice list must cover them too. You may read branch job-relnotice1-* for reference, but do not cherry-pick it blindly. Keep the edits small and additive to cut conflicts.

# relnotice1: third-party notices for vendored and derived code (CPython stdlib copies, typeshed), checked by a test

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** files in the repository and in the `ailc` wheel that are copied or derived from third-party
code but carry no notice of where they come from and under which license. Not measured today. Known cases:
`AIL_CURRENT/stdlib/` holds AIL copies of CPython 3.12 modules (`getopt.py`, `difflib.py`, `shlex.py`,
`colorsys.py`, `keyword.py`, `token.py`, `stat.py`, `tomllib/`), which are under the PSF License; `third_party/typeshed`
has its own `LICENSE`; the root only has `LICENSE-MIT` and `LICENSE-APACHE`. Publishing `ailc` (roadmap P3) with PSF
code and no PSF notice is a license problem. The target: 0 such files without a notice, a `THIRD_PARTY_NOTICES.md`,
and a test that fails when a new derived file arrives without an entry.

Base: `origin/integ`. Files you may create or edit, and no others:
- `THIRD_PARTY_NOTICES.md` (new, repository root)
- `AIL_CURRENT/stdlib/LICENSE-PSF.txt` (new: the PSF License version 2 text, as printed in CPython's `LICENSE` file;
  copy it from `/usr/lib/python3.12/LICENSE.txt` or the system's CPython `LICENSE` file)
- the module docstring (first lines only) of each derived file under `AIL_CURRENT/stdlib/`, to add one line:
  `Derived from CPython 3.12 Lib/<name>.py; PSF License, see stdlib/LICENSE-PSF.txt.`
- `AIL_CURRENT/test_ail_third_party_notices.py` (new) and `AIL_CURRENT/tests.d/test_ail_third_party_notices.txt`
  (new, one line: `test_ail_third_party_notices`)
- the manifest files that `tools/update_manifest.py` writes
Do not edit `packaging/ail_wheel_backend.py` or `pyproject.toml`: another lane owns them. If the wheel needs a
change, write it in `THIRD_PARTY_NOTICES.md` under "Follow-ups" with the exact line to change.

## Sub-steps

1. **Inventory (20 min).** Find every vendored or derived file: everything under `third_party/` and
   `AIL_CURRENT/stdlib/`; any `.c`/`.h` copied from elsewhere (`zlib_glue.c` is AIL's own glue; check whether it
   copies zlib code); files whose header says "from CPython", "derived", "copied", "vendored", "Copyright" (grep
   `-i -E 'copyright|derived from|vendored|adapted from|license'` across `AIL_CURRENT`, `packaging`, `tools`, `lab`,
   `examples`). For each stdlib copy, confirm it is derived by comparing it with
   `python3 -c "import X, inspect; print(inspect.getsource(X))"`. Write the table (file, origin, license, already has
   a notice yes/no) into `THIRD_PARTY_NOTICES.md`. Commit, push, and open the PR against `integ`.
2. **Notices (20 min).** Add `LICENSE-PSF.txt` and the one-line docstring note to each derived stdlib file. Do not
   change code: only docstring text. Rebuild one program per touched module (from `lab/stdlib/<name>/`) to prove the
   docstring edit did not change its output. Fill `THIRD_PARTY_NOTICES.md`: for each origin, the license name, the
   license file path, and the list of files. Commit and push.
3. **Test (25 min).** Write `AIL_CURRENT/test_ail_third_party_notices.py`:
   - every file under `AIL_CURRENT/stdlib/` and `third_party/` is listed in `THIRD_PARTY_NOTICES.md` or is marked
     there as AIL's own;
   - every file marked as derived from CPython names `LICENSE-PSF.txt` in its first 15 lines;
   - every license file the notices name exists;
   - when a C compiler and the wheel backend are available: build the wheel into a temp dir
     (`ail_wheel_backend.build_wheel`) and check that `LICENSE-PSF.txt` and each derived stdlib file are in it, and
     the two root licenses are under `.dist-info/licenses/`. Report the wheel result as a test, not a skip, if it
     fails.
   Register the test (Appendix A rule 6). Commit and push.
4. **Verify (15 min).** Run the new test, `test_ail_packaging`, and the `test_ail_std_*` modules of every stdlib file
   you touched. Commit, push, and wait for CI.

## Done-check

- `python3 AIL_CURRENT/test_ail_third_party_notices.py` passes (or its wheel check fails with a follow-up written).
- 0 derived files without a notice; the count of derived files is in `THIRD_PARTY_NOTICES.md`.
- Every touched stdlib module's own test still passes.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop and report if a file's origin or license cannot be determined in 5 minutes; list it as "unknown" and go on.
Never guess a license. Stop when 80 minutes pass. Push what is done first.

## Appendix A: standing rules (from agent-brief-rules.md)

1. No regressions: a program that built and matched CPython before must still do so in the default build. A loud
   stop is allowed only where the value cannot be computed.
2. Probe ints beyond int64 wherever ints come from text or arithmetic; run probes in the default build and with
   `AIL_UNIFIED_FORCE=1`, compare both with `python3`. (This job changes docstrings only.)
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

- `packaging/ail_wheel_backend.py`: `LICENSE_FILES = ("LICENSE-APACHE", "LICENSE-MIT")` (line ~43) go to
  `.dist-info/licenses/`; `sdk_files()` selects compiler and `stdlib/` files from the manifest flags.
- `AIL_CURRENT/ail_modules.py` (`BUNDLED_DIR`) finds `AIL_CURRENT/stdlib/*.py` for `import X`.
- The project license is MIT OR Apache-2.0; the PyPI name is `ailc`.

> (2026-11-09) relnotice1_rr1 then failed its precheck twice (see relnotice1_rr1-suite.md for the failing tests). Run those tests yourself before pushing; a new notices file must not break test_ail_third_party_notices or test_ail_packaging.

**Rules for every job.**
- **Load:** you are one of up to five agents on a 16 GB PC. Keep local parallelism at 2 (`-j 2`) and never run the whole suite; the full suite runs on CI after merge.
- **Commits:** commit with explicit `git add` on your branch. Messages end with a `Co-Authored-By:` line naming the model you actually are (Claude: `Claude Opus 5.5 <noreply@anthropic.com>` or `Claude Sonnet 5.5 <noreply@anthropic.com>`; other models: omit the line).
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
