# job job-rbfailfast-11011832  started 2026-11-01T09:33:17Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `6a1a93c`.

- Root cause: integration `a72a4db` refreshed `walkmemo.py`'s pin without the `s` flag, so the SDK omitted it; `test_ail_packaging` fails with `['python/pkg-v12/walkmemo.py']`.
- Fix: `ail_manifest.load` now selects existing pinned compiler sources under `python/pkg-v12/` and top-level `stdlib/`; other/absent/nested files stay out. Integration tree `a72a4db` + this file passes 17/17 packaging tests.
- Final tests: 5 modules, 0 failed (`test_ail_packaging`, `test_ail_walkmemo`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`); manifest `--check` passes.
- Probes: `p_manifest` (flag/subdir/absent boundaries) ok; `p_plain`, `p_walk_small` match CPython on both builds; `p_walk` refused by name for int64 overflow on both builds, as before.
[cost $0.0000, opencode tokens {"total": 2866415, "input": 94903, "output": 8528, "reasoning": 24296, "cache.write": 0, "cache.read": 2738688}]
    tool time: bash 11.5 min
        327s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_packaging test_ail_walkmemo tes
        274s bash   cd /home/runner/work/ail-ci/ail-ci && python3 /tmp/probes/p_manifest.py && python3 tools/update_manifest.py --
         19s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_packaging 2>&1 | tail -60
         16s bash   cd AIL_CURRENT && git status --short; python3 -m unittest -q test_ail_packaging -v 2>&1 | tail -40
         16s bash   cd /home/runner/work/ail-ci/ail-ci && cp AIL_CURRENT/ail_manifest.py /tmp/integwork/AIL_CURRENT/ail_manifest.p
         16s bash   cd /home/runner/work/ail-ci/ail-ci && git worktree add --detach /tmp/integwork origin/cand-1101180129 2>&1 | t
          6s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 120 git fetch --depth=80 origin integ main 2>&1 | tail -20; echo
          6s bash   mkdir -p /tmp/probes && cat > /tmp/probes/p_manifest.py <<'PY' import sys, tempfile from pathlib import Path s

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: `6a1a93c` — packaging: select every pinned compiler source in the SDK

**What the change really does (one line):** `ail_manifest.load` now adds every *pinned, existing* `.py/.h/.c` under `python/pkg-v12/` (any depth) and top-level `stdlib/` to `sdk_files`, regardless of the shard's `s` flag; `sha256`/`files` and all other paths are untouched. This matches the report.

**Claims checked**
1. Root cause — integration `a72a4db` has `... - python/pkg-v12/walkmemo.py` (no `s`), hash matches the file: **verified**. Base `load` gives 546 sdk files and the test fails with exactly `['python/pkg-v12/walkmemo.py']`.
2. Fix boundaries — existing pinned compiler sources selected; absent, non-source, `__pycache__`, nested `stdlib/`, and non-compiler paths stay out: **verified** by probes.
3. Integration tree + file/pin passes 17/17 packaging tests: **verified** (reproduced: patched `/tmp/integ` with HEAD `ail_manifest.py` + updated `c4.txt`; `Ran 17 tests ... OK`).
4. Final 5 modules pass and manifest `--check` passes: **verified** (all 5 plus `test_ail_sdk` pass; `update_manifest.py --check` exit 0).
5. Worker's `p_walk`/`p_walk_small` int64-refusal probes: **unverified** (not re-run).

**Probes (in `/tmp/rprobes/`)**
- `p_manifest_bounds.py` — synthetic pins: existing `pkg-v12` source without `s` selected on HEAD only; absent, `.md`, `__pycache__`, nested `stdlib/`, non-compiler excluded; `s`-flagged still selected; `sha256`/`files` unchanged; plain tree unchanged. All ok.
- `p_manifest_mutation.py` — flag change visible on next load, deleted file drops out, empty shard dir preserves manifest. All ok.
- `p_plain.py` via `cmp.sh` on HEAD and `/tmp/base` — both builds same as CPython.

**Integration regression check:** with the fix applied, integration `test_ail_packaging` 17/17 and `test_ail_sdk` 29/29 pass; `walkmemo.py` introduces no missing compiler imports. Base integration fails only the target test (the defect being fixed).

**Notes:** The change makes `s` redundant for pinned compiler sources, which is exactly the invariant `test_every_compiler_file_is_selected` enforces. Extra `load` cost is ~8 ms over the existing ~90 ms (256 shards) in preflight/export, not the compile hot path. No pre-existing branch differences found.

**Unverified:** full suite (by design), integration runs of `test_ail_walkmemo`/`test_ail_check`, worker's `p_walk*` probes.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1199250, "input": 128753, "output": 8009, "reasoning": 17368, "cache.write": 0, "cache.read": 1045120}]
    tool time: bash 11.5 min
        221s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 1500 python3 tools/par_check.py -j 2 test_ail_packaging 
        214s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 900 python3 tools/par_check.py -j 2 test_ail_walkmemo te
        185s bash   cd /tmp/integ && cp /home/runner/work/ail-ci/ail-ci/AIL_CURRENT/ail_manifest.py AIL_CURRENT/ail_manifest.py &&
         37s bash   cd /home/runner/work/ail-ci/ail-ci && git show 6a1a93c --stat; echo "--- diff of DEVLOG date etc done ---"; py
         15s bash   cd /tmp/integ && cp /home/runner/work/ail-ci/ail-ci/AIL_CURRENT/ail_manifest.py AIL_CURRENT/ail_manifest.py &&
          7s bash   cat > /tmp/rprobes/p_plain.py <<'PY' from dataclasses import dataclass  @dataclass class P:     x: int     y: 
          3s bash   cd /tmp/integ && python3 - <<'PY' import ast,sys from pathlib import Path root=Path('AIL_CURRENT') pins={} imp
          1s bash   cd /tmp/integ && ls pyproject.toml packaging >/dev/null 2>&1 && echo has-packaging; cd /tmp/integ/AIL_CURRENT 

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-01T11:20:18Z
