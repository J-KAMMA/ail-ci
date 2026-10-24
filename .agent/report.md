# job job-perf7-10240917  started 2026-10-24T00:17:29Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented on branch `job-perf7-10240917`, commit `425dfc9`.

**Hot spot / fix**
- Instrumented generated C: on the 64 MiB `count` case, read was ~22 ms, `ail_bytes_count_range` ~69 ms of 94 ms total.
- Microbenchmark: existing pair-Horspool ~71 ms vs glibc `memmem` ~38 ms.
- Runtime change in `AIL_CURRENT/python/pkg-v12/cruntime.py`: short-needle, non-Windows `bytes.count` now uses the same non-overlapping `memmem` loop as the C reference; Windows keeps Horspool.

**Benchmark (`python3 bench/compare.py --app binary_search`)**
- Before (base): 98.2 ms; after: 69.2 ms.
- AIL/C: `1.414 [1.411, 1.420] slower` -> `0.994 [0.985, 1.018] tie`.
- AIL/base: `0.703 [0.682, 0.728] faster` (ranges do not overlap).
- AIL/Rust: `0.352 [0.351, 0.364] faster`.

**Probes** (`bash ~/tools/cmp.sh`, both general and default builds)
- `/tmp/probes/count_core.py`: empty/overlap/window/negative/bytearray, needle lengths 0–64 — both builds same as CPython.
- `/tmp/probes/count_sources.py`: bytes via argument, list item, attribute, dict value; str count; aliasing — both same.
- `/tmp/probes/count_boundaries.py`: int64 bounds, inverted windows, empty/overlong needles — both same.

