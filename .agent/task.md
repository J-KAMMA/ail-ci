Lane: roof

# roof1: how close is each compare program to the hardware limit, and what limits it

Time budget: 120 minutes. Commit and push after each sub-step. Follow `.agent/` rules (no regressions, CI first).
Measurement only: do not change the compiler.

**Why (owner, 2026-11-07):** the owner asked whether AIL can reach the limit of the von Neumann machine. Before building
any hardware-use feature (restrict from ownership proofs, SIMD guarantees with "why not vectorised" messages, small
int/float types, GIL-free `par for`, loop tiling, GPU offload), measure which limit each program actually hits.

**Number this moves:** `lab/roof/RESULTS.md`: for each of the 10 `lab/compare/src/*/main.py` programs (AIL build) and
the C version of the same program (from lab/compare), one row:
wall s, instructions, cycles, IPC, LLC misses, achieved memory bandwidth GB/s, % of the machine's measured STREAM
triad bandwidth, % of peak scalar IPC (4), fraction of hot-loop instructions that are vector (from `perf annotate` or
`gcc -fopt-info-vec` on the generated C), cores used, and a verdict: `memory-bound` / `compute-bound (scalar)` /
`compute-bound (could vectorise)` / `latency-bound (pointer chasing)` / `boxed general path` / `allocation-bound`.
Add the headline column `% of physical minimum` = (max of: bytes moved / STREAM bandwidth, operations / spec peak, dependent-load chain length x measured latency) / wall, for AIL and C; the owner's goal (2026-11-07) is to bring this to the physical minimum. Subtraction first (owner, 2026-11-07: removing beats adding): for each program, break AIL's extra instructions over C into: overflow/range checks, bounds checks, refcount inc/dec, boxing/unboxing, allocation/free, copies, other (attribute by perf annotate on the generated C's runtime helpers, or by building with each check disabled in a throwaway local build). Rank what to remove first, by measured share. Then a ranked list: which of the features above would move how many programs, with the measured headroom
(Amdahl: share of wall in the hot part × achievable speedup), not guesses.

## Steps
1. (30 min) `lab/roof/stream.c` (STREAM triad, 4 sizes), `lab/roof/chase.c` (random pointer chase: ns per dependent load, the roof for latency-bound programs), the `lscpu` facts (model, clock, SIMD width, cores) with the spec peak = clock x cores x ops per cycle, all measured in the same job on the same runner as the programs, and `lab/roof/run.sh`: build each program as compare-lab
   does, run under `perf stat -e cycles,instructions,LLC-load-misses,cache-references` (install `linux-tools` on the
   runner and `sudo sysctl kernel.perf_event_paranoid=-1`; if perf is unavailable, fall back to `tools/icount.c` and
   say so in the table). 3 runs, median. Commit, push.
2. (50 min) Fill the table for AIL and C. Note where AIL is on the general (boxed) path. Commit, push.
3. (40 min) Verdicts and the ranked feature list in RESULTS.md, with one paragraph per top-3 feature: which programs,
   expected speedup bound, and what in the compiler it needs. Commit, push.

Files you may create: `lab/roof/*` only.

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
