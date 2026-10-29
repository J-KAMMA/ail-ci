"""G4: the C FFI declaration module, and its CPython implementation (ctypes only, standard library).

A program declares a C function as a Python stub whose annotations are the C prototype:

    from ail_ffi import extern, length, c_ulong, c_uint

    @extern(lib="z", header="zlib.h")
    def crc32(crc: c_ulong, buf: bytes, n: length("buf", c_uint)) -> c_ulong: ...

    print(crc32(0, b"hello"))

`python3 prog.py` runs it here, through ctypes. `ail compile prog.py` reads the same stub (without
importing this file), generates a C adapter that includes the header and checks the prototype, links
`-lz`, and the compiled program prints the same bytes. Both sides call the same C library.

Annotations (the stub's whole contract; a missing parameter or return annotation is refused)

    integers   c_int c_uint c_short c_ushort c_long c_ulong c_longlong c_ulonglong c_size_t c_ssize_t
               c_int8 .. c_int64 c_uint8 .. c_uint64 (c_byte, c_ubyte)   an AIL/Python int, range checked
    floats     c_double c_float
    bool       c_bool
    bytes      `bytes`              const unsigned char *   borrowed for the call, never copied
    bytearray  `bytearray`          unsigned char *         the C function may write to it; the length
                                    cannot change (copied in and out around the call when compiled)
    pointers   ptr(T) / cptr(T)     T * over a bytearray / const T * over bytes, T an integer, c_double,
                                    c_float or c_bool type. The out-parameter form: `q: ptr(c_int)` takes
                                    `bytearray(4)`; read it back by shifting bytes. A length that is not a
                                    whole number of T is a ValueError
    str        c_char_p             const char *            UTF-8, NUL terminated copy (embedded NUL: error)
               c_mut_char_p         char *                  the same, for a C prototype without const; C must not write it
    handles    c_void_p             void *                  an int (0 is NULL); the program owns lifetime
    owned      Handle(name, free=)  void *                  an object that owns the pointer (see below)
    raw views  c_const_void_p       const void *  (takes bytes)      c_mut_void_p   void *  (takes bytearray)
    length     length("buf", T)     the C parameter that carries len(buf) (elements for ptr/cptr); the call
                                    supplies it, it is not a parameter of the Python function
    results    any of the above except bytes/bytearray; `c_char_p` is copied and decoded (NULL gives "");
               `None` is void; a missing return annotation is refused

Owned handles (F4). `Db = Handle("sqlite3", free="sqlite3_close")` at module level (or `Handle(...)` written
inline as an annotation) makes a type for an `@extern` stub's parameter or result: the value is an object that
holds the pointer and frees it exactly once with the C function `free` (declared by no stub; it is looked up in
the libraries of the stubs that use the type).

    Db = Handle("sqlite3", free="sqlite3_close")
    @extern(lib="sqlite3", trust=True)
    def sqlite3_open(path: c_char_p, out: ptr(c_void_p)) -> c_int: ...
    @extern(lib="sqlite3", trust=True)
    def sqlite3_exec(db: Db, sql: c_char_p, cb: c_void_p, arg: c_void_p, err: c_void_p) -> c_int: ...

    out = bytearray(8)
    sqlite3_open(":memory:", out)
    db = Db.adopt(out)          # takes the pointer out of the out-parameter (the buffer is zeroed)
    sqlite3_exec(db, "create table t(x)", 0, 0, 0)
    db.close()                  # calls sqlite3_close once, zeroes the pointer; a second close() does nothing
    sqlite3_exec(db, "...", 0, 0, 0)    # ValueError: sqlite3 handle is closed

`with db:` closes the handle on the way out. A result that is NULL is a handle that is already closed.
An unclosed handle is freed when its last reference drops (CPython) and, for what is still open, at program
exit in the reverse order of creation. A bare `c_void_p` is an int and works as before. A Handle is not a number:
arithmetic on one, or passing one into a parallel worker, is refused when compiling.
The compiled program frees an unclosed handle at program exit (or at close()), not when the last reference
drops: the two differ only if the C library's free function does something the program can observe earlier.

Callbacks (F7). `callback(ret, arg1, ...)` is a parameter type: a C function pointer the C function calls during
the call. The argument is the name of a module-level `def` whose annotations are the Python types of the C types.

    Cmp = callback(c_int, cptr(c_int), cptr(c_int), on_error=0)
    @extern(header="stdlib.h", trust=True)
    def qsort(base: ptr(c_int), n: length("base", c_size_t), size: c_size_t, cmp: Cmp) -> None: ...

    def by_value(a: int, b: int) -> int:
        return a - b

    qsort(buf, 4, by_value)

    ret        None (void), an integer type, c_double, c_float, c_bool or c_void_p (an int)
    arguments  integer types, c_double, c_float, c_bool (the value); c_void_p, c_const_void_p (the address, an int);
               c_char_p, c_mut_char_p (str: UTF-8, NULL gives ""); cptr(T) (`const T *` to one T: the T it points
               at, NULL gives 0); array(T, k) (`T *` with as many elements as the integer argument number k, 0-based,
               says: a list; T an integer type, c_double, c_float, c_bool, c_char_p or c_mut_char_p)
    on_error=  the value C gets back when the callback raises (required unless ret is None)

An exception raised in the callback is stored, the callback returns `on_error` to C, and every later call of a
callback during the same C call returns `on_error` without running the function; when the C call returns, the
stored exception is raised (before `check=`). Plain ctypes would print "Exception ignored" and go on; this module
and the compiled program both store and re-raise. A result that does not fit ret is an OverflowError, raised the
same way. A callback is valid only during the call: `retain=True` (C stores it) and `threads=True` (C calls it from
another thread) are refused, and a call from another thread or after the C call returned aborts the program.
The callback is a module-level def: a lambda, a closure, a method or a variable is refused when compiling (and is a
TypeError here). The compiled program runs the C function on a stack of its own and runs the callback in between,
on the caller's stack and thread; a bytearray argument is copied in and out around the whole call there, so the
callback sees the bytearray as it was before the call.
A stub that takes a callback is called in the file that declares it; another module calls a def of that file.

`link("m", "z")` at module level names libraries for every stub of the file that has no `lib=`.
`ptr(c_void_p)` is `void **`, the out-parameter that returns a handle (sqlite3_open). A struct passed by pointer
is a bytearray (`c_mut_void_p`) / bytes (`c_const_void_p`) laid out by hand with the C offsets; give a stub whose
C prototype names a struct `trust=True` (the exact-prototype check cannot spell the struct).

`@extern(...)` options: `trust` (True: the header is included but its prototype is not compared with the stub;
for a C prototype that names a struct), `lib` (library name for -l, or a path to a shared library relative to the
declaring file; None is the C library), `header` (checked against the real prototype at compile time;
without one the declaration is trusted and `ail check --ffi` says so), `symbol` (the C name when it differs
from the stub name), `pkg_config` (link flags from pkg-config, compile side only), `check` (one of
"negative", "nonzero", "null", "minus1": a result that means failure), `errno` (read errno right after the
call and raise OSError(errno, strerror): `str(e)` is `[Errno 2] No such file or directory`, `e.errno` is 2),
`exc` (OSError by default with errno, else RuntimeError; one of the built-in kinds AIL can raise: OSError ValueError RuntimeError KeyError
IndexError OverflowError EOFError), `sources` (a list of .c files beside the declaring file: the compiled
program links them into its adapter object, CPython builds them into a shared library on first use).

What the compiled program does differently (the declared differences):
  * `c_ulong`, `c_size_t` and `c_uint64` results above 2**63 - 1 come back as the negative int with the
    same bits in the compiled program (AIL ints are 64 bit); CPython gives the positive value.
    The same holds for callback arguments of those types.
  * a callback reads a bytearray that was passed to the same C call as it was before the call (the compiled program
    copies it in and out around the whole call); C's writes are seen after the call returns.
  * a bytearray argument is copied in and out around the call in the compiled program; two names for one
    bytearray in one call see C's writes only after it returns.
  * `e.errno`, `e.strerror` and `str(e)` of an OSError are built in the compiled program only on a name bound by
    `except OSError as e` (or one of the five errno classes AIL has); any other class is refused by name.
    An OSError that did not come from an errno (a bare `OSError("x")`) has no errno there: reading it raises
    RuntimeError, where CPython gives None.
"""
import ctypes
import ctypes.util
import os
import sys

