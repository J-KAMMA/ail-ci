"""A named refusal for list/dict/set/bytearray aliasing in Python-syntax (def) files.

CPython binds `ys = xs` to the SAME object: a write through one name shows through the other. The
legacy emitter gives every name its own value (copies on assignment), so a program that writes
through one name and reads the other afterwards would print something else, silently. Until the
IR's sharing semantics (ir/ownership.py, design section 13) covers every function, a def-syntax
function that stays on the legacy emitter and has such a site is refused here instead, naming the
line and the copy spellings. Block-syntax files keep their value semantics (the W-ALIAS note).

A syntactic, deliberately approximate scan (same shape as ir/walias.py, which reports the same
sites as a warning): `dst = src` (or `obj.field = src`) between two container names, after which
one name is written (element store, `del`, `+=`, a mutating method) and the other is mentioned again,
in the statements that follow or anywhere in an enclosing loop.
"""
import ast
import os

_LIST = ('append', 'pop', 'clear', 'extend', 'insert', 'remove', 'sort', 'reverse')
_SET = ('add', 'discard', 'remove', 'pop', 'clear', 'update', 'difference_update',
        'intersection_update', 'symmetric_difference_update')
_DICT = ('pop', 'popitem', 'clear', 'update', 'setdefault')
_MUTATORS = frozenset(_LIST + _SET + _DICT)


def _name(node):
    return node.id if isinstance(node, ast.Name) else None


def _is(node, ref):
    """`node` is the container called `ref`: a name, or a (holder, field) pair for `holder.field`."""
    if isinstance(ref, tuple):
        return (isinstance(node, ast.Attribute) and node.attr == ref[1] and _name(node.value) == ref[0])
    return _name(node) == ref


def _written(nodes, name):
    for st in nodes:
        for n in ast.walk(st):
            targets = ()
            if isinstance(n, ast.Assign):
                targets = n.targets
            elif isinstance(n, (ast.AugAssign, ast.AnnAssign)):
                targets = (n.target,)
                if isinstance(n, ast.AugAssign) and _is(n.target, name):
                    return True            # `xs += [..]`, `s |= t` mutate in place
            elif isinstance(n, ast.Delete):
                targets = n.targets
            for t in targets:
                while isinstance(t, ast.Subscript):
                    if _is(t.value, name):
                        return True
                    t = t.value
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr in _MUTATORS and _is(n.func.value, name)):
                return True
    return False


def _mentioned(nodes, name):
    return any(_is(n, name) for st in nodes for n in ast.walk(st))


def sites(P, fn, ctx):
    """[(line, dst, src)] of the sites where Python would share and this compiler would copy."""
    kinds = getattr(ctx, 'types', {}) or {}
    containers = {P.LIST, P.FLIST, P.SLIST, P.BLIST, P.OLIST, P.HLIST, P.SET, P.DICT,
                  P.BYTEARRAY, *P.MAPS}
    found = []

    def is_cont(name):
        return kinds.get(name) in containers

    def visit(stmts, after, loops):
        for i, st in enumerate(stmts):
            rest = list(stmts[i + 1:]) + after
            region = rest + [s for loop in loops for s in loop]
            if (isinstance(st, (ast.Assign, ast.AnnAssign)) and getattr(st, 'value', None) is not None):
                tgt = st.targets[0] if isinstance(st, ast.Assign) and len(st.targets) == 1 else (
                    st.target if isinstance(st, ast.AnnAssign) else None)
                src, dst = _name(st.value), _name(tgt)
                label = None
                if src and is_cont(src):
                    if dst and dst != src and is_cont(dst):
                        label = dst
                    elif isinstance(tgt, ast.Attribute) and _name(tgt.value):
                        label = '%s.%s' % (_name(tgt.value), tgt.attr)
                if label is not None:
                    holder = None if dst else _name(tgt.value)
                    # a write through either name that the other name can observe afterwards
                    src_written, dst_written = _written(region, src), dst is not None and _written(region, dst)
                    obs_src = _mentioned(region, src)
                    obs_dst = _mentioned(region, dst) if dst else _mentioned(region, holder)
                    if (dst_written and obs_src) or (src_written and obs_dst) \
                            or (holder and _written(region, holder) and obs_src):
                        found.append((getattr(st, 'lineno', 0), label, src))
            if isinstance(st, (ast.For, ast.While, ast.AsyncFor)):
                visit(st.body, rest, loops + [list(st.body)])
                visit(st.orelse, rest, loops)
            elif isinstance(st, ast.If):
                visit(st.body, rest, loops)
                visit(st.orelse, rest, loops)
            elif isinstance(st, ast.Try):
                visit(st.body, rest, loops)
                for h in st.handlers:
                    visit(h.body, rest, loops)
                visit(st.orelse, rest, loops)
                visit(st.finalbody, rest, loops)
            elif isinstance(st, ast.With):
                visit(st.body, rest, loops)

    visit(list(fn.body), [], [])
    return found


def check(P, fn, ctx):
    """Raise P.Unsupported for the first aliasing site of a def-syntax function."""
    if os.environ.get('AIL_SURFACE') != 'python' or os.environ.get('AIL_ALIAS_REFUSE') == '0':
        return
    found = sites(P, fn, ctx)
    if found:
        line, dst, src = found[0]
        raise P.Unsupported(
            'line %d: `%s = %s` makes a second name for the same container, and one of the two is '
            'written while the other is read afterwards. CPython shares the object there (a write '
            'through one name shows in the other); this compiler would copy and print something '
            'else, so it refuses rather than differ. If a copy was meant, write `%s = %s.copy()` '
            '(or list(%s) / dict(%s) / set(%s) / bytearray(%s)); if sharing was meant, '
            'keep a single name or pass the container to a function'
            % (line, dst, src, dst, src, src, src, src, src))
