# Type-mixing table: AIL vs CPython 3.12

Base commit: `3d4b600` (`HEAD`); date: 2026-11-05. 37 probes touching bool/int/float/str/None mixing, each run in four build modes. Binaries run under `ulimit -v 1500000` and `timeout 20`; runner wall time 187.3s.

Classes: `match` = same stdout and exit status, and same last stderr line on an error; `loud-stop` = AIL exits non-zero with a named error where CPython printed a value (e.g. beyond int64) or the same error with another text; `refused` = the build fails with a reason; `crash` = signal/timeout or no error line; `silent-wrong` = exit 0 or same exit, different stdout.

## Silent-wrong and crash first

(none)

## Full table

| program | typed | default | general | hybrid |
| --- | --- | --- | --- | --- |
| t01_bool_add.py | match | match | match | match |
| t02_bool_sum.py | refused | match | match | match |
| t03_bool_mul.py | match | match | match | match |
| t04_bool_index.py | refused | match | match | match |
| t05_bool_abs.py | match | match | match | match |
| t06_bool_format.py | refused | match | match | match |
| t07_bool_div.py | match | match | match | match |
| t08_bool_max.py | refused | match | match | match |
| t09_bool_isinstance.py | refused | match | match | match |
| t10_bool_arith_mix.py | match | match | match | match |
| t11_dict_bool_key.py | refused | match | match | match |
| t12_set_zero.py | refused | match | match | match |
| t13_hash_neg.py | refused | match | match | match |
| t14_dict_numeric_keys.py | refused | match | match | match |
| t15_big_int_float_eq.py | match | match | match | match |
| t16_big_int_float_lt.py | match | match | match | match |
| t17_int_1e300.py | loud-stop | loud-stop | loud-stop | match |
| t18_floor_neg_float.py | match | match | match | match |
| t19_mod_neg_float.py | match | match | match | match |
| t20_divmod_mixed.py | match | match | match | match |
| t21_round_half.py | match | match | match | match |
| t22_nan_eq.py | match | match | match | match |
| t23_sorted_mixed.py | refused | match | match | match |
| t24_int_float_compare.py | refused | refused | refused | match |
| t25_float_int_convert.py | match | match | match | match |
| t26_str_add_int.py | refused | match | match | match |
| t27_str_mul_bool.py | match | match | match | match |
| t28_str_lt_int.py | refused | match | match | match |
| t29_int_str_float.py | match | match | match | match |
| t30_float_str_underscore.py | match | match | match | match |
| t31_str_float_repr.py | match | match | match | match |
| t32_repr_neg_zero.py | match | match | match | match |
| t33_percent_format.py | refused | match | match | match |
| t34_str_int_eq.py | refused | match | match | match |
| t35_none_add.py | refused | match | match | match |
| t36_none_lt.py | refused | match | match | match |
| t37_none_index.py | refused | match | match | match |

## Totals

| class | typed | default | general | hybrid | all |
| --- | --- | --- | --- | --- | --- |
| match | 18 | 35 | 35 | 37 | 125 |
| loud-stop | 1 | 1 | 1 | 0 | 3 |
| refused | 18 | 1 | 1 | 0 | 20 |
| **all** | 37 | 37 | 37 | 37 | **148** |

## Follow-ups

Every `loud-stop`, `refused` and `silent-wrong`/`crash` cell follows, with a minimal repro. CPython's last stderr line is the oracle.

