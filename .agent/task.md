**Make the project installable with pip (build only, never publish).**

Add a `pyproject.toml` at the repository root (setuptools backend, no other build dependencies) for a distribution named `ail-lang`, license `MIT OR Apache-2.0` (both LICENSE files exist), Python >= the version CI uses. It installs the compiler (the `AIL_CURRENT` sources the CLI needs, including `python/pkg-v12`, `stdlib`, and any runtime data files the compiler reads at run time — find them by reading how `ail_chatgpt.py` locates its files) and a console script `ail` that runs `ail_chatgpt.py`'s main. Tests, benchmarks, docs and `lab/` are not packaged. If the compiler finds its files by paths relative to the repository, add the smallest change that makes it work from an installed package as well, without changing behaviour when run from the repository.

Add `AIL_CURRENT/test_ail_packaging.py` (register it in `ail_check.py` MODULES): it builds a wheel with `python3 -m pip wheel --no-deps --no-build-isolation` into a temporary directory (skip with a clear message if `setuptools`/`wheel` are missing), installs it into a fresh `venv` in a temporary directory, and from a directory outside the repository runs `ail compile hello.py --syntax python -o hello` and the resulting binary, checking the output. Run `python3 tools/update_manifest.py`, run only `test_ail_packaging` and `test_ail_safetynet`, then commit.

Never run `twine`, `pip upload`, or anything that publishes; publishing to PyPI is the owner's decision at release time.

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
