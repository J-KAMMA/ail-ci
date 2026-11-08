# job job-err2_fix1-11080948  started 2026-11-08T00:50:06Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Commit `a15e1b9` on `job-err2_fix1-11080948` (not pushed).

- Cause: err2 added `ail_agent_errors.py`, imported by `ail_chatgpt.py`, but `ail_sdk.py`’s legacy export path (MANIFEST without `sdk_files`) only listed the older hard-coded CLI modules, so legacy re-export dropped it and failed the sha256 comparison.
- Fix: added `ail_agent_errors.py` to the legacy list (still selected only when its pin exists); refreshed the manifest pin via `tools/update_manifest.py`.
- Counts: `test_ail_sdk` 30/31 -> 31/31. Final commit, `par_check.py -j 2`: 9/9 modules, 0 failed (`sdk`, `agent_errors`, `registry`, `manifest_compiler`, `packaging`, `sdk_environment`, `safetynet`, `files`, `corpus_findings3`). `compileall` clean; manifest `--check` rc 0.
- Probe: `/tmp/probes/sdk_legacy_agent_errors.py` passes (declared/legacy equality, new module present, older legacy snapshot unchanged). It is a Python tooling probe, so `cmp.sh` is not applicable.
[cost $0.0000, opencode tokens {"total": 950459, "input": 48015, "output": 4523, "reasoning": 6273, "cache.write": 0, "cache.read": 891648}]
    tool time: bash 25.5 min, edit 0.0 min, write 0.0 min
        607s bash   timeout 2400 python3 tools/par_check.py -j 2 test_ail_sdk test_ail_agent_errors test_ail_registry test_ail_man
        564s bash   timeout 2400 python3 tools/par_check.py -j 2 test_ail_sdk test_ail_agent_errors test_ail_registry test_ail_man
        182s bash   cd AIL_CURRENT && timeout 1800 python3 -m unittest test_ail_sdk -v > /tmp/sdk_before.log 2>&1; echo "rc=$?"; t
        168s bash   cd AIL_CURRENT && timeout 1800 python3 -m unittest test_ail_sdk -v > /tmp/sdk_after.log 2>&1; echo "rc=$?"; ta
          1s bash   PYTHONPATH=$PWD/AIL_CURRENT python3 /tmp/probes/sdk_legacy_agent_errors.py $PWD/AIL_CURRENT
          1s bash   cd AIL_CURRENT && timeout 300 python3 -m unittest test_ail_sdk.SdkTests.test_declared_distribution_excludes_un
          1s bash   cd AIL_CURRENT && timeout 900 python3 -m unittest test_ail_sdk.SdkTests.test_declared_distribution_excludes_un
          1s bash   python3 -m compileall -q -j 0 AIL_CURRENT tools; echo "compileall rc=$?"

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: err2_fix1 — legacy SDK discovery keeps `ail_agent_errors.py`

**What the diff really does:** adds `ail_agent_errors.py` to the hard-coded "legacy" module tuple in `ail_sdk.export_sdk()` (`AIL_CURRENT/ail_sdk.py:756`, selected only when the name is in `pins`), refreshes the `ail_sdk.py` pin in `manifest.d/60.txt`, and adds a DEVLOG entry. Matches the report.

**Reproduction**
- Base `test_ail_sdk`: `Ran 31 tests … FAILED (failures=1)` → 30/31; only `test_declared_distribution_excludes_unadopted_files_and_checks_closure` fails at the legacy-copy `sha256` assertion (same as culprit log).
- HEAD: that test passes; full module `ok` (31/31).

**Probes** (`/tmp/rprobes/sdk_legacy_probe.py`, run on HEAD and `/tmp/base`; `cmp.sh` is not applicable to Python SDK tooling, so I also compared generated C):

| probe | HEAD | base |
|---|---|---|
| P1 declared→drop `sdk_files` re-export equals declared hashes and keeps `ail_agent_errors.py` | OK | FAIL (drops module) |
| P2 old snapshot with its pin removed, file still on disk → excluded, hashes match | OK | OK |
| P3 pinned but tampered module → refused by name, no output | OK | FAIL (module silently dropped) |
| P4 declared `sdk_files` that omits it → declared path still honours exclusion | OK | OK |

**C unchanged:** `plain.py` compiled with `--debug-dir` on HEAD and base produced byte-identical `program.c` (665 lines) and identical program output (`36 3 11`); only temp-path fields in `native_report.json` differ. No pre-existing behavioural differences found.

**Tests on HEAD** (`par_check.py -j 2`): all 9 claimed modules green, 0 failed (`test_ail_sdk`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_agent_errors`, `test_ail_registry`, `test_ail_manifest_compiler`, `test_ail_packaging`, `test_ail_sdk_environment`). `compileall` rc 0; `update_manifest.py --check` rc 0; recomputed `ail_sdk.py` SHA matches the refreshed pin; worker probe reruns PASS.

**Claim check:** cause — verified (`ail_chatgpt.py:32` imports it; pin is `s`); fix/selection-only-when-pinned — verified; 30/31→31/31 — verified; 9/9 modules — verified; compileall and manifest `--check` — verified; probe passes — verified. No claim was false. No hot-code/speed concern (SDK tooling only). Unverified: whether the pin line was edited by the tool or by hand (result is consistent either way).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 971029, "input": 36936, "output": 6647, "reasoning": 10710, "cache.write": 0, "cache.read": 916736}]
    tool time: bash 13.1 min
        561s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 2400 python3 tools/par_check.py -j 2 test_ail_sdk test_a
        169s bash   cd /tmp/base/AIL_CURRENT && date && timeout 1200 python3 -m unittest test_ail_sdk > /tmp/base_sdk_full.log 2>&
         34s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 2000 python3 tools/par_check.py -j 2 test_ail_manifest_c
          6s bash   cd /tmp && sed -i "s|rewrite(sdk/'MANIFEST.json', lambda x: (x.pop('sdk_files'), x\['sha256'\].pop('ail_agent_
          6s bash   cd /tmp && echo "=== HEAD ==="; python3 /tmp/rprobes/sdk_legacy_probe.py /home/runner/work/ail-ci/ail-ci/AIL_C
          2s bash   cat > /tmp/rprobes/p2_diff.py <<'PY' import json, sys, tempfile, importlib.util from pathlib import Path root=
          1s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 -m unittest test_ail_sdk.SdkTests.test_
          1s bash   cd /tmp/base/AIL_CURRENT && timeout 1800 python3 -m unittest test_ail_sdk.SdkTests.test_declared_distribution_

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-08T02:47:27Z