- `t02_bool_sum.py` / **typed**: refused. Build: `   write instead: build it in main() (`values: list[str] = [...]`) and pass it to the functions that read it as a parameter, or build it inside the one function that reads it`. Repro: `rm -rf /tmp/safetype1-t02_bool_sum-typed && python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/typemix/t02_bool_sum.py -o /tmp/safetype1-t02_bool_sum-typed --strict && (ulimit -v 1500000; timeout 20 /tmp/safetype1-t02_bool_sum-typed)`
- `t04_bool_index.py` / **typed**: refused. Build: `   write instead: split the statement into simple named steps with annotated types, using only constructs listed in AIL_REFERENCE.md`. Repro: `rm -rf /tmp/safetype1-t04_bool_index-typed && python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/typemix/t04_bool_index.py -o /tmp/safetype1-t04_bool_index-typed --strict && (ulimit -v 1500000; timeout 20 /tmp/safetype1-t04_bool_index-typed)`
- `t06_bool_format.py` / **typed**: refused. Build: `   write instead: split the statement into simple named steps with annotated types, using only constructs listed in AIL_REFERENCE.md`. Repro: `rm -rf /tmp/safetype1-t06_bool_format-typed && python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/typemix/t06_bool_format.py -o /tmp/safetype1-t06_bool_format-typed --strict && (ulimit -v 1500000; timeout 20 /tmp/safetype1-t06_bool_format-typed)`
- `t08_bool_max.py` / **typed**: refused. Build: `   write instead: split the statement into simple named steps with annotated types, using only constructs listed in AIL_REFERENCE.md`. Repro: `rm -rf /tmp/safetype1-t08_bool_max-typed && python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/typemix/t08_bool_max.py -o /tmp/safetype1-t08_bool_max-typed --strict && (ulimit -v 1500000; timeout 20 /tmp/safetype1-t08_bool_max-typed)`
- `t09_bool_isinstance.py` / **typed**: refused. Build: `   write instead: split the statement into simple named steps with annotated types, using only constructs listed in AIL_REFERENCE.md`. Repro: `rm -rf /tmp/safetype1-t09_bool_isinstance-typed && python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/typemix/t09_bool_isinstance.py -o /tmp/safetype1-t09_bool_isinstance-typed --strict && (ulimit -v 1500000; timeout 20 /tmp/safetype1-t09_bool_isinstance-typed)`
- `t11_dict_bool_key.py` / **typed**: refused. Build: `   write instead: split the statement into simple named steps with annotated types, using only constructs listed in AIL_REFERENCE.md`. Repro: `rm -rf /tmp/safetype1-t11_dict_bool_key-typed && python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/typemix/t11_dict_bool_key.py -o /tmp/safetype1-t11_dict_bool_key-typed --strict && (ulimit -v 1500000; timeout 20 /tmp/safetype1-t11_dict_bool_key-typed)`
- `t12_set_zero.py` / **typed**: refused. Build: `   write instead: split the statement into simple named steps with annotated types, using only constructs listed in AIL_REFERENCE.md`. Repro: `rm -rf /tmp/safetype1-t12_set_zero-typed && python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/typemix/t12_set_zero.py -o /tmp/safetype1-t12_set_zero-typed --strict && (ulimit -v 1500000; timeout 20 /tmp/safetype1-t12_set_zero-typed)`
- `t13_hash_neg.py` / **typed**: refused. Build: `   write instead: split the statement into simple named steps with annotated types, using only constructs listed in AIL_REFERENCE.md`. Repro: `rm -rf /tmp/safetype1-t13_hash_neg-typed && python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/typemix/t13_hash_neg.py -o /tmp/safetype1-t13_hash_neg-typed --strict && (ulimit -v 1500000; timeout 20 /tmp/safetype1-t13_hash_neg-typed)`
- `t14_dict_numeric_keys.py` / **typed**: refused. Build: `   write instead: build it in main() (`d: dict[str, int] = {...}`) and pass it to the functions that read it as a parameter, or build it inside the one function that reads it`. Repro: `rm -rf /tmp/safetype1-t14_dict_numeric_keys-typed && python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/typemix/t14_dict_numeric_keys.py -o /tmp/safetype1-t14_dict_numeric_keys-typed --strict && (ulimit -v 1500000; timeout 20 /tmp/safetype1-t14_dict_numeric_keys-typed)`
- `t17_int_1e300.py` / **typed**: loud-stop. CPython: `(no stderr)` (exit 0). AIL: `OverflowError: integer overflow in int(float) (ints are 64-bit; --exact-int gives exact ints)` (exit 1).
  - stdout CPython: `small 3\nnegative -2\ntext 10000000000\nhuge 1000000000000000052504760255204420248704468581108159154915854115511802457988908195786371375080447864043704443832883878176942523235360430575644792184786706982848387200926575803737830233794788090059368953234970799945081119038967640880074652742780142494579258788820056842838115669472196386865459400540160\n`; AIL: `small 3\nnegative -2\ntext 10000000000\n`.
  - repro: `rm -rf /tmp/safetype1-t17_int_1e300-typed && python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/typemix/t17_int_1e300.py -o /tmp/safetype1-t17_int_1e300-typed --strict && (ulimit -v 1500000; timeout 20 /tmp/safetype1-t17_int_1e300-typed)`
