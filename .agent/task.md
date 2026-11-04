Lane: frontend

**Finish onelangs15b from its existing work; do not redo it.** The run on branch `job-onelangs15b-11040443` did the work, then ended ERROR because the pipeline's review step crashed (a bug in the job runner, now fixed; not your work's fault), so it got no verdict.

Start by checking whether `origin/integ` already contains this work: if `git diff origin/integ...origin/job-onelangs15b-11040443` adds nothing new, report NOCHANGE and stop.

Otherwise apply that branch's work: cherry-pick, in order, every commit after "export of staging:integ + task" except "agent worker report".

```
git fetch origin job-onelangs15b-11040443
git log --oneline origin/job-onelangs15b-11040443
```

Commits named "worker: uncommitted edits" or "fix: uncommitted edits" hold unfinished work: read them, then finish the job.

Then verify against the original task below: re-run its measurements and targeted tests, check the boundary cases, fix what is wrong, and report the numbers. Time budget: 60 minutes.

**Owner decisions (2026-11-03):** AIL is one language, Python syntax plus optional annotations. The compare-lab `ail` column may use the converted annotated `typed.py` when its C is identical, and the plain `main.py` stays as its own row. The brace front end is removed before the 0.1 tag. AIL-only built-ins are spelled `from ail import ...`.

# onelang s15: `ail convert`, the deprecation warning, lab/flags and lab/syntax

Time budget: 80 minutes. Commit and push after each sub-step.

**Number this moves:** `ail convert FILE.ail [-o FILE.py]` exists; compiling a brace or S-expression source prints one
warning line on the compiler's stderr; no tracked program outside `lab/syntax/runs` and the s16 removal list is still a
`.ail` file.

Base: `origin/integ` after onelang s14 merged.

## Sub-steps

1. CLI: add the `convert` subcommand to `AIL_CURRENT/ail_chatgpt.py` (and so to `ail` from the wheel,
   `packaging/ail_lang/cli.py` if it lists subcommands) calling the converter core; move the core from `tools/ail2py.py`
   into `AIL_CURRENT/ail2py.py` and leave `tools/ail2py.py` as a thin wrapper. `ail convert --check` = the `--check` of
   s1/s3. Commit, push, open the PR.
2. Warning: when `load()` selects brace syntax (`detect` true, `--syntax ail`, or `ail_sexpr.detect` true), print once
   per build to the compiler's stderr: `warning: <file>: the brace syntax is deprecated and will be removed; convert it
   with: ail convert <file>`. Never on the built program's output. `AIL_BRACE_WARNING=0` silences it (tests that
   compare compiler stderr exactly set it; find them by running the full suite). Commit, push.
3. `lab/flags/programs/*.ail` (4 files, already Python text) -> `.py`; update `lab/flags/configs.json` /
   `run_config.py`. Commit, push.
4. `lab/syntax/score.py`: before compiling a brace attempt (`attempt1.ail` whose variant is brace), convert it with
   `ail convert` to a temp `.py` and compile that; the `runs/` files stay as they are (experiment records). Commit, push.
5. Full suite once (`tools/par_check.py -j 2` all modules) because of the stderr line; fix by setting
   `AIL_BRACE_WARNING=0` only in tests that compare the compiler's stderr byte for byte. Commit, push.

## Done-check

`ail convert lab/syntax/runs/_sample/ail-brace/caesar/attempt1.ail` prints a Python file that `python3` runs; building
any brace file prints the warning once; `git ls-files '*.ail'` lists only `lab/syntax/runs/**` and
`AIL_CURRENT/language_examples/**`; all 20 shards pass.

## Stop rule

a compiler change outside the files named here would be needed; any compare-lab `program.c` changes; any listed test module fails for a reason the base did not have; or 80 minutes pass. Push what is green and report. Do not touch `.github/workflows`.

## Appendix A: standing rules

1. No regressions: a program that built and matched CPython before must still do so in the default build.
2. Probe ints beyond int64 wherever ints come from text or arithmetic; run probes in the default build and with
   `AIL_UNIFIED_FORCE=1`, compare both with `python3`.
3. Push early, open the PR against `integ`, wait for all 20 `shard` checks (`gh pr checks <n> -R J-KAMMA/ail-ci`, at most
   once every 10 minutes). Report only when all pass, or say which fail and why.
4. Branch from `integ` (or one unmerged PR at most).
5. Memory: wrap heavy runs in `ulimit -v 1500000`; `tools/par_check.py -j 2` at most; leave no background jobs.
6. New test module: `AIL_CURRENT/tests.d/<module>.txt` if the directory exists, else `ail_check.py` MODULES; `git add`,
   `tools/update_manifest.py`, then `--check`.
7. Never print credentials, run a broad pkill, merge PRs, change repository settings, cancel runs, or edit
   `.github/workflows`.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--syntax python] [--strict] [--debug-dir DIR]`;
  `DIR/program.c` is the generated C; `--strict` = typed path or refuse. `-o` must not exist yet.
- Brace front end: `AIL_CURRENT/ail_syntax.py` `detect()` (about line 206) and `translate()` (about line 285), which
  turns brace text into annotated Python text (`-> R` becomes `-> __ail_checked_R__`). `python_surface()` (about line
  4101) maps Python spellings onto the compiler's built-ins. The per-file loader is `load()` in
  `AIL_CURRENT/ail_chatgpt.py` (about lines 4908-5190; `syntax == 'ail'` branches there are brace-only checks).
- `use m` resolves `AIL_CURRENT/language_examples/m.ail` (`standard = ROOT / 'language_examples'`, about line 4897 of
  ail_chatgpt.py). Python `from m import *` is merged by `AIL_CURRENT/ail_modules.py` `merge_program`, which renames
  `m.f` to `m__f` in the C.
- The converter (onelang s1-s3): `python3 tools/ail2py.py SRC.ail [-o OUT.py] [--check [--flags "..."]]`; `--check`
  prints `identical` / `identical-renamed` / `differ ...` / `py-refused ...` / `both-fail`.
- compare-lab: `lab/compare/src/<task>/main.ail` (brace) and `main.py` (plain CPython program; the pyreach line works on
  these); `lab/compare/run_task.py` (`LANGS`, `SOURCE` map about line 33, `build_cmd` about line 58,
  `EXACT_INT_TASKS = ('rail_transfer', 'chain_relax')`, cold builds with a fresh `AIL_CACHE`, `compile_s` = median).
  Tasks: berth_sim chain_relax echo_pack ledger_bin rail_transfer scar_life tally_lang term_rank ticket_audit tree_fold.
- Census of 2026-11-03 (integ f6d5825c): 391 tracked `.ail` (268 `AIL_CURRENT/language_examples`, of which 262 brace and
  137 entry programs; 10 compare-lab; 109 `lab/syntax/runs` experiment records; 4 `lab/flags/programs`, Python text);
  147 test modules embed brace sources (699 `fn main(`), 37 test modules read `language_examples/`, 46 hash
  `pyfunc.to_c(...)` codegen pins.

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
