# SBOM coverage, measured

Measured 2026-11-08 on the staging base `4aa2626` (`origin/integ` with ffrepro1 merged) using
`tools/sbom.py`. The tool writes CycloneDX 1.5 JSON and `--check` compares it with
`readelf -d`, the link line recorded in `native_report.json`, the bundled sources visible in
the generated C, and the nearest `Cargo.lock`.

## Corpus and result

The compare-lab AIL source is `typed.py` (the `ail` column), not `main.py` (the CPython oracle).
All ten typed programs build in the default build; the four `main.py` sources that use values
outside int64 or CPython-only set ordering are refused by design and are not in this corpus.

| group | programs | built | `--check` with 0 missing and 0 extra |
| --- | ---: | ---: | ---: |
| `lab/compare/src/*/typed.py` | 10 | 10 | **10** |
| `examples/ffi/` (`zlib_check`, `libm_math`, `libc_text`, `sqlite_count`) | 4 | 4 | **4** |
| libcurl `urllib` request example | 1 | 1 | **1** |
| `examples/crate/*/main.py` | 7 | 7 | **7** |
| **total** | **22** | **22** | **22** |

There is no standalone libcurl example checked into the repository, so the urllib row used the
`urllib.request.urlopen` + `urllib.parse.quote` shape from `test_ail_http.py`, compiled from a
temporary source. It links `libcurl.so.4` and embeds `ailhttp_core.h` and `ailurl_core.h`.

Two more programs outside the target corpus were measured to exercise runtime headers and the
bundled zlib glue:

| program | result | components that matter |
| --- | --- | --- |
| `lab/stdlib/sqlite3/01_basic_crud.py` | 0 missing, 0 extra | `ailfile_core.h`, `ailsql_core.h`, `libsqlite3.so.0` |
| `import zlib` / `zlib.compress` probe | 0 missing, 0 extra | `zlib_glue.c`, `zlib_glue.h`, `libz.so.1` |

## Components seen

Across the 22 target binaries:

| kind | occurrences | names |
| --- | ---: | --- |
| shared library (`DT_NEEDED`) | 32 | `libc.so.6` 22, `ld-linux-x86-64.so.2` 3, `libgcc_s.so.1` 3, `libz.so.1` 1, `libm.so.6` 1, `libsqlite3.so.0` 1, `libcurl.so.4` 1 |
| bundled C source / header | 4 | `ailfile_core.h` 2, `ailhttp_core.h` 1, `ailurl_core.h` 1 |
| Rust crate from `Cargo.lock` | 8 | `bits`, `tinydep`, `fnvhash`, `rle`, `slugify`, `textstat`, `walk`, `wordbag` |

Every shared library that a Debian package owns got its package version from `dpkg-query`;
for example `libc6 2.39-0ubuntu8.9`, `zlib1g 1:1.3.dfsg-3.1ubuntu2.3`,
`libsqlite3-0 3.45.1-1ubuntu2.8`, `libcurl4t64 8.5.0-2ubuntu10.16`. Licences were filled in
where the package copyright named one (`LGPL-2.1-or-later` for libc, `Zlib` for zlib1g,
`public-domain` for sqlite3, `curl` for libcurl). Crates with a `license` field in their
manifest get that field; the example crates do not declare one.

The other cross-check lists (`link_missing`, `link_static_missing`, `bundled_missing`,
`bundled_extra`, `crate_missing`, `crate_extra`) were empty for every binary.

## Toolchain notes for this run

The runner had gcc 13.3.0 (`cc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0`) and Python 3.12, which
covers the C and urllib paths directly. Two pieces were supplied from the distribution's package
mirror without root:

* **Rust.** `rustup` had no toolchain. Ubuntu's `rustc`/`cargo` 1.75.0 packages were extracted
  under `/tmp`; the repository's `Cargo.lock` files are version 4, which 1.75 cannot read, so
  the seven crates were built from temporary copies with `version = 3` locks and their `out/`
  directories inside each crate tree. The repository sources and locks were not edited. The
  compare-lab toolchain pin is Rust 1.99.1, where the version-4 locks are read directly.
* **libcurl.** `curl/curl.h` was not installed. The `libcurl4-openssl-dev` package was
  extracted under `/tmp` and the urllib example was compiled with `CPATH` and `LIBRARY_PATH`
  pointing there; the executable still names the system `libcurl.so.4`.

Neither workaround changes an AIL file or the SBOM logic; they only supply a compiler or a
header that the measured CI image normally has.

## Limits

* Only the nearest `Cargo.lock` is read; all of its packages are listed, including a package a
  particular example does not call (Cargo resolved them as one workspace).
* Transitive dependencies of a shared library and libraries opened with `dlopen` are not in
  the BOM.
* Package names, versions and licences are best effort from `dpkg -S`, `dpkg-query` and
  `/usr/share/doc`; on a non-Debian host the component keeps its soname and still passes the
  `readelf` cross-check.
* There is no compiler `--sbom` flag yet; see `docs/SUPPLY_CHAIN.md` for the follow-up hook.
