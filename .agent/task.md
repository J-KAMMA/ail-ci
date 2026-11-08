# wedge2: let hybrid-native functions index lists and dicts

Lane: hybrid
Needs: wedge1

wedge1 (lab/wedge/, 15 modules) found that the hybrid build sends only 24.7% of functions native, so the hybrid runs
at CPython speed. The main gate is `_unsafe_body` in AIL_CURRENT/ail_cpython_hybrid.py (around :309, called around
:571). It returns "indexing can raise" for **any** `Subscript`, so any function with `a[i]` stays on CPython.

## Goal

A native function may index when a failure behaves exactly like CPython:
- an out-of-range index raises IndexError;
- a missing key raises KeyError;
- in both cases the message and the exception type seen by the Python caller match CPython.

There are two ways to get there; do whichever is smaller and correct:
- propagate the native exception across the boundary as the same Python exception;
- or prove the index is in range (loop bounds of `range(len(a))`, and similar), and keep refusing the rest by name.

## Rules

- Never print a different result from CPython. A case that is not proven or propagated stays on CPython, with a
  reason the user can see. wedge1 found that 54 of 73 refusals were silent; this job makes them visible:
  `ailc ext --why` or the build log names every refused function and its reason.
- Do not change the default (non-hybrid) build path.

## Work

1. Start a branch from `origin/integ`.
2. Implement the change.
3. Add tests in the hybrid test modules, each comparing against CPython:
   - an in-range index;
   - IndexError;
   - a negative index;
   - KeyError;
   - a dict hit;
   - mutation through an index;
   - a nested `a[i][j]`.
4. Re-run the lab/wedge measurement before and after the change, under `ulimit -v 2500000`. Use the ratio
   convention hybrid_time/cpython_time, and fix measure.py's label if wedge1 has not already fixed it.
5. Report:
   - the native share before and after;
   - the speed ratio per module;
   - the top remaining refusal reasons;
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
