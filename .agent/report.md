# job job-relwheelfix-11031144  started 2026-11-03T02:44:39Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed on `job-relwheelfix-11031144` as `b4a3f85`.

- **macOS wheel build:** `_no_links` now resolves the root with `os.path.realpath` and checks only components at/below it. `/var -> /private/var` no longer blocks export; file and directory symlinks inside the tree are still refused. Added both cases to `test_ail_sdk`.
- **Windows tutorial tests:** runs use an absolute `work/name.bin` path, with a `.bin.exe` fallback if the platform compiler appended it. Read `ail_chatgpt.py`: for `-o name.bin` it writes `name.bin` (the `.exe` suffix is only added when the requested name has no suffix).
- **Manifest:** `tools/update_manifest.py` run, `--check` passes.
- **Tests on Linux:** `test_ail_tutorial` 15 OK, `test_ail_sdk` 31 OK, `test_ail_packaging` 19 OK, `test_ail_safetynet` 5 OK, `test_ail_files` 18 OK (1 skipped), `test_ail_corpus_findings3` 2 OK, `tools/wheel_check.py` passed.
- **Probes:** `/tmp/probes/sdk_symlink_roots.py` and `/tmp/probes/tutorial_artifact_abs.py` pass directly; both are refused by name under `cmp.sh` (`importlib` is outside the AIL subset), as expected for Python-only packaging code.

Actual macOS/Windows runs were not available here; PR #352 will verify those.
[cost $0.0000, opencode tokens {"total": 14205424, "input": 161788, "output": 19414, "reasoning": 35102, "cache.write": 0, "cache.read": 13989120}]
    tool time: bash 11.2 min, edit 0.0 min, write 0.0 min
        145s bash   python3 -B AIL_CURRENT/test_ail_corpus_findings3.py -q 2>&1 | tail -15
        144s bash   python3 -B AIL_CURRENT/test_ail_safetynet.py -q 2>&1 | tail -15
        136s bash   python3 -B AIL_CURRENT/test_ail_sdk.py -q 2>&1 | tail -20
         88s bash   python3 -B AIL_CURRENT/test_ail_sdk.py -q 2>&1 | tail -8
         65s bash   python3 -B AIL_CURRENT/test_ail_files.py -q 2>&1 | tail -15
         16s bash   python3 tools/wheel_check.py 2>&1 | tail -15
         15s bash   python3 tools/wheel_check.py 2>&1 | tail -40
         12s bash   python3 -B AIL_CURRENT/test_ail_packaging.py -q 2>&1 | tail -25

## review 0
[model opencode/deepseek-v4.1-flash-free]
Review report

**What the change does:** `_no_links(path, root)` now resolves `root` with `os.path.realpath` and checks only the components from `root` down to `path`; all SDK export call sites pass the source/output root. `test_ail_tutorial` now runs `work/name.bin` by absolute path (with a `.bin.exe` fallback). Compiler/runtime untouched. The diff matches the report.

**Probes** (`/tmp/rprobes/`, direct Python for packaging code):
- `sdkprobe.py`: symlinked parent allowed; source-root-through-symlink allowed; inner file symlink refused; inner dir symlink refused; symlinked root refused; full export with both source and output under symlinked parents succeeds. All PASS.
- `sdk_dir_symlink.py`: whole `language_examples` directory symlink inside an SDK is refused. PASS.
- `base_repro.py`: base still refuses the symlinked-parent export, confirming the fix addresses a real failure. PASS.
- `plain.py` via `cmp.sh`: general and default builds match CPython; `--debug-dir` C identical to `/tmp/base` (only temp paths differ). PASS.

**Tests on HEAD:** `test_ail_tutorial`, `test_ail_sdk`, `test_ail_safetynet` pass; `test_ail_packaging` 19 OK; `test_ail_files` and `test_ail_corpus_findings3` pass; `wheel_check.py` builds/installs the wheel and runs 15 tutorial samples OK; `update_manifest.py --check` exit 0. Tutorial artifact naming verified at `AIL_CURRENT/ail_chatgpt.py:6581` (`.exe` only when the requested name has no suffix, so `name.bin` is correct).

**Claims:** all verified except the DEVLOG wording that says the test covers “a file and a directory symlink inside the tree”; the added test covers a file symlink only. The code does refuse directory symlinks (probe above), so this is a documentation overstatement, not a defect.

**Pre-existing:** none found.

**Unverified:** actual macOS and Windows CI runs (not available here).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1077862, "input": 34392, "output": 4475, "reasoning": 17939, "cache.write": 0, "cache.read": 1021056}]
    tool time: bash 5.2 min
        151s bash   date; python3 ../tools/par_check.py -j 2 test_ail_sdk test_ail_tutorial test_ail_safetynet 2>&1 | tail -30
        131s bash   date; python3 ../tools/par_check.py -j 2 test_ail_files test_ail_corpus_findings3 2>&1 | tail -12
         14s bash   date; timeout 600 python3 tools/wheel_check.py 2>&1 | tail -20
         11s bash   date; python3 -B AIL_CURRENT/test_ail_packaging.py -q 2>&1 | tail -8
          2s bash   cat > /tmp/rprobes/plain.py <<'PY' print(sum([1,2,3])) xs=[3,1,2] xs.sort() print(xs) PY date; bash ~/tools/cm
          1s bash   date; python3 -B AIL_CURRENT/test_ail_sdk.py -v SdkTests.test_export_root_below_a_symlinked_parent_is_allowed 
          1s bash   rm -rf /tmp/rprobes/dh /tmp/rprobes/db /tmp/rprobes/h.bin /tmp/rprobes/b.bin python3 AIL_CURRENT/ail_chatgpt.p
          0s bash   cat > /tmp/rprobes/sdk_dir_symlink.py <<'PY' import sys, tempfile from pathlib import Path sys.path.insert(0, 

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-03T04:26:19Z
