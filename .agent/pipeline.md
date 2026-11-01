# job job-std_numbers-11020026  started 2026-11-01T15:28:20Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done. Commit `d08c7d4` on `job-std_numbers-11020026`.

- **Coverage:** 12 programs in `lab/stdlib/numbers/`, 17–49 lines. **11/12 build** on the default path (general) and match CPython 3.12 stdout + exit; `complex_literal.py` remains a named follow-up (`a constant of type complex`).
- **Implementation:** `prelude_numbers.py` ABC hierarchy + `numberslib.py` lowering of `isinstance`/`issubclass`/`register`, wired through `stdlib5.py`/`ail_syntax.py`.
- **Docs:** `RESULTS.md`, `DIFFERENCES.md`, `DEVLOG.md`; follow-up refusal texts now show the actual generic first line plus the naming note.
- **Tests on final commit:** `test_ail_std_numbers` OK, `test_ail_safetynet` OK, `test_ail_files` OK (1 Windows skip: no zig), `test_ail_corpus_findings3` OK. Manifest `--check` exits 0.
- **Codegen:** all 20 `lab/compare` sources (`main.ail` + `main.py`, 10 tasks) produce byte-identical C vs `HEAD`.
- **Probes:** `/tmp/probes/num_aliases`, `num_custom`, `num_isinstance`, `num_issubclass`, `num_register`, `num_empty_errors` match CPython on both builds; `num_dynamic_refused`, `num_register_base`, `num_complex_value`, and two ABC-method probes are refused by name.
[cost $0.0330, opencode tokens {"total": 3087282, "input": 97266, "output": 7235, "reasoning": 8573, "cache.write": 0, "cache.read": 2974208}]
    tool time: bash 43.9 min, edit 0.0 min, read 0.0 min
        955s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && for m in test_ail_std_numbers test_ail_safetynet test_ail_files t
        455s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/probes/num_*.py; do echo "===== $p"; timeout 300 bash ~/tools/c
        332s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && AIL_NO_CACHE=1 AIL_EXTRA_CFLAGS='-Werror=incompatible-pointer-typ
        274s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && AIL_NO_CACHE=1 AIL_EXTRA_CFLAGS='-Werror=incompatible-pointer-typ
        262s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && AIL_NO_CACHE=1 AIL_EXTRA_CFLAGS='-Werror=incompatible-pointer-typ
        169s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && AIL_NO_CACHE=1 AIL_EXTRA_CFLAGS='-Werror=incompatible-pointer-typ
        100s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && AIL_NO_CACHE=1 AIL_EXTRA_CFLAGS='-Werror=incompatible-pointer-typ
         70s bash   cd /home/runner/work/_temp/w2 && sed -i "s|r=subprocess.run(\[sys.executable,'-B','-c',GEN,str(root)\],input=j

## review 0
[model opencode-go/deepseek-v4.1-flash]
**What the diff really does:** gates the `stdlib5` source pass on `import numbers`, injects five plain ABC classes (`prelude_numbers.py`), and rewrites `isinstance` / `issubclass` / `register` (`numberslib.py`) into helpers that classify by exact `type(v).__name__` and by bases of the injected classes.

**Defects (reproduced on HEAD, both `g` and `d` builds, same exit status, wrong stdout):**

1. **A subclass of `Fraction` is not a number.** Helper only matches `type(v).__name__ == "Fraction"`; static tables only know the exact name.
   `/tmp/rprobes/num_fraction_subclass.py`
   - CPython: `1/2 True True True` / `True True` / `True`
   - AIL: `1/2 False False False` / `False False` / `True`

2. **User classes named `Fraction` / `Decimal` are misclassified.**
   `/tmp/rprobes/num_user_named_fraction.py`
   - CPython: `False False False` / `False False` / `False False`
   - AIL: `True True True` / `True False` / `False False`
   (The name check is unconditional; it does not verify that `fractions`/`decimal` was imported.)

