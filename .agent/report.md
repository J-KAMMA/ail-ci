# job job-pre245-10260358  started 2026-10-25T18:59:38Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":481,"duration_api_ms":354,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":439,"duration_api_ms":314,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the pre-existing p8c difference: `print({(x for x in [1, 2])})` now refuses a generator expression used as a hash key by name on both builds instead of failing with `unhashable type: 'list'`. Ported the pre222 fix with bound-name resolution so user-defined `hash`/`set`/`frozenset`/`tuple` calls still run.

- Probes: 41 in `/tmp/probes/p245_*`; 11 compile-refused, 15 runtime named refusals, 14 match CPython, 1 still differs (`print(g)` repr, pre-existing and out of scope). `p245_bound_param` is a pre-existing base limitation, now named.
- Added `test_ail_pre245.py`, registered in `ail_check` and CI shards; added DEVLOG/DIFFERENCES rows.
- Final commit `0ccd91f`; manifest `--check` rc 0.
- Tests on final commit: `test_ail_pre245`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed, 330 s, `-j 2`.
- Speed: not measured; the runtime change is only on the unhashable-error branch.
[cost $0.0000, opencode tokens {"total": 3572662, "input": 103820, "output": 12290, "reasoning": 15784, "cache.write": 0, "cache.read": 3440768}]
    tool time: bash 8.5 min, edit 0.0 min, write 0.0 min
        332s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pre
        129s bash   cd /tmp/probes; : > p245_results.log; for f in p245_*.py; do echo "===== $f" >> p245_results.log; timeout 240 
         25s bash   cd /tmp/probes; for f in p245_*.py; do echo "===== $f"; timeout 240 bash ~/tools/cmp.sh "$f" /home/runner/work
         17s bash   rm -rf /tmp/base245 && mkdir -p /tmp/base245 && git archive ba07955 | tar -x -C /tmp/base245 && cd /tmp/probes
          2s bash   git fetch --no-tags origin job-pre222-10260116:refs/pre222 2>&1 | tail -5; echo ====; git log refs/pre222 --on
          0s bash   git fetch --no-tags origin job-pre207-10252129:refs/pre207 2>&1 | tail -3; git show refs/pre207:.agent/task.md
          0s bash   mkdir -p /tmp/probes && cd /tmp/probes cat > p245_p8_get.py <<'EOF' d = {1: "one"} g = (x for x in [1, 2]) pri
          0s bash   git ls-remote origin 2>&1 | grep -E 'pre207|job-pre207'

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: pre245 — generator expression as a hash key

**What the change really does:** adds `_check_genexpr_hash_keys` (AST walk in `ail_chatgpt.py`) to refuse, at compile time, a generator expression that a set/dict key context (or `hash`/`set`/`frozenset` over a collection) must hash; and adds the same named `TypeError` to the v2 `ail_obj_hash` default branch in `cruntime.py`, mirrored in `dunderrt.py`. This matches the report.

**Probes** (`/tmp/rprobes`, `bash ~/tools/cmp.sh` on HEAD and `/tmp/base`):

- `r01` p8c `print({(x for x in [1,2])})`: both builds compile-refuse by name (base: `unhashable type: 'list'`). **Fixed.**
- `r02` dict-key literal: both compile-refuse by name.
- `r03` `list(g)` then `{l}`; `r04` `sorted(g)` then `{sorted(g)}`: both builds match CPython (`unhashable type: 'list'`); no flag leak.
- `r05` `set(g)`/`tuple(g)`; `r06` setcomp over genexpr; `r07` `{*g}`; `r08` `{tuple(genexpr):1}`/`{frozenset(genexpr):2}`; `r13` direct consumers: all match CPython.
- `r09` `{tuple([g]):1}`, `r20` IfExp tuple key, `r21` `dict.fromkeys([g])`, `r22` `dict([(g,1)])`, `r23` `set.update([g])`, `r24` `{**{g:1}}`, `r25` `frozenset([g])`: runtime named refusal (base: unhashable list) — accepted named refusal.
- `r10` plain int/tuple/str hashes: tuple/int match; str hash value differs on HEAD **and base** (pre-existing).
- `r11`/`r30` genexpr as dict value, then consumed: match.
- `r12` nested `def set`; `r18` module `hash = lambda`: user code runs, matches.
- `r14` `{listcomp}`; `r31` `hash([genexpr])`: unhashable list, matches.
- `r16` no-feature program: identical to CPython except set iteration order, **identical on base**.
- `r27` mutate `list(g)`/`[*g]` copies then hash: matches.
- `r28` empty genexpr key: compile-refuse; `r29` saved empty: runtime named refusal.
- `r32` `print(g)`: differs (list repr) **identically on base** (pre-existing).

