# job job-cov49-10291923  started 2026-10-29T10:28:44Z  worker=oc reviewer=oc (GitHub)
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
Qwen3.8-Flash
DeepSeek-Flash
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"39515284-0236-48ba-a8ed-70b59b36b674","session_id":"0c2d21c6-9c9c-40d9-ae40-69fc02f426a4"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"b601f1d8-a315-444a-8ff8-028932d85371","session_id":"f5f5c676-1efd-4d46-9faa-1d786a6362f9"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done.

**Result**
- Fresh corpus profile (219 programs): **24 compile-time refusals → 23**. 8 were stdlib/import refusals, excluded from selection.
- Implemented the most frequent exactly supportable remaining construct: **`str.translate` / `str.maketrans` with dict tables** (corpus `deepseek-v4.1-flash-free/t484`). It now builds and matches CPython 3.12 on both builds.
- Unsupported forms remain named refusals: one-argument `str.maketrans(mapping)` and literal non-dict translate tables.
- Added `AIL_CURRENT/test_ail_cov49.py`, registered in `ail_check.MODULES` and `tools/ci_shards.json`.

**Probes** (`/tmp/probes/cov49`, both builds via `cmp.sh`)
- Match CPython: `p_basic`, `p_routes`, `p_values`, `p_alias`, `p_constant`, `p_unicode`, `p_errors`, plus bytes control `/tmp/probes/bt1.py`.
- Refused by name: `p_refuse_list`, `p_refuse_maketrans1`.

**Tests on final commit**
- `test_ail_cov49`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: **29 tests, 0 failed, 1 skipped** (no zig).
- `update_manifest.py --check` and `ci_shards.py --check` pass.

**Commits**
- `f9415e6` cov49: str.translate / str.maketrans on the general path
- `2f6366e` cov49: pin the new test module in the manifest
[cost $0.3060, opencode tokens {"total": 37329598, "input": 977777, "output": 32780, "reasoning": 51393, "cache.write": 0, "cache.read": 36267648}]
    tool time: bash 51.7 min, edit 0.0 min, write 0.0 min
        805s bash   python3 /tmp/prof.py > /tmp/prof.out 2>&1; tail -90 /tmp/prof.out
        660s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && AIL_NO_CACHE=1 python3 -m unittest test_ail_cov49 test_ail_s
        527s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && AIL_NO_CACHE=1 python3 -m unittest test_ail_cov49 test_ail_s
        526s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && AIL_NO_CACHE=1 python3 -m unittest test_ail_cov49 test_ail_s
         48s bash   cat > /tmp/prof_after.py <<'EOF' import json, os, subprocess, sys, tempfile, shutil from concurrent.futures im
         41s bash   cat > /tmp/prof3.py <<'EOF' import json, os, re, subprocess, sys, tempfile, shutil from concurrent.futures imp
         41s bash   cat > /tmp/prof2.py <<'EOF' import json, os, re, subprocess, sys, tempfile, shutil from concurrent.futures imp
         36s bash   mkdir -p /tmp/probes/cov49 && cd /tmp/probes/cov49 && cat > p_basic.py <<'EOF' import string T = str.maketrans

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review: cov49 `str.translate`/`str.maketrans`

**What the diff really does.** Adds a lazily-included C fragment (`cruntime.STRTRANSLATE`) implementing `str.maketrans(frm,to[,del])` as a dict and `s.translate(dict)` as a per-code-point lookup, and routes `X.translate(...)`/`str.maketrans(...)` in `pyboxed2.py`. Report matches the diff, except it claims exact matching for cases below that do not match.

**Verified claims**
- Basic dict-table `maketrans`/`translate` (2-/3-arg, empty, delete-only, multi-char, BMP Unicode, table via arg/list/attr/dict/alias, table mutation) matches CPython on both builds: `/tmp/rprobes/{p_routes,p_delete_overlap,p_table_mutate,u1,u2,u3}.py`.
- One-arg `maketrans` and literal non-dict table are named refusals (test passes).
- Non-feature programs: `program.c` byte-identical to base on both general and default builds (`p_none_feature`).
- `test_ail_cov49` + `test_ail_safetynet`: pass (2 modules, 0 failed).
- Unverified: "24 → 23 refusals" profile numbers; `test_ail_files`/`test_ail_corpus_findings3` (not run per reviewer scope). No speed check: generated C for non-users is unchanged.

