# DEVLOG

## 2026-10-23

- fuzz70: `assert cond, msg` now keeps the message object in `AssertionError.args` on the general
  path (`ail2x_raise_builtin`), so tuple/list/dict/None/custom messages match CPython's `str(e)`
  and `e.args`. A mixed-mode typed clone is no longer selected for a function that asserts, so a
  failed assert inside a helper is caught by the surrounding boxed `try`. Typed-only builds still
  refuse a tuple assert message by name. New coverage: `test_ail_fuzz70.py`.
