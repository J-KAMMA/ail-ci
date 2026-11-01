**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change does:** adds the stdlib-reach census, lowers saved raising generator expressions to module-level generator functions with by-value captures (and routes the default build there), tightens those captures, and also includes an unrelated `ail_modules.py` import-fallback relaxation and a `nestfn.py` skip.

**Verified**
- Census: reran the nine generator-expression modules on HEAD; each now reaches the next blocker, matching `STDLIB_REACH.md`.
- `update_manifest.py --check` passes.
- `test_ail_stdlib_reach`, `test_ail_pre116`, `test_ail_pre211`, `test_ail_safetynet`: 4 modules, 0 failed.
- Base used `/tmp/basework` (`work` = `fc01930`); `/tmp/base` was stale at `f5cdafe`.

**Defects**
1. Rebinding on a later loop iteration is not detected. The safety check in `pyboxed2.py:13168-13181` accepts a `for` target that is bound before the generator, but each iteration changes the CPython cell.
   - `p_loop_after`:
     ```python
     def main():
         gens = []
         for x in [1, 2, 3]:
             gens.append((10 // x for _ in [0]))
         print([list(g) for g in gens])
     main()
     ```
     Expected `[[3], [3], [3]]`; actual `[[10], [5], [3]]` on both builds. Base refuses by name.
   - `p_while_after` (`x = i + 1` before the generator each iteration) expected `[[5], [5]]`, actual `[[10], [5]]`, both builds. Base refuses.
   - `p_loop_two_targets` expected `[[1], [1]]`, actual `[[3], [1]]`, both builds. Base refuses.

2. A generator in a default argument is analysed as if it were in the function body, so a parameter with the same name hides the real enclosing scope and the capture is snapshotted too early.
   ```python
   def main():
       x = 100
       def f(x=1, g=(10 // x for _ in [0])):
           return list(g)
       x = 7
       return f()
   print(main())
   ```
   Expected `[1]` (CPython reads the enclosing cell at consumption); actual `[0]` on both builds. The same happens when `x` is a module global rebound after the `def`. Base refuses by name.

**Pre-existing (unchanged on `work`)**
- `p_loop_append_after` (non-raising body, generators escape a loop): expected `[[4], [4]]`, actual `[[2], [4]]` on base and HEAD.
- `p_global_only` (nested `global` read): expected `[1]`, actual `[2]` on base and HEAD.

**Report claims**
- “Added those cases to `test_ail_stdlib_reach.py`”: false; the added test file contains only the 8 original test methods and none of the extra probe cases.
- “A captured local … is not rebound/deleted at or after creation” and “definitely-bound plain assignment”: false for loop targets and repeated assignments shown above.
- Lab/compare C byte-identity, the other 5 test modules, the 14 still-building modules, and speed were not rechecked.

VERDICT: FIX
[cost $0.0342, opencode tokens {"total": 1802298, "input": 79444, "output": 6285, "reasoning": 22361, "cache.write": 0, "cache.read": 1694208}]
    tool time: bash 4.3 min
        134s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_
         35s bash   cd /tmp/stdlib_census && date && timeout 1800 python3 census9.py 2>&1 | tail -15; date
         25s bash   cd /tmp/rprobes && date && for p in p_loop_after p_loop_inline p_global_nested p_default_arg p_default_local p
         21s bash   cd /tmp/rprobes && cat > p_global_only.py <<'EOF' x = 1 def main():     x = 2     def inner():         global 
         13s bash   cd /tmp/rprobes && cat > p_default_collide_global.py <<'EOF' x = 100 def main():     def f(x=1, g=(10 // x for
         11s bash   cd /tmp/rprobes && date && for p in p_loop_after p_while_after p_loop_two_targets p_default_stale p_default_st
         11s bash   cd /tmp/rprobes && date && for p in p_loop_after p_loop_inline p_global_nested p_default_arg p_default_local p
          7s bash   cd /tmp/rprobes && cat > p_default_stale.py <<'EOF' def main():     x = 100     def f(x=1, g=(10 // x for _ in


--- ORIGINAL TASK ---
**Coverage: CPython stdlib modules.** /home/bluec/pub/modsys_census is not available here, so: for the pure-Python stdlib modules of the CPython 3.12 that is installed, build `import X; print('ok')` with X copied next to main.py and record which build and which refuse and why (first refusal message), in docs/design/STDLIB_REACH.md (counts by reason). Then fix the single reason that blocks the most modules. Acceptance: compare stdout and exit code with CPython on your own boundary probes; the generated C of the 10 lab/compare tasks must stay byte-identical unless the task is about them; add tests (register new modules in tests.d), run them plus test_ail_safetynet, run `python3 tools/update_manifest.py`, commit.

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
