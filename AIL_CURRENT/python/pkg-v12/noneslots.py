"""`xs = [None] * n` rows with a present bit per row, lowered to a list of empty rows.

A Python list whose slots start as None and later hold lists (`st_lines[u] = [a]`,
`st_lines[u].append(a)`, `adj.append([])`) has no typed representation of its own.  This module
rewrites the list into the two typed lists the compiler already builds: `xs` holds one list per
slot (an empty list where Python has None) and `xs__p` holds the present bit.  `xs[i] is None`
reads the bit, `xs[i] = <list>` sets it, and `xs.append(<list>)` grows both lists together.

The rewrite only runs when every use of the name is one of those shapes; otherwise the source is
returned exactly as written, so a program this does not cover keeps its old route and refusal.
"""
import ast
import copy

_SIMPLE = (ast.Name, ast.Constant)


def _is_simple(e):
    """An index expression with no call or subscript, so evaluating it twice is indistinguishable."""
    if isinstance(e, _SIMPLE):
        return True
    if isinstance(e, (ast.BinOp, ast.UnaryOp, ast.Compare, ast.BoolOp, ast.IfExp, ast.Tuple)):
        return all(_is_simple(ch) for ch in ast.iter_child_nodes(e) if isinstance(ch, ast.expr))
    return False


def _is_none(e):
    return isinstance(e, ast.Constant) and e.value is None


def _list_value(e):
    return isinstance(e, (ast.List, ast.ListComp, ast.SetComp)) or (
        isinstance(e, ast.Call) and isinstance(e.func, ast.Name) and e.func.id in ('list', 'sorted'))


def _mult_list_none(e):
    """The `n` of `[None] * n` / `n * [None]`, else None."""
    if not (isinstance(e, ast.BinOp) and isinstance(e.op, ast.Mult)):
        return None
    for lst, other in ((e.left, e.right), (e.right, e.left)):
        if (isinstance(lst, ast.List) and len(lst.elts) == 1 and _is_none(lst.elts[0])
                and not isinstance(other, ast.Starred)):
            return other
    return None


def _own_walk(fn):
    """Nodes of `fn`'s body, not entering nested functions or classes."""
    out = []

    def walk(n):
        out.append(n)
        for c in ast.iter_child_nodes(n):
            if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                continue
            walk(c)
    for st in fn.body:
        walk(st)
    return out


def _guard_key(test, name):
    """For `xs[i] is None` / `xs[i] is not None` (a single comparison, `xs[i]` a subscript of the
    candidate), `(key, present_when_true, index_names)`; else None.  The key is the unparsed
    subscript, so the branch body can tell that same row is present."""
    if not (isinstance(test, ast.Compare) and len(test.ops) == 1
            and isinstance(test.ops[0], (ast.Is, ast.IsNot))):
        return None
    left, right = test.left, test.comparators[0]
    if _is_none(right):
        sub = left
    elif _is_none(left):
        sub = right
    else:
        return None
    if not (isinstance(sub, ast.Subscript) and isinstance(sub.value, ast.Name)
            and sub.value.id == name and _is_simple(sub.slice)):
        return None
    index_names = {n.id for n in ast.walk(sub.slice) if isinstance(n, ast.Name)}
    return ast.unparse(sub), isinstance(test.ops[0], ast.IsNot), index_names


def _stored_names(stmts):
    """Names assigned anywhere in `stmts` (nested functions included: conservative)."""
    out = set()
    for st in stmts:
        for n in ast.walk(st):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                out.add(n.id)
    return out


