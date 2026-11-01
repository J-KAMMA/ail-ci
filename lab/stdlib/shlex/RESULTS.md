# `shlex` coverage results

Build command for every program:

```
python3 AIL_CURRENT/ail_chatgpt.py compile lab/stdlib/shlex/<program>.py --syntax python
```

The oracle is `python3 <program>.py` (CPython 3.12.3). Every listed program is compared by stdout
and exit code on the default build and on the forced general build (`AIL_UNIFIED_FORCE=1`); all
twelve agree on both.

Before the fix every program was refused at the import. The common first-refusal prefix `P` was:

```
not in the subset: import of 'shlex' is not available: this compiler builds only the modules it
models (math, sys, collections, itertools, functools, heapq, bisect, re, json) (the general path
could not build this program either); general path:
```

| program | default build | first refusal before the fix | CPython stdout + exit |
| --- | --- | --- | --- |
| `01_command_line.py` | general | `P shlex.split (not yet published in NAMES_library.json)` | same, exit 0 |
| `02_config_comments.py` | general | `P shlex.split (not yet published in NAMES_library.json)` | same, exit 0 |
| `03_non_posix.py` | general | `P shlex.split (not yet published in NAMES_library.json)` | same, exit 0 |
| `04_lexer_iteration.py` | general | `P shlex.shlex (not yet published in NAMES_library.json)` | same, exit 0 |
| `05_get_token.py` | general | `P shlex.shlex (not yet published in NAMES_library.json)` | same, exit 0 |
| `06_punctuation.py` | general | `P shlex.shlex (not yet published in NAMES_library.json)` | same, exit 0 |
| `07_wordchars.py` | general | `P shlex.shlex (not yet published in NAMES_library.json)` | same, exit 0 |
| `08_custom_delimiters.py` | general | `P shlex.shlex (not yet published in NAMES_library.json)` | same, exit 0 |
| `09_errors.py` | general | `P shlex.split (not yet published in NAMES_library.json)` | same, exit 0 |
| `10_build_command.py` | general | `P shlex.join (not yet published in NAMES_library.json)` | same, exit 0 |
| `11_sources.py` | general | `P shlex.shlex (not yet published in NAMES_library.json)` | same, exit 0 |
| `12_shell_tokens.py` | general | `P shlex.shlex (not yet published in NAMES_library.json)` | same, exit 0 |

Result: **12 built, 0 typed, 0 refused** (9 required). The default build falls back to the general
path for every program because the shared bundled lexer still has a `__init__` default argument:

```
note: AIL_CURRENT/stdlib/shlex.py:90:5: built on the general path (about 20x slower) because
shlex.shlex.__init__ must take plain positional arguments, no defaults, *args or **kwargs;
run with --strict to see why
```

## What was fixed

`AIL_CURRENT/stdlib/shlex.py` was added as a bundled standard-library module, so `import shlex`
now resolves before the compiler treats an unknown library name as unavailable. It implements
`split`, `quote`, `join` and the `shlex` lexer class (attributes, `get_token`/`read_token`,
`push_token`, `push_source`/`pop_source`, `error_leader`, iteration, punctuation characters and
`ValueError` for an unclosed quotation or a trailing escape). The programs use those APIs only;
no program was changed to fit the compiler.

## Follow-ups (out of scope: a new typed-path feature)

* The typed path refuses **default arguments on methods** (`_check_plain_args` in
  `python/pkg-v12/pyfunc.py`). The public `shlex.shlex` constructor needs defaults
  (`instream=None, infile=None, posix=False, punctuation_chars=False`), so every program that
  imports the bundled module uses the general path. Exact fallback text is above. Allowing a
  method default would be a call-convention feature, not a shlex fix.
* POSIX `get_token()`/`read_token()`/`eof` at end of input is the empty string instead of
  CPython's `None`, because AIL has no `None` value for `str`. Iteration and `split()` still stop
  correctly, and an empty quoted token (`split("''")`) is distinct from end of file; a program
  that prints the `None` itself or compares an empty token to `lex.eof` would differ. Recorded in
  `DIFFERENCES.md`.
* The bundled lexer's `source` inclusion hook is not available in a single-file program, and
  `instream` is a string rather than a file object.
