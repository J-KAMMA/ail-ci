## 2026-11-09 -- wedge3d: real-library breadth for the observed-type hybrid (job-wedge3d-11091228)

Measured the `job-obs5-op1109` hybrid (commit 69e2dcd0) on python-dateutil 2.9.0.post0
(`dateutil.parser.parse`, 50,000 ISO strings) and ahocorapy 1.8.0 (500 patterns over 19.2 MB)
against PyPy 3.10.16 and native rewrites ciso8601 2.3.3 (C) and ahocorasick_rs 1.0.3 (Rust).
The hybrid accelerated 0 of 61 dateutil definitions and 0 of 20 ahocorapy definitions, with and
without `ail_observe.py annotate`; it ran at CPython speed (1.011x and 1.008x) while native ran
7.577x and 8.355x faster.  Hot paths are blocked structurally: dateutil's tokenizer/parser are
methods on classes with bases/class attributes, and ahocorapy's search methods read
`self._zero_state`, a `State` object with no supported field kind.  All workload and probe
outputs are byte-identical to CPython.  No compiler, runtime or AIL test module changed; work is
confined to `lab/wedge3/wedge3d/`.  Details: `lab/wedge3/wedge3d/RESULTS.md`, data:
`lab/wedge3/wedge3d/results.json`.
