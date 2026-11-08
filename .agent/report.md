# job job-ffsbom1-11081519  started 2026-11-08T06:21:22Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Verified state:

**Deliverables (commits `3b9d968`, `4ca2331`)**
- `tools/sbom.py` — stdlib-only CycloneDX 1.5 emitter: ailc version+git commit, C compiler/version, each `DT_NEEDED` library with dpkg package/version/licence, bundled C sources and runtime headers with sha256, Cargo.lock crates with purl/checksum/licence, built-in `validate_bom`, plus `--check` cross-check.
- `docs/SUPPLY_CHAIN.md` — ships/links/SBOM/reproducibility (`tools/repro_check.py`) and what is not covered, including the follow-up `--sbom` hook.
- `lab/sbom/RESULTS.md`, `AIL_CURRENT/test_ail_sbom.py`, `AIL_CURRENT/tests.d/test_ail_sbom.txt`, manifest updated (`--check` passes).

**Verification (runner, gcc 13.3.0, Rust 1.99.1)**
- Corpus rebuilt and cross-checked: 10 compare-lab + 4 FFI + 1 urllib/libcurl + 7 crate examples = **22/22**, all eight check lists (`missing`, `extra`, `link_missing`, `link_static_missing`, `bundled_missing`, `bundled_extra`, `crate_missing`, `crate_extra`) empty.
- Checker is not vacuous: deleting `libc6`, `zlib_glue.c`, or the crates from real BOMs produced `missing`, `bundled_missing`, `crate_missing`; a bad `specVersion` was rejected.
- Required tests pass: `test_ail_sbom` 9/9, `test_ail_safetynet` 5/5, `test_ail_files` 18/18 (1 skip), `test_ail_corpus_findings3` 2/2.
- Probes: urllib build + SBOM (`libcurl.so.4`, `libc.so.6`, 3 runtime headers) clean; zlib stdlib (`zlib_glue.c/.h`, `libz.so.1`) clean; tamper probes as above.

**Not done:** no push (job rule "do not push"), so the 20 CI shards were not run. Nothing remained unidentified; no regressions found.
[commandcode stop=end_turn turns=38 out_tokens=18098]

## review 0
[model commandcode/deepseek-v4.1-flash]
## Review: ffsbom1 (SBOM tool + supply-chain page)

**What the change really does:** Adds `tools/sbom.py` (a CycloneDX 1.5 emitter plus a built-in `validate_bom` and a `--check` cross-check), `docs/SUPPLY_CHAIN.md`, `lab/sbom/RESULTS.md`, `AIL_CURRENT/test_ail_sbom.py` + `tests.d/` entry, and the two generated `manifest.d` lines. No compiler, runtime, or I/O file is touched, so generated C is unchanged. This matches the report.

**Probes** (`/tmp/rprobes`, `--debug-dir` on HEAD and on a `work` worktree)

| probe | result |
|---|---|
| `plain.py` (plain ints) | C byte-identical HEAD vs base; default+general match CPython; SBOM = libc6 only, no bundled files |
| `guardstr.py` (prints `AILFILE_CORE_H`, `zglue_deflate` literals) | no false components (string literals are emitted as byte arrays); matches CPython |
| `zbuf.py` (`import zlib`) | `zlib_glue.c`+`.h` + `libz.so.1`; eight lists empty, rc 0; matches CPython |
| `zffi.py` (`examples/ffi/zlib_check`) | `libz.so.1`+`libc.so.6`, no bundled; rc 0 |
| echo_pack/sqlite_count/libm_math/libc_text | BOM shared set == `readelf -d`; rc 0. libm_math correctly yields two components (both from libc6, distinct bom-refs) |
| sqlite_crud | `ailfile_core.h`+`ailsql_core.h` detected, exactly the guards embedded in `program.c` |
| proc/pathp/hashp | proc→ailfile+ailproc, hashp→ailhash, pathp→none; all match embedded guards |
| bits crate, copied in-tree | crates `bits`+`tinydep`, `link_static_missing` empty, rc 0 |
| bits crate, out-of-tree copy | crates `[]`, `link_static_missing=[libbits.a]`, rc 1 |
| static / empty / non-dpkg-lib / empty debug dir | static→0 components rc 0; empty file→BOM rc 0; `libfoo.so.1` listed by soname, no crash; missing `native_report.json` tolerated |
| `elf_needed` fallback, `SOURCE_DATE_EPOCH`, tamper | fallback == readelf; BOM byte-identical; removing libc6 → `missing`; `specVersion 1.4` rejected |

**Report claims**
- `sbom.py` stdlib emitter with the listed fields — **verified**, except the compiler version is a truncated package fragment (see note 1).
- `SUPPLY_CHAIN.md`, `RESULTS.md`, test, `tests.d`, manifest — **verified**; `update_manifest.py --check` rc 0, documented `repro_check.py -j 2 --filter` is a real option.
- 22/22 corpus, eight lists empty — **partially verified**: 4 FFI + echo_pack + bits-crate binaries reproduced clean; all 7 crate locks resolve as listed; urllib/libcurl row **unverified** (no `curl/curl.h` here).
- "Checker is not vacuous" — **verified** for tampered BOMs/libc6/`specVersion`; but see note 2.
- Tests: `test_ail_sbom` 9 ok, `test_ail_safetynet` 5 ok (par_check `-j 2`, 0 failed) — **verified**. `test_ail_files`/`corpus_findings3` **unverified** (out of review scope).
- No push / no CI shards — **true**.

**Pre-existing** (identical on base, not caused): `zbuf` generated C differs only in worktree-path-derived symbol hashes; `proc` general-path is a named refusal ("subprocess output or input as bytes … typed code only") on both HEAD and base.

**Notes (non-blocking)**
1. `metadata.tools[1].version` is `13.3.0-6ubuntu2` (truncated at `~`) and `vendor` is `""` for Ubuntu's `cc` banner; GCC's version is `13.3.0` and the raw banner is kept in `ail:compiler:banner`.
2. In `--check`, `missing/extra/bundled_*/crate_*` are recomputed with the same functions `build_bom` used, so they can never fire on the tool's own output; only `link_missing`/`link_static_missing` are independent. I verified the lists independently against `readelf`/embedded guards.
3. Out-of-tree crate builds lose the nearest `Cargo.lock` (no crates, rc 1) — loud, but not mentioned in the docs/RESULTS.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=39 out_tokens=47857]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-08T08:30:41Z
