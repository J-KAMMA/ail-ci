**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model commandcode/deepseek-v4.1-flash]
## Review — fdgpu2 (G5: `/` and `sqrt` as SPIR-V kernels)

**What the diff really does:** lifts the two G1 refusals (`/`, `math.sqrt`) and adds a residual-based (Veltkamp/Dekker/TwoSum) correctly-rounded division and sqrt to the SPIR-V generator, an emulation twin in `gpu.RUNTIME` (`GK_FDIV` guard + CPU `/`/`sqrt`), and an AST pre-pass in `prepare()` that lowers `math.sqrt(x)` inside marked statements to `(float(x) if float(x)==0.0 else (1.0/0.0 if float(x)<0.0 else float(x)**0.5))` and drops the now-dead `_ail_math_sqrt` helper. The report only describes the last commit's two bug fixes; the diff is the whole feature (that commit stack is the real change).

**Probes** (`/tmp/rprobes`, `gcmp.sh` = `--gpu` build, CPython vs `AIL_GPU=0/emu/force`; `cmp.sh` = general+default):

| probe | result |
|---|---|
| p1/p2 sqrt out-of-range and in-range (`pow≠sqrt` values) | all match CPython |
| p4 int `/` incl. 2⁵³±1, negatives | flags `range`, matches |
| p8/p19 `/` by 0.0 | same stdout/exit (1), replay |
| p13 sqrt in marked comprehension | matches, kernel runs |
| p14/p21/p22 sqrt of int lists, ints > 2⁵³ | match CPython |
| p5/p16/p17 user `** 0.5`, `sq = math.sqrt` | refused by name, exit 3 |
| p12/p7 plain and marked `+` loop | C byte-identical to base (GPU build only gains unused inline helpers) |
| **p24** | **wrong output** (below) |

