# job job-clihelpb-11032054  started 2026-11-03T11:54:33Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done on branch `job-clihelpb-11032054`, commit `95dc349`.

- Cherry-picked `0a98612` from `job-clihelp-11031523` (excluded the agent report commit); resolved the DEVLOG conflict by keeping both entries.
- Finished remaining gaps: `--separate`/`--debug-dir` now grouped under experimental in `ail compile --help`; `ail run/build/check` now reject missing sources with one clean message naming the path and next step.
- Verified all 17 subcommands return 0 for `--help`; `--version` works; no-arg and unknown commands exit 2; help no longer advertises brace `.ail` syntax.

Tests on final commit (`python3 tools/par_check.py -j 2`):

| module | time | result |
|---|---:|---|
| test_ail_cli_help | 4.9s | ok |
| test_ail_project | 9.9s | ok |
| test_ail_packaging | 33.3s | ok |
| test_ail_files | 171.6s | ok |
| test_ail_safetynet | 268.5s | ok |
| test_ail_corpus_findings3 | 260.5s | ok |

6 modules, 465s, 0 failed. `tools/update_manifest.py --check` exits 0.

Probes: `hello.py` and `basics.py` both match CPython on default and unified builds; `/tmp/probes/cli_probe.sh` passes all help/version/usage/missing-source/experimental-grouping checks. No push.
[cost $0.0000, opencode tokens {"total": 2384902, "input": 81629, "output": 8456, "reasoning": 11681, "cache.write": 0, "cache.read": 2283136}]
    tool time: bash 8.4 min, write 0.0 min
        467s bash   python3 tools/par_check.py -j 2 test_ail_cli_help test_ail_packaging test_ail_project test_ail_safetynet test_
          8s bash   git fetch origin job-clihelp-11031523 2>&1 | tail -5; git log --oneline origin/job-clihelp-11031523 2>&1 | hea
          6s bash   for p in hello basics; do echo "===== $p"; bash ~/tools/cmp.sh /tmp/probes/$p.py "$PWD" 2>&1 | tail -20; done
          5s bash   cd AIL_CURRENT && python3 test_ail_cli_help.py 2>&1 | tail -60
          4s bash   cd AIL_CURRENT && python3 test_ail_cli_help.py 2>&1 | tail -40
          4s bash   export PYTHONPATH=$PWD/packaging AIL_SDK_DIR=$PWD/AIL_CURRENT PYTHONUTF8=1; for c in run build check new lsp c
          3s bash   bash /tmp/probes/cli_probe.sh "$PWD" 2>&1 | tail -30; echo "cli_status=${PIPESTATUS[0]}"
          3s bash   export PYTHONPATH=$PWD/packaging AIL_SDK_DIR=$PWD/AIL_CURRENT PYTHONUTF8=1; for c in run build check new lsp c

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does:** Rewrites `packaging/ail_lang/cli.py` help/usage (`--help`, per-command help, `--version`, experimental grouping, missing-source guard) and adds help strings to `ail_chatgpt.py`'s argparse parsers; adds `test_ail_cli_help`. No compiler/C-generation change.

**Verified against the report**
- All 17 advertised subcommands return 0 for `--help`; `--version` prints `ailc 0.1.0.dev0`.
- No args and an unknown command each print `SHORT_USAGE` to stderr and exit 2.
- `run`/`build`/`check` on a missing source print the path plus `check the path` and exit 2.
- `grep` of every help page finds no `brace` / `.ail` syntax advertisement.
- Generated C is unchanged: `--debug-dir` `program.c` from base and HEAD for `basics.py` are byte-identical (`native_report.json` differs only in temp paths).
- Probes `hello.py`, `basics.py`, `mut.py` match CPython on both builds, and match base.
- `test_ail_cli_help` (4.8s) and `test_ail_safetynet` (216.7s) pass; `update_manifest.py --check` exits 0.

**Defects**

1. The new help advertises build-only options for `ail run`, and one advertised option is silently ignored.
   ```
   $ ail run -o /tmp/rout /tmp/rprobes/hello.py
   hello 3                       # exit 0
   $ ls /tmp/rout
   No such file                  # expected: the executable written to /tmp/rout
   ```
   ```
   $ ail run --lib mylib /tmp/rprobes/libsrc.py
   usage: ail_chatgpt.py ...
   ail_chatgpt.py: error: --lib output must be an existing directory (-o DIR)   # exit 2
   ```
   `--help` says `options for run and build:` includes `-o`, `--lib`, `--freestanding`, `--m32`, and `RUN_HELP` lists `--lib` under `run`. Expected: run help lists only options run honours (and `--no-ffi`, which run does honour, is missing). The underlying run behaviour is pre-existing, but the new help text makes it a documented option and exposes the raw `ail_chatgpt.py` error.

2. The experimental grouping is still incomplete: `--debug-dir` remains in the ordinary `options:` block of `ail compile-module --help`, `ail compile-library --help` and `ail compile-c --help` (e.g. `ail compile-module --help | sed -n '/^options:/,/^$/p'` lists it after `--json`). Task item 2 requires debug/experimental options under a separate heading; only `compile` was fixed.

