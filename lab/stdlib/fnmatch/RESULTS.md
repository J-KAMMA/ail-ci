# `fnmatch`: real programs against CPython 3.12

Compiler: `python3 AIL_CURRENT/ail_chatgpt.py compile X.py --syntax python` (default build).
`lab/stdlib/fnmatch` has 12 programs. All 12 build, and all 12 print exactly CPython's stdout with
CPython's exit status. Every one takes the general path (`AIL_UNIFIED_FORCE=1` builds the same
program); the fallback note is a pre-existing annotation inference limit in the injected prelude,
not a refusal, and it is identical for every program except `pattern_translation.py`:

> note: built on the general path (about 20x slower) because 'pat' is annotated str in the source, but
> the caller also supplies list; refusing rather than silently choosing one. write instead: make the
> annotation match what the callers pass, or convert at the call (`int(x)`, `float(x)`, `str(x)`);
> run with --strict to see why

`pattern_translation.py` instead names `'name'` (also annotated `str`, also supplied `bytes`).

| program | result | first refusal message | CPython stdout / exit |
| --- | --- | --- | --- |
| `release_assets.py` | general | none | same |
| `bytes_names.py` | general | none | same |
| `config_globs.py` | general | none | same |
| `pattern_translation.py` | general | none | same |
| `keyword_calls.py` | general | none | same |
| `class_matching.py` | general | none | same |
| `log_rotation.py` | general | none | same |
| `safe_match.py` | general | none | same |
| `case_variants.py` | general | none | same |
| `build_clean.py` | general | none | same |
| `translate_join.py` | general | none | same |
| `select_backups.py` | general | none | same |

Covered: `fnmatch`, `fnmatchcase`, `filter`, `translate`; module import and `from ... import ... as`;
positional and keyword arguments; aliases; str and bytes names/patterns; empty name, empty pattern,
`*`, `?`, character classes, ranges, negations, `[]]`, `[!]`, `[-a]`, `[a-]`, escaped characters;
`translate` output and joining translations with `|`; and the `TypeError`s for non-string names,
patterns and iterables (caught by the programs).

## Follow-ups

None: no program is refused, and there is no reason that needs a new feature. `fnmatch.fnmatch`
uses `os.path.normcase` only for the case normalisation CPython does on the running platform; on
Linux that is the identity, which is what these programs observe.
