Lane: codegen

**Land spec1's two safe, zero-cost speedups in the code generator (owner approved 2026-11-03).**

spec1 found two specializations that keep every safety check. It measured them by hand-editing the generated C of `tally_lang`:
- the popcount idiom (about 1.03×);
- a shared span check for parallel lists (about 1.05×).

Together they gave about 1.06–1.09×, with no cost in binary size, RSS or compile time. The details, the profile and the prototype edits are in `docs/design/SPEC1.md`, its `DEVLOG.md` entry and `lab/beatc/results/spec1-*`. Read them first.

New rule from the owner: a gain may be small if it costs nothing. Land it when the instruction count drops and nothing else gets worse.

1. **The generator change.** Make the code generator (AIL_CURRENT) emit both shapes wherever their preconditions hold. Every bounds and recursion check must stay: no silent change, and the same error at the same place when an index is out of range.
2. **Probes.** Add one probe each for the shapes, the edge cases included:
   - an empty list;
   - the last index;
   - one past the end, which must still raise;
   - lists of different lengths sharing a loop;
   - negative values for popcount.

   Compare with CPython through `~/tools/cmp.sh`.
3. **Measure with instruction counts** (tools/icount.c, or valgrind if it exists; not wall time, which is noisy on runners):
   - `tally_lang` on its compare-lab perf case;
   - all 10 lab/compare tasks.

   Report, per task, the instructions, binary bytes, RSS and compile time, before and after.

Commit and push after each sub-step.

**Adopt only if:**
- `tally_lang`'s instructions drop by at least 3%;
- no compare-lab task gets worse in instructions (by more than 0.2%), binary bytes, RSS or compile time;
- all 76 tally cases and every probe match.

Otherwise stop, revert the generator change, and record the numbers in DEVLOG.

**Stop rule:** if a shape needs a check removed to pay off, do not land it.

Time budget: 80 minutes.

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
