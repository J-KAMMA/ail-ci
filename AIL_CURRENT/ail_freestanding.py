"""Plain-Python meaning of AIL freestanding modules, so pure logic can run (and be compared) on CPython.

A freestanding module (docs/design/FREESTANDING.md) compiles to C for `-ffreestanding -nostdlib`.
Its pure parts -- integer arithmetic, structs, arrays, pointers into them -- also run here:

    import ail_freestanding
    crc = ail_freestanding.load('crc32.py')        # the module, with the compiled build's semantics
    crc.crc32_update(crc.u32(0), ail_freestanding.as_ptr(buf), crc.usize(n))

`load` rewrites the module's arithmetic so every `+ - * // % << >> & | ^ ~` and unary `-` keeps its
fixed width, wraps or traps exactly as the C build does (`@wrapping`, `@checked`, `wrapping(e)`,
`checked(e)`, `arithmetic("...")`), and coerces annotated locals, parameters, returns, fields and
elements to their types. A plain `import` of the module also works, with Python's unbounded ints.

What the C build does with hardware -- an address made from an integer, `asm(...)`, an `@extern`
function nobody provided -- raises `HardwareAccess` here. A trap (overflow under `@checked`, an
index outside an Array, division by zero, a shift count outside the width) raises `Trap`.
"""
import ast
import inspect
import sys
import types
from pathlib import Path

__all__ = ['u8', 'u16', 'u32', 'u64', 'i8', 'i16', 'i32', 'i64', 'usize', 'isize', 'Ptr', 'Array', 'struct',
           'extern', 'wrapping', 'checked', 'arithmetic', 'addr', 'addr_of', 'as_ptr', 'volatile_load',
           'volatile_store', 'asm', 'Trap', 'Fn', 'interrupt', 'packed', 'align', 'size_of', 'align_of']


class Trap(Exception):
    """What `__builtin_trap()` is in the compiled build."""


class HardwareAccess(Exception):
    """The operation needs real memory or a CPU instruction; run the compiled build."""


# ------------------------------------------------------------------------------------- integers

class _Fixed(int):
    BITS = 0
    SIGNED = False

    def __new__(cls, value=0):
        if isinstance(value, _Ptr):
            raise TypeError('%s() of a pointer; write addr(p)' % cls.__name__)
        value = int(value) & ((1 << cls.BITS) - 1)
        if cls.SIGNED and value >= 1 << (cls.BITS - 1):
            value -= 1 << cls.BITS
        return int.__new__(cls, value)

    @classmethod
    def fits(cls, value):
        lo = -(1 << (cls.BITS - 1)) if cls.SIGNED else 0
        hi = (1 << (cls.BITS - 1)) - 1 if cls.SIGNED else (1 << cls.BITS) - 1
        return lo <= value <= hi

    def __repr__(self):
        return '%s(%d)' % (type(self).__name__, int(self))


def _int_type(name, bits, signed):
    return type(name, (_Fixed,), {'BITS': bits, 'SIGNED': signed, '__module__': __name__})


u8, u16, u32, u64 = (_int_type('u%d' % b, b, False) for b in (8, 16, 32, 64))
i8, i16, i32, i64 = (_int_type('i%d' % b, b, True) for b in (8, 16, 32, 64))
usize = _int_type('usize', 64, False)
isize = _int_type('isize', 64, True)


def _width(a, b):
    ta = type(a) if isinstance(a, _Fixed) else None
    tb = type(b) if isinstance(b, _Fixed) else None
    if ta and tb and ta is not tb:
        raise TypeError('an operation mixes %s and %s; convert one side' % (ta.__name__, tb.__name__))
    return ta or tb


def _bin(op, a, b, mode):
    """`a op b` with the compiled build's meaning (the loader rewrites every binary operator to this)."""
    if isinstance(a, _Ptr) or isinstance(b, _Ptr):
        raise TypeError('arithmetic on a pointer; write p.offset(n)')
    x, y = int(a), int(b)
    t = None if op in ('<<', '>>') else _width(a, b)
    if op in ('<<', '>>'):
        t = type(a) if isinstance(a, _Fixed) else None
        if t is not None and not 0 <= y < t.BITS:
            raise Trap('shift count %d outside 0..%d' % (y, t.BITS - 1))
        r = x << y if op == '<<' else x >> y
        return t(r) if t else r
    if op in ('//', '%'):
        if y == 0:
            raise Trap('division by zero')
        r = x // y if op == '//' else x % y
    else:
        r = {'+': x + y, '-': x - y, '*': x * y, '&': x & y, '|': x | y, '^': x ^ y}[op]
    if t is None:
        return r
    if mode == 'check' and op in ('+', '-', '*', '//', '%') and not t.fits(r):
        raise Trap('%s overflow: %d %s %d' % (t.__name__, x, op, y))
    return t(r)


