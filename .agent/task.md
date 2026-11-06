**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model commandcode/deepseek-v4.1-flash]
I've reproduced the cross-builds, the census, the tests and the tables. Here's what I found.

**What the change really does:** adds only `lab/robo/` (a measurement lab: 3 programs, a Cortex-M harness, `run.py`, `results.json`, `README`/`RESULTS`, 7 census programs) plus a DEVLOG entry. No compiler, runtime, workflow or test file is touched.

**Probes** (`bash ~/tools/cmp.sh … $PWD`, both builds, all "same stdout"):
`/tmp/rprobes/empty_alias.py` (empty list mean, negative values, dict value, list alias mutated, append during iteration); `/tmp/rprobes/widths.py` (float via argument/list item/attribute/dict value, `-0.0`, negative floor/true division, round ties); `/tmp/rprobes/plain.py` (no feature: generated C byte-identical between `/tmp/base` and HEAD).

**Independent reproduction:** built `pid/ringbuf/kin2` with AIL and gcc at the README's flags:
- all 12 cells (native, aarch64+qemu, armhf+qemu, Cortex-M3+qemu) reproduce the table's text/data/bss **exactly** and match CPython;
- without `-u _printf_float` kin2 prints `0.0` (the documented silent-float failure);
- `pid/program.c` = 3232 lines, 0 refs to pthread/mmap/socket/clock_gettime/nanosleep;
- `pid` via `compile -o exe` is also text 12846; `STRICT_DECL_FLAGS` is exactly the three `-Werror=` flags claimed.

**Claims:** 1 mostly verified (0 mismatches for cross/RAM/jitter) but "regenerated every table" is **false** (census row, below); 2 verified; 3 verified; 4 verified; 5 verified; 12/12 verified; tests `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` → 3 modules, 0 failed; manifest `--check` rc 0; diff scope verified. Jitter numbers not re-run (JSON↔table↔prose cross-checked only).

**Defects**
1. `RESULTS.md` §2 parallel-loop row is stale and wrong. Reproduce: `AIL … compile lab/robo/progs/census/census_par.py --debug-dir`, then the `run.py` `bm_build` command. Expected (actual build **and** `results.json`): `program.c:516:38: error: 'CLOCK_MONOTONIC' undeclared (first use in this function)`. Table says: `program.c:473:5: error: unknown type name 'pthread_mutex_t'`. The diagnosis is wrong too: newlib's `pthread.h` does declare `pthread_mutex_t` (473 compiles); what is missing is `PTHREAD_MUTEX_INITIALIZER` (568) plus the clock helper — i.e. the pool's clock, not the type. This row did not change when `results.json` was regenerated (`git show 3308c12:lab/robo/results.json` census.par still has the old 473 error).
2. `RESULTS.md` §3 prose: "C and AIL … worst miss 271-406 us" contradicts the data. `results.json` run maxima: C 198–312 µs, AIL 208–**635.8** µs (alloc run). Even the table's median-of-maxima column spans 247–405. The 635.8 µs AIL outlier is understated.

**Pre-existing:** none — no compiler/runtime code changed; base and HEAD emit identical C.

**Speed:** not applicable (no hot path changed).

VERDICT: FIX
1. Regenerate/fix the `RESULTS.md` §2 `ail.par_range` row to the measured first error (`program.c:516:38: 'CLOCK_MONOTONIC' undeclared`) and correct "what is missing" (initializers/clock, not `pthread_mutex_t`).
2. Correct the §3 "worst miss 271-406 us" sentence to the true observed maxima (C ≤312 µs, AIL ≤636 µs).
[commandcode stop=end_turn turns=28 out_tokens=23241]


--- ORIGINAL TASK ---
Lane: robo

# robo1: robotics/embedded probe: can AIL's generated C run on ARM and on a microcontroller, and how steady is a 1 kHz control loop

Time budget: 150 minutes. Commit and push after each sub-step. Follow `.agent/` rules (no regressions, memory cap).

**Why (owner, 2026-11-06):** the owner asked whether AIL could be a language for robots. Before any design work we need
numbers: does the generated C cross-compile, what blocks bare-metal, and how much does a control loop jitter compared
with C and MicroPython. This is a measurement probe; it does not change the compiler. Report what fails as plainly as
what works.

**Numbers this produces** (all in `lab/robo/RESULTS.md`):
1. Cross-build table for 3 programs (below) x 3 targets: `aarch64-linux-gnu` (Raspberry Pi class, run under
   `qemu-aarch64` user mode), `arm-linux-gnueabihf` (32-bit Pi, `qemu-arm`), `arm-none-eabi` Cortex-M3/M4 bare metal
   (link with newlib-nano, run under `qemu-system-arm -M mps2-an385` with semihosting). Per cell: builds yes/no,
   first error line, text+data+bss bytes (`size`), runs and output matches CPython yes/no.
2. Bare-metal blocker census: every libc/OS symbol the AIL runtime needs that newlib-nano bare metal lacks
   (threads, mmap, signals, files, clock...), with the runtime file and function that uses it, and a one-line guess of
   how to stub it (e.g. "pthread: single-thread build flag"). Do not implement the stubs.
