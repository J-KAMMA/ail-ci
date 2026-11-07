# layout1: why AIL's typed builds miss cache more than C, and what flat layout would save

Lane: roof

Measurement and design only. Do not change the compiler.

## Background
lab/energy/RESULTS.md (energy1) found that 99.8% of the model energy typed AIL spends beyond C is
LLC misses, not instructions. Examples: tree_fold has 106.1M LLC misses against C's 20.0M, and
berth_sim and ticket_audit also show large deltas. Removing checks is worth millijoules; memory
behaviour is worth joules (and wall time).

## Do
1. For tree_fold, berth_sim, ticket_audit, echo_pack and ledger_bin, read the C that AIL emits for
   typed.py next to the hand-written main.c in the compare programs. List concretely how each hot
   data structure is laid out in memory in both. Look for:
   - object headers and refcount words;
   - pointer-per-element lists against inline values;
   - separately allocated nodes against an arena or array;
   - padding;
   - temporaries that are copied;
   - a dict or set where C uses an array.
2. Measure with cachegrind (same geometry as lab/roof and lab/energy: L1d 32K, L2 512K, LLC 32M), per
   function or per data structure where possible: D1 and LL misses and bytes touched. Attribute
   AIL's extra misses to the layout causes from step 1.
3. For the top 2-3 causes, hand-edit a copy of the emitted C to the flat layout (outside the
   compiler; files under lab/layout/). Re-measure misses, instructions and wall time (best of 5,
   same runner), and check that the output is byte-identical to CPython.
4. Rank the candidate compiler changes by measured saving. For each one, give:
   - which programs it applies to;
   - the semantic conditions under which it is safe (aliasing, mutation, escape), in docs/SPEC terms;
   - RSS and binary-size effect;
   - an Amdahl bound from the measured share.

   Do not project a gain that you have not measured on the hand-edited C.

## Output
- lab/layout/RESULTS.md: tables plus the ranked list.
- Scripts in lab/layout/; raw data in lab/layout/data/.
- Ready-to-queue task texts for the top candidates. Each is an implementation step of 2 hours or
  less, with its own guard test.

## Done when
RESULTS.md answers, with numbers, "which layout change removes the most of AIL's extra cache misses,
and is it safe".

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
