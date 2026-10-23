# job job-pre25-10240322  started 2026-10-23T18:24:50Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the first still-differing case (p09), and p12 too.

**Change:** `dict(m)`, `dict.update(m)` and `defaultdict(factory, m)` now use the mapping protocol (`keys()` then `m[k]`) when the object defines `keys()`, instead of iterating it as pairs. Implemented in `AIL_CURRENT/python/pkg-v12/dunderrt.py`.

**Probes** — all matched CPython on both builds (`g` and `d`) via `bash ~/tools/cmp.sh`:
- `p09` keys-only mapping → `{'a': 1}`
- `p12` `keys()`/`__iter__` disagreement → CPython result
- `k01` basic `dict` / `dict.update` / no aliasing
- `k02` keys returning list, tuple, range, str, empty
- `k03` disagreement plus ordinary pair iteration
- `k04` mapping via function argument, list item, attribute, dict value
- `k05` missing key, non-iterable keys, missing `__getitem__`
- `k06` inheritance, generator keys, dict view keys
- `k07` `defaultdict(int, mapping)`

**Tests on final commit `623ac34`:**
- `test_ail_pre25`: ok, 10.9s
- `test_ail_safetynet`: ok, 97.0s
- `test_ail_files`: ok, 103.2s
- `test_ail_corpus_findings3`: ok, 154.9s
- 4 modules, 0 failed; `update_manifest.py --check` exit 0.

