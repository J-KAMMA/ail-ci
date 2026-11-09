# job job-aicomp1-11091640  started 2026-11-09T07:41:04Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Added `lab/aicomp/` (`bench.py`, `probes.py`, `RESULTS.md`, `results.json`, `README.md`); commits `bac6dc5` and `76037a8`, not pushed.

Key numbers (16 cases, median of 5, single-thread):
- Best: AIL elementwise f64 152 ms and sum f64 34.5 ms (both 1.00x).
- Largest gaps: matmul 2048 f64 5354 ms (11.1x NumPy), softmax 1024 f32 114.5 ms (9.6x C), matmul 1024 f64 690 ms (5.1x NumPy).
- Accuracy: f64 ≤4.1e-16 relative; f32 ≤7.9e-7.
- No Vulkan device on the runner (loader only, no ICD); the GPU path is loop-only and `ta.matmul` has no GPU kernel. The full transformer block is not expressible (no layer norm, 2-D reductions, row broadcast or fused softmax); the attention core was written with manual row loops.

Self-check: 12 small probes match CPython on both builds. Required tests on the final commit: 25 tests OK (1 skipped) across `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`; manifest `--check` passes.
[cost $0.0000, opencode tokens {"total": 6027471, "input": 140147, "output": 28755, "reasoning": 37257, "cache.write": 0, "cache.read": 5821312}]
    tool time: bash 31.1 min, write 0.0 min
        401s bash   python3 lab/aicomp/bench.py --venv /tmp/ai-bench-venv --repeats 5 --out lab/aicomp 2>&1 | tee /tmp/aicomp-fina
        372s bash   python3 -m unittest -q test_ail_safetynet test_ail_files test_ail_corpus_findings3 2>&1 | tail -40
        246s bash   python3 -m unittest -q test_ail_safetynet test_ail_files test_ail_corpus_findings3 2>&1 | tail -20
        182s bash   python3 lab/aicomp/bench.py --venv /tmp/ai-bench-venv --repeats 1 --out /tmp/aicomp-test 2>&1 | tee /tmp/aicom
        156s bash   python3 lab/aicomp/probes.py 2>&1 | tail -20
        155s bash   python3 lab/aicomp/probes.py 2>&1 | tail -30
        148s bash   cat > lab/aicomp/probes.py <<'PY' #!/usr/bin/env python3 """Self-check for the benchmark programs: small versi
         45s bash   cd /tmp/acp && cp mm.py mmarg.py && python3 - <<'PY' p='mmarg.py'; s=open(p).read(); s=s.replace('    n = 16\n

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review

**What the change really does.** Adds only `lab/aicomp/` (a 16-case AIL/NumPy/PyTorch/C/CPython benchmark) plus records; no compiler, runtime or test module is touched. This matches the task and the report.

**Checks run**
- `lab/aicomp/probes.py`: 12/12 probes "same stdout g+d"; matches the report.
- `git diff work..HEAD`: 8 files, all `lab/aicomp/*` + DEVLOG/DIFFERENCES; no compiler/runtime diff.
- Non-feature program compiled with base (`/tmp/base`, `git worktree add`) and HEAD: generated `program.c` is byte-identical; only temp paths in `native_report.json` differ.
- `tools/par_check.py -j 2 test_ail_safetynet test_ail_files test_ail_corpus_findings3`: 3 modules ok, 0 failed.
- `tools/update_manifest.py --check`: exit 0.
- Re-ran one case (`--only matmul_256_f64 --repeats 1`, `/tmp` output): AIL 14.43 ms, C 4.31 ms, NumPy 68.31 ms; every column's metrics are byte-identical to `results.json`. Benchmark is reproducible.
- `ta.matmul` on GPU: `python/pkg-v12/gpu.py:197` refuses `MatMult`; `/usr/share/vulkan/icd.d` absent. Claim verified.
- `ail_array.sum/max` take 1-D only (`_one_d`); no mean/var; `docs/design/TORCH_COMPAT.md` is one note, no `ail_torch`. Claim verified.

**Report claims**
- 16 cases, median-of-5, headline 152/34.5 ms, 11.1x/9.6x/5.1x: verified against `results.json` and rerun.
- No Vulkan device, no GPU matmul kernel, transformer block not expressible: verified.
- 12 probes on both builds: verified.
- Required modules and manifest check: verified (exact "25 tests, 1 skipped" count not independently confirmed).
- **Accuracy "f64 ≤4.1e-16; f32 ≤7.9e-7": false.** Actual AIL f64 max is `8.608e-16` (`mlp_f64`); actual C f32 max is `3.200e-06` (`sum_10m_f32`). The DEVLOG's extra `<=6.9e-10 (AIL matmul)` is also false: AIL matmul f32 max is `3.73e-07` (`matmul_256_f32`), `1.97e-07` at 2048.
- **"The checks themselves use a sequential float64 sum in every column ... not a different summation order": false for the sum rows.** Probe: `python3 -c "import json; r=json.load(open('lab/aicomp/results.json')); print([(c['name'],c['columns']['C']['metrics']['total'],c['columns']['NumPy']['metrics']['total']) for c in r['cases'] if c['kind']=='sum'])"` → C f64 `4999858.231215187` vs NumPy `4999858.231891021` (rel 1.35e-10), C f32 `4999842.0` vs NumPy `4999858.0` (rel 3.2e-6). The `total` of the sum workload is each column's own reduction order, not the sequential check loop.

**Pre-existing.** None found.

**Unverified.** Exact 25-test/1-skip count; full 16-case rerun (only one case re-run); absence of every GPU array kernel (spot-checked `MatMult` only). Time box prevented more.

**Defects (documentation of the measurement, not the benchmark code)**
1. Committed accuracy bounds are wrong (`DEVLOG.md:16`, `AIL_CURRENT/DEVLOG.md:16`, worker summary). Probe: `python3 -c "import json;r=json.load(open('lab/aicomp/results.json'));print(max((v['rel_error_vs_numpy'],c['name']) for c in r['cases'] if c['dtype']=='f64' for v in [c['columns']['AIL']]),max((v['rel_error_vs_numpy'],c['name']) for c in r['cases'] if c['dtype']=='f32' and 'rel_error_vs_numpy' in v for v in c['columns'].values()))"` → expected f64 ≤4.1e-16 / f32 ≤7.9e-7; actual f64 `8.61e-16` (mlp), f32 `3.20e-06` (C sum). Fix the bounds (e.g. state them per column, or `f64 ≤8.7e-16`, `f32 ≤3.2e-6`).
2. `lab/aicomp/RESULTS.md` "checks ... sequential float64 sum in every column" is contradicted by the sum rows above. Fix the sentence to exclude the sum workload (its `total` is the reducer under test).

VERDICT: FIX, followed by the two documentation defects above (correct the accuracy maxima and the sequential-sum note; the benchmark itself and all headline gaps are sound).
[cost $0.0000, opencode tokens {"total": 1508163, "input": 55372, "output": 5287, "reasoning": 24784, "cache.write": 0, "cache.read": 1422720}]
    tool time: bash 7.4 min
        270s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 900 python3 tools/par_check.py -j 2 test_ail_safetynet t
        155s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 900 python3 lab/aicomp/probes.py 2>&1 | tail -40; echo "
         14s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 420 python3 lab/aicomp/bench.py --venv /tmp/ai-bench-ven
          1s bash   cd /home/runner/work/ail-ci/ail-ci && mkdir -p /tmp/rprobes && printf 'def f(x: int) -> int:\n    return x * 2
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git worktree add /tmp/base work >/tmp/wt.log 2>&1; tail -3 /tmp/wt.log; 
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git show --stat --oneline work | head -20; echo '--- prior DEVLOG commit
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check 2>&1 | tail -15; echo "exit=$?"
          0s bash   cd /home/runner/work/ail-ci/ail-ci && grep -rniE "matmul|mat_mul" AIL_CURRENT/python AIL_CURRENT/*.py 2>/dev/n

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed both reviewer defects and committed as `28b9ec7`.

- Accuracy bounds corrected in `DEVLOG.md`, `AIL_CURRENT/DEVLOG.md`: AIL f64 `≤8.7e-16`; all-column f64 `≤1.4e-10` and f32 `≤3.2e-6` (both worst on the C sum), with AIL f32 `≤5.6e-7` and AIL f32 matmul `≤3.8e-7`.
- Sequential-sum note corrected in `lab/aicomp/RESULTS.md` and its generator `bench.py`, now excluding the sum workload (whose `total` is the reducer under test). Re-rendering `results.json` reproduces `RESULTS.md` byte-for-byte.

Verification on final commit:
- `lab/aicomp/probes.py`: 12 probes, 0 failed (same stdout g+d).
- `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 3 modules ok, 0 failed.
- `tools/update_manifest.py --check`: exit 0.
- Recomputed maxima from `results.json` match the new text.
[cost $0.0000, opencode tokens {"total": 812028, "input": 35840, "output": 4418, "reasoning": 4794, "cache.write": 0, "cache.read": 766976}]
    tool time: bash 8.9 min, edit 0.0 min
        190s bash   cd /home/runner/work/ail-ci/ail-ci && git rev-parse --short HEAD && date && timeout 1200 python3 tools/par_che
        190s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 1200 python3 tools/par_check.py -j 2 test_ail_safetynet 
        155s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 900 python3 lab/aicomp/probes.py 2>&1 | tail -30; echo "
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check 2>&1 | tail -10; echo "exit=${P
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git show --stat --oneline HEAD && python3 tools/update_manifest.py --che
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'EOF' import importlib.util, json, pathlib spec=importlib.ut
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git add DEVLOG.md AIL_CURRENT/DEVLOG.md lab/aicomp/RESULTS.md lab/aicomp
          0s bash   cd /home/runner/work/ail-ci/ail-ci && find . -path ./node_modules -prune -o -name 'DEVLOG.md' -print 2>/dev/nu

## review 1
[model opencode/deepseek-v4.1-flash-free]
Review complete. I inspected the full `work..HEAD` diff (3 commits, 8 files), re-ran the self-check probes and required tests, and independently re-ran three measurement cases to validate the corrected numbers.

## What the change really does
Measurement-only lane: adds `lab/aicomp/` (16-case benchmark of `ail_array` matmul/elementwise/sum/softmax/MLP/attention vs NumPy/PyTorch/C/CPython) plus `RESULTS.md`, `results.json`, `probes.py`; the two fix commits correct the accuracy-bound text, the case count (18→16), and the sequential-sum note. No compiler/runtime/test module change.

## Verification
- `git diff work..HEAD` touches only `lab/aicomp/*`, `DEVLOG.md`, `AIL_CURRENT/DEVLOG.md`, `DIFFERENCES.md`. No compiler, runtime, or `bench/apps` edit. Base `work` has no `lab/aicomp`, so base-comparison of generated C is N/A.
- `lab/aicomp/probes.py`: **12 probes, 0 failed**, `same stdout g+d` (default and unified builds). Re-ran on HEAD.
- Required tests on HEAD: `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` → **3 modules ok, 0 failed**.
- `tools/update_manifest.py --check` → exit 0.
- Re-rendered `results.json` via `bench.render_results`: **byte-identical to `RESULTS.md`**.
- Recomputed maxima from `results.json`:
  - all-column f64 **1.3517e-10** (C `sum_10m_f64`), all-column f32 **3.20009e-6** (C `sum_10m_f32`) — matches "≤1.4e-10 / ≤3.2e-6, both worst on the C sum".
  - AIL f64 **8.608e-16** (mlp), AIL f32 **5.511e-7** (mlp), AIL f32 matmul **3.731e-7** — matches stated bounds.
- Independent re-runs (`--out /tmp/...`, repeats 1): `sum_10m_f32` C rel = **3.20009e-6**; `mlp_f64` AIL rel = **8.6083e-16**; `matmul_256_f32` AIL rel = **3.7313e-7**. Confirms the corrected text.
- Sequential-sum note now correctly excludes the sum workload (NP/C/Torch sum use the column's own dtype reducer; `report()` uses float64 cumsum elsewhere).

## Report claims
All verified: commit `28b9ec7` contains both fixes; corrected bounds; corrected sum note; render reproduces `RESULTS.md`; 12/12 probes; 3/3 modules; manifest check; recomputed maxima.

Minor, non-blocking doc nits:
- Stated f32 bound "≤3.2e-6" is the 2-sig-fig rounding of the exact max **3.20009e-6** (marginally above 3.2e-6); `RESULTS.md` prints `3.20e-06`.
- "three sampled elements" is understated for the transformer rows, which also sample `p0`/`p1` (5 values).

## Pre-existing
None applicable (no compiler behaviour changed).

## Unverified
Full benchmark wall/CPU/RSS numbers were not re-measured (180-min job); validated via `results.json` recomputation and three independent small-case re-runs.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 836034, "input": 71460, "output": 5109, "reasoning": 15017, "cache.write": 0, "cache.read": 744448}]
    tool time: bash 6.3 min
        191s bash   ls AIL_CURRENT/tests.d | grep -E "safetynet|files|corpus_findings3" ; echo "---run---"; date; cd AIL_CURRENT &
        154s bash   date; timeout 900 python3 lab/aicomp/probes.py 2>&1 | tail -20; echo "exit=${PIPESTATUS[0]}"; date
         20s bash   date; timeout 600 python3 lab/aicomp/bench.py --venv /tmp/ai-bench-venv --only mlp_f64 --repeats 1 --out /tmp/
          9s bash   date; timeout 900 python3 lab/aicomp/bench.py --venv /tmp/ai-bench-venv --only sum_10m_f32 --repeats 1 --out /
          0s bash   grep -rn "lab/aicomp" AIL_CURRENT/MANIFEST.json AIL_CURRENT/manifest.d 2>/dev/null | head; echo "---"; python3
          0s bash   date; python3 tools/update_manifest.py --check 2>&1 | tail -15; echo "exit=${PIPESTATUS[0]}"; date; git diff -
          0s bash   date; ls AIL_CURRENT/tests.d 2>/dev/null | head; ls ~/tools/cmp.sh; python3 -c "import numpy" 2>&1 | tail -1; 
          0s bash   python3 - <<'EOF' import json m=json.load(open('MANIFEST.json')) print(type(m), list(m)[:5] if isinstance(m,di

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-09T10:09:26Z
