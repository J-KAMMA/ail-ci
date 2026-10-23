"""AIL freestanding mode: Python-syntax modules compiled to C for `-ffreestanding -nostdlib`.

`ail_chatgpt.py compile --freestanding mod.py -o mod.o` (or `-o mod.c`) builds a module of typed
functions, plain structs, fixed arrays, raw pointers and static storage into C that includes only the
freestanding C headers (<stdint.h>, <stddef.h>, <stdbool.h>), calls no runtime and references no libc
symbol. A header `mod.h` is written beside the output for the C code that links it. The design is
docs/design/FREESTANDING.md; the plain-Python meaning of every construct is ail_freestanding.py.

Everything outside the subset is refused by name with a "write instead:" hint (exit status 3).
The ordinary compile path never imports this module, so its C output is unchanged.
"""
import ast
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


class Refusal(Exception):
    def __init__(self, node, what, instead=None):
        self.line = getattr(node, 'lineno', None)
        self.what = what
        self.instead = instead
        super().__init__(self.text())

    def text(self, path=None):
        where = '%s:%s: ' % (path, self.line) if path and self.line else ('line %s: ' % self.line if self.line else '')
        return 'AIL freestanding: %s%s%s' % (where, self.what, '; write instead: ' + self.instead if self.instead else '')


# ---------------------------------------------------------------------------------------------- types

class Type:
    def is_int(self):
        return isinstance(self, IntT)


class IntT(Type):
    def __init__(self, name, bits, signed, ctype, cmin=None):
        self.name, self.bits, self.signed, self.ctype = name, bits, signed, ctype
        self.min = -(1 << (bits - 1)) if signed else 0
        self.max = (1 << (bits - 1)) - 1 if signed else (1 << bits) - 1
        self.cmin = cmin
        self.wide = 'uint32_t' if bits <= 32 else 'uint64_t'    # unsigned type the wrapping arithmetic uses

    def __repr__(self):
        return self.name

    def fits(self, value):
        return self.min <= value <= self.max

    def wrap(self, value):
        value &= (1 << self.bits) - 1
        if self.signed and value > self.max:
            value -= 1 << self.bits
        return value


class _Named(Type):
    def __init__(self, name, ctype):
        self.name, self.ctype = name, ctype

    def __repr__(self):
        return self.name


BOOL = _Named('bool', 'bool')
VOID = _Named('None', 'void')

def make_ints(ptr_bits):
    """The integer types of a target; `usize`/`isize` are pointer-sized (64 bits on x86-64, 32 on --m32)."""
    return {t.name: t for t in (
        IntT('u8', 8, False, 'uint8_t'), IntT('u16', 16, False, 'uint16_t'),
        IntT('u32', 32, False, 'uint32_t'), IntT('u64', 64, False, 'uint64_t'),
        IntT('i8', 8, True, 'int8_t', 'INT8_MIN'), IntT('i16', 16, True, 'int16_t', 'INT16_MIN'),
        IntT('i32', 32, True, 'int32_t', 'INT32_MIN'), IntT('i64', 64, True, 'int64_t', 'INT64_MIN'),
        IntT('usize', ptr_bits, False, 'uintptr_t'), IntT('isize', ptr_bits, True, 'intptr_t', 'INTPTR_MIN'))}


INTS = make_ints(64)
INTS32 = make_ints(32)
USIZE = INTS['usize']
TARGETS = {'x86_64': (INTS, 8), 'i386': (INTS32, 4)}


@dataclass(frozen=True)
class PtrT(Type):
    target: object

    @property
    def name(self):
        return 'Ptr[%s]' % self.target.name

    def __repr__(self):
        return self.name


@dataclass(frozen=True)
class ArrayT(Type):
    elem: object
    n: int

    @property
    def name(self):
        return 'Array[%s, %d]' % (self.elem.name, self.n)

    def __repr__(self):
        return self.name


@dataclass(frozen=True)
class FnT(Type):
    """A function pointer: `Fn[[u32, Ptr[u8]], u32]`, C `uint32_t (*)(uint32_t, uint8_t *)`."""
    params: tuple
    ret: object

    @property
    def name(self):
        return 'Fn[[%s], %s]' % (', '.join(p.name for p in self.params), self.ret.name)

    def __repr__(self):
        return self.name


class StructT(Type):
    def __init__(self, name, node):
        self.name, self.node = name, node
        self.fields = None          # name -> type, filled in declaration order
        self.methods = {}
        self.packed = False
        self.align = None           # an explicit @align(n)

    def __repr__(self):
        return self.name


class Lit:
    """An integer constant without a width yet; it takes the width of what it meets."""
    def __init__(self, value):
        self.value = value
    name = 'int literal'


def declare(t, name=''):
    """C declaration of `name` with type `t` (an abstract declarator when `name` is empty)."""
    if isinstance(t, PtrT):
        return declare(t.target, '*' + name)
    if isinstance(t, FnT):
        params = ', '.join(declare(p) for p in t.params) or 'void'
        return declare(t.ret, '(*%s)(%s)' % (name, params))
    if isinstance(t, ArrayT):
        inner = '(%s)' % name if name.startswith('*') else name
        return declare(t.elem, '%s[%d]' % (inner, t.n))
    base = t.ctype if isinstance(t, (IntT, _Named)) else t.name
    return '%s %s' % (base, name) if name else base


def lit_c(t, v):
    if t is BOOL:
        return 'true' if v else 'false'
    if not t.signed:
        return '((%s)%du%s)' % (t.ctype, v, 'll' if t.bits == 64 else '')
    if t.bits == 64:
        text = '(-9223372036854775807ll - 1)' if v == t.min else '%dll' % v
    else:
        text = '(%d)' % v if v < 0 else '%d' % v
    return '((%s)%s)' % (t.ctype, text)


C_RESERVED = set('''auto break case char const continue default do double else enum extern float for goto if
inline int long register restrict return short signed sizeof static struct switch typedef union unsigned void
volatile while _Bool _Complex _Imaginary _Alignas _Alignof _Atomic _Generic _Noreturn _Static_assert
_Thread_local bool true false asm typeof alignas alignof NULL errno main memcpy memmove memset memcmp
int8_t int16_t int32_t int64_t uint8_t uint16_t uint32_t uint64_t intptr_t uintptr_t size_t ptrdiff_t
offsetof'''.split())

INTRINSICS = {'u8', 'u16', 'u32', 'u64', 'i8', 'i16', 'i32', 'i64', 'usize', 'isize', 'Ptr', 'Array',
              'struct', 'extern', 'wrapping', 'checked', 'arithmetic', 'addr', 'addr_of', 'as_ptr',
              'volatile_load', 'volatile_store', 'asm', 'Trap', 'Fn', 'interrupt', 'packed', 'align',
              'size_of', 'align_of'}

RUNTIME_NAMES = {
    'print': 'write bytes to a device: a serial port through an @extern function, or a static Array[u16, 2000] VGA buffer',
    'input': 'read bytes from a device through an @extern function or volatile_load',
    'open': 'a driver: the kernel has no files until it has one',
    'str': 'an Array[u8, N] of bytes with a length field',
    'list': 'Array[T, N] with a count field',
    'dict': 'a fixed Array[T, N] table searched by key',
    'set': 'a bitmap in an Array[u64, N]',
    'tuple': 'a @struct class with one field per element',
    'bytes': 'Array[u8, N]',
    'bytearray': 'Array[u8, N]',
    'float': 'fixed-point integers (for example a value times 1000 in an i64)',
    'int': 'a fixed-width conversion such as u32(x) or i64(x)',
    'range': 'range only as the iterable of a for loop',
    'isinstance': 'a kind field in the struct',
    'super': 'composition: put the base struct in a field',
    'object': 'a @struct class',
    'abs': 'x if x >= 0 else -x (under @checked or @wrapping)',
    'min': 'a if a < b else b',
    'max': 'a if a > b else b',
    'sum': 'a for loop over range(len(xs))',
    'enumerate': 'for i in range(len(xs))',
    'zip': 'for i in range(n) indexing both arrays',
    'sorted': 'an in-place sort over an Array',
    'id': 'addr(addr_of(x))',
    'hash': 'an explicit hash function over the fields',
    'iter': 'for i in range(n)',
    'next': 'an index field',
    'getattr': 'the field by name: x.field',
    'setattr': 'x.field = value',
    'type': 'a kind field in the struct',
    'repr': 'format digits into an Array[u8, N] yourself',
    'format': 'format digits into an Array[u8, N] yourself',
    'chr': 'the code as a u8',
    'ord': 'the byte value as a u8',
    'divmod': 'q = a // b and r = a % b',
    'pow': 'a loop or a shift',
    'round': 'integer arithmetic',
    'exit': 'return from kernel_main, or a halt loop with asm("hlt")',
}

ASM_INPUTS = {'r', 'q', 'a', 'b', 'c', 'd', 'S', 'D', 'i', 'n', 'N', 'Nd', 'm'}
ASM_OUTPUTS = {'=r', '=q', '=a', '=b', '=c', '=d', '=S', '=D', '=m', '=&r', '=&a',
               '+r', '+q', '+a', '+b', '+c', '+d', '+S', '+D', '+m'}
_ASM_COMMON = ['memory', 'cc']
ASM_CLOBBERS_X64 = set(_ASM_COMMON + ['rax', 'rbx', 'rcx', 'rdx', 'rsi', 'rdi'] + ['r%d' % i for i in range(8, 16)])
ASM_CLOBBERS_I386 = set(_ASM_COMMON + ['eax', 'ebx', 'ecx', 'edx', 'esi', 'edi'])

ARITH = ('+', '-', '*', '//', '%')
BINOPS = {ast.Add: '+', ast.Sub: '-', ast.Mult: '*', ast.FloorDiv: '//', ast.Mod: '%', ast.LShift: '<<',
          ast.RShift: '>>', ast.BitAnd: '&', ast.BitOr: '|', ast.BitXor: '^'}
CMPOPS = {ast.Lt: '<', ast.LtE: '<=', ast.Gt: '>', ast.GtE: '>=', ast.Eq: '==', ast.NotEq: '!='}
MODE_HINT = ('@wrapping or @checked on the function, wrapping(expr) or checked(expr) around it, '
             'or arithmetic("checked") at the top of the module')


def _fold(op, a, b, node):
    if op in ('//', '%') and b == 0:
        raise Refusal(node, 'division by the constant zero')
    if op in ('<<', '>>') and b < 0:
        raise Refusal(node, 'a negative shift count')
    if op == '<<' and b > 64:
        raise Refusal(node, 'a constant shift count above 64')
    return {'+': lambda: a + b, '-': lambda: a - b, '*': lambda: a * b, '//': lambda: a // b,
            '%': lambda: a % b, '<<': lambda: a << b, '>>': lambda: a >> b, '&': lambda: a & b,
            '|': lambda: a | b, '^': lambda: a ^ b}[op]()


class Val:
    def __init__(self, c, t, lvalue=False, pure=False):
        self.c, self.t, self.lvalue, self.pure = c, t, lvalue, pure

    @property
    def lit(self):
        return isinstance(self.t, Lit)


def lit(value):
    return Val('', Lit(value), pure=True)


# ------------------------------------------------------------------------------------------- checker

