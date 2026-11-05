# Runtime-stop table: AIL vs CPython 3.12

Base commit: `03e5350` (`HEAD`); date: 2026-11-05. Each program prints values and then raises one uncaught error. Binaries run under `ulimit -v 1500000` and `timeout 20`.

| program | typed | default | general | hybrid |
| --- | --- | --- | --- | --- |
| 01_zero_floor_text.py | match | match | match | match |
| 02_zero_mod.py | match | match | match | match |
| 03_zero_truediv_int.py | match | match | match | match |
| 04_zero_truediv_float.py | stop-differs | stop-differs | match | match |
| 05_zero_divmod.py | match | match | match | match |
| 06_rec_direct.py | match | match | crash | match |
| 07_rec_mutual.py | match | match | crash | match |
| 08_rec_method.py | match | match | crash | match |
| 09_rec_deep5000.py | silent-wrong | silent-wrong | silent-wrong | match |
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
| match | 63 |
| stop-differs | 10 |
| silent-wrong | 3 |
| crash | 3 |
| refused | 1 |
| **all** | **80** |

## Follow-ups

Every `crash`, `silent-wrong` and `stop-differs` cell follows. CPython's last line is the oracle.

- `04_zero_truediv_float.py` / **typed**: stop-differs. CPython: `ZeroDivisionError: float division by zero` (exit 1). AIL: `ZeroDivisionError: division by zero` (exit 1).
- `04_zero_truediv_float.py` / **default**: stop-differs. CPython: `ZeroDivisionError: float division by zero` (exit 1). AIL: `ZeroDivisionError: division by zero` (exit 1).
- `06_rec_direct.py` / **general**: crash. CPython: `RecursionError: maximum recursion depth exceeded` (exit 1). AIL: `(no stderr)` (signal -11 (SIGSEGV)).
  - stdout CPython: `prefix 10\n`; AIL: ``.
- `07_rec_mutual.py` / **general**: crash. CPython: `RecursionError: maximum recursion depth exceeded` (exit 1). AIL: `(no stderr)` (signal -11 (SIGSEGV)).
  - stdout CPython: `prefix 10\n`; AIL: ``.
- `08_rec_method.py` / **general**: crash. CPython: `RecursionError: maximum recursion depth exceeded` (exit 1). AIL: `(no stderr)` (signal -11 (SIGSEGV)).
  - stdout CPython: `prefix 0\n`; AIL: ``.
- `09_rec_deep5000.py` / **typed**: silent-wrong. CPython: `RecursionError: maximum recursion depth exceeded` (exit 1). AIL: `(no stderr)` (exit 0).
  - stdout CPython: `prefix 0\n`; AIL: `prefix 0\nstart 0\nunreachable 1\n`.
- `09_rec_deep5000.py` / **default**: silent-wrong. CPython: `RecursionError: maximum recursion depth exceeded` (exit 1). AIL: `(no stderr)` (exit 0).
  - stdout CPython: `prefix 0\n`; AIL: `prefix 0\nstart 0\nunreachable 1\n`.
- `09_rec_deep5000.py` / **general**: silent-wrong. CPython: `RecursionError: maximum recursion depth exceeded` (exit 1). AIL: `(no stderr)` (exit 0).
  - stdout CPython: `prefix 0\n`; AIL: `prefix 0\nstart 0\nunreachable 1\n`.
- `12_value_float_abc.py` / **typed**: stop-differs. CPython: `ValueError: could not convert string to float: 'abc'` (exit 1). AIL: `ValueError` (exit 1).
- `12_value_float_abc.py` / **default**: stop-differs. CPython: `ValueError: could not convert string to float: 'abc'` (exit 1). AIL: `ValueError` (exit 1).
- `16_overflow_int_inf.py` / **typed**: stop-differs. CPython: `OverflowError: cannot convert float infinity to integer` (exit 1). AIL: `cannot convert float infinity to integer` (exit 1).
- `16_overflow_int_inf.py` / **default**: stop-differs. CPython: `OverflowError: cannot convert float infinity to integer` (exit 1). AIL: `cannot convert float infinity to integer` (exit 1).
- `17_value_int_nan.py` / **typed**: stop-differs. CPython: `ValueError: cannot convert float NaN to integer` (exit 1). AIL: `ValueError` (exit 1).
- `17_value_int_nan.py` / **default**: stop-differs. CPython: `ValueError: cannot convert float NaN to integer` (exit 1). AIL: `ValueError` (exit 1).
- `18_unicode_decode.py` / **typed**: stop-differs. CPython: `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 0: invalid start byte` (exit 1). AIL: `bytes are not valid UTF-8` (exit 1).
- `18_unicode_decode.py` / **default**: stop-differs. CPython: `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 0: invalid start byte` (exit 1). AIL: `bytes are not valid UTF-8` (exit 1).
