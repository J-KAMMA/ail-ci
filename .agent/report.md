Done. Final report:

## Profile (cProfile, `AIL_NO_CACHE=1`, median of 5 runs each)

`cProfile` on the wrapper only sees the child process, so `python/pkg-v12/pyc.py` was profiled too and every phase re-measured with real timers.

| phase | g16_002 (small, 8 ln) 244 ms | g11_014 (medium, 71 ln) 3286 ms | g25_034 (largest, 166 ln) 3568 ms |
|---|---|---|---|
| `cc` — compile+link of the generated C (external) | 60 ms (25%) | 2460 ms (75%) | 3130 ms (88%) |
| imports (child `import pyc` 71 ms; `import pyboxed2` ~150 ms on the general path, ~70 ms of it `cruntime.repr_runtime_for_host`'s 1.1 M-codepoint scan) | 102 ms (42%) | 104 ms (3%) | 181 ms (5%) |
| Python frontend (typed signature fixed point / general path + C emission) | 27 ms (11%) | 615 ms (19%) | 183 ms (5%) |
| wrapper surface rewrite + process/copy overhead | 55 ms (22%) | 107 ms (3%) | 74 ms (2%) |

`cc` is untouchable (same C, same flags). Largest avoidable Python cost: the typed path's signature inference — over 20 corpus programs `_signatures` is 3.19 s of the 11.55 s frontend, `_caller_ctx` 2.07 s, and **67–70 % of that `_caller_ctx` time is an exact repeat**: `_propagate_signatures_pass`, `_infer_strparam_pass` and `_plan_clones` each rebuild a full per-function type context once per pass per fixed-point round, and a round usually leaves most functions' signatures unchanged.

## Fix (commit `411727c`)

`pyfunc._caller_ctx_memo` + `_SignatureKey`: memo keyed on the question (all signatures + all arity seeds, built once per pass) and the function's identity (`is`-checked), cleared on entry to `_signatures`, dropped past 4096 entries; a hit re-points `ctx.funcs` at the live `sigs`. The two users that write to their ctx keep calling `_caller_ctx`. DEVLOG entry added, `update_manifest.py` + `--check` clean.

## Time

- Full `compile`, median of 5, 20 corpus programs: **45086 → 43637 ms (−3.2 % total, median per-program −1.6 %)** — `cc` dominates.
- Frontend only (no `cc`): **−8.2 %** over 85 programs; −19 % `g11_014` (562→459 ms), −16 % `g05_010` (4.06→3.44 s), −15 % `g17_030` (11.8→10.0 s).

## C unchanged

85 corpus/gdev programs (every 6th file) before vs after: **0 of 85 differ** by sha256 of the emitted `.c`; 8 probe `.c` files identical; re-compiled g16_002/g25_034 executables hash `905a03f2…`/`bbc1d641…`, same as before the change.

## Probes (`bash ~/tools/cmp.sh`, both builds `g`/`d`) — all identical to CPython

`p1_paramprop` (param kinds via call sites, empty list, negative) ✔g/d · `p2_retchain` (3-hop float return chain) ✔ · `p3_clones` (same helper with int and float) ✔ · `p4_strparam` (unannotated str / list-of-str param) ✔ · `p5_structattr` (class instance via param, attribute, struct list) ✔ · `p6_dictvalues` (values via dict value, list item, arg, `len`, empty) ✔ · `p7_rows` (list-of-tuples arity seeds) ✔ · `p8b` (bounded recursion, mutual bool returns) ✔. (`p8_recursion` with unbounded recursion segfaults in the forced general-path `g` build — **pre-existing**: the base tree segfaults identically; the default `d` build matches CPython.)

Tests on the final commit: `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_unified`, `test_ail_quirks`, `test_ail_tuples`, `test_ail_unbound` — 7 modules, 0 failed (`-j 2`). Not run: the whole suite.
[cost $0.44, turns 191]