class Function:
    def __init__(self, name, cname, node, params, ret, mode, owner=None, extern=False, interrupt=False):
        self.name, self.cname, self.node, self.params, self.ret = name, cname, node, params, ret
        self.mode, self.owner, self.extern, self.interrupt = mode, owner, extern, interrupt
        self.exported = not name.startswith('_')

    def prototype(self):
        params = ', '.join(declare(t, n) for n, t in self.params) or 'void'
        return ('__attribute__((interrupt)) ' if self.interrupt else '') + declare(self.ret, '%s(%s)' % (self.cname, params))

    def value_type(self):
        """The type of the function as a value: a function pointer."""
        return FnT(tuple(t for _, t in self.params), self.ret)


class Module:
    def __init__(self, source, path='<module>', target='x86_64'):
        self.path = path
        self.target = target
        self.ints, self.ptr_bytes = TARGETS[target]
        self.usize = self.ints['usize']
        self.interrupts = False
        self.tree = ast.parse(source, filename=str(path))
        self.imported = set()
        self.star = False
        self.consts = {}           # name -> Val (literal or typed constant)
        self.statics = {}          # name -> (type, init C text or None, node)
        self.structs = {}          # name -> StructT, declaration order
        self.funcs = {}            # name -> Function (module functions and externs)
        self.mode = None
        self.helpers = {}          # name -> C text
        self.out = []

    # -- names
    def need(self, node, name):
        if name in INTRINSICS and not self.star and name not in self.imported:
            raise Refusal(node, '%s is not imported, so CPython cannot run the module' % name,
                          'from ail_freestanding import %s' % name)

    def check_name(self, node, name, what):
        if name in C_RESERVED or name.startswith(('ail_fs_', '__')):
            raise Refusal(node, '%s name %r is reserved in the generated C' % (what, name), '%s_' % name.strip('_'))
        if not name.isascii():
            raise Refusal(node, '%s name %r is not ASCII' % (what, name), 'an ASCII name')

    # -- types
    def ann(self, node, *, ret=False):
        if node is None:
            if ret:
                return VOID
            raise Refusal(None, 'a missing annotation')
        if isinstance(node, ast.Constant) and node.value is None and ret:
            return VOID
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return self.ann(ast.parse(node.value, mode='eval').body)
        if isinstance(node, ast.Name):
            name = node.id
            if name in INTS:
                self.need(node, name)
                return self.ints[name]
            if name == 'bool':
                return BOOL
            if name in self.structs:
                return self.structs[name]
            if name == 'int':
                raise Refusal(node, 'the annotation int has no fixed width', 'u8, u16, u32, u64, i8, i16, i32, i64 or usize')
            if name == 'float':
                raise Refusal(node, 'floats are off in freestanding mode (no FPU state is saved)', RUNTIME_NAMES['float'])
            if name in RUNTIME_NAMES:
                raise Refusal(node, 'the type %s needs the runtime' % name, RUNTIME_NAMES[name])
            raise Refusal(node, 'unknown type %s' % name, 'a fixed-width int, bool, Ptr[T], Array[T, N] or a @struct class')
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
            head = node.value.id
            if head == 'Ptr':
                self.need(node, 'Ptr')
                target = self.ann(node.slice)
                if target is VOID:
                    raise Refusal(node, 'Ptr[None]', 'Ptr[u8] for untyped bytes')
                return PtrT(target)
            if head == 'Array':
                self.need(node, 'Array')
                if not (isinstance(node.slice, ast.Tuple) and len(node.slice.elts) == 2):
                    raise Refusal(node, 'Array needs an element type and a length', 'Array[u8, 4096]')
                elem = self.ann(node.slice.elts[0])
                n = self.const_int(node.slice.elts[1])
                if n <= 0:
                    raise Refusal(node, 'an Array length must be positive')
                return ArrayT(elem, n)
            if head == 'Fn':
                self.need(node, 'Fn')
                sl = node.slice
                if not (isinstance(sl, ast.Tuple) and len(sl.elts) == 2 and isinstance(sl.elts[0], ast.List)):
                    raise Refusal(node, 'Fn needs a parameter list and a result', 'Fn[[u32], u32] or Fn[[], None]')
                params = tuple(self.ann(e) for e in sl.elts[0].elts)
                ret = self.ann(sl.elts[1], ret=True)
                for t in (*params, ret):
                    if isinstance(t, (StructT, ArrayT)):
                        raise Refusal(node, 'a function pointer type that passes a %s by value' % t.name,
                                      'Ptr[%s] and addr_of(x) at the call' % t.name)
                return FnT(params, ret)
            if head == 'Callable':
                raise Refusal(node, 'the type Callable needs the runtime', 'Fn[[u32], u32] (a plain C function pointer)')
            if head in RUNTIME_NAMES or head in ('List', 'Dict', 'Optional', 'Tuple'):
                raise Refusal(node, 'the type %s needs the runtime' % head, RUNTIME_NAMES.get(head.lower(), 'Array[T, N] or a @struct class'))
        if isinstance(node, ast.Attribute):
            raise Refusal(node, 'a qualified type name', 'from ail_freestanding import u32, Ptr, ... and use the bare name')
        raise Refusal(node, 'an unsupported annotation %s' % ast.unparse(node))

    def const_int(self, node):
        v = self.expr(node, None)
        if not v.lit:
            raise Refusal(node, 'a length or initializer that is not a constant', 'an integer literal or a module constant')
        return v.t.value

    # -- module
    def check(self):
        body = self.tree.body
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
            body = body[1:]
        # imports first, then struct names (Ptr["Node"] may name a later struct)
        for st in body:
            if isinstance(st, ast.ClassDef):
                self.check_name(st, st.name, 'struct')
                self.structs[st.name] = StructT(st.name, st)
        pending = []
        for st in body:
            if isinstance(st, ast.ImportFrom):
                if st.module == '__future__':
                    continue
                if st.module != 'ail_freestanding':
                    raise Refusal(st, 'importing %s needs the runtime' % st.module,
                                  'only from ail_freestanding import ...; pass other modules\' data through Ptr arguments')
                for alias in st.names:
                    if alias.name == '*':
                        self.star = True
                    elif alias.asname:
                        raise Refusal(st, 'renaming %s on import' % alias.name, 'from ail_freestanding import %s' % alias.name)
                    else:
                        self.imported.add(alias.name)
            elif isinstance(st, ast.Import):
                raise Refusal(st, 'import %s' % ', '.join(a.name for a in st.names),
                              'from ail_freestanding import u32, Ptr, ...')
            elif isinstance(st, ast.Assign):
                self.module_const(st)
            elif isinstance(st, ast.AnnAssign):
                self.module_static(st)
            elif isinstance(st, ast.ClassDef):
                self.struct(st)
            elif isinstance(st, ast.FunctionDef):
                pending.append(st)
                self.signature(st)
            elif isinstance(st, ast.Expr) and isinstance(st.value, ast.Call) and isinstance(st.value.func, ast.Name) \
                    and st.value.func.id == 'arithmetic':
                self.need(st, 'arithmetic')
                arg = st.value.args[0] if len(st.value.args) == 1 else None
                if not (isinstance(arg, ast.Constant) and arg.value in ('wrapping', 'checked')):
                    raise Refusal(st, 'arithmetic() takes "wrapping" or "checked"', 'arithmetic("checked")')
                self.mode = 'wrap' if arg.value == 'wrapping' else 'check'
            elif isinstance(st, ast.If) and _is_main_guard(st):
                continue        # hosted-only code: CPython runs it, the freestanding build leaves it out
            elif isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant) and isinstance(st.value.value, str):
                continue
            else:
                self.refuse_statement(st, module=True)
        for st in body:
            if isinstance(st, ast.ClassDef):
                for item in st.body:
                    if isinstance(item, ast.FunctionDef):
                        self.function(self.structs[st.name].methods[item.name])
        for st in pending:
            fn = self.funcs[st.name]
            if not fn.extern:
                self.function(fn)

    def module_const(self, st):
        if len(st.targets) != 1 or not isinstance(st.targets[0], ast.Name):
            raise Refusal(st, 'a module-level assignment that is not NAME = constant',
                          'NAME = 4096 for a constant, or name: u32 = 0 for static storage')
        name = st.targets[0].id
        self.check_name(st, name, 'constant')
        self.taken(st, name)
        v = self.expr(st.value, None)
        if not v.pure:
            raise Refusal(st, 'module constant %s is not a constant expression' % name,
                          '%s: <type> = ... for static storage set at run time by a function' % name)
        self.consts[name] = v

    def taken(self, node, name):
        if name in self.consts or name in self.statics or name in self.funcs or name in INTRINSICS:
            raise Refusal(node, 'the name %s is defined twice' % name, 'a distinct name')

    def module_static(self, st):
        if not isinstance(st.target, ast.Name):
            raise Refusal(st, 'a static that is not a plain name')
        name = st.target.id
        self.check_name(st, name, 'static')
        self.taken(st, name)
        t = self.ann(st.annotation)
        if st.value is None:
            raise Refusal(st, 'static %s has no initializer' % name, '%s: %s = %s' % (name, t.name, _zero_spelling(t)))
        init = self.static_init(st.value, t)
        self.statics[name] = (t, init, st)

    def static_init(self, node, t):
        if isinstance(t, (StructT, ArrayT)):
            return self.aggregate_init(node, t, static=True)
        v = self.coerce(self.expr(node, t), t, node)
        if not v.pure:
            raise Refusal(node, 'a static initializer that is not a constant', 'a constant, then set it in an init function')
        return v.c

    def aggregate_init(self, node, t, static):
        """`Ring()` / `Ring(head=1)` / `Array[u8, 4]()` / `Array[u8, 4]([1, 2])` -> list of (C path, Val) and the type check."""
        if not isinstance(node, ast.Call):
            raise Refusal(node, 'a %s value that is not a new one' % t.name,
                          '%s %s; copying a struct or array is not part of the subset (CPython would share it)' % (
                              'a new one:', _zero_spelling(t)))
        made = self.ann(node.func) if isinstance(node.func, ast.Subscript) else (
            self.structs.get(node.func.id) if isinstance(node.func, ast.Name) else None)
        if made is None or made != t:
            raise Refusal(node, 'an initializer that does not make a %s' % t.name, _zero_spelling(t))
        if isinstance(t, StructT):
            if node.args:
                raise Refusal(node, 'positional struct fields', '%s(field=value, ...)' % t.name)
            items = []
            for kw in node.keywords:
                if kw.arg not in t.fields:
                    raise Refusal(node, '%s has no field %s' % (t.name, kw.arg))
                ft = t.fields[kw.arg]
                if isinstance(ft, (StructT, ArrayT)):
                    raise Refusal(node, 'an aggregate field initializer', 'set the field after construction')
                items.append((kw.arg, self.coerce(self.expr(kw.value, ft), ft, kw.value)))
            if static:
                if any(not v.pure for _, v in items):
                    raise Refusal(node, 'a static initializer that is not a constant')
                return '{%s}' % ', '.join('.%s = %s' % (k, v.c) for k, v in items) if items else '{0}'
            return items
        if node.keywords or len(node.args) > 1:
            raise Refusal(node, 'an Array initializer other than a list of values', 'Array[T, N]() or Array[T, N]([1, 2, 3])')
        items = []
        if node.args:
            lst = node.args[0]
            if isinstance(lst, ast.Constant) and isinstance(lst.value, bytes):
                u8 = self.ints['u8']
                if t.elem is not u8:
                    raise Refusal(node, 'a bytes initializer for %s' % t.name, 'Array[u8, N](b"text") or a list of values')
                if len(lst.value) != t.n:
                    raise Refusal(node, '%d bytes for %s (the length must match, so that len() is the text length)' % (
                        len(lst.value), t.name), 'Array[u8, %d](b"...")' % len(lst.value))
                items = [(i, Val(lit_c(u8, b), u8, pure=True)) for i, b in enumerate(lst.value)]
            else:
                if not isinstance(lst, ast.List):
                    raise Refusal(node, 'an Array initializer other than a list literal', 'Array[T, N]([1, 2, 3])')
                if len(lst.elts) > t.n:
                    raise Refusal(node, '%d values for %s' % (len(lst.elts), t.name))
                if isinstance(t.elem, (StructT, ArrayT)):
                    raise Refusal(node, 'a list initializer for an Array of aggregates', 'Array[T, N]() and set the elements')
                items = [(i, self.coerce(self.expr(e, t.elem), t.elem, e)) for i, e in enumerate(lst.elts)]
        if static:
            if any(not v.pure for _, v in items):
                raise Refusal(node, 'a static initializer that is not a constant')
            return '{%s}' % ', '.join(v.c for _, v in items) if items else '{0}'
        return items

    def struct(self, st):
        s = self.structs[st.name]
        self.need(st, 'struct')
        if st.bases or st.keywords:
            raise Refusal(st, 'struct %s inherits' % st.name, 'composition: put the other struct in a field')
        is_struct = False
        for d in st.decorator_list:
            if isinstance(d, ast.Name) and d.id == 'struct':
                is_struct = True
            elif isinstance(d, ast.Name) and d.id == 'packed':
                self.need(d, 'packed')
                s.packed = True
            elif isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == 'align':
                self.need(d, 'align')
                n = d.args[0].value if len(d.args) == 1 and not d.keywords and isinstance(d.args[0], ast.Constant)                     and isinstance(d.args[0].value, int) and not isinstance(d.args[0].value, bool) else None
                if n is None or n < 1 or n > 4096 or n & (n - 1):
                    raise Refusal(d, '@align takes a power of two from 1 to 4096 as an integer literal', '@align(16)')
                s.align = n
            else:
                raise Refusal(st, 'the class decorator %s' % ast.unparse(d), '@struct, with @packed and @align(n) if the layout needs it')
        if not is_struct:
            raise Refusal(st, 'class %s is not a @struct' % st.name,
                          '@struct above the class; the plain-Python shim gives it the zeroed fields')
        s.fields = {}
        for item in st.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                if item.value is not None:
                    raise Refusal(item, 'a field default', 'fields start at zero; pass Ring(field=value)')
                self.check_name(item, item.target.id, 'field')
                ft = self.ann(item.annotation)
                if ft is s or (isinstance(ft, StructT) and ft.fields is None):
                    raise Refusal(item, 'field %s holds a struct that is not complete yet' % item.target.id,
                                  'Ptr["%s"] for a link, or declare the inner struct first' % ft.name)
                s.fields[item.target.id] = ft
            elif isinstance(item, ast.FunctionDef):
                if item.name.startswith('__'):
                    raise Refusal(item, 'the special method %s needs the object runtime' % item.name,
                                  'fields start at zero; write a module function that sets them' if item.name == '__init__'
                                  else 'an ordinary method or function')
                self.check_name(item, item.name, 'method')
                cname = '%s_%s' % (st.name, item.name)
                if cname in self.funcs or cname in self.statics:
                    raise Refusal(item, 'method %s.%s collides with %s' % (st.name, item.name, cname))
                s.methods[item.name] = self.signature(item, owner=s)
            elif isinstance(item, ast.Pass) or (isinstance(item, ast.Expr) and isinstance(item.value, ast.Constant)
                                                 and isinstance(item.value.value, str)):
                continue
            else:
                raise Refusal(item, 'a class body statement other than a field or a method',
                              'name: type fields and def methods')
        if not s.fields:
            raise Refusal(st, 'struct %s has no fields' % st.name)
        s.size, s.alignment = self.layout(s)

    def layout(self, t):
        """(size, alignment) in bytes exactly as the C compiler lays `t` out (the output asserts it with _Static_assert)."""
        if isinstance(t, IntT):
            return t.bits // 8, (4 if self.target == 'i386' and t.bits == 64 else t.bits // 8)
        if t is BOOL:
            return 1, 1
        if isinstance(t, (PtrT, FnT)):
            return self.ptr_bytes, self.ptr_bytes
        if isinstance(t, ArrayT):
            size, align = self.layout(t.elem)
            return size * t.n, align
        if isinstance(t, StructT):
            if t.fields is None:
                raise Refusal(t.node, 'the size of %s is not known yet' % t.name, 'declare the struct before using its size')
            offset, align = 0, 1
            for ft in t.fields.values():
                size, fa = self.layout(ft)
                if t.packed:
                    fa = 1
                offset = (offset + fa - 1) // fa * fa + size
                align = max(align, fa)
            if t.align:
                align = max(align, t.align)
            return (offset + align - 1) // align * align, align
        raise Refusal(None, 'the size of %s' % getattr(t, 'name', t))

    def signature(self, st, owner=None):
        name = st.name
        if owner is None:
            self.check_name(st, name, 'function')
            self.taken(st, name)
        mode, extern, interrupt = self.mode, False, False
        for d in st.decorator_list:
            if isinstance(d, ast.Name) and d.id in ('wrapping', 'checked'):
                self.need(d, d.id)
                mode = 'wrap' if d.id == 'wrapping' else 'check'
            elif isinstance(d, ast.Name) and d.id == 'extern' and owner is None:
                self.need(d, 'extern')
                extern = True
            elif isinstance(d, ast.Name) and d.id == 'interrupt' and owner is None:
                self.need(d, 'interrupt')
                interrupt = True
            else:
                raise Refusal(st, 'the decorator %s' % ast.unparse(d), '@wrapping, @checked, @extern or @interrupt')
        a = st.args
        if a.vararg or a.kwarg or a.kwonlyargs or a.defaults or a.kw_defaults or a.posonlyargs:
            raise Refusal(st, 'defaults, *args, **kwargs or keyword-only parameters', 'plain positional parameters')
        params = []
        args = a.args
        if owner is not None:
            if not args or args[0].arg != 'self' or args[0].annotation is not None:
                raise Refusal(st, 'method %s needs an unannotated self first' % name, 'def %s(self, ...)' % name)
            params.append(('self', PtrT(owner)))
            args = args[1:]
        for arg in args:
            self.check_name(st, arg.arg, 'parameter')
            if arg.annotation is None:
                raise Refusal(st, 'parameter %s of %s has no type' % (arg.arg, name), '%s: u32' % arg.arg)
            t = self.ann(arg.annotation)
            if isinstance(t, (StructT, ArrayT)):
                raise Refusal(st, 'parameter %s takes a %s by value (C copies it, CPython shares it)' % (arg.arg, t.name),
                              '%s: Ptr[%s] and addr_of(x) at the call' % (arg.arg, t.name))
            params.append((arg.arg, t))
        ret = self.ann(st.returns, ret=True)
        if isinstance(ret, (StructT, ArrayT)):
            raise Refusal(st, '%s returns a %s by value' % (name, ret.name), 'a Ptr[%s] parameter the function fills' % ret.name)
        if extern:
            body = [s for s in st.body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))]
            if body and not (len(body) == 1 and isinstance(body[0], ast.Pass)):
                raise Refusal(st, 'an @extern function with a body', 'def %s(...) -> ...: ... (the C side defines it)' % name)
        if interrupt:
            ok = (len(params) in (1, 2) and isinstance(params[0][1], PtrT) and isinstance(params[0][1].target, StructT)
                  and (len(params) == 1 or params[1][1] is self.usize) and ret is VOID and not extern)
            if not ok:
                raise Refusal(st, '@interrupt %s must be def %s(frame: Ptr[Frame]) -> None, or (frame: Ptr[Frame], error: usize) '
                                  'for an exception that pushes an error code' % (name, name),
                              'a @struct Frame with ip, cs, flags, sp, ss as usize fields')
            self.interrupts = True
        cname = '%s_%s' % (owner.name, name) if owner else name
        fn = Function(name, cname, st, params, ret, mode, owner, extern, interrupt)
        if owner is None:
            self.funcs[name] = fn
        return fn

    def refuse_statement(self, st, module=False):
        kinds = {
            ast.Try: ('exceptions need the runtime', 'return an error code (for example a u32 status) and check it'),
            ast.Raise: ('raise needs the runtime', 'return an error code, or assert for a fatal trap'),
            ast.With: ('with needs the runtime', 'explicit calls before and after'),
            ast.Delete: ('del needs the runtime', 'set the field or element to zero'),
            ast.AsyncFunctionDef: ('async functions need the runtime', 'a state machine in a struct'),
            ast.Nonlocal: ('nonlocal needs closures', 'a Ptr parameter'),
            ast.Import: ('import needs the runtime', 'from ail_freestanding import ...'),
            ast.AsyncFor: ('async for needs the runtime', 'for i in range(n)'),
            ast.AsyncWith: ('async with needs the runtime', 'explicit calls'),
        }
        for kind, (what, instead) in kinds.items():
            if isinstance(st, kind):
                raise Refusal(st, what, instead)
        if isinstance(st, ast.FunctionDef):
            raise Refusal(st, 'a nested function needs closures', 'a module-level function with the captured values as parameters')
        if isinstance(st, ast.ClassDef):
            raise Refusal(st, 'a class inside a function', 'a @struct class at module level')
        if module:
            raise Refusal(st, 'a module-level %s statement runs at import time, and a kernel has no import' % type(st).__name__.lower(),
                          'module constants (NAME = 1), statics (name: u32 = 0) and an init function the entry stub calls')
        raise Refusal(st, 'the statement %s' % type(st).__name__)

    # -- functions
    def function(self, fn):
        self.fn = fn
        self.locals = dict(fn.params)
        self.globals = set()
        self.decl_order = []
        self.tmp = 0
        self.loop = 0
        body = fn.node.body
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
            body = body[1:]
        for st in body:
            if isinstance(st, ast.Global):
                for name in st.names:
                    if name not in self.statics:
                        raise Refusal(st, 'global %s does not name a static' % name, '%s: u32 = 0 at module level' % name)
                    self.globals.add(name)
        lines = self.block(body, 1, top=True)
        if fn.ret is not VOID and not _always_returns(body):
            raise Refusal(fn.node, '%s can reach its end without returning a %s (CPython would return None)' % (fn.name, fn.ret.name),
                          'a return at the end')
        head = ('static ' if not fn.exported else '') + fn.prototype()
        decls = ['    %s = %s;' % (declare(t, n), _zero_spelling_c(t)) for n, t in self.decl_order]
        self.out.append('%s\n{\n%s}\n' % (head, ''.join(l + '\n' for l in decls + lines)))

    def new_local(self, node, name, t):
        self.check_name(node, name, 'local')
        if name in self.statics or name in self.consts or name in self.funcs or name in INTRINSICS or name in self.structs:
            raise Refusal(node, 'local %s hides a module name' % name,
                          ('global %s, to assign the static' % name) if name in self.statics else 'a different local name')
        self.locals[name] = t
        self.decl_order.append((name, t))

    def block(self, body, depth, top=False):
        lines = []
        for st in body:
            lines += self.stmt(st, depth, top)
        return lines

    def stmt(self, st, d, top):
        pad = '    ' * d
        line = getattr(st, 'lineno', 0)
        mark = []
        if isinstance(st, ast.Expr):
            if isinstance(st.value, ast.Constant) and isinstance(st.value.value, str):
                return []
            if isinstance(st.value, ast.Constant) and st.value.value is Ellipsis:
                return []
            if not isinstance(st.value, ast.Call):
                self.expr(st.value, None)       # a yield, a list ... is refused by name
                raise Refusal(st, 'an expression statement that is not a call', 'assign the value or drop the line')
            if isinstance(st.value.func, ast.Name) and st.value.func.id == 'asm':
                return mark + [pad + self.asm(st.value)]
            v = self.expr(st.value, None, statement=True)
            return mark + [pad + ('(void)%s;' % v.c if v.t is not VOID else '%s;' % v.c)]
        if isinstance(st, ast.Pass):
            return []
        if isinstance(st, ast.Global):
            return []
        if isinstance(st, ast.Return):
            if self.fn.ret is VOID:
                if st.value is not None:
                    raise Refusal(st, '%s returns None but this return has a value' % self.fn.name, '-> %s in the signature' % self.expr(st.value, None).t.name)
                return [pad + 'return;']
            if st.value is None:
                raise Refusal(st, 'a bare return in a function that returns %s' % self.fn.ret.name)
            v = self.coerce(self.expr(st.value, self.fn.ret), self.fn.ret, st.value)
            return [pad + 'return %s;' % v.c]
        if isinstance(st, ast.AnnAssign):
            if not isinstance(st.target, ast.Name):
                raise Refusal(st, 'an annotation on something that is not a local name')
            name = st.target.id
            t = self.ann(st.annotation)
            if name in self.locals:
                if self.locals[name] != t:
                    raise Refusal(st, '%s was a %s and is now declared %s' % (name, self.locals[name].name, t.name), 'a new name')
                if isinstance(t, (StructT, ArrayT)):
                    raise Refusal(st, '%s is declared twice' % name, 'one declaration at the top of the function')
            else:
                if isinstance(t, (StructT, ArrayT)) and not top:
                    raise Refusal(st, 'a %s local inside a block (CPython makes a new one each time, C reuses the storage)' % t.name,
                                  'declare %s at the top level of the function' % name)
                self.new_local(st, name, t)
            if st.value is None:
                if isinstance(t, (StructT, ArrayT)):
                    raise Refusal(st, '%s: %s without a value' % (name, t.name), '%s = %s' % (name, _zero_spelling(t)))
                return []
            if isinstance(t, (StructT, ArrayT)):
                return self.local_aggregate(st.value, name, t, pad)
            v = self.coerce(self.expr(st.value, t), t, st.value)
            return [pad + '%s = %s;' % (name, v.c)]
        if isinstance(st, ast.Assign):
            if len(st.targets) != 1 or isinstance(st.targets[0], (ast.Tuple, ast.List)):
                raise Refusal(st, 'multiple or tuple assignment needs tuples', 'one assignment per line')
            target = st.targets[0]
            if isinstance(target, ast.Name) and target.id not in self.locals and target.id not in self.globals:
                name = target.id
                if name in self.statics:
                    raise Refusal(st, 'assigning %s here makes a new local in Python' % name, 'global %s at the top of the function' % name)
                if isinstance(st.value, ast.Call) and self.makes_aggregate(st.value):
                    t = self.ann(st.value.func) if isinstance(st.value.func, ast.Subscript) else self.structs[st.value.func.id]
                    if not top:
                        raise Refusal(st, 'a %s local inside a block (CPython makes a new one each time, C reuses the storage)' % t.name,
                                      'declare %s at the top level of the function' % name)
                    self.new_local(st, name, t)
                    return self.local_aggregate(st.value, name, t, pad)
                v = self.expr(st.value, None)
                if v.lit:
                    raise Refusal(st, 'local %s gets an integer literal with no width' % name,
                                  '%s: u32 = %d (or another width)' % (name, v.t.value))
                if v.t is VOID:
                    raise Refusal(st, 'assigning the result of a function that returns None')
                if isinstance(v.t, (StructT, ArrayT)):
                    raise Refusal(st, 'copying a %s (C copies, CPython shares)' % v.t.name, '%s = addr_of(...) for a Ptr[%s]' % (name, v.t.name))
                self.new_local(st, name, v.t)
                return [pad + '%s = %s;' % (name, v.c)]
            lv = self.expr(target, None)
            if isinstance(target, ast.Name) and isinstance(lv.t, (StructT, ArrayT)):
                raise Refusal(st, '%s is declared once; assigning a new %s replaces the object in CPython' % (target.id, lv.t.name),
                              'set its fields')
            if not lv.lvalue:
                raise Refusal(st, 'assigning to something that is not a variable, field or element')
            if isinstance(lv.t, (StructT, ArrayT)):
                raise Refusal(st, 'copying a %s (C copies, CPython shares)' % lv.t.name, 'set the fields one by one, or keep a Ptr')
            if isinstance(target, ast.Name) and target.id == 'self':
                raise Refusal(st, 'assigning self')
            v = self.coerce(self.expr(st.value, lv.t), lv.t, st.value)
            return [pad + '%s = %s;' % (lv.c, v.c)]
        if isinstance(st, ast.AugAssign):
            target = st.target
            if isinstance(target, ast.Name) and target.id in self.statics and target.id not in self.globals:
                raise Refusal(st, 'assigning %s here makes a new local in Python' % target.id, 'global %s at the top of the function' % target.id)
            if any(isinstance(n, ast.Call) for n in ast.walk(target)):
                raise Refusal(st, 'an augmented assignment whose target has a call', 'name the element first: p = ...; p[i] = p[i] + x')
            lv = self.expr(target, None)
            if not lv.lvalue:
                raise Refusal(st, 'assigning to something that is not a variable, field or element')
            op = BINOPS.get(type(st.op))
            if op is None:
                raise Refusal(st, 'the operator %s=' % _opname(st.op))
            v = self.binop(st, op, lv, self.expr(st.value, lv.t))
            v = self.coerce(v, lv.t, st)
            return [pad + '%s = %s;' % (lv.c, v.c)]
        if isinstance(st, ast.If):
            c = self.cond(st.test)
            lines = [pad + 'if (%s) {' % c] + self.block(st.body, d + 1)
            if st.orelse:
                if len(st.orelse) == 1 and isinstance(st.orelse[0], ast.If):
                    rest = self.stmt(st.orelse[0], d, False)
                    lines += [pad + '} else ' + rest[0].lstrip()] + rest[1:]
                    return lines
                lines += [pad + '} else {'] + self.block(st.orelse, d + 1)
            return lines + [pad + '}']
        if isinstance(st, ast.While):
            if st.orelse:
                raise Refusal(st, 'while ... else', 'a flag set before break')
            self.loop += 1
            body = self.block(st.body, d + 1)
            self.loop -= 1
            if isinstance(st.test, ast.Constant) and st.test.value is True:
                return [pad + 'for (;;) {'] + body + [pad + '}']
            return [pad + 'while (%s) {' % self.cond(st.test)] + body + [pad + '}']
        if isinstance(st, ast.For):
            return self.for_range(st, d)
        if isinstance(st, ast.Break):
            if not self.loop:
                raise Refusal(st, 'break outside a loop')
            return [pad + 'break;']
        if isinstance(st, ast.Continue):
            if not self.loop:
                raise Refusal(st, 'continue outside a loop')
            return [pad + 'continue;']
        if isinstance(st, ast.Match):
            return self.match(st, d)
        if isinstance(st, ast.Assert):
            return [pad + 'if (!(%s)) __builtin_trap();' % self.cond(st.test)]
        self.refuse_statement(st)

    def makes_aggregate(self, call):
        f = call.func
        return (isinstance(f, ast.Name) and f.id in self.structs) or (
            isinstance(f, ast.Subscript) and isinstance(f.value, ast.Name) and f.value.id == 'Array')

    def local_aggregate(self, node, name, t, pad):
        items = self.aggregate_init(node, t, static=False)
        if isinstance(t, StructT):
            return [pad + '%s.%s = %s;' % (name, k, v.c) for k, v in items]
        return [pad + '%s[%d] = %s;' % (name, i, v.c) for i, v in items]

    def for_range(self, st, d):
        pad = '    ' * d
        if st.orelse:
            raise Refusal(st, 'for ... else', 'a flag set before break')
        it = st.iter
        if not (isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == 'range'):
            raise Refusal(st, 'a for loop over %s needs an iterator object' % ast.unparse(it),
                          'for i in range(len(xs)) and index the array')
        if not isinstance(st.target, ast.Name):
            raise Refusal(st, 'a for target that is not a name')
        if it.keywords or not 1 <= len(it.args) <= 3:
            raise Refusal(st, 'range takes one to three positional bounds')
        vals = [self.expr(a, None) for a in it.args]
        typed = [v.t for v in vals if not v.lit]
        for t in typed:
            if not isinstance(t, IntT):
                raise Refusal(st, 'a range bound of type %s' % t.name, 'fixed-width int bounds')
        if any(t != typed[0] for t in typed):
            raise Refusal(st, 'range bounds of different types %s' % ', '.join(t.name for t in typed),
                          'convert them to one type, for example u32(n)')
        T = typed[0] if typed else self.usize
        name = st.target.id
        if name == '_':
            pass            # the loop counter nobody reads: no variable in C
        elif name in self.locals:
            if self.locals[name] != T:
                raise Refusal(st, 'loop variable %s is a %s but the range makes %s' % (name, self.locals[name].name, T.name),
                              'range(%s(...)) so the bounds have the variable\'s type' % self.locals[name].name)
        else:
            self.new_local(st, name, T)
        if len(it.args) == 3:
            if not vals[2].lit:
                raise Refusal(st, 'a range step that is not a constant', 'a while loop')
            step = vals[2].t.value
            if step == 0:
                raise Refusal(st, 'range() step 0')
        else:
            step = 1
        start = self.coerce(vals[0], T, st) if len(vals) > 1 else Val(lit_c(T, 0), T)
        stop = self.coerce(vals[1] if len(vals) > 1 else vals[0], T, st)
        self.tmp += 1
        k, e = '_ail_k%d' % self.tmp, '_ail_e%d' % self.tmp
        U = T.wide
        if step == 1:
            head = 'for (%s %s = %s; %s < %s; %s++) {' % (T.ctype, k, start.c, k, e, k)
        elif step > 0:
            head = 'for (%s %s = %s; %s < %s; %s = ((%s)%s - (%s)%s > %du) ? (%s)((%s)%s + %du) : %s) {' % (
                T.ctype, k, start.c, k, e, k, U, e, U, k, step, T.ctype, U, k, step, e)
        else:
            head = 'for (%s %s = %s; %s > %s; %s = ((%s)%s - (%s)%s > %du) ? (%s)((%s)%s - %du) : %s) {' % (
                T.ctype, k, start.c, k, e, k, U, k, U, e, -step, T.ctype, U, k, -step, e)
        self.loop += 1
        body = self.block(st.body, d + 2)
        self.loop -= 1
        bind = [] if name == '_' else [pad + '        %s = %s;' % (name, k)]
        return [pad + '{', pad + '    %s %s = %s;' % (T.ctype, e, stop.c), pad + '    ' + head] + bind + body + [
            pad + '    }', pad + '}']

    def match(self, st, d):
        pad = '    ' * d
        subj = self.expr(st.subject, None)
        if not isinstance(subj.t, IntT):
            raise Refusal(st, 'match on a %s' % subj.t.name, 'match on a fixed-width int')
        self.tmp += 1
        m = '_ail_m%d' % self.tmp
        lines = [pad + '{', pad + '    %s %s = %s;' % (subj.t.ctype, m, subj.c)]
        first = True
        for case in st.cases:
            if case.guard is not None:
                raise Refusal(case.pattern, 'a case guard', 'an if inside the case')
            tests = self.pattern(case.pattern, m, subj.t)
            body = self.block(case.body, d + 2)
            if tests is None:
                lines += [pad + ('    {' if first else '    else {')] + body + [pad + '    }']
                break
            lines += [pad + '    %sif (%s) {' % ('' if first else 'else ', ' || '.join(tests))] + body + [pad + '    }']
            first = False
        return lines + [pad + '}']

    def pattern(self, p, m, t):
        if isinstance(p, ast.MatchAs) and p.pattern is None and p.name is None:
            return None
        if isinstance(p, ast.MatchAs):
            raise Refusal(p, 'a capture pattern (a bare name in case binds, it does not compare)',
                          'case 1:, case 2 | 3:, a dotted constant, or case _:')
        if isinstance(p, ast.MatchOr):
            out = []
            for q in p.patterns:
                r = self.pattern(q, m, t)
                if r is None:
                    raise Refusal(p, 'a wildcard inside |')
                out += r
            return out
        if isinstance(p, ast.MatchValue):
            v = self.coerce(self.expr(p.value, t), t, p)
            return ['%s == %s' % (m, v.c)]
        raise Refusal(p, 'a %s pattern needs the object runtime' % type(p).__name__, 'integer cases')

    def asm(self, call):
        self.need(call, 'asm')
        if len(call.args) != 1 or not (isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str)):
            raise Refusal(call, 'asm takes one string literal first',
                          'asm("cli"), or asm("outb %0, %1", inputs=[("a", value), ("Nd", port)])')
        text = call.args[0].value
        if not text.isascii() or '\0' in text:
            raise Refusal(call, 'non-ASCII inline assembly')
        esc = text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\t', '\\t')
        if not call.keywords:
            return '__asm__ __volatile__("%s" ::: "memory");' % esc
        given = {}
        for kw in call.keywords:
            if kw.arg not in ('inputs', 'outputs', 'clobbers', 'volatile') or kw.arg in given:
                raise Refusal(call, 'asm keyword %s' % (kw.arg or '**'), 'inputs=[...], outputs=[...], clobbers=[...], volatile=False')
            given[kw.arg] = kw.value
        volatile = True
        if 'volatile' in given:
            v = given['volatile']
            if not (isinstance(v, ast.Constant) and isinstance(v.value, bool)):
                raise Refusal(call, 'asm volatile= takes True or False')
            volatile = v.value
        outs = [self.asm_operand(call, e, 'outputs', ASM_OUTPUTS) for e in self.asm_list(call, given.get('outputs'), 'outputs')]
        ins = [self.asm_operand(call, e, 'inputs', ASM_INPUTS) for e in self.asm_list(call, given.get('inputs'), 'inputs')]
        clobbers = ['memory'] if volatile else []
        for e in self.asm_list(call, given.get('clobbers'), 'clobbers', tuples=False):
            if not (isinstance(e, ast.Constant) and isinstance(e.value, str)) or e.value not in self.asm_clobbers():
                raise Refusal(call, 'asm clobber %s is not in the vetted list' % ast.unparse(e),
                              ', '.join(sorted(self.asm_clobbers())))
            if e.value not in clobbers:
                clobbers.append(e.value)
        count = len(outs) + len(ins)
        for m in re.finditer(r'%(%|\d+)', text):
            if m.group(1) != '%' and int(m.group(1)) >= count:
                raise Refusal(call, 'the template uses operand %%%s but there are %d operands' % (m.group(1), count),
                              'outputs are numbered first, then inputs; a register is %%rax')
        return '%s("%s" : %s : %s : %s);' % ('__asm__ __volatile__' if volatile else '__asm__', esc, ', '.join(outs),
                                              ', '.join(ins), ', '.join('"%s"' % c for c in clobbers))

    def asm_clobbers(self):
        return ASM_CLOBBERS_X64 if self.target == 'x86_64' else ASM_CLOBBERS_I386

    def asm_list(self, call, node, what, tuples=True):
        if node is None:
            return []
        if not isinstance(node, ast.List):
            raise Refusal(call, 'asm %s= takes a list literal' % what)
        return node.elts

    def asm_operand(self, call, e, what, vetted):
        if not (isinstance(e, ast.Tuple) and len(e.elts) == 2 and isinstance(e.elts[0], ast.Constant)
                and isinstance(e.elts[0].value, str)):
            raise Refusal(call, 'an asm %s entry that is not ("constraint", expression)' % what[:-1], '("a", value)')
        constraint = e.elts[0].value
        if constraint not in vetted:
            raise Refusal(call, 'the asm constraint %r is not in the vetted list for %s' % (constraint, what),
                          ', '.join(sorted(vetted)))
        v = self.expr(e.elts[1], None)
        memory = constraint.endswith('m')
        if v.lit:
            raise Refusal(e, 'an asm operand that is an integer literal has no width', 'u8(%d) or another fixed width' % v.t.value)
        if not memory and not isinstance(v.t, (IntT, PtrT, FnT)) and v.t is not BOOL:
            raise Refusal(e, 'an asm operand of type %s in a register' % v.t.name,
                          'a fixed-width int or pointer; addr_of(x) for a struct, or the "m" constraint on the struct itself')
        if what == 'outputs' or memory:
            if not v.lvalue:
                raise Refusal(e, 'an asm %s operand with no storage' % ('output' if what == 'outputs' else 'memory'),
                              'a local, a field, an element or (with global) a static')
        elif constraint in ('i', 'n', 'N') and not self.const_syntax(e.elts[1]):
            raise Refusal(e, 'the asm constraint %r needs a compile-time constant' % constraint, 'u8(0x20), or "r"')
        return '"%s"(%s)' % (constraint, v.c)

    def const_syntax(self, node):
        """True for an integer literal, a module constant, a fixed-width conversion of one, or arithmetic over them."""
        if isinstance(node, ast.Constant):
            return isinstance(node.value, int)
        if isinstance(node, ast.Name):
            return node.id in self.consts and not (getattr(self, 'fn', None) is not None and node.id in self.locals)
        if isinstance(node, ast.UnaryOp):
            return self.const_syntax(node.operand)
        if isinstance(node, ast.BinOp):
            return self.const_syntax(node.left) and self.const_syntax(node.right)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in INTS and len(node.args) == 1:
            return self.const_syntax(node.args[0])
        return False

    # -- expressions
    def cond(self, node):
        v = self.expr(node, BOOL)
        if v.lit:
            return '1' if v.t.value else '0'
        if v.t is BOOL:
            return v.c
        if isinstance(v.t, IntT):
            return '(%s != 0)' % v.c
        raise Refusal(node, 'a %s as a condition' % v.t.name, 'an explicit comparison such as addr(p) != 0')

    def coerce(self, v, t, node):
        if v.lit:
            if isinstance(t, IntT):
                if not t.fits(v.t.value):
                    raise Refusal(node, 'the literal %d does not fit %s' % (v.t.value, t.name),
                                  '%s(%d) to wrap it, or a wider type' % (t.name, v.t.value))
                return Val(lit_c(t, v.t.value), t, pure=True)
            raise Refusal(node, 'an integer literal where a %s is expected' % t.name,
                          {BOOL: 'True or False'}.get(t, 'Ptr[T](address)' if isinstance(t, PtrT) else (
                              '%s(0) for a null function pointer, or a function name' % t.name if isinstance(t, FnT) else 'a %s value' % t.name)))
        if v.t != t:
            raise Refusal(node, 'a %s value where a %s is expected' % (v.t.name, t.name),
                          ('%s(...) to convert it' % t.name) if isinstance(t, IntT) and isinstance(v.t, (IntT, _Named)) and v.t is not VOID
                          else ('Ptr[%s](p) to reinterpret it' % t.target.name if isinstance(t, PtrT) and isinstance(v.t, PtrT)
                                else 'a value of type %s' % t.name))
        return v

    def unify(self, node, a, b, what):
        if a.lit and b.lit:
            return a, b, None
        if a.lit:
            a = self.coerce(a, b.t, node)
        elif b.lit:
            b = self.coerce(b, a.t, node)
        if a.t != b.t:
            raise Refusal(node, '%s mixes %s and %s' % (what, a.t.name, b.t.name),
                          'convert one side, for example %s(x)' % (b.t.name if isinstance(b.t, IntT) else a.t.name))
        return a, b, a.t

    def helper(self, kind, t):
        name = 'ail_fs_%s_%s' % (kind, t.name)
        if name in self.helpers:
            return name
        T, U, W = t.ctype, t.wide, t.bits
        body = {
            'wadd': 'return (%s)((%s)a + (%s)b);' % (T, U, U),
            'wsub': 'return (%s)((%s)a - (%s)b);' % (T, U, U),
            'wmul': 'return (%s)((%s)a * (%s)b);' % (T, U, U),
            'cadd': '%s r; if (__builtin_add_overflow(a, b, &r)) __builtin_trap(); return r;' % T,
            'csub': '%s r; if (__builtin_sub_overflow(a, b, &r)) __builtin_trap(); return r;' % T,
            'cmul': '%s r; if (__builtin_mul_overflow(a, b, &r)) __builtin_trap(); return r;' % T,
        }
        if kind in body:
            sig, text = '%s a, %s b' % (T, T), body[kind]
        elif kind in ('wneg', 'cneg'):
            sig = '%s a' % T
            text = ('return (%s)((%s)0 - (%s)a);' % (T, U, U) if kind == 'wneg' else
                    '%s r; if (__builtin_sub_overflow((%s)0, a, &r)) __builtin_trap(); return r;' % (T, T))
        elif kind in ('wdiv', 'cdiv', 'wmod', 'cmod'):
            sig = '%s a, %s b' % (T, T)
            if not t.signed:
                text = 'if (b == 0) __builtin_trap(); return a %s b;' % ('/' if 'div' in kind else '%')
            elif 'div' in kind:
                text = ('if (b == 0) __builtin_trap(); if (b == -1) { %sreturn (%s)((%s)0 - (%s)a); } '
                        '%s q = a / b; if (a %% b != 0 && ((a < 0) != (b < 0))) q--; return q;' % (
                            'if (a == %s) __builtin_trap(); ' % t.cmin if kind == 'cdiv' else '', T, U, U, T))
            else:
                text = ('if (b == 0) __builtin_trap(); if (b == -1) return 0; '
                        '%s r = a %% b; if (r != 0 && ((r < 0) != (b < 0))) r += b; return r;' % T)
        elif kind == 'shl':
            sig, text = '%s a, uint64_t n' % T, 'if (n >= %du) __builtin_trap(); return (%s)((%s)a << n);' % (W, T, U)
        elif kind == 'shr':
            sig, text = '%s a, uint64_t n' % T, 'if (n >= %du) __builtin_trap(); return (%s)(a >> n);' % (W, T)
        elif kind == 'shamt':
            sig, text = '%s n' % T, 'if (n < 0) __builtin_trap(); return (uint64_t)n;'
            self.helpers[name] = 'static inline uint64_t %s(%s) { %s }\n' % (name, sig, text)
            return name
        elif kind == 'ix':
            sig = '%s i, uint64_t n' % T
            text = ('if (i < 0 || (uint64_t)i >= n) __builtin_trap(); return (uintptr_t)i;' if t.signed else
                    'if ((uint64_t)i >= n) __builtin_trap(); return (uintptr_t)i;')
            self.helpers[name] = 'static inline uintptr_t %s(%s) { %s }\n' % (name, sig, text)
            return name
        self.helpers[name] = 'static inline %s %s(%s) { %s }\n' % (T, name, sig, text)
        return name

    def binop(self, node, op, a, b):
        if a.t is VOID or b.t is VOID:
            raise Refusal(node, 'arithmetic on None')
        for v in (a, b):
            if v.t is BOOL:
                raise Refusal(node, 'arithmetic on a bool', 'u32(flag) first, or and/or/not')
            if isinstance(v.t, PtrT):
                raise Refusal(node, 'arithmetic on a pointer', 'p.offset(n) for elements, or Ptr[T](addr(p) + n) for bytes')
            if isinstance(v.t, (StructT, ArrayT)):
                raise Refusal(node, 'arithmetic on a %s' % v.t.name)
        if a.lit and b.lit:
            return lit(_fold(op, a.t.value, b.t.value, node))
        if op in ('<<', '>>'):
            if a.lit:
                raise Refusal(node, 'the shifted literal %d has no width' % a.t.value, 'u32(%d) %s n' % (a.t.value, op))
            t = a.t
            if b.lit:
                n = b.t.value
                if not 0 <= n < t.bits:
                    raise Refusal(node, 'shift count %d is outside 0..%d for %s' % (n, t.bits - 1, t.name))
                if op == '<<':
                    return Val('((%s)((%s)%s << %d))' % (t.ctype, t.wide, a.c, n), t, pure=a.pure)
                return Val('((%s)(%s >> %d))' % (t.ctype, a.c, n), t, pure=a.pure)
            n = b.c if not b.t.signed else '%s(%s)' % (self.helper('shamt', b.t), b.c)
            return Val('%s(%s, %s)' % (self.helper('shl' if op == '<<' else 'shr', t), a.c, n), t)
        a, b, t = self.unify(node, a, b, 'the operator %s' % op)
        if op in ('&', '|', '^'):
            return Val('((%s)(%s %s %s))' % (t.ctype, a.c, op, b.c), t, pure=a.pure and b.pure)
        mode = self.mode_now
        if mode is None:
            raise Refusal(node, 'the %s %s needs a declared overflow rule' % (t.name, op), MODE_HINT)
        kind = {'+': 'add', '-': 'sub', '*': 'mul', '//': 'div', '%': 'mod'}[op]
        return Val('%s(%s, %s)' % (self.helper(mode[0] + kind, t), a.c, b.c), t)

    @property
    def mode_now(self):
        return getattr(self, '_mode_override', None) or (self.fn.mode if getattr(self, 'fn', None) else self.mode)

    def expr(self, node, want, statement=False):
        if isinstance(node, ast.Constant):
            v = node.value
            if isinstance(v, bool):
                return Val('true' if v else 'false', BOOL, pure=True)
            if isinstance(v, int):
                return lit(v)
            if isinstance(v, float):
                raise Refusal(node, 'floats are off in freestanding mode (no FPU state is saved)', RUNTIME_NAMES['float'])
            if isinstance(v, str):
                raise Refusal(node, 'a str needs the runtime', RUNTIME_NAMES['str'] + ', or Array[u8, N]([...]) of the codes')
            if isinstance(v, bytes):
                raise Refusal(node, 'bytes need the runtime', 'Array[u8, N]([...]) of the byte values, or Array[u8, N](b"text") as a declaration\'s initializer')
            if v is None:
                raise Refusal(node, 'None as a value', 'Ptr[T](0) for a null pointer, or a status code')
            raise Refusal(node, 'the constant %r' % (v,))
        if isinstance(node, ast.Name):
            name = node.id
            fn = getattr(self, 'fn', None)
            if fn is not None and name in self.locals:
                return Val(name, self.locals[name], lvalue=name != 'self', pure=True)
            if name in self.consts:
                return self.consts[name]
            if name in self.statics:
                t = self.statics[name][0]
                return Val(name, t, lvalue=fn is None or name in self.globals or isinstance(t, (StructT, ArrayT)), pure=False)
            if name in self.funcs:
                fn = self.funcs[name]
                if fn.interrupt:
                    raise Refusal(node, '@interrupt handler %s is entered by the CPU and returns with iret, not called or stored as a function value' % name,
                                  'addr(%s) for the IDT entry' % name)
                return Val(fn.cname, fn.value_type(), pure=True)
            if name in RUNTIME_NAMES:
                raise Refusal(node, '%s needs the runtime' % name, RUNTIME_NAMES[name])
            raise Refusal(node, 'unknown name %s' % name)
        if isinstance(node, ast.BinOp):
            op = BINOPS.get(type(node.op))
            if op is None:
                raise Refusal(node, 'the operator %s' % _opname(node.op),
                              {ast.Div: 'a // b (integer division)', ast.Pow: 'a loop or a shift',
                               ast.MatMult: 'a loop'}.get(type(node.op)))
            return self.binop(node, op, self.expr(node.left, want), self.expr(node.right, want))
        if isinstance(node, ast.UnaryOp):
            v = self.expr(node.operand, want)
            if isinstance(node.op, ast.Not):
                c = self.cond(node.operand)
                return Val('(!%s)' % c, BOOL, pure=v.pure)
            if v.lit:
                return lit({ast.USub: -v.t.value, ast.UAdd: v.t.value, ast.Invert: ~v.t.value}[type(node.op)])
            if not isinstance(v.t, IntT):
                raise Refusal(node, 'the operator %s on a %s' % (_opname(node.op), v.t.name))
            if isinstance(node.op, ast.UAdd):
                return v
            if isinstance(node.op, ast.Invert):
                return Val('((%s)~%s)' % (v.t.ctype, v.c), v.t, pure=v.pure)
            mode = self.mode_now
            if mode is None:
                raise Refusal(node, 'negating a %s needs a declared overflow rule' % v.t.name, MODE_HINT)
            return Val('%s(%s)' % (self.helper(mode[0] + 'neg', v.t), v.c), v.t)
        if isinstance(node, ast.BoolOp):
            parts = []
            for value in node.values:
                v = self.expr(value, BOOL)
                if v.t is not BOOL:
                    raise Refusal(value, '%s on a %s (Python returns the operand, not a bool)' % (
                        'and' if isinstance(node.op, ast.And) else 'or', v.t.name), '(x != 0)')
                parts.append(v)
            return Val('(%s)' % (' && ' if isinstance(node.op, ast.And) else ' || ').join(p.c for p in parts), BOOL,
                       pure=all(p.pure for p in parts))
        if isinstance(node, ast.Compare):
            return self.compare(node)
        if isinstance(node, ast.IfExp):
            c = self.cond(node.test)
            a, b, t = self.unify(node, self.expr(node.body, want), self.expr(node.orelse, want), 'a conditional expression')
            if t is None and isinstance(want, IntT):
                a, b, t = self.coerce(a, want, node.body), self.coerce(b, want, node.orelse), want
            if t is None:
                raise Refusal(node, 'a conditional expression of two literals has no width', 'u32(1) if c else u32(0)')
            if isinstance(t, (StructT, ArrayT)):
                raise Refusal(node, 'a conditional %s copies it' % t.name, 'a Ptr')
            return Val('(%s ? %s : %s)' % (c, a.c, b.c), t, pure=a.pure and b.pure)
        if isinstance(node, ast.Attribute):
            base = self.expr(node.value, None)
            st, via = self.struct_of(base, node)
            if node.attr not in st.fields:
                if node.attr in st.methods:
                    raise Refusal(node, 'method %s as a value needs closures' % node.attr, 'call it')
                raise Refusal(node, '%s has no field %s' % (st.name, node.attr))
            return Val('%s%s%s' % (base.c, via, node.attr), st.fields[node.attr], lvalue=True, pure=base.pure)
        if isinstance(node, ast.Subscript):
            if isinstance(node.slice, ast.Slice):
                raise Refusal(node, 'a slice makes a new list', 'a Ptr to the first element and a length: as_ptr(a).offset(i)')
            base = self.expr(node.value, None)
            idx = self.expr(node.slice, None)
            if not idx.lit and not isinstance(idx.t, IntT):
                raise Refusal(node, 'an index of type %s' % idx.t.name, 'a fixed-width int index')
            if isinstance(base.t, ArrayT):
                n = base.t.n
                if idx.lit:
                    if not 0 <= idx.t.value < n:
                        raise Refusal(node, 'index %d is outside %s' % (idx.t.value, base.t.name),
                                      'an index in 0..%d (negative indexes from the end are not part of the subset)' % (n - 1))
                    i = '%d' % idx.t.value
                else:
                    i = '%s(%s, %du)' % (self.helper('ix', idx.t), idx.c, n)
                return Val('%s[%s]' % (base.c, i), base.t.elem, lvalue=True, pure=base.pure and idx.pure)
            if isinstance(base.t, PtrT):
                if isinstance(base.t.target, ArrayT):
                    raise Refusal(node, 'indexing a Ptr to an Array', 'as_ptr(...) for a Ptr to the first element, or p[0][i]')
                i = '%d' % idx.t.value if idx.lit else idx.c
                return Val('%s[%s]' % (base.c, i), base.t.target, lvalue=True, pure=base.pure and idx.pure)
            raise Refusal(node, 'indexing a %s' % base.t.name, 'an Array[T, N] or a Ptr[T]')
        if isinstance(node, ast.Call):
            return self.call(node, want, statement)
        refusals = {
            ast.List: ('a list needs the runtime', RUNTIME_NAMES['list']),
            ast.Dict: ('a dict needs the runtime', RUNTIME_NAMES['dict']),
            ast.Set: ('a set needs the runtime', RUNTIME_NAMES['set']),
            ast.Tuple: ('a tuple needs the runtime', RUNTIME_NAMES['tuple']),
            ast.ListComp: ('a comprehension needs the runtime', 'a for loop over range filling an Array'),
            ast.SetComp: ('a comprehension needs the runtime', 'a for loop over range filling a bitmap'),
            ast.DictComp: ('a comprehension needs the runtime', 'a for loop over range filling a table'),
            ast.GeneratorExp: ('a generator needs the runtime', 'a for loop over range'),
            ast.Lambda: ('a lambda needs closures', 'a module-level function called directly'),
            ast.JoinedStr: ('an f-string needs the runtime', 'format digits into an Array[u8, N] yourself'),
            ast.Yield: ('a generator needs the runtime', 'a state machine in a @struct'),
            ast.YieldFrom: ('a generator needs the runtime', 'a state machine in a @struct'),
            ast.Await: ('await needs the runtime', 'a state machine in a @struct'),
            ast.NamedExpr: ('the walrus operator', 'an assignment on its own line'),
            ast.Starred: ('star arguments need tuples', 'positional arguments'),
        }
        what, instead = refusals.get(type(node), ('the expression %s' % type(node).__name__, None))
        raise Refusal(node, what, instead)

    def struct_of(self, base, node):
        if isinstance(base.t, StructT):
            return base.t, '.'
        if isinstance(base.t, PtrT) and isinstance(base.t.target, StructT):
            return base.t.target, '->'
        raise Refusal(node, 'a field of a %s' % base.t.name, 'a @struct value or a Ptr to one')

    def compare(self, node):
        for op in node.ops:
            if type(op) not in CMPOPS:
                raise Refusal(node, 'the comparison %s' % _opname(op),
                              {ast.Is: 'addr(p) == 0 or ==', ast.IsNot: '!=', ast.In: 'a loop over the array',
                               ast.NotIn: 'a loop over the array'}.get(type(op)))
        if len(node.ops) > 1 and any(not _pure_syntax(n) for n in node.comparators[:-1]):
            raise Refusal(node, 'a chained comparison whose middle has a call', 'name the middle value first')
        operands = [node.left] + node.comparators
        parts, pure = [], True
        for i, op in enumerate(node.ops):
            a, b = self.expr(operands[i], None), self.expr(operands[i + 1], None)
            sym = CMPOPS[type(op)]
            if a.lit and b.lit:
                parts.append('1' if {'<': a.t.value < b.t.value, '<=': a.t.value <= b.t.value, '>': a.t.value > b.t.value,
                                     '>=': a.t.value >= b.t.value, '==': a.t.value == b.t.value,
                                     '!=': a.t.value != b.t.value}[sym] else '0')
                continue
            a, b, t = self.unify(node, a, b, 'the comparison %s' % sym)
            if isinstance(t, (StructT, ArrayT)) or t is VOID:
                raise Refusal(node, 'comparing %s values' % t.name, 'compare the fields')
            if (t is BOOL or isinstance(t, (PtrT, FnT))) and sym not in ('==', '!='):
                raise Refusal(node, 'ordering %s values' % t.name, 'addr(p) < addr(q)' if isinstance(t, (PtrT, FnT)) else '== or !=')
            parts.append('(%s %s %s)' % (a.c, sym, b.c))
            pure = pure and a.pure and b.pure
        return Val('(%s)' % ' && '.join(parts) if len(parts) > 1 else parts[0], BOOL, pure=pure)

    def args(self, node, params, what):
        if node.keywords:
            raise Refusal(node, 'keyword arguments to %s' % what, 'positional arguments')
        if len(node.args) != len(params):
            raise Refusal(node, '%s takes %d arguments, not %d' % (what, len(params), len(node.args)))
        return [self.coerce(self.expr(a, t), t, a).c for a, (_, t) in zip(node.args, params)]

    def call(self, node, want, statement):
        f = node.func
        if isinstance(f, ast.Name):
            name = f.id
            fn_here = getattr(self, 'fn', None)
            if (fn_here is not None and name in self.locals) or name in self.statics:
                callee = self.expr(f, None)
                if isinstance(callee.t, FnT):
                    return self.indirect_call(node, callee)
                raise Refusal(node, 'a call of %s, a %s' % (name, callee.t.name), 'a function name or an Fn[...] value')
            if name in INTS or name == 'bool':
                if name in INTS:
                    self.need(node, name)
                if len(node.args) != 1 or node.keywords:
                    raise Refusal(node, '%s() takes one value' % name)
                v = self.expr(node.args[0], None)
                t = self.ints.get(name, BOOL)
                if v.lit:
                    if t is BOOL:
                        return Val('true' if v.t.value else 'false', BOOL, pure=True)
                    return Val(lit_c(t, t.wrap(v.t.value)), t, pure=True)
                if t is BOOL:
                    if not isinstance(v.t, IntT) and v.t is not BOOL:
                        raise Refusal(node, 'bool() of a %s' % v.t.name)
                    return Val('(%s != 0)' % v.c, BOOL, pure=v.pure)
                if not (isinstance(v.t, IntT) or v.t is BOOL):
                    raise Refusal(node, '%s() of a %s' % (name, v.t.name), 'addr(p) for the address of a pointer' if isinstance(v.t, PtrT) else None)
                return Val('((%s)%s)' % (t.ctype, v.c), t, pure=v.pure)
            if name in ('wrapping', 'checked'):
                self.need(node, name)
                if len(node.args) != 1 or node.keywords:
                    raise Refusal(node, '%s() takes one expression' % name)
                saved = getattr(self, '_mode_override', None)
                self._mode_override = 'wrap' if name == 'wrapping' else 'check'
                try:
                    return self.expr(node.args[0], want)
                finally:
                    self._mode_override = saved
            if name == 'len':
                v = self.expr(node.args[0], None) if len(node.args) == 1 else None
                if v is None or not isinstance(v.t, ArrayT):
                    raise Refusal(node, 'len() of something that is not an Array', 'keep the length in a field')
                return lit(v.t.n)
            if name == 'addr':
                self.need(node, name)
                arg = node.args[0] if len(node.args) == 1 and not node.keywords else None
                if isinstance(arg, ast.Name) and arg.id in self.funcs and not (
                        getattr(self, 'fn', None) is not None and arg.id in self.locals):
                    return Val('((uintptr_t)%s)' % self.funcs[arg.id].cname, self.usize, pure=True)
                v = self.one(node, name)
                if not isinstance(v.t, (PtrT, FnT)):
                    raise Refusal(node, 'addr() of a %s' % v.t.name, 'addr(p) for a Ptr; addr(addr_of(x)) for a struct')
                return Val('((uintptr_t)%s)' % v.c, self.usize, pure=v.pure)
            if name == 'addr_of':
                self.need(node, name)
                v = self.one(node, name)
                if not v.lvalue and not (isinstance(v.t, (StructT, ArrayT)) and isinstance(node.args[0], ast.Name)):
                    raise Refusal(node, 'addr_of() of a value that has no storage')
                if not isinstance(v.t, (StructT, ArrayT)):
                    raise Refusal(node, 'addr_of() of a %s (CPython has no reference to an int)' % v.t.name,
                                  'keep it in a @struct field and take addr_of the struct')
                return Val('(&%s)' % v.c, PtrT(v.t), pure=v.pure)
            if name == 'as_ptr':
                self.need(node, name)
                v = self.one(node, name)
                if not isinstance(v.t, ArrayT):
                    raise Refusal(node, 'as_ptr() of a %s' % v.t.name, 'as_ptr(array)')
                return Val('(&%s[0])' % v.c, PtrT(v.t.elem), pure=v.pure)
            if name in ('volatile_load', 'volatile_store'):
                self.need(node, name)
                if node.keywords or len(node.args) != (1 if name == 'volatile_load' else 2):
                    raise Refusal(node, '%s takes %s' % (name, 'a Ptr' if name == 'volatile_load' else 'a Ptr and a value'))
                p = self.expr(node.args[0], None)
                if not isinstance(p.t, PtrT) or not (isinstance(p.t.target, IntT) or p.t.target is BOOL):
                    raise Refusal(node, '%s through a %s' % (name, p.t.name), 'a Ptr to a fixed-width int')
                cell = '(*(volatile %s *)%s)' % (declare(p.t.target), p.c)
                if name == 'volatile_load':
                    return Val(cell, p.t.target)
                if not statement:
                    raise Refusal(node, 'volatile_store used as a value')
                v = self.coerce(self.expr(node.args[1], p.t.target), p.t.target, node.args[1])
                return Val('%s = %s' % (cell, v.c), VOID)
            if name == 'asm':
                raise Refusal(node, 'asm() used as a value', 'asm("...") on its own line')
            if name == 'range':
                raise Refusal(node, RUNTIME_NAMES['range'], 'for i in range(n)')
            if name in self.structs or name == 'Array':
                raise Refusal(node, 'a new %s outside a declaration' % name, 'x = %s() at the top level of the function, or a static' % name)
            if name == 'size_of' or name == 'align_of':
                self.need(node, name)
                if len(node.args) != 1 or node.keywords:
                    raise Refusal(node, '%s() takes one type' % name)
                size, align = self.layout(self.ann(node.args[0]))
                return lit(size if name == 'size_of' else align)
            if name in self.funcs:
                fn = self.funcs[name]
                if fn.interrupt:
                    raise Refusal(node, '@interrupt handler %s cannot be called (it returns with iret)' % name,
                                  'put the work in an ordinary function and call that from the handler')
                vals = self.args(node, fn.params, name)
                return Val('%s(%s)' % (fn.cname, ', '.join(vals)), fn.ret)
            if name in RUNTIME_NAMES:
                raise Refusal(node, '%s() needs the runtime' % name, RUNTIME_NAMES[name])
            raise Refusal(node, 'unknown function %s' % name)
        if isinstance(f, ast.Subscript) and isinstance(f.value, ast.Name) and f.value.id == 'Ptr':
            t = self.ann(f)
            v = self.one(node, 'Ptr')
            if v.lit:
                if v.t.value < 0:
                    raise Refusal(node, 'a negative address')
                if v.t.value >= 1 << (8 * self.ptr_bytes):
                    raise Refusal(node, 'the address %#x does not fit a %d-bit pointer' % (v.t.value, 8 * self.ptr_bytes))
                return Val('((%s)(uintptr_t)%du%s)' % (declare(t), v.t.value, 'll'), t, pure=True)
            if isinstance(v.t, IntT):
                return Val('((%s)(uintptr_t)%s)' % (declare(t), v.c), t, pure=v.pure)
            if isinstance(v.t, PtrT):
                return Val('((%s)%s)' % (declare(t), v.c), t, pure=v.pure)
            raise Refusal(node, 'Ptr() of a %s' % v.t.name, 'Ptr[T](address) or Ptr[T](other_pointer)')
        if isinstance(f, ast.Subscript) and isinstance(f.value, ast.Name) and f.value.id == 'Fn':
            t = self.ann(f)
            v = self.one(node, 'Fn')
            if v.lit:
                if not 0 <= v.t.value < 1 << (8 * self.ptr_bytes):
                    raise Refusal(node, 'the address %d does not fit a %d-bit pointer' % (v.t.value, 8 * self.ptr_bytes))
                return Val('((%s)(uintptr_t)%du%s)' % (declare(t), v.t.value, 'll'), t, pure=True)
            if v.t is self.usize:
                return Val('((%s)%s)' % (declare(t), v.c), t, pure=v.pure)
            raise Refusal(node, 'Fn[...]() of a %s' % v.t.name, 'Fn[[...], ...](0) for null, or an address as a usize')
        if isinstance(f, ast.Subscript) and isinstance(f.value, ast.Name) and f.value.id == 'Array':
            raise Refusal(node, 'a new %s outside a declaration' % ast.unparse(f), 'x = %s() at the top level of the function, or a static' % ast.unparse(f))
        if isinstance(f, ast.Attribute):
            base = self.expr(f.value, None)
            if f.attr == 'offset' and isinstance(base.t, PtrT):
                n = self.one(node, 'offset')
                if n.lit:
                    return Val('(%s + %d)' % (base.c, n.t.value), base.t, pure=base.pure)
                if not isinstance(n.t, IntT):
                    raise Refusal(node, 'offset() by a %s' % n.t.name)
                return Val('(%s + %s)' % (base.c, n.c), base.t, pure=base.pure and n.pure)
            if isinstance(base.t, StructT) or (isinstance(base.t, PtrT) and isinstance(base.t.target, StructT)):
                st, via = self.struct_of(base, f)
                if isinstance(st.fields.get(f.attr), FnT):
                    return self.indirect_call(node, self.expr(f, None))
                if f.attr not in st.methods:
                    raise Refusal(node, '%s has no method %s' % (st.name, f.attr))
                fn = st.methods[f.attr]
                if via == '.' and not base.lvalue and not isinstance(base.t, StructT):
                    raise Refusal(node, 'a method call on a value without storage')
                selfc = ('(&%s)' % base.c) if via == '.' else base.c
                vals = self.args(node, fn.params[1:], '%s.%s' % (st.name, f.attr))
                return Val('%s(%s)' % (fn.cname, ', '.join([selfc] + vals)), fn.ret)
            raise Refusal(node, 'the method %s on a %s needs the runtime' % (f.attr, base.t.name if not base.lit else 'literal'),
                          'a function over the value')
        callee = self.expr(f, None)
        if isinstance(callee.t, FnT):
            return self.indirect_call(node, callee)
        raise Refusal(node, 'a call of %s' % ast.unparse(f))

    def indirect_call(self, node, callee):
        """Call through an Fn[...] value: a local, a static, a field, an element or another call's result."""
        vals = self.args(node, [('', p) for p in callee.t.params], 'a call through %s' % ast.unparse(node.func))
        return Val('(%s)(%s)' % (callee.c, ', '.join(vals)), callee.t.ret)

    def one(self, node, what):
        if node.keywords or len(node.args) != 1:
            raise Refusal(node, '%s() takes one argument' % what)
        return self.expr(node.args[0], None)

    # -- output
    def emit(self, source_name):
        parts = []
        guard = '/* Generated by AIL --freestanding from %s. Needs no runtime and no libc:\n' \
                '   only the freestanding headers <stdint.h>, <stddef.h> and <stdbool.h>. */\n' % source_name
        head = ['#include <stdint.h>\n#include <stddef.h>\n#include <stdbool.h>\n']
        types = self.type_decls()
        externs = [('extern %s;\n' % fn.prototype()) for fn in self.funcs.values() if fn.extern]
        statics = []
        protos = []
        for name, (t, init, _) in self.statics.items():
            statics.append('%s%s = %s;\n' % ('static ' if name.startswith('_') else '', declare(t, name), init))
        for fn in self._all_functions():
            if not fn.extern:
                protos.append('%s%s;\n' % ('static ' if not fn.exported else '', fn.prototype()))
        parts = [guard] + head + ['\n'] + types + self.layout_asserts() + ['\n'] + list(self.helpers.values()) + ['\n'] + externs + protos + \
            ['\n'] + statics + ['\n'] + [o + '\n' for o in self.out] + [MEM_FUNCTIONS]
        return ''.join(parts)

    def _all_functions(self):
        for s in self.structs.values():
            yield from s.methods.values()
        yield from self.funcs.values()

    def type_decls(self):
        out = ['typedef struct %s %s;\n' % (s.name, s.name) for s in self.structs.values()]
        for s in self.structs.values():
            attrs = (['packed'] if s.packed else []) + (['aligned(%d)' % s.align] if s.align else [])
            out.append('struct %s%s {\n%s};\n' % ('__attribute__((%s)) ' % ', '.join(attrs) if attrs else '', s.name,
                                                   ''.join('    %s;\n' % declare(t, n) for n, t in s.fields.items())))
        return out

    def layout_asserts(self):
        """The checker's size and alignment of every struct, asserted against what the C compiler computes."""
        return ['_Static_assert(sizeof(%s) == %d && _Alignof(%s) == %d, "AIL layout of %s");\n' % (
            s.name, s.size, s.name, s.alignment, s.name) for s in self.structs.values()]

    def header(self, stem):
        guard = 'AIL_FS_%s_H' % ''.join(c if c.isalnum() else '_' for c in stem).upper()
        lines = ['/* Generated by AIL --freestanding: declarations of %s for the C code that links it. */\n' % stem,
                 '#ifndef %s\n#define %s\n' % (guard, guard),
                 '#include <stdint.h>\n#include <stddef.h>\n#include <stdbool.h>\n\n'] + self.type_decls() + ['\n']
        for name, (t, _, _) in self.statics.items():
            if not name.startswith('_'):
                lines.append('extern %s;\n' % declare(t, name))
        for fn in self._all_functions():
            if fn.exported and not fn.extern:
                lines.append('%s;\n' % fn.prototype())
        externs = [fn for fn in self.funcs.values() if fn.extern]
        if externs:
            lines.append('/* to be defined by the kernel or the harness */\n')
            lines += ['%s;\n' % fn.prototype() for fn in externs]
        lines.append('#endif\n')
        return ''.join(lines)