3. Control-loop jitter on the x86 runner (native, not qemu): a 1 kHz loop (`clock_nanosleep` absolute deadlines in C;
   the same loop shape in AIL and in MicroPython unix port, pinned version) running a small PID update over a list of
   8 floats plus one allocation-free and one allocating variant, 20000 iterations. Report per tool: p50/p99/p99.9/max
   of the deadline miss in microseconds, and how many periods overran. State that a shared GitHub runner is noisy and
   give the C row as the noise floor.
4. RAM: peak RSS (Linux targets) and heap high-water mark (bare metal, via newlib `mallinfo` or a counting allocator
   in the harness) for the 3 programs.

Programs (write them in `lab/robo/progs/`, plain annotated Python that AIL compiles, plus `pid.c` and `pid_mpy.py`):
`pid.py` (PID controller over a fixed list, prints final state), `ringbuf.py` (fixed-size sensor ring buffer, moving
average), `kin2.py` (2-link arm forward kinematics with math.sin/cos, 10000 angles, prints checksum rounded to 6 dp).

Base: `origin/integ`. Files you may create or edit, and no others (all new): everything under `lab/robo/`
(`README.md`, `RESULTS.md`, `run.py`, `progs/*`, `harness/*` for the bare-metal startup, linker script and semihosting
glue, `results.json`). Do not edit any compiler/runtime file or any workflow. Tools from Ubuntu apt or pinned PyPI /
official release tarballs only; record exact versions in `lab/robo/README.md`.

Use the AIL build that emits C (see `AIL_CURRENT` docs / `ail build --emit-c` or the equivalent the repo provides) and
compile that C with the cross gcc at `-O2`, same flags otherwise as the native build.

## Sub-steps
1. (40 min) Programs + CPython reference outputs; native AIL/C/MicroPython builds; aarch64 and armhf cross builds
   under qemu. Commit, push.
2. (50 min) Bare-metal Cortex-M attempt and the blocker census. Commit, push.
3. (40 min) Jitter and RAM measurements. Commit, push.
4. (20 min) `RESULTS.md`: the four tables and a 6-line verdict: what AIL needs (in order of size) to be a fit for
   robot control, and where it already beats MicroPython. Commit, push.

**Rules for every job.**
- **Load:** you are one of up to five agents on a 16 GB PC. Keep local parallelism at 2 (`-j 2`) and never run the whole suite; the full suite runs on CI after merge.
- **Commits:** commit with explicit `git add` on your branch. Messages end with a `Co-Authored-By:` line naming the model you actually are (Claude: `Claude Opus 5.5 <noreply@anthropic.com>` or `Claude Sonnet 5.5 <noreply@anthropic.com>`; other models: omit the line).
- **Forbidden:** push, stash, rebase, reset, and deletion outside /tmp.
- **Records:**
  - New DIFFERENCES rows use placeholder ids `C?-<your branch>-N`.
  - Add a DEVLOG entry at the top with today's date.
  - Register a new test module: if `AIL_CURRENT/tests.d/` exists, add `AIL_CURRENT/tests.d/<module>.txt` containing the module
    name and do NOT edit the tuple in `ail_check.py`; otherwise append it to the `MODULES` tuple.
  - `git add` new files, run `python3 tools/update_manifest.py`, then `--check`. Do not hand-edit `MANIFEST.json` or `manifest.d/`.
- **Required tests:** the targeted modules for what you touch, plus test_ail_safetynet, test_ail_files and test_ail_corpus_findings3. Run them on your final commit, not an earlier one.
- **Mandatory self-check before you report.** A reviewer will repeat it, and past reports were wrong about half the time.
  1. Write probe programs in /tmp/probes/ for every behaviour you changed. Cover the boundaries your implementation implies, not only the example: types, widths, empty, negative, aliasing, values reaching the code through an argument, a list item, an attribute and a dict value, and both builds.
  2. Run each probe with `bash ~/tools/cmp.sh /tmp/probes/<p>.py $PWD`.
  3. Every probe must match CPython or be refused by name.
  4. List the probes and their results in the report.
- **Never claim something works unless a probe or test you ran shows it.** If you did not verify something, say so.
- **Tokens:** use grep -n, narrow reads, and `tail` on long logs.
- **Budget:** stop at the budget note, leaving a committed, consistent state.
- **Report:** keep it brief, with numbers.
- Test data: email addresses only on example.com / example.org (the public export audit rejects any other domain).

**Work in few steps** (each step costs model time):
- Write all probe programs first, then run them together with one command, for example a loop over `bash ~/tools/cmp.sh`, instead of one command per program.
- Search only inside the repository (`grep -rn ... AIL_CURRENT tools`), never across `/home` or `/tmp`.
- Read a file once, using a range that is large enough, instead of many small reads.
- Do not re-run a test that already passed unless you changed code since.

**Where you run:** a GitHub Actions runner (4 cores). Commit your work on the current branch; do not push.
