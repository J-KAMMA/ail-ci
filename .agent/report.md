# job job-rbpre36-10261703  started 2026-10-26T08:04:43Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":622,"duration_api_ms":493,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":655,"duration_api_ms":510,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `d7be15d` on `job-rbpre36-10261703` (not pushed).

- Re-applied pre36: added `_const_int` folding and non-BMP constant-expression refusal in `pyboxed2._b_chr`, keeping pre90's literal/surrogate and `WIDE_STRINGS` checks.
- Added `test_ail_pre36.py`; registered in `ail_check.MODULES` and `tools/ci_shards.json`; added DEVLOG + DIFFERENCES row `C?-job-rbpre36-10261703-1`.
- `update_manifest.py --check` and `ci_shards.py --check` pass. `tools/diff_ids.py` does not exist in this tree (could not run).

Probes (`bash ~/tools/cmp.sh`, both builds):
- `pre36_literal`: general refused by name (`U+10000`); default matched CPython.
- `pre36_expr_nonbmp`: general refused by name (`U+1F600`); default matched CPython.
- `pre36_expr_bmp`: both builds matched CPython.
- `pre36_routes`: both builds matched CPython (arg/list/attr/dict, bool, negative/out-of-range/type errors).
- `pre36_alias_bmp`: both builds matched CPython.

Tests: `test_ail_pre36`, `test_ail_pre90`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 33 tests, 533 s, OK (1 skipped).
[cost $0.0000, opencode tokens {"total": 3015936, "input": 72062, "output": 10788, "reasoning": 16094, "cache.write": 0, "cache.read": 2916992}]
    tool time: bash 10.1 min, edit 0.0 min, write 0.0 min
        533s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest test_ail_pre36 test_ail_pre90 test_ail_s
         26s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 600 python3 -m unittest -v test_ail_pre90 2>&1 | tai
         24s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/pre36_*.py; do echo "===== $(basename $p)"; bash ~/
          5s bash   mkdir -p /tmp/probes && printf 'print(chr(0x10000))\nprint(chr(0x1F600))\nprint(chr(0x10FFFF))\nprint(len(chr(
          5s bash   cd /home/runner/work/ail-ci/ail-ci && bash ~/tools/cmp.sh /tmp/probes/pre36_alias_bmp.py "$PWD" 2>&1 | tee /tm
          5s bash   cd /tmp && python3 - <<'PY' import tempfile, subprocess, sys, os from pathlib import Path ROOT=Path('/home/run
          4s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && sed -n '85,115p' test_ail_pre90.py; python3 - <<'PY' import 
          2s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-pre36-10240955 2>&1 | tail -5

## review 0
[model opencode/deepseek-v4.1-flash-free]
Reviewed `d7be15d` against `work`.

**What the change does:** Adds `_const_int` constant-expression folding to `pyboxed2._b_chr`, so `chr()` of a folded non-BMP constant (U+10000..U+10FFFF) is refused by name on the 16-bit general path; keeps pre90's literal surrogate and `WIDE_STRINGS` gating. Also adds `test_ail_pre36.py`, registers it, adds DEVLOG/DIFFERENCES/MANIFEST/shards entries. Matches the accepted pre36 diff, with the pre90 conflict resolved by keeping both checks.

**Probes** (`bash ~/tools/cmp.sh`, HEAD vs `/tmp/base`):
- Non-BMP constants via `+`, `+`, `*`, `<<`, `//`, `%`, `|`, `&`, `^`, `~(-x)` — all refused by name, no runtime fatal; base crashed on all of them. Named refusal is acceptable and strictly better.
- BMP boundaries (`0x7FFF+1`, `0xFFFF`, `0x1FFFF>>1`, `~(-0x10000)`, `0`, `+0xFFFF`) — both builds match CPython.
- Out-of-range constants (`0x10FFFF+1`, `-1`, `-0x10000`, `0x110000`) — both builds match CPython (ValueError).
- BMP via argument/list/attr/dict, bool `chr(True)/chr(False)` — both match.
- Non-BMP via argument/list/attr/dict — both builds still hit the runtime fatal, identical on base.
- Non-`chr` program (`p7_nochr`) — `program.c` byte-identical to base via `--debug-dir` (only temp paths differ in `native_report.json`).
- Literal/simple-expression non-BMP on the default build still matches CPython (`test_ail_pre36` verifies this).

**Pre-existing (not blocking):**
- Non-constant non-BMP values and tuple-context default-build routes still fail with `AIL internal error: chr() non-BMP code point requires 32-bit strings`; identical runtime failure on base.

**Tests:** `test_ail_pre36`, `test_ail_pre90`, `test_ail_safetynet` — 3 modules, 0 failed (149 s). `update_manifest.py --check` and `ci_shards.py --check` pass. `tools/diff_ids.py` is absent from this tree, as reported. Commit has the required co-author trailer; diff touches only expected files.

**Unverified:** worker's full 33-test/533 s run (I reran the targeted subset only); instruction-count speed (change is compile-time only, no runtime hot path touched).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 664497, "input": 31317, "output": 5151, "reasoning": 7997, "cache.write": 0, "cache.read": 620032}]
    tool time: bash 4.2 min, write 0.0 min
        151s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_
         39s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in /tmp/rprobes/*.py; do echo "===== $(basename $p)"; bash
         19s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p1[1-5]_*.py; do echo "===== $(basename $p)"; bash
         15s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p9_simple_expr.py /tmp/rprobes/p10_const_oob.py; d
         13s bash   cd /tmp/base && date && for p in /tmp/rprobes/p1_expr_nonbmp.py /tmp/rprobes/p3_max.py /tmp/rprobes/p4_routes.
          8s bash   cd /tmp/base && for p in /tmp/rprobes/p11_shift.py /tmp/rprobes/p13_bitwise.py; do echo "===== BASE $(basename
          6s bash   set -e; rm -rf /tmp/dbg_head /tmp/dbg_base /tmp/dbgsrc; mkdir -p /tmp/dbgsrc; cp /tmp/rprobes/p7_nochr.py /tmp
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git worktree add /tmp/base work 2>&1 | tail -3; git -C /tmp/base log --o

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-26T09:44:47Z
