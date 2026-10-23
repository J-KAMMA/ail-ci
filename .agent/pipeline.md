# job job-fuzz61-10231419  started 2026-10-23T05:20:06Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `8539818` on `job-fuzz61-10231419`.

**Fixed:** Run-time encoding names only knew a few spellings. Added every CPython alias of utf-8, ascii and latin-1 (e.g. `csascii`, `cp367`, `ibm367`, `csisolatin1`, `ibm819`, `utf8_ucs2`, `utf8_ucs4`) to `prelude_bytes.py` and `safetyrt.ENCODINGS`; literal spellings now build instead of being refused. Added `test_ail_fuzz61.py` and registered it.

**Probes** (`bash ~/tools/cmp.sh`, both builds):
- p1–p10: 7 same as CPython, 3 refused by name (non-BMP literal / nested class).
- a1 (dynamic alias matrix): differed before, same on both builds after.
- r1–r5 (aliases via variable/argument/list/attribute/dict, empty, huge, errors, wrong types): same on both builds.
- r6–r7: other, pre-existing differences listed below.

**Other differences seen, not fixed:**
- Dynamic names of codecs outside utf-8/ascii/latin-1 (`cp1252`, `utf-8-sig`, `utf-16`, `iso-8859-2`) raise `LookupError` where CPython succeeds; literal forms are refused by name.
- `b"".decode("unknown")` raises `LookupError`; CPython returns `b""` without looking up the codec.
- `UnicodeEncodeError`/`UnicodeDecodeError` lack `.encoding`, `.object`, `.start`, `.end`, `.reason`.
- Valid non-BMP decode hits an internal error; non-BMP literals are refused.

**Tests on final commit:** `test_ail_fuzz61`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 207s, 0 failed. `update_manifest.py --check` exit 0. Records files were absent in this export, so `DEVLOG.md` and `docs/spec/DIFFERENCES.md` were created.
[cost $0.0000, opencode tokens {"total": 6305390, "input": 306662, "output": 23051, "reasoning": 24061, "cache.write": 0, "cache.read": 5951616}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review of `8539818` (job-fuzz61-10231419)**

**Change summary.** Adds 30 CPython aliases for utf-8/ascii/latin-1 to `prelude_bytes._ail_b_codec` and `safetyrt.ENCODINGS`; adds `test_ail_fuzz61.py`; creates DEVLOG/DIFFERENCES records; manifest updated.

**Probes (my own, `/tmp/rprobes/p1–p17`, both builds via `cmp.sh`).**
- p1,p16: all 30 aliases via variable/list/attribute/dict/argument and all literal spellings — same as CPython on general and default builds.
- p2,p3,p10,p12–p15: literal/dynamic aliases, empty strings, wrong types, constructors, keyword args, bytearray, all 256 latin-1 bytes, lengths of non-ASCII encodings — same on both builds.
- p4,p8: named compile-time refusals (unsupported error handler / non-BMP literal) — acceptable.
- p5,p6,p7,p11: mutation during iteration, nesting, bytes literals, errors strict/ignore/replace — same on both builds.
- Base comparison: p1 fails on base with `LookupError` for new aliases and passes on HEAD; p9, p17 and r6/r7 are identical on base and HEAD.

**Report claims.**
- Runtime/literal aliases fixed: verified (p1/p2/p16).
- p1–p10: 7 same, 3 refused by name: verified by rerunning the worker's `/tmp/probes`.
- a1 differed before, same after: verified (base DIFF, HEAD same).
- r1–r5 same on both builds: verified.
- r6–r7 pre-existing: verified identical on base.
- `test_ail_fuzz61` + `test_ail_safetynet`: rerun on HEAD, 2 modules, 97s, 0 failed. Worker's `test_ail_files`/`test_ail_corpus_findings3` run not rerun by me (unverified).
- `update_manifest.py --check` exit 0: verified. Records files absent on base: verified.

**Pre-existing (identical on base, non-blocking).**
- Tab/colon-normalized names (`utf\t8`, `iso-8859-1:1987`) still raise `LookupError` (p9).
- Non-utf/ascii/latin-1 dynamic codecs raise `LookupError`; `b"".decode("bad")` raises; missing exception attributes (r6/r7).
- Non-BMP decode on the general path hits an internal error (p17).
- Non-feature C is unchanged: `--debug-dir` `program.c` identical to base for `g00_000` and `g05_012`.

**Speed.** `tools/icount` could not run (`perf_event_open: Permission denied`). The relevant gdev programs (`g22_016`, `g05_032`, `g21_026`) call encode/decode only a few times, so no hot-loop risk was evident from inspection.

No defect introduced by the change; the fixed case was a wrong `LookupError` rather than a silent output, but it is a correct, verified fix in the requested area.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1364477, "input": 103791, "output": 8801, "reasoning": 12589, "cache.write": 0, "cache.read": 1239296}]

FINAL VERDICT: ACCEPT  2026-10-23T05:59:25Z
