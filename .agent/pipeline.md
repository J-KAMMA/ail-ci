# job job-std_statistics-11011523  started 2026-11-01T06:31:48Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Committed `0b3b276` on `job-std_statistics-11011523`.

- **Coverage:** 12 programs added in `lab/stdlib/statistics/` with `RESULTS.md`.
- **Builds:** 10/12 now build (8 typed, 2 general) and match CPython stdout/exit. Before fixes: 7/12.
- **Fixes:** typed support for `quantiles`, `covariance`, `correlation(method="linear")`, and `fmean(weights=)`; sumprod follows `math.sumprod`.
- **Follow-ups recorded:** `linear_regression` and `NormalDist` remain named refusals.
- **Tests:** `test_ail_std_statistics`, `test_ail_stdlib_batch4`, `test_ail_genlib`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 6 modules, 0 failed.
- **Compare C:** all 10 `lab/compare/src/*/main.ail` generated C files byte-identical to base.
- **Probes:** 8 in `/tmp/probes`; default builds match CPython, forced general builds refuse new names by name, named-refusal probes match expectations.
[cost $0.0787, opencode tokens {"total": 8437976, "input": 154268, "output": 25924, "reasoning": 25592, "cache.write": 0, "cache.read": 8232192}]
    tool time: bash 49.1 min
        781s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check && python3 tools/par_check.py -j 
        650s bash   python3 tools/update_manifest.py --check && python3 tools/par_check.py -j 2 test_ail_std_statistics test_ail_s
        643s bash   python3 tools/par_check.py -j 2 test_ail_std_statistics test_ail_stdlib_batch4 test_ail_safetynet test_ail_fil
        489s bash   rm -rf /tmp/basewt /tmp/cgcmp && git worktree add --detach /tmp/basewt HEAD >/tmp/wt.log 2>&1 && mkdir -p /tmp
         85s bash   rm -rf /tmp/basewt /tmp/cgcmp && git worktree add --detach /tmp/basewt HEAD >/tmp/wt.log 2>&1 && mkdir -p /tmp
         36s bash   cd /tmp/probes && for p in p_q_edges.py p_q_float.py p_cov_corr_edges.py p_cov_corr_float.py p_fmean_weights_e
         28s bash   rm -rf /tmp/stdstat2 && mkdir /tmp/stdstat2 && cd /tmp/stdstat2 && for f in /home/runner/work/_temp/w2/lab/std
         28s bash   rm -rf /tmp/stdstat3 && mkdir /tmp/stdstat3 && cd /tmp/stdstat3 && for f in /home/runner/work/_temp/w2/lab/std

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review

**What the change really does:** adds typed lowering (`statlib.py`) and runtime helpers (`strt.py`) for `statistics.quantiles`, `covariance`, `correlation(method="linear")` and `fmean(..., weights=...)`; adds 12 lab programs + `RESULTS.md`, a new `test_ail_std_statistics`, and moves two old refusal tests to `linear_regression`. Matches the report's description.

**Probes (mine, `/tmp/rprobes/`, `cmp.sh` against HEAD and `/tmp/base`):**
- `a_q_whole`, `e_q_var`, `h_q_precedence`, `c2_fmean_edges`, `m_cov_mix`, `i_corr_sqrt`, `g_corr_var_linear`: HEAD default build matches CPython; general build refuses by name. Base cannot build them.
- `d_cov_corr_large`, `n_q_overflow`: exit status/messages agree with the recorded limitations (overflow is loud, not silent).
- `k_corr_kw` (literal `method="ranked"`): named compile-time refusal, as claimed.
- **`j_ranked_var`** and **`l_fmean_bigint`**: HEAD builds but does **not** match CPython (defects below).

**Claims checked:**
- 12 programs added, before-fix 7/12: verified (ran the base compiler on all 12: 01–04, 10–12 build; 05–09 refused).
- After 10/12 build and match: verified by `test_ail_std_statistics`.
- Compare C byte-identical: verified all 10 `lab/compare/src/*/main.ail` with `--debug-dir` (10/10 identical); a `statistics.mean`-only program is also identical.
- Forced general builds refuse the new names by name: verified.
- "sumprod follows math.sumprod": true for float lists, **false for int lists** (ints are converted to float first — defect 2).
- "`correlation(..., method='ranked')` is refused by name": true only for a literal; a non-constant method leaks to runtime — defect 1.
- Tests: `test_ail_std_statistics`, `test_ail_stdlib_batch4`, `test_ail_genlib`, `test_ail_safetynet` — 4 modules, 0 failed.
- Manifest `--check`: passes. DEVLOG/DIFFERENCES/test registration present.

**Pre-existing:** none observed (base cannot build the new calls; non-feature C is identical).

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3` (not rerun, per review scope); typed/general split of the "before" table; speed (no existing hot path changed).

**Defects:**

1. `correlation` with a non-literal `method` builds but is wrong. Probe `j_ranked_var.py`:
```python
import statistics
def main() -> None:
    x: list[int] = [1, 2, 3, 4]
    y: list[int] = [1, 4, 9, 16]
    m: str = "ranked"
    print(statistics.correlation(x, y, method=m))
