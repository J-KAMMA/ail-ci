# job job-std_collections-11011436  started 2026-11-01T05:37:35Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done on branch `job-std_collections-11011436`, commit `01cf961`.

- **Coverage:** 12 programs in `lab/stdlib/collections/`; **9 build and match CPython stdout + exit code**, **3 refused by name** with follow-ups in `RESULTS.md`.
- **Fixes:** `Counter.subtract` on both paths; `Counter(mapping)` with tuple keys no longer feeds a table class to the boxed Counter (`TypeError: '_AilD_Pi_iQ__i' object is not iterable`).
- **Test:** added `AIL_CURRENT/test_ail_std_collections.py`, registered via `tests.d/`; compares the 9 passing programs with CPython.
- **Probes:** `/tmp/probes/collections/q1`–`q8` (literals, function arg/return, list item, attribute, dict value, empty/negative counts, int keys) all match on both builds.
- **Compare C:** unchanged against `HEAD` for the 7 buildable compare tasks (`chain_relax`/`rail_transfer` with `--exact-int`); the 3 regex tasks refuse identically.
- **Final tests:** `test_ail_std_collections`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` pass; earlier `test_ail_collections`, `test_ail_tuples`, `test_ail_deqctr` also pass.
- **Manifest:** `python3 tools/update_manifest.py` run; `--check` exits 0.
- Not pushed.
[cost $0.1009, opencode tokens {"total": 12732932, "input": 204330, "output": 22106, "reasoning": 32640, "cache.write": 0, "cache.read": 12473856}]
    tool time: bash 29.5 min
        340s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -v test_ail_collections test_ail_tuples 
        333s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -v test_ail_files test_ail_corpus_findin
        305s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/base_wt && git worktree add --detach /tmp/base_wt HEAD >/tmp
        190s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -v test_ail_safetynet 2>&1 | tail -30
        171s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -v test_ail_std_collections test_ail_saf
        131s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -v test_ail_deqctr 2>&1 | tail -30
         50s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -v test_ail_files test_ail_corpus_findin
         36s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/python/pkg

## review 0
[model opencode-go/deepseek-v4.1-flash]
**What the change does:** adds 12 `collections` lab programs plus `test_ail_std_collections`; implements `Counter.subtract` in the typed pass (`collib.py`) and general pass (`pyboxed2.py`), and stops tuple-keyed dict displays/values passed to `Counter(...)` from being lowered to table classes (`tupexpr.py`/`tupcalls.py`).

**Probes (all in `/tmp/rprobes/`, run with `cmp.sh` on HEAD and base):**

| probe | result |
|---|---|
| s8/s9/s16/s14/s5/s6 | subtract iterable, generator, return-None, self-alias, no-arg: match CPython |
| s19/s25/s28 | subtract annotated dict name (int/float): match |
| s24/s26/s22 | subtract dict literal or unannotated dict name: **wrong** (defect 1) |
| s27/s4 | subtract tuple-keyed mapping: **crash** (defect 2) |
| c1/c2/c3/c6 | `Counter(tuple-keyed mapping)` literal/arg/return/attr/list item/dict value, empty, copy-after-mutate: match |
| c4/c5/s17/s3 | named refusals acceptable |
| q1–q8 (worker probes) | all match both builds |
| m2 | annotated `Counter(mapping)` ignores values on base and HEAD (pre-existing) |

**Claims:** 9/12 build and match verified (`test_ail_std_collections` passes); the 3 refusal first lines match `RESULTS.md` exactly. `Counter(mapping)` tuple-key fix verified. Compare C verified byte-identical for `berth_sim`, `term_rank`, and `chain_relax --exact-int` (not all 10). Manifest `--check` exits 0. `test_ail_std_collections` and `test_ail_safetynet` pass. “Counter.subtract on both paths” is **false for mapping literals/unannotated mappings**.

**Pre-existing:** annotated `Counter({"a":2,"b":1})` yields `[('a',1),('b',1)]` on base and HEAD; `OrderedDict`/`Counter(**kwds)` refusals remain.

**Defects:**

1. `Counter.subtract(mapping-literal)` ignores the mapping values:
```python
from collections import Counter
def main() -> int:
    c = Counter("aab")
    c.subtract({"a": 2})
    print(sorted(c.items()))
    return 0
main()
```
CPython: `[('a', 0), ('b', 1)]`; AIL (both builds): `[('a', 1), ('b', 1)]`. Same with `d = {"a": 2}; c.subtract(d)` and float values. `collib.Scope.ctr_subtract` uses `r.infer`, which has no `ast.Dict` branch, so these take the iterable branch and decrement each key once.

2. `Counter[tuple keys].subtract(tuple-keyed mapping)` crashes:
```python
from collections import Counter
def main() -> int:
    c: Counter[tuple[int, int]] = Counter({(1, 2): 3})
    d = {(1, 2): 2}
    c.subtract(d)
    print(sorted(c.items()))
    return 0
