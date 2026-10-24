# job job-perf5b-10241003  started 2026-10-24T01:04:06Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
​Implemented and committed on `job-perf5b-10241003` as `eaacb8e`.

**Measured cost** (1.3 MB benchmark, instrumented generated C): read 1.0 ms, UTF-8 validation 0.46 ms, JSON scan 4.35 ms, render 0.12 ms, write 0.14 ms.

**Change:** the scan now validates `null`/`true`/`false`/number tokens directly from the already-validated bytes with `_json_scan_literal_kind`, removing 781,921 per-token decodes on a 39 MB profile. No mmap or borrowed file storage.

**Benchmark**
- Before: `7.9/7.9/4.9/5.3`, ail/base `1.004 [0.986, 1.025] tie`
- After: `7.4/7.9/4.8/5.4`, ail/base `0.933 [0.930, 0.954] faster`
- 6.7% gain, non-overlapping ranges; outputs and boundary controls unchanged.

**Probes** (all match CPython on both builds)
- `file_boundaries.py`: sizes 0, 1, 1 MiB−1, 1 MiB, 1 MiB+1; overwrite/truncate after reading.
- `file_snapshot.py`: same sizes plus overwrite and truncate after read through a function argument.
- `literal_kind.py`: old/new literal validation across valid/invalid numbers, `null`/`true`/`false`, empty, huge, Unicode, negative, list/dict/attribute paths.

**Tests on final commit:** `test_json_pointer_scan`, `test_ail_scan_spec_modes`, `test_json_query_cli`, `test_json_query_file`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 7 modules, 0 failed. Manifest `--check` passes.
[cost $0.0000, opencode tokens {"total": 5103599, "input": 113971, "output": 12796, "reasoning": 16114, "cache.write": 0, "cache.read": 4960718}]
    tool time: bash 9.8 min
        372s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_json_pointer_scan test_ail_scan_spec_modes test_json
         55s bash   python3 bench/compare.py --app json_query 2>&1 | tee /tmp/json_query_before.txt
         43s bash   mkdir -p /tmp/probes && cat > /tmp/probes/literal_kind.py <<'PY' def old_kind(token):     if token == "null": 
         43s bash   for p in /tmp/probes/*.py; do echo "=== $(basename $p)"; bash ~/tools/cmp.sh "$p" "$PWD" | grep -E 'cpython ex
         38s bash   python3 bench/compare.py --app json_query 2>&1 | tee /tmp/json_query_after.txt
          8s bash   python3 - <<'PY' p='AIL_CURRENT/language_examples/json_pointer_scan.ail' s=open(p).read() old='''fn _json_scan
          8s bash   rm -rf /tmp/jqdebug && AIL_NO_CACHE=1 python3 AIL_CURRENT/ail_chatgpt.py compile AIL_CURRENT/language_examples
          7s bash   python3 - <<'PY' import importlib.util, random, json, pathlib spec=importlib.util.spec_from_file_location('app

## review 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
## Review

**What the change really does:** replaces `_json_literal_kind(data[start:i].decode("utf-8"))` in `json_pointer_scan.ail` with a byte-level `_json_scan_literal_kind(data, start, i)` that runs the same number/literal state machine directly on the token bytes. No I/O, mmap or file-buffer code is touched. This matches the report.

**Probes** (all in `/tmp/rprobes`, actual compiled AIL vs CPython):
- `lit.ail` on 2,819 bare-token documents: current == CPython == base, 0 diffs.
- `lit.ail` on 5,304 array/object/nested documents (token boundaries against `]`, `}`, `,`, whitespace): 0 diffs.
- `filesnap.ail`: sizes 0, 1, 1 MiB−1, 1 MiB, 1 MiB+1, plus overwrite and truncate after `read_bytes`: current and base both match CPython; bytes remain snapshots.
- `stdin_sum.ail --debug-dir`: `program.c` byte-identical to base; only temp paths in `native_report.json` differ.
- Worker's three `/tmp/probes` via `cmp.sh`: general and default builds both same stdout.
- General path refuses the AIL-module probe by name (`not in the subset: general path explicitly requested`), identical on base.

**Tests:** `test_json_pointer_scan`, `test_ail_scan_spec_modes`, `test_json_query_cli`, `test_json_query_file`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 7/7 ok, 281s, 0 failed. `tools/update_manifest.py --check` passes.

**Speed:** independent `python3 bench/compare.py --base work --app json_query`: 7.3/7.9/4.8/5.4 ms, ail/base `0.919 [0.913, 0.941]` faster (~8.1%), non-overlapping. Report's committed numbers (0.933 `[0.930, 0.954]`) are verified.

**Claims:** diff, no-mmap/owned-buffer statement, tests, benchmark and worker-probe claim verified. The worker probes only simulate the two algorithms in Python; my compiled-AIL probes cover the real path. Timing breakdown (1.0/0.46/4.35/0.12/0.14 ms) and the “781,921 decodes on 39 MB” count are unverified. `HEAD` also contains `d88ff3e`, which adds only benchmark result JSONs.

**Pre-existing:** none observed. **Unverified:** instruction counts (`perf_event_open: Permission denied`); exact timing breakdown above.

VERDICT: ACCEPT
[cost $0.0367, opencode tokens {"total": 2472712, "input": 81565, "output": 10425, "reasoning": 18610, "cache.write": 0, "cache.read": 2362112}]
    tool time: bash 7.1 min
        283s bash   date; cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_json_pointer_scan test_ail_scan_spec_modes tes
         43s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/*.py; do echo "=== $(basename $p)"; bash ~/tools/cm
         30s bash   date; python3 bench/compare.py --base work --app json_query > /tmp/rprobes/bench.log 2>&1; echo exit=$?; tail 
         22s bash   cd /tmp/rprobes && mkdir -p runcur runbase && python3 - <<'PY' import os for d in ('runcur','runbase'):     fo
         13s bash   cd /tmp/rprobes && rm -rf gdev && mkdir gdev && for p in g00_008 g21_002; do for w in cur base; do wt=$([ $w =
          8s bash   cd /tmp/rprobes && AIL_NO_CACHE=1 AIL_QUIET_FALLBACK=1 AIL_UNIFIED_FORCE=1 python3 /home/runner/work/ail-ci/ai
          7s bash   cd /tmp/rprobes && AIL_NO_CACHE=1 AIL_QUIET_FALLBACK=1 AIL_UNIFIED_FORCE=1 python3 /tmp/base/AIL_CURRENT/ail_c
          7s bash   cat > /tmp/rprobes/lit.ail <<'EOF' use json_pointer_scan; fn main() -> int {     let raw: bytes = read_bytes(s

FINAL VERDICT: ACCEPT  2026-10-24T01:43:27Z
