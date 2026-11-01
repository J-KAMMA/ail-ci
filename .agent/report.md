# job job-std_enum-11011520  started 2026-11-01T06:29:24Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done. Commit: `bb43a83` (not pushed).

- 12 programs in `lab/stdlib/enum/`: 9 build (general path) and match CPython; 3 remain refused as documented follow-ups in `RESULTS.md`.
- Fixes in `enumlib.py`/`prelude_enum.py`: StrEnum forwarding, IntEnum power, chained/direct-name aliases, CPython 3.12 `auto()` max+1, empty-enum call, value containment incl. unhashable `TypeError`.
- Added `test_ail_std_enum` (2 tests: 9 lab programs + edge program) and registered it in `tests.d/`.
- Tests on final commit: `test_ail_std_enum` OK, `test_ail_safetynet` OK, `test_ail_files` OK (1 skip), `test_ail_corpus_findings3` OK, `update_manifest.py --check` OK.
- Compare tasks: all 10 AIL-source generated C byte-identical; Python-source 7 byte-identical, 3 refused identically at base and current (`scar_life`, `tally_lang`, `tree_fold`).
- Probes, both builds, all match CPython: `enum_alias`, `enum_empty`, `enum_contains`, `strenum_methods`, `intenum_pow`, `flags_alias`, `enum_edges_combined`.
[cost $0.0436, opencode tokens {"total": 3582183, "input": 98297, "output": 13589, "reasoning": 17241, "cache.write": 0, "cache.read": 3453056}]
    tool time: bash 38.6 min
        463s bash   rm -rf /tmp/ail-base /tmp/ccmp && git worktree add --detach /tmp/ail-base HEAD >/tmp/wt.log 2>&1 && mkdir -p /
        266s bash   cd AIL_CURRENT && python3 -B test_ail_corpus_findings3.py 2>&1 | tail -20
        241s bash   repo=/home/runner/work/ail-ci/ail-ci; for t in berth_sim chain_relax echo_pack ledger_bin rail_transfer scar_l
        200s bash   cd AIL_CURRENT && python3 -B test_ail_safetynet.py 2>&1 | tail -8
        199s bash   cd AIL_CURRENT && python3 -B test_ail_safetynet.py 2>&1 | tail -20
        137s bash   cd AIL_CURRENT && python3 -B test_ail_files.py 2>&1 | tail -20
        110s bash   cd /tmp/probes && : > final_cmp.txt; for p in enum_alias enum_empty enum_contains strenum_methods intenum_pow 
        105s bash   cd AIL_CURRENT && python3 -B test_ail_std_enum.py 2>&1 | tail -8

## review 0
[model opencode-go/deepseek-v4.1-flash]
**What the change really does:** fixes enum lowering (definition-ordered `__members__`, literal/direct-name aliases, max+1 `auto()`, empty-Enum call, value-based `in` for all enum kinds) and adds hand-written StrEnum string forwarding plus IntEnum `__pow__` to `prelude_enum.py`; adds 12 lab programs, RESULTS, DEVLOG and `test_ail_std_enum`.

**Tests run on HEAD**
- `test_ail_std_enum` ok, `test_ail_safetynet` ok.
- `test_ail_stdlib5` **FAILED (4 subtests)**, `test_ail_pre442` **FAILED (2 subtests)**. On `/tmp/base` (work) both modules pass. This is a regression introduced by the change.

**Defects**

1. **The new StrEnum `split(self, sep)` narrows the compiler's global `split` signature and breaks previously working programs.** Probe `/tmp/rprobes/p_fb_bytes.py`:
```python
from enum import IntEnum
class E(IntEnum):
    B = b"2"
print(E.B.__index__())
print([10, 20, 30][E.B])
```
Expected: builds and prints `2` / `30` (base does). Actual HEAD, both builds: `not in the subset: split() called with too many positional arguments`; `test_ail_pre442` case `float_bool_bytes` fails the same way, and `test_ail_stdlib5` case `small_modules` fails with `split() called without a required argument sep`. The injected runtime/bytes preludes call `split(x, n)`/`split()`, so the added method poisons plain str/bytes calls whenever `prelude_enum` is injected.

