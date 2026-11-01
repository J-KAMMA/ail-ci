**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
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


--- ORIGINAL TASK ---
**Coverage: make real programs that use the CPython stdlib module `numbers` build and print exactly what CPython prints.**

1. Write 12 small realistic programs, each 15–60 lines, that use `numbers` the way typical code does: its most common functions and classes, the common argument forms and keyword arguments, and its edge cases (empty inputs, errors that the program catches). Put them in lab/stdlib/numbers/.
2. Build each one in the default mode (`ail_chatgpt.py compile X.py --syntax python`). Record the result for each: typed / general / refused, with the first refusal message, in lab/stdlib/numbers/RESULTS.md.
3. Fix the reasons, starting with the one that blocks the most programs, until at least 9 of the 12 build. Each built program must match CPython's stdout and exit code. Fix the compiler, runtime or prelude, never the programs.
4. A reason that needs a big new feature is out of scope for this task: leave it, and write it in RESULTS.md as a follow-up with the exact refusal text.

Rules:
- Never wrap ints silently. Default ints are int64, and overflow stops loudly.
- The generated C of the 10 lab/compare tasks must stay byte-identical.
- Add the passing programs as a test (a new test_ail_std_numbers.py registered in tests.d), and compare them with CPython in the test.
- Run that test plus test_ail_safetynet, run `python3 tools/update_manifest.py`, and commit.

**Rules for every job.**
- **Load:** you are one of up to five agents on a 16 GB PC. Keep local parallelism at 2 (`-j 2`) and never run the whole suite; the full suite runs on CI after merge.
- **Commits:** commit with explicit `git add` on your branch. Messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- **Forbidden:** push, stash, rebase, reset, and deletion outside /tmp.
- **Records:**
  - New DIFFERENCES rows use placeholder ids `C?-<your branch>-N`.
  - Add a DEVLOG entry at the top with today's date.
  - Register a new test module: if `AIL_CURRENT/tests.d/` exists, add `AIL_CURRENT/tests.d/<module>.txt` containing the module
    name and do NOT edit the tuple in `ail_check.py`; otherwise append it to the `MODULES` tuple.
  - `git add` new files, run `python3 tools/update_manifest.py`, then `--check`. Do not hand-edit `MANIFEST.json` or `manifest.d/`.
- **Required tests:** the targeted modules for what you touch, plus test_ail_safetynet, test_ail_files and test_ail_corpus_findings3. Run them on your final commit, not an earlier one.
- **Mandatory self-check before you report.** A reviewer will repeat it, and past reports were wrong about half the time.
  1. Write probe programs in /tmp/probes/ for every behaviour you changed. Cover the boundaries your implementation implies, not only the example: types, widths, empty, negative, aliasing, values reaching the code through an argument, a list item, an attribute and a dict value, and both builds.
  2. Run each probe with `bash ~/tools/cmp.sh /tmp/probes/<p>.py $PWD`.
  3. Every probe must match CPython or be refused by name.
  4. List the probes and their results in the report.
- **Never claim something works unless a probe or test you ran shows it.** If you did not verify something, say so.
- **Tokens:** use grep -n, narrow reads, and `tail` on long logs.
- **Budget:** stop at the budget note, leaving a committed, consistent state.
- **Report:** keep it brief, with numbers.
- Test data: email addresses only on example.com / example.org (the public export audit rejects any other domain).

**Work in few steps** (each step costs model time):
- Write all probe programs first, then run them together with one command, for example a loop over `bash ~/tools/cmp.sh`, instead of one command per program.
- Search only inside the repository (`grep -rn ... AIL_CURRENT tools`), never across `/home` or `/tmp`.
- Read a file once, using a range that is large enough, instead of many small reads.
- Do not re-run a test that already passed unless you changed code since.

**Where you run:** a GitHub Actions runner (4 cores). Commit your work on the current branch; do not push.
