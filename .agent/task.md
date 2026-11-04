**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model commandcode/deepseek-v4.1-flash]
I've finished checking. Here's the review.

**What the change really does:** adds a self-containted audit lane — `lab/diffixed/audit.py` (list `fixed` rows of `DIFFERENCES.md` that cite no test/lab file, build one probe per row in both builds, write `AUDIT.md`, exit 1 on a difference), 34 probe programs, `AIL_CURRENT/test_ail_diffixed.py` + registration, and two manifest pins. No compiler/runtime file is touched (probe `plain.py`: generated C from HEAD vs `/tmp/base` is byte-identical except the embedded source path).

**Claims checked**
- 34 probes, `AUDIT.md`, test module, `tests.d` line, 2 manifest shards, only allowed paths: **verified** (`git diff --name-only work..HEAD`; `update_manifest.py --check` rc=0).
- `test_ail_diffixed` passes at 223 s: **verified** — 229.0 s solo (`-j 1`), 0 failures; 293 s only under `-j 2` contention with safetynet.
- `test_ail_safetynet` passes: **verified** (0 failed, `-j 2` run).
- `test_ail_files` / `test_ail_corpus_findings3` pass: **unverified** (not run, not required by this review).
- 33/34 probes match CPython in both builds: **verified** (AUDIT table + test pass; `pre26` is the one exclusion).
- Finding `C?-job-pre26-10240859-1`: **verified** — exact probe on HEAD gives `d: 3.0 3.0 '3.0' 3.0` vs CPython `3.0 3.0 3.0 3.0`, `g` matches. Trigger is a repeated `e.args[0]` *expression*; binding it to a local (`a = e.args[0]`) matches, so "same element twice" is imprecise but the finding is real and correctly attributed to the row.
- "`--run` emits 4 verdicts / no-repro lines / RC=1": **unverified end-to-end** (code path read; the differing outputs reproduced directly). `audited_rows()` on HEAD yields exactly 34.
- "finds 34 rows ... including `C?-job-fuzz65-10231438-1`": **FALSE** — see defect 1.

**My probes** (`/tmp/rprobes`, `bash ~/tools/cmp.sh`): `exact.py` d-differs (finding above), g-matches; `min1.py` (`print("{!r}".format(e.args[0]), e.args[0])`) d-differs, `min2.py` (local binding) matches; `pre166b.py` (genexp via argument/list/dict/attribute), `c168b.py` (`None` bounds via attribute), `pre70b.py` (`None` sep via attribute/argument) all match both builds; `fuzz65.py`, `pre101.py`, `pre104.py` match both builds; `plain.py` C unchanged. **Pre-existing:** only the recorded `pre26` default-build bug (identical on base; no compiler code changed).

**Defect 1 — the audit silently drops `fixed` rows whose status is not the last cell.**
`audited_rows()` takes `cells[-1]` as the status. Three rows put `fixed` in the third cell with the description fourth, so they are missing from `AUDIT.md`, have no probe and no verdict — including the row the report says it found:
- `C?-job-fuzz65-10231438-1` (line 357), `C?-job-pre101-10242138-1` (365), `C?-job-pre104-10242140-1` (366).

Reproducer / expected vs actual:
```
$ python3 lab/diffixed/audit.py | grep -E 'fuzz65|pre101|pre104'
# expected: 3 lines;  actual: no output (exit 1 from grep)
```
Synthetic fixture confirming the parser, not the file, is at fault: row `| B-2 | malformed | fixed | a description after the status |` is skipped while the other three rows are selected. Probes I wrote for those three rows (`/tmp/rprobes/fuzz65.py`, `pre101.py`, `pre104.py`) match CPython in both builds, so no hidden regression is being masked, but the lane is incomplete (34 of the 37 `fixed`, no-test rows) and the report's fuzz65 claim is false.

Minor, non-blocking: four probes exceed the 5–30-line limit (37/36/36/36 lines).

Unverified: `--run` end-to-end including the no-repro line and RC=1; `test_ail_files`/`test_ail_corpus_findings3`; CI shards (cannot push/run here).

VERDICT: FIX

1. `lab/diffixed/audit.py` `audited_rows()` uses `cells[-1]` as the status, so the three `fixed`, test-less rows `C?-job-fuzz65-10231438-1`, `C?-job-pre101-10242138-1` and `C?-job-pre104-10242140-1` (status in the third cell, description in the fourth) get no probe and no verdict. Expected: 37 rows listed with probes; actual: 34, and `python3 lab/diffixed/audit.py | grep -E 'fuzz65|pre101|pre104'` prints nothing. The report's claim that fuzz65 is found is false.
[commandcode stop=end_turn turns=34 out_tokens=33469]


