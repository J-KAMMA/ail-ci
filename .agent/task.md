# aiknow1: make AI coding agents know when and how to use ailc

Lane: aiknow

The owner approved this on 2026-11-08. In future vibe coding, an AI agent writes and runs the code. AIL is used only
if agents know it exists, when it helps, and how to call it. This job prepares that material. **Nothing is published
by this job**: publishing waits for the 0.1 release, which needs the owner's approval.

## Deliverables (all in the repository)

1. **`llms.txt` at the repository root** (llmstxt.org format):
   - what AIL is, in one sentence (it compiles typed Python to native code; CPython fallback through the hybrid
     build);
   - when to use it (CPU-bound pure-Python hot paths; instead of rewriting them in Rust);
   - when not to use it;
   - the 5 commands an agent needs (`ailc build`, `ailc run`, `ailc ext`, `--json` diagnostics, `--why`);
   - links to the docs.

   Under 150 lines. Every command in it must run on the current integ build; check each one in a test.
2. **`integrations/claude-code/skills/ailc/SKILL.md`**: a Claude Code skill that tells an agent:
   - when to reach for ailc (it profiled a slow pure-Python function);
   - how to build;
   - how to read the `--json` diagnostics and apply their fixes;
   - how to confirm that the output still matches CPython.

   Also write an equivalent `AGENTS.md` snippet for other agents (Codex, Cursor).
3. **`integrations/mcp/`**: a minimal stdio MCP server in Python, with these tools:
   - `ailc_check(path)`: diagnostics as JSON;
   - `ailc_build(path)`: build, and return the artifact path or the diagnostics;
   - `ailc_explain(path, function)`: why a function stays on CPython.

   It has no network access and no dependencies beyond the standard library plus the `mcp` package, which is
   optional and imported lazily. Include tests that run the tools on 3 example files.
4. **docs/AGENT_GUIDE.md**: a worked example. An agent finds a slow function, builds it, gets a refusal, applies the
   suggested fix, and gets a speedup. Every number in it comes from a real run recorded in the doc.

## Rules

- Do not invent features. If a command or flag in the plan above does not exist yet (for example `--why`), say so in
  the report, leave it out of the docs, and add a 2-hour task text for it.
- Work under `ulimit -v 2500000`.

## Report

- the files added;
- which planned commands exist and which are missing;
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
