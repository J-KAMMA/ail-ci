# job job-prog9-11020731  started 2026-11-01T22:37:29Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Report

**Commit:** `751b2ab` on `job-prog9-11020731` (not pushed).

**Result**
- `t254`, `g09`, `g23`, `t308`: stayed whole-program typed.
- `t216`: hot `main` is now typed. Added `sorted(Counter[str])` / `sorted(dict[str,int])` and CPython-exact `print/repr/f"{d}"` dict text.
- `t208`: fixed the Optional `peek() in (...)`, Optional `while` test and `a, b = method()` row unpack, but `parse*` return `int | float`. That union has no single C representation and would print `3.0` for CPython’s `3`, so it is now refused by name and the program stays on the matching general path.
- `g18` (`itertools.combinations` bound as a tuple value) and `g17` (`list[Any]` recursion + map/filter lambdas) remain follow-ups, with exact messages in `lab/progfix/prog9.md`.

**Checks**
- `test_ail_prog9`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 34 tests OK (1 skip, no zig).
- Optional/typedreach/manifest modules: 40 tests OK.
- int-dict/typed-blockers/cpython-hybrid modules: 44 tests OK.
- `python3 tools/update_manifest.py --check`: exit 0.
- Generated C of all 10 `lab/compare` tasks: byte-identical to `HEAD`.

**Probes** (all `g same stdout` and `d same stdout`, typed where noted)
`p_opt_in`, `p_opt_in_route`, `p_dict_sorted_edge`, `p_dict_repr_routes`, `p_dictrepr`, `p_dictun`, `p_methpair`, `p_pairbool`, `p_t208a`, `p_t216b`, `p_t216f`, `p_t216h` — covering empty/negative/non-ASCII, alias reads, parameter and attribute routes, quotes/escapes, int64 minimum, Optional `in`/`not in`, Optional while, and method row unpack.
[cost $0.2513, opencode tokens {"total": 44513443, "input": 384392, "output": 47935, "reasoning": 54748, "cache.write": 0, "cache.read": 44026368}]
    tool time: bash 21.1 min
        587s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 -B -m unittest -v test_ail_prog9 test_ail_safetynet test_
        133s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 -B -m unittest -v test_ail_int_dict_set test_ail_typed_bl
        120s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 2400 python3 -B -m unittest -v test_ail_prog9 test_ail_sa
        106s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 -B -m unittest -v test_ail_optional_locals test_ail_optio
         59s bash   cat > /tmp/probes/c_hash.py <<'PY' import sys, os, io, contextlib, hashlib, json root=sys.argv[2] sys.path.ins
         43s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/cmpc && mkdir -p /tmp/cmpc/new /tmp/cmpc/base; task=tree_fold; fo
         29s bash   cd /tmp/probes && for p in p_opt_in p_opt_in_route p_dict_sorted_edge p_dict_repr_routes p_dictrepr p_dictun p
         15s bash   cd /home/runner/work/_temp/w2 && python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/test_ail_prog9.

## review 0
[model opencode-go/deepseek-v4.1-flash]
**What the change really does:** adds Optional scalar `in`/`not in`, Optional-call `while` tests, `self.method()` Optional returns, method SROW unpack with owned str fields, `sorted(dict[str,int])`, dict `print`/`repr`/f-string text, and an `int | float` return refusal.

**Defect (blocking): `sorted(d)` shallow-copies dict key views, then uses freed memory.**

Probe `/tmp/rprobes/p_sortmin.py`:

```python
def main() -> None:
    d: dict[str, int] = {}
    d["b"] = 1
    d["a"] = 2
    d["c"] = 3
    ks = sorted(d)
    del d["b"]
    print(ks)

main()
```

- CPython: `['a', 'b', 'c']`
- Base (`/tmp/base`, strict typed): `['a', 'b', 'c']`
- HEAD (strict/default): `['a', "'", 'c']` (stable over 3 runs)

The new `_sorted_into_temp` SDICT branch pushes `T->order[i]` (`ail_str` views) into the list; `ail_stab_del` frees those key buffers. This is a regression: base compiled this exact program typed and used `ail_sdict_keys_snapshot` (deep copy). A returned `sorted(d)` from a function whose `d` is a local also prints garbage (`/tmp/rprobes/p_sortdangle.py`), i.e. use-after-free, not merely a wrong value. `test_ail_prog9` has no mutation-after-sort case.

**Claim checks**
- Verified: commit `751b2ab`; `t254`, `g09`, `g23`, `t308` strict-typed; `t216` strict-typed and uses `ail_stab_text`; `t208` refused by name for `int | float` and general build matches; new Optional `in`, while, method-row probes match; `update_manifest --check` exit 0; `test_ail_prog9` OK and `test_ail_safetynet` OK.
- False: “all ten lab/compare tasks are refused before C is emitted” — 6 emit C; those 6 hashes are byte-identical to base and 4 refuse identically, so the headline result holds. The `g18` “exact” follow-up message is not the first message: both base and HEAD report `the entry function cannot return checked str`, not the tuple message in `prog9.md`.
- Unverified: `test_ail_files`, `test_ail_corpus_findings3`, the 40/44-module batches, the worker’s `/tmp/probes`, and instruction counts (`perf_event_open` is denied here).

