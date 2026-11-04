# job job-infer1-11041502  started 2026-11-04T06:06:41Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `71f9731`.

- `ref.py`: added optional `STEPS`; prompt >1024 and decode past context now refuse by name with exit 2 after printing top-5, matching `gpt2.py` (no more numpy traceback).
- `export_f32.py`: quantized GGUF tensors are refused by name instead of silently writing raw blocks; F32/F16 path unchanged.
- `RESULTS.md`: corrected 8.34 s to label it `AIL_NO_CACHE=1` (0.57 s warm).
- The suite's `test_ail_modules` failure was not reproducible; it passes on HEAD.

Probes (`/tmp/probes/`), all pass:
- `lab_ref_guard.py`: 1024 default → top-5 + named refusal exit 2; 1024 steps 0 → exit 0; 1025 prompt → refusal exit 2; negative STEPS → exit 0; 16 STEPS → 16 ids.
- `lab_export_guard.py`: F32/F16 accepted; Q5_K and non-float data refused by name with exit 2.

Tests on final commit: `test_ail_modules`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. Manifest `--check` clean. No compiler files changed.
[cost $0.0000, opencode tokens {"total": 1658389, "input": 68575, "output": 8069, "reasoning": 12593, "cache.write": 0, "cache.read": 1569152}]
    tool time: bash 14.9 min, edit 0.0 min
        335s bash   cd AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_safetynet test_ail_files test_ail_c
        331s bash   cd AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_modules test_ail_safetynet test_ail
        108s bash   find / -type d -name 'gguf' 2>/dev/null | head; find /root/.cache /home/runner/.cache -iname '*gguf*' 2>/dev/n
        102s bash   cd AIL_CURRENT && timeout 900 python3 -m unittest -q test_ail_modules > /tmp/tam.log 2>&1; rc=$?; echo "rc=$rc
         12s bash   rm -f /tmp/gpt2_check && python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/infer/gpt2.py -o /tmp/gpt2_check --
          1s bash   which -a python3 python3.11 python3.12; ls /usr/lib/python3/dist-packages 2>/dev/null | grep -i numpy; find / 
          1s bash   python3 -m py_compile lab/infer/ref.py lab/infer/export_f32.py && python3 tools/update_manifest.py && python3 
          1s bash   python3 tools/update_manifest.py; echo "update rc=$?"; python3 tools/update_manifest.py --check; echo "check r

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: infer s1 fix (`71f9731`)

**What the change really does:** Only `lab/infer/` scripts and docs change (no `AIL_CURRENT/*.py` or `tools/*`). `ref.py` gains optional `STEPS` plus the same prompt/context guards as `gpt2.py`; `export_f32.py` refuses non-F32/F16 tensor types; `RESULTS.md` relabels the 8.34 s compile time as `AIL_NO_CACHE=1`. Matches the report.

**Probes (in `/tmp/rprobes/`)**
- `refguard.py` (real numpy, fake model): 1024+default → top-5 then named refusal exit 2; 1024+STEPS=0 → top-5 + `greedy` exit 0; 1024+1, 1023+2 → refusal; 1025 prompt → no top-5, named refusal; 1-token with -5 and 16 → exit 0, 16 ids. All pass; guard text/ordering identical to `gpt2.py:261-264`.
- Real GGUFs built with pinned `gguf 0.19.0` / `numpy 2.5.4`: F32 and F16 export values equal expected; Q5_K refused by name, exit 2, no `.f32` written. All pass.
- `gpt2.py --strict` compiles to 106,816 B (matches RESULTS); `update_manifest.py --check` clean.
- Worker's `/tmp/probes/lab_ref_guard.py` and `lab_export_guard.py` both pass.

**Tests:** `test_ail_modules` passes (98 s) and `test_ail_safetynet` passes (183 s) on HEAD with `-j 2`. Note: my first `test_ail_modules` run failed only because I had installed numpy (its "third party alias" case imports numpy and expects `ModuleNotFoundError`); after uninstalling, it passes. This is an environment artifact, not the change.

**Claims:** ref.py guard/STEPS match gpt2.py — verified. export refusal + unchanged F32/F16 path — verified with the pinned libraries. RESULTS label — text verified; the 8.34/0.57 s numbers themselves not re-measured. `test_ail_modules` non-reproducible/passes — verified. "4 modules, 0 failed": I re-ran only test_ail_modules and test_ail_safetynet per the review rules; test_ail_files/test_ail_corpus_findings3 unverified. No compiler files changed, no weights in git — verified.

**Non-blocking observations**
- F64 GGUFs are now refused too, with the inaccurate message "not an unquantized float type" (I built one; rc 2). Out of the documented f32/f16 path, so not blocking.
- Pre-existing: empty prompt still crashes `ref.py` (`IndexError`) while `gpt2.py` prints zeros; invalid `STEPS` raises `ValueError` in both. Neither is introduced by this change.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1355659, "input": 56569, "output": 7171, "reasoning": 17679, "cache.write": 0, "cache.read": 1274240}]
    tool time: bash 5.1 min
        184s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1500 python3 ../tools/par_check.py -j 2 test
         99s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_
          6s bash   find / -name 'gguf_reader.py' 2>/dev/null | head; find / -iname 'gguf*.whl' 2>/dev/null | head; ls /tmp/ail-in
          4s bash   cd /tmp && timeout 60 python3 -m pip install --quiet numpy gguf 2>&1 | tail -5; echo "rc=$?"; python3 -c "impo
          4s bash   cd /tmp && timeout 60 python3 -m pip install --quiet numpy==2.5.4 gguf==0.19.0 2>&1 | tail -2; cd /tmp/rprobes
          1s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 600 python3 -m unittest -q test_ail_modules.
          1s bash   cd /tmp/rprobes && for k in F32 F16 Q5_K; do echo "=== $k ==="; rm -rf out_$k; python3 /home/runner/work/ail-c
          1s bash   cd /home/runner/work/ail-ci/ail-ci && rm -f /tmp/gpt2_check && timeout 300 python3 -B AIL_CURRENT/ail_chatgpt.

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-04T07:48:22Z
