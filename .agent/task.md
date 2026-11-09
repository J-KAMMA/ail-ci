Lane: err
Needs: err3

# err4: apply the agent format to the other 13 compiler messages

Time budget: 120 minutes. Commit and push after each sub-step. Follow `.agent/` rules (no regressions, CI first).

**Why (owner, 2026-11-07):** AIL is for vibe coding; vibe1 found AI fix rate ~0 after AIL errors. err1 measured and
designed the fix: `docs/design/AGENT_ERRORS.md` and `lab/err/*` (on integ; if missing, `git fetch origin
job-err1-11071624` and read them from that branch). Rewritten messages raised the fix rate 0.75 -> 0.92 on the
15-message set. This job is **Step 3** of that design's "Implementation split"; read the whole section first.
Rules from the design: position is in the user's file, cause names only the user's identifiers (never `_ail_*`),
`Replace:`/`With:` is a literal edit that builds on the typed path and keeps output. Never change what a program
prints; a message rewrite must not turn a building program into a refusal.

## Do
- `pyfunc.py` (Yield, while-else, dict of containers, tuple refusals), `pyc.py` (fallback template),
  `strictmode.py` (classification text). Use the exact rewritten texts in `lab/err/messages_rewritten.json`.
- `test_ail_agent_errors.py`: every message has a location in the user's file, no `_ail_` identifier, and a `With:`
  block that builds.
- Update any test that pins old message text (grep tests for the old strings); change text only, never behaviour.

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
