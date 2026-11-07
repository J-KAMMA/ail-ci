# Errors and diagnostics

AIL is written to be read by an agent as much as by a person. This chapter fixes what the compiler
and the runtime say when a program cannot mean what it says, what a caught exception carries, and
how the two sides of a compatibility run are compared.

## ED1 — A refusal is a named build error

**Rule.** A construct outside the language is refused at build time, by name, with the file and
line. The exit status is 2 for a syntax or size error and 3 for a construct outside the subset.
The message names the construct and, where possible, the rewrite.

```text
prog.py:7: exec is not supported: AIL builds whole programs; call the function directly
```

**CPython.** Runs the construct.

**Status.** implemented.

**Proof.** [`docs/LIMITATIONS.md`](../LIMITATIONS.md) conventions; [`docs/CLI.md`](../CLI.md);
`test_ail_corpus_findings3`.

## ED2 — A trap exits 1 and keeps stdout

**Rule.** An uncaught runtime trap or exception exits 1. The text `Kind: message` goes to stderr.
Nothing is rolled back: the stdout written before the trap stays, and files are flushed (MO6)
before the exception text. A caught exception has the same `Kind` and message, and the built-in
`except` clauses that are modelled catch it.

```python
print("before")
1 / 0                         # stdout keeps "before"; stderr says ZeroDivisionError; exit 1
```

**CPython.** The same exit status and the same `Kind: message` line, plus a traceback.

**Status.** implemented.

**Proof.** [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A4, A12; [`docs/CLI.md`](../CLI.md).

## ED3 — No traceback; `--debug` adds a line

**Rule.** An uncaught exception prints no traceback. `--debug` / `AIL_DEBUG=1` adds a single
`raised near file:line` line after the `Kind: message` line. A program that catches the exception
sees the same value with or without `--debug`.

```text
$ ./prog
ZeroDivisionError: division by zero

$ ./prog --debug
ZeroDivisionError: division by zero
raised near prog.py:3
```

**CPython.** Prints a traceback and no `raised near` line.

**Status.** implemented.

**Proof.** [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A4, `C?-job-relrterr4-11042111-1`.

## ED4 — A failed proof says what it kept

**Rule.** When a proof fails, the compiler prints one line per failure:

```text
file:line: could not prove <property>: <reason>; runtime check kept
```

The `<property>` vocabulary is closed: `ownership`, `bounds` or `race-freedom`. The `<reason>`
vocabulary is closed and shared by the analyzer and the prose: `index may be negative`, `list
length may change (length-changing op or unknown call)`, `no length value of this container`,
`sum rule needs the offset at most -1`. `AIL_BCE_EXPLAIN=1` prints the explanation;
`AIL_BCE_AUDIT=1` makes a failed proof exit 86 for an audit run.

```text
prog.py:12: could not prove bounds: index may be negative; runtime check kept
```

**CPython.** Has no proof layer; every operation is checked.

**Status.** implemented.

**Proof.** [`docs/design/SAFETY_PROOF.md`](../design/SAFETY_PROOF.md) section 2.2, 4; `test_ail_safetynet`.

## ED5 — A fallback is one note; `--strict` refuses instead

**Rule.** When the compiler falls back from the typed path to the general path, it prints one
`note: ... built on the general path` line and continues. `--strict` / `AIL_NO_GENERAL=1` refuses
the same program with exit 3 instead. A fallback never changes the answer; it changes the speed
and, in the rows marked general-only, the presence of a difference.

```bash
./prog                       # note: ... built on the general path
AIL_NO_GENERAL=1 ./prog      # exit 3: the same program, refused
```

**CPython.** No typed path, so no fallback note.

**Status.** implemented.

**Proof.** [`docs/CLI.md`](../CLI.md); [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A62.

## ED6 — `ail run --diff` compares against CPython

**Rule.** `ail run --diff prog.py` runs the native binary and CPython 3.12 on the same input and
reports one machine-readable line (or a JSON object under `--json`):

* `same` — stdout and exit status agree;
* `diff` — they differ, with the first differing line;
* `loud stop` — the native run is a declared loud stop (the exit 4 of the comparison mode);
* `timeout` — exit 124 after the deadline.

A documented difference in `DIFFERENCES.md` is reported as a loud stop, not a failure. The
command also names the declared difference id when one applies.

```bash
ail run --diff prog.py -- --flag
```

**CPython.** The reference run.

**Status.** implemented.

**Proof.** [`docs/CLI.md`](../CLI.md); `test_ail_rundiff`; `lab/rundiff/RESULTS.md`.

## ED7 — Which trap text is a promise

**Rule.** The text a caught exception carries is CPython 3.12's for the A12 list (AR11). For the
other runtime-built messages the text is AIL's own and is not a compatibility promise; a program
should not parse it. An uncaught exception's stderr text is never part of the promise beyond
ED2-ED3.

```python
try:
    [][1]
except IndexError as e:
    print(e)                  # list index out of range (A12, promised)
```

**CPython.** The same for A12; different wording elsewhere.

**Status.** partly (the A12 list is promised; the rest is documented per row).

**Proof.** [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A12, A71, C244.

## ED8 — Agent-readable errors are a roadmap item

**Rule.** A structured error format aimed at agents (a machine-readable object with a code, the
construct, a rewrite and the location) is planned. **No `docs/design/AGENT_ERRORS.md` exists in
this tree**, so the current contract is ED1-ED7: a named refusal, a `Kind: message` trap, a
`could not prove` line, the fallback note and the `--diff` line. Do not document a format that is
not here.

```text
# planned, not current: {"code": "E_EXEC", "line": 7, "construct": "exec", ...}
```

**CPython.** Has none.

**Status.** planned.

**Proof.** [`docs/ROADMAP.md`](../ROADMAP.md) P2; the absence of `docs/design/AGENT_ERRORS.md`.
