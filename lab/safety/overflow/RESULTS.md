# int64 overflow safety across the builds

Date: 2026-11-05  
Base: `origin/integ` at `e92f5e9b`  
Generator: `python3 lab/safety/overflow/run.py` (every binary under `ulimit -v 1500000` and `timeout 20`)  
Oracle: CPython 3.12.3 from `python3 <program>.py`.

Ints are int64 by default and an overflow must stop loudly (owner decision 2026-10-31). A cell is `match` when stdout, the exit status and the last stderr line equal CPython's; `ovf-stop` when CPython prints a result and AIL exits 1 with an `OverflowError: integer overflow` last stderr line and nothing wrong on stdout first. `ovf-stop` counts as safe.

24 programs, 120 classified cells (0 cells `n/a`), generated in 339s.

## Summary

- unsafe cells: 0 `silent-wrong`, 0 `crash`, 0 `stop-differs`.
- `typed`: 1 `match`, 21 `ovf-stop`, 2 `refused`; `default`: 1 `match`, 23 `ovf-stop`; `general`: 1 `match`, 23 `ovf-stop`; `hybrid`: 24 `match`.
- `exact`: 19 `match`, 5 not `match` (`iadd_list.py`, `imul_class.py`, `imul_dict.py`, `int_neg_text.py`, `int_text.py`).

## Table

| program | typed | default | general | hybrid | exact |
|---|---|---|---|---|---|
| `abs_min.py` | ovf-stop | ovf-stop | ovf-stop | match | match |
| `add_max.py` | ovf-stop | ovf-stop | ovf-stop | match | match |
| `divmod_min.py` | refused | ovf-stop | ovf-stop | match | match |
| `factorial_prod.py` | ovf-stop | ovf-stop | ovf-stop | match | match |
| `fib93.py` | ovf-stop | ovf-stop | ovf-stop | match | match |
| `floordiv_min.py` | ovf-stop | ovf-stop | ovf-stop | match | match |
| `iadd_list.py` | ovf-stop | ovf-stop | ovf-stop | match | ovf-stop |
| `iadd_local.py` | ovf-stop | ovf-stop | ovf-stop | match | match |
| `imul_class.py` | ovf-stop | ovf-stop | ovf-stop | match | ovf-stop |
| `imul_dict.py` | ovf-stop | ovf-stop | ovf-stop | match | ovf-stop |
| `int_float.py` | ovf-stop | ovf-stop | ovf-stop | match | match |
| `int_neg_text.py` | ovf-stop | ovf-stop | ovf-stop | match | ovf-stop |
| `int_text.py` | ovf-stop | ovf-stop | ovf-stop | match | ovf-stop |
| `mod_min.py` | match | match | match | match | match |
| `mul_max.py` | ovf-stop | ovf-stop | ovf-stop | match | match |
| `neg_min.py` | ovf-stop | ovf-stop | ovf-stop | match | match |
| `pow_2_63.py` | ovf-stop | ovf-stop | ovf-stop | match | match |
| `pow_3_40.py` | refused | ovf-stop | ovf-stop | match | match |
| `round_float.py` | ovf-stop | ovf-stop | ovf-stop | match | match |
| `roundtrip.py` | ovf-stop | ovf-stop | ovf-stop | match | match |
| `shift_64.py` | ovf-stop | ovf-stop | ovf-stop | match | match |
| `shift_loop.py` | ovf-stop | ovf-stop | ovf-stop | match | match |
| `sub_min.py` | ovf-stop | ovf-stop | ovf-stop | match | match |
| `sum_big.py` | ovf-stop | ovf-stop | ovf-stop | match | match |

## Totals

| class | typed | default | general | hybrid | exact | total |
|---|---|---|---|---|---|---|
| `match` | 1 | 1 | 1 | 24 | 19 | 46 |
| `ovf-stop` | 21 | 23 | 23 | 0 | 5 | 72 |
| `refused` | 2 | 0 | 0 | 0 | 0 | 2 |
| **cells** | 24 | 24 | 24 | 24 | 24 | 120 |

## Cells that need a follow-up

Unsafe cells anywhere, plus every `exact` cell that is not `match`.

