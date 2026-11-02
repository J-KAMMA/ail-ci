# job job-rbprog9-11022049  started 2026-11-02T11:49:50Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed both review defects and committed as `18efed3` on `job-rbprog9-11022049`.

- Bool-row flags now pre-register per function, fixing `for`/`while` loop back-edges (`0` then `True`).
- Optional-method resolution now infers receiver classes from `make()` returns, list items and dict values; ambiguous/unresolvable receivers are refused rather than reinterpreted.

Probes: 16 run (`w_loop_backedge*`, `b_loop_*`, `s_fallback_int2`, `v_fallback_dictrecv`, `m_*`); all matched CPython on both builds.

Tests: `test_ail_prog9`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_quirks`, `test_ail_optint_exact`, `test_ail_optional_locals`, `test_ail_nonecrash` — 8 modules, 0 failed. `update_manifest.py --check` rc=0.
[cost $0.0000, opencode tokens {"total": 3088513, "input": 304803, "output": 10003, "reasoning": 14795, "cache.write": 0, "cache.read": 2758912}]
    tool time: bash 16.6 min
        409s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1800 python3 ../tools/par_check.py -j 2 test
        338s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1500 python3 ../tools/par_check.py -j 2 test
        188s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1500 python3 ../tools/par_check.py -j 2 test
         21s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/b_loop_false.py /tmp/probes/b_loop_rebind_after.py 
         11s bash   cd /home/runner/work/ail-ci/ail-ci && cat > /tmp/probes/m_recursive.py <<'EOF' class P:     def __init__(self)
         10s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/w_loop_backedge.py /tmp/probes/w_loop_backedge_whil
         10s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/w_loop_backedge.py /tmp/probes/w_loop_backedge_whil
          3s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 300 bash ~/tools/cmp.sh /tmp/probes/m_attr_q.py $PWD 2>&1 | head

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: rbprog9 loop-flag + receiver-class fix

**What the change really does.** It pre-registers SROW bool companion flags for every `a, b = p.m()` assign in a function before body codegen (pyfunc.py:38277), and replaces the unique-name Optional-method fallback in `optlib.py` with receiver-class inference from `Cls()`, function returns (`make()`), list items, and dict values, refusing when classes that define the name disagree. This matches the report, except receiver inference is not scoped to the current function.

**Checks run**
- Review probes: `w_loop_backedge*`, `s_fallback_int2`, `v_fallback_dictrecv` all match CPython on both builds; both named defects are fixed.
- Bool boundaries: straight-line before/after unpack, taken/untaken branch, zero-iteration loop, loop rebind to int — all match.
- Receiver boundaries: annotated param, `make()` return (annotated and unannotated), list item, dict value, attribute, two call sites with different classes — match or compile correctly.
- Regression probe (below): base matches CPython, HEAD both builds do not.
- Non-feature `plain.py`: generated `program.c` byte-identical to `/tmp/base`.
- Tests on HEAD: `test_ail_prog9`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_quirks`, `test_ail_optint_exact`, `test_ail_optional_locals`, `test_ail_nonecrash` — 8 modules, 0 failed. `update_manifest.py --check` rc=0.

**Pre-existing.** Class-instance repr (`<__main__.Q object at ...>` vs `<Q object>`) and mixed-class container mutation (`TypeError: 'int' object is not subscriptable`) fail identically on `/tmp/base`.

**Defect**

1. **New receiver inference walks nested function bodies, so an inner local class leaks into the outer receiver.** `receiver_classes_of` collects assigns with `ast.walk(node)`; the new `value_class`/`literal_element_class` then make an inner `q = make()` or `qs = [Q()]` determine the *outer* `q`/`qs` class.
   `/tmp/rprobes/c6_nested_list.py`:
   ```python
   class P:
       def __init__(self) -> None: self.x = 1
       def peek(self) -> int | None: return None
   class Q:
       def __init__(self) -> None: self.n = 7
       def peek(self) -> int: return self.n
   def main(qs) -> None:
       def inner() -> None:
           qs = [Q()]
           print(qs[0].peek())
       inner()
       print(qs[0].peek())
   main([P()])
   ```
   CPython and `/tmp/base`: `7`, `None`. HEAD `cmp.sh g` and `d`: `7`, `(False, 0)`. The inner `qs = [Q()]` marks outer `qs` as Q, so the real `P.peek()` Optional call is not lowered. `/tmp/rprobes/c7_nested_unannotated.py` (`q = make()` with unannotated `def make(): return Q()`) reproduces the same `None` → `(False, 0)`. The direct-class nested leak exists on base, but these two forms are new because base did not follow list literals or function returns; base is correct on both.

