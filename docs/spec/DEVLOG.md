# Development log

## 2026-10-22 -- C169: list.index / tuple.index bounds

Closed C169.  The general path now evaluates a start/stop bound once, converts an instance through
`__index__`, and raises CPython 3.12's slice-index TypeError for `None`, floats, strs and other
non-index values (including `__index__` returning a non-int).  The same check covers list, tuple and
deque; str's own None-as-default behaviour is unchanged.  New tests: `AIL_CURRENT/test_ail_c169.py`.