Added `AIL_CURRENT/test_ail_pre25.py`, a DEVLOG entry, and a DIFFERENCES row `C?-job-pre25-10240322-1`.
[cost $0.0000, opencode tokens {"total": 6146509, "input": 136785, "output": 13306, "reasoning": 14466, "cache.write": 0, "cache.read": 5981952}]
    tool time: bash 6.1 min, edit 0.0 min
        254s bash   python3 tools/par_check.py -j 2 test_ail_pre25 test_ail_safetynet test_ail_files test_ail_corpus_findings3
         33s bash   for p in /tmp/rprobes/p09.py /tmp/rprobes/p12.py /tmp/probes/k0*.py; do echo ==== $p; bash ~/tools/cmp.sh $p "
         26s bash   for p in /tmp/probes/k0*.py; do echo ==== $p; bash ~/tools/cmp.sh $p "$PWD"; done
         16s bash   mkdir -p /tmp/probes && cat > /tmp/probes/k01_basic.py <<'PY' class KeysOnly:     def keys(self):         retu
         11s bash   cat > AIL_CURRENT/test_ail_pre25.py <<'PY' """A dict built from a keys-only mapping uses keys() and __getitem_
          8s bash   mkdir -p /tmp/probes /tmp/rprobes && cat > /tmp/rprobes/p09.py <<'PY' class KeysOnly:     def keys(self):     
          8s bash   for p in /tmp/probes/k04_sources.py /tmp/probes/k05_errors.py; do echo ==== $p; bash ~/tools/cmp.sh $p "$PWD";
          7s bash   for p in /tmp/rprobes/p09.py /tmp/rprobes/p12.py; do echo ==== $p; bash ~/tools/cmp.sh $p "$PWD"; done

## review 0
[model opencode/deepseek-v4.1-flash-free]
Reviewed HEAD `623ac34`; base is `/tmp/base` at `work`. Probes in `/tmp/rprobes`, run with `bash ~/tools/cmp.sh <probe> $PWD` on both builds unless noted.

**Probes**
- `p09` keys-only mapping: CPython and HEAD both `{'a': 1}` on g/d; base raises `TypeError` -> fixed.
- `p12` `keys()`/`__iter__` disagreement: CPython and HEAD both `{'a': 1}` on g/d -> fixed.
- `k01`–`k07` rerun: all same stdout on g/d.
- Extra probes: `q02` argument/list/attribute/dict sources; `q03` tuple/range/str/empty/negative/duplicate keys; `q05`,`q14` mutation during iteration; `q06`,`q01`,`q12` errors; `q08`,`q16` defaultdict with builtin/lambda factories; `q13` custom iterator keys; `q15` custom key objects. All match CPython except the pre-existing cases below.
- `q10` (general path, class with only `__add__`, no keys/mapping): generated `program.c` differs from base (new `AIL_D1_KEYS` enum, dead mapping branch, class-name subscript error). No output change.

**Tests**
- `test_ail_pre25`: ok, 11.0s.
- `test_ail_safetynet`: ok, 95.8s.
- `2 modules, 0 failed`; `tools/update_manifest.py --check` exit 0.
- `test_ail_files` and `test_ail_corpus_findings3`: not rerun (review rule); worker's claim unverified.

**Pre-existing (same on base, so not blocking)**
- `q01` `keys()` returning a user instance without `__iter__`: CPython `TypeError NonIterInst.keys() returned a non-iterable (type NoIter)`; HEAD and base `'instance' object is not iterable`.
- `q07` `keys` as a class attribute (`list`/`str`): CPython `'list'/'str' object is not callable`; HEAD and base `'instance' object is not iterable`.
- `q02` `dict([m])` (pair-sequence path): CPython `KeyError: 0`; HEAD and base `TypeError: cannot convert dictionary update sequence element...` (same exit status).

**Speed**
- `icount` could not run: `perf_event_open: Permission denied`. Unverified.

**Report claims**: fix and probes verified; test timings verified for the two modules run; manifest/records verified; `test_ail_files`/corpus timings unverified.

**Defect**
1. `AIL_CURRENT/python/pkg-v12/dunderrt.py:505-508`: the value fetched in the new mapping branch is held only in the C local `mval` and is not rooted while `ail_dict_set()` hashes the key. A user `__hash__` that allocates triggers GC and frees `mval` before it is stored (use-after-free). This is exactly the discipline `test_ail_gcstress` checks. Probe:

```python
class K:
    def __hash__(self):
        junk = [i for i in range(10)]
        return len(junk)
    def __repr__(self):
        return "K"

class M:
    def keys(self):
        return [K()]
    def __getitem__(self, k):
        return [1, 2, 3, 4]

def main() -> None:
    print(dict(M()))

main()
```

Expected (CPython, normal build): `{K: [1, 2, 3, 4]}` exit 0. Actual under `pyc.py --general-only` with `-DAIL_GC_STRESS` + ASan (the `test_ail_gcstress` flags): empty stdout, exit 1, `AddressSanitizer: heap-use-after-free ... ail_dict_update_pairs`, freed object allocated in `pm_M___getitem__`. The equivalent pair path (`dict([(K(), [1,2,3,4])])`) passes under the same stress build. Root `mval` (e.g. a third frame slot or `AIL_ROOT1` before `ail_op_getitem`).

VERDICT: FIX
1. Unrooted mapping value `mval` in `ail_dict_update_pairs` causes a heap-use-after-free under GC stress (probe `q17_gcstress.py`; expected `{K: [1, 2, 3, 4]}`, actual ASan abort).
[cost $0.0000, opencode tokens {"total": 4580968, "input": 116087, "output": 11953, "reasoning": 39104, "cache.write": 0, "cache.read": 4413824}]
    tool time: bash 4.7 min
         97s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre25 test
         47s bash   date; cd /home/runner/work/ail-ci/ail-ci; for p in /tmp/rprobes/p09.py /tmp/rprobes/p12.py /tmp/rprobes/q0*.py
         27s bash   date; cd /home/runner/work/ail-ci/ail-ci; for p in /tmp/probes/k0*.py; do echo "==== $p"; bash ~/tools/cmp.sh 
         21s bash   date; cd /home/runner/work/ail-ci/ail-ci; for p in g05_024 g06_034 g08_028 g13_024; do for v in h b; do wt=$([
         21s bash   date; cd /home/runner/work/ail-ci/ail-ci; for p in /tmp/rprobes/p09.py /tmp/rprobes/q01_noniter.py /tmp/rprobe
         11s bash   date; cd /home/runner/work/ail-ci/ail-ci && cc -O2 -w -include signal.h -include stdlib.h -o /tmp/icount tools
          9s bash   date; cd /tmp/rprobes; cat > q14_mutation.py <<'PY' class Grow:     def __init__(self):         self.ks = ["a"
          8s bash   date; for p in q10_nofeature_add q11_nofeature_plain; do rm -rf /tmp/dbg_hg_$p /tmp/dbg_bg_$p; AIL_UNIFIED_FOR

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `83de175`.

**Defect:** `ail_dict_update_pairs` held the `__getitem__` value in an unrooted C local (`mval`), so a user `__hash__` triggering GC freed it before `ail_dict_set`. It now uses a third rooted frame slot (`fr.slots[2]`).

**Probes** (both g/d builds, all match CPython):
- `gc_mapping.py` — reviewer's exact allocating-`__hash__` case -> `{K: [1, 2, 3, 4]}`
- `gc_mapping_sources.py` — values via dict/list/attribute/argument, generator/custom keys, duplicates, negative keys, empty, update/defaultdict/fromkeys
- `gc_mapping_alias.py` — aliasing, non-scalar/None/list values

Added `test_ail_gcstress.dict_from_mapping` (ASan + `-DAIL_GC_STRESS`); DEVLOG updated.

**Tests on final commit** (`-j 2`): `test_ail_pre25` 7.8s, `test_ail_gcstress` 46.9s, `test_ail_safetynet` 78.0s, `test_ail_files` 79.9s, `test_ail_corpus_findings3` 117.4s — 5 modules, 0 failed. `update_manifest.py --check` exit 0.
[cost $0.0000, opencode tokens {"total": 968992, "input": 35166, "output": 6146, "reasoning": 4544, "cache.write": 0, "cache.read": 923136}]
    tool time: bash 6.0 min, edit 0.0 min
        167s bash   cd /home/runner/work/ail-ci/ail-ci && date && python3 tools/par_check.py -j 2 test_ail_pre25 test_ail_gcstress
        167s bash   cd /home/runner/work/ail-ci/ail-ci && date && python3 tools/par_check.py -j 2 test_ail_pre25 test_ail_gcstress
          9s bash   cat > /tmp/probes/gc_mapping_sources.py <<'PY' from collections import defaultdict   class K:     def __init__
          9s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/gc_mapping.py /tmp/probes/gc_mapping_sources.py /tm
          3s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 -B -m unittest -v test_ail_gcstress.GCStress
          3s bash   cat > /tmp/probes/gc_mapping_alias.py <<'PY' class K:     def __hash__(self):         return len([i for i in r
          0s bash   cd /home/runner/work/ail-ci/ail-ci && date && python3 tools/par_check.py -j 2 test_ail_pre25 test_ail_gcstress
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c

## review 1 failed to run:           6s bash   cat > /tmp/rprobes/r_getitem.py <<'PY' class Box:     def __init__(self, v):         self.v = v      def __get           5s bash   date; for p in p09 p12; do echo "===== $p ====="; bash ~/tools/cmp.sh /tmp/rprobes/$p.py $PWD; done (cut off after 60 minutes) 

## review 1
[model opencode/deepseek-v4.1-flash-free]
(no final text)
[cost $0.0000, opencode tokens {}]
    tool time: 
(cut off after 60 minutes)

FINAL VERDICT: ERROR  2026-10-23T21:00:19Z
