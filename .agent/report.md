# job job-pre409-10281141  started 2026-10-28T02:42:29Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"3bb6f6f6-8b75-4462-b575-8ddfda6831e9","session_id":"67847ff0-6ad7-4558-bcd5-9ea85fe9dd41"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"6cf490d4-eda2-43cb-9c72-4e1d1793d8ac","session_id":"aca75463-fad6-4c3b-82b3-e742e7bd6c15"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the first still-differing case: class-object `A[1]` (and class slices) now say `type 'A' is not subscriptable` on both builds.

- Commit: `c7f3369` (not pushed)
- Change: v2 runtime class subscript index/slice error formatting in `cruntime.py`
- Added `test_ail_pre409.py` (3 tests) and registered it
- Probes: `p409_classobj_index.py`, `p409_classobj_slice.py`, `p409_classobj_store.py`, `p409_classobj_controls.py` all match CPython on both builds; `p409_classobj_unicode.py` is refused by name (v2 runtime is ASCII-only)
- Tests: `test_ail_pre409`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 28 run, OK (1 skipped: no zig for Windows target)
- `python3 tools/update_manifest.py --check`: exit 0
- DIFFERENCES row and DEVLOG entry added.
[cost $0.0000, opencode tokens {"total": 3176221, "input": 248416, "output": 10726, "reasoning": 12503, "cache.write": 0, "cache.read": 2904576}]
    tool time: bash 7.1 min, edit 0.0 min
        342s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -v test_ail_pre409 test_ail_safetynet te
         18s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p = Path('AIL_CURRENT/python/p
         17s bash   for f in /tmp/probes/p409_classobj_index.py /tmp/probes/p409_classobj_slice.py /tmp/probes/p409_classobj_store
         14s bash   cat > /tmp/probes/p409_classobj_index.py <<'EOF' class A:     pass   class B(A):     pass   class _AilDeque_Fo
         12s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p = Path('AIL_CURRENT/python/p
         12s bash   cat > /tmp/probes/p409_classobj_store.py <<'EOF' class A:     pass   class B(A):     pass   class Holder:     
          3s bash   mkdir -p /tmp/probes; cat > /tmp/probes/p_classobj.py <<'EOF' class A:     pass  try:     A[1] except TypeErro
          3s bash   bash ~/tools/cmp.sh /tmp/probes/p_classobj.py $PWD

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does:** adds a v2 runtime helper `ail__class_subscript_error` and calls it from the class cases of `ail_op_getitem`/`ail_op_getslice`; it formats `type '<name>' is not subscriptable`, adds `test_ail_pre409.py`, a DIFFERENCES row, a DEVLOG entry and manifest pins.

**Probes (both builds, HEAD vs CPython):**
- `r3_routes`: base/subclass/alias/argument/list/tuple/nested/attribute/dict/dict.get/slice-object/`[1:2]` — all match; `_AilDeque_Foo` now matches CPython, not the internal special case.
- `r10_pass_class`: plain `class A: pass`, `B(A)` — both builds match.
- `r2_unicode_name`: refused by name (`non-ASCII ... v2 runtime is ASCII-only`) — acceptable.
- `r4_assign_del`: read fixed; `del A[1]` still `"doesn't"` vs CPython `"does not"` (base same).
- `r5_plain`: unaffected program matches; `--debug-dir` C diff is only the new runtime helper (lowering unchanged).
- `r1_long_name`, `r11_long_slice`: **fail** (below).

**Tests:** `test_ail_pre409`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass (`-j 2`). `tools/update_manifest.py --check` exits 0.

**Report claims:**
- index/slice now name the class on both builds: verified for names up to 95 code points.
- subclass/alias/argument/list/item/attr/dict routes: verified.
- unicode refusal: verified.
- `_AilDeque_` special case not used here: verified.
- tests added/registered and run: verified.
- “assignment and deletion keep CPython's ... wording”: **false for deletion** — CPython says `'type' object does not support item deletion`; both builds say `doesn't` (pre-existing).
- Named probes `/tmp/probes/p409_*`: not available, unverified; my probes cover the same boundaries.

**Pre-existing:** `del A[1]` deletion wording; `MyError()[1]` and nested-slice cases were not re-checked (task said fix the first differing case only). Unverified: gdev instruction-count speed (error path only) and full suite.

**Defects:**

1. Class names longer than 95 code points are truncated in the TypeError on both builds. Probe `/tmp/rprobes/r1_long_name.py`:
```python
class AAAA...100...AAAA:
    pass
def sub(label, c, k):
    try: c[k]
    except TypeError as e: print(label, type(e).__name__, e)
def main():
    sub('index', AAAA...100...AAAA, 1)
    AAAA...100...AAAA[0:1]
main()
```
Expected (CPython): `type '` + all 100 A's + `' is not subscriptable`. Actual on both builds: 95 A's. Same at the exact boundary: a 96-character name loses its last character (`r11_long_slice.py`). Base was also wrong (`'type' object is not subscriptable`), but this fix's stated purpose is to print the class name; its fixed 96-byte buffer does not. `test_ail_pre409.py` has no long-name case.

VERDICT: FIX

1. `ail__class_subscript_error` truncates names at 95 code points: `char name[96]`/`k + 1 < sizeof name`. Write the name into a dynamically sized buffer (or allocate `nm.n + 1`), and add a long-name case to `test_ail_pre409.py`.
[cost $0.0000, opencode tokens {"total": 746744, "input": 45397, "output": 5470, "reasoning": 9669, "cache.write": 0, "cache.read": 686208}]
    tool time: bash 5.3 min
        158s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_files te
         88s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_pre409 t
         23s bash   cd /tmp/rprobes cat > r6_builtin_types.py <<'EOF' def show(label, c, k):     try:         c[k]     except Type
         18s bash   mkdir -p /tmp/rprobes; cd /tmp/rprobes python3 - <<'PY' from pathlib import Path n='A'*100 Path('r1_long_name.
          8s bash   cd /tmp/rprobes; for f in r3_routes r4_assign_del; do echo "=== HEAD $f full"; bash ~/tools/cmp.sh /tmp/rprobe
          7s bash   cd /tmp/rprobes; for f in r6_builtin_types r7_type_route; do echo "=== $f HEAD"; bash ~/tools/cmp.sh /tmp/rpro
          4s bash   cd /tmp/rprobes; cat > r11_long_slice.py <<'EOF' class %s:     pass   def main():     try:         %s[0:1]    
          3s bash   cd /tmp/rprobes; cat > r10_pass_class.py <<'EOF' class A:     pass   class B(A):     pass   def sub(label, c, 

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `95c5217`.

- `ail__class_subscript_error` now uses dynamically sized buffers instead of the 96-byte name buffer; it also matches CPython’s 200-character name limit (CPython truncates 300-char names to 200).
- Added long-name coverage to `test_ail_pre409.py`: 95/96/100/199/200/201/300 code points, index and slice, both builds.
- Corrected the false deletion-wording claim in DEVLOG/DIFFERENCES/test docstring; `del A[1]` remains the pre-existing `doesn't` vs `does not` difference.
- Probes `/tmp/probes/p409_long_names.py`, `p409_long_routes.py`, `p409_short_controls.py`: all match CPython on both builds.
- `test_ail_pre409`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 4/4 pass at `-j 2` on the final commit.
- `tools/update_manifest.py --check`: exit 0.
[cost $0.0000, opencode tokens {"total": 742358, "input": 43649, "output": 5961, "reasoning": 5132, "cache.write": 0, "cache.read": 687616}]
    tool time: bash 6.4 min
        176s bash   cd AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_pre409 test_ail_safetynet test_ail_files
        174s bash   cd AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_pre409 test_ail_safetynet test_ail_files
         12s bash   cd /tmp/probes && for f in p409_long_names p409_long_routes p409_short_controls; do echo "=== $f"; bash ~/tool
         12s bash   cd /tmp/probes && for f in p409_long_names p409_long_routes p409_short_controls; do echo "=== $f"; bash ~/tool
         12s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/python/pkg-v12/cruntime.py') s=p.read_text() old
          0s bash   mkdir -p /tmp/probes && cd /tmp/probes && python3 - <<'PY' from pathlib import Path names=['A'*95,'A'*96,'A'*1
          0s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/DEVLOG.md') s=p.read_text() old="""`_AilDeque_` 
          0s bash   git status --short && git diff --stat && git diff -- AIL_CURRENT/python/pkg-v12/cruntime.py AIL_CURRENT/test_a

## review 1
[model opencode/deepseek-v4.1-flash-free]
Read the diff, probed both HEAD (`95c5217`) and base (worktree at `work`), ran the targeted tests and manifest check.

**What the change really does:** Adds a v2-runtime helper `ail__class_subscript_error` used by class-value index and slice reads; it formats `type '<name>' is not subscriptable` from the class's own name with a dynamically sized buffer and CPython's 200-character cap. Assignment, deletion and instance paths are untouched. (The change spans two commits: `c7f3369` + `95c5217`; the report names only the last.)

**Probes (HEAD vs CPython, both builds unless noted)**
- `p_class_basic`: matches except the known `del A[1]` wording; base had the `'type' object` message for index/slice, now fixed.
- `p_class_long` (95/96/100/199/200/201/300, index+slice): same stdout both builds; base wrong. Confirms exact 200-char truncation.
- `p_class_name_len` (300-char name, `__name__`, error): matches; base only differs in the message.
- `p_class_exc`: `MyError[1]`/slice now match; exception-instance and plain-instance messages are unchanged vs base.
- `p_class_containers`, `p_class_msg_lifetime`, `p_class_controls`, `p_untyped_slice`, `r1`, `r3`, `r5`, `r8`–`r11`: match on both builds; retained message after later raises shows the raise copies the buffer (no use-after-free).
- `r4`: only the pre-existing `doesn't` vs `does not` deletion difference.
- `p_class_unicode`/`r2`, `r6`, `r7`, `p_class_nested`, `p_class_getitem`: refused/undefined identically on base and HEAD.
- No-feature `--debug-dir` comparison: `program.c` differs only by the new helper and two case arms; emitted program body is identical. `update_manifest.py --check` exit 0.
- Required tests: `test_ail_pre409 test_ail_safetynet test_ail_files test_ail_corpus_findings3` → 4/4 pass at `-j 2`.

**Claims:** all verified (long-name fix, truncation limit, deletion-wording correction, probe results, test results, manifest). Only inaccuracy: the report says the whole fix is commit `95c5217`, but it also includes `c7f3369`; not a behavioural defect.

**Pre-existing:** `del A[1]` wording; exception/instance subscript class names; non-ASCII class-name refusal; nested-class, `type()`, builtin-type and `__class_getitem__` refusals.

**Unverified:** instruction-count speed check — `perf_event_open` is denied on this runner; the change is error-path-only, so no hot-path effect expected. Wider suite deliberately not run.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1894023, "input": 66338, "output": 8813, "reasoning": 18168, "cache.write": 0, "cache.read": 1800704}]
    tool time: bash 5.7 min
        177s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre409 tes
         30s bash   date; cd /tmp/rprobes && for f in r1_long_name r2_unicode_name r3_routes r4_assign_del r5_plain r8_min r9_mult
         30s bash   date; cd /tmp/speed && cp ~/corpus/gdev/g00_020.py .; for p in g00_000 g00_020; do for tag in head base; do if
         19s bash   date; cd /tmp/rprobes && for f in p_class_basic p_class_long p_class_unicode p_class_controls p_class_nested p
         14s bash   cd /tmp/rprobes && for f in p_class_basic p_class_long p_class_unicode p_class_nested; do echo "########## $f 
         14s bash   date; cd /tmp/rprobes && for f in p_class_basic p_class_long p_class_unicode p_class_nested; do echo "########
         12s bash   date; cd /tmp/rprobes && for f in r6_builtin_types r7_type_route; do echo "########## $f HEAD"; bash ~/tools/c
          9s bash   cd /tmp/rprobes && cat > p_class_exc.py <<'PY' class MyError(Exception):     pass class A:     pass class Plai

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-28T04:36:23Z
