**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 0
[model commandcode/deepseek-v4.1-flash]
All checks are done. Final report:

## Review: fdinf1 (bench.sh + profile.sh)

**What the change really does:** adds `lab/infer/bench.sh` (5-run AIL-vs-`llama-cli` tok/s table with per-run greedy-id checks), `lab/infer/profile.sh` (callgrind/perf top-10 decode profile, load-only subtracted, mapped to `gpt2.py` def lines), and README/RESULTS sections. No compiler, runtime or benchmark-program file changed: `git diff --stat work..HEAD` = `lab/infer/` only. Matches the report.

**Probes / checks**
- `bench.sh /tmp/ail-infer 5`, full run, exit 0: table printed; 5 AIL runs and 5 llama runs at `-t 1` and `-t 4`, ids equal to `ref.py` on every run (16/16 each); `prompt.txt`→64 ids check passed. `/tmp/rprobes/p1.py` (attrs/dict/list argument) and `p2.py` (int64 boundary): `cmp.sh` both `same stdout`, exit 0; `--debug-dir` C and binary for `p1` identical on HEAD vs `/tmp/base` (compiler untouched).
- `profile.sh /tmp/ail-infer 4`, exit 0: reproduces RESULTS.md exactly — `linear__irl` 84.40%, memset 13.65%, memcpy 1.28%, `ck_add` 0.15%, `py_main` 0.12%, `ail_flist_get` 0.08%, `gelu__irl` 0.08%, `layer_norm__irl` 0.05%, `__expm1_fma` 0.05%, `ail_flist_set` 0.03%; `gpt2.py:73-87/88-98/49-72` match the real `def` lines.
- `test_ail_safetynet`: pass (493 s, 1/1).

**Claims**
- peak RSS 1053 MiB / 417 MiB — verified. Binary 111,120 B / 1,898,560 B — verified.
- "`--strict` and default binaries byte-identical" — verified (same sha256).
- "perf denied, `perf_event_paranoid=4`" — verified (`perf record` and `perf stat` both fail).
- "prefill 120.5×, decode 8.75×" — **unverified, environment-dependent**: my rerun of the same harness gave AIL 352.6 ms/token prefill / 455.7 ms/forward, llama 5.97 / 40.07 ms → 59× prefill, 11.4× decode. AIL and llama are timed in separate blocks, so runner drift biases the ratio (both still show AIL far slower). Not a code defect.
- "loader 58% (`read_f32` 32%, `ail_bytes_get` 19%, memset 7%)" — unverified (script never prints the load profile; my load-only callgrind gives read_f32 61%, `ail_bytes_get` 34%, memset 2.2% of the load-only run).
- Note: RESULTS.md's source column says `runtime (libc)`/`runtime (libm)`, which `profile.sh` prints as plain `runtime` — hand annotation, cosmetic. llama's ids are checked via re-tokenised text, which the report discloses.

**Pre-existing:** none (no compiler/runtime change).

Not checked: absolute timings under the worker's conditions; CI shards (not pushed by design).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=40 out_tokens=28310]

## full suite
test_ail_modules

## suite fix skipped: only 146 minutes left


--- ORIGINAL TASK ---
Lane: fd-infer

# fdinf1: GPT-2 tokens per second, AIL against llama.cpp, plus where AIL's time goes

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** tokens per second for prefill and decode, AIL / llama.cpp, from a repeatable harness, with the
greedy ids checked equal on every run. infer1 reported milliseconds once (decode 10.1x slower); there is no harness
and no profile. Target: a `bench.sh` that prints the table in one run; medians of 5; a ranked list of AIL's top 10
functions by time, each with its share.

Base: `origin/integ`. All files under `lab/infer/`. Do not edit any compiler file. Files you may create or edit:
- `lab/infer/bench.sh` (new), `lab/infer/profile.sh` (new), `lab/infer/RESULTS.md` (a new "Tokens per second" and a
  "Profile" section), `lab/infer/README.md` (how to run them)

## Sub-steps

1. **Harness (25 min).** `bench.sh` uses `fetch.sh` and `export_f32.py` as infer1 does, builds `gpt2.py` with the
   default command and llama.cpp at the tag pinned in `README.md`, then runs 5 times each: AIL (prompt `tokens.txt`,
   16 greedy tokens) and `llama-cli -t 1` (the headline; also `-t 4` as a context row, labelled). It prints prefill
   tok/s, decode tok/s (llama.cpp's first token comes from the prefill: use its own eval count), peak RSS
   (`/usr/bin/time -v`), binary size, and checks the 16 greedy ids against `ref.py` and llama.cpp on every run.
   Commit, push, and open the PR against `integ`.
2. **Run on GitHub (15 min).** Peak RSS is about 1 GB, so run where infer1 ran (see `README.md`). Fill the table.
   Commit and push.
3. **Profile (20 min).** `profile.sh` runs `perf record -g` on the decode (or `valgrind --tool=callgrind` on a
   4-token run if perf is missing) and prints the top 10 C functions with their share, mapped to `gpt2.py` lines
   through a `--debug` build's line table. Write the list into `RESULTS.md` with one line per entry: what it is
   (matmul inner loop, list indexing, bounds checks, ...) and a follow-up job idea. Commit, push, and wait for CI.

## Done-check

- `bash lab/infer/bench.sh` prints the table; the ids are equal on all runs; `RESULTS.md` has the medians and the
  profile list.
- The 20 shards pass (nothing outside `lab/infer/` changed); `git diff --stat origin/integ` shows only `lab/infer/`.

## Stop rule

Stop and report if the greedy ids differ in any run; that is wrong output, give the run and both id lists. Stop at
once and report if any build prints output different from CPython (or from the reference this task names) without a
refusal or a loud stop: give the program, both outputs and the commit. Never commit a change that does that. Stop when
60 minutes pass. Push what is done first.

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
- `lab/infer/` (infer1, merged): `gpt2.py` (AIL), `ref.py` (numpy), `fetch.sh`, `export_f32.py`, `tokens.txt`,
  `README.md` (pinned llama.cpp tag and model), `RESULTS.md`. infer1's numbers: decode 130.6 ms/token AIL vs
  12.93 ms/token llama.cpp `llama-cli -t 1` (10.1x), prefill 64 tokens 8.52 s vs 0.150 s, peak RSS 1.06 GiB vs
  417 MiB; greedy ids equal in all three programs. AIL computes in binary64, llama.cpp in binary32.
- Model weights are never committed (CC BY-SA, large). Runs above about 1 GB of memory go to GitHub, as infer1 did.

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
