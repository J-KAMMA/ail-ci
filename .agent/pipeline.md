# job job-fuzz43-10231200  started 2026-10-23T03:00:55Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the `str.startswith`/`str.endswith` tuple-prefix TypeError wording at `AIL_CURRENT/python/pkg-v12/cruntime.py:18007` and `:18022`, so bytes/user-class members now name their class instead of `instance`.

Added `test_ail_fuzz43.py`, `DEVLOG.md`, `DIFFERENCES.md`, and updated the manifest. Required 4-module test run passed. Committed as `252a4247`.

Other observed differences left unfixed: bytes `in`/search wrong-type messages and the documented non-ASCII `lower`/`upper` limit.
[cost $0.0000, opencode tokens {"total": 29989947, "input": 659770, "output": 62011, "reasoning": 95046, "cache.write": 0, "cache.read": 29173120}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: `252a4247`

**Change:** two lines in `pkg-v12/cruntime.py` now name the actual member class (`ail__tname_c`) in `startswith`/`endswith` tuple-member `TypeError`s; adds `test_ail_fuzz43.py`, `DEVLOG.md`, `DIFFERENCES.md`, manifest pins.

**Probes** (`cmp.sh`, g+d; HEAD unless noted): `p1` count overlap/empty/window, `p2` find/rfind empty at every position, `p3` index/rindex errors, `p4` `in` with empties via list/attr/dict, `p5` wrong types/bounds, `p7`/`p14` unicode, `p8` arg/list/attr/dict values, `p9`/`p24` huge bounds, `p10`/`p11` full find/rfind/count/index window sweeps, `p12`/`p13` bytes/bytearray, `p15` `in` wrong types, `p17` nesting/args, `p19` bool bounds, `p20` startswith/endswith window sweep, `p21` aliasing, `p22` slice receivers, `p23` NULs — **all same as CPython** except named refusals below.

**Fix confirmed:** `p6` on base differs (`not instance` vs CPython `not bytes`/`not bytearray`/`not Marker`); HEAD matches CPython on both builds. `p16c` confirms user-class members are fixed; builtin-function members remain different on base and HEAD.

**No-feature C:** `program.c` byte-identical base vs HEAD for `print("hello")` and `x.count("b")`.

**Tests:** `test_ail_fuzz43`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` on HEAD: 4/4 pass (`-j 2`). Manifest `--check` rc 0.

**Claims:** fix, records, manifest, 4-module run, bytes wrong-type messages, and documented non-ASCII lower/upper limit — verified. The report does not list the probe programs/results required by the self-check; that is the only process gap.

**Pre-existing (identical on base):** bytes `in` wrong-type text (`p15`: `argument should be integer or bytes-like object…` vs `a bytes-like object is required…`); builtin-function tuple member prints `function` vs `builtin_function_or_method` (`p16c`); general build refuses non-BMP literals (`p7`) and errors on `chr(non-BMP)` (`p14`); int64-min literal refused by general build (`p24`).

**Scope note:** the fixed bug is in `startswith`/`endswith` (string searching) rather than the parenthetical count/find/in/rindex/index examples; those examples already match CPython on base and HEAD (`p1`–`p5`, `p10`–`p11`, `p17`, `p21`–`p23`).

**Speed:** changed branch is error-only; no hot-path impact.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2945759, "input": 191172, "output": 14827, "reasoning": 32176, "cache.write": 0, "cache.read": 2707584}]

FINAL VERDICT: ACCEPT  2026-10-23T04:28:59Z
