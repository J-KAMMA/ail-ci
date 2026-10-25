# job job-pre236-10260352  started 2026-10-25T18:53:16Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":374,"duration_api_ms":250,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":360,"duration_api_ms":233,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed on `job-pre236-10260352` (HEAD `e69d1d2`, 3 commits; final diff 9 files, +233/−35).

- Fixed large special exponents and absorbing zero in both constant folders: `0 *`, `0 &`, and `0/1/-1 **` now fold before the size guard, with a 2**24-bit special-exponent retry.
- Added `test_ail_pre236.py`, registered it in `ail_check.py`/`ci_shards.json`, and accepted pre177’s named `int64 constant out of range` wording in `test_ail_pre121.py`.
- Added DEVLOG/DIFFERENCES entries; `update_manifest.py --check` and `git diff --check` pass.

Final tests on HEAD: 13 modules, 12 pass — `test_ail_pre236`, `pre121`, `pre190`, `safetynet`, `files`, `corpus_findings3` all pass. `test_ail_pre195` fails identically on base (`2**4096 // 2**4050` is accepted where its stale test expects refusal), so it is pre-existing and untouched.

Probes: 8 match both builds (`special_module`, `special_routes2`, `zero_big_beyond`, `special_small`, `cap_zero`, `maxsplit_special_small`, `nonint`, `neg_small`); 9 are named refusals (`16m_boundary`, `zero_broad`, `routes`, `cap_shift`, `cap_pow`, `cap_maxsplit`, `pre121`, `pre121_split`, `under_cap`). No whole-suite run.
[cost $0.0000, opencode tokens {"total": 10606311, "input": 313412, "output": 26918, "reasoning": 53117, "cache.write": 0, "cache.read": 10212864}]
    tool time: bash 30.2 min
        325s bash   cd AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pre236 test_ail_pre121 test_ail_pre
        301s bash   cat > /tmp/probes/p236_nonint.py <<'EOF' def f():     print('called')     return 2   def main():     print(1.5
        255s bash   cd AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pre236 test_ail_pre121 test_ail_pre
        249s bash   cd AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pre236 test_ail_pre121 test_ail_pre
        185s bash   cat > /tmp/probes/p236_maxsplit_special_small.py <<'EOF' print('a b c d'.split(' ', 0 ** (1 << 2000000))) prin
        181s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/python/pkg-v12/pyfunc.py') s=p.read_text() old="
         55s bash   cd /tmp/ail_base/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre190 2>&1 | tail -35
         35s bash   cd /home/runner/work/ail-ci/ail-ci; : > /tmp/p236_probes_final.log; for f in p236_special_module p236_special_

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does.** In the two non-`pyfront` constant folders it decides absorbing zero (`0 *`, `0 &`) and power bases `0/1/-1` before the size guard, threads the limit through recursion, and retries a huge exponent at `2**24` bits; plus `test_ail_pre236.py`, a pre121 wording relaxation, docs and manifest. This matches the report.

**Probes** (`bash ~/tools/cmp.sh`, HEAD and base):
- Match CPython on HEAD where base refused: `p1_special`, `p4_boundary`, `p6_routes`, `p10b_cancel`, `p11_absorb_neg`, `p14_cap2`, `p19_maxsplit`, `p20_index`, `p29_zero_bigger`, `p32_func_pos`.
- Match CPython on both builds (no regression): `p7_nonfeature`, `p8_pre190`, `p9_nonint`, `p18_neg_small`, `p23_cancelnegpow`, `p25_cancelsmall`.
- Named refusals, identical behaviour on base: `p2`/`p3`/`p15`/`p16`/`p17`/`p30`/`p31` (huge negative exponents), `p5`/`p13` (exponent at/over 2^24), `p12` (huge negative shift), `p21`/`p22`/`p24`/`p26`/`p27`/`p28` (non-special intermediates).
- Non-feature C: `program.c` byte-identical to base for both default and `AIL_UNIFIED_FORCE=1` (only temp paths in `native_report.json` differ).

**Tests on HEAD.** `test_ail_pre236`, `test_ail_pre121`, `test_ail_safetynet`: 3 modules, 111s, 0 failed. Also `test_ail_pre190`, `test_ail_files`, `test_ail_corpus_findings3`: 171s, 0 failed. `test_ail_pre195` fails identically on base (verified). `update_manifest.py --check` and `git diff --check work..HEAD` pass; commit trailers and `C?-job-pre236-10260352-1` id are present.

**Claims.** All verified except the worker's own probe list and its "13 modules" count (unverified). Speed check not applicable: compile-time-only change, runtime C identical. Minor doc nit only: `test_ail_pre236.py`/DIFFERENCES say the "generic" folder guard was `2**20`, while `_CONST_INT_BITS` there is 4096 (`pyfront` is the 2^20 one); no functional impact.

**Pre-existing (identical on base, not blocking):** `1 ** (1 << 16777216)` and `(1 << 2000000) >> 2000000` refused where CPython gives 1; huge negative-exponent powers refused where CPython raises `OverflowError`; non-special cancellation-zero expressions refused.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1779386, "input": 79646, "output": 8164, "reasoning": 36920, "cache.write": 0, "cache.read": 1654656}]
    tool time: bash 8.3 min
        172s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_pre
        112s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pre
         27s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && echo "=== HEAD"; timeout 900 python3 ../tools/par_check.py -
         24s bash   cd /tmp/rprobes cat > p15_neg5000.py <<'EOF' print(1 ** -(1 << 5000)) EOF cat > p16_neg100k.py <<'EOF' print((
         22s bash   cd /home/runner/work/ail-ci/ail-ci; for p in p2_neg_huge p3_zero_neg_huge p5_wide_special p8_pre190 p9_nonint;
         19s bash   cd /tmp/rprobes cat > p30_func_neg.py <<'EOF' def f():     return 1 ** -(1 << 2000000)  print(f()) EOF cat > p
         18s bash   cd /tmp/rprobes cat > p23_cancelnegpow.py <<'EOF' print(((((1 << 5000) - (1 << 5000)) + 1) ** -1)) EOF cat > p
         14s bash   cd /tmp/rprobes cat > p19_maxsplit.py <<'EOF' def main():     print("a b c d".split(" ", 0 * (1 << 2000000))) 

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-25T21:07:30Z
