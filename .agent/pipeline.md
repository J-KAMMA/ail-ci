# job job-pre198-10252040  started 2026-10-25T11:40:53Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":370,"duration_api_ms":245,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":370,"duration_api_ms":245,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the iterator/`NotImplemented` fillchar type names on both builds.

- `ail_type_name_of` now maps concrete iterator kinds (`list_iterator`, `enumerate`, `zip`, `map`, `filter`, `dict_*iterator`, `set_iterator`, `str_ascii_iterator`, `str_iterator`, `list_reverseiterator`, itertools kinds) and displays the hidden `_AilNotImplementedType` as `NotImplementedType`.
- `bytes`/`bytearray` iterators now name themselves `bytes_iterator`/`bytearray_iterator` via `_ail_b_iter`, without changing per-item iteration.
- Added `test_ail_pre198.py`; updated `DIFFERENCES.md`, `DEVLOG.md`, and `MANIFEST.json`.

Probes (all `same stdout` on general and default builds):
`p_pre198_all.py`, `p_pre198_pre182a.py`, `p_pre198_bytesiter.py`, `p_pre198_iterbytes.py`, `p_pre198_widthorder.py`.

Tests on final commit: `test_ail_pre198`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. `test_ail_pre182` and `test_ail_fuzz51` also pass.

