# job job-rbpyproof1-11051621  started 2026-11-05T07:22:03Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Re-applied the accepted `pyproof1` change on the current tree and committed as `8be8e05a`.

- Applied `lab/pyproof` (README, RESULTS, programs, report.py, results.jsonl, 7 reproducers), `test_ail_pyproof_report.py`, and its `tests.d` registration. The `agent-worker.yml` hunk was already present.
- `tools/diff_ids.py` is absent on this tree; `tools/update_manifest.py` regenerated pins and `--check` passes.
- Final-commit tests (`par_check -j 2`): `test_ail_pyproof_report`, `test_ail_examples_crate`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5 modules, 0 failed (239 s).
- Probes: 9 run via `cmp.sh`; the 5 bucket reproducers match CPython or are refused by name, `probe_exit3`/`probe_numbers` match both builds, and the 2 documented overflow reproducers remain the census's intended `wrong` rows. `report.py` classified both new probes as `typed` with equal stdout and exit status.
- No push; `.agent/pipeline.md` remains untracked.
[cost $0.0000, opencode tokens {"total": 846102, "input": 44464, "output": 3942, "reasoning": 5888, "cache.write": 0, "cache.read": 791808}]
    tool time: bash 9.2 min, edit 0.0 min
        292s bash   python3 tools/par_check.py -j 2 test_ail_pyproof_report test_ail_examples_crate test_ail_safetynet test_ail_fi
        240s bash   python3 tools/par_check.py -j 2 test_ail_pyproof_report test_ail_examples_crate test_ail_safetynet test_ail_fi
         13s bash   mkdir -p /tmp/probes && cp lab/pyproof/repro/*.py /tmp/probes/ && cat > /tmp/probes/probe_exit3.py <<'EOF' imp
          7s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-pyproof1-11051358 2>&1 | tail -20
          1s bash   printf '%s\tnone\n%s\tnone\n' /tmp/probes/probe_exit3.py /tmp/probes/probe_numbers.py > /tmp/probes/programs.t
          0s bash   git add AIL_CURRENT/test_ail_pyproof_report.py AIL_CURRENT/tests.d/test_ail_pyproof_report.txt lab/pyproof && 
          0s bash   pwd && git status && git branch --show-current && git log --oneline -5
          0s bash   git add AIL_CURRENT/manifest.d/9a.txt AIL_CURRENT/manifest.d/f7.txt DEVLOG.md && python3 tools/update_manifest

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review of `job-rbpyproof1-11051621` (HEAD `8be8e05a`)

**What the change really does.** Pure re-application of the accepted `pyproof1` census: adds `lab/pyproof` (README, RESULTS, 55-program `programs.txt`, `report.py`, `results.jsonl`, 7 reproducers), `AIL_CURRENT/test_ail_pyproof_report.py` + `tests.d` registration, regenerated `manifest.d` pins, and a DEVLOG entry. No compiler/runtime source is touched (`git diff work..HEAD -- AIL_CURRENT/*.py tools/` is empty).

**Fidelity to the accepted diff.** Compared every path in `git diff 803122d3..FETCH_HEAD` against HEAD: all 17 post-images are byte-identical, including `manifest.d/9a.txt`/`f7.txt` and `.github/workflows/agent-worker.yml` (which already lacked `GH_MODELS_TOKEN`). The only extra change is the required DEVLOG entry. `tools/diff_ids.py` is absent at base, at FETCH_HEAD and here, so it could not run.

**Probes (`/tmp/rprobes`, report.py boundaries).**
- typed / general / refused / wrong / oracle-failure fixtures → classified `typed`, `general`, `refused`, `wrong`, `not run` exactly as documented (`p_oraclefail` where CPython also fails is `not run`, not `refused`).
- `bucket_counts` on synthetic records: typed ignored, general note bucketed, two-reason row counted `listed` but not `alone`, timeout line normalised to empty, wrong ignored. Correct.
- `absolute`/`argv`/`gen` paths not separately exercised; `render-only` not exercised.
- All seven `lab/pyproof/repro/*.py` via `cmp.sh`: five match CPython or are refused by name; the two overflow rows reproduce the documented `wrong` behaviour.
- `report.py` does not mutate its source (md5 unchanged before/after).

**C unchanged.** HEAD vs `work` (`/tmp/base`) `--debug-dir` build of a non-feature program: `program.c` identical, binaries identical (only temp paths in `native_report.json` differ). Expected, since no codegen file changed. No speed impact (lab-only change).

**Tests on HEAD (`par_check -j 2`).** `test_ail_pyproof_report`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — all pass. `update_manifest.py --check` → rc 0.

**Report claims.** Re-application, file set, missing `diff_ids.py`, manifest check, probe results: verified. Five-module test run including `test_ail_examples_crate`: unverified (I did not re-run that module). `results.jsonl` base `work 88e666c0` is the original census tree, not this export (`work` = `ab3b5244`); accurate as a record, not a defect.

**Pre-existing:** the two overflow reproducers are the census's documented `wrong` rows; not caused by this change.

**Unverified:** `test_ail_examples_crate`; full census re-run (by design, not required).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 672266, "input": 66843, "output": 5062, "reasoning": 8873, "cache.write": 0, "cache.read": 591488}]
    tool time: bash 6.0 min
        181s bash   cd /home/runner/work/ail-ci/ail-ci && date && python3 tools/par_check.py -j 2 test_ail_files test_ail_corpus_f
        155s bash   cd /home/runner/work/ail-ci/ail-ci && date && python3 tools/par_check.py -j 2 test_ail_pyproof_report test_ail
         10s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in lab/pyproof/repro/*.py; do echo "=== $p"; bash ~/tools/
          3s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/dd2 && mkdir -p /tmp/dd2 && for t in "head:$PWD" "base:/tmp/
          3s bash   cd /home/runner/work/ail-ci/ail-ci && date && python3 lab/pyproof/report.py --programs /tmp/rprobes/programs.t
          3s bash   ls -la /tmp/probes 2>&1 | head; echo ---; cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/probe_exi
          1s bash   cd /home/runner/work/ail-ci/ail-ci && before=$(md5sum lab/pyproof/repro/a-list-parameter-is-read-only.py); pyt
          0s bash   cd /home/runner/work/ail-ci/ail-ci && grep -n "debug-dir" AIL_CURRENT/ail_chatgpt.py | head -5; git worktree a

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T08:57:04Z