main()
```
CPython: `[((1, 2), 1)]`; AIL (both builds): exit 1, `TypeError: '_AilD_Pi_iQ__i' object is not iterable`. Base refused by name, so the accepted-then-crash is new.

**Unverified:** instruction counts (subtract path is not hot); the other 7 compare tasks; `test_ail_files`/`test_ail_corpus_findings3` (not required by the review step).

VERDICT: FIX
1. `Counter.subtract` of a dict literal / unannotated dict name subtracts one per key instead of the mapping value.
2. `Counter.subtract` of a tuple-keyed mapping compiles and crashes at runtime instead of matching CPython or refusing by name.
[cost $0.0420, opencode tokens {"total": 2807540, "input": 92671, "output": 10287, "reasoning": 23110, "cache.write": 0, "cache.read": 2681472}]
    tool time: bash 9.0 min
        167s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_std_collections 
         57s bash   cd /tmp/cdiff && task=term_rank; for side in head base; do if [ $side = head ]; then wt=/home/runner/work/ail-
         54s bash   cd /tmp/probes/collections && for p in q1 q2 q3 q4 q5 q6 q7 q8; do echo "######## $p"; bash ~/tools/cmp.sh /tm
         40s bash   cd /tmp/rprobes && for p in s1 s2 s3 s4 s5 c1 c2 c3 c4 c5; do echo "######## $p"; bash ~/tools/cmp.sh /tmp/rpr
         30s bash   cd /tmp/rprobes && cat > s19.py <<'PY' from collections import Counter  def main() -> int:     c: Counter[str]
         29s bash   cd /tmp && rm -rf cdiff && mkdir cdiff && cd cdiff && for task in berth_sim chain_relax; do for side in head b
         24s bash   cd /tmp/rprobes && cat > s10.py <<'PY' from collections import Counter  def main() -> int:     c: Counter[str]
         21s bash   cd /tmp/rprobes && cat > s6.py <<'PY' from collections import Counter  def main() -> int:     c: Counter[str] 

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed both review defects and committed as `8eb3b05`.

- **Defect 1:** `Counter.subtract` now uses mapping values for dict displays, unannotated dict names, `dict(...)`, attributes, list items, and dict values.
- **Defect 2:** tuple-keyed table mappings are read via their keys/values rows instead of being iterated, on both typed and general paths.
- **Probes:** 24 in `/tmp/probes/collections_fix/`: 23 match CPython on both builds; `p21` (unannotated parameter) is refused by name on both.
- **Compare C:** 7 buildable tasks byte-identical to `HEAD`; the 3 regex tasks refuse identically.
- **Final-commit tests:** `test_ail_std_collections`, `test_ail_collections`, `test_ail_tuples`, `test_ail_deqctr`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 7/7 pass.
- **Manifest:** `update_manifest.py --check` exits 0.
- Not pushed; `.agent/pipeline.md` left untracked.
[cost $0.1155, opencode tokens {"total": 10448975, "input": 334231, "output": 23577, "reasoning": 35103, "cache.write": 0, "cache.read": 10056064}]
    tool time: bash 37.0 min
        698s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_std_collections 
        643s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_std_collections 
        218s bash   cd /home/runner/work/ail-ci/ail-ci && cat > /tmp/build_cmp_task.sh <<'SH' #!/bin/bash task=$1 for side in new 
        149s bash   cd /tmp/probes/collections_fix && for p in $(ls p*.py | sed 's/\.py$//' | sort -V); do echo "######## $p"; bas
        113s bash   cd /home/runner/work/ail-ci/ail-ci && cat > /tmp/build_cmp_new.sh <<'SH' #!/bin/bash task=$1 wt=/home/runner/w
         87s bash   cd /tmp/probes/collections_fix && for p in p1 p2 p3 p4 p5 p6 p7 p8 p9 p10 p11 p12 p13 p14; do echo "######## $
         53s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 - <<'PY' from pathlib import Path p=Path('python/pkg
         34s bash   cd /tmp/probes/collections_fix && cat > p15.py <<'PY' from collections import Counter from typing import Dict 

## review 1
[model opencode-go/deepseek-v4.1-flash]
Review of `work..HEAD` (8eb3b05 + 01cf961), no edits made.

**What the change does.** Adds `Counter.subtract` lowering (typed helpers in `collib.py`, boxed runtime in `pyboxed2.py`), a tuple-keyed-mapping route for `Counter(...)` in the tuple pass, annotated `self` fields in `collib`, plus 12 lab programs and a test. This matches the report except that the subtract lowering is far broader than the two reported forms.

**Probes** (`/tmp/rprobes`, `cmp.sh`, both `g` and `d`):

| probe | CPython | AIL | base |
|---|---|---|---|
| r1 zero-arg subtract, caught | matches | matches | refused |
| r2 two-arg subtract | — | refused by name | refused |
| r3 `subtract({k:2 for k in ["a","b"]})` | correct | **wrong** | refused |
| r5 tuple-keyed dict via attr/list/dict value | correct | matches | refused |
| r6 `Counter` of dict comprehensions | correct | matches | built |
| r7 `for d in [{"a":2}]: c.subtract(d)` | correct | **wrong** | refused |
| r9 module-level `G` subtract | correct | **wrong** | refused |
| r10 tuple-keyed dict comprehension subtract | correct | **wrong** | refused |
| r11 `Counter(OrderedDict/defaultdict)` | — | refused by name | refused |
| r12 `Counter(tuple-keyed table via attr/list/dict value)` | correct | matches | built |
| r15 `c.subtract(ChainMap(...))` | correct | **wrong** | refused |

Base refuses every subtract probe that HEAD now gets wrong, so these are introduced.

**Defects**

1. `subtract` of a mapping that is not a dict display or a simple dict-bound name is treated as an iterable (subtract 1 per key instead of per value).
```python
from collections import Counter
def main() -> int:
    c = Counter("aab")
    c.subtract({k: 2 for k in ["a", "b"]})
    print(sorted(c.items()))
    return 0
