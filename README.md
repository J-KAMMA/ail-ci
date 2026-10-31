# ail-ci

CI mirror of the AIL compiler and its regression test suite.

AIL is a small statically typed language that compiles to C. This repository holds a snapshot of
the compiler (`AIL_CURRENT/`), its runtime, the language reference, and the test modules, so the
suite can run on GitHub Actions. Development happens elsewhere; this tree is updated by export.

New to AIL? Start with [docs/INSTALL.md](docs/INSTALL.md) (setup and a first compile), then
[docs/QUICKSTART.md](docs/QUICKSTART.md) (a 10-minute English tour with complete, tested programs)
or [docs/tutorial.md](docs/tutorial.md) (a 15-20 minute tutorial).

## Running the tests

Requirements: Python 3.10 or newer and `gcc` on `PATH`.

```sh
python3 tools/par_check.py            # whole suite, 8 modules at a time
python3 tools/par_check.py -j 4 test_ail_list_ops test_ail_check   # selected modules
```

`par_check.py` first checks the SHA-256 pins in `AIL_CURRENT/manifest.d/` (one `<sha256> <flags> <name>`
line per file, 256 small shard files; `MANIFEST.json` keeps only the provenance fields). After editing a
pinned file, or adding a new test, `git add` the new files and refresh the pins with
`python3 tools/update_manifest.py`; `python3 tools/update_manifest.py --check` is what CI runs.

**Adding a test module.** Create `AIL_CURRENT/test_<name>.py` and one registration file
`AIL_CURRENT/tests.d/test_<name>.txt` that contains the module name on one line (`#` lines are
comments). Do not edit the `LISTED_MODULES` tuple in `ail_check.py` and do not edit `MANIFEST.json`:
those shared lines were what made concurrent pull requests conflict. `ail_check.MODULES` is the
listed tuple followed by the `tests.d` modules sorted by name, so `par_check.py`, `tools/ci_shards.py`
and the CI shards all see the union.

**Merge conflicts in `manifest.d/`.** They happen only when two requests changed the very same file
(or neighbouring lines of one shard). Keep either side (or leave the markers), then run
`python3 tools/update_manifest.py`: it tolerates conflict markers and recomputes every pin from the files.

The workflow in `.github/workflows/tests.yml` splits the module list into 20 shards and runs them in
parallel on `ubuntu-24.04`.

## License

MIT OR Apache-2.0, at your option: see [LICENSE-MIT](LICENSE-MIT) and [LICENSE-APACHE](LICENSE-APACHE).
