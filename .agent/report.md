# job job-cpyhyb2c-11041014  started 2026-11-04T01:16:51Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model commandcode/deepseek-v4.1-flash]
Done. Here's the report.

## Result

The cpyhyb2b work was not on `origin/integ`, but it was already applied verbatim on this branch as `81a29a1` (byte-identical hybrid module, test, and `lab/hybrid/` files to `origin/job-cpyhyb2b-11040506`), so I verified and finished it rather than re-applying. `AIL_CURRENT/ail_chatgpt.py`, `packaging/` and `pkg-v12/` are untouched.

## Numbers

- **40/40 programs match CPython** (stdout, exit status, last stderr line; 60 s timeout). Fresh 2026-11-04 run reproduced the prior result exactly: same 1 accelerated function (`reverse_words` in `t079.py`) and same 7 functions kept in Python with reasons.
- **10/10 `program.c` identical to `origin/integ` (`133ca78`)** — 8 identical files, 2 identical refusals (`tally_lang`, `tree_fold`).
- **Wall time, median of 5** on the 10 compare tasks: hybrid/python ratio within 1% on 8 tasks (`chain_relax` 12.6 s vs 16.6 s, `tree_fold` 17.8 s vs 21.5 s under shared-runner load). `echo_pack` CPython and hybrid both `MemoryError` under the 1.5 GB cap; standalone fits. Instructions unavailable (`perf_event_open: Permission denied`).

## Tests

- `test_ail_cpython_hybrid` 7/7, `test_ail_safetynet` 5/5, `test_ail_files` 18 (1 skip), `test_ail_corpus_findings3` 2/2. (Safetynet fails only under `ulimit -v 1500000` on `S4_generators_gc`; it passes without the cap, as CI runs it.)
- `update_manifest.py --check` exits 0.

## Probes

- int64 edges via argument/list item/attribute/dict value, arithmetic and return overflow, float/int mismatch, empty/negative, empty/non-ASCII/lone-surrogate strings: **match**, 9 native functions.
- mutation/two-list/subnormal floats: **match**, 3 native.
- bool literal where `int` is annotated: analysis refuses the whole program (build-time conservatism) but output **matches** CPython.
- standalone default + `AIL_UNIFIED_FORCE=1` on out-of-int64 text/arithmetic: **refused by name** (`OverflowError ... --exact-int`).

## Commits

`46cc1ef` re-verification numbers + `926c3f0` boundary probes (both docs only). Not pushed, per the "do not push" runner rule. All 20 shards were not run (full suite is CI-only).
[commandcode stop=end_turn turns=85 out_tokens=39260]

## review 0 failed to run: [model opencode/deepseek-v4.1-flash-free] 

## review 0
[model opencode/deepseek-v4.1-flash-free]

FINAL VERDICT: ERROR  2026-11-04T05:45:06Z
