# job job-pre195-10251916  started 2026-10-25T10:29:05Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":532,"duration_api_ms":415,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":517,"duration_api_ms":399,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the maxsplit folder: powers are now folded under the same 4096-bit bound as the other constant folder, so `"a b c".split(" ", 2**100 // 2**80)` works on both builds.

- Commit: `3f29957`
- Tests: `test_ail_pre195`, `test_ail_pre97`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5 modules, 0 failed (224s)
- Probes: p1, p2, p4, p5, p6 match CPython on both builds; p3 (`2**100`) and p7 (`2**2049 // 2**2029`) are refused by name, with p7's remaining >4096-bit fold limit recorded in DIFFERENCES.
- Manifest updated; `--check` passes.
[cost $0.0000, opencode tokens {"total": 1189978, "input": 57912, "output": 7026, "reasoning": 11312, "cache.write": 0, "cache.read": 1113728}]
    tool time: bash 4.7 min, edit 0.0 min
        225s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pre195 test_ail_pre97 test_ail_
         18s bash   cd /tmp/probes && cat > p6_boundary.py <<'EOF' print("a b c".split(" ", 2**2048 // 2**2028)) EOF cat > p7_over
         16s bash   cd /tmp/probes && for p in p1_direct p2_pow_div p3_pow_out p4_routes p5_negative; do echo "===== $p ====="; ba
         13s bash   cd /tmp/probes && for p in p1_direct p2_pow_div p3_pow_out p4_routes p5_negative; do echo "===== $p ====="; ba
         11s bash   cd /home/runner/work/ail-ci/ail-ci && python3 AIL_CURRENT/test_ail_pre195.py -v 2>&1 | tail -40
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git status --short && git add AIL_CURRENT/python/pkg-v12/pyfunc.py AIL_C
          0s bash   cd /home/runner/work/ail-ci/ail-ci && head -80 DEVLOG.md && head -60 DIFFERENCES.md && ls AIL_CURRENT/test_ail
          0s bash   ls -la && git status && git branch --show-current && git log --oneline -5

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change does:** in `_maxsplit_const` (pyfunc.py:627) the `Pow` branch replaces the old `right >= 64` cutoff with `left.bit_length() * right > 4096`, so maxsplit powers are folded instead of refused by exponent.

**Probes (both builds vs CPython, `/tmp/rprobes`):**
- Target fix: `p1_orig` (`2**100 // 2**80`, rsplit `2**200 // 2**180`) — base refuses, HEAD matches CPython on g and d. Verified.
- `p2_neg`, `p3a_bound`, `p4_routes` (argument/list/attribute/dict/local), `p5_small_bases`, `p7_types`, `p8_shift` — match on both builds. Verified.
- `p3b_over` (`2**2049 // 2**2029`) and `p9_huge` — refused by name on base and HEAD. Acceptable, as reported.
- Non-feature `p10_plain`: `--debug-dir` `program.c` identical to base (only temp paths in native_report.json differ).
- **Regression `p6_regress`:** builds and matches on base, refused on HEAD (both builds). New defect caused by the change.

**Report claims:** target fix verified; tests `pre195`, `pre97`, `safetynet`, `files`, `corpus_findings3` all pass on HEAD (5 modules, 0 failed); manifest `--check` passes; DEVLOG/DIFFERENCES present. Claim "same bound as the other folder ... folds exactly" is misleading: the bound is a conservative upper estimate, not the actual result width, and it narrows previously accepted input. Worker's own p1–p7 not re-inspected.

**Unverified:** speed (compile-time-only change, no runtime C change), worker's probe files.

VERDICT: FIX
1. The new `Pow` guard rejects in-range constants whose exact value fits the 4096-bit fold limit, so HEAD refuses programs the base compiled and CPython runs. Probe:
   ```
   print("a b c".split(" ", ((2**63 * 4)**63) >> 4095))
   ```
   Value is `(2**65)**63 >> 4095 == 1`. Expected: CPython and base both print `['a', 'b c']`. Actual HEAD (general and default): build refused with "maxsplit constant does not fit in a 64-bit signed integer". Cause: `left.bit_length()*right = 66*63 = 4158 > 4096`, although the actual intermediate `2**4095` is within the folder's own 4096-bit limit; the old `right < 64` rule accepted it. The guard must bound the actual result width (e.g. `(left.bit_length()-1)*right+1`), not `bit_length(left)*exponent`.
[cost $0.0000, opencode tokens {"total": 769535, "input": 33753, "output": 4139, "reasoning": 11771, "cache.write": 0, "cache.read": 719872}]
    tool time: bash 4.7 min, read 0.0 min
        133s bash   date; cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_files test_ail_corpus_fin
         80s bash   date; cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pre195 test_ail_safetynet
         23s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check 2>&1 | tail -5; echo rc=$?; pyt
         21s bash   cd /tmp/rprobes cat > p3a_bound.py <<'EOF' print("a b c".split(" ", 2**2048 // 2**2028)) print("a b c".split("
         15s bash   cd /tmp/rprobes && for p in p6_regress p3b_over p9_huge; do echo "######## BASE $p"; bash ~/tools/cmp.sh /tmp/
          5s bash   cd /tmp/rprobes cat > p11_i64.py <<'EOF' print("a b c".split(" ", 2**63 - 1)) print("a b c".split(" ", -2**63)
          3s bash   cd /tmp/rprobes && echo BASE p1; bash ~/tools/cmp.sh /tmp/rprobes/p1_orig.py /tmp/base 2>&1 | tail -12; echo H
          2s bash   rm -rf /tmp/dbgcmp; mkdir -p /tmp/dbgcmp; cd /tmp AIL_NO_CACHE=1 python3 /tmp/base/AIL_CURRENT/ail_chatgpt.py 

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed the reviewer's regression in `_maxsplit_const` (`AIL_CURRENT/python/pkg-v12/pyfunc.py:592`): powers are now tested against their exact result width with capped square-and-multiply, so 4096-bit intermediates are accepted instead of refused by the `bit_length(base) * exponent` overestimate. Genuinely wider intermediates are still refused by name.

Probes (final commit, both g/d builds vs CPython):
- `p_regress` `((2**63*4)**63)>>4095`, `p_orig`, `p_boundary`, `p_neg`, `p_routes`, `p_types`: match CPython.
- `p_over_literal`, `p_over_reduced`, `p_over_intermediate`: refused by name.

Updated `test_ail_pre195.py` (adds the regression, `2**2049//2**2029`, 4096-bit boundary, genuine over-limit refusal) and corrected DEVLOG/DIFFERENCES. Manifest `--check` passes.

Final-commit tests: `pre195`, `pre97`, `safetynet`, `files`, `corpus_findings3` — 5 modules, 0 failed.

Commit `a479d15`, message ends with the required co-author line. Only pre-existing untracked `.agent/pipeline.md` remains uncommitted.
[cost $0.0000, opencode tokens {"total": 1554962, "input": 52701, "output": 9449, "reasoning": 12620, "cache.write": 0, "cache.read": 1480192}]
    tool time: bash 6.0 min, write 0.0 min
        132s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check && date && python3 tools/par_ch
        129s bash   cd /home/runner/work/ail-ci/ail-ci && date && python3 tools/par_check.py -j 2 test_ail_pre195 test_ail_pre97 t
         43s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/*.py; do echo "######## HEAD $(basename $p)"; bash 
         16s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p_regress.py /tmp/probes/p_orig.py /tmp/probes/p_bo
         13s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p_regress.py /tmp/probes/p_orig.py /tmp/probes/p_bo
         13s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p_regress.py /tmp/probes/p_orig.py /tmp/probes/p_bo
          6s bash   cd /home/runner/work/ail-ci/ail-ci && date && python3 tools/par_check.py -j 2 test_ail_pre195 2>&1 | tail -25
          4s bash   cd /tmp && rm -rf pbi && mkdir pbi && cd pbi && i=0; while IFS= read -r line; do i=$((i+1)); printf '%s\n' "$l

## review 1
[model opencode/deepseek-v4.1-flash-free]
## Review

**What the change does (one line):** In `_maxsplit_const` (`AIL_CURRENT/python/pkg-v12/pyfunc.py:649`), the power branch replaces the blanket `right >= 64` refusal with a 4096-bit bound checked by capped square-and-multiply on the actual power width, then folds the exact value; final out-of-int64 and >4096-bit intermediates are still refused by name.

**Probes (HEAD, both g/d builds vs CPython):**
- `rv1_orig`: `2**100//2**80`, `2**200//2**180`, `3**50//3**30`, `2**64//2**4` → match. Base refuses (pre-existing bug now fixed).
- `rv2_reduce`: `((2**63*4)**63)>>4095`, `(2**63)**65>>4095`, `2**4095//2**4050`, `2**100>>80`, `(-2)**101//(-2)**81` → match. Base refuses all (pre-existing).
- `rv3_neg_small`: negative bases/results, `0**5000`, `1**100000`, `(-1)**odd/even`, `2**100//2**100` → match.
- `rv4_routes`: same value via argument, list item, attribute, dict value, local → match (base also passes this shape).
- `rv5_bound`: 4095-bit shift/power boundaries, `(2**64)**63>>4095`, `(-2)**64>>64`, `(-2)**63>>0` → match. Base refuses the ≥64-exponent lines (named, pre-existing).
- `rv6_over_inter` (`2**4096//2**4050`) and `rv8` (`2**4096>>4096`): refused by name, same as base; acceptable named refusal.
- `rv7_over_final` (`2**100`): refused by name; base same.
- Non-feature program: `program.c` from `--debug-dir` byte-identical to base; only temp-path fields differ in `native_report.json`.

**Tests:** `test_ail_pre195` and `test_ail_safetynet` on HEAD → 2 modules, 0 failed. `tools/update_manifest.py --check` rc=0. Commit `a479d15` has the required co-author line; only untracked `.agent/pipeline.md` remains.

**Report claims:**
- Original `2**100//2**80` now matches CPython on both builds — **verified**.
- Exact-width power test accepts 4096-bit intermediates instead of overestimate refusal — **verified** (rv2/rv5).
- Genuinely wider intermediates still refused by name — **verified** (rv6/rv8).
- Test/DEVLOG/DIFFERENCES updates and manifest check — **verified**.
- Final-commit module list — **verified for the two modules I was asked to run**; the other three were not re-run here.

**Pre-existing (identical on base, not blocking):** `2**4096//2**4050`, `2**4096>>4096`, and direct out-of-int64 maxsplit remain named compile-time refusals where CPython computes/raises at run time.

**Unverified:** wider suite (per instructions); instruction-count speed (change is compile-time constant folding only, no hot path).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 332931, "input": 25809, "output": 3619, "reasoning": 11407, "cache.write": 0, "cache.read": 292096}]
    tool time: bash 1.7 min
         67s bash   date; cd /home/runner/work/ail-ci/ail-ci && timeout 900 python3 tools/par_check.py -j 2 test_ail_pre195 test_a
         11s bash   date; for p in /tmp/rprobes/rv1_orig.py /tmp/rprobes/rv2_reduce.py /tmp/rprobes/rv3_neg_small.py /tmp/rprobes/
          7s bash   mkdir -p /tmp/rprobes && cat > /tmp/rprobes/rv1_orig.py <<'EOF' print("a b c".split(" ", 2**100 // 2**80)) pri
          5s bash   date; for p in /tmp/rprobes/rv5_bound.py /tmp/rprobes/rv6_over_inter.py; do echo "######## BASE $(basename $p)
          5s bash   cat > /tmp/rprobes/rv5_bound.py <<'EOF' print("a b c".split(" ", 2**4095 >> 4095)) print("a b c".split(" ", (2
          3s bash   date; mkdir -p /tmp/rprobes/dbg && printf 'print("a b c".split(" ", 2**100 // 2**80))\n' > /tmp/rprobes/dbg/on
          1s bash   date; mkdir -p /tmp/rprobes/dbg2 && cat > /tmp/rprobes/dbg2/plain.py <<'EOF' def main():     xs = [1, 2, 3]   
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git log -1 --format='%H%n%B' | head -10; echo ---; python3 tools/update_

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-25T11:39:27Z