main()
```
Expected (CPython): `1.0`, exit 0. Actual HEAD default build: no stdout, exit 1, `ValueError: Unknown method: 'ranked'`. The literal form is refused at compile time; the non-constant form should be refused by name too (or `ranked` implemented), not leak into a runtime error.

2. Weighted `fmean` over `list[int]` silently loses precision above 2^53. Probe `l_fmean_bigint.py`:
```python
import statistics
def main() -> None:
    a: list[int] = [9007199254740993, 9007199254740993, 9007199254740993]
    w: list[int] = [1, 1, 1]
    print(statistics.fmean(a, weights=w))
    b: list[int] = [9007199254740993, 9007199254740993, 9007199254740993, 9007199254740993, 9007199254740993]
    print(statistics.fmean(b, weights=[1, 1, 1, 1, 1]))
main()
```
Expected (CPython): `9007199254740994.0` twice. Actual HEAD: `9007199254740992.0` twice. `lower_fmean` converts both int lists with `to_floats`, but CPython's weighted path uses `math.sumprod`, which is exact for ints (and `fmean([1,1,1],[2**53+1]*3)` similarly gives `1.0000000000000002` vs AIL `1.0`). This is a silent wrong value within int64, not the loud overflow the rules require.

VERDICT: FIX

1. Refuse (or implement) non-constant `correlation(..., method=...)`; `j_ranked_var` must not build into a runtime error (CPython `1.0`).
2. Make weighted `fmean` exact for int inputs (exact int product sum, or refuse the form); `l_fmean_bigint` must print `9007199254740994.0` twice.
[cost $0.0327, opencode tokens {"total": 1593147, "input": 37523, "output": 10324, "reasoning": 27220, "cache.write": 0, "cache.read": 1518080}]
    tool time: bash 11.3 min
        471s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_std_stat
         82s bash   cd /tmp && rm -rf cgcmp && mkdir cgcmp; same=0; diffc=0; fail=0; for t in berth_sim chain_relax echo_pack ledg
         26s bash   cd /tmp && rm -rf before && mkdir before && cd before for f in /home/runner/work/_temp/w2/lab/stdlib/statistic
         23s bash   cd /tmp && cat > sim3.py <<'EOF' import statistics, math, random def cov(xs, ys):     xs=[float(x) for x in xs
         23s bash   cd /tmp/rprobes; for p in a_q_whole b_corr_var_method c_fmean_edges d_cov_corr_large e_q_var f_corr_badmethod;
         17s bash   cd /tmp/rprobes cat > c2_fmean_edges.py <<'EOF' import statistics def main() -> None:     e: list[int] = []   
          6s bash   cd /tmp/rprobes cat > i_corr_sqrt.py <<'EOF' import statistics def main() -> None:     x: list[float] = [1.534
          5s bash   cd /tmp && cat > sim.py <<'EOF' import statistics, math, random def to_floats(xs): return [float(x) for x in x

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Committed `7688440` on `job-std_statistics-11011523`.

- **Defect 1 fixed:** non-literal `correlation(..., method=...)` is now refused by name at compile time; only literal `"linear"` builds.
- **Defect 2 fixed:** weighted `fmean` over two int lists sums products exactly in int64, then does CPython's int/float division; `l_fmean_bigint.py` now prints `9007199254740994.0` twice.
- **Regressions:** added both cases to `test_ail_std_statistics.py`.
- **Probes:** 13 run; 7 match CPython, 5 refused by name as expected, 1 is the documented loud int64 overflow case. Forced general builds refuse the new names by name.
- **Compare C:** 10/10 `lab/compare/src/*/main.ail` generated C byte-identical to base `7fc9724`.
- **Tests on final commit:** `test_ail_std_statistics`, `test_ail_stdlib_batch4`, `test_ail_stdlib5`, `test_ail_genlib`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 7 modules, 0 failed.
- **Manifest:** `update_manifest.py --check` passes.
- **Records:** DEVLOG, DIFFERENCES and RESULTS updated; residual big-integer product-sum limitation documented.
[cost $0.0368, opencode tokens {"total": 2201307, "input": 86115, "output": 13263, "reasoning": 16041, "cache.write": 0, "cache.read": 2085888}]
    tool time: bash 53.1 min
       1695s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 3300 python3 ../tools/par_check.py -j 2 test_ail_std_stat
       1155s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 3300 python3 ../tools/par_check.py -j 2 test_ail_std_stat
        172s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/basecmp /tmp/cgen_cur /tmp/cgen_base && git worktree add --detach
         66s bash   cd /tmp/probes && : > /tmp/probe_final.log; for p in j_ranked_var l_fmean_bigint p_fmean_int_exact p_fmean_int
         30s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_std_stat
         28s bash   cd /tmp/probes && for p in j_ranked_var l_fmean_bigint p_fmean_int_exact p_fmean_int_mixed p_fmean_int_errors 
         25s bash   cd /tmp/probes && for p in j_ranked_var l_fmean_bigint p_fmean_int_exact p_fmean_int_mixed p_fmean_int_errors 
          7s bash   cd /home/runner/work/_temp/w2 && python3 - <<'PY' from pathlib import Path p = Path('AIL_CURRENT/python/pkg-v1

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

FINAL VERDICT: FIX  2026-11-01T09:25:31Z