__all__ = ['extern', 'export', 'exports', 'link', 'length', 'ptr', 'cptr', 'declarations', 'Handle', 'callback', 'array', 'c_int', 'c_uint', 'c_short', 'c_ushort', 'c_long', 'c_ulong',
           'c_longlong', 'c_ulonglong', 'c_size_t', 'c_ssize_t', 'c_int8', 'c_int16', 'c_int32', 'c_int64',
           'c_uint8', 'c_uint16', 'c_uint32', 'c_uint64', 'c_byte', 'c_ubyte', 'c_bool', 'c_double', 'c_float',
           'c_char_p', 'c_mut_char_p', 'c_void_p', 'c_const_void_p', 'c_mut_void_p']

EXCEPTIONS = {'OSError': OSError, 'ValueError': ValueError, 'RuntimeError': RuntimeError, 'KeyError': KeyError,
              'IndexError': IndexError, 'OverflowError': OverflowError, 'EOFError': EOFError}
CHECKS = {
    'negative': lambda rc: rc < 0,
    'nonzero': lambda rc: rc != 0,
    'null': lambda rc: rc == 0,
    'minus1': lambda rc: rc == -1,
}


class CType:
    """An annotation marker. `kind` is int, float, bool, str, handle, bytes, bytearray or length."""

    def __init__(self, name, kind, ctype=None, bits=0, signed=True):
        self.name, self.kind, self.ctype, self.bits, self.signed = name, kind, ctype, bits, signed

    def __repr__(self):
        return self.name

    def limits(self):
        if self.signed:
            return -(1 << (self.bits - 1)), (1 << (self.bits - 1)) - 1
        return 0, (1 << self.bits) - 1


