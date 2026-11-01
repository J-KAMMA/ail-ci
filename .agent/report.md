# job job-i64base1-11011226  started 2026-11-01T03:27:08Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `6ef6167` on `job-i64base1-11011226`: `int(str, base)` now lowers to `ail_str_to_int_base` on the IR int64 path with CPython parsing rules and the loud overflow stop; exact mode and bytes-with-base are unchanged.

Added `test_ail_int_base`, registered it, updated DEVLOG, manifest, and CI shards. Final-state run: 108 tests pass (1 skipped); generated C for the 10 `lab/compare/src/*/main.ail` tasks is byte-identical; manifest and shard checks pass.
[cost $0.0000, opencode tokens {"total": 7945952, "input": 400782, "output": 25386, "reasoning": 22312, "cache.write": 0, "cache.read": 7497472}]
    tool time: bash 22.4 min, edit 0.0 min
        484s bash   python3 -m unittest -q test_ail_int_base test_ail_pre192 test_ail_pre212 test_ail_pre253 test_ail_int64_defaul
        384s bash   python3 -m unittest -q test_ail_pre192 test_ail_pre212 test_ail_pre253 test_ail_int64_default test_ail_ir_s0 t
        349s bash   python3 -m unittest -q test_ail_safetynet test_ail_files test_ail_corpus_findings3 2>&1 | tail -60
         16s bash   python3 -m unittest -q test_ail_int_base 2>&1 | tail -40
         16s bash   cat > /tmp/opencode/gen_c.py <<'PY' import sys, os, hashlib, json, traceback root = sys.argv[1] sys.path[:0] =
         16s bash   python3 -m unittest -q test_ail_int_base 2>&1 | tail -50
         15s bash   python3 /tmp/opencode/gen_c.py "$PWD/AIL_CURRENT" > /tmp/opencode/after_c.json 2>/tmp/opencode/after_c.err; ec
         12s bash   cat > /tmp/probes/int_base_types.py <<'PY' class Box:     def __init__(self, b):         self.b = b   def main

## review 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
## Review report

**What the change really does:** Adds a `str_to_int_base` RTC entry and changes `lower.int_text` so that in default int64 mode a `str` first argument lowers to the existing `ail_str_to_int_base` runtime instead of refusing IR lowering; exact mode and bytes+base keep their old paths. This matches the report.

**Claims checked**
- Committed `6ef6167`, message/co-author correct — verified.
- `int(str, base)` lowers on the IR path (`AIL_IR=verify` stats say `path: ir`; kept C calls `ail_str_to_int_base`) — verified.
- CPython parsing rules and loud overflow above int64 — verified by probes.
- Exact mode and bytes-with-base unchanged — verified (identical outputs; bytes-only C has identical SHA).
- Test module, `tests.d` registration, DEVLOG, manifest and CI shard updates — verified; `update_manifest.py --check` and `ci_shards.py --check` pass.
- 10 `lab/compare/src/*/main.ail` generated C byte-identical — verified for all 10 via `--debug-dir`.
- "108 tests pass (1 skipped)" — unverified (I reran only the required subset).

**Probes** (cmp.sh, general + default, against HEAD and `/tmp/rbase`)
- `a_shapes`: direct/keyword/argument/list/attr/dict/alias — matches CPython.
- `b_rules`: whitespace, sign, underscores, 0x/0o/0b, base 0, invalid literals/bases/messages — matches.
- `c_overflow`: int64 boundaries; above boundary stops loudly as the task requires (identical on base).
- `d_typing`, `g_typing2`: float/str/None/bool bases — matches CPython.
- `e_nobase_bytes`: `int(str)` and `int(bytes, base)` — matches.
- `f_limit`, `o_limit2`: 4300/4301 digits, long leading zeros — matches (allowed 4300-digit values overflow loudly by policy).
- `h_exact`: `--exact-int` results identical on HEAD, base and CPython.
- `j_ir`: IR-path check — verified.
- `k_edge`, `l_base_range`, `n_uniws`: unicode digits/whitespace, huge positive/negative bases, computed bases — matches.
- `m_unrelated`, `i_bytesonly`: C unchanged for non-feature programs.

**Pre-existing:** none found.

**Tests:** `test_ail_int_base` and `test_ail_safetynet` pass; also ran `test_ail_files` and `test_ail_corpus_findings3` (both pass). Speed not checked: no gdev program calls `int(str, base)`.

VERDICT: ACCEPT
[cost $0.0288, opencode tokens {"total": 1795815, "input": 68265, "output": 9020, "reasoning": 13314, "cache.write": 0, "cache.read": 1705216}]
    tool time: bash 9.7 min
        221s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_files test_ail_c
        174s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_int_base test_ai
         56s bash   cd /tmp && rm -rf cdiff && mkdir -p cdiff && : > cdiff/result.txt; for d in /home/runner/work/ail-ci/ail-ci/la
         28s bash   cd /tmp/rprobes; for p in a_shapes b_rules c_overflow d_typing e_nobase_bytes f_limit; do echo "=== BASE $p"; 
         27s bash   cd /tmp/rprobes; for p in a_shapes b_rules c_overflow d_typing e_nobase_bytes f_limit; do echo "=== HEAD $p"; 
         15s bash   cat > /tmp/rprobes/i_bytesonly.py <<'PY' def main():     print(int(b'101', 2)) main() PY cd /tmp && for t in H
         14s bash   cat > /tmp/rprobes/h_exact.py <<'PY' def conv(t: str, b: int) -> int:     return int(t, b)  def main():     pr
         12s bash   cat > /tmp/rprobes/o_limit2.py <<'PY' def rep(s: str, n: int) -> str:     return s * n  def parse(t: str, b: i

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-01T05:27:49Z
