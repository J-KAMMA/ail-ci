# setord2: set order — match CPython where its order is fixed; do not refuse where CPython's own order is random

Lane: setord

Start from setord1's branch, `job-setord1-11080325`. Its review was ACCEPT, but the gate run on PR
#454 was red. setord1 refuses order-revealing iteration of sets too broadly. That broke existing
correct programs and AIL's own stdlib:

- difflib.py:189;
- pprint;
- examples life.py;
- test_ail_fuzz81 (set.pop);
- test_ail_re_value;
- test_ail_pyreach_dictrows;
- test_ail_bigint (tuple output order).

## Rule (the AIL principle is "CPython-identical, or a loud refusal; never a silent difference")

- **Sets whose elements hash deterministically in CPython:** int, bool, None, float, and tuples of
  these. CPython's iteration order is fixed by its hash-table layout, so emulate it exactly:
  - the same table size and growth;
  - the same probing (perturb);
  - the same deletion dummies.

  Then iteration, `pop()`, `repr()` and `list(s)` match CPython byte for byte. Where emulation is not
  implemented for a case, refuse by name (as setord1 does) instead of printing a different order.
- **Sets that contain str or bytes:** CPython's order is random per run (PYTHONHASHSEED). No single
  order is "the CPython order", so AIL's fixed order is one valid CPython run. Do not refuse these;
  keep a deterministic order.
  - Document it in docs/spec as "iteration order of str/bytes sets is unspecified (CPython varies it
    per run); AIL's order is deterministic".
  - Tests that compare against CPython must not depend on that order.
- **Mixed sets** follow the stricter rule of their element kinds.
- **frozenset** follows the same rules.

## Work

1. Start a branch from `origin/integ` and bring setord1's work across.
2. Implement the rule above on both the typed path and the general path.
3. Re-run all the modules that failed at the gate, one after another under `ulimit -v 2500000`:
   - test_ail_fuzz81
   - test_ail_std_difflib
   - test_ail_std_pprint
   - test_ail_pyreach_dictrows
   - test_ail_re_value
   - test_ail_examples_algos
   - test_ail_bigint
   - test_ail_setorder

   Add cases to test_ail_setorder covering:
   - int sets with collisions, deletions and growth, comparing iteration, `pop()` and `repr()`
     against CPython;
   - str sets, which must build and run without refusal.
4. Report which kinds are emulated, which are refused, and the test results with times.

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
