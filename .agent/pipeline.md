# job job-rundiff1_rr1-11070956  started 2026-11-07T00:57:19Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the review's defect and committed on `job-rundiff1_rr1-11070956`.

- `_diff_build_failed` now reports only `LOUD_STOPS` build refusals as `loud stop by design` (exit 4); any unrecognised build stop is a `DIFFER` (exit 3).
- Probes: `--link /nonexistent/libnope.so` → `DIFFER: no native program…`, exit 3; `-I /nonexistent/dir` → DIFFER, exit 3; build refusal → exit 4; int64 overflow → exit 4.
- Added a regression test; updated `docs/CLI.md` and DEVLOG.
- Tests: `test_ail_rundiff` 15 OK (11.5 s), `test_ail_safetynet` 5 OK (180 s), `test_ail_files` 18 OK/1 skip (105 s), `test_ail_corpus_findings3` 2 OK (229 s).
- `tools/update_manifest.py` run; `--check` clean.
- Commit `61c199f` (5 files). Not pushed.
[cost $0.0000, opencode tokens {"total": 1099354, "input": 53907, "output": 5033, "reasoning": 3870, "cache.write": 0, "cache.read": 1036544}]
    tool time: bash 7.1 min, edit 0.0 min
        229s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1200 python3 -B AIL_CURRENT/test_ail_corpus_findings3.py >/tmp/c
        180s bash   cd /home/runner/work/ail-ci/ail-ci && (timeout 1200 python3 -B AIL_CURRENT/test_ail_safetynet.py >/tmp/safetyn
         12s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 900 python3 -B AIL_CURRENT/test_ail_rundiff.py 2>&1 | tail -30
          2s bash   cat > /tmp/probes/p_refuse.py <<'EOF' def main() -> None:     d = {}     d["k"] = 1     view = d.items()     p
          2s bash   mkdir -p /tmp/probes && cat > /tmp/probes/p_agree.py <<'EOF' import sys  data = sys.stdin.read() print("read",
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          1s bash   cat > /tmp/probes/p_build_refuse.py <<'EOF' def f(a, /, b=2):     return a + b   print(f(1, a=3)) EOF cd /tmp/
          0s bash   git status && git log --oneline -10 && git branch --show-current

## review 0
[model opencode/deepseek-v4.1-flash-free]
## What the change really does

Only `_diff_build_failed` changes: a build stop is now `loud stop by design` (exit 4) **only** when `_loud_stop(..., "build")` matches the `LOUD_STOPS` build table; every other build stop is a `DIFFER: no native program…` (exit 3). Docs sentence and a regression test updated. Matches the report.

## Probes (`/tmp/rprobes`, HEAD vs `/tmp/base`)

| probe | HEAD | base |
|---|---|---|
| `run --diff --link /nonexistent/libnope.so p_agree.py` | `DIFFER: no native program…` exit **3** | `loud stop by design` exit 4 |
| `run --diff -I /nonexistent/dir p_agree.py` | `DIFFER…` exit **3** | exit 4 |
| same link failure, CPython exits 2 (`p_exit2.py`) | `DIFFER… (exit 4) where CPython exited 2` exit 3 | identical exit 3 |
| `-I` bad dir, CPython exits 2 | `DIFFER…` exit 3 | identical |
| build refusal `not in the subset` (`p_refuse.py`) | `loud stop by design` exit **4** | same |
| int64 literal out of range (`p_big.py`) | `loud stop by design` exit **4** | same |
| runtime int64 overflow | exit **4** | same |
| `--json` on link failure | `{"outcome":"differ",…,"exit":[4,0]}` exit 3 | — |
| plain `run` (no `--diff`) and agree with exit code 2 | unchanged; `--debug-dir` generated C identical (only temp paths differ) | — |

No new crash, wrong output, or wrong exit status; no pre-existing differences encountered.

## Tests

`par_check.py -j 2 test_ail_rundiff test_ail_safetynet` → both ok (11.7 s / 174.7 s). `test_ail_rundiff` directly: `Ran 15 tests … OK` (new test executes). `tools/update_manifest.py --check` clean; no unexpected files.

## Claim check

- Fix classification to only `LOUD_STOPS` build rows → **verified**.
- `--link`/`-I` → DIFFER exit 3; build refusal/int64 overflow → exit 4 → **verified**.
- Added regression test, updated `docs/CLI.md` and DEVLOG → **verified**.
- `test_ail_rundiff` 15 OK, `test_ail_safetynet` OK → **verified**.
- `test_ail_files`, `test_ail_corpus_findings3` results → **unverified** (not run per reviewer budget).
- `update_manifest.py --check` clean → **verified**.
- Commit `61c199f`, 5 files, not pushed → **verified**.

## Unverified / notes

- Worker's `test_ail_files` and `test_ail_corpus_findings3` runs.
- Speed not measured (CLI-only change; no hot code).
- Pre-existing wording nit (not this change): docs say "last three rows of the table" while the build refusals are the last two rows (three messages).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 784166, "input": 43022, "output": 4877, "reasoning": 6411, "cache.write": 0, "cache.read": 729856}]
    tool time: bash 3.3 min
        176s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_a
         11s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 900 python3 -B AIL_CURRENT/test_ail_rundiff.py 2>&1 | tail -6
          3s bash   cat > /tmp/rprobes/run.sh <<'EOF' #!/bin/bash # run.sh WORKTREE PROBE [args...]; stdin from /dev/null wt=$1; p
          1s bash   cd /tmp/rprobes && echo "=== HEAD link, cpython fails ===" && ./run.sh /home/runner/work/ail-ci/ail-ci p_fail.
          1s bash   cd /tmp/rprobes && cat > p_exit2.py <<'EOF' import sys  print("about to exit") sys.exit(2) EOF echo "=== HEAD 
          1s bash   cd /tmp/rprobes && echo "=== HEAD int64 overflow runtime ===" && ./run.sh /home/runner/work/ail-ci/ail-ci p_ov
          1s bash   cd /tmp/rprobes && echo "=== refuse program ===" && ./run.sh /home/runner/work/ail-ci/ail-ci p_refuse.py run -
          1s bash   cd /tmp/rprobes && rm -rf dbg_head dbg_base PYTHONPATH=/home/runner/work/ail-ci/ail-ci/packaging AIL_SDK_DIR=/

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-07T02:30:00Z