def _candidate_ok(fn, name, init_target, parents):
    """Every use of `name` is a shape the rewrite translates or a read guarded by a direct
    `is None` / `is not None` test on the same simple subscript.  A plain read, an alias, a `del`
    or an augmented target would silently differ from CPython, so it rejects the whole name."""
    ok = [True]

    def fail():
        ok[0] = False

    def key_of(sub):
        return ast.unparse(sub)

    def unpacked(sub):
        """The subscript is an element of an unpack target (`xs[i], x = ...`, `*xs[i], x = ...`),
        which the store rewrite never lowers."""
        node, parent = sub, parents.get(id(sub))
        while isinstance(parent, (ast.Tuple, ast.List, ast.Starred)):
            if isinstance(parent.ctx, ast.Store):
                return True
            node, parent = parent, parents.get(id(parent))
        return False

    def role(sub):
        parent = parents.get(id(sub))
        if unpacked(sub):
            return 'bad'          # a store inside an unpack target is never lowered
        if (isinstance(parent, ast.Compare) and len(parent.ops) == 1
                and isinstance(parent.ops[0], (ast.Is, ast.IsNot))):
            if parent.left is sub:
                other = parent.comparators[0]
            elif parent.comparators[0] is sub:
                other = parent.left
            else:
                other = None
            if other is not None and _is_none(other) and not isinstance(sub.slice, ast.Slice):
                return 'guard'
        if isinstance(parent, ast.Assign) and any(t is sub for t in parent.targets):
            return 'store'
        if isinstance(parent, (ast.For, ast.AsyncFor)) and parent.target is sub:
            return 'bad'
        if isinstance(parent, ast.AugAssign) and parent.target is sub:
            return 'bad'
        if isinstance(parent, ast.Delete) and any(t is sub for t in parent.targets):
            return 'bad'
        if isinstance(parent, ast.AnnAssign) and parent.target is sub:
            return 'bad'
        return 'read'

    def check_use(n, present):
        if not ok[0]:
            return
        if isinstance(n, ast.Name) and n.id == name:
            if n is init_target:
                return
            parent = parents.get(id(n))
            if isinstance(parent, ast.Subscript) and parent.value is n:
                return                              # the Subscript node is checked below
            if (isinstance(parent, ast.Attribute) and parent.value is n
                    and parent.attr == 'append'):
                call = parents.get(id(parent))
                stmt = parents.get(id(call)) if call is not None else None
                if not (isinstance(call, ast.Call) and call.func is parent
                        and isinstance(stmt, ast.Expr)):
                    fail()
                return
            if (isinstance(parent, ast.Call) and isinstance(parent.func, ast.Name)
                    and parent.func.id == 'len' and n in parent.args):
                return
            fail()
        elif (isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name)
              and n.value.id == name):
            r = role(n)
            if r in ('guard', 'store'):
                return
            if r == 'read':
                if key_of(n) not in present:
                    fail()
                return
            fail()

    def walk_node(n, present):
        if not ok[0] or isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef,
                                       ast.Lambda, ast.ClassDef)):
            return
        if isinstance(n, ast.If):
            walk_node(n.test, present)
            guard = _guard_key(n.test, name)
            if guard is not None:
                key, when_true, index_names = guard

                def branch(stmts):
                    if (index_names | {name}) & _stored_names(stmts):
                        return present
                    return present | {key}
                body = branch(n.body) if when_true else present
                orelse = present if when_true else branch(n.orelse)
            else:
                body = orelse = present
            for s in n.body:
                walk_node(s, body)
            for s in n.orelse:
                walk_node(s, orelse)
            return
        check_use(n, present)
        for c in ast.iter_child_nodes(n):
            walk_node(c, present)

    for st in fn.body:
        walk_node(st, frozenset())
    return ok[0]


def _candidates(fn, taken):
    """Names of `fn` initialized as `[None] * n` and used only in the shapes this rewrite knows."""
    own = _own_walk(fn)
    declared = set()
    for n in own:
        if isinstance(n, (ast.Global, ast.Nonlocal)):
            declared.update(n.names)
    args = set()
    for a in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs:
        args.add(a.arg)
    if fn.args.vararg is not None:
        args.add(fn.args.vararg.arg)
    if fn.args.kwarg is not None:
        args.add(fn.args.kwarg.arg)
    init = {}
    for n in own:
        target = value = None
        if isinstance(n, ast.Assign) and len(n.targets) == 1:
            target, value = n.targets[0], n.value
        elif isinstance(n, ast.AnnAssign):
            target, value = n.target, n.value
        if isinstance(target, ast.Name) and value is not None and _mult_list_none(value) is not None:
            init.setdefault(target.id, []).append(n)
    out = []
    nodes = own
    parents = {id(child): parent for parent in nodes for child in ast.iter_child_nodes(parent)}
    for name, inits in init.items():
        if (len(inits) != 1 or name + '__p' in taken or name in declared
                or name in args):
            continue
        init_target = inits[0].targets[0] if isinstance(inits[0], ast.Assign) else inits[0].target
        if not _candidate_ok(fn, name, init_target, parents):
            continue
        ok = True
        for n in nodes:
            if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and isinstance(n.func.value, ast.Name) and n.func.value.id == name):
                continue
            if n.func.attr != 'append' or len(n.args) != 1 or n.keywords:
                ok = False
            elif not (_is_none(n.args[0]) or _list_value(n.args[0])):
                ok = False
        for n in nodes:
            if isinstance(n, ast.Assign):
                targets, value = n.targets, n.value
            elif isinstance(n, ast.AnnAssign):
                targets, value = [n.target], n.value
            else:
                continue
            for target in targets:
                if not (isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name)
                        and target.value.id == name):
                    continue
                if isinstance(target.slice, ast.Slice):
                    ok = False
                elif len(targets) != 1:
                    ok = False        # the store rewrite emits one target; a chained store is unhandled
                elif not _is_simple(target.slice):
                    ok = False        # the store rewrite would evaluate the index twice
                elif not (_is_none(value) or _list_value(value)):
                    ok = False
        if ok:
            out.append(name)
    return out