MEM_FUNCTIONS = r'''/* GCC and Clang may emit calls to these four even under -ffreestanding (struct copies and
   zeroing). They are weak, so a kernel's own definitions win; the loops are kept as loops. */
#if defined(__GNUC__) && !defined(__clang__)
#define AIL_FS_MEMFN __attribute__((weak, optimize("no-tree-loop-distribute-patterns")))
#else
#define AIL_FS_MEMFN __attribute__((weak))
#endif
AIL_FS_MEMFN void *memset(void *dst, int c, size_t n) {
    unsigned char *d = (unsigned char *)dst;
    while (n--) *d++ = (unsigned char)c;
    return dst;
}
AIL_FS_MEMFN void *memcpy(void *restrict dst, const void *restrict src, size_t n) {
    unsigned char *d = (unsigned char *)dst; const unsigned char *s = (const unsigned char *)src;
    while (n--) *d++ = *s++;
    return dst;
}
AIL_FS_MEMFN void *memmove(void *dst, const void *src, size_t n) {
    unsigned char *d = (unsigned char *)dst; const unsigned char *s = (const unsigned char *)src;
    if (d < s) { while (n--) *d++ = *s++; } else { d += n; s += n; while (n--) *--d = *--s; }
    return dst;
}
AIL_FS_MEMFN int memcmp(const void *a, const void *b, size_t n) {
    const unsigned char *x = (const unsigned char *)a, *y = (const unsigned char *)b;
    for (; n; n--, x++, y++) if (*x != *y) return *x < *y ? -1 : 1;
    return 0;
}
'''
MEM_SYMBOLS = ('memset', 'memcpy', 'memmove', 'memcmp')


