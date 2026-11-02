# AIL roadmap

Updated 2026-11-03. Progress is judged by numbers: the compare-lab table, which runs daily on `integ`, and the test gate. It is not judged by the number of merged jobs.

## Where AIL stands

Figures from compare-lab, commit 4f1245b, 10 tasks. Each row gives the result against Rust and against the best other language (C, Rust, Go, Nim, Python); the second figure is a geomean.

| Column | vs Rust | vs best other |
|---|---|---|
| Binary size | smaller on 10/10 | 3.1× smaller |
| Build disk | smaller on 10/10 | 10× smaller |
| Wall time | faster on 6/10 | 2.1× faster |
| Peak RSS | lower on 6/10 | 1.3× lower |
| Compile time | slower on 10/10 | 27× slower |

AIL programs written in Python syntax (`.py`) reach the typed path on 0/10 tasks. They run 50–200× slower, and the compiler refuses 3 of them.

## P0 — Release blockers (now)

| Job | What it delivers |
|---|---|
| relevalorder | No silent wrong output from argument evaluation order. |
| relrterr | Runtime errors name the exception and the source line in the default build. |
| reldiag | Beginner mistakes get an error with a location. |
| relpkgname | The PyPI distribution is named `ailc`; the command stays `ail`. |
| relplatinstall | `pip install` is tested in CI on Linux, macOS and Windows. |
| reltable | The full comparison table is published in docs/COMPARISON.md, wins and losses. |

**Done when:** all six are merged and the test gate is green.

## P1 — Python proof

"Write Python, get Rust-level speed and a small binary." This is the main claim, and today it does not hold.

- **Jobs:** pyreachs1–8.
- **How it works:**
  - `None` is an exact tagged value.
  - Integers wider than int64 use exact u64 only where the compiler can prove they are needed.
  - Code that cannot be typed falls back to the general path, or to CPython (hybrid mode).
- **Done when:** the `.py` sources of the compare-lab tasks reach the typed path on 10/10 tasks, refuse none, and land within 1.5× of the `.ail` sources on wall time.

## P2 — Close the Rust gaps

| Area | Jobs | Target |
|---|---|---|
| Fair benchmark | rails1–3 | rail_transfer runs the same two-sided search as C and Rust. |
| Memory | arena1s1–s4 | tree_fold peak RSS from 465 MiB to about 340 MiB. |
| Compile time | fecache1 (merged, opt-in `AIL_FE_CACHE=1`), cached separate runtime | No loss in instruction count; compile time within 5× of Rust. |
| Interpreter-style hot loops | spec1 | tally_lang faster than C, or the job stops if the gain is under 1.2×. |

## P3 — Release 0.1

1. Merge `integ` into `main`.
2. Tag on `main`.
3. Publish `ailc` on PyPI.

Every tag and every publish waits for the owner's approval. The license is MIT OR Apache-2.0.

## P4 — One niche, then users

Small, fast CLI and data-processing tools written in Python syntax. This phase brings in:
- the CPython hybrid, in which typed functions run as an extension;
- modules and packages;
- C FFI and crate FFI;
- an LSP;
- docs written from what users report.

## Later

- Self-hosting: compiler parts rewritten in AIL, checked by a byte-identical C diff.
- GPU through Vulkan: `ail_array` with a torch-like API, exact by default, with a fast matmul kernel as an opt-in.
- GIL-free typed parallelism.

## Method

- An Opus design pass splits each big job into steps of 80 minutes or less.
- Jobs that touch the same files share a lane and run one at a time.
- Every merge passes the 20-shard test gate and the CPython differential gate.
- Speed claims are checked by instruction count, and the output must stay unchanged.
