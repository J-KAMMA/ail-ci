# job job-nturl2path1-11060458  started 2026-11-05T20:01:49Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Summary:

**Result: 10/10 programs build and match CPython in both the default build and `AIL_UNIFIED_FORCE=1`** (was 0/10 refused).

- **Programs** — `lab/stdlib/nturl2path/`, 10 files, 11–17 lines each, covering every mandated `url2pathname`/`pathname2url` case, all `OSError` texts, and an 8-path round trip.
- **Module** — `AIL_CURRENT/stdlib/nturl2path.py` (230 lines), CPython 3.12's logic and error texts. Two compiler facts forced changes: urllib is typed-path only, so a top-level `import urllib.parse` still refuses the whole module under `AIL_UNIFIED_FORCE=1`; the module therefore carries `_quote`/`_unquote` with CPython's exact rules. Parameters are copied to locals because the typed path forbids rebinding them.
- **Differential check** — module vs `urllib.parse` / `nturl2path` on 91 path/URL inputs plus a codec corpus (bad escapes, overlongs, surrogates, 4-byte UTF-8, empty): 0 differences.
- **Test** — `AIL_CURRENT/test_ail_std_nturl2path.py`, registered via `tests.d/`; `python3 AIL_CURRENT/test_ail_std_nturl2path.py` → OK (2 tests, 72s). Manifest updated, `--check` passes.
- **Probes** — 4 in `/tmp/probes/` (argument, list index, attribute, dict value; errors; round trip); all matched CPython in both builds.
- **Required tests** — `test_ail_files` OK, `test_ail_corpus_findings3` OK, `test_ail_safetynet` OK (140s). Note: safetynet's `S4_generators_gc` produced truncated output under `ulimit -v 1500000` and passed without the cap — memory pressure, not a regression.
- Typed-only build (`AIL_NO_GENERAL=1`) is refused because it has no `ord()`; not required by the done-check and recorded in `RESULTS.md`.
- Not pushed (per the runner instruction), so the 20 CI shards were not run. `git diff --stat` vs the base shows only the named files plus the three manifest shards.
[commandcode stop=end_turn turns=62 out_tokens=47667]

## review 0
[model commandcode/deepseek-v4.1-flash]
I've completed the review. Final report:

## What the change really does

Adds `AIL_CURRENT/stdlib/nturl2path.py` (230 lines) as bundled AIL source: CPython 3.12's `url2pathname`/`pathname2url` logic with a home-grown `_quote`/`_unquote` (CPython's `urllib.parse` is typed-path-only and would refuse `AIL_UNIFIED_FORCE=1`), plus 10 lab programs, a RESULTS table and a registered test. No compiler/runtime file is touched — verified: `git diff work..HEAD` is pure addition of the named files + 3 manifest shards.

## Claims checked

| Claim | Status |
|---|---|
| 10/10 build and match CPython in default and `AIL_UNIFIED_FORCE=1` | **verified** — `test_ail_std_nturl2path` ok (111s); my own 134-case corpus probe matches both builds |
| 0/10 before; base refuses with `nturl2path.url2pathname (not yet published ...)` | **verified** on `/tmp/base2` |
| urllib is typed-path-only, hence the inline codec | **verified** (`urllib is built on the typed path only ...`) |
| typed-only build refused for `ord()` | **verified** (same message as report) |
| codec matches `urllib.parse`/`nturl2path`, 0 differences on 91 inputs + corpus | **verified by my own stronger test**: 4046 random/structured inputs through the module source, 0 differences except lone surrogates |
| manifest updated, `--check` passes | **verified**, rc=0 |
| test registered via `tests.d/` | **verified**, manifest entry present |
| 4 probes in `/tmp/probes/` all match | **verified**, 4/4 match in both builds |
| safetynet S4 truncation under `ulimit -v` | **unverified** (ran safetynet without the cap: pass, 168s) |

## Probes I wrote (`/tmp/rprobes/`)

- `p2_values` (arg, list item, dict value, attribute), `p7_alias` (from-import alias, list mutation, dict rebind), `p8_dynamic` (runtime-built URL/percent/path) — **match** both builds.
- `p3_edges` (empty, `"//"`, `"///C|/"`, `"C:"`, `":"`, `"\\\\?\\x"`, `"|"` → IndexError) and `p5_corpus` (30 URLs + 19 paths, all error texts) — **match**.
- `p12_big` (134-case mixed corpus incl. `%G2`, `%2G`, `%0a`, `%fF`, NUL/DEL, é/€/ÿ/ࠀ) — **match**.
- `p9_utf8` (`%C3`, `%E0%A0`, `%ED%A0%80`, `%C0%AF`, overlongs/4-byte) — matches **except** `%F0%9F%98%80` / `%F4%8F%BF%BF`: AIL stops with the named limit `AIL limit: chr_non_bmp` (exit 3) where CPython yields `'😀'` / `'\U0010ffff'`.
- `p1_surrogate` / `p6_chr` (lone `\ud800`): refused by name at compile time (`a surrogate string literal`, `chr() with the surrogate code point U+D800`), so the module's surrogate-vs-Python difference is unreachable.
- `p11_long` (8k-char paths) — match, ~8s total.
- `p4_nofeature` (no `nturl2path`): generated C byte-identical to `/tmp/base2` in both the typed and general builds.

## Not a defect (explained)

- `chr_non_bmp` is a pre-existing named 16-bit-runtime limit (`cruntime.py:19296`, covered by `test_ail_repre20`); the same value is already refused at compile time when written as a literal, and the base refused the whole import, so there is no regression and no silent wrong output. It does mean emoji-bearing percent escapes stop loudly on the general path, though the typed `urllib.parse.unquote` handles them.
- Speed: no hot code touched; C for non-importers is identical, so no icount run was needed.

## Tests run

`cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_std_nturl2path test_ail_safetynet` → `ok test_ail_std_nturl2path 111.3s`, `ok test_ail_safetynet 168.0s`, `0 failed`.

## Unverified

- The claimed `ulimit`-related S4 behaviour; CI shards (not pushed); the worker's exact 91-input differential script (my own fuzz substitutes for it).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=38 out_tokens=32929]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T21:46:31Z