**Pre-existing:** base `/tmp/base` also ignores `ail run -o` and fails `ail run --lib` (same exit/output); only the new advertising/help text is new. No compile-output differences.

**Unverified:** did not re-run `test_ail_project`, `test_ail_packaging`, `test_ail_files`, `test_ail_corpus_findings3` (worker-reported); no speed check because the change touches no hot code.

VERDICT: FIX

1. `ail run --help` / top-level `--help`: stop advertising `-o`, `--lib`, `--freestanding`, `--m32` for `run` (or implement them cleanly); `ail run -o /tmp/rout hello.py` is expected to create `/tmp/rout`, actual: exit 0, file absent. `ail run --lib ...` is expected to be absent from run help, actual: listed and fails with raw `ail_chatgpt.py` error.
2. Move `--debug-dir` into an experimental argument group for `compile-module`, `compile-library` and `compile-c`; `ail compile-module --help` currently prints it under `options:`.
[cost $0.0000, opencode tokens {"total": 1127068, "input": 137063, "output": 6231, "reasoning": 24670, "cache.write": 0, "cache.read": 959104}]
    tool time: bash 5.5 min
        218s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_cli_help test_ai
         42s bash   cd /home/runner/work/ail-ci/ail-ci && for p in hello basics mut; do echo "===== BASE $p"; bash ~/tools/cmp.sh 
         41s bash   cd /home/runner/work/ail-ci/ail-ci && for p in hello basics mut; do echo "===== HEAD $p"; bash ~/tools/cmp.sh 
          7s bash   cd /tmp && rm -rf dbg_base1 dbg_head1 out_base out_head AIL_NO_CACHE=1 python3 /tmp/base/AIL_CURRENT/ail_chatg
          4s bash   cd /home/runner/work/ail-ci/ail-ci && export PYTHONPATH=$PWD/packaging AIL_SDK_DIR=$PWD/AIL_CURRENT PYTHONUTF8
          3s bash   cd /home/runner/work/ail-ci/ail-ci && export PYTHONPATH=$PWD/packaging AIL_SDK_DIR=$PWD/AIL_CURRENT PYTHONUTF8
          3s bash   cd /home/runner/work/ail-ci/ail-ci && export PYTHONPATH=$PWD/packaging AIL_SDK_DIR=$PWD/AIL_CURRENT PYTHONUTF8
          3s bash   cd /home/runner/work/ail-ci/ail-ci && export PYTHONPATH=$PWD/packaging AIL_SDK_DIR=$PWD/AIL_CURRENT PYTHONUTF8

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed both review defects and committed as `2be616e`.

- `ail run --help` and top-level help no longer advertise `-o/--output`, `--lib`, `--freestanding`, `--m32` for `run`; run help now lists `--no-ffi`. Top-level help separates build-only options and labels build-only experimental ones.
- `--debug-dir` is now under "experimental and debug options" for `compile-module`, `compile-library` and `compile-c`.
- Strengthened `test_ail_cli_help` to cover both defects.
- Probes: `hello`, `basics`, `readme_edge_values`, `readme_aliasing` all match CPython on both builds; CLI probe passes all help/version/usage/grouping checks.
- Tests on final commit: `test_ail_cli_help`, `test_ail_packaging`, `test_ail_project`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_safetynet` — 6 modules, 0 failed. `update_manifest.py --check` exits 0.

No compiler or generated-C behaviour changed. `ail run -o` remains pre-existing/unsupported, but is no longer advertised.
[cost $0.0000, opencode tokens {"total": 1296842, "input": 46378, "output": 8334, "reasoning": 7186, "cache.write": 0, "cache.read": 1234944}]
    tool time: bash 13.4 min, edit 0.0 min, write 0.0 min
        399s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_cli_help test_ail_packaging test_ail_project tes
        368s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_cli_help test_ail_packaging test_ail_project tes
         13s bash   cd "$PWD" && for p in hello basics readme_edge_values readme_aliasing; do echo "===== $p"; bash ~/tools/cmp.sh
          6s bash   python3 - <<'PY' from pathlib import Path p = Path('AIL_CURRENT/test_ail_cli_help.py') s = p.read_text() old =
          5s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_cli_help 2>&1 | tail -40
          5s bash   python3 - <<'PY' from pathlib import Path p = Path('AIL_CURRENT/test_ail_cli_help.py') s = p.read_text() old =
          4s bash   bash /tmp/probes/cli_probe.sh "$PWD"; echo "probe exit: $?"
          0s bash   git diff AIL_CURRENT/manifest.d/13.txt AIL_CURRENT/manifest.d/bc.txt; python3 tools/update_manifest.py --check

## review 1 failed to run: (no final text) [cost $0.0000, opencode tokens {}]     tool time:  

## review 1
[model opencode-go/deepseek-v4.1-flash]
(no final text)
[cost $0.0000, opencode tokens {}]
    tool time: 

FINAL VERDICT: ERROR  2026-11-03T13:05:15Z
