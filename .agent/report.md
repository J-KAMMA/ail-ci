# job job-std_bisect-11012338  started 2026-11-01T14:47:18Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed both review defects.

- `ail__bisect_len` now uses the runtime's generic `ail_op_len` instead of the manual list/tuple/str switch, covering `range`, `bytes`, `bytearray` and deques.
- Probes `/tmp/probes/v_range.py` and `/tmp/probes/v_bytes.py`: both builds match CPython exactly (exit 0, identical stdout), including lo/hi, `hi=None`, negative lo, empty sequences, out-of-range hi, and `insort` AttributeError.
- Added regression coverage (`test_key_on_range_and_bytes`) to `test_ail_std_bisect`.
- `python3 tools/update_manifest.py && --check`: pass.
- Final tests on the commit: `test_ail_std_bisect`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed.

Committed as `bc714b3`.
[cost $0.0000, opencode tokens {"total": 1333660, "input": 49547, "output": 6783, "reasoning": 4626, "cache.write": 0, "cache.read": 1272704}]
    tool time: bash 18.5 min, edit 0.0 min
        412s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_std_bisect test_ail_safetynet t
        322s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_std_bisect test_ail_safetynet t
        313s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_std_bisect test_ail_safetynet t
         33s bash   cd /tmp/probes && for f in v_range v_bytes; do echo "=== $f"; bash ~/tools/cmp.sh /tmp/probes/$f.py /home/runn
         24s bash   mkdir -p /tmp/probes && cat > /tmp/probes/v_range.py <<'EOF' import bisect  def key(v):     return str(v)  cla
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c

## review 0
[model opencode/deepseek-v4.1-flash-free]
## review 2

**What the change does.** Replaces the manual list/tuple/str length switch in `ail__bisect_len` (`AIL_CURRENT/python/pkg-v12/pyboxed2.py:693`) with `ail_op_len`, plus a new range/bytes/bytearray test, DEVLOG and manifest hashes. Matches the report.

**Verified.**
- Review defects 1 and 2 are fixed: `v_range.py`, `v_bytes.py`, `v_deque.py` and a custom `__len__`/`__getitem__` class (`v_custom.py`) match CPython on both builds; base fails the range/bytes probes with exit 1.
- `test_ail_std_bisect` + `test_ail_safetynet`: 2 modules, 0 failed. `update_manifest.py` and `--check` clean.
- Non-key codegen unchanged: `nokey.py` and `lab/compare/src/berth_sim/main.py` `program.c` byte-identical to `/tmp/base`.
- Report claims verified except that "instance `__len__`" only works when the instance also has `__getitem__` (see defect 2).

**Defects (all introduced by this change; base raised TypeError).**

VERDICT: FIX
1. `ail_op_len` accepts `dict`/`set`/`frozenset`, but `bisect` must reject non-sequences even when empty. `v_dict_empty.py`:
```python
import bisect
def ident(v): return v
def main():
    try: print("dl", bisect.bisect_left({}, 1, key=ident))
    except TypeError as e: print("dl TypeError", e)
    try: print("dr", bisect.bisect_right({}, 1, key=ident))
    except TypeError as e: print("dr TypeError", e)
    try: print("sl", bisect.bisect_left(set(), 1, key=ident))
    except TypeError as e: print("sl TypeError", e)
    try: print("sr", bisect.bisect_right(frozenset(), 1, key=ident))
    except TypeError as e: print("sr TypeError", e)
main()
```
Expected (CPython): `dl TypeError dict is not a sequence`, `dr TypeError dict is not a sequence`, `sl TypeError 'set' object does not support indexing`, `sr TypeError 'frozenset' object does not support indexing`. Actual both builds: `dl 0`, `dr 0`, `sl 0`, `sr 0`, exit 0. Non-empty `{0:10,1:20,2:30}` likewise prints `dl 0`/`dr 0` instead of TypeError (`v_dict_full.py`).
2. Same root cause for any object with `__len__` but no `__getitem__` and length 0. `v_lenonly.py` defines `class NoGet: def __len__(self): return 0`; expected CPython `TypeError 'NoGet' object does not support indexing`, actual both builds `0` twice.

