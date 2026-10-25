# job job-pre240-10260355  started 2026-10-25T19:00:13Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":372,"duration_api_ms":248,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":385,"duration_api_ms":259,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed `34dbbf7` on `job-pre240-10260355`.

**Difference fixed:** the first remaining item from the `rbrbrbmemsafe2` review — `float()` wrong-type errors used `a string or a number` instead of CPython 3.12's `a string or a real number`. User instances also said `instance`, and long names such as `builtin_function_or_method` were cut by an 80-byte buffer. Both tested builds now match; valid conversions unchanged.

**Probes** (all `same stdout`, exit 0, general + default builds):
- `pre240_simple.py`, `pre240_basic.py`
- `pre240_flows.py`, `pre240_types.py`
- `pre240_instance.py`, `pre240_dunder.py`, `pre240_callables.py`

Coverage: None/empty/nested containers, list/tuple/dict/set/frozenset/bytes/bytearray, int64 bounds, negatives/-0.0, valid/invalid strings, aliases, argument/list-item/attribute/dict-value paths, user instance/function/class value, builtin function, and `__float__`/`__index__`/`__int__`/operator hooks.

**Tests on final commit:** `test_ail_pre240`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed (332s). Manifest and shard checks pass. Records updated; `test_ail_pre240.py` registered and assigned to a shard. Not pushed. Speed not measured (`perf_event_open` denied).
[cost $0.0000, opencode tokens {"total": 5473166, "input": 125198, "output": 15577, "reasoning": 15655, "cache.write": 0, "cache.read": 5316736}]
    tool time: bash 12.3 min, websearch 0.0 min
        334s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre240 test_ail_
        126s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre240 test_ail_
         67s bash   cd /tmp/probes && cat > pre240_simple.py <<'EOF' def main():     try:         print(float(None))     except Ex
         66s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check; echo "manifest rc=$?"; python3
         37s bash   cd /tmp/probes && for p in pre240_basic.py pre240_flows.py pre240_instance.py; do echo "===== $p ====="; bash 
         20s bash   cd /tmp/probes && cat > pre240_types.py <<'EOF' def show(label, fn):     try:         print(label, repr(fn()))
         18s bash   cd /tmp/probes && cat > pre240_flows.py <<'EOF' class Box:     def __init__(self):         self.x = None      
         14s bash   cd /tmp/probes && cat > pre240_basic.py <<'EOF' class Box:     pass  def show(label, fn):     try:         pri

## review 0
[model opencode/deepseek-v4.1-flash-free]
Reviewed `34dbbf7`. The change only rewrites the `float()` wrong-type TypeError text (and buffer size) in both `ail_to_float` copies plus the dunder anchors, and adds tests/records.

**Claims**
- Wording `a string or a real number`, user class name (`Box`), builtin function name, `Counter`/`deque`/`defaultdict`: **verified** on both builds (`rA`, `rD`, `rG`); base shows the old text.
- Valid conversions unchanged: **verified** (`rE`, plus the added tests).
- “Both tested builds now match” for long names: **false** (defect 1).
- Tests: `test_ail_pre240`+`test_ail_safetynet` pass (124s); `test_ail_files`+`test_ail_corpus_findings3` pass (211s); manifest and shard `--check` rc=0. **verified**.
- C for a non-`float` program differs from base only in the one changed runtime line. **verified**.
- “First still-differing item”: **unverified**; the supplied task text contains no difference list.

