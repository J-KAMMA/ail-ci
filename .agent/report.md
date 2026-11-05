# job job-rbsched1-11051643  started 2026-11-05T07:43:46Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `6d0b4601` on `job-rbsched1-11051643`.

- Re-applied accepted `sched1` change: new `AIL_CURRENT/stdlib/sched.py`, `test_ail_std_sched.py`, `tests.d` registration, 10 `lab/stdlib/sched/` programs + `RESULTS.md`.
- Workflow hunk was already present; manifest regenerated with `tools/update_manifest.py`; `--check` rc=0. `tools/diff_ids.py` does not exist on this tree.
- Added DEVLOG entry and DIFFERENCES row `C?-job-rbsched1-11051643-1`.
- Required tests on final commit: `test_ail_std_sched`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4/4 passed (315s, `-j 2`).
- Probes (`/tmp/probes`): `sched_basic`, `sched_args`, `sched_cancel_alias`, `sched_provenance`, `sched_exception_resume`, `sched_width`, `sched_defaults` — all match CPython stdout/exit on both `cmp.sh` builds.
[cost $0.0000, opencode tokens {"total": 1280991, "input": 71686, "output": 6155, "reasoning": 7374, "cache.write": 0, "cache.read": 1195776}]
    tool time: bash 13.7 min, edit 0.0 min
        395s bash   python3 tools/par_check.py -j 2 test_ail_std_sched test_ail_safetynet test_ail_files test_ail_corpus_findings3
        317s bash   python3 tools/update_manifest.py --check && python3 tools/par_check.py -j 2 test_ail_std_sched test_ail_safety
         86s bash   for p in /tmp/probes/sched_*.py; do echo "=== $(basename $p)"; bash ~/tools/cmp.sh "$p" "$PWD"; done > /tmp/pr
         14s bash   python3 - <<'PY' from pathlib import Path p=Path('/tmp/probes/sched_basic.py') s=p.read_text() s=s.replace('de
          9s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-sched1-11051443 && git log --oneline -3 FETCH_HEAD && git 
          1s bash   git add AIL_CURRENT/stdlib/sched.py AIL_CURRENT/test_ail_std_sched.py AIL_CURRENT/tests.d/test_ail_std_sched.t
          0s bash   pwd && ls -la && git status && git branch --show-current && git log --oneline -5
          0s bash   ls tools/diff_ids.py AIL_CURRENT/tools/diff_ids.py 2>&1; git ls-files | grep -i diff_ids; python3 tools/update

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: rbsched1 re-apply

**What the change really does:** Re-applies the accepted `sched1` change: adds `AIL_CURRENT/stdlib/sched.py` (CPython 3.12 `sched` port: insertion-sorted list queue, `namedtuple` Event, identity `cancel`, `_invoke` dispatch ≤16 positional args, non-empty `kwargs` → `TypeError`), its test module + `tests.d` registration, 10 `lab/stdlib/sched` programs + `RESULTS.md`, a DEVLOG entry, a DIFFERENCES row, and three regenerated `manifest.d` pins. It matches the fetched accepted diff.

**Verification of re-application:**
- All 14 added files are byte-identical to `FETCH_HEAD` (`git diff FETCH_HEAD HEAD` empty).
- `.github/workflows/agent-worker.yml` hunk is already present; current file equals `FETCH_HEAD`.
- `python3 tools/update_manifest.py --check` → rc 0.
- `tools/diff_ids.py` absent from tree (verified), as reported.
- Non-feature C unchanged: `plain.py` built on `work` and HEAD; all generated `.c` files identical (only temp paths differ in `native_report.json`).

**Worker claims:** committed `6d0b4601` (verified); files/test/lab additions (verified); workflow already present (verified); manifest regenerated/`--check` (verified); DEVLOG+DIFFERENCES (verified); 4/4 tests (verified); probes match (verified by re-running `/tmp/probes/sched_*` on HEAD).

**Tests on HEAD:** `test_ail_std_sched`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` → 4/4 passed, 315s, `-j 2`.

**Own probes (`/tmp/rprobes`, both builds):** p1 empty/run, p2 arg counts, p3 float times, p4 cancel/ValueError, p5 queue snapshot+identity, p7 list/dict argument mutation, p8 default `scheduler()`, p9 `enter` relative/negative deadline, p11 delayfunc mutating queue, p12 clock funcs via list item/dict value/attribute, p14 float priorities, p16 cancel-in-action, p17 negative times, p18 ±2^62 widths — all match CPython.

**Documented differences (not defects):** p6/p6b non-empty `kwargs=` raises `TypeError` instead of calling (recorded in DIFFERENCES); p15 two field-equal Events compare unequal and cross-scheduler cancel raises `ValueError` (recorded); p13 refusal for `*args` function first-class value is by name.

**Pre-existing:** p10 `namedtuple._fields`, `_replace`, `_asdict` unsupported — reproduced on `work` with a plain namedtuple, unrelated to this change.

**Unverified:** full suite, packaging test, speed (no hot-path change).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 604306, "input": 34162, "output": 7043, "reasoning": 7325, "cache.write": 0, "cache.read": 555776}]
    tool time: bash 11.1 min
        316s bash   cd /home/runner/work/ail-ci/ail-ci && date && python3 tools/par_check.py -j 2 test_ail_std_sched test_ail_safe
        104s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in /tmp/rprobes/*.py; do echo "=== $(basename $p)"; bash ~
         94s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in /tmp/probes/sched_*.py; do echo "=== $(basename $p)"; b
         84s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in /tmp/rprobes/p6b_kwargs_ok.py /tmp/rprobes/p9_enter_rel
         26s bash   cd /tmp/rprobes && cat > p17_negative.py <<'EOF' import sched now = -10 def t(): return now def d(x):     glob
         26s bash   cd /tmp/rprobes && cat > p15_cancel_equal.py <<'EOF' import sched now = 0 def t(): return now def d(x):     gl
          6s bash   cat > /tmp/rprobes/named_base.py <<'EOF' from collections import namedtuple E = namedtuple('E', 'a, b, c') e =
          5s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/dd_head /tmp/dd_base && AIL_NO_CACHE=1 AIL_QUIET_FALLBACK=1 

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T09:26:47Z
