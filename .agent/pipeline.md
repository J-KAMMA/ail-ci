# job job-srvdef1-11011011  started 2026-11-01T01:13:33Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done on `job-srvdef1-11011011`, commit `45a5882`.

- Server now defaults on for POSIX; `AIL_SERVER=0` disables, Windows stays off.
- First build starts a detached starter behind one per-user `start.lock` in the 0700 runtime dir and compiles in-process; later builds use the warm server.
- Source changes (including pkg-v12) select a fresh server; `--exact-int`, flags, cwd and environment are applied per request.
- Unreachable, slow (>2 s) or crashed servers fall back silently; idle exit remains 600 s.

Acceptance:
- 112 builds (10 `lab/compare`, first 100 `lab/corpus`, exact-int `rail_transfer`/`chain_relax`): return code and generated-C/exe sha256 all identical with and without the server.
- `rail_transfer`/`chain_relax` exact-int C and exe match for `PYTHONHASHSEED=0..5`.
- Median of 5 warm vs 5 in-process builds: `chain_relax` no-cache **2.293 s vs 3.047 s**; hello no-cache **0.368 s vs 0.481 s**; hello with warm cache **0.275 s vs 0.282 s**.

Tests on final commit:
- Server on: `test_ail_server`, `test_ail_build_cache`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 0 failed.
- `AIL_SERVER=0`: `test_ail_server`, `test_ail_build_cache`, `test_ail_safetynet` — 0 failed.

Probes in `/tmp/probes`: `p_srv_arith`, `p_srv_routes`, `p_srv_edges`, `p_srv_functions` match CPython on both builds. `p_srv_exact` matches CPython stdout and server/non-server C+exe with `PYTHONHASHSEED=1`; without a fixed seed the existing compiler may choose typed vs general rendering (same exe/output). `update_manifest.py --check` passes; no new DIFFERENCES rows.
[cost $0.0583, opencode tokens {"total": 4444516, "input": 140036, "output": 16487, "reasoning": 24313, "cache.write": 0, "cache.read": 4263680}]
    tool time: bash 51.0 min
        950s bash   mkdir -p /tmp/probes && cat > /tmp/accept.py <<'PY' import hashlib, os, pathlib, shutil, subprocess, sys, temp
        509s bash   cd /home/runner/work/_temp/w2 && timeout 2400 python3 tools/par_check.py -j 2 test_ail_server test_ail_build_c
        494s bash   cd /home/runner/work/_temp/w2 && timeout 2400 python3 tools/par_check.py -j 2 test_ail_build_cache test_ail_sa
        372s bash   cd /home/runner/work/_temp/w2 && AIL_SERVER=0 timeout 2400 python3 tools/par_check.py -j 2 test_ail_build_cach
        242s bash   cd /home/runner/work/_temp/w2 && AIL_SERVER=0 timeout 2400 python3 tools/par_check.py -j 2 test_ail_server tes
        177s bash   cd /home/runner/work/_temp/w2 && timeout 1800 python3 tools/par_check.py -j 2 test_ail_server 2>&1 | tail -80
         67s bash   cat > /tmp/probes/exact_seeds.py <<'PY' import hashlib, os, pathlib, shutil, subprocess, sys, tempfile, time R
         35s bash   cat > /tmp/probes/p_srv_arith.py <<'PY' def show(label, v):     print(label, v)  def pow2(b, e):     return b 

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review report

**What the change does.** Turns the resident compile server on by default on POSIX (`AIL_SERVER=0`/off/false/no disables), starts it from a detached per-user starter on the first build while that build runs in-process, and makes the client fall back in-process when a server is missing/slow/dead. Only `ail_chatgpt.py`, `ail_server.py`, its test, manifest and DEVLOG changed; no codegen/runtime change.

**Defects**

