# log_scan

Read application log lines from standard input and report counts by status and by hour.

- Each non-empty line has the form `YYYY-MM-DD HH:MM:SS STATUS MESSAGE`. The date and time are
  exactly as shown. `STATUS` is one of `DEBUG`, `INFO`, `WARN`, `ERROR`. `MESSAGE` is the rest of
  the line and may contain spaces; it may be empty or absent. The hour is the two digits after
  the space in the time field (00 through 23).
- Every line in the input is a valid record. A final line without a terminating newline counts
  as a line.
- Print one `status STATUS COUNT` line for every status that occurs, sorted by `STATUS`
  ascending. Then print one `hour HH COUNT` line for every hour that occurs, sorted by the
  numeric hour ascending and formatted with two digits. Empty input prints nothing. Exit status 0.

The performance input has 500000 log lines.
