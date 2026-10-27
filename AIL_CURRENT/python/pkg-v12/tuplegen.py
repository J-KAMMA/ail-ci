"""Types and generated helper code for tuplib.py (tuples lowered onto classes).

A tuple type is a class `_AilT_<codes>` with fields f0, f1, ... (one class per element-type list).  The
helpers below are plain Python-syntax source, appended to the program by tuplib.py and compiled by the
ordinary typed path: repr, lexicographic compare, equality, hash, an insertion-ordered open-addressing
table for dict / set keyed by (or valued with) tuples, linear list helpers, divmod, partition.  Nothing
here touches the C runtime.
"""
import re

INT, FLT, STR, BOOL, BYTES = 'int', 'float', 'str', 'bool', 'bytes'
SCALARS = (INT, FLT, STR, BOOL)


class Refused(Exception):
    """(line, message): a use this lowering does not build."""


class Hole:
    """An element type that is not known yet (an empty `[]`); filled by the first append / store."""
    def __init__(self):
        self.t = None


def R(t):
    while isinstance(t, Hole):
        t = t.t
    return t


def deep(t):
    """The type with every filled hole replaced; an unfilled hole is None."""
    t = R(t)
    if not isinstance(t, tuple):
        return t
    kind = t[0]
    if kind == 'tuple':
        return ('tuple', tuple(deep(e) for e in t[1]))
    if kind in ('list', 'set', 'opt', 'iter'):
        return (kind, deep(t[1]))
    if kind == 'dict':
        return ('dict', deep(t[1]), deep(t[2]))
    if kind == 'callable':
        return ('callable', tuple(deep(p) for p in t[1]), deep(t[2]))
    return t


def is_tuple(t):
    t = R(t)
    return isinstance(t, tuple) and t[0] == 'tuple'


def has_tuple(t):
    t = R(t)
    if not isinstance(t, tuple):
        return False
    if t[0] == 'tuple':
        return True
    if t[0] in ('list', 'set', 'opt', 'iter'):
        return has_tuple(t[1])
    if t[0] == 'dict':
        return has_tuple(t[1]) or has_tuple(t[2])
    if t[0] == 'callable':
        return any(has_tuple(p) for p in t[1]) or has_tuple(t[2])
    return False


def is_table_dict(t):
    t = R(t)
    return isinstance(t, tuple) and t[0] == 'dict' and (has_tuple(t[1]) or has_tuple(t[2]))


def is_table_set(t):
    t = R(t)
    return isinstance(t, tuple) and t[0] == 'set' and has_tuple(t[1])


def is_table(t):
    return is_table_dict(t) or is_table_set(t)


def known(t):
    """True when no hole is left anywhere in t."""
    t = deep(t)
    if t is None:
        return False
    if isinstance(t, tuple):
        if t[0] == 'tuple':
            return all(known(e) for e in t[1])
        if t[0] in ('list', 'set', 'opt', 'iter'):
            return known(t[1])
        if t[0] == 'dict':
            return known(t[1]) and known(t[2])
        if t[0] == 'callable':
            return all(known(p) for p in t[1]) and known(t[2])
    return True


LEAF = {INT: 'i', FLT: 'f', STR: 's', BOOL: 'b', BYTES: 'y'}


def code(t):
    t = deep(t)
    if t in LEAF:
        return LEAF[t]
    if isinstance(t, tuple):
        if t[0] == 'tuple':
            return 'P' + tcode(t) + 'Q'
        if t[0] == 'list':
            return 'L' + code(t[1]) + 'E'
        if t[0] == 'set':
            return 'S' + code(t[1]) + 'E'
        if t[0] == 'dict':
            return 'D' + code(t[1]) + '_' + code(t[2]) + 'E'
        if t[0] == 'cls':
            return 'c%d%s' % (len(t[1]), t[1])
        if t[0] == 'opt':
            return 'O' + code(t[1]) + 'E'
    raise Refused((1, 'the type of a tuple element cannot be told from how it is used; annotate it'))


def tcode(t):
    return '_'.join(code(e) for e in deep(t)[1])


def tname(t):
    return '_AilT_' + tcode(t)


def ann_text(t):
    """The annotation spelling of a (lowered) type."""
    t = deep(t)
    if t in (INT, FLT, STR, BOOL, BYTES):
        return t
    if t == 'none':
        return 'None'
    if isinstance(t, tuple):
        kind = t[0]
        if kind == 'tuple':
            return tname(t)
        if kind == 'list':
            return 'list[%s]' % ann_text(t[1])
        if kind == 'dict':
            if is_table_dict(t):
                return table_name(t[1], t[2])
            return 'dict[%s, %s]' % (ann_text(t[1]), ann_text(t[2]))
        if kind == 'set':
            if is_table_set(t):
                return table_name(t[1], None)
            return 'set[%s]' % ann_text(t[1])
        if kind == 'cls':
            return t[1]
        if kind == 'opt':
            return 'Optional[%s]' % ann_text(t[1])
        if kind == 'callable':
            return 'Callable[[%s], %s]' % (', '.join(ann_text(p) for p in t[1]), ann_text(t[2]))
    raise Refused((1, 'the type of a tuple element cannot be told from how it is used; annotate it'))