def _int(name, ctype, signed=None):
    bits = ctypes.sizeof(ctype) * 8
    return CType(name, 'int', ctype, bits, ctype(-1).value < 0 if signed is None else signed)


c_int8 = c_byte = _int('c_int8', ctypes.c_int8)
c_int16 = _int('c_int16', ctypes.c_int16)
c_int32 = _int('c_int32', ctypes.c_int32)
c_int64 = _int('c_int64', ctypes.c_int64)
c_uint8 = c_ubyte = _int('c_uint8', ctypes.c_uint8)
c_uint16 = _int('c_uint16', ctypes.c_uint16)
c_uint32 = _int('c_uint32', ctypes.c_uint32)
c_uint64 = _int('c_uint64', ctypes.c_uint64)
c_short = _int('c_short', ctypes.c_short)
c_ushort = _int('c_ushort', ctypes.c_ushort)
c_int = _int('c_int', ctypes.c_int)
c_uint = _int('c_uint', ctypes.c_uint)
c_long = _int('c_long', ctypes.c_long)
c_ulong = _int('c_ulong', ctypes.c_ulong)
c_longlong = _int('c_longlong', ctypes.c_longlong)
c_ulonglong = _int('c_ulonglong', ctypes.c_ulonglong)
c_size_t = _int('c_size_t', ctypes.c_size_t)
c_ssize_t = _int('c_ssize_t', ctypes.c_ssize_t)
c_bool = CType('c_bool', 'bool', ctypes.c_bool)
c_double = CType('c_double', 'float', ctypes.c_double)
c_float = CType('c_float', 'float', ctypes.c_float)
c_char_p = CType('c_char_p', 'str', ctypes.c_char_p)
c_mut_char_p = CType('c_mut_char_p', 'str', ctypes.c_char_p)
c_void_p = CType('c_void_p', 'handle', ctypes.c_void_p)
c_const_void_p = CType('c_const_void_p', 'bytes', ctypes.c_char_p)
c_mut_void_p = CType('c_mut_void_p', 'bytearray', ctypes.c_void_p)
_BYTES = CType('bytes', 'bytes', ctypes.c_char_p)
_BYTEARRAY = CType('bytearray', 'bytearray', ctypes.c_void_p)


class ptr:
    """Annotation: `T *` backed by a bytearray (C may write it); cptr(T) is `const T *` backed by bytes.
    The buffer holds a whole number of T."""
    const = False

    def __init__(self, ctype):
        if not isinstance(ctype, CType) or ctype.kind not in ('int', 'float', 'bool', 'handle'):
            raise TypeError('%s(integer, float, bool or c_void_p C type)' % type(self).__name__)
        self.ctype = ctype

    @property
    def kind(self):
        return 'bytes' if self.const else 'bytearray'

    def __repr__(self):
        return '%s(%s)' % (type(self).__name__, self.ctype)


class cptr(ptr):
    const = True


class length:
    """Annotation of the C parameter that receives len(<name>) of another parameter."""

    def __init__(self, name, ctype=c_size_t):
        if not isinstance(name, str) or not isinstance(ctype, CType) or ctype.kind != 'int':
            raise TypeError('length(name, integer C type)')
        self.name, self.ctype = name, ctype

    def __repr__(self):
        return 'length(%r, %s)' % (self.name, self.ctype)


class array:
    """Callback argument type: `T *` with as many elements as the integer argument number `count` (0-based) says.
    The callback gets a list."""

    def __init__(self, ctype, count):
        if not isinstance(ctype, CType) or ctype.kind not in ('int', 'float', 'bool', 'str') or type(count) is not int:
            raise TypeError('array(integer, float, bool or c_char_p C type, index of the count argument)')
        self.ctype, self.count = ctype, count

    def __repr__(self):
        return 'array(%s, %d)' % (self.ctype, self.count)


_CB_RESULTS = ('int', 'float', 'bool', 'handle')


