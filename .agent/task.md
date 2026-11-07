**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model commandcode/deepseek-v4.1-flash]
Time check: I started at 00:15 and it is now ~00:52, so I'm stopping probes here and writing up.

## What the change really does

Beyond the reported fix, `git diff work..HEAD` adds the whole feature: a `--diff` mode in `packaging/ail_lang/cli.py` (`_split_diff`, `_diff_run`, `_diff_verdict`, `_diff_report`, `_diff_build_failed`, `LOUD_STOPS`), `docs/CLI.md`, `test_ail_rundiff.py` (+ registration), `lab/rundiff/*`, DEVLOG. The last commit `a30063f` is the reported fix: `_split_diff` now keeps a two-word compiler option **and its value** and detects `--diff` in the same scan. That part is correct and verified.

## Defect

The build-failure classifier reports **any** unrecognised build stop as `loud stop by design` (exit 4) whenever CPython ran the program, not just AIL's documented loud errors. The task says exit 4 is for "one of AIL's documented loud errors … list the recognised messages in one table"; a broken link or a bad option is not one of them, and exit 3 is "reserved" for a difference. A real toolchain/compiler breakage is therefore mislabelled as "by design" — the exact failure class the command exists to surface.

Probe 1 — `/tmp/rprobes/p_agree.py` (reads stdin, echoes argv; CPython exits 0):
```
ail run --diff --link /nonexistent/libnope.so p_agree.py   (stdin empty)
```
- expected: `DIFFER` (no native program, the build stopped), exit 3
- actual: `ail diff: loud stop by design: the C compiler rejected this:` , exit 4 (CPython's `read 0` was fine). The "reason" is the driver's banner line, not a cause.

Probe 2 — same program:
```
ail run --diff -I /nonexistent/dir p_agree.py
```
- expected: exit 3 (difference) or exit 2 (usage), not a language limit
- actual: `ail diff: loud stop by design: each --module-path must name an existing directory`, exit 4

`docs/CLI.md` codifies this wrong rule ("Any other build stop is `loud stop by design` when CPython runs the program fine"), so code and docs agree with each other but not with the task.

## Verified (agree with the report)

- Two-word option values now reach the build: `--diff -I .`, `--diff --syntax python`, `--diff --debug-dir DIR`, `--diff -o OUT` all `agree`, exit 0; `-I`-less base exit 2 was the old bug.
- `--diff` detection: `run --diff … prog.py --diff` hands `--diff` to the program (`arg --diff`, agree); `run --diff --` and `run --diff --cc tcc` behave exactly as base (pre-existing).
- `ail run` without `--diff` unchanged: plain run, `--strict --json`, stdin/argv — same as `/tmp/base`; generated C identical (`--debug-dir` A/B diff empty).
- Modes: agree (with stdin/args/base exit code 5), stdout DIFFER (line N, both lines), exception type only (IndexError both → agree, exit 1), exit-code DIFFER, `--json` shape (agree/differ/loud/timeout, `line` null, `seconds` pair, own line after non-newline output), `--timeout 1` → `timeout: native` 124 and `timeout: cpython` 124, `--python` name/path/`=value`, `--timeout=0`/`-3`/`soon` refused with exit 2, int64 overflow → loud stop exit 4, `--exact-int` agree, project mode (`ail.toml` entry) agree.
- Tests: `test_ail_rundiff` ok (12.4 s), `test_ail_safetynet` ok (192.9 s), `test_ail_files` ok, `test_ail_corpus_findings3` ok; `tools/update_manifest.py --check` clean.
- Census spot-check: `corpus/gdev/g01_008.py` really differs (`native ''` vs `'Parsed entries: 6'`).

## Unverified / pre-existing

- Census counts 17/4/9 and 46/1/3: only the one spot-check above was reproduced; the table as a whole is unverified.
- `--cc tcc`, `-- p.py`, `--link` failure exit code: identical on `/tmp/base` — pre-existing, not caused here.
- Speed: CLI-only change, no hot code touched, so no icount run.

VERDICT: FIX
1. `_diff_build_failed` treats every build stop where CPython succeeded as `loud stop by design` (exit 4) instead of only the `LOUD_STOPS` table. Probe `/tmp/rprobes/p_agree.py` with `ail run --diff --link /nonexistent/libnope.so p_agree.py`: expected a `DIFFER`/exit 3 (unrecognised build failure — a compiler/toolchain defect, which this command must not call "by design"), actual `ail diff: loud stop by design: the C compiler rejected this:` exit 4. Same for `-I /nonexistent/dir` (actual exit 4, expected 3 or 2). Fix: gate the exit-4 path on `_loud_stop(..., "build")` and report other build stops as differences; update the docs sentence that blesses the current rule.
[commandcode stop=end_turn turns=31 out_tokens=149397]


--- ORIGINAL TASK ---
Lane: cli

> Re-run of rundiff1, whose GitHub run was lost (no verdict 6.5 h after dispatch). If its branch job-rundiff1-* has work commits, cherry-pick them first and continue; otherwise do the task from scratch on origin/integ. Commit and push after every sub-step, so a cancel does not lose the work again.

# rundiff1: `ail run --diff`: run the program natively and under CPython with the same input, and stop loudly on any difference

Time budget: 120 minutes. Commit and push after each sub-step. Follow `.agent/` rules (no regressions, CI first).

**Why (owner, 2026-11-07):** AIL is for vibe coding (docs/ROADMAP.md). The worst failure of AI-written code is plausible
wrong output. AIL is Python syntax, so CPython is a free oracle: if the native build and CPython disagree, one of them
(usually our compiler, sometimes the program's reliance on unspecified behaviour) is wrong, and the AI should be told
at once.

**Number this moves:** a new command mode with tests; in `lab/rundiff/RESULTS.md`, run it over the 10
`lab/compare/src/*/main.py` programs on their public cases and over 50 corpus programs: count agree / differ /
loud-stop-by-design, with each "differ" listed (that list is a bug list for the compiler: do not fix them here).

## Behaviour (implement exactly; put it in `docs/CLI.md` under a new heading, creating the file if it does not exist)

`ail run --diff [--python PATH] [--timeout SEC] [--json] prog.py [args...]`
1. Build as `ail run` does. Read stdin fully once (if stdin is not a TTY) into a temp file; feed the same bytes to both
   runs. Run the native program, then `PATH prog.py args...` (default: the `python3` that runs `ail`, i.e.
   `sys.executable`), same cwd, same args, same environment, each with the timeout (default 60 s).
2. Compare stdout bytes and the exit code. For an uncaught exception compare the exception type name only (from the
   last line of stderr), not the traceback text.
3. Outcomes, printed on stderr after the program's own output, one line, prefixed `ail diff:`:
   - `agree` (exit with the program's exit code);
   - `DIFFER: stdout line N` with both lines (truncated to 200 chars), or `DIFFER: exit code A vs B`, or
     `DIFFER: exception X vs Y` → exit code 3 (reserve it; say so in docs);
   - `loud stop by design: <reason>` when the native run stopped with one of AIL's documented loud errors where CPython
     continued (int64 overflow, AIL's own refusals); exit code 4. Read the reason from the native stderr; list the
     recognised messages in one table in the code and in docs/CLI.md.
   - `timeout: native|cpython` → exit code 124.
4. `--json`: print one JSON object on stdout at the end instead of the stderr line:
   `{"outcome":..., "line":N|null, "native":..., "cpython":..., "exit":[a,b], "seconds":[t1,t2]}`.
5. The native program's stdout/stderr are shown live as in `ail run`; CPython's are captured, not shown (except in the
   DIFFER line).
6. Docs must warn: the program runs twice, so file writes, network calls and other side effects happen twice.

Base: `origin/integ`. Files you may create or edit, and no others:
- `packaging/ail_lang/cli.py` (the `run` command and its argument parsing only; keep `ail run` without `--diff`
  byte-for-byte unchanged in behaviour);
- `docs/CLI.md`;
- `AIL_CURRENT/test_ail_rundiff.py` (new) and its registration the way other test modules are registered
  (`AIL_CURRENT/tests.d/test_ail_rundiff.txt` if that is the pattern; check `tools/update_manifest.py`);
- `lab/rundiff/*` (new) and the manifest files `tools/update_manifest.py` writes.

## Tests (`test_ail_rundiff.py`)
agree on a small program with stdin; DIFFER on stdout using `--python` pointing to a tiny fake interpreter script that
prints a different line; DIFFER on exit code; exception-type compare (same type → agree even if traceback text
differs); loud stop by design (int64 overflow program); timeout with `--timeout 1`; `--json` shape. Skip cleanly if no C
compiler is available, as other CLI tests do.

## Sub-steps
1. (50 min) Implementation + docs. Commit, push.
2. (40 min) Tests, register, run `test_ail_rundiff` and the existing CLI test modules (find them by grepping for
   `cli.py`/`cmd_run` in `AIL_CURRENT/test_ail_*.py`). Commit, push, wait for CI.
3. (30 min) `lab/rundiff/RESULTS.md` census. Commit, push.

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