Commits: `98098f0`, `868dc67`. Working tree clean except untracked `.agent/pipeline.md`.
[cost $0.0000, opencode tokens {"total": 10950223, "input": 329085, "output": 26837, "reasoning": 42365, "cache.write": 0, "cache.read": 10551936}]
    tool time: bash 21.2 min
        333s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre198 test_ail_safetynet test_ail_files test_ai
        258s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre198 test_ail_safetynet test_ail_files test_ai
        257s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre198 test_ail_safetynet test_ail_files test_ai
         73s bash   for p in /tmp/probes/p_pre198_all.py /tmp/probes/p_pre198_pre182a.py /tmp/probes/p_pre198_bytesiter.py /tmp/pr
         36s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre198 test_ail_pre182 test_ail_fuzz51
         25s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre182 test_ail_fuzz51
         21s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre198
         19s bash   cat > /tmp/probes/p_pre198_all.py <<'PY' class Box:     pass   def show(label, f):     try:         print(labe

## review 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
**What the diff really does.** Adds a `name_kind` byte to `ail_iterobj` (set only by a new `_ail_b_iter` primitive for `bytes`/`bytearray`), makes `type(x).__name__` (`ail_type_name_of`) switch on iterator kind and rename `_AilNotImplementedType` to `NotImplementedType`, plus test/records. Iteration itself is unchanged.

**Probes (HEAD both builds unless noted)**
- `a_views.py` — direct `iter(d.keys())` OK, but a view reached via a tuple/loop variable is `list_iterator` (CPython `dict_*iterator`).
- `g_def1.py` — deque and reversed-deque iterators are `list_iterator`/`list_reverseiterator` (CPython `_deque_iterator`/`_deque_reverse_iterator`; fillchar errors also need `collections.`); view route as above. Base said `iterator` for all.
- `f_itt.py` — accumulate/zip_longest/starmap errors say `not accumulate` etc.; CPython says `not itertools.accumulate` etc. (their `type().__name__` is correctly `accumulate`). Base said `iterator`.
- `h_mut.py` — bytearray mutation/append before consuming the iterator: values and `bytearray_iterator`/`str_ascii_iterator` match CPython; base names were `iterator`. Verified.
- `d_it.py`, `b_misc.py` — generator-backed `itertools` kinds still named `generator`; base identical → pre-existing.
- `i_nofeature.py` — matches CPython on both builds/base.
- Worker's five `/tmp/probes/p_pre198_*` probes: all `same stdout` on both builds (verified).

**Claims.** Core list/tuple/str/enumerate/zip/map/filter/reversed/NotImplemented and bytes/bytearray names: verified. "dict/set/range iterators and the itertools kinds now match CPython": **false/incomplete** (see defects; direct dict iteration and `iter(h.values())` do match). `update_manifest.py --check` rc 0, commits `98098f0`/`868dc67`, test `test_ail_pre198`+`test_ail_safetynet`+`test_ail_pre182` passed on HEAD (3 modules, 125 s, 0 failed). Worker's `test_ail_files`/`test_ail_corpus_findings3` run not repeated → unverified. Speed not measured; no hot path by inspection.

**Pre-existing.** `itertools.chain/count/cycle/repeat/islice/takewhile/dropwhile/pairwise` are generators in AIL and report `generator` (base identical).

**Defects**
1. `ail__iter_type_name`'s `AIL_IT_LIST`/`AIL_IT_REVERSED` cases ignore the target's deque flag and dict-view `aux`, so the fix replaces the old generic `iterator` with a *wrong concrete* name. Probe `/tmp/rprobes/g_def1.py`: expected `_deque_iterator` / `_deque_reverse_iterator` / `dict_keyiterator` / `dict_valueiterator` / `dict_itemiterator`, actual `list_iterator` / `list_reverseiterator` / `list_iterator` (x3) on both builds; base `iterator`. The fillchar errors inherit the same wrong names. (`x = d.keys()` is refused by name, acceptable; the tuple/loop route compiles and misnames.)
2. Iterator fillchar errors use `type().__name__`, but CPython's message uses the type's qualified `tp_name`: probe `/tmp/rprobes/f_itt.py` — `b"abc".ljust(5, itertools.accumulate([1]))` expected `... not itertools.accumulate`, actual `... not accumulate` (also `itertools.zip_longest`, `itertools.starmap`); base said `iterator`. The new AIL_LIT_* mapping is correct for `__name__` but the error text remains wrong.

VERDICT: FIX
[cost $0.0430, opencode tokens {"total": 1251308, "input": 133740, "output": 7382, "reasoning": 25386, "cache.write": 0, "cache.read": 1084800}]
    tool time: bash 7.9 min
        127s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_pre
         74s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p_pre198_all p_pre198_pre182a p_pre198_bytesiter p_pre198_iterb
         54s bash   cat > /tmp/rprobes/g_def1.py <<'PY' from collections import deque d = {"a": 1, "b": 2} def show(label, f):    
         43s bash   cd /home/runner/work/ail-ci/ail-ci && for p in a_views b_misc; do echo "===== $p HEAD"; bash ~/tools/cmp.sh /t
         35s bash   cd /home/runner/work/ail-ci/ail-ci && for p in a_views b_misc c_ni; do echo "===== $p HEAD"; bash ~/tools/cmp.
         35s bash   cat > /tmp/rprobes/e_views2.py <<'PY' class Box:     pass def show(label, f):     try:         print(label, re
         30s bash   cat > /tmp/rprobes/d_it.py <<'PY' import itertools from collections import deque def show(label, f):     try: 
         27s bash   cat > /tmp/rprobes/i_nofeature.py <<'PY' class C:     pass c = C() c.x = [1, 2, 3] d = {"k": c.x} print(sum(d[

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed both reviewer defects and committed as `101d77e`.

**Changes**
- Deque iterators now report `_deque_iterator` / `_deque_reverse_iterator`; `reversed(deque)` also yields values in CPython order (it previously returned the wrapper's contents). Dict-view iterators now report `dict_keyiterator` / `dict_valueiterator` / `dict_itemiterator`.
- Fillchar errors now use a new `_ail_b_tpname` primitive (CPython `tp_name`), giving `itertools.accumulate` / `zip_longest` / `starmap` / `groupby` / `_grouper` and `collections._deque_iterator` etc., while `type(x).__name__` stays unqualified.
- Updated `test_ail_pre198.py`, DIFFERENCES, DEVLOG; `update_manifest.py --check` rc 0.

**Tests on final commit**
`test_ail_pre198`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_pre182` — 5 modules, 264 s, 0 failed.

**Probes** (all `same stdout` on both builds)
- `p198_deque`, `p198_views`, `p198_it5`, `p198_groupby`, `p198_tpmore`, `p198_dequeops`, `p198_testprog`
- Regression: `p_pre198_all`, `p_pre198_bytesiter`, `p_pre198_iterbytes`, `p_pre198_pre182a`, `p_pre198_edges`, `p_pre198_widthorder`

Speed was not measured; the default-fill path still returns before the new code, so no expected hot-path change.
[cost $0.0635, opencode tokens {"total": 6624250, "input": 126796, "output": 20733, "reasoning": 21169, "cache.write": 0, "cache.read": 6455552}]
    tool time: bash 14.6 min, edit 0.0 min
        266s bash   cd AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_pre198 test_ail_safetynet test_ail_
        128s bash   cd AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_pre198 test_ail_safetynet 2>&1 | ta
        112s bash   for p in p198_testprog p198_deque p198_views p198_it5 p198_tpmore p198_groupby; do echo "===== $p"; bash ~/too
         91s bash   for p in p_pre198_all p_pre198_bytesiter p_pre198_iterbytes p_pre198_pre182a p_pre198_edges p_pre198_widthorde
         59s bash   for p in p198_deque p198_views p198_it5; do echo "===== $p"; bash ~/tools/cmp.sh /tmp/probes/$p.py "$PWD"; don
         26s bash   bash ~/tools/cmp.sh /tmp/probes/p198_deque.py "$PWD"
         25s bash   cat > /tmp/probes/p198_deque.py <<'PY' from collections import deque  class Box:     pass  def show(label, f):
         24s bash   python3 - <<'PY' import ast from pathlib import Path s = Path('AIL_CURRENT/test_ail_pre198.py').read_text() m 

## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change does.** Adds a `name_kind` byte to `ail_iterobj`, teaches `ail_type_name_of`/a new `_ail_b_tpname` to name iterator classes (CPython `__name__` and `tp_name`), marks deque and bytes/bytearray iterators, adds real `reversed(deque)` traversal, and switches the `ljust/rjust/center` fillchar TypeError from `type().__name__` to `ail__tname_c`/`tp_name`. A program using none of this (`print(1 + 2)`) emits byte-identical C (0-line diff, `--debug-dir` vs base); a plain loop only contains the runtime struct/`ail_iter` edits.

**Probes (HEAD and base, both builds).** `r_fill2` (all core iterator kinds and module-qualified itertools/deque fillchars), `r_deque` (iter/for/reversed, empty, maxlen, mutation), `r_views` (keys/values/items, arguments, mutation), `r_revviews`, `r_collide`, `r_prefix`, `r_exc2` (caught exceptions as fillchar), `r_bamut` (bytearray mutation/slice/reuse), `r_nofeat`/`r_plain` (C diff).

**Defects found (introduced by this change).**
1. Exception values regress. `_ail_b_tpname`/`ail__tpname_c` (`pyboxed2.py:666`) falls through to `ail__tname_c`, which handles `AIL_T_INST` but not `AIL_T_EXC` (`cruntime.py:14673`), so a caught exception is named `exception`. Base matched CPython.
2. Reusing `ail__tname_c` also makes hidden-class detection name-based: a user class named `_AilDeque_*` is reported as `collections.deque`, and a user class named `_AilNotImplementedType` is renamed `NotImplementedType` even in `type(x).__name__`. Base matched CPython.

The new `test_ail_pre198.py` does not cover an exception fillchar, so it misses defect 1.

**Pre-existing (also wrong on base; not blocking).**
- `itertools.chain/islice/count/cycle/repeat/takewhile/dropwhile/pairwise` fillchar names say `generator` (baseline too; they are generator-backed, so the new `AIL_LIT_*` cases are dead).
- `reversed(d.keys()/values()/items())` reports `list_reverseiterator` instead of `dict_reverse*iterator` (base reported `iterator`; still wrong).
- Deque mutation during iteration never raises CPython's `RuntimeError` (forward was already wrong on base; the new reversed path repeats that; `r_deque`/`r_bamut`).

**Claims.** Deque/dict-view forward names, `reversed(deque)` order (non-mutated), `accumulate/zip_longest/starmap/groupby/_grouper` and `collections._deque_iterator`, unqualified `type().__name__`, DIFFERENCES/DEVLOG, and `update_manifest.py --check` rc 0: **verified**. “5 modules, 264 s, 0 failed”: **unverified** (I ran only the required two). The `itertools` fillchar claim holds only for the four named classes; `chain` etc. remain `generator` (not claimed in the report body). Speed: **unverified** — `tools/icount.c` builds but `perf_event_open: Permission denied`, as reported; the extra work is one predictable branch per iterator construction.

**Tests.** `test_ail_pre198`, `test_ail_safetynet` on HEAD: 2 modules, 127 s, 0 failed. `git diff --check` clean.

VERDICT: FIX

1. **Exception fillchar is named `exception`.** Probe `r_exc2.py`: `try: 1/0` / `except ZeroDivisionError as e:` / `b"abc".ljust(5, e)`. Expected `TypeError: ljust() argument 2 must be a byte string of length 1, not ZeroDivisionError` (also `ValueError` for a caught `raise ValueError("x")`); actual on both builds `... not exception`. Base matches CPython. Fix `ail__tpname_c`/`ail__tname_c` to handle `AIL_T_EXC` (and add an exception case to the test).
2. **Hidden classes are recognised by class-name text.** Probe `r_prefix.py`: `class _AilDeque_Foo: pass` / `b"abc".ljust(5, _AilDeque_Foo())`; expected `... not _AilDeque_Foo`, actual `... not collections.deque`. Probe `r_collide.py`: `class _AilNotImplementedType: pass` / `type(_AilNotImplementedType()).__name__`; expected `_AilNotImplementedType`, actual `NotImplementedType` (and the fillchar text likewise). Both builds; base matches CPython. Identify the internal deque/NotImplemented classes by object identity, not by name prefix/`strcmp`.
[cost $0.0523, opencode tokens {"total": 2960495, "input": 101378, "output": 14667, "reasoning": 33058, "cache.write": 0, "cache.read": 2811392}]
    tool time: bash 8.0 min
        129s bash   cd AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pre198 test_ail_safetynet 2>&1 | ta
         72s bash   cat > /tmp/rprobes/r_fill2.py <<'PY' import itertools from collections import deque  class Box:     pass  def 
         29s bash   cd /tmp && for p in r_revviews r_collide; do echo "===== HEAD $p"; timeout 600 bash ~/tools/cmp.sh /tmp/rprobe
         28s bash   cd /tmp && for p in r_revviews r_collide; do echo "===== base $p"; timeout 600 bash ~/tools/cmp.sh /tmp/rprobe
         28s bash   cd /tmp && for p in r_exc r_names r_itfill; do echo "===== HEAD $p"; timeout 600 bash ~/tools/cmp.sh /tmp/rpro
         27s bash   cat > /tmp/rprobes/r_exc2.py <<'PY' def fill(v):     return b"abc".ljust(5, v)  def main() -> None:     try:  
         27s bash   cat > /tmp/rprobes/r_prefix.py <<'PY' class _AilDeque_Foo:     pass  def fill(v):     return b"abc".ljust(5, v
         24s bash   cd /tmp && timeout 600 bash ~/tools/cmp.sh /tmp/rprobes/r_fill2.py /tmp/base > /tmp/base_fill2.log 2>&1; echo 

FINAL VERDICT: FIX  2026-10-25T13:20:06Z
