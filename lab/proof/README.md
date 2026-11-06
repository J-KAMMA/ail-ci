# lab/proof — how much of real Python does the compiler already prove safe?

`census.py` asks the compiler's own analyses three questions about every typed function of three
corpora and writes one JSON record per function plus a summary.  It edits nothing: every analysis
is imported and called.

    python3 lab/proof/census.py --jobs 2 [-o lab/proof/census.json] [--limit N]

Numbers: `RESULTS.md` (five headline percentages) and `census.json` (every function and blocker).
Design: `docs/design/SAFETY_PROOF.md`.

## Corpora

| corpus | programs | what it is |
|---|---:|---|
| `compare` | 20 | `lab/compare/src/*/typed.py` (the annotated AIL form of the ten novel tasks) and `main.py` (the CPython source of the same tasks) |
| `pyproof` | 55 | every program in `lab/pyproof/programs.txt`, the repository's own typed-reach list |
| `gdev` | 200 | the first 200 of `corpus/gdev`, the corpus the C-diff checks (`lab/devcc`, `lab/tccprobe`) build |
| `race` | 31 | `lab/race/safe` and `lab/race/racy`, for the race section only |

A program is prepared exactly as `ail_chatgpt.py compile --syntax python` prepares it
(`ail_chatgpt._load_sources` + `shadowing.rename_all`), then built with `pyc.build` and a no-op C
compiler (`PIPE_CC=/bin/true`): the census measures the Python front end, the IR and the emitter,
not gcc.  Line numbers are the prepared source's; for a program the typed-parallel lowering
rewrites they can differ from the file (that affects the race corpus only).

## What is measured, and with which API

* **ownership** — `ir.borrow.analyze(tree)`: the set of parameters rc2 borrows.  A parameter is a
  *reference* when its annotation names a class, `dict`, `set`, `bytearray` or a list of
  non-scalars.  A borrowed reference parameter needs 0 run-time RC operations, an unborrowed one
  needs 2 (retain on entry, release on exit); that is the numerator and denominator.
  `full` = no reference parameter needs a pair, `part` = some do, `none` = all do.
* **bounds** — the pass statistics `ir/driver.py` records in `AIL_IR_STATS`:
  `idx_total`, `idx_legacy_proven`, `idx_ssa_proven` from `ir/passes/ranges.py`.  Removed =
  legacy_proven + ssa_proven, kept = the rest.  A function the IR does not lower has no record;
  its AST index sites are counted as kept and reported as the blocker `no-index-api`.
  `AIL_BCE_EXPLAIN` supplies the per-site reason for every site left checked.
* **races** — `typedpar.rewrite_text` (which fork-join shapes are lowered, and the notes for the
  ones that are not) and `parallel._Body` (the body proof).  Each access to shared state is
  counted `safe`, `refused` (by rule D1-D5, named in the script and in the design doc) or
  `unknown`.

## Blocker labels

The *decision* is always the analysis'; the label names the rule that produced it, by the same
predicates the module's docstring states (`_param_blocker` mirrors `ir/borrow.py`; the bounds
reasons are `ranges.fail_reason`'s own strings; the lowering reason is `AIL_IR_STATS`' `reason`;
the race rules are `parallel.py`/`typedpar.py`).  Where an analysis has no API to answer, the
census records `NO_API` (see the module docstring) instead of patching it.

## Notes on the numbers

* A program the typed path refuses is built by the general path and its functions are reported
  `boxed`; if both paths refuse, its functions are counted with the blocker `program refused`.
* `pyc.last_fallback_reason` is captured per program, so the general-path blockers can be ranked
  by the reason the typed path gave.
* The identity of the `ail_obj_store`/`_release` sites the emitter actually writes is not exposed
  per function (blocker `no-rc-api`), which is why ownership is counted per parameter reference.
