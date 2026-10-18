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
        # a function's own locals, and the lists it owns (`Own(fn,x)`, possibly inside `Elem(..)` or
        # `Spine(..)`), are invisible to its callers
        marks = ('Local(%s,' % fn_name, 'Own(%s,' % fn_name)
        return Effects([l for l in self.reads if not any(m in l for m in marks)],
                       [l for l in self.writes if not any(m in l for m in marks)],
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
INDEX = 'IndexError'
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
        if ins.attrs.get('mode') == 'nonneg':
            return NONE            # the range pass proved the divisor >= 1 and the dividend >= 0
        divisor = const_value(ins.operands[1], defs if defs is not None else defs_of(fn))
        if isinstance(divisor, (int, float)) and not isinstance(divisor, bool) and divisor != 0:
            # a non-zero constant divisor: no ZeroDivisionError; INT64_MIN // -1 is the one overflow
            return Effects(raises=[OVERFLOW]) if op == 'floordiv' and divisor == -1 else NONE
        return Effects(raises=_ALWAYS_RAISES[op])
    if op in _CHECKED_RAISES:
        mode = ins.attrs.get('mode', 'ck')
        return Effects(raises=_CHECKED_RAISES[op]) if mode == 'ck' else NONE
    if op in ('bytes.get', 'list.get', 'list.set'):
        eff = Effects(raises=[INDEX]) if ins.attrs.get('mode', 'ck') == 'ck' else NONE
        if op == 'list.set':
            eff = eff | Effects(writes=['Elem(%s)' % _root(ins.operands[0], fn, defs)])
        elif op == 'list.get':
            eff = eff | Effects(reads=['Elem(%s)' % _root(ins.operands[0], fn, defs)])
        return eff
    if op in ('list.push', 'list.pop', 'list.clear', 'list.len'):
        root = _root(ins.operands[0], fn, defs)
        loc = 'Elem(%s)' % root
        if op == 'list.len':
            return Effects(reads=[loc])
        # a resize also writes the list's spine (data pointer and length): what span hoisting and
        # the range facts about len() depend on
        return Effects(reads=[loc], writes=[loc, 'Spine(%s)' % root], raises=[INDEX] if op == 'list.pop' else [])
    if op in ('field.list', 'list.ref', 'field.plist'):
        return NONE
    if op in ('plist.len', 'plist.get', 'plist.has'):
        eff = Effects(reads=['Elem(%s)' % _root(ins.operands[0], fn, defs)])
        if op == 'plist.get' and ins.attrs.get('mode', 'ck') == 'ck':
            eff = eff | Effects(raises=[INDEX])
        return eff
    if op == 'list.sortperm':
        perm = _root(ins.operands[0], fn, defs)
        eff = Effects(reads=['Elem(%s)' % perm], writes=['Elem(%s)' % perm, 'Spine(%s)' % perm, 'Rebind(%s)' % perm],
                      raises=[VALUE, rtc.DIE])
        for c in ins.operands[1:]:
            eff = eff | Effects(reads=['Elem(%s)' % _root(c, fn, defs)])
        return eff
    if op == 'list.permute':
        loc = 'Elem(%s)' % _root(ins.operands[0], fn, defs)
        return Effects(reads=[loc, 'Elem(%s)' % _root(ins.operands[1], fn, defs)], writes=[loc], raises=[rtc.DIE])
    if op in ('rec.push', 'rec.up', 'rec.pop'):
        root = _root(ins.operands[0], fn, defs)
        loc = 'Elem(%s)' % root
        if op == 'rec.up':
            return Effects(reads=[loc], writes=[loc])
        return Effects(reads=[loc], writes=[loc, 'Spine(%s)' % root],
                       raises=[INDEX] if op == 'rec.pop' else [rtc.DIE])
    if op in ('dict.has', 'dict.need', 'dict.get', 'dict.put', 'dict.len', 'dict.reset'):
        names = places if places is not None else place_names(fn)
        loc = 'Local(%s,%s)' % (fn.name, names.get(ins.operands[0], '?'))
        if op in ('dict.put', 'dict.reset'):
            return Effects(reads=[loc], writes=[loc], raises=[rtc.DIE])
        return Effects(reads=[loc], raises=[rtc.DIE] if op == 'dict.need' else [])
    if op == 'list.has':
        return Effects(reads=['Elem(%s)' % _root(ins.operands[0], fn, defs)])
    if op == 'list.sort':
        loc = 'Elem(%s)' % _root(ins.operands[0], fn, defs)
        return Effects(reads=[loc], writes=[loc], raises=[VALUE] if ins.operands[0].type.args[0].args[0] == I.F64 else [])
    if op == 'list.join':
        return Effects(reads=['Elem(%s)' % _root(ins.operands[1], fn, defs)], allocs=[rtc.ARENA], raises=[rtc.DIE])
    if op in ('list.reset', 'list.repeat', 'list.lit', 'list.reserve', 'list.move', 'list.call',
              'list.copy', 'list.share', 'list.rt'):
        # these replace or grow the content of the list(s) they name (the destination first)
        refs = ins.operands[:2] if op in ('list.move', 'list.copy', 'list.share') else ins.operands[:1]
        eff = NONE
        for k, r in enumerate(refs):
            root = _root(r, fn, defs)
            eff = eff | Effects(reads=['Elem(%s)' % root], writes=['Elem(%s)' % root, 'Spine(%s)' % root])
            if k == 0 and op != 'list.reserve':
                # the destination's list is replaced (rebound), not only resized: a borrow of the
                # old list (S3b, ownership.py) must not outlive it
                eff = eff | Effects(writes=['Rebind(%s)' % root])
        if op == 'list.rt':
            eff = eff | rtc.LIST_ENTRIES[ins.attrs['callee']]['effects']
        if op == 'list.call':
            sym = ins.attrs.get('callee')
            callee = program.functions.get(sym) if program is not None else None
            if summaries is not None and sym in summaries:
                eff = eff | summaries[sym]
            elif callee is not None and callee.effects is not None:
                eff = eff | callee.effects
            else:
                eff = eff | UNKNOWN
        return eff
    if op == 'ba.call':
        names = places if places is not None else place_names(fn)
        sym = ins.attrs.get('callee')
        callee = program.functions.get(sym) if program is not None else None
        if summaries is not None and sym in summaries:
            base = summaries[sym]
        elif callee is not None and callee.effects is not None:
            base = callee.effects
        else:
            base = UNKNOWN
        return base | Effects(writes=['Local(%s,%s)' % (fn.name, names.get(ins.operands[0], '?'))])
    if op in ('ba.new', 'ba.drop'):
        names = places if places is not None else place_names(fn)
        return Effects(writes=['Local(%s,%s)' % (fn.name, names.get(ins.operands[0], '?'))])
    if op == 'ba.clear':
        root = _root(ins.operands[0], fn, defs)
        return Effects(reads=['Elem(%s)' % root], writes=['Elem(%s)' % root, 'Spine(%s)' % root])
    if op == 'field.ba':
        return Effects(reads=['Field(%s,%s)' % (ins.attrs.get('cls', '?'), ins.attrs.get('name', '?'))])
    if op == 'ba.extend_lit':
        root = _root(ins.operands[0], fn, defs)
        return Effects(reads=['Elem(%s)' % root], writes=['Elem(%s)' % root, 'Spine(%s)' % root], raises=[VALUE])
    if op == 'obj.init':
        names = places if places is not None else place_names(fn)
        eff = Effects(writes=['Local(%s,%s)' % (fn.name, names.get(ins.operands[0], '?'))])
        for v, a in zip(ins.operands[1:], ins.attrs.get('abi') or []):
            if a == 'list':
                root = _root(v, fn, defs)
                eff = eff | Effects(reads=['Elem(%s)' % root], writes=['Elem(%s)' % root, 'Spine(%s)' % root,
                                                                       'Rebind(%s)' % root])
        return eff | Effects(allocs=['Heap'])
    if op == 'obj.copyref':
        names = places if places is not None else place_names(fn)
        return Effects(writes=['Local(%s,%s)' % (fn.name, names.get(ins.operands[0], '?'))])
    if op == 'ba.extend':
        root = _root(ins.operands[0], fn, defs)
        return Effects(reads=['Elem(%s)' % root], writes=['Elem(%s)' % root, 'Spine(%s)' % root], raises=[VALUE])
    if op == 'ba.write':
        return Effects(reads=['Elem(%s)' % _root(ins.operands[0], fn, defs)], io=True)
    if op in ('ba.len', 'ba.get', 'ba.set', 'ba.push'):
        loc = 'Elem(%s)' % _root(ins.operands[0], fn, defs)
        if op == 'ba.len':
            return Effects(reads=[loc])
        if op == 'ba.get':
            return Effects(reads=[loc], raises=[INDEX] if ins.attrs.get('mode', 'ck') == 'ck' else [])
        if op == 'ba.set':
            return Effects(writes=[loc], raises=[INDEX, VALUE] if ins.attrs.get('mode', 'ck') == 'ck' else [])
        return Effects(reads=[loc], writes=[loc, 'Spine(%s)' % _root(ins.operands[0], fn, defs)], raises=[VALUE])
    if op in ('span.of', 'span.len'):
        return NONE if op == 'span.len' else Effects(reads=['Elem(%s)' % _root(ins.operands[0], fn, defs)])
    if op in ('span.get', 'span.set'):
        d = (defs if defs is not None else defs_of(fn)).get(ins.operands[0])
        loc = 'Elem(%s)' % (_root(d.operands[0], fn, defs) if d is not None and d.op == 'span.of' else 'Any')
        eff = Effects(raises=[INDEX]) if ins.attrs.get('mode', 'ck') == 'ck' else NONE
        if op == 'span.set' and ins.operands[0].type == I.T('span', I.T('u8')) and ins.attrs.get('mode', 'ck') == 'ck':
            eff = eff | Effects(raises=[VALUE])
        return eff | (Effects(writes=[loc]) if op == 'span.set' else Effects(reads=[loc]))
    if op in ('field.get', 'field.set'):
        loc = 'Field(%s,%s)' % (ins.attrs.get('cls', '?'), ins.attrs.get('name', '?'))
        return Effects(reads=[loc]) if op == 'field.get' else Effects(writes=[loc])
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
    if op == 'print':
        return Effects(io=True, writes=['Global(rt,stdout)'])
    if op in ('str.lit', 'bytes.lit'):
        return NONE
    if op == 'raise':
        return Effects(raises=[ins.attrs.get('name', 'Exception')])
    if op == 'reraise':
        return Effects(raises=['Exception'])
    if op == 'for.range':
        step = const_value(ins.operands[2], defs) if defs is not None else None
        return NONE if isinstance(step, int) and step != 0 else Effects(raises=[VALUE])
    return NONE


def _root(v, fn, defs=None):
    """The abstract location of a container value: `Field(C,f)` for a struct field's list,
    `Param(fn,p)` for a parameter, else `Any`."""
    for p, n in zip(fn.params, fn.param_names):
        if p is v:
            return 'Param(%s,%s)' % (fn.name, n)
    defs = defs if defs is not None else defs_of(fn)
    d = defs.get(v)
    if d is not None and d.op in ('field.list', 'field.plist'):
        return 'Field(%s,%s)' % (d.attrs.get('cls', '?'), d.attrs.get('name', '?'))
    if d is not None and d.op == 'field.ba':
        return 'Field(%s,%s)' % (d.attrs.get('cls', '?'), d.attrs.get('name', '?'))
    if d is not None and d.op == 'list.ref':
        place = defs.get(d.operands[0])
        return 'Own(%s,%s)' % (fn.name, place.attrs.get('name', '?') if place is not None else '?')
    return 'Any'



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


# the text stage's runtime calls (rtc.py); imported last because it builds on the names above
from . import rtc      # noqa: E402,F401  (registers its entries in RUNTIME)