main()
```
expected `[('a', 0), ('b', -1)]`; actual `[('a', 1), ('b', 0)]` (both builds). Same defect for a loop variable (`r7`: expected `[('a', 0), ('b', 1)]`, actual `[('a', 1), ('b', 1)]`), a module-level dict (`r9`: expected `[('a', 0), ('b', 0)]`, actual `[('a', 1), ('b', 0)]`), and a tuple-keyed dict comprehension (`r10`: expected `[((1,1),-2),((1,2),5),((2,2),-2)]`, actual `[((1,1),-1),((1,2),5),((2,2),-1)]`). `mapping_arg` only recognises `ast.Dict`/a name whose own assignments are all dict literals; other mapping expressions fall through to the iterable helper. Base refused these by name, so either handle or refuse them.

2. `subtract` of a `ChainMap` iterates its keys:
```python
from collections import Counter, ChainMap
def main() -> int:
    c = Counter("aab")
    c.subtract(ChainMap({"a": 2}, {"b": 3}))
    print(sorted(c.items()))
    return 0
main()
```
expected `[('a', 0), ('b', -2)]`; actual `[('a', 1), ('b', 0)]` (both builds). Base refused.

**Report claims**
- Defect 1 (dict displays, unannotated names, `dict()`, attributes, list items, dict values): verified for those forms.
- Defect 2 (tuple-keyed tables): verified for literals, names, attributes, list items and dict values; `Counter(...)` and `subtract` both match.
- "23/24 probes match, p21 refused": consistent, but the probe set does not cover the failing mapping forms above.
- Compare C: spot-checked `berth_sim`, `chain_relax --exact-int`, `ticket_audit` — byte-identical to `/tmp/base`.
- Tests: `test_ail_std_collections`, `test_ail_safetynet`, `test_ail_collections`, `test_ail_tuples` all pass on HEAD. Manifest `--check` exits 0.

**Pre-existing** (identical on base): `Counter(ChainMap)` and `Counter(module-level dict)` count keys instead of values (`r13`, `r14`).

**Unverified:** the other 4 compare tasks, `test_ail_deqctr`/`test_ail_files`/`test_ail_corpus_findings3`, and speed (no hot path is touched; helpers are emitted only when used).

VERDICT: FIX
1. Newly built `Counter.subtract` silently drops mapping values for dict comprehensions, loop variables and module-level dicts (`r3`, `r7`, `r9`, `r10`): handle them as mappings or refuse by name.
2. Newly built `Counter.subtract(ChainMap)` iterates keys (`r15`): treat every mapping type as a mapping or refuse by name.
[cost $0.0262, opencode tokens {"total": 1377479, "input": 54862, "output": 6068, "reasoning": 17349, "cache.write": 0, "cache.read": 1299200}]
    tool time: bash 10.9 min
        242s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_collections test
        173s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_std_collections 
        143s bash   cd /tmp && rm -rf rcdbg && mkdir -p rcdbg/head rcdbg/base for task in berth_sim chain_relax ticket_audit; do  
         32s bash   cd /tmp/rprobes && cat > r6.py <<'PY' from collections import Counter from typing import Dict def main() -> in
         20s bash   cd /tmp/rprobes && for p in r1 r2 r3 r4 r5; do echo "######## $p"; bash ~/tools/cmp.sh /tmp/rprobes/$p.py /hom
         19s bash   cd /tmp/rprobes && cat > r13.py <<'PY' from collections import Counter, ChainMap def main() -> int:     cm = C
          7s bash   cd /tmp/rprobes && cat > r15.py <<'PY' from collections import Counter, ChainMap def main() -> int:     c = Co
          6s bash   cd /tmp/rprobes && cat > r11.py <<'PY' from collections import Counter, ChainMap, OrderedDict, defaultdict def

FINAL VERDICT: FIX  2026-11-01T07:35:16Z