| program | mode | class | CPython | AIL |
|---|---|---|---|---|
| `divmod_min.py` | typed | `refused` | (exit 0, stdout '(3074457345618258602, 1)\n(-3074457345618258603, 1)\n(-4, 1)\n(9223372036854775808, 0)\n', last stderr '') | build refused: strict: 1 typed-path blocker; nothing was built (ranked by the code each one keeps off the typed path) / 1. divmod_min.py:6:5  blocks 8 lines (split, main) / code:          return divmod(a, b) / construct:     call to divmod() / why not typed: call to divmod(); this compiler builds only the builtins it names, and refuses the rest by name rather than guessing at one. / write instead: define `divmod` yourself with a `def` and call that, or use the builtin that does the job (len, sum, min, max, sorted, abs, range, int, float, str) |
| `iadd_list.py` | exact | `ovf-stop` | (exit 0, stdout '16 3\n4611686018427387904\n13835058055282163712\n', last stderr '') | (exit 1, stdout '16 3\n4611686018427387904\n', last stderr 'OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints)') |
| `imul_class.py` | exact | `ovf-stop` | (exit 0, stdout '16\n4611686018427387904\n9223372036854775808\n', last stderr '') | (exit 1, stdout '16\n4611686018427387904\n', last stderr 'OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints)') |
| `imul_dict.py` | exact | `ovf-stop` | (exit 0, stdout '16\n4611686018427387904\n9223372036854775808\n', last stderr '') | (exit 1, stdout '16\n4611686018427387904\n', last stderr 'OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints)') |
| `int_neg_text.py` | exact | `ovf-stop` | (exit 0, stdout '-922337203685477580\n-42\n-9223372036854775809\n', last stderr '') | (exit 1, stdout '-922337203685477580\n-42\n', last stderr 'OverflowError: integer overflow in a conversion to int64 (ints are 64-bit; --exact-int gives exact ints)') |
| `int_text.py` | exact | `ovf-stop` | (exit 0, stdout '1234567890123456789\n42\n99999999999999999999\n', last stderr '') | (exit 1, stdout '1234567890123456789\n42\n', last stderr 'OverflowError: integer overflow in a conversion to int64 (ints are 64-bit; --exact-int gives exact ints)') |
| `pow_3_40.py` | typed | `refused` | (exit 0, stdout '81\n4052555153018976267\n1\n12157665459056928801\n', last stderr '') | build refused: strict: 2 typed-path blockers; nothing was built (ranked by the code each one keeps off the typed path) / 1. pow_3_40.py:2:5  blocks 7 lines (power, main) / code:          return pow(base, exp) / construct:     call to pow() / why not typed: call to pow(); this compiler builds only the builtins it names, and refuses the rest by name rather than guessing at one. / write instead: define `pow` yourself with a `def` and call that, or use the builtin that does the job (len, sum, min, max, sorted, abs, range, int, float, str) / 2. pow_3_40.py  blocks 1 line / construct:     no def found / why not ty... |

## Follow-ups

Each cell below is a measurement the compiler owner must decide on; this suite never fixes the compiler.

- `iadd_list.py` / exact is `ovf-stop`: CPython exits 0 with stdout '16 3\n4611686018427387904\n13835058055282163712\n' and last stderr ''; AIL exits 1 with stdout '16 3\n4611686018427387904\n' and last stderr 'OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints)'. Repro: `python3 lab/safety/overflow/iadd_list.py` and `python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/overflow/iadd_list.py -o /tmp/ovf-out --exact-int`.
- `imul_class.py` / exact is `ovf-stop`: CPython exits 0 with stdout '16\n4611686018427387904\n9223372036854775808\n' and last stderr ''; AIL exits 1 with stdout '16\n4611686018427387904\n' and last stderr 'OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints)'. Repro: `python3 lab/safety/overflow/imul_class.py` and `python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/overflow/imul_class.py -o /tmp/ovf-out --exact-int`.
- `imul_dict.py` / exact is `ovf-stop`: CPython exits 0 with stdout '16\n4611686018427387904\n9223372036854775808\n' and last stderr ''; AIL exits 1 with stdout '16\n4611686018427387904\n' and last stderr 'OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints)'. Repro: `python3 lab/safety/overflow/imul_dict.py` and `python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/overflow/imul_dict.py -o /tmp/ovf-out --exact-int`.
- `int_neg_text.py` / exact is `ovf-stop`: CPython exits 0 with stdout '-922337203685477580\n-42\n-9223372036854775809\n' and last stderr ''; AIL exits 1 with stdout '-922337203685477580\n-42\n' and last stderr 'OverflowError: integer overflow in a conversion to int64 (ints are 64-bit; --exact-int gives exact ints)'. Repro: `python3 lab/safety/overflow/int_neg_text.py` and `python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/overflow/int_neg_text.py -o /tmp/ovf-out --exact-int`.
- `int_text.py` / exact is `ovf-stop`: CPython exits 0 with stdout '1234567890123456789\n42\n99999999999999999999\n' and last stderr ''; AIL exits 1 with stdout '1234567890123456789\n42\n' and last stderr 'OverflowError: integer overflow in a conversion to int64 (ints are 64-bit; --exact-int gives exact ints)'. Repro: `python3 lab/safety/overflow/int_text.py` and `python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/overflow/int_text.py -o /tmp/ovf-out --exact-int`.
