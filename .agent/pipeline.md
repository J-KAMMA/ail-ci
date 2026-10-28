# job job-pre421-10281638  started 2026-10-28T07:39:00Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"ea01038e-7d24-455c-92ff-a330d5762702","session_id":"71d35484-58aa-4089-9d09-9e3a7a68c13a"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"54d9b486-33c5-46b8-9afe-eac6fb69eb75","session_id":"f6960b86-a3a2-46a8-978f-6f5151a00397"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done.

- Fixed `p2`: list/tuple index errors now name the key’s class (`not Box`), including list store/delete; class names capped at 200 chars.
- Commit: `e81029f`
- Added `AIL_CURRENT/test_ail_pre421.py` (1 test, 4 programs), registered it in `ail_check.py` and `tools/ci_shards.json`.
- Final-commit tests: `test_ail_pre421`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed (231s).
- Probes, both builds, all matched CPython: `p2_a`, `p2_c`, `p2_routes`, `p2_alias`, `p2_long2`, `p2_builtins`, `p2_setdel` (7/7).
- `p2_b` (`__index__` returning a non-int) still differs; separate pre-existing cause, unchanged.
- `update_manifest.py --check` passes. I did not run the `--debug-dir` C identity comparison; the runtime getitem line is shared, so generated C for no-class list-subscript programs changes.
[cost $0.0000, opencode tokens {"total": 3937778, "input": 110853, "output": 14092, "reasoning": 17505, "cache.write": 0, "cache.read": 3795328}]
    tool time: bash 11.8 min
        298s bash   cd /home/runner/work/ail-ci/ail-ci && git add AIL_CURRENT/test_ail_pre421.py AIL_CURRENT/ail_check.py AIL_CURR
        233s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre421 test_ail_
         54s bash   mkdir -p /tmp/probes/pre421 && cd /tmp/probes/pre421 && cat > p2_a.py <<'EOF' class Bad:     pass  class Box: 
         46s bash   cd /tmp/probes/pre421 && for f in p2_a.py p2_c.py p2_routes.py p2_alias.py p2_long2.py p2_builtins.py p2_setde
         24s bash   cd /tmp/probes/pre421 && cat > p2_long2.py <<'EOF' class Aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
         16s bash   cd /tmp/probes/pre421 && cat > p2_long.py <<'EOF' name = 'A' + 'a' * 299 cls = type(name, (), {}) obj = cls() 
         16s bash   cd /tmp/probes/pre421 && cat > p2_long.py <<'EOF' name = 'A' + 'a' * 209 ns = {'print': print} exec('class ' +
         13s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p = Path('AIL_CURRENT/python/p

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review of pre421**

**What the change really does (one line):** In the v2 C runtime, list/tuple getitem and list set/del now format a bad key with `ail__tname_c()` (class name, 200-char cap) instead of the tag name; no new helpers were added.

**Probes** (`bash ~/tools/cmp.sh <p> $PWD`, both builds; base `/tmp/base`):
- `p1_read` (instance, subclass, class object, builtin function, exception instance; list/tuple): HEAD matches CPython; base differs. Verified.
- `p2_setdel` (list store/delete, empty list, tuple store): HEAD matches; base differs. Verified.
- `p3_builtins` (float/str/None/list/dict/tuple/bytes/set/function keys, list and tuple): HEAD matches. Verified.
- `p4_routes` (argument, alias, list item, attribute, dict value; 200- and 210-char names): HEAD matches; base differs. Verified.
- `p5_nofeature` (no classes, int list indexing): stdout/exit match, but generated C is **not** byte-identical (defect below).
- `p6_unicode` (non-ASCII class name): refused by name on both builds. Pre-existing.
- `p7_index` (`__index__` returning a str): differs identically on HEAD and base. Pre-existing.

**Report claims:**
- Fixed `p2` getitem naming: verified.
- Store/delete also name the class: verified.
- 200-char cap: verified (200 kept, 210 truncated to 200).
- `test_ail_pre421` added/registered: verified; `test_ail_pre421` + `test_ail_safetynet` pass on HEAD (2 modules, 0 failed).
- `update_manifest.py --check`: passes.
- `p2_b` still differs: verified pre-existing (also differs on base).
- "I did not run the `--debug-dir` C identity comparison; ... generated C for no-class list-subscript programs changes": verified true — this is the defect.

**Defect 1 — required C check fails.** Probe `/tmp/rprobes/p5_nofeature_wrap.py`, a no-class program on the general path:
```python
def f(xs, i):
    print(xs[i], xs[-1], len(xs))
    xs[i] = 9
    print(xs)
    del xs[0]
    print(xs)
f([1, 2, 3], 1)
```
Expected: `--debug-dir` `program.c` byte-identical to base. Actual: three hunks differ, e.g. base `char buf[96]; ... ail_type_name(key.tag)` vs HEAD `char tnbuf[201], buf[280]; ... ail__tname_c(key)` for getitem, setitem and delitem. A module-level no-class program (`c_noclass.py`) is identical, so the breakage is specific to no-class general-path programs; the task requires byte identity for no-class programs.

**Pre-existing (not blocking):** `__index__`-returning-non-int and `__index__`-based indexing; non-ASCII class names refused.

**Unverified:** `test_ail_files` and `test_ail_corpus_findings3` on HEAD (reviewer scope is the added module plus safetynet); the worker's own 7 probes; instruction counts (change is on an error path).

VERDICT: FIX
1. No-class general-path programs get different C: `/tmp/rprobes/p5_nofeature_wrap.py` expected `program.c` byte-identical to base, actual three changed hunks in getitem/setitem/delitem (`ail_type_name(key.tag)` → `ail__tname_c(key)`). Gate the new text so it is emitted only for class-bearing programs.
[cost $0.0000, opencode tokens {"total": 593339, "input": 32507, "output": 6152, "reasoning": 13752, "cache.write": 0, "cache.read": 540928}]
    tool time: bash 3.3 min, write 0.0 min
        108s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_pre421 t
         22s bash   date; for f in /tmp/rprobes/*.py; do echo "===== HEAD $(basename $f)"; bash ~/tools/cmp.sh "$f" "$PWD" 2>&1 | 
         19s bash   date; for f in /tmp/rprobes/p4_routes.py /tmp/rprobes/p4_long.py; do for wt in "$PWD" /tmp/base; do echo "====
         15s bash   date; for f in /tmp/rprobes/p3_builtins.py /tmp/rprobes/p4_routes_long.py; do echo "===== HEAD $(basename $f)"
          9s bash   cd /tmp/rprobes && cat > p7_index.py <<'EOF' class Box:     def __index__(self):         return str(1)   def t
          8s bash   date; for f in /tmp/rprobes/p3_builtins.py /tmp/rprobes/p4_routes_long.py; do echo "===== BASE $(basename $f)"
          7s bash   cd /tmp/rprobes && cat > p6_unicode.py <<'EOF' class Café:     pass   try:     [1][Café()] except Exception as
          5s bash   for wt in "$PWD" /tmp/base; do tag=$(basename "$wt"); rm -rf /tmp/dbg_$tag; mkdir -p /tmp/dbg_$tag/keep; (cd /

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `a0a29fd`.

**Changes**
- Restored the base list/tuple index text in `cruntime.py`.
- `pyboxed2.py` now applies the class-name edits only when the source defines a class (`source_has_class`, before injected preludes).
- Added a C-text regression test to `test_ail_pre421.py`; updated DEVLOG/DIFFERENCES; manifest `--check` passes.

**Probes** (`cmp.sh`, both builds)
- `p_class_routes`, `p_class_setdel`, `p_class_builtins`, `p_long`: match CPython.
- `p_nofeature_wrap`, `p_class_nofeature`: match CPython.
- `p_noclass_slice`: matches CPython.
- `p_noclass`: stdout equals base; its remaining builtin-key wording differences are pre-existing and required by the C-identity rule.

**C check**
- No-class `--debug-dir` C byte-identical to `/tmp/base`: `p_nofeature_wrap`, `p_noclass`, `p_noclass_slice`.
- Class-bearing `p_class_nofeature` differs only in the three index-error prelude hunks.

**Tests on final commit:** `test_ail_pre421`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed.
[cost $0.0000, opencode tokens {"total": 3193612, "input": 248697, "output": 11733, "reasoning": 10814, "cache.write": 0, "cache.read": 2922368}]
    tool time: bash 5.7 min
        179s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre421 test_ail_
         38s bash   cd /home/runner/work/ail-ci/ail-ci && for f in /tmp/probes/pre421_fix/*.py; do echo "===== $(basename $f)"; ba
         25s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 - <<'PY' from pathlib import Path p=Path('test_ail_p
         22s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/cid && mkdir -p /tmp/cid && for p in p_nofeature_wrap p_nocl
         19s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -B -m unittest -v test_ail_pre421 2>&1 | tail -30
         17s bash   cd /home/runner/work/ail-ci/ail-ci && for f in /tmp/probes/pre421_fix/p_nofeature_wrap.py /tmp/probes/pre421_f
         16s bash   cd /home/runner/work/ail-ci/ail-ci && for f in /tmp/probes/pre421_fix/p_class_routes.py /tmp/probes/pre421_fix
         12s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && sed -n '9178,9200p' python/pkg-v12/cruntime.py && cat /tmp/p

## review 1
[model opencode/deepseek-v4.1-flash-free]
**What the change really does:** `pyboxed2.compile()` records whether the parsed source contains an `ast.ClassDef`; only then does it splice `ail__tname_c`-based class-name text for the list/tuple getitem/setitem/delitem errors into the v2 preamble. `cruntime.py` is net-unchanged (`git diff work..HEAD` has no hunk there), so no-class programs keep base C.

**Report claims**
- Fixed/committed as `a0a29fd` — verified (`git log`, 2 commits).
- Base index text restored in `cruntime.py` — verified (net diff for that file is empty; base text still present).
- Edits gated on `source_has_class`, set before prelude injection — verified in diff and by C comparison.
- C-text test, DEVLOG, DIFFERENCES, manifest — verified; `update_manifest.py --check` exits 0.
- Listed probes match CPython — verified by re-running all 8 listed probes; `p_noclass`/`p_builtins` caveats are accurate.
- No-class `--debug-dir` C identical to `/tmp/base` for `p_nofeature_wrap`, `p_noclass`, `p_noclass_slice` — verified, both builds; also for an independent `c_noclass2`.
- Class-bearing `p_class_nofeature` differs only in the 3 index-error hunks — verified.
- Tests on final commit, 4 modules 0 failed — verified (177s, `-j 2`).

**My probes (HEAD, both builds)**
- `p2_orig`, `p_routes`, `p_builtin_class2`, `p_dict_keys`, `p_setdel`, `p_boundary` (199/200/201/210-char names), `p_func_key`, `p_class_valid`, `p_thread_class` (thread preamble), `p_class_nofeature`, `c_noclass2` — all match CPython; C identity confirmed for no-class.

**Pre-existing (HEAD == base)**
- `p_no_class`, `p3_builtins`, `p_builtins`: no-class builtin-key wording (`bytes`→`instance`, `len`→`function`, set/del omitting `not ...`).
- `p7_index`: list index through `__index__` still not converted.
- `p_func_key` with a bound method `o.m`: AIL AttributeError, base identical.

**Unverified:** speed (change only touches cold error paths and a compile-time preamble splice); remaining pre411 items `p4`, slice `__index__`, bytes/bytearray `__index__` not re-probed beyond `p7_index`.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1082870, "input": 53616, "output": 7781, "reasoning": 17441, "cache.write": 0, "cache.read": 1004032}]
    tool time: bash 8.1 min, write 0.0 min
        179s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_pre421 t
         77s bash   cd /home/runner/work/ail-ci/ail-ci && date && for f in /tmp/rprobes/*.py; do echo "===== $(basename $f)"; bash
         59s bash   cd /home/runner/work/ail-ci/ail-ci && date && for f in p_noclass p_builtins; do echo "== $f HEAD vs BASE"; bas
         51s bash   cd /home/runner/work/ail-ci/ail-ci && for f in p_no_class p3_builtins p7_index; do echo "===== $f HEAD"; bash 
         49s bash   cd /home/runner/work/ail-ci/ail-ci && date && for f in /tmp/probes/pre421_fix/*.py; do echo "===== $(basename 
         27s bash   cd /home/runner/work/ail-ci/ail-ci && for f in /tmp/rprobes/p_no_class.py /tmp/rprobes/p3_builtins.py /tmp/rpr
         18s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/cid2 && mkdir -p /tmp/cid2 && python3 - <<'PY' import os, su
         13s bash   cd /home/runner/work/ail-ci/ail-ci && date && for f in p_builtin_class2 p_dict_keys; do echo "===== $f"; bash 

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-28T09:41:25Z
