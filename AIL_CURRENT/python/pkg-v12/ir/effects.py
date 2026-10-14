"""Effect records (design §2.4: every instruction has one), the runtime catalogue for the S0
subset, and per-function summaries.

An effect record names abstract locations (§2.3) as strings: `Local(fn,x)`, `Global(m,x)`.
Locals of a function are invisible to its callers, so a summary drops them.
"""
from . import ir as I


class Effects(object):
    __slots__ = ('reads', 'writes', 'allocs', 'raises', 'io', 'unknown')
    FIELDS = ('reads', 'writes', 'allocs', 'raises', 'io', 'unknown')

    def __init__(self, reads=(), writes=(), allocs=(), raises=(), io=False, unknown=False):
        self.reads = frozenset(reads)
        self.writes = frozenset(writes)
        self.allocs = frozenset(allocs)
        self.raises = frozenset(raises)
        self.io = bool(io)
        self.unknown = bool(unknown)

    def __or__(self, other):
        return Effects(self.reads | other.reads, self.writes | other.writes,
                       self.allocs | other.allocs, self.raises | other.raises,
                       self.io or other.io, self.unknown or other.unknown)

    def __eq__(self, other):
        return isinstance(other, Effects) and all(getattr(self, f) == getattr(other, f)
                                                  for f in self.FIELDS)

    def __ne__(self, other):
        return not self == other

    def __repr__(self):
        return 'Effects(%s)' % ', '.join('%s=%r' % (f, getattr(self, f)) for f in self.FIELDS
                                         if getattr(self, f))

    def covers(self, other):
        """Whether a declared summary `self` admits everything `other` may do."""
        if self.unknown:
            return True
        if other.unknown:
            return False
        return (other.reads <= self.reads and other.writes <= self.writes
                and other.allocs <= self.allocs and other.raises <= self.raises
                and (self.io or not other.io))

    def without_locals(self, fn_name):
        prefix = 'Local(%s,' % fn_name
        return Effects([l for l in self.reads if not l.startswith(prefix)],
                       [l for l in self.writes if not l.startswith(prefix)],
                       self.allocs, self.raises, self.io, self.unknown)

    @property
    def pure(self):
        return not (self.reads or self.writes or self.allocs or self.raises or self.io
                    or self.unknown)


NONE = Effects()
UNKNOWN = Effects(unknown=True)
OVERFLOW = 'OverflowError'
ZERODIV = 'ZeroDivisionError'
VALUE = 'ValueError'
RECURSION = 'RecursionError'
DEPTH = 'Global(rt,ail_depth)'

# Runtime entry points the S0 subset calls through `rt @name`: (param types, result types, effects).
RUNTIME = {
    'ail_depth_enter': ((), (), Effects(reads=[DEPTH], writes=[DEPTH], raises=[RECURSION])),
    'ail_depth_leave': ((), (), Effects(reads=[DEPTH], writes=[DEPTH])),
}

# Per-op raise sets for checked (`ck`) modes; ops absent here never raise.
_CHECKED_RAISES = {
    'add': (OVERFLOW,), 'sub': (OVERFLOW,), 'mul': (OVERFLOW,), 'neg': (OVERFLOW,),
    'shl': (OVERFLOW, VALUE), 'shr': (VALUE,), 'pow': (OVERFLOW, VALUE),
    'fptosi': (VALUE,),
}
_ALWAYS_RAISES = {
    'floordiv': (ZERODIV, OVERFLOW), 'floormod': (ZERODIV,),
    'fdiv': (ZERODIV,), 'ffloordiv': (ZERODIV,), 'ffloormod': (ZERODIV,),
}


def place_names(fn):
    """{place value: source name} for the function's local places."""
    out = {}
    for ins in I.walk(fn.body):
        if ins.op == 'local.alloc':
            out[ins.result] = ins.attrs.get('name', '?')
    return out


def const_value(value, defs):
    ins = defs.get(value)
    if ins is not None and ins.op == 'const':
        return ins.attrs.get('value')
    return None


def instr_effects(ins, fn, program, places=None, defs=None, summaries=None):
    """The effect record of one instruction itself (not of its nested regions)."""
    op = ins.op
    if op in ('load', 'store'):
        names = places if places is not None else place_names(fn)
        loc = 'Local(%s,%s)' % (fn.name, names.get(ins.operands[0], '?'))
        return Effects(reads=[loc]) if op == 'load' else Effects(writes=[loc])
    if op in _ALWAYS_RAISES:
        divisor = const_value(ins.operands[1], defs if defs is not None else defs_of(fn))
        if isinstance(divisor, (int, float)) and not isinstance(divisor, bool) and divisor != 0:
            # a non-zero constant divisor: no ZeroDivisionError; INT64_MIN // -1 is the one overflow
            return Effects(raises=[OVERFLOW]) if op == 'floordiv' and divisor == -1 else NONE
        return Effects(raises=_ALWAYS_RAISES[op])
    if op in _CHECKED_RAISES:
        mode = ins.attrs.get('mode', 'ck')
        return Effects(raises=_CHECKED_RAISES[op]) if mode == 'ck' else NONE
    if op == 'call':
        sym = ins.attrs.get('callee')
        if summaries is not None and sym in summaries:
            return summaries[sym]
        callee = program.functions.get(sym) if program is not None else None
        if callee is not None and callee.effects is not None:
            return callee.effects
        return UNKNOWN
    if op == 'rt':
        entry = RUNTIME.get(ins.attrs.get('callee'))
        return entry[2] if entry else UNKNOWN
    if op == 'for.range':
        step = const_value(ins.operands[2], defs) if defs is not None else None
        return NONE if isinstance(step, int) and step != 0 else Effects(raises=[VALUE])
    return NONE


def defs_of(fn):
    return {r: ins for ins in I.walk(fn.body) for r in ins.results}


def body_effects(fn, program, summaries=None):
    places, defs = place_names(fn), defs_of(fn)
    total = NONE
    for ins in I.walk(fn.body):
        total = total | instr_effects(ins, fn, program, places, defs, summaries)
    return total


def summarize(fn, program, summaries=None):
    """The function's summary: everything its body may do, minus its own locals."""
    return body_effects(fn, program, summaries).without_locals(fn.name)


def summarize_program(program):
    """Summaries for every IR function, iterated to a fixed point over (mutual) recursion."""
    summaries = {sym: NONE for sym in program.functions}
    changed = True
    while changed:
        changed = False
        for sym, fn in program.functions.items():
            new = summarize(fn, program, summaries)
            if new != summaries[sym]:
                summaries[sym] = new
                changed = True
    for sym, fn in program.functions.items():
        fn.effects = summaries[sym]
    return summaries