**Claims:**
- p8c fixed, both-build refusal, runtime named refusal, list/sorted copies, consumption/dict-value parity, test registration, CI shard, DEVLOG/DIFFERENCES row, commit `0ccd91f`, manifest `--check` rc 0: **verified**.
- “Bound-name resolution so user-defined calls still run”: **partially false**. Nested `def` shadowing and module-level `hash = ...` work, but a *local assignment* (`tuple = lambda...` inside a function) and a *parameter* (`def f(set)`) are still resolved as builtins by the general path: `r33` and `p245_bound_param` refuse at run time where CPython prints a result. This is **pre-existing** (base also exits 1, only with `unhashable type: 'list'`), so it is a record-wording overclaim, not a behavioural regression.
- Worker’s 41-probe tally: not re-run; my probes cover the same boundaries.
- “4 modules, 0 failed”: I re-ran only `test_ail_pre245` + `test_ail_safetynet` (2 modules, 0 failed, 123 s, `-j 2`); `test_ail_files`/`test_ail_corpus_findings3` unverified (reviewer scope).
- “Speed not measured, no hot-path effect”: **verified by inspection** — the runtime branch is in the hash `default` (error) path, and a `--debug-dir` diff of a no-feature program shows only that added branch.

**Pre-existing (identical on base):** str hash values (`r10`), set iteration order (`r16`), `print(g)`/tuple-holding-genexpr repr (`r32`, `r26`), builtin-shadowing via parameter/local assignment (`p245_bound_param`, `r33`).

**Unverified:** full suite, `test_ail_files`/`test_ail_corpus_findings3`, instruction counts (perf not needed), v1 general path (`AIL_GENERAL=v1`, which has no runtime refusal; not one of the two cmp.sh builds).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 3789978, "input": 54078, "output": 9612, "reasoning": 38992, "cache.write": 0, "cache.read": 3687296}]
    tool time: bash 4.9 min, write 0.0 min
        125s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre2
         43s bash   cd /tmp/rprobes && for f in r*.py; do echo "===== $f"; timeout 180 bash ~/tools/cmp.sh "$f" /home/runner/work/
         33s bash   cd /tmp/rprobes && for f in r13_direct_consumers.py r14_plain_list_comp.py r15_star_var.py r16_no_feature.py r
         25s bash   cd /tmp/rprobes && for f in r21_fromkeys.py r22_dict_ctor.py r23_set_update.py r24_dict_merge.py r25_frozenset
         17s bash   cd /tmp/rprobes && for f in r27_mutated_copy.py r28_empty.py r29_empty_runtime.py r30_dictvalue_hash.py; do ec
         12s bash   cd /tmp/rprobes && for f in r01_p8c.py r09_tuple_holding_gen.py r10_plain.py; do echo "===== BASE $f"; timeout
          8s bash   cd /tmp/probes && echo "== HEAD"; timeout 180 bash ~/tools/cmp.sh p245_bound_param.py /home/runner/work/ail-ci
          8s bash   cd /tmp/rprobes && echo HEAD; timeout 180 bash ~/tools/cmp.sh r32_print_g.py /home/runner/work/ail-ci/ail-ci 2

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-25T20:39:52Z
