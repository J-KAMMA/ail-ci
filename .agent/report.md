# job job-rbpre205-10252303  started 2026-10-25T14:08:54Z  worker=oc reviewer=oc (GitHub)
## qoder discovery
1.1.78
  -m, --model <model>                  Model for the current session. Default
                                       and New Models use model name; Custom
                                       uses modelID
  --reasoning-effort <level>           Set reasoning effort level
  --thinking <mode>                    Set thinking mode (auto, adaptive,
                                       enabled, or disabled)
--
                                       models
  --list-models                        List available models for the current
                                       user
  -i, --prompt-interactive <text>      Execute prompt and continue in
                                       interactive mode
### --list-models
MODEL
Auto
Ultimate
Fast
Efficient
Sonus
Cantus
Qwen3.8-Max
Qwen3.8-Flash
Kimi-K3.1-Pro
Kimi-K2.8-Preview
GLM-5.3
GLM-5.3-Flash
DeepSeek-V4-Pro
DeepSeek-Flash
MiniMax-M3.1-Flash
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":297,"duration_api_ms":177,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":293,"duration_api_ms":173,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Commit `bf66df7` on `job-rbpre205-10252303`.

- Re-applied pre205 metadata/test changes; `pyfunc.py` already had rbpre121's stronger exact `_pow_within_maxsplit_bits` bound, so that fix was kept.
- `python3 tools/update_manifest.py` updated pins; `--check` passes.
- `tools/diff_ids.py` does not exist in this tree, so it could not be run.
- Final-commit tests: `test_ail_pre205`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4/4 passed (215s).
- Probes: `p205_direct`, `p205_flows`, `p205_types`, `p205_features` matched CPython on both builds; `p205_out_of_range` was refused by name on both builds (`maxsplit ... does not fit in a 64-bit signed integer`; CPython OverflowError).
- Additional `test_ail_pre121` fails on the unchanged base code: `ail_chatgpt.py` emits `int64 constant out of range`, which its `REFUSALS` list lacks. Unrelated to this commit (no `pyfunc.py`/`ail_chatgpt.py` changes).
[cost $0.0000, opencode tokens {"total": 956652, "input": 25161, "output": 5696, "reasoning": 6371, "cache.write": 0, "cache.read": 919424}]
    tool time: bash 8.7 min, edit 0.0 min
        285s bash   python3 tools/par_check.py -j 2 test_ail_pre205 test_ail_pre121 test_ail_safetynet test_ail_files test_ail_cor
        217s bash   python3 tools/par_check.py -j 2 test_ail_pre205 test_ail_safetynet test_ail_files test_ail_corpus_findings3 2>
         18s bash   for p in /tmp/probes/p205_direct.py /tmp/probes/p205_flows.py /tmp/probes/p205_types.py /tmp/probes/p205_featu
          2s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-pre205-10252054 && git log --oneline -3 FETCH_HEAD
          0s bash   grep -n "test_ail_pre205\|test_ail_pre192\|test_ail_pre188" tools/ci_shards.json; sed -n '225,245p' tools/ci_s
          0s bash   git add AIL_CURRENT/test_ail_pre205.py && python3 tools/update_manifest.py && python3 tools/update_manifest.py
          0s bash   python3 tools/update_manifest.py --check && python3 -m py_compile AIL_CURRENT/test_ail_pre205.py && git add AI
          0s bash   git status --short && python3 tools/update_manifest.py --check; echo "manifest_check=$?"

## review 0
[model opencode/deepseek-v4.1-flash-free]
Review complete. Findings:

**What the diff really does:** re-applies job pre205's test/registration/metadata side only (`test_ail_pre205.py`, `ail_check.py`, `ci_shards.json`, `DEVLOG`, `DIFFERENCES`, `MANIFEST`). It deliberately omits pre205's `pyfunc.py` hunk because `work` already carries rbpre121's stronger exact `_pow_within_maxsplit_bits` bound. I confirmed that base implementation accepts a strict superset of the pre205 `right*bit_length` rule, so both sides' fixes are kept. This matches the report.

**Claims checked**
- pre205 metadata/test re-applied; test file byte-identical to `FETCH_HEAD` — verified.
- `pyfunc.py` already has the stronger fix; no compiler change in diff — verified.
- `update_manifest.py --check` passes — verified (exit 0).
- `tools/diff_ids.py` absent — verified (no such file anywhere in repo).
- Tests `test_ail_pre205`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` pass on HEAD — verified (4/4, 101s + 167s).
- `test_ail_pre121` fails on unchanged base, unrelated — verified by running it in `/tmp/base` (same 2 failures, `int64 constant out of range` vs its `REFUSALS`).
- Probe results — independently reproduced with my own probes.

**Probes (HEAD, both builds unless noted)**
- `r205_direct.py`, `r205_flows.py`, `r205_kw.py`, `r205_ok.py`, `r205_plain.py`, `r205_bytes.py`: same stdout as CPython, exit 0. Covers `2**100//2**80` via powers/shifts/sums/products, negative/zero/-1/`2**63-1`, empty string, `None`/explicit sep, keyword `maxsplit=`, list item, attribute, class attribute, dict value, `bytes.split`.
- `r205_e100.py`, `r205_e63.py` (maxsplit context): refused by name on both builds with the maxsplit wording; CPython `OverflowError`. Acceptable.
- `r205_e4096.py` (`2**4096//2**4096`, final 1): refused by name — identical on base, pre-existing.
- `r205_refuse.py` (`2**63` as a bare tuple element, not maxsplit): `int64 constant out of range` — identical on base, pre-existing.
- Non-feature program: `program.c` from `--debug-dir` byte-identical to `/tmp/base`; feature probe C also identical.

**Pre-existing (do not block):** pre121 failure above; `2**4096 // 2**4096` maxsplit refusal; bare `2**63` tuple-constant refusal.
**Unverified:** instruction-count speed (no compiler/runtime change in the diff; not applicable).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 584483, "input": 28842, "output": 5595, "reasoning": 7454, "cache.write": 0, "cache.read": 542592}]
    tool time: bash 5.7 min
        169s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_files te
        103s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_pre205 t
         18s bash   cd /tmp/base/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_pre121 2>&1 | tail -25; date
         15s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/*.py; do echo "===== $p"; bash ~/tools/cmp.sh "$p"
         14s bash   cat > /tmp/rprobes/r205_kw.py <<'EOF' n = 2**100 // 2**80 print("a b c".split(sep=" ", maxsplit=n)) print("a b
         13s bash   cat > /tmp/rprobes/r205_ok.py <<'EOF' vals = [0, 1, 2, 62, 63, 64, 100, 4095, 2**62, 2**63-1, -1, -2, -64] for
          4s bash   cd /tmp && rm -rf dbg && mkdir -p dbg/out && cp /tmp/rprobes/r205_plain.py dbg/p.ail && AIL_NO_CACHE=1 AIL_QUI
          3s bash   for p in /tmp/rprobes/r205_e4096.py /tmp/rprobes/r205_refuse.py; do echo "===== BASE $p"; bash ~/tools/cmp.sh 

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-25T15:25:23Z
