# Iteration-mutation table: AIL vs CPython 3.12

Base commit: `1612f5f` (`branch base`); date: 2026-11-05. Each program mutates a list, dict or set while iterating it, prints the visited items and the final container, and where CPython raises, lets the error escape through a `finally`. Binaries run under `ulimit -v 1500000` and `timeout 20`. No compiler file was changed.

Classes: `match` (same stdout, exit status and last stderr line), `loud-stop` (non-zero exit with a named error, text or name differs from CPython's), `silent-wrong` (different stdout, or exit 0 where CPython raised), `crash` (signal, timeout, or a non-zero exit with no error line), `refused` (build failed), `n/a` (mode not available).

## Silent-wrong and crash rows

### `18_sort_key_appends.py` / **default** / silent-wrong

- CPython: exit 1; stdout `final [1, 2, 3]\n`; last stderr `ValueError: list modified during sort`.
- AIL:     exit 0; stdout `final [1, 2, 3, 3, 1, 2]\n`; last stderr `(no stderr)`.

### `18_sort_key_appends.py` / **general** / silent-wrong

- CPython: exit 1; stdout `final [1, 2, 3]\n`; last stderr `ValueError: list modified during sort`.
- AIL:     exit 0; stdout `final [1, 2, 3, 3, 1, 2]\n`; last stderr `(no stderr)`.

### `25_dict_pop_readd.py` / **default** / silent-wrong

- CPython: exit 1; stdout `visited ['a', 'b']\nfinal {'a': 1, 'b': 2}\n`; last stderr `RuntimeError: dictionary keys changed during iteration`.
- AIL:     exit 0; stdout `visited ['a', 'a']\nfinal {'b': 2, 'a': 1}\n`; last stderr `(no stderr)`.

### `25_dict_pop_readd.py` / **general** / silent-wrong

- CPython: exit 1; stdout `visited ['a', 'b']\nfinal {'a': 1, 'b': 2}\n`; last stderr `RuntimeError: dictionary keys changed during iteration`.
- AIL:     exit 0; stdout `visited ['a', 'a']\nfinal {'b': 2, 'a': 1}\n`; last stderr `(no stderr)`.

### `26_set_add.py` / **typed** / silent-wrong

- CPython: exit 1; stdout `visited [1]\nfinal [1, 2, 3, 11]\n`; last stderr `RuntimeError: Set changed size during iteration`.
- AIL:     exit 0; stdout `visited [1, 2, 3, 11, 12, 13, 21, 22, 23, 31, 32, 33, 41, 42, 43, 51, 52, 53, 61, 62, 63, 71, 72, 73, 81, 82, 83, 91, 92, 93, 101, 102, 103, 111, 112, 113, 121, 122, 123, 131, 132, 133, 141, 142, 143, 151, 152, 153, 161, 162]\nfinal [1, 2, 3, 11, 12, 13, 21, 22, 23, 31, 32, 33, 41, 42, 43, 51, 52, 53, 61, 62, 63, 71, 72, 73, 81, 82, 83, 91, 92, 93, 101, 102, 103, 111, 112, 113, 121, 122, 123, 131, 132, 133, 141, 142, 143, 151, 152, 153, 161, 162, 163, 171, 172]\n`; last stderr `(no stderr)`.

### `26_set_add.py` / **default** / silent-wrong

- CPython: exit 1; stdout `visited [1]\nfinal [1, 2, 3, 11]\n`; last stderr `RuntimeError: Set changed size during iteration`.
- AIL:     exit 0; stdout `visited [1, 2, 3, 11, 12, 13, 21, 22, 23, 31, 32, 33, 41, 42, 43, 51, 52, 53, 61, 62, 63, 71, 72, 73, 81, 82, 83, 91, 92, 93, 101, 102, 103, 111, 112, 113, 121, 122, 123, 131, 132, 133, 141, 142, 143, 151, 152, 153, 161, 162]\nfinal [1, 2, 3, 11, 12, 13, 21, 22, 23, 31, 32, 33, 41, 42, 43, 51, 52, 53, 61, 62, 63, 71, 72, 73, 81, 82, 83, 91, 92, 93, 101, 102, 103, 111, 112, 113, 121, 122, 123, 131, 132, 133, 141, 142, 143, 151, 152, 153, 161, 162, 163, 171, 172]\n`; last stderr `(no stderr)`.

### `27_set_discard.py` / **typed** / silent-wrong

- CPython: exit 1; stdout `visited [1]\nfinal [2, 3, 4]\n`; last stderr `RuntimeError: Set changed size during iteration`.
- AIL:     exit 0; stdout `visited [1, 3]\nfinal [2, 4]\n`; last stderr `(no stderr)`.

### `27_set_discard.py` / **default** / silent-wrong

- CPython: exit 1; stdout `visited [1]\nfinal [2, 3, 4]\n`; last stderr `RuntimeError: Set changed size during iteration`.
- AIL:     exit 0; stdout `visited [1, 3]\nfinal [2, 4]\n`; last stderr `(no stderr)`.

## Other differences (loud-stop, refused)

- `05_list_del_index.py` / **typed**: refused at build: `05_list_del_index.py:7:9: not in the subset: 'xs' is a module-level constant; deleting from it would mutate it, which is not supported`.
- `06_list_clear.py` / **typed**: refused at build: `06_list_clear.py:5:5: not in the subset: xs.clear(): a list has no method 'clear' here (or not with these arguments).`.
- `07_list_slice_clear.py` / **typed**: refused at build: `07_list_slice_clear.py:5:5: not in the subset: Slice is not one of the expression shapes this compiler builds; it is refused by name rather than guessed at (SEMANTICS.md section 5)`.
- `12_list_zip.py` / **typed**: refused at build: `12_list_zip.py:4:1: not in the subset: a tuple target over a sequence (`for i, x in ...` is built for enumerate(xs), zip(a, b) and d.items() only).`.
- `14_list_saved_iter.py` / **typed**: refused at build: `14_list_saved_iter.py:2:1: not in the subset: call to iter(); this compiler builds only the builtins it names, and refuses the rest by name rather than guessing at one.`.
- `15_list_comprehension.py` / **typed**: refused at build: `   write instead: split the statement into simple named steps with annotated types, using only constructs listed in AIL_REFERENCE.md`.
- `16_list_genexp.py` / **typed**: refused at build: `   write instead: split the statement into simple named steps with annotated types, using only constructs listed in AIL_REFERENCE.md`.
- `17_sorted_key_appends.py` / **typed**: refused at build: `   write instead: split the statement into simple named steps with annotated types, using only constructs listed in AIL_REFERENCE.md`.
- `18_sort_key_appends.py` / **typed**: refused at build: `   write instead: split the statement into simple named steps with annotated types, using only constructs listed in AIL_REFERENCE.md`.
- `19_dict_add_key.py` / **typed**: refused at build: `19_dict_add_key.py:13:5: not in the subset: print() given a dict, not a number or a str.`.
- `20_dict_delete_key.py` / **typed**: refused at build: `20_dict_delete_key.py:1:1: not in the subset: 'd' is keyed by a str in one place and by something else in another; a dict or a set has one key kind throughout`.
- `21_dict_value_only.py` / **typed**: refused at build: `21_dict_value_only.py:1:1: not in the subset: 'd' is keyed by a str in one place and by something else in another; a dict or a set has one key kind throughout`.
- `22_dict_items_add.py` / **typed**: refused at build: `22_dict_items_add.py:9:9: not in the subset: 'k' is a str used where a number is needed; a str is not an int64 (a list, set or dict of numbers cannot hold it).`.
- `23_dict_keys_add.py` / **typed**: refused at build: `23_dict_keys_add.py:5:5: not in the subset: 'k' is an int and is being assigned a str; a local's kind is settled by its FIRST assignment and never changes afterwards -- give the second kind a different name, or use the value inline without binding it to one`.
- `24_dict_values_add.py` / **typed**: refused at build: `24_dict_values_add.py:13:5: not in the subset: print() given a dict, not a number or a str.`.
- `25_dict_pop_readd.py` / **typed**: refused at build: `25_dict_pop_readd.py:1:1: not in the subset: 'd' is keyed by a str in one place and by something else in another; a dict or a set has one key kind throughout`.
- `28_big_list_append.py` / **typed**: refused at build: `28_big_list_append.py:11:1: not in the subset: `visited[:5]` cannot be walked inline here; bind it to a name first: `part = visited[:5]` then walk `part` (`for x in part: ...`)`.

## Full table

| program | typed | default | general | hybrid |
| --- | --- | --- | --- | --- |
| 01_list_append_bounded.py | match | match | match | match |
| 02_list_remove_current.py | match | match | match | match |
| 03_list_pop0.py | match | match | match | match |
| 04_list_insert0.py | match | match | match | match |
| 05_list_del_index.py | refused | match | match | match |
| 06_list_clear.py | refused | match | match | match |
| 07_list_slice_clear.py | refused | match | match | match |
| 08_list_sort_midloop.py | match | match | match | match |
| 09_list_reverse_midloop.py | match | match | match | match |
| 10_list_extend_self.py | match | match | match | match |
| 11_list_enumerate.py | match | match | match | match |
| 12_list_zip.py | refused | match | match | match |
| 13_list_reversed.py | match | match | match | match |
| 14_list_saved_iter.py | refused | match | match | match |
| 15_list_comprehension.py | refused | match | match | match |
| 16_list_genexp.py | refused | match | match | match |
| 17_sorted_key_appends.py | refused | match | match | match |
| 18_sort_key_appends.py | refused | silent-wrong | silent-wrong | match |
| 19_dict_add_key.py | refused | match | match | match |
| 20_dict_delete_key.py | refused | match | match | match |
| 21_dict_value_only.py | refused | match | match | match |
| 22_dict_items_add.py | refused | match | match | match |
| 23_dict_keys_add.py | refused | match | match | match |
| 24_dict_values_add.py | refused | match | match | match |
| 25_dict_pop_readd.py | refused | silent-wrong | silent-wrong | match |
| 26_set_add.py | silent-wrong | silent-wrong | match | match |
| 27_set_discard.py | silent-wrong | silent-wrong | match | match |
| 28_big_list_append.py | refused | match | match | match |

## Totals

| class | cells |
| --- | --- |
| match | 87 |
| silent-wrong | 8 |
| refused | 17 |
| **all** | **112** |

28 programs x 4 modes = 112 cells.

## Notes

- `sorted(xs, key=f)` with `f` appending to `xs` does **not** raise in CPython 3.12 (`sorted` sorts a copy); probe 17 therefore matches. Only in-place `xs.sort(key=f)` raises `ValueError: list modified during sort` (probe 18).
- `d.pop(k); d[k] = v` on the current key raises `RuntimeError: dictionary keys changed during iteration` in CPython 3.12 only when the re-add moves the key: with two keys (probe 25) it does; with three keys the position is unchanged and it does not.
- The set probes 26 and 27 are `silent-wrong` on the default and typed paths: no `RuntimeError: Set changed size during iteration`, and iteration runs to the 50-step counter. The general path raises as CPython does.
- Probes 18 and 25 are `silent-wrong` on the default and general paths: no `ValueError: list modified during sort` for `list.sort(key=...)`, and no `RuntimeError: dictionary keys changed during iteration` on a key re-add.
- Every `silent-wrong` row above names its probe file and prints both outputs; that file is the minimal repro. This lane edits no compiler file.
