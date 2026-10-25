# job job-pre204-10252054  started 2026-10-25T12:06:28Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":582,"duration_api_ms":445,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":554,"duration_api_ms":437,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `fbd378c` on `job-pre204-10252054`.

- Root cause: unary emitters folded only literal operands, so `-(1 << 63)` and `-((1 << 5000) >> 4937)` evaluated overflowing intermediates. All four emitter modes now fold the whole unary constant expression; the exact-fold limit was raised to cover the 5000-bit intermediate.
- Same change also fixed `0 >> (1 << 5000)`, `2 ** ((1 << 2000000) - (1 << 2000000))`, and `(1 << 2000000) >> 2000000`.
- Probes `/tmp/probes/p204_{negmin,boundary,flows,reductions,dynamic}.py` and `p1`–`p4`, `p6` match CPython on both builds. `p5` still has different stderr wording; `p7` (`int("1"*5000, 2)`) still differs, untouched.
- Final-commit tests: `test_ail_pre204`, `pre113`, `pre172`, `pre97`, `pre160`, `safetynet`, `files`, `corpus_findings3` — 8/8 pass in 232s. Manifest and CI-shard checks pass.
[cost $0.0000, opencode tokens {"total": 3194733, "input": 98081, "output": 10734, "reasoning": 15454, "cache.write": 0, "cache.read": 3070464}]
    tool time: bash 5.7 min
        233s bash   cd /home/runner/work/ail-ci/ail-ci; timeout 5400 python3 tools/par_check.py -j 2 test_ail_pre204 test_ail_pre1
         40s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT; timeout 2400 python3 -X utf8 -B -m unittest -q test_ail_pre113
         20s bash   cd /home/runner/work/ail-ci/ail-ci; for f in p1 p2 p3 p4 p5 p6 p7; do echo "=== $f ==="; timeout 600 bash ~/to
         18s bash   cd /home/runner/work/ail-ci/ail-ci; for f in p1 p2 p3 p4 p5 p6 p7; do echo "=== $f ==="; timeout 600 bash ~/to
         16s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT; timeout 1800 python3 -X utf8 -B -m unittest -v test_ail_pre204
         11s bash   cd /home/runner/work/ail-ci/ail-ci; for f in /tmp/probes/p204_*.py; do echo "=== $(basename $f) ==="; timeout 
          2s bash   cd /tmp/probes; sed -i 's/>> 3936/>> 3937/' p204_boundary.py; cd /home/runner/work/ail-ci/ail-ci; timeout 900 
          0s bash   mkdir -p /tmp/probes; cd /tmp/probes; cat > p1.py <<'EOF' print(-(1 << 63)) EOF cat > p2.py <<'EOF' print(-((1

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: pre204 (`fbd378c`)

**What the change really does:** raises `int_constant`'s exact-fold cap from 4096 to 4M bits and makes the unary emitters (`lower.py`, `pyfunc.py`, `pyboxed.py`, `pyboxed2.py`, `unified.py`) fold a whole `+`/`-` constant expression to one in-range int64 literal. This matches the report; the cap was raised to cover the 2M-bit reduction intermediates too, not merely the 5000-bit one.

**Probes** (`/tmp/rprobes`, `cmp.sh` general+default, base `/tmp/base`):
- `p_negmin.py` (INT64_MIN via shift/pow/invert/unary+): matches CPython on HEAD; base fails with `integer overflow`.
- `p_flows.py` (argument, list item, attribute, dict value, alias, return, call): matches.
- `p_reductions.py`, `p_edge.py` (`0>>(1<<5000)`, `2**((1<<2000000)-(1<<2000000))`, `(1<<2000000)>>2000000`, negative-shift/div/mod/bitwise variants): match on HEAD; base overflows.
- `p_more.py` (module constants, class attrs, tuple, float/bool context): matches.
- `p_unrelated.py`, `p_nofeature.py`: stdout matches; `program.c` for the no-feature program is byte-identical base vs HEAD (md5 equal). `p_unrelated.c` differs only by the now-unused `ck_neg` helper, expected for constant unary.
- `p_dynamic.py` still differs at `z = 1<<63; print(z-z)` identically on base.

**Tests:** `test_ail_pre204` and `test_ail_safetynet` pass on HEAD (2/2, 77s). `update_manifest.py --check` and `ci_shards.py --check` return 0. New module is registered in both MANIFEST, `ail_check.py`, and ci_shards.

**Report claims:** root cause and all-emitter fold — verified; limit raise — verified; the three extra reductions fixed — verified; `p1`–`p4`, `p6` correct — verified indirectly (same expressions in my probes); `p5` stderr wording and `p7` still differ, untouched — verified and identical on base; "8/8 tests pass" — only pre204/safetynet re-run (unverified for pre113/pre172/pre97/pre160/files/corpus_findings3).

**Pre-existing (identical on base, do not block):**
- Out-of-int64 results `-(1<<63)-1`, `-(1<<64)`, `-(1<<5000)` → `integer overflow` vs CPython bignums.
- `z = 1<<63; print(z-z)` → overflow at the assignment vs `0`.
- `0 ** (-(1<<5000))` → same stdout/exit, only stderr wording differs.
- `int("1"*5000, 2)` → still differs.

**Unverified:** runtime icount on gdev programs (change is compile-time; no-feature C is bit-identical, so no hot-path effect expected); the six non-re-run test modules.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1679584, "input": 78067, "output": 6878, "reasoning": 29199, "cache.write": 0, "cache.read": 1565440}]
    tool time: bash 2.0 min
         78s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_a
         14s bash   date; cd /home/runner/work/ail-ci/ail-ci; for f in /tmp/rprobes/p_*.py; do echo "===== $(basename $f) HEAD ===
         10s bash   date; cd /tmp/base; for f in /tmp/rprobes/p_negmin.py /tmp/rprobes/p_dynamic.py /tmp/rprobes/p_reductions.py /
          5s bash   cd /tmp/rprobes && cat > p_p5.py <<'EOF' def main():     print(0 ** (-(1 << 5000))) main() EOF cat > p_p7.py <
          5s bash   date; for f in p_p5.py p_p7.py; do echo "== $f BASE =="; timeout 600 bash ~/tools/cmp.sh /tmp/rprobes/$f /tmp/
          3s bash   cd /tmp/rprobes && cat > p_more.py <<'EOF' X = -(1 << 63) Y = -((1 << 5000) >> 4937)   class Box:     a = -(1 
          2s bash   cd /tmp/rprobes && cat > p_edge.py <<'EOF' def main():     print((-(1 << 5000)) >> 4937)     print(((-1) << 50
          1s bash   cd /tmp/rprobes && rm -rf /tmp/dbg_base2 /tmp/dbg_head2; AIL_NO_CACHE=1 AIL_QUIET_FALLBACK=1 python3 /tmp/base

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-25T13:10:43Z
