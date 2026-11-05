# Why AIL

AIL is a small language that reads Python syntax. Type annotations are optional. The compiler turns a program into C, then into one executable, so it starts without an interpreter and ships as a single file. Where AIL cannot prove that Python's behaviour is kept, it refuses the program by name instead of guessing.

This page states the release 0.1 claim — Python syntax, Rust-level speed, safe binaries — and shows where each part holds today and where it does not. [source: docs/ROADMAP.md](ROADMAP.md)

Every number below is copied from a committed result file, linked on the same line.

## Speed

- A typed 256 by 256 matrix multiply takes 18 ms. The same C takes 32 ms, and CPython takes 1453 ms, which is 80.7x slower. [source: lab/array/RESULTS.md](../lab/array/RESULTS.md)
- `mandelbrot` takes 92 ms against CPython's 1826 ms, 19.75x faster. [source: examples/algos/RESULTS.md](../examples/algos/RESULTS.md)
- On the compare-lab tasks AIL is faster than Rust on 6/10. `ledger_bin` takes 840 ms against 2833 ms (0.30x), and `echo_pack` takes 934 ms against 1895 ms (0.49x). [source: docs/COMPARISON.md](COMPARISON.md)
- The typed `fannkuch` takes 0.184 s against CPython's 4.953 s, 27x faster. [source: lab/pyperf/RESULTS.md](../lab/pyperf/RESULTS.md)
- Exact big-integer programs improve from a 1.1009 geomean to 0.9990, a 9.3 % gain. [source: lab/bigbench/RESULTS.md](../lab/bigbench/RESULTS.md)

## Binary size and disk

- Across the ten compare-lab tasks AIL binaries are 34–102 KiB against Rust's 4450–4518 KiB. AIL is lower on 10/10. [source: docs/COMPARISON.md](COMPARISON.md)
- Big-integer programs build to 103760 to 142168 bytes. [source: lab/bigbench/RESULTS.md](../lab/bigbench/RESULTS.md)
- AIL's toolchain install is 41,692 KiB, against Rust's 1,563,104 KiB and C's 124,048 KiB. [source: lab/compare_cand/RESULTS.md](../lab/compare_cand/RESULTS.md)
- Disk is not always smaller. On `csv_rollup` the fresh AIL build directory is 0.22 MiB, against 4.40 MiB for Rust but 0.02 MiB for C, so AIL is 9.50x larger than C. [source: lab/compare_cand/RESULTS.md](../lab/compare_cand/RESULTS.md)

## Safety

- Integers are int64. Out-of-range arithmetic stops with a named error instead of wrapping: the corpus run records 4 overflow stops among 338 runs. [source: lab/corpus/RESULTS.md](../lab/corpus/RESULTS.md)
- Five exact-big-integer programs build and print exactly what CPython prints, 5/5 equal. [source: lab/bigbench/RESULTS.md](../lab/bigbench/RESULTS.md)
- All 40 refusal programs in the errux corpus use a clean status (exit 2 or 3), never a Python traceback or a C compiler error. [source: lab/errux/RESULTS.md](../lab/errux/RESULTS.md)
- An 8-byte unsigned `int.from_bytes` leaves int64 and stops with `OverflowError`, not a wrong value. [source: lab/stdlib/hashlib/RESULTS.md](../lab/stdlib/hashlib/RESULTS.md)

## Python compatibility

- Of 12 algorithm programs, 11/12 build and match CPython in the default build; 0 are typed, 12 are general, 0 are refused, and the geomean speed-up is 1.04x. [source: examples/algos/RESULTS.md](../examples/algos/RESULTS.md)
- The bundled `shlex` reaches 12 built, 0 typed and 0 refused, against 9 required. [source: lab/stdlib/shlex/RESULTS.md](../lab/stdlib/shlex/RESULTS.md)
- With `csv`, 9 of 12 programs build and match CPython. [source: lab/stdlib/csv/RESULTS.md](../lab/stdlib/csv/RESULTS.md)
- Across 219 generated programs, 111 match CPython in the default build; 95 are refused, 7 differ and 3 crash. [source: lab/corpus/RESULTS.md](../lab/corpus/RESULTS.md)
- The vendored typeshed gives a known signature for 79.5 % of call sites, and 91.9 % on the stdlib programs. [source: lab/typeshed/RESULTS.md](../lab/typeshed/RESULTS.md)
- Over ten plain-Python programs AIL is 1.35x faster than CPython overall, but most of them use the general path. [source: lab/pyperf/RESULTS.md](../lab/pyperf/RESULTS.md)

## Where it is not there yet

- Compile time loses to Rust on every task: AIL is lower on 0/10. AIL takes 1.87–11.17 s and Rust takes 0.19–0.56 s. [source: docs/COMPARISON.md](COMPARISON.md)
- Plain `.py` sources reach the typed path on 0/10 tasks. They run 50–200× slower, and the compiler refuses 3 of them. [source: docs/ROADMAP.md](ROADMAP.md)
- Peak RSS on `tree_fold` is 464.6 MiB against Rust's 314.9 MiB, 1.48x higher. [source: docs/COMPARISON.md](COMPARISON.md)
- The stdlib census builds 3 of 197 modules, all on the general path; 187 are refused, and 6 more compile but drop the module's code. [source: lab/stdcensus/RESULTS.md](../lab/stdcensus/RESULTS.md)
- `rail_transfer` is 17.96x slower than Rust: 862 ms against 48 ms. [source: docs/COMPARISON.md](COMPARISON.md)
- The inference showcase is 56.7x slower in prefill and 10.1x slower per decoded token than llama.cpp. [source: lab/infer/RESULTS.md](../lab/infer/RESULTS.md)
- On `csv_rollup` the AIL binary is 64 KiB against C's 21 KiB, 3.07x larger. [source: lab/compare_cand/RESULTS.md](../lab/compare_cand/RESULTS.md)
- The errux refusal corpus scores 116 / 160 on clean status, location, named construct and rewrite hint. [source: lab/errux/RESULTS.md](../lab/errux/RESULTS.md)

## Numbers I do not use

Two committed files disagree on the same measure, so neither figure is a claim here. [source: docs/ROADMAP.md](ROADMAP.md) [source: docs/COMPARISON.md](COMPARISON.md)

- Wall time: docs/ROADMAP.md says 2.1× faster than the best other, while docs/COMPARISON.md says 1.00x. [source: docs/ROADMAP.md](ROADMAP.md) [source: docs/COMPARISON.md](COMPARISON.md)
- Build disk: docs/ROADMAP.md says 10× smaller than the best other, while one `csv_rollup` task measures 9.50x larger than C. [source: docs/ROADMAP.md](ROADMAP.md) [source: lab/compare_cand/RESULTS.md](../lab/compare_cand/RESULTS.md)

## Summary

| Where the claim holds | Where it does not |
|---|---|
| binary size against Rust | compile time |
| typed matmul and several tasks | plain `.py` typed reach |
| loud int64 overflow | peak RSS and the stdlib census |
