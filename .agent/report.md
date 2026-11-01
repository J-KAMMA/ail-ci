# job job-std_base64-11011521  started 2026-11-01T06:27:09Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented and committed as `b9ccb5e`.

- Added `b16encode/b16decode`, `b32encode/b32decode`, `encodebytes/decodebytes`, `b64encode(altchars=)`, `b64decode(altchars=, validate=)`, and run-time `validate`/`casefold` flags.
- Decoder errors now use a `ValueError` subclass named `Error`, matching CPython's `binascii.Error` name.
- Added `lab/stdlib/base64/` with 12 programs; **10 build and match CPython 3.12.3 stdout/exit**, 2 are documented follow-ups (`b85`/`a85`, legacy stream API).
- Added `test_ail_std_base64.py` (registered via `tests.d`) and updated `test_ail_crypto.py`.
- Required tests passed on the final commit: **44 tests, OK, 1 skipped** (`std_base64`, `crypto`, `safetynet`, `files`, `corpus_findings3`).
- Probes in `/tmp/probes/` covered empty/length boundaries, bytes vs str, aliases, arguments, list items, attributes, dict values, error classes, and both builds: all matched CPython or were refused by name.
- `python3 tools/update_manifest.py --check` exits 0.
[cost $0.0000, opencode tokens {"total": 8710302, "input": 217954, "output": 32930, "reasoning": 40474, "cache.write": 0, "cache.read": 8418944}]
    tool time: bash 47.3 min, write 0.0 min
        964s bash   cd /home/runner/work/_temp/w2 && python3 -m unittest AIL_CURRENT.test_ail_std_base64 AIL_CURRENT.test_ail_cryp
        459s bash   cd /home/runner/work/_temp/w2 && ls AIL_CURRENT/test_ail_safetynet.py AIL_CURRENT/test_ail_files.py AIL_CURREN
        276s bash   cd /home/runner/work/_temp/w2 && for f in altchars_enc altchars_dec encodebytes b16 b32 strarg feat impl_test 
        233s bash   cd /home/runner/work/_temp/w2 && python3 -m unittest AIL_CURRENT.test_ail_std_base64 -v 2>&1 | tail -60
        189s bash   cd /home/runner/work/_temp/w2 && for f in base64_routes base64_edges errtypes kwargs more_b64; do echo "##### 
        120s bash   cd /home/runner/work/_temp/w2 && for f in altchars_enc altchars_dec encodebytes b16 b32 b85 byteslike errors o
         96s bash   cd /tmp/b64build && for b in basic_roundtrip basic_auth url_token json_payload altchars_filesystem mime_lines 
         95s bash   cd /tmp/b64build && for b in basic_roundtrip basic_auth url_token json_payload altchars_filesystem mime_lines 

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: `std_base64` (commit `b9ccb5e`)

**What the diff really does:** adds base16/base32/encodebytes/altchars/runtime-flag lowering and prelude helpers for `base64`, a prelude `Error(ValueError)`, a `_strish` tightening for `.lower()/.upper()`, plus 12 lab programs, a new test, manifest/DEVLOG updates. This matches the report's description, but not its "all probes matched" claim.

**Probes** (`bash ~/tools/cmp.sh <p> $PWD`, general + default):
- `b16.py`, `b32.py`, `casefold.py`, `validate.py`, `bytesio.py`: same stdout/exit as CPython.
- `strlower2.py`, `g21_026.py`: identical C/stdout on HEAD and `/tmp/base` (no non-feature regression).
- `echo_pack/main.py`: generated `program.c` byte-identical HEAD vs base.
- Failing probes: `altwrong2.py`, `altcatch.py`, `decodebytes_str.py`, `b32ba.py`, `types.py`.

**Defects**
1. `altchars` length is not validated on the typed path and raises the wrong class elsewhere.
   `altwrong2.py`: `print(repr(base64.b64decode("-_-_", altchars="-_x")))`
   Expected (CPython): `AssertionError`, exit 1, empty stdout. Actual (default): `b'\xfb\xff\xbf'`, exit 0.
   `altcatch.py`: `try: print(base64.b64decode("-_", altchars="-")) except ValueError as e: print("caught", e)` — expected exit 1 (AssertionError), actual exit 0 `caught altchars must be a bytes-like object of length 2`. (A named refusal would be acceptable.)
