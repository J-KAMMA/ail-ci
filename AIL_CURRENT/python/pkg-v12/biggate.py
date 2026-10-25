# -*- coding: utf-8 -*-
"""biggate.py -- the size gate of the big ints (docs/design/BIGINT.md section 9).

The general runtime carries the big int support (bigint_core / bigint_obj and the AIL_T_BIG arms spread through cruntime.OBJ2).
A program that cannot create a big int must not pay for it: its C has to be what it was before the big ints existed, byte for byte.
So every text that differs between the two worlds is written once, as a conditional block

    /*B<*/ ...text with big ints... /*B|*/ ...text without... /*B>*/

(a whole-line form in cruntime.py, an inline form in the emitters: `cond(new, old)`), and `finalize(text)` picks a side for the
whole program: the first side when a function that can create a big int is reachable from the program's own code, the second side
when none is. Reachability is a token graph over the top-level definitions of the finished text (a conservative over-estimate:
a name that appears in a body counts as a call), and the creators are the functions that make a big int out of something that is
not one (`CREATORS`). The unboxed arms of unified.py mark their calls with `/*U*/`: they stop on a big result, they never keep one,
so they do not make their callee reachable by themselves.
"""
import os
import re

OPEN, MID, CLOSE = '/*B<*/', '/*B|*/', '/*B>*/'
_BLOCK = re.compile(r'/\*B<\*/(.*?)/\*B\|\*/(.*?)/\*B>\*/', re.S)
_LINEBLOCK = re.compile(r'/\*B<\*/\n(.*?)/\*B\|\*/\n(.*?)/\*B>\*/\n', re.S)
POPEN, PMID, PCLOSE = '/*P:', '<*/', '/*P|*/'
_PBLOCK = re.compile(r'/\*P:([a-z]+)<\*/(.*?)/\*P\|\*/(.*?)/\*P>\*/', re.S)
UMARK = '/*U*/'
IMARK = '/*I*/'                  # a source-level int arithmetic operator on the general path
USER_MARK = '/*@USER@*/\n'     # between the shared runtime and the program's own text

# Runtime pieces emitted only when the program's own text can reach the operation (B3). Each name is a
# marker `/*P:name<*/ new /*P|*/ old /*P>*/` around a group of definitions, and the trigger names are
# the C entry points the emitters use for that operation. The scan is over the text after USER_MARK,
# so the runtime's own references never enable a piece by themselves.
PIECES = {
    # floor division / modulo / true division of ints, divmod() and the range arithmetic that divides
    'div': ('ail_op_floordiv', 'ail_op_mod', 'ail_op_ifloordiv', 'ail_op_imod',
            'ail_op_idiv', 'ail_op_truediv', 'ail_int_divmod', 'ail_big_divmod',
            'ail_bi_divmod', 'ail__big_floordiv', 'ail__big_mod', 'ail__big_truediv',
            'ail__int_truediv', 'ail__ov_floordiv', 'ail__ov_truediv', 'ail__floordiv_slow',
            'ail__mod_slow', 'ail__truediv_slow', 'ail_tint_floordiv', 'ail_tint_mod',
            'ail_tint__slow_divmod', 'ail_tint__divmod', 'ail_range_make',
            'pf__ail_b_divmod', 'pf__ail_b_floordiv', 'pf__ail_b_mod'),
    'pow': ('ail_op_pow', 'ail_op_ipow', 'ail__int_pow', 'ail__ov_pow', 'ail__big_pow',
            'ail_bi_pow', 'ail__pow3_big', 'pf__ail_b_pow'),
    'shift': ('ail_op_lshift', 'ail_op_rshift', 'ail_op_ilshift', 'ail_op_irshift',
              'ail_big_shl', 'ail_big_shr', 'ail__big_shift', 'ail__ov_shl',
              'ail_tint_lshift', 'ail_tint_rshift', 'ail_tint__slow_shift', 'ail_tint__shift'),
    'bits': ('ail_op_bitand', 'ail_op_bitor', 'ail_op_bitxor', 'ail_op_invert',
             'ail_op_ibitand', 'ail_op_ibitor', 'ail_op_ibitxor', 'ail__bit_logic',
             'ail_big_bitop'),
    'text': ('ail2_do_print', 'ail_obj_write_str', 'ail_obj_write_repr', 'ail_obj_str',
             'ail_obj_repr', 'ail_int_to_str', 'ail_tint_str', 'ail_tint_repr',
             'ail_str_of_int', 'ail_str_from_int', 'ail_big_dec', 'ail_big_radix',
             'ail_big_from_digits', 'pf__ail_b_str', 'pf__ail_b_repr', 'pf__ail_b_int',
             'pf__ail_b_format', 'ail_bi_str', 'ail_bi_repr', 'ail_bi_int',
             'ail_bi_format'),
}


