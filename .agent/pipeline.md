# job job-pre243-10260357  started 2026-10-25T19:02:11Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":332,"duration_api_ms":207,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":332,"duration_api_ms":208,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `d38c32b` on `job-pre243-10260357`.

- Fixed the first still-differing pre225 item: `ValueError: Invalid format specifier` now includes the full spec text and value type, e.g. `Invalid format specifier '=_8,q' for object of type 'int'`. Added `C?-job-pre243-10260357-1`, DEVLOG entries, `test_ail_pre243.py`, registered it, and refreshed the manifest (`--check` passes).
- Probes: `p243_invalid_spec.py` and `p243_extra.py` both match CPython on the general and default builds (`same stdout`), covering int/bool/float/str, long/control/NUL specs, and literal/argument/list/attribute/dict routes. The separate `str` sign-vs-grouping case remains unchanged.
- Final-commit tests (`par_check -j 2`): test_ail_pre243 6.8s, test_ail_safetynet 124.6s, test_ail_files 131.4s, test_ail_corpus_findings3 207.0s — 4 modules, 0 failed.
[cost $0.0000, opencode tokens {"total": 5246091, "input": 127862, "output": 10412, "reasoning": 18665, "cache.write": 0, "cache.read": 5089152}]
    tool time: bash 7.1 min
        334s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre243 test_ail_safetynet test_ail_files test_ai
         31s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre243 test_ail_pre103 test_ail_pre132 test_ail_
         12s bash   for p in /tmp/probes/p243_invalid_spec.py /tmp/probes/p243_extra.py; do echo "==== $(basename $p)"; bash ~/too
         11s bash   mkdir -p /tmp/probes && cat > /tmp/probes/p243_invalid_spec.py <<'EOF' for spec in ['=_8,q', '<7 \x7f', '+ q',
          7s bash   python3 - <<'PY' from pathlib import Path p = Path('AIL_CURRENT/test_ail_pre243.py') s = p.read_text(encoding=
          6s bash   cat > /tmp/probes/p243_invalid_spec.py <<'EOF' class Box:     spec = '=+8,q'   def show(v, s):     try:       
          6s bash   python3 - <<'PY' from pathlib import Path p = Path('/tmp/probes/p243_invalid_spec.py') s = p.read_text() s = s
          6s bash   cat > /tmp/probes/p243_invalid_spec.py <<'EOF' class Box:     spec = '=+8,q'   def show(v, s):     try:       

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review of `job-pre243-10260357` (`d38c32b` vs `work` = `5bf1981`)**

**What the change really does.** `ail2f_parse` now returns a distinct `-2` when more than one type-code char is left; `ail2f_format` maps the value tag to `int`/`bool`/`float`/`str` and `ail2f_invalid_spec` builds `Invalid format specifier '<spec>' for object of type '<type>'` by concatenating the original spec (no repr escaping). Test, DIFFERENCES row, DEVLOGx2 and manifest are added. This matches the report; no extra behaviour.

**Probes** (`bash ~/tools/cmp.sh`, general + default, CPython oracle):
- `p243a_specs.py` (33 specs × 9 int/bool/float/str values: quotes, newline, backslash, DEL, NUL, `é`, 200-char spec, signs, widths, grouping) — all targeted `Invalid format specifier` lines match. Remaining diffs are only `,q`, `, `, `+_`, `+_q`, `=+8,q`.
- `p243b_routes.py` — literal/argument/list/attribute/dict for value and spec: both builds same stdout.
- `p243d_valid.py` — 10 values × 24 valid specs: same stdout.
- `p243e_noformat.py` — same stdout; `--debug-dir` `program.c` byte-identical to base (only temp paths in `native_report.json` differ).
- `p243c_emoji.py`, `p243f_astral.py` — non-BMP literals/`chr()` refused by name (`not in the subset`), acceptable.
- `p243g_bmp_high.py` — single type code `\x80`/`\uffff` still bare `Invalid format specifier`; byte-identical to base.
- Worker probes `p243_invalid_spec.py`, `p243_extra.py` re-run: both builds `same stdout`.

**Pre-existing (identical on base, non-blocking).** Grouping-conflict specs `,q`/`, `/`+_`/`+_q`/`=+8,q` (pre225 fix is not in this exported base); single non-ASCII type code >127 keeps the bare message.

**Claims.** Fixed message — verified. Probes match — verified. `+_` unchanged — verified. DIFFERENCES/DEVLOG/manifest (`--check` exit 0)/test registration/trailer — verified. Worker's `test_ail_files` 131.4s and `test_ail_corpus_findings3` 207.0s — unverified (not re-run, per review scope).

**Tests on HEAD** (`par_check -j 2`): test_ail_pre243 6.7s, test_ail_safetynet 122.5s — 2 modules, 0 failed. Speed: not run; change is error-path/message only.

**Unverified:** files/corpus worker numbers; non-BMP runtime strings (refused by name).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1950573, "input": 66439, "output": 27366, "reasoning": 0, "cache.write": 0, "cache.read": 1856768}]
    tool time: bash 3.2 min
        125s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre243 test_ail_
         26s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p243a_specs.py /tmp/rprobes/p243b_routes.py /tmp/r
         12s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p243_invalid_spec.py /tmp/probes/p243_extra.py; do 
          6s bash   cd /home/runner/work/ail-ci/ail-ci && bash ~/tools/cmp.sh /tmp/rprobes/p243a_specs.py /tmp/base 2>&1 | tail -2
          6s bash   cd /tmp/rprobes && cat > p243g_bmp_high.py <<'PY' def show(v, s):     try:         r = format(v, s)         pr
          6s bash   cd /home/runner/work/ail-ci/ail-ci && bash ~/tools/cmp.sh /tmp/rprobes/p243g_bmp_high.py /tmp/base 2>&1 | tail
          5s bash   set -e; rm -rf /tmp/dbg_head /tmp/dbg_base /tmp/dbgsrc; mkdir -p /tmp/dbgsrc; cp /tmp/rprobes/p243e_noformat.p
          4s bash   cd /tmp/rprobes && cat > p243f_astral.py <<'PY' def show(v, s):     try:         r = format(v, s)         prin

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-25T20:37:47Z
