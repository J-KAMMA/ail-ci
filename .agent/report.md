# job job-pre427-10281842  started 2026-10-28T09:43:29Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"56f33e2d-c28b-4652-b532-ee374a44cb6d","session_id":"b1dc4451-ceda-4b8e-a336-dea29da483b3"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"ee6316d5-a549-4c20-bd30-b602be46bcc2","session_id":"6922518d-e587-4d68-9bf2-a57e16c9b13b"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the first still-differing pre-existing item: a positional-only lambda.

- Before: `list(map(lambda x, /, y: y * 2, [5]))` printed `[10]` and `sorted([3,1,2], key=lambda x, /, y: y)` printed `[1,2,3]`; CPython raises `TypeError` because `x` consumes the argument and `y` is missing. The map/key lowerings read only `args.args` and dropped `posonlyargs`.
- Fix: every lambda with a positional-only parameter is now refused by name on both builds at the Python-surface pass, with a second check in `pyc.py` for bypassing sources.
- Probes: 17 relevant probes run after the fix; all either match CPython or are refused by name. Posonly map/key/multi/body-first/nested/returned/direct/mixed/default forms are refused; `def` posonly and vararg `def` controls match CPython; kwonly/vararg lambdas keep their existing refusals.
- Tests on final commit `717227e`: `test_ail_pre427`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed.
- Records updated; `update_manifest.py --check` passes. Wider suite not run per instructions.
[cost $0.0000, opencode tokens {"total": 5315351, "input": 144807, "output": 13003, "reasoning": 17061, "cache.write": 0, "cache.read": 5140480}]
    tool time: bash 11.9 min, edit 0.0 min, write 0.0 min, read 0.0 min
        237s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre427 test_ail_safetynet test_ail_files test_ai
        233s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_files test_ail_corpus_findings3 test_ail_safetyn
         59s bash   mkdir -p /tmp/probes cat > /tmp/probes/lp_key_posonly.py <<'EOF' print(sorted([3, 1, 2], key=lambda x, /: -x))
         41s bash   for p in /tmp/probes/lp_posonly_ignored.py /tmp/probes/lp_posonly_ignored_key.py /tmp/probes/lp_posonly_multi.
         38s bash   cat > /tmp/probes/lp_posonly_ignored.py <<'EOF' print(list(map(lambda x, /, y: y * 2, [5]))) EOF cat > /tmp/pr
         34s bash   for p in /tmp/probes/lp_*.py; do echo "===== $p"; bash ~/tools/cmp.sh "$p" "$PWD"; done 2>&1 | tee /tmp/probes
         33s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre427 2>&1 | tail -60
         19s bash   for p in /tmp/probes/lp_posonly_ignored.py /tmp/probes/lp_posonly_ignored_key.py /tmp/probes/lp_posonly_multi.

## review 0
[model opencode/deepseek-v4.1-flash-free]
Reviewed `717227e` against `work` (base worktree at `/tmp/base`).

**What the change does:** Adds an early `ast`-walk refusal for any `lambda` whose `args.posonlyargs` is non-empty, in `python_surface` (`ail_syntax.py:3380`) and again in `pyc.build` (`pyc.py:743`), plus a new test module and records.

**Probes (31, both builds via `cmp.sh`):**
- Base reproductions: `p01` map and `p02` key produced `[10]` / `[1, 2, 3]` on both base builds. On HEAD both are refused by name on both builds: correct.
- Posonly routes: direct, nested, returned, default, attribute, list item, dict value, argument, tuple, `reduce`, f-string, multi-iterable, class body, comprehension, typed `Callable` are all refused by name on both HEAD builds (base mostly refused with a different name).
- Controls: plain lambda, division + lambda, strings/comments containing `lambda x, /`, division only, posonly `def`, mixed posonly `def` + plain lambda, kwonly/vararg lambda/def all behave as reported; `p04/p05/p06/p17/p21/p22/p31` match CPython.
- `--debug-dir` `program.c` for `p04/p05/p06` is byte-identical to `/tmp/base` (only `native_report.json` temp paths differ). No C change when the feature is unused.
- Pre-existing: no new difference observed; base refusals that differ only in wording are not counted.

