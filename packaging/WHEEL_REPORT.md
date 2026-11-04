# ailc wheel report (pkgcheck1)

Date: 2026-11-04. Base branch: `job-pkgcheck1-11041238` (from `integ`).

## Baseline

`python3 tools/wheel_check.py`: **pass** (wheel built with `pip wheel`, fresh venv, installed, hello +
typed program matched CPython, 15 tutorial samples passed).

`python3 -m pip wheel . -w /tmp/whl --no-deps --no-build-isolation`:

| measure | before |
|---|---:|
| wheel bytes | 3,682,395 |
| wheel members | 567 |
| installed `ail_lang` bytes (`du -sb`) | 29,015,593 |
| installed files (incl. `__pycache__` from pip) | 764 |
| installed files without `__pycache__` | 561 / 13,747,838 bytes |

Biggest groups in the wheel (uncompressed bytes, files):

| bytes | files | group |
|---:|---:|---|
| 10,468,479 | 163 | `python/pkg-v12` |
| 1,354,010 | 24 | SDK root (`ail_chatgpt.py`, `ail_syntax.py`, ...) |
| 1,200,770 | 342 | `language_examples` |
| 531,074 | 15 | `python/pkg-v12/ir` |
| 130,875 | 8 | `python/pkg-v12/ir/passes` |
| 73,472 | 6 | `ailc-0.1.0.dev0.dist-info` |
| 40,258 | 5 | `ail_lang` command |
| 22,372 | 4 | `stdlib` |

20 biggest wheel files before (uncompressed / compressed):

```
 2381788  611008  ail_lang/sdk/python/pkg-v12/pyfunc.py
 1581650  391255  ail_lang/sdk/python/pkg-v12/cruntime.py
  730348  254966  ail_lang/sdk/python/pkg-v12/SEMANTICS.md
  727349  173612  ail_lang/sdk/python/pkg-v12/pyboxed2.py
  332066   71811  ail_lang/sdk/ail_chatgpt.py
  245983   55600  ail_lang/sdk/ail_syntax.py
  188010   42052  ail_lang/sdk/python/pkg-v12/ir/lower.py
  166044   41812  ail_lang/sdk/language_examples/binary_cursor_integer_price_linux_r457.baseline.c
  166044   41812  ail_lang/sdk/language_examples/binary_cursor_integer_price_linux_r457_marker.baseline.c
  166044   41812  ail_lang/sdk/language_examples/binary_cursor_integer_price_linux_r457_marker_final.baseline.c
  166044   41812  ail_lang/sdk/language_examples/binary_cursor_integer_price_linux_r457_warm.baseline.c
  164017   37782  ail_lang/sdk/ail_modules.py
  161129   39494  ail_lang/sdk/python/pkg-v12/unified.py
  155839   36611  ail_lang/sdk/python/pkg-v12/safetyrt.py
  146648   31757  ail_lang/sdk/python/pkg-v12/collib.py
  142742   34106  ail_lang/sdk/python/pkg-v12/pyboxed.py
  138323   30724  ail_lang/sdk/python/pkg-v12/dunders.py
  121204   28046  ail_lang/sdk/ail_ffi_lower.py
  110131   32295  ail_lang/sdk/python/pkg-v12/pyc.py
   95867   23983  ail_lang/sdk/python/pkg-v12/freestanding.py
```

## Same C from the installed wheel

`python3 tools/wheel_same_c.py` builds each program twice with `--syntax python --debug-dir` (checkout
`AIL_CURRENT/ail_chatgpt.py` vs the installed `ail_lang/sdk/ail_chatgpt.py`), each from a temporary copy,
`AIL_NO_CACHE=1`, `ulimit -v 1500000`, two at a time.

- 10 `lab/compare/src/*/main.py`
- first program (sorted) of each `lab/stdlib/<module>/` directory: 19 directories in this checkout

Result: **28/28** for the task's set (10 + 18) and **29/29** for every candidate (this checkout has 19
stdlib module directories, not 18). Every program had the same build exit code, byte-identical
`program.c`, and the same stdout/exit status of the built program. No missing wheel file was found, so
step 3 made no fix.

## Size: files left out of the wheel

Proved unused at run time with `git grep -n <name>` in `AIL_CURRENT/*.py` and
`AIL_CURRENT/python/pkg-v12/`: no reader outside the compiler's own tests/docs. Examples:

```
git grep -n -E '\.baseline\.c|_host\.c|_reference[^ ]*\.c' -- 'AIL_CURRENT/*.py' 'AIL_CURRENT/python/pkg-v12/*.py'
git grep -n -E "test_all\.py|test_pipeline\.py" -- 'AIL_CURRENT/*.py' 'AIL_CURRENT/python/pkg-v12/*.py'
```

