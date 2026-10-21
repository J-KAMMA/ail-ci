# DEVLOG

Newest first. Each entry: what changed, why, and the numbers that justify it.

## 2026-10-21 — compile speed: memoise the repeated caller contexts in `_signatures`

**Profiled:** `ail_chatgpt.py compile … --syntax python` with `cProfile`, `AIL_NO_CACHE=1`, on three
`corpus/gdev` programs (small `g16_002` 8 lines, medium `g11_014` 71 lines, largest `g25_034`
166 lines). cProfile only sees the outer wrapper, so the child (`python/pkg-v12/pyc.py`) was profiled
too, and every phase was then re-measured with real timers (median of 5).

Phase shares of wall time (median of 5, `AIL_NO_CACHE=1`):

| phase | g16_002 (small) | g11_014 (medium) | g25_034 (largest) |
|---|---|---|---|
| `cc` (generated-C compile+link, external) | 60 ms / 25% | 2460 ms / 75% | 3130 ms / 88% |
| Python frontend (typed signature fixed point, general path, C emission) | 27 ms / 11% | 615 ms / 19% | 183 ms / 5% |
| imports (`import pyc` 71 ms; `import pyboxed2` ~150 ms on the general path, of which ~70 ms is `cruntime.repr_runtime_for_host`'s 1.1 M-codepoint printability scan) | 102 ms / 42% | 104 ms / 3% | 181 ms / 5% |
| surface rewrite in the wrapper (`python_surface`) + process/copy overhead | 55 ms / 22% | 107 ms / 3% | 74 ms / 2% |

The C compiler is the largest single cost and is untouchable here (it must keep compiling the same
C with the same flags). The largest *avoidable* Python cost is the typed path's signature inference:
`_signatures` = 3.19 s of an 11.55 s frontend over 20 corpus programs, of which `_caller_ctx` is
2.07 s — and 67–70% of that `_caller_ctx` time is an **exact repeat**: the three whole-program
passes (`_propagate_signatures_pass`, `_infer_strparam_pass`, `_plan_clones`) each rebuild a full
"what kind does this expression have" context for every function, once per pass per fixed-point
round, and a round normally leaves most functions' signatures where the previous one did.

**Change:** `pyfunc._caller_ctx_memo` (plus `_SignatureKey`, `_signature_key`). `_caller_ctx` is a
pure function of (the function's AST, `sigs`, `arity_seed`, `classes`); the memo is keyed on the
question (every signature + every arity seed, computed once per pass) and the function's identity,
is cleared on entry to `_signatures` (so it lives for one `_signatures` call, and is dropped past
4096 entries), and the two users that *write* to what they get back (`_borrowed_callback_helper`,
`_to_c_once`'s base context) still call `_caller_ctx` itself.

**Numbers** (full `compile`, median of 5 runs each, `AIL_NO_CACHE=1`, 20 corpus/gdev programs):
wall time 45086 ms → 43637 ms (**-3.2%** overall, median per-program -1.6%; the C compiler dominates
most of them). Frontend only (no `cc`): **-8.2%** over 85 programs, -15% to -19% on the typed-path-heavy
ones (`g17_030` 11.8 s → 10.0 s, `g05_010` 4.06 s → 3.44 s, `g11_014` 562 ms → 459 ms).

**Generated C is unchanged:** byte-identical `.c` for all 85 corpus/gdev programs sampled every 6th
file-plus-baseline (0 of 85 differ by sha256) and for 8 new probes. `test_ail_safetynet`,
`test_ail_files`, `test_ail_corpus_findings3`, `test_ail_unified`, `test_ail_quirks`,
`test_ail_tuples`, `test_ail_unbound` all pass.
