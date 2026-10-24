# job job-pre102-10242138  started 2026-10-24T12:39:13Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":480,"duration_api_ms":352,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":466,"duration_api_ms":341,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the first pre-existing difference and committed as `abf94d7` (branch `job-pre102-10242138`).

- Cause: spec parsing ran before value dispatch. `safetyrt.py` now rejects non-empty specs for None and classes without `__format__` with CPython’s `TypeError`, before `ail2f_parse`; str/int/bool/float still parse, custom `__format__` still dispatches first.
- Added `AIL_CURRENT/test_ail_pre102.py`, registered it in `ail_check.MODULES`, updated `DEVLOG.md`, `DIFFERENCES.md`, and `MANIFEST.json` (`--check` passes).

Probes (`bash ~/tools/cmp.sh ...`, both builds):
- `fmt_none.py` — None/Box via literal, argument, list item, dict value, attribute, f-string, str.format, empty spec: matches CPython.
- `fmt_custom.py` — class with `__format__`, including ` +8`: matches.
- `fmt_other.py` — list/tuple/dict/set/range plus valid int/float/str specs: matches.
- `fmt_unknown_nul.py` — still differs; this is the separately listed NUL/non-ASCII pre-existing difference, not changed by this job.

Tests on final commit: `test_ail_pre102`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 26 tests, OK (1 skipped).
[cost $0.0000, opencode tokens {"total": 3163976, "input": 105096, "output": 10255, "reasoning": 11185, "cache.write": 0, "cache.read": 3037440}]
    tool time: bash 13.7 min
        477s bash   cd /home/runner/work/ail-ci/ail-ci && python3 -m unittest AIL_CURRENT.test_ail_pre102 AIL_CURRENT.test_ail_saf
        212s bash   cd /home/runner/work/ail-ci/ail-ci && git status --short && python3 -m unittest AIL_CURRENT.test_ail_pre102 AI
         33s bash   python3 - <<'PY' import pathlib p = pathlib.Path('/tmp/probes/fmt_none.py') s = p.read_text() for line in ("  
         21s bash   cat > /tmp/probes/fmt_none.py <<'EOF' class Box:     def __init__(self, v):         self.v = v     def __str__
         15s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/fmt_none.py /tmp/probes/fmt_unknown_nul.py /tmp/pro
         13s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' import pathlib p = pathlib.Path('AIL_CURRENT/test_ail_p
         12s bash   cat > /home/runner/work/ail-ci/ail-ci/AIL_CURRENT/test_ail_pre102.py <<'EOF' """format() of None / an instance
         11s bash   cd /home/runner/work/ail-ci/ail-ci && bash ~/tools/cmp.sh /tmp/probes/fmt_none.py "$PWD" > /tmp/fmt_none2.log 

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review of `abf94d7` (`work..HEAD`)**

What the diff does: in the general runtime (`safetyrt.py`), any non-empty format spec on a value whose tag is not str/int/bool/float is now rejected with CPython's `TypeError: unsupported format string passed to <type>.__format__` *before* `ail2f_parse`, instead of parsing first. New `test_ail_pre102.py` (registered in `ail_check.MODULES`), plus DEVLOG/DIFFERENCES/MANIFEST updates. This matches the report.

Probes (`/tmp/rprobes`, both builds, HEAD and `/tmp/base`):
- `p_none.py` — None / Box via literal, arg, list item, dict value, attribute, f-string, `str.format`, empty/valid/invalid/NUL specs: HEAD matches CPython on both builds; base gave `ValueError`. Fix verified.
- `p_custom.py` — own/inherited `__format__`, valid int/float/str/bool specs: custom and valid-spec lines match. Remaining diffs (empty-spec object repr, invalid-spec message wording, NUL for int/str) are identical on base.
- `p_types.py` — class, exception class/instance, function, frozenset, range, list/tuple/dict/set with non-empty specs: matches CPython. Only `format([1], '')`-style empty spec on a class differs identically on base.
- `p_bytes.py`, `p_alias.py` — match CPython.
- `p_long.py`, `p_misc.py` — long class-name truncation and generic `function`/`iterator` type names in the message differ from CPython but are **identical on base** (same code path already existed).
- `p_plain.py` — non-format program: generated C byte-identical to base for both general and default builds; behaviour unchanged.

Tests on HEAD: `test_ail_pre102`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules OK (`par_check.py -j 2`). `update_manifest.py --check` passes; commit trailer and DIFFERENCES id/DEVLOG date correct.

Claims: cause/fix, dispatch order, test registration, manifest, probe results and NUL remaining difference all verified. Minor non-defect: the old None/fallthrough block at `safetyrt.py:897-909` is now unreachable dead code.

Pre-existing (identical on base): empty-spec object/class repr, generic type names (`function`, `iterator`, `object`), long class-name truncation, invalid int/float spec message wording, NUL unknown-code for int/str/float.

Unverified: instruction counts (format is not hot); non-BMP/surrogate specs (compiler is ASCII-only); wider suite (not run per review rules).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 988147, "input": 40819, "output": 7271, "reasoning": 11033, "cache.write": 0, "cache.read": 929024}]
    tool time: bash 7.8 min
        340s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1800 python3 ../tools/par_check.py -j 2 test
         24s bash   date; cd /tmp/base; for p in /tmp/rprobes/p_custom.py /tmp/rprobes/p_none.py /tmp/rprobes/p_types.py; do echo 
         18s bash   date; cd /home/runner/work/ail-ci/ail-ci; for p in /tmp/rprobes/p_none.py /tmp/rprobes/p_custom.py; do echo "=
         14s bash   cat > /tmp/rprobes/p_bytes.py <<'EOF' def show(label, f):     try:         print(label, repr(f()))     except 
         13s bash   date; cd /tmp; rm -rf dbg_h dbg_b; mkdir -p /tmp/dbgp; cp /tmp/rprobes/p_plain.py /tmp/dbgp/p.ail; cd /tmp/dbg
         12s bash   cat > /tmp/rprobes/p_types.py <<'EOF' class E(Exception):     pass  class C:     def __init__(self, x):       
         11s bash   date; cd /home/runner/work/ail-ci/ail-ci; for p in /tmp/rprobes/p_types.py /tmp/rprobes/p_alias.py; do echo "=
          5s bash   date; cd /tmp/base; timeout 1200 bash ~/tools/cmp.sh /tmp/rprobes/p_misc.py "$PWD" 2>&1 | tail -40; date

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-24T14:20:22Z
