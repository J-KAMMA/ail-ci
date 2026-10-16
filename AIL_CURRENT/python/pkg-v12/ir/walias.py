"""W-ALIAS for functions the IR does not take (design section 13).

Under the decided sharing semantics `ys = xs` makes one list with two names; the legacy emitter, whose
value semantics this program may have been written for, copies. The ownership analysis (ownership.py)
reports the sites it resolves. This module covers the rest -- functions that stay on the legacy
emitter for any reason (a `main` that prints, a Rule X site) -- with a syntactic, deliberately
approximate scan: an assignment of one numeric-list name to another name, or to a struct field, after
which either name is written (`xs[i] = v`, `xs[i] += v`, `xs.append(v)`, `del`) while the other is mentioned
again, in the statements that follow or anywhere in an enclosing loop. It reports where the two meanings
may differ; it never changes what is compiled.
"""
import ast

_MUTATORS = ('append', 'pop', 'clear', 'extend', 'insert', 'remove', 'sort', 'reverse')


def _name(node):
    return node.id if isinstance(node, ast.Name) else None


def _written(nodes, name):
    """Whether any of `nodes` writes the list called `name` (element store, mutating method, del)."""
    for st in nodes:
        for n in ast.walk(st):
            targets = ()
            if isinstance(n, ast.Assign):
                targets = n.targets
            elif isinstance(n, (ast.AugAssign, ast.AnnAssign)):
                targets = (n.target,)
            elif isinstance(n, ast.Delete):
                targets = n.targets
            for t in targets:
                while isinstance(t, ast.Subscript):
                    if _name(t.value) == name:
                        return True
                    t = t.value
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in _MUTATORS \
                    and _name(n.func.value) == name:
                return True
    return False


def _mentioned(nodes, name):
    return any(isinstance(n, ast.Name) and n.id == name for st in nodes for n in ast.walk(st))


def scan(P, fn, ctx):
    """[{'line', 'dst', 'src', 'rule': 'ast', 'differs': True}] for the sites of `fn` that may differ."""
    kinds = getattr(ctx, 'types', {}) or {}
    lists = (P.LIST, P.FLIST)
    found = []

    def is_list(name):
        return kinds.get(name) in lists

    def visit(stmts, after, loops):
        for i, st in enumerate(stmts):
            rest = list(stmts[i + 1:]) + after
            region = rest + [s for loop in loops for s in loop]
            if isinstance(st, ast.Assign) and len(st.targets) == 1:
                tgt, val = st.targets[0], st.value
                src = _name(val)
                dst = _name(tgt)
                label = None
                if src and is_list(src):
                    if dst and dst != src and is_list(dst):
                        label = dst
                    elif isinstance(tgt, ast.Attribute) and _name(tgt.value):
                        label = '%s.%s' % (_name(tgt.value), tgt.attr)
                if label is not None:
                    other_written = _written(region, src) or (dst is not None and _written(region, dst))
                    # a field is read through its object; any later mention of the object counts
                    other_read = _mentioned(region, src) or (dst is not None and _mentioned(region, dst)) \
                        or (dst is None and _mentioned(region, _name(tgt.value)))
                    if other_written and other_read:
                        found.append({'line': getattr(st, 'lineno', 0), 'dst': label, 'src': src,
                                      'rule': 'ast', 'differs': True})
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
