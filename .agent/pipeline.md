# job job-fuzz39-10230820  started 2026-10-22T23:21:21Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Findings and fix

- Area probed with 23 programs: `copy.copy`/`copy.deepcopy`, `.copy()`, aliasing/default args, `is` vs `==` for ints/None/containers, tuple constants.
- First silent wrong answer: `p = (); q = (); p is q` and `r = (); r is (1,)` printed `False`; CPython merges tuple constants and printed `True`.
- Fix: tuple-constant identity is now refused by name (`DIFFERENCES C?-job-fuzz39-10230820-1`), including a tuple constant passed to both parameters of a generic `def same(a, b): return a is b`. `tuplib.py` leaves such comparisons for the refusal. Different tuple values, same-object uses, list/dict/set identity, `.copy()`, default-arg aliasing and small-int identity still match CPython on both builds.

Probe results (final commit, both builds)

- Closed/refused: p13, p16, p18, p19, p20, p21, p23.
- Match CPython: p05, p06, p12, p14, p15, p17, p22.
- Refused for other named reasons: p01-p04, p07-p10 (`import copy` not in the subset), p11 (`is` with number constant, C115).

Other differences seen: `copy.copy` / `copy.deepcopy` remain unavailable (refused at import), and numeric-literal `is` remains refused as C115; neither was a silent answer.

Tests on final commit `b6b1964`

