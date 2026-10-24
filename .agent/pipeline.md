# job job-pre103-10242139  started 2026-10-24T12:39:48Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":810,"duration_api_ms":681,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":694,"duration_api_ms":572,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
**Report**

- Reproduced all four; the first still differing was the single-NUL format code. Fixed in `AIL_CURRENT/python/pkg-v12/safetyrt.py` (`has_type` flag; float keeps CPython’s NUL quirk; control codes use `\x<hex>`).
- Added `AIL_CURRENT/test_ail_pre103.py`, registered it in `ail_check.py` and `ci_shards.json`; added DEVLOG/DIFFERENCES entries; manifest updated and `--check` passes.
- Final probes, all matching CPython on both builds: `p_nul_int.py` (types, widths/sign/group/fill, argument/list/attribute/dict), `p_nul_float.py`, `p_nul_literal.py`, `p_nul_control.py`, `p_valid2.py`.
- Final tests: `test_ail_pre103`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 26 run, OK, 1 skipped (zig/windows target).
- Commit `df828b9` on `job-pre103-10242139`; not pushed. Differences #2–#4 remain untouched.
[cost $0.0000, opencode tokens {"total": 3998097, "input": 120281, "output": 13729, "reasoning": 15511, "cache.write": 0, "cache.read": 3848576}]
    tool time: bash 9.3 min
        461s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && AIL_NO_CACHE=1 python3 -m unittest -v test_ail_pre103 test_a
         32s bash   cat > /tmp/probes/p_nul_literal.py <<'EOF' for x in (1, 'a', True):     try:         print(type(x).__name__, r
         27s bash   python3 - <<'PY' from pathlib import Path p=Path('/tmp/probes/p_nul_int.py') s=p.read_text() s=s.replace("spec
         27s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p_*.py; do echo "===== $p"; timeout 120 bash ~/tool
          6s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && AIL_NO_CACHE=1 python3 -m unittest -v test_ail_pre103 2>&1 |
          2s bash   cd /tmp && mkdir -p dbg && cd dbg && cp /tmp/probes/p_nul_int.py p.ail && AIL_NO_CACHE=1 AIL_QUIET_FALLBACK=1 
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git add AIL_CURRENT/ail_check.py AIL_CURRENT/python/pkg-v12/safetyrt.py 
          0s bash   cd /home/runner/work/ail-ci/ail-ci && grep -rn "fuzz65\|pre51\|fuzz82" DEVLOG.md AIL_CURRENT/DEVLOG.md | head 

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: pre103 single-NUL format code

**What the diff does:** adds `has_type` to `ail2f_spec` so a trailing NUL is no longer indistinguishable from "no type"; int/bool/str now raise CPython's `Unknown format code '\x0'`, float still accepts NUL, and unknown codes are spelled with CPython's `\x<hex>` escaping. One test module, DEVLOG, DIFFERENCES row, manifest/shard registration.

**Claims**
- Reproduced all four, first differing is single-NUL — verified: base returned the value/failed differently for NUL; #2–#4 still differ identically on base and HEAD.
- `has_type`, float NUL quirk, control-code spelling — verified by probes on both builds.
- Test/registration/DEVLOG/DIFFERENCES/manifest `--check` — verified (check rc 0).
- "26 run, OK, 1 skipped" for four modules — unverified (only the two in-scope modules were rerun).
- Commit `df828b9`, not pushed — verified (`ahead 1`).

**Probes** (`cmp.sh`, HEAD vs base)
- `p_nul_single.py`: HEAD g/d identical to CPython; base differs for int/bool/str/float, incl. width/sign/group/`z`/`.`/`#` and argument/list/attribute/dict/literal paths.
- `p_nul_fill.py`: NUL fill + NUL type (`'\x00>5\x00'`) matches CPython on HEAD; base returns padded value.
- `p_nul_float.py`: only diff is `format(1e300,'#\x00')` alt-form, identical on base.
- `p_nul_control.py`: only pre-existing differences (`'\x80'`, multi-char invalid specs).
- `p_other.py`: items #2/#3/#4 reproduced identically on base and HEAD.
- `p_plain.py`: normal formatting matches CPython on both; a format-free program has byte-identical `--debug-dir` C on g and d paths.

**Tests:** `par_check.py -j 2 test_ail_pre103 test_ail_safetynet` → 2 modules, 0 failed, 122s.

**Pre-existing (identical on base, not blocking):**
1. `format(1e300,'#')` (and `'#\x00'`) gives `1e+300`, CPython `1.e+300`.
2. Non-ASCII single code (`'\x80'`) → generic `Invalid format specifier` instead of `Unknown format code '\x80'`.
3. Multi-char invalid spec (e.g. `'\x00d'`, `'dd'`) message lacks spec/type name; None/instance give ValueError instead of TypeError (recorded #2).
4. Default repr `<Box object>` (recorded #3).
5. `chr()` non-BMP internal error (recorded #4).

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3` (not rerun per scope); instruction counts (change is error-path only; no hot-path concern).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 836984, "input": 38880, "output": 5789, "reasoning": 12027, "cache.write": 0, "cache.read": 780288}]
    tool time: bash 3.7 min
        124s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre1
         18s bash   cd /tmp/base && for p in /tmp/rprobes/p_nul_single.py /tmp/rprobes/p_nul_float.py /tmp/rprobes/p_nul_control.p
         18s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p_nul_single.py /tmp/rprobes/p_nul_float.py /tmp/r
         12s bash   cat > /tmp/rprobes/p_plain.py <<'EOF' class Box:     def __init__(self, n):         self.n = n  def main():   
         12s bash   cd /home/runner/work/ail-ci/ail-ci && echo "=== HEAD plain"; timeout 180 bash ~/tools/cmp.sh /tmp/rprobes/p_pl
         10s bash   cat > /tmp/rprobes/p_nul_fill.py <<'EOF' def show(v, s):     try:         print(type(v).__name__, repr(s), rep
         10s bash   cat > /tmp/rprobes/p_alt.py <<'EOF' def show(v, s):     try:         print(repr(v), repr(s), repr(format(v, s)
          8s bash   cat > /tmp/rprobes/p_noformat.py <<'EOF' def main():     xs = [1, 2, 3]     d = {'a': 10, 'b': 20}     s = 0  

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-24T14:11:52Z
