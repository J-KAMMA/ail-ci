# job job-std_difflib-11011614  started 2026-11-01T07:16:24Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done. Final state at commit `8d71495` (job branch).

- **Lab programs:** 12 written; **10/12 build** on the default/general path and match CPython stdout + exit code (`01`–`03`, `05`–`11`). Follow-ups in `RESULTS.md`: `04_unified_edges.py` (`**kwargs` call argument), `12_htmldiff.py` (`HtmlDiff`).
- **Fix in this commit:** `difflib.Match` now follows CPython's namedtuple for indexing, slicing, equality and hashing; `Différences`/`DEVLOG` updated. Remaining limit recorded: `Match` is not a tuple subclass, so plain-tuple key lookup misses.
- **Probes** (`/tmp/probes/`, both general `g` and default `d` builds): `dif_close_context`, `dif_diffs_context`, `dif_errors`, `dif_sequence_boundaries`, `dif_extra`, `dif_match` — all same stdout and exit status as CPython (`dif_errors`/`dif_sequence_boundaries` both exit 1 with the same output).
- **Tests on final commit:** `test_ail_std_difflib`, `test_ail_genlib`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — **5 modules, 0 failed**.
- **Codegen:** 10/10 `lab/compare` `main.ail` C hashes byte-identical to base; 7/10 `main.py` builds identical, 3 refused identically on both base and HEAD.
- **Manifest:** `update_manifest.py --check` exits 0.
[cost $0.0430, opencode tokens {"total": 4172334, "input": 105506, "output": 11725, "reasoning": 13375, "cache.write": 0, "cache.read": 4041728}]
    tool time: bash 22.9 min, edit 0.0 min, write 0.0 min
        376s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_std_difflib test_ail_
        279s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_std_difflib test_ail_
        267s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/dbgcmp && mkdir -p /tmp/dbgcmp && for t in berth_sim chain_relax 
         78s bash   cd /tmp/probes && for p in dif_close_context.py dif_diffs_context.py dif_errors.py dif_sequence_boundaries.py 
         78s bash   cd /tmp/probes && for p in dif_close_context.py dif_diffs_context.py dif_errors.py dif_sequence_boundaries.py 
         70s bash   cd /tmp/probes && for p in dif_*.py; do echo "===== $p"; bash ~/tools/cmp.sh /tmp/probes/$p /home/runner/work/
         44s bash   for p in dif_close_context.py dif_sequence_boundaries.py dif_extra.py dif_match.py; do echo "===== $p"; bash ~
         42s bash   for p in dif_close_context.py dif_sequence_boundaries.py dif_extra.py dif_match.py; do echo "===== $p"; bash ~

## review 0
[model opencode-go/deepseek-v4.1-flash]
**What the change really does:** Adds `difflib` to the general-path prelude (`prelude_genlib.py`) and TABLE/renamer (`genlib.py`): `Match`, `SequenceMatcher`, `Differ`, `get_close_matches`, `unified_diff`, `context_diff`, `ndiff`, `restore`, `diff_bytes`, `IS_LINE_JUNK`, `IS_CHARACTER_JUNK`; a rewrite for literal `diff_bytes(unified_diff|context_diff, …)`; 12 lab programs, `RESULTS.md`, `test_ail_std_difflib.py`, DEVLOG/DIFFERENCES/manifest. It is a faithful port of CPython 3.12's algorithms.

