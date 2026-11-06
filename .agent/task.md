**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model commandcode/deepseek-v4.1-flash]
## Review: cmprival1

**What the change really does:** adds a measurement lab, `lab/compare_rival/run.py`, which builds `lab/compare/src/<task>/{main,typed}.py` with Nuitka, Cython (plain and annotated), mypyc and Codon, checks every public/hidden case against each task's `reference.py`, adds five safety probes, pins versions, and ships `results.json`, `RESULTS.md` and a proposed workflow. No compiler or runtime file is touched (`git diff work..HEAD -- . ':!lab/compare_rival'` is empty). The worker report is empty, so there are no report claims to verify; I checked the artifacts themselves.

**Verified**
- `RESULTS.md` is exactly `render(results.json)` (byte-identical) and contains all 10 tasks.
- Data is real: a fresh `--safety` rerun reproduced all 35 table cells bit-identically; a fresh `rail_transfer` run reproduced identical `binary_bytes`/`build_disk_kib` and 3/3 + 21/21 cases (wall was inflated ~4x by my concurrent builds, ratios unchanged); a manual Cython-typed `scar_life` build really does run past 180 s, so that "timeout" is genuine.
- Installed rivals match `toolchains.env` exactly (Cython 3.3.1, mypy 2.4.1, Nuitka 4.3.4, Codon 0.20.6); Codon licence/absence of Mojo explained.
- `test_ail_safetynet`: pass (1/1, 350 s). No test modules added/edited.
- Workflow: `workflow_dispatch` only, pinned SHAs identical to `compare-lab.yml`, `persist-credentials: false`, `max-parallel: 4`, outside `.github/`.

**Defects**

1. **The proposed workflow's report job cannot merge anything.** `run.py:566` globs `Path(args.merge).glob('*.json')`, but `actions/download-artifact` with `pattern:` writes each artifact into `results/<artifact>/…` (this repo's own `census-lab.yml` needs `merge-multiple: true` for a flat layout). Reproduced on the exact layout: `python3 run.py --merge results --out x.json` writes `{}` and dies with `TypeError: 'NoneType' object is not subscriptable` at `run.py:580` (`render(None)`). Expected: "merged 10 tasks"; actual: rc=1, empty report.
2. **The five-line summary is malformed**: every bullet reads `- - wall time: …` because `verdict()` returns `- …` and `render()` prepends `- ` (`run.py:508-512`, `RESULTS.md:108-112`).
3. **README understates the methodology change.** `README.md:32` says "the one difference from compare-lab is one cold build"; `run.py:73-76` also cuts `RUN_TIMEOUT` 1500→180, `CASE_TIMEOUT` 120→30, `CALLGRIND_TIMEOUT` 7000→120, skips callgrind above 4 s wall and adds a 240 s case budget. Consequence: 74 of 80 instruction cells are `-`, the instruction verdict rests on n=1, and two rival rows are "timeout" that `run_task.py`'s 1500 s would have measured. The brief asked for measurement exactly as `run_task.py` does.
4. **Safety classification does not implement its stated rule.** `classify()` (`run.py:338-345`) calls any non-zero exit "stops loudly"; README:153 and the docstring say "non-zero exit **with the same stdout prefix**". Observed: `cython-main index` printed 0 bytes vs CPython's `1\n2\n3\n`, `ail overflow` 0 of 25 bytes, both labelled "stops loudly". A tool that prints wrong data then exits would be reported as safe.
5. **No DEVLOG entry** for 2026-11-06 (the brief requires one at the top; `DEVLOG.md` still starts at fnvfix1/2026-11-05).
6. **Empty worker report** — no probes, no numbers, so the mandatory self-check list is absent.

**Pre-existing:** none (no compiler/runtime behaviour changed; nothing to compare against `/tmp/base`).

**Unverified:** the full 10-task re-measurement and most instruction counts were not re-run (budget); action SHAs were not resolved against GitHub. I accidentally let a `--tasks rail_transfer` rerun rewrite `lab/compare_rival/RESULTS.md` (run.py always regenerates it); I restored it with `git checkout` — tree is clean again apart from the untracked `.agent/pipeline.md`.

VERDICT: FIX

1. `--merge` glob is not recursive: `run.py:566` + workflow report job. Probe: nested `results/<artifact>/*.json` (what `actions/download-artifact` produces); expected `merged 10 tasks`, actual `{}` and `TypeError: 'NoneType' object is not subscriptable` (run.py:580).
2. Five-line summary prints `- - ` on every line (`run.py:508-512`, `RESULTS.md:108-112`); expected `- wall time: …`.
3. `README.md:32` claims the only difference from compare-lab is one cold build; the code also changes three timeouts, skips callgrind above 4 s and caps cases at 240 s — fix the statement or restore the reference timeouts.
4. `classify()` (`run.py:338-345`) does not apply the documented same-stdout-prefix test; "stops loudly" cells (`cython-main index`, `ail overflow`) contradict README:153.
5. Missing DEVLOG entry dated 2026-11-06, required by the brief.
6. Worker report is empty; re-submit with the probes and numbers the brief requires.
[commandcode stop=end_turn turns=45 out_tokens=37399]


