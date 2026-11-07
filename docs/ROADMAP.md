# AIL roadmap

Updated 2026-11-07. Progress is judged by numbers: the compare-lab table, which runs daily on `integ`, the vibe-coding
benchmark (below), and the test gate. It is not judged by the number of merged jobs.

## What AIL is for

**AIL is a language for vibe coding: programs that an AI writes and a person runs.** AIs write Python best, so AIL is
Python syntax. The syntax is Python, but the semantics are AIL's own and are written down in the
[language specification](SPEC/README.md); printing the same output as CPython is a compatibility mode, not the
definition of the language, and every divergence is a named refusal or a documented difference. AIL is not designed to
fit today's world: it aims to be the future standard language for AI-written programs, with semantics chosen
deliberately rather than inherited from an implementation. The [language specification](SPEC/README.md) is where that
standard is written down rule by rule, and it is versioned so the language can change on purpose. What AIL adds is what AI-written code most needs:

- **No silent wrong output.** Overflow, out-of-range access and other mistakes stop loudly with the source line,
  instead of printing a plausible wrong answer that nobody reads closely.
- **Errors an AI can fix.** Every error and every "could not take the fast path" note gives a location, a reason and a
  fix, in a form an agent can read.
- **A fast write-run-fix loop.** Compile time is part of the product: the AI runs the compiler dozens of times per task.
- **Rust-level speed and a small standalone binary** from the same plain Python, so the result can be shipped as is.

The headline benchmark is therefore not only speed: the same AI writes the same tasks in Python, Rust and AIL, and we
compare how often it reaches a correct program, how many fix rounds it needs, and how many silently wrong programs
pass its own checks.

## Where AIL stands

Figures from compare-lab, commit 4f1245b, 10 tasks. Each row gives the result against Rust and against the best other language (C, Rust, Go, Nim, Python); the second figure is a geomean.

| Column | vs Rust | vs best other |
|---|---|---|
| Binary size | smaller on 10/10 | 3.1× smaller |
| Build disk | smaller on 10/10 | 10× smaller |
| Wall time | faster on 6/10 | 2.1× faster |
| Peak RSS | lower on 6/10 | 1.3× lower |
| Compile time | slower on 10/10 | 27× slower |

AIL programs written in Python syntax (`.py`) reached the typed path on 0/10 tasks at that commit, ran 50–200× slower, and the compiler refused 3 of them; the P1 jobs below
change this, and the table is re-measured when they land. The rival Python compilers (Codon, Nuitka, mypyc, Cython)
are being added to the comparison (job cmprival1).

## P0 — Release blockers (done)

relevalorder, relrterr, reldiag, relpkgname, relplatinstall and reltable are merged.

## P1 — Python proof

"Write Python, get Rust-level speed and a small binary."

- **Jobs:** pyreachs1–8 (2, 6 and 8 still to land).
- **How it works:**
  - `None` is an exact tagged value.
  - Integers wider than int64 use exact u64 only where the compiler can prove they are needed.
  - Code that cannot be typed falls back to the general path, or to CPython (hybrid mode).
- **Done when:** the `.py` sources of the compare-lab tasks reach the typed path on 10/10 tasks, refuse none, and land within 1.5× of the `.ail` sources on wall time.

## P2 — The AI loop (before 0.1)

| Area | Jobs | Target |
|---|---|---|
| Vibe-coding benchmark | vibe1 | The same AI writes the tasks in Python, Rust and AIL; correct-program rate, fix rounds and silent-wrong count are published, wins and losses. |
| Compile time | ctimes1, ctpred1–3, fecache1 (merged, opt-in `AIL_FE_CACHE=1`), cached separate runtime | No loss in instruction count; compile time within 5× of Rust. |
| Errors for agents | reldiag follow-ups, "why not typed" notes | Every error and fallback note has location, reason and fix, and a machine-readable form. |

## P3 — Close the Rust gaps

| Area | Jobs | Target |
|---|---|---|
| Fair benchmark | rails1–3 | rail_transfer runs the same two-sided search as C and Rust. |
| Memory | arena1s1–s4 | tree_fold peak RSS from 465 MiB to about 340 MiB. |
| Interpreter-style hot loops | spec1 | tally_lang faster than C, or the job stops if the gain is under 1.2×. |

## P4 — Release 0.1

1. Merge `integ` into `main`.
2. Tag on `main`.
3. Publish `ailc` on PyPI.

Every tag and every publish waits for the owner's approval. The license is MIT OR Apache-2.0.

## P5 — One niche, then users

Small, fast CLI and data-processing tools that an AI writes in Python syntax. This phase brings in:
- the CPython hybrid, in which typed functions run as an extension;
- modules and packages;
- C FFI and crate FFI;
- an LSP;
- docs written from what users report.

## Later

- Safety proofs without lifetimes: the compiler infers ownership and proves memory safety and race freedom for typed
  code, and keeps a loud runtime check where it cannot (design and census: job proof1).
- Self-hosting: compiler parts rewritten in AIL, checked by a byte-identical C diff.
- GPU through Vulkan: `ail_array` with a torch-like API, exact by default, with a fast matmul kernel as an opt-in.
- GIL-free typed parallelism.
- Robotics and embedded targets (probe: job robo1).

## Method

- An Opus design pass splits each big job into steps of 80 minutes or less.
- Jobs that touch the same files share a lane and run one at a time.
- Every merge passes the 20-shard test gate and the CPython differential gate.
- Speed claims are checked by instruction count, and the output must stay unchanged.