**Claims checked**
- 10/12 lab programs build and match CPython: **verified** (`test_ail_std_difflib` ran 10 programs, 0 failures); 04 and 12 refuse with the exact text in RESULTS on both base and HEAD.
- Match indexing/slicing/equality/hashing follows namedtuple: **verified**. Plain-tuple-key dict lookup misses: **verified** (and the reverse, tuple-stored key + Match lookup, also misses; set membership works).
- `/tmp/probes/dif_*` all match: **verified** by re-running all six on g+d.
- 5 test modules, 0 failed: **verified** (`test_ail_std_difflib`, `test_ail_safetynet`, `test_ail_genlib`, `test_ail_files`, `test_ail_corpus_findings3`).
- Manifest `--check` exits 0: **verified**.
- No difflib-free C change: **verified** for a plain program and `lab/compare/src/berth_sim/main.ail` (`program.c` byte-identical to base); diff_bytes latin-1 round-trip is output-identical for high bytes.
- 10/10 compare C hashes: **partially verified** (1/10 spot-checked). "7/10 main.py identical, 3 refused": **unverified**.

**Probes** (both g/d): p1_seq, p2_diff, p3_differ, p5_diffbytes, p6_fuzz (144 SequenceMatcher pairs, junk/autojunk/grouped), p7_differ_fuzz, p11_diff_fuzz, p12_gcm_ties, p13_match_iter, p14_bytes_defaults — all same stdout/exit as CPython. p4_match/p15_isinstance show only the documented non-tuple `Match` limits. p8b/p8c (function-as-value) are named refusals.

**Defects** (both caused by the new code; neither is pre-existing):

1. `diff_bytes` explicit `None` is silently treated as the omitted default. Probe `/tmp/rprobes/p9_db_none.py`, e.g. `list(difflib.diff_bytes(difflib.unified_diff, [b"a\n"], [b"b\n"], fromfile=None))`. CPython: `TypeError: all arguments must be bytes, not NoneType (None)`. AIL: prints the diff (`[b'--- \n', b'+++ \n', b'@@ -1 +1 @@\n', b'-a\n', b'+b\n']`). Same for `tofile`, `fromfiledate`, `tofiledate`, `lineterm`. Cause: `_ail_difflib_bytes_or` uses `None` as the "omitted" sentinel; `b''` defaults compile fine (p14), so this is avoidable.
2. `IS_LINE_JUNK` on a non-`str` raises the wrong exception or returns a value instead of `TypeError`. Probe `/tmp/rprobes/p10_pred_types.py`: `IS_LINE_JUNK(5)` — CPython `TypeError: expected string or bytes-like object, got 'int'`; AIL `AttributeError: 'int' object has no attribute 'strip'`. `IS_LINE_JUNK(None)`/`IS_LINE_JUNK([])` likewise `AttributeError`; `IS_LINE_JUNK(b"a")` — CPython `TypeError: cannot use a string pattern on a bytes-like object`; AIL `False`.

**Pre-existing:** none observed (base has no `difflib` support, so all probed differences are new).
**Unverified:** the other 9 `lab/compare` C hashes and the 7 `main.py` build comparisons; no instruction-count check (the change is not on a hot path and difflib-free `program.c` is identical).

