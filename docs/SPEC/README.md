# The AIL language specification

Status: **first draft, 2026-11-07** (spec version `0.1-draft`, for the compiler on `integ`).
This directory writes down what an AIL program means. It is not a user tutorial and not a
compiler reference: the chapters state rules, the evidence behind them, and where CPython
behaves differently.

## Purpose

AIL reads Python syntax. That is a surface choice: AIs write Python best, so the language they
already write should be the language they can compile. But **the syntax is Python, the semantics
are AIL's own.** "Prints the same as CPython" is a compatibility target, not the definition of the
language.

The central rule:

> A program either has exactly the meaning this specification gives it, or the build refuses it by
> name. It never silently has a different meaning. Where AIL differs from CPython, the difference is
> either a named refusal or a declared difference in [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md).

The owner's decision of 2026-11-07 is the reason for the split: fit the world less, aim to be a
future standard language. Python syntax stays because it is what AI authors and human readers know;
the semantics are written down here so they can be reviewed, versioned and changed deliberately.

## How to read a rule

Every rule has an identifier (`VT2`, `AR1`, `CO3`, ...), a statement, an example, what CPython does
where it differs, a status, and the test or document that shows the status is true.

Status vocabulary:

| status | meaning |
|---|---|
| **implemented** | the compiler does this today on the path named in the rule, and a test or committed result proves it. |
| **partly** | some paths or shapes do this; the rule says which. |
| **planned** | accepted as the language's direction; not built or not verified yet. |
| **refused** | the meaning is defined, but the build refuses the construct by name rather than approximate it. |
| **open** | the specification has not chosen yet. The choices are in [OPEN.md](OPEN.md), marked "owner decision". |

A rule with an owner decision has a source in the repository. A rule whose source is a test names
the module; a rule whose source is a design note links it.

## How the spec is versioned

* The version is the one in the line above (`0.1-draft`). It moves when a chapter gains, loses or
  changes a rule that programs can observe.
* Rule identifiers are stable once published. A rule is not renumbered; a changed rule keeps its
  identifier and gains a note with the date and the change. A removed rule is marked withdrawn,
  not reused.
* A semantic change lands with (a) the code, (b) the rule's status and example, and (c) a
  `DEVLOG` entry. A new or changed difference also lands in
  [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) with a stable id.
* A chapter that is incomplete says so. The long tail of small CPython differences stays in
  `docs/spec/DIFFERENCES.md` (rows `A*` and `C*`); this specification states the rules those rows
  follow and points at them.

## Chapters

| chapter | what it fixes |
|---|---|
| [INVENTORY.md](INVENTORY.md) | the numbered rules collected from across the repository, each with its source |
| [values-and-types.md](values-and-types.md) | int, float, bool, str, bytes, None, containers, classes |
| [arithmetic-and-errors.md](arithmetic-and-errors.md) | operations, traps, special values, message text |
| [evaluation-order.md](evaluation-order.md) | left-to-right order, determinism, iteration, clocks |
| [memory-and-ownership.md](memory-and-ownership.md) | aliasing, copies, identity, buffers, file lifetime |
| [concurrency.md](concurrency.md) | the lock, typed parallel regions, race rules D1-D5 |
| [modules-and-ffi.md](modules-and-ffi.md) | whole-program modules, the stdlib subset, C FFI, the hybrid |
| [errors-and-diagnostics.md](errors-and-diagnostics.md) | refusals, traps, agent-readable output, `--diff` |
| [compatibility.md](compatibility.md) | what "same as CPython" guarantees and what a compatibility mode means |
| [OPEN.md](OPEN.md) | questions the specification must still decide (owner decisions) |

## Evidence rule

A rule is **implemented** only when a test, a committed result file, or a probe named in the rule
shows it. A doc statement alone is not evidence. The main evidence sets are:

* `AIL_CURRENT/test_ail_*.py` modules and their committed output;
* [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md), which records every declared difference and
  the test that covers it;
* [`docs/LIMITATIONS.md`](../LIMITATIONS.md) and `lab/limits/expected.json`, which pin the limits a
  user meets first;
* [`docs/MIGRATING.md`](../MIGRATING.md) and `lab/migrating/RESULTS.md`, which run every declared
  difference against CPython 3.12;
* `lab/corpus`, `lab/compare`, `lab/errux`, `lab/proof` and the daily fuzz results.

Where this draft is unsure, it says so rather than guessing. The open questions are in
[OPEN.md](OPEN.md).
