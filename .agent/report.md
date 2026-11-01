# job job-std_copy-11011617  started 2026-11-01T07:19:52Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done.

- **Programs:** 12/12 in `lab/stdlib/copy/` build (all general path, 0 refused); stdout and exit code match CPython on the default and forced-general builds. Results in `lab/stdlib/copy/RESULTS.md`.
- **Probes:** 9 files `/tmp/probes/copy_*.py` (types, containers, mutation, cycles, memo, caught errors, instances, dict keys/sets, empty). All match CPython on both builds.
- **Compare C:** all 10 `lab/compare` `main.ail` builds are byte-identical to base; `main.py` where it builds is identical, and the three that do not build refuse identically on base.
- **Tests:** `test_ail_std_copy`, `test_ail_genlib`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5 modules, 0 failed (547s).
- **Manifest:** `update_manifest.py --check` rc 0.
- **Commit:** `68be291`

Follow-ups (typed-path `copy`, user `__copy__`/`__deepcopy__`/`__reduce__` protocol) are recorded in `RESULTS.md`.
[cost $0.0444, opencode tokens {"total": 3939383, "input": 112769, "output": 12775, "reasoning": 14031, "cache.write": 0, "cache.read": 3799808}]
    tool time: bash 38.1 min, write 0.0 min, edit 0.0 min
        793s bash   set -e rm -rf /tmp/ccmp && mkdir -p /tmp/ccmp fail=0 for t in $(ls lab/compare/src); do   for mode in d g; do 
        594s bash   set -e rm -rf /tmp/ccmp2 && mkdir -p /tmp/ccmp2 fail=0 for t in $(ls lab/compare/src); do   for lang in ail py
        549s bash   cd AIL_CURRENT && timeout 3600 python3 ../tools/par_check.py -j 2 test_ail_std_copy test_ail_genlib test_ail_s
         84s bash   cd AIL_CURRENT && AIL_NO_CACHE=1 timeout 1800 python3 test_ail_std_copy.py 2>&1 | tail -40
         83s bash   for f in /tmp/probes/copy_*.py; do echo "######## $(basename $f)"; bash ~/tools/cmp.sh "$f" "$PWD" 2>&1 | grep
         58s bash   for f in /tmp/probes/copy_*.py; do echo "######## $f"; bash ~/tools/cmp.sh "$f" "$PWD" 2>&1 | tail -12; done
         38s bash   python3 - <<'PY' from pathlib import Path p=Path('/tmp/probes/copy_empty.py') s=p.read_text() s=s.replace('   
         30s bash   cd lab/stdlib/copy && for f in p*.py; do echo "=== $f"; AIL_NO_CACHE=1 python3 ../../../AIL_CURRENT/ail_chatgp

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review

**What the change really does:** Adds `copy.copy` / `copy.deepcopy` names to the general-path library table (`genlib.py`), implements a boxed shallow/deep copier with memo + keep-alive (`safetyrt.py`), and adds signature wrappers (`prelude_genlib.py`). It also changes `_bound_names` so class-body `def` names are no longer treated as module bindings.

**Worker claims**
- 12/12 `lab/stdlib/copy` build and match CPython on both builds — **verified** (`test_ail_std_copy`, 121s).
- `test_ail_std_copy`, `test_ail_safetynet` pass — **verified** (197s, 0 failed). `test_ail_genlib`, `test_ail_files`, `test_ail_corpus_findings3` — **unverified** (not re-run, per reviewer rules).
- 10 `lab/compare` `main.ail` / `main.py` C unchanged — **verified** (`--debug-dir` C identical to `/tmp/base` where both build; identical refusals otherwise).
- 9 `/tmp/probes/copy_*.py` all match — **unverified** (not re-run; files present).
- Manifest `--check` rc 0 — **verified**.
- Commit `68be291` — **verified**.
- Protocol (`__copy__`/`__deepcopy__`/`__reduce__`) recorded as follow-up — **verified**, but it is silently ignored rather than refused (defect 2).

**My probes** (all in `/tmp/rprobes`, `bash ~/tools/cmp.sh <p> $PWD`, both `g` and `d`):
- Match: `r4_memo_err.py` (memo error texts), `r5_containers.py` (deque, bytearray, bytes, frozenset), `r12_dictops.py`, `r15_tuplekey_paths.py`, `r17_shallow_mutate.py` (dict copy through arg/list/attr/value; shallow mutation).
- Mismatch: `r7_protocol2.py`, `r8_generator2.py`, `r9_alias2.py` / `shallow_tuplekey.py` below. Base (`/tmp/base`) refuses all three at compile time (`copy.copy` not published), so these are introduced by the change.

**Pre-existing:** generic `iter()` on a compiler-specialized tuple-key dict (`_AilD_*` class) fails identically on base and HEAD (same C, same `TypeError`), even without copy. The copy cases inherit that.

**Unverified:** speed/icount (copy is not on a hot path, so not applicable); wider suite and the three non-target tests above.

VERDICT: FIX

1. `copy.copy` / `copy.deepcopy` return a generator instead of raising `TypeError`.
```python
import copy
def gen():
    yield 1
def main():
    g = gen()
    try:
        copy.copy(g); print("copy ok")
    except Exception as exc: print("copy", type(exc).__name__, exc)
    try:
        copy.deepcopy(g); print("deep ok")
    except Exception as exc: print("deep", type(exc).__name__, exc)
main()
```
Expected (CPython 3.12): `copy TypeError cannot pickle 'generator' object` and `deep TypeError cannot pickle 'generator' object`. Actual (both builds): `copy ok` and `deep ok`.

2. User `__copy__` / `__deepcopy__` are silently ignored, so the program prints wrong values instead of being refused.
```python
import copy
class WithCopy:
    def __init__(self): self.v = [1]
    def __copy__(self): return "copied"
    def __deepcopy__(self, memo): return "deep"
def main():
    a = WithCopy()
    print(copy.copy(a))
    print(copy.deepcopy(a))
main()
```
Expected: `copied` / `deep`. Actual (both builds): `<WithCopy object>` / `<WithCopy object>`. RESULTS.md lists this as a follow-up, but there is no named refusal, so a program reaching it silently differs.

3. `copy.copy` / `copy.deepcopy` of a dict with tuple keys returns an object that cannot be iterated.
```python
import copy
def main():
    table = {("a", 1): 10}
    other = copy.copy(table)      # deepcopy is the same
    for k in other:
        print("k", k)
main()
```
Expected: `k ('a', 1)`. Actual (both builds): `TypeError: '_AilD_Ps_iQ__i' object is not iterable`, exit 1. The same generic-iteration failure exists on base for an un-copied `_AilD_*` dict, but the copy change turns a compile-time refusal into a crash and the copier should handle or refuse these instances rather than hand back a partly usable object.
[cost $0.0729, opencode tokens {"total": 5205132, "input": 143830, "output": 11872, "reasoning": 48598, "cache.write": 0, "cache.read": 5000832}]
    tool time: bash 22.4 min
        973s bash   cd /tmp && rm -rf cmpcmp && mkdir cmpcmp && cd cmpcmp for t in $(ls /home/runner/work/_temp/w2/lab/compare/src
        199s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_
         36s bash   cd /tmp/rprobes && for f in r*.py; do echo "######## $f"; timeout 300 bash ~/tools/cmp.sh "$f" /home/runner/wo
         27s bash   cd /tmp/rprobes && for f in r7*.py r8*.py r9*.py r10*.py r11*.py; do echo "######## $f"; timeout 300 bash ~/to
         22s bash   cd /tmp/di && cat > hide.py <<'PY' def hide(x: object) -> object:     return x  def main() -> None:     table 
         16s bash   cd /tmp && rm -rf di && mkdir di && cat > di/no.py <<'PY' def main() -> None:     key = ("a", 1)     table = {
         10s bash   cd /tmp/di && cat > geniter.py <<'PY' def main() -> None:     table = {("a", 1): 10}     print(list(table))   
          8s bash   cd /tmp && rm -rf ub3 && mkdir ub3 && cat > ub3/u.py <<'PY' from json import dumps  class C:     def dumps(sel

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed all three review defects and committed as `b247b44`.

**Fixes**
1. Generator copying now raises `TypeError: cannot pickle 'generator' object`, directly and through deep-copied containers.
2. Classes defining `__copy__` / `__deepcopy__` / `__reduce__` / `__reduce_ex__` are refused by name instead of silently copied. Exact text is recorded in `lab/stdlib/copy/RESULTS.md`.
3. Copies of typed tuple-keyed dicts (`_AilD_...`) and tuple-element sets (`_AilS_...`) are rebuilt as plain `dict` / `set`, so iteration works.

**Probes** (`bash ~/tools/cmp.sh`, both builds)
- Match: `d1_gen`, `d1c` (generators direct/list/dict), `d3_tdict`, `d3d`, `d3f`, `t2b`, `t3sorted`, `p12_deep_keys`.
- Refused by name: `d2_proto`, `d2b`, `d2c` (copy protocol).
- Unchanged: `d2d` (class method defined but copy not called) matches.
- Observed pre-existing, not caused by copy: source-set iteration order (`t3src`, `t3b`) and source tuple-table `type()` names.

**Tests on final tree**
- `test_ail_std_copy`, `test_ail_genlib`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 5 modules, 0 failed (500s).
- `lab/compare`: 15/20 builds byte-identical C; remaining 5 have identical refusal codes on current and base.
- `update_manifest.py --check`: rc 0.
[cost $0.0543, opencode tokens {"total": 5575797, "input": 118196, "output": 13962, "reasoning": 19895, "cache.write": 0, "cache.read": 5423744}]
    tool time: bash 34.7 min, edit 0.0 min
        559s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_
        501s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_
        358s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/base_compare /tmp/cmpwork && mkdir -p /tmp/base_compare /tmp/cmpw
        343s bash   cat > /tmp/cmpwork/one.sh <<'SH' #!/bin/bash task=$1; ext=$2 cur=/home/runner/work/_temp/w2; base=/tmp/base_co
         71s bash   cd /tmp/probes && cat > t2b.py <<'PY' import copy def main():     table = {("a", 1): [10]}     other = copy.co
         58s bash   cd /tmp/probes && for f in d1_gen.py d1c.py d2_proto.py d3_tdict.py d3d.py d3f.py t2b.py t3sorted.py p12_deep_
         52s bash   cd /tmp/probes && for f in d1_gen.py d3_tdict.py d3d.py d3e.py t2_tdict_list.py t3_tset.py p12_deep_keys.py; d
         22s bash   cat > /tmp/probes/t1_tdict_int.py <<'PY' import copy def main():     table = {("a", 1): 10}     print(type(tab

## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change really does.** Adds `copy.copy`/`copy.deepcopy` to the general path (`genlib.py` names/keywords, `prelude_genlib.py` signatures, a new `COPY` runtime fragment with memo/keep-alive), refuses class-body `__copy__`/`__deepcopy__`/`__reduce__`/`__reduce_ex__` when copy is used, rebuilds typed `_AilD_`/`_AilS_` copies as plain `dict`/`set`, and adds 12 lab programs plus `test_ail_std_copy`.

**Claims checked**
- Generator raises `TypeError: cannot pickle 'generator' object`, direct and nested: **verified** (`rv_gen.py`, both builds).
- Class-body copy-hook methods refused by name: **verified** (`rv_proto.py`); the report's broad claim is **false** for runtime assignment (defect 2).
- `_AilD_`/`_AilS_` copies are plain `dict`/`set`: **verified** (`rv_typed.py`, `rv_paths.py`).
- 15/20 lab/compare C identical, 5 same refusals: **verified** (my `--debug-dir` builds: 15 `program.c` SAME; `scar_life/tally_lang/tree_fold` `main.py` refuse identically on base/head).
- `test_ail_std_copy` + `test_ail_safetynet`: **verified** (168s, 0 failed). The other 3 reported modules: **unverified**.
- `update_manifest.py --check`: **verified** rc 0.
- Worker's individual probe files and the "pre-existing set order / table `type()` names": **unverified** (not rerun).
- Non-copy programs: general-path C byte-identical to base (`rv_nocopy.py`).

**Other probes** (`rv_shallow`, `rv_deep`, `rv_memo`, `rv_args`, `rv_exc2`, `rv_coll`) match CPython on both builds; except the memo-size case below.

VERDICT: FIX

1. **`__getstate__`/`__setstate__` are silently ignored instead of refused or honoured.** Probe `/tmp/rprobes/rv_state.py`: a class whose `__getstate__`/`__setstate__` change the copied state. CPython and expected output `99 2 99 2`; actual on general and default builds `1 None 1 None`. These hooks are part of the copy protocol and easy to add to `_COPY_PROTOCOL`; otherwise a built program prints wrong output.

2. **Runtime-assigned copy hooks are not detected.** Probe `/tmp/rprobes/rv_dynamic.py`: `C.__copy__ = alt` then `print(copy.copy(C()))`. Expected `special`; actual `<C object>` on both builds. The class-body scan misses `Assign`/`AnnAssign` targets whose attribute is a protocol name, so the report's claim that a class defining `__copy__` is refused is false in this case.

3. **`len(memo)` after `deepcopy(frozenset)` differs.** Probe `/tmp/rprobes/rv_frozen.py`: `m={}; copy.deepcopy(frozenset({1,2}), m); print(len(m), ...)`. CPython/expected `3 False True`; actual `2 False True` on both builds. Low severity, but the documented `memo` argument is observable and this is not one of CPython's optimisations: CPython reconstructs the frozenset through a temporary list that is also memoised.

Non-blocking note: any class defining one of the four protocol names anywhere makes every copy-using program refuse (`rv_proto_unrelated.py`), even when only an unrelated container is copied. That is a named refusal (allowed), but it narrows coverage more than necessary.

No pre-existing output differences were observed in the probes I ran.
[cost $0.0424, opencode tokens {"total": 2504751, "input": 71232, "output": 11540, "reasoning": 29275, "cache.write": 0, "cache.read": 2392704}]
    tool time: bash 21.4 min
        524s bash   cd /tmp && rm -rf ccmp && mkdir -p ccmp && for d in /home/runner/work/_temp/w2/lab/compare/src/*/; do t=$(base
        445s bash   cd /tmp && rm -rf ccmp && mkdir -p ccmp && for d in /home/runner/work/_temp/w2/lab/compare/src/*/; do t=$(base
        169s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_
         39s bash   cd /tmp/rprobes && for f in rv_memo rv_args rv_gen rv_typed rv_paths rv_exc; do echo "######## $f"; timeout 30
         35s bash   cd /tmp/rprobes && for f in rv_shallow rv_deep rv_memo rv_gen rv_proto rv_proto_unrelated; do echo "######## $
         29s bash   cd /tmp/rprobes && cat > rv_memo2.py <<'PY' import copy  def main() -> None:     for v in ((1, 2), (1, "a"), f
         17s bash   cd /tmp/rprobes && cat > rv_nocopy.py <<'PY' def main() -> None:     values = [3, 1, 2]     table = {"a": valu
         10s bash   cd /tmp/rprobes && cat > rv_state.py <<'PY' import copy  class WithState:     def __init__(self):         self

FINAL VERDICT: FIX  2026-11-01T10:00:54Z
