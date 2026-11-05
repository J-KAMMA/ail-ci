Lane: fd-gpu

# fdgpu1: a fast Vulkan compute smoke test on lavapipe in CI

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** smoke checks that pass in the `gpu (lavapipe)` job: 0/6 today (no smoke module), target 6/6, in
under 90 seconds of test time (recorded from the job log). It is the first thing to read when the GPU job turns red.

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/test_ail_gpu_smoke.py` (new) and `AIL_CURRENT/gpu_smoke_cases/*.py` (new)
- `AIL_CURRENT/test_ail_gpu_g2.py` (one import line, Appendix B)
- `tools/ci_shards.py` (add `test_ail_gpu_smoke` to `GPU_JOB`)
- `AIL_CURRENT/tests.d/test_ail_gpu_smoke.txt` (new, one line: `test_ail_gpu_smoke`)
- the manifest files that `tools/update_manifest.py` writes

## Sub-steps

1. **Cases (15 min).** Two small marked programs (`# ail: gpu`): an int64 map over 4096 elements and a binary64 map
   (`+ - *`, a comparison, `abs`) over 4096 elements. Commit, push, and open the PR against `integ`.
2. **The six checks (30 min).** Build each program once with `--gpu` and reuse the binary:
   1. the Vulkan loader and a device are found: `AIL_GPU_TRACE=1` shows `device=llvmpipe` (fail, not skip, when
      `AIL_GPU_REQUIRE_DEVICE=1` is set and no device is found);
   2. the int64 kernel's stdout and exit status equal CPython's and the `AIL_GPU=0` run's;
   3. the same for the binary64 kernel;
   4. no loader (`VK_ICD_FILENAMES=/nonexistent` or the runtime's own switch): the CPU fallback prints the same and
      the trace says `cpu`;
   5. `AIL_GPU_FAULT=3000` (if the test build has it, see GPU.md 5.1; else an index error planted at element 3000):
      the replay prints what CPython prints;
   6. every emitted module passes `spirv-val` (skip only when `spirv-val` is missing outside CI).
   Each check prints one `smoke: <name> ok <ms>` line. Commit and push.
3. **CI (15 min).** Add the import line to `test_ail_gpu_g2.py` and the module to `GPU_JOB`; register it. Run it
   locally (lavapipe if installed, else the checks that need a device skip locally only). Commit, push, and wait for
   the `gpu (lavapipe)` job and the shards. Write the total time from the job log into the PR body.

## Done-check

- In the `gpu (lavapipe)` job log: six `smoke: ... ok` lines, total under 90 s.
- `test_ail_gpu_g1.py` and `test_ail_gpu_g2.py` still pass; the 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop and report if the `gpu (lavapipe)` job does not start on your PR (the plan job decides it); give the plan job's
output. Stop at once and report if any build prints output different from CPython (or from the reference this task
names) without a refusal or a loud stop: give the program, both outputs and the commit. Never commit a change that
does that. Stop when 60 minutes pass. Push what is done first.

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
- **Commits:** commit with explicit `git add` on your branch. Messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
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
