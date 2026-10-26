# job job-pre298-10270442  started 2026-10-26T19:44:06Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":319,"duration_api_ms":194,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":323,"duration_api_ms":196,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Implemented and committed as `b13256e`.

**Fix:** the tree lacked the accepted pre26 change, so direct `repr(e.args[i])`, `f"{e.args[i]!r}"` and `%r` of exception arguments printed/refused the textual form. Added `arg_repr()` + `ail_exc_argrepr` and routed those forms through it; `str`/`print`/`%s` paths are unchanged.

**Probes** (`/tmp/probes/pre298`, both builds):
- `types`, `index_kinds`, `formats`, `escapes`, `pre26test`, `nonrepr`: match CPython on `d`; `g` keeps the pre-existing named multi-argument `raise` refusal.
- `single`: matches CPython on both `g` and `d`.
- `after` (store `x = e.args[i]`, then `repr(x)`): still quotes numeric args; verified identical on base `523c597`, so pre-existing and unrelated.

**Tests on final tree:** `test_ail_pre298`, exception core/app/aggregate/context, `test_ail_exc_str`, `test_ail_excfix`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 10 modules, 488 s, 0 failed.

**Records:** `test_ail_pre298.py` registered in `ail_check.MODULES` and `ci_shards.json`; DEVLOG entry and DIFFERENCES row `C?-job-pre298-10270442-1` added. `update_manifest.py --check` and `ci_shards.py --check` pass.
[cost $0.0463, opencode tokens {"total": 3786635, "input": 112561, "output": 13882, "reasoning": 16928, "cache.write": 0, "cache.read": 3643264}]
    tool time: bash 10.1 min, edit 0.0 min, write 0.0 min
        490s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre298 test_ail_exception_values_core test_ail_e
         33s bash   mkdir -p /tmp/probes/pre298 && cat > /tmp/probes/pre298/types.py <<'EOF' def show(i: int) -> None:     try:   
         18s bash   mkdir -p /tmp/probes/pre298 && cat > /tmp/probes/pre298/multiarg.py <<'EOF' def main() -> None:     try:      
         18s bash   cat > /tmp/probes/pre298/bytes_single.py <<'EOF' def main() -> None:     try:         raise ValueError(b"oops"
         12s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/test_ail_pre298.py') s=p.read_text() s=s.replace
         10s bash   python3 tools/update_manifest.py >/dev/null && cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_p
         10s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre298 2>&1 | tail -40
          9s bash   git worktree add --detach /tmp/base298 523c597 >/tmp/wt.log 2>&1 && for p in after pre26test; do echo "===== b

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review: `b13256e` (pre298)

**What the diff really does:** adds an `_ail_exc_arg_repr` rewrite plus `ail_exc_argrepr()` runtime accessor, routing direct `repr(e.args[i])`, `f"{...!r}"` and `%r` through the stored argument's kind (`ail__exc_piece(..., 1, ...)`); `str`/`print`/`%s` stay on the old text path. It also adds the test module and records. This matches the report.

**Probes** (`/tmp/rprobes`, HEAD; base = `/tmp/base` at `work` 6ce25dd):
- `types`, `floats`, `general`, `indexes`, `formats2`, `traps`, `bytesvals`, `escapes2`, `escapes3`, `oobfmt`, `percent`, `reprroutes`, `attrroute`, `alias`: `d` matches CPython; `g` matches for single-argument cases and gives the pre-existing named multi-argument-`raise` refusal.
- Base: `types` prints quoted numerics (`'7'`, `'True'`, …) and `formats2`/`reprroutes` fail at `%r` — the change genuinely fixes this.
- `nofeat` C is byte-identical base vs HEAD; `exctext` C differs only by the new unused `static ail_exc_argrepr`.
- `after` (`x = e.args[i]; repr(x)`) prints `'2'` on both base and HEAD: pre-existing.
- User-defined `repr` shadowing prints `USER<7>` on both base and HEAD vs CPython's `TypeError`: pre-existing.

**Tests:** `test_ail_pre298`, `test_ail_safetynet` — 2/2 ok, 124 s. `update_manifest.py --check` and `ci_shards.py --check` pass; DEVLOG/DIFFERENCES/registration present. The worker's other 8 test modules were not rerun (reviewer scope). No icount run: no-exception C is identical and exception-text C gains only an unused function, so no hot-path change.

**Claims:** fix verified; no-exception C identity verified; extra-unused-function note verified; `after` pre-existing note verified; 10-module test claim unverified beyond the 2 rerun. No false claims found.

Pre-existing, non-blocking: `x = e.args[i]` then `repr(x)` still quotes numerics; user-defined `repr` on `e.args[i]`; g-path multi-argument `raise` refusal.

VERDICT: ACCEPT
[cost $0.0360, opencode tokens {"total": 1947352, "input": 75183, "output": 8606, "reasoning": 23435, "cache.write": 0, "cache.read": 1840128}]
    tool time: bash 4.7 min
        126s bash   date; cd AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre298 test_ail_safetynet 2>&1
         36s bash   date; for p in /tmp/rprobes/formats2.py /tmp/rprobes/general.py; do echo "########## $(basename $p) HEAD"; tim
         25s bash   date; for p in alias floats bytesvals percent; do echo "########## $p HEAD"; timeout 300 bash ~/tools/cmp.sh /
         21s bash   date; for p in /tmp/rprobes/*.py; do echo "########## $(basename $p)"; timeout 240 bash ~/tools/cmp.sh "$p" "$
         17s bash   cat > /tmp/rprobes/escapes2.py <<'EOF' def main() -> None:     try:         raise ValueError("a'b\"c", "a\tb\r
         10s bash   cat > /tmp/rprobes/specs.py <<'EOF' def main() -> None:     try:         raise ValueError(2.5)     except Valu
          9s bash   cat > /tmp/rprobes/escapes.py <<'EOF' def main() -> None:     try:         raise ValueError("a'b\"c", "a\tb\rc
          9s bash   date; for p in types formats2; do echo "########## $p BASE"; timeout 300 bash ~/tools/cmp.sh /tmp/rprobes/$p.p

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-26T21:26:03Z
