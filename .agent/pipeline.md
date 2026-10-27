# job job-pre354-10280045  started 2026-10-27T15:46:08Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"4376393e-3404-46ef-b7ba-4a12d00f7934","session_id":"5d8df77d-2bfe-4d46-a31c-35bb127e6692"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"9525974c-3b75-4ec8-9085-854b86abee7d","session_id":"fd801c70-72ef-45ae-bfc3-0062e2944ba0"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the first pre-existing item from the pre327 review: a parameter/local named `slice` shadowed the slice class, causing `TypeError: 'int' object is not callable`. The prelude now exposes a private `_ail_slice_type` alias used by `_slice_obj`.

Probes in `/tmp/probes/pre354` (both builds):
- Match CPython after fix: `p01_shadow_param`, `p02_shadow_local`, `p03_shadow_method`, `p04_shadow_module`, `p05_shadow_global_func`, `p06_user_slice`, `p07_shadow_loop`, `p10_routes_shadow` (alias, attribute, dict value, list item, assignment/deletion).
- Still pre-existing and unchanged: `p08_dict_slice` (`TypeError` vs CPython `KeyError slice(...)`), `p09_instance_name` (`'instance'` vs `'A'`).

Final commit `1412c1c`; tests on it: `test_ail_pre354`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. `tools/update_manifest.py --check` passes. Not pushed.
[cost $0.0000, opencode tokens {"total": 2875132, "input": 156762, "output": 10458, "reasoning": 11848, "cache.write": 0, "cache.read": 2696064}]
    tool time: bash 9.6 min, edit 0.0 min, write 0.0 min
        338s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre354 test_ail_safetynet test_ail_files test_ai
        120s bash   find / -path /proc -prune -o -path /sys -prune -o -name '*pre327*' -print 2>/dev/null | head -50
         47s bash   for f in /tmp/probes/pre354/p*.py; do echo "===== $(basename $f)"; bash ~/tools/cmp.sh "$f" "$PWD" 2>&1 | grep
         47s bash   for f in /tmp/probes/pre354/p*.py; do echo "===== $(basename $f)"; bash ~/tools/cmp.sh "$f" "$PWD" 2>&1 | grep
         10s bash   for f in /tmp/probes/pre354/p10_routes_shadow.py /tmp/probes/pre354/p11_lambda_comp.py; do echo "===== $(basen
          4s bash   bash ~/tools/cmp.sh /tmp/probes/pre354/p11_lambda_comp.py "$PWD" 2>&1 | tail -40
          4s bash   bash ~/tools/cmp.sh /tmp/probes/pre354/p11_lambda_comp.py "$PWD" 2>&1 | tail -30
          4s bash   bash ~/tools/cmp.sh /tmp/probes/pre354/p11_lambda_comp.py "$PWD" 2>&1 | tail -30

## review 0
[model opencode/deepseek-v4.1-flash-free]
Review complete.

## What the change does
It fixes the pre327 item by making `_slice_obj` emit a call to a new prelude alias `_ail_slice_type = slice` instead of the name `slice` (`pyboxed2.py:3322`, `safetyrt.py:2350`). It also adds `test_ail_pre354.py`, registers it, and adds DEVLOG/DIFFERENCES rows.

## Verification
- Base (`/tmp/base`) fails the reported case; HEAD passes it: `r01_shadow_param_neg.py` (param `slice`, negative/step slices) and worker probes `p01`–`p07`, `p10` match CPython on both builds.
- Tests on HEAD: `test_ail_pre354` ok (45.3s), `test_ail_safetynet` ok (124.2s); `update_manifest.py --check` rc=0.
- C unchanged for a program with no slices and for a program with ordinary list slicing (`--debug-dir`, base vs HEAD identical).

## Claims
- "A local/parameter named `slice` no longer shadows the class": **verified**.
- "Private `_ail_slice_type` alias": **false** — it is not private; user code can bind it and then miscompiles (below).
- "p08/p09 still pre-existing unchanged": **verified** (both differ identically on base).
- "Final tests 4 modules 0 failed": **partially verified** (I re-ran only the added module + safetynet per instructions; `test_ail_files`/`corpus_findings3` not re-run).

