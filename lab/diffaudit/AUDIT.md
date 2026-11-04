# diffaudit: re-check of open DIFFERENCES.md rows

Date: 2026-11-04. Base: `origin/integ` (`d6cd9ee`). Every probe is in `lab/diffaudit/`;
`python3 lab/diffaudit/audit.py --run` builds it in the default build and with
`AIL_UNIFIED_FORCE=1` (temp dir, `AIL_NO_CACHE=1`, 120 s timeout, `ulimit -v 1500000`)
and compares stdout and exit status with CPython 3.12.

## Findings: behaviour changed in another way

### `C?-job-pre90-10242040-2` (`chr()` / 16-bit strings)

Stays open: the forced build no longer dies with the row's 16-bit internal error,
it now stops with a named runtime limit. The default build matches.

```
probe lab/diffaudit/C__job_pre90_10242040_2.py:
    def to_code(n): return ord(chr(n))
    print(to_code(0x10000))

CPython 3.12          rc=0 stdout="65536\n"
default build/run     rc=0 stdout="65536\n"
forced build          rc=0 (compiled)
forced run            rc=3 stdout="" stderr="AIL limit: chr_non_bmp\n"
```

## Residual difference: a single-expression pipeline with `%` by zero

This is not the row's stated form. `C?-job-pre138-10250109-2` says `%` by zero
*inside a lambda* ends the process; its own lambda example now matches CPython in
both builds (see the verdict table), so the row is marked `fixed`. A bare
single-expression program `sum(1 % x for x in xs)` is still compiled as the fused
pipeline (`pymod` in `python/pkg-v12/pyfront.py`), where `pymod` calls `ail_die`,
so the tool exits 1 instead of raising a catchable `ZeroDivisionError`. No
DIFFERENCES row describes this bare program and the task does not allow adding
rows, so the difference is recorded here rather than as a row.

```
program: sum(1 % x for x in xs)
input.bin = 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00   (int64 1, 0)

CPython (oracle)      rc=0 stdout="caught\n"
default build/run     rc=1 stdout="" stderr="integer modulo by zero\n"
forced build          rc=3 stderr="not in the subset: general path explicitly requested\n"
```

## Owner to decide

`C?-job-pre116-10242227-1` is status `refused`, but the saved generator now builds lazily
and matches CPython on both builds (`caught integer modulo by zero`). Its status is left
`refused` as the task requires for refused rows; the owner may retire or rewrite it.

## The list (27 rows at base, statuses before the audit)

Counts: open=10, empty=0, refused=4, declared=13 (total 27).

| id | area | status |
| --- | --- | --- |
| C?-job-rbstd_math-11020651-5 | math / `gamma`, `lgamma`, `frexp`, `ldexp`, `ulp` | declared; `lab/stdlib/math/RESULTS.md` |
| C?-job-std_random-11011523-1 | random / coverage and int64 limit | declared (int64); `test_ail_std_random.py`, `lab/stdlib/random/RESULTS.md` |
| C?-job-cpyhyb1-11011403-1 | CPython hybrid / opt-in artifact | declared; `test_ail_cpython_hybrid.py`, `docs/design/CPYTHON_HYBRID.md` |
| stdtop-decimal-1 | decimal / what is built | declared; `test_ail_stdtop1.py` |
| stdtop-unicodedata-1 | unicodedata / category only | declared; `test_ail_stdtop2.py` |
| stdtop-ipaddress-1 | ipaddress / IPv4 only | declared; `test_ail_stdtop3.py` |
| stdtop-html-1 | html / escape only | declared; `test_ail_stdtop4.py` |
| C?-job-pre388-10280828-2 | `int()` / attribute-held list | open |
| C?-job-pre134-10250029-1 | `del` of a class name | refused |
| C?-job-pre90-10242040-1 | `chr()` / 16-bit strings | refused |
| C?-job-pre90-10242040-2 | `chr()` / 16-bit strings | open |
| C?-job-pre116-10251611-1 | generator expressions | open |
| C?-job-pre116-10242227-1 | generator expressions | refused |
| C?-job-pre138-10250109-2 | integer `%` by zero in a fused closure | open |
| C?-job-rbrbfuzz4-10262129-3 | dict iteration | open |
| C?-job-rbrbfuzz4-10262129-4 | dict construction | open |
| C?-job-rbrbfuzz4-10262129-5 | dict operators | open |
| C?-job-rbfuzz4-10240913-3 | dict iteration | open |
| C?-job-rbfuzz4-10240913-4 | dict construction | open |
| C?-job-rbfuzz4-10240913-5 | dict operators | open |
| C?-job-rbpre54-10270147-1 | round | refused |
| MODSYS-1 | modules / `__file__`, `__package__`, `__path__` | declared; `test_ail_modsys.py` |
| MODSYS-2 | modules / `try: import m / except ImportError:` | declared; `test_ail_modsys.py` |
| MODSYS-3 | modules / function-level imports of modules with effects | declared; `test_ail_modsys.py` |
| MODSYS-4 | modules / private names and the entry file | declared; `test_ail_modsys.py` |
| MODSYS-5 | modules / a module reached through a function or a name that has two meanings | declared; `test_ail_modsys.py` |
| MODSYS-6 | modules / conditions that guard an import | declared; `test_ail_modsys.py` |

