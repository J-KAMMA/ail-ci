# job job-rbpre23-10242019  started 2026-10-24T11:19:54Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":113762,"duration_api_ms":0,"is_error":true,"num_turns":1,"stop_reason":null,"total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server_tool_use"
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":113907,"duration_api_ms":0,"is_error":true,"num_turns":1,"stop_reason":null,"total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server_tool_use"

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Commit `6d4f904` on `job-rbpre23-10242019` (8 files, +195/−21).

- Re-applied codec-name normalization in `prelude_bytes`, `safetyrt`, `pyboxed2`, `pyfunc`; added `test_ail_pre23.py`, DIFFERENCES row, DEVLOG entry, manifest pins.
- Tests on final commit: `test_ail_pre23`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4/4 passed.
- Probes: p1/p2/p4 match CPython on both builds; p3/p5 refused by name; typed path p4 matches on IR=0/1, p5 refused by name.
- `update_manifest.py --check` passes. `tools/diff_ids.py` does not exist in this tree, so it could not be run. Not pushed.
[cost $0.0000, opencode tokens {"total": 2219124, "input": 67672, "output": 12951, "reasoning": 13957, "cache.write": 0, "cache.read": 2124544}]
    tool time: bash 12.3 min, edit 0.0 min
        327s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pre23 test_ail_safetynet test_a
        252s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pre23 test_ail_safetynet test_a
         51s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p*.py; do echo "===== $(basename $p)"; bash ~/tools
         49s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p*.py; do echo "===== $(basename $p)"; bash ~/tools
         17s bash   cat > /tmp/probes/p4_typed_utf8.py <<'PY' def lit():     return "abc".encode("utf\t8")  def lit_alias():     r
         13s bash   cat > /tmp/probes/p4_typed_utf8.py <<'PY' def lit():     return "abc".encode("utf\t8")  def lit_alias():     r
         11s bash   cat > /tmp/probes/p4_typed_utf8.py <<'PY' def main():     print(repr("abc".encode("utf\t8")))     print(repr("
          7s bash   cd /tmp && rm -rf typedprobe && mkdir typedprobe && cd typedprobe && cp /tmp/probes/p4_typed_utf8.py s4.ail &&

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Change (one line).** It replaces the ad-hoc `lower()/replace()` codec-name matching with an `encodings.normalize_encoding`-style normalizer shared by the bytes prelude and both compile-time checks, and expands the alias tables to the normalised forms of the aliases already present in this tree; test, DIFFERENCES row, DEVLOG and manifest pins are added.

**Claims**
- Re-applied prelude_bytes/safetyrt/pyboxed2/pyfunc hunks: verified — identical to the fetched `job-pre23` diff, and the current tree's extra aliases were retained.
- test_ail_pre23 + row + DEVLOG + manifest pins: verified.
- Targeted tests on final HEAD: verified — `test_ail_pre23`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, 4/4 in 250s.
- Worker probes p1/p2/p4 match, p3/p5 refused by name: verified directly on HEAD; typed path (AIL_NO_GENERAL=1, IR 0/1) also matched.
- `update_manifest.py --check`: verified (exit 0). `tools/diff_ids.py` absent from this tree and from the fetched commit: verified.

**My probes** (`/tmp/rprobes`, `cmp.sh`, general + default): p1 literals, p2 dynamic names via arg/list/dict/attribute and punctuation/aliases, p3 content widths + encode/decode boundaries, p4 non-str encodings and error handlers, p5 plain program, p6 typed-path names, p7 dot aliases — p1/p2/p3/p5/p6 all match CPython; p7 differs identically on base (see below).

**Pre-existing** (identical on base): `iso.8859.1`, `us.ascii` still raise LookupError while CPython accepts them (CPython's alias lookup also tries replacing dots with underscores); `decode(non-str)` reports `encode() argument...` and `None` as `NoneType`.

No-feature C check: `print("hi")` produced byte-identical C on HEAD and `/tmp/base`. The bytes-using p5 C differs only by removal of the now-unused Unicode casemap tables (the old prelude called `.lower()`); behaviour is identical.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2759759, "input": 77660, "output": 8154, "reasoning": 14745, "cache.write": 0, "cache.read": 2659200}]
    tool time: bash 8.3 min
        252s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_
         65s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p*.py; do echo "===== $(basename $p)"; bash ~/tool
         43s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p1_runtime_names.py /tmp/probes/p2_literal_names.py
         26s bash   cat > /tmp/rprobes/p7_dots.py <<'PY' def main():     for name in ["iso.8859.1", "ISO.8859.1", "us.ascii", "utf
         26s bash   cd /home/runner/work/ail-ci/ail-ci && bash ~/tools/cmp.sh /tmp/rprobes/p7_dots.py $PWD >/tmp/p7h.log 2>&1; dh=
         21s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p1_literals.py /tmp/rprobes/p2_dynamic.py /tmp/rpr
         15s bash   rm -rf /tmp/ph2 /tmp/pb2; cp /tmp/rprobes/p5_plain.py /tmp/nmc/q.py; cd /tmp/nmc && AIL_NO_CACHE=1 python3 /ho
         15s bash   rm -rf /tmp/plainh /tmp/plainb /tmp/plainh_dbg /tmp/plainb_dbg; mkdir /tmp/plainh /tmp/plainb; cp /tmp/rprobes

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-24T13:03:11Z
