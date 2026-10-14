"""IR data structures: types (design §2.2), values, instructions with regions and block
arguments (§2.1), functions, programs, and the op table (§2.4).

Everything here is plain data. Typing and structural rules live in `verify.py`, effects in
`effects.py`, the textual form in `text.py`.
"""

# --------------------------------------------------------------------------------------------
# Types
#
# One immutable class for every type: a head and type arguments, plus a name for class types.
# The table of heads below is the whole of §2.2 from day one (S0 lowers only scalars, but the
# semantic container types exist so no later stage has to re-plumb the type representation).
# --------------------------------------------------------------------------------------------

INT_SCALARS = ('i1', 'i8', 'i16', 'i32', 'i64', 'u8', 'u16', 'u32', 'u64')
FLOAT_SCALARS = ('f32', 'f64')
SCALARS = INT_SCALARS + FLOAT_SCALARS
TEXT = ('str', 'strv', 'bytes', 'bytesv')
LEAVES = SCALARS + TEXT + ('exc',)
# head -> number of type arguments (None: any number)
HEADS = dict({h: 0 for h in LEAVES}, tup=None, opt=1, obj=1, list=1, dict=2, set=1, bytearray=0,
             cell=1, fn=2, closure=2, place=1)
# heads that may only appear directly under obj<..>
OBJ_INNER = ('list', 'dict', 'set', 'bytearray', 'class')


class Type(object):
    __slots__ = ('head', 'args', 'name', '_key')

    def __init__(self, head, args=(), name=None):
        self.head = head
        self.args = tuple(args)
        self.name = name
        self._key = (head, self.args, name)

    def __eq__(self, other):
        return isinstance(other, Type) and self._key == other._key

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash(self._key)

    def __repr__(self):
        return 'Type(%s)' % self

    def __str__(self):
        if self.head == 'class':
            return self.name
        if self.head in ('fn', 'closure'):
            params, results = self.args
            return '%s<(%s) -> (%s)>' % (self.head, ', '.join(map(str, params.args)),
                                         ', '.join(map(str, results.args)))
        if not self.args and HEADS.get(self.head) == 0:
            return self.head
        return '%s<%s>' % (self.head, ', '.join(map(str, self.args)))

    @property
    def is_scalar(self):
        return self.head in SCALARS

    @property
    def is_int(self):
        return self.head in INT_SCALARS

    @property
    def is_float(self):
        return self.head in FLOAT_SCALARS

    @property
    def is_place(self):
        return self.head == 'place'

    @property
    def pointee(self):
        assert self.head == 'place'
        return self.args[0]


def T(head, *args):
    return Type(head, args)


def class_type(name):
    return Type('class', (), name)


def fn_type(params, results, closure=False):
    return Type('closure' if closure else 'fn', (Type('tup', params), Type('tup', results)))


I1, I64, F64 = T('i1'), T('i64'), T('f64')


def place(t):
    return Type('place', (t,))


def type_errors(t, under_obj=False):
    """Well-formedness of a type against the §2.2 table; a list of messages (empty if fine)."""
    if not isinstance(t, Type):
        return ['not a type: %r' % (t,)]
    if t.head == 'class':
        if not under_obj:
            return ['class type %s must appear as obj<%s>' % (t.name, t.name)]
        return [] if t.name and t.name.isidentifier() else ['bad class name %r' % t.name]
    if t.head not in HEADS:
        return ['unknown type head %r' % t.head]
    arity = HEADS[t.head]
    if arity is not None and len(t.args) != arity:
        return ['%s takes %d type argument(s), got %d' % (t.head, arity, len(t.args))]
    if t.head in OBJ_INNER and not under_obj:
        return ['%s must appear as obj<%s>' % (t.head, t)]
    if t.head == 'obj':
        inner = t.args[0]
        if inner.head not in OBJ_INNER:
            return ['obj<..> holds a list, dict, set, bytearray or class, not %s' % inner]
        return type_errors(inner, under_obj=True)
    if t.head in ('fn', 'closure'):
        errs = []
        for part in t.args:
            if part.head != 'tup':
                errs.append('malformed function type %s' % t)
            else:
                for a in part.args:
                    errs.extend(type_errors(a))
        return errs
    if t.head in ('list', 'set', 'dict'):
        errs = []
        for a in t.args:
            errs.extend(type_errors(a))
        return errs
    errs = []
    for a in t.args:
        errs.extend(type_errors(a))
    if t.head == 'place' and not errs and t.args[0].head == 'place':
        errs.append('place of a place')
    return errs


# --------------------------------------------------------------------------------------------
# Values, instructions, regions, functions
# --------------------------------------------------------------------------------------------

class Value(object):
    """An SSA value: defined once, by an instruction result, a region argument or a parameter."""
    __slots__ = ('type', 'hint')

    def __init__(self, type, hint=None):
        self.type = type
        self.hint = hint

    def __repr__(self):
        return '<%%%s: %s>' % (self.hint or hex(id(self))[-4:], self.type)


class Region(object):
    """A single-block region with block arguments; its last instruction is a terminator."""
    __slots__ = ('args', 'instrs')

    def __init__(self, args=None, instrs=None):
        self.args = list(args or [])
        self.instrs = list(instrs or [])


