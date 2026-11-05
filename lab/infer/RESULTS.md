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
| 1-token prompt, AIL vs llama.cpp | 16 greedy ids equal (reviewer-confirmed) |
| 1024-token prompt, AIL vs `ref.py` | top-5 ids/values equal (`STEPS=0`); both refuse a decode past the context by name, exit 2 |

llama.cpp prints no logits, so its top-5 is not compared for any prompt; only the
greedy ids are checked against it (64-token and 1-token prompts). No 1024-token
llama.cpp run was made.

`tokens1024.txt` is `tokens.txt` repeated 16 times (1024 ids, exactly the context
length). The default 16 decode steps do not fit there, so with no third argument
the program prints the prompt's top-5 and then refuses with a named context error
on stderr (exit 2); `STEPS=0` stops after the top-5. The 1-token prompt was also
run as the same `gpt2.py` program under CPython and matched the compiled output.

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

The llama.cpp column is the `llama-cli` report with `-t 1`. `llama-simple` has no
thread option and uses ggml's default of 4 threads, so its report here (73 ms
prompt eval, 10.1 ms/token over 15 evals) is not a one-thread comparison and is
not used in the table. The ratio depends on the harness and the thread count; the
AIL numbers do not change.

| resource | AIL | llama.cpp |
| --- | ---: | ---: |
| peak RSS (decode run) | 1,108,044 KiB (1.06 GiB) | 427,444 KiB (417 MiB) |
| binary size | 106,816 B (`gpt2`) | 1,898,560 B (`llama-cli`); 27,120 B (`llama-simple`) |
| AIL compile time | 8.34 s (`--strict`, `AIL_NO_CACHE=1`; 0.57 s warm) | n/a |

## Tokens per second (`bench.sh`)

One command, one table, medians of 5: `bash lab/infer/bench.sh`. Same runner
family as above but a later, noticeably slower allocation of it - llama.cpp's
decode is 30.1 ms/forward here against 12.93 ms in the table above, and AIL's
is 263.7 ms against 130.6 ms, so read the ratios, not the absolute numbers.
Both programs see `tokens.txt` (64 ids) and the same F32 weights; AIL is the
default (release) compile, `gpt2.py` needs no `--strict` flag it does not
already satisfy (the `--strict` and default binaries are byte-identical).

| program | threads | prefill tok/s | decode tok/s | peak RSS | binary |
| --- | ---: | ---: | ---: | ---: | ---: |
| AIL `gpt2.py`, default build | 1 | 3.84 | 3.79 | 1053 MiB | 111,120 B |
| llama.cpp `llama-cli` | 1 | **462.90** | **33.17** | 417 MiB | 1,898,560 B |
| llama.cpp `llama-cli`, context row | 4 | 298.70 | 7.91 | 417 MiB | 1,898,560 B |

| phase (medians of 5) | AIL | llama.cpp `-t 1` | ratio |
| --- | ---: | ---: | ---: |
| prefill, 64 tokens | 16.680 s (260.6 ms/token) | 138.2 ms (2.16 ms/token) | **120.5x** |
| decode, per forward | 263.7 ms | 30.15 ms | **8.75x** |
| load weights | 1.16 s | n/a | |
| peak RSS | 1053 MiB | 417 MiB | 2.5x |
| binary size | 111,120 B | 1,898,560 B | 0.06x |

How the two decode tok/s are counted: AIL runs 16 decode forwards for its 16
tokens (the last one's logits are never used); llama.cpp's first generated
token comes out of the prefill, so its own report has 15 eval runs for 16
tokens. Each row divides by the number of forwards it actually ran, so the
numbers are per-forward throughput on both sides.

The `-t 4` row is context only and, on this runner, slower than one thread:
the four vCPUs are shared and the per-run spread was 75-549 prefill tok/s, so
it is not a speedup claim and not part of the headline. Greedy ids were equal
to `ref.py` and to `llama-cli` on all 5 runs for both `-t 1` and `-t 4`; the
harness prints both id lists and exits non-zero if any run differs.
llama.cpp prints generated text rather than ids, so its ids are recovered with
`llama-tokenize` on the generated text (same model, `--no-bos`); that
round-trip is checked to be 16 ids every run.

The absolute gap from the table above is the machine: AIL and llama.cpp both
slowed by roughly 2.3x on this allocation, so the AIL/llama ratio is the same
story (prefill ~2x worse than before, decode slightly better). The phase
sizes are unchanged.

## Profile (`profile.sh`)

`perf record` is denied on the GitHub runner (`perf_event_paranoid=4`, no
`CAP_PERFMON`), so `profile.sh` falls back to
`valgrind --tool=callgrind` on a one-token prompt plus 4 decode forwards -
five copies of the same one-token forward that prefill and decode both use.
The binary is the `--debug` build (`-g -O0`, `#line` back to `gpt2.py`), which
is what makes the source-line column possible; the callgrind shares are of
that `-O0` build, so they show where the work is, not the exact `-O2` split.

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
3. **The per-layer `linear()` calls snapshot their list arguments.** The generated
   call sites take an `ail_flist_snapshot(...)` copy of every list argument: per
   layer the four weight matrices `qkv_w[layer]`, `o_w[layer]`, `up_w[layer]` and
   `down_w[layer]`, their four bias lists, and the four `attn_norm` / `ffn_norm`
   weight and bias lists. That is 7,087,872 doubles (54.07 MiB, 56.7 MB) copied
   per layer-token, or ~40.6 GiB (43.5 GB) for the 12-layer x 64-token prefill, on
   top of the arithmetic. Nested `list[list[float]]` indexing triggers the copy; a
   flat weight list indexed with an explicit base offset would avoid it. The final
   head call passes `head_w`/`zero_bias` directly, so it is not part of this copy
   volume.
4. **All arithmetic is float64**, while llama.cpp uses float32 and FMA. This is
   not the main cost (AIL is not memory-bandwidth bound), but it doubles the
   bytes moved and prevents the compiler from using FMA in the same way.

The fixes, if this becomes a benchmark rather than a showcase, are: batch the
prompt matmuls, pass weights as flat lists (or borrows) without snapshotting,
get a typed f32 array path, and let the inner loop be a plain C `for` over
`double*` (or `float*`) with no per-element bounds/overflow checks.
