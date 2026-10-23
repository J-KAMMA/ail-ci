# job job-fuzz76-10231547  started 2026-10-23T06:47:56Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `1233b8d` on `job-fuzz76-10231547`.

**Fix:** IR str format specs ignored fill entirely; general runtime stored fill in `char`, truncating non-Latin-1 fill code points. Both now preserve the full fill code point. Added `test_ail_fuzz76.py`.

**Tests (final commit):** `test_ail_fuzz76`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed, 250s. Manifest and shard checks pass.

**Self-check probes:** `p01` fill/align/empty/zero, `p02`/`p02b` ASCII+non-ASCII fill, `p04` narrow width, `p05` width+precision, `p06` arg/list/dict/attribute, `p12` combined string+numeric fill — all matched CPython on both builds. First differing program was `p02`; fixed. Other differences seen but not fixed: IR numeric `=` alignment/sign flags dropped (`p03`, `p09`, `p10`, `p11`), huge negative literal refused on general path (`p07`), wrong-type specs raise `TypeError` instead of `ValueError` (`p08`). No `DEVLOG`/`DIFFERENCES` file exists in this export, so no rows were added.
[cost $0.0000, opencode tokens {"total": 5314398, "input": 473931, "output": 13317, "reasoning": 16014, "cache.write": 0, "cache.read": 4811136}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
Reviewed `1233b8d` (`work..HEAD`). The patch is the fill fix it claims: IR `fmt_str` now carries `ord(fill)` and calls `ail_fmt_gen_str`; both general-runtime `ail_fmtspec.fill` fields are `int` and every padding write stores the whole code point.

Probes (`bash ~/tools/cmp.sh SRC $PWD`; HEAD `d`/`g`, base in `/tmp/base`):
- `r1_bmp_fill` (f-string + `.format`; é/日; literal/arg/list/dict/attr; narrow; width+precision): HEAD `d` and `g` match CPython. Base `g` prints `å` for `日`, base `d` prints spaces → fixed.
- `r7_narrow_fill` (`width < len`, non-ASCII fill, `len()`): both HEAD builds match.
- `r4_num_bmp_and_sign` (numeric 日/é fill with `=` and `+`): HEAD `g` matches (base `g` `å`); HEAD `d` still drops `=`/sign, identical to base → pre-existing.
- `r9_percent_zero` (`%05s`, `%-05s`, ...): HEAD both builds and base match.
- `r6`/`r6b` (`{s:05}`, `{s:<05}`): HEAD == base, `[000ab]`/`[ab   ]` vs CPython `[ab000]` → pre-existing.
- `r2` (emoji fill): both builds and base refuse `non-BMP string literal` by name; acceptable.
- `r5`/plain int: output matches, and `py_main` C is byte-identical to base.
- worker `p12`: both builds match.

Pre-existing (not blocking): str zero-fill `{s:05}`/`{s:<05}` is wrong; IR numeric `=`/sign flags dropped; huge negative literal refused on general path; wrong-type specs raise `TypeError` instead of `ValueError`. The new str-spec guard is effectively dead (legacy refuses those specs before IR), but harmless.

Claims: IR-fill ignored — verified; general `char` truncation — verified; full fill now — verified for expressible BMP fills (non-BMP literals are outside the 16-bit runtime); numeric general padding fixed — verified; 4 test modules — `test_ail_fuzz76` + `test_ail_safetynet` re-run (2 modules, 0 failed, 118s), other two not re-run per reviewer scope (unverified); manifest/shard — verified; other differences — verified on p07/p08; no DEVLOG/DIFFERENCES — verified absent.

Speed: `tools/icount` cannot run (perf_event_open EPERM, paranoid=4). Wall-time proxy: g01_026 unchanged (0.64–0.71 ms) and int/plain control loops unchanged. A 4M width-only str-format loop is ~1.43× slower (0.059s→0.084s, ≈6 ns/call) because space fill now goes through `ail_fmt_gen_str`; no gdev program is hot in this path, so no corpus slowdown observed.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 6396508, "input": 352052, "output": 13988, "reasoning": 52868, "cache.write": 0, "cache.read": 5977600}]

FINAL VERDICT: ACCEPT  2026-10-23T07:39:13Z
