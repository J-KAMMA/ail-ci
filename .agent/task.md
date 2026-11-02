**Release readiness: find what blocks a first public release of AIL, with evidence (owner request 2026-11-02: リリースに向けて大きい仕事からやるべき).** This task audits and plans. It fixes only small, obvious doc errors. The big fixes become separate tasks.

A release means:
- `pip install ail-lang` (do not publish anything) gives a working `ail` command on Linux, macOS and Windows;
- a new user can follow docs/INSTALL.md, docs/QUICKSTART.md and docs/tutorial.md without help;
- AIL wins against Rust in the published comparison table on what we claim, and loses only where we say so.

**Step 1, a clean-room install.** On a fresh ubuntu-24.04 runner:
- build the wheel or sdist the way a release would;
- install it into a new venv;
- run every code block in INSTALL, QUICKSTART and tutorial exactly as a user would.

Record each failure with the exact command and output. Do the same on macos-latest and windows-latest as far as the runners allow (platforms.yml shows what already works).

**Step 2, user-facing gaps.** For each item, check it and give evidence (a command plus its output):
1. Error messages: 20 typical beginner mistakes. Is the message useful, with the line, the cause and a hint?
2. The CLI: does `ail --help`, `ail run`, `ail build` and `ail --version` behave as documented?
3. Programs AIL rejects: the share of lab/corpus and lab/census that builds today. List the top 10 refusal reasons with counts.
4. Silent wrong output: does any known open bug give a wrong answer with no error? Check fuzz-lab and the issues.
5. Tooling: formatter, editor support or LSP, a debugger story. What exists and what is missing.
6. The packaging metadata: license files, version, classifiers, the README rendering on PyPI.
7. The compare-lab table against Rust and C on the current integ: AIL's wins and losses.

**Step 3, the plan.** Write docs/design/RELEASE_PLAN.md:
- the blockers, ranked by user impact. Each one gets the evidence, a size estimate in lines and days, and whether it needs an owner decision;
- separately, what can wait until after the release;
- for each of the top 5 blockers, a ready-to-run task brief in the same style as this one, written as `lab/release/task_<name>.md`.

Rules:
- Publish nothing. No PyPI upload, no tags, no releases.
- Do not change compiler behaviour or any test expectation.
- Time budget: commit and push after each step, and keep the whole job under 4 hours.

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