class callback:
    """Parameter type: a C function pointer that C calls during the call; the argument is a module-level def."""
    kind = 'callback'

    def __init__(self, ret, *args, on_error=None, retain=False, threads=False):
        if retain:
            raise TypeError('callback(retain=True): C would keep the callback after the call returns, and a callback '
                            'is valid only during the call')
        if threads:
            raise TypeError('callback(threads=True): C would call the callback from another thread, and a callback runs '
                            'only on the thread that made the call')
        if ret is not None and (not isinstance(ret, CType) or ret.kind not in _CB_RESULTS):
            raise TypeError('callback result: None, an integer type, c_double, c_float, c_bool or c_void_p')
        if len(args) > 16:
            raise TypeError('callback: at most 16 arguments')
        for index, arg in enumerate(args):
            if isinstance(arg, array):
                if not 0 <= arg.count < len(args) or not isinstance(args[arg.count], CType) or args[arg.count].kind != 'int':
                    raise TypeError('callback: array(T, %d) must name an integer argument' % arg.count)
            elif isinstance(arg, ptr):
                if not arg.const:
                    raise TypeError('callback: ptr(T) is not an argument type (write cptr(T): the value it points at)')
            elif not isinstance(arg, CType) or arg.kind not in ('int', 'float', 'bool', 'handle', 'str') and arg is not c_const_void_p:
                raise TypeError('callback argument %d: unsupported type %r' % (index, arg))
        if ret is None:
            if on_error is not None:
                raise TypeError('callback: a void callback has no on_error')
        else:
            if on_error is None:
                raise TypeError('callback(%s, ...) needs on_error=<value>: what C gets back when the callback raises' % ret)
            _cb_result(ret, on_error, 'on_error')
        self.ret, self.args, self.on_error = ret, args, on_error
        self._cfunctype = None

    def __repr__(self):
        return 'callback(%s)' % ', '.join(repr(x) for x in (self.ret,) + self.args)

    def cfunctype(self):
        if self._cfunctype is None:
            def ctype_of(arg):
                if isinstance(arg, array):
                    return ctypes.POINTER(ctypes.c_char_p if arg.ctype.kind == 'str' else arg.ctype.ctype)
                if isinstance(arg, ptr):
                    return ctypes.POINTER(arg.ctype.ctype)
                if arg.kind in ('handle', 'bytes'):
                    return ctypes.c_void_p
                if arg.kind == 'str':
                    return ctypes.c_char_p
                return arg.ctype
            restype = None if self.ret is None else ctypes.c_void_p if self.ret.kind == 'handle' else self.ret.ctype
            self._cfunctype = ctypes.CFUNCTYPE(restype, *[ctype_of(a) for a in self.args])
        return self._cfunctype

    def python_types(self):
        """The annotations a callback def must have: ([parameter types], result type)."""
        def one(arg):
            if isinstance(arg, array):
                return list[_PYTHON[arg.ctype.kind]]
            if isinstance(arg, ptr):
                return _PYTHON[arg.ctype.kind]
            return int if arg is c_const_void_p else _PYTHON[arg.kind]
        return [one(a) for a in self.args], None if self.ret is None else _PYTHON[self.ret.kind]


_PYTHON = {'int': int, 'float': float, 'bool': bool, 'str': str, 'handle': int}


def _cb_result(ret, value, what):
    """Check a callback result (or on_error) against ret; the C value."""
    if ret.kind == 'int':
        if type(value) is not int:
            raise TypeError('%s must be an int' % what)
        low, high = ret.limits()
        if not low <= value <= high:
            raise OverflowError('%s does not fit %s' % (what, ret))
        return value
    if ret.kind == 'handle':
        if type(value) is not int:
            raise TypeError('%s must be an int' % what)
        if not 0 <= value < (1 << 64):
            raise OverflowError('%s does not fit %s' % (what, ret))
        return value
    if ret.kind == 'bool':
        if type(value) is not bool:
            raise TypeError('%s must be a bool' % what)
        return value
    if type(value) not in (int, float):
        raise TypeError('%s must be a float' % what)
    return float(value)


def _cb_function(stub, name, cb, value):
    """The checks the compiler makes on a callback argument: a module-level def with the annotations of cb."""
    import inspect
    import typing
    where = '%s: the callback %s' % (stub, name)
    if not inspect.isfunction(value):
        if inspect.ismethod(value):
            raise TypeError('%s is a method; a callback is a module-level def' % where)
        raise TypeError('%s must be a module-level def' % where)
    if value.__name__ == '<lambda>':
        raise TypeError('%s is a lambda; a callback is a module-level def' % where)
    if value.__closure__ or '<locals>' in value.__qualname__:
        raise TypeError('%s is a closure; a callback is a module-level def' % where)
    if '.' in value.__qualname__:
        raise TypeError('%s is a method; a callback is a module-level def' % where)
    params, result = cb.python_types()
    try:
        hints = typing.get_type_hints(value)
    except Exception:
        hints = {}
    names = list(inspect.signature(value).parameters)
    got = [hints.get(n) for n in names]
    want_result = type(None) if result is None else result
    if got != params or hints.get('return', inspect.Parameter.empty) != want_result:
        raise TypeError('%s: %s must be `def %s(%s) -> %s`' % (
            where, value.__name__, value.__name__,
            ', '.join('a%d: %s' % (i, _type_text(t)) for i, t in enumerate(params)), _type_text(result)))
    return value


def _type_text(t):
    return 'None' if t is None else t.__name__ if isinstance(t, type) else repr(t)


def _cb_argument(arg, raw, args):
    """The Python value a callback def gets for one C argument."""
    if isinstance(arg, array):
        n = args[arg.count]
        if not raw or n <= 0:
            return []
        if arg.ctype.kind == 'str':
            return ['' if raw[i] is None else raw[i].decode('utf-8') for i in range(n)]
        return [raw[i] for i in range(n)]
    if isinstance(arg, ptr):
        if not raw:
            return {'float': 0.0, 'bool': False}.get(arg.ctype.kind, 0)
        return raw[0]
    if arg.kind in ('handle', 'bytes'):
        return raw or 0
    if arg.kind == 'str':
        return '' if raw is None else raw.decode('utf-8')
    return raw


