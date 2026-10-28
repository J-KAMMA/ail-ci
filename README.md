# ail-ci

CI mirror of the AIL compiler and its regression test suite.

AIL is a small statically typed language that compiles to C. This repository holds a snapshot of
the compiler (`AIL_CURRENT/`), its runtime, the language reference, and the test modules, so the
suite can run on GitHub Actions. Development happens elsewhere; this tree is updated by export.

## Running the tests

Requirements: Python 3.10 or newer and `gcc` on `PATH`.

```sh
python3 tools/par_check.py            # whole suite, 8 modules at a time
python3 tools/par_check.py -j 4 test_ail_list_ops test_ail_check   # selected modules
```

`par_check.py` first checks the SHA-256 pins in `AIL_CURRENT/MANIFEST.json`. After editing a
pinned file, refresh them with `python3 tools/update_manifest.py`.

The workflow in `.github/workflows/tests.yml` splits the module list into 20 shards and runs them in
parallel on `ubuntu-24.04`.

## Editor support

`tools/ail_lsp.py` is a small diagnostics-only Language Server Protocol server over stdio. Start it
with:

```sh
python3 tools/ail_lsp.py
```

Point your editor's LSP client at that command. It publishes `ail` diagnostics when a document is
opened, changed (full sync, debounced 500 ms) or saved, and clears them on close.

## License

No license file is included; all rights reserved unless stated otherwise.
