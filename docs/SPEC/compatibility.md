# Compatibility with CPython

AIL reads Python. The natural question is how close its answers are to CPython's. This chapter
fixes what "same as CPython" means here, what is promised, and why compatibility is a mode rather
than the definition of the language.

## CM1 — The default build is AIL semantics

**Rule.** The default build implements this specification. Where a rule is silent and no declared
difference applies, the general path answers with CPython 3.12's value. That is a fallback
guarantee, not the definition: a program is an AIL program first, and the CPython answer is what
AIL promises when it has no rule of its own.

```python
print(sorted([3, 1, 2]))       # [1, 2, 3]; both languages, and no difference row
```

**CPython.** The reference for the silent rows only.

**Status.** implemented.

**Proof.** [`docs/WHY.md`](../WHY.md); [`docs/MIGRATING.md`](../MIGRATING.md);
[`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) introduction.

## CM2 — A CPython-identical mode is a target, not the language

**Rule.** "Same output as CPython" is a compatibility target. Today there are two tools that
approach it and neither is a language mode:

* `ail run --diff` runs the native binary and CPython on the same input and reports `same`,
  `diff`, `loud stop` or `timeout` (ED6);
* `ail build --cpython` builds a hybrid in which selected functions run natively and the rest
  runs on CPython, with the original function as the fallback at every boundary (MF7).

A full `--compat cpython` semantics switch (where every declared difference becomes CPython's
answer, including arbitrary-precision ints, hash-ordered sets, tracebacks and `None` for an
unmatched `re` group) **does not exist yet**. It is open question O11.

```bash
ail run --diff prog.py        # oracle comparison
ail build --cpython prog.py -o prog   # hybrid, not a semantics switch
```

**CPython.** The target.

**Status.** partly (the oracle and the hybrid exist; the switch does not).

**Proof.** [`docs/CLI.md`](../CLI.md); [`docs/design/CPYTHON_HYBRID.md`](../design/CPYTHON_HYBRID.md);
[OPEN.md](OPEN.md) O11.

## CM3 — Every difference is named or declared

**Rule.** A divergence from CPython is exactly one of:

1. a **refusal**: the build stops by name (ED1);
2. a **loud stop**: the program stops by name at run time (ED2);
3. a **declared difference**: a row in `docs/spec/DIFFERENCES.md` with an id (`A*` or `C*`) and
   the test that covers it.

A silent difference is a bug in AIL. A program that relies on CPython's answer must either keep
to the rows where AIL promises that answer or use a compatibility tool of CM2.

```text
1. input:  print(2 ** 100)        -> refusal (int64), A1
2. input:  print([1][5])          -> loud stop, A4
3. input:  print(sum([0.1] * 10)) -> declared same, C1
```

**CPython.** May differ in the row's direction without saying so.

**Status.** implemented as the policy; the coverage of every row by a test is the thing to audit.

**Proof.** [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) introduction and IDs; the
migrating samples in [`docs/MIGRATING.md`](../MIGRATING.md).

## CM4 — The build modes

**Rule.** The modes a program can be built or run in are fixed:

| mode | how | meaning |
|---|---|---|
| default | `ail build` / `ail run` | typed path with general fallback |
| strict | `--strict` / `AIL_NO_GENERAL=1` | typed only; a fallback is a refusal (ED5) |
| exact ints | `--exact-int` / `AIL_EXACT_INT=1` | arbitrary-precision ints (VT2) |
| forced general | `AIL_UNIFIED_FORCE=1` | measurement and fallback tests, not for shipping |
| hybrid | `ail build --cpython` | selected functions native, rest on CPython (MF7) |
| oracle | `ail run --diff` | native vs CPython comparison (ED6) |

A mode changes representation or checking; it does not change the language's rules except where a
rule says the mode changes the answer (VT2, ED5). A program's output may differ between default
and forced general only in the rows marked general-only in `DIFFERENCES.md`.

```bash
AIL_EXACT_INT=1 ./prog
AIL_NO_GENERAL=1 ./prog
```

**CPython.** Has one mode.

**Status.** implemented.

**Proof.** [`docs/CLI.md`](../CLI.md); [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A62, A65.

## CM5 — The promise is stdout and exit status

**Rule.** The compatibility promise covers the program's stdout and its exit status. It does not
cover stderr wording (beyond ED2-ED3 and the A12 trap text), object ids and addresses, hash order,
thread ids, or timing. A difference row that changes stdout or the exit status is a real
difference; one that changes only the protected text is not.

```python
print(id(x))                  # outside the promise
print(x)                      # inside it
```

**CPython.** The same boundary is not stated; CPython's `repr` of a default object exposes the
address.

**Status.** implemented.

**Proof.** [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A2, A4, A39, A72.

## CM6 — Compatibility is measured, not claimed

**Rule.** A compatibility claim quotes a committed result file: `lab/compare`, `lab/corpus`,
`lab/migrating/RESULTS.md`, the daily fuzz and `lab/limits`. A number in a document names the
task set and the commit it came from. A claim without a result file is not a claim.

```text
lab/compare/history/<run>/               # the per-task result files
lab/migrating/RESULTS.md                 # the declared-difference samples
lab/corpus/RESULTS.md                    # the corpus run
```

**CPython.** No such measurement.

**Status.** implemented as policy.

**Proof.** [`docs/WHY.md`](../WHY.md); [`docs/COMPARISON.md`](../COMPARISON.md);
`lab/migrating/RESULTS.md`.

## CM7 — A number is dated; a stale number is corrected

**Rule.** Every number in the specification or the roadmap is attached to the set of programs and
the commit that produced it. When a change makes a number stale, the number is re-measured and
the document corrected; it is not carried forward "because it was true". This is why the roadmap
cites result files instead of paraphrasing them.

```text
# correct: "98.9% of the corpus, lab/corpus/RESULTS.md at <commit>"
# wrong:   "almost all programs"
```

**CPython.** Not applicable.

**Status.** implemented as policy.

**Proof.** [`docs/ROADMAP.md`](../ROADMAP.md); [`docs/COMPARISON.md`](../COMPARISON.md).