**Tests on HEAD:** `test_ail_pre427`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed.

**Report claims:** base output claim verified; fix on both builds verified; kwonly/vararg refusals unchanged verified; test results verified; `update_manifest.py --check` exits 0 verified; wider suite not run is consistent. The "second check in `pyc.py` for bypassing sources" exists in code but I did not construct a source that bypasses `python_surface`, so that particular route is unverified.

**Defect found:** the new regression test is not registered, so the integrator/CI suite never runs it.

VERDICT: FIX
1. `AIL_CURRENT/test_ail_pre427.py` is not added to `ail_check.MODULES` or `tools/ci_shards.json`, and has no `MANIFEST.json` pin.
   Probe: `cd AIL_CURRENT && python3 -c "import ail_check; print('test_ail_pre427' in ail_check.MODULES)"`
   Expected: `True` (then `par_check.py` with no module list and the CI shards run it).
   Actual: `False`; `python3 tools/ci_shards.py --shard 0` contains no `test_ail_pre427`, so the new test runs nowhere after merge.
[cost $0.0000, opencode tokens {"total": 2012081, "input": 77494, "output": 7240, "reasoning": 29235, "cache.write": 0, "cache.read": 1898112}]
    tool time: bash 7.1 min
        233s bash   date; cd AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_pre427 test_ail_safetynet tes
         62s bash   cd /tmp/rprobes; for p in p*.py; do echo "########## $p"; bash ~/tools/cmp.sh "$p" /tmp/base 2>&1 | grep -v '^
         28s bash   cd /tmp/rprobes cat > p27_map_vararg.py <<'EOF' print(list(map(lambda *a: sum(a), [1, 2, 3]))) EOF cat > p28_m
         28s bash   cd /tmp/rprobes; for p in p*.py; do echo "########## $p"; bash ~/tools/cmp.sh "$p" /home/runner/work/ail-ci/ai
         21s bash   cd /tmp/rprobes cat > p18_key_ok.py <<'EOF' print(sorted([3, 1, 2], key=lambda x, /: -x)) EOF cat > p19_map_ok
         16s bash   cd /tmp/rprobes cat > p23_arg.py <<'EOF' def call(f):     return f(5) print(call(lambda x, /, y: y)) EOF cat >
         11s bash   cd /tmp/probes; for p in lp_classbody_posonly.py lp_comp_posonly.py lp_typed_callable_posonly.py; do echo "###
         10s bash   cd /tmp && rm -rf cdbase cdhead && mkdir cdbase cdhead for f in p04_plain_map p05_div_lambda p06_strings; do c

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed the defect and committed as `42897f8`.

- Registered `test_ail_pre427` in `ail_check.MODULES`, placed it on CI shard 4 via `ci_shards.py --update`, and pinned it in `MANIFEST.json`.
- Checks: `update_manifest.py --check` = 0, `ci_shards.py --check` = 0, registration probe = `True`.
- Probes: all 40 in `/tmp/probes` match CPython or are refused by name on both builds (`lp_direct_vararg` is refused by its existing lambda-value message; no DIFFs).
- Required tests on final commit: `test_ail_pre427`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed (238s).
[cost $0.0000, opencode tokens {"total": 501006, "input": 31803, "output": 2957, "reasoning": 1862, "cache.write": 0, "cache.read": 464384}]
    tool time: bash 5.2 min, edit 0.0 min
        240s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pre
         68s bash   cd /tmp/probes && for p in *.py; do echo "##### $p"; bash ~/tools/cmp.sh "$p" /home/runner/work/ail-ci/ail-ci 
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check; echo "manifest=$?"; python3 to
          1s bash   cd /home/runner/work/ail-ci/ail-ci && for i in $(seq 0 19); do python3 tools/ci_shards.py --shard $i | tr ' ' 
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/ci_shards.py --update && python3 tools/ci_shards.py --chec
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 -c "import sys; sys.path.insert(0,'AIL_CURRENT'); import ail_che
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git status && git log --oneline -5 && ls
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git add AIL_CURRENT/ail_check.py AIL_CURRENT/MANIFEST.json tools/ci_shar