- `t17_int_1e300.py` / **default**: loud-stop. CPython: `(no stderr)` (exit 0). AIL: `OverflowError: integer overflow in int(float) (ints are 64-bit; --exact-int gives exact ints)` (exit 1).
  - stdout CPython: `small 3\nnegative -2\ntext 10000000000\nhuge 1000000000000000052504760255204420248704468581108159154915854115511802457988908195786371375080447864043704443832883878176942523235360430575644792184786706982848387200926575803737830233794788090059368953234970799945081119038967640880074652742780142494579258788820056842838115669472196386865459400540160\n`; AIL: `small 3\nnegative -2\ntext 10000000000\n`.
  - repro: `rm -rf /tmp/safetype1-t17_int_1e300-default && python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/typemix/t17_int_1e300.py -o /tmp/safetype1-t17_int_1e300-default && (ulimit -v 1500000; timeout 20 /tmp/safetype1-t17_int_1e300-default)`
- `t17_int_1e300.py` / **general**: loud-stop. CPython: `(no stderr)` (exit 0). AIL: `OverflowError: integer overflow in int(float) (ints are 64-bit; --exact-int gives exact ints)` (exit 1).
  - stdout CPython: `small 3\nnegative -2\ntext 10000000000\nhuge 1000000000000000052504760255204420248704468581108159154915854115511802457988908195786371375080447864043704443832883878176942523235360430575644792184786706982848387200926575803737830233794788090059368953234970799945081119038967640880074652742780142494579258788820056842838115669472196386865459400540160\n`; AIL: `small 3\nnegative -2\ntext 10000000000\n`.
  - repro: `rm -rf /tmp/safetype1-t17_int_1e300-general && AIL_UNIFIED_FORCE=1 python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/typemix/t17_int_1e300.py -o /tmp/safetype1-t17_int_1e300-general && (ulimit -v 1500000; timeout 20 /tmp/safetype1-t17_int_1e300-general)`