On the final tree `audit.py` prints 23 rows (open=6, refused=4, declared=13): the four
`open` rows below prove `now-matches` in both builds and moved to `fixed`.

## Verdicts (20 probes)

| id | area | old status | verdict default | verdict forced | probe file |
| --- | --- | --- | --- | --- | --- |
| C?-job-rbstd_math-11020651-5 | math / `gamma`, `lgamma`, `frexp`, `ldexp`, `ulp` | declared; `lab/stdlib/math/RESULTS.md` | refused-as-said | refused-as-said | `lab/diffaudit/C__job_rbstd_math_11020651_5.py` |
| C?-job-std_random-11011523-1 | random / coverage and int64 limit | declared (int64); `test_ail_std_random.py`, `lab/stdlib/random/RESULTS.md` | still-differs | still-differs | `lab/diffaudit/C__job_std_random_11011523_1.py` |
| stdtop-decimal-1 | decimal / what is built | declared; `test_ail_stdtop1.py` | refused-as-said | refused-as-said | `lab/diffaudit/stdtop_decimal_1.py` |
| stdtop-unicodedata-1 | unicodedata / category only | declared; `test_ail_stdtop2.py` | refused-as-said | refused-as-said | `lab/diffaudit/stdtop_unicodedata_1.py` |
| stdtop-ipaddress-1 | ipaddress / IPv4 only | declared; `test_ail_stdtop3.py` | refused-as-said | refused-as-said | `lab/diffaudit/stdtop_ipaddress_1.py` |
| stdtop-html-1 | html / escape only | declared; `test_ail_stdtop4.py` | refused-as-said | refused-as-said | `lab/diffaudit/stdtop_html_1.py` |
| C?-job-pre388-10280828-2 | `int()` / attribute-held list | open | still-differs | still-differs | `lab/diffaudit/C__job_pre388_10280828_2.py` |
| C?-job-pre134-10250029-1 | `del` of a class name | refused | refused-as-said | refused-as-said | `lab/diffaudit/C__job_pre134_10250029_1.py` |
| C?-job-pre90-10242040-1 | `chr()` / 16-bit strings | refused | refused-as-said | refused-as-said | `lab/diffaudit/C__job_pre90_10242040_1.py` |
| C?-job-pre90-10242040-2 | `chr()` / 16-bit strings | open | now-matches | differs-otherwise | `lab/diffaudit/C__job_pre90_10242040_2.py` |
| C?-job-pre116-10251611-1 | generator expressions | open | now-matches | now-matches | `lab/diffaudit/C__job_pre116_10251611_1.py` |
| C?-job-pre116-10242227-1 | generator expressions | refused | now-matches | now-matches | `lab/diffaudit/C__job_pre116_10242227_1.py` |
| C?-job-pre138-10250109-2 | integer `%` by zero in a fused closure | open | now-matches | now-matches | `lab/diffaudit/C__job_pre138_10250109_2.py` |
| C?-job-rbrbfuzz4-10262129-3 | dict iteration | open | still-differs | still-differs | `lab/diffaudit/C__job_rbrbfuzz4_10262129_3.py` |
| C?-job-rbrbfuzz4-10262129-4 | dict construction | open | now-matches | now-matches | `lab/diffaudit/C__job_rbrbfuzz4_10262129_4.py` |
| C?-job-rbrbfuzz4-10262129-5 | dict operators | open | still-differs | still-differs | `lab/diffaudit/C__job_rbrbfuzz4_10262129_5.py` |
| C?-job-rbfuzz4-10240913-3 | dict iteration | open | still-differs | still-differs | `lab/diffaudit/C__job_rbfuzz4_10240913_3.py` |
| C?-job-rbfuzz4-10240913-4 | dict construction | open | now-matches | now-matches | `lab/diffaudit/C__job_rbfuzz4_10240913_4.py` |
| C?-job-rbfuzz4-10240913-5 | dict operators | open | still-differs | still-differs | `lab/diffaudit/C__job_rbfuzz4_10240913_5.py` |
| C?-job-rbpre54-10270147-1 | round | refused | refused-as-said | refused-as-said | `lab/diffaudit/C__job_rbpre54_10270147_1.py` |