--- ORIGINAL TASK ---
Lane: diffixed

# diffixed1: re-check the `fixed` rows of DIFFERENCES.md that cite no test, each with a probe that becomes a regression test

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** `fixed` rows of `DIFFERENCES.md` with no regression check. diffaudit1 audits the `open`,
empty, `refused` and `declared` rows; nobody checks that the `fixed` rows are still fixed. On 2026-11-04 about 230
rows had a status that starts with `fixed`, and about 34 of them cite neither a `test_ail_*` module nor a `lab/` file
anywhere in the row. Target: every such row has a probe in `lab/diffixed/` and a verdict, and every probe that matches
CPython is locked by a test; a row that differs again is a regression finding (zero silent differences is a release
goal).

Base: `origin/integ`. Files you may create or edit, and no others (all new):
- `lab/diffixed/audit.py`, `lab/diffixed/AUDIT.md`, `lab/diffixed/<slug>.py` (one probe per audited row)
- `AIL_CURRENT/test_ail_diffixed.py` and `AIL_CURRENT/tests.d/test_ail_diffixed.txt` (one line: `test_ail_diffixed`)
- the manifest files that `tools/update_manifest.py` writes
Do not edit `DIFFERENCES.md` (other lanes edit it), the compiler or the runtime. A difference you find is recorded, not
fixed. Do not redo rows that `lab/diffaudit/` already probes.

## Sub-steps

1. **The list (10 min).** Write `lab/diffixed/audit.py`. It parses the `| id | area | difference | status |` table of
   `DIFFERENCES.md` and prints every row whose status cell (trimmed) starts with `fixed` and whose whole row text
   contains neither `test_ail_` nor `lab/`, as `id | area | status`. Put the list and its count in `AUDIT.md`. Commit,
   push, and open the PR against `integ`.
2. **Probes (40 min).** For each row write `lab/diffixed/<slug>.py` (the slug is the id with characters other than
   `[A-Za-z0-9_]` replaced by `_`), 5-30 lines, that exercises exactly what the row says was fixed, using the row's own
   example where it gives one. Start the file with a comment that quotes the row id. Where a row is about ints, add a
   line with a value beyond int64 (rule 2). `audit.py --run` builds each probe in the default build and with
   `AIL_UNIFIED_FORCE=1` (temp dir, `AIL_NO_CACHE=1`, timeout 120 s, at most 2 builds at a time,
   `ulimit -v 1500000`), runs it and `python3`, and gives one verdict per build:
   - `matches`: stdout and exit status equal CPython's;
   - `refused`: the build is refused (a finding if the row says the construct now works);
   - `differs`: output or exit status differs. This is a regression finding: put it at the top of `AUDIT.md` with both
     outputs and the commit range to search (`git log -S` on the row id gives the fixing commit);
   - `no-repro`: the row's text is not enough to write a probe; say why in one line.
   Commit and push every 10 probes.
3. **Test (20 min).** Write `AIL_CURRENT/test_ail_diffixed.py`, copying the build-and-compare structure of
   `AIL_CURRENT/test_ail_std_shlex.py`: every probe whose verdict is `matches` in both builds must still match CPython
   in both builds. Skip when there is no C compiler. Keep it under 4 minutes on one core; if it would be longer, test
   the default build only and say so. Register it (Appendix A rule 6) and run
   `python3 tools/par_check.py -j 2 test_ail_diffixed`. Commit and push.
4. **Report (10 min).** Finish `AUDIT.md`: the table (id, area, verdict default, verdict forced, probe file), the
   counts per verdict, and the findings first. Wait for CI.

## Done-check

- Every listed row has a probe file and a verdict in `AUDIT.md`, or a `no-repro` line.
- `python3 AIL_CURRENT/test_ail_diffixed.py` passes.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

If the list has more than 45 rows, audit the 45 newest (by the date in the id) and list the rest as not done. Stop
when 80 minutes pass. Push what is done first.

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

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`. `DIR/program.c` is
  the generated C. `--strict` means the typed path or a refusal. `-o` must not exist yet. A fallback to the general
  path prints `note: ... built on the general path ...` on stderr.
- AIL is Python syntax plus optional annotations. Ints are int64, and overflow stops loudly.
- Modules in `AIL_CURRENT/stdlib/*.py` are standard modules shipped as AIL source. `AIL_CURRENT/ail_modules.py`
  (`BUNDLED_DIR`, line ~85) searches them after the program's own directory and `AIL_PATH`. Examples:
  `AIL_CURRENT/stdlib/shlex.py` and its test `AIL_CURRENT/test_ail_std_shlex.py`.
- CPython 3.12 is the oracle: compare stdout and the exit status, and stderr where a task says so.

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
