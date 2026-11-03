# job job-ffiex1-11040509  started 2026-11-03T20:11:31Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
**Report**

- Added 4 examples in `examples/ffi/`: `zlib_check.py`, `libm_math.py`, `libc_text.py`, `sqlite_count.py`.
- All 4 produce identical stdout and exit status under `python3` and the compiled binary, on both the default and `AIL_UNIFIED_FORCE=1` builds.
- Added `AIL_CURRENT/test_ail_ffi_examples.py`; skips name the missing header/library. Registered via `tests.d`; manifest check passes.
- No FFI defect was hit, so `ail_ffi.py` / `ail_ffi_lower.py` are untouched.
- Added `docs/FFI.md` and linked it from tutorial section 6.

Probes: `bash ~/tools/cmp.sh` over all four `/tmp/probes/ffi/*.py` showed `g same stdout` and `d same stdout`.

Tests passed: `test_ail_ffi_examples`, `test_ail_ffi`, `test_ail_ffi_handles`, `test_ail_ffi_f3a`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_tutorial`; manifest `--check` rc 0. Commit `2f5b523`; not pushed, so the 20 CI shards were not run.
[cost $0.0000, opencode tokens {"total": 3442071, "input": 197241, "output": 12248, "reasoning": 21574, "cache.write": 0, "cache.read": 3211008}]
    tool time: bash 15.7 min
        602s bash   python3 tools/par_check.py -j 2 test_ail_ffi_examples test_ail_ffi test_ail_ffi_handles test_ail_ffi_f3a test_
        268s bash   python3 tools/par_check.py -j 2 test_ail_ffi_examples test_ail_ffi test_ail_ffi_handles test_ail_ffi_f3a test_
         22s bash   cd /tmp/probes/ffi && export PYTHONPATH=/home/runner/work/_temp/w2/AIL_CURRENT; for f in zlib_check libm_math 
         17s bash   python3 tools/par_check.py -j 2 test_ail_tutorial 2>&1 | tail -20
          8s bash   cd /tmp/probes/ffi && for f in zlib_check libm_math libc_text sqlite_count; do echo "=== $f compile default ==
          7s bash   cd AIL_CURRENT && python3 -B -m unittest -v test_ail_ffi_examples 2>&1 | tail -30
          7s bash   cd /tmp/probes/ffi && for f in zlib_check libm_math libc_text sqlite_count; do rm -f $f.uni; PYTHONPATH=/home/
          5s bash   cd /tmp/probes/ffi && bash ~/tools/cmp.sh zlib_check.py /home/runner/work/_temp/w2 2>&1 | tail -20

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change does:** purely additive — four `examples/ffi/` programs, `test_ail_ffi_examples.py` (+ `tests.d`/manifest), `docs/FFI.md`, a tutorial link, DEVLOG. `ail_ffi.py` / `ail_ffi_lower.py` are untouched; matches the report.

**Verified**
- All 4 examples: `cmp.sh` → CPython exit 0; `g` (unified) and `d` (default) exit 0 and same stdout. Outputs: zlib checksums + `round trip ok`, 6 libm lines with `-0.0`/`inf`/`5e-324`, libc edge + `[Errno 34] Numerical result out of range`, sqlite `1000 500500`.
- New test: 4 tests, 0 skips, OK. `test_ail_safetynet`: OK.
- `tools/update_manifest.py --check` rc 0; `tests.d/test_ail_ffi_examples.txt` registered.
- Docs build command runs; tutorial section 6 link resolves.
- No-feature probe: `--debug-dir` `program.c` byte-identical between HEAD and `/tmp/base` (only path fields differ).
- Probes `zlib_edge.py`, `libc_edge.py`, `sqlite_edge.py` (empty/level 0/9 zlib, int64 edges + base 2/8/16/36, empty/negative/overflow sqlite sums, double close): `g` and `d` both same stdout as CPython. `zlib_edge` also same on base.

**Report claims:** all code/doc/test/commit claims verified. Test claims for `test_ail_ffi`, `test_ail_ffi_handles`, `test_ail_ffi_f3a`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_tutorial`, and 20 CI shards are unverified (not run per review scope; not pushed).

**Pre-existing:** `print(bytes)` is refused by the compiler; found while writing a probe, unrelated to this change. No differences observed.

**Unverified:** big-endian portability of the manual byte-shift out-parameter reads (runner is little-endian); broader affected-test modules; CI shards. Speed skipped: no compiler/runtime hot-path change.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1038035, "input": 42708, "output": 7689, "reasoning": 14582, "cache.write": 0, "cache.read": 973056}]
    tool time: bash 5.2 min
        238s bash   cd /home/runner/work/_temp/w2; cd AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_ffi_e
         19s bash   cd /home/runner/work/_temp/w2; export PYTHONPATH=/home/runner/work/_temp/w2/AIL_CURRENT; for f in zlib_check l
         10s bash   cd /home/runner/work/_temp/w2; export PYTHONPATH=$PWD/AIL_CURRENT; for f in zlib_edge libc_edge sqlite_edge; d
          9s bash   cd /home/runner/work/_temp/w2; export PYTHONPATH=$PWD/AIL_CURRENT; for f in zlib_edge libc_edge sqlite_edge; d
          9s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT; export PYTHONPATH=$PWD; timeout 300 python3 -B -m unittest -v test_
          5s bash   cd /tmp/base; export PYTHONPATH=/tmp/base/AIL_CURRENT; bash ~/tools/cmp.sh /tmp/rprobes/zlib_edge.py /tmp/base
          3s bash   cat > /tmp/rprobes/libc_edge.py <<'PY' from ail_ffi import * @extern(header="string.h", symbol="strlen") def s
          3s bash   cd /home/runner/work/_temp/w2; sed -i 's/print(bytes(buf))/print(buf.decode("latin-1"))/' /tmp/rprobes/libc_ed

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-03T21:55:12Z