class _Rewrite(ast.NodeTransformer):
    def __init__(self, name, init):
        self.name = name
        self.init = init
        self.pname = name + '__p'

    def _init(self, node):
        value = node.value
        n = _mult_list_none(value)
        rows = ast.ListComp(
            elt=ast.List(elts=[], ctx=ast.Load()),
            generators=[ast.comprehension(
                target=ast.Name(id='_slot_i', ctx=ast.Store()),
                iter=ast.Call(func=ast.Name(id='range', ctx=ast.Load()), args=[copy.deepcopy(n)], keywords=[]),
                ifs=[], is_async=0)])
        ast.copy_location(rows, value)
        node.value = rows
        flags = ast.BinOp(
            left=ast.List(elts=[ast.Constant(value=False)], ctx=ast.Load()),
            op=ast.Mult(),
            right=ast.Call(func=ast.Name(id='len', ctx=ast.Load()), args=[ast.Name(id=self.name, ctx=ast.Load())], keywords=[]))
        ast.copy_location(flags, value)
        if isinstance(node, ast.AnnAssign):
            comp = ast.Assign(targets=[ast.Name(id=self.pname, ctx=ast.Store())], value=flags)
        else:
            comp = ast.Assign(targets=[ast.Name(id=self.pname, ctx=ast.Store())], value=flags)
        ast.copy_location(comp, node)
        return [node, comp]

    def _index(self, sub):
        return ast.Name(id=self.pname, ctx=ast.Load()), copy.deepcopy(sub.slice)

    def visit_Assign(self, node):
        if (len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == self.name and _mult_list_none(node.value) is not None):
            return self._init(node)
        if (len(node.targets) == 1 and isinstance(node.targets[0], ast.Subscript)
                and isinstance(node.targets[0].value, ast.Name)
                and node.targets[0].value.id == self.name):
            node = self.generic_visit(node)
            sub = node.targets[0]
            if _is_none(node.value):
                node.value = ast.List(elts=[], ctx=ast.Load())
                flag = ast.Constant(value=False)
            else:
                flag = ast.Constant(value=True)
            ast.copy_location(node.value, sub)
            setp = ast.Assign(targets=[ast.Subscript(value=ast.Name(id=self.pname, ctx=ast.Load()),
                                                     slice=copy.deepcopy(sub.slice), ctx=ast.Store())],
                              value=flag)
            ast.copy_location(setp, node)
            return [node, setp]
        return self.generic_visit(node)

    def visit_AnnAssign(self, node):
        if (isinstance(node.target, ast.Name) and node.target.id == self.name
                and node.value is not None and _mult_list_none(node.value) is not None):
            return self._init(node)
        return self.generic_visit(node)

    def visit_Expr(self, node):
        node = self.generic_visit(node)
        call = node.value
        if (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name) and call.func.value.id == self.name
                and call.func.attr == 'append'):
            value = call.args[0]
            if _is_none(value):
                call.args[0] = ast.List(elts=[], ctx=ast.Load())
                ast.copy_location(call.args[0], value)
                flag = ast.Constant(value=False)
            else:
                flag = ast.Constant(value=True)
            grow = ast.Expr(value=ast.Call(
                func=ast.Attribute(value=ast.Name(id=self.pname, ctx=ast.Load()), attr='append', ctx=ast.Load()),
                args=[flag], keywords=[]))
            ast.copy_location(grow, node)
            return [node, grow]
        return node

    def visit_Compare(self, node):
        if len(node.ops) == 1 and isinstance(node.ops[0], (ast.Is, ast.IsNot)):
            left, right = node.left, node.comparators[0]
            sub = None
            target_sub = None
            if _is_none(right) and isinstance(left, ast.Subscript) \
                    and isinstance(left.value, ast.Name) and left.value.id == self.name:
                sub, target_sub = left, left
            elif _is_none(left) and isinstance(right, ast.Subscript) \
                    and isinstance(right.value, ast.Name) and right.value.id == self.name:
                sub, target_sub = right, right
            if sub is not None and not isinstance(sub.slice, ast.Slice):
                bit = ast.Subscript(value=ast.Name(id=self.pname, ctx=ast.Load()),
                                    slice=copy.deepcopy(sub.slice), ctx=ast.Load())
                ast.copy_location(bit, node)
                if isinstance(node.ops[0], ast.Is):
                    result = ast.UnaryOp(op=ast.Not(), operand=bit)
                else:
                    result = bit
                ast.copy_location(result, node)
                return result
        return self.generic_visit(node)


def rewrite(source):
    """The source with every recognized `[None] * n` row list lowered; the source as written when
    no candidate has only the shapes this rewrite covers."""
    if '[None]' not in source and 'None]' not in source:
        return source
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    taken = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
        n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    changed = False
    fns = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    fns += [m for c in tree.body if isinstance(c, ast.ClassDef) for m in c.body if isinstance(m, ast.FunctionDef)]
    for fn in fns:
        if any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef))
               for st in fn.body for n in ast.walk(st)):
            continue
        names = _candidates(fn, taken)
        if not names:
            continue
        new_body = fn.body
        for name in names:
            init = next(n for n in _own_walk(fn) if (
                isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)
                and n.targets[0].id == name and _mult_list_none(n.value) is not None)
                or (isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)
                    and n.target.id == name and n.value is not None and _mult_list_none(n.value) is not None))
            box = _Rewrite(name, init)
            flat = []
            for s in new_body:
                visited = box.visit(s)
                if isinstance(visited, list):
                    flat.extend(visited)
                elif visited is not None:
                    flat.append(visited)
            new_body = flat
            changed = True
        fn.body = new_body
    if not changed:
        return source
    ast.fix_missing_locations(tree)
    return ast.unparse(tree) + '\n'
