**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode/deepseek-v4.1-flash-free]
## Review: relcheck1 fix

**What the diff really does.** The two commits only change `tools/release_check.py`: check 9 peels `refs/tags/v<version>^{commit}`, check 1 splits off `+local` and anchors pre-release markers, check 2 replaces the `\b` boundary with exact lookarounds; four fixture tests and one manifest line are added. This matches the report.

**Runs**
- `test_ail_release_check`: 12/12 pass.
- `par_check -j 2 test_ail_release_check test_ail_safetynet`: release check ok; safetynet `S4_generators_gc` fails under the 1.5 GB cap, uncapped 5/5 passes -> pre-existing, no compiler/runtime files changed.
- `update_manifest.py --check` 0; `ci_shards.py --check` 0 (module unassigned but spread by `--shard`; not a defect).
- `release_check.py --branch origin/integ` matches `lab/release/PREFLIGHT.md` exactly; `--branch HEAD --build` PASS 11.
- No C probes needed: the diff is only the six allowed non-compiler files.

**Probes** (fixture repos in `/tmp/rprobes`, `--branch main --remote ''`)
- Claimed fixes verified: annotated tag on main PASS 9, annotated tag on old commit FAIL 9; `## 0.1.0.dev0` FAIL 2, `## v0.1.0` PASS 2, `## [0.1.0]` PASS 2; `0.1.0+local`/`0.1.0+ubuntu` PASS 1, `0.1.0.dev0+local` FAIL 1.
- Defect: `0.1.0_rc1` (also `_dev1`, `_a1`) -> check 1 `PASS ... is a final release`; expected FAIL. PEP 440 accepts `_` separators; old `b8a302c` FAILed these, so the new boundary regex `(?:^|[.\-]|(?<=\d))` regressed it.
- Defect: `v0.1.0` tagged on a tree object -> check 9 `PASS ... no tag v0.1.0 yet`; expected FAIL (a tag exists and does not point at main). Old `b8a302c` FAILed; `^{commit}` failure is treated as absence.

**Claims**: all report claims verified except `test_ail_files`/`test_ail_corpus_findings3` (not rerun) and `--online` (not run).

**Pre-existing**: uppercase `0.1.0.RC1` passes check 1 on both old and new; `S4` under the cap; the check 7 15-vs-17 open-cell observation is unchanged.

**Unverified**: `--online`; `test_ail_files`; `test_ail_corpus_findings3`.

VERDICT: FIX
1. Check 1 misses underscore-separated PEP 440 pre-release markers. Probe: fixture with `__version__ = "0.1.0_rc1"`. Expected `FAIL 1 ... development version`; actual `PASS 1 ... final release` (same for `0.1.0_dev1`, `0.1.0_a1`). Allow `_` before `dev|a|b|rc`.
2. Check 9 treats a tag that does not peel to a commit as absent. Probe: `git tag -a v0.1.0 -m rel <tree>` in a fixture. Expected `FAIL 9 ... not main`; actual `PASS 9 ... no tag v0.1.0 yet`. Check for the tag first, then compare its peeled commit; FAIL when peeling fails.
[cost $0.0000, opencode tokens {"total": 1106849, "input": 87904, "output": 5795, "reasoning": 25758, "cache.write": 0, "cache.read": 987392}]
    tool time: bash 9.9 min
        312s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 500 python3 test_ail_safetynet.py 2>&1 | tail -8; echo "e
        254s bash   date; cd /home/runner/work/_temp/w2/AIL_CURRENT && ulimit -v 1500000; timeout 700 python3 ../tools/par_check.p
         15s bash   mkdir -p /tmp/rprobes && cat > /tmp/rprobes/probe_release.py <<'PY' import os, subprocess, sys, tempfile, shut
          6s bash   date; cd /home/runner/work/_temp/w2 && ulimit -v 1500000; timeout 300 python3 tools/release_check.py --branch 
          4s bash   cd /home/runner/work/_temp/w2 && python3 AIL_CURRENT/test_ail_release_check.py -v 2>&1 | tail -22; echo "exit=
          3s bash   cd /home/runner/work/_temp/w2 && git show b8a302c:tools/release_check.py > /tmp/rprobes/old_release_check.py &
          1s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py --check; echo manifest=$?; python3 tools/ci_
          0s bash   cd /home/runner/work/_temp/w2 && timeout 120 python3 tools/release_check.py --branch origin/integ > /tmp/rprob


--- ORIGINAL TASK ---
Lane: relcheck

# relcheck1: `tools/release_check.py`, a release-0.1 preflight that prints every P0/P3 condition as PASS or FAIL

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** release conditions that a script checks instead of a person. Today 0: `docs/ROADMAP.md` lists
the P0 blockers ("all six are merged and the test gate is green") and the P3 steps (merge `integ` into `main`, tag,
publish `ailc`), but nobody can tell in one command how far the release is. The target: a script with at least 10
checks, each PASS, FAIL or INFO with a one-line reason, a test that drives it on a fixture repository, and today's
report committed. The script only reads; it never tags, pushes, merges or publishes.

Base: `origin/integ`. Files you may create or edit, and no others:
- `tools/release_check.py` (new)
- `AIL_CURRENT/test_ail_release_check.py` (new) and `AIL_CURRENT/tests.d/test_ail_release_check.txt` (new, one line:
  `test_ail_release_check`)
