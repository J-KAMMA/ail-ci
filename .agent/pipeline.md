# job job-pre97-10242045  started 2026-10-24T11:45:53Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":604,"duration_api_ms":490,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":464,"duration_api_ms":348,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Recovered the blank item list from `origin/job-pre70-10241829`: the remaining pre-existing difference was qtest2's constant `str.split`/`rsplit` maxsplit above int64.

**Commit:** `0c8a778` — constant maxsplit expressions are folded at compile time. In-range values (including `2**63 - 1`, `-(2**63)`) are emitted directly; out-of-int64 values are refused by name on both builds.

**Probes:** 18 in `/tmp/probes`, each with `cmp.sh` on both general and default builds:
- 9 matched CPython exactly: `big_boundary`, `valid_matrix`, `p97_inrange`, `p97_dynamic` (argument/list/attribute/dict), `p97_keyword`, `p97_nonint`, `p97_empty`, `p97_nofeature`, `p97_aliasing`.
- 9 refused by name: 7 maxsplit-specific (`big_pow`, `neg_big_pow`, `big_pow_rsplit`, `big_pow_none_sep`, `big_pow_kw`, `big_boundary_over`, `p97_huge`) and 2 direct literals (`big_literal`, `p97_literal`, using the older `int64 literal out of range` refusal).

**Tests (final commit, `-j 2`):** `test_ail_pre97`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 168 s, 0 failed. Manifest `--check` rc 0.

**Not changed:** run-time `sep=None` still differs on this tree because pre70's fix is not in this integration; unrelated to this change. Instruction counts not measured (compile-time-only change).
[cost $0.0000, opencode tokens {"total": 7269312, "input": 147902, "output": 17146, "reasoning": 27144, "cache.write": 0, "cache.read": 7077120}]
    tool time: bash 4.3 min, edit 0.0 min, read 0.0 min, write 0.0 min
        169s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre97 test_ail_s
         25s bash   mkdir -p /tmp/probes && cd /tmp/probes && cat > big_literal.py <<'EOF' print("a b c".split(" ", 92233720368547
         20s bash   cd /tmp/probes && cat > p97_inrange.py <<'EOF' def main():     s = "a b c d"     print(s.split(" ", 2**63 - 1)
         17s bash   python3 -m py_compile AIL_CURRENT/python/pkg-v12/pyfunc.py AIL_CURRENT/python/pkg-v12/pyboxed2.py && echo OK; 
         10s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre97
          5s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/python/pkg
          2s bash   cd /tmp && rm -rf dbgbig && mkdir dbgbig && cp /tmp/probes/big_pow.py dbgbig/p.ail && cd dbgbig && AIL_UNIFIED
          2s bash   cd /tmp/probes && cat > p97_aliasing.py <<'EOF' def main():     s = "a b c"     n = 1     a = s.split(" ", n) 

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: pre97 — constant `str.split`/`rsplit` maxsplit

**What the diff really does:** Adds exact compile-time folding of constant-int maxsplit expressions (`_maxsplit_const`/`fold_maxsplit_constant` in `pyfunc.py`) and applies it in the typed SLIST/SPLITN path and in the general emitter (`_str_arg_checks`, `_maxsplit_expr`); in-range values become one literal, values outside int64 raise `Unsupported`. This matches the report.

**Probes** (`bash ~/tools/cmp.sh`, HEAD vs base; `/tmp/rprobes`):

| probe | HEAD | base |
|---|---|---|
| p1 boundary (`2**63-1`, `-(2**63)`, `-1<<63`, `(-2)**63`, `~(-2**63)`, `None` sep, keyword) | both builds == CPython | integer overflow |
| p2 ops (`//`,`%`,`<<`,`>>`,`^`,`|`,`&`,`*`,`-`,`+`,`~`) | both == CPython | — |
| p3 in-range result via >64-bit intermediate (`2**100//2**80`, `2**64>>2`) | both refuse "maxsplit constant does not fit…" | runtime overflow |
| p4 dynamic via arg/list/attr/dict | both == CPython | — |
| p5 unbound `str.split(...)` | both "name 'str' is not defined" | same |
| p6 user-defined `split(sep,n)` with `10**30` | runtime integer overflow | same |
| p7 plain `x=2**63-1`, `2**100//2**80` | integer overflow | same |
| p8 no-feature / p9 dynamic-split C via `--debug-dir` | C identical to base (only temp paths differ) | — |
| p10 direct literals `-9223372036854775808`, `9223372036854775807` | both == CPython | general build refused (`-2**63` case) |
| p11 literal `9223372036854775808` | both "int64 literal out of range" | same |
| p12 runtime `sep=None` | ValueError empty separator | same |
| p13 maxsplit via variable `N=2**63-1` | overflow | same |

**Claim checks**
- Folding + in-range boundary values: verified (p1, p2, p10). Caveat: an in-range *result* reached through an out-of-int64 intermediate is refused, not emitted (p3) — an accepted named refusal, but the report's "in-range values are emitted directly" is not literally complete.
- Out-of-int64 refusal on both builds: verified (p3; p11 older literal message).
- Worker's 18 probes: unverified (not re-run).
- Tests: `test_ail_pre97` + `test_ail_safetynet` pass on HEAD (`-j 2`, 67 s, 0 failed). `test_ail_files`, `test_ail_corpus_findings3` unverified (outside reviewer scope).
- Manifest `--check`: rc 0. Commit has required trailer; no benchmark/example edits.
- "run-time `sep=None` still differs": verified identical on base (p12), pre-existing.

**Pre-existing (not blocking):** p5 unbound `str.split`; p6 user `split` with huge int; p7/p13 general int64 overflow for `2**63-1` in ordinary arithmetic/variables; p12 runtime `sep=None`.

**Unverified:** instruction counts (compile-time-only change; no runtime path touched); worker's exact probe files; `test_ail_files`/`test_ail_corpus_findings3` claim.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 736482, "input": 46841, "output": 4469, "reasoning": 23924, "cache.write": 0, "cache.read": 661248}]
    tool time: bash 1.9 min
         68s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre97 test
         12s bash   date; cd /tmp/rprobes; for p in p3_intermediate p5_unbound p6_user_split p7_nofeature; do echo "===== $p BASE 
         12s bash   date; cd /tmp/rprobes; for p in p1_boundary p2_ops p3_intermediate p4_dynamic p5_unbound p6_user_split p7_nofe
         10s bash   date; cd /tmp/rprobes && cat > p12_runtime_none.py <<'EOF' sep = None print(" a  b ".split(sep)) print(" a  b 
          4s bash   date; cd /tmp/rprobes && cat > p8_plain.py <<'EOF' def add(a, b):     return a + b xs = [1, 2, 3] d = {"k": "v
          4s bash   date; cd /tmp/rprobes && cat > p10_literal_min.py <<'EOF' s = "a b c" print(s.split(" ", -9223372036854775808)
          3s bash   date; cd /tmp/rprobes; echo "===== p1 BASE ====="; bash ~/tools/cmp.sh /tmp/rprobes/p1_boundary.py /tmp/base 2
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git worktree add /tmp/base work 2>&1 | tail -3; date

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-24T12:46:05Z
