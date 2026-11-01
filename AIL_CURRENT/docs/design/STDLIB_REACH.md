# CPython stdlib reach (2026-11-01)

Census of the pure-Python modules of the CPython 3.12.3 installed on the build machine, and
the one refusal reason that blocked the most of them before this job (job
`job-stdlib2-11011233`). The change is in `python/pkg-v12/pyboxed2.py` and `python/pkg-v12/pyc.py`.

## Method

- Modules: `sys.stdlib_module_names`, keeping the names whose `importlib.util.find_spec` origin is a `.py` file. A top-level module is copied as `X.py`; a package is copied as its directory (`X/__init__.py` and the rest of the package). 176 top-level modules qualify (including packages such as `asyncio`, `json`, `email`, `tomllib` and `zoneinfo`).
- Program: `main.py` contains exactly `import X; print("ok")`. The copy sits beside it, so the import resolves to the copied file, as `cp X.py .` does in CPython.
- Builds: the default build (`python3 AIL_CURRENT/ail_chatgpt.py compile main.py --syntax python -o ...`) and the forced-general build (same with `AIL_UNIFIED_FORCE=1`). Both use `AIL_NO_CACHE=1`, `AIL_QUIET_FALLBACK=1`, a 180 s timeout and two concurrent modules.
- "Build" means exit 0 and an executable written. "Refuse" means a nonzero exit. The reason is the first diagnostic line of stderr/stdout after dropping the `file:line:col:` prefix and the leading `note:` lines, so it is the first refusal message the compiler prints.
- Counts below are by that reason text. A reason that quotes a module, name or number is one row only when the whole text is equal; `name 'os' is not defined` and `name 're' is not defined` are therefore different reasons.

## Summary

| build | before: build | before: refuse | after: build | after: refuse |
| --- | ---: | ---: | ---: | ---: |
| default | 14 | 162 | 14 | 162 |
| general | 14 | 162 | 14 | 162 |

The two builds agree on every module except `copy`, whose first refusal names a different
rebound import (`weakref` on the default build, `types` on the general build).

## The reason that blocked the most modules

Before the change the most common first reason on both builds was
`not in the subset: a generator expression used as a value.` (9 modules), ahead of the
5-module `io` group and the 4-module `os.path.normcase`, `os.stat` and caught-exception-
attribute groups. Those 9 modules were:

| module | before (both builds) | after: default | after: general |
| --- | --- | --- | --- |
| _weakrefset | _weakrefset.py:156:9: not in the subset: a generator expression used as a value. | not in the subset: `with` around a `yield`: closing the generator does not pass GeneratorExit to __exit__ (no… | not in the subset: `with` around a `yield`: closing the generator does not pass GeneratorExit to __exit__ (no… |
| calendar | calendar.py:417:13: not in the subset: a generator expression used as a value. | not in the subset: str.encode() with the error handler 'xmlcharrefreplace' on the general path (built: utf-8,… | not in the subset: str.encode() with the error handler 'xmlcharrefreplace' on the general path (built: utf-8,… |
| dataclasses | dataclasses.py:1366:9: not in the subset: a generator expression used as a value. | not in the subset: the decorator on def __repr__ (only @staticmethod on a method and @functools.lru_cache/@lr… | not in the subset: the decorator on def __repr__ (only @staticmethod on a method and @functools.lru_cache/@lr… |
| glob | glob.py:108:9: not in the subset: a generator expression used as a value. | not in the subset: `with` around a `yield`: closing the generator does not pass GeneratorExit to __exit__ (no… | not in the subset: `with` around a `yield`: closing the generator does not pass GeneratorExit to __exit__ (no… |
| socketserver | socketserver.py:670:9: not in the subset: a generator expression used as a value. | not in the subset: os.waitpid is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir… | not in the subset: os.waitpid is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir… |
| statistics | statistics.py:593:9: not in the subset: a generator expression used as a value. | not in the subset: the name 'type' is not a known function/class/builtin | not in the subset: the name 'type' is not a known function/class/builtin |
| tabnanny | tabnanny.py:272:5: not in the subset: a generator expression used as a value. | tabnanny.py:88:13: not in the subset: os.path.normcase is not built. Built: join exists isfile isdir islink l… | tabnanny.py:88:13: not in the subset: os.path.normcase is not built. Built: join exists isfile isdir islink l… |
| tomllib | not in the subset: a generator expression used as a value. | not in the subset: a required keyword-only parameter recursive in def set (this cut requires every keyword-on… | not in the subset: a required keyword-only parameter recursive in def set (this cut requires every keyword-on… |
| zoneinfo | zoneinfo/_zoneinfo.py:308:9: not in the subset: a generator expression used as a value. | zoneinfo/_zoneinfo.py:292:13: not in the subset: os used here is not built. Built: os.getcwd chdir listdir mk… | zoneinfo/_zoneinfo.py:292:13: not in the subset: os used here is not built. Built: os.getcwd chdir listdir mk… |

After the change the generator-expression reason appears 0 times on both builds. The nine
modules are still refused, but at the next blocker each one reaches (the last two columns),
so the total build count is unchanged: removing a first refusal does not remove every later
one. This is the honest reach result: the generator-expression gap is closed, not the whole
module surface.

### What was fixed

A generator expression used as a value is now lowered on the general path to a real
module-level generator function (`pyboxed2._lazy_genexp_functions`), so the outermost
iterable is evaluated at the call and the element body and its exceptions run at `next()`,
as in CPython. Free names of the enclosing function become arguments (the value they had
when the generator was made); module globals stay global. The default build routes a
program that contains such an expression straight to that path
(`pyc._saved_genexp_source`), so the typed path's old by-name refusal is not the reason
reported when the general path fails later. Only an expression whose body can raise needs the
new lowering (the old eager list lowering refused exactly those); a body that cannot raise
keeps its eager lowering, as before, so its observable creation-time side effects and captured
rebinding keep the pre-existing timing (that was not the refused reason). Keeping the eager
lowering also keeps the generated C of the ten `lab/compare` tasks byte-identical (checked on
every task and both builds that build).

Still refused by name: a generator expression directly in a class body, a nested generator
expression, a walrus inside one, a captured local rebound after creation (including a same-line
store and a nested function's `nonlocal` write), a captured local that may be unbound when the
generator is made, and a generator expression that calls a constructor of a class defined by the
program (moving that call into the generated function changed the general path's class
resolution). When `nestfn` would create the nested-function environment only after a saved
generator that reads a shared name, it leaves the function as written, so the compilers refuse
that lazy read by name instead of passing the old value. The diagnostics for those are unchanged
or name the narrower construct.

## Reasons after the change

The final reason table, both builds (they are identical except `copy`).

| id | count (default) | count (general) | first refusal message (without file:line:col) |
| --- | ---: | ---: | --- |
| R1 | 5 | 5 | not in the subset: io used here is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir rename replace getenv environ walk, os.sep linesep name curdir, and the os.path functions join exists isfile isdir islink getsize basename dirname split splitext abspath normpath isabs relpath |
| R2 | 5 | 5 | not in the subset: os.path.normcase is not built. Built: join exists isfile isdir islink lexists getsize basename dirname split splitext abspath normpath isabs relpath |
| R3 | 4 | 4 | not in the subset: `with` around a `yield`: closing the generator does not pass GeneratorExit to __exit__ (not built) |
| R4 | 4 | 4 | not in the subset: a caught exception type Attribute (only builtin or user Exception subclasses are supported) |
| R5 | 4 | 4 | not in the subset: os.stat is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir rename replace getenv environ walk, os.sep linesep name curdir, and os.path join exists isfile isdir islink getsize basename dirname split splitext abspath normpath isabs relpath |
| R6 | 3 | 3 | not in the subset: warnings.warn (not yet published in NAMES_library.json) |
| R7 | 2 | 2 | module 'zlib' used as a value (passed, stored or compared); this compiler needs a module to be named at each use. |
| R8 | 2 | 2 | not in the subset: a class-level constant built through a list item, attribute or dict value; write instead: bind the number as a module constant before the class |
| R9 | 2 | 2 | not in the subset: a constant integer expression overflows int64: its exact value is outside the signed 64-bit range and does not fit in a 64-bit signed integer (CPython computes it exactly because its int is unbounded, while this language's int is int64, SEMANTICS section 1). |
| R10 | 2 | 2 | not in the subset: os.environ.get(key) without a default returns None, and there is no None str. |
| R11 | 2 | 2 | not in the subset: os.system is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir rename replace getenv environ walk, os.sep linesep name curdir, and os.path join exists isfile isdir islink getsize basename dirname split splitext abspath normpath isabs relpath |
| R12 | 2 | 2 | not in the subset: str.encode() with the error handler 'backslashreplace' on the general path (built: utf-8, ascii, latin-1; errors strict, ignore, replace) |
| R13 | 2 | 2 | not in the subset: sys.stdin used as a plain value |
| R14 | 2 | 2 | not in the subset: the decorator on def __repr__ (only @staticmethod on a method and @functools.lru_cache/@lru_cache/@cache are supported) |
| R15 | 2 | 2 | not in the subset: urllib is built on the typed path only (bytes and the exception records are not on the general path). |
| R16 | 2 | 2 | not in the subset: warnings.catch_warnings (not yet published in NAMES_library.json) |
| R17 | 2 | 2 | one `import` statement mixes local modules and others; the compiler needs them apart. |
| R18 | 1 | 1 | 'FileIO' is imported and also assigned or defined again in _pyio.py; this compiler does not guess which binding a reader meant. |
| R19 | 1 | 1 | 'StrFormatter' is imported and also assigned or defined again in __init__.py; this compiler does not guess which binding a reader meant. |
| R20 | 1 | 1 | '_opcodes_all' is imported and also assigned or defined again in dis.py; this compiler does not guess which binding a reader meant. |
| R21 | 1 | 1 | '_thread' is imported and also assigned or defined again in threading.py; this compiler does not guess which binding a reader meant. |
| R22 | 1 | 0 | 'bz2' is imported and also assigned or defined again in shutil.py; this compiler does not guess which binding a reader meant. |
| R23 | 1 | 1 | 'collections' is bound to two different imports in typing.py. |
| R24 | 0 | 1 | 'contextvars' is imported and also assigned or defined again in _pydecimal.py; this compiler does not guess which binding a reader meant. |
| R25 | 1 | 1 | 'email' is bound to two different imports in mailbox.py. |
| R26 | 1 | 1 | 'email' is bound to two different imports in smtplib.py. |
| R27 | 1 | 1 | 'encodings' is bound to two different imports in locale.py. |
| R28 | 1 | 1 | 'importlib' is bound to two different imports in modulefinder.py. |
| R29 | 1 | 1 | 'importlib' is bound to two different imports in pkgutil.py. |
| R30 | 1 | 1 | 'importlib' is bound to two different imports in py_compile.py. |
| R31 | 1 | 1 | 'importlib' is bound to two different imports in pydoc.py. |
| R32 | 1 | 1 | 'os' is bound to two different imports in __init__.py. |
| R33 | 1 | 1 | 're' is imported and also assigned or defined again in _markupbase.py; this compiler does not guess which binding a reader meant. |
| R34 | 1 | 0 | 're' is imported and also assigned or defined again in _pydecimal.py; this compiler does not guess which binding a reader meant. |
| R35 | 1 | 1 | 'sys' is imported and also assigned or defined again in types.py; this compiler does not guess which binding a reader meant. |
| R36 | 1 | 1 | 'token' is imported and also assigned or defined again in tokenize.py; this compiler does not guess which binding a reader meant. |
| R37 | 0 | 1 | 'types' is imported and also assigned or defined again in copy.py; this compiler does not guess which binding a reader meant. |
| R38 | 1 | 0 | 'weakref' is imported and also assigned or defined again in copy.py; this compiler does not guess which binding a reader meant. |
| R39 | 0 | 1 | 'zlib' is imported and also assigned or defined again in shutil.py; this compiler does not guess which binding a reader meant. |
| R40 | 1 | 1 | __builtins__ is not available: the program is built into one executable, so a module has no loader, spec or cache file at run time. |
| R41 | 1 | 1 | __init__.py binds the name 'main' and unittest.main is also a submodule that the program imports: CPython's import of unittest.main stores the module over that attribute, so what unittest.main means depends on the order of the imports. |
| R42 | 1 | 1 | `from ctypes import *` in an import cycle: ctypes has not been read yet when _endian.py star-imports it. |
| R43 | 1 | 1 | `from sqlite3.dbapi2 import *`: dbapi2.py itself star-imports a standard-library module, so the names it exports are not known. |
| R44 | 1 | 1 | encodings.mbcs is read inside a function that is defined before the import that binds it: CPython raises AttributeError if the function runs first, and this compiler cannot tell when it runs. |
| R45 | 1 | 1 | import of '__main__' is not available: it is not part of the standard library and no module of that name is on the search path, so CPython stops here with ModuleNotFoundError. |
| R46 | 1 | 1 | import of a local module or package below the top level (inside a class body) is not supported: CPython runs it when that code runs, and the program is built before it runs. |
| R47 | 1 | 1 | import of the CPython C module '_collections' guarded by `except ImportError`: this compiler does not provide it, and the handler does not define _deque_iterator, so there is no Python fallback. |
| R48 | 1 | 1 | import of the CPython C module '_crypt' guarded by `except ImportError`: this compiler does not provide it, and the handler does not define _crypt, so there is no Python fallback. |
| R49 | 1 | 1 | import of the CPython C module '_opcode' guarded by `except ImportError`: this compiler does not provide it, and the handler does not define stack_effect, so there is no Python fallback. |
| R50 | 1 | 1 | import of the CPython C module '_pickle' guarded by `except ImportError`: this compiler does not provide it, and the handler does not define PickleBuffer, so there is no Python fallback. |
| R51 | 1 | 1 | import of the CPython C module '_ssl' guarded by `except ImportError`: this compiler does not provide it, and the handler does not define RAND_egd, so there is no Python fallback. |
| R52 | 1 | 1 | int64 constant expression out of range: 340282366920938463463374607431768211455 |
| R53 | 1 | 1 | int64 literal out of range: 18446744073709551615 |
| R54 | 1 | 1 | int64 literal out of range: 18446744073709551616 |
| R55 | 1 | 1 | module 'asyncio' has no top-level name 'DefaultEventLoopPolicy' (it defines: BaseEventLoop, Server, iscoroutine, iscoroutinefunction, sys). |
| R56 | 1 | 1 | module 'dbm.ndbm' used as a value (passed, stored or compared); this compiler needs a module to be named at each use. |
| R57 | 1 | 1 | module 'multiprocessing' has no top-level name 'AuthenticationError' (it defines: SUBDEBUG, SUBWARNING, context, sys). |
| R58 | 1 | 1 | module 're._constants' has no top-level name 'BRANCH' (it defines: ATCODES, AT_LOCALE, AT_MULTILINE, AT_UNICODE, CHCODES, CH_LOCALE, CH_UNICODE, MAGIC, MAXGROUPS, MAXREPEAT, OPCODES, OP_IGNORE, OP_LOCALE_IGNORE, OP_UNICODE_IGNORE, SRE_FLAG_ASCII, SRE_FLAG_DEBUG, SRE_FLAG_DOTALL, SRE_FLAG_IGNORECASE, SRE_FLAG_LOCALE, SRE_FLAG_MULTILINE, SRE_FLAG_TEMPLATE, SRE_FLAG_UNICODE, SRE_FLAG_VERBOSE, SRE_INFO_CHARSET, SRE_INFO_LITERAL, SRE_INFO_PREFIX, error). |
| R59 | 1 | 1 | module 'zlib' has no top-level name 'compressobj' (it defines: DEFLATED, DEF_BUF_SIZE, DEF_MEM_LEVEL, MAX_WBITS, Z_BEST_COMPRESSION, Z_BEST_SPEED, Z_BLOCK, Z_DEFAULT_COMPRESSION, Z_DEFAULT_STRATEGY, Z_FILTERED, Z_FINISH, Z_FIXED, Z_FULL_FLUSH, Z_HUFFMAN_ONLY, Z_NO_COMPRESSION, Z_NO_FLUSH, Z_PARTIAL_FLUSH, Z_RLE, Z_SYNC_FLUSH, Z_TREES, adler32, compress, crc32, decompress, ffi_put_3c1db0, ffi_widen_3c1db0, zglue_deflate, zglue_errmsg, zglue_inflate, zglue_size, zglue_take, zlib_adler32, zlib_crc32). |
| R60 | 1 | 1 | name 'email' is bound by an import in __init__.py and by another import in _adapters.py; this compiler keeps standard-library names unrenamed, so the two would collide. |
| R61 | 1 | 1 | not in the subset: .__dataclass_fields__: the table dataclass builds for a class is not modelled, so the read would fail at run time where CPython has it |
| R62 | 1 | 1 | not in the subset: __exit__ uses 'traceback' other than in `is None` / `is not None`; traceback objects are not modelled |
| R63 | 1 | 1 | not in the subset: _symtable.symtable (not yet published in NAMES_library.json) |
| R64 | 1 | 1 | not in the subset: `is` with a tuple constant (line 185, DIFFERENCES C175): CPython merges equal tuple constants of a code object (`a = (); b = (); a is b` is True; `()` is a singleton) and here each tuple display is a value of its own; compare with `==` |
| R65 | 1 | 1 | not in the subset: a default in method turtle.TNavigator.__init__ reads the class-body name DEFAULT_MODE; this path evaluates defaults at module scope, so it would read a different value (CPython evaluates the default in the class body) |
| R66 | 1 | 1 | not in the subset: a dict view kept in a name, field, item or container (`x = d.items()`, line 399): a view follows its dict in CPython, but here it is a snapshot, so it would show old contents and a loop over it would not raise "dictionary changed size during iteration"; call `d.items()` where it is used, or keep `list(d.items())` for a snapshot |
| R67 | 1 | 1 | not in the subset: a dict view kept in a name, field, item or container (`x = d.items()`, line 544): a view follows its dict in CPython, but here it is a snapshot, so it would show old contents and a loop over it would not raise "dictionary changed size during iteration"; call `d.items()` where it is used, or keep `list(d.items())` for a snapshot |
| R68 | 1 | 1 | not in the subset: a dict view kept in a name, field, item or container (`x = d.items()`, line 644): a view follows its dict in CPython, but here it is a snapshot, so it would show old contents and a loop over it would not raise "dictionary changed size during iteration"; call `d.items()` where it is used, or keep `list(d.items())` for a snapshot |
| R69 | 1 | 1 | not in the subset: a dict view kept in a name, field, item or container (`x = d.keys()`, line 91): a view follows its dict in CPython, but here it is a snapshot, so it would show old contents and a loop over it would not raise "dictionary changed size during iteration"; call `d.keys()` where it is used, or keep `list(d.keys())` for a snapshot |
| R70 | 1 | 1 | not in the subset: a dict view kept in a name, field, item or container (`x = d.values()`, line 2341): a view follows its dict in CPython, but here it is a snapshot, so it would show old contents and a loop over it would not raise "dictionary changed size during iteration"; call `d.values()` where it is used, or keep `list(d.values())` for a snapshot |
| R71 | 1 | 1 | not in the subset: a generator function in a program with threads (the general path runs a generator on a stack of its own, which the thread lock does not follow) |
| R72 | 1 | 1 | not in the subset: a non-BMP string literal in the 16-bit v2 runtime |
| R73 | 1 | 1 | not in the subset: a non-name base class in class fractions.Fraction |
| R74 | 1 | 1 | not in the subset: a non-name base class in class pyclbr._ModuleBrowser |
| R75 | 1 | 1 | not in the subset: a required keyword-only parameter append in def warnings._add_filter (this cut requires every keyword-only parameter to have a default) |
| R76 | 1 | 1 | not in the subset: a required keyword-only parameter recursive in def set (this cut requires every keyword-only parameter to have a default) |
| R77 | 1 | 1 | not in the subset: a starred (*args) call argument (only print(*xs), zip(*rows), and a call to a def f(*args) or a fixed-arity def with no defaults are modelled) |
| R78 | 1 | 1 | not in the subset: builtins.abs (not yet published in NAMES_library.json) |
| R79 | 1 | 1 | not in the subset: cancel() called without a required argument event |
| R80 | 1 | 1 | not in the subset: class _py_abc.ABCMeta bases on type, defined after it or unknown |
| R81 | 1 | 1 | not in the subset: class selectors._SelectorMapping bases on Mapping, defined after it or unknown |
| R82 | 1 | 1 | not in the subset: class traceback.StackSummary bases on list, defined after it or unknown |
| R83 | 1 | 1 | not in the subset: codeop.CommandCompiler (not yet published in NAMES_library.json) |
| R84 | 1 | 1 | not in the subset: constructing fileinput.FileInput: the class also stores an instance field named _readline holding a bound method, which this subset cannot build (CPython reads the method as a value) |
| R85 | 1 | 1 | not in the subset: datetime.date.fromisocalendar is not built on the general path (date.today(), date.fromtimestamp() and the class attributes min / max / resolution) |
| R86 | 1 | 1 | not in the subset: decimal.Decimal used as a plain value |
| R87 | 1 | 1 | not in the subset: import subprocess together with other modules on one line: write one import per line |
| R88 | 1 | 1 | not in the subset: import urllib at the top of the file, not inside a function or block |
| R89 | 1 | 1 | not in the subset: io.BytesIO used here is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir rename replace getenv environ walk, os.sep linesep name curdir, and the os.path functions join exists isfile isdir islink getsize basename dirname split splitext abspath normpath isabs relpath |
| R90 | 1 | 1 | not in the subset: isinstance() against an unknown type base64.bytes_types |
| R91 | 1 | 1 | not in the subset: isinstance() against an unknown type hmac._functype |
| R92 | 1 | 1 | not in the subset: name 'IGNBRK' is not defined |
| R93 | 1 | 1 | not in the subset: name 'WindowsError' is not defined |
| R94 | 1 | 1 | not in the subset: name 'b2a_qp' is not defined |
| R95 | 1 | 1 | not in the subset: name 'builtins' is not defined |
| R96 | 1 | 1 | not in the subset: name 'complex' is not defined |
| R97 | 1 | 1 | not in the subset: name 'float' is not defined |
| R98 | 1 | 1 | not in the subset: name 'int' is not defined |
| R99 | 1 | 1 | not in the subset: name 'os' is not defined |
| R100 | 1 | 1 | not in the subset: name 're' is not defined |
| R101 | 1 | 1 | not in the subset: open() with a mode that is not a string literal: the file kind (text or binary) has to be known when the program is built. |
| R102 | 1 | 1 | not in the subset: os used here is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir rename replace getenv environ walk, os.sep linesep name curdir, and the os.path functions join exists isfile isdir islink getsize basename dirname split splitext abspath normpath isabs relpath |
| R103 | 1 | 1 | not in the subset: os.PathLike used here is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir rename replace getenv environ walk, os.sep linesep name curdir, and the os.path functions join exists isfile isdir islink getsize basename dirname split splitext abspath normpath isabs relpath |
| R104 | 1 | 1 | not in the subset: os._get_exports_list is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir rename replace getenv environ walk, os.sep linesep name curdir, and os.path join exists isfile isdir islink getsize basename dirname split splitext abspath normpath isabs relpath |
| R105 | 1 | 1 | not in the subset: os.confstr is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir rename replace getenv environ walk, os.sep linesep name curdir, and os.path join exists isfile isdir islink getsize basename dirname split splitext abspath normpath isabs relpath |
| R106 | 1 | 1 | not in the subset: os.fdopen is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir rename replace getenv environ walk, os.sep linesep name curdir, and os.path join exists isfile isdir islink getsize basename dirname split splitext abspath normpath isabs relpath |
| R107 | 1 | 1 | not in the subset: os.fspath is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir rename replace getenv environ walk, os.sep linesep name curdir, and os.path join exists isfile isdir islink getsize basename dirname split splitext abspath normpath isabs relpath |
| R108 | 1 | 1 | not in the subset: os.lstat is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir rename replace getenv environ walk, os.sep linesep name curdir, and os.path join exists isfile isdir islink getsize basename dirname split splitext abspath normpath isabs relpath |
| R109 | 1 | 1 | not in the subset: os.open is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir rename replace getenv environ walk, os.sep linesep name curdir, and os.path join exists isfile isdir islink getsize basename dirname split splitext abspath normpath isabs relpath |
| R110 | 1 | 1 | not in the subset: os.openpty is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir rename replace getenv environ walk, os.sep linesep name curdir, and os.path join exists isfile isdir islink getsize basename dirname split splitext abspath normpath isabs relpath |
| R111 | 1 | 1 | not in the subset: os.path.expanduser is not built. Built: join exists isfile isdir islink lexists getsize basename dirname split splitext abspath normpath isabs relpath |
| R112 | 1 | 1 | not in the subset: os.popen is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir rename replace getenv environ walk, os.sep linesep name curdir, and os.path join exists isfile isdir islink getsize basename dirname split splitext abspath normpath isabs relpath |
| R113 | 1 | 1 | not in the subset: os.waitpid is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir rename replace getenv environ walk, os.sep linesep name curdir, and os.path join exists isfile isdir islink getsize basename dirname split splitext abspath normpath isabs relpath |
| R114 | 1 | 1 | not in the subset: reading the class attribute queue.Queue.__class_getitem__ through the class: its value is not a constant, and the general path can only read a class attribute through the class when it is an int/float/str/bytes/bool literal. |
| R115 | 1 | 1 | not in the subset: socket.getservbyname (not yet published in NAMES_library.json) |
| R116 | 1 | 1 | not in the subset: str() with the encoding 'raw-unicode-escape' on the general path (built: utf-8, ascii, latin-1; errors strict, ignore, replace) |
| R117 | 1 | 1 | not in the subset: str.encode() with the encoding 'unicode_escape' on the general path (built: utf-8, ascii, latin-1; errors strict, ignore, replace) |
| R118 | 1 | 1 | not in the subset: str.encode() with the error handler 'surrogateescape' on the general path (built: utf-8, ascii, latin-1; errors strict, ignore, replace) |
| R119 | 1 | 1 | not in the subset: str.encode() with the error handler 'xmlcharrefreplace' on the general path (built: utf-8, ascii, latin-1; errors strict, ignore, replace) |
| R120 | 1 | 1 | not in the subset: subprocess output or input as bytes: the general path has no bytes values, so this is built in typed code only. |
| R121 | 1 | 1 | not in the subset: subprocess.check_output() with * or ** arguments is not built. |
| R122 | 1 | 1 | not in the subset: super() in a class with no base class |
| R123 | 1 | 1 | not in the subset: sys.audit (not yet published in NAMES_library.json) |
| R124 | 1 | 1 | not in the subset: the decorator on def signal.signal (only @staticmethod on a method and @functools.lru_cache/@lru_cache/@cache are supported) |
| R125 | 1 | 1 | not in the subset: the method ._randbelow() (on a value of unknown static kind) |
| R126 | 1 | 1 | not in the subset: the name 'complex' is not a known function/class/builtin |
| R127 | 1 | 1 | not in the subset: the name 'globals' is not a known function/class/builtin |
| R128 | 1 | 1 | not in the subset: the name 'id' is not a known function/class/builtin |
| R129 | 1 | 1 | not in the subset: the name 'object' is not a known function/class/builtin |
| R130 | 1 | 1 | not in the subset: the name 'type' is not a known function/class/builtin |
| R131 | 1 | 1 | not in the subset: the program binds the name date that the library piece for datetime.date needs; rename it |
| R132 | 1 | 1 | not in the subset: unicodedata.ucd_3_2_0 is not supported (see the note below) |
| R133 | 1 | 1 | not in the subset: using function bisect.bisect_right as a first-class value (it has defaults, *args or **kwargs) |
| R134 | 1 | 1 | the import fails here (No module named '_sha1'), inside a `try:` in a nested statement; CPython would run the handler, and the compiler can only choose a branch for an import that is a direct statement of the `try:`. |
| R135 | 1 | 1 | the import fails here (No module named '_winreg'), inside a `try:` in a nested statement; CPython would run the handler, and the compiler can only choose a branch for an import that is a direct statement of the `try:`. |

## Before: most common first reasons

| count (default) | count (general) | first refusal message |
| ---: | ---: | --- |
| 9 | 9 | not in the subset: a generator expression used as a value. |
| 5 | 5 | not in the subset: io used here is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir rename replace getenv environ walk, os.sep linesep name curdir, and the os.path functions join exists isfile isdir islink getsize basename dirname split splitext abspath normpath isabs relpath |
| 4 | 4 | not in the subset: a caught exception type Attribute (only builtin or user Exception subclasses are supported) |
| 4 | 4 | not in the subset: os.path.normcase is not built. Built: join exists isfile isdir islink lexists getsize basename dirname split splitext abspath normpath isabs relpath |
| 4 | 4 | not in the subset: os.stat is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir rename replace getenv environ walk, os.sep linesep name curdir, and os.path join exists isfile isdir islink getsize basename dirname split splitext abspath normpath isabs relpath |
| 3 | 3 | not in the subset: warnings.warn (not yet published in NAMES_library.json) |
| 2 | 2 | module 'zlib' used as a value (passed, stored or compared); this compiler needs a module to be named at each use. |
| 2 | 2 | not in the subset: `with` around a `yield`: closing the generator does not pass GeneratorExit to __exit__ (not built) |
| 2 | 2 | not in the subset: a class-level constant built through a list item, attribute or dict value; write instead: bind the number as a module constant before the class |
| 2 | 2 | not in the subset: a constant integer expression overflows int64: its exact value is outside the signed 64-bit range and does not fit in a 64-bit signed integer (CPython computes it exactly because its int is unbounded, while this language's int is int64, SEMANTICS section 1). |
| 2 | 2 | not in the subset: os.environ.get(key) without a default returns None, and there is no None str. |
| 2 | 2 | not in the subset: os.system is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir rename replace getenv environ walk, os.sep linesep name curdir, and os.path join exists isfile isdir islink getsize basename dirname split splitext abspath normpath isabs relpath |
| 2 | 2 | not in the subset: str.encode() with the error handler 'backslashreplace' on the general path (built: utf-8, ascii, latin-1; errors strict, ignore, replace) |
| 2 | 2 | not in the subset: sys.stdin used as a plain value |
| 2 | 2 | not in the subset: urllib is built on the typed path only (bytes and the exception records are not on the general path). |
| 2 | 2 | not in the subset: warnings.catch_warnings (not yet published in NAMES_library.json) |

## Appendix: every module

`build` = exit 0 and an executable; `R#` is the reason id above. The default and general
columns are the two builds; `copy` is the only row where they differ.

| module | form | default | general |
| --- | --- | --- | --- |
| __future__ | module | build | build |
| _aix_support | module | R99 | R99 |
| _compat_pickle | module | R93 | R93 |
| _compression | module | R1 | R1 |
| _markupbase | module | R33 | R33 |
| _osx_support | module | R11 | R11 |
| _py_abc | module | R80 | R80 |
| _pydatetime | module | R8 | R8 |
| _pydecimal | module | R34 | R24 |
| _pyio | module | R18 | R18 |
| _pylong | module | R86 | R86 |
| _strptime | module | R85 | R85 |
| _threading_local | module | R71 | R71 |
| _weakrefset | module | R3 | R3 |
| aifc | module | R4 | R4 |
| antigravity | module | R97 | R97 |
| argparse | module | R101 | R101 |
| ast | module | R117 | R117 |
| asyncio | package | R55 | R55 |
| base64 | module | R90 | R90 |
| bdb | module | R2 | R2 |
| bisect | module | R133 | R133 |
| bz2 | module | R1 | R1 |
| cProfile | module | R1 | R1 |
| calendar | module | R119 | R119 |
| cgi | module | R118 | R118 |
| cgitb | module | R106 | R106 |
| chunk | module | R4 | R4 |
| cmd | module | R13 | R13 |
| code | module | R83 | R83 |
| codeop | module | R16 | R16 |
| collections | package | R47 | R47 |
| colorsys | module | build | build |
| compileall | module | R12 | R12 |
| concurrent | package | build | build |
| configparser | module | R107 | R107 |
| contextlib | module | R62 | R62 |
| contextvars | module | build | build |
| copy | module | R38 | R37 |
| copyreg | module | R96 | R96 |
| crypt | module | R48 | R48 |
| csv | module | R66 | R66 |
| ctypes | package | R42 | R42 |
| curses | package | R17 | R17 |
| dataclasses | module | R14 | R14 |
| datetime | module | build | build |
| dbm | package | R56 | R56 |
| decimal | module | build | build |
| difflib | module | R17 | R17 |
| dis | module | R20 | R20 |
| doctest | module | R12 | R12 |
| email | package | R46 | R46 |
| encodings | package | R44 | R44 |
| ensurepip | package | R32 | R32 |
| enum | module | R61 | R61 |
| filecmp | module | R5 | R5 |
| fileinput | module | R84 | R84 |
| fnmatch | module | R2 | R2 |
| fractions | module | R73 | R73 |
| ftplib | module | R100 | R100 |
| functools | module | R14 | R14 |
| getopt | module | R10 | R10 |
| getpass | module | R109 | R109 |
| gettext | module | R10 | R10 |
| glob | module | R3 | R3 |
| graphlib | module | R77 | R77 |
| gzip | module | R59 | R59 |
| hashlib | module | R134 | R134 |
| heapq | module | R129 | R129 |
| hmac | module | R91 | R91 |
| html | package | R72 | R72 |
| http | package | R98 | R98 |
| imaplib | module | R87 | R87 |
| imghdr | module | R103 | R103 |
| importlib | package | R60 | R60 |
| inspect | module | R70 | R70 |
| ipaddress | module | R52 | R52 |
| json | package | R68 | R68 |
| keyword | module | build | build |
| linecache | module | R5 | R5 |
| locale | module | R27 | R27 |
| logging | package | R19 | R19 |
| lzma | module | R1 | R1 |
| mailbox | module | R25 | R25 |
| mailcap | module | R11 | R11 |
| mimetypes | module | R15 | R15 |
| modulefinder | module | R28 | R28 |
| multiprocessing | package | R57 | R57 |
| netrc | module | R111 | R111 |
| nntplib | module | R131 | R131 |
| nturl2path | module | R88 | R88 |
| numbers | module | R126 | R126 |
| opcode | module | R49 | R49 |
| operator | module | R78 | R78 |
| optparse | module | R64 | R64 |
| pathlib | module | R15 | R15 |
| pdb | module | R40 | R40 |
| pickle | module | R50 | R50 |
| pickletools | module | R116 | R116 |
| pipes | module | R112 | R112 |
| pkgutil | module | R29 | R29 |
| platform | module | R135 | R135 |
| plistlib | module | R9 | R9 |
| poplib | module | R123 | R123 |
| pprint | module | R67 | R67 |
| profile | module | R1 | R1 |
| pstats | module | R5 | R5 |
| pty | module | R110 | R110 |
| py_compile | module | R30 | R30 |
| pyclbr | module | R74 | R74 |
| pydoc | module | R31 | R31 |
| pydoc_data | package | build | build |
| queue | module | R114 | R114 |
| quopri | module | R94 | R94 |
| random | module | R53 | R53 |
| re | package | R58 | R58 |
| reprlib | module | R128 | R128 |
| rlcompleter | module | R45 | R45 |
| sched | module | R79 | R79 |
| secrets | module | R125 | R125 |
| selectors | module | R81 | R81 |
| shelve | module | R89 | R89 |
| shlex | module | R13 | R13 |
| shutil | module | R22 | R39 |
| signal | module | R124 | R124 |
| smtplib | module | R26 | R26 |
| sndhdr | module | R16 | R16 |
| socket | module | R104 | R104 |
| socketserver | module | R113 | R113 |
| sqlite3 | package | R43 | R43 |
| sre_compile | module | R6 | R6 |
| sre_constants | module | R6 | R6 |
| sre_parse | module | R6 | R6 |
| ssl | module | R51 | R51 |
| statistics | module | R130 | R130 |
| string | module | R122 | R122 |
| stringprep | module | R132 | R132 |
| struct | module | build | build |
| subprocess | module | R105 | R105 |
| sunau | module | R95 | R95 |
| symtable | module | R63 | R63 |
| sysconfig | module | R69 | R69 |
| tabnanny | module | R2 | R2 |
| tarfile | module | R7 | R7 |
| telnetlib | module | R115 | R115 |
| tempfile | module | R108 | R108 |
| textwrap | module | R8 | R8 |
| this | module | build | build |
| threading | module | R21 | R21 |
| timeit | module | R4 | R4 |
| token | module | R127 | R127 |
| tokenize | module | R36 | R36 |
| tomllib | package | R76 | R76 |
| trace | module | R2 | R2 |
| traceback | module | R82 | R82 |
| tracemalloc | module | R2 | R2 |
| tty | module | R92 | R92 |
| turtle | module | R65 | R65 |
| types | module | R35 | R35 |
| typing | module | R23 | R23 |
| unittest | package | R41 | R41 |
| urllib | package | build | build |
| uu | module | R5 | R5 |
| uuid | module | R9 | R9 |
| venv | package | R121 | R121 |
| warnings | module | R75 | R75 |
| wave | module | R4 | R4 |
| weakref | module | R3 | R3 |
| webbrowser | module | R120 | R120 |
| wsgiref | package | build | build |
| xdrlib | module | R54 | R54 |
| xml | package | build | build |
| xmlrpc | package | build | build |
| zipapp | module | R3 | R3 |
| zipfile | package | R7 | R7 |
| zoneinfo | package | R102 | R102 |