class Instr(object):
    __slots__ = ('op', 'operands', 'results', 'attrs', 'regions')

    def __init__(self, op, operands=(), results=(), attrs=None, regions=()):
        self.op = op
        self.operands = list(operands)
        self.results = list(results)
        self.attrs = dict(attrs or {})
        self.regions = list(regions)

    def __repr__(self):
        return '<Instr %s>' % self.op

    @property
    def result(self):
        assert len(self.results) == 1, self.op
        return self.results[0]


class Function(object):
    """`params` are SSA values (the body's entry arguments); `param_names` their source names.
    `attrs` carries the C boundary: `sym` (C symbol), `linkage` ('extern' | 'static' |
    'inline_always'), and `fallback` (the legacy fall-off-the-end return value)."""

    def __init__(self, name, params, param_names, results, body=None, attrs=None, effects=None):
        self.name = name
        self.params = list(params)
        self.param_names = list(param_names)
        self.results = list(results)
        self.body = body if body is not None else Region()
        self.attrs = dict(attrs or {})
        self.effects = effects          # declared summary (effects.Effects) or None

    @property
    def sym(self):
        return self.attrs.get('sym', self.name)

    @property
    def signature(self):
        return fn_type([p.type for p in self.params], self.results)


class Program(object):
    """`functions`: IR functions by C symbol. `externs`: signatures (fn types) of functions the
    IR calls but does not own (during migration: functions the legacy emitter compiled)."""

    def __init__(self, functions=None, externs=None):
        self.functions = dict(functions or {})
        self.externs = dict(externs or {})

    def add(self, fn):
        self.functions[fn.sym] = fn
        return fn

    def callee_type(self, sym):
        if sym in self.functions:
            return self.functions[sym].signature
        return self.externs.get(sym)


# --------------------------------------------------------------------------------------------
# The op table (§2.4)
#
# Each op: (min operands, max operands or None, regions, terminator?). Typing is in verify.py.
# RESERVED ops are part of the design's instruction set but belong to later stages; the parser
# accepts them (generic syntax) and the S0 verifier refuses them by name and stage.
# --------------------------------------------------------------------------------------------

ARITH_MODES = ('ck', 'wrap', 'nsw')
CMP_PREDICATES = ('eq', 'ne', 'lt', 'le', 'gt', 'ge')

INT_BINARY = ('add', 'sub', 'mul', 'floordiv', 'floormod', 'pow', 'and', 'or', 'xor', 'shl', 'shr')
FLOAT_BINARY = ('fadd', 'fsub', 'fmul', 'fdiv', 'ffloordiv', 'ffloormod', 'fpow')

OPS = {}


def _op(name, nmin, nmax, regions=0, terminator=False):
    OPS[name] = (nmin, nmax, regions, terminator)


_op('const', 0, 0)
for _name in INT_BINARY + FLOAT_BINARY:
    _op(_name, 2, 2)
for _name in ('neg', 'inv', 'fneg', 'zext', 'sitofp', 'fptosi'):
    _op(_name, 1, 1)
for _pred in CMP_PREDICATES:
    _op('cmp.' + _pred, 2, 2)
_op('select', 3, 3)
_op('local.alloc', 0, 0)
_op('load', 1, 1)
_op('store', 2, 2)
_op('call', 0, None)
_op('rt', 0, None)
_op('if', 1, 1, regions=2)
_op('loop', 0, None, regions=1)
_op('for.range', 3, None, regions=1)
for _name in ('yield', 'break', 'continue', 'return'):
    _op(_name, 0, None, terminator=True)
_op('unreachable', 0, 0, terminator=True)

LOOP_OPS = ('loop', 'for.range')

RESERVED = {}
for _name in ('field', 'elem', 'slot', 'tupfield', 'env', 'global', 'borrow', 'take', 'copy', 'move',
              'drop', 'call.indirect', 'closure.make', 'tup.make', 'tup.get', 'opt.none', 'opt.some',
              'opt.is_some', 'opt.get', 'par.for'):
    RESERVED[_name] = 'S1'
for _name in ('try', 'raise', 'exc.new'):
    RESERVED[_name] = 'S2'
for _name in ('list.new', 'list.lit', 'list.repeat', 'list.len', 'list.push', 'list.pop', 'list.insert',
              'list.extend', 'list.slice', 'list.sort', 'dict.new', 'set.new', 'dict.get', 'dict.contains',
              'dict.put', 'dict.del', 'dict.upsert', 'dict.items', 'dict.keys', 'dict.values', 'heap.push',
              'heap.pop', 'copy.list', 'copy.dict', 'copy.set', 'box.wrap', 'rc.inc', 'rc.dec', 'is'):
    RESERVED[_name] = 'S3'
for _name in ('str.lit', 'str.len.bytes', 'str.len.cp', 'str.byte', 'str.cp_at', 'str.cat', 'str.append',
              'str.slice', 'str.split', 'str.fmt', 'str.eq', 'str.lt', 'str.hash', 'print',
              'region.enter', 'region.exit'):
    RESERVED[_name] = 'S4'
for _name in ('obj.new', 'reuse.token', 'obj.new.reuse'):
    RESERVED[_name] = 'S5'


def is_known_op(name):
    return name in OPS or name in RESERVED


def walk(region):
    """Every instruction in `region`, depth first, in program order."""
    for ins in region.instrs:
        yield ins
        for r in ins.regions:
            for sub in walk(r):
                yield sub


class IRError(Exception):
    """Malformed IR (a verifier failure), or IR the S0 emitter cannot emit."""
