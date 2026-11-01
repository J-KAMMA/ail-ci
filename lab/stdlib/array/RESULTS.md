# array lab: build results

All twelve programs were built in the default mode (`python3 AIL_CURRENT/ail_chatgpt.py compile X.py
--syntax python`). The array prelude is Python source, so every build is on the general path; no
program reaches the typed path. Each built program was compared with CPython 3.12 (stdout and exit
status) on both `AIL_IR=0` and `AIL_IR=1`.

Initial: 7 build (all general), 5 refused. Final: 9 build (all general), 3 refused.

| Program | Initial result | First refusal | Final result |
|---|---|---|---|
| `audio_frames.py` | general | - | general |
| `binary_packets.py` | refused | `not in the subset: import of 'array' is not available ... general path: array.array (not yet published in NAMES_library.json)` | refused |
| `constructor_forms.py` | general | - | general |
| `error_edges.py` | general | - | general |
| `float32_readings.py` | refused | `not in the subset: import of 'array' is not available ... general path: array.array (not yet published in NAMES_library.json)` | refused |
| `histogram.py` | general | - | general |
| `inventory.py` | refused | `not in the subset: dunder method _AilArray.__delitem__; ... general path: index() called with too many positional arguments` | general |
| `matrix_rows.py` | refused | `not in the subset: iterating a _AilArray: its __iter__ is not \`return iter(...)\` or a generator ... general path: the method .fromlist() (on a instance:_AilArray)` | general |
| `ring_buffer.py` | general | - | general |
| `rolling_mean.py` | general | - | general |
| `sensor_compare.py` | general | - | general |
| `unicode_codes.py` | refused | `not in the subset: import of 'array' is not available ... general path: array.array (not yet published in NAMES_library.json)` | refused |

## Fix applied

The two blockers that were not big features were `array.index(x, start[, stop])` (the general path
rejected the extra positional arguments) and `array.fromlist()`. Both are now in
`python/pkg-v12/prelude_array.py`; `inventory.py` and `matrix_rows.py` build and match CPython.

The same prelude change rounded out CPython's sequence behaviour for the programs: slice reads
return an `array`; slice assignment accepts only a same-typecode `array` (an extended-slice length
mismatch says `attempt to assign array of size ...`); deletion accepts slices and integers;
`__getitem__`/`__setitem__`/`__delitem__` report CPython's `TypeError`/`IndexError` texts;
`remove`/`index` report `array.remove(x): x not in array` / `array.index(x): x not in array`;
`index(x, start[, stop])` treats an omitted bound differently from an explicit `None` or another
non-integer and raises CPython's `slice indices must be integers or have an __index__ method`;
`fromlist` requires a real list (a generator expression, even after AIL materialises it, raises
`arg must be list`); comparisons and `+`, `+=`, `*`, `*=`, `2 * a` follow CPython (including the
"can only append/extend ..." and same-typecode messages); and `array(...)` with keyword arguments
raises CPython's `TypeError("array.array() takes no keyword arguments")` at run time.

`test_ail_std_array.py` builds the nine passing programs in both `AIL_IR` modes and compares stdout
and exit status with CPython.

## Follow-ups (not fixed: each needs a new feature)

- `float32_readings.py` -- single-precision storage. The typed path refuses it by name with:
  `not in the subset: import of 'array' is not available ...` followed by
  `note: lab/stdlib/array/float32_readings.py:5: array typecode 'f' is not built (single precision and unicode arrays); use 'd' or an int type`.
  A correct `'f'` needs real float32 rounding and an `itemsize` of 4, not a `'d'` array with a new label.
- `unicode_codes.py` -- unicode elements. The typed path refuses it by name with:
  `not in the subset: import of 'array' is not available ...` followed by
  `note: lab/stdlib/array/unicode_codes.py:5: array typecode 'u' is not built (single precision and unicode arrays); use 'd' or an int type`.
- `binary_packets.py` -- byte views. The typed path refuses it by name with:
  `not in the subset: import of 'array' is not available ...` followed by
  `note: lab/stdlib/array/binary_packets.py:6: array.tobytes is not built: arrays are lists of numbers here (tolist(), extend, append, pop, insert, index, count, reverse, byteswap)`.
  `frombytes()` and `buffer_info()` are refused by the same rule and need a real byte buffer.

Comparisons with a non-array now name the actual operator in the error (`'<='`, `'>'`, `'>='`),
including when the array reaches the comparison through a function parameter, a list item, an
attribute or a dict value. Array-to-array ordering and all nine programs match.