def _zero_spelling(t):
    if isinstance(t, (StructT, ArrayT)):
        return '%s()' % t.name
    if isinstance(t, PtrT):
        return '%s(0)' % t.name
    return 'False' if t is BOOL else '0'


def _zero_spelling_c(t):
    return '{0}' if isinstance(t, (StructT, ArrayT)) else '0'


def _opname(op):
    return {ast.Div: '/', ast.Pow: '**', ast.MatMult: '@', ast.Is: 'is', ast.IsNot: 'is not', ast.In: 'in',
            ast.NotIn: 'not in'}.get(type(op), type(op).__name__)


def _pure_syntax(node):
    return all(not isinstance(n, ast.Call) for n in ast.walk(node))


def _is_main_guard(st):
    t = st.test
    return (isinstance(t, ast.Compare) and isinstance(t.left, ast.Name) and t.left.id == '__name__'
            and len(t.comparators) == 1 and isinstance(t.comparators[0], ast.Constant) and t.comparators[0].value == '__main__')


def _always_returns(body):
    if not body:
        return False
    last = body[-1]
    if isinstance(last, ast.Return):
        return True
    if isinstance(last, ast.If):
        return _always_returns(last.body) and _always_returns(last.orelse)
    if isinstance(last, ast.While) and isinstance(last.test, ast.Constant) and last.test.value is True:
        return not any(isinstance(n, ast.Break) for n in _loop_level(last.body))
    if isinstance(last, ast.Match):
        wild = any(isinstance(c.pattern, ast.MatchAs) and c.pattern.pattern is None and c.pattern.name is None for c in last.cases)
        return wild and all(_always_returns(c.body) for c in last.cases)
    if isinstance(last, ast.Assert) and isinstance(last.test, ast.Constant) and not last.test.value:
        return True
    return False


