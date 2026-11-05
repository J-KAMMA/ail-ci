# Bounds-safety results

- Integ commit: `b3f2285`
- Date: 2026-11-05
- Oracle: CPython 3.12.3
- Programs: 24; modes: typed, default, general, hybrid; cells: 96
- Limits: `ulimit -v 1500000`, `timeout 20`; runner wall time 98.3s

Classification: `match` = stdout, exit status and last stderr line equal CPython; `stop-differs` = both stop nonzero, last stderr line differs; `silent-wrong` = one stops and the other does not, or stdout differs while CPython stops; `crash` = signal or timeout; `refused` = build refused.

| Program | typed | default | general | hybrid |
| --- | --- | --- | --- | --- |
| p01_list_read_len.py | match | match | match | match |
| p02_list_read_neg_len.py | match | match | match | match |
| p03_list_write_len.py | refused | stop-differs | stop-differs | match |
| p04_list_write_neg_len.py | refused | stop-differs | stop-differs | match |
| p05_grid_row.py | stop-differs | stop-differs | match | match |
| p06_grid_column.py | match | match | match | match |
| p07_str_huge_index.py | match | match | match | match |
| p08_bytes_huge_negative.py | stop-differs | stop-differs | match | match |
| p09_bytearray_index.py | refused | match | match | match |
| p10_tuple_index.py | stop-differs | stop-differs | match | match |
| p11_index_from_text.py | match | match | match | match |
| p12_while_off_by_one.py | match | match | match | match |
| p13_pop_empty.py | match | match | match | match |
| p14_pop_out_of_range.py | match | match | match | match |
| p15_del_out_of_range.py | refused | match | match | match |
| p16_class_field_list.py | match | match | match | match |
| p17_list_argument.py | match | match | match | match |
| p18_dict_missing_str.py | refused | match | match | match |
| p19_dict_missing_int.py | refused | match | match | match |
| p20_list_index_missing.py | match | match | match | match |
| p21_str_index_missing.py | stop-differs | stop-differs | match | match |
| p22_deque_pop_empty.py | refused | match | match | match |
| p23_heappop_empty.py | refused | match | match | match |
| p24_slice_out_of_range.py | refused | match | match | match |

## Totals

| Class | typed | default | general | hybrid | All |
| --- | --- | --- | --- | --- | --- |
| match | 11 | 18 | 22 | 24 | 75 |
| stop-differs | 4 | 6 | 2 | 0 | 12 |
| silent-wrong | 0 | 0 | 0 | 0 | 0 |
| crash | 0 | 0 | 0 | 0 | 0 |
| refused | 9 | 0 | 0 | 0 | 9 |
| **All cells** | 24 | 24 | 24 | 24 | **96** |

## Follow-ups