def _un(op, a, mode):
    if op == '+':
        return a
    t = type(a) if isinstance(a, _Fixed) else None
    r = -int(a) if op == '-' else ~int(a)
    if t is None:
        return r
    if mode == 'check' and op == '-' and not t.fits(r):
        raise Trap('%s overflow: -%d' % (t.__name__, int(a)))
    return t(r)


def _range(*bounds):
    t = None
    for b in bounds:
        if isinstance(b, _Fixed):
            t = t or type(b)
    t = t or usize
    for v in range(*(int(b) for b in bounds)):
        yield t(v)


# ------------------------------------------------------------------------- pointers and memory

class _PtrType:
    _cache = {}

    def __new__(cls, target):
        key = target if not isinstance(target, str) else ('name', target)
        if key not in cls._cache:
            obj = object.__new__(cls)
            obj.target = target
            cls._cache[key] = obj
        return cls._cache[key]

    def __call__(self, value):
        if isinstance(value, _Ptr):
            return _Ptr(value._obj, value._index, self, value._addr)
        value = int(value)
        return _Ptr(None, None, self, value)

    def __repr__(self):
        name = self.target if isinstance(self.target, str) else getattr(self.target, '__name__', repr(self.target))
        return 'Ptr[%s]' % name


class _PtrMeta(type):
    def __getitem__(cls, target):
        return _PtrType(target)


class Ptr(metaclass=_PtrMeta):
    """`Ptr[T]`: a typed pointer. Here it points into a struct or an Array object."""


class _Ptr:
    __slots__ = ('_obj', '_index', '_type', '_addr')

    def __init__(self, obj, index, ptype, address=None):
        object.__setattr__(self, '_obj', obj)
        object.__setattr__(self, '_index', index)
        object.__setattr__(self, '_type', ptype)
        object.__setattr__(self, '_addr', address)

    def _target(self):
        if self._obj is None:
            if self._addr == 0:
                raise Trap('null pointer dereference')
            raise HardwareAccess('memory at address %#x needs the compiled build' % self._addr)
        if self._index is None:
            return self._obj
        return self._obj[self._index]

    def __getattr__(self, name):
        return getattr(self._target(), name)

    def __setattr__(self, name, value):
        setattr(self._target(), name, value)

    def _cell(self, i):
        if self._obj is None:
            self._target()
        if self._index is None:
            if int(i) != 0:
                raise Trap('index %d past a single object' % int(i))
            return None
        return self._index + int(i)

    def __getitem__(self, i):
        cell = self._cell(i)
        return self._obj if cell is None else self._obj[cell]

    def __setitem__(self, i, value):
        cell = self._cell(i)
        if cell is None:
            raise TypeError('storing a whole struct through a pointer copies it; set the fields')
        self._obj[cell] = value

    def offset(self, n):
        if self._obj is None:
            raise HardwareAccess('address arithmetic on %#x needs the compiled build' % (self._addr or 0))
        if self._index is None:
            if int(n) != 0:
                raise Trap('offset past a single object')
            return self
        return _Ptr(self._obj, self._index + int(n), self._type)

    def __eq__(self, other):
        return isinstance(other, _Ptr) and self._obj is other._obj and self._index == other._index and self._addr == other._addr

    def __hash__(self):
        return hash((id(self._obj), self._index, self._addr))

    def __bool__(self):
        raise TypeError('a pointer as a condition; write addr(p) != 0')

    def __repr__(self):
        if self._obj is None:
            return '%r(%#x)' % (self._type, self._addr)
        return '<%r to %s%s>' % (self._type, type(self._obj).__name__, '' if self._index is None else '[%d]' % self._index)


def _null(ptype):
    return _Ptr(None, None, ptype, 0)


class _ArrayType:
    _cache = {}

    def __new__(cls, elem, n):
        key = (elem if not isinstance(elem, str) else ('name', elem), int(n))
        if key not in cls._cache:
            obj = object.__new__(cls)
            obj.elem, obj.n = elem, int(n)
            cls._cache[key] = obj
        return cls._cache[key]

    def __call__(self, values=None):
        return _Array(self, values)

    def __repr__(self):
        return 'Array[%s, %d]' % (getattr(self.elem, '__name__', repr(self.elem)), self.n)


