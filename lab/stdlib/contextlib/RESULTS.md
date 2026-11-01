# contextlib: CPython 3.12 versus AIL

Twelve ordinary Python programs in this directory are the coverage set.  Each was built with the default
command (`ail_chatgpt.py compile X.py --syntax python`) and run against CPython 3.12; stdout and the exit
status were compared.

The default build takes every contextlib program on the general path: the typed front end does not model
`import contextlib`, so its fallback note is `import of 'contextlib' is not available ...`.  No contextlib
program is typed.  The ten programs below now build and print what CPython prints; the two redirect
programs are refused by name and are the follow-up.

## Results

| program | contextlib use | before | after |
| --- | --- | --- | --- |
| `chdir_context.py` | `chdir` | refused: `not in the subset: contextlib.chdir is not built: contextmanager, suppress, closing and nullcontext are built` | general, same stdout/exit |
| `closing_demo.py` | `closing` | general, same | general, same |
| `contextmanager_basic.py` | `@contextmanager`, `try/finally`, `return`/`break`/`continue` | general, same | general, same |
| `contextmanager_edges.py` | `@contextmanager` swallowing/replacing errors, `StopIteration`, empty yield | general, same | general, same |
| `contextmanager_methods.py` | `@contextmanager` on a method, nested managers | general, same | general, same |
| `custom_manager.py` | class `__enter__`/`__exit__`, `exc_type is/is in/issubclass`, `tb is None` | refused: `not in the subset: isinstance() against an unknown type ArithmeticError` | general, same stdout/exit |
| `exitstack_basic.py` | `ExitStack`, `enter_context`, `push`, `closing`, `nullcontext`, body error | refused: `not in the subset: contextlib.ExitStack is not built: contextmanager, suppress, closing and nullcontext are built` | general, same stdout/exit |
| `exitstack_nested.py` | nested/passed `ExitStack`, `pop_all`, LIFO close | refused: same `ExitStack` refusal | general, same stdout/exit |
| `nullcontext_demo.py` | `nullcontext()`, positional and `enter_result=` value | general, same | general, same |
| `suppress_errors.py` | `suppress()` / `suppress(A, B)`, nested, not-suppressed errors | general, same | general, same |
| `redirect_stderr_capture.py` | `redirect_stderr` + `io.StringIO` | refused: `not in the subset: contextlib.redirect_stderr is not built: contextmanager, suppress, closing and nullcontext are built` | refused (follow-up) |
| `redirect_stdout_capture.py` | `redirect_stdout` + `io.StringIO` | refused: `not in the subset: contextlib.redirect_stdout is not built: contextmanager, suppress, closing and nullcontext are built` | refused (follow-up) |

Before: 6 of 12 built.  After: 10 of 12 build, and every built program matches CPython's stdout and exit code.

## Fixes

1. **ExitStack (blocked 2 programs).** `prelude_with.py` now has `_AilExitStack`: `enter_context`, `push`
   (registers a manager's `__exit__` without entering it, as CPython 3.12 does), `callback` with up to two
   positional arguments, `pop_all`, `close`, `__enter__`/`__exit__`.  `__exit__` passes the active exception
   to manager exits, honours a true return (suppresses the rest of the stack) and keeps unwinding after a
   failing exit, like CPython.  `withlib.py` maps `ExitStack` (both the attribute and the from-import name)
   to the prelude class.
2. **chdir (blocked 1 program).** `_AilChdir` saves `_ail_os_getcwd()` in `__enter__`, calls
   `_ail_os_chdir(path)`, and restores the old directory in `__exit__`, including on an error.  A missing
   directory raises `FileNotFoundError` and leaves the old directory in place.
3. **`issubclass(exc_type, BuiltinException)` in `__exit__` (blocked 1 program).** `withlib.py` used
   `isinstance` for classes the boxed runtime has.  `ArithmeticError`, `LookupError` and `UnicodeError` are
   hierarchy names the runtime does not have; `prelude_bytes.py` also defines its own `UnicodeError` and
   `LookupError` classes, so `isinstance` against them was wrong.  Builtin exception names now go through
   `_ail_exc_is` and a name hierarchy in `prelude_with.py`; user exception classes still use `isinstance`.

## Follow-up (out of scope here)

`redirect_stdout` / `redirect_stderr` need dynamic redirection of the runtime's print stream (and
`sys.stderr.write`) into a Python stream object; that is a new output-stream feature, not a contextlib
mapping.  Their exact refusal text is:

```text
not in the subset: contextlib.redirect_stdout is not built: contextmanager, suppress, closing, nullcontext, ExitStack and chdir are built
not in the subset: contextlib.redirect_stderr is not built: contextmanager, suppress, closing, nullcontext, ExitStack and chdir are built
```

Known limits of the new ExitStack mapping: `callback` takes at most two positional arguments (no keyword
arguments) and `@stack.callback` as a decorator is not built; the programs and the new test use the common
positional forms.  These are declared in `DIFFERENCES.md` as `C?-job-std_contextlib-11011755-1`.