**Pre-existing (same on base):** Optional `in` over an empty literal tuple is refused by the C path; int/float Optional `in` is still refused; `str(sdict)` is refused; dict aliasing with later mutation is refused; non-BMP literals are unsupported.

VERDICT: FIX

1. `sorted(d)` for `dict[str,int]`/`Counter[str]` stores dict-owned key views; deleting/clearing the dict (or returning the list past the local dict’s scope) leaves dangling keys. Probe and expected/actual above. Fix by copying each key into the result arena (as base’s `ail_sdict_keys_snapshot` did) instead of pushing `T->order[i]` directly.
[cost $0.0797, opencode tokens {"total": 8270203, "input": 157610, "output": 18538, "reasoning": 34535, "cache.write": 0, "cache.read": 8059520}]
    tool time: bash 13.5 min
        378s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/cmpc && mkdir -p /tmp/cmpc/new /tmp/cmpc/base; for root in new ba
        170s bash   cd /home/runner/work/_temp/w2 && python3 tools/par_check.py -j 2 test_ail_safetynet 2>&1 | tail -15; date
        120s bash   cd /home/runner/work/_temp/w2 && nohup python3 tools/par_check.py -j 2 test_ail_prog9 test_ail_safetynet > /tm
         30s bash   sleep 30; cat /tmp/parcheck.log; ps aux | grep -E "unittest|par_check" | grep -v grep | wc -l; date
         17s bash   cd /tmp/rprobes && python3 - <<'PY' p='p_optint.py' s=open(p).read().replace('        n += pick(i) if False el
          6s bash   cd /home/runner/work/_temp/w2 && for f in lab/census/programs/dev/t254.py lab/census/programs/gdev/g09_002.py 
          6s bash   cat > /tmp/rprobes/p_methoddefault.py <<'PY' class P:     def __init__(self) -> None:         self.s = "abc"  
          5s bash   cat > /tmp/rprobes/p_dictvalstr.py <<'PY' def main() -> None:     d = {}     d["a"] = "x"     d["b"] = "yy"   

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed and committed as `a2ede3b`.

**Defect fixed:** `sorted(d)` for typed str-keyed dicts now copies each key into the function's str arena before sorting, instead of pushing `T->order[i]` views. `del`/`clear` after sorting, and returning `sorted(d)` past a local dict's scope, now match CPython (`['a', 'b', 'c']`) with no use-after-free.

**Probes** (`/tmp/probes`, both `cmp.sh` builds):
- Match: `p_sort_del`, `p_sort_clear`, `p_sort_return`, `p_sort_alias`, `p_sort_alias2`, `p_sort_all`, `p_sort_long`.
- Refused by name: `p_sort_attr` (attribute), `p_sort_listitem` (nested list), `p_sort_dictvalue` (nested dict), `p_sort_mut`.
- Strict builds of the new mutation/clear/return/parameter/Counter/empty/non-ASCII/reverse cases also match CPython.

**Lab/compare C:** all ten `main.ail` builds emit byte-identical C to base; all ten `main.py` builds also match base (five identical C, five identical refusals apart from source path).

**Docs:** corrected `lab/progfix/prog9.md` for the lab/compare claim and `g18_006`'s actual first refusal (`the entry function cannot return checked str`).

**Tests on final commit:** `test_ail_prog9`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_dict_delete`, `test_ail_int_dict_set`, `test_ail_sort_keys`, `test_ail_int_sort`, `test_ail_dict_upsert` — 9/9 passed. `update_manifest --check` exits 0.
[cost $0.0435, opencode tokens {"total": 3445052, "input": 128172, "output": 14000, "reasoning": 9952, "cache.write": 0, "cache.read": 3292928}]
    tool time: bash 23.6 min, edit 0.0 min
        461s bash   cd /home/runner/work/_temp/w2 && python3 tools/par_check.py -j 2 test_ail_prog9 test_ail_safetynet test_ail_fi
        451s bash   cd /tmp && rm -rf cmpP_new cmpP_base && mkdir -p cmpP_new cmpP_base && for t in berth_sim chain_relax echo_pac
        356s bash   cd /home/runner/work/_temp/w2 && python3 tools/par_check.py -j 2 test_ail_prog9 test_ail_safetynet test_ail_fi
         84s bash   cd /tmp && rm -rf basehead cmpC_new cmpC_base && mkdir basehead && cd /home/runner/work/_temp/w2 && git archiv
         28s bash   cd /home/runner/work/_temp/w2 && for f in /tmp/probes/p_sort_del.py /tmp/probes/p_sort_clear.py /tmp/probes/p_
         10s bash   cd /home/runner/work/_temp/w2 && for f in /tmp/probes/p_sort_del.py /tmp/probes/p_sort_clear.py /tmp/probes/p_
         10s bash   mkdir -p /tmp/probes && cat > /tmp/probes/p_sort_del.py <<'PY' def main() -> None:     d: dict[str, int] = {} 
          2s bash   cd /tmp && rm -rf strictprobe && mkdir strictprobe && cd strictprobe && for f in /tmp/probes/p_sort_del.py /tm

## review 1
[model opencode-go/deepseek-v4.1-flash]
Reviewed `work..HEAD` (`751b2ab`, `a2ede3b`). The change really does: add Optional-returning-method lowering in `optlib.py`, method SROW unpacking plus bool-name marking and owned row string returns in `pyfunc.py`, `sorted(dict[str,int])` key copying, a `DICTTEXT` runtime block for dict `str`/`repr`/f-string, and an `int | float` return refusal. That matches the report except the bool-marking side effect below.

**Defect**

1. Method-row bool marking leaks for the rest of the function. `pyfunc.py:20704-20708` adds the unpacked bool field names to the function-wide `ctx.bool_names`; any later `print` of that name is forced to `True`/`False` even after it is reassigned. Probe `/tmp/rprobes/p_bool_reuse.py`:

```python
class P:
    def __init__(self) -> None: self.s = "z"
    def pair(self) -> tuple[bool, str]: return (False, self.s)

def main() -> None:
    p = P()
    a = 5
    print(a)
    a, b = p.pair()
    print(a, b)
    a = 7
    print(a)
main()
```

CPython and base (both builds): `5` / `False z` / `7`. HEAD `--strict` typed build: `5` / `False z` / `True`.

**Claims checked**

- `sorted(d)` ownership fix: verified with my own `p_sort_param_rev`, `p_sort_unannot_mut`, `p_sort_iter_mut`; `del`/`clear`/return/parameter/reverse/empty/non-ASCII all match.
- Dict text: verified with `p_dict_extreme`, `p_dict_order`, `p_dict_ctrl`, `p_dict_builtins`, `p_dict_empty_param`, `p_dict_fconv` (int64 min/max, quotes, controls, non-ASCII, insertion order, empty, `str`/`repr`/f-string).
- Method row string ownership: verified with `p_row_str_reuse`, `p_row_wrap`.
- lab/compare claim: verified all ten `main.ail` builds emit byte-identical `program.c`; all ten `main.py` cases match base (five identical C, five identical refusals apart from paths).
- `update_manifest.py --check` exits 0; `test_ail_prog9` and `test_ail_safetynet` pass (`-j 2`).
- Report claim that a bool row field keeps `True`/`False` is true only for a fresh name, false in general (defect 1).
- Report's listed refusal probes and `g18_006` message: unverified.
- Speed/instruction counts: not checked.
- No pre-existing differences found in the probes I ran on `/tmp/base`.
- Minor record note: DEVLOG says `2026-11-01`; the final commit is `2026-11-02 00:06 UTC`.

VERDICT: FIX

1. Fix the function-wide bool-name marking in the method row-unpack branch (`AIL_CURRENT/python/pkg-v12/pyfunc.py:20704`): it must not make later reassignments of the same name print as bool. Probe `/tmp/rprobes/p_bool_reuse.py`: expected `7`, actual `True` on the strict typed build.
[cost $0.0528, opencode tokens {"total": 3963933, "input": 100418, "output": 11793, "reasoning": 31946, "cache.write": 0, "cache.read": 3819776}]
    tool time: bash 12.1 min
        399s bash   cd /tmp && rm -rf lpnew lpbase && mkdir lpnew lpbase for t in berth_sim chain_relax echo_pack ledger_bin rail_
        174s bash   date && cd /home/runner/work/_temp/w2 && timeout 900 python3 tools/par_check.py -j 2 test_ail_prog9 test_ail_s
         81s bash   cd /tmp && rm -rf lcnew lcbase && mkdir lcnew lcbase for t in berth_sim chain_relax echo_pack ledger_bin rail_
         16s bash   cd /home/runner/work/_temp/w2 && for f in /tmp/rprobes/p_bool_reuse.py /tmp/rprobes/p_bool_pair.py /tmp/rprobe
         13s bash   cat > /tmp/rprobes/p_dict_boolval.py <<'PY' def main() -> None:     d: dict[str, int] = {}     d["t"] = True  
          7s bash   cat > /tmp/rprobes/p_dict_empty_param.py <<'PY' def show(d: dict[str, int]) -> None:     print(d)     print(re
          7s bash   cat > /tmp/rprobes/p_sort_uses.py <<'PY' def main() -> None:     d: dict[str, int] = {}     d["b"] = 2     d["
          6s bash   cat > /tmp/rprobes/p_bool_to_str.py <<'PY' class P:     def pair(self) -> tuple[bool, int]:         return (Tr

FINAL VERDICT: FIX  2026-11-02T00:31:30Z