2. **StrEnum `partition`/`rpartition` return lists, not tuples.** `/tmp/rprobes/p_strenum_ops.py`, e.g. `print(M.READ.partition("-"), M.READ.rpartition("-"))`. Expected `('read', '-', 'mode') ('read', '-', 'mode')`; actual `['read', '-', 'mode'] ['read', '-', 'mode']`. `prelude_enum.py` wraps the results in `list(...)`; plain `str.partition` correctly yields a tuple.

3. **An empty `Flag`/`IntFlag` now builds but `EF(0)` returns a pseudo-member instead of CPython's TypeError.** `p_empty.py`: `class EF(Flag): pass; print(EF(0))`. Expected `TypeError: <flag 'EF'> has no members; specify ...`; actual `EF(0)`. The empty-enum special case was only added to `generated()`, not `generated_flag()`, while the compile-time refusal was removed for all kinds.

4. **Chained assignment only aliases literals; a computed RHS becomes a duplicate member.** `p_chained_expr.py`: `class X(Enum): A = B = 1 + 1; C = 3`. Expected `[('A', 2), ('C', 3)]` and `X.A is X.B == True`; actual `[('A', 2), ('B', 2), ('C', 3)]` and `X.A is X.B == False` (alias requires `literal(value)`, which is `None` for `1+1`).

**Claim check**
- 9/12 lab programs build and match CPython: verified by `test_ail_std_enum`.
- `auto()` max+1 after descending/negative values, alias ordering, direct-name aliases, `in` through argument/list/attribute/dict, unhashable `TypeError`: verified by my probes (`p_auto_alias`, `p_in_cases`).
- IntEnum `**`/`r**`: verified; builtin `pow(member, n)` still fails in both builds (pre-existing "IntEnum is not int" limitation).
- "StrEnum forwarding" is incomplete/incorrect (defects 1–2); "empty-enum call" false for Flag (defect 3); "chained ... aliases" false for computed RHS (defect 4).
- The 10 compare tasks' generated C byte-identity: not re-verified by me; no `main.ail` imports enum.

**Pre-existing / out of scope:** builtin `pow()` on IntEnum, and using an Enum class as a first-class value (it is rewritten to the member list).

VERDICT: FIX

1. `p_fb_bytes.py` (above): expected build + `2`/`30`; actual compile refusal `split() called with too many positional arguments` (base builds and matches). Same root cause makes `test_ail_stdlib5` and `test_ail_pre442` fail on HEAD while passing at base.
2. `p_strenum_ops.py`: expected tuple from `partition`/`rpartition`; actual list.
3. `p_empty.py`: expected `TypeError` from `EF(0)`; actual `EF(0)`.
4. `p_chained_expr.py`: expected `B` aliased to `A`; actual separate member with value 2.
[cost $0.0495, opencode tokens {"total": 3437295, "input": 105358, "output": 10085, "reasoning": 29692, "cache.write": 0, "cache.read": 3292160}]
    tool time: bash 23.7 min
        328s bash   cd /tmp/base && date && python3 tools/par_check.py -j 2 test_ail_stdlib5 test_ail_pre442 > /tmp/base_tests.log
        276s bash   cd /home/runner/work/ail-ci/ail-ci && date && python3 tools/par_check.py -j 2 test_ail_stdlib5 test_ail_pre442
        271s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_stdlib5 
        202s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_std_enum
        104s bash   cd /tmp/rprobes && date && for p in p_auto_alias p_in_cases p_strenum_ops p_empty p_intenum_pow p_chained_expr
         55s bash   cd /tmp/rprobes && cat > p_auto_alias.py <<'EOF' from enum import Enum, IntEnum, auto  class C(Enum):     A = 
         26s bash   cd /tmp/rprobes && bash ~/tools/cmp.sh p_fb_bytes.py /home/runner/work/ail-ci/ail-ci 2>&1 | grep -v '^cpython 
         22s bash   cd /tmp/rprobes && cat > p_str_after_enum.py <<'EOF' from enum import Enum  class C(Enum):     A = 1  def main

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed all four review defects and committed as `139d0e6`.

