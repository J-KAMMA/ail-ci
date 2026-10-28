# job job-fz196-10282142  started 2026-10-28T12:44:56Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"7bbc1a03-ebd2-477c-8b76-02a112b296e3","session_id":"b9f38c77-865f-4691-a1dc-480bfc3e2813"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"42bc1667-3554-46b8-b56c-30298d6455eb","session_id":"645db861-2fd6-4a9e-ad1e-ddacaddc44ea"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Implemented and committed as `587f1d85` (not pushed).

**Cause:** `deepseek-v4.1-flash-free/t196.py` uses `Pattern.sub(callable, ...)` with callbacks annotated `re.Match[str]`. An older compiler snapshot sent any callable not named as a bare module-level `def` to the string-template helper, which did `"\\" in repl` and failed with `TypeError: argument of type 'function' is not iterable` (exit 1). On the exported base, the direct `def` case already matched CPython; the same path still misrouted aliases, list items, dict values, arguments, function results and class attributes. Negative `re` `count`/`maxsplit` also differed.

**Fix:** `ail_syntax.py` now emits a runtime-dispatching helper for unknown-kind replacements (`callable(repl)` vs template), refuses instance-attribute replacements and unknown-kind `subn` by name, and `relib.py` treats negative counts/maxsplit as CPython does. Added `AIL_CURRENT/test_ail_fz196.py` (7 tests), registered in `ail_check.MODULES` and CI shards.