1. **The “slow (>2 s)” / mid-build crash fallback is neither silent nor correct.** After the server has sent `S` and started the build, losing the connection makes `_wait` return `None` (`AIL_CURRENT/ail_server.py:338`), so `ail_chatgpt.py` re-runs the build in-process while the server's orphaned worker keeps building the same output.
   - Probe `/tmp/rprobes_w2/final_slowack.py`: delay the server's `S` by 3 s (`sitecustomize` wrapping `socket.sendall`). Expected: exit 0, one success JSON, empty stderr (task: “slow (>2 s to answer) … compile in-process and print nothing extra”). Actual: **exit 2**, stdout has the success JSON, stderr `ail_chatgpt.py: error: output already exists`; the produced exe is valid (`HI`). The base (`/tmp/base`, `AIL_SERVER=1`, same delay) exits 0 after 3.18 s.
   - Probe `/tmp/rprobes_w2/final_midbuild_crash.py`: kill the server's per-request supervisor during the build. Expected: compile in-process, print nothing extra. Actual: **exit 1** with an unhandled `FileExistsError: … /out` traceback, while the server's worker already wrote the valid exe and printed the success JSON.
   - The existing `test_slow_server_falls_back_silently` / `test_server_death_falls_back_silently` use a fake server that never builds, so they miss this. Fix: do not fall back after `S` (or cancel/clean the worker's output before rebuilding).

**Report claims**

- Default on / `AIL_SERVER=0` off; first build background+in-process; per-request `--exact-int`/env/cwd/umask: **verified** (tests, probes, cwd/umask probe).
- Source change selects a fresh server: **verified** (`test_source_change_means_a_new_server` passed).
- “Unreachable, slow (>2 s) or crashed servers fall back silently”: **false** (defect 1).
- 112 builds identical: **partially verified** — all 10 `lab/compare` tasks plus `--exact-int` `rail_transfer`/`chain_relax` gave identical C, exe sha256, stdout server vs off; the 100 corpus programs were not run.
- Medians: roughly confirmed (hello: warm 0.236 s vs in-process 0.354 s median of 5).
- Tests on HEAD: `test_ail_server`+`test_ail_safetynet` (server on) 0 failed; `AIL_SERVER=0` `test_ail_server`/`test_ail_build_cache`/`test_ail_safetynet` 0 failed; `test_ail_files`+`test_ail_corpus_findings3` 0 failed. Note `test_ail_build_cache` strips all `AIL_*` vars, so its `AIL_SERVER=0` run actually uses the default (on); it still passed.
- Probes `p1`–`p5` match CPython with server on and off; `p6` exact-int matches C/exe/stdout; HEAD vs base C+exe identical for `p2` and `chain_relax`. `update_manifest.py --check` passes.

**Pre-existing:** none observed; the slow-ACK failure is new (base exits 0).

**Unverified:** full first-100-corpus acceptance set; Windows/macOS default behaviour (macOS lacks `SO_PEERCRED`, so it stays off, not literally “POSIX on”); instruction counts (no codegen change).

VERDICT: FIX
[cost $0.0541, opencode tokens {"total": 2932792, "input": 106818, "output": 14634, "reasoning": 34892, "cache.write": 0, "cache.read": 2776448}]
    tool time: bash 20.4 min
        348s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_files tes
        264s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && AIL_SERVER=0 timeout 1200 python3 ../tools/par_check.py -j 2 test
        228s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_server t
        137s bash   cat > /tmp/rprobes/cmp_srv.py <<'PY' import hashlib, os, pathlib, shutil, subprocess, sys, tempfile, time WT =
        120s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && nohup python3 ../tools/par_check.py -j 2 test_ail_server test_ail
         19s bash   cd /tmp/rprobes && for p in p1_arith p2_routes p3_int64 p4_file p5_hello; do echo "===== $p (server off) =====
         18s bash   cd /tmp/rprobes && for p in p1_arith p2_routes p3_int64 p4_file p5_hello p6_exact; do echo "===== $p (server d
         13s bash   cd /tmp/rprobes && sed -i 's|for pass in 1 2; do|for pass in 1 2; do rm -f /tmp/rprobes/exe_$mode;|' compare_e

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
(no final text)
[cost $0.0574, opencode tokens {"total": 4303214, "input": 104866, "output": 16563, "reasoning": 32153, "cache.write": 0, "cache.read": 4149632}]
    tool time: bash 33.9 min, edit 0.0 min
       1077s bash   cat > /tmp/probes/acceptance.py <<'PY' import hashlib, os, pathlib, subprocess, sys, tempfile, time, shutil, j
        300s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_build_ca
        271s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 2100 python3 ../tools/par_check.py -j 2 test_ail_server t
        224s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && AIL_SERVER=0 timeout 2400 python3 ../tools/par_check.py -j 2 test
         36s bash   cd /tmp/probes && for p in p_srv_arith p_srv_routes p_srv_edges p_srv_functions; do echo "===== $p (server def
         19s bash   cd /home/runner/work/_temp/w2 && python3 -m py_compile AIL_CURRENT/ail_server.py && cd /tmp/probes && python3 
         13s bash   cd /tmp/probes && python3 exact_compare.py; echo rerun; python3 exact_compare.py
         10s bash   cat > /tmp/probes/exact_compare2.py <<'PY' import hashlib, os, pathlib, subprocess, sys, tempfile, shutil WT='
(cut off after 60 minutes)

## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change does (one line):** makes `AIL_SERVER` default-on for Linux/POSIX, starts a per-user-locked server in the background on the first build, adds an "accepted"/"go" handshake with a 2 s fallback, and makes both the supervisor and worker able to report the build result.

**Claim check.** The worker report is empty (“no final text”); the only claims are in `DEVLOG.md`, and I treated those as the report:
- Default on / `AIL_SERVER=0` off / Windows off — **verified**: `UNSET`, `""`, `1`, `yes` started one socket; `0`, `off`, `FALSE`, `no` started none.
- First build in background, later builds warm — **verified** by timing (warm median ~0.44 s vs ~0.66 s in-process for hello) and `test_first_build_starts_the_server_in_the_background`.
- Server notices source changes, including pkg-v12 — **verified** by the existing `CopiedTree` test passing.
- Per-request env/flags, including `--exact-int` — **verified**: on one warm server, `--exact-int` and `AIL_EXACT_INT=1` produced the same C/exe as `AIL_SERVER=0`; default and exact-int requests re-used the same server correctly.
- Silent fallback on slow/crash — **verified**: my fake server that sent `A` then died after receiving `go` gave rc 0, empty stderr, correct `42` output; slow-server test passed.
- 112-build C/exe equality and medians — **partially verified**: 3 compare tasks (plus exact-int rail_transfer/chain_relax) and 8 corpus programs gave identical C and exe; did not rerun all 100.

**Probes** (all in `/tmp/rprobes`; `bash ~/tools/cmp.sh`, default and `AIL_SERVER=0`):
- `p_routes` (arg/list/attr/dict, aliasing, empty/reverse slices), `p_edges` (empty/negative/bool/dict default), `p_mutate` (slice then mutate list/bytearray) — stdout matched CPython on both builds; C/exe identical to the base worktree for `p_routes`/`p_mutate`.
- `p_exact` (big ints through argument, attribute, list, dict) — `--exact-int` C and exe identical with/without server, stdout matched CPython.
- `p_arith` — **Pre-existing**: `OverflowError` on int64 `+`; identical on `/tmp/base`, so not caused by this change.

**Tests** (on HEAD, `-j 2`): `test_ail_server`, `test_ail_build_cache`, `test_ail_safetynet` pass; `test_ail_build_cache` and `test_ail_safetynet` also pass with `AIL_SERVER=0`. `tools/update_manifest.py --check` passes.

**Non-blocking process notes:** the worker supplied no final report text; commit `b506af4` (“fix: uncommitted edits”) lacks the required `Co-Authored-By` trailer.

**Unverified:** exhaustive 10 compare tasks + first 100 corpus programs; Windows behaviour.

VERDICT: ACCEPT
[cost $0.0383, opencode tokens {"total": 1961920, "input": 84821, "output": 8369, "reasoning": 25018, "cache.write": 0, "cache.read": 1843712}]
    tool time: bash 15.3 min
        319s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && rm -f /tmp/srvtest0.log && date && AIL_SERVER=0 timeout 800 pytho
        168s bash   cd /tmp/rprobes && for p in p_arith p_routes p_edges p_mutate; do echo "===== $p default"; bash ~/tools/cmp.sh
        120s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && rm -f /tmp/srvtest.log && (timeout 1500 python3 ../tools/par_chec
         71s bash   cd /tmp && rm -rf /tmp/warm && mkdir /tmp/warm && cp /tmp/rprobes/p_routes.py /tmp/warm/h.py && WT=/home/runne
         44s bash   cd /tmp/rprobes && cat > switchcheck.sh <<'SH' WT=/home/runner/work/_temp/w2 rm -rf /tmp/rprobes/sw; mkdir -p 
         42s bash   cd /tmp/rprobes && bash basecmp.sh /tmp/rprobes/p_routes.py r_routes 2>&1 | tail -5; bash basecmp.sh /tmp/rpro
         41s bash   cd /tmp && rm -rf /tmp/labchk && mkdir /tmp/labchk && WT=/home/runner/work/_temp/w2; for t in chain_relax rail
         29s bash   cd /tmp && rm -rf /tmp/corpchk && mkdir /tmp/corpchk; WT=/home/runner/work/_temp/w2; files=$(find $WT/lab/corp

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-01T05:42:36Z