**Claims.** Bool loop back-edge: verified. `make`/list/dict receiver resolution: verified for the worker's shapes, but the "refused rather than reinterpreted" claim is false for the nested-shadowing case above (it is silently reinterpreted). 8 test modules / manifest check: verified. The worker's exact 16 probes: only equivalents re-run.

**Unverified.** Wider suite; instruction counts (`perf_event_open: Permission denied`), though the change is compile-time plus SROW-only flag writes and non-feature C is identical.

VERDICT: FIX
1. `/tmp/rprobes/c6_nested_list.py` and `/tmp/rprobes/c7_nested_unannotated.py`: expected `7` then `None`; HEAD both builds print `7` then `(False, 0)`. Restrict `receiver_classes_of`/`container_classes` to the current function scope (do not descend into nested `FunctionDef`/`Lambda`/`ClassDef`), or refuse when a receiver name is bound in a nested scope.
[cost $0.0000, opencode tokens {"total": 2237298, "input": 171049, "output": 10581, "reasoning": 25332, "cache.write": 0, "cache.read": 2030336}]
    tool time: bash 12.1 min
        221s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT; date; timeout 1200 python3 ../tools/par_check.py -j 2 test_ail
        188s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT; date; timeout 1200 python3 ../tools/par_check.py -j 2 test_ail
        168s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT; date; timeout 1500 python3 ../tools/par_check.py -j 2 test_ail
         19s bash   cat > /tmp/rprobes/m1_list_mut.py <<'EOF' class P:     def __init__(self) -> None: self.x = 1     def peek(sel
         16s bash   cat > /tmp/rprobes/c1_nested_make.py <<'EOF' class P:     def __init__(self) -> None: self.x = 0     def peek(
         13s bash   cd /home/runner/work/ail-ci/ail-ci; date; for p in /tmp/rprobes/*.py; do echo "===== $p HEAD"; timeout 300 bas
         12s bash   cd /tmp/base; for p in /tmp/rprobes/c1_nested_make.py /tmp/rprobes/c2_nested_container.py /tmp/rprobes/s1_fall
         12s bash   cat > /tmp/rprobes/c6_nested_list.py <<'EOF' class P:     def __init__(self) -> None: self.x = 1     def peek(

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed the remaining review defect: `receiver_classes_of` now walks only the current function scope (`_own_nodes` no longer enters nested defs/lambdas/classes), so nested `qs = [Q()]` / `q = make()` cannot retype an outer receiver.

- Probes: 45 run on both builds — 40 match CPython; `c1`/`c2` differ only in known pre-existing class-instance repr, and `m1`/`m2`/`m3` fail identically to `/tmp/base` on mixed-class container mutation.
- `c6_nested_list`, `c7_nested_unannotated`, `s_fallback_int2`, `v_fallback_dictrecv`, `w_loop_backedge`, `w_loop_backedge_while` all match.
- Tests: 8 modules (`test_ail_prog9`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_quirks`, `test_ail_optint_exact`, `test_ail_optional_locals`, `test_ail_nonecrash`) — 0 failed.
- `update_manifest.py --check` rc=0; committed as `751c1bf`.
[cost $0.0000, opencode tokens {"total": 1185782, "input": 75594, "output": 5457, "reasoning": 6491, "cache.write": 0, "cache.read": 1098240}]
    tool time: bash 9.1 min, read 0.0 min, edit 0.0 min
        409s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
        108s bash   cd /home/runner/work/ail-ci/ail-ci && : > /tmp/probe_results.txt; for p in /tmp/probes/*.py /tmp/rprobes/*.py;
         16s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/c6_nested_list.py /tmp/rprobes/c7_nested_unannotat
          6s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/c6_nested_list.py /tmp/rprobes/c7_nested_unannotat
          6s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/c6_nested_list.py /tmp/rprobes/c7_nested_unannotat
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1500 python3 ../tools/par_check.py -j 2 test
          0s bash   cd /home/runner/work/ail-ci/ail-ci && sed -n '1,60p' DEVLOG.md && echo ==== && git show --stat HEAD && echo ==

## review 1
[model opencode/deepseek-v4.1-flash-free]
## Review: rbprog9 review fix 5

**What the change really does.** Two commits: (a) pre-registers bool-row companion flags for every SROW bool unpack before compiling the function body (fixes the loop back-edge), and broadens Optional-method receiver resolution to function-return classes, list literals and dict values, with a class-aware unique-name fallback that refuses otherwise; (b) restricts `_own_nodes`/`receiver_classes_of` to the current scope. Matches the report except that the new container inference is unsound under element mutation (below).

**Checks run**
- Review defects 1 and 2 re-run: `w_loop_backedge`, `w_loop_backedge_while`, `s_fallback_int2`, `v_fallback_dictrecv` now match CPython on both builds (base still fails all four). Fixed.
- All 13 worker `/tmp/probes/*.py` match on both builds; 24 earlier probes also match; `c1/c2` differ only in pre-existing class repr; `m1/m2/m3` are byte-for-byte the same failure as base.
- Nested-scope claims: `c6_nested_list`, `c7_nested_unannotated` match.
- Non-feature `plain.py`: `program.c` byte-identical to `/tmp/base`.
- `test_ail_prog9` + `test_ail_safetynet`: 2 modules, 0 failed. `update_manifest.py --check` rc=0; `tools/diff_ids.py` absent.
- Probes for list/dict element mutation, aliasing, negative index, iteration, empty containers.

**Defect 1 (new, blocking).** Container literal element class is inferred but element mutation is ignored, so a method call on a reassigned element resolves the wrong class.

```python
class P:
    def __init__(self) -> None: self.x = 0
    def peek(self) -> int | None: return None
class Q:
    def __init__(self) -> None: self.s = "q"
    def peek(self) -> tuple[str, int]: return (self.s, 5)
def main() -> None:
    qs = [Q()]
    qs[0] = P()
    print(qs[0].peek())
main()
```
CPython/`/tmp/base`: `None`. HEAD (both builds): `(False, 0)`.
Same root, same wrong output (`(False, 0)` vs `None`) for:
- dict value: `d = {"k": Q()}; d["k"] = P(); print(d["k"].peek())`
- aliasing: `qs = [Q()]; rs = qs; rs[0] = P(); print(qs[0].peek())`
- append: `qs = [Q()]; qs.append(P()); print(qs[1].peek())`
- negative index: `qs = [Q(), Q()]; qs[-1] = P(); print(qs[-1].peek())`
- after a loop: `qs = [Q()]` print, then `qs[0] = P()`, print again → second line `(False, 0)` vs `None`.
`container_classes` keys only on `ast.Assign` to a bare `Name`, so subscript stores/append/aliases are invisible. Base is correct on all of these, so this is introduced by the change.

**Pre-existing (do not block).** `r12_reverse_mut` (`qs=[P()]; qs[0]=Q()`) prints `5` vs `('q', 5)` on both HEAD and base; `r10` (empty list then append) is wrong on base and now correct on HEAD; `c1/c2` class repr; `m1/m2/m3`.

**Report claims:** loop back-edge — verified fixed; external receivers / unique-fallback — verified fixed; nested-scope fix — verified; probe counts and tests — consistent for what I ran; manifest check — verified. No false claims found.

**Unverified:** the six other test modules named in the report, and wider corpus/perf (the change is not on a hot path).

VERDICT: FIX
1. Element mutation after a container literal is not tracked. Probe `r1_list_mut.py` above (and the dict, alias, append, negative-index and post-loop variants): expected `None`, HEAD prints `(False, 0)`. Invalidate `container_classes` for a name that is subscript-assigned/appended, or refuse the receiver.
[cost $0.0000, opencode tokens {"total": 2311791, "input": 128583, "output": 8295, "reasoning": 20801, "cache.write": 0, "cache.read": 2154112}]
    tool time: bash 6.3 min
        169s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1500 python3 ../tools/par_check.py -j 2 test
         54s bash   cd /home/runner/work/ail-ci/ail-ci && date && for n in a1_attr b1_straight b2_cond b3_loop_rebind b4_zero_loop
         34s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in /tmp/probes/*.py; do n=$(basename $p .py); out=$(timeou
         30s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in c1_nested_make c2_nested_container m1_list_mut m2_dict_
         17s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in r1_list_mut r2_dict_mut r3_alias_mut r4_append r5_neste
         15s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in w_loop_backedge w_loop_backedge_while s_fallback_int2 v
         13s bash   cd /tmp && date && for p in r1_list_mut r2_dict_mut r3_alias_mut r4_append; do echo "===== BASE $p"; timeout 3
         12s bash   cat > /tmp/rprobes/r10_empty_then_append.py <<'EOF' class P:     def __init__(self) -> None: self.x = 0     de

FINAL VERDICT: FIX  2026-11-02T12:54:31Z