VERDICT: FIX
1. `diff_bytes(..., fromfile=None)` (and the other four byte metadata/lineterm arguments) must raise CPython's `TypeError` instead of silently using the default; probe `p9_db_none.py`, expected `TypeError: all arguments must be bytes, not NoneType (None)`, actual a printed diff.
2. `IS_LINE_JUNK(x)` for non-`str` must raise CPython's `TypeError` (`IS_LINE_JUNK(5)` and `IS_LINE_JUNK(b"a")`), not `AttributeError`/`False`; probe `p10_pred_types.py`.
[cost $0.0495, opencode tokens {"total": 2796331, "input": 99005, "output": 12005, "reasoning": 32521, "cache.write": 0, "cache.read": 2652800}]
    tool time: bash 10.6 min
        204s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_genlib t
        163s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_std_diff
         80s bash   cd /tmp/probes && for p in dif_close_context.py dif_diffs_context.py dif_errors.py dif_sequence_boundaries.py 
         51s bash   cd /tmp/rprobes && for p in p1_seq.py p2_diff.py p3_differ.py p4_match.py p5_diffbytes.py; do echo "##########
         21s bash   cat > /tmp/rprobes/p8a_fromimport.py <<'EOF' from difflib import unified_diff, context_diff, diff_bytes   def 
         16s bash   cat > /tmp/rprobes/p9_db_none.py <<'EOF' import difflib   def main():     a = [b"a\n"]     b = [b"b\n"]     fo
         15s bash   cat > /tmp/rprobes/p10_pred_types.py <<'EOF' import difflib   def main():     for v in [5, None, b"a", [], "x"
         13s bash   cat > /tmp/rprobes/p7_differ_fuzz.py <<'EOF' import difflib   def gen():     lines = []     x = 7     chars = 

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed both review defects and committed as `b999199`.

- `diff_bytes`: explicit `None` for `fromfile`, `tofile`, `fromfiledate`, `tofiledate`, `lineterm` now raises CPython’s `TypeError: all arguments must be bytes, not NoneType (None)`; omitted arguments still use `b''`/`b'\n'`.
- `IS_LINE_JUNK`: non-`str` now raises CPython’s errors for bytes-like values and other types instead of `AttributeError`/`False`.
- Added `test_argument_type_errors` regression coverage.

Probes (`/tmp/probes/dif_fix_db_none.py`, `dif_fix_db_types.py`, `dif_fix_linejunk.py`, `dif_fix_charjunk.py`): all match CPython on both g and d builds.

Final-commit tests: `test_ail_std_difflib`, `test_ail_genlib`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5 modules, 0 failed. Manifest `--check` passes.

Compare-task C: 5/10 build and have byte-identical `program.c`; the other 5 are refused with identical diagnostics (only the cwd path prefix differs).
[cost $0.0448, opencode tokens {"total": 3627993, "input": 99567, "output": 15741, "reasoning": 16493, "cache.write": 0, "cache.read": 3496192}]
    tool time: bash 29.0 min
        335s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py && python3 tools/update_manifest.py --check 
        332s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py --check && cd AIL_CURRENT && timeout 3000 py
        327s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 3000 python3 ../tools/par_check.py -j 2 test_ail_std_diff
        183s bash   cat > /tmp/cmpc/one.sh <<'EOF' #!/bin/bash t=$1 curr=/home/runner/work/_temp/w2 base=/tmp/ail-base d=/tmp/cmpc
        117s bash   cd /tmp/probes && for p in dif_fix_db_none.py dif_fix_db_types.py dif_fix_linejunk.py dif_fix_charjunk.py; do 
         85s bash   cd /tmp/probes && for p in dif_fix_db_none.py dif_fix_db_types.py dif_fix_linejunk.py dif_fix_charjunk.py; do 
         82s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_std_diff
         78s bash   cd /home/runner/work/_temp/w2 && python3 - <<'EOF' p='AIL_CURRENT/python/pkg-v12/prelude_genlib.py' s=open(p).

## review 1
[model opencode-go/deepseek-v4.1-flash]
Review complete. Started 09:14 UTC, finished ~09:41 UTC.

## What the change really does
Adds general-path `difflib` support: 11 names in `prelude_genlib.py` (SequenceMatcher, Differ, Match, get_close_matches, unified/context/ndiff/restore/diff_bytes, junk predicates), `genlib.py` renames plus a `diff_bytes(unified_diff|context_diff, ...)` rewrite, 12 lab programs, a test module, DEVLOG/DIFFERENCES rows. The follow-up commit `b999199` replaces the `None` sentinel with `_AIL_DIFFLIB_MISSING` and hardens `IS_LINE_JUNK` type errors. This matches the report.

## Probes (`/tmp/rprobes`, `cmp.sh` on HEAD, g + d builds)
| Probe | Result |
|---|---|
| `p_db2.py` — diff_bytes explicit `None` for all 5 args, both diff funcs, `n=None`, bytes/bytearray/str/int/high-byte inputs, via param/list/attr/dict | same stdout, both builds |
| `p_linejunk2.py` — IS_LINE_JUNK on blank/#/unicode whitespace/\x1c-\x1f/bytes/bytearray/int/None/list/float/dict/tuple | same stdout, both builds |
| `p_close.py` — ties, n, cutoff, invalid n/cutoff, empty | same stdout, both builds |
| `p_seq.py` — blocks, opcodes, grouped (n=0/1), isjunk, autojunk, sub-range `find_longest_match`, Match index/slice/eq/hash/repr/iter | same except documented Match-vs-tuple dict lookup |
| `p_ndiff.py` — ndiff junk, restore, list mutation after taking a generator, Differ.compare | same stdout, both builds |
| `p_restore.py` — which = 1/2/3/0/-1/bool/float/str/None | same except `restore(d, None)` TypeError text |
| `p_db_custom.py` — diff_bytes with user dfunc inspecting high bytes | differs (latin-1 vs surrogateescape) |
| `p_db_alias.py` — from-import alias / `dfunc=` keyword | named compile-time refusal (acceptable) |
| `p_intnone.py` — plain `int(None)` | identical wrong message on HEAD **and** `/tmp/base` → pre-existing |

## Pre-existing (does not block)
- `int(None)` message: `int() argument must be a string or a number, not 'NoneType'` vs CPython's longer text; identical on base. This is what makes `restore(d, None)` differ.

## Documented limits (disclosed, outside the task's programs)
- `Match` is not a tuple subclass: a dict lookup of a `Match` key through an equal plain tuple misses (DIFFERENCES.md).
- `diff_bytes` uses latin-1, so a *user-supplied* `dfunc` that inspects decoded non-ASCII bytes sees `255` where CPython sees `56575`; unified/context output is byte-identical (verified with `b"\xff"`). Disclosed in RESULTS.md/DIFFERENCES.md.
- `04_unified_edges.py` (`**kwargs`) and `12_htmldiff.py` (HtmlDiff) are refused with the documented messages; confirmed.

## Claims checked
- Both review defects fixed: **verified** (all five args, both diff funcs; junk types on both builds).
- `test_argument_type_errors` added: **verified**, passes.
- Five test modules 0 failed: **verified** (`test_ail_std_difflib`, `test_ail_genlib`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`; 524 s, 0 failed).
- Manifest `--check` passes: **verified** (rc 0).
- Compare-task C: 5/10 build with byte-identical `program.c` (berth_sim, echo_pack, ledger_bin, term_rank, ticket_audit); other 5 refuse with identical diagnostics after path normalization: **verified**.
- 10/12 lab programs match CPython; ≥9 required: **verified** via test.
- Speed not checked (no hot-path C changed; compare-task C identical).

VERDICT: ACCEPT
[cost $0.0268, opencode tokens {"total": 876295, "input": 38262, "output": 7737, "reasoning": 23384, "cache.write": 0, "cache.read": 806912}]
    tool time: bash 20.6 min
        526s bash   date; cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 3000 python3 ../tools/par_check.py -j 2 test_ail_st
        504s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/cmpC && mkdir -p /tmp/cmpC; for t in $(ls lab/compare/src); do fo
         94s bash   cd /tmp/rprobes && for p in p_restore.py p_db_types.py p_linejunk.py p_close.py p_seq.py p_ndiff.py; do echo "
         61s bash   cat > /tmp/rprobes/p_db2.py <<'EOF' import difflib  class Box:     def __init__(self, v):         self.v = v  
         35s bash   cat > /tmp/rprobes/p_db_custom.py <<'EOF' import difflib  def show(lines):     out = []     for line in lines:
          8s bash   cat > /tmp/rprobes/p_intnone.py <<'EOF' def main():     try:         int(None)     except Exception as e:     
          5s bash   cd /home/runner/work/_temp/w2 && for p in 04_unified_edges 12_htmldiff; do echo "== $p =="; AIL_NO_CACHE=1 pyt
          0s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py --check 2>&1 | tail -5; echo rc=$?; git stat

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-01T10:54:46Z
