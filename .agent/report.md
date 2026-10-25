# job job-pre205-10252054  started 2026-10-25T11:56:02Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":530,"duration_api_ms":406,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":551,"duration_api_ms":430,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. The task's pre-existing list was empty in the export, so I used the first item from the `rbpre121` review.

- **Difference fixed:** `"a b c".split(" ", 2**100 // 2**80)` was refused by name although the final value `2**20` fits; CPython splits normally. The maxsplit folder now bounds the intermediate by its existing 4096-bit budget instead of rejecting every exponent `>= 64`.
- Out-of-int64 final values (`2**100`, `10**30`, `(2**64)//2*2`) are still refused by name.
- Added `test_ail_pre205.py`; registered in `ail_check.MODULES` and `tools/ci_shards.json`; updated `DIFFERENCES.md` (`C?-job-pre205-10252054-1`), `DEVLOG.md`, and the manifest.
- Commit: `7cc81f8`.

**Probes (both builds):**
- `p205_direct`, `p205_flows`, `p205_types`, `p205_features`, `p205_budget_ok` — match CPython.
- `p205_out_of_range`, `p205_budget_pow_refuse`, `p205_budget_mult_refuse` — refused by name on both builds.

**Tests on HEAD:** `test_ail_pre205`, `test_ail_pre97`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5 modules, 0 failed (214s). `update_manifest.py --check` and `ci_shards.py --check` both clean.
[cost $0.0000, opencode tokens {"total": 3861308, "input": 97076, "output": 11544, "reasoning": 14320, "cache.write": 0, "cache.read": 3738368}]
    tool time: bash 10.2 min, edit 0.0 min, write 0.0 min
        280s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check && cd AIL_CURRENT && python3 ../t
        216s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre205 test_ail_pre97 test_ail_safetynet test_ai
         21s bash   grep -rn "rbpre121\|pre121\|10251547" /home/runner 2>/dev/null | grep -v "/work/ail-ci/ail-ci/.agent/task.md" 
         21s bash   for p in /tmp/probes/p205_direct.py /tmp/probes/p205_flows.py /tmp/probes/p205_types.py /tmp/probes/p205_featu
         18s bash   for p in /tmp/probes/p205_direct.py /tmp/probes/p205_flows.py /tmp/probes/p205_types.py /tmp/probes/p205_out_o
         17s bash   python3 tools/update_manifest.py >/dev/null && python3 tools/update_manifest.py --check && cd AIL_CURRENT && p
         10s bash   for p in /tmp/probes/p205_budget_ok.py /tmp/probes/p205_budget_pow_refuse.py /tmp/probes/p205_budget_mult_refu
          8s bash   git add AIL_CURRENT/test_ail_pre205.py && python3 tools/update_manifest.py && python3 tools/update_manifest.py

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change does:** in `_maxsplit_const` (`AIL_CURRENT/python/pkg-v12/pyfunc.py:629`), replaces the blanket `right >= 64` power refusal with `right * max(1, left.bit_length()) > _MAXSPLIT_BITS`, letting in-budget intermediates fold; out-of-int64 final values still raise the named maxsplit refusal. Matches the report.

**Claims**
- Exact case fixed — verified: `p205_direct` matches CPython on HEAD (both builds); base `/tmp/base` refuses by name.
- Out-of-int64 final values still refused — verified (`p205_refuse`: `2**63`, `2**100`, `3**63`, `(-2)**100`, `10**30`).
- Test added/registered, DEVLOG, DIFFERENCES id `C?-job-pre205-10252054-1`, manifest — verified; `update_manifest.py --check` and `ci_shards.py --check` clean.
- Worker probe list — verified representative files (`p205_features`, `p205_budget_ok` match; `p205_out_of_range` refused by name).
- Commit `7cc81f8` — verified.
- Chosen item came from the rbpre121 review — unverified (review not in tree); the difference itself is real on base.
- pre97/files/corpus_findings3 re-runs — unverified (not rerun per reviewer rules).

**My probes (HEAD):** `p205_inrange`, `p205_flows`, `p205_limits`, `p205_alias`, `p205_types`, `p205_neg` match CPython on both builds; `p205_refuse`/`p205_refuse2`/`p205_huge_exp` give the named refusal; no hang on `2**100000000`. Unrelated program `p205_unrelated` has byte-identical generated `program.c` vs base (only temp paths/warnings differ in the report).

**Tests:** `test_ail_pre205`, `test_ail_safetynet` — 2 modules, 0 failed.

**Pre-existing:** `2**4097 // 2**4090` etc. remain refused by name (same on base; the 4096-bit budget is intentional). No new defects.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 786277, "input": 33804, "output": 5294, "reasoning": 10411, "cache.write": 0, "cache.read": 736768}]
    tool time: bash 2.8 min
         87s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre205 tes
         21s bash   date; cd /tmp/rprobes; for p in p205_direct p205_bounds p205_bits p205_flows p205_limits p205_unrelated; do ec
         19s bash   date; cd /tmp/rprobes; for p in p205_direct p205_flows p205_inrange p205_limits p205_unrelated; do echo "=== $
         11s bash   date; cd /tmp/rprobes; for p in p205_inrange p205_refuse p205_refuse2; do echo "=== $p HEAD"; bash ~/tools/cmp
         10s bash   cd /tmp/rprobes && cat > p205_alias.py <<'EOF' def main():     b = bytearray(b"a b c")     s = "a b c"     n =
          5s bash   cd /tmp && date; for p in p205_features p205_budget_ok p205_out_of_range; do echo "=== $p worker file HEAD"; t
          4s bash   cd /tmp/rprobes && cat > p205_types.py <<'EOF' def main():     t = True     f = 2.0     print("a b c".split(" 
          4s bash   cd /tmp/rprobes && sed -i 's/2\*\*4096 \/\/ 2\*\*4090/2**4095 \/\/ 2**4089/' p205_inrange.py && date && bash ~

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-25T13:10:35Z