**Defect 1 (change-caused, base refuses).** `/tmp/rprobes/p24_catch3.py`: `def g(a: list[float]) -> list[float]` holds a `# ail: gpu` loop `r[i] = math.sqrt(a[i])`, `main()` wraps `g(a)` (one element `-1.0`) in `try/except ValueError / except ZeroDivisionError`. The rewrite's negative arm `1.0/0.0` raises `ZeroDivisionError`.
- CPython: `caught ValueError` (exit 0)
- HEAD (`--gpu`, `AIL_GPU=0`, `emu`, `force`): `caught ZeroDivisionError` (exit 0)
- base (`--gpu`): named refusal, `math.sqrt needs the correctly rounded GPU square root of stage G5`, exit 3
So the branch taken differs silently — no refusal, no uncaught stop. Narrow (the catch must sit in a caller; a `try` in the loop's own function is refused), but it is observable program output. The uncaught form (p3/p9) only differs in the message with the same exit status.

**Diff-level notes (not defects):** guard predicates and bounds are identical in emulation and device; a loop containing one zero/NaN/out-of-range operand replays entirely on the CPU (documented); a program that also calls `math.sqrt` outside the marked loop keeps `_ail_math_sqrt`, falls to the general path and prints the `ignored` note — correct output, no kernel.

**Report claims:** "sqrt(NaN) died with ZeroDivisionError, fixed" — verified (g5 `SQRT_EDGES`, p1/p2). "hand-written `** 0.5` refused" — verified. "8 OK / 2 skips" — verified. "1 safetynet failure, pre-existing" — verified: base fails the same `S4_generators_gc` with the identical assertion. "manifest `--check` = 0" — verified. "0 mismatches over 100k pairs on lavapipe" — **unverified**: no Vulkan device and no `spirv-val` here, so `BitTests` and `test_every_kernel_validates` skip. My independent Python model of the emitted algorithm is bit-exact over 200k random in-range pairs, 350k near-1.0 divisions and 200k sqrts (also with `s0` perturbed 1–2 ulp), and `test_no_division_instruction_and_no_fma`/NoContraction pass.

**Tests on HEAD** (`par_check.py -j 2`): g5, g1, g2, smoke all ok; `test_ail_safetynet` 1 failure.
**Pre-existing:** `test_ail_safetynet::test_programs[S4_generators_gc]` — identical on `/tmp/base`.
**Unverified:** device bits, SPIR-V validity, and speed (no GPU; the non-GPU generated C is unchanged, so no hot path is affected).

VERDICT: FIX
1. `math.sqrt(x)` with `x < 0` in a marked loop raises `ZeroDivisionError` (the rewrite's `1.0/0.0` arm) where CPython raises `ValueError`, so a caller's `except ValueError` no longer catches it: probe `/tmp/rprobes/p24_catch3.py` prints `caught ValueError` (exit 0) under CPython but `caught ZeroDivisionError` (exit 0) in every `--gpu` run (`AIL_GPU=0`, `emu`, `force`); the base refused the program by name (exit 3). Expected: `caught ValueError`, or a named refusal.
[commandcode stop=end_turn turns=57 out_tokens=58942]


--- ORIGINAL TASK ---
Lane: fd-gpu
Needs: fdgpu1

# fdgpu2: GPU stage G5, correctly rounded binary64 `/` and `sqrt` in SPIR-V

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** bit mismatches between the device and the CPU's `double` `/` and `sqrt` over at least 100,000
operand pairs per op plus the edge and halfway sets of GPU.md 5.1: target 0. Second number: the G1 refusals for
`/` and `math.sqrt` in a GPU loop go from 2 to 0 (they become kernels).

Base: `origin/integ` (with fdgpu1 integrated). Files you may create or edit, and no others:
- `AIL_CURRENT/python/pkg-v12/gpu.py` (lift the two refusals), `gpu_spirv.py`, `gpu_vk.py`
- `AIL_CURRENT/test_ail_gpu_g5.py` (new), `AIL_CURRENT/gpu_g5_cases/*` (new)
- `AIL_CURRENT/test_ail_gpu_g1.py` (only the two refusal cases that become builds)
- `AIL_CURRENT/test_ail_gpu_g2.py` (one import line), `tools/ci_shards.py` (`GPU_JOB`)
- `AIL_CURRENT/tests.d/test_ail_gpu_g5.txt` (new, one line: `test_ail_gpu_g5`)
- `AIL_CURRENT/docs/design/GPU.md` (a "6.3 G5 as built" section)
- the manifest files that `tools/update_manifest.py` writes

## Sub-steps

1. **Bit test first (15 min).** A kernel that applies `/` and `sqrt` to the operand set and a C check that compares
   every result bit with the CPU, using the emulation first (so the test exists before the SPIR-V does). Operands:
   random bit patterns, +-0, subnormals, the largest and smallest normals, 1 +- ulp, powers of two, halfway cases.
   Commit, push, and open the PR against `integ`.
2. **SPIR-V (30 min).** No `OpFDiv` and no `Fma` (the G2 tests reject them). Compute an approximation, then correct
   it with an exact residual: products split with Veltkamp/Dekker in plain `NoContraction` binary64 ops, the final
   rounding decided by the sign of the residual. Operands or results outside about [2**-1000, 2**1000], zeros, inf
   and NaN set the flag and replay on the CPU (that keeps the kernel small and exact). Put the same algorithm in the
   emulation so both twins agree. Commit and push.
3. **Test (15 min).** `test_ail_gpu_g5.py`: the bit test on lavapipe (0 mismatches), and 4 marked programs using `/`
   and `math.sqrt` whose output equals CPython and `AIL_GPU=0`, with the trace showing the device. Register it
   (import line, `GPU_JOB`). Write GPU.md 6.3. Commit, push, and wait for the `gpu (lavapipe)` job and the shards.

## Done-check

- `test_ail_gpu_g5.py` passes in the `gpu (lavapipe)` job: 0 mismatches over at least 100,000 pairs per op.
- `test_ail_gpu_g1.py`, `test_ail_gpu_g2.py`, `test_ail_gpu_smoke.py` pass; the 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop and report if any bit differs on lavapipe after the residual correction; give the operands in hex. Stop at once
and report if any build prints output different from CPython (or from the reference this task names) without a refusal
or a loud stop: give the program, both outputs and the commit. Never commit a change that does that. Stop when 60
minutes pass. Push what is done first.

## Appendix A: standing rules (from agent-brief-rules.md)

1. No regressions: a program that built and matched CPython before must still do so in the default build. A loud
   stop is allowed only where the value cannot be computed.
2. Probe ints beyond int64 wherever ints come from text or arithmetic; run probes in the default build and with
   `AIL_UNIFIED_FORCE=1`, compare both with `python3`.
3. Push early, open the PR against `integ`, wait for all 20 `shard` checks (`gh pr checks <n> -R J-KAMMA/ail-ci`, at most
   once every 10 minutes). Report only when all pass, or say which fail and why.
4. Branch from `integ` (or one unmerged PR at most).
5. Memory: wrap heavy runs in `ulimit -v 1500000`; `tools/par_check.py -j 2` at most; leave no background jobs.
6. New test module: `AIL_CURRENT/tests.d/<module>.txt` if the directory exists, else `ail_check.py` MODULES; `git add`,
   `tools/update_manifest.py`, then `tools/update_manifest.py --check`.
7. Never print credentials, run a broad pkill, merge PRs, change repository settings, cancel runs, tag, publish, or edit
   `.github/workflows`.
8. Never edit `AIL_CURRENT/ail_chatgpt.py`, `AIL_CURRENT/ail_syntax.py`, `AIL_CURRENT/python/pkg-v12/pyfunc.py`,
   `pyc.py`, `buildcache.py`, `pyboxed2.py`, or `packaging/ail_lang/cli.py`. Other lanes own them. Do not edit
   `DEVLOG.md` either: put your notes in the files this task names. Edit only the files this task names, plus the
   manifest files that `tools/update_manifest.py` writes.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug] [--debug-dir DIR]`.
  `DIR/program.c` is the generated C. `--strict` means the typed path or a refusal. `-o` must not exist yet. A fallback
  to the general path prints `note: ... built on the general path ...` on stderr.
- AIL is Python syntax plus optional annotations (`.py` files only; the `.ail` brace syntax is retired). Ints are
  int64, and overflow stops loudly. Never silent wrong output: a value AIL cannot compute exactly is refused by name
  or stops loudly.
- CPython 3.12 is the oracle: compare stdout and the exit status, and stderr where a task says so.
- GPU design: `AIL_CURRENT/docs/design/GPU.md` (rule: a `--gpu` build prints exactly what `AIL_GPU=0` prints;
  Vulkan only, no CUDA; float rules 3.2; reductions 3.4; CI on lavapipe 5.1; staging 6; G1 and G2 as built 6.1, 6.2).
  Code: `python/pkg-v12/gpu.py`, `gpu_spirv.py`, `gpu_vk.py`; tests `test_ail_gpu_g1.py` (emulation, in the shards)
  and `test_ail_gpu_g2.py` (SPIR-V on lavapipe, `GPU_JOB` in `tools/ci_shards.py`).
- The `gpu (lavapipe)` job in `.github/workflows/tests.yml` runs `test_ail_gpu_g1.py` and `test_ail_gpu_g2.py -v` with
  `AIL_GPU_REQUIRE_DEVICE=1`. Workers cannot edit the workflow (rule 7). A new GPU test module therefore also gets a
  `from test_ail_gpu_<name> import *` line near the top of `test_ail_gpu_g2.py`, so the job runs it now; the main
  session may later replace those lines with a workflow glob.
- Exact means bit-equal: every SPIR-V float op carries `NoContraction`; no `Fma`, `FDiv`, fast-math or `FMin`/`FMax`;
  a case the device cannot do exactly sets the flag and is replayed on the CPU (`AIL_GPU_TRACE=1` shows it). A fast,
  device-dependent matmul is an explicit opt-in only, and not part of these jobs.

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
