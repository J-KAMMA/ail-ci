Lane: vibe

# vibe3: the main judge from now on: re-run the vibe benchmark on current integ, add Go and app-like tasks

Time budget: 240 minutes. Commit and push after each sub-step. Follow `.agent/` rules. No compiler change.

**Why (owner, 2026-11-09):** the goal is "the standard language of the vibe-coding-native era". AIL is no longer judged
by running existing Python libraries faster than PyPy (wedge3: 0/328 functions native, owner shrank that line). It is
judged by: when an AI writes a NEW program, does AIL reach a correct program more often, in fewer fix rounds, with
zero silently wrong results, and run it at Rust-level speed? vibe1 (`lab/vibe/RESULTS.md`, 2026-11-06) found correct
rate Rust 100%, Python 84%, AIL 64%. Since then err1-err3, fe1 and many front-end fixes landed. Report losses plainly.

**Reuse** `lab/vibe/run.py` and `lab/vibe/AIL_FOR_AI.md` (improve AIL_FOR_AI.md only if a measured failure shows a
missing fact; keep it at most 40 lines and list every change). Same model and settings for every language; say which.
Use the free model this worker runs on through the installed CLI; no API keys or secrets. If no model CLI can be
called, stop after the harness changes and say so.

**Languages:** python (CPython 3.12), rust (rustc -O, std only), go (go build, std only; install Go on the runner if
missing), ail (current integ, compiling the plain Python the AI wrote).

**Tasks:** the vibe1 tasks, plus 10 new app-like tasks in `lab/vibe/tasks2/` that you write (spec.md, gen.py with
public and hidden cases, CPython reference): the kind of code people vibe-code, using classes, dicts, string
parsing, sorting with keys, small state machines, error handling, a CLI over a text file. Hidden cases must probe
boundaries the spec does not mention (empty input, large counts, int64 edges, unicode). Do not show reference
solutions to the AI.

**Numbers** (`lab/vibe/RESULTS3.md`, `lab/vibe/results3.json`), per language, over 3 seeds (cut to 2 if short, say so):
1. correct % (all public + hidden cases), 2. median fix rounds (max 5) and gave-up count, 3. silent-wrong count and
loud-stop count on hidden cases, 4. loop wall seconds and final program run time, 5. for ail: typed / general /
refused final programs, the 10 most common compiler messages and whether the AI fixed each from the message alone.
6. A delta table vs vibe1 on the old tasks, and every AIL failure classified: refused construct / message not
actionable / runtime stop / wrong output.

Base: `origin/integ`. Files you may create or edit: `lab/vibe/*` only (new files plus run.py and AIL_FOR_AI.md).

## Sub-steps
1. (60 min) Go support + tasks2 with references verified by CPython; dry run 1 task x 4 languages x 1 seed. Commit, push.
2. (130 min) Full run; commit, push after each language.
3. (30 min) RESULTS3.md: tables above and a 5-line verdict naming the top 3 things that cost AIL correct programs.
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
