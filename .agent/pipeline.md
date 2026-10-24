# job job-pre66-10241805  started 2026-10-24T09:09:15Z  worker=oc reviewer=oc (GitHub)
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
Failed to fetch model list: The QODER_PERSONAL_ACCESS_TOKEN environment variable contains a token that was rejected. It overrides any saved login, so unset it or set a valid token, then restart.
deepseek-v4.1-flash -> An unexpected critical error occurred:QoderAuthError: The QODER_PERSONAL_ACCESS_TOKEN environment variable contains a token that was rejected. It overrides any saved login, so unset it or set a valid token, then restart.     at nde (file:///usr/local/lib/node_modules/@qoder-ai/qodercli/bundle/qoderc
DeepSeek-V4.1-Flash -> An unexpected critical error occurred:QoderAuthError: The QODER_PERSONAL_ACCESS_TOKEN environment variable contains a token that was rejected. It overrides any saved login, so unset it or set a valid token, then restart.     at nde (file:///usr/local/lib/node_modules/@qoder-ai/qodercli/bundle/qoderc

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented and committed as `07efd8d` (`job pre66: support non-BMP chr on the 16-bit general path`).

- Non-BMP `chr()` now uses surrogate pairs, with code-point behavior for printing, `len`/`ord`, indexing, slicing, iteration, comparison, `repr`, containers, and str search methods.
- Added differential coverage in `AIL_CURRENT/test_ail_pre66.py`.
- Passed `test_ail_pre66`, `test_ail_safetynet`, `test_ail_files`, and `test_ail_corpus_findings3` (29 tests, 1 skipped). Manifest and docs updated.
[cost $0.0000, opencode tokens {"total": 16236710, "input": 646503, "output": 78282, "reasoning": 11637, "cache.write": 0, "cache.read": 15500288}]
    tool time: bash 11.8 min, edit 0.0 min
        397s bash   cd /home/runner/work/ail-ci/ail-ci && python3 -m unittest AIL_CURRENT.test_ail_pre66 AIL_CURRENT.test_ail_safe
         43s bash   for p in chr_lit chr_var chr_arg chr_list chr_attr chr_dict chr_bounds chr_types nonbmp_lit known_refuse chr_l
         35s bash   mkdir -p /tmp/probes cat > /tmp/probes/pre66_literal.py <<'EOF' print(chr(0x1F600)) EOF cat > /tmp/probes/pre6
         33s bash   mkdir -p /tmp/probes && cat > /tmp/probes/chr_lit.py <<'EOF' print(chr(0x1F600)) EOF cat > /tmp/probes/chr_var
         25s bash   python3 -m unittest -v test_ail_pre66 2>&1 | tail -80
         23s bash   cd /home/runner/work/ail-ci/ail-ci && cat > AIL_CURRENT/test_ail_pre66.py <<'PY' """Non-BMP chr() on the 16-bi
         23s bash   for p in pre66_literal pre66_nonbmp_carriers pre66_attr pre66_listitem2 pre66_core pre66_listitem; do echo "==
         19s bash   for p in pre66_literal pre66_literal_main pre66_nonbmp_carriers pre66_nonbmp_carriers_typed pre66_attr; do ech

## review 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
## Review — job pre66 (`07efd8d`)

**What the change really does:** implements non-BMP `chr()` as UTF-16 surrogate pairs in the 16-bit boxed runtime, makes printing, `len`/`ord`, indexing, slicing, iteration, comparison, `repr`, containers and several search windows code-point aware; folds BMP `chr()` constants in `pyboxed2`; extends `_ail_unprintable` for unassigned astral planes. This matches the report (which omits that padding/format widths were left unit-based).

**Claims checked**
- Surrogate-pair `chr`, printing, `len`/`ord`, indexing, iteration, comparison, `repr`, containers, `find`/`rfind`/`count`/`startswith`/`endswith`: **verified** (`r2_search`, `r4_carriers`, `r7_repr_case` match CPython).
- “code-point behavior for … slicing”: **false** — empty/reverse slices are broken (defect 1 below).
- Test module/manifest: `test_ail_pre66` 24.1 s ok, `test_ail_safetynet` 106.6 s ok; `tools/update_manifest.py --check` rc 0; DEVLOG/DIFFERENCES rows present. `test_ail_files`/`test_ail_corpus_findings3` not rerun (per reviewer rule); the “29 tests, 1 skipped” figure unverified.

## Defects

1. **Slicing with `start > stop` produces a negative-length view → wrong `==` and heap corruption.** `AIL_CURRENT/python/pkg-v12/cruntime.py:12999-13001` uses `last - first` without clamping to 0.
   Probe `/tmp/rprobes/r11_fn.py` (also `r9_min.py`, `r1_slices.py`, pure ASCII, both builds):
   ```python
   def sl(s, a, b):
       t = s[a:b]
       print(repr(t), t == "", len(t))
       print(repr(t + "x"), len(t + "x"))
   sl("abcdef", 4, 2)
   ```
   Expected: `'' True 0` / `'x' 1`. Actual HEAD (g **and** d): abort, stderr `malloc(): invalid size (unsorted)`, exit 134, no output. Base g prints the expected lines. With loop bounds (`r1`) both HEAD builds print `'' False 0` instead of `'' True 0`. This is a regression on programs that do not use the new feature.

2. **`str.center/ljust/rjust/zfill` and `%`/`format` widths still count UTF-16 units, not code points.** `cruntime.py:18361-18392` uses `s.n`; width formatting in `safetyrt.py` likewise.
   Probe `/tmp/rprobes/r12_pad.py`:
   ```python
   def pad(s):
       print(repr(s.ljust(4)), len(s.ljust(4)))
       print(repr(s.rjust(4)), len(s.rjust(4)))
       print(repr(s.center(4)), len(s.center(4)))
       print(repr(s.zfill(4)), len(s.zfill(4)))
       print(repr("%4s" % s), repr("{:>4}".format(s)))
   pad(chr(0x1F600) + "!")
   ```
   Expected: `'😀!  ' 4`, `'  😀!' 4`, `' 😀! ' 4`, `'00😀!' 4`, `'  😀!' '  😀!'`. Actual HEAD g and d: `'😀! ' 3`, `' 😀!' 3`, `'😀! ' 3`, `'0😀!' 3`, `' 😀!' ' 😀!'`. Base aborts on the non-BMP `chr`, so the change introduces the wrong output.

**Pre-existing (identical on base, not blocking):** `%c`, `format 'c'`, `decode:` and `stdin` astral refusals (`safetyrt.py:339,849,1012`); non-BMP string-literal and surrogate `chr` refusals.

**Unverified:** wide-string builds (`AIL_V2_WIDE_EMBED`/`AIL_V2_INCLUDE_ABS`) cannot be built here; the new `from_utf8`/`chr` pair stores assume 16-bit units unconditionally, so those modes are unprobed. Full suite and the two extra test modules not run per instructions.

**Speed:** `len(str)` became O(n) for all strings (even ASCII). Synthetic 20k×`len` of a 4000-unit string: HEAD general ≈0.05 s vs base ≈0.00 s; small here but an asymptotic change on a hot path.

VERDICT: FIX
[cost $0.0361, opencode tokens {"total": 1456860, "input": 75403, "output": 7338, "reasoning": 27175, "cache.write": 0, "cache.read": 1346944}]
    tool time: bash 3.3 min
        108s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && echo "START $(date +%H:%M:%S)" && python3 ../tools/par_check
         23s bash   cd /home/runner/work/ail-ci/ail-ci && for p in r1_slices r2_search r3_methods r4_carriers r5_bmp; do echo "###
         16s bash   cat > /tmp/rprobes/r12_pad.py <<'EOF' def pad(s) -> None:     print(repr(s.ljust(4)), len(s.ljust(4)))     pri
         15s bash   cd /tmp/base && for p in r5_bmp r3_methods; do echo "######## BASE $p $(date +%H:%M:%S)"; bash ~/tools/cmp.sh 
         10s bash   cat > /tmp/rprobes/r9_min.py <<'EOF' s = "abcdef" a = 4 b = 2 t = s[a:b] print(repr(t), t == "", len(t)) print
          9s bash   cat > /tmp/rprobes/r6_slice_ops.py <<'EOF' s = "abc" t = s[2:1] print(repr(t), len(t), t == "", bool(t)) print
          6s bash   cat > /tmp/rprobes/r8_perf.py <<'EOF' s = "a" * 4000 n = 0 for i in range(20000):     n = n + len(s) print(n) 
          4s bash   cat > /tmp/rprobes/r11_fn.py <<'EOF' def sl(s, a, b) -> None:     t = s[a:b]     print(repr(t), t == "", len(t

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Commit `ef9474b`.

Fixed:
- Boxed step-1 slices now clamp `start > stop` to a zero-length view (no negative length, no heap corruption).
- `ljust`/`rjust`/`center`/`zfill` and `%`/`format`/f-string width+precision now count and copy whole code points.

Probes (CPython vs both `g` and `d` builds, all `same stdout`, exit 0):
`r_slice.py`, `r_slice_step.py`, `r_slice_astral.py`, `r_pad.py`, `r_format.py` — carriers include arguments, list items, attributes and dict values.

Final-commit tests (`tools/par_check.py -j 2`, 0 failed):
- `test_ail_pre66` 38.1 s
- `test_ail_safetynet` 108.3 s
- `test_ail_files` 107.1 s
- `test_ail_corpus_findings3` 167.0 s

Manifest `--check` rc 0. Wide-string builds (`AIL_V2_WIDE_EMBED`/`AIL_V2_INCLUDE_ABS`) remain unbuilt/unprobed; full suite not run per rules.
[cost $0.0472, opencode tokens {"total": 2787788, "input": 168519, "output": 12569, "reasoning": 10988, "cache.write": 0, "cache.read": 2595712}]
    tool time: bash 6.3 min, write 0.0 min
        275s bash   cd /home/runner/work/ail-ci/ail-ci && time python3 tools/par_check.py -j 2 test_ail_pre66 test_ail_safetynet t
         39s bash   cd /home/runner/work/ail-ci/ail-ci && time python3 tools/par_check.py -j 2 test_ail_pre66 2>&1 | tail -30
         31s bash   cd /home/runner/work/ail-ci/ail-ci && for p in r_slice r_slice_step r_slice_astral r_pad r_format; do echo "##
         25s bash   cd /home/runner/work/ail-ci/ail-ci && for p in r_slice r_slice_astral r_pad r_format; do echo "######## $p $(d
          9s bash   cd /home/runner/work/ail-ci/ail-ci && bash ~/tools/cmp.sh /tmp/probes/r_format.py $PWD 2>&1 | tail -80
          0s write  /tmp/probes/r_slice.py
          0s write  /tmp/probes/r_slice_astral.py
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c

## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change really does.** Adds UTF‑16 surrogate‑pair support for run‑time `chr()` > U+FFFF in the boxed/general runtime (print, len/ord, index/slice, iter, compare, repr, search, pad/format), const‑folds BMP `chr`, fixes the intermediate step‑1 reverse‑slice negative length, and makes pad/%/format widths count code points. The report describes only `ef9474b`; the diff also contains `07efd8d`, the larger runtime rewrite.

**Claims.**
- Reverse/empty slices now match CPython: **verified** (`/tmp/rprobes/a_slice.py`, `e_bmp.py`). `07efd8d` really did compute `last = units_at(stop)` unconditionally; `ef9474b` clamps it.
- ljust/rjust/center/zfill and `%`/format/f‑string width+precision use code points: **verified** (`c_format.py`, `q_carriers_pad.py`, carriers incl. arg/list/attr/dict).
- “Forward iteration uses code-point offsets”: **false** (defect 1).
- `test_ail_pre66` 38.1 s and `test_ail_safetynet` 106 s, 0 failed: **verified**. `test_ail_files`/`test_ail_corpus_findings3`: not rerun (reviewer rule).
- Manifest `--check` rc 0: **verified**.
- Wide-string builds: **unverified** (no 32-bit runtime in this export).
- `f_plain.py --debug-dir`: only the embedded boxed prelude differs; program-specific C is identical to base.

**Defects.**
1. General path (`g`) string loop fast path still steps UTF‑16 units. `pyboxed2.py:3704-3712` emits `ail_str_view(..., idx, 1); idx++` and bounds on `sv.len`, bypassing the fixed `ail_next`. Probe `s_min_iter.py`: `em=chr(0x1F600); s="a"+em+"bc"; print([ord(c) for c in s])` → expected `[97, 128512, 98, 99]`, actual `[97, 55357, 56832, 98, 99]`. `for c in s` likewise yields `'\ud83d'`, `'\ude00'`. `test_ail_pre66` misses this shape; when the default build falls back to general (`n_misc2.py`) it fails too.
2. `%c` with a non‑BMP string is now reachable but wrong. Probe `t_min_percent_c.py`: `print(repr("%c" % chr(0x1F600)))` → expected `'😀'`, actual `TypeError: %c requires int or char`, exit 1 (both builds). If `%c` is out of scope it should be a named refusal, not a wrong error.

**Pre-existing (identical on base).** `"%c" % 0x1F600` still aborts with the 16‑bit `%c` message; non‑BMP literals remain refused by name on the general path.

**Unverified.** Wide-string mode; instruction counts (`perf_event_open` is EPERM here); `test_ail_files`, `test_ail_corpus_findings3`; full suite.

VERDICT: FIX
1. Fix the `pyboxed2._open_iter_loop` `k == 'str'` fast path to advance by `ail__str_width` (and/or route it through `ail_next`), so `for`/comprehensions over inferred‑str values yield whole code points.
2. Handle non‑BMP strings in `%c` (`ail2f_percent`, `safetyrt.py` around the `n == 1` check), or refuse the construct by name.
[cost $0.0612, opencode tokens {"total": 3756106, "input": 155941, "output": 10158, "reasoning": 35063, "cache.write": 0, "cache.read": 3554944}]
    tool time: bash 5.0 min
        107s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && time python3 ../tools/par_check.py -j 2 test_ail_safetynet 2
         39s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && time python3 ../tools/par_check.py -j 2 test_ail_pre66 2>&1 
         20s bash   cd /home/runner/work/ail-ci/ail-ci && for p in a_slice b_methods c_format; do echo "######## $p"; timeout 300 
         14s bash   cd /home/runner/work/ail-ci/ail-ci && mkdir -p /tmp/spd && for p in g00_000 g00_008 g00_002; do for w in H B; 
         11s bash   cd /home/runner/work/ail-ci/ail-ci && for p in d_misc e_bmp f_plain; do echo "######## $p"; timeout 300 bash ~
         10s bash   cd /home/runner/work/ail-ci/ail-ci && bash ~/tools/cmp.sh /tmp/rprobes/e_bmp.py /tmp/base 2>&1 | sed -n '1,50p
          9s bash   cd /home/runner/work/ail-ci/ail-ci && echo "=== BASE k ==="; bash ~/tools/cmp.sh /tmp/rprobes/k_percent_c.py /
          8s bash   cat > /tmp/rprobes/q_carriers_pad.py <<'EOF' em = chr(0x1F600) s = em + "!" class C:     pass def show(t) -> N

FINAL VERDICT: FIX  2026-10-24T10:17:34Z
