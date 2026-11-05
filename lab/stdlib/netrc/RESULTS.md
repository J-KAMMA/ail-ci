# netrc in compiled programs

Ten `lab/stdlib/netrc/` programs, each writing a netrc file in the current directory and
reading it back with `netrc.netrc(name)`. Build command (default):

    python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT

Comparison is stdout and exit status against `python3 -B` (3.12), in the default build and
with `AIL_UNIFIED_FORCE=1`.

## Before

There was no `AIL_CURRENT/stdlib/netrc.py`, so `import netrc` had no bundled module. Nine
programs refused at the `netrc.netrc` call; 08 refused first at the `except
netrc.NetrcParseError` clause. (With CPython's own `netrc.py` placed beside a program the
first refusal is instead `os.path.expanduser is not built`, which is the census line for
`netrc`.)

| # | Program | Result | First refusal line |
|---|---------|--------|--------------------|
| 01 | 01_basic_machine.py | refused | `p.py:8:1: not in the subset: netrc.netrc (not yet published in NAMES_library.json)` |
| 02 | 02_default_entry.py | refused | `p.py:9:1: not in the subset: netrc.netrc (not yet published in NAMES_library.json)` |
| 03 | 03_account_and_hosts.py | refused | `p.py:10:1: not in the subset: netrc.netrc (not yet published in NAMES_library.json)` |
| 04 | 04_macros.py | refused | `p.py:16:1: not in the subset: netrc.netrc (not yet published in NAMES_library.json)` |
| 05 | 05_comments.py | refused | `p.py:11:1: not in the subset: netrc.netrc (not yet published in NAMES_library.json)` |
| 06 | 06_quoted_tokens.py | refused | `p.py:7:1: not in the subset: netrc.netrc (not yet published in NAMES_library.json)` |
| 07 | 07_repr.py | refused | `p.py:9:1: not in the subset: netrc.netrc (not yet published in NAMES_library.json)` |
| 08 | 08_errors.py | refused | `p.py:7:5: not in the subset: a caught exception type Attribute (only builtin or user Exception subclasses are supported)` |
| 09 | 09_missing_file.py | refused | `p.py:4:5: not in the subset: netrc.netrc (not yet published in NAMES_library.json)` |
| 10 | 10_multiple_hosts.py | refused | `p.py:11:1: not in the subset: netrc.netrc (not yet published in NAMES_library.json)` |

Before: 0/10 typed or general (10/10 refused).

## After

With `AIL_CURRENT/stdlib/netrc.py`, every program builds on the general path (the module's
`NetrcParseError` is a user-defined exception subclass) and matches CPython.

| # | Program | Default build | `AIL_UNIFIED_FORCE=1` |
|---|---------|---------------|------------------------|
| 01 | 01_basic_machine.py | match | match |
| 02 | 02_default_entry.py | match | match |
| 03 | 03_account_and_hosts.py | match | match |
| 04 | 04_macros.py | match | match |
| 05 | 05_comments.py | match | match |
| 06 | 06_quoted_tokens.py | match | match |
| 07 | 07_repr.py | match | match |
| 08 | 08_errors.py | match | match |
| 09 | 09_missing_file.py | match | match |
| 10 | 10_multiple_hosts.py | match | match |

After: 10/10 in both builds.

`python3 AIL_CURRENT/test_ail_std_netrc.py` builds all ten in both builds, runs each in a
temporary directory and compares stdout and exit status with `python3`; it passes.

## Module differences from CPython 3.12

Only what the compiler refuses was rewritten; parsing, tokenizing, `authenticators`,
`__repr__` and `NetrcParseError.__str__` follow CPython.

- `_netrclex.get_token` uses explicit `while` loops instead of `iter(self._read_char, "")`:
  two-argument `iter` is not built.
- No `file=None` default-file branch: `os.path.expanduser`, `os.stat`, `os.fstat`,
  `os.getuid` and `pwd` are all refused. `netrc.netrc(None)` raises `OSError` with a clear
  message instead. No program uses the default file.
- The `UnicodeDecodeError` retry with `encoding="locale"` is dropped; only utf-8, ascii and
  latin-1 file encodings are built. All programs use ASCII.
- The unused `toplevel = tt = lexer.get_token()` chain became `tt = lexer.get_token()`
  (CPython never reads `toplevel`); the chained assignment with an unused first target was
  miscompiled on the general path and caused a spurious "bad toplevel token".

No program needed a compiler-file change.
