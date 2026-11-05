# Releasing AIL

The AIL version has one source: `packaging/ail_lang/__init__.py`, `__version__`. Everything else
reads it: `pyproject.toml` declares `dynamic = ["version"]`,
`packaging/ail_wheel_backend.py` reads it for the wheel file name and `METADATA`, and
`ail --version` prints `ailc <version>`. Docs use placeholders such as `<version>` or
`<ail --version>`; the VS Code sample in `docs/LSP.md` states the current value, so the proof test
names that line too when a bump forgets it.

`packaging/WHEEL_REPORT.md` is a dated measurement. An old version there is historical, not a
current statement, and the test allows it only in that report.

## Version bump

1. Edit the one source, `packaging/ail_lang/__init__.py`: set `__version__ = "X.Y.Z"`. The
   proof below names any doc line that still states the old value; refresh it (today `docs/LSP.md`).
2. Run the proof: `python3 AIL_CURRENT/test_ail_version_consistency.py`.
   When packaging changes, also run `python3 AIL_CURRENT/test_ail_packaging.py` and
   `python3 AIL_CURRENT/test_ail_quickstart_docs.py`.
3. Refresh the manifest pins: `git add` the changed files, run
   `python3 tools/update_manifest.py`, then `python3 tools/update_manifest.py --check`.

## Tag and publish

Every tag and every publish waits for the owner. Do not tag, publish, merge, cancel runs, or change
repository settings.

## Follow-ups

None. `packaging/ail_lang/cli.py`, `packaging/ail_lang/lsp.py`,
`packaging/ail_wheel_backend.py` and `pyproject.toml` already read the single source; none needs a
line changed for a version bump.
