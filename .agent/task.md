Lane: errdesign

# err1: compiler messages an AI can act on: measure the fix rate per message, then design the rewrite (measurement + design only)

Time budget: 120 minutes. Commit and push after each sub-step. Follow `.agent/` rules (no regressions, CI first).
Do not change the compiler. Output: `lab/err/*` and `docs/design/AGENT_ERRORS.md`.

**Why (owner, 2026-11-07):** vibe1 (`lab/vibe/RESULTS.md`, "AIL compiler errors") found that after almost every AIL
compiler error or "built on the general path" note, the model's next round did not fix it (fix rate 0.00 on 9 of the
top 10 messages). AIL is for vibe coding; a message that an AI cannot act on is a defect.

## Measure (`lab/err/RESULTS.md`)
1. Collect the compiler's refusal and fallback messages: grep the emitter/front end for the message builders, and run
   the compiler over the vibe programs, compare `main.py` and 100 gdev programs to get the messages that actually
   fire, with counts.
2. For the 15 most frequent: a small program that triggers it; ask the same model vibe1 used (`lab/vibe/run.py`'s
   model call path, same settings) to fix the program given only the message, 5 tries each. Record: fixed (types /
   builds and output matches CPython), changed but still blocked, made it worse. That is the per-message fix rate.
3. Classify why low-rate messages fail: names an internal symbol (`_ail_l1l`), says what is wrong but not what to
   write, points at the wrong line, the fix is not expressible in plain Python, needs a type annotation the model
   does not know the syntax for, etc.

## Design (`docs/design/AGENT_ERRORS.md`)
A message format for agents: location, one-sentence cause in the user's own names, a concrete replacement snippet
built from the user's code, and a `--json` form `{"code","file","line","col","cause","fix":{"replace_range","with"}}`
so an agent can apply it. Rewrite the 15 messages in that format (as a table: old, new); re-run step 2 on the
rewritten text (fed to the model as if the compiler had printed it) to show the new fix rate. Then split the
implementation into steps of at most 2 hours with files, tests and the number each moves, as ready-to-queue task text.

## Sub-steps
1. (70 min) Collection and fix-rate measurement. Commit, push.
2. (50 min) AGENT_ERRORS.md with rewrites, re-measured fix rate, step split. Commit, push.

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
