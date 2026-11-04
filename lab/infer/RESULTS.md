# infer s1 results

Machine: GitHub Actions runner, 4 cores, 15 GiB RAM, Linux x86-64 (AVX2/AVX512).
Both programs: one thread, F32 weights, the same 64-token prompt, 16 greedy
tokens. AIL is float64 arithmetic; llama.cpp is float32. Medians of 5 runs.

`zenz-v3.2-small` is a 90M-parameter GPT-2. The source is the public Q5_K_M GGUF,
dequantized once to F32, so AIL, `ref.py` and llama.cpp all read identical f32
values.

## Correctness

| check | result |
| --- | --- |
| AIL greedy 16 == `ref.py` greedy 16 | yes (exact ids) |
| AIL greedy 16 == llama.cpp greedy 16 | yes (exact ids) |
| AIL top-5 ids/values == `ref.py` | yes (ids equal, 9 printed significant digits equal) |
| 1-token prompt, AIL vs `ref.py` | top-5 and 16 greedy ids equal |
| 1024-token prompt, AIL vs `ref.py` | top-5 ids/values equal |

Greedy ids (all three programs):
`244 249 248 172 120 202 435 354 280 386 259 623 241 435 354 280`.

## Timing

AIL phases are wall-clock `/usr/bin/time` medians. `load` reads and decodes all
149 f32 tensors (0.82 s), `prefill` is the 64-token prompt after subtracting
`load`, and `decode` is 16 one-token steps after subtracting `load+prefill`.
llama.cpp numbers are its own report lines (`prompt eval time`, `eval time`).

| phase | AIL | llama.cpp F32 | ratio AIL / llama |
| --- | ---: | ---: | ---: |
| prefill 64 tokens | 8.52 s | 0.150 s | **56.7x** |
| decode 16 tokens | 2.09 s (16 steps) | 0.194 s (15 evals*) | **10.8x** |
| decode, per token | 130.6 ms | 12.93 ms | **10.1x** |
| total wall, load included | 11.43 s | 0.40 s | **28.6x** |

\* llama.cpp produces the first generated token from the prefill logits, so its
report has 15 eval runs for 16 generated tokens. The per-token row is the fair
decode comparison.

| resource | AIL | llama.cpp |
| --- | ---: | ---: |
| peak RSS (decode run) | 1,108,044 KiB (1.06 GiB) | 427,444 KiB (417 MiB) |
| binary size | 94,544 B (`gpt2`) | 1,898,560 B (`llama-cli`); 27,120 B (`llama-simple`) |
| AIL compile time | 8.32 s (`--strict`, warm C compiler cache) | n/a |

## Where the time goes (findings)

AIL is 56.7x slower in prefill and 10.1x per decoded token, so it is well past
the 2x line. `perf record` is denied on this runner (`perf_event_paranoid`), so
this is from the generated C (`--debug-dir`), which is enough to name the causes:

1. **Prefill is not batched.** `gpt2.py` feeds the 64 prompt tokens one at a time
   through the same one-token path as decode (64 x 130 ms = 8.3 s). llama.cpp
   evaluates the prompt as one 64-token batch (2.35 ms/token) but decodes one
   token at a time (12.9 ms/token). This explains why the prefill ratio (56.7x)
   is much worse than the decode ratio (10.1x).
2. **The matmul inner loop is scalar with checked indexing.** In
   `linear__irl` (generated `program.c`) every weight read is
   `ail_flist_view_get(v_w.p, v_w.n, k)`, a function call with a bounds check,
   and every index add/multiply is `ck_add`/`ck_mul`, which checks int64
   overflow. There is one `double` multiply-add per branch, no SIMD, no loop
   unrolling. `-O2` cannot vectorize the call-per-element loop.
3. **Every `linear()` call snapshots its list arguments.** The generated call site
   is `ail_flist_snapshot(...)` for `qkv_w[layer]`, `o_w[layer]`, `up_w[layer]`,
   `down_w[layer]`, etc. That is ~7.1M doubles (57 MiB) copied per layer-token
   triplet, or ~3.6 GiB of copying for the 64-token prefill, on top of the
   arithmetic. Nested `list[list[float]]` indexing triggers the copy; a flat
   weight list indexed with an explicit base offset would avoid it.
4. **All arithmetic is float64**, while llama.cpp uses float32 and FMA. This is
   not the main cost (AIL is not memory-bandwidth bound), but it doubles the
   bytes moved and prevents the compiler from using FMA in the same way.

The fixes, if this becomes a benchmark rather than a showcase, are: batch the
prompt matmuls, pass weights as flat lists (or borrows) without snapshotting,
get a typed f32 array path, and let the inner loop be a plain C `for` over
`double*` (or `float*`) with no per-element bounds/overflow checks.