**Verification**
- Corpus t196, all 3 inputs × default/IR: `same`, CPython rc=0, AIL rc=0.
- Probes in `/tmp/probes/fz196` on both builds via `cmp.sh`: `p01_exact`, `p02_direct/alias/item/dict/arg/localdef`, `p02a/b/c/e`, `p02f_classfunc`, `p03_none_count`, `p05_bytes`, `p06_phone_tricky`, `p07_receiver_sub`, `p09_counts_split`, `p11_bytes_dyn` match CPython. `p02_classattr`, `p02_routes`, `p02d`, `p04_groups_named`, `p08_bind`, `p10_dynamic_string`, `p12_subn_routes` are refused by name.
- Final commit tests: `test_ail_fz196`, `test_ail_re`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5 modules, 0 failed (724 s).
- `tools/update_manifest.py --check` and `tools/ci_shards.py --check` both exit 0.
[cost $0.1015, opencode tokens {"total": 12023677, "input": 202707, "output": 26363, "reasoning": 33327, "cache.write": 0, "cache.read": 11761280}]
    tool time: bash 62.2 min
        726s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_fz196 test_ail_r
        672s bash   cd /home/runner/work/ail-ci/ail-ci && cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_fz196 test
        597s bash   cd /home/runner/work/ail-ci/ail-ci && : > /tmp/probe_results.txt; for p in /tmp/probes/fz196/*.py; do b=$(base
        343s bash   cd /home/runner/work/ail-ci/ail-ci && python3 -c "import ast; ast.parse(open('AIL_CURRENT/python/pkg-v12/relib
        191s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/fz196/*.py; do echo "=== $(basename $p)"; bash ~/to
        188s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p02a_routes.py p02b_routes.py p02c_routes.py p02d_routes.py p02
        183s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'EOF' from pathlib import Path p = Path('AIL_CURRENT/test_ai
        161s bash   cd /tmp/probes/fz196 && cat > p02_arg.py <<'EOF' import re P = re.compile(r"(\d+)-([a-z]+)") def bump(m: re.Ma

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review: `587f1d85` — fz196 / `re.sub` callable dispatch

**What the diff really does:** in `ail_syntax.re_emit`, an `re.sub` whose replacement kind is not statically known now calls a new runtime helper `Library.sub_any` that branches on `callable(repl)` (callable → `finditer` + call, else `_ail_re_sublit`); instance-attribute replacements and unknown-kind `subn` are refused by name; four re helpers change `count/maxsplit > 0` to `!= 0`. Plus test/shard/manifest/DIFFERENCES/DEVLOG records.

### Probes (`/tmp/rprobes`, `cmp.sh` vs HEAD and `/tmp/base`)
| probe | HEAD g/d | base | note |
|---|---|---|---|
| p1_neg (negative count/maxsplit, template, compiled, callable, subn, split) | same | **DIFF** | base replaced/split; change fixes it |
| p2_routes (arg, list item, dict value, call, alias, lambda) | same | **TypeError** | base bug reproduced |
| p3_cb (None result, zero-width, bytes, bytes neg count) | same | **DIFF** (bytes neg count) | fixed |
| p8_empty, p11_zero (empty subject/pattern, zero-width, negative) | same | — | |
| p12_subn_localstr, p9_badtype, p10_noneres | same rc/stdout | same | |
| p4_runtime_template (runtime `\1` template via arg) | exit 1 both | exit 1 **identical** | pre-existing |
| p6_subn_unknown, p7_static | refused by name | p7 refused on base too | acceptable / pre-existing |
| p13_subn_arg (runtime string template through arg) | **refused by name** | compiled & correct | coverage regression, but a named refusal (allowed) |
| p5_plain + findall-only C | non-re `program.c` byte-identical; re-using C differs only by the `> 0`→`!= 0` helper text | | |

Corpus `t196`, all 3 inputs, default + `AIL_UNIFIED_FORCE=1`: matches CPython rc 0 — **and it already matched on base**, confirming the report's own caveat. The actual t196 failure is not reproducible in this tree; what was fixed is the neighbouring unknown-kind misrouting (verified broken on base by p2).

### Report claims
- Cause and misrouted routes: **verified** (base p2 crashes with the quoted `function is not iterable`).
- t196 already matching on base: **verified**.
- Negative count/maxsplit semantics: **verified** against CPython 3.12 and base.
- Named refusals for instance attribute / dynamic subn: **verified** (tests + p13).
- 7-test module registered in `ail_check.MODULES` and both shard maps: **verified**.
- `update_manifest.py --check` and `ci_shards.py --check`: **verified** (rc 0).
- Final tests `test_ail_fz196 test_ail_re test_ail_safetynet test_ail_files test_ail_corpus_findings3`: **verified** — 5 modules, 0 failed (586 s, `-j 2`).
- Per-probe list from `/tmp/probes/fz196`: not present in worktree; equivalent probes above confirm the outcomes.

### Pre-existing (not blocking)
- Runtime replacement template containing a backslash (via argument) still raises `ValueError` on both builds; CPython supports it.
- `@staticmethod`/method read through a class value is refused on both builds (`reading method C.up through a class value`).
- Non-string callback results differ only in exception text.

### Unverified
- Instruction counts / gdev speed: not measured; the change is one integer comparison in re loops plus a compile-time branch, not hot benchmark code.

**Scope note:** the change fixes more than the stated t196 symptom (unknown-kind callables, negative counts) and narrows `subn`/attribute forms to named refusals. Every narrowing is by name and no silent difference was introduced.

VERDICT: ACCEPT
[cost $0.0225, opencode tokens {"total": 1064254, "input": 53854, "output": 6274, "reasoning": 12766, "cache.write": 0, "cache.read": 991360}]
    tool time: bash 22.9 min
        588s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1500 python3 ../tools/par_check.py -j 2 test
        265s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in /tmp/rprobes/p{1_neg,2_routes,3_cb,4_runtime_template,5
        108s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p4_runtime_template.py; do echo "## BASE $p"; time
        101s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p1_neg.py /tmp/rprobes/p2_routes.py /tmp/rprobes/p
         66s bash   cat > /tmp/rprobes/p12_subn_localstr.py <<'EOF' import re def f():     repl = "X"     return re.subn("a", repl
         49s bash   cd /tmp/t196run && for m in g d; do rm -f exe_$m; if [ "$m" = g ]; then export AIL_UNIFIED_FORCE=1; else unset
         45s bash   cd /tmp && rm -rf t196base && mkdir t196base && cd t196base && cp /home/runner/work/ail-ci/ail-ci/lab/corpus/p
         43s bash   cat > /tmp/rprobes/p13_subn_arg.py <<'EOF' import re def f(r, s):     return re.subn("a", r, s) print(f("X", "

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-28T15:52:15Z