## review 1
[model opencode/deepseek-v4.1-flash-free]
## Review: pre427 posonly-lambda refusal

**What the diff really does:** Adds a compile-time refusal for any AST `Lambda` whose `args.posonlyargs` is non-empty, in both `ail_syntax.python_surface` (raw source) and `pyc.build` (after shadowing), plus a new `test_ail_pre427` registered in `ail_check.MODULES`, `tools/ci_shards.json` (shard 4) and `MANIFEST.json`. No runtime/emitted-C change. The report's “committed as `42897f8`” is imprecise: `717227e` is the fix, `42897f8` is only the test registration; the functional description is accurate.

**Baseline reproduction (`/tmp/base` = `work`):**
- `list(map(lambda x, /, y: y * 2, [5]))` → base both builds `[10]`, CPython `TypeError` (p1).
- `sorted([3,1,2], key=lambda x, /, y: y)` → base both builds `[1, 2, 3]`, CPython `TypeError` (p2).

**Own probes (`/tmp/rprobes`, cmp.sh, both builds):**
- `p1` map posonly, `p2` direct posonly → named refusal `not in the subset: a lambda with a positional-only parameter ...` on both builds; base differs as above.
- `p3` posonly `def` → matches CPython both builds (base too).
- `p4` `lambda` + `/` but no posonly → matches both builds (base too).
- `p5` `lambda` / `/` only in comments/strings → matches both builds (base too).
- Worker's 40 probes: reran all; no `DIFF`, every build failure is a named refusal (`lp_direct_vararg` uses its existing “lambda used as a value” note, matching the report).

**No-feature C:** `--debug-dir` compare base vs HEAD: `program.c` identical and executable sha256 identical for a no-lambda program and for a plain `lambda`+`/` program. No runtime change, so no icount run needed.

**Tests/records (HEAD `42897f8`):** `test_ail_pre427`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` → 4 modules, 0 failed (235s). `update_manifest.py --check`=0, `ci_shards.py --check`=0, module present in `ail_check.MODULES`, shard 4 confirmed. Commit trailers present.

**Claim check:** fix/refusal both builds — verified; registration/manifest/shards — verified; 40 probes/no DIFFs — verified; test pass counts — verified (238s vs my 235s). Pre413 items beyond this one and the wider suite — not rechecked (out of scope by design).

**Pre-existing (not blocking):** a lambda returned from an imported module and used as `map()` argument is refused on base and HEAD alike; unrelated to this change.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 925612, "input": 49707, "output": 5361, "reasoning": 18448, "cache.write": 0, "cache.read": 852096}]
    tool time: bash 7.2 min
        237s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre4
         69s bash   ls /tmp/probes/*.py 2>/dev/null | wc -l; cd /tmp/probes && for p in *.py; do out=$(bash ~/tools/cmp.sh "$p" /h
         55s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p*.py; do echo "##### $(basename $p)"; bash ~/tool
         22s bash   cd /tmp/base && for p in p27_map_vararg p28_map_kwonly p29_key_vararg p30_key_kwonly p18_key_ok p19_map_ok; do
         18s bash   cd /home/runner/work/ail-ci/ail-ci && sed -n '4185,4220p' AIL_CURRENT/ail_chatgpt.py; echo ---; ls /tmp/rprobe
          8s bash   cd /tmp/base && cat > /tmp/t1.py <<'EOF' print(list(map(lambda x, /, y: y * 2, [5]))) EOF cat > /tmp/t2.py <<'
          6s bash   cd /tmp && rm -rf dbg_head dbg_base dbgdir_head dbgdir_base && cat > /tmp/nofeature.py <<'EOF' def add(a, b): 
          5s bash   cd /tmp && rm -rf dbg2_head dbg2_base dbgdir2_head dbgdir2_base && cp /tmp/rprobes/p4_div_lambda.py /tmp/divla

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-28T11:47:29Z