**Defect**
1. The fixed 128-byte buffer still cuts legal long class names. `rB_min.py`:
```python
class CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC:  # 70 C's
    pass
try:
    float(CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC())
except Exception as e:
    print(type(e).__name__, str(e))
```
Expected (CPython, both builds): `TypeError float() argument must be a string or a real number, not '<70 C's>'`
Actual (both builds): the name is 69 C's and the closing `'` is missing. Boundary is 69 characters (`rB_long.py`). Base truncates even earlier, but the task asked to fix the 80-byte truncation; only enlarging the fixed buffer leaves the cause in place.

**Pre-existing (same on base)**
- `int(None)`/`int([1])` still say `a string or a number` instead of `a string, a bytes-like object or a real number` (`rI_int.py`).
- `__float__` returning a non-float is accepted (`Bad.__float__` → `5.0`; CPython raises `TypeError`) (`rE_hooks.py`).
- Bound-method access is unsupported (`b.m` → `AttributeError`) (`rH_misc.py`).

**Unverified:** speed (only a cold error path; no `icount` run); the other `float()` message sites at `cruntime.py:17652` (`ail_bi_float`) and `statbrt.py:67` still use `ail_type_name`, but I could not reach them from a program (`float` as a value is refused by name).

VERDICT: FIX
1. Long class names (>69 chars) are still truncated in the new 128-byte `buf` in both `ail_to_float` paths; use a dynamically sized message (as `ail__tname_c` already provides) so any class name prints in full.
[cost $0.0000, opencode tokens {"total": 2178357, "input": 39571, "output": 30626, "reasoning": 0, "cache.write": 0, "cache.read": 2108160}]
    tool time: bash 9.0 min
        213s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ai
        127s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre2
         36s bash   date; cd /tmp/rprobes && for p in rA_basic.py rC_unicode.py rD_paths.py rE_hooks.py; do echo "########## $p"; 
         27s bash   date; cd /tmp/rprobes && for p in rE_hooks.py rA_basic.py; do echo "##### BASE $p"; timeout 600 bash ~/tools/c
         26s bash   cd /tmp/rprobes && cat > rI_int.py <<'EOF' def show(label, fn):     try:         print(label, repr(fn()))     
         10s bash   cd /tmp/rprobes && cat > rH_misc.py <<'EOF' class Box:     def __init__(self):         self.x = 1      def m(s
          9s bash   cd /tmp/rprobes && cat > rK2.py <<'EOF' class Box:     def __init__(self):         self.x = 1  def show(label,
          8s bash   cd /tmp/rprobes && cat > rK_floatvalue.py <<'EOF' class Box:     def __init__(self):         self.x = 1  def s

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Committed `28ca296`.

**Fix:** both `ail_to_float` sites now build the wrong-type message from the class-aware type name in a dynamically sized buffer, applying CPython's own `%.200s` cap. Names up to 200 chars print in full; 201/300 truncate exactly as CPython.

**Probes** (`bash ~/tools/cmp.sh ... $PWD`, both `g` and `d` builds):
- `/tmp/probes/longname.py` — short and 70-char class: same stdout.
- `/tmp/probes/pre240_long.py` — names 1, 63, 64, 69, 70, 127, 128, 129, 200, 300, via direct/arg/list/dict/attr/alias: same stdout.
- `/tmp/probes/pre240_types.py` — types, empty/negative, int64 bounds, valid/invalid strings, callables/classes, via arg/list/dict/attr/alias: same stdout.

**Tests on final commit:** `test_ail_pre240`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4/4 passed in 258s. Manifest `--check` rc=0.
[cost $0.0000, opencode tokens {"total": 2905163, "input": 89503, "output": 12707, "reasoning": 12553, "cache.write": 0, "cache.read": 2790400}]
    tool time: bash 5.7 min, edit 0.0 min
        260s bash   timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pre240 test_ail_safetynet test_ail_files test_ail_cor
         25s bash   for p in /tmp/probes/longname.py /tmp/probes/pre240_long.py /tmp/probes/pre240_types.py; do echo "########## $
         24s bash   for p in /tmp/probes/longname.py /tmp/probes/pre240_long.py /tmp/probes/pre240_types.py; do echo "########## $
          7s bash   python3 - <<'PY' from pathlib import Path p = Path('/tmp/probes/pre240_long.py') s = p.read_text() s = s.repla
          7s bash   python3 - <<'PY' from pathlib import Path p = Path('/tmp/probes/pre240_long.py') s = p.read_text() s = s.repla
          6s bash   bash ~/tools/cmp.sh /tmp/probes/pre240_long.py $PWD
          4s bash   bash ~/tools/cmp.sh /tmp/probes/longname.py $PWD
          4s bash   bash ~/tools/cmp.sh /tmp/probes/longname.py $PWD

## review 1 failed to run: [cost $0.0000, opencode tokens {}]     tool time:  (cut off after 60 minutes) 

## review 1
[model opencode-go/deepseek-v4.1-flash]
(no final text)
[cost $0.0000, opencode tokens {}]
    tool time: 
(cut off after 60 minutes)

FINAL VERDICT: ERROR  2026-10-25T22:00:05Z
