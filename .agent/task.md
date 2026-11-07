Lane: pyreachdesign

# pyreach9: why plain `.py` still falls to the general path after pyreachs1-8, and the next steps (census + design only)

Time budget: 120 minutes. Commit and push after each sub-step. Follow `.agent/` rules (no regressions, CI first).
Do not change the compiler. Output: `lab/pyreach9/*` and `docs/design/PYREACH_NEXT.md`.

**Why (owner, 2026-11-07):** roof1 (`lab/roof/RESULTS.md`) measured 6 of 8 compiling compare `main.py` builds on the
general path at 1.6x-143x C, while the annotated `typed.py` runs at 1.31x C (median); getting plain Python onto the
typed path is worth 12-122x on those programs, more than every hardware feature combined. vibe1
(`lab/vibe/RESULTS.md`) found every AI-written AIL program on the general path (0 typed / 8 general). The owner chose
to work on this first.

## Census (`lab/pyreach9/RESULTS.md`), on current `origin/integ`
Corpora: the 10 compare `main.py`; the AI-written programs in `lab/vibe/programs` (all languages' Python versions,
since an AI writes plain Python); 100 `corpus/gdev` programs (fixed seed). For each program: path (typed / general /
refused), and for every general or refused program the full list of reasons (not only the first: use `--strict` and
the compiler's explain output, or iterate by locally patching the source in a throwaway copy until it types, noting
each blocker in order). Rank reasons by "programs that would become typed if this reason alone were removed" (count
programs whose only remaining blocker is it, and programs it appears in). Note which reasons are AI-typical (from the
vibe programs) vs corpus-typical.

## Design (`docs/design/PYREACH_NEXT.md`)
For the top 5 reasons: what Python semantics must hold (CPython-identical output, or a loud refusal by name; never a
silent difference), which compiler file/function decides it, the change, the proof obligations, and the expected
programs moved (from the census). Split into implementation steps of at most 2 hours each, with files, tests,
`.agent/cmp.sh` probes, and the number each moves, written as ready-to-queue task text at the end. Mark any step that
changes language semantics as "needs owner decision" with the options.

## Sub-steps
1. (70 min) Census. Commit, push.
2. (50 min) PYREACH_NEXT.md. Commit, push.

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