- `StrEnum` forwarders now accept CPython’s argument forms; plain `str`/`bytes` calls are no longer narrowed (`p_fb_bytes` prints `2`/`30`).
- `partition`/`rpartition` return tuples.
- Empty `Flag`/`IntFlag` calls raise CPython’s `TypeError`.
- Computed chained assignments alias (`A = B = 1 + 1`), including equal constant values.
- Dynamic method dispatch skips classes whose signature cannot take the call, fixing shared prelude names like `index`/`count`.

Probes: 10/10 match CPython in both builds (`p_fb_bytes`, `p_strenum_ops`, `p_empty`, `p_chained_expr`, `p_strenum_methods2`, `p_strenum_containers`, `p_plain_str_bytes`, `p_empty_flags`, `p_chained_expr2`, `p_cross_modules`).

Tests on final commit: `test_ail_std_enum`, `test_ail_stdlib5`, `test_ail_pre442`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — all 6 pass. Manifest check passes. All 10 `lab/compare` AIL tasks still generate byte-identical C and executables.
[cost $0.0618, opencode tokens {"total": 6227699, "input": 138925, "output": 16585, "reasoning": 21501, "cache.write": 0, "cache.read": 6050688}]
    tool time: bash 35.2 min
        704s bash   cd AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_std_enum test_ail_stdlib5 test_ail_pre44
        362s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && cd AIL_CURRENT && date && python3 ..
        339s bash   cd AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_stdlib5 test_ail_pre442 > /tmp/step_test
        112s bash   cd /tmp/probes && for p in p_strenum_containers p_plain_str_bytes p_empty_flags p_chained_expr2 p_cross_module
        101s bash   cd /tmp/probes && for p in p_fb_bytes p_strenum_ops p_empty p_chained_expr p_strenum_methods2; do echo "=== $p
         73s bash   cd /tmp/probes && for p in p_empty_flags p_chained_expr2 p_cross_modules; do echo "=== $p"; bash ~/tools/cmp.s
         72s bash   cd /tmp/probes && for p in p_strenum_methods2 p_strenum_containers p_plain_str_bytes; do echo "=== $p"; bash ~
         64s bash   cd AIL_CURRENT && python3 - <<'EOF' from pathlib import Path p = Path('python/pkg-v12/pyboxed2.py') s = p.read

## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review report

**What the change really does (one line):** adds StrEnum/IntEnum prelude methods, enum-body alias/`auto()`/empty-class/`in` lowering changes in `enumlib.py`, a signature check for dynamic method dispatch in `pyboxed2.py`, 12 lab programs + `test_ail_std_enum`, and manifest/DEVLOG updates. The report matches this, except its `auto()` claim is overbroad (see below).

**Probes (own, `/tmp/rprobes`, both builds unless noted):**
- Match CPython: `r1_auto` (descending/negative/alias `auto`), `r2_alias` (`1`/`True`/`1.0`/unhashable aliases), `r3_empty` (empty Enum/IntEnum/StrEnum/Flag/IntFlag, calls, iter, `in`), `r4_strenum`+`r19_morestr` (full argument forms, tuples, bounds, slices, `rindex`, `casefold`, tuple returns), `r5_plain` (calendar injection + plain str/bytes), `r6_in` (arg/list-item/attribute/dict value, cross-enum, unhashable), `r7_flags`, `r10_flagalias` (chained Flag aliases), `r13_chained` (computed chained int/str/float/tuple), `r14_dispatch` (array/str/list vs classes with incompatible `index`/`count`), `r17_autoalias`.
- Named refusals (acceptable): `r8` (`auto()` after str/tuple), `r15`/base `r16` (plain/StrEnum `isprintable`).
- **Defect:** `r16_minpred`.