def pieces_for(text):
    """The runtime pieces the program's own text needs (after USER_MARK).

    A name in the program text is only the start: the runtime functions the program reaches call
    more runtime functions, and a piece whose entry point is named *there* is needed too.  The
    round() path is the example that exposed this: the program names round(), and the runtime's
    ail__round_int_big calls ail__int_pow and ail_int_divmod.  Walk the same token graph the big
    gate uses from the program's own identifiers, and collect every trigger named by a reachable
    definition; a piece reached that way adds its own references on the next walk step.
    """
    if USER_MARK not in text:
        return set(PIECES)
    pre, user = text.split(USER_MARK, 1)
    key = hash(pre)
    gp = _RT_CACHE.get(key)
    if gp is None:
        if len(_RT_CACHE) > 4:
            _RT_CACHE.clear()
        gp = _RT_CACHE[key] = _graph(pre)
    gu = _graph(user)
    roots = set()
    for _names, ids in chunks(user):
        roots |= ids
    seen, stack = set(), list(roots)
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        stack.extend(v for v in gp.get(n, ()) if v not in seen)
        stack.extend(v for v in gu.get(n, ()) if v not in seen)
    found = set()
    for name in seen:
        ids = gp.get(name) or gu.get(name) or ()
        for piece, triggers in PIECES.items():
            if piece not in found and (name in triggers or any(t in ids for t in triggers)):
                found.add(piece)
    # 3-argument pow() reduces modulo at every step, so it also reaches the division piece
    if 'pow' in found and any(t in user for t in ('ail_bi_pow', 'pf__ail_b_pow')):
        found.add('div')
    return found


def cond(new, old=''):
    """An inline conditional: `new` in a program with big ints, `old` in one without."""
    assert OPEN not in new + old and CLOSE not in new + old
    return OPEN + new + MID + old + CLOSE


def resolve(text, big, keep=False, pieces=None):
    """Pick one side of every block (and drop the /*U*/ marks unless `keep`). `pieces` limits the
    /*P:name<*/ blocks: a named piece keeps its first side only when the program names it."""
    k = 1 if big else 2
    text = _LINEBLOCK.sub(lambda m: m.group(k), text)
    text = _BLOCK.sub(lambda m: m.group(k), text)
    if pieces is False:
        pass
    elif pieces is not None:
        text = _PBLOCK.sub(lambda m: m.group(2) if (big and m.group(1) in pieces) else m.group(3), text)
    else:
        text = _PBLOCK.sub(lambda m: m.group(2) if big else m.group(3), text)
    return text if keep else text.replace(UMARK, '')


# ---------------------------------------------------------------------------------------------------------------------------
# reachability
_IDENT = re.compile(r'[A-Za-z_]\w*')
_STR = re.compile(r'"(?:\\.|[^"\\\n])*"')
_CHR = re.compile(r"'(?:\\.|[^'\\\n])'")
_ATTR = re.compile(r'__attribute__\s*\(\(.*?\)\)')
_UCALL = re.compile(r'/\*U\*/\s*[A-Za-z_]\w*')

