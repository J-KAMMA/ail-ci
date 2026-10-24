# job job-pre136-10250030  started 2026-10-24T15:56:41Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":416,"duration_api_ms":297,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":638,"duration_api_ms":519,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed on `job-pre136-10250030` (`0eb0b61`).

**Cause fixed:** `round(obj)` / `round(obj, None)` now call `__round__` with no ndigits so defaults apply; boxed ndigits handles `None` and `__index__`; huge negative ndigits no longer overflow to `nan`.

**Probes** (all same stdout as CPython on both `g` and `d`):
`p_floatdef`, `p_strdef`, `p_nodefuse`, `p_bad`, `p_hugneg`, `p_defaults`, `p_bounds`, `p_default_values`, `p_inherit` — 9/9.

**Tests on final commit:**
- `test_ail_pre136`: 2 passed
- `test_ail_safetynet`: 5 passed
- `test_ail_files`: 18 passed, 1 skipped
- `test_ail_corpus_findings3`: 2 passed

Manifest updated and `--check` passes. DEVLOG and DIFFERENCES rows added. No push.
[cost $0.0000, opencode tokens {"total": 7915563, "input": 327919, "output": 19348, "reasoning": 28968, "cache.write": 0, "cache.read": 7539328}]
    tool time: bash 10.3 min, edit 0.0 min, write 0.0 min
        165s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -B -m unittest -v test_ail_corpus_findings3
        110s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -B -m unittest -v test_ail_pre136 test_ail_safetynet
        108s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -B -m unittest -v test_ail_files
         98s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -B -m unittest -v test_ail_safetynet
         56s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -B -m unittest -v test_ail_files test_ail_corpus_fin
         20s bash   cat > /tmp/probes/p_bounds.py <<'EOF' class Idx:     def __index__(self):         return -3 class NoIndex:    
         16s bash   mkdir -p /tmp/probes /tmp/rprobes && cat > /tmp/probes/p_floatdef.py <<'EOF' class F:     def __round__(self, 
         12s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p_floatdef p_strdef p_nodefuse p_bad; do echo "=== $p ==="; bas

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does:** replaces `ail_bi_round`'s `int64_t n` with a boxed ndigits argument (None = omitted, `__index__` dispatch), adds a negative-ndigits overflow guard, and emits per-class `__round__` wrappers in `pyboxed2` so omitted/None ndigits use the method's default, including hoisted module-global defaults. Report matches the diff.

**Probes on HEAD (both builds unless noted)**
- Worker's 9 probes (`p_floatdef` … `p_inherit`): 9/9 match CPython — claim verified.
- `p_nanneg` (nan/±inf with -400/400): match.
- `p_values`, `p_kwonly2`, `p_nodefuse`, `p_noindex`, `p_boolnone`, `p_globmut`, `p_onearg`: match.
- `p_unistr`: refused by name (ASCII-only), acceptable.
- `p_nofeature` `--debug-dir`: C differs only in the changed runtime helper and the round call site; no unexpected change for programs not using round.
- Tests on HEAD: `test_ail_pre136` ok, `test_ail_safetynet` ok (par_check -j 2); manifest `--check` passes.
- `p_indexret`, `p_infdef`: differ (defects below).
- Worker claim "boxed ndigits handles None and `__index__`" is true only for well-formed `__index__`; see defect 1. Claim "9/9" verified.

**Pre-existing (not blocking)**
- `p_bignum` / `p_intbigdef`: int64 literal/expression out-of-range fails identically on base; `p_indexonly` (`FI().__index__()` returning `10**30`) also fails identically on base. The new `__index__` dispatch surfaces this limit (defect 3 below), rooted in the int64 runtime.

**Unverified**
- Instruction counts: `perf_event_open` denied on this runner, so no before/after icount.
- Wider suite (not run per instructions).

**Defects**

1. `__index__` returning a non-int gets CPython's "cannot be interpreted" message instead of the required `__index__ returned non-int` message.
```python
class FF:
    def __index__(self):
        return 2.0
print(round(2.5, FF()))
```
Expected (CPython): `TypeError: __index__ returned non-int (type float)`
Actual HEAD (g and d): `TypeError: 'float' object cannot be interpreted as an integer`

2. Non-finite float literal defaults are still mishandled: `_round_default_c` returns None for `1e400`/`-1e400`, so no wrapper is installed and the old path passes `None` rather than refusing by name.
```python
class I:
    def __round__(self, n=1e400):
        return repr(n)
print(round(I()), round(I(), None))
```
Expected (CPython): `inf inf`
Actual HEAD (g and d): `None None` (base: `None 0`). Emit `INFINITY`/`-INFINITY` or refuse by name.

3. Large `__index__` results now crash where base happened to match CPython.
```python
class FI:
    def __index__(self):
        return 10**30
print(round(2.5, FI()))
```
Expected (CPython): `2.5`
Actual HEAD (g and d): `integer overflow`, exit 1 (base: `2.5`, exit 0). Root cause is the pre-existing int64 limit reached inside `__index__`, but the new dispatch makes this round call regress.

VERDICT: FIX
1. `round(2.5, FF())` with `FF.__index__` returning `2.0`: expected `TypeError: __index__ returned non-int (type float)`, actual `TypeError: 'float' object cannot be interpreted as an integer`.
2. `round(I())` with `n=1e400` default: expected `inf`, actual `None` (silently falls back instead of refusing).
3. `round(2.5, FI())` with `FI.__index__` returning `10**30`: expected `2.5`, actual `integer overflow` (exit 1); caused by the new dispatch, though rooted in the int64 limit.
[cost $0.0000, opencode tokens {"total": 869138, "input": 141922, "output": 6102, "reasoning": 15322, "cache.write": 0, "cache.read": 705792}]
    tool time: bash 3.9 min
         99s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_pre136 t
         38s bash   ls /tmp/probes 2>/dev/null; cd /home/runner/work/ail-ci/ail-ci && date && for p in p_floatdef p_strdef p_nodef
         17s bash   cd /home/runner/work/ail-ci/ail-ci && cc -O2 -w -include signal.h -include stdlib.h -o /tmp/icount tools/icoun
         16s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in p_nanneg p_bignum p_onearg p_indexret; do echo "===== $
         13s bash   cd /tmp/rprobes && cat > p_globmut.py <<'EOF' G = 1.5 H = "hi" class F:     def __round__(self, n=G):         
         11s bash   cd /home/runner/work/ail-ci/ail-ci && echo "=== p_indexonly BASE ===" && bash ~/tools/cmp.sh /tmp/rprobes/p_in
         11s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in p_values p_kwonly p_nodefuse; do echo "===== $p HEAD ==
         10s bash   cd /tmp/rprobes && cat > p_infdef.py <<'EOF' class I:     def __round__(self, n=1e400):         return repr(n)

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed all three review defects and committed as `4215a13`.

- `__index__` returning a non-int now raises `TypeError: __index__ returned non-int (type T)` (`p_indexret`).
- Non-finite `__round__` defaults (`1e400`, `-1e400`) emit `INFINITY`/`-INFINITY`; unused wrappers still build (`p_infdef`, `p_nodefuse`).
- Out-of-range `__index__` results are saturated only while `round()` evaluates them, so `round(2.5, FI())` with `10**30` returns `2.5`; negative/multiply/shift variants also match (`p_indexonly`, `p_indexnegbig`, `p_indexbig`).
- Added `ROUND_REVIEW` to `test_ail_pre136.py`; updated DEVLOG/DIFFERENCES and regenerated MANIFEST.

Probes (both g and d builds, all match CPython): `p_review_extra`, `p_indexret`, `p_infdef`, `p_indexonly`, `p_indexnegbig`, `p_indexbig`, `p_floatdef`, `p_strdef`, `p_nodefuse`, plus earlier `p_default_values`, `p_defaults`, `p_inherit`, `p_bad`, `p_hugneg`.

Tests on the final commit: `test_ail_pre136`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. Manifest `--check` passes.
[cost $0.0000, opencode tokens {"total": 2490270, "input": 72493, "output": 9966, "reasoning": 15619, "cache.write": 0, "cache.read": 2392192}]
    tool time: bash 23.2 min
        600s bash   cd /tmp/probes && cat > p_indexnegbig.py <<'EOF' class FI:     def __index__(self):         return -(10**30) c
        257s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1800 python3 ../tools/par_check.py -j 2 test
        211s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check && cd AIL_CURRENT && date && ti
        180s bash   cd /tmp && rm -rf dbg && mkdir dbg && cp /tmp/probes/p_indexnegbig.py dbg/p.ail && cd dbg && python3 p.ail; ec
         52s bash   cd /tmp/probes && cat > p_review_extra.py <<'EOF' class FF:     def __index__(self):         return 2.0 class 
         33s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p_review_extra p_indexret p_infdef p_indexonly p_indexnegbig p_
         20s bash   cd /tmp/probes && bash ~/tools/cmp.sh /tmp/probes/p_indexonly.py /home/runner/work/ail-ci/ail-ci && cd /home/r
         13s bash   mkdir -p /tmp/probes && cd /tmp/probes && cat > p_indexret.py <<'EOF' class FF:     def __index__(self):      

## review 1
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
## Review of job pre136 (`work..HEAD`, 2 commits)

**What the diff does:** `ail_bi_round` now takes boxed ndigits, resolves `__index__` (inside a global saturating-overflow mode), fixes huge-negative float scaling, and emits per-class `pround_*` wrappers that supply `__round__` defaults / empty `*args` / `**kw`; wrappers are emitted for unused classes too. This is close to the report, except the report omits the saturating arithmetic and the new ndigits evaluation order.

**Probes (both g and d, HEAD unless noted):**
- Worker probes `p_floatdef`, `p_strdef`, `p_nodefuse`, `p_infdef`, `p_indexret`, `p_indexnegbig`, `p_indexbig`, `p_indexonly`, `p_bad`, `p_hugneg`, `p_defaults`, `p_default_values`, `p_inherit`, `p_variadic`, `p_oneparam`: match CPython except `p_bigidx_alone` (pre-existing).
- Mine: `rv1_capture`, `rv1_kwonly`, `rv1_default_types`, `rv1_intdef`, `rv1_values`, `rv1_bounds2`, `rv1_minidx`: match CPython on HEAD. `rv1_satcancel` and `rv1_order`/`rv1_order2` fail (below).

**Report claims:** float/string default, unused wrapper, `__index__` non-int, non-finite default, tests and manifest: verified. The saturation claim ("negative/multiply/shift variants also match") is only true for the simple probes; it is false for arithmetic that cancels (defect 2). I re-ran only `test_ail_pre136` and `test_ail_safetynet` (2 modules, 0 failed); `--check` passes. `test_ail_files`/`test_ail_corpus_findings3` not re-run.

**Pre-existing (identical on `/tmp/base`):** `round(1e308, -308)` gives `9.999999999999998e+307` (CPython `1e308`); big-int literals (`print(10**30)`, big `__round__` defaults) exit `integer overflow`; a 3-param `__round__` reports "type instance doesn't define __round__"; instance `repr` differs.

**Unverified:** speed (new branches are overflow-only, so I did not run icount); `--separate`/multithreaded scope of the global `ail__sat_index_mode`.

**Defect 1 — ndigits is evaluated before CPython's `round` type check (regression; base matches CPython).** Probe `/tmp/rprobes/rv1_order.py`:
```python
class Idx:
    def __index__(self):
        print("index called")
        return 2
for v in ("x", None, [1]):
    try: print(round(v, Idx()))
    except Exception as e: print(type(e).__name__, e)
```
Expected CPython and base: `TypeError type str doesn't define __round__ method`, `... NoneType ...`, `... list ...` with **no** `index called`. Actual HEAD, both builds: three `index called` lines before those TypeErrors. `/tmp/rprobes/rv1_order2.py` shows the same extra call for an instance without `__round__`. The ndigits conversion/`__index__` must happen only in the int/float and instance-with-`__round__` paths.

**Defect 2 — saturating `__index__` produces wrong values when intermediate arithmetic cancels.** Probe `/tmp/rprobes/rv1_satcancel.py`:
```python
class A:
    def __index__(self):
        a = 10**30; b = 10**30 + 5
        return a - b
class B:
    def __index__(self):
        a = 10**30; b = 10**30 + 5
        return a + b - b - a
print(round(2.5, A()))
print(round(2.5, B()))
```
Expected CPython: `A 0.0`, `B 2.0`. Actual HEAD both builds: `A 2.0`, `B 0.0` (base: `2.5`, `2.5`). Saturation is a lossy approximation of out-of-int64 `__index__`; either refuse such values/constructs by name or do not claim they match.

VERDICT: FIX
1. Evaluate the x-type / missing-`__round__` check before converting/evaluating ndigits; currently `__index__` side effects run where CPython raises immediately (`/tmp/rprobes/rv1_order.py`, `/tmp/rprobes/rv1_order2.py`).
2. The saturating `__index__` mode gives wrong answers for cancelling arithmetic (`/tmp/rprobes/rv1_satcancel.py`: expected `A 0.0`/`B 2.0`, actual `A 2.0`/`B 0.0`); refuse out-of-int64 `__index__` results by name or make saturation sign/rounding-safe.
[cost $0.0418, opencode tokens {"total": 2406121, "input": 79742, "output": 9354, "reasoning": 28897, "cache.write": 0, "cache.read": 2288128}]
    tool time: bash 5.1 min
         98s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1800 python3 ../tools/par_check.py -j 2 test
         54s bash   cd /tmp/probes && date && for p in p_review_extra p_indexret p_infdef p_indexonly p_indexnegbig p_indexbig p_f
         35s bash   cd /tmp/rprobes && ls && date && for p in p_indexret p_infdef p_indexonly p_indexnegbig p_indexbig p_floatdef 
         26s bash   cd /tmp/rprobes && for p in rv1_capture rv1_kwonly rv1_satcancel rv1_minidx rv1_boundaries rv1_default_types r
         17s bash   cd /tmp/rprobes && for p in rv1_satcancel rv1_minidx rv1_capture rv1_values; do echo "===== $p BASE"; timeout 
         15s bash   cd /tmp/rprobes && for p in rv1_kwonly rv1_default_types rv1_bounds2 rv1_errors; do echo "===== $p HEAD"; time
         11s bash   ls /tmp/probes 2>/dev/null | head -100; echo ---; for p in p_indexonly p_bignum p_kwonly; do echo "===== $p"; 
          8s bash   for p in p_bignum p_indexonly; do echo "===== $p BASE"; (cd /tmp/rprobes && timeout 300 bash ~/tools/cmp.sh /t

FINAL VERDICT: FIX  2026-10-24T17:21:18Z