- `lab/release/PREFLIGHT.md` (new: today's output and how to read it)
- the manifest files that `tools/update_manifest.py` writes

## The checks (at least these 10)

1. `__version__` in `packaging/ail_lang/__init__.py` is a final release (no `.dev`, `a`, `b`, `rc`) — FAIL today.
2. A `CHANGELOG.md` (root) exists and has a heading for that version.
3. `LICENSE-MIT` and `LICENSE-APACHE` exist; `pyproject.toml` has `license = "MIT OR Apache-2.0"`.
4. `THIRD_PARTY_NOTICES.md` exists (job relnotice1 adds it; FAIL until it merges).
5. Each job in the ROADMAP P0 table (parse the `| Job |` table, do not hard-code the six names) has a merge on the
   checked branch: a commit subject containing `integrate <job>` or `job-<job>-` (see `git log --oneline` on integ).
6. The ROADMAP P1 done condition is shown as INFO with the latest figures found in `docs/COMPARISON.md`, if present.
7. `DIFFERENCES.md` (find its path; `docs/spec/DIFFERENCES.md` or the root `DIFFERENCES.md`): count rows whose
   status is `open` or empty; PASS at 0, else FAIL with the count.
8. The branch is clean and `integ`'s commits not on `main`: INFO with the count (`git rev-list --count main..integ`
   with the remote names given by `--remote`, default `origin`).
9. No tag `v<version>` exists yet (PASS), or it exists and points at `main` (PASS), else FAIL.
10. With `--online` only: the latest `tests.yml` run on the branch head succeeded (`gh run list --workflow tests.yml
    --branch <b> --limit 1 --json conclusion,headSha`); without `--online` this check is SKIP.
11. With `--build` only: the wheel builds into a temp dir through `packaging/ail_wheel_backend.py` and its file name
    contains the version.

Output: one aligned line per check (`PASS  3 licenses  MIT OR Apache-2.0`), then `N pass, M fail, K info/skip`.
Exit status is 1 when any check fails, else 0. `--json` prints the same as JSON. `--repo DIR` and `--branch NAME`
(default `origin/integ`) select what to read; read files with `git show <branch>:<path>`, so the working tree does
not matter.

## Sub-steps

1. **Skeleton and 5 checks (25 min).** Write `tools/release_check.py` with checks 1-5, the output format and
   `--json`. Run it on `origin/integ`. Commit, push, and open the PR against `integ`.
2. **The rest (20 min).** Add checks 6-11. Run it on `origin/integ` and on `origin/main`. Commit and push.
3. **Test (25 min).** Write `AIL_CURRENT/test_ail_release_check.py`. It makes a temp git repository with fake
   `packaging/ail_lang/__init__.py`, `docs/ROADMAP.md` (a P0 table with two jobs), `DIFFERENCES.md`, licenses and
   commits, then runs the script with `--repo` and `--branch` and checks: a dev version fails check 1, a final
   version passes; a missing P0 merge fails check 5 and names the job; two open DIFFERENCES rows report `2`; the exit
   status; `--json` parses. No network, no wheel build in the test. Register it (Appendix A rule 6). Commit and push.
4. **Report (10 min).** Write `lab/release/PREFLIGHT.md`: the date, the integ commit, the script's full output, and
   for each FAIL the job or step that would fix it. Commit, push, and wait for CI.

## Done-check

- `python3 tools/release_check.py --branch origin/integ` prints at least 10 checks and a summary line; check 1 fails
  today with the reason `0.1.0.dev0 is a development version`.
- `python3 AIL_CURRENT/test_ail_release_check.py` passes with at least 6 test methods.
- `lab/release/PREFLIGHT.md` has today's output.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop and report if the ROADMAP P0 table cannot be parsed reliably; give its exact header line. Stop when 80 minutes
pass. Push what is done first.

## Appendix A: standing rules (from agent-brief-rules.md)

1. No regressions: a program that built and matched CPython before must still do so in the default build. A loud
   stop is allowed only where the value cannot be computed.
2. Probe ints beyond int64 wherever ints come from text or arithmetic. (This job touches no compiler code.)
3. Push early, open the PR against `integ`, wait for all 20 `shard` checks (`gh pr checks <n> -R J-KAMMA/ail-ci`, at most
   once every 10 minutes). Report only when all pass, or say which fail and why.
4. Branch from `integ` (or one unmerged PR at most).
5. Memory: wrap heavy runs in `ulimit -v 1500000`; `tools/par_check.py -j 2` at most; leave no background jobs.
6. New test module: `AIL_CURRENT/tests.d/<module>.txt` if the directory exists, else `ail_check.py` MODULES; `git add`,
   `tools/update_manifest.py`, then `tools/update_manifest.py --check`.
7. Never print credentials, run a broad pkill, merge PRs, change repository settings, cancel runs, tag, publish, or edit
   `.github/workflows`. The script itself must never tag, push, merge or publish.
8. Never edit `AIL_CURRENT/ail_chatgpt.py`, `AIL_CURRENT/ail_syntax.py`, `AIL_CURRENT/python/pkg-v12/pyfunc.py`,
   `pyc.py`, `cruntime.py`, `unified.py`, `buildcache.py`, `pyboxed2.py`, `ir/emit_c.py`, or
   `packaging/ail_lang/cli.py`. Other lanes own them. Do not edit `DEVLOG.md` either: put your notes in the files
   this task names. Edit only the files this task names, plus the manifest files that `tools/update_manifest.py`
   writes.

## Appendix B: repository facts

- Version: `packaging/ail_lang/__init__.py` `__version__`; `pyproject.toml` has `dynamic = ["version"]`.
- Integration commits on integ look like `integrate fz227 (job-fz227-11050703)`; merges like
  `Merge pull request #392 from J-KAMMA/cand-...`.
- The release flow is integ -> main -> tag -> PyPI `ailc`; every tag and publish waits for the owner.

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