# the allocators of a big int: a function that mentions one of them can make a big int out of its operands
ALLOC = frozenset(('ail_big_alloc', 'ail_big_from_limbs', 'ail_big_from_digits', 'ail_big_addsub', 'ail_big_mul', 'ail_big_neg',
                   'ail_big_shl', 'ail_big_shr', 'ail_big_bitop', 'ail_big_divmod', 'ail_big_abs'))

# The generic operators are not a way for the program's text to ask for big ints: their int arms are there for every program
# that can call them, including a float `*` or a str `+`. The emitters mark the source operators that really are int arithmetic
# with IMARK; reachability is only for the constructs that make a big int without an int64 overflow (a literal, int(str),
# factorial, ...). Stop the walk at the generic operator entry points so a float/str call cannot pull the whole core in.
GENERIC = frozenset(('ail_op_add', 'ail_op_sub', 'ail_op_mul', 'ail_op_truediv', 'ail_op_floordiv', 'ail_op_mod', 'ail_op_pow',
                     'ail_op_bitand', 'ail_op_bitor', 'ail_op_bitxor', 'ail_op_lshift', 'ail_op_rshift', 'ail_op_iadd',
                     'ail_op_isub', 'ail_op_imul', 'ail_op_idiv', 'ail_op_ifloordiv', 'ail_op_imod', 'ail_op_ipow',
                     'ail_op_ibitand', 'ail_op_ibitor', 'ail_op_ibitxor', 'ail_op_ilshift', 'ail_op_irshift',
                     'ail_op_neg', 'ail_op_pos', 'ail_op_invert', 'ail__bit_logic'))


_NONINT = frozenset(('float', 'str', 'list', 'tuple', 'dict', 'set', 'frozenset', 'bytes', 'bytearray', 'range', 'none'))


def int_arith(opname, lk, rk):
    """Is a source `opname` an int arithmetic operator, given the known kinds of its operands? Only the emitters' proven
    kinds are used: a float or str operand is not int arithmetic, while a proven int/bool (or an unknown operand next to
    one) is. Two unknown operands count as int arithmetic too: a list item, an attribute, a dict value and a function
    parameter have no proven kind, yet `d[k] + d[k]` can be an int addition that overflows (the gate must keep the big
    runtime). Only the emitters' own local evidence is used: there is no call-site, field or container scan (BIGINT.md
    rules 2-4). `**` and the shifts can only be int or a float power (`<<` / `>>` are int-only)."""
    if opname in ('LShift', 'RShift'):
        return lk not in _NONINT and rk not in _NONINT
    if opname == 'Pow':
        return lk not in _NONINT and rk not in _NONINT
    if lk is None and rk is None:
        return True
    if lk in ('int', 'bool'):
        return rk in (None, 'int', 'bool')
    if rk in ('int', 'bool'):
        return lk in (None, 'int', 'bool')
    return False


def unary_arith(lk):
    return lk in (None, 'int', 'bool')


def _consumer(name):
    """A function that has a big operand already (a big int cannot be there unless a creator ran): never a creator by itself."""
    return name.startswith(('ail_big_', 'ail__big_', 'ail__bigrange_', 'ail_bn_')) or name in ('ail__bit_logic', 'ail_op_invert')