class _ArrayMeta(type):
    def __getitem__(cls, key):
        elem, n = key
        return _ArrayType(elem, n)


class Array(metaclass=_ArrayMeta):
    """`Array[T, N]`: N elements of T, zeroed; `Array[T, N]([v0, v1, ...])` sets the first ones."""


class _Array:
    __slots__ = ('_type', '_items')

    def __init__(self, atype, values=None):
        self._type = atype
        self._items = [_zero(atype.elem) for _ in range(atype.n)]
        if values is not None:
            values = list(values)
            if len(values) > atype.n:
                raise TypeError('%d values for %r' % (len(values), atype))
            for i, v in enumerate(values):
                self._items[i] = _co(atype.elem, v)

    def _check(self, i):
        if isinstance(i, slice):
            raise TypeError('a slice makes a new list; use a Ptr and a length')
        i = int(i)
        if not 0 <= i < self._type.n:
            raise Trap('index %d outside %r' % (i, self._type))
        return i

    def __getitem__(self, i):
        return self._items[self._check(i)]

    def __setitem__(self, i, value):
        self._items[self._check(i)] = _co(self._type.elem, value)

    def __len__(self):
        return self._type.n

    def __iter__(self):
        raise TypeError('iterating an Array; write for i in range(len(a))')

    def __repr__(self):
        return '%r(%r)' % (self._type, self._items)


class _FnType:
    """`Fn[[u32], u32]`: a function pointer type. Values are Python callables (or the null pointer)."""
    _cache = {}

    def __new__(cls, params, ret):
        key = (tuple(params), ret)
        if key not in cls._cache:
            obj = object.__new__(cls)
            obj.params, obj.ret = key
            cls._cache[key] = obj
        return cls._cache[key]

    def __call__(self, value):
        """`Fn[...](0)` is the null pointer; an address has no function on CPython."""
        value = int(value)
        return _NullFn(self) if value == 0 else _FnAt(self, value)

    def __repr__(self):
        names = lambda ts: ', '.join(getattr(t, '__name__', repr(t)) for t in ts)
        return 'Fn[[%s], %s]' % (names(self.params), getattr(self.ret, '__name__', repr(self.ret)))


class _FnMeta(type):
    def __getitem__(cls, key):
        params, ret = key
        return _FnType(tuple(params), ret)


class Fn(metaclass=_FnMeta):
    """`Fn[[u32], u32]`: a pointer to a function; a module function name is a value of this type."""


class _NullFn:
    __slots__ = ('_type',)

    def __init__(self, ftype):
        self._type = ftype

    def __call__(self, *args):
        raise Trap('call through a null function pointer')

    def __eq__(self, other):
        return isinstance(other, _NullFn) and other._type is self._type

    def __hash__(self):
        return hash(('null', id(self._type)))

    def __bool__(self):
        raise TypeError('a function pointer as a condition; write addr(f) != 0')

    def __repr__(self):
        return '%r(0)' % (self._type,)


class _FnAt:
    __slots__ = ('_type', '_addr')

    def __init__(self, ftype, address):
        self._type, self._addr = ftype, address

    def __call__(self, *args):
        raise HardwareAccess('code at address %#x needs the compiled build' % self._addr)

    def __eq__(self, other):
        return isinstance(other, _FnAt) and other._addr == self._addr and other._type is self._type

    def __hash__(self):
        return hash((self._addr, id(self._type)))


def _resolve(t, where=None):
    if isinstance(t, str):
        module = sys.modules.get(getattr(where, '__module__', None) or '')
        found = getattr(module, t, None) if module else None
        if found is None and where is not None:
            found = getattr(where, '_ail_namespace', {}).get(t)
        if found is None:
            raise TypeError('unknown type %s' % t)
        return found
    return t


def _zero(t):
    t = _resolve(t)
    if isinstance(t, type) and issubclass(t, _Fixed):
        return t(0)
    if t is bool:
        return False
    if isinstance(t, _PtrType):
        return _null(t)
    if isinstance(t, _ArrayType):
        return t()
    if isinstance(t, _FnType):
        return _NullFn(t)
    if getattr(t, '_ail_struct', False):
        return t()
    raise TypeError('no zero value for %r' % (t,))


