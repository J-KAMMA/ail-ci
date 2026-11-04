# Python compilers: Codon, mypyc and Nuitka against AIL

Date 2026-11-03. AIL compiler commit `26ab724` (unchanged in this job); runner ubuntu-24.04, 4 vCPU, 16 GB.
Versions: Codon `0.20.6`, mypyc `mypy 2.4.1 (compiled: yes)`, Nuitka `4.3.4`, CPython 3.12.3.
Pins are in `lab/compare/toolchains.env`; the workflow installs them on the runner, not on a PC.

Every tool compiles the same annotated `typed.py` as the AIL column: Codon with `codon build -release`
(the helpers from `compat/codon/ail.py`), mypyc with `mypyc` (the result is a CPython extension and still
needs CPython at run time), Nuitka with `--standalone --onefile`. No task was rewritten for a tool.

Method follows the existing compare-lab columns: wall time is the median of 5 runs (3 for the Python
compilers) of the perf input, compile time the median of 3 cold builds, binary size as built, build disk
`du -sk` of a fresh build directory, peak RSS from `/usr/bin/time -v`. Every program ran on every public
and hidden case of its task and its stdout and exit code were compared byte for byte with the CPython
`reference.py`. A build failure or a timeout counts as a loss, not as a skipped row.

Instruction counts are user-space Ir from valgrind callgrind: `perf_event_open` is not permitted on the
runner, so `--icount auto` selects callgrind (`icount_method` is `callgrind`), and the workflow installs
valgrind. Each run records the count in its result JSON (`instructions`, same perf input as the other
metrics) and a `chain_relax` smoke run was checked to return numeric Ir for all four columns. Callgrind
on the full perf inputs did not fit this job's budget (the Nuitka binaries alone take more than ten times
their 16-70 s wall time under it), so the tables below report the other metrics and this document makes
no instruction-count comparison. For mypyc the count, when present, includes CPython, which the
extension still needs at run time.

## Correctness against the CPython reference

Every public and hidden case; a successful build that then differed would show `MISMATCH`.

| task | AIL | Codon | mypyc | Nuitka | CPython |
|---|---|---|---|---|---|
| berth_sim | match 26/26 | match 26/26 | match 26/26 | match 26/26 | match 26/26 |
| chain_relax | match 32/32 | match 32/32 | match 32/32 | match 32/32 | match 32/32 |
| echo_pack | match 57/57 | match 57/57 | build failed | match 57/57 | match 57/57 |
| ledger_bin | match 55/55 | match 55/55 | match 55/55 | match 55/55 | match 55/55 |
| rail_transfer | match 24/24 | build failed | match 24/24 | match 24/24 | match 24/24 |
| tally_lang | match 75/75 | match 75/75 | match 75/75 | match 75/75 | match 75/75 |
| term_rank | match 43/43 | match 43/43 | match 43/43 | match 43/43 | match 43/43 |
| ticket_audit | match 91/91 | build failed | match 91/91 | match 91/91 | match 91/91 |

Build errors, verbatim (first line of each):

- `echo_pack`, mypyc: `mod.py:12: ValueError: bytearray is not a valid sequence` (an internal mypyc error).
- `rail_transfer`, Codon: `main.py:27 (9-13): error: cannot typecheck 'self'` (the heap-item generic type).
- `ticket_audit`, Codon: `'bytes' object has no attribute '__int__'` while realizing `__new__(what: bytes)`.
- No successful build printed output that differed from CPython on any case. In particular, no task exposed
  Codon's 64-bit int changing an output on these inputs.

## Wall time (ms, median of 3-5 runs of the perf input)

Lower is better.

| task | AIL | Codon | mypyc | Nuitka | CPython |
|---|---:|---:|---:|---:|---:|
| berth_sim | 2744 | 5355 | 15098 | 22403 | 18756 |
| chain_relax | 1437 | 1358 | 10267 | 16647 | 11218 |
| echo_pack | 1188 | 3213 | build failed | 41851 | 48165 |
| ledger_bin | 970 | 1684 | 13035 | 27134 | 25489 |
| rail_transfer | 74 | build failed | 1222 | 1756 | 695 |
| tally_lang | 1632 | 1906 | 11794 | 70843 | 11005 |
| term_rank | 2372 | 4208 | 7450 | 25176 | 8344 |
| ticket_audit | 1818 | build failed | 7953 | 19477 | 8902 |

## Compile time (s, median of 3 cold builds)

CPython has no build step. Lower is better.

| task | AIL | Codon | mypyc | Nuitka | CPython |
|---|---:|---:|---:|---:|---:|
| berth_sim | 10.86 | 9.72 | 5.33 | 63.78 | - |
| chain_relax | 2.34 | 9.02 | 4.02 | 62.50 | - |
| echo_pack | 4.17 | 9.01 | build failed | 62.50 | - |
| ledger_bin | 4.38 | 11.46 | 5.31 | 64.35 | - |
| rail_transfer | 3.50 | build failed | 5.90 | 63.85 | - |
| tally_lang | 4.43 | 10.97 | 5.77 | 61.34 | - |
| term_rank | 3.81 | 11.71 | 4.76 | 58.48 | - |
| ticket_audit | 5.81 | build failed | 5.54 | 59.63 | - |

