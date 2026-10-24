# job job-pre29-10240900  started 2026-10-24T00:01:12Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
​Fixed the first listed difference: invalid format specifiers now report `Invalid format specifier '<spec>' for object of type '<type>'`.

Changes (branch `job-pre29-10240900`, commits `9804a62`, `893a5f8`):
- `safetyrt.py`: parser now returns a dedicated invalid-spec status; `ail2f_format` builds the full 16-bit message for str/int/bool/float. Object types (None/list/tuple/dict) raise `unsupported format string ...` before parsing, matching CPython. Single non-ASCII type characters now produce CPython's escaped `Unknown format code '\x..'`.
- Added `test_ail_pre29.py` (5 programs, both builds) and registered it in `ail_check.MODULES`.
- Added `DIFFERENCES` row `C?-job-pre29-10240900-1` and a top `DEVLOG` entry.

Verification on final commit `893a5f8`:
- `test_ail_pre29`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: **4/4 passed**, 329 s, `-j 2`.
- Probes `/tmp/probes/pre29_invalid.py`, `pre29_sources.py`, `pre29_objects.py`, `pre29_valid2.py`, `pre29_unicode.py`, `pre29_unicode2.py`: all **same stdout on both builds** as CPython. They cover literal/argument/list-item/attribute/dict sources, widths, empty and negative specs, int/bool/float/str, and non-ASCII specs.
- `update_manifest.py --check` passes.

The other recorded items still differ: `z` flag, `!s`/`!r` with a sign, `format(1e300, '#')`, and `10**30`. Nothing pushed.
[cost $0.0000, opencode tokens {"total": 4635534, "input": 104258, "output": 14446, "reasoning": 25503, "cache.write": 0, "cache.read": 4491327}]
    tool time: bash 8.6 min, edit 0.0 min
        331s bash   python3 tools/par_check.py -j 2 test_ail_pre29 test_ail_safetynet test_ail_files test_ail_corpus_findings3
         35s bash   for p in p1 p1b pre29_invalid pre29_sources pre29_unicode pre29_unicode2; do echo "===== $p ====="; bash ~/too
         35s bash   for p in pre29_invalid pre29_sources pre29_objects pre29_valid2 pre29_unicode pre29_unicode2; do echo "===== $
         29s bash   cd AIL_CURRENT && AIL_NO_CACHE=1 PYTHONUTF8=1 python3 -B -m unittest -q test_ail_pre29
         18s bash   cat > /tmp/probes/pre29_invalid.py <<'EOF' def show(v, spec):     try:         print(repr(v), repr(spec), repr
         12s bash   mkdir -p /tmp/probes && cat > /tmp/probes/p1.py <<'EOF' def t(spec):     try:         print(repr(format('x', s
         12s bash   bash ~/tools/cmp.sh /tmp/probes/pre29_unicode.py $PWD; echo ====; cat > /tmp/probes/pre29_unicode2.py <<'EOF' 
         12s bash   cat > /tmp/probes/pre29_objects.py <<'EOF' def show(v, spec):     try:         print(repr(v), repr(spec), repr

## review 0
[model opencode/deepseek-v4.1-flash-free]
Review of `pre29` (branch `job-pre29-10240900`, commits `9804a62`, `893a5f8`).

**Probes (both builds unless noted)**
- `/tmp/rprobes/inv.py` (literal/arg/list/attr/dict sources; str/int/bool/float/None/list/tuple/dict): matches CPython, except pre-existing default-`Box` repr.
- `/tmp/rprobes/uni.py` (non-ASCII, 600-char specs, NUL): matches; only pre-existing single-`'\x00'` spec differs.
- `/tmp/rprobes/obj.py` (Plain object, custom `__format__`, None/list/tuple/dict): matches; custom `__format__` still reached; only pre-existing Plain repr differs.
- `/tmp/rprobes/moreobj.py` (bytes/bytearray/set/frozenset/range, incl. `'é'`): matches both builds.
- `/tmp/rprobes/valid.py`: differences identical to base (`' 8'` Space vs Sign; `z` flag).
- `/tmp/rprobes/ctrl.py`: NUL/control differences identical on base; `'\x80'` now matches.
- `/tmp/rprobes/fz.py`: 1463 specs x 4 types = 5852 cases — **0 new divergences**, 3376 fixed, 283 identical to base.
- `/tmp/rprobes/nouse.py`: `program.c` byte-identical base vs HEAD on both emitters (only temp paths in `native_report.json`).
- `/tmp/rprobes/others.py`: `z`, `z#`, `!s`/`!r` sign, `format(1e300,'#')`, `10**30` differ identically on base and HEAD.

**Pre-existing (not blocking)**
- `'z'` flag and `' 8'` message; NUL/control format codes; default object repr; `format(1e300,'#')`; `10**30` overflow. All reproduce on `/tmp/base`.

**Claims**
- Invalid-spec suffix, 16-bit message, object `__format__` TypeError, non-ASCII code escaping: verified.
- `test_ail_pre29` (5 tests, both builds) and `ail_check.MODULES` registration: verified.
- DIFFERENCES row, DEVLOG entry, manifest `--check`: verified.
- `4/4` tests: partially verified — re-ran `test_ail_pre29` + `test_ail_safetynet`: 2/2 passed, 122 s on `893a5f8`; did not re-run `test_ail_files`/`test_ail_corpus_findings3`.
- Other recorded items still differ: verified.
- Instruction-count speed: unverified (`perf_event_open: Permission denied`); change adds only one tag check to the common path and touches no formatting arithmetic.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2081640, "input": 72723, "output": 8220, "reasoning": 18873, "cache.write": 0, "cache.read": 1981824}]
    tool time: bash 4.2 min
        124s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ai
         24s bash   cat > /tmp/rprobes/obj.py <<'EOF' class Plain:     def __init__(self, v):         self.v = v  class Fmt:     d
         18s bash   cd /tmp/rprobes && for t in head base; do wt=/tmp/base; [ $t = head ] && wt=/home/runner/work/ail-ci/ail-ci; A
         16s bash   cd /tmp/rprobes && printf '%s\n' inv uni obj valid nouse | xargs -P2 -I{} bash -c 'bash ~/tools/cmp.sh /tmp/rp
         16s bash   cc -O2 -w -include signal.h -include stdlib.h -o /tmp/rprobes/icount /home/runner/work/ail-ci/ail-ci/tools/ico
         13s bash   cat > /tmp/rprobes/moreobj.py <<'EOF' def sh(v, spec):     try:         print(type(v).__name__, repr(spec), re
         12s bash   cat > /tmp/rprobes/ctrl.py <<'EOF' def sh(v, spec):     try:         print(type(v).__name__, repr(spec), repr(
         11s bash   set -e cd /tmp/rprobes for t in base head; do   wt=/tmp/base; [ $t = head ] && wt=/home/runner/work/ail-ci/ail

FINAL VERDICT: ACCEPT  2026-10-24T00:25:12Z