def table_name(k, v):
    if v is None:
        return '_AilS_' + code(k)
    return '_AilD_' + code(k) + '__' + code(v)


def sub(text, **kw):
    for key, value in kw.items():
        text = text.replace('@' + key + '@', value)
    return text


def fld(e, i):
    """Field name of element i.  A bool element has its own spelling (fb0): the compiler judges a field by name
    before typing and calls it a bool only when every class defining that name declares it bool."""
    return 'fb%d' % i if deep(e) == BOOL else 'f%d' % i


def leaves(t, path='n'):
    """[(accessor text, type)] of the scalar leaves of a tuple type, depth first."""
    out = []
    for i, e in enumerate(deep(t)[1]):
        e = deep(e)
        p = '%s.%s' % (path, fld(e, i))
        if is_tuple(e):
            out.extend(leaves(e, p))
        else:
            out.append((p, e))
    return out


# --------------------------------------------------------------------------------------------------
# fixed helpers
HFIN = '''def _ail_hfin(h: int) -> int:
    h = wrapping_mul(h ^ (h >> 31), -4658895280553007687)
    return h ^ (h >> 29)
'''
STRHASH = '''def _ail_strhash(s: str) -> int:
    h = 5381
    for ch in s:
        h = wrapping_add(wrapping_mul(h, 33), ord(ch))
    return h
'''
SREPR = r'''def _ail_srepr(s: str) -> str:
    q = "'"
    if "'" in s and '"' not in s:
        q = '"'
    out = [q]
    for ch in s:
        o = ord(ch)
        if ch == q or ch == "\\":
            out.append("\\" + ch)
        elif o == 10:
            out.append("\\n")
        elif o == 13:
            out.append("\\r")
        elif o == 9:
            out.append("\\t")
        elif o < 32 or o == 127 or (o >= 128 and _ail_unprintable(o)):
            out.append(_ail_escape(o))
        else:
            out.append(ch)
    out.append(q)
    return "".join(out)


def _ail_escape(o: int) -> str:
    hexd = "0123456789abcdef"
    if o < 256:
        return "\\x" + hexd[(o >> 4) & 15] + hexd[o & 15]
    if o < 65536:
        return "\\u" + hexd[(o >> 12) & 15] + hexd[(o >> 8) & 15] + hexd[(o >> 4) & 15] + hexd[o & 15]
    r = "\\U"
    shift = 28
    while shift >= 0:
        r += hexd[(o >> shift) & 15]
        shift -= 4
    return r


def _ail_unprintable(o: int) -> bool:
    if o <= 160 or o == 173:
        return True
    if o >= 1536 and o <= 1541:
        return True
    if o == 1564 or o == 1757 or o == 1807 or o == 2274 or o == 5760 or o == 6158 or o == 12288:
        return True
    if o >= 8192 and o <= 8207:
        return True
    if o >= 8232 and o <= 8239:
        return True
    if o >= 8287 and o <= 8303:
        return True
    if o >= 55296 and o <= 63743:
        return True
    if o == 65279 or (o >= 65529 and o <= 65531):
        return True
    return False
'''
DIVMOD_I = '''def _ail_divmod_i(a: int, b: int) -> _AilT_i_i:
    return _AilT_i_i(a // b, a % b)
'''
MODF = '''def _ail_modf(x: float) -> _AilT_f_f:
    t = _ail_c_trunc(x)
    if x - x != 0.0 and x == x:
        return _AilT_f_f(_ail_c_copysign(0.0, x), x)
    f = x - t
    if f == 0.0:
        f = _ail_c_copysign(0.0, x)
    return _AilT_f_f(f, t)
'''
DIVMOD_F = '''def _ail_divmod_f(a: float, b: float) -> _AilT_f_f:
    if b == 0.0:
        raise ZeroDivisionError("float divmod()")
    r = _ail_c_fmod(a, b)
    adjust = r != 0.0 and (r < 0.0) != (b < 0.0)
    q = (a - r) / b
    if adjust:
        q = q - 1.0
    if r == 0.0:
        r = _ail_c_copysign(0.0, b)
    elif adjust:
        r = r + b
    if q == 0.0:
        q = _ail_c_copysign(0.0, a / b)
    else:
        f = _ail_c_floor(q)
        if q - f > 0.5:
            q = f + 1.0
        else:
            q = f
    return _AilT_f_f(q, r)
'''
PARTITION = '''def _ail_partition(s: str, sep: str) -> _AilT_s_s_s:
    i = s.find(sep)
    if len(sep) == 0:
        raise ValueError("empty separator")
    if i < 0:
        return _AilT_s_s_s(s, "", "")
    return _AilT_s_s_s(s[:i], sep, s[i + len(sep):])
'''
RPARTITION = '''def _ail_rpartition(s: str, sep: str) -> _AilT_s_s_s:
    i = s.rfind(sep)
    if len(sep) == 0:
        raise ValueError("empty separator")
    if i < 0:
        return _AilT_s_s_s("", "", s)
    return _AilT_s_s_s(s[:i], sep, s[i + len(sep):])
'''


