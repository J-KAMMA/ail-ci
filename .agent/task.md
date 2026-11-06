Lane: vibe

# vibe1: the vibe-coding benchmark: the same AI writes the same tasks in Python, Rust and AIL; compare correct-program rate, fix rounds and silent-wrong count

Time budget: 200 minutes. Commit and push after each sub-step. Follow `.agent/` rules. No compiler change.

**Why (owner, 2026-11-07):** AIL is meant for vibe coding (docs/ROADMAP.md, "What AIL is for"). Its headline number is
not raw speed but: when an AI writes a program, does AIL get it to a correct program more often, in fewer fix rounds,
and with fewer silently wrong results than Python or Rust? Report losses as plainly as wins.

**Numbers this produces** (`lab/vibe/RESULTS.md`, `lab/vibe/results.json`), per language (python = CPython,
rust = rustc -O, ail = AIL compiling the plain Python the AI wrote) and per task, over 3 seeds:
1. **Correct:** passes every public and hidden case of the task (the tasks' own `gen.py` / CPython reference).
2. **Fix rounds:** rounds used (max 5) until the program passes the public cases; "gave up" if never.
3. **Silent wrong:** the program passed all public cases the AI saw, printed output with exit code 0 on a hidden
   case, and that output was wrong. This is the number AIL is meant to reduce: AIL's loud stops (overflow,
   out-of-range) should turn some of these into visible errors. Also count "loud stop on a hidden case" separately.
4. **Wall seconds of the loop** (compile + run time summed over rounds), and the final program's run time.
5. For ail: how many final programs reached the typed path vs general vs refused, and the 10 most common compiler
   errors/notes the AI received, with whether the AI managed to fix each from the message alone.

**Harness** (`lab/vibe/run.py`): for each (task, language, seed): prompt = the task's `spec.md` + one short language
note (python: "Python 3.12"; rust: "Rust 2021, std only"; ail: `lab/vibe/AIL_FOR_AI.md`, at most 40 lines you write:
"AIL is Python syntax; annotations help; it compiles to a native binary; what it refuses and how errors look").
Ask for one file. Build/run on the public cases; on failure send back the compiler/runtime error or the first diff
and ask for a fixed file; up to 5 rounds. Then run hidden cases. Record every round in `results.json` (prompt and
reply lengths, errors, pass/fail), without storing secrets.

**Model:** use the free model this worker itself runs on, through the CLI already installed on the runner (e.g.
`opencode run -m <model>`), non-interactive, with a per-call timeout. Use the same model and settings for all three
languages and say which in RESULTS.md. Do not add API keys or secrets; if no model CLI can be called from the job,
stop after writing the harness and say so (the Claude session will run it).

**Tasks:** the 10 tasks in `lab/compare/tasks/` (and `lab/compare_cand/tasks/csv_rollup` if it exists). Do not show
the AI the existing solutions in `lab/compare/src/`.

Base: `origin/integ`. Files you may create or edit, and no others (all new): `lab/vibe/*`. Do not edit compiler files,
`lab/compare/`, or workflows; put a proposed repeatable workflow at `lab/vibe/vibe.yml` (not under `.github/`).

## Sub-steps
1. (50 min) Harness + AIL_FOR_AI.md; dry run on 1 task x 3 languages x 1 seed. Commit, push.
2. (100 min) Full run (cut seeds to 2 if the budget runs short, and say so). Commit, push after each language.
3. (30 min) RESULTS.md: the per-language table (correct %, median fix rounds, silent-wrong count, loud-stop count,
   loop seconds), per-task detail, the AIL error table, and a 5-line verdict. Commit, push.

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