def chunks(text):
    """Top-level definitions of C text: [(defined names, set of identifiers mentioned)]."""
    out = []
    cur, depth, in_c = [], 0, False
    for line in text.split('\n'):
        s = _STR.sub('""', line)
        s = _CHR.sub("''", s)
        if in_c:
            if '*/' in s:
                s = s.split('*/', 1)[1]
                in_c = False
            else:
                s = ''
        while '/*' in s:
            a, b = s.split('/*', 1)
            if '*/' in b:
                s = a + b.split('*/', 1)[1]
            else:
                s = a
                in_c = True
        i = s.find('//')
        if i >= 0:
            s = s[:i]
        cur.append(s)
        depth += s.count('{') - s.count('}')
        st = s.strip()
        if depth <= 0 and not st.endswith('\\') and (st.endswith(('}', ';')) or st.startswith('#') or st == ''):
            if any(c.strip() for c in cur):
                out.append(_defined(cur))
            cur, depth = [], 0
    if cur and any(c.strip() for c in cur):
        out.append(_defined(cur))
    return out


def _defined(lines):
    body = '\n'.join(lines)
    ids = set(_IDENT.findall(body))
    m = re.match(r'\s*#\s*define\s+(\w+)', body)
    if m:
        return [m.group(1)], ids
    flat = _ATTR.sub(' ', body)
    head = flat.split('{', 1)[0] if '{' in flat else flat
    names = []
    for m in re.finditer(r'\b([A-Za-z_]\w*)\s*\(', head):
        if m.group(1) not in ('sizeof', 'defined', 'void', 'if', 'while', 'for', 'switch', 'return'):
            names.append(m.group(1))
            break
    if not names:
        m = re.search(r'([A-Za-z_]\w*)\s*(?:\[[^\]]*\]\s*)*(?:=|;|\{)', head.strip())
        if m:
            names.append(m.group(1))
    m = re.search(r'\}\s*([A-Za-z_]\w*)\s*;\s*$', flat)
    if m:
        names.append(m.group(1))
    return names, ids


_RT_CACHE = {}


def _graph(text):
    g = {}
    for names, ids in chunks(text):
        for n in names:
            g.setdefault(n, set()).update(ids - {n})
    return g


def reachable_creator(text):
    """The name of a creator of big ints that the program's own text can reach (see the module docstring), or None. `text` is the
    big-side program with its USER_MARK; a `/*U*/name` call does not count."""
    pre, user = text.split(USER_MARK, 1)
    key = hash(pre)
    gp = _RT_CACHE.get(key)
    if gp is None:
        if len(_RT_CACHE) > 4:
            _RT_CACHE.clear()
        gp = _RT_CACHE[key] = _graph(pre.replace(UMARK, ''))
    u = _UCALL.sub(' ', user)
    gu = _graph(u)
    roots = set()
    for _names, ids in chunks(u):
        roots |= ids
    seen, stack = {}, [(r, None) for r in roots]
    while stack:
        n, parent = stack.pop()
        if n in seen:
            continue
        seen[n] = parent
        if _consumer(n) or n in GENERIC:
            continue            # runs only on a big int, or is a generic operator whose int arm is not the program's own request
        stack.extend((v, n) for v in gp.get(n, ()) if v not in seen)
        stack.extend((v, n) for v in gu.get(n, ()) if v not in seen)
    for n in sorted(seen):
        if not _consumer(n) and n not in GENERIC and ((set(gp.get(n, ())) | gu.get(n, set())) & ALLOC):
            if os.environ.get('AIL_BIGINT_WHY'):
                chain, q = [], n
                while q is not None:
                    chain.append(q)
                    q = seen[q]
                import sys
                sys.stderr.write('biggate: ' + ' <- '.join(chain) + '\n')
            return n
    return None


def wants_big(text):
    """Does the program need the big int runtime? Yes for a source-level int arithmetic operator on the general path (IMARK)
    or for a reachable construct that makes a big int without an int64 overflow (see reachable_creator)."""
    _pre, user = text.split(USER_MARK, 1)
    return IMARK in user or reachable_creator(text) is not None


def strip(text):
    """The finished program: no USER_MARK, no /*U*/ or /*I*/ mark."""
    return text.replace(USER_MARK, '').replace(UMARK, '').replace(IMARK, '')


ON = True        # the pass in progress emits the program with big ints (True) or as before them (False)
