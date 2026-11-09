## 2026-11-09 -- wedge3d: fix review defects (job-wedge3d-11091228)

Review fixes only; new timings and corrected counts are in `results.json` and `RESULTS.md`.
- Function totals now come from the installed library's hot module before `install_hybrid`
  overwrites it: dateutil `_parser.py` is 58 defs / 2 top-level / 54 methods (was reported as
  61 / 4 / 54) and ahocorapy `keywordtree.py` is 17 / 0 / 17 (was 20 / 2 / 17).
- Refusal profiling now matches the exact resolved hot-module path, so stdlib
  `re/_parser.py` no longer pollutes dateutil's reasons (`hot_self_s` 2.447 -> 2.473 includes
  only dateutil functions; the old 2.447 included 0.00036 s of `re`).
- `normalise_reason` strips one suffix, not both, so the ahocorapy reason is stored as
  "method: calls a method that stays in CPython" instead of the truncated
  "method: calls a method that".
- Re-ran both edge probes across CPython, PyPy, native, hybrid and hybrid+obs: all match.

## 2026-11-09 -- wedge3d: real-library breadth for the observed-type hybrid (job-wedge3d-11091228)

Measured the `job-obs5-op1109` hybrid (commit 69e2dcd0) on python-dateutil 2.9.0.post0
(`dateutil.parser.parse`, 50,000 ISO strings) and ahocorapy 1.8.0 (500 patterns over 19.2 MB)
against PyPy 3.10.16 and native rewrites ciso8601 2.3.3 (C) and ahocorasick_rs 1.0.3 (Rust).
The hybrid accelerated 0 of 58 dateutil definitions and 0 of 17 ahocorapy definitions, with and
without `ail_observe.py annotate`; it ran at CPython speed (1.001x and 1.001x) while native ran
7.536x and 8.103x faster.  Hot paths are blocked structurally: dateutil's tokenizer/parser are
methods on classes with bases/class attributes, and ahocorapy's search methods read
`self._zero_state`, a `State` object with no supported field kind.  All workload and probe
outputs are byte-identical to CPython.  No compiler, runtime or AIL test module changed; work is
confined to `lab/wedge3/wedge3d/`.  Details: `lab/wedge3/wedge3d/RESULTS.md`, data:
`lab/wedge3/wedge3d/results.json`.