- `p03_list_write_len.py` (default): CPython last line 'IndexError: list assignment index out of range'; AIL exit 1: IndexError: list index out of range. Repro: `rm -rf /tmp/safebnd1-p03_list_write_len-default && python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/bounds/p03_list_write_len.py -o /tmp/safebnd1-p03_list_write_len-default && (ulimit -v 1500000; timeout 20 /tmp/safebnd1-p03_list_write_len-default)`
- `p03_list_write_len.py` (general): CPython last line 'IndexError: list assignment index out of range'; AIL exit 1: IndexError: list index out of range. Repro: `rm -rf /tmp/safebnd1-p03_list_write_len-general && AIL_UNIFIED_FORCE=1 python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/bounds/p03_list_write_len.py -o /tmp/safebnd1-p03_list_write_len-general && (ulimit -v 1500000; timeout 20 /tmp/safebnd1-p03_list_write_len-general)`
- `p04_list_write_neg_len.py` (default): CPython last line 'IndexError: list assignment index out of range'; AIL exit 1: IndexError: list index out of range. Repro: `rm -rf /tmp/safebnd1-p04_list_write_neg_len-default && python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/bounds/p04_list_write_neg_len.py -o /tmp/safebnd1-p04_list_write_neg_len-default && (ulimit -v 1500000; timeout 20 /tmp/safebnd1-p04_list_write_neg_len-default)`
- `p04_list_write_neg_len.py` (general): CPython last line 'IndexError: list assignment index out of range'; AIL exit 1: IndexError: list index out of range. Repro: `rm -rf /tmp/safebnd1-p04_list_write_neg_len-general && AIL_UNIFIED_FORCE=1 python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/bounds/p04_list_write_neg_len.py -o /tmp/safebnd1-p04_list_write_neg_len-general && (ulimit -v 1500000; timeout 20 /tmp/safebnd1-p04_list_write_neg_len-general)`
- `p05_grid_row.py` (typed): CPython last line 'IndexError: list index out of range'; AIL exit 1: IndexError. Repro: `rm -rf /tmp/safebnd1-p05_grid_row-typed && python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/bounds/p05_grid_row.py -o /tmp/safebnd1-p05_grid_row-typed --strict && (ulimit -v 1500000; timeout 20 /tmp/safebnd1-p05_grid_row-typed)`
- `p05_grid_row.py` (default): CPython last line 'IndexError: list index out of range'; AIL exit 1: IndexError. Repro: `rm -rf /tmp/safebnd1-p05_grid_row-default && python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/bounds/p05_grid_row.py -o /tmp/safebnd1-p05_grid_row-default && (ulimit -v 1500000; timeout 20 /tmp/safebnd1-p05_grid_row-default)`
- `p08_bytes_huge_negative.py` (typed): CPython last line 'IndexError: index out of range'; AIL exit 1: IndexError: bytes index out of range. Repro: `rm -rf /tmp/safebnd1-p08_bytes_huge_negative-typed && python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/bounds/p08_bytes_huge_negative.py -o /tmp/safebnd1-p08_bytes_huge_negative-typed --strict && (ulimit -v 1500000; timeout 20 /tmp/safebnd1-p08_bytes_huge_negative-typed)`
- `p08_bytes_huge_negative.py` (default): CPython last line 'IndexError: index out of range'; AIL exit 1: IndexError: bytes index out of range. Repro: `rm -rf /tmp/safebnd1-p08_bytes_huge_negative-default && python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/bounds/p08_bytes_huge_negative.py -o /tmp/safebnd1-p08_bytes_huge_negative-default && (ulimit -v 1500000; timeout 20 /tmp/safebnd1-p08_bytes_huge_negative-default)`
- `p10_tuple_index.py` (typed): CPython last line 'IndexError: tuple index out of range'; AIL exit 1: IndexError: list index out of range. Repro: `rm -rf /tmp/safebnd1-p10_tuple_index-typed && python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/bounds/p10_tuple_index.py -o /tmp/safebnd1-p10_tuple_index-typed --strict && (ulimit -v 1500000; timeout 20 /tmp/safebnd1-p10_tuple_index-typed)`
- `p10_tuple_index.py` (default): CPython last line 'IndexError: tuple index out of range'; AIL exit 1: IndexError: list index out of range. Repro: `rm -rf /tmp/safebnd1-p10_tuple_index-default && python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/bounds/p10_tuple_index.py -o /tmp/safebnd1-p10_tuple_index-default && (ulimit -v 1500000; timeout 20 /tmp/safebnd1-p10_tuple_index-default)`
- `p21_str_index_missing.py` (typed): CPython last line 'ValueError: substring not found'; AIL exit 1: ValueError. Repro: `rm -rf /tmp/safebnd1-p21_str_index_missing-typed && python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/bounds/p21_str_index_missing.py -o /tmp/safebnd1-p21_str_index_missing-typed --strict && (ulimit -v 1500000; timeout 20 /tmp/safebnd1-p21_str_index_missing-typed)`
- `p21_str_index_missing.py` (default): CPython last line 'ValueError: substring not found'; AIL exit 1: ValueError. Repro: `rm -rf /tmp/safebnd1-p21_str_index_missing-default && python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/safety/bounds/p21_str_index_missing.py -o /tmp/safebnd1-p21_str_index_missing-default && (ulimit -v 1500000; timeout 20 /tmp/safebnd1-p21_str_index_missing-default)`