_HANDLE_TYPES = {}                      # (name, free) -> the class Handle() made for it
_LIVE = {}                              # creation number -> weakref of an open handle
_COUNTER = [0]
_HOOKED = [False]


def _close_all():
    """At exit: free what is still open, newest first (a statement before its database)."""
    for number in sorted(_LIVE, reverse=True):
        handle = _LIVE.get(number)
        handle = None if handle is None else handle()
        if handle is not None:
            try:
                handle.close()
            except Exception:
                pass


class _HandleBase:
    """The object an owned handle type (`Handle(name, free=...)`) makes: it owns one pointer."""
    _name = ''
    _free = ''

    def __init__(self, address=0):
        if type(address) is not int or not 0 <= address < (1 << 64):
            raise TypeError('a handle is made by a stub that returns it, or by %s.adopt(buffer)' % type(self).__name__)
        self._p = address
        self._number = 0
        if address:
            import atexit
            import weakref
            _COUNTER[0] += 1
            self._number = _COUNTER[0]
            _LIVE[self._number] = weakref.ref(self)
            if not _HOOKED[0]:
                _HOOKED[0] = True
                atexit.register(_close_all)

    def _check(self):
        if not self._p:
            raise ValueError('%s handle is closed' % self._name)

    def close(self):
        """Free the pointer (once) and zero it; closing a closed handle does nothing."""
        address = self._p
        if address:
            self._p = 0
            _LIVE.pop(self._number, None)
            cls = type(self)
            for library in cls._libraries + [ctypes.CDLL(None)]:
                try:
                    free = getattr(library, cls._free)
                except AttributeError:
                    continue
                free.argtypes = [ctypes.c_void_p]
                free.restype = None
                free(address)
                return
            raise RuntimeError('cannot find %s to free a %s handle' % (cls._free, cls._name))

    def __enter__(self):
        self._check()
        return self

    def __exit__(self, kind, value, trace):
        self.close()
        return False

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    @classmethod
    def adopt(cls, buffer):
        """The handle for the pointer a C function stored through a `ptr(c_void_p)` out-parameter. The buffer
        (a bytearray of 8 bytes) is zeroed, so the pointer has one owner."""
        if type(buffer) is not bytearray or len(buffer) != 8:
            raise ValueError('adopt takes the bytearray(8) of a ptr(c_void_p) out-parameter')
        address = int.from_bytes(buffer, sys.byteorder)
        buffer[:] = bytes(8)
        return cls(address)


def Handle(name, *, free):
    """An owned handle type: `Handle("sqlite3", free="sqlite3_close")`. The same name and free give the same type."""
    if not isinstance(name, str) or not name.isidentifier() or not isinstance(free, str) or not free.isidentifier():
        raise TypeError('Handle("name", free="c_function"): both are identifiers')
    key = (name, free)
    if key not in _HANDLE_TYPES:
        _HANDLE_TYPES[key] = type('Handle_' + name, (_HandleBase,), dict(_name=name, _free=free, _libraries=[]))
    return _HANDLE_TYPES[key]


_DECLARED = []
_LINKED = {}                         # declaring file -> [library name or path, ...] from link()


def link(*libs, pkg_config=None):
    """Module-level declaration: the libraries this file's `@extern` stubs (those without `lib=`) resolve their
    symbols in, in order after the C library. `link("m", "z")` is `-lm -lz` when compiled and the same two
    libraries loaded by name here. A name is a library name; a path (`./libfoo.so`, relative to this file) is
    that file. `pkg_config=` (compile side) takes the link flags from pkg-config for these names."""
    if not libs or not all(isinstance(lib, str) and lib for lib in libs):
        raise TypeError('link("name", ...) takes library names or paths')
    filename = sys._getframe(1).f_code.co_filename
    _LINKED.setdefault(filename, []).extend(libs)


class _Chain:
    """Symbol lookup over the C library and then each linked library."""

    def __init__(self, libraries):
        self.libraries = libraries

    def __getattr__(self, name):
        for library in self.libraries:
            try:
                return getattr(library, name)
            except AttributeError:
                continue
        raise AttributeError('symbol %r not found in the C library or any link() library' % name)


def declarations():
    """The stubs declared so far in this process: dicts with name, lib, header, symbol, signature."""
    return [dict(d) for d in _DECLARED]


def _classify(annotation):
    if annotation is bytes:
        return _BYTES
    if annotation is bytearray:
        return _BYTEARRAY
    if annotation is str:
        return c_char_p
    if annotation is int or annotation is float or annotation is bool:
        raise TypeError('annotate with a C type (c_int, c_double, ...), not %s' % annotation.__name__)
    if isinstance(annotation, (CType, length, ptr, callback)):
        return annotation
    if isinstance(annotation, type) and issubclass(annotation, _HandleBase) and annotation is not _HandleBase:
        owned = CType('Handle(%s)' % annotation._name, 'owned', ctypes.c_void_p)
        owned.handle = annotation
        return owned
    raise TypeError('unsupported FFI annotation: %r' % (annotation,))


