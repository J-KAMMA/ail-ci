# Differences from CPython

This file records the AIL/CPython differences found by the fuzz jobs. Ids with `?` are placeholders
until the coordinator assigns the final number.

| id | status | difference |
|---|---|---|
| C?-job-fuzz14-10220830-1 | fixed | A slice read on the general path used `(value).i` for its bounds. CPython accepts None as an omitted bound and raises TypeError for non-integers; AIL turned `a[None:None]` into an empty slice and read a float/str bound as an int. Slice reads now convert bounds through `ail_op_getslice_obj`. |
| C?-job-fuzz14-10220830-2 | fixed | `list.index` / `tuple.index` start and stop, and the index of `list.insert` / `list.pop`, were read as `.i`. CPython accepts only ints for list.index (None is rejected with "slice indices must be integers or have an __index__ method") and uses its integer-conversion TypeError for insert/pop. The bounds now go through `ail_op_index_bound` / `ail_op_int_index`. |