def _loop_level(body):
    """Statements of a loop body, not entering nested loops (whose break does not leave this one)."""
    for st in body:
        yield st
        if isinstance(st, (ast.While, ast.For)):
            continue
        for field in ('body', 'orelse'):
            yield from _loop_level(getattr(st, field, []) or [])
        if isinstance(st, ast.Match):
            for case in st.cases:
                yield from _loop_level(case.body)


# -------------------------------------------------------------------------------------------- driver

def translate_module(source, path='<module>', target='x86_64'):
    m = Module(source, path, target)
    m.check()
    stem = Path(str(path)).stem
    return m, m.emit(Path(str(path)).name), m.header(stem), sorted(fn.cname for fn in m.funcs.values() if fn.extern)


def translate(source, path='<module>', target='x86_64'):
    """Source text -> (C text, header text, declared extern names). Raises Refusal."""
    return translate_module(source, path, target)[1:]


CFLAGS = ['-std=c11', '-O2', '-ffreestanding', '-fno-builtin', '-nostdlib', '-fno-stack-protector',
          '-fno-asynchronous-unwind-tables', '-fno-exceptions', '-Wall', '-Wno-unused-function',
          '-Werror=address-of-packed-member', '-fcf-protection=none']
TARGET_FLAGS = {'x86_64': [], 'i386': ['-m32', '-fno-pic', '-fno-pie']}
INTERRUPT_FLAGS = ['-mgeneral-regs-only', '-mno-red-zone']      # what GCC needs for __attribute__((interrupt))
LIBGCC_SYMBOLS = ('__udivdi3', '__umoddi3', '__divdi3', '__moddi3')