class Gen:
    """The helper functions and classes a lowered program needs, each emitted once, on demand."""
    def __init__(self):
        self.out = {}          # name -> source text, in the order first needed
        self.building = set()

    def add(self, name, text):
        if name not in self.out:
            self.out[name] = text.rstrip('\n') + '\n'
        return name

    def source(self):
        classes = [text for name, text in self.out.items() if text.startswith('class ')]
        others = [text for name, text in self.out.items() if not text.startswith('class ')]
        return '\n\n'.join(classes + others)

    # -- fixed ----------------------------------------------------------------------------------
    def hfin(self):
        return self.add('_ail_hfin', HFIN)

    def strhash(self):
        return self.add('_ail_strhash', STRHASH)

    def srepr(self):
        self.add('_ail_srepr', SREPR)
        return '_ail_srepr'

    def divmod(self, floats):
        if floats:
            self.tcls(('tuple', (FLT, FLT)))
            return self.add('_ail_divmod_f', DIVMOD_F)
        self.tcls(('tuple', (INT, INT)))
        return self.add('_ail_divmod_i', DIVMOD_I)

    def modf(self):
        self.tcls(('tuple', (FLT, FLT)))
        return self.add('_ail_modf', MODF)

    def partition(self, right=False):
        self.tcls(('tuple', (STR, STR, STR)))
        return self.add('_ail_rpartition' if right else '_ail_partition', RPARTITION if right else PARTITION)

    # -- tuple class and its helpers --------------------------------------------------------------
    def tcls(self, t):
        t = deep(t)
        name = tname(t)
        if name in self.out:
            return name
        elts = t[1]
        params = ', '.join('%s: %s' % (fld(e, i), ann_text(e)) for i, e in enumerate(elts))
        body = '\n'.join('        self.%s = %s' % (fld(e, i), fld(e, i)) for i, e in enumerate(elts))
        if not elts:
            body = '        pass'   # the empty tuple: a class with no fields still needs a body
        self.out[name] = 'class %s:\n    def __init__(self, %s):\n%s\n' % (name, params, body)
        for e in elts:
            if is_tuple(e):
                self.tcls(e)
        return name

    def repr_expr(self, t, x):
        t = deep(t)
        if t in (INT, FLT, BOOL):
            return 'str(%s)' % x
        if t == STR:
            return '%s(%s)' % (self.srepr(), x)
        if is_tuple(t):
            return '%s(%s)' % (self.trepr(t), x)
        if isinstance(t, tuple) and t[0] == 'list':
            return '%s(%s)' % (self.lrepr(t), x)
        if isinstance(t, tuple) and t[0] == 'opt':
            return '%s(%s)' % (self.orepr(t), x)
        raise Refused((1, 'a tuple element of this type has no repr here (int, float, bool, str, tuples and '
                       'lists of those are built)'))

    def trepr(self, t):
        t = deep(t)
        name = '_ail_trepr_' + tcode(t)
        if name in self.out:
            return name
        self.out[name] = None
        cls = self.tcls(t)
        elts = t[1]
        if not elts:
            self.out[name] = 'def %s(t: %s) -> str:\n    return "()"\n' % (name, cls)
            return name
        parts = ' + ", " + '.join(self.repr_expr(e, 't.' + fld(e, i)) for i, e in enumerate(elts))
        tail = ' + ",)"' if len(elts) == 1 else ' + ")"'
        self.out[name] = 'def %s(t: %s) -> str:\n    return "(" + %s%s\n' % (name, cls, parts, tail)
        return name

    def orepr(self, t):
        t = deep(t)
        name = '_ail_orepr_' + code(t[1])
        if name in self.out:
            return name
        self.out[name] = None
        self.out[name] = ('def %s(x: %s) -> str:\n    if x is None:\n        return "None"\n    return %s\n'
                          % (name, ann_text(t), self.repr_expr(t[1], 'x')))
        return name

    def lrepr(self, t):
        t = deep(t)
        name = '_ail_lrepr_' + code(t[1])
        if name in self.out:
            return name
        self.out[name] = None
        elem = ann_text(t[1])
        # `repr()` as a name is shadowable (a program may define its own `repr`); `%r` is the
        # built-in conversion and still uses the VALUE's repr if a heap or slice store put
        # another scalar type into a slot whose annotation says otherwise.  It includes a str
        # slot: `_ail_srepr` takes a str and would raise on an int that reached a list[str].
        if t[1] in SCALARS:
            shown = '("%r" % (x,))'
        else:
            shown = self.repr_expr(t[1], 'x')
        self.out[name] = ('def %s(xs: list[%s]) -> str:\n    parts: list[str] = []\n    for x in xs:\n'
                          '        parts.append(%s)\n    return "[" + ", ".join(parts) + "]"\n'
                          % (name, elem, shown))
        return name

    def tcmp(self, t):
        """-1 / 0 / 1; a nan field raises (CPython's identity shortcut cannot be reproduced)."""
        t = deep(t)
        name = '_ail_tcmp_' + tcode(t)
        if name in self.out:
            return name
        self.out[name] = None
        cls = self.tcls(t)
        lines = ['def %s(a: %s, b: %s) -> int:' % (name, cls, cls)]
        for i, e in enumerate(t[1]):
            e = deep(e)
            x, y = 'a.' + fld(e, i), 'b.' + fld(e, i)
            if is_tuple(e):
                lines += ['    c%d = %s(%s, %s)' % (i, self.tcmp(e), x, y), '    if c%d != 0:' % i,
                          '        return c%d' % i]
                continue
            if e == FLT:
                lines += ['    if %s != %s or %s != %s:' % (x, x, y, y),
                          '        raise ValueError("a tuple comparison reached a nan")']
            if e == BOOL:
                x, y = 'int(%s)' % x, 'int(%s)' % y
            elif e not in (INT, FLT, STR):
                raise Refused((1, 'tuples holding %s cannot be compared here' % (e,)))
            lines += ['    if %s != %s:' % (x, y), '        if %s < %s:' % (x, y), '            return -1',
                      '        return 1']
        lines.append('    return 0')
        self.out[name] = '\n'.join(lines) + '\n'
        return name

    def teq(self, t):
        t = deep(t)
        name = '_ail_teq_' + tcode(t)
        if name in self.out:
            return name
        self.out[name] = None
        cls = self.tcls(t)
        lines = ['def %s(a: %s, b: %s) -> bool:' % (name, cls, cls)]
        for i, e in enumerate(t[1]):
            e = deep(e)
            x, y = 'a.' + fld(e, i), 'b.' + fld(e, i)
            if is_tuple(e):
                lines += ['    if not %s(%s, %s):' % (self.teq(e), x, y), '        return False']
                continue
            if e == FLT:
                lines += ['    if %s != %s or %s != %s:' % (x, x, y, y),
                          '        raise ValueError("a tuple comparison reached a nan")']
            elif e not in (INT, STR, BOOL):
                raise Refused((1, 'tuples holding %s cannot be compared here' % (e,)))
            lines += ['    if %s != %s:' % (x, y), '        return False']
        lines.append('    return True')
        self.out[name] = '\n'.join(lines) + '\n'
        return name

    def thash(self, t):
        t = deep(t)
        name = '_ail_thash_' + tcode(t)
        if name in self.out:
            return name
        self.out[name] = None
        cls = self.tcls(t)
        self.hfin()
        lines = ['def %s(k: %s) -> int:' % (name, cls), '    h = 17']
        for i, e in enumerate(t[1]):
            lines.append('    h = wrapping_add(wrapping_mul(h, 1000003), %s)' % self.hash_leaf(e, 'k.' + fld(e, i)))
        lines.append('    return _ail_hfin(h)')
        self.out[name] = '\n'.join(lines) + '\n'
        return name

    def hash_leaf(self, e, x):
        e = deep(e)
        if e == INT:
            return x
        if e == BOOL:
            return 'int(%s)' % x
        if e == STR:
            self.strhash()
            return '_ail_strhash(%s)' % x
        if is_tuple(e):
            return '%s(%s)' % (self.thash(e), x)
        raise Refused((1, 'a dict key or set element holding %s is not built (int, bool, str and tuples of those '
                       'are)' % ('a float' if e == FLT else str(e),)))

    def key_hash(self, k, x):
        k = deep(k)
        if is_tuple(k):
            return '%s(%s)' % (self.thash(k), x)
        self.hfin()
        return '_ail_hfin(wrapping_mul(%s, -7046029254386353131))' % self.hash_leaf(k, x)

    def key_eq(self, k, a, b):
        k = deep(k)
        if is_tuple(k):
            return '%s(%s, %s)' % (self.teq(k), a, b)
        return '%s == %s' % (a, b)

    # -- list-of-tuple helpers ---------------------------------------------------------------------
    def list_helper(self, op, t):
        t = deep(t)
        c = tcode(t)
        cls = self.tcls(t)
        eq, cmp_ = None, None
        name = '_ail_t%s_%s' % (op, c)
        if name in self.out:
            return name
        self.out[name] = None
        if op == 'in':
            eq = self.teq(t)
            text = ('def %s(xs: list[%s], x: %s) -> bool:\n    for y in xs:\n        if %s(y, x):\n'
                    '            return True\n    return False\n' % (name, cls, cls, eq))
        elif op == 'index':
            eq = self.teq(t)
            text = ('def %s(xs: list[%s], x: %s) -> int:\n    for i in range(len(xs)):\n        if %s(xs[i], x):\n'
                    '            return i\n    raise ValueError(%s(x) + " is not in list")\n'
                    % (name, cls, cls, eq, self.trepr(t)))
        elif op == 'count':
            eq = self.teq(t)
            text = ('def %s(xs: list[%s], x: %s) -> int:\n    n = 0\n    for y in xs:\n        if %s(y, x):\n'
                    '            n += 1\n    return n\n' % (name, cls, cls, eq))
        elif op in ('max', 'min'):
            cmp_ = self.tcmp(t)
            sign = '>' if op == 'max' else '<'
            text = ('def %s(xs: list[%s]) -> %s:\n    if len(xs) == 0:\n        raise ValueError("%s() arg is an '
                    'empty sequence")\n    best = xs[0]\n    for y in xs:\n        if %s(y, best) %s 0:\n'
                    '            best = y\n    return best\n' % (name, cls, cls, op, cmp_, sign))
        elif op == 'leq':
            eq = self.teq(t)
            text = ('def %s(a: list[%s], b: list[%s]) -> bool:\n    if len(a) != len(b):\n        return False\n'
                    '    for i in range(len(a)):\n        if not %s(a[i], b[i]):\n            return False\n'
                    '    return True\n' % (name, cls, cls, eq))
        else:
            raise KeyError(op)
        self.out[name] = text
        return name

    def pair_max(self, op, t):
        name = '_ail_t%s2_%s' % (op, tcode(t))
        if name in self.out:
            return name
        cls = self.tcls(t)
        cmp_ = self.tcmp(t)
        sign = '>' if op == 'max' else '<'
        self.out[name] = ('def %s(a: %s, b: %s) -> %s:\n    if %s(b, a) %s 0:\n        return b\n    return a\n'
                          % (name, cls, cls, cls, cmp_, sign))
        return name

    def bitems(self, k, v):
        """list of (k, v) pairs from a plain dict (d.items() outside a for header)."""
        k, v = deep(k), deep(v)
        pair = ('tuple', (k, v))
        cls = self.tcls(pair)
        name = '_ail_bitems_%s__%s' % (code(k), code(v))
        if name not in self.out:
            self.out[name] = ('def %s(d: dict[%s, %s]) -> list[%s]:\n    out: list[%s] = []\n    for k in d:\n'
                              '        out.append(%s(k, d[k]))\n    return out\n'
                              % (name, ann_text(k), ann_text(v), cls, cls, cls))
        return name

    def rowconst(self, nm, t):
        """A module-level list of number tuples is kept as columns NAME__c0, ...; this rebuilds the list."""
        t = deep(t)
        cls = self.tcls(t)
        name = '_ail_rc_' + nm
        args = ', '.join('%s__c%d[i]' % (nm, j) for j in range(len(t[1])))
        self.out[name] = ('def %s() -> list[%s]:\n    out: list[%s] = []\n    for i in range(len(%s__c0)):\n'
                          '        out.append(%s(%s))\n    return out\n' % (name, cls, cls, nm, cls, args))
        return name

    # -- dict / set tables ---------------------------------------------------------------------------
    def table(self, k, v):
        return Table(self, deep(k), None if v is None else deep(v))