2. `decodebytes` accepts `str`; CPython rejects it.
   `decodebytes_str.py`: `base64.decodebytes("aGVsbG8=")`
   Expected: `TypeError: expected bytes-like object, not str`; actual: `b'hello'`. Non-ASCII str: expected `TypeError`, actual `ValueError: string argument should contain only ASCII characters`.
3. `b32decode` crashes on `bytearray`.
   `b32ba.py`: `base64.b32decode(bytearray(b"MZXW6==="))`
   Expected: `b'foo'`; actual: `AttributeError: 'bytearray' object has no attribute '_s'`, exit 1 (both builds). `b16decode(bytearray)` and `b32encode(bytearray)` work.
4. Encoders leak internal error text for `str` input (`types.py`).
   `b16encode("hi")` / `b32encode("hi")`: expected `TypeError: a bytes-like object is required, not 'str'` / `memoryview: ...`; actual `TypeError: unsupported operand type(s) for >>: 'str' and 'int'`. `encodebytes("hi")`: expected `expected bytes-like object, not str`, actual `a bytes-like object is required, not 'str'`.

**Claims checked**
- Added functions / `Error` class / runtime `validate`+`casefold`: verified (probes print `Error`, subclass of `ValueError`; runtime flags match).
- 10 of 12 lab programs build and match: verified (`test_ail_std_base64` passes both `AIL_IR` builds; 2 refusals pinned).
- `update_manifest.py --check`: verified exit 0.
- "Probes ... all matched": **false** (defects above).
- "44 tests, OK, 1 skipped": **unverified** — ran only `std_base64`, `crypto`, `safetynet` (all ok, 413s).
- Required test modules: pass on HEAD.

**Pre-existing:** none found. New-feature probes cannot run on base (b16/b32/encodebytes refused by name); non-feature probes are identical.

**Unverified:** speed (no gdev program exercises the new Python-level codec loops; `g21_026` uses only unchanged C primitives); full five-module test count.

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 3594142, "input": 114947, "output": 11806, "reasoning": 35837, "cache.write": 0, "cache.read": 3431552}]
    tool time: bash 15.8 min, write 0.0 min
        415s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_std_base64 test_ail_c
        114s bash   cd /tmp/rprobes; for p in b16 b32 altchars bytesio validate; do echo "##### $p"; bash ~/tools/cmp.sh /tmp/rpro
         48s bash   cd /tmp/rprobes; echo "=== altcatch HEAD"; bash ~/tools/cmp.sh /tmp/rprobes/altcatch.py /home/runner/work/_tem
         44s bash   cd /tmp/rprobes; echo "=== b64ba BASE"; bash ~/tools/cmp.sh /tmp/rprobes/b64ba.py /tmp/base 2>&1 | tail -20; e
         44s bash   cd /tmp/rprobes; for p in altstr casefold; do echo "##### $p"; bash ~/tools/cmp.sh /tmp/rprobes/$p.py /home/ru
         43s bash   cd /tmp; echo BASE; bash ~/tools/cmp.sh ~/corpus/gdev/g21_026.py /tmp/base 2>&1 | tail -12
         37s bash   cd /tmp; echo HEAD; bash ~/tools/cmp.sh ~/corpus/gdev/g21_026.py /home/runner/work/_temp/w2 2>&1 | tail -12
         36s bash   cd /tmp/rprobes; echo "=== HEAD strlower"; bash ~/tools/cmp.sh /tmp/rprobes/strlower.py /home/runner/work/_tem

## worker report 1
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Fixed all five defects and committed as `3cf0d72`.