def _load(lib, filename):
    if lib is None:
        linked = _LINKED.get(filename)
        if linked:
            return _Chain([ctypes.CDLL(None, use_errno=True)] + [_load(name, filename) for name in linked])
        return ctypes.CDLL(None, use_errno=True)
    if '/' in lib or os.sep in lib or lib.endswith(('.so', '.dylib', '.dll')) or '.so.' in lib:
        base = os.path.dirname(os.path.abspath(filename)) if filename else os.getcwd()
        return ctypes.CDLL(os.path.normpath(os.path.join(base, lib)), use_errno=True)
    found = ctypes.util.find_library(lib)
    if found is None:
        for candidate in ('lib%s.so' % lib, 'lib%s.dylib' % lib, '%s.dll' % lib):
            try:
                return ctypes.CDLL(candidate, use_errno=True)
            except OSError:
                continue
        raise OSError('cannot find library %r' % lib)
    return ctypes.CDLL(found, use_errno=True)


def _signature(function):
    import inspect
    signature = inspect.signature(function, eval_str=False)
    # `from __future__ import annotations` leaves the annotations as strings
    annotations = {key: (eval(value, function.__globals__) if isinstance(value, str) else value)
                   for key, value in function.__annotations__.items()}
    params = []
    for name, parameter in signature.parameters.items():
        if name not in annotations:
            raise TypeError('%s: parameter %r needs an annotation (the C prototype)' % (function.__name__, name))
        if parameter.kind not in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD):
            raise TypeError('%s: *args and keyword-only parameters are not C parameters' % function.__name__)
        params.append((name, _classify(annotations[name]), parameter.default))
    if 'return' not in annotations:
        raise TypeError('%s: a missing return annotation is refused (write `-> None` for void)' % function.__name__)
    result = annotations['return']
    result = None if result is None else _classify(result)
    if result is not None and result.kind in ('bytes', 'bytearray', 'length', 'callback'):
        raise TypeError('%s: bytes, bytearray and length cannot be results' % function.__name__)
    return params, result


def _build_sources(sources, lib, filename):
    """Compile the C files an @extern names (`sources=[...]`, beside the declaring file) into a shared library
    for this process; the compiled program links the same files into its adapter object."""
    import hashlib
    import shutil
    import subprocess
    import tempfile
    base = os.path.dirname(os.path.abspath(filename))
    paths = [os.path.join(base, name) for name in sources]
    digest = hashlib.sha256()
    for path in paths:
        with open(path, 'rb') as stream:
            digest.update(os.path.basename(path).encode() + b'\0' + stream.read() + b'\0')
    for name in sorted(os.listdir(base)):
        if name.endswith('.h'):
            with open(os.path.join(base, name), 'rb') as stream:
                digest.update(name.encode() + b'\0' + stream.read() + b'\0')
    digest.update((lib or '').encode())
    directory = os.path.join(tempfile.gettempdir(), 'ail_ffi_cache_%d' % os.getuid() if hasattr(os, 'getuid') else 'ail_ffi_cache')
    os.makedirs(directory, exist_ok=True)
    target = os.path.join(directory, digest.hexdigest()[:24] + '.so')
    if not os.path.exists(target):
        compiler = os.environ.get('PIPE_CC') or os.environ.get('CC') or shutil.which('cc') or shutil.which('gcc') or 'cc'
        command = [compiler, '-O2', '-ffp-contract=off', '-shared', '-fPIC', '-I', base, '-o', target + '.tmp.%d' % os.getpid(), *paths]
        if lib and not (os.sep in lib or lib.endswith('.so')):
            command.append('-l' + lib)
        done = subprocess.run(command, capture_output=True, text=True)
        if done.returncode:
            raise OSError('cannot build FFI sources %s:\n%s' % (', '.join(sources), done.stderr[-2000:]))
        os.replace(target + '.tmp.%d' % os.getpid(), target)
    return ctypes.CDLL(target, use_errno=True)


def _trampoline(stub, cb, fn, stored):
    """The Python function behind a CFUNCTYPE: runs fn on C's arguments; an exception is stored (the first one) and C
    gets on_error, here and on every later call during the same C call."""
    import threading
    owner = threading.get_ident()

    def call(*raw):
        if threading.get_ident() != owner:
            sys.stdout.flush()
            sys.stderr.write('ail_ffi: the callback of %s was called from another thread or after its C call returned\n' % stub)
            sys.stderr.flush()
            os.abort()
        if stored:
            return cb.on_error
        try:
            value = fn(*[_cb_argument(arg, r, raw) for arg, r in zip(cb.args, raw)])
            if cb.ret is None:
                return None
            return _cb_result(cb.ret, value, '%s: the result of %s' % (stub, fn.__name__))
        except BaseException as error:
            stored.append(error)
            return cb.on_error
    return call


