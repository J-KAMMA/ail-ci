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
    raw views  c_const_void_p       const void *  (takes bytes)      c_mut_void_p   void *  (takes bytearray)
    length     length("buf", T)     the C parameter that carries len(buf) (elements for ptr/cptr); the call
                                    supplies it, it is not a parameter of the Python function
    results    any of the above except bytes/bytearray; `c_char_p` is copied and decoded (NULL gives "");
               `None` is void; a missing return annotation is refused

`@extern(...)` options: `lib` (library name for -l, or a path to a shared library relative to the
declaring file; None is the C library), `header` (checked against the real prototype at compile time;
without one the declaration is trusted and `ail check --ffi` says so), `symbol` (the C name when it differs
from the stub name), `pkg_config` (link flags from pkg-config, compile side only), `check` (one of
"negative", "nonzero", "null", "minus1": a result that means failure), `errno` (read errno right after the
call and put it in the message: `[Errno 2] No such file or directory`), `exc` (OSError by default with
errno, else RuntimeError; one of the built-in kinds AIL can raise: OSError ValueError RuntimeError KeyError
IndexError OverflowError EOFError), `sources` (a list of .c files beside the declaring file: the compiled
program links them into its adapter object, CPython builds them into a shared library on first use).

What the compiled program does differently (the declared differences):
  * `c_ulong`, `c_size_t` and `c_uint64` results above 2**63 - 1 come back as the negative int with the
    same bits in the compiled program (AIL ints are 64 bit); CPython gives the positive value.
  * a bytearray argument is copied in and out around the call in the compiled program; two names for one
    bytearray in one call see C's writes only after it returns.
  * `OSError` carries the message `[Errno N] text`; the compiled program has no `.errno` attribute and no
    FileNotFoundError subclass selection.
"""
import ctypes
import ctypes.util
import os
import sys

__all__ = ['extern', 'length', 'ptr', 'cptr', 'declarations', 'c_int', 'c_uint', 'c_short', 'c_ushort', 'c_long', 'c_ulong',
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
        if not isinstance(ctype, CType) or ctype.kind not in ('int', 'float', 'bool'):
            raise TypeError('%s(integer, float or bool C type)' % type(self).__name__)
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


_DECLARED = []


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
    if isinstance(annotation, (CType, length, ptr)):
        return annotation
    raise TypeError('unsupported FFI annotation: %r' % (annotation,))


def _load(lib, filename):
    if lib is None:
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
    if result is not None and result.kind in ('bytes', 'bytearray', 'length'):
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


def extern(lib=None, header=None, *, symbol=None, check=None, errno=False, exc=None, pkg_config=None, sources=None):
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
                    array = (ctypes.c_ubyte * len(value)).from_buffer(value)
                    keep.append(array)
                    converted.append(ctypes.addressof(array))
            ctypes.set_errno(0)
            rc = cfn(*converted)
            err = ctypes.get_errno()
            del keep[:]
            if result is None:
                return None
            probe = (0 if rc is None else 1) if result.kind == 'str' else (rc or 0) if result.kind == 'handle' else rc
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
            return rc

        call.__name__ = function.__name__
        call.__qualname__ = function.__qualname__
        call.__doc__ = function.__doc__
        call.__wrapped__ = function
        call.__ail_extern__ = record
        return call

    return declare


def param_empty():
    import inspect
    return inspect.Parameter.empty