- **altchars**: length now asserts on both decode paths (incl. constant `str`) with `AssertionError`; dynamic `str` for encode gets CPython’s `TypeError`.
- **decodebytes**: rejects `str`/non-bytes with `TypeError: expected bytes-like object, not …`.
- **b32decode(bytearray)**: normalizes to bytes; no more `_s` crash.
- **b16encode/b32encode/encodebytes**: validate input first and emit CPython’s exact `TypeError` texts.
- **RESULTS/DEVLOG** updated; `chunked_stream.py` is now general.

Verification:
- Reviewer probes `altwrong2`, `altcatch`, `decodebytes_str`, `b32ba`, `types`: **all match CPython on both builds**.
- All 19 `/tmp/rprobes` probes: **19/19 × 2 builds same stdout**.
- 5 new boundary probes `/tmp/probes/fix_*.py`: **5/5 same stdout/exit on both builds**.
- Required tests: `test_ail_std_base64`, `test_ail_crypto`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — **5 modules, 0 failed (777s)**.
- `tools/update_manifest.py --check`: **exit 0**.
[cost $0.0586, opencode tokens {"total": 5884437, "input": 122977, "output": 12748, "reasoning": 25576, "cache.write": 0, "cache.read": 5723136}]
    tool time: bash 26.7 min, edit 0.0 min
        778s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_std_base64 test_ail_c
        331s bash   cd /tmp/rprobes && ls *.py | sed 's/\.py$//' | xargs -P 2 -I{} bash -c 'bash ~/tools/cmp.sh /tmp/rprobes/{}.py
        156s bash   cd /tmp/probes && for p in fix_alt fix_decodebytes fix_encoder_types fix_b32ba fix_alt_types; do rm -f /tmp/ru
        127s bash   cd /tmp/rprobes && for p in altwrong2 altcatch decodebytes_str b32ba types; do echo "##### $p"; timeout 180 ba
         83s bash   mkdir -p /tmp/runprobes && cd /tmp/rprobes && printf '%s\n' altwrong2 altcatch decodebytes_str b32ba types | x
         74s bash   rm -rf /tmp/laball && mkdir -p /tmp/laball && cp lab/stdlib/base64/*.py /tmp/laball/ && cd /tmp/laball && ls *
         13s bash   rm -rf /tmp/labchk && mkdir -p /tmp/labchk && cp lab/stdlib/base64/chunked_stream.py /tmp/labchk/ && cd /tmp/l
         13s bash   rm -rf /tmp/ba2 && mkdir -p /tmp/ba2 && cat > /tmp/ba2/p.py <<'EOF' import base64   def main() -> None:     pr

## review 1
[model opencode-go/deepseek-v4.1-flash]
**Change (one line).** `3cf0d72`+`b9ccb5e` add base16/base32/`encodebytes`/`decodebytes` and `altchars=`/runtime `validate=` lowering to `hashlower.py`, implement them plus a `ValueError`-subclass `Error` in `hash_prelude.py`, add 12 lab programs and `test_ail_std_base64`; this is broader than the report's "fixed five defects", but consistent with the two commits.

**Probes (both builds, `bash ~/tools/cmp.sh ... $PWD`).**
- `r_alt.py`, `r_altstr.py`, `r_alt2.py` (altchars lengths 0/1/2/3/4, bytes/str/bytearray, constant/dynamic, decode+encode): match, incl. `AssertionError: b'?'` / `"'-'"` and dynamic-str encode `TypeError`.
- `r_b32.py`, `r_b32b.py` (enc 0–11, 30 padded/unpadded/bad-padding/lowercase/invalid tokens × casefold, bytearray): match.
- `r_b64alt.py` (7 altchars incl. `++`, `//`, NUL; validate true/false with whitespace): match.
- `r_bytes.py` (encodebytes lengths 0,1,2,55,56,57,58,113,114,115; multi-line decode; bytearray; str errors): match.
- `r_routes.py`, `r_types2.py`, `r_kw.py`, `r_badtypes.py`, `r_b16.py`: two mismatches below.
- Compare tasks: generated C byte-identical on HEAD/base for the 5 that build plainly; the other 5 refuse identically on both.

**Tests.** `test_ail_std_base64`, `test_ail_crypto`, `test_ail_safetynet` on HEAD: 3 modules, 0 failed, 421s. `update_manifest.py --check`: exit 0.

**Claims.** altchars assert (both decode paths, constant str) — verified. Dynamic-str encode TypeError — verified. `decodebytes` str/non-bytes TypeError text — verified. `b32decode(bytearray)` — verified. Encoder TypeError texts (str/int) — verified. `update_manifest --check` — verified. Their 19 `rprobes` + 5 `fix_*` rerun, `test_ail_files`, `test_ail_corpus_findings3`, and “chunked_stream is general” — unverified (not rerun/inspected). Speed — not checked (no hot-path change).

**Pre-existing.** None found; both defects are in code added by this change.

**Defects.**
1. `base64.b16decode` skips its input type check for non-bytes/non-str (`/tmp/rprobes/r_b16.py`, `r_badtypes.py`, both builds). `base64.b16decode(123)` expected `te argument should be a bytes-like object or ASCII string, not 'int'`; actual `te object of type 'int' has no len()`. Same for `None`. Cause: `_ail_hl_b16d_dyn` omits `_ail_hl_need_bytes(data, 3)` that `_ail_hl_b32d_dyn` has.
2. `base64.b64encode(b"\xfb\xff", altchars=[1, 2])` silently returns `b'\x01\x028='` (`/tmp/rprobes/r_badtypes.py`, both builds). CPython expected `te a bytes-like object is required, not 'list'` (assert passes, then `bytes.maketrans` rejects the list). Cause: `_ail_hl_alt_bytes`/`_ail_hl_alt_enc_dyn` check only length, never that altchars is bytes-like, so an invalid altchars is used as character codes.

VERDICT: FIX
1. Add the bytes-like check to `_ail_hl_b16d_dyn` (probe `/tmp/rprobes/r_b16.py`, `base64.b16decode(123)` expected `argument should be a bytes-like object or ASCII string, not 'int'`, actual `object of type 'int' has no len()`).
2. Reject non-bytes-like `altchars` after the length assert (probe `/tmp/rprobes/r_badtypes.py`, `base64.b64encode(b"\xfb\xff", altchars=[1, 2])` expected `TypeError: a bytes-like object is required, not 'list'`, actual `b'\x01\x028='`).
[cost $0.0346, opencode tokens {"total": 2334414, "input": 39566, "output": 9073, "reasoning": 27343, "cache.write": 0, "cache.read": 2258432}]
    tool time: bash 18.8 min, write 0.0 min, edit 0.0 min
        441s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/cmpgc && mkdir -p /tmp/cmpgc/src /tmp/cmpgc/head /tmp/cmpgc/base 
        240s bash   sleep 240; ps -p $(cat /tmp/rev_par.pid) -o pid,etime; wc -l /tmp/rev_par.log; tail -20 /tmp/rev_par.log; date
        175s bash   cd /tmp/rprobes && for p in r_alt r_altstr r_b16 r_b32 r_bytes r_routes; do echo "##### $p"; timeout 300 bash 
         82s bash   cd /tmp/rprobes && for p in r_alt r_b16 r_routes; do echo "##### $p"; timeout 300 bash ~/tools/cmp.sh /tmp/rpr
         53s bash   cd /tmp/rprobes && for p in r_b32b r_b64alt; do echo "##### $p"; timeout 400 bash ~/tools/cmp.sh /tmp/rprobes/
         40s bash   cd /tmp/rprobes && timeout 300 bash ~/tools/cmp.sh /tmp/rprobes/r_types2.py /home/runner/work/_temp/w2 2>&1 | 
         36s bash   cd /tmp/rprobes && timeout 300 bash ~/tools/cmp.sh /tmp/rprobes/r_alt2.py /home/runner/work/_temp/w2 2>&1 | gr
         35s bash   cd /tmp/rprobes && timeout 300 bash ~/tools/cmp.sh /tmp/rprobes/r_badtypes.py /home/runner/work/_temp/w2 2>&1 

FINAL VERDICT: FIX  2026-11-01T08:58:31Z