## Binary size (KiB, as built)

CPython has no build step. For mypyc this is the extension only; it still needs CPython. Lower is better.

| task | AIL | Codon | mypyc | Nuitka | CPython |
|---|---:|---:|---:|---:|---:|
| berth_sim | 63 | 185 | 386 | 4418 | - |
| chain_relax | 34 | 171 | 307 | 4402 | - |
| echo_pack | 35 | 187 | build failed | 4422 | - |
| ledger_bin | 60 | 249 | 390 | 4410 | - |
| rail_transfer | 63 | build failed | 470 | 4418 | - |
| tally_lang | 73 | 249 | 458 | 4446 | - |
| term_rank | 73 | 1129 | 391 | 4426 | - |
| ticket_audit | 102 | build failed | 471 | 4446 | - |

Codon's cells were re-measured from `codon build -release` with Codon 0.20.6 on 2026-11-04 and converted
with 1024 bytes to the KiB; the other columns are from the 2026-11-03 run.

## Build disk (MiB, fresh build dir with its caches)

Nuitka --onefile keeps its whole standalone tree in the build directory. Lower is better.

| task | AIL | Codon | mypyc | Nuitka | CPython |
|---|---:|---:|---:|---:|---:|
| berth_sim | 0.22 | 0.20 | 3.95 | 45.75 | - |
| chain_relax | 0.14 | 0.18 | 3.48 | 45.51 | - |
| echo_pack | 0.14 | 0.20 | build failed | 45.70 | - |
| ledger_bin | 0.21 | 0.26 | 3.97 | 45.82 | - |
| rail_transfer | 0.22 | build failed | 4.39 | 46.16 | - |
| tally_lang | 0.26 | 0.27 | 4.33 | 46.71 | - |
| term_rank | 0.25 | 1.12 | 3.95 | 45.85 | - |
| ticket_audit | 0.34 | build failed | 4.43 | 46.61 | - |

## Peak RSS (MiB, /usr/bin/time -v)

Lower is better.

| task | AIL | Codon | mypyc | Nuitka | CPython |
|---|---:|---:|---:|---:|---:|
| berth_sim | 238.7 | 318.7 | 792.0 | 909.7 | 1093.9 |
| chain_relax | 3.8 | 12.0 | 23.3 | 30.5 | 21.3 |
| echo_pack | 346.0 | 415.3 | build failed | 1372.8 | 1555.9 |
| ledger_bin | 330.4 | 355.7 | 744.4 | 841.8 | 1238.3 |
| rail_transfer | 28.1 | build failed | 88.4 | 125.3 | 111.2 |
| tally_lang | 1.5 | 9.7 | 12.2 | 21.5 | 11.5 |
| term_rank | 158.1 | 289.1 | 231.1 | 156.4 | 407.0 |
| ticket_audit | 248.7 | build failed | 297.0 | 392.0 | 534.4 |

## Where AIL wins and where it loses

- **Wall time.** AIL beats the best Python compiler on 7 of the 8 completed tasks (geometric mean 0.44x of the best). Its only loss is `chain_relax`, where Codon is 1.06x faster. Codon is the only speed rival: AIL is 0.14x mypyc's time and 0.06x Nuitka's as a geometric mean. Nuitka is slower than plain CPython on 7 of 8 tasks; mypyc beats CPython on 5 of 7 it could build.
- **Compile time.** AIL beats the best builder on 6 of 8 tasks (geometric mean 0.72x of the best) and loses only to mypyc on `berth_sim` (2.04x) and `ticket_audit` (1.05x). mypyc is the fastest builder at 4.02-5.90 s; Codon takes 9.0-11.7 s and Nuitka 58-64 s.
- **Binary size.** AIL wins on every task: 34-102 KiB against 171-1,129 KiB for Codon, 307-471 KiB for mypyc and about 4.3 MiB for Nuitka.
- **Build disk.** AIL wins on 7 of 8 tasks (geometric mean 0.38x of the best); Codon is smaller on `berth_sim` (200 vs 228 KiB). Codon otherwise needs 184-1,147 KiB, mypyc 3.5-4.4 MiB and Nuitka about 46 MiB.
- **Peak RSS.** AIL has the lowest peak RSS on 7 of 8 tasks (geometric mean 0.54x of the best); Nuitka is lower on `term_rank` (156.4 vs 158.1 MiB). Codon and mypyc are consistently higher (Codon up to 6.7x and mypyc up to 8.3x, both on `tally_lang`), and mypyc carries CPython with it.
- **Instructions.** Not compared here: the runner records user-space Ir in each result JSON, but callgrind on the perf inputs did not fit the job budget (see the method note above). The smoke check confirmed numeric Ir for all four columns.
- **Not measured:** `scar_life` and `tree_fold` did not finish inside this job: mypyc ran more than 25 minutes of CPU on `scar_life`'s perf input before the task was stopped, and Codon ran more than 10 minutes on `tree_fold`'s. Both count as losses for the tool that did not finish; the other columns for those two tasks are missing from these tables, not from the lab.
