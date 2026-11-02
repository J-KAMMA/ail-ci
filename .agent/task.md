Lane: packaging

# rel-pkgname: a distribution name we own, and PyPI metadata a user can trust

**Owner decision (2026-11-02): the PyPI distribution name is `ailc`.** The command stays `ail`. Publish nothing.

**Release blocker 1.** `ail-lang` on PyPI is someone else's project (versions 2.1 and 2.1.2, 2021, an unrelated
interpreter). Every place where AIL tells users `pip install ail-lang` would install that package.

**Number this changes:** `git grep -n "ail-lang" -- docs packaging pyproject.toml tools 'AIL_CURRENT/*.md'
AIL_CURRENT/test_ail_packaging.py .github ':!AIL_CURRENT/docs'` (user-facing places) goes from 26 lines to 1:
the single sentence in docs/INSTALL.md that says the old name is not ours (and the test that checks it is
absent elsewhere). METADATA gains `Project-URL` lines and
OS/Python-version/status classifiers (from 2 classifiers to at least 9).

## Standing rules (inlined)

1. No regressions: `tools/wheel_check.py` and `test_ail_packaging` must pass before and after.
2. Publish nothing: no PyPI upload (not even TestPyPI), no tags, no releases.
3. Push early, PR against `integ`, wait for all 20 `shard` checks and the `wheel` job (poll at most every 10 min).
4. Branch from `origin/integ`. Never merge, change settings or cancel runs.
5. After editing pinned files run `python3 tools/update_manifest.py`, then `--check`.

## Evidence (2026-11-02)

```
$ pip download ail-lang --no-deps            -> Saved ./ail_lang-2.1.2-py3-none-any.whl
METADATA: Name: ail-lang / Version: 2.1.2 / Summary: UNKNOWN; files ail/core/aparser.py, ail/core/acompiler.py
          ... dated 2021-06-19
https://pypi.org/pypi/<name>/json:  ail 200 (taken)  ail-lang 200 (taken)
                                    ailc 404  ail-compiler 404  ail-language 404  ailang 404  (free)
Our wheel today: ail_lang-0.1.0.dev0-py3-none-any.whl, METADATA:
  Name: ail-lang / Version: 0.1.0.dev0 / License-Expression: MIT OR Apache-2.0 / Requires-Python: >=3.10
  Classifier: Programming Language :: Python :: 3
  Classifier: Topic :: Software Development :: Compilers
  (no Project-URL, no Operating System / Python version / Development Status classifiers)
```

## What stays

- The command is still `ail`; the import package is still `ail_lang`; `python -m ail_lang` still works.
- The version stays `0.1.0.dev0` (the owner sets the release version).
- License files and `License-Expression` unchanged.

## Changes

1. `pyproject.toml`: `name = "ailc"`.
2. `packaging/ail_wheel_backend.py`: `NAME = "ailc"`; `DIST` becomes the normalized wheel name `ailc` (the
   wheel file and the `.dist-info` directory must be `ailc-<version>...`); the `build_sdist` refusal text.
   In `metadata_text()` add:
   - `Project-URL: Homepage, https://github.com/J-KAMMA/ail-ci`
   - `Project-URL: Documentation, https://github.com/J-KAMMA/ail-ci/blob/main/docs/INSTALL.md`
   - `Project-URL: Issues, https://github.com/J-KAMMA/ail-ci/issues`
   - classifiers `Development Status :: 3 - Alpha`, `Environment :: Console`,
     `Intended Audience :: Developers`, `Operating System :: POSIX :: Linux`, `Operating System :: MacOS`,
     `Operating System :: Microsoft :: Windows`, `Programming Language :: Python :: 3.10`, `... :: 3.11`,
     `... :: 3.12`, `... :: 3.13`, `Programming Language :: C` (keep the two existing ones).
3. `packaging/ail_lang/cli.py`: the `--version` line becomes `ailc <version>` (it prints `ail-lang %s` today,
   about line 341); the no-C-compiler hint `pip install "ail-lang[zig]"` (about line 69) and the comment near
   line 84, and the broken-install message near line 344, use `ailc`.
4. `packaging/ail_lang/__init__.py` docstring; `packaging/README.md` (it is the PyPI page): `pip install ailc`,
   one line "the command is `ail`", and links to INSTALL, QUICKSTART and tutorial on GitHub (absolute URLs:
   relative links do not work on PyPI).
5. Docs: `docs/INSTALL.md` (lines 4, 6, 20, 148), `docs/tutorial.md` (line 4),
   `AIL_CURRENT/LANGUAGE_QUICKSTART_JA.md` (lines 29-46), `tools/wheel_check.py` docstring, the comment in
   `.github/workflows/tests.yml` job `wheel`. In INSTALL add one sentence: "The PyPI project `ail-lang` is not
   AIL; install `ailc`." Leave `AIL_CURRENT/docs/design/*.md` history as it is.
6. `AIL_CURRENT/test_ail_packaging.py`: `"\nName: ail-lang\n"` (about line 132) and the two
   `"ail-lang " + source_version()` checks (about lines 297 and 302) follow the new name; add asserts that
   METADATA contains the three `Project-URL` lines and the three `Operating System ::` classifiers, and a test
   that no file under `docs/` or `packaging/` contains `pip install ail-lang`.

## Gate

- `python3 tools/wheel_check.py` passes and the built file is `ailc-0.1.0.dev0-py3-none-any.whl`.
- `python3 AIL_CURRENT/test_ail_packaging.py` passes (including `test_build_is_reproducible`,
  `test_record_matches`, `test_nothing_private_is_in_the_wheel`).
- `python3 tools/par_check.py -j 2 test_ail_packaging test_ail_tutorial test_ail_quickstart_docs
  test_ail_doctor test_ail_project` all pass.
- `python3 tools/update_manifest.py --check`; PR against `integ`, all 20 shards and the `wheel` job green.

## Commit and push

Commit and push after each sub-step: (a) changes 1-2 + the test updates for name and METADATA, (b) change 3,
(c) changes 4-5, (d) the new tests of change 6 and the manifest. Open the PR after (a).

## Stop rule

Stop and report if: the wheel cannot be renamed without changing the import package `ail_lang`; any test
outside packaging/docs needs the old name; something would upload or reserve a name; or 80 minutes pass.

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