- `t23_sorted_mixed.py` / **typed**: refused. Build: `   write instead: build it in main() (`values: list[str] = [...]`) and pass it to the functions that read it as a parameter, or build it inside the one function that reads it`. Repro: `rm -rf /tmp/safetype1-t23_sorted_mixed-typed && python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/typemix/t23_sorted_mixed.py -o /tmp/safetype1-t23_sorted_mixed-typed --strict && (ulimit -v 1500000; timeout 20 /tmp/safetype1-t23_sorted_mixed-typed)`
- `t24_int_float_compare.py` / **typed**: refused. Build: `  write instead: keep the value inside int64, or compile with --exact-int (or AIL_EXACT_INT=1) for exact big ints, about 20x slower`. Repro: `rm -rf /tmp/safetype1-t24_int_float_compare-typed && python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/typemix/t24_int_float_compare.py -o /tmp/safetype1-t24_int_float_compare-typed --strict && (ulimit -v 1500000; timeout 20 /tmp/safetype1-t24_int_float_compare-typed)`
- `t24_int_float_compare.py` / **default**: refused. Build: `  write instead: keep the value inside int64, or compile with --exact-int (or AIL_EXACT_INT=1) for exact big ints, about 20x slower`. Repro: `rm -rf /tmp/safetype1-t24_int_float_compare-default && python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/typemix/t24_int_float_compare.py -o /tmp/safetype1-t24_int_float_compare-default && (ulimit -v 1500000; timeout 20 /tmp/safetype1-t24_int_float_compare-default)`
- `t24_int_float_compare.py` / **general**: refused. Build: `  write instead: keep the value inside int64, or compile with --exact-int (or AIL_EXACT_INT=1) for exact big ints, about 20x slower`. Repro: `rm -rf /tmp/safetype1-t24_int_float_compare-general && AIL_UNIFIED_FORCE=1 python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/typemix/t24_int_float_compare.py -o /tmp/safetype1-t24_int_float_compare-general && (ulimit -v 1500000; timeout 20 /tmp/safetype1-t24_int_float_compare-general)`
- `t26_str_add_int.py` / **typed**: refused. Build: `   write instead: split the statement into simple named steps with annotated types, using only constructs listed in AIL_REFERENCE.md`. Repro: `rm -rf /tmp/safetype1-t26_str_add_int-typed && python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/typemix/t26_str_add_int.py -o /tmp/safetype1-t26_str_add_int-typed --strict && (ulimit -v 1500000; timeout 20 /tmp/safetype1-t26_str_add_int-typed)`
- `t28_str_lt_int.py` / **typed**: refused. Build: `   write instead: split the statement into simple named steps with annotated types, using only constructs listed in AIL_REFERENCE.md`. Repro: `rm -rf /tmp/safetype1-t28_str_lt_int-typed && python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/typemix/t28_str_lt_int.py -o /tmp/safetype1-t28_str_lt_int-typed --strict && (ulimit -v 1500000; timeout 20 /tmp/safetype1-t28_str_lt_int-typed)`
- `t33_percent_format.py` / **typed**: refused. Build: `   write instead: split the statement into simple named steps with annotated types, using only constructs listed in AIL_REFERENCE.md`. Repro: `rm -rf /tmp/safetype1-t33_percent_format-typed && python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/typemix/t33_percent_format.py -o /tmp/safetype1-t33_percent_format-typed --strict && (ulimit -v 1500000; timeout 20 /tmp/safetype1-t33_percent_format-typed)`
- `t34_str_int_eq.py` / **typed**: refused. Build: `   write instead: split the statement into simple named steps with annotated types, using only constructs listed in AIL_REFERENCE.md`. Repro: `rm -rf /tmp/safetype1-t34_str_int_eq-typed && python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/typemix/t34_str_int_eq.py -o /tmp/safetype1-t34_str_int_eq-typed --strict && (ulimit -v 1500000; timeout 20 /tmp/safetype1-t34_str_int_eq-typed)`
- `t35_none_add.py` / **typed**: refused. Build: `   write instead: split the statement into simple named steps with annotated types, using only constructs listed in AIL_REFERENCE.md`. Repro: `rm -rf /tmp/safetype1-t35_none_add-typed && python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/typemix/t35_none_add.py -o /tmp/safetype1-t35_none_add-typed --strict && (ulimit -v 1500000; timeout 20 /tmp/safetype1-t35_none_add-typed)`
- `t36_none_lt.py` / **typed**: refused. Build: `   write instead: split the statement into simple named steps with annotated types, using only constructs listed in AIL_REFERENCE.md`. Repro: `rm -rf /tmp/safetype1-t36_none_lt-typed && python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/typemix/t36_none_lt.py -o /tmp/safetype1-t36_none_lt-typed --strict && (ulimit -v 1500000; timeout 20 /tmp/safetype1-t36_none_lt-typed)`
- `t37_none_index.py` / **typed**: refused. Build: `   write instead: build it in main() (`values: list[str] = [...]`) and pass it to the functions that read it as a parameter, or build it inside the one function that reads it`. Repro: `rm -rf /tmp/safetype1-t37_none_index-typed && python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/typemix/t37_none_index.py -o /tmp/safetype1-t37_none_index-typed --strict && (ulimit -v 1500000; timeout 20 /tmp/safetype1-t37_none_index-typed)`