def extern(lib=None, header=None, *, symbol=None, check=None, errno=False, exc=None, pkg_config=None, sources=None, trust=False):
    if check is not None and check not in CHECKS:
        raise ValueError('check must be one of %s' % ', '.join(sorted(CHECKS)))
    if exc is not None and exc not in EXCEPTIONS.values():
        raise ValueError('exc must be one of %s' % ', '.join(sorted(EXCEPTIONS)))
    if errno and check is None:
        raise ValueError('errno=True needs check= (which results are failures)')

    def declare(function):
        params, result = _signature(function)
        names = {name for name, _, _ in params}
        for name, kind, _ in params:
            if isinstance(kind, length):
                if kind.name not in names or not isinstance(next(k for n, k, _ in params if n == kind.name), (CType, ptr)) \
                        or next(k for n, k, _ in params if n == kind.name).kind not in ('bytes', 'bytearray'):
                    raise TypeError('%s: length(%r) must name a bytes or bytearray parameter' % (function.__name__, kind.name))
        c_name = symbol or function.__name__
        record = dict(name=function.__name__, symbol=c_name, lib=lib, header=header,
                      file=getattr(function.__code__, 'co_filename', None))
        _DECLARED.append(record)
        state = {}

        def bind():
            cdll = _build_sources(sources, lib, record['file']) if sources else _load(lib, record['file'])
            cfn = getattr(cdll, c_name)
            for _, kind, _ in params + [('return', result, None)]:
                if getattr(kind, 'kind', None) == 'owned' and cdll not in kind.handle._libraries:
                    kind.handle._libraries.append(cdll)
            argtypes = []
            for _, kind, _ in params:
                if isinstance(kind, length):
                    argtypes.append(kind.ctype.ctype)
                elif kind.kind == 'bytes':
                    argtypes.append(ctypes.c_char_p)
                elif kind.kind == 'bytearray':
                    argtypes.append(ctypes.c_void_p)
                elif kind.kind == 'handle':
                    argtypes.append(ctypes.c_void_p)
                elif kind.kind == 'str':
                    argtypes.append(ctypes.c_char_p)
                elif kind.kind == 'callback':
                    argtypes.append(kind.cfunctype())
                else:
                    argtypes.append(kind.ctype)
            cfn.argtypes = argtypes
            if result is None:
                cfn.restype = None
            elif result.kind == 'str':
                cfn.restype = ctypes.c_char_p
            elif result.kind == 'handle':
                cfn.restype = ctypes.c_void_p
            else:
                cfn.restype = result.ctype
            return cfn

        def call(*args, **kwargs):
            if 'cfn' not in state:
                state['cfn'] = bind()
            cfn = state['cfn']
            visible = [p for p in params if not isinstance(p[1], length)]
            if kwargs or len(args) > len(visible):
                if len(args) > len(visible):
                    raise TypeError('%s() takes %d positional arguments but %d were given' % (function.__name__, len(visible), len(args)))
                bound = dict(zip((p[0] for p in visible), args))
                for key, value in kwargs.items():
                    if key in bound or key not in {p[0] for p in visible}:
                        raise TypeError('%s() got an unexpected or repeated argument %r' % (function.__name__, key))
                    bound[key] = value
            else:
                bound = dict(zip((p[0] for p in visible), args))
            values, keep = {}, []
            for name, kind, default in visible:
                if name in bound:
                    values[name] = bound[name]
                elif default is not param_empty():
                    values[name] = default
                else:
                    raise TypeError('%s() missing required argument %r' % (function.__name__, name))
            converted = []
            stored = []                 # the first exception a callback raised during this call
            for name, kind, _ in params:
                if isinstance(kind, length):
                    target = next(k for n, k, _ in params if n == kind.name)
                    size = ctypes.sizeof(target.ctype.ctype) if isinstance(target, ptr) else 1
                    n = len(values[kind.name]) // size
                    low, high = kind.ctype.limits()
                    if not low <= n <= high:
                        raise OverflowError('length of %s does not fit %s' % (kind.name, kind.ctype))
                    converted.append(n)
                    continue
                value = values[name]
                if kind.kind == 'int':
                    if type(value) is not int:
                        raise TypeError('%s: %s must be an int' % (function.__name__, name))
                    low, high = kind.limits()
                    if not low <= value <= high:
                        raise OverflowError('%s: %s does not fit %s' % (function.__name__, name, kind))
                    converted.append(value)
                elif kind.kind == 'float':
                    if type(value) not in (int, float):
                        raise TypeError('%s: %s must be a float' % (function.__name__, name))
                    converted.append(float(value))
                elif kind.kind == 'bool':
                    if type(value) is not bool:
                        raise TypeError('%s: %s must be a bool' % (function.__name__, name))
                    converted.append(value)
                elif kind.kind == 'str':
                    if type(value) is not str:
                        raise TypeError('%s: %s must be a str' % (function.__name__, name))
                    data = value.encode('utf-8')
                    if b'\0' in data:
                        raise ValueError('embedded null character')
                    converted.append(data)
                elif kind.kind == 'handle':
                    if type(value) is not int or not 0 <= value < (1 << 64):
                        raise TypeError('%s: %s must be an address (int)' % (function.__name__, name))
                    converted.append(value)
                elif kind.kind == 'owned':
                    if not isinstance(value, kind.handle):
                        raise TypeError('%s: %s must be a %s handle' % (function.__name__, name, kind.handle._name))
                    value._check()
                    converted.append(value._p)
                elif kind.kind == 'bytes':
                    if type(value) is not bytes:
                        raise TypeError('%s: %s must be bytes' % (function.__name__, name))
                    if isinstance(kind, ptr) and len(value) % ctypes.sizeof(kind.ctype.ctype):
                        raise ValueError('%s: %s must hold a whole number of %s' % (function.__name__, name, kind.ctype))
                    converted.append(value)
                elif kind.kind == 'bytearray':
                    if type(value) is not bytearray:
                        raise TypeError('%s: %s must be a bytearray' % (function.__name__, name))
                    if isinstance(kind, ptr) and len(value) % ctypes.sizeof(kind.ctype.ctype):
                        raise ValueError('%s: %s must hold a whole number of %s' % (function.__name__, name, kind.ctype))
                    buffer = (ctypes.c_ubyte * len(value)).from_buffer(value)
                    keep.append(buffer)
                    converted.append(ctypes.addressof(buffer))
                elif kind.kind == 'callback':
                    trampoline = kind.cfunctype()(_trampoline(function.__name__, kind, _cb_function(function.__name__, name, kind, value), stored))
                    keep.append(trampoline)
                    converted.append(trampoline)
            ctypes.set_errno(0)
            rc = cfn(*converted)
            err = ctypes.get_errno()
            del keep[:]
            if stored:
                raise stored[0]
            if result is None:
                return None
            probe = (0 if rc is None else 1) if result.kind == 'str' else (rc or 0) if result.kind in ('handle', 'owned') else rc
            if check is not None and CHECKS[check](probe):
                failure = exc if exc is not None else (OSError if errno else RuntimeError)
                if errno:
                    if failure is OSError:
                        raise OSError(err, os.strerror(err))
                    raise failure('[Errno %d] %s' % (err, os.strerror(err)))
                raise failure('%s failed with %d' % (function.__name__, probe))
            if result.kind == 'str':
                return '' if rc is None else rc.decode('utf-8')
            if result.kind == 'handle':
                return rc or 0
            if result.kind == 'owned':
                return result.handle(rc or 0)
            return rc

        call.__name__ = function.__name__
        call.__qualname__ = function.__qualname__
        call.__doc__ = function.__doc__
        call.__wrapped__ = function
        call.__ail_extern__ = record
        return call

    return declare