def _co(t, v):
    """Coerce `v` to the declared type `t` the way the compiler checks it."""
    if isinstance(t, str):
        t = _resolve(t)
    if isinstance(t, type) and issubclass(t, _Fixed):
        if isinstance(v, t):
            return v
        if isinstance(v, _Fixed):
            raise TypeError('a %s value where %s is expected; write %s(x)' % (type(v).__name__, t.__name__, t.__name__))
        if isinstance(v, bool) or not isinstance(v, int):
            raise TypeError('a %s where %s is expected' % (type(v).__name__, t.__name__))
        if not t.fits(v):
            raise TypeError('%d does not fit %s' % (v, t.__name__))
        return t(v)
    if t is bool:
        if not isinstance(v, bool):
            raise TypeError('a %s where bool is expected' % type(v).__name__)
        return v
    if isinstance(t, _PtrType):
        if not isinstance(v, _Ptr):
            raise TypeError('a %s where %r is expected' % (type(v).__name__, t))
        return v
    if isinstance(t, _ArrayType):
        if not isinstance(v, _Array) or v._type is not t:
            raise TypeError('a %s where %r is expected' % (type(v).__name__, t))
        return v
    if isinstance(t, _FnType):
        if isinstance(v, (_NullFn, _FnAt)):
            if v._type is not t:
                raise TypeError('%r where %r is expected' % (v._type, t))
            return v
        if not callable(v) or isinstance(v, (type, _Ptr)):
            raise TypeError('a %s where %r is expected' % (type(v).__name__, t))
        try:
            sig = inspect.signature(v)
        except (TypeError, ValueError):
            return v
        if not any(p.kind == p.VAR_POSITIONAL for p in sig.parameters.values()) and len(sig.parameters) != len(t.params):
            raise TypeError('a function of %d parameters where %r is expected' % (len(sig.parameters), t))
        return v
    if getattr(t, '_ail_struct', False):
        if not isinstance(v, t):
            raise TypeError('a %s where %s is expected' % (type(v).__name__, t.__name__))
        return v
    return v


def struct(cls):
    """`@struct class Ring: head: u32 ...` -- fields start at zero; `Ring(head=1)` sets some."""
    fields = dict(cls.__dict__.get('__annotations__', {}))

    def __init__(self, **values):
        for name, t in fields.items():
            object.__setattr__(self, name, _zero(_resolve(t, cls)))
        for name, v in values.items():
            setattr(self, name, v)

    def __setattr__(self, name, value):
        if name not in fields:
            raise AttributeError('%s has no field %s' % (cls.__name__, name))
        object.__setattr__(self, name, _co(_resolve(fields[name], cls), value))

    def __repr__(self):
        return '%s(%s)' % (cls.__name__, ', '.join('%s=%r' % (n, getattr(self, n)) for n in fields))

    cls.__init__, cls.__setattr__, cls.__repr__ = __init__, __setattr__, __repr__
    cls._ail_struct = True
    cls._ail_fields = fields
    return cls


def interrupt(function):
    """`@interrupt` on a handler taking a frame pointer (and an error code): the compiled build returns with iret.
    On CPython it is the plain function, so the logic around it can be called with a fake frame."""
    function._ail_interrupt = True
    return function


def packed(cls):
    """`@packed` on a @struct class: no padding between the fields (C `__attribute__((packed))`)."""
    cls._ail_packed = True
    return cls


def align(n):
    """`@align(16)` on a @struct class: the whole struct is aligned to n bytes."""
    def apply(cls):
        cls._ail_align = int(n)
        return cls
    return apply


def _layout(t, where=None):
    """(size, alignment) the way the 64-bit C build lays `t` out."""
    t = _resolve(t, where)
    if isinstance(t, type) and issubclass(t, _Fixed):
        return t.BITS // 8, t.BITS // 8
    if t is bool:
        return 1, 1
    if isinstance(t, (_PtrType, _FnType)):
        return 8, 8
    if isinstance(t, _ArrayType):
        size, alignment = _layout(t.elem, where)
        return size * t.n, alignment
    if getattr(t, '_ail_struct', False):
        offset, alignment = 0, 1
        for ft in t._ail_fields.values():
            size, fa = _layout(ft, t)
            if getattr(t, '_ail_packed', False):
                fa = 1
            offset = (offset + fa - 1) // fa * fa + size
            alignment = max(alignment, fa)
        alignment = max(alignment, getattr(t, '_ail_align', 1))
        return (offset + alignment - 1) // alignment * alignment, alignment
    raise TypeError('size_of() of %r' % (t,))


