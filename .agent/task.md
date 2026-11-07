# err2b: land err2 (agent error format) after fixing the packaging failures it caused

Lane: err

**Do not redo err2. Start from its finished work and fix only what broke at the gate.**

err2 is on branch `job-err2-11080418`. Its review verdict was ACCEPT, but the gate run on PR #455
was red.

## Setup

Start a branch from `origin/integ`. Bring err2's work across in one of two ways:

- `git merge origin/job-err2-11080418`;
- or cherry-pick its commits, leaving out "export of staging" and "agent worker report".

## Failures to fix (all new against integ)

1. **`ModuleNotFoundError: No module named 'ail_agent_errors'`.** This failed:
   - test_ail_sdk;
   - test_ail_packaging (the wheel check);
   - test_ail_sdk_environment;
   - the `wheel` job.

   The new module `ail_agent_errors` is imported, but the installed package does not ship it. Add it
   wherever the other AIL modules are listed for packaging (pyproject / setup / MANIFEST / package
   lists; look at how a sibling module such as the CLI module is listed) and in the update_manifest
   manifests.
   - Prefer that a missing optional diagnostics module never breaks a plain build. If the import is
     only needed for `--json`, import it lazily there.
2. **Shard 2 hit the 60-minute cap.** Check whether err2 makes builds slower. Compare the time of
   test_ail_std_re or another long module on shard 2 against integ.
   - If err2 is not the cause, say so with the numbers. Do not edit tools/ci_shards.json unless a
     module's measured time is far off its weight, and report any such edit.

## Run, one after another, under `ulimit -v 2500000`

- test_ail_sdk
- test_ail_packaging
- test_ail_sdk_environment
- test_ail_agent_errors

Also run `python3 tools/update_manifest.py --check`, and build a wheel and import it in a fresh venv.

## Report

- the cause of each failure;
- test results with times.

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
