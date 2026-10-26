# job job-rbpre52-10261857  started 2026-10-26T10:09:31Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":570,"duration_api_ms":450,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":573,"duration_api_ms":456,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `abb68bc` on `job-rbpre52-10261857` (not pushed).

- Re-applied pre52 to `pyboxed2.stmt_Try`: imports guarded by `except ImportError`/`ModuleNotFoundError` are named and located; other caught types now located at the `try`.
- Added `test_ail_pre52.py`; registered in `ail_check.MODULES` and `ci_shards.json`; added DEVLOG/DIFFERENCES entries.
- `tools/diff_ids.py` does not exist on this tree; `tools/update_manifest.py --check` passes.
- Probes: 18 `/tmp/probes/pre52_*` programs; all match CPython or are refused by name on both builds.
- Final-commit tests: `test_ail_pre52`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 186 s, 0 failed.
[cost $0.0000, opencode tokens {"total": 1384197, "input": 49039, "output": 6400, "reasoning": 4982, "cache.write": 0, "cache.read": 1323776}]
    tool time: bash 7.7 min
        221s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pre52 test_ail_safetynet test_a
        187s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check && echo manifest-ok && python3 
         50s bash   cd /home/runner/work/ail-ci/ail-ci && for f in /tmp/probes/pre52_*.py; do echo "===== $(basename $f)"; bash ~/
          2s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-pre52-10241239 2>&1 | tail -20
          1s bash   mkdir -p /tmp/probes && cd /tmp/probes && python3 - <<'PY' from pathlib import Path cases = {  'pre52_import_e
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path dev = Path('DEVLOG.md') entry 
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git add AIL_CURRENT/test_ail_pre52.py AIL_CURRENT/ail_check.py AIL_CURRE
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pre52 test_ail_safetynet test_a

## review 0
[model opencode/deepseek-v4.1-flash-free]
Review complete.

**What the change really does:** in `pyboxed2.stmt_Try`, a caught `ImportError`/`ModuleNotFoundError` whose `try` body contains an import now raises a located `Unsupported` naming those imports (line/column of the first import); other unsupported caught types are now located at the `try`. This is exactly the accepted pre52 diff — `pyboxed2.py` and `test_ail_pre52.py` are byte-identical to `3a815f85..FETCH_HEAD`.

**Claims**
- Re-applied pre52 faithfully — verified (diff identical).
- Test added and registered in `ail_check.MODULES` + `ci_shards.json`, DEVLOG/DIFFERENCES added — verified.
- `tools/diff_ids.py` absent — verified.
- `update_manifest.py --check` passes — verified.
- 18 probes match/refused on both builds — verified on 3 of them plus my own; all by-name.
- Tests 4 modules, ~186 s, 0 failed — verified (189 s, 0 failed).

**My probes** (`/tmp/rprobes`, HEAD vs base, both builds)
- `p1_alias` (`import html as h`, `except ImportError as e`): refused by name at `p.ail:2:5` on HEAD; base refused unlocated — intended.
- `p2_submodule` (`from http import client`): refused, names `'http'` at 2:5.
- `p3_relative` (`from . import thing`): pre-existing local-import refusal, same on base.
- `p4_user_exc` (user class named `ImportError`): pre-existing shadowing refusal, same on base.
- `p5_other_type` (`except KeyboardInterrupt`): refused at `1:1` on HEAD; base unlocated — intended.
- No-feature program `try/except ZeroDivisionError`: `--debug-dir` `program.c` identical to base on both general and default builds.

**Pre-existing** (identical on `/tmp/base`): relative/local import refusal; user class shadowing `ImportError`.

**Unverified:** instruction counts (change is only on a compile-time error path, not hot code).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 434283, "input": 48922, "output": 3085, "reasoning": 4164, "cache.write": 0, "cache.read": 378112}]
    tool time: bash 3.8 min
        190s bash   date && cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pre52 test_ail_safetyne
         11s bash   cd /home/runner/work/ail-ci/ail-ci && for f in p1_alias p2_submodule p3_relative p4_user_exc p5_other_type; do
         11s bash   cd /home/runner/work/ail-ci/ail-ci && for f in p1_alias p2_submodule p3_relative p4_user_exc p5_other_type; do
          8s bash   ls /tmp/probes/pre52_*.py | sed 's#.*/##' && for f in /tmp/probes/pre52_import_as_handler_name.py /tmp/probes/
          3s bash   mkdir -p /tmp/rprobes/nofeat && cat > /tmp/rprobes/nofeat/p.py <<'EOF' def f(x):     try:         return 10 //
          2s bash   cd /tmp/rprobes/nofeat && unset AIL_UNIFIED_FORCE; AIL_NO_CACHE=1 python3 /home/runner/work/ail-ci/ail-ci/AIL_
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git worktree add /tmp/base work 2>&1 | tail -3
          0s bash   mkdir -p /tmp/rprobes && cd /tmp/rprobes && cat > p1_alias.py <<'EOF' try:     import html as h except ImportE

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-26T11:17:59Z
