Lane: rterrfix

# recstop1: deep recursion must stop loudly, never with a bare SIGSEGV (safety hole found by safestop1)

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap). Stop on any wrong output against CPython.

**Number this moves:** `lab/safety/stops/RESULTS.md` (from job safestop1, branch `job-safestop1-*`; cherry-pick its
files if they are not on integ yet). Today `06_rec_direct.py`, `07_rec_mutual.py` and `08_rec_method.py` crash on the
**general** path with signal 11 and nothing on stderr. The target: all three exit nonzero, and the last stderr line
starts with `RecursionError:`, in every mode.

Owner rule: AIL matches CPython or stops loudly by name; it never dies silently. A segfault prints nothing, so it
breaks the 0.1 safety claim.

Do **not** change how deep recursion may go. `09_rec_deep5000.py` (depth 5000, which CPython refuses at its default
limit 1000, while AIL completes) is a separate owner decision. Leave it as is and keep its row in RESULTS.md.

## Steps

1. **Reproduce (10 min).** Build the three programs with `AIL_UNIFIED_FORCE=1` (the general path) and in default mode.
   Record the exit signal. Find why the typed path already raises `RecursionError` (a depth counter or a stack check
   in the typed emitter or runtime) and why the general path lacks it.
2. **Fix (50 min).** Give the general path the same check the typed path uses, so `RecursionError` is raised from
   AIL's own exception path, catchable like CPython's. If that cannot fit, install a last-resort guard: a
   `sigaltstack` and `SIGSEGV` handler that tells a stack overflow (fault address near the stack guard) from other
   faults. On a stack overflow it prints `RecursionError: maximum recursion depth exceeded (stack overflow)` and
   exits 1; on any other fault it re-raises the signal. Keep the cost small: run icount on 3 compare-lab programs
   (tools/icount.c), with no regression over 0.5%.
3. **Verify (20 min).**
   - Rerun the safestop suite: 06, 07 and 08 must show `match` or `stop-differs` (a loud stop), with 0 crashes.
   - The other modes and rows must be unchanged.
   - Run the test modules of the files you touched.
   - Run `python3 -m compileall -q -j 0 AIL_CURRENT tools`.
   Report the counts before and after, and the icount ratios.

## Owner decision (2026-11-05)

- Deep recursion within the real stack (e.g. depth 5000) keeps working: AIL does NOT emulate CPython's default recursion limit of 1000. Record this as a documented difference (DIFFERENCES.md and docs/LIMITATIONS.md), and classify `09_rec_deep5000.py` in RESULTS.md as "documented difference", not silent-wrong. Only a real stack exhaustion must stop loudly with RecursionError.

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
