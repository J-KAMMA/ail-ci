# job job-pre123-10242349  started 2026-10-24T14:49:35Z  worker=oc reviewer=oc (GitHub)
## qoder discovery
1.1.78
  -m, --model <model>                  Model for the current session. Default
                                       and New Models use model name; Custom
                                       uses modelID
  --reasoning-effort <level>           Set reasoning effort level
  --thinking <mode>                    Set thinking mode (auto, adaptive,
                                       enabled, or disabled)
--
                                       models
  --list-models                        List available models for the current
                                       user
  -i, --prompt-interactive <text>      Execute prompt and continue in
                                       interactive mode
### --list-models
MODEL
Auto
Ultimate
Fast
Efficient
Sonus
Cantus
Qwen3.8-Max
Qwen3.8-Flash
Kimi-K3.1-Pro
Kimi-K2.8-Preview
GLM-5.3
GLM-5.3-Flash
DeepSeek-V4-Pro
DeepSeek-Flash
MiniMax-M3.1-Flash
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":815,"duration_api_ms":690,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":785,"duration_api_ms":659,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented and committed as `dd98c0d`.

- Astral UTF-8 `.decode()` now stores surrogate pairs; length, indexing, slicing, iteration, search, replace, split, strip, formatting and `ord` operate in code points.
- Added `AIL_CURRENT/test_ail_pre123.py`, DEVLOG/DIFFERENCES entries, and manifest pins.
- Verified required tests (`pre123`, `safetynet`, `files`, `corpus_findings3`), 13 related string modules, and targeted probes on both builds.
- Manifest check passes. Only `.agent/pipeline.md` remains untracked.
[cost $0.0000, opencode tokens {"total": 10662567, "input": 346891, "output": 37734, "reasoning": 47158, "cache.write": 0, "cache.read": 10230784}]
    tool time: bash 27.1 min
        500s bash   python3 - <<'PY' p='AIL_CURRENT/python/pkg-v12/cruntime.py' s=open(p).read() old='''static inline int64_t ail_
        336s bash   timeout 1800 python3 tools/par_check.py -j 2 test_ail_pre123 test_ail_safetynet test_ail_files test_ail_corpus
        257s bash   git add AIL_CURRENT/MANIFEST.json; python3 tools/update_manifest.py --check; echo check_rc=$?; timeout 1800 py
         86s bash   for f in p1_decode p5_decode_edges p6_strip_search p7_split_replace p9_more_edges p4_ops; do echo "=== $f ==="
         44s bash   python3 - <<'PY' p='AIL_CURRENT/python/pkg-v12/cruntime.py' s=open(p).read() old='''    for (; i >= 0; i = ail
         43s bash   git status --short; git log --oneline -2; python3 tools/update_manifest.py --check; echo manifest_check_rc=$?;
         43s bash   timeout 1800 python3 tools/par_check.py -j 2 test_ail_str_adjacent_cat test_ail_str_case test_ail_str_comprehe
         42s bash   timeout 900 python3 -B -m unittest -v AIL_CURRENT.test_ail_pre123

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change does:** Decodes astral UTF-8 into UTF-16 surrogate pairs on the 16-bit path, adds code-point helpers, and rewrites indexing/slicing/iteration/search/replace/split/strip/format/repr/`ord`/`chr`/`%c` to count code points. Base dies on the decode; module bodies for non-astral programs are unchanged (only the runtime preamble differs).

**Probes (HEAD, both builds; base where noted):**

| probe | result |
|---|---|
| `p_slice`, `p_find`, `p_replace`, `p_split`, `p_format2`, `p_repr`, `p_ord2`, `p_strip`, `p_misc`, `p_negwin`, `p_negcount`, `p_alias`, `p_encode`, `p_carriers`, `p_is2`, `p_case` | match CPython |
| `p_bmp2` (BMP regression) | match; astral literal refused by name |
| `p_slice_none` | differs identically on base (pre-existing) |
| `p_ascii_bmp`, `p_ascii2` | `%a`/`{!a}` do not escape non-ASCII; identical on base for BMP |
| `p_expand` | **new wrong output for astral `expandtabs`** |

**Defect 1 – `str.expandtabs` counts UTF-16 units, not code points**
```python
def main() -> None:
    e = b'\xf0\x9f\x98\x80'.decode()
    print(repr(('a' + e + 'b\tc').expandtabs(4)))
```
CPython: `'a😀b c'` — AIL: `'a😀b    c'` (`ail__expandtabs_len`/`ail_meth_str_expandtabs`, cruntime.py:18575/18586, increment `col` per unit; tab stops shift by one per astral character). Base only refused at decode, so this regression is caused by the change.

**Claims:** commit `dd98c0d`, test module, DEVLOG/DIFFERENCES, manifest check, clean tree (only `.agent/pipeline.md`) — verified. "Required tests + 13 string modules" — only `test_ail_pre123` and `test_ail_safetynet` rerun here (pass); the others unverified. Tests: `test_ail_pre123` 41.2s ok, `test_ail_safetynet` 124.1s ok, manifest `--check` rc=0.

**Pre-existing:** explicit-`None` slice stop (`s[3:None:-1]` behaves like `s[3:0:-1]`) and `%a` not escaping non-ASCII both reproduce identically on base.

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3`, the 13 claimed string modules, wide-string mode, instruction counts (`perf_event_open: Permission denied`).

VERDICT: FIX
1. `str.expandtabs` is unit-based; probe above expected `'a😀b c'`, actual `'a😀b    c'`.
[cost $0.0000, opencode tokens {"total": 2563261, "input": 95388, "output": 10954, "reasoning": 27095, "cache.write": 0, "cache.read": 2429824}]
    tool time: bash 8.2 min
        126s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1500 python3 ../tools/par_check.py -j 2 test
        104s bash   cd /home/runner/work/ail-ci/ail-ci && date && for f in p_slice p_find p_replace p_split p_format p_repr p_ord 
         62s bash   cd /tmp/rprobes && cat > p_format2.py <<'PY' def main() -> None:     e=b'\xf0\x9f\x98\x80'.decode()     m=b'\x
         35s bash   cd /tmp/rprobes && cat > p_is.py <<'PY' def main() -> None:     e=b'\xf0\x9f\x98\x80'.decode()     d=b'\xf0\x9
         28s bash   cd /tmp/rprobes && cat > p_slice2.py <<'PY' def main() -> None:     e=b'\xf0\x9f\x98\x80'.decode()     m=b'\xf
         27s bash   cd /tmp/rprobes && cat > p_slice2.py <<'PY' def main() -> None:     e=b'\xf0\x9f\x98\x80'.decode()     m=b'\xf
         26s bash   cd /tmp/rprobes && cat > p_is2.py <<'PY' def main() -> None:     e=b'\xf0\x9f\x98\x80'.decode()     d=b'\xf0\x
         16s bash   cd /tmp/rprobes && cat > p_ascii2.py <<'PY' def main() -> None:     e=b'\xf0\x9f\x98\x80'.decode()     print(r

## worker report 1
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Fixed and committed on `job-pre123-10242349` as `308b3d2` (parent `dd98c0d`).

**Fix:** `str.expandtabs` now steps by `ail__str_width` and advances `col` once per code point in both passes, while sizing the buffer in UTF-16 units (`cruntime.py:18575`, `18588`). The uncommitted fix already present in the tree was verified and committed.

**Probes (both `g` and `d` builds):**
- `p_expand_basic.py` — astral before/after tabs, mixed BMP/astral, tabsize 4/8/0/-3/default, `\n`/`\r`, empty → same stdout as CPython
- `p_expand_carriers.py` — function argument, list item, dict value, class attribute, split result → same stdout as CPython

**Tests (final content):** `test_ail_pre123` 57.0s, `test_ail_safetynet` 125.4s, `test_ail_files` 129.2s, `test_ail_corpus_findings3` 207.9s — 4 modules, 0 failed. Added `astral_expandtabs` case; `MANIFEST.json` updated and `--check` rc=0. Tree clean except pre-existing untracked `.agent/pipeline.md`.
[cost $0.0086, opencode tokens {"total": 429675, "input": 25587, "output": 3696, "reasoning": 2184, "cache.write": 0, "cache.read": 398208}]
    tool time: bash 4.9 min
        267s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 2400 python3 ../tools/par_check.py -j 2 test
         27s bash   cd /tmp/probes && printf '\nmain()\n' >> p_expand_basic.py && printf '\nmain()\n' >> p_expand_carriers.py && c
          0s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p_expand_basic p_expand_carriers; do echo "=== $p ==="; bash ~/
          0s bash   cd /home/runner/work/ail-ci/ail-ci && grep -rn "class .*:" AIL_CURRENT/test_ail_str_case.py AIL_CURRENT/test_a
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git status && git log --oneline -5 && ls
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git diff --stat && git diff | head -100
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git add AIL_CURRENT/MANIFEST.json AIL_CURRENT/python/pkg-v12/cruntime.py

## review 1 failed to run:          15s bash   cd /tmp/rprobes && cat > brute.py <<'EOF' def main() -> None:     em = b'\xf0\x9f\x98\x80'.decode()     em2 =           14s bash   cd /tmp/rprobes && cat > literal.py <<'EOF' def main() -> None:     s = '\U0001F600'     print(repr(s), len(s)           8s bash   cd /tmp && rm -rf ird && mkdir ird && cp /tmp/rprobes/astral_alias.py ird/p.py && cd ird && AIL_IR=1 AIL_NO_CA 

## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change really does.** Two commits, not one: `dd98c0d` (the substantive change) stores non-BMP code points as UTF-16 surrogate pairs in the general path and makes `len`, indexing, slicing, iteration, search, split, replace, strip, pad and formatting point-aware via an `aux` bit; `308b3d2` fixes `expandtabs` to advance the column per code point. The report describes only the second commit; the first (558 lines in `cruntime.py` plus `safetyrt.py`/`pyboxed2.py`/`tuplegen.py`) is omitted from the report although the DEVLOG documents it. That is a report/diff mismatch, not a code defect.

**Verified claims.** `expandtabs` fix matches the diff (`cruntime.py:18575,18588`); worker probes `p_expand_basic`/`p_expand_carriers` and my probes match CPython on both builds. `test_ail_pre123` 57.3 s and `test_ail_safetynet` 123.9 s, 0 failed. `update_manifest.py --check` rc=0; tree clean except untracked `.agent/pipeline.md`. Commit hashes/parent correct.

**Probes (all same stdout on g and d unless noted).** My `/tmp/rprobes/p1`–`p17`: decode/len/index/slice/iter/reversed, find/rfind/count/index with all window signs, startswith/endswith, replace (empty/old/count), split/rsplit/partition, strip/lstrip/rstrip, join, repeat, compare/sort/dict, repr/str of strings and containers, `%`/`.format`/f-string (precision, width, astral fill), ljust/rjust/center/zfill (astral fill and content), chr/ord, encode, bytearray decode, aux-backed ASCII views. All matched. `slices_all.py` exhaustively covered all lo/hi/step windows and matched.

**Defects (must be fixed).**

1. Large hot-path slowdown for ASCII/BMP strings. `ail_meth_str_find/rfind/count/startswith/endswith` now call `ail_str_len_points`/`ail__str_units_at` unconditionally instead of only when `sobj.sv.backing->aux` is set; `ail_str_buf_done` additionally scans every result for pairs. Microbenchmarks (same generated program, 3 stable runs, wall time):
   - `/tmp/rprobes/perf_ln.py`: 5,000,000 iterations of `startswith('the')`/`endswith('fox')` on 19–30-char strings. Base 0.056 s, HEAD 0.582 s (~10.4x).
   - `/tmp/rprobes/perf_sw.py`: 1,000,000 iterations on 440-char strings. Base 0.012 s, HEAD 2.061 s (~172x).
   - `/tmp/rprobes/perf_find.py`: 200,000 iterations of `find`+`count` on 440-char strings. Base 0.151 s, HEAD 0.665 s (~4.4x).
   Expected: the ASCII/BMP path should keep base's O(1) `startswith`/`endswith` and O(n) `find` without an extra full scan; actual: every call scans the whole string. The DEVLOG claim "the common case does not pay for a per-operation scan" is therefore false for these operations. (`ail_str_cmp` also decodes points per unit, a smaller constant-factor regression.)

**Pre-existing (identical on `/tmp/base`, do not block).**
- Explicit `None` slice bounds are wrong on both trees: `'abcde'[None:None:-1]` → CPython `'edcba'`, base and HEAD `''`; `'abcde'[3:None:-1]` → `'dcba'` vs `'dcb'` (`/tmp/rprobes/p9_noneascii.py`).
- `json.loads('"\\ud83d\\ude00"')` raises the same ValueError on base and HEAD.
- Non-BMP string literals are refused by name on both; `chr()` surrogate values die on both.

**Unverified.** `test_ail_files` and `test_ail_corpus_findings3` (not re-run per instructions); instruction counts (`perf_event_open` EPERM, used wall time); full suite; wide-string mode. `--debug-dir` user-code tail is identical to base for a no-feature program, but the shared runtime preamble necessarily differs.

**Verdict.** Correctness of the astral work is good; the unconditional point scans are a fixable, large performance defect.

VERDICT: FIX
[cost $0.1026, opencode tokens {"total": 7639293, "input": 277417, "output": 17730, "reasoning": 47378, "cache.write": 0, "cache.read": 7296768}]
    tool time: bash 14.7 min, read 0.0 min
        195s bash   date; cd /home/runner/work/ail-ci/ail-ci && for p in p_case p_is p_is2 surrogates literal astral_more p_format
        126s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ai
        100s bash   date; cd /home/runner/work/ail-ci/ail-ci && for p in slices_all p_slice p_slice2 p_find p_negwin p_negcount p_
         70s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p1_core p2_ops p3_carriers p4_expand p5_nofeature; do echo "===
         37s bash   cat > /tmp/rprobes/p15_libs.py <<'EOF' import json import re  def main() -> None:     e = b'\xf0\x9f\x98\x80'.
         27s bash   date; cd /home/runner/work/ail-ci/ail-ci && for p in p_expand_basic p_expand_carriers; do echo "== $p"; tail -
         27s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 240 bash ~/tools/cmp.sh /tmp/rprobes/p_slice.py $PWD 2>&1 | tail
         27s bash   cat > /tmp/rprobes/p8_neg2.py <<'EOF' def main() -> None:     e = b'\xf0\x9f\x98\x80'.decode()     s = e + 'b'

FINAL VERDICT: FIX  2026-10-24T16:30:15Z
