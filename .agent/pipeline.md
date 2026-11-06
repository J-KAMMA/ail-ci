# job job-fdgpu1-11061059  started 2026-11-06T02:00:06Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `a47fb9a`.

Root cause: `test_ail_gpu_smoke.test_06_spirv_valid` treated any `CI=true` runner as the GPU job and failed when `spirv-val` was absent. Both `test_ail_gpu_smoke` and `test_ail_gpu_g2` (it imports `GPUSmoke`) failed for that reason; the other four listed modules already passed.

Change: missing `spirv-val` now fails only when `AIL_GPU_REQUIRE_DEVICE=1` (the lavapipe job that installs spirv-tools); otherwise the check skips. No compiler/runtime behaviour changed. DEVLOG and manifest pin updated.

Tests on final commit:
- `test_ail_gpu_smoke`: OK, 6 run, 2 skipped
- `test_ail_gpu_g2`: OK, 31 run, 11 skipped
- `test_ail_safetynet`: OK, 5
- `test_ail_files`: OK, 18 (1 skipped)
- `test_ail_corpus_findings3`: OK, 2
- `test_ail_obj_refs`: OK, 3
- `test_ail_unified`: OK, 14
- `test_ail_virtual_dispatch`: OK, 6

Probes: no `/tmp/probes` compiler probes apply because this is a test-harness-only change. Harness checks: no `spirv-val` → skip; `SPIRV_VAL=/bin/true` → validator path runs and passes; `AIL_GPU_REQUIRE_DEVICE=1` without the tool → fails as intended. `update_manifest.py --check` passes.
[cost $0.0000, opencode tokens {"total": 2629046, "input": 90512, "output": 6667, "reasoning": 9243, "cache.write": 0, "cache.read": 2522624}]
    tool time: bash 21.3 min, edit 0.0 min
        234s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_unified 2>&1 | tail -100
        228s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_unified 2>&1 | tail -15
        159s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_safetynet 2>&1 | tail -80
        154s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_corpus_findings3 2>&1 | tail -15
        149s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_safetynet 2>&1 | tail -15
        120s bash   which spirv-val spirv-dis glslangValidator gcc clang 2>&1; ls /usr/bin | grep -i spirv | head; find / -name 's
         70s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_files 2>&1 | tail -15
         51s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_virtual_dispatch 2>&1 | tail -80

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: `a47fb9a`

**What the change really does:** In `test_ail_gpu_smoke.py`, `GPUSmoke.test_06_spirv_valid` now fails on a missing `spirv-val` only when `AIL_GPU_REQUIRE_DEVICE` is set, and otherwise skips. It removes the now-unused `IN_CI`, updates the docstring, DEVLOG and the manifest pin. No compiler or runtime code is touched.

**Harness probes (base worktree `/tmp/base` vs HEAD)**
- Base, `CI=true`, no `spirv-val` → `FAIL` ("missing in CI"), reproduces the reported failure.
- HEAD, same environment → `OK (skipped=1)`.
- HEAD, `SPIRV_VAL=/bin/true` → `OK`, prints `smoke: spirv-val ok` (validator path still exercised).
- HEAD, `AIL_GPU_REQUIRE_DEVICE=1`, no tool → `FAIL` with "missing in the GPU job".
- No C probes apply: the diff contains no compiler/runtime change, so generated C is necessarily unchanged. Speed check not applicable (no hot code touched).

**Tests on HEAD**
- `par_check -j 2 test_ail_gpu_smoke test_ail_gpu_g2 test_ail_safetynet test_ail_obj_refs test_ail_unified test_ail_virtual_dispatch`: 6/6 pass.
- Counts reproduced: gpu_smoke 6 run/2 skipped, gpu_g2 31/11, files 18/1, corpus_findings3 2. `update_manifest.py --check` and `ci_shards.py --check` pass.

**Report claims**
- Root cause (`CI=true` treated as GPU job): verified.
- Both smoke and g2 failed for that reason: verified (g2 does `from test_ail_gpu_smoke import *`).
- Other four listed modules already passed: verified by HEAD pass plus the fact none import the changed module; base was not re-run.
- No compiler/runtime behaviour changed: verified from the diff.
- Exact counts for safetynet/obj_refs/unified/virtual_dispatch: unverified, though all four passed.
- Minor wording inaccuracy only: DEVLOG says g2 "went red before any check ran", but `test_06` is last and checks 1–5 execute/skip first. Not a defect.

No defects found. Pre-existing differences: none relevant.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 386501, "input": 33397, "output": 3178, "reasoning": 6374, "cache.write": 0, "cache.read": 343552}]
    tool time: bash 6.2 min
        241s bash   date; python3 ../tools/par_check.py -j 2 test_ail_gpu_smoke test_ail_gpu_g2 test_ail_safetynet test_ail_obj_re
        107s bash   python3 -m unittest -q test_ail_files 2>&1 | tail -4; echo ===; python3 -m unittest -q test_ail_corpus_finding
         16s bash   python3 -m unittest -q test_ail_gpu_smoke 2>&1 | tail -4; echo ===; python3 -m unittest -q test_ail_gpu_g2 2>&
          2s bash   CI=true python3 -m unittest -q test_ail_gpu_smoke.GPUSmoke.test_06_spirv_valid 2>&1 | tail -15
          1s bash   CI=true python3 -m unittest -q test_ail_gpu_smoke.GPUSmoke.test_06_spirv_valid 2>&1 | tail -15
          1s bash   CI=true AIL_GPU_REQUIRE_DEVICE=1 python3 -m unittest -q test_ail_gpu_smoke.GPUSmoke.test_06_spirv_valid 2>&1 |
          1s bash   CI=true SPIRV_VAL=/bin/true python3 -m unittest -v test_ail_gpu_smoke.GPUSmoke.test_06_spirv_valid 2>&1 | tail
          0s bash   git worktree add /tmp/base work >/dev/null 2>&1 && echo OK || echo EXISTS; ls /tmp/base/AIL_CURRENT/test_ail_g

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-06T03:52:47Z
