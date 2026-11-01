# job job-std_base64-11012057  started 2026-11-01T12:00:56Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed both review defects and committed `08c392a`.

- `b16decode` now rejects non-bytes/non-str with CPython's `argument should be a bytes-like object or ASCII string, not '...'`.
- `b64encode(altchars=...)` now rejects non-bytes-like altchars after the length assert with `a bytes-like object is required, not '...'`.
- Probes `r_b16.py`, `r_badtypes.py`, `r_alt.py`, `r_b16b.py`: all match CPython on both builds.
- Tests: `test_ail_std_base64` (2), `test_ail_safetynet` (5), `test_ail_files` (18, 1 skip), `test_ail_corpus_findings3` (2) — all passed.
- `tools/update_manifest.py --check`: exit 0. DEVLOG entry added.
[cost $0.0000, opencode tokens {"total": 1040208, "input": 44901, "output": 6018, "reasoning": 7913, "cache.write": 0, "cache.read": 981376}]
    tool time: bash 15.1 min, edit 0.0 min
        262s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && AIL_NO_CACHE=1 timeout 1800 python3 -m unittest -v test_ail_
        222s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && AIL_NO_CACHE=1 timeout 1200 python3 -m unittest -v test_ail_
        177s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && AIL_NO_CACHE=1 timeout 1800 python3 -m unittest -v test_ail_
        106s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && AIL_NO_CACHE=1 timeout 1200 python3 -m unittest -v test_ail_
         44s bash   cd /tmp/rprobes && cat > r_alt.py <<'EOF' import base64 for alt in (b'+-', b'++', b'//', bytearray(b'+-'), '+-
         44s bash   cd /tmp/rprobes && for p in r_b16 r_badtypes; do echo "##### $p"; timeout 300 bash ~/tools/cmp.sh /tmp/rprobes
         26s bash   cd /tmp/rprobes && for p in r_b16 r_badtypes; do echo "##### $p"; timeout 300 bash ~/tools/cmp.sh /tmp/rprobes
         22s bash   cd /tmp/rprobes && cat > r_badtypes.py <<'EOF' import base64 for v in ([1, 2], 123, bytearray(b'ab'), 'ab', b'

## review 0
[model opencode/deepseek-v4.1-flash-free]
## review 2
**Change (one line).** `08c392a` adds a `_ail_hl_need_bytes` call to `_ail_hl_b16d_dyn`, and passes a `kind` into `_ail_hl_alt_bytes` so the lowerer's altchars helpers reject non-bytes-like altchars after the length assert; plus DEVLOG/manifest updates.

**Probes (both builds, `bash ~/tools/cmp.sh ... $PWD`, HEAD vs `/tmp/base` from `git worktree add /tmp/base work`).**
- `/tmp/rprobes/r_b16.py`: HEAD matches CPython (g/d); base shows the old `has no len()` / `Non-base16 digit` errors. Defect 1 fixed.
- `/tmp/rprobes/r_badtypes.py`: HEAD matches (`a bytes-like object is required, not 'list'`); base returns `b'\x01\x028='`. Defect 2 fixed.
- `/tmp/rprobes/r_alt.py`, `r_b16b.py`: HEAD matches both builds.
- `/tmp/rprobes2/p_len.py` (altchars lengths 0,1,2,3,4; bytes/bytearray/str/list/int, enc+dec): matches.
- `/tmp/rprobes2/p_mv.py` (`memoryview`): identically refused on HEAD and base (`the name 'memoryview' is not a known function/class/builtin`) — not a regression.
- `/tmp/rprobes2/p_order.py` (invalid data + invalid altchars, incl. list item/attribute/dict value): two new mismatches, below. Base matched CPython on those two; `b64decode(123, altchars=...)` differs on base too (pre-existing).

**Tests.** `par_check.py -j 2 test_ail_std_base64 test_ail_safetynet`: 2 modules, 0 failed, 223s. `update_manifest.py --check`: exit 0.

**Claims.** b16decode type rejection — verified. altchars non-bytes rejection for valid data — verified. `r_alt`/`r_b16b` match — verified. Manifest/DEVLOG — verified. `test_ail_files`/`test_ail_corpus_findings3` — unverified (not rerun). Speed — not checked (error-path-only change).

**Pre-existing.** `b64decode(123, altchars=...)` already reports the wrong type on base (`'int' object is not iterable` / altchars name) and still does; `memoryview` input is refused on both.

**Defects.**
1. `b64encode` now validates `altchars` before it validates/encodes `s`, but CPython runs `binascii.b2a_base64(s)` first. Introduced regression; base matched CPython. Probe:
```python
import base64
def enc(s, a):
    try: print('enc', repr(s), repr(a), base64.b64encode(s, altchars=a))
    except Exception as e: print('enc', repr(s), repr(a), type(e).__name__, str(e))
enc(123, [1, 2])
enc('x', [1, 2])
```
Expected (CPython and base): `enc 123 [1, 2] TypeError a bytes-like object is required, not 'int'` / `enc 'x' [1, 2] TypeError a bytes-like object is required, not 'str'`.
Actual HEAD (g and d): `enc 123 [1, 2] TypeError a bytes-like object is required, not 'list'` / `enc 'x' [1, 2] TypeError a bytes-like object is required, not 'list'`. Cause: the helper-call argument check in `_ail_hl_alt_enc_dyn`/`_ail_hl_alt_bytes` fires before `_ail_hl_b64e_alt` sees the data. Validate/encode `data` before checking `altchars` (e.g. pass raw altchars into `_ail_hl_b64e_alt` and check data first).

**Unverified.** Generated-C byte-identity for non-base64 programs (not diffed); `test_ail_files`, `test_ail_corpus_findings3`.

VERDICT: FIX
1. `b64encode` with both invalid data and invalid altchars reports the altchars type instead of the data type (probe above): expected `...not 'int'` / `...not 'str'`, actual `...not 'list'`. This regressed from base, which matched CPython.
[cost $0.0000, opencode tokens {"total": 470702, "input": 32211, "output": 4316, "reasoning": 11135, "cache.write": 0, "cache.read": 423040}]
    tool time: bash 7.3 min
        225s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && AIL_NO_CACHE=1 timeout 1500 python3 ../tools/par_check.py -j
         86s bash   cd /tmp/rprobes && for p in r_b16 r_badtypes; do echo "##### $p HEAD"; timeout 300 bash ~/tools/cmp.sh /tmp/rp
         52s bash   cd /tmp/rprobes2 && for p in p_mv p_order p_len; do echo "##### $p HEAD"; timeout 400 bash ~/tools/cmp.sh /tmp
         44s bash   cd /tmp/rprobes && for p in r_alt r_b16b; do echo "##### $p HEAD"; timeout 400 bash ~/tools/cmp.sh /tmp/rprobe
         29s bash   cd /tmp/rprobes2 && echo "##### p_order BASE"; timeout 400 bash ~/tools/cmp.sh /tmp/rprobes2/p_order.py /tmp/b
          0s bash   git worktree add /tmp/base work 2>&1 | tail -3; ls /tmp/base | head
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check; echo "manifest exit $?"; date
          0s bash   git show --stat a93407e | head -40; git log --oneline -3 a93407e

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed the remaining review defect and committed `fa6eb63`.

- `b64encode` now validates/encodes `data` before touching `altchars`; decode ordering matches CPython too, and runtime `altchars=None` behaves like omission.
- Probes match CPython on both builds: `/tmp/probes/order_{literal,static,alts,containers}.py`, `/tmp/rprobes/{p_order,r_badtypes,r_alt,r_b16,r_b16b}.py`, `/tmp/rprobes2/p_len.py`; `p_mv.py` is refused identically.
- Tests: `test_ail_std_base64`, `test_ail_crypto`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5 modules, 0 failed, 593s.
- `update_manifest.py --check`: exit 0.
- Compare tasks: 5 generated C files byte-identical; 5 refusal logs identical.
[cost $0.0000, opencode tokens {"total": 2388013, "input": 117224, "output": 9047, "reasoning": 17390, "cache.write": 0, "cache.read": 2244352}]
    tool time: bash 19.8 min, edit 0.0 min
        594s bash   cd /home/runner/work/ail-ci/ail-ci && AIL_NO_CACHE=1 timeout 2400 python3 tools/par_check.py -j 2 test_ail_std
        315s bash   cd /tmp && rm -rf cmpctasks && mkdir cmpctasks && cd cmpctasks && fail=0; for t in berth_sim chain_relax echo_
         88s bash   cd /tmp/rprobes && for p in r_b16 r_badtypes r_alt r_b16b; do echo "##### $p"; timeout 400 bash ~/tools/cmp.sh
         48s bash   cat > /tmp/probes/order_literal.py <<'EOF' import base64 def show(tag, fn):     try:         print(tag, fn()) 
         45s bash   cat > /tmp/probes/order_alts.py <<'EOF' import base64 alts = [b'', b'+', b'+-x', b'abcd', bytearray(b''), byte
         29s bash   cd /tmp/rprobes2 && for p in p_len p_mv; do echo "##### $p"; timeout 400 bash ~/tools/cmp.sh /tmp/rprobes2/$p.
         23s bash   cd /tmp/rprobes2 && timeout 400 bash ~/tools/cmp.sh /tmp/rprobes2/p_order.py /home/runner/work/ail-ci/ail-ci 2
         23s bash   cd /tmp/rprobes2 && timeout 500 bash ~/tools/cmp.sh /tmp/rprobes2/p_order.py /home/runner/work/ail-ci/ail-ci 2

## review 1
[model opencode/deepseek-v4.1-flash-free]
**Change (one line).** `08c392a`+`fa6eb63` move altchars validation into the runtime helpers *after* data conversion, accept runtime `altchars=None`, and add the bytes-like check to `_ail_hl_b16d_dyn`; manifest hashes and DEVLOG follow. This matches the report.

**Probes** (HEAD, both builds, plus base where needed).
- `pb16_int/none/list`, `r_b16`, `r_b16b`, `r_badtypes`, `r_alt`: same stdout, stderr type text and exit as CPython, both builds.
- `order_literal/static/alts/containers`, `p_types3`, `p_len`: match (altchars as literal, variable, dict value, attribute, list item).
- `p_none` (runtime `altchars=None`, valid and invalid data, encode+decode): matches.
- `pba_mut` (bytearray data/altchars mutated after use): stdout/exit identical to CPython and to base.
- `pmv_alt`, `p_mv`: refused identically on HEAD and base (`memoryview` not in subset).
- Non-feature C: `g22_024` and compare tasks `berth_sim`, `chain_relax` `program.c` byte-identical HEAD vs `/tmp/base`.

**Tests.** `test_ail_std_base64` 225.8s ok, `test_ail_safetynet` 180.1s ok, `test_ail_crypto` 174.9s ok; 0 failed. `update_manifest.py --check`: exit 0.

**Claims.** Both review defects verified fixed. Ordering, runtime `None`, probe list, manifest and non-feature C verified. Test-set claim verified for 3 of 5 modules; compare-task claim spot-checked for 2 of 10. Speed not checked (no hot-path gdev base64 work).

**Pre-existing.** `memoryview` unsupported (refused identically on base). Uncaught decoder exception prints `Error:` rather than `binascii.Error:` (identical on base; stdout/exit equal). Constant/malformed altchars compile-time refusals are named, pre-existing, and unchanged.

**Unverified.** `test_ail_files`, `test_ail_corpus_findings3`, the other 8 compare tasks, instruction counts.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2509519, "input": 41942, "output": 7072, "reasoning": 24921, "cache.write": 0, "cache.read": 2435584}]
    tool time: bash 16.7 min
        227s bash   cd /home/runner/work/ail-ci/ail-ci && AIL_NO_CACHE=1 timeout 1500 python3 tools/par_check.py -j 2 test_ail_std
        176s bash   cd /home/runner/work/ail-ci/ail-ci && AIL_NO_CACHE=1 timeout 1200 python3 tools/par_check.py -j 2 test_ail_cry
        123s bash   cd /tmp/rprobes && for p in pb16_int pb16_none pb16_list pb64e_str pb64e_str2 pb64d_int; do echo "##### $p"; t
        120s bash   cd /home/runner/work/ail-ci/ail-ci && AIL_NO_CACHE=1 nohup python3 tools/par_check.py -j 2 test_ail_std_base64
         90s bash   cd /tmp/rprobes && for p in r_b16 r_badtypes order_literal order_alts; do f=$p; [ -f "$f.py" ] || f=/tmp/probe
         69s bash   for p in /tmp/probes/order_static /tmp/probes/order_containers /tmp/rprobes2/p_len; do echo "##### $p"; timeou
         59s bash   cd /tmp/rprobes && for p in pmv_alt pba_mut; do echo "##### $p HEAD"; timeout 300 bash ~/tools/cmp.sh /tmp/rpr
         46s bash   cd /tmp/rprobes && cat > p_types3.py <<'EOF' import base64 def show(tag, fn):     try:         print(tag, fn()

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-01T14:26:17Z
