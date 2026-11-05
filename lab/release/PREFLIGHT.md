# Release 0.1 preflight

Date: 2026-11-05
Checked branch: `origin/integ` at `fcc4ccae33bf` (the single-commit staging export of `staging:integ`)
Command: `python3 tools/release_check.py --branch origin/integ`
Exit status: 1 (at least one check failed)

```text
FAIL   1 version      0.1.0.dev0 is a development version
FAIL   2 changelog    CHANGELOG.md is missing
PASS   3 licenses     MIT OR Apache-2.0 and both license files
FAIL   4 notices      THIRD_PARTY_NOTICES.md is missing (job relnotice1)
FAIL   5 p0-merges    missing merge for relevalorder, relrterr, reldiag, relpkgname, relplatinstall, reltable
INFO   6 p1-figures   P1 done when: the .py sources of the compare-lab tasks reach the typed path on 10/10 tasks, refuse none, and land within 1.5× of the .ail sources on wall time.; comparison: AIL commit `4f1245b`; date 2026-11-02; 10 tasks; run 41393616319; fixture `tools/testdata/compare-report.json`.
FAIL   7 differences  15 open or empty rows in DIFFERENCES.md
INFO   8 branch       origin/integ is 0 commits ahead of origin/main; working tree clean
PASS   9 tag          no tag v0.1.0.dev0 yet
SKIP  10 ci           not requested (use --online)
SKIP  11 wheel        not requested (use --build)
2 pass, 5 fail, 4 info/skip
```

## How to read it

- `PASS` means the condition holds on the checked branch. `FAIL` means it does not and makes the exit status 1.
  `INFO` records a fact that does not block the release; `SKIP` is an opt-in check that was not requested.
- Every file is read with `git show <branch>:<path>`, so the working tree does not change what the report says.
  `--repo DIR` and `--branch NAME` read another checkout or branch; `--remote` names the remote used for `main`.
- `--json` prints the same checks and counts for a machine; `--online` adds the latest `tests.yml` result from
  GitHub; `--build` builds the wheel into a temporary directory through `packaging/ail_wheel_backend.py`.
- The script only reads. It never tags, pushes, merges, publishes or edits a workflow.
- This checkout is the one-commit staging export of `integ`; its flattened history has no `integrate <job>` subjects,
  so check 5 cannot see the six merges here even if they are on the real `integ` branch.

## What fixes each FAIL

| Check | Fix |
| --- | --- |
| 1 version | Bump `packaging/ail_lang/__init__.py` `__version__` from `0.1.0.dev0` to the final `0.1.0` (release owner, before the P3 tag). |
| 2 changelog | Add a root `CHANGELOG.md` with a heading for that final version (`## 0.1.0`). |
| 4 notices | Merge job `relnotice1`, which adds `THIRD_PARTY_NOTICES.md`. |
| 5 p0-merges | Merge the six ROADMAP P0 jobs: `relevalorder`, `relrterr`, `reldiag`, `relpkgname`, `relplatinstall`, `reltable`. Their commits carry `integrate <job>` or `job-<job>-` subjects on the real `integ`. |
| 7 differences | Close the 15 open rows in `DIFFERENCES.md` as their lanes finish: `C?-job-pre388-10280828-2`, `C?-job-pre90-10242040-2`, `C?-job-pre116-10251611-1`, `C?-job-pre138-10250109-2`, `C?-job-rbrbfuzz4-10262129-3/4/5`, `C?-job-rbfuzz4-10240913-3/4/5`, `C?-job-fuzz8-10220554-2/3/4/5`, `C?-job-fuzz8-10221632-2`. Mark each `fixed` when its behaviour is fixed. |

Checks 10 and 11 were `SKIP` because the command above did not pass `--online` or `--build`; run
`python3 tools/release_check.py --branch origin/integ --online --build` at release time for those conditions.