Notes on the `still-differs` dict-operator rows: both builds print `iterator` for
`type(r).__name__` where CPython prints `dict_reversekeyiterator`, then print `next(r)`,
then stop at `d1 | d2` with `TypeError: unsupported operand type(s) for |: 'dict' and
'dict'` and exit 1; the `d1 |= d2` line is never reached. (The probe prints
`type(r).__name__`, then `next(r)`, then `d1 | d2`, then `d1 |= d2`.)

## Stale rows changed in DIFFERENCES.md

Four `open` rows proved `now-matches` in both builds; only their status cell changed:

| id | old status | new status |
| --- | --- | --- |
| C?-job-pre116-10251611-1 | open | fixed;lab/diffaudit/C__job_pre116_10251611_1.py |
| C?-job-pre138-10250109-2 | open | fixed;lab/diffaudit/C__job_pre138_10250109_2.py |
| C?-job-rbrbfuzz4-10262129-4 | open | fixed;lab/diffaudit/C__job_rbrbfuzz4_10262129_4.py |
| C?-job-rbfuzz4-10240913-4 | open | fixed;lab/diffaudit/C__job_rbfuzz4_10240913_4.py |

## Not audited (7 declared rows)

| id | area | reason |
| --- | --- | --- |
| C?-job-cpyhyb1-11011403-1 | CPython hybrid / opt-in artifact | opt-in `ail build --cpython` artifact; the audit builds with `compile`, so this row needs its own driver. |
| MODSYS-1 | modules / `__file__`, `__package__`, `__path__` | module `__file__`/`__package__`/`__path__` values need a multi-module build; no single-file probe shows the row. |
| MODSYS-2 | modules / `try: import m / except ImportError:` | guarded-import decision needs several modules and a missing/C-accelerator name; no single-file probe. |
| MODSYS-3 | modules / function-level imports of modules with effects | function-level import effects need two modules; no single-file probe. |
| MODSYS-4 | modules / private names and the entry file | entry-file re-import needs a package layout; no single-file probe. |
| MODSYS-5 | modules / a module reached through a function or a name that has two meanings | module value through a function needs two modules; no single-file probe. |
| MODSYS-6 | modules / conditions that guard an import | build-time import guard needs a platform/import condition and a module; no single-file probe. |

## Totals

- Rows listed at base: 27 (open 10, empty 0, refused 4, declared 13).
- Rows with a committed probe and a verdict: 20 (all 10 open, all 4 refused, 6 declared).
- `now-matches` in both builds: 5 (4 open rows marked fixed; 1 refused row in Owner to decide).
- `refused-as-said` in both builds: 8 (4 refused rows and 4 declared refusals).
- `still-differs` in both builds: 6 (pre388, both dict-iteration rows, both dict-operator rows, and the declared random row).
- `differs-otherwise`: 1 row (pre90 forced only).
- Known open differences after this audit: 6 open rows (pre388, pre90 forced-only, rbrbfuzz4-3, rbrbfuzz4-5, rbfuzz4-3, rbfuzz4-5).
- Residual difference outside any row: a bare single-expression pipeline `sum(1 % x for x in xs)` still exits 1 through `ail_die` instead of raising (see above).