## Pre-existing (same on base)
- `p08_dict_slice.py`: `TypeError` vs CPython `KeyError slice(...)`.
- `p09_instance_name.py`: `'instance'` vs `'A'`.
- Worker's `p11_lambda_comp.py`: compile refusal `a slice object the general path could not build`, identical on base.

## Defect
The fix trades the `slice` collision for a new `_ail_slice_type` collision. A user local/global of that name (which worked on base) now makes every slice subscript call an int.

Probe `r02_alias_local.py` (same for module-level `r03_alias_global.py` with `_ail_slice_type = 9` at top level):
```python
class C:
    def __getitem__(self, i):
        return (i.start, i.stop, i.step)

def cut(x):
    _ail_slice_type = 9
    return x[1:2]

print(cut(C()))
```
Expected (CPython, both builds on base): `(1, 2, None)` exit 0.
Actual (HEAD, both builds): `TypeError: 'int' object is not callable` exit 1.

VERDICT: FIX

1. New reserved-name collision `_ail_slice_type`: a user local/global named `_ail_slice_type` shadows the prelude alias, so `x[1:2]` calls the int and exits 1 with `TypeError: 'int' object is not callable` instead of CPython's `(1, 2, None)`. Probes: `/tmp/rprobes/r02_alias_local.py` (local) and `/tmp/rprobes/r03_alias_global.py` (module global). Both pass on base and fail on HEAD on both builds. Use a name the surface cannot bind (a compiler-generated unique symbol or direct runtime class reference), or refuse `_ail_slice_type` bindings by name.
[cost $0.0000, opencode tokens {"total": 445104, "input": 19759, "output": 3891, "reasoning": 6606, "cache.write": 0, "cache.read": 414848}]
    tool time: bash 4.4 min
        126s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre354 test_ail_safetynet 2>&1 | tail -25; date
         56s bash   for f in /tmp/probes/pre354/p*.py; do echo "== $(basename $f)"; bash ~/tools/cmp.sh "$f" "$PWD" 2>&1 | grep -E
         47s bash   for f in /tmp/rprobes/r*.py; do echo "===== $(basename $f)"; bash ~/tools/cmp.sh "$f" "$PWD" 2>&1 | grep -E 's
         17s bash   for f in /tmp/rprobes/r02_alias_local.py /tmp/rprobes/r03_alias_global.py /tmp/rprobes/r01_shadow_param_neg.py
          8s bash   cat /tmp/probes/pre354/p11_lambda_comp.py; echo ---; for m in g d; do if [ $m = g ]; then export AIL_UNIFIED_F
          6s bash   mkdir -p /tmp/rdbg && cd /tmp/rdbg printf 'x = 1 + 2\nprint(x)\n' > noslice.py printf 'a = [1, 2, 3]\nprint(a[
          3s bash   d=$(mktemp -d /tmp/r2XXXX); cp /tmp/rprobes/r02_alias_local.py $d/p.ail; cd $d; AIL_NO_CACHE=1 AIL_QUIET_FALLB
          0s bash   git worktree add /tmp/base work 2>&1 | tail -3; mkdir -p /tmp/rprobes; date

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed the review defect in commit `2c825a1`.

- `_slice_obj` now calls `_call_class('slice', ...)` directly, bypassing name lookup entirely; the shadowable `_ail_slice_type` alias is removed.
- Added `_ail_slice_type` local/global/parameter cases to `test_ail_pre354.py` (now 11 programs, both builds).

Verification:
- Probes `r01`–`r07`, `p01`–`p07`, `p10`: match CPython on both builds.
- `p08`/`p09`: unchanged pre-existing differences; `p11`: still refused by name.
- Tests: `test_ail_pre354`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 287s, 0 failed.
- `tools/update_manifest.py --check`: rc=0.
[cost $0.0000, opencode tokens {"total": 1009248, "input": 56628, "output": 4893, "reasoning": 5135, "cache.write": 0, "cache.read": 942592}]
    tool time: bash 6.9 min
        289s bash   python3 ../tools/par_check.py -j 2 test_ail_pre354 test_ail_safetynet test_ail_files test_ail_corpus_findings3
        102s bash   for f in /tmp/rprobes/r*.py /tmp/probes/pre354/p*.py; do echo "== $(basename $f)"; bash ~/tools/cmp.sh "$f" "$
         25s bash   for f in /tmp/rprobes/r01_shadow_param_neg.py /tmp/rprobes/r02_alias_local.py /tmp/rprobes/r03_alias_global.py
          0s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check
          0s bash   git status --short && git diff --stat && git diff --check
          0s bash   git status && git log --oneline -8 && ls
          0s bash   git add AIL_CURRENT/MANIFEST.json AIL_CURRENT/python/pkg-v12/pyboxed2.py AIL_CURRENT/python/pkg-v12/safetyrt.p
          0s bash   grep -rn "_ail_slice_type" AIL_CURRENT tools 2>/dev/null | head -40