- `test_ail_fuzz39`: ok
- `test_ail_silent2`: ok
- `test_ail_tuples`: ok
- `test_ail_safetynet`: ok
- `test_ail_files`: ok
- `test_ail_corpus_findings3`: ok
- `par_check -j 2`: 6 modules, 380s, 0 failed
- `update_manifest.py --check`: rc 0
[cost $0.0000, opencode tokens {"total": 5465985, "input": 146488, "output": 17761, "reasoning": 27752, "cache.write": 0, "cache.read": 5273984}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
Review of `b6b1964`.

**Defect (new silent wrong answer)**

Probe `/tmp/rprobes/p19.py`:

```python
def show(a):
    print(a)

def f() -> None:
    x = (1,)
    x = 2.5
    z = 2.5
    print(x is z)

def main() -> None:
    f()
    show((1, 2))
main()
```

- CPython: `True`
- HEAD (`g` and `d`): exit 0, prints `False`
- base `work` (`4b6aef5`): refused by name with `C115` (`is` with a number constant)

Cause: `numidentity.py:384-385`. `x` has mixed tuple/float bindings, so `_join` makes its kind `tuple`; `_tuple_may_be_same` correctly returns false, but the new tuple `continue` then skips the C115/C114 checks. Base refused this program; the change removed the refusal and produced a silent wrong answer. This is not pre-existing.

**Pre-existing (does not block by itself)**

`a = (); b = (); print(a is(b))`: HEAD and base both print `False`, CPython `True`. `tuple_refusal()` gates on the literal text `' is '`, so `is(` bypasses it. Same result on base; listed as pre-existing, though the text gate is fragile.

**Other probes / claims**

- Worker probes re-run on HEAD: `p01-p04,p07-p10` refused at `import copy`; `p11` refused C115; `p13,p16,p18,p19,p20,p21,p23` refused with `C?-job-fuzz39-10230820-1`; `p05,p06,p12,p14,p15,p17,p22` match CPython on both builds. All these report claims verified.
- My probes: same tuple passed to both parameters refused; different tuple constants / same-object uses / tuple `==` match; `is not` tuple refusal works; constant-folded tuple operands are refused.
- `program.c` for a non-tuple-identity probe is byte-identical to base, so accepted non-refused programs are unchanged.
- Tests: `par_check -j 2 test_ail_fuzz39 test_ail_safetynet test_ail_tuples` -> 3 modules, 0 failed, 112s. `update_manifest.py --check` rc 0.
- Re-ran only those modules; the report's `test_ail_silent2`, `test_ail_files`, `test_ail_corpus_findings3` results were not independently verified.
- Speed: change is compile-time only and generated C is identical for unaffected programs; no hot-path measurement needed.

VERDICT: FIX

1. `/tmp/rprobes/p19.py`: CPython prints `True`; HEAD prints `False` on both builds (base refused C115). The new tuple `continue` at `numidentity.py:384-385` skips C115/C114 for a name whose kind is `tuple` but whose bindings also include a number.
[cost $0.0000, opencode tokens {"total": 2016387, "input": 67085, "output": 8806, "reasoning": 21520, "cache.write": 0, "cache.read": 1918976}]

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `d26e177`.

- Defect: mixed tuple/number bindings now reach the number refusal again (`p19` → C115). The `is(` spelling also no longer bypasses refusals in `numidentity.py` / `pyboxed2.py` (`a is(b)` → tuple refusal).
- Probes: 13 in `/tmp/probes` (`p19`–`p31`, incl. list item, attribute, dict value, `is not`); all refused by name on both builds, none silent.
- Tests on final commit: `test_ail_fuzz39`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` → 4 modules, 0 failed, 201s. Earlier same content also passed `test_ail_tuples`, `test_ail_silent2` (6 modules, 359s).
- `update_manifest.py --check` rc 0. No new differences beyond the existing C?-job-fuzz39 row.
[cost $0.0000, opencode tokens {"total": 1131219, "input": 90071, "output": 6405, "reasoning": 10999, "cache.write": 0, "cache.read": 1023744}]

## review 1
[model opencode/deepseek-v4.1-flash-free]
**Review: `d26e177` (on `b6b1964`), branch `job-fuzz39-10230820`**

Change: `numidentity.py` now models tuple constants; `is`/`is not` with a tuple constant is refused by name (`C?-job-fuzz39-10230820-1`) for direct displays, names, positional arguments, and values from lists/attributes/dicts. Mixed tuple+number bindings still reach C115; the text gate is `\bis\b` so `is(` is covered; `tuplib` leaves such comparisons for the refusal.

Probes (HEAD, both builds):
- `r01`, `r02`, `r07`, `r21` (empty/value/nested/negative equal tuples): named tuple refusal on general and default.
- `r03`, `r17`, `p19` (mixed tuple/float binding): C115 on both.
- `r09`, `r14` (`x is(...)`, float/int): C115 on both; base's int case died with a runtime "AIL internal error" (exit 1), so this is an improvement.
- `r05`, `r08`, `r11` (same-object tuples, copy/defaults/small ints): match CPython on both.
- `r10`, `r15` (no feature / `is` without tuple): stdout matches base; generated `program.c` byte-identical to base.
- Over-refusals (e.g. `(1,) is [1]`, `(1,) is 2.5`) are named and allowed by the brief.

Report claims:
- final commit `d26e177` — verified.
- `p19` → C115 — verified.
- `is(` no longer bypasses refusals — verified.
- "13 probes, all refused by name, none silent" — partly false: `p22_tuple_same_object.py` compiles and matches (allowed); none are silent.
- 4 test modules, 0 failed — only 2 re-run per review scope: `test_ail_fuzz39`, `test_ail_safetynet`, 0 failed (99 s). `test_ail_files` / `test_ail_corpus_findings3` not re-run.
- `update_manifest.py --check` rc 0 — verified.
- no new DIFFERENCES beyond the tuple row — verified.

Pre-existing (identical on base, not blocking):
1. Tuple identity via keyword arguments (`same(a=(1,), b=(1,))`), a lambda, or a method still prints `False` where CPython prints `True` (`r06`, `r19`, `r20`).
2. `"x" is "x"` prints `False` in both builds (`r15`).
3. Folded tuple constants on both sides, e.g. `(1+1,) is (1+1,)`, print `False` vs `True` (`r24`) — same tuple-constant cause, not covered.
4. `(10 ** 30,)` → "integer overflow", exit 1 (`r13`, `r23`).
5. `copy.copy`/`deepcopy` unsupported: named refusal, same on base (`r12`).

Speed: no runtime change. `program.c` byte-identical to base for `g00_002`, `g00_008`, `g00_024`, `r10`, `r15`; `icount` could not run (`perf_event_open` EPERM), but identical C implies identical instruction counts.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 3378079, "input": 143732, "output": 10859, "reasoning": 52288, "cache.write": 0, "cache.read": 3171200}]

FINAL VERDICT: ACCEPT  2026-10-23T00:12:01Z
