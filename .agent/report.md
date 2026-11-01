# job job-std_statistics-11011831  started 2026-11-01T09:32:39Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed all three review defects and committed as `04e2824`.

- `sumprod_floats` now uses CPython’s TripleLength compensated sum with power-of-two-scaled Dekker products and CPython’s ordinary-float fallback. `k_split_overflow.py` now matches (`15.0`, `2.4285714285714285e+301`); `j_float_overflow.py` matches (`inf`, `inf`, `nan`), including subnormal cases.
- Unknown-method errors use `repr`: `c2_q_quote.py`, `l_corr_quote.py`, `p_method_literals.py` match CPython.
- `11_geometric_harmonic.py` is now 17 lines and its test still matches CPython.

Tests on the final commit: `test_ail_std_statistics`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass. Also passed earlier on the same code: `test_ail_stdlib_batch4`, `test_ail_genlib`. Manifest `--check` passes. The 10 `lab/compare` C outputs are unaffected because none use `statistics`.
[cost $0.0000, opencode tokens {"total": 3931612, "input": 102018, "output": 16559, "reasoning": 31275, "cache.write": 0, "cache.read": 3781760}]
    tool time: bash 24.4 min, edit 0.0 min
        486s bash   cd /home/runner/work/ail-ci/ail-ci && for t in test_ail_safetynet test_ail_files test_ail_corpus_findings3 tes
        311s bash   cd /home/runner/work/ail-ci/ail-ci && AIL_NO_CACHE=1 python3 AIL_CURRENT/test_ail_stdlib_batch4.py > /tmp/batc
        283s bash   cd /home/runner/work/ail-ci/ail-ci && for t in test_ail_files test_ail_corpus_findings3; do echo "=== $t"; AIL
        175s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check && echo manifest-ok; for t in t
        117s bash   python3 - <<'PY' import sys, math, inspect print(sys.version) PY find / -name mathmodule.c 2>/dev/null | head;
         24s bash   cd /home/runner/work/ail-ci/ail-ci && AIL_NO_CACHE=1 python3 AIL_CURRENT/test_ail_std_statistics.py 2>&1 | tai
         21s bash   cd /home/runner/work/ail-ci/ail-ci && for f in /tmp/probes/*.py; do echo "######## $f"; bash ~/tools/cmp.sh "$
         16s bash   python3 - <<'PY' import random, struct, math from fractions import Fraction SPLIT=134217729.0 def two(a,b):   

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review of `04e2824`

**What the change really does:** in `AIL_CURRENT/python/pkg-v12/strt.py`, replaces `sumprod_floats` with CPython's TripleLength compensated sum (`dl_sum`, scaled-Dekker `dl_product`, `tl_to_d`, `strt.py:591-704`), with the ordinary-float fallback after a non-finite product/sum; changes the three unknown-method errors to `repr` (`strt.py:541,570,717`); adds 3 lines to `11_geometric_harmonic.py` and updates DEVLOG/DIFFERENCES/RESULTS/manifest. This matches the report.

**Claims checked**
- Defect 1 fixed: **verified** — `k_split_overflow.py` gives `15.0` / `2.4285714285714285e+301`; `j_float_overflow.py` gives `inf`, `inf`, `nan`.
- Defect 2 fixed: **verified** — `c2_q_quote.py`, `c3_repr_ctrl.py`, `e2_q_float.py`, `p_method_literals.py` match CPython for `'`, `"`, `\`, newline, tab, NUL, `é`, emoji, `""`.
- Defect 3 fixed: **verified** — file is 17 lines; `11_geometric_harmonic.py` matches CPython on both builds.
- Compensated sum exactness: **verified** — 150-case full/tiny-product fuzz, 200-case subnormal-product fuzz, and 100-case extreme fuzz all match CPython (the only diffs in the latter come from pre-existing `fsum`).
- Tests on HEAD: **verified** — `test_ail_std_statistics`, `test_ail_files`, `test_ail_safetynet`, `test_ail_corpus_findings3` pass (4 modules, 312s, 0 failed).
- Manifest `--check`: **verified**.
- Compare-C unchanged: **partially verified** — `ticket_audit` and `ledger_bin` generated C byte-identical to base; `chain_relax`/`scar_life` fail identically on base; committed compare files untouched.
- `test_ail_stdlib_batch4`/`test_ail_genlib` re-run and “before” counts: **unverified** (not re-run; outside instructed set).

**Pre-existing:** CPython's `math.fsum` raises `ValueError: -inf + inf in fsum` and `OverflowError: intermediate overflow in fsum`; AIL returns `nan`. Probe `p86_fsum_inf.py` is identical on `/tmp/base`, so not caused by this change.

**Defects:** none found. The committed change is correct and the three review items are fixed.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2142647, "input": 101225, "output": 10259, "reasoning": 31419, "cache.write": 0, "cache.read": 1999744}]
    tool time: bash 11.8 min
        120s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && nohup setsid timeout 1700 python3 ../tools/par_check.py -j 2
        109s bash   cd /tmp/rprobes && python3 - <<'PY' import random, math random.seed(9876) def rep(v):     return repr(v) def l
         77s bash   cd /tmp/rprobes && python3 - <<'PY' import random, math random.seed(424242) def lits(vals): return "[" + ", ".
         69s bash   cd /tmp/rprobes && python3 - <<'PY' import random, math random.seed(12345)  def lits(vals):     return "[" + "
         65s bash   cd /tmp/rprobes && python3 - <<'PY' import random, math random.seed(12345) def rep(v):     if v==float('inf'):
         60s bash   cd /tmp && rm -rf dbg_head dbg_base csrc && mkdir -p csrc && cp /home/runner/work/ail-ci/ail-ci/lab/compare/sr
         59s bash   cd /tmp && rm -rf csrc_base dbg_base && mkdir csrc_base && cp /home/runner/work/ail-ci/ail-ci/lab/compare/src/
         50s bash   cd /tmp && for t in chain_relax scar_life ledger_bin; do rm -rf ch_$t cb_$t; mkdir -p ch_$t cb_$t; cp /home/ru

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-01T11:35:19Z