## review 1
[model opencode/deepseek-v4.1-flash-free]
**What the change really does:** `_slice_obj` now builds the prelude slice object through `_call_class('slice', ...)` instead of emitting a call to the user-visible name `slice`; the interim `_ail_slice_type` alias is gone. That matches the report.

**Probes (all in /tmp/rprobes, both builds, HEAD vs base where relevant)**
- `r01`–`r18`, `p01`–`p11`: parameter/local/method/loop/module/global shadows, user class/assignment named `slice`, `_ail_slice_type` local/global/param, routes through attribute/dict/list/alias, slice get/set/del, negative/None/step bounds, side-effecting and mutating bounds, plain builtin slices, local `def`/`class` named `slice`, no-feature programs.
- All match CPython except the pre-existing cases below, which are identical on base.
- No-feature program: generated C identical to base via `--debug-dir` (`program.c` byte-identical).
- `p08`/`p09` differ exactly as on base; `p11` is refused by name on both.

**Claims**
- Fix for local/parameter `slice` shadow — verified (`r01`, `r03`, `p01`–`p07`, `p10`).
- `_ail_slice_type` alias removed and no longer shadowable — verified (diff; `r02`, `r03`).
- Added 11-case `test_ail_pre354.py` on both builds — verified.
- Worker probes match CPython — verified for `p01`–`p07`, `p10`; `p08`/`p09` pre-existing; `p11` refused.
- Tests: `test_ail_pre354`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — verified, 0 failed (134 s + 231 s with `-j 2`).
- `tools/update_manifest.py --check` rc=0 — verified.
- Speed: not checked; no `~/corpus/gdev` program defines `__getitem__`, so the changed branch is unreachable there.

**Pre-existing (not blocking)**
- `p08`: dict with a slice key gives `TypeError` instead of CPython `KeyError slice(...)`; identical on base.
- `p09`: instance without `__getitem__` names `'instance'` instead of the class; identical on base.
- `p11`, `r11`–`r16`: a nested `def slice` / nested `class slice` before an instance slice is refused by name (`a slice object the general path could not build` / nested class refusal); identical on base.
- `r13` nested class `slice`: refused by name on both.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2120776, "input": 66874, "output": 7075, "reasoning": 15467, "cache.write": 0, "cache.read": 2031360}]
    tool time: bash 10.6 min, write 0.0 min
        233s bash   date; cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_files test_ail_corpus_findings3 2>&1 | tai
        135s bash   date; cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre354 test_ail_safetynet 2>&1 | tail -40
         99s bash   date; for f in /tmp/rprobes/r*.py; do echo "===== $(basename $f)"; bash ~/tools/cmp.sh "$f" "$PWD"; done 2>&1 
         51s bash   date; for f in /tmp/probes/pre354/p01_shadow_param.py /tmp/probes/pre354/p02_shadow_local.py /tmp/probes/pre35
         34s bash   date; for f in /tmp/rprobes/r11_local_def_slice.py /tmp/rprobes/r12_unrelated_local_def_slice.py /tmp/rprobes/
         27s bash   date; for f in /tmp/rprobes/r15_local_def_slice_bytes.py /tmp/rprobes/r16_local_def_slice_encode.py; do for wt
         26s bash   date; for f in /tmp/probes/pre354/p08_dict_slice.py /tmp/probes/pre354/p09_instance_name.py /tmp/probes/pre354
         15s bash   date; for f in /tmp/rprobes/n01_nofeature.py /tmp/rprobes/n02_plain_slice.py; do echo "== $(basename $f)"; bas

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-27T17:47:23Z