def size_of(t):
    return _layout(t)[0]


def align_of(t):
    return _layout(t)[1]


def addr_of(obj):
    if isinstance(obj, _Array):
        return _Ptr(obj, None, _PtrType(obj._type))
    if getattr(type(obj), '_ail_struct', False):
        return _Ptr(obj, None, _PtrType(type(obj)))
    raise TypeError('addr_of() of a %s; keep it in a struct field' % type(obj).__name__)


def as_ptr(array):
    if not isinstance(array, _Array):
        raise TypeError('as_ptr() of a %s' % type(array).__name__)
    return _Ptr(array, 0, _PtrType(array._type.elem))


def addr(p):
    if isinstance(p, _NullFn):
        return usize(0)
    if isinstance(p, _FnAt):
        return usize(p._addr)
    if callable(p) and not isinstance(p, (_Ptr, type)):
        raise HardwareAccess('a function has no address on CPython; run the compiled build')
    if not isinstance(p, _Ptr):
        raise TypeError('addr() of a %s' % type(p).__name__)
    if p._obj is not None:
        raise HardwareAccess('the address of a Python object has no meaning on CPython')
    return usize(p._addr)


def volatile_load(p):
    return p[0]


def volatile_store(p, value):
    p[0] = value


def asm(text, inputs=None, outputs=None, clobbers=None, volatile=True):
    """Inline assembly, with GCC operands: asm("outb %0, %1", inputs=[("a", v), ("Nd", port)]). Compiled build only."""
    raise HardwareAccess('asm(%r) needs the compiled build' % text)


_EXTERNS = {}


def provide(name, function):
    """Give an @extern function a Python body for a hosted run (a fake device, a recorder)."""
    _EXTERNS[name] = function


def extern(function):
    name = function.__name__

    def call(*args):
        if name not in _EXTERNS:
            raise HardwareAccess('%s is a C function; provide it with ail_freestanding.provide(%r, f)' % (name, name))
        return _EXTERNS[name](*args)
    call.__name__ = name
    call._ail_extern = True
    return call


def wrapping(x):
    """`@wrapping` on a function, or `wrapping(expr)`: + - * // % and unary - wrap at the width."""
    return x


def checked(x):
    """`@checked` on a function, or `checked(expr)`: + - * // % and unary - trap on overflow."""
    return x


def arithmetic(mode):
    """`arithmetic("checked")` or `arithmetic("wrapping")` at the top of a module: the default rule."""
    if mode not in ('checked', 'wrapping'):
        raise ValueError('arithmetic() takes "checked" or "wrapping"')


# ------------------------------------------------------------------------------------- the loader

_BIN = {ast.Add: '+', ast.Sub: '-', ast.Mult: '*', ast.FloorDiv: '//', ast.Mod: '%', ast.LShift: '<<',
        ast.RShift: '>>', ast.BitAnd: '&', ast.BitOr: '|', ast.BitXor: '^'}
_UN = {ast.USub: '-', ast.UAdd: '+', ast.Invert: '~'}


def _call(name, *args):
    return ast.Call(ast.Name(name, ast.Load()), list(args), [])


def _mode_of(decorators, default):
    for d in decorators:
        if isinstance(d, ast.Name) and d.id in ('wrapping', 'checked'):
            return 'wrap' if d.id == 'wrapping' else 'check'
    return default