--- ORIGINAL TASK ---
Lane: cmprival

# cmprival1: compare AIL with its real rivals, the Python compilers Codon, Nuitka, mypyc and Cython (and Mojo if it installs without an account)

Time budget: 150 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
if you can read it (no regressions, CI first, memory cap); on GitHub follow `.agent/` rules.

**Why (owner, 2026-11-06):** the comparison table has C, Rust, Go, Nim and CPython, but AIL's real competitors are tools
that compile Python. The owner wants to know whether AIL still wins any column against them. Losses must be
reported as plainly as wins.

**Number this moves:** a new table `lab/compare_rival/RESULTS.md` with, for each of the 10 tasks in
`lab/compare/src/`, one row per tool: correct (all public + hidden cases match the CPython reference: yes/no, and
how many wrong), wall time (median of 5), instructions, peak RSS, binary/artifact size, compile time, build disk, and
whether the result is a single standalone executable. Plus a safety table (below).

Base: `origin/integ`. Files you may create or edit, and no others (all new):
- `lab/compare_rival/run.py`, `lab/compare_rival/README.md`, `lab/compare_rival/RESULTS.md`, `lab/compare_rival/results.json`
- `lab/compare_rival/toolchains.env` (exact pinned versions of every rival you install)
- `lab/compare_rival/safety/*.py` (probe programs) and `lab/compare_rival/patches/<tool>/<task>/*` (see the source rule)
- `lab/compare_rival/compare-rival.yml`: a proposed GitHub workflow, NOT under `.github/` (workers cannot push
  workflow files; the Claude session installs it after review). Model it on `.github/workflows/compare-lab.yml`
  (one job per task, max-parallel 4, pinned action SHAs, `persist-credentials: false`, manual dispatch only).
Do not edit anything under `lab/compare/`, any workflow under `.github/`, or any compiler file.

Read first: `lab/compare/README.md`, `lab/compare/run_task.py`, `lab/compare/toolchains.env`,
`lab/compare/tasks/<task>/` (gen.py, reference.py) and `lab/compare/src/<task>/` (`main.py` plain Python, `typed.py`
annotated Python that the `ail` column compiles).

## The rule for sources (same algorithm everywhere)

- Every rival compiles the **same** `main.py` or `typed.py` that AIL uses. Nuitka and plain Cython take `main.py`;
  mypyc, Codon and Cython with annotations take `typed.py` (report both Cython variants if both build).
- If a tool refuses a source, record the refusal and its first error line in the table (that is a result). You may
  add the smallest syntax-only patch that makes it build (no algorithm change, no different data structure), stored in
  `patches/<tool>/<task>/` with a one-line reason, and the table marks that row "patched". Never change AIL's sources.
- Wall/instructions/RSS are measured exactly as `lab/compare/run_task.py` does for the other languages; reuse its
  functions instead of re-implementing them where possible.

## Tools

Install with pinned versions, from official sources only (pip/PyPI, the official Codon release tarball from
github.com/exaloop/codon, Modular's official installer for Mojo). Codon: say which license the release carries.
Mojo: only if it installs and runs without creating an account or accepting an interactive license; otherwise
write "not measured: needs an account" and move on. No API keys, no secrets.

## Safety table

5 probe programs, each run by every tool and by AIL, with the expected CPython behaviour:
1. int64 overflow in a loop (`x = x * 3` 50 times), 2. list index out of range in a loop,
3. negative index past the start, 4. division by zero in an expression, 5. deep recursion (100000 levels).
For each tool record: same as CPython / stops loudly with an error / **silently wrong output** / crash (signal).
Silent-wrong is the number that matters most; state it per tool.

## Sub-steps

1. (40 min) `toolchains.env`, install scripts in `run.py`, build all 10 tasks with each tool on the runner, record
   build success/refusal. Commit, push.
2. (60 min) Measure all columns for the tools that built, run all cases against the reference. Commit, push.
3. (30 min) Safety probes and table. Commit, push.
4. (20 min) `RESULTS.md`: the two tables, a 5-line summary of which columns AIL wins and loses against the best rival
   (geomean ratios, like docs/ROADMAP.md "Where AIL stands"), and the proposed workflow file. Commit, push.

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