_EXPORTED = []
_EXPORT_SCALARS = (int, float, bool, str, bytes)


def _export_type(annotation, *, result):
    """Check one @export annotation against the C-library type table (the one `ail build --lib` uses)."""
    import dataclasses
    import typing
    if annotation is None or annotation is type(None):
        return result
    if annotation in _EXPORT_SCALARS:
        return True
    if typing.get_origin(annotation) is list and typing.get_args(annotation) in ((int,), (float,)):
        return True
    if not result and isinstance(annotation, type) and dataclasses.is_dataclass(annotation):
        return all(f.type in (int, float, bool) for f in dataclasses.fields(annotation))
    return False


def export(function=None):
    """Mark a top-level typed function as part of the C library built by `ail build --lib NAME prog.py`.

        from ail_ffi import export

        @export
        def add(a: int, b: int) -> int:
            return a + b

    On CPython the decorator checks the annotations and returns the function unchanged, so the file
    runs as ordinary Python and is the reference the compiled library is compared against. Allowed
    types: int float bool str bytes list[int] list[float] (a result may also be None); a parameter may
    also be a dataclass whose fields are int, float or bool (a C struct passed by pointer). Every
    parameter and the result must be annotated; defaults, *args and **kwargs are refused.
    """
    def mark(fn):
        import inspect
        import typing
        if not inspect.isfunction(fn):
            raise TypeError('@export applies to a top-level function')
        signature = inspect.signature(fn)
        if any(p.default is not p.empty or p.kind is not p.POSITIONAL_OR_KEYWORD
               for p in signature.parameters.values()):
            raise TypeError('@export %s: plain parameters without defaults only' % fn.__name__)
        if signature.return_annotation is signature.empty:
            raise TypeError('@export %s: the result needs an annotation (-> None for no result)' % fn.__name__)
        hints = typing.get_type_hints(fn)
        for name in signature.parameters:
            if name not in hints or not _export_type(hints[name], result=False):
                raise TypeError('@export %s: parameter %s needs one of int float bool str bytes list[int] '
                                'list[float] or a dataclass of int/float/bool' % (fn.__name__, name))
        if not _export_type(hints.get('return'), result=True):
            raise TypeError('@export %s: the result must be int float bool str bytes list[int] list[float] or None'
                            % fn.__name__)
        _EXPORTED.append(fn)
        fn.__ail_export__ = True
        return fn
    return mark if function is None else mark(function)


def exports():
    """The functions marked with @export so far, in declaration order."""
    return list(_EXPORTED)


def param_empty():
    import inspect
    return inspect.Parameter.empty