**Tests on final commit**
- `test_ail_left1`, `test_ail_text_find_search`, `test_ail_str_find_alias`, `test_ail_str_rfind`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 48 tests OK, 1 skipped.
- `python3 tools/update_manifest.py --check`: pass.
- No DIFFERENCES row added; observable output is unchanged.
[cost $0.0000, opencode tokens {"total": 3603546, "input": 84481, "output": 24656, "reasoning": 9, "cache.write": 0, "cache.read": 3494400}]
    tool time: bash 12.8 min
        303s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && AIL_NO_CACHE=1 python3 -m unittest test_ail_left1 test_ail_t
        294s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && AIL_NO_CACHE=1 python3 -m unittest test_ail_left1 test_ail_t
         75s bash   cd /home/runner/work/ail-ci/ail-ci && python3 bench/compare.py --app binary_search > /tmp/bs/compare_after.txt
         26s bash   cd /home/runner/work/ail-ci/ail-ci && for p in count_core count_sources count_boundaries; do echo ==== $p ====
         19s bash   cd /tmp/probes && sed -i 's/-9223372036854775808/(-9223372036854775807 - 1)/g' count_core.py count_boundaries.
         17s bash   mkdir -p /tmp/probes && cat >/tmp/probes/count_core.py <<'EOF' def check(label, value):     print(label, value
         15s bash   cd /tmp/bs && python3 - <<'EOF' import importlib.util, pathlib p='/home/runner/work/ail-ci/ail-ci/bench/apps/b
          6s bash   cd /tmp/bs && for b in bs_ail bs_c bs_rust; do echo ==$b==; for i in 1 2 3; do ./icount ./$b count large.bin $

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review of `job-perf7-10240917` (425dfc9)**

**Diff.** `cruntime.py`: for non-Windows `bytes.count` with needles 2–31 bytes, replace pair-Horspool with a non-overlapping `memmem` loop; Windows keeps Horspool. Manifest, DEVLOGs and a benchmark JSON updated.

**Probes (mine, `bash ~/tools/cmp.sh ... $PWD`, both g/d builds)**
- `rp1_len.py` — needle lengths 2–31, all-same/overlap patterns, negative windows, 32/33/64 boundary: same as CPython.
- `rp2_alias.py` — needles sliced out of the haystack, self-overlap, window aliasing: same.
- `rp3_sources.py` — needle via argument/list/attribute/dict, bytearray receiver and needle, negative windows: same.
- `rp4_large.py` — ~130 KB haystack, lengths 2,3,4,7,13,30,31,32, empty/inverted windows: same.
- `rp5_nofeature.py`, `rp6_nobytes.py` — bytes.find/startswith but no count; pure int/str program. `rp6` generated C byte-identical to base; `rp5` differs only in the dead `ail_bytes_count_range` body.
- `rp7_count_small.py` — 2-byte count, windows: same via `cmp.sh`.
- Worker probes `count_core`, `count_sources`, `count_boundaries`: re-ran, all same as CPython on both builds.

**Speed (verified).** Re-ran `bench/compare.py --app binary_search --base work`: AIL 65.8 ms vs base 92.7 ms, `ail/base 0.708 [0.677,0.722] faster`, `ail/c 0.999 [0.979,1.040] tie`, `ail/rust 0.344 faster`. Gain ≈1.41x, ranges disjoint — matches the report.

**Tests (HEAD).** `test_ail_safetynet` (62.8 s), `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_text_find_search`: all pass. `tools/update_manifest.py --check`: pass.

**Claims.** Speed numbers: verified. Probes on both builds: verified. Tests: verified for the modules re-run (did not reproduce the exact 48/1 count). Hot-spot share (22/69/94 ms) and the 71 vs 38 ms microbenchmark: unverified (instrumentation not reproduced). "No output change": verified.

**No pre-existing differences found.**

**Defect.** The new `memmem` call has no declaration in a strict-standard build. The emitted default-path C contains no `_GNU_SOURCE`; glibc declares `memmem` only under `__USE_MISC`/`_GNU_SOURCE`, so compiling that C with `-std=c11` (a mode AIL itself uses for `to_c` output and C-object builds) yields an implicit `int` declaration and truncates the returned pointer.
- Probe: `/tmp/rprobes/rp7_count_small.py` (prints `4 2 2`).
- Repro: `ail_chatgpt.py compile /tmp/rprobes/rp7_count_small.py --syntax python -o /tmp/rp7 --debug-dir /tmp/dbg7u`, then `gcc -std=c11 -O2 /tmp/dbg7u/program.c -lm -o /tmp/rp7_c11 && /tmp/rp7_c11`.
- Expected: `4 2 2`; actual: `Segmentation fault`, exit 139. Same generated C from `/tmp/base` prints `4 2 2` under `-std=c11`, so this is introduced by the change. `cmp.sh` builds are unaffected because the compiler's default (gnu17) flags expose `memmem`.

VERDICT: FIX
1. `ail_bytes_count_range` calls `memmem` without a visible declaration in strict-C11 builds of the emitted C. Probe `/tmp/rprobes/rp7_count_small.py`; expected `4 2 2`, actual segfault (exit 139) after `gcc -std=c11 -O2`; base prints `4 2 2`. Define `_GNU_SOURCE` before the generated file's first system include (or declare/provide a local `memmem`) so the runtime is self-contained.
[cost $0.0000, opencode tokens {"total": 3443044, "input": 103361, "output": 28231, "reasoning": 3804, "cache.write": 0, "cache.read": 3307648}]
    tool time: bash 4.9 min
         93s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 800 python3 ../tools/par_check.py -j 2 test_
         68s bash   date; cd /home/runner/work/ail-ci/ail-ci && timeout 600 python3 bench/compare.py --app binary_search --base wo
         64s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 500 python3 ../tools/par_check.py -j 2 test_
         16s bash   cd /tmp && for p in count_core count_sources; do echo "==== $p"; bash ~/tools/cmp.sh /tmp/probes/$p.py /home/r
          8s bash   cd /tmp && bash ~/tools/cmp.sh /tmp/rprobes/rp3_sources.py /home/runner/work/ail-ci/ail-ci 2>&1 | tail -12
          7s bash   cd /tmp && echo "==== count_boundaries"; bash ~/tools/cmp.sh /tmp/probes/count_boundaries.py /home/runner/work
          7s bash   cd /tmp && python3 /home/runner/work/ail-ci/ail-ci/AIL_CURRENT/ail_chatgpt.py compile /tmp/rprobes/rp3_sources
          5s bash   cd /tmp && bash ~/tools/cmp.sh /tmp/rprobes/rp1_len.py /home/runner/work/ail-ci/ail-ci 2>&1 | tail -12

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `6dc366a`.

- **Fix:** `BYTES` runtime block now self-declares `memmem` on non-Windows after `<string.h>`, so emitted C builds under strict `-std=c11` without relying on `_GNU_SOURCE`.
- **Defect probe:** `/tmp/rprobes/rp7_count_small.py` now prints `4 2 2` under both `-std=c11 -O2` and `-std=gnu17` (previously segfault, exit 139).
- **Probes:** `count_core`, `count_sources`, `count_boundaries`, `rp1`–`rp7` all match CPython on both g and d builds.
- **Speed:** `binary_search` AIL 64.9 ms vs base 92.0 ms; `ail/base 0.711 [0.706,0.717] faster`, `ail/c 0.997 tie`.
- **Tests on final commit:** `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_text_find_search` pass; `update_manifest.py --check` passes.
- DEVLOG entries added; no new DIFFERENCES rows.
[cost $0.0000, opencode tokens {"total": 1562433, "input": 48325, "output": 6099, "reasoning": 5288, "cache.write": 0, "cache.read": 1502721}]
    tool time: bash 6.3 min, edit 0.0 min
        126s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_
        125s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check && cd AIL_CURRENT && date && ti
         69s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 700 python3 bench/compare.py --app binary_search --base 
         54s bash   cd /tmp && for p in probes/count_core.py probes/count_sources.py probes/count_boundaries.py rprobes/rp1_len.py
          1s bash   cd /tmp && rm -rf /tmp/dbgfix2 && python3 /home/runner/work/ail-ci/ail-ci/AIL_CURRENT/ail_chatgpt.py compile /
          1s bash   cd /tmp && rm -rf /tmp/dbgfix && python3 /home/runner/work/ail-ci/ail-ci/AIL_CURRENT/ail_chatgpt.py compile /t
          0s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && git diff --stat && date && timeout 900 python3 ../tools/par_
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c

## review 1
[model opencode/deepseek-v4.1-flash-free]
## Review: job perf7 — memmem for short `bytes.count`

**Change:** `ail_bytes_count_range` uses a non-overlapping `memmem` loop for 2..31-byte needles on non-Windows (Horspool retained for Windows); `BYTES` now declares `memmem` after `<string.h>` so strict-C builds do not get an implicit `int` return.

**Probes (HEAD, g and d builds; all match CPython):**
- Worker probes: `count_core`, `count_sources`, `count_boundaries`, `rp1`–`rp7`.
- Mine (`/tmp/rprobes2`): `b1_31_32` (lengths 2/3/6/7/8/15/16/17/30/31/32/33, windows), `b2_alias2` (needle sliced from haystack, self-match), `b3_types` (bytes/bytearray, arg/list/attr/dict), `b4_edges` (negative/clamped/inverted/huge bounds), `b5_nul` (NUL/0xFF and embedded-NUL needles).

**Boundary/build checks:**
- Emitted C for `rp7` compiles and runs under `gcc -std=c11 -O2`, `-std=gnu17`, `-D_GNU_SOURCE`, `-D_DEFAULT_SOURCE`: `4 2 2`, exit 0.
- Removing the new declaration reproduces the implicit-declaration truncation and exit 139, confirming the reported prior defect.
- No-bytes program (`rp6`) `--debug-dir` C is byte-identical between HEAD and `/tmp/base` (`aff0805`).
- No new DIFFERENCES rows; both DEVLOGs updated; `update_manifest.py --check` passes.

**Tests:** `test_ail_safetynet`, `test_ail_text_find_search`, `test_ail_files`, `test_ail_corpus_findings3` pass on final commit `6dc366a`.

**Speed (my run, `compare.py --app binary_search --base work`):** AIL 64.7 ms vs base 91.5 ms, `ail/base 0.707 [0.705,0.713] faster`; `ail/c 0.999 [0.992,1.000] tie`. Gain ~29%, ranges non-overlapping.

**Report claims:** all verified, including the prior segfault (reproduced by dropping the declaration) and the test list.

**Pre-existing:** none observed; all probes matched CPython on HEAD.

**Unverified:** gdev instruction-count check — no gdev program calls `bytes.count` on bytes, so `compare.py` was used as the relevant hot-path measurement instead.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1016590, "input": 57165, "output": 6440, "reasoning": 11033, "cache.write": 0, "cache.read": 941952}]
    tool time: bash 5.4 min
        100s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_
         67s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 400 python3 bench/compare.py --app binary_search --base 
         65s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_
         54s bash   cd /tmp && for f in rprobes/rp1_len.py rprobes/rp2_alias.py rprobes/rp3_sources.py rprobes/rp4_large.py rprobe
         24s bash   cd /tmp && mkdir -p rprobes2 && cat > rprobes2/b1_31_32.py <<'EOF' def main():     for n in (2,3,6,7,8,15,16,1
          8s bash   cd /tmp && cat > rprobes2/b5_nul.py <<'EOF' def main():     hay = (b"\x00\xff\x00ab\x00\x00" * 40) + b"\x00" *
          3s bash   cd /tmp && rm -rf dbgh dbgb && mkdir -p dbgh dbgb && cp rprobes/rp7_count_small.py dbgh/p.py && cp rprobes/rp7
          1s bash   cd /tmp && for opts in "-std=c11 -O2" "-std=c11 -O2 -Wall -Wextra" "-std=c11 -O2 -Wall -Wextra -Werror" "-std=

FINAL VERDICT: ACCEPT  2026-10-24T01:06:29Z
