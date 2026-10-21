Committed on `job-docs1-10212003` (`8a5f64b`).

**Examples**
- All 16 runnable reference examples (`python` with `def main`, brace `fn main`) build and run. The doc test checks every stated output exactly.
- The 5 Python examples also match CPython 3.12: core card, Text I/O, Regex, Collections, Tuples. The native-library snippet at `AIL_REFERENCE_MORE.md:1067` is not standalone (both CPython and AIL fail on missing `ail_cbuf`/`ail_ffi`), so it was not counted.
- No runnable doc example was wrong.

**Claims fixed**
- `with` / `contextlib`, `with open(...)` + `f.write`, file modes/encodings.
- `Flag` / `IntFlag` (removed “refused”), including composition, membership, iteration, formatting.
- `@dataclass` inheritance on the general path.
- `re.subn` and function replacements now documented as general-path; lookaround already correct.
- `print(*xs)`, `Cls(*xs)`, `zip` in `for`, dict comprehensions, `isinstance`, `min`/`max(key=)`, scalar `int|None` / `float|None` / `str|None`.
- `print` of lists/tuples, `dict[str, Struct]` / `dict[str, list[T]]` general-path support, `str(b)` default build, file I/O; `partition` / `ljust` / `rjust` / `center` string methods.
- Refused table rows now distinguish typed path from default/general fallback; `csv` added to the core module list.

**Probe results**
- 41 probe logs: 29 matched CPython byte-for-byte, 10 were refused by name as documented, 1 was the documented 64-bit `OverflowError`, and 1 found a residual compiler bug.
- Representative matching probes: `with_user`, `with_ctx`, `with_open2`, `flag`, `flag_big`, `dataclass_inherit`, `re_look2`, `re_subn2`, `star_print`, `star_class`, `print_star_typed`, `zip_for`, `dict_comp`, `isinstance_types`, `min_key`, `fstring_nested`, `print_containers`, `struct_eq`, `optional_int/str/float/param`, `strings_more2`, `global_change`, `str_bytes`.
- Correctly refused: `star_f`/`star_call2` (ordinary `f(*xs)`), `re_multi` (multi-group findall / group split), `re_groups`, `with_dialect`, `context_exitstack`, `optional_bytes`/`optional_list`/`optional_more` on the typed path, `print_dict2` typed.
- Residual compiler bug found: `csv.writer.writerows` writes `None` as `"None"` (CPython writes an empty field); `writerow` is correct. Not fixed or newly documented, since this is a compiler issue.

**Records and tests**
- `docs/spec/DIFFERENCES.md` is absent from this export, so no new DISFFERENCES rows; added `DEVLOG.md` with today’s entry.
- Rebuilt the MORE index and refreshed/checked `MANIFEST.json`.
- Final commit tests, all green in 492 s: `test_ail_reference_examples`, `test_ail_modconst`, `test_ail_collections`, `test_ail_tuples`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_cov2`.
[cost $0.29, turns 118]
