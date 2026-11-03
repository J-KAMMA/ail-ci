# csv_group

Read CSV from standard input and print the sum of the second column for every group in the
first column.

- The input is UTF-8 text. Each non-empty line has exactly two fields: `GROUP,VALUE`.
  `GROUP` is a non-empty name written in printable ASCII without a comma. `VALUE` is a decimal
  integer from 0 to 1000000000; leading zeros are allowed.
- Empty lines (including the empty piece after a final newline) are ignored. A final line
  without a terminating newline counts as a line.
- For every distinct group print one line `GROUP,SUM`, where `SUM` is the sum of its values.
  Groups are printed in ascending byte order of the group name.
- Empty input prints nothing. Exit status 0.

The performance input has 200000 rows.
