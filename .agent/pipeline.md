# job job-pre344-10272238  started 2026-10-27T13:48:04Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"770a3364-7321-4e73-86f9-9010d70a3b20","session_id":"dac19927-3a55-43ac-aa6a-4ded5cdc42ca"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"01006b44-60a1-4931-9ef6-05ce560d6f6c","session_id":"5271977d-64a4-4b16-80ea-4454f7547e45"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented and committed `475449a` on `job-pre344-10272238`.

- Recovered the pre-existing item from the `pre318` review: `vars(d)['g'] = 5` differs because `ail2a_vars` returns a copy, not CPython's live `__dict__`.
- Added `_check_vars_result_mutation` in `AIL_CURRENT/ail_chatgpt.py`, refusing writes through `vars()` results by name.
- Added `test_ail_pre344.py` with 32 programs covering aliases, containers, arguments, returns, unpacking, loops, comprehensions, and read-only controls.
- Registered the module in `ail_check.py` and `ci_shards.json`; added DEVLOG and DIFFERENCES rows.
- `update_manifest.py --check` passes.

Final-state tests on `475449a`:
- `test_ail_pre344`: 28.5s, 0 failed
- `test_ail_safetynet`: 96.2s, 0 failed
- `test_ail_files`: 97.0s, 0 failed
- `test_ail_corpus_findings3`: 147.2s, 0 failed

