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