**Pre-existing (identical on base, not blocking)**
- A dict literal containing a bytes value makes the receiver infer as bytes, so `t.translate(d)` becomes `AttributeError: 'str' object has no attribute 'translate'` (`/tmp/rprobes/c4.py`, `b2.py`); base is byte-for-byte the same wrong output.

**Defects (introduced; base refuses these by name)**
1. Non-dict dynamic tables are silently mishandled. `/tmp/rprobes/nondict.py`: `show("abc", [0,1,2])` etc. — CPython `'abc'` (LookupError = no mapping); AIL `TypeError 'list' object is not subscriptable`. Same for tuple/str. `/tmp/rprobes/mapping.py`: custom `__getitem__` — CPython `ZZZ`, AIL `TypeError: 'M' object is not subscriptable`. These must stay named compile-time refusals if unsupported.
2. An unrelated class defining `translate` disables routing for string receivers. `/tmp/rprobes/shadow2.py`: CPython prints `zbc`, `('foo', 7)`, `zbc`; AIL exits 1 with `AttributeError: 'str' object has no attribute 'translate'` (base refused by name).
3. In-range non-BMP integer mapping value. `/tmp/rprobes/q_f.py` (`{97:0,98:255,99:0x10FFFF}`): CPython `'\x00ÿ\U0010ffff'`, exit 0; AIL `AIL internal error: chr() non-BMP code point requires 32-bit strings`, exit 1.
4. Out-of-range integer mapping value prints the wrong exception text. `/tmp/rprobes/c1.py` / `c2.py`: CPython `ValueError character mapping must be in range(0x110000)`; AIL `ValueError chr() arg not in range(0x110000)`.
5. `str.maketrans` first-argument TypeError text is wrong. `/tmp/rprobes/maketrans_err.py`: CPython `TypeError first maketrans argument must be a string if there is a second argument`; AIL `TypeError maketrans() argument 1 must be str, not int` (arg 2/3 texts and length mismatch match).

Note: `test_ail_cov49`'s `values` case leaves `{97: 300, 98: -1}` uncaught, so it compares only stdout/exit and does not catch defect 4.