DEPS = {
    'find': (), 'rebuild': (), 'ins': ('rebuild',), 'new': (), 'set': ('find', 'ins'), 'get': ('find',),
    'get1': ('find',), 'sdent': ('find', 'ins'),
    'getd': ('find',), 'has': ('find',), 'del': (), 'pop': ('find', 'del'), 'popd': ('find', 'del'),
    'setdefault': ('find', 'ins'), 'ent': ('find',), 'keys': (), 'vals': (), 'items': (), 'clear': ('new',),
    'copy': (), 'update': ('set',), 'popitem': ('del',),
    'add': ('find', 'ins'), 'discard': ('find', 'del'), 'remove': ('del',), 'spop': ('del',), 'union': ('copy', 'add'),
    'inter': ('new', 'has', 'add'), 'diff': ('new', 'has', 'add'), 'symdiff': ('new', 'has', 'add'),
    'subset': ('has',), 'seq': ('subset',), 'disjoint': ('has',), 'addall': ('add',), 'fromlist': ('new', 'add'),
    'dfromlist': ('new', 'set'),
}


class Table:
    """One insertion-ordered open-addressing table for (K, V) (a dict) or (K, None) (a set)."""
    def __init__(self, gen, k, v):
        self.g, self.k, self.v = gen, k, v
        self.cls = table_name(k, v)
        self.p = self.cls + '_'
        self.is_set = v is None
        self.KA = ann_text(k)
        self.VA = None if v is None else ann_text(v)
        gen.hash_leaf(k, 'x') if deep(k) != INT else None   # refuses an unhashable key early
        dv = deep(v)
        self.rows = isinstance(dv, tuple) and dv[0] == 'list'
        if isinstance(dv, tuple) and (dv[0] in ('set', 'dict') or (
                dv[0] == 'list' and isinstance(deep(dv[1]), tuple) and deep(dv[1])[0] in ('list', 'set', 'dict'))):
            raise Refused((1, 'a dict with tuples whose values are sets, dicts or lists of containers is not '
                           'built; keep a dict key -> index into a list of lists'))
        if is_tuple(k):
            gen.tcls(k)
        if v is not None and is_tuple(v):
            gen.tcls(v)
        self.made = set()
        self.make_class()

    def make_class(self):
        g = self.g
        if self.cls in g.out:
            return
        if self.is_set:
            g.out[self.cls] = ('class %s:\n    def __init__(self, ks: list[%s], live: list[int], hs: list[int], '
                               'idx: list[int], n: int):\n        self.ks = ks\n        self.live = live\n'
                               '        self.hs = hs\n        self.idx = idx\n        self.n = n\n'
                               % (self.cls, self.KA))
        else:
            g.out[self.cls] = ('class %s:\n    def __init__(self, ks: list[%s], vs: list[%s], live: list[int], '
                               'hs: list[int], idx: list[int], n: int):\n        self.ks = ks\n        self.vs = vs\n'
                               '        self.live = live\n        self.hs = hs\n        self.idx = idx\n'
                               '        self.n = n\n' % (self.cls, self.KA, self.VA))

    def fn(self, op):
        """The name of helper `op`, generating it (and what it needs) on first use."""
        name = self.p + op
        if name in self.g.out:
            return name
        self.g.out[name] = None
        for dep in DEPS[op]:
            self.fn(dep)
        self.g.out[name] = getattr(self, 'op_' + op)(name)
        return name

    def sub(self, text, **kw):
        return sub(text, T=self.cls, p=self.p, KA=self.KA, VA=self.VA or '', **kw)

    def keyrepr(self, x='k'):
        k = deep(self.k)
        if k == INT or k == BOOL:
            return 'str(%s)' % x
        return self.g.repr_expr(k, x)

    def hash_of(self, x='k'):
        return self.g.key_hash(self.k, x)

    def eq(self, a, b):
        return self.g.key_eq(self.k, a, b)

    # each op returns source text ------------------------------------------------------------------------
    def op_new(self, name):
        if self.is_set:
            return self.sub('def @p@new() -> @T@:\n    return @T@([], [], [], [-1] * 8, 0)\n')
        return self.sub('def @p@new() -> @T@:\n    return @T@([], [], [], [], [-1] * 8, 0)\n')

    def op_find(self, name):
        return self.sub('''def @p@find(d: @T@, k: @KA@, h: int) -> int:
    mask = len(d.idx) - 1
    i = h & mask
    while True:
        e = d.idx[i]
        if e == -1:
            return -1
        if e >= 0 and d.hs[e] == h and @EQ@:
            return e
        i = (i + 1) & mask
''', EQ=self.eq('d.ks[e]', 'k'))

    def op_rebuild(self, name):
        if self.rows:
            # rows are moved, never copied: references to a row stay valid across a rebuild
            return self.sub('''def @p@rebuild(d: @T@) -> None:
    cap = 8
    while cap < (d.n + 1) * 3:
        cap = cap * 2
    j = 0
    for e in range(len(d.ks)):
        if d.live[e] == 1:
            d.ks[j] = d.ks[e]
            d.vs[j] = d.vs[e]
            d.hs[j] = d.hs[e]
            j += 1
    while len(d.ks) > j:
        del d.ks[len(d.ks) - 1]
        del d.vs[len(d.vs) - 1]
        del d.hs[len(d.hs) - 1]
    d.live = [1] * j
    idx = [-1] * cap
    mask = cap - 1
    for e in range(j):
        i = d.hs[e] & mask
        while idx[i] != -1:
            i = (i + 1) & mask
        idx[i] = e
    d.idx = idx
''')
        vs_decl = '' if self.is_set else '    vs: list[@VA@] = []\n'
        vs_copy = '' if self.is_set else '            vs.append(d.vs[e])\n'
        vs_set = '' if self.is_set else '    d.vs = vs\n'
        return self.sub('''def @p@rebuild(d: @T@) -> None:
    cap = 8
    while cap < (d.n + 1) * 3:
        cap = cap * 2
    ks: list[@KA@] = []
''' + vs_decl + '''    hs: list[int] = []
    for e in range(len(d.ks)):
        if d.live[e] == 1:
            ks.append(d.ks[e])
''' + vs_copy + '''            hs.append(d.hs[e])
    d.ks = ks
''' + vs_set + '''    d.hs = hs
    d.live = [1] * len(ks)
    idx = [-1] * cap
    mask = cap - 1
    for e in range(len(ks)):
        i = hs[e] & mask
        while idx[i] != -1:
            i = (i + 1) & mask
        idx[i] = e
    d.idx = idx
''')

    def op_ins(self, name):
        sig = 'k: @KA@, h: int' if self.is_set else 'k: @KA@, v: @VA@, h: int'
        vs_app = '' if self.is_set else '    d.vs.append(v)\n'
        return self.sub('''def @p@ins(d: @T@, ''' + sig + ''') -> None:
    if (len(d.ks) + 1) * 3 > len(d.idx) * 2:
        @p@rebuild(d)
    mask = len(d.idx) - 1
    i = h & mask
    while d.idx[i] >= 0:
        i = (i + 1) & mask
    d.idx[i] = len(d.ks)
    d.ks.append(k)
''' + vs_app + '''    d.hs.append(h)
    d.live.append(1)
    d.n += 1
''')

    def op_set(self, name):
        return self.sub('''def @p@set(d: @T@, k: @KA@, v: @VA@) -> None:
    h = @H@
    e = @p@find(d, k, h)
    if e >= 0:
        d.vs[e] = v
        return
    @p@ins(d, k, v, h)
''', H=self.hash_of())

    def op_get(self, name):
        return self.sub('''def @p@get(d: @T@, k: @KA@) -> @VA@:
    e = @p@find(d, k, @H@)
    if e < 0:
        raise KeyError(@R@)
    return d.vs[e]
''', H=self.hash_of(), R=self.keyrepr())

    def op_ent(self, name):
        return self.sub('''def @p@ent(d: @T@, k: @KA@) -> int:
    e = @p@find(d, k, @H@)
    if e < 0:
        raise KeyError(@R@)
    return e
''', H=self.hash_of(), R=self.keyrepr())

    def op_sdent(self, name):
        return self.sub('''def @p@sdent(d: @T@, k: @KA@, default: @VA@) -> int:
    h = @H@
    e = @p@find(d, k, h)
    if e >= 0:
        return e
    @p@ins(d, k, default, h)
    return len(d.ks) - 1
''', H=self.hash_of())

    def op_get1(self, name):
        return self.sub('''def @p@get1(d: @T@, k: @KA@) -> Optional[@VA@]:
    e = @p@find(d, k, @H@)
    if e < 0:
        return None
    return d.vs[e]
''', H=self.hash_of())

    def op_getd(self, name):
        return self.sub('''def @p@getd(d: @T@, k: @KA@, default: @VA@) -> @VA@:
    e = @p@find(d, k, @H@)
    if e < 0:
        return default
    return d.vs[e]
''', H=self.hash_of())

    def op_has(self, name):
        return self.sub('''def @p@has(d: @T@, k: @KA@) -> bool:
    return @p@find(d, k, @H@) >= 0
''', H=self.hash_of())

    def op_del(self, name):
        return self.sub('''def @p@del(d: @T@, k: @KA@) -> None:
    h = @H@
    mask = len(d.idx) - 1
    i = h & mask
    while True:
        e = d.idx[i]
        if e == -1:
            raise KeyError(@R@)
        if e >= 0 and d.hs[e] == h and @EQ@:
            d.idx[i] = -2
            d.live[e] = 0
            d.n -= 1
            return
        i = (i + 1) & mask
''', H=self.hash_of(), R=self.keyrepr(), EQ=self.eq('d.ks[e]', 'k'))

    def op_pop(self, name):
        return self.sub('''def @p@pop(d: @T@, k: @KA@) -> @VA@:
    e = @p@find(d, k, @H@)
    if e < 0:
        raise KeyError(@R@)
    v = d.vs[e]
    @p@del(d, k)
    return v
''', H=self.hash_of(), R=self.keyrepr())

    def op_popd(self, name):
        return self.sub('''def @p@popd(d: @T@, k: @KA@, default: @VA@) -> @VA@:
    e = @p@find(d, k, @H@)
    if e < 0:
        return default
    v = d.vs[e]
    @p@del(d, k)
    return v
''', H=self.hash_of())

    def op_setdefault(self, name):
        return self.sub('''def @p@setdefault(d: @T@, k: @KA@, default: @VA@) -> @VA@:
    h = @H@
    e = @p@find(d, k, h)
    if e >= 0:
        return d.vs[e]
    @p@ins(d, k, default, h)
    return default
''', H=self.hash_of())

    def op_keys(self, name):
        return self.sub('''def @p@keys(d: @T@) -> list[@KA@]:
    out: list[@KA@] = []
    for e in range(len(d.ks)):
        if d.live[e] == 1:
            out.append(d.ks[e])
    return out
''')

    def op_vals(self, name):
        return self.sub('''def @p@vals(d: @T@) -> list[@VA@]:
    out: list[@VA@] = []
    for e in range(len(d.ks)):
        if d.live[e] == 1:
            out.append(d.vs[e])
    return out
''')

    def pair(self):
        return self.g.tcls(('tuple', (self.k, self.v)))

    def op_items(self, name):
        pair = self.pair()
        return self.sub('''def @p@items(d: @T@) -> list[@PAIR@]:
    out: list[@PAIR@] = []
    for e in range(len(d.ks)):
        if d.live[e] == 1:
            out.append(@PAIR@(d.ks[e], d.vs[e]))
    return out
''', PAIR=pair)

    def op_clear(self, name):
        return self.sub('''def @p@clear(d: @T@) -> None:
    fresh = @p@new()
    d.ks = fresh.ks
''' + ('' if self.is_set else '    d.vs = fresh.vs\n') + '''    d.live = fresh.live
    d.hs = fresh.hs
    d.idx = fresh.idx
    d.n = 0
''')

    def op_copy(self, name):
        vs = '' if self.is_set else 'list(d.vs), '
        return self.sub('''def @p@copy(d: @T@) -> @T@:
    return @T@(list(d.ks), ''' + vs + '''list(d.live), list(d.hs), list(d.idx), d.n)
''')

    def op_update(self, name):
        return self.sub('''def @p@update(d: @T@, o: @T@) -> None:
    for e in range(len(o.ks)):
        if o.live[e] == 1:
            @p@set(d, o.ks[e], o.vs[e])
''')

    def op_popitem(self, name):
        pair = self.pair()
        return self.sub('''def @p@popitem(d: @T@) -> @PAIR@:
    e = len(d.ks) - 1
    while e >= 0 and d.live[e] == 0:
        e -= 1
    if e < 0:
        raise KeyError("popitem(): dictionary is empty")
    r = @PAIR@(d.ks[e], d.vs[e])
    @p@del(d, d.ks[e])
    return r
''', PAIR=pair)

    def op_dfromlist(self, name):
        """dict from a list of (K, V) pairs (dict(pairs), dict(zip(...)))."""
        pair = self.pair()
        return self.sub('''def @p@dfromlist(xs: list[@PAIR@]) -> @T@:
    d = @p@new()
    for x in xs:
        @p@set(d, x.@F0@, x.@F1@)
    return d
''', PAIR=pair, F0=fld(self.k, 0), F1=fld(self.v, 1))

    # -- sets -------------------------------------------------------------------------------------------
    def op_add(self, name):
        return self.sub('''def @p@add(d: @T@, k: @KA@) -> None:
    h = @H@
    if @p@find(d, k, h) < 0:
        @p@ins(d, k, h)
''', H=self.hash_of())

    def op_discard(self, name):
        return self.sub('''def @p@discard(d: @T@, k: @KA@) -> None:
    if @p@find(d, k, @H@) >= 0:
        @p@del(d, k)
''', H=self.hash_of())

    def op_remove(self, name):
        return self.sub('''def @p@remove(d: @T@, k: @KA@) -> None:
    @p@del(d, k)
''')

    def op_spop(self, name):
        return self.sub('''def @p@spop(d: @T@) -> @KA@:
    e = len(d.ks) - 1
    while e >= 0 and d.live[e] == 0:
        e -= 1
    if e < 0:
        raise KeyError("pop from an empty set")
    k = d.ks[e]
    @p@del(d, k)
    return k
''')

    def op_fromlist(self, name):
        return self.sub('''def @p@fromlist(xs: list[@KA@]) -> @T@:
    d = @p@new()
    for x in xs:
        @p@add(d, x)
    return d
''')

    def op_addall(self, name):
        return self.sub('''def @p@addall(d: @T@, xs: list[@KA@]) -> None:
    for x in xs:
        @p@add(d, x)
''')

    def op_union(self, name):
        return self.sub('''def @p@union(a: @T@, b: @T@) -> @T@:
    r = @p@copy(a)
    for e in range(len(b.ks)):
        if b.live[e] == 1:
            @p@add(r, b.ks[e])
    return r
''')

    def op_inter(self, name):
        return self.sub('''def @p@inter(a: @T@, b: @T@) -> @T@:
    r = @p@new()
    for e in range(len(a.ks)):
        if a.live[e] == 1 and @p@has(b, a.ks[e]):
            @p@add(r, a.ks[e])
    return r
''')

    def op_diff(self, name):
        return self.sub('''def @p@diff(a: @T@, b: @T@) -> @T@:
    r = @p@new()
    for e in range(len(a.ks)):
        if a.live[e] == 1 and not @p@has(b, a.ks[e]):
            @p@add(r, a.ks[e])
    return r
''')

    def op_symdiff(self, name):
        return self.sub('''def @p@symdiff(a: @T@, b: @T@) -> @T@:
    r = @p@new()
    for e in range(len(a.ks)):
        if a.live[e] == 1 and not @p@has(b, a.ks[e]):
            @p@add(r, a.ks[e])
    for e in range(len(b.ks)):
        if b.live[e] == 1 and not @p@has(a, b.ks[e]):
            @p@add(r, b.ks[e])
    return r
''')

    def op_subset(self, name):
        return self.sub('''def @p@subset(a: @T@, b: @T@) -> bool:
    for e in range(len(a.ks)):
        if a.live[e] == 1 and not @p@has(b, a.ks[e]):
            return False
    return True
''')

    def op_seq(self, name):
        return self.sub('''def @p@seq(a: @T@, b: @T@) -> bool:
    return a.n == b.n and @p@subset(a, b)
''')

    def op_disjoint(self, name):
        return self.sub('''def @p@disjoint(a: @T@, b: @T@) -> bool:
    for e in range(len(a.ks)):
        if a.live[e] == 1 and @p@has(b, a.ks[e]):
            return False
    return True
''')
