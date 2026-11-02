**Specialization: beat C on tally_lang with an opcode-specialized evaluator (owner approved 2026-11-02).** docs/design/BEAT_C.md ranks this (mechanism C) as the only single mechanism whose priced gain closes its gap with C: a bound of 2.86×, about 1.74× at 40% reach, against the 1.49× needed. The cheap `popcnt` edit measured only about 1.03×. So the win needs the real mechanism, and nothing so far proves it.

**Step 1, profile first (the speed-claims rule).**
- Profile `tally_lang`'s AIL binary with `perf` or callgrind instruction counts, and with tools/icount.c where it fits.
- Name the generic paths that dominate: the dispatch, the boxed values, the dict/str lookups and the callbacks.
- State each one's measured share and the Amdahl bound before you write code.

**Step 2, implement.** Specialize the hot generic paths in the generated C and the runtime. Use what the front end already knows: the types, the constant opcodes and the callback targets. Examples:
- an opcode-specialized evaluator (a switch on known opcodes, with no generic dispatch);
- dict and str routines for the known key types;
- direct calls in place of callbacks.

Keep it general: these are compiler rules that fire wherever their conditions hold, not special cases for tally_lang. Also apply them to `echo_pack` if its hot path matches.

**Step 3, prove the output is unchanged (the optimization-adoption rule).**
- stdout and the exit code must be identical on every public and hidden case of all 10 lab/compare tasks and on lab/corpus;
- the full test suite must pass;
- the specialized and generic paths must agree on boundary inputs: empty, one element, the largest sizes, unusual keys.

**Step 4, measure.** Measure every task affected:
- instruction counts and the median of 5 wall runs;
- RSS, binary size, compile time and build disk, before and after.

Any task that regresses beyond noise must be reported. Write docs/design/SPEC1.md with:
- the measured share against the bound against the gain;
- the tally_lang and echo_pack results against C;
- the code size cost.

Rules:
- If the measured gain on tally_lang is below 1.2×, stop and report, and do not land the code. The doc and the measurement are still the deliverable.
- New package files need the right manifest flag.
- Commit and push after each step, and keep the whole job under 4.5 hours.

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