**Claims:** computed chained aliases, partition tuples, empty Flag `TypeError`, descending `auto()`, dynamic-dispatch filtering: verified. Plain str/bytes not narrowed: verified. “`auto()` uses largest previous int + 1 as CPython 3.12 does”: true for int members, **false as a general claim** — CPython continues past a str/tuple (`A=1; B='x'; C=auto()` → 2), AIL refuses by name (so not a defect, but the claim is incomplete). “10/10 probes match”: not re-run.

**Pre-existing (identical on `/tmp/base`):** `r20_strdup` — duplicate *computed non-literal* values (`A="x"+"y"; B="xy"`) are not aliased; both builds print 3 members where CPython prints 1. `r9_shadow` — class-name shadowing already corrupts `in`/subscript on base.

**Tests run on HEAD:** `test_ail_std_enum`, `test_ail_safetynet`, `test_ail_stdlib5`, `test_ail_pre442` all pass (`-j 2`), `update_manifest.py --check` passes. C of `chain_relax` and `berth_sim` is byte-identical to base (only `native_report.json` paths differ).

**Unverified:** remaining 8 lab/compare task C files; the worker’s 10 probes; full suite (not run by instruction).

### Defects
1. **Added `_AilStrEnum.isprintable` turns a named refusal into a runtime `AttributeError`.** Probe `/tmp/rprobes/r16_minpred.py`:
   ```python
   from enum import StrEnum
   class S(StrEnum):
       A = "abc"
   def main():
       print(S.A.isprintable())
   main()
   ```
   CPython: `True`, exit 0. HEAD (both `g` and `d`): builds, then stdout empty, exit 1, stderr `AttributeError: 'str' object has no attribute 'isprintable'`. Base: build refused by name (`not in the subset: the method .isprintable() (on a value of unknown static kind)`), which is acceptable. The added forwarder calls `self.value.isprintable()`, but `str.isprintable` is not built (`pyfunc._STR_METHOD_GROUP` still maps it to the `isdigit` refusal), so the new method cannot work. Fix by dropping the `isprintable` forwarder (restoring the named refusal) or implementing `str.isprintable`.

VERDICT: FIX
[cost $0.0603, opencode tokens {"total": 4626581, "input": 70701, "output": 15410, "reasoning": 44854, "cache.write": 0, "cache.read": 4495616}]
    tool time: bash 19.3 min
        346s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_stdlib5 
        211s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_std_enum
         91s bash   cat > /tmp/rprobes/r9_shadow.py <<'EOF' from enum import Enum  class C(Enum):     A = 1     B = 2  class F(Enu
         84s bash   cd /tmp/rprobes && for p in r5_plain r6_in r7_flags r8_chain; do echo "===== $p"; bash ~/tools/cmp.sh /tmp/rpr
         79s bash   cat > /tmp/rprobes/r1_auto.py <<'EOF' from enum import Enum, auto  class Desc(Enum):     A = 5     B = 2     C
         78s bash   cd /tmp/rprobes && date && : > /tmp/rprobes/res.txt; for p in r1_auto r2_alias r3_empty r4_strenum; do echo "=
         46s bash   cd /tmp && python3 - <<'EOF' from enum import IntEnum try:     class E(IntEnum):         B = b"2"     print(E.
         33s bash   cat > /tmp/rprobes/r4_strenum.py <<'EOF' from enum import StrEnum  class S(StrEnum):     SPACE = "  Hello Worl

FINAL VERDICT: FIX  2026-11-01T09:28:06Z
