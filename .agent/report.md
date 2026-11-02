# job job-prog29-11021624  started 2026-11-02T07:32:27Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Committed `7668cf4` on `job-prog29-11021624`.

- Profiled all 8 programs; recorded hot-function table and follow-ups in `lab/progfix/prog29.md`.
- Moved `g17_026` fully typed (4/4 project functions) by fixing:
  - module-level `frozenset` of str literals as an ordered constant (reads limited to `in`/`not in`/`len`, otherwise refused by name)
  - `len({...})` set comprehensions via the eager list comprehension plus a private set table
- `t161`, `g08_004`, `t188` were already typed; `g17_010`, `t475`, `g16_006`, `g14_020` keep named follow-ups.
- Added `AIL_CURRENT/test_ail_prog29.py`, registered via `tests.d/test_ail_prog29.txt`.
- Probes: 5/6 match CPython on both `cmp.sh` builds; `frozenset_iter` is refused by name under `--strict` (non-strict general path uses the pre-existing documented A2 insertion order, same as base).
- `lab/compare`: generated C byte-identical on 10/10 tasks versus base.
- Tests: new module 7/7 on final commit; required `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` plus targeted modules passed (35 tests, 1 windows-only skip; 84 targeted tests passed). Manifest `--check` clean.
[cost $0.0372, opencode tokens {"total": 3354632, "input": 104350, "output": 8876, "reasoning": 10814, "cache.write": 0, "cache.read": 3230592}]
    tool time: bash 17.3 min, edit 0.0 min
        524s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 -m unittest -v test_ail_python_syntax test_ail_safetynet 
        339s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && (python3 -m unittest -v test_ail_prog29 test_ail_modconst test_ai
         83s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/cmpc && mkdir -p /tmp/cmpc/current /tmp/cmpc/base && for task in 
         30s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 -m unittest test_ail_prog29 2>&1 | tail -5 && cd .. && py
         29s bash   cd /home/runner/work/_temp/w2 && which gcc python3 && python3 --version && cd AIL_CURRENT && python3 -m unitte
         16s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/probes/prog29_setcomp_len.py /tmp/probes/prog29_setcomp_routes.
          7s bash   cd /home/runner/work/_temp/w2 && for f in lab/census/programs/gdev/g17_010.py lab/corpus/programs/deepseek-v4.
          3s bash   cd /home/runner/work/_temp/w2 && for f in lab/census/programs/gdev/g17_010.py lab/census/programs/gdev/g14_020

## review 0
[model opencode-go/deepseek-v4.1-flash]
**What the change really does.** Adds module-level `frozenset(<str literal>)` / `frozenset([str...])` as an ordered, de-duplicated `list[str]` constant (reads restricted to `in`/`not in`/`len`), lowers `len({...})` to an eager list comprehension plus a private int/str set, and touches `pyc._rewrite_script`. The added `AnnAssign` path there is dead (`_count_assign_targets` never counts `AnnAssign`); annotated forms work only because `python_surface` strips the annotation to a plain `Assign`.

**Verified**
- `g17_026` builds strictly typed on HEAD (C has `v_VOWELS`, `ail_slist_has`, `ail_sset_add`); base strict refuses the set comprehension.
- `lab/compare`: 10/10 `program.c` byte-identical to base.
- `test_ail_prog29` 7/7, `test_ail_safetynet` 5/5, `update_manifest.py --check` clean.
- Set-comp probes (routes, unicode, NUL, tuple/bool/str/bytes elements, empty/negative/range, nested/multiple/loop, caught exceptions) match CPython or refuse by name.
- `frozenset` iteration on both builds is the pre-existing A2 insertion order (same output on base).

**Defects**

1. Local shadowing of `len` bypasses the frozenset read guard and exposes the list lowering. Probe `/tmp/rprobes/z_shadowlen.py`:
```python
V = frozenset("aeiou")

def f() -> str:
    def len(x: list[str]) -> str:
        return x[0]
    return len(V)

print(f())
```
Expected (CPython and base default build): no stdout, exit 1, `TypeError: 'frozenset' object is not subscriptable`. Actual HEAD default and `--strict` typed build: prints `a`, exit 0. Cause: `_frozenset_reads_ordered` accepts any call spelled `len(V)` without checking that `len` is the builtin, so `V` is passed to user code as `list[str]`.

2. Read before assignment is silently allowed. Probe `/tmp/rprobes/r_order.py`:
```python
def f() -> bool:
    return "a" in V

print(f())
V = frozenset("aeiou")
```
Expected (CPython and base default build): no stdout, exit 1, `NameError: name 'V' is not defined`. Actual HEAD default typed build: prints `True`, exit 0. Cause: the frozenset is hoisted to module scope and exists before its source assignment. (The same hoisting already exists for int/str module constants on base, but this frozenset probe is correct on base and wrong on HEAD.)

**Claims**
- Verified: commit `7668cf4`; g17_026 newly typed; 10/10 compare C; probes/tests above.
- False: “`pyc._rewrite_script` keeps that assignment at module scope” for the annotated `AnnAssign` form — that branch cannot fire; the annotated case only works via the surface’s annotation stripping.
- Unverified: profiler table numbers; “t161/g08_004/t188 already typed”; follow-up messages for t475/g16_006/g14_020/g17_010; `test_ail_files`/`test_ail_corpus_findings3` and the 35/84 counts; speed/instruction counts.

**Pre-existing**
- `frozenset` iteration order differs from CPython on both HEAD and base (documented A2 insertion order); not caused by this change.

VERDICT: FIX
1. `_frozenset_reads_ordered` must not treat a shadowed/local `len` as the builtin; `z_shadowlen.py` prints `a`/exit 0 where CPython and base raise `TypeError`/exit 1.
2. A module `frozenset` read that can run before its assignment must be refused (or ordered correctly); `r_order.py` prints `True`/exit 0 where CPython and base raise `NameError`/exit 1.
[cost $0.1107, opencode tokens {"total": 8104292, "input": 311550, "output": 18984, "reasoning": 49086, "cache.write": 0, "cache.read": 7724672}]
    tool time: bash 9.0 min
        202s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1200 python3 -m unittest test_ail_safetynet 2>&1 | tail -
        115s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/cmpc && mkdir -p /tmp/cmpc/cur /tmp/cmpc/base; ok=0; bad=0; for t
         57s bash   cd /home/runner/work/_temp/w2 && for p in p_multi p_types p_float p_froz_int p_froz_chained p_froz_emptylist p
         44s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 900 python3 -m unittest -v test_ail_prog29 2>&1 | tail -2
         13s bash   cd /home/runner/work/_temp/w2 && for p in r_lambda r_nested r_while r_chained1 r_chained2 r_nul; do echo "====
         10s bash   cd /tmp/rprobes && cat > s_frozsetitem.py <<'EOF' V = frozenset("aeiou")  def main() -> None:     print(frozen
          9s bash   cd /tmp/rprobes && cat > u_del.py <<'EOF' V = frozenset("aeiou")  def f() -> None:     global V     del V  f()
          8s bash   cd /tmp/rprobes && cat > z_shadowlen.py <<'EOF' V = frozenset("aeiou")   def f() -> str:     def len(x: list[s

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
(no final text)
[cost $0.1198, opencode tokens {"total": 4735086, "input": 585992, "output": 14005, "reasoning": 18609, "cache.write": 0, "cache.read": 4116480}]
    tool time: bash 16.4 min
        425s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1200 python3 -m unittest -v test_ail_modconst test_ail_un
        373s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1800 python3 -m unittest -v test_ail_safetynet test_ail_f
         89s bash   rm -rf /tmp/cmpc && mkdir -p /tmp/cmpc/cur /tmp/cmpc/head && cd /home/runner/work/_temp/w2 && ok=0; bad=0; for
         34s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 900 python3 -m unittest -v test_ail_prog29 2>&1 | tail -3
         21s bash   cd /tmp/probes && cat > prog29_z_shadowlen_local.py <<'EOF' V = frozenset("aeiou")  def f() -> str:     len = 
         18s bash   mkdir -p /tmp/probes && cd /tmp/probes && cat > prog29_z_shadowlen.py <<'EOF' V = frozenset("aeiou")  def f() 
          9s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/cmpc1 && mkdir -p /tmp/cmpc1 && AIL_NO_CACHE=1 python3 AIL_CURREN
          5s bash   cd /tmp/probes && for p in prog29_z_shadowlen prog29_z_shadowlen_param prog29_z_shadowlen_local prog29_z_shado
(cut off after 30 minutes)

## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review of prog29

**What the change does:** accepts module-level `frozenset(<str literal>)` (also list/tuple of str) as an ordered deduped `list[str]` readable only via `in`/`not in`/`len`, keeps it at module scope, adds refusals for shadowed `len` and reads before assignment, and lowers `len({...})` to an eager list comprehension plus a private int/str set. That matches the report.

**Verified**
- `g17_026` builds under `--strict` and matches CPython. The other seven report the same first blockers as claimed (`range`, `str(<list>)`, `yield`, instance `__hash__`); `t161`, `g08_004`, `t188` build strict.
- All ten `lab/compare/src/*/main.ail` `program.c` files are byte-identical base vs HEAD (only temp paths in `native_report.json` differ).
- `test_ail_prog29 test_ail_fz208 test_ail_cpython_hybrid test_ail_modconst test_ail_safetynet`: 5 modules, 0 failed. `tools/update_manifest.py --check` clean.
- Own probes (strict typed) matched CPython for setcomp over str/int/list/set/bytes/slice/tuple/bool, empty/duplicates/negatives, and frozenset membership/`len` through arguments, list items, attributes, unicode and duplicates.
- Same-scope parameter/local `len` shadows are refused; nested-def and module-literal shadows are refused; read-before-assignment refusals work for call/class/list.
- No programs/benchmarks edited. DEVLOG/test registration present.

**False / inaccurate claims**
- `prog29_z_shadowlen_param.py` and `..._local.py` were *not* refused; they build typed and match CPython. Correct, since the `len` call is in another function. Report table says refused.
- `prog29_r_order_arg.py` is refused because annotated `frozenset` parameters are unsupported, not by the read-before-assignment check.

**Pre-existing**
- A module-level non-literal binding of `len` (`for len in ...`, `if: len = 5`, `with ... as len`) is mishandled by both base and HEAD non-strict builds: `len(V)` prints `5` where CPython raises `TypeError`. Base differs identically, so this is pre-existing; HEAD additionally accepts it under `--strict` where base refused.

**Defect (caused by this change)**
1. Mutation of the set-comprehension source during iteration. `p_sc_mutate_attr.py`:
```python
class Box:
    def __init__(self) -> None:
        self.xs: list[int] = [1, 2]
    def side(self) -> bool:
        if len(self.xs) < 3:
            self.xs.append(99)
        return True

def f(box: Box) -> int:
    return len({x for x in box.xs if box.side()})

def main() -> None:
    box = Box()
    print(f(box), len(box.xs))

main()
```
CPython and base default build: `3 3`; HEAD default/strict build: `2 3` (both exit 0). CPython's list iterator sees the appended `99`; the new lowering iterates the pre-sized list comprehension bound. `bash ~/tools/cmp.sh p_sc_mutate_attr.py $PWD` shows base `g same / d same`, HEAD `g same / d DIFF`.

**Unverified:** frozenset-iteration general-path order vs base (not compared); instruction counts (`perf_event_open` denied).

VERDICT: FIX
[cost $0.0893, opencode tokens {"total": 6309540, "input": 160608, "output": 19983, "reasoning": 58421, "cache.write": 0, "cache.read": 6070528}]
    tool time: bash 10.3 min
        232s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_prog29 t
         81s bash   cd /tmp && rm -rf cmpbase cmphe && mkdir -p cmpbase cmphe; cd /home/runner/work/_temp/w2; ok=0; bad=0; for t i
         50s bash   cd /tmp/rprobes && cat > p_sc_tuple.py <<'EOF' def f(xs: list[int]) -> int:     return len({(x, x % 2) for x i
         47s bash   cd /tmp/rprobes && cat > p_sc_dict.py <<'EOF' def f(d: dict[str, int]) -> int:     return len({k for k in d}) 
         37s bash   cd /tmp/rprobes && cat > p_sc_byteslit.py <<'EOF' def f() -> int:     return len({b"a" for _ in [1, 2]})  def 
         25s bash   cd /tmp/rprobes && for p in p_ann_list p_ann_set p_ann_dict p_fset_sources p_fset_edges p_fset_types p_setcomp
         24s bash   cd /tmp/rprobes && cat > p_sc_tuple2.py <<'EOF' def f(xs: list[int]) -> int:     return len({(x, x % 2) for x 
         11s bash   cd /tmp/rprobes && cat > p_sc_len_modconst.py <<'EOF' def f() -> int:     return len({x for x in [1, 1, 2]}) l

FINAL VERDICT: FIX  2026-11-02T11:35:08Z
