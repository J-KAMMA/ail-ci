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