**Pre-existing / not rechecked.** Earlier non-key items (str `bisect_left` segfault, default-build insort IndexError, non-BMP refusals) were not re-run this round. Huge-range keyed bisect gives the same empty stdout and exit 1 as CPython, with AIL's declared int-overflow message.
[cost $0.0000, opencode tokens {"total": 1122974, "input": 42976, "output": 6147, "reasoning": 10555, "cache.write": 0, "cache.read": 1063296}]
    tool time: bash 4.7 min
        171s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_
         31s bash   cd /tmp/rprobes && for f in v_range v_bytes v_dict_empty v_dict_full v_custom v_deque; do echo "=== $f"; bash 
         30s bash   cd /tmp/rprobes && for f in v_dict_empty v_dict_full v_range v_bytes; do echo "=== $f BASE"; bash ~/tools/cmp.
         25s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/cg_head /tmp/cg_base && mkdir -p /tmp/cg_head /tmp/cg_base &
          7s bash   cd /tmp/rprobes && for f in v_dict_empty v_dict_full; do echo "=== $f BASE"; bash ~/tools/cmp.sh /tmp/rprobes/
          7s bash   cd /tmp/rprobes && for f in v_dict_empty v_dict_full; do echo "=== $f"; bash ~/tools/cmp.sh /tmp/rprobes/$f.py
          7s bash   cd /tmp/rprobes && cat > v_lenonly.py <<'EOF' import bisect   class NoGet:     def __len__(self):         retu
          3s bash   cd /tmp/rprobes && cat > v_huge_range.py <<'EOF' import bisect   def main():     r = range(-922337203685477580

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed both review defects and committed as `edcc092`.

- Keyed bisect now rejects non-sequences like CPython: plain `dict` / `defaultdict` → `... is not a sequence`; `set` / `frozenset` / `__len__`-only instances → `... does not support indexing`.
- Preserved valid cases: `Counter`, `range`, bytes/bytearray, custom `__getitem__` objects, and `hi=` paths that avoid calling `len()`.

Probes `/tmp/rprobes/{v_dict_empty,v_dict_full,v_lenonly,v_lenonly_noinit,v_getonly_hi,v_range,v_bytes,v_custom,v_deque}.py` match CPython on both builds.

Tests: `test_ail_std_bisect`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. `update_manifest.py --check` clean.
[cost $0.0000, opencode tokens {"total": 4767244, "input": 106471, "output": 12473, "reasoning": 17132, "cache.write": 0, "cache.read": 4631168}]
    tool time: bash 8.5 min, websearch 0.0 min, edit 0.0 min
        311s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1800 python3 ../tools/par_check.py -j 2 test
        120s bash   python3 - <<'EOF' import _bisect, sys print(_bisect) print(_bisect.__spec__) EOF find / -name "_bisect*" 2>/de
         37s bash   cd /tmp/rprobes && for f in v_range v_bytes v_custom v_deque v_dict_empty v_dict_full v_lenonly v_getonly_hi v
         12s bash   cd /tmp/rprobes && cat > v_dict_full.py <<'EOF' import bisect def ident(v): return v def main():     d = {0: 1
          8s bash   cd /tmp && rm -rf ccheck && mkdir ccheck && cd ccheck && cat > p.py <<'EOF' import bisect class NoGet:     def
          8s bash   cd /tmp/ccheck && AIL_UNIFIED_FORCE=1 AIL_NO_CACHE=1 python3 /home/runner/work/ail-ci/ail-ci/AIL_CURRENT/pytho
          4s bash   cd /tmp/rprobes && cat > v_lenonly_noinit.py <<'EOF' import bisect class NoGet:     def __len__(self):        
          3s bash   cd /tmp && rm -rf nkey && mkdir nkey && cd nkey && AIL_NO_CACHE=1 python3 /home/runner/work/ail-ci/ail-ci/AIL_

## review 1
[model opencode/deepseek-v4.1-flash-free]
## Review report

**What the change does.** In `BISECTKEY_C` (`AIL_CURRENT/python/pkg-v12/pyboxed2.py`) it replaces the manual list/tuple/str `ail__bisect_len` with a generic `ail_op_len`, and adds `ail__bisect_is_seq`/`ail__bisect_seq_chk` so keyed `bisect*` rejects mappings (except `Counter`) and index-less objects with CPython's messages. `hi=` given still avoids `len()`. The fragment is gated on `needs_bisect_key`, so non-key codegen is untouched.

**Previous defects — both fixed.**
- `v_range.py`: `5 6 0 ...` matches CPython, exit 0 on both builds.
- `v_bytes.py`: `2 3 0 ...` matches CPython, exit 0 on both builds (general path now works).

**Report claims — all verified.**
- Non-sequences rejected like CPython: dict/defaultdict → `... is not a sequence`; set/frozenset/`__len__`-only → `... does not support indexing` (`v_dict_empty`, `v_dict_full`, `v_lenonly`, `v_lenonly_noinit`, `c_dd2`).
- Valid cases preserved: `Counter`, `range`, `bytes`/`bytearray`, custom `__getitem__`, `hi=` without `len()` (`c_counter`, `c_inherit`, `c_order`, `v_custom`, `v_getonly_hi`).
- Order of key calls / error precedence on `insort` of non-lists matches CPython (`c_order`, `c_mutate`).
- Tests `test_ail_std_bisect test_ail_safetynet test_ail_files test_ail_corpus_findings3`: 4 modules, 0 failed. `update_manifest.py --check` clean.
- `berth_sim` generated `program.c` is byte-identical to `/tmp/base`.

**Pre-existing / not caused by the change.** `OrderedDict`/`defaultdict(factory, mapping)` programs are refused by name (unsupported collections surface), independent of `key=`. Not blocking.

**Unverified.** Full 17-pair codegen sweep (spot-checked one); instruction counts (keyed bisect is not in the gdev hot path, and non-key C is identical).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 879264, "input": 164528, "output": 6249, "reasoning": 13447, "cache.write": 0, "cache.read": 695040}]
    tool time: bash 6.9 min
        314s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1800 python3 ../tools/par_check.py -j 2 test
         55s bash   cd /home/runner/work/ail-ci/ail-ci && date && for f in /tmp/rprobes/*.py; do echo "=== $(basename $f) ==="; ti
         18s bash   rm -rf /tmp/cg && mkdir -p /tmp/cg && (cd /home/runner/work/ail-ci/ail-ci && timeout 300 python3 AIL_CURRENT/a
         18s bash   cd /tmp/rprobes && cat > c_counter.py <<'EOF' import bisect from collections import Counter   def main():     
          4s bash   cd /tmp/rprobes && cat > c_dd2.py <<'EOF' import bisect from collections import defaultdict   def ident(v):   
          1s bash   cd /tmp/rprobes && cat > c_od_counter.py <<'EOF' import bisect from collections import OrderedDict, Counter   
          0s bash   cd /tmp && rm -rf cg_head cg_base && mkdir -p cg_head cg_base && (cd /home/runner/work/ail-ci/ail-ci && timeou
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check 2>&1 | tail -5; ls lab/compare/

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-01T17:02:39Z
