**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change really does:** adds typed lowering and runtime helpers for `statistics.quantiles`, `covariance`, `correlation(method="linear")` and weighted `fmean`, adds 12 lab programs/RESULTS and a registered test, and moves two refusal tests to `linear_regression`. This matches the report except that the new float product-sum helper is not numerically equivalent to CPython's `math.sumprod` on large magnitudes.

**Claims checked**
- Computed `correlation` method refused by name: **verified** (`test_ail_std_statistics` passes; code refuses non-constant method).
- Exact int weighted `fmean`: **verified** (`/tmp/rprobes/c_fmean_int_big.py` matches, including `9007199254740994.0`).
- 10/12 build and match CPython: **verified** (`test_ail_std_statistics` passed).
- Targeted tests on HEAD: **verified** — `test_ail_std_statistics`, `test_ail_genlib`, `test_ail_stdlib_batch4`, `test_ail_safetynet` all pass (batch4 900s under a loaded runner).
- Manifest `--check`: **verified**.
- 10/10 compare C byte-identical: **unverified** (spot-checked one non-statistics program, C identical).
- “Error messages follow CPython”: **false** for methods needing `repr` quoting (defect 2).
- “Product sum follows `math.sumprod`”: **false** when float products or Dekker splits overflow (defect 1).

Probes: `c_fmean_int_big`, `e_cov_float`, `f_alias_mutation`, `f2_cov_args`, `i_fmean_errors`, `b2_q_edges`, `e2_q_float`, `h_no_feature` all matched CPython. Loud int64 `OverflowError` (`d_fmean_overflow`, `g_q_int_overflow`) is the documented/required behaviour, not a defect.

**Pre-existing:** none observed. Forced-general refusal of the new names is a named refusal, not a defect.

**Unverified:** the “before” counts in RESULTS.md; the full 10/10 compare-C claim; `test_ail_files`/`test_ail_corpus_findings3` (not part of this review).

**Defects**

1. `sumprod_floats` returns `nan` where CPython returns finite values (runtime, `strt.py:591`). The unscaled Dekker split (`split = 134217729.0`) overflows for `|x| > ~1.3e300`, and ordinary products overflow near `1e155`.
   Probe `/tmp/rprobes/k_split_overflow.py`:
   ```python
   x = [1e301, 2e301, 3e301]
   y = [1e-300, 2e-300, 4e-300]
   print(statistics.covariance(x, y))
   print(statistics.fmean(x, weights=y))
   ```
   Expected (CPython): `15.0` and `2.4285714285714285e+301`; actual: `nan` and `nan`.
   Also `/tmp/rprobes/j_float_overflow.py`: CPython prints `inf` for `covariance`/`fmean`, AIL prints `nan`.

2. Unknown-method error text is built by concatenation instead of `repr` (`strt.py:541,570,635`).
   Probe `/tmp/rprobes/c2_q_quote.py`:
   ```python
   try:
       print(statistics.quantiles([1, 2, 3], method="a'b"))
   except ValueError as exc:
       print("quote:", exc)
   ```
   Expected (CPython): `quote: Unknown method: "a'b"`; actual: `quote: Unknown method: 'a'b'`.
   Same for `correlation(..., method="a'b")` (`/tmp/rprobes/l_corr_quote.py`).

3. Minor task deviation: `lab/stdlib/statistics/11_geometric_harmonic.py` is 14 lines, below the required 15–60.

VERDICT: FIX

1. `sumprod_floats` must avoid overflow in the Dekker split/product (scale/normalize, as CPython's `math.sumprod` does) so finite CPython results are not `nan`; probe `/tmp/rprobes/k_split_overflow.py` (expected `15.0` / `2.4285714285714285e+301`, actual `nan` / `nan`).
2. Use `repr` for the method in the unknown-method errors; probe `/tmp/rprobes/c2_q_quote.py` (expected `Unknown method: "a'b"`, actual `Unknown method: 'a'b'`).
3. Make `11_geometric_harmonic.py` at least 15 lines.
[cost $0.0383, opencode tokens {"total": 2092100, "input": 77960, "output": 11201, "reasoning": 23163, "cache.write": 0, "cache.read": 1979776}]
    tool time: bash 28.1 min
        703s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 --timeout 700 tes
        240s bash   sleep 240; tail -6 /tmp/batch4.log; ps -o pid,etime,cmd -C python3 | grep "par_check.py -j 1" | head; date
        180s bash   sleep 180; tail -4 /tmp/batch4.log; ps -o pid,etime,cmd -C python3 | grep "par_check.py -j 1" | head; date
        120s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && nohup setsid timeout 1300 python3 ../tools/par_check.py -j 1 --ti
        120s bash   sleep 120; tail -4 /tmp/batch4.log; ps -o pid,etime,cmd -C python3 | grep "par_check.py -j 1" | head; date
         90s bash   sleep 90; tail -4 /tmp/batch4.log; ps -o pid,etime,cmd -C python3 | grep "par_check.py -j 1" | head; date
         60s bash   sleep 60; cat /tmp/batch4.log 2>/dev/null | tail -5; ps -o pid,etime,cmd -C python3 | grep par_check | head; d
         43s bash   cd /tmp/rprobes cat > b2_q_edges.py <<'PY' import statistics   def main() -> None:     xs: list[int] = [1, 2, 


--- ORIGINAL TASK ---
**Coverage: make real programs that use the CPython stdlib module `statistics` build and print exactly what CPython prints.**

1. Write 12 small realistic programs, each 15–60 lines, that use `statistics` the way typical code does: its most common functions and classes, the common argument forms and keyword arguments, and its edge cases (empty inputs, errors that the program catches). Put them in lab/stdlib/statistics/.
2. Build each one in the default mode (`ail_chatgpt.py compile X.py --syntax python`). Record the result for each: typed / general / refused, with the first refusal message, in lab/stdlib/statistics/RESULTS.md.
3. Fix the reasons, starting with the one that blocks the most programs, until at least 9 of the 12 build. Each built program must match CPython's stdout and exit code. Fix the compiler, runtime or prelude, never the programs.
4. A reason that needs a big new feature is out of scope for this task: leave it, and write it in RESULTS.md as a follow-up with the exact refusal text.

Rules:
- Never wrap ints silently. Default ints are int64, and overflow stops loudly.
- The generated C of the 10 lab/compare tasks must stay byte-identical.
- Add the passing programs as a test (a new test_ail_std_statistics.py registered in tests.d), and compare them with CPython in the test.
- Run that test plus test_ail_safetynet, run `python3 tools/update_manifest.py`, and commit.

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