The only hits are the test files' own docstrings, `SEMANTICS.md`, and `AIL_CURRENT/test_ail_build_cache.py`
(a test). Left out in `packaging/ail_wheel_backend.py` (`unused_sdk_file`, after the SDK export; the SDK
export and source tree are unchanged), and the wheel's SDK `MANIFEST.json` no longer pins them:

- `python/pkg-v12/test_all.py`, `python/pkg-v12/test_pipeline.py`
- 4 `language_examples/*.baseline.c` (664,176 bytes)
- 9 `language_examples/*_host.c` (49,562 bytes)
- 14 `language_examples/*_reference*.c` (62,925 bytes)

29 files, 835,869 uncompressed bytes (59,206 + 776,663).

| measure | before | after | change |
|---|---:|---:|---:|
| wheel bytes | 3,682,395 | 3,453,000 | -229,395 (-6.2%) |
| wheel members | 567 | 538 | -29 |
| installed `ail_lang` bytes (`du -sb`) | 29,015,593 | 28,105,773 | -909,820 |
| installed files (incl. `__pycache__`) | 764 | 733 | -31 |
| installed files without `__pycache__` | 13,747,838 / 561 | 12,906,797 / 532 | -841,041 / -29 |
| wheel uncompressed payload | 13,821,310 | 12,976,863 | -844,447 |

Biggest groups after:

| bytes | files | group |
|---:|---:|---|
| 10,409,273 | 161 | `python/pkg-v12` |
| 1,348,838 | 24 | SDK root |
| 531,074 | 15 | `python/pkg-v12/ir` |
| 424,107 | 315 | `language_examples` |
| 130,875 | 8 | `python/pkg-v12/ir/passes` |
| 70,066 | 6 | `ailc-0.1.0.dev0.dist-info` |
| 40,258 | 5 | `ail_lang` command |
| 22,372 | 4 | `stdlib` |

20 biggest wheel files after:

```
 2381788  611008  ail_lang/sdk/python/pkg-v12/pyfunc.py
 1581650  391255  ail_lang/sdk/python/pkg-v12/cruntime.py
  730348  254966  ail_lang/sdk/python/pkg-v12/SEMANTICS.md
  727349  173612  ail_lang/sdk/python/pkg-v12/pyboxed2.py
  332066   71811  ail_lang/sdk/ail_chatgpt.py
  245983   55600  ail_lang/sdk/ail_syntax.py
  188010   42052  ail_lang/sdk/python/pkg-v12/ir/lower.py
  164017   37782  ail_lang/sdk/ail_modules.py
  161129   39494  ail_lang/sdk/python/pkg-v12/unified.py
  155839   36611  ail_lang/sdk/python/pkg-v12/safetyrt.py
  146648   31757  ail_lang/sdk/python/pkg-v12/collib.py
  142742   34106  ail_lang/sdk/python/pkg-v12/pyboxed.py
  138323   30724  ail_lang/sdk/python/pkg-v12/dunders.py
  121204   28046  ail_lang/sdk/ail_ffi_lower.py
  110131   32295  ail_lang/sdk/python/pkg-v12/pyc.py
   95867   23983  ail_lang/sdk/python/pkg-v12/freestanding.py
   93834   19081  ail_lang/sdk/python/pkg-v12/prelude_genlib.py
   92967   21054  ail_lang/sdk/python/pkg-v12/ir/emit_c.py
   89010   19697  ail_lang/sdk/python/pkg-v12/optlib.py
   84142   22281  ail_lang/sdk/python/pkg-v12/gpu.py
```

After the removal: `python3 tools/wheel_same_c.py` still gives **29/29** and
`python3 tools/wheel_check.py` still passes. `test_ail_packaging.py` now checks that the left-out names are
absent from the wheel and runs `tools/wheel_check.py`.

## Checks run

- `python3 tools/wheel_check.py` before and after: pass.
- `python3 tools/wheel_same_c.py` before and after: 29/29.
- `python3 tools/par_check.py -j 2 test_ail_packaging test_ail_sdk`: 2 modules, 0 failed
  (`test_ail_packaging` 66.9s, `test_ail_sdk` 285.4s).
- `python3 tools/par_check.py -j 2 test_ail_safetynet test_ail_files test_ail_corpus_findings3`:
  3 modules, 0 failed.
- `python3 tools/update_manifest.py` then `--check`: clean.
