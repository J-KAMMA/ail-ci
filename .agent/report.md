# job job-docsrun1-11051133  started 2026-11-05T02:35:43Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented and committed as `42e5c27` (not pushed, per the runner instructions).

- Added `AIL_CURRENT/test_ail_docs_blocks.py` plus `tests.d` registration and manifest pins.
- Inventoried 20 fenced blocks: 8 run/verified (4 FFI examples, 3 shell blocks, 1 JSON), 12 skipped with documented reasons, 0 uncovered.
- Added `<!-- docs-test: skip ... -->` / `ffi` markers to `README.md`, `docs/FFI.md`, `docs/LSP.md`, `docs/INSTALL.md`.
- Wrote `lab/docsrun/RESULTS.md` with Before/After tables and skip reasons.

Verification: `test_ail_docs_blocks`, `test_ail_quickstart_docs`, `test_ail_tutorial`, `test_ail_packaging`, `test_ail_examples_mdlite`, `test_ail_files`, `test_ail_corpus_findings3` pass. `test_ail_safetynet` failed only under the 1.5 GB virtual-memory cap; it passes without the cap. No compiler bugs found.
[cost $0.0000, opencode tokens {"total": 2252024, "input": 93452, "output": 13479, "reasoning": 18629, "cache.write": 0, "cache.read": 2126464}]
    tool time: bash 10.5 min, edit 0.0 min, read 0.0 min, write 0.0 min
        413s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; python3 tools/par_check.py -j 2 test_ail_docs_blocks 
        190s bash   cd /home/runner/work/ail-ci/ail-ci && python3 AIL_CURRENT/test_ail_safetynet.py 2>&1 | tail -40
         10s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check && python3 AIL_CURRENT/test_ail
          9s bash   cd /home/runner/work/ail-ci/ail-ci && python3 AIL_CURRENT/test_ail_docs_blocks.py -v 2>&1 | tail -80
          2s bash   cd /home/runner/work/ail-ci/ail-ci && python3 -B AIL_CURRENT/ail_chatgpt.py --help 2>&1 | head -60; echo "---"
          1s bash   pwd && git status --short && git branch --show-current && git log --oneline -5
          1s bash   cd /home/runner/work/ail-ci/ail-ci && tmp=$(mktemp -d) && mkdir -p "$tmp/bin" && cat > "$tmp/bin/ail" <<EOF #!
          1s bash   cd /home/runner/work/ail-ci/ail-ci && git add AIL_CURRENT/test_ail_docs_blocks.py AIL_CURRENT/tests.d/test_ail

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: docsrun1 (`42e5c27`)

**What the diff really does:** adds `AIL_CURRENT/test_ail_docs_blocks.py` (parses the four docs, runs or marks each fenced block), 12 `docs-test` markers, `lab/docsrun/RESULTS.md`, `tests.d` registration, and two manifest pins. No compiler/runtime file is touched.

**Probes** (`/tmp/rprobes/probe_harness.py`, one harness probe with 8 cases):
- unmarked unknown block → test fails (`unknown` not allowed) — expected
- skip with no reason / 2-word reason → test fails — expected
- shell block whose stdout disagrees with its `# output` comment → test fails — expected
- FFI block text not present in the named example → test fails — expected
- invalid JSON block → test fails — expected
- correct shell and Python blocks → test passes — expected

I also ran the two skipped-but-runnable shell blocks directly: the `docs/FFI.md` zlib build/run block (CPython, compile, run all exit 0, same stdout) and the `docs/INSTALL.md` checkout block (`doctor --check` + `compile hello.py`, prints `Hello, AIL!`) both work. The README selected-modules command and `python3 -m ail_lang --version` also work. `cmp.sh` is not applicable: the diff changes no compiler/runtime file, so C output cannot change.

**Tests on HEAD:** `test_ail_docs_blocks` 6 tests OK (9s; 4 FFI examples actually built/run, 3 shell blocks run, JSON parsed, 12 skips); `test_ail_safetynet` 5 tests OK (190s, no cap); `test_ail_quickstart_docs`, `test_ail_tutorial`, `test_ail_packaging`, `test_ail_examples_mdlite`, `test_compare_publish`, `test_ail_examples_hybrid` all pass; `tools/update_manifest.py --check` passes.

**Claim check:**
- 20 blocks / 8 run / 12 skipped / 0 uncovered — verified (table line numbers match base).
- Markers, RESULTS.md, tests.d registration, manifest pins — verified.
- `test_ail_files`, `test_ail_corpus_findings3` pass — unverified (not run).
- `test_ail_safetynet` passes without the 1.5 GB cap — verified; under-cap failure not rerun (environmental, not this diff).
- No compiler bugs — consistent with the diff (no compiler change).

**Notes:** Two skipped shell blocks are runnable here (FFI zlib build/run; INSTALL checkout compile). Their behaviour is covered by the FFI example test and the first-program/check-setup blocks, so the redundancy-based skip reasons are defensible, but they are not the network/OS/editor class the task names. Not a blocking defect.

**Pre-existing / unverified:** safetynet under the 1.5 GB virtual-memory cap; `test_ail_files`; `test_ail_corpus_findings3`; the 20 CI shards; network/macOS/Windows/editor blocks.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1366554, "input": 35368, "output": 7257, "reasoning": 38297, "cache.write": 0, "cache.read": 1285632}]
    tool time: bash 5.7 min
        191s bash   date; cd /home/runner/work/ail-ci/ail-ci && timeout 700 python3 AIL_CURRENT/test_ail_safetynet.py 2>&1 | tail 
         56s bash   cd /home/runner/work/ail-ci/ail-ci; timeout 300 python3 tools/par_check.py -j 2 test_ail_list_ops test_ail_che
         43s bash   date; cd /home/runner/work/ail-ci/ail-ci && timeout 700 python3 tools/par_check.py -j 2 test_ail_quickstart_do
         26s bash   cd /home/runner/work/ail-ci/ail-ci; timeout 600 python3 tools/par_check.py -j 2 test_ail_examples_mdlite test_
          9s bash   date; cd /home/runner/work/ail-ci/ail-ci; time python3 AIL_CURRENT/test_ail_docs_blocks.py 2>&1 | tail -6
          9s bash   date; cd /home/runner/work/ail-ci/ail-ci && timeout 900 python3 AIL_CURRENT/test_ail_docs_blocks.py -v 2>&1 | 
          2s bash   cd /home/runner/work/ail-ci/ail-ci; rm -f /tmp/zlib_check; export PYTHONPATH="$PWD/AIL_CURRENT"; timeout 120 p
          1s bash   d=$(mktemp -d /tmp/instXXXX); ln -s /home/runner/work/ail-ci/ail-ci/AIL_CURRENT "$d/AIL_CURRENT"; printf 'prin

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T04:23:44Z
