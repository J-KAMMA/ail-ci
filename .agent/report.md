# job job-pre416-10281338  started 2026-10-28T04:39:02Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"af9bd2c8-dede-4abf-928e-7246e5e3a86c","session_id":"8e377b31-c9fd-40c5-9087-c05f1c7864ee"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"5a41fd46-61f7-4a82-adeb-06522b926f75","session_id":"ff59b6e2-38df-4481-bffe-9eceb8c065ca"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented and committed as `6085593 pre416: exception item errors name the class`.

- Fixed `ail__tname_c` in `AIL_CURRENT/python/pkg-v12/cruntime.py:14815` to name `AIL_T_EXC` values by their class. `E()[0]`, slices, assignment, and deletion now print `'E'`, matching CPython.
- Added `AIL_CURRENT/test_ail_pre416.py` (2 tests, 6 programs, both builds), registered it in `ail_check.MODULES` and `tools/ci_shards.json`.
- Added DIFFERENCES row `C?-job-pre416-10281338-1` and a top DEVLOG entry.
- Probes `e01`, `e02`, `e03`, `e05`, `e06` and controls `a01`, `a02`, `d02`: all matched CPython on both builds.
- Final-state tests passed on the commit: `test_ail_pre416`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 309s, 0 failed.
- `update_manifest.py --check` and `ci_shards.py --check` pass. Class-object differences (`A[0]`, `del A[0]`, `__class_getitem__`) remain untouched.
[cost $0.0000, opencode tokens {"total": 4686398, "input": 295435, "output": 15314, "reasoning": 19681, "cache.write": 0, "cache.read": 4355968}]
    tool time: bash 9.2 min
        311s bash   python3 tools/par_check.py -j 2 test_ail_pre416 test_ail_safetynet test_ail_files test_ail_corpus_findings3 2>
         55s bash   python3 tools/par_check.py -j 2 test_ail_pre416 test_ail_pre377 2>&1 | tail -40
         45s bash   rm -f /tmp/probes/pre416/e04_builtins.py cat > /tmp/probes/pre416/e05_dunder.py <<'PY' class E(Exception):    
         34s bash   ls /tmp/probes/pre416; echo ===; for f in /tmp/probes/pre416/*.py; do printf '%s: ' "$(basename "$f")"; bash ~
         30s bash   for p in /tmp/probes/pre416/*.py; do echo "===== $(basename $p)"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | grep 
         29s bash   for f in /tmp/probes/pre416/*.py; do echo "=== $(basename $f)"; bash ~/tools/cmp.sh "$f" /home/runner/work/ail
         19s bash   cat > /tmp/probes/pre416/e03_routes.py <<'PY' class E(Exception):     pass  class F(E):     pass  class Holder
         19s bash   for p in e01_exc e02_exc_slice k01_class_sub c01_classgetitem d01_del_class; do echo "===== $p"; bash ~/tools/

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: `6085593 pre416: exception item errors name the class`

**What the change really does:** broadens `ail__tname_c` (`cruntime.py:14815`) so *every* error message using that helper names an exception value's class, not just item errors. It does not restrict the change to item paths.

**Probes** (`bash ~/tools/cmp.sh …`, both builds, HEAD vs `/tmp/base`):
- `p1_item_routes.py` — `E()[0]`, negative/bool/string keys, getitem slices, int-key assignment/deletion via arg, list item, attribute, dict value, subclass: **match CPython**.
- `p1b_slice.py` — slice assignment/deletion on `E`/`F`: still `'exception'`; **identical on base**.
- `p2b_long.py` — 211-char class name, get/set/del: **match**.
- `p3_other_tname.py` — `E()+1`, `1+E()`, `E()-1`, `"abc"[E()]` now **fixed**; `E()*2`, `/`, `divmod`, `iter`, `int`, `len`, `.nope` still differ, **identical on base**.
- `p5_control.py` — ordinary indexing/errors: **same stdout**; debug-dir C differs only in the intended helper line.
- `p6_getitem.py`, `p7b_builtin.py`, `p8_raised.py` — dunder `__getitem__`, builtin exceptions, caught/re-raised: **match**.
- `p12_alias.py` — **fails** (below).
- `p2_names.py` — non-ASCII class name refused by name; acceptable.

**Claims:**
- Helper now names `AIL_T_EXC` by class — **verified**.
- "`E()[0]`, slices, assignment, deletion print `'E'`" — **verified** for getitem and int-key set/del; slice assignment/deletion still `'exception'` (pre-existing), so the wording is overbroad.
- New test registered in `ail_check.MODULES`/`ci_shards.json`, DIFFERENCES/DEVLOG added — **verified**.
- Tests: `test_ail_pre416` 25.9s ok, `test_ail_safetynet` 106.9s ok. `test_ail_files`, `test_ail_corpus_findings3` — **unverified** (not re-run per instructions).
- `update_manifest.py --check`, `ci_shards.py --check` — **verified**.
- Worker's `/tmp/probes/pre416` results — **unverified** (files not present).
- Speed: cold error path only; no measurement needed — **agree**.

**Pre-existing (identical on base, non-blocking):** slice assignment/deletion still `'exception'` (`safetyrt.py:141`); `*`, `/`, `//`, `%`, `**`, `divmod`, comparison and `iter`/`int`/`len`/attribute messages still use generic names.

VERDICT: FIX
1. **Two-exception operand messages now repeat the left class.** Probe `/tmp/rprobes/p12_alias.py`:
   ```
   class E(Exception): pass
   class F(Exception): pass
   def show(label, fn):
       try: fn()
       except TypeError as e: print(label, '=>', str(e))
   show('E+F', lambda: E() + F())
   show('F+E', lambda: F() + E())
   show('E&F', lambda: E() & F())
   show('E<<F', lambda: E() << F())
   ```
   Expected (CPython):
   ```
   E+F => unsupported operand type(s) for +: 'E' and 'F'
   F+E => unsupported operand type(s) for +: 'F' and 'E'
   E&F => unsupported operand type(s) for &: 'E' and 'F'
   E<<F => unsupported operand type(s) for <<: 'E' and 'F'
   ```
   Actual (both builds):
   ```
   E+F => unsupported operand type(s) for +: 'E' and 'E'
   F+E => unsupported operand type(s) for +: 'F' and 'F'
   E&F => unsupported operand type(s) for &: 'E' and 'E'
   E<<F => unsupported operand type(s) for <<: 'E' and 'E'
   ```
   Cause: `ail__tname_c` returns one static buffer (`tnb`); callers such as `cruntime.py:14877`/`15084`/`15116` call it twice in one `snprintf`, so both `%s` see the same (left) name. Before this change exceptions fell through to the literal `"exception"`, so the aliasing was unreachable for them; the broadened condition newly exposes it. Base output was `'exception' and 'exception'`, so this wrong output is **not** identical to base. Fix by formatting each operand name into its own buffer (or applying class naming only in `ail__raise_item_tname`); add a two-exception case to `test_ail_pre416.py`.
[cost $0.0000, opencode tokens {"total": 1538717, "input": 96236, "output": 8151, "reasoning": 20954, "cache.write": 0, "cache.read": 1413376}]
    tool time: bash 3.8 min
        109s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT; date; python3 ../tools/par_check.py -j 2 test_ail_pre416 test_
         35s bash   cd /home/runner/work/ail-ci/ail-ci; date; for f in /tmp/rprobes/p*.py; do echo "===== $(basename $f)"; bash ~/
         19s bash   cd /home/runner/work/ail-ci/ail-ci; date; for f in /tmp/rprobes/p1b_slice.py /tmp/rprobes/p2b_long.py /tmp/rpr
         16s bash   cd /tmp/base; date; for f in /tmp/rprobes/p1b_slice.py /tmp/rprobes/p4b_two.py /tmp/rprobes/p3_other_tname.py;
         10s bash   cd /tmp/rprobes && cat > p10_inst_bit.py <<'PY' class A:     pass class B:     pass for op in ['&', '|', '^']:
          9s bash   cd /tmp/rprobes && cat > p9_inst_alias.py <<'PY' class A:     pass class B:     pass try:     A() + B() except
          6s bash   cd /tmp/rprobes && cat > p11_ops.py <<'PY' class E(Exception):     pass class F(Exception):     pass def show(
          5s bash   cd /tmp/rprobes && cat > p12_alias.py <<'PY' class E(Exception):     pass class F(Exception):     pass def sho

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed the review defect: two-operand messages now format each class name into its own buffer, and arithmetic names use CPython's 100-character cap. Commit `bffdb2e`.

Probes in `/tmp/probes/pre416_fix`, both builds via `cmp.sh` — all match CPython:
- `p1_two_exc`: `+ - & | ^ << >>`, both operand orders
- `p2_routes`: argument, list item, attribute, dict value, alias
- `p3_mixed`: exception with builtin operand, both orders
- `p4_controls`: ordinary instances and builtin operand pairs
- `p5_long`: 211-character class names
- `p6_item_regress`: item access/slice/assignment/deletion
- `p7_views`: dict-view/set comparison messages

Tests (final code state): `test_ail_pre416`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 231s, 0 failed. `update_manifest.py --check` and `ci_shards.py --check` pass.

Pre-existing `*`, `/`, and `len` wording remains unchanged, as the review noted.
[cost $0.0000, opencode tokens {"total": 1864104, "input": 98302, "output": 9370, "reasoning": 9232, "cache.write": 0, "cache.read": 1747200}]
    tool time: bash 5.2 min, write 0.0 min
        233s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pre416 test_ail_safetynet test_
         31s bash   cd /home/runner/work/ail-ci/ail-ci && for f in /tmp/probes/pre416_fix/*.py; do echo "===== $(basename $f)"; ba
         30s bash   cd /home/runner/work/ail-ci/ail-ci && for f in /tmp/probes/pre416_fix/*.py; do echo "===== $(basename $f)"; ba
         14s bash   cd /home/runner/work/ail-ci/ail-ci && for f in /tmp/probes/pre416_fix/*.py; do echo "===== $(basename $f)"; ba
          4s bash   cd /home/runner/work/ail-ci/ail-ci && bash ~/tools/cmp.sh /tmp/probes/pre416_fix/p7_views.py "$PWD"
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p = Path('DEVLOG.md') s = p.re
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c

## review 1
[model opencode/deepseek-v4.1-flash-free]
**What the change does.** It broadens the general runtime's object-to-name helper to `AIL_T_EXC` so item errors and two-operand messages name an exception subclass, copies each operand name into its own buffer for `+`, `-`, bitwise and dict-view messages, caps the arithmetic names at 100, and enlarges the arithmetic message buffers (with matching `dunderrt.py` anchors). This matches the report except that the dict-view names are not capped and sequence concatenation was left uncapped.

**Verified claims.**
- Item access/slice/assignment/deletion name the exception class on both builds (r6 with 100/201-char names, r10 with a 300-char name all match CPython).
- `+`, `-`, `&`, `<<` etc. with two exception operands or mixed builtins now match, including the 100-char cap (r1, r7).
- `test_ail_pre416`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 4 modules, 233s, 0 failed. `update_manifest.py --check` and `ci_shards.py --check` pass.
- Pre-existing `*`, `//`, `%`, `/`, `**` and comparison wording is unchanged (r4, r5 differ identically on `/tmp/base`).

**Defects.**

1. `/tmp/rprobes/r2_dview_long.py` — dict-view comparison with a long exception class name. `class Naaa…(Exception)` (150 chars); `{}.keys() < N()`. CPython caps the name at 100 chars: line length 157, `…aaaa'`. Both builds instead emit 159 chars, no closing quote (the 160-byte `eb` truncates the uncapped `ail__tname_c` result). The new `na`/`nb` copies in `dictviews.py:288-290` still need `%.100s`.

2. `/tmp/rprobes/r11_concat211.py` — sequence concatenation names an exception. 211-char class name; `[] + N()`. CPython prints the name cut to 200 chars (line 242). Both builds print the full 211 chars (line 253) because the concat branch (`cruntime.py:14884`) calls `ail__tname_c(b)` directly; the enlarged 256-byte buffer only moved the cut point. With a 300-char name (r9) the message is cut mid-name with no closing quote.

**Pre-existing (identical on base).** `E() * F()`, `E() // F()`, `E() % F()`, `E() / F()`, `E() ** F()` print `'exception'` (r4); `E() < F()` etc. print `'exception'` (r5). Neither is touched by this change.

**Unverified.** Did not re-run the worker's exact probes (inspected them; equivalents were run). Speed not measured: the edited paths are cold error paths. Did not compare `--debug-dir` text for unrelated programs because these runtime-template edits necessarily change every general-path C file; behaviour controls (r8) match CPython.

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 1505771, "input": 64271, "output": 5584, "reasoning": 18956, "cache.write": 0, "cache.read": 1416960}]
    tool time: bash 5.5 min
        234s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre416 tes
         38s bash   date; cd /home/runner/work/ail-ci/ail-ci && for f in /tmp/rprobes/r*.py; do echo "########## $(basename $f)"; 
         19s bash   date; cd /tmp/base && for f in r2_dview_long r4_star_alias r5_cmp_alias r1_add_long; do echo "########## BASE 
         14s bash   date; cd /home/runner/work/ail-ci/ail-ci && for f in r2_dview_long r4_star_alias r5_cmp_alias; do echo "######
          9s bash   python3 - <<'PY' from pathlib import Path N300='N'+'a'*299 Path('/tmp/rprobes/r9_concat300.py').write_text(f''
          5s bash   date; cd /home/runner/work/ail-ci/ail-ci && out=$(bash ~/tools/cmp.sh /tmp/rprobes/r2_dview_long.py "$PWD" 2>&
          5s bash   python3 - <<'PY' from pathlib import Path N='N'+'a'*210 Path('/tmp/rprobes/r11_concat211.py').write_text(f''' 
          4s bash   python3 - <<'PY' from pathlib import Path N='N'+'a'*210 Path('/tmp/rprobes/r12_concat_inst211.py').write_text(

FINAL VERDICT: FIX  2026-10-28T05:25:52Z