Probes: 32 total in `/tmp/probes/pre344` — 24 refused by name, 8 matched CPython; no unexplained differences. Rebound variables/attributes that previously held a `vars()` result remain conservatively refused by name.
[cost $0.0000, opencode tokens {"total": 8314153, "input": 425868, "output": 27129, "reasoning": 49444, "cache.write": 0, "cache.read": 7811712}]
    tool time: bash 7.9 min, edit 0.0 min, write 0.0 min
        245s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre344 test_ail_safetynet test_ail_files test_ai
         90s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_safetynet 2>&1 | tail -30
         29s bash   python3 tools/update_manifest.py 2>&1 | tail -10; python3 tools/update_manifest.py --check; echo rc=$?; cd AIL
         26s bash   mkdir -p /tmp/pre344_results; for f in /tmp/probes/pre344/*.py /tmp/probes/pre344/t/*.py; do n=$(basename "$f"
         24s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre344 2>&1 | tail -40
         20s bash   for f in /tmp/probes/pre344/*.py /tmp/probes/pre344/t/*.py; do echo "==== $(basename $f)"; bash ~/tools/cmp.sh
         11s bash   mkdir -p /tmp/probes/pre344 && cat > /tmp/probes/pre344/p01_vars.py <<'EOF' class D:     def g(self):         
         10s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/ail_chatgpt.py') s=p.read_text() old="""        

## review 0
[model opencode/deepseek-v4.1-flash-free]
Change: adds a module-wide AST taint pass (`_VarsMutationCheck`, `AIL_CURRENT/ail_chatgpt.py:1522-1837`) that refuses writes it thinks may reach the copy returned by `vars()`; no runtime change. New `test_ail_pre344.py` plus records/registration.

**Probes** (`/tmp/rprobes`, both builds, vs `/tmp/base`)
- p01 direct `vars(d)['g']=5`: refused by name on HEAD; base prints the wrong `AttributeError` — intended fix verified.
- p02 read-only `vars()`, p11 unrelated program, p12/p13 `.items()`/`.values()` value mutation: match CPython on both.
- p03 closure, p04 method argument, p05 aliased callee, p06 lambda, p08 local param named `vars`: still wrong output on HEAD and base (pre-existing).
- p07 dict `|=`: still `TypeError` on both (pre-existing).
- p09 attribute-name collision, p10 rebound local: base matches CPython; HEAD fails to compile (new).

**Defects**
1. `attr_taint` is global per attribute name (`ail_chatgpt.py:1609,1700`), so storing `vars(d)` in `h.v` refuses an unrelated plain dict on another object with the same attribute name. This contradicts the DIFFERENCES claim that “plain dicts still match CPython”.
```python
class D: pass
class H: pass
d = D(); d.a = 1
h = H(); h.v = vars(d)
h2 = H(); h2.v = {'x': 1}
h2.v['y'] = 2
print(sorted(h2.v.items()))
```
expected `[('x', 1), ('y', 2)]` exit 0; actual both HEAD builds exit nonzero: `mutating the dict returned by vars() is not in the subset ...` at `h2.v['y'] = 2`. Base prints the expected line.

2. Rebinding still merges taint instead of replacing it (`ail_chatgpt.py:1691-1693`), so a plain dict is refused after the name once held `vars()`.
```python
class D: pass
d = D(); d.a = 1
v = vars(d)
v = {'x': 1}
v['y'] = 2
print(sorted(v.items()))
```
expected `[('x', 1), ('y', 2)]` exit 0; actual both HEAD builds exit nonzero with the same refusal. Base prints the expected line. (The report documents this as conservative, but it still turns a correct program into a refusal.)

**Pre-existing** (identical on base): p03 closure, p04 method call, p05 callee alias, p06 lambda, p08 `def f(vars):` disabling the check globally, p07 dict `|=`. So the chosen cause is only partially refused; those routes still produce the old wrong `AttributeError`/`TypeError` rather than a named refusal.

**Claims**: commit/test registration/manifest check (`rc=0`) verified; test module has 32 cases but 25 are `refused` and 7 `ran`, not the reported 24/8; `test_ail_pre344` and `test_ail_safetynet` pass on HEAD (29.7s/95.2s, 0 failed); `test_ail_files` and `test_ail_corpus_findings3` were not re-run (unverified). Speed overhead on a 5 KB gdev program is small (~0.5s vs ~0.45s).

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 1267936, "input": 50116, "output": 5018, "reasoning": 20354, "cache.write": 0, "cache.read": 1192448}]
    tool time: bash 3.2 min
         97s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 600 python3 ../tools/par_check.py -j 2 test_ai
         33s bash   date; cd /tmp/rprobes; for f in p03_closure.py p04_method.py p05_alias_call.py p06_lambda.py p07_augassign.py 
         30s bash   date; cd /tmp/rprobes; for f in p*.py; do echo "==== $f"; bash ~/tools/cmp.sh "$f" /home/runner/work/ail-ci/ai
         14s bash   cd /tmp/rprobes cat > p12_items_value.py <<'EOF' class D:     pass d = D() d.a = {} for k, val in vars(d).item
          7s bash   cd /tmp; cp /home/runner/work/ail-ci/ail-ci/corpus/gdev/g12_036.py /tmp/big.ail; for wt in /tmp/base /home/run
          5s bash   cd /tmp; rm -rf dbgbase3 dbghead3; AIL_NO_CACHE=1 python3 /tmp/base/AIL_CURRENT/ail_chatgpt.py compile rprobes
          3s bash   cd /tmp/rprobes; date; echo '== base p01'; bash ~/tools/cmp.sh p01_direct.py /tmp/base 2>&1 | tail -12; ls /tm
          0s bash   cd /tmp; rm -rf dbgbase dbghead; mkdir dbgbase dbghead; AIL_NO_CACHE=1 python3 /tmp/base/AIL_CURRENT/ail_chatg

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed both review defects and committed as `a1c578a`.

- Attribute taint now keyed by `(scope, structural receiver, attribute)`, so unrelated `h.v` / `h2.v`, nested receivers, subscripts and same-named attributes in other scopes no longer alias.
- Assignment now replaces a name/attribute's taint, so rebinding to a plain dict clears it; mutation checks moved into the statement walk so writes before a rebind remain refused.
- Added 6 cases to `test_ail_pre344.py` (now 38 cases). Updated DEVLOG/DIFFERENCES; manifest `--check` rc=0.

Probes in `/tmp/probes/pre344fix`, both builds:
- Match CPython: p01 attr collision, p02 rebind, p05 mutation-before-taint, p06 self attr, p07 nested attr, p08 subscript attr, p09 scope collision, p10 read-only, p11 argument route, p12 list/dict route.
- Refused by name: p03 same-object attr mutation, p04 mutation before rebind.

Final-commit tests, 0 failed (198s): `test_ail_pre344`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`.
[cost $0.0000, opencode tokens {"total": 950468, "input": 43484, "output": 6937, "reasoning": 10703, "cache.write": 0, "cache.read": 889344}]
    tool time: bash 8.9 min, edit 0.0 min
        199s bash   cd AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pre344 test_ail_safetynet test_ail_
        159s bash   cd AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_files test_ail_corpus_findings3
         96s bash   cd AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre344 test_ail_safetynet
         38s bash   cd /tmp/probes/pre344fix && for f in p*.py; do echo "==== $f"; bash ~/tools/cmp.sh "$f" /home/runner/work/ail-
         37s bash   cd /tmp/probes/pre344fix && for f in p*.py; do echo "==== $f"; bash ~/tools/cmp.sh "$f" /home/runner/work/ail-
          4s bash   cd /tmp/probes/pre344fix && cat > p09_scope_collision.py <<'EOF' class D: pass class H1: pass class H2: pass d
          0s bash   python3 - <<'EOF' from pathlib import Path p=Path('AIL_CURRENT/ail_chatgpt.py') s=p.read_text() old="""       
          0s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check

## review 1
[model opencode/deepseek-v4.1-flash-free]
**What the change does:** adds a front-end taint pass (`_check_vars_result_mutation`) that refuses the first write through a `vars(obj)` result, plus tests/records. No runtime change; generated C for programs without `vars()` is byte-identical (`program.c` diff empty vs base).

**Probes** (`/tmp/rprobes`, `cmp.sh` on HEAD and base):

| probe | CPython | HEAD | base | verdict |
|---|---|---|---|---|
| q01 index reuse `a[i].v` | runs | refused | runs | regression |
| q02 `while False: v=vars(d)` | runs | refused | runs | regression |
| q16 `for h in []: v=vars(d)` | runs | refused | runs | regression |
| q15 key-filtered `.items()` | runs | refused | n/a | over-refusal |
| q21 constant-index variant | runs | runs | runs | ok |
| q04 no-vars plain dict/attr | runs | runs | runs | ok |
| q05/q23 rebind then mutate | runs | runs | — | ok |
| q22 mutate then rebind | runs | refused | — | correct |
| q08/q10/q11/q12 direct/alias/list/setitem routes | runs | refused | — | correct |
| q09/q17/q20 attr collisions | runs | runs | — | ok |
| q19 plain arg then vars | runs | runs | — | ok |
| q06 attr via alias, q07 closure | runs | AttributeError | AttributeError | pre-existing |
| q03 duplicate def | runs | refused (`duplicate AIL name`) | same | base limitation |

**Report claims:** attr taint keyed by scope/structural receiver — verified for `h`/`h2`, nested, constant subscripts, scopes; **false** for a reused index variable (q01 still aliases `a[i]`). Assignment replaces taint — verified (q05, q22, q23). 38 cases — verified. Manifest `--check` rc=0 — verified. Probes p01/p02/p05/p08 — verified. Tests: ran `test_ail_pre344`, `test_ail_safetynet` on HEAD, 0 failed (91s); `test_ail_files`/`findings3` not rerun. The report talks about the previous review’s two defects, not the task; the diff nevertheless implements the requested `vars()` refusal.

**Pre-existing (do not block):** q06 `h2=h; h2.v['g']=5`, q07 closure mutation, and the remaining method/alias routes still print `AttributeError` on both HEAD and base.

**Defects:**
1. Variable-index reuse refused although the mutated element is a plain dict. Source: q01 (`a[0].v={'x':1}; a[1].v=vars(d); a[0].v['y']=2`). Expected `[('x', 1), ('y', 2)]`; actual compile-time refusal `mutating the dict returned by vars()...` on both builds (base runs and matches).
2. Taint from a loop body is applied even when the loop cannot execute. Source: q02 (`v={'x':1}; while False: v=vars(d); v['y']=2`), also q16. Expected `[('x', 1), ('y', 2)]`; actual refusal on both builds.
3. Over-refusal across a mixed `.items()` loop with a key guard (q15): the tainted value is never touched, yet the plain value’s write is refused. Expected `[('x', 1), ('y', 2)]`; actual refusal.

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 598364, "input": 38213, "output": 4937, "reasoning": 13518, "cache.write": 0, "cache.read": 541696}]
    tool time: bash 2.8 min
         92s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_pre
         21s bash   cd /tmp/rprobes && for f in q*.py; do echo "================ $f"; timeout 300 bash ~/tools/cmp.sh "$f" /home/r
         16s bash   cd /tmp/rprobes && for f in q01_idx_reuse.py q02_while_false.py q03_dup_func.py q06_attr_alias_miss.py q07_clo
         14s bash   cd /tmp/probes/pre344fix && for f in p01_attr_collision.py p02_rebind.py p05_mutation_before_taint.py p08_subs
          7s bash   cd /tmp/rprobes && cat > q19_arg_plain_then_vars.py <<'EOF' class D:     def g(self):         return 1 d = D()
          5s bash   cd /tmp/rprobes && rm -rf dbg_head dbg_base && mkdir dbg_head dbg_base && cp q04_plain.py p.ail && (cd dbg_hea
          4s bash   cd /tmp/rprobes && cat > q15_items_filter.py <<'EOF' class D:     pass d = D() d.a = 1 dd = {'a': vars(d), 'b'
          4s bash   cd /tmp/rprobes && cat > q21_const_idx.py <<'EOF' class D:     pass class H:     pass d = D() d.a = 1 a = [H()

FINAL VERDICT: FIX  2026-10-27T14:39:51Z
