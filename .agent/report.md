# job job-pre48-10270755  started 2026-10-26T22:56:53Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":403,"duration_api_ms":281,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":392,"duration_api_ms":270,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done.

- Merged current `origin/integ` (pre298 already had direct `repr(e.args[i])`), then re-applied the missing pre48 pieces: file OSError `args == (errno, strerror)` in `filert.py`, and typed-path refusal when `e.args[i]` is stored in a name/container/attribute/function argument.
- Added/updated `test_ail_pre48.py`, `ail_check.py`, `DEVLOG.md`, `DIFFERENCES.md` (`C?-job-pre48-10270755-1`); manifest updated and `--check` passes.
- Final tests on commit `dcd5c52`: `test_ail_pre48`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_pre298` — 5 modules, 341 s, 0 failed.
- Probes in `/tmp/probes`: `p48_file_oserror.py`, `p48_manual_oserror3.py`, `p48_direct_repr.py`, `p48_alias_routes.py`. File-OSError, direct-repr and alias probes match CPython on both `cmp.sh` builds; `p48_manual_oserror3.py` matches on the default build and is refused by name on the forced general build (pre-existing multi-argument `raise OSError` limitation).
[cost $0.0455, opencode tokens {"total": 4240404, "input": 120079, "output": 9630, "reasoning": 15719, "cache.write": 0, "cache.read": 4094976}]
    tool time: bash 12.3 min, edit 0.0 min
        344s bash   python3 ../tools/par_check.py -j 2 test_ail_pre48 test_ail_safetynet test_ail_files test_ail_corpus_findings3 
        127s bash   python3 -m unittest -q test_ail_safetynet 2>&1 | tail -80
        126s bash   python3 -m unittest -q test_ail_safetynet 2>&1 | tail -60
         33s bash   python3 ../tools/par_check.py -j 2 test_ail_pre48 test_ail_pre298 test_ail_pre26 2>&1 | tail -60
         31s bash   python3 -m unittest -q test_ail_pre48 2>&1 | tail -80
         30s bash   python3 -m unittest -q test_ail_pre48 2>&1 | tail -60
         18s bash   mkdir -p /tmp/probes && cat > /tmp/probes/p48_file_oserror.py <<'PY' def main() -> None:     try:         open
         13s bash   cat > /tmp/probes/p48_alias_routes.py <<'PY' class Box:     def __init__(self) -> None:         self.v = 0.0  

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review — job-pre48-10270755 (HEAD `dcd5c52` vs integ `8346862`)

Start 23:13, end 23:25. No source edits made.

**What the change really does (one line):** re-applies pre48 on integ — the general file-OSError adapter now builds `args == (errno, strerror)` and keeps only `filename`/`filename2` as attributes (`filert.py`), and the typed exception rewrite refuses `e.args[i]` when it is stored in a name/container/attribute/user-call argument (`exctext.py`); adds `test_ail_pre48.py` and its registry/manifest/docs entries. This matches the report. (Diff vs integ also carries `corpus/gdev` and `.agent` files already present in the `work` ancestry; not authored by this job.)

**Tests on HEAD** (`par_check.py -j 2`): `test_ail_pre48` 30.4s ok, `test_ail_safetynet` 131s ok, `test_ail_files` 138s ok, 0 failed. `manifest --check` passes.

**Probes** (`cmp.sh`, HEAD g/d, plus typed-only):
- `p_os_file` (open missing, open dir): HEAD both builds = CPython; base general prints 3-element args → change fixes it. Typed build also matches.
- `p_os_rename` (`os.rename`/`os.replace` failures): HEAD both = CPython (`args` length 2, `filename`/`filename2` intact); base general = 3-element args.
- `p_os_stable` (overwrite the failed path, allocate, then reread `e.args`/`e.filename`): HEAD both = CPython; values stable; base general wrong args only.
- `p_file_alias` (file OSError `s = e.args[1]`): HEAD default = CPython, typed = named refusal (`storing an exception argument e.args[i] ...`).
- `p_elem_alias` (name/list/dict/attribute/function argument): HEAD g/d = CPython; typed named refusal; base typed failed with an obscure type error.
- `p_dyn_index` (dynamic/negative index in direct `repr`): typed = CPython on HEAD and base.
- `p_args_slice`, `p_plain`: HEAD = CPython; plain `program.c` identical to base.
- Worker probes `p48_file_oserror`, `p48_direct_repr`, `p48_alias_routes` = CPython both builds; `p48_manual_oserror3` = CPython default, named refusal general. All verified.

**Pre-existing** (identical on base, not blocking):
- `raise OSError(2, "gone")` then `e.filename`: expected `None` / `FileNotFoundError(2, 'gone')`; actual `RuntimeError: this OSError carries no filename in a compiled program` (`p_os_manual2`).
- Whole `e.args` passed to `%r`/tuple: expected `3.0`, actual `(3.0,)`; reproduced with a plain tuple (`p_tuple_percent`), so it is the general `%`-with-tuple rule, not this change.
- Multiple-argument `raise ValueError/OSError` refused by the general path (seen throughout).

**Unverified:** `test_ail_pre298` and `test_ail_corpus_findings3` (not run per review scope). Speed: no runtime path added (alias checks are compile-time; no C change for programs not reading exception args), so no icount run.

VERDICT: ACCEPT
[cost $0.0322, opencode tokens {"total": 1639373, "input": 73424, "output": 7543, "reasoning": 20102, "cache.write": 0, "cache.read": 1538304}]
    tool time: bash 7.1 min
        140s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 600 python3 ../tools/par_check.py -j 2 test_ail_file
        133s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre4
         28s bash   cat > /tmp/typecmp.sh <<'EOF' #!/bin/bash src=$1; wt=$2; d=$(mktemp -d /tmp/tcmpXXXX); cp "$src" $d/p.ail; cd 
         24s bash   cd /tmp/rprobes && for p in p_os_args p_args_whole_alias p_args_slice p_elem_alias p_plain; do echo "===== $p 
         19s bash   cd /tmp/rprobes && for p in p_os_file p_os_manual2 p_args_whole_alias p_args_slice; do echo "===== $p BASE"; b
         19s bash   cd /tmp/probes && for p in p48_file_oserror p48_manual_oserror3 p48_direct_repr p48_alias_routes; do echo "===
         14s bash   cd /tmp/rprobes && cat > p_os_stable.py <<'PY' import os  def main() -> None:     p = "rprobe_stable_xyz.txt" 
         12s bash   cd /tmp/rprobes && cat > p_file_alias.py <<'PY' def main() -> None:     try:         open("rprobe_missing_zzz.

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-27T00:39:28Z
