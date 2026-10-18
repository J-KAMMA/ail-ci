# -*- coding: utf-8 -*-
"""filelib.py -- stage G7: files and the os module (docs/design/GENERAL_PURPOSE.md s4.1, s4.2).

Python's `open()`, `with`, `print(file=f)`, `os` and `os.path` are lowered, as a tree-to-tree pass
that both compile paths run, onto

  * a small set of primitives (`PRIMS`, spelled `_ail_f_*` and `_ail_os_*`), each taking and
    returning int / str / bytes only. The C behind them is `ailfile_core.h`, one implementation
    shared by the typed runtime and the general runtime (filert.py holds the adapters);
  * a prelude of ordinary Python (classes `_AilTextIO` / `_AilBinaryIO`, `os.path` functions, ...)
    written in the subset both paths compile, injected only into a program that uses it, so every
    other program keeps its C byte for byte.

A file object is therefore a class instance holding an int handle. It can be passed, stored and
returned like any instance, and closing it, `with`, iteration and `print(file=f)` are lowered here.

Refusals are named and carry a `write instead:` line, never a silent change of meaning.
"""
import ast
import copy
import os
import re

import proclib

# ---------------------------------------------------------------------------------------------
# The primitives. name -> (result kind, argument kinds), kinds in {'int', 'str', 'bytes'}.
# A primitive that has nothing to return returns int 0 (the prelude ignores it).

PRIMS = {
    '_ail_f_open': ('int', ('str', 'str', 'int', 'str', 'int', 'str', 'int', 'str', 'int')),
    '_ail_f_close': ('int', ('int',)),
    '_ail_f_flush': ('int', ('int',)),
    '_ail_f_tread': ('str', ('int', 'int')),
    '_ail_f_treadline': ('str', ('int', 'int')),
    '_ail_f_tnext': ('str', ('int',)),
    '_ail_f_twrite': ('int', ('int', 'str')),
    '_ail_f_bread': ('bytes', ('int', 'int')),
    '_ail_f_breadline': ('bytes', ('int', 'int')),
    '_ail_f_bnext': ('bytes', ('int',)),
    '_ail_f_bwrite': ('int', ('int', 'bytes')),
    '_ail_f_seek': ('int', ('int', 'int', 'int')),
    '_ail_f_tell': ('int', ('int',)),
    '_ail_f_readable': ('int', ('int',)),
    '_ail_f_writable': ('int', ('int',)),
    '_ail_f_seekable': ('int', ('int',)),
    '_ail_os_getcwd': ('str', ()),
    '_ail_os_chdir': ('int', ('str',)),
    '_ail_os_scandir': ('str', ('str', 'int')),
    '_ail_os_kind': ('int', ('str', 'int')),
    '_ail_os_getsize': ('int', ('str',)),
    '_ail_os_mkdir': ('int', ('str', 'int')),
    '_ail_os_rmdir': ('int', ('str',)),
    '_ail_os_unlink': ('int', ('str',)),
    '_ail_os_chmod': ('int', ('str', 'int')),
    '_ail_os_rename': ('int', ('str', 'str')),
    '_ail_os_replace': ('int', ('str', 'str')),
    '_ail_os_getenv': ('str', ('str',)),
    '_ail_os_hasenv': ('int', ('str',)),
    '_ail_os_setenv': ('int', ('str', 'str')),
    '_ail_os_unsetenv': ('int', ('str',)),
}
PRIMS.update(proclib.PROCS)        # stage G8: the process primitives (ailproc_core.h), a part of their own
# stage G10: three small primitives for pathlib (ailpath_core.h), also a part of their own
PATHS = {
    '_ail_pp_staterr': ('int', ('str',)),          # errno of stat(path): 0 works, -1 a path CPython refuses with ValueError
    '_ail_pp_readlink': ('str', ('str',)),
    '_ail_pp_repr': ('str', ('str',)),             # repr() of a str
}
PRIMS.update(PATHS)


def is_proc_prim(prim):
    return prim.startswith('_ail_sp_')


def is_path_prim(prim):
    return prim.startswith('_ail_pp_')


def prim_kind(prim):
    """'file' (ailfile_core.h), 'proc' (ailproc_core.h) or 'path' (ailpath_core.h)."""
    return 'proc' if is_proc_prim(prim) else 'path' if is_path_prim(prim) else 'file'


def c_name(prim):
    """`_ail_f_open` -> `f_open`: the suffix of the adapter functions (ailt_f_open, ailo_f_open)."""
    return prim[len('_ail_'):]


# Set once a program has been lowered with the file layer: the exception classes of the OS family
# then get codes of their own in the typed path (pyfunc reads this).
ACTIVE = bool(os.environ.get('AIL_G7_FORCE'))      # (the variable lets the prelude be tried without the rewrite)


# ---------------------------------------------------------------------------------------------
# The entry points

_ENCODINGS = {'utf-8': 'utf-8', 'ascii': 'ascii', 'iso8859-1': 'latin-1'}      # codecs.lookup name -> ours


def canonical_encoding(name):
    """The name the runtime understands for a literal encoding, or None for one that is not built."""
    import codecs
    try:
        found = codecs.lookup(name).name
    except LookupError:
        return None
    return _ENCODINGS.get(found)


def target_windows():
    """Whether paths are the ntpath flavour: the build target (AIL_TARGET), else the host."""
    target = os.environ.get('AIL_TARGET', '')
    if target:
        return target.startswith('windows')
    import sys
    return sys.platform == 'win32'


def rewrite_tree(tree, Unsupported, general=False):
    """Lower `open`, `with`, `print(file=)`, file iteration, `os` and `os.path` in `tree` (in place).
    Returns whether the program uses the file layer; a program that does not is left untouched."""
    global ACTIVE
    ACTIVE = bool(os.environ.get('AIL_G7_FORCE'))
    import pathlower
    path_need = pathlower.rewrite_tree(tree, Unsupported, general)     # G10: pathlib.Path -> prelude functions + open()
    used_proc = proclib.rewrite_tree(tree, Unsupported, general)      # G8: subprocess -> primitives + prelude
    import filelower
    lowerer = filelower._Lowerer(tree, Unsupported, general)
    lowerer.scan()
    if path_need is not None:
        lowerer.need.update(path_need)
    if not lowerer.wants() and path_need is None:
        ACTIVE = ACTIVE or used_proc           # subprocess raises the OS-family classes too
        return used_proc
    lowerer.run()
    ACTIVE = True
    if os.environ.get('AIL_G7_DUMP'):
        import sys
        print(ast.unparse(tree), file=sys.stderr)
        seen = {}
        for each in ast.walk(tree):
            if id(each) in seen and not isinstance(each, (ast.Load, ast.Store, ast.Del, ast.operator, ast.cmpop, ast.unaryop, ast.boolop)):
                print('SHARED NODE', type(each).__name__, getattr(each, 'lineno', None), file=sys.stderr)
            seen[id(each)] = True
    return True
