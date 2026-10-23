# job job-bench1-10232331  started 2026-10-23T14:32:15Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Benchmark complete and committed.

- Full run: 5 apps, 9 windows × 16 rounds; all AIL/C/Rust builds and controls passed.
- Commit `4d7b350`: only `bench/results/2026-10-23-table.md` and `2026-10-23-b933536.json`.
- Furthest behind C: `binary_cursor_records` 4.534×, `csv_table` 2.500×, `json_query` 1.654×; causes documented in the table.
- Toolchain install: C 121.1 MiB, Rust 616.5 MiB, AIL 17.6 MiB.
- Final-commit tests passed: `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` (334s, 0 failures). Manifest `--check` passed.
- No compiler behaviour changed, so no probes were applicable; this export has no DEVLOG/DIFFERENCES files.
[cost $0.0000, opencode tokens {"total": 627747, "input": 40412, "output": 4218, "reasoning": 4557, "cache.write": 0, "cache.read": 578560}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review report**

Change: commit `4d7b350` adds only `bench/results/2026-10-23-table.md` and `bench/results/2026-10-23-b933536.json`; no compiler code or tests changed.

Verification:
- Diff/commit: exactly the two result files, correct trailer; `git status` clean apart from pipeline-owned `.agent/pipeline.md`.
- Table vs JSON: recomputed every median/range, RSS, binary size and build-disk value; all match the committed JSON.
- Reproduced two apps in a fresh `/tmp` worktree (`binary_cursor_records`, `binary_search`, `--rounds 4`): AIL/C 4.436 and 1.407, AIL/Rust 4.251 and 0.453, versus table 4.534/1.414 and 4.487/0.452; RSS, binary size, build disk and toolchain KiB identical. Data is real.
- Full smoke run: all 5 apps build in AIL/C/Rust and all boundary controls pass.
- Causes in the table checked in source: `BinaryCursor.remaining()` per field read; `csv_table_group_scan` uses `field += ch`, `slots.get`, and parallel count/total/min/max lists; `json_query_file` does `data.decode("utf-8")` plus `json_pointer_scan_bytes`.
- Tests on HEAD: `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass (269 s, 0 failures). `tools/update_manifest.py --check` exits 0.
- Probes/speed: not applicable, no behaviour change. No pre-existing differences to report.

Report claims: all verified (test time differs, 269 s vs claimed 334 s, not material).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 716546, "input": 44248, "output": 4080, "reasoning": 11194, "cache.write": 0, "cache.read": 657024}]

FINAL VERDICT: ACCEPT  2026-10-23T14:54:51Z
