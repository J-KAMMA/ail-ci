Lane: frontend

# pyr3fix: fix what pyreachs3c broke, the CPython-hybrid acceleration and the collections refusal names (integ is red)

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** failing integ test modules. pyreachs3c broke these four, which were green before it merged:
`test_ail_cpython_hybrid`, `test_ail_prog2`, `test_ail_prog21` and `test_ail_collections`. The target is all four green.

Base: `origin/integ`. pyreachs3c is commit 805ce9ba (merged in PR #371, cand-1104144602). It was the only job in
that candidate. A culprit run applied each integ candidate alone on top of d1afe1f8 (the last green commit). These
modules passed on everything up to #370 and fail from #371 on, so pyreachs3c is the cause.

The same commit also broke the call-site diagnostics: `test_ail_sdk`, `test_ail_source_check`,
`test_ail_argument_type_details` and `test_ail_check_repair_context`. Job `sdkdiag1` owns those, and it runs before
this one in the same lane. If sdkdiag1's branch has merged, build on it. If it has not, rebase on its branch
`job-sdkdiag1-*` when that branch has commits. Do not redo its work.

## What broke (from the culprit log)

pyreachs3c added a refusal: "'x' is annotated T in the source, but the caller also supplies U; refusing rather than
silently choosing one". It fires at the function declaration, before other checks. As a result:
- `test_ail_collections` `test_refusals_are_named [ctr_subtract]` now gets that refusal ("'xs' is annotated slist ... caller also supplies str")
  instead of the expected refusal that names `subtract`.
- `test_ail_cpython_hybrid` `test_accelerated_and_fallbacks`: `'join'` is no longer accelerated
  (accelerated = add1, isbig, total, half, dflt, mul, echo).
- `test_ail_prog2` `test_modulo_by_a_constant_is_accelerated`: `state_at` is no longer accelerated (only `down`).
- `test_ail_prog21`: `label` is no longer accelerated, and `rejected['fmt']` is no longer
  'a call can raise or have side effects'.

In hybrid mode, a function that fails this new check should fall back only when a caller really passes the
mismatched type. A function that no caller passes a mismatched type must stay accelerated, as before.

## What to do

1. **Reproduce (10 min).** Run the four modules on `origin/integ` and on `805ce9ba^`. Record the pass counts.
2. **Fix (50 min).** Keep the new refusal's intent: never silently choose between the annotation and the caller's
   type. Restore the previous behaviour for the cases above. Where the new check misreads the callers (for example
   a str passed to a different overload, or a default argument), fix the analysis. Do not just reorder messages to
   satisfy the tests. Do not edit the expectations of these four tests.
3. **Verify (20 min).**
   - the four modules green;
   - the pyreach tests that pyreachs3c added still green (`git show --stat 805ce9ba` lists them);
   - `python3 -m compileall -q -j 0 AIL_CURRENT tools`.
   Report each module's pass count before and after.

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
