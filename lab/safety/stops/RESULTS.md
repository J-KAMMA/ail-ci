# Runtime-stop table: AIL vs CPython 3.12

Base commit: `5c1c321fe` (`origin/integ`); date: 2026-11-06. Each program prints values and then raises one uncaught error. Binaries run under `ulimit -v 1500000` and `timeout 20`.

| program | typed | default | general | hybrid |
| --- | --- | --- | --- | --- |
| 01_zero_floor_text.py | match | match | match | match |
| 02_zero_mod.py | match | match | match | match |
| 03_zero_truediv_int.py | match | match | match | match |
| 04_zero_truediv_float.py | stop-differs | stop-differs | match | match |
| 05_zero_divmod.py | match | match | match | match |
| 06_rec_direct.py | match | match | match | match |
| 07_rec_mutual.py | match | match | match | match |
| 08_rec_method.py | match | match | match | match |
| 09_rec_deep5000.py | documented difference | documented difference | documented difference | match |
| 10_value_int_x.py | match | match | match | match |
| 11_value_int_empty.py | match | match | match | match |
| 12_value_float_abc.py | stop-differs | stop-differs | match | match |
| 13_value_chr_neg.py | match | match | match | match |
| 14_value_sqrt_neg.py | match | match | match | match |
| 15_value_log_zero.py | match | match | match | match |
| 16_overflow_int_inf.py | stop-differs | stop-differs | match | match |
| 17_value_int_nan.py | stop-differs | stop-differs | match | match |
| 18_unicode_decode.py | stop-differs | stop-differs | match | match |
| 19_stop_iteration.py | refused | match | match | match |
| 20_assert_message.py | match | match | match | match |

## Totals

| class | cells |
| --- | --- |
| match | 66 |
| stop-differs | 10 |
| documented difference | 3 |
| refused | 1 |
| **all** | **80** |

## Follow-ups

Every `crash`, `silent-wrong` and `stop-differs` cell follows. CPython's last line is the oracle.

- `04_zero_truediv_float.py` / **typed**: stop-differs. CPython: `ZeroDivisionError: float division by zero` (exit 1). AIL: `ZeroDivisionError: division by zero` (exit 1).
- `04_zero_truediv_float.py` / **default**: stop-differs. CPython: `ZeroDivisionError: float division by zero` (exit 1). AIL: `ZeroDivisionError: division by zero` (exit 1).
- `12_value_float_abc.py` / **typed**: stop-differs. CPython: `ValueError: could not convert string to float: 'abc'` (exit 1). AIL: `ValueError` (exit 1).
- `12_value_float_abc.py` / **default**: stop-differs. CPython: `ValueError: could not convert string to float: 'abc'` (exit 1). AIL: `ValueError` (exit 1).
- `16_overflow_int_inf.py` / **typed**: stop-differs. CPython: `OverflowError: cannot convert float infinity to integer` (exit 1). AIL: `cannot convert float infinity to integer` (exit 1).
- `16_overflow_int_inf.py` / **default**: stop-differs. CPython: `OverflowError: cannot convert float infinity to integer` (exit 1). AIL: `cannot convert float infinity to integer` (exit 1).
- `17_value_int_nan.py` / **typed**: stop-differs. CPython: `ValueError: cannot convert float NaN to integer` (exit 1). AIL: `ValueError` (exit 1).
- `17_value_int_nan.py` / **default**: stop-differs. CPython: `ValueError: cannot convert float NaN to integer` (exit 1). AIL: `ValueError` (exit 1).
- `18_unicode_decode.py` / **typed**: stop-differs. CPython: `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 0: invalid start byte` (exit 1). AIL: `bytes are not valid UTF-8` (exit 1).
- `18_unicode_decode.py` / **default**: stop-differs. CPython: `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 0: invalid start byte` (exit 1). AIL: `bytes are not valid UTF-8` (exit 1).

## Documented differences

AIL runs recursion on the real C stack and does not emulate CPython's default limit of 1000 (owner decision 2026-11-05; `docs/LIMITATIONS.md`). The depth in these cells fits, so AIL prints its result where CPython refuses; only an actual stack exhaustion stops, and then with `RecursionError: maximum recursion depth exceeded`.

- `09_rec_deep5000.py` / **typed**: depth within the real stack (documented difference).
- `09_rec_deep5000.py` / **default**: depth within the real stack (documented difference).
- `09_rec_deep5000.py` / **general**: depth within the real stack (documented difference).