def undefined_symbols(obj):
    nm = shutil.which('nm')
    if nm is None:
        return None
    out = subprocess.run([nm, '-u', str(obj)], capture_output=True, text=True, check=True).stdout
    return sorted(line.split()[-1] for line in out.splitlines() if line.strip())


def build(source_path, output, cc=None, target='x86_64'):
    """Write `output` (.c or .o) and the header beside it. Returns a report dict; raises Refusal / RuntimeError."""
    source_path, output = Path(source_path), Path(output)
    text = source_path.read_text(encoding='utf-8-sig')
    module, c_text, h_text, externs = translate_module(text, source_path, target)
    header = output.with_suffix('.h')
    report = {'output': str(output), 'header': str(header), 'externs': externs}
    if target != 'x86_64':
        report['target'] = target
    if module.interrupts:
        report['interrupts'] = True
    if output.suffix == '.c':
        output.write_text(c_text, encoding='utf-8')
        header.write_text(h_text, encoding='utf-8')
        return report
    compiler = cc or os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc')
    if not compiler:
        raise RuntimeError('no C compiler (cc or gcc) on PATH')
    extra = shlex.split(os.environ.get('AIL_FS_CFLAGS', ''))
    with tempfile.TemporaryDirectory(prefix='ail-fs-') as tmp:
        c_path = Path(tmp) / (source_path.stem + '.c')
        c_path.write_text(c_text, encoding='utf-8')
        flags = [*CFLAGS, *TARGET_FLAGS[target], *(INTERRUPT_FLAGS if module.interrupts else [])]
        result = subprocess.run([*shlex.split(compiler), *flags, *extra, '-c', str(c_path), '-o', str(Path(tmp) / 'out.o')],
                                capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError('C compiler failed on the freestanding output:\n' + result.stderr)
        undefined = undefined_symbols(Path(tmp) / 'out.o')
        if undefined is not None:
            stray = [s for s in undefined if s not in externs]
            if stray:
                hint = ''
                if any(s in LIBGCC_SYMBOLS for s in stray):
                    hint = ('; 64-bit // and %% on a 32-bit target call libgcc: write instead: 32-bit division, a shift, '
                            'or define %s in the kernel and declare it with @extern' % ', '.join(s for s in stray if s in LIBGCC_SYMBOLS))
                raise RuntimeError('the object references undeclared symbols %s (only @extern functions may be undefined)%s'
                                   % (', '.join(stray), hint))
            report['undefined'] = undefined
        shutil.copyfile(Path(tmp) / 'out.o', output)
    header.write_text(h_text, encoding='utf-8')
    return report


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description='compile an AIL freestanding module to C or an object')
    ap.add_argument('source')
    ap.add_argument('-o', '--output', required=True)
    ap.add_argument('--m32', action='store_true', help='32-bit x86 target (usize is 32 bits; compiled with gcc -m32)')
    a = ap.parse_args(argv)
    try:
        report = build(a.source, a.output, target='i386' if a.m32 else 'x86_64')
    except Refusal as error:
        print(error.text(a.source), file=sys.stderr)
        return 3
    except RuntimeError as error:
        print('AIL freestanding: %s' % error, file=sys.stderr)
        return 2
    print(report)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