3. **An ordinary `isinstance(x, (A, B))` tuple breaks in any program that imports `numbers`.** The lowering emits `isinstance(x, A, B)` when the tuple has no `numbers.*` element.
   `/tmp/rprobes2/tuple_numbers.py` (`import numbers` + `isinstance(x, (A, B))`)
   - Works on base without the import: `True True False`
   - HEAD: compile fails, `not in the subset: isinstance() with other than 2 arguments`
   Same root silently miscompiles nested tuples: `/tmp/rprobes/num_nested_wrong.py` expected `True True False`, actual `False False False`.

4. **`numbers.Real` etc. used as a value is not refused** (contradicting `numberslib.py`'s own docstring) and prints a different class.
   `/tmp/rprobes/num_value_ref.py`
   - CPython: `<class 'numbers.Real'>` / `Number` / `<class 'numbers.Integral'>` / `ABCMeta`
   - AIL: `<class '__main__.Real'>` / `Number` / `<class '__main__.Integral'>` / `type`

**Pre-existing:** `isinstance(x, ())` cannot build on base either (base fails later in C with `ail_box_bool()` arity); on HEAD it is refused earlier. Not caused by this change.

**Claim check:**
- 12 programs, 11 build/match: verified by `test_ail_std_numbers` (OK).
- `test_ail_safetynet`: OK. `test_ail_files` / `test_ail_corpus_findings3`: not re-run per the "targeted modules only" rule (unverified).
- Codegen byte-identical: no `lab/compare/src/*/main.{py,ail}` mentions `numbers`; `berth_sim` `program.c` is byte-identical HEAD vs `/tmp/base2`. Verified.
- "numbers used as a value is refused by name" (module docstring): **false** (defect 4).
- Worker's own `/tmp/probes/num_*` set: not re-run; independent probes found the gaps above.

**Not checked:** speed (pass is compile-time only; injected helper not hot), `test_ail_files`, `test_ail_corpus_findings3`, all 20 compare C files individually.

VERDICT: FIX
1. Fraction subclasses must classify as Rational/Real/Number (probe `num_fraction_subclass.py`, expected `1/2 True True True`, got `1/2 False False False`).
2. Exact-name checks must not classify user classes named `Fraction`/`Decimal` (probe `num_user_named_fraction.py`, expected all `False`, got `True True True` / `True False`).
3. Do not rewrite an `isinstance` tuple that contains no `numbers.*` element (or wrap the remaining tuple); today `isinstance(x, (A, B))` in a numbers program fails with `isinstance() with other than 2 arguments`, and a nested tuple returns False (probe `tuple_numbers.py`, `num_nested_wrong.py`).
4. Either refuse `numbers.X` used as a plain value as the docstring says, or reproduce CPython's class repr/module (probe `num_value_ref.py`, expected `<class 'numbers.Real'>`, got `<class '__main__.Real'>`).
[cost $0.0266, opencode tokens {"total": 1072321, "input": 49514, "output": 6141, "reasoning": 20826, "cache.write": 0, "cache.read": 995840}]
    tool time: bash 10.5 min
        441s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1000 python3 ../tools/par_check.py -j 2 test_ail_std_numb
         72s bash   cat > /tmp/rprobes/num_tuple_classes.py <<'EOF' import numbers  class A:     pass  class B:     pass  def kind
         45s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/rprobes/num_empty_tuple.py /tmp/rprobes/num_nested_tuple.py /tm
         30s bash   cat > /tmp/rprobes/num_fraction_subclass.py <<'EOF' import numbers from fractions import Fraction  class Half(
         25s bash   cd /tmp && rm -rf cA cB; mkdir cA cB; for wt in /home/runner/work/_temp/w2 /tmp/base2; do tag=$( [ "$wt" = /tm
         12s bash   cat > /tmp/rprobes/num_value_ref.py <<'EOF' import numbers  def main():     print(numbers.Real)     print(numb
          1s bash   cat > /tmp/rprobes2/tuple_plain2.py <<'EOF' class A:     pass  class B:     pass  def f(x):     return isinsta
          1s bash   cd /home/runner/work/_temp/w2 && git worktree add /tmp/base2 work 2>&1 | tail -2; cd /tmp/base2 && git rev-par

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed all four review defects in `numberslib.py` and committed as `eb2479a`.

- Fraction subclasses now classify as Rational/Real/Number, including through aliases.
- User classes merely named `Fraction` / `Decimal` are no longer numbers.
- Ordinary `isinstance(x, (A, B))` is untouched; nested number tuples are flattened and classify correctly.
- `numbers.X` used as a plain value is refused by name; class bases and annotations still work.

Probes (13, both `cmp.sh` builds): `num_fraction_routes`, `num_fraction_aliases`, `num_user_named`, `num_tuple_plain`, `num_tuple_nested`, `num_bases_annotations`, `num_kinds_values`, `num_registered_subclass`, `num_from_import_allowed`, `num_alias_base` all match CPython; `num_value_refuse`, `num_from_import_refuse`, `num_alias_refuse` are refused by name.

Tests on the final commit: `test_ail_std_numbers` (12 lab programs plus new regressions), `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_stdlib5` — 5/5 pass. Manifest `--check` clean.

Not re-run: lab/compare generated-C identity. No compare source uses `numbers`, so the changed pass is not reached; no codegen change was made outside that gate.
[cost $0.0480, opencode tokens {"total": 3371542, "input": 105878, "output": 14242, "reasoning": 23134, "cache.write": 0, "cache.read": 3228288}]
    tool time: bash 24.7 min
        605s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_std_numb
        323s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_std_numb
        318s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_std_numb
        145s bash   cd /home/runner/work/_temp/w2 && for p in num_fraction_routes num_fraction_aliases num_user_named num_tuple_pl
         28s bash   cd /home/runner/work/_temp/w2 && mkdir -p /tmp/repro && cp /tmp/rprobes/num_fraction_subclass.py /tmp/rprobes/
         26s bash   cd /home/runner/work/_temp/w2 && python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/python/pkg-v12/
         12s bash   cd /tmp/repro && cp /tmp/rprobes/num_fraction_subclass.py /tmp/rprobes/num_user_named_fraction.py /tmp/rprobes
         10s bash   cd /tmp/probes && cat > num_from_import_allowed.py <<'EOF' import numbers from numbers import Number, Real   c

## review 1
[model opencode-go/deepseek-v4.1-flash]
**Review report — job-std_numbers (work..HEAD, HEAD `eb2479a`)**

**What the diff does.** Adds a `numbers` batch-5 pass (`numberslib.py`, `prelude_numbers.py`), a gate word in `ail_syntax.py`/`stdlib5.py`, 12 lab programs, a test module, DEVLOG/DIFFERENCES. It injects the five ABCs as plain classes and lowers `isinstance`/`issubclass`/`register` onto them. The second commit makes the runtime classifier use the real `Fraction`/`Decimal` classes, flattens number tuples, and refuses `numbers.X` as a plain value. This matches the report.

**Verified claims.**
- Fraction subclass routes + aliases: verified (`rev_frac_routes2`, `rev_frac_alias`, both builds match CPython).
- User class named `Fraction`/`Decimal` is not a number: verified (`rev_user_named`).
- Ordinary `(A,B)` untouched, nested number tuples flattened: verified (`rev_plain_tuple`, `rev_nested2`).
- `numbers.X` plain value refused; bases/annotations work: verified (`rev_values2`, `rev_ann`).
- Tests: `test_ail_std_numbers`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` = 4/4 pass (508s). `update_manifest.py --check` rc=0.
- Codegen: `program.c` byte-identical HEAD vs base for `chain_relax`, `ledger_bin`, `echo_pack` (only `native_report.json` temp paths differ). No compare source mentions `numbers`.

**Defects (all build and print wrong values on both `cmp.sh` builds; base refuses `import numbers`, so not pre-existing).**

1. Registration is applied at compile time regardless of whether it executes.
```python
import numbers
class A: pass
def setup(): numbers.Number.register(A)
def main():
    print(isinstance(A(), numbers.Number))
    setup()
    print(isinstance(A(), numbers.Number))
main()
```
Expected `False` then `True`; actual `True`/`True`. Same for `if False: numbers.Number.register(A)` (expected `False`/`False`, actual `True`/`True`) and for a check before a module-level register (expected `False`, actual `True`). Registration timing/control flow is ignored.

2. A virtual registration leaks the ABC's concrete methods, unlike CPython.
```python
import numbers
class Money: pass
numbers.Real.register(Money)
numbers.Rational.register(Money)
print(hasattr(Money,"real"), hasattr(Money,"imag"), hasattr(Money,"conjugate"))
print(hasattr(Money(),"real"), hasattr(Money(),"imag"))
```
Expected `False False False` / `False False`; actual `True True True` / `True True`. CPython's `register` makes a virtual subclass only, it does not inherit `real`/`imag`/`conjugate`.

3. A parameter shadowing a from-imported ABC is still lowered as the ABC.
```python
from numbers import Number, Real
class A: pass
class B: pass
def f(Number, Real, x):
    return (isinstance(x, Number), isinstance(x, Real))
print(f(A, B, A()))
print(f(B, A, A()))
```
Expected `(True, False)` / `(False, True)`; actual `(False, False)` / `(False, False)`. The collision check covers `ast.Name`/defs but not `ast.arg`.

**Unverified / notes.** Only 3 of 10 compare tasks checked for byte-identical C (grep shows no compare source uses `numbers`). `test_ail_stdlib5` and the worker's own 13 probes not re-run. Speed not checked: the change only adds code for programs that import `numbers`; no hot path changes. Pre-existing/not blocking: `tree_fold` fails identically on base and HEAD; nested non-numbers tuples, builtin types passed as values, and `class D(Decimal)` are compiler limitations present on base.

VERDICT: FIX

1. Registration is lowered statically: `rev_reg_order` / `rev_reg_in_func` / `rev_reg_cond` give `True` for an `isinstance` that in CPython is still `False` (before registration, in an uncalled function, or under `if False`). Expected `False`/`True` (or `False`/`False`), actual `True`/`True`.
2. `register` adds a real base, so virtual subclasses gain ABC attributes: `rev_reg_virtual` prints `True True True` / `True True` where CPython prints `False False False` / `False False`.
3. A function parameter shadowing a from-imported ABC is ignored: `rev_param_shadow2` prints `(False, False)` for both calls where CPython prints `(True, False)` and `(False, True)`.
[cost $0.0468, opencode tokens {"total": 2275846, "input": 96490, "output": 10511, "reasoning": 32653, "cache.write": 0, "cache.read": 2136192}]
    tool time: bash 11.6 min
        120s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && nohup python3 ../tools/par_check.py -j 2 test_ail_std_numbers tes
        120s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && setsid bash -c 'python3 ../tools/par_check.py -j 2 test_ail_std_n
        113s bash   cd /tmp/rprobes cat > rev_frac_routes2.py <<'EOF' import numbers from fractions import Fraction  class Half(Fr
         78s bash   cd /home/runner/work/_temp/w2; for t in chain_relax ledger_bin echo_pack; do rm -rf /tmp/cgh_$t /tmp/cgb_$t; A
         63s bash   cd /home/runner/work/_temp/w2; rm -rf /tmp/cgh1 /tmp/cgb1; AIL_NO_CACHE=1 python3 AIL_CURRENT/ail_chatgpt.py c
         57s bash   cd /tmp/rprobes cat > rev_nested2.py <<'EOF' import numbers  class A:     pass  class B:     pass  def main():
         40s bash   date; cd /home/runner/work/_temp/w2; for p in /tmp/rprobes/rev_*.py; do echo "===== $(basename $p)"; timeout 4
         30s bash   sleep 30; tail -8 /tmp/rev_tests.log; pgrep -af par_check.py | head -1; date

FINAL VERDICT: FIX  2026-11-01T18:10:02Z
