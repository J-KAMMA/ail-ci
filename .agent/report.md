# job job-relnotes-11031523  started 2026-11-03T06:25:17Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
- Rewrote `README.md`: 3-sentence intro, `pip install ailc` + per-OS C compiler, tested 9-line example, `ail run`/`ail build`, int64/`--exact-int`, supported/not-yet, and `docs/COMPARISON.md` link with wins/losses (no copied numbers).
- Added `CHANGELOG.md` 0.1.0 grouped into features, correctness, performance, known limitations.
- Updated `docs/INSTALL.md` to use PyPI `ailc` by default, checkout as fallback.
- Added `AIL_CURRENT/test_ail_readme.py` + `tests.d/test_ail_readme.txt`; extracts the 1 fenced `python` block and runs it through `ail run` via `packaging/ail_lang`, comparing CPython stdout/exit.

Verification on final commit `c64abe3`:
- Required modules: `test_ail_readme`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed, 343s.
- `tools/update_manifest.py --check`: clean.
- Probes `readme_example` and `readme_edge_values`: same stdout as CPython on both default and unified builds.

Commits: `5a015bb`, `c64abe3`. No push, tag, publish, or version change.
[cost $0.0000, opencode tokens {"total": 3454738, "input": 113195, "output": 10378, "reasoning": 11613, "cache.write": 0, "cache.read": 3319552}]
    tool time: bash 13.1 min, write 0.0 min
        424s bash   python3 tools/par_check.py -j 2 test_ail_readme test_ail_safetynet test_ail_files test_ail_corpus_findings3 2>
        344s bash   python3 tools/par_check.py -j 2 test_ail_readme test_ail_safetynet test_ail_files test_ail_corpus_findings3 2>
          7s bash   for p in /tmp/probes/readme_example.py /tmp/probes/readme_edge_values.py; do echo "==== $p"; bash .agent/cmp.s
          7s bash   for p in /tmp/probes/readme_example.py /tmp/probes/readme_edge_values.py; do echo "==== $p"; bash .agent/cmp.s
          2s bash   python3 -B AIL_CURRENT/test_ail_readme.py -v 2>&1 | tail -60
          1s bash   git add CHANGELOG.md README.md DEVLOG.md docs/INSTALL.md AIL_CURRENT/test_ail_readme.py AIL_CURRENT/tests.d/te
          0s bash   git add CHANGELOG.md && git commit -m "reldocs: correct runtime-error and evaluation-order claims in CHANGELOG
          0s bash   git log --all --oneline | head -40; echo ====; git branch -a; echo ====; git tag; echo ====; git show --stat -

## review 0 failed to run: [cost $0.0000, opencode tokens {}]     tool time:  (cut off after 60 minutes) 

## review 0
[model opencode-go/deepseek-v4.1-flash]
(no final text)
[cost $0.0000, opencode tokens {}]
    tool time: 
(cut off after 6 minutes)

FINAL VERDICT: ERROR  2026-11-03T11:09:38Z