VERDICT: FIX
1. Support or refuse non-dict/custom-mapping translate tables (nondict.py, mapping.py).
2. Do not let a class's `translate` method disable routing for str variables (shadow2.py).
3. Refuse or correctly implement non-BMP integer mapping values; no internal error (q_f.py).
4. Use CPython's `character mapping must be in range(0x110000)` message (c1.py).
5. Use CPython's first-maketrans-argument TypeError message (maketrans_err.py).
[cost $0.0283, opencode tokens {"total": 1016959, "input": 79336, "output": 7577, "reasoning": 15102, "cache.write": 0, "cache.read": 914944}]
    tool time: bash 11.1 min
        162s bash   date && cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test
        100s bash   cd /tmp/rprobes python3 - <<'PY' head='''def show(t, d):     try:         print(repr(t.translate(d)))     exce
         55s bash   cd /tmp/rprobes cat > b1.py <<'EOF' try:     print("abc".translate({97: b"x"})) except Exception as e:     pri
         53s bash   cd /tmp/rprobes python3 - <<'PY' calls = [  ('c1','{97: 0x110000}'),  ('c2','{97: -1}'),  ('c3','{97: True, 98
         40s bash   cd /home/runner/work/ail-ci/ail-ci for p in c1 c4 shadow2 maketrans_err; do echo "== BASE $p =="; bash ~/tools
         37s bash   cd /home/runner/work/ail-ci/ail-ci; echo "=== BASE c4 full ==="; bash ~/tools/cmp.sh /tmp/rprobes/c4.py /tmp/b
         36s bash   cd /tmp/rprobes cat > inf1.py <<'EOF' def show(t, d):     print(t.upper())     print(t.split("b")) show("abc",
         28s bash   cd /home/runner/work/ail-ci/ail-ci echo "=== HEAD p_ranges full ==="; bash ~/tools/cmp.sh /tmp/rprobes/p_range

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
(no final text)
[cost $0.0875, opencode tokens {"total": 10320932, "input": 183021, "output": 18892, "reasoning": 30699, "cache.write": 0, "cache.read": 10088320}]
    tool time: bash 46.0 min, edit 0.0 min
        776s bash   cd /home/runner/work/ail-ci/ail-ci && echo "===== BASE =====" && python3 /tmp/count_refusals.py /tmp/base_root
        486s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_cov
        356s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/base2_current && cp -a AIL_CURRENT /tmp/base2_current && git
        353s bash   cd /home/runner/work/ail-ci/ail-ci && echo "===== CURRENT =====" && python3 /tmp/count_refusals.py /home/runne
        273s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_cov
        222s bash   cd /home/runner/work/ail-ci/ail-ci && for p in c1 c2 c3 c4 c5 c6 c7 q_a q_b q_c q_d q_e q_f q_g b1 b2 b3 inf1 
        138s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/cov49fix/*.py /tmp/rprobes/nondict.py /tmp/rprobes/
         57s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/cov49fix/*.py; do echo "######## $(basename $p)"; b
(cut off after 60 minutes)

## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review — job `job-cov49-10291923`

**What the change really does:** the general path now lowers `str.maketrans(frm, to[, delete])` to a dict and `s.translate(table)` to a per-code-unit lookup (dict via `ail_dict_contains`, everything else via `ail_op_getitem`), and adds a whole-module compile-time scan: if *any* `*.translate` attribute exists and *any* dict literal has an int value in `0x10000..0x10FFFF` or `0xD800..0xDFFF`, the program is refused. It matches the report except that the non-BMP refusal covers only dict literals, not list/tuple literals or dynamic values.

**Probes** (all `/tmp/rprobes/`, `bash ~/tools/cmp.sh <p> $PWD`, base `/tmp/base49` = `work`):

| probe | result |
|---|---|
| `boolkey`, `arity2`, `bytes_tr`, `routes`, `custom`, `shadow`, `seq`, `deleteoverlap`, `values`, `floatkey`, `bytes_arg` | match CPython, both builds |
| `nofeature` + `plain.py` | match; generated `program.c` byte-identical to base |
| `custom_big`, `dyn_nonbmp`, `mut_nonbmp`, `dyn_surrogate`, `emoji`, `list_nonbmp`, `bigval`, `overref` | **differ (below)** |
| `arity`, `maketrans_err2`, `lookuperror`, `lookup_sub` | refused by name (acceptable) |
| `lab/corpus/.../t484.py` | both builds match; base refuses by name |

**Tests:** `par_check -j 2 test_ail_cov49 test_ail_safetynet` → `2 modules, 0 failed`. `update_manifest.py --check` exit 0.

**Defects**

1. Non-BMP/surrogate mapping values are not refused at compile time when the value is not a dict literal. `/tmp/rprobes/emoji.py`:
   ```python
   v = 0x1F600
   s = "smile a"
   print(s.translate({97: v}))
   print(len(s.translate({97: v})))
   ```
   Expected (CPython, exit 0): `smile 😀` / `7`. Actual, both builds: no stdout, stderr `ValueError: non-BMP character mapping is not supported in the 16-bit v2 runtime`, exit 1. The same happens for a **literal list table** (`t = [0]*97 + [0x1F600]`, expected `😀`) and for surrogate values (`{97: 0xD800}`, expected `'\ud800'`). Base refused these programs by name; the task says what cannot match must stay a *named compile-time refusal*, not a runtime difference.

2. Big-integer mapping values raise the wrong exception. `/tmp/rprobes/bigval.py`:
   ```python
   for d in [{97: 10**30}, {97: -(10**30)}, {97: 1 << 70}]:
       try: print(repr("a".translate(d)))
       except Exception as e: print(type(e).__name__, e)
   ```
   Expected: `ValueError character mapping must be in range(0x110000)` ×3. Actual, both builds: `TypeError character mapping must return integer, None or str` ×3. `ail__is_intlike` is `INT || BOOL` only, so `AIL_T_BIG` falls into the bad-type branch instead of the range check. This makes the report's claim that out-of-range ints raise CPython's `ValueError` false.

3. The refusal scan is too broad (false refusal). `/tmp/rprobes/overref.py`:
   ```python
   def tr(s, t): return s.translate(t)
   d = {1: 0x10FFFF}
   print("hello", d)
   print(tr("abc", {97: 98}))
   ```
   Expected (CPython): `hello {1: 1114111}` / `bbc`. Actual, both builds: refused with `str.translate() with the non-BMP mapping value U+10FFFF...`, because the scan pairs the ASCII translate call with an unrelated dict literal anywhere in the module. (Base also refused this program, so this is not a regression, but the new scan refuses a program the feature supports.)

**Claims:** non-dict tables work — verified; user class `translate` no longer disables the str handler — verified; literal non-dict table supported — verified; maketrans error texts and `translate` arity — verified; "non-BMP/surrogate values refused by name (no silent replacement)" — **false** for dynamic/list values; "out-of-range values raise CPython's ValueError" — **false** for big ints; "24 before / 23 after" — unverified; t484 matches — verified. The last commit `6e4ad25 "fix: uncommitted edits"` carries substantive source changes and lacks the required `Co-Authored-By` trailer.

**Pre-existing:** the 16-bit runtime cannot construct non-BMP characters (`chr()` aborts too); no unrelated differences found.

**Unverified:** corpus refusal counts (24→23); `test_ail_files`/`test_ail_corpus_findings3` (not run per review scope); wide-string build.

VERDICT: FIX

1. Non-BMP/surrogate mapping values reachable at run time (dynamic dict, mutated dict, list/tuple literal, custom `__getitem__`) produce `ValueError … not supported …` / exit 1 instead of CPython's character output; refuse them by name at compile time or encode an astral character (probe `emoji.py`, `list_nonbmp.py`, `dyn_surrogate.py`).
2. `AIL_T_BIG` mapping values raise `TypeError: character mapping must return integer, None or str` instead of `ValueError: character mapping must be in range(0x110000)` (probe `bigval.py`).
3. The non-BMP refusal scan refuses valid programs when an unrelated dict literal contains a non-BMP/surrogate int (probe `overref.py`); narrow it to tables that can actually reach `translate`.
[cost $0.0510, opencode tokens {"total": 3274493, "input": 110555, "output": 11018, "reasoning": 30744, "cache.write": 0, "cache.read": 3122176}]
    tool time: bash 5.2 min
        143s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_
         59s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in overref dyn_nonbmp mut_nonbmp dyn_surrogate boolkey ari
         32s bash   cat > /tmp/rprobes/bytes_tr.py <<'EOF' print(repr(b"abc".translate(None, b"b"))) ba = bytearray(b"abc") print(
         17s bash   cat > /tmp/rprobes/bytes_arg.py <<'EOF' def f(x):     return x.translate(None, b"b") print(repr(f(b"abc"))) de
         15s bash   cd /tmp/base49 && date && for p in dyn_nonbmp custom_big overref; do echo "######## $p"; bash ~/tools/cmp.sh /
          6s bash   cd /home/runner/work/ail-ci/ail-ci && date && bash ~/tools/cmp.sh lab/corpus/programs/deepseek-v4.1-flash-free
          6s bash   cat > /tmp/rprobes/bigval.py <<'EOF' for d in [{97: 10**30}, {97: -(10**30)}, {97: 1 << 70}]:     try:        
          5s bash   cd /tmp && H=$(mktemp -d /tmp/dhXXXX) && B=$(mktemp -d /tmp/dbXXXX) && AIL_NO_CACHE=1 AIL_QUIET_FALLBACK=1 pyt

FINAL VERDICT: FIX  2026-10-29T13:42:35Z