class _Rewrite(ast.NodeTransformer):
    def __init__(self, module_mode, statics):
        self.mode = module_mode
        self.module_mode = module_mode
        self.statics = statics
        self.types = None           # name -> annotation node inside the current function
        self.ret = None

    def visit_FunctionDef(self, node):
        saved = self.mode, self.types, self.ret
        self.mode = _mode_of(node.decorator_list, self.module_mode)
        self.types = {}
        self.ret = node.returns
        coerce = []
        for arg in node.args.args:
            if arg.annotation is not None:
                self.types[arg.arg] = arg.annotation
                coerce.append(ast.Assign([ast.Name(arg.arg, ast.Store())],
                                         _call('_ail_co', arg.annotation, ast.Name(arg.arg, ast.Load()))))
        for st in ast.walk(node):
            if isinstance(st, ast.Global):
                for name in st.names:
                    if name in self.statics:
                        self.types[name] = self.statics[name]
        node.body = coerce + [self.visit(st) for st in node.body]
        node.body = [s for st in node.body for s in (st if isinstance(st, list) else [st])]
        self.mode, self.types, self.ret = saved
        return node

    def visit_ClassDef(self, node):
        node.body = [self.visit(st) if isinstance(st, ast.FunctionDef) else st for st in node.body]
        return node

    def visit_BinOp(self, node):
        self.generic_visit(node)
        op = _BIN.get(type(node.op))
        if op is None:
            return node
        return _call('_ail_bin', ast.Constant(op), node.left, node.right, ast.Constant(self.mode))

    def visit_UnaryOp(self, node):
        self.generic_visit(node)
        op = _UN.get(type(node.op))
        if op is None:
            return node
        return _call('_ail_un', ast.Constant(op), node.operand, ast.Constant(self.mode))

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id in ('wrapping', 'checked') and len(node.args) == 1 \
                and self.types is not None:
            saved = self.mode
            self.mode = 'wrap' if node.func.id == 'wrapping' else 'check'
            inner = self.visit(node.args[0])
            self.mode = saved
            return inner
        self.generic_visit(node)
        return node

    def visit_AnnAssign(self, node):
        if self.types is None:
            return node
        self.generic_visit(node)
        if isinstance(node.target, ast.Name):
            self.types[node.target.id] = node.annotation
            value = node.value if node.value is not None else ast.Constant(0)
            if node.value is None:
                return ast.Assign([ast.Name(node.target.id, ast.Store())], _call('_ail_zero', node.annotation))
            return ast.Assign([ast.Name(node.target.id, ast.Store())], _call('_ail_co', node.annotation, value))
        return node

    def visit_Assign(self, node):
        self.generic_visit(node)
        if self.types is not None and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id in self.types:
            node.value = _call('_ail_co', self.types[node.targets[0].id], node.value)
        return node

    def visit_AugAssign(self, node):
        self.generic_visit(node)
        op = _BIN.get(type(node.op))
        if op is None:
            return node
        load = ast.parse(ast.unparse(node.target), mode='eval').body
        value = _call('_ail_bin', ast.Constant(op), load, node.value, ast.Constant(self.mode))
        if self.types is not None and isinstance(node.target, ast.Name) and node.target.id in self.types:
            value = _call('_ail_co', self.types[node.target.id], value)
        return ast.Assign([node.target], value)

    def visit_Return(self, node):
        self.generic_visit(node)
        if node.value is not None and self.ret is not None and not (isinstance(self.ret, ast.Constant) and self.ret.value is None):
            node.value = _call('_ail_co', self.ret, node.value)
        return node


def load(path, name=None):
    """Load a freestanding module with the compiled build's integer semantics."""
    path = Path(path)
    source = path.read_text(encoding='utf-8-sig')
    tree = ast.parse(source, filename=str(path))
    module_mode = None
    statics = {}
    body = []
    for st in tree.body:
        if (isinstance(st, ast.Expr) and isinstance(st.value, ast.Call) and isinstance(st.value.func, ast.Name)
                and st.value.func.id == 'arithmetic' and st.value.args and isinstance(st.value.args[0], ast.Constant)):
            module_mode = 'wrap' if st.value.args[0].value == 'wrapping' else 'check'
        if isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name) and st.value is not None:
            statics[st.target.id] = st.annotation
            st = ast.Assign([ast.Name(st.target.id, ast.Store())], _call('_ail_co', st.annotation, st.value))
        body.append(st)
    tree.body = body
    rewriter = _Rewrite(module_mode, statics)
    tree.body = [rewriter.visit(st) if isinstance(st, (ast.FunctionDef, ast.ClassDef)) else _module_level(st, rewriter)
                 for st in tree.body]
    ast.fix_missing_locations(tree)
    name = name or path.stem
    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__dict__.update(_ail_bin=_bin, _ail_un=_un, _ail_co=_co, _ail_zero=_zero, range=_range)
    sys.modules[name] = module
    exec(compile(tree, str(path), 'exec'), module.__dict__)
    for value in list(module.__dict__.values()):
        if isinstance(value, type) and getattr(value, '_ail_struct', False):
            value._ail_namespace = module.__dict__
    return module


def _module_level(st, rewriter):
    """Module constants and static initializers: constant arithmetic folds exactly, as in the compiler."""
    return st
