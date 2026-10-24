# job job-pre51-10241239  started 2026-10-24T03:39:25Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the first pre-existing difference: the `' 8'` diagnostic. The `z` flag already matched CPython; the format-spec error messages did not.

- `AIL_CURRENT/python/pkg-v12/safetyrt.py`: space signs on str now say `Space not allowed...`; invalid specs include the spec and value type; unknown format codes use CPython’s `\xNN` escaping, including non-ASCII and surrogate pairs.
- Added and registered `AIL_CURRENT/test_ail_pre51.py` (2 tests, both builds).
- Updated `DEVLOG`, `DIFFERENCES`, and `MANIFEST.json`; `update_manifest.py --check` passes.
- Probes: `/tmp/probes/p_z.py`, `p_pre51_fmt.py`, `p_pre51_ctl.py` — all same stdout on CPython and both builds. The separate NUL code-point difference remains pre-existing and untouched.
- Required tests: `test_ail_pre51`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed.
- Commit: `1586908`.
[cost $0.0000, opencode tokens {"total": 4069072, "input": 204056, "output": 12132, "reasoning": 20436, "cache.write": 0, "cache.read": 3832448}]
    tool time: bash 8.2 min
        317s bash   python3 tools/par_check.py -j 2 test_ail_pre51 test_ail_safetynet test_ail_files test_ail_corpus_findings3 2>&
        101s bash   python3 - <<'EOF' import sysconfig, os print(sysconfig.get_config_var('srcdir')) print(os.path.exists(sysconfi
         25s bash   for p in /tmp/probes/p_z.py /tmp/probes/p_ctl.py /tmp/probes/p_repr.py /tmp/probes/p_hash.py /tmp/probes/p_big
         16s bash   python3 - <<'PY' from pathlib import Path p=Path('/tmp/probes/p_pre51_fmt.py') s=p.read_text() s=s.replace("""
         12s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_pre51 2>&1 | tail -40
          6s bash   cat > /tmp/probes/p_pre51_fmt.py <<'EOF' class Box:     def __init__(self, v):         self.v = v   def show(l
          5s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/python/pkg-v12/safetyrt.py') s=p.read_text() old
          4s bash   bash ~/tools/cmp.sh /tmp/probes/p_ctl.py "$PWD" 2>&1 | tail -30

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review: job pre51 (`1586908`)**

**What the change really does:** In `AIL_CURRENT/python/pkg-v12/safetyrt.py` it rewrites format-spec error text: `Space not allowed...` for a str space sign, full `Invalid format specifier '<spec>' for object of type '<tn>'` for invalid specs, `\xNN` for unknown codes, and accepts non-ASCII type codes (uint32_t). It adds `test_ail_pre51.py`, DEVLOG/DIFFERENCES/MANIFEST entries.

**Claims checked**
- `z` already matched: verified (`p_valid.py` passes on HEAD **and** base).
- str space sign wording: verified.
- invalid specs include spec and value type: **false** for non-ASCII and embedded NUL (see defect).
- unknown codes use `\xNN`, incl. non-ASCII: verified for `é`/`☃`; surrogate pairs unverified (non-BMP literal is refused by the subset).
- test added/registered, both builds: verified; `test_ail_pre51` + `test_ail_safetynet` pass (`2 modules, 0 failed`); `update_manifest.py --check` passes.
- NUL code-point difference still pre-existing: verified (`format(1,'\x00')` still returns `1` on both).
- "all my probes same stdout": **false** — probes below differ on HEAD.
- 4 required modules: I ran only the two above per review scope; `test_ail_files`/`test_ail_corpus_findings3` unverified.

**Defect 1 — new invalid-spec message is mangled/truncated** (`safetyrt.py:710-733`)
`ail2f_bad_spec` UTF-8-encodes code points into a C string, then `ail_str_from_cstr` treats each byte as a code unit and uses `strlen`, so non-ASCII is double-encoded and an embedded NUL truncates the message.

Probe `/tmp/rprobes/p_uni.py`:
```
int '8☃x' => ValueError Invalid format specifier '8☃x' for object of type 'int'
```
CPython: `... '8☃x' ...`; HEAD: `... '8â\x98\x83x' ...` (`8\xc3\xa2\xc2\x98\xc2\x83x`). Same for `'8éx'` -> `'8Ã©x'`.

Probe `/tmp/rprobes/p_nul.py`:
```
int 'a\x00b' => ValueError Invalid format specifier 'a\x00b' for object of type 'int'
```
CPython keeps the embedded NUL and suffix; HEAD outputs `Invalid format specifier 'a` (truncated at NUL). Base printed only `Invalid format specifier` (also wrong), so this is a newly malformed result, not a pre-existing identical one. Fix by building the `ail_str` from code units (or a UTF-8 decoder) rather than a C string.

**Pre-existing (not blocking)**
- `format(None, ' +8')` and `format(Box(...), ' +8')` raise ValueError instead of CPython TypeError on both base and HEAD (HEAD now says `NoneType`/`instance`).
- NUL in the unknown-code path (`format(1,'\x00')`) still formats successfully on both.
- Base also differed for non-ASCII invalid specs (omitted the spec entirely).

**Unverified:** surrogate/non-BMP format-code handling; `test_ail_files` and `test_ail_corpus_findings3`; instruction-count speed (format not hot).

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 952055, "input": 48475, "output": 6028, "reasoning": 13712, "cache.write": 0, "cache.read": 883840}]
    tool time: bash 3.1 min
        120s bash   date; cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre51 test_ail_safetynet 2>&1 | tail -20
          7s bash   python3 - <<'EOF' p='/tmp/rprobes/p_bad.py' s=open(p).read().replace("    si(d['i'])\n","    si(d['i'], '8\\u2
          7s bash   bash ~/tools/cmp.sh /tmp/rprobes/p_bad.py /tmp/base 2>&1 | tail -30
          6s bash   bash ~/tools/cmp.sh /tmp/rprobes/p_valid.py "$PWD" 2>&1 | tail -30
          6s bash   bash ~/tools/cmp.sh /tmp/rprobes/p_valid.py /tmp/base 2>&1 | tail -12
          6s bash   cat > /tmp/rprobes/p_uni.py <<'EOF' def pi(v, s):     try: r = repr(format(v, s))     except Exception as e: r
          6s bash   bash ~/tools/cmp.sh /tmp/rprobes/p_uni.py /tmp/base 2>&1 | tail -20
          5s bash   cat > /tmp/rprobes/p_nul.py <<'EOF' def pi(v, s):     try: r = repr(format(v, s))     except Exception as e: r

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed both review defects in `ail2f_bad_spec` (`AIL_CURRENT/python/pkg-v12/safetyrt.py`): the invalid-spec message is now built from 16-bit code units instead of UTF-8 bytes in a C string, so non-ASCII specs are no longer double-encoded and embedded NULs no longer truncate.

- Probes `/tmp/probes/p_badspec.py` (non-ASCII `☃`/`é`, embedded NUL, boundaries, via argument/list item/attribute/dict value, both builds) and `/tmp/probes/p_valid2.py`: `same stdout` on g and d.
- Extended `test_ail_pre51.py` with those cases.
- Required tests on commit `d9dace4`: `4 modules in 242s, 0 failed` (`test_ail_pre51`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`).
- `update_manifest.py --check`: ok. DEVLOG/DIFFERENCES updated.
- Known pre-existing, unchanged: single-NUL code (`format(1, '\x00')`) and None/object invalid-spec ordering still differ on both builds.
[cost $0.0000, opencode tokens {"total": 1100395, "input": 40615, "output": 7037, "reasoning": 5703, "cache.write": 0, "cache.read": 1047040}]
    tool time: bash 6.9 min, edit 0.0 min
        244s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre51 test_ail_safetynet test_ail_files test_ail
        121s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre51 test_ail_safetynet 2>&1 | tail -20
         11s bash   for p in p_badspec p_valid2; do echo "=== $p ==="; bash ~/tools/cmp.sh /tmp/probes/$p.py /home/runner/work/ail
         11s bash   for p in p_badspec p_valid2; do echo "=== $p ==="; bash ~/tools/cmp.sh /tmp/probes/$p.py "$PWD" 2>&1 | tail -2
          6s bash   python3 - <<'EOF' p='/tmp/probes/p_badspec.py' s=open(p).read() s=s.replace("        for v in [7, 'ab', 1.5, T
          6s bash   python3 - <<'EOF' p='/tmp/probes/p_badspec.py' s=open(p).read() s=s.replace("'8\\u2603', '\\u2603', '\\x00', '
          6s bash   bash ~/tools/cmp.sh /tmp/probes/p_badspec.py /home/runner/work/ail-ci/ail-ci 2>&1 | tail -30
          6s bash   python3 - <<'EOF' p='/tmp/probes/p_badspec.py' s=open(p).read() s=s.replace("    pi(7, ' ' + chr(0))\n    pi('

## review 1
[model opencode/deepseek-v4.1-flash-free]
## Review of `work..HEAD` (pre51)

**What the change does:** Fixes general-path `format()` spec diagnostics — `Space not allowed` for a str space sign, full `Invalid format specifier '<spec>' for object of type '<type>'`, CPython-style `\xNN` escaping of unknown codes, and builds the invalid-spec message from 16-bit code units so non-ASCII/NUL survive. (`1586908` did the diagnostics; `d9dace4` fixed the message encoding.) The report only describes the second commit; it understates the diff but does not contradict it.

**Probes** (`bash ~/tools/cmp.sh ...`, both g and d; base compared where needed):

| probe | result |
|---|---|
| r1 nonascii | non-BMP literal refused by name (acceptable) |
| r2 nul | head matches CPython except pre-existing single-NUL; base was worse (generic/truncated) |
| r3 space sign | g/d same stdout |
| r4 plain valid specs | g/d same stdout |
| r5 arg/list/attr/dict | all 9 compared lines identical (incl. NUL) |
| r6 repeated/long BMP, non-ASCII fill, aliasing | g/d same stdout |
| r7 `chr(0x1F600)` | pre-existing internal error on base and head |
| r8 code boundaries 0x00–0x2603, bool, None/Box | head matches except pre-existing items below |
| r9 `z` boundaries (nan/inf/−0.0, width/prec/%/group) | g/d same; base differed on `'z, .2f'` |

**Pre-existing (also on `/tmp/base`, not caused):**
1. Single-NUL code (`format(1,'\x00')`, `'8\x00'`, `format('a','\x00')`): AIL returns a value, CPython raises `Unknown format code '\x0'`.
2. None/instance with an invalid spec: AIL `ValueError: Invalid format specifier ...`, CPython `TypeError: unsupported format string passed to X.__format__` (ordering).
3. Default object repr (`<Box object>` vs `<__main__.Box object at 0x...>`).
4. `chr()` of a non-BMP code point: internal error on both builds.

**Claims:** message-from-code-units / no double-encoding / no NUL truncation — verified; worker probes `p_badspec`, `p_valid2` same stdout on g/d — verified; test extension — verified; manifest `--check` — verified; DEVLOG/DIFFERENCES — verified; "4 modules, 0 failed" — partially verified (reran `test_ail_pre51`, `test_ail_safetynet`: 2 modules, 0 failed, 118s); other two modules not rerun per review scope.

**Other checks:** plain program's generated C (default and general path) unchanged vs base (only path strings differ). Instruction counts not measured: `perf_event_open` is denied (`perf_event_paranoid=4`); the change is error-path only plus one surrogate check, no hot-path concern observed.

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3`; speed via `icount` (unavailable).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1477030, "input": 154422, "output": 7964, "reasoning": 15956, "cache.write": 0, "cache.read": 1298688}]
    tool time: bash 3.8 min
        120s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_pre51 te
         26s bash   date; for p in r1_nonascii r2_nul r3_space r4_plain r5_forms; do echo "=== $p ==="; bash ~/tools/cmp.sh /tmp/r
         14s bash   cd /home/runner/work/ail-ci/ail-ci && cc -O2 -w -include signal.h -include stdlib.h -o /tmp/icount tools/icoun
         12s bash   cat > /tmp/rprobes/r8_codes.py <<'EOF' class Box:     def __init__(self, v):         self.v = v  def apply(v, 
         11s bash   cat > /tmp/rprobes/r6_edge.py <<'EOF' class Box:     def __init__(self, v):         self.v = v  def apply(v, s
         11s bash   for p in r2_nul r5_forms; do echo "=== BASE $p ==="; bash ~/tools/cmp.sh /tmp/rprobes/$p.py /tmp/base 2>&1 | t
         11s bash   date; for p in p_badspec p_valid2; do echo "=== $p ==="; bash ~/tools/cmp.sh /tmp/probes/$p.py /home/runner/wo
         10s bash   cat > /tmp/rprobes/r9_z.py <<'EOF' def show(v, s):     try:         print(repr(v), repr(s), '->', repr(format(

FINAL VERDICT: ACCEPT  2026-10-24T04:18:05Z
