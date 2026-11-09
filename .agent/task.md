Lane: vibe-waste
Needs: vibe3

# waste1: compute waste per correct program, by language (the owner's new top goal)

Time budget: 150 minutes. Commit and push after each sub-step. Follow `.agent/` rules. No compiler change.

**Why (owner, 2026-11-09):** the top goal is now "eliminate the waste of the world's computing resources". More and
more code is written by AI; if the language an AI writes in is efficient by default, the waste shrinks without anyone
tuning. So the headline is: for the same task written by the same AI, how much compute does each language's correct
program spend, compared with the physical minimum we can reach?

**Input:** the final programs of vibe3 (`lab/vibe/results3.json`, branch job-vibe3-11091615 if not yet integrated),
languages python, rust, go, ail. Use only programs that were correct on all cases.

**Numbers** (`lab/waste/RESULTS.md`, `lab/waste/results.json`), per task and per language, on the largest hidden case:
1. CPU seconds (user+sys, median of 5), wall seconds, peak RSS, binary/disk size of what must be shipped (interpreter
   counted for python), compile CPU seconds.
2. Energy estimate: RAPL (`/sys/class/powercap`) if readable, otherwise state "not measurable on this runner" and
   use CPU seconds as the proxy; never invent watts.
3. Per task, the best correct program across all languages = 1.0; report each language as a multiple of it
   ("waste factor"), and the geomean per language. Also count the cost of failure: programs that never became
   correct waste every round's compile+run CPU (from results3.json loop seconds).
4. A 5-line verdict: where AIL wastes most and the top 3 causes (general path, boxing, refusal, startup, ...).

Files: `lab/waste/*` only.

## Sub-steps
1. (40 min) Harness on 2 tasks; commit, push. 2. (80 min) all tasks; commit, push. 3. (30 min) RESULTS.md.
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
