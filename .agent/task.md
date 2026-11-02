Lane: tooling

# rel-platinstall: prove `pip install` + `ail` on macOS and Windows in CI

**Release blocker 4.** The release promises a working `ail` after `pip install` on Linux, macOS and Windows.
CI proves it only on Linux. On macOS and Windows, `.github/workflows/platforms.yml` runs a test subset from the
checkout; it never builds, installs or runs the wheel.

**Number this changes:** operating systems on which CI builds the wheel, installs it into a fresh venv and runs
`ail --version`, `ail doctor --check`, `ail run` (hello + typed fib) and every docs/tutorial.md sample through the
installed command: 1/3 today (Linux, job `wheel` in tests.yml) -> 3/3.

## Standing rules (inlined)

1. No regressions; do not change compiler behaviour or test expectations to make a platform pass. A real
   platform bug is recorded, not hidden.
2. Push early, PR against `integ`; wait for all 20 `shard` checks plus the new jobs (poll at most every 10 min).
3. Branch from `origin/integ`. Never merge, change repository settings or cancel runs.
4. Few runner minutes: the new jobs run only when packaging, platform or docs files change.

## Evidence (2026-11-02)

- `platforms.yml` triggers: `workflow_dispatch`, and `pull_request` to `branches: [main]` with paths
  `AIL_CURRENT/**`, `lab/platforms/**`, `.github/workflows/platforms.yml` (comment: "not the integration gate
  (2026-10-25)"). Its jobs: `platform` (windows-latest x4 shards with MinGW UCRT gcc from MSYS2, macos-14 x2 with
  `PIPE_CC=$(command -v cc)`, ubuntu-24.04-arm x2) running `python lab/platforms/run.py`, and `console-probe`.
- Last run: 2026-10-26, all 9 jobs green; two earlier runs that day failed on macos 1/2, windows 1/4,
  linux-arm64 1/2.
- `lab/platforms/config.json` "representative" (61 modules) does not contain `test_ail_packaging`.
- `AIL_CURRENT/test_ail_packaging.py` class `InstalledWheel` already builds the wheel with
  `pip wheel --no-deps --no-index`, installs it offline into a venv, and handles `Scripts\ail.exe` on Windows.
- `tools/wheel_check.py` (used by the Linux-only `wheel` job of `.github/workflows/tests.yml`) does: `pip wheel .`,
  fresh venv, `pip install` of the wheel, `ail --version`, `ail doctor --check`, `ail run` hello and fib compared
  with CPython, then `AIL_CURRENT/test_ail_tutorial.py` against the installed command. It already picks
  `Scripts`/`ail.exe` when `os.name == "nt"`.
- On Linux (WSL Ubuntu 24.04, Python 3.12.3) the whole flow passes: wheel 3.6 MB, `ail doctor --check`
  `"status": "passed"`, all tutorial samples equal CPython.

## Changes

1. `.github/workflows/platforms.yml`: add a job `wheel` with a matrix
   `{windows-latest (MinGW UCRT gcc set up exactly like the platform job), macos-14 (PIPE_CC=cc), ubuntu-24.04}`,
   steps: keep-LF git config, checkout (same pinned SHA as the other jobs, `persist-credentials: false`),
   setup-python 3.12 (same pinned SHA), toolchain, then `python tools/wheel_check.py` with `PYTHONUTF8=1`.
   `timeout-minutes: 30`.
2. Triggers: add `integ` to the `pull_request` branches and add the paths `packaging/**`, `pyproject.toml`,
   `tools/wheel_check.py`, `docs/**`. Keep the old behaviour of the `platform` and `console-probe` jobs with
   `if: github.event_name != 'pull_request' || github.base_ref == 'main'`, so integ PRs run only the new `wheel`
   job. (Integ PRs that touch only `AIL_CURRENT/**` will then start the workflow and skip all jobs: fine.)
3. `tools/wheel_check.py`: make it work on Windows and macOS if it does not: CRLF in CPython's stdout on Windows
   (compare after `.replace("\r\n", "\n")` on both sides), `PATH`/`PIPE_CC` passed through to the venv's `ail`,
   no POSIX-only shell commands. If a tutorial sample cannot run on a platform for a documented reason (for
   example `link("m")` on Windows, or no Vulkan loader for the GPU sample), skip that one sample on that platform
   with a printed reason, following how `lab/platforms/config.json` documents its skips; do not skip a sample
   because AIL prints something different.
4. `lab/platforms/config.json`: add `test_ail_packaging` to "representative" with a weight of about 60.
5. `docs/INSTALL.md`, section "Platforms": state per OS what CI now checks ("wheel install + tutorial samples");
   in the opening paragraph, drop "The macOS and native Windows steps below were not run by hand; CI covers a
   subset" only for what the new job actually proves.

## Tests

The new job is the test. Locally, `python3 tools/wheel_check.py` must still pass on Linux (it needs Python with
venv + pip and gcc; no network). Check the config still parses:
`python3 -c "import json; json.load(open('lab/platforms/config.json'))"`, and that `lab/platforms/run.py` still
reads it (run it with `--help` first to see its options; use its own listing or dry-run option if it has one).

## Gate

- The PR's `wheel` job is green on all three OSes, or every red one is explained in the PR body with the exact
  failing command and its output (that output is the deliverable: it tells the owner what breaks for users).
- `tests.yml` shards unchanged and green.
- `python3 tools/update_manifest.py --check` (only if pinned files changed).

## Commit and push

Commit and push after each sub-step: (a) changes 1-2 (open the PR now so the job runs), (b) change 3 for each
platform failure you fix, (c) change 4, (d) change 5 with the results from the last green run.

## Stop rule

Stop and report if: a platform failure needs a change under `AIL_CURRENT/` or `packaging/ail_lang/` (report the
command and output, do not fix it here); the Windows toolchain step cannot install gcc; any `tests.yml` shard
changes behaviour; or 80 minutes pass (push, report which OS is green and what fails where).

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
