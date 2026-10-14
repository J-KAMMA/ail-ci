"""Keyed sorting, lowered to key columns and a permutation before code generation.

`sorted(xs, key=lambda w: (-counts[w], w))`, `xs.sort(key=..., reverse=...)` and
`for k, v in sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))` all mean the same thing: compute
each element's key ONCE, order the elements by the keys (stable, lexicographic over the tuple
components), move the elements. This module rewrites such a site, in the AST, into

    _ail_sk1_c0 = [-counts[e] for e in xs]    one column per key component, evaluated once per
    _ail_sk1_p: list[int] = []                element by the ordinary comprehension machinery, so
    _ail_sort_perm(_ail_sk1_p, False, c0, c1) any expression the compiler can already compute as
    ys = xs.copy()                            int, float or str works as a key, with its ordinary
    _ail_sort_apply(ys, _ail_sk1_p)           ownership rules

and pyfunc.py compiles `_ail_sort_perm` / `_ail_sort_apply` to the KEYSORT runtime in cruntime.py.
A dict's `.items()` never becomes a tuple value: `for k, v in sorted(d.items(), ...)` walks the
permutation over the dict's `keys()` and `values()` snapshots, and `kv[0]` / `kv[1]` inside the key
read those two lists.

The rewrite runs only when the plain compile fails (see `to_c`), so every program that compiled
before compiles to the same C as before. Stage 1 rewrites the sites no existing path can take;
stage 2 also rewrites key shapes an existing path accepts for other element types (a dict-lookup
key over a list of str, say), after the existing path has refused the program as a whole.
"""
import ast
import copy

PERM = '_ail_sort_perm'
APPLY = '_ail_sort_apply'
MAX_COMPONENTS = 4
DONE = object()


def _is_dict_annotation(node):
    return (isinstance(node, ast.Name) and node.id == 'dict'
            or isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
            and node.value.id == 'dict')


def _dict_names(fn):
    names = set()
    for arg in fn.args.args:
        if arg.annotation is not None and _is_dict_annotation(arg.annotation):
            names.add(arg.arg)
    for node in ast.walk(fn):
        if (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                and _is_dict_annotation(node.annotation)):
            names.add(node.target.id)
        elif (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and (isinstance(node.value, ast.Dict)
                     or isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)
                     and node.value.func.id == 'dict')):
            names.add(node.targets[0].id)
    return names


def _struct_list_names(fn, classes):
    """Names in `fn` that visibly hold a list of structs: annotated `list[Class]`, built from a
    literal of constructor calls, or a copy / sorted() / list() of such a name."""
    def annotated(node):
        return (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
                and node.value.id == 'list' and isinstance(node.slice, ast.Name)
                and node.slice.id in classes)

    def constructed(node):
        return (isinstance(node, ast.List) and node.elts and isinstance(node.elts[0], ast.Call)
                and isinstance(node.elts[0].func, ast.Name) and node.elts[0].func.id in classes)

    names = {arg.arg for arg in fn.args.args if arg.annotation is not None and annotated(arg.annotation)}
    assigns = []
    for node in ast.walk(fn):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if annotated(node.annotation):
                names.add(node.target.id)
        elif (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)):
            if constructed(node.value):
                names.add(node.targets[0].id)
            else:
                assigns.append((node.targets[0].id, node.value))
    changed = True
    while changed:
        changed = False
        for target, value in assigns:
            if target in names:
                continue
            source = None
            if isinstance(value, ast.Call):
                if isinstance(value.func, ast.Name) and value.func.id in ('sorted', 'list') and value.args:
                    source = value.args[0]
                elif isinstance(value.func, ast.Attribute) and value.func.attr == 'copy':
                    source = value.func.value
            elif isinstance(value, ast.Name):
                source = value
            if isinstance(source, ast.Name) and source.id in names:
                names.add(target)
                changed = True
    return names


def stamp(node, lineno, column):
    for child in ast.walk(node):
        if 'lineno' in child._attributes:
            child.lineno = child.end_lineno = lineno
            child.col_offset = child.end_col_offset = column


def _name(identifier, store=False):
    return ast.Name(id=identifier, ctx=ast.Store() if store else ast.Load())


def _call(func, *args):
    return ast.Call(func=_name(func) if isinstance(func, str) else func, args=list(args), keywords=[])


def _method(receiver, attr):
    return ast.Call(func=ast.Attribute(value=_name(receiver), attr=attr, ctx=ast.Load()),
                    args=[], keywords=[])


def _is_sorted_call(node):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == 'sorted')


def _items_receiver(node):
    """`d` of `d.items()`, when `d` is a plain name; else None."""
    if (isinstance(node, ast.Call) and not node.args and not node.keywords
            and isinstance(node.func, ast.Attribute) and node.func.attr == 'items'
            and isinstance(node.func.value, ast.Name)):
        return node.func.value.id
    return None


def _field_style(body, param):
    """True when `body` reads a FIELD of `param` (`p.score`, `p.name.lower()`), which only a struct
    element has; a method call on it (`w.lower()`) does not count."""
    parents = {}
    for node in ast.walk(body):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    for node in ast.walk(body):
        if isinstance(node, ast.Name) and node.id == param:
            parent = parents.get(node)
            if isinstance(parent, ast.Attribute) and parent.value is node:
                grand = parents.get(parent)
                if not (isinstance(grand, ast.Call) and grand.func is parent):
                    return True
    return False


class _Substitute(ast.NodeTransformer):
    def __init__(self, param, replacement):
        self.param, self.replacement = param, replacement

    def visit_Name(self, node):
        if node.id == self.param and isinstance(node.ctx, ast.Load):
            return copy.deepcopy(self.replacement)
        return node


def _pair_reads(body, param):
    """The set of constant indexes (0 for the key, 1 for the value) `body` reads off `param`."""
    reads = set()
    for node in ast.walk(body):
        if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
                and node.value.id == param and isinstance(node.slice, ast.Constant)
                and type(node.slice.value) is int and node.slice.value in (0, 1)):
            reads.add(node.slice.value)
    return reads


class _SubstituteItem(ast.NodeTransformer):
    """`kv[0]` -> replacement[0], `kv[1]` -> replacement[1]; any other use of `kv` is refused."""
    def __init__(self, param, replacement, Unsupported):
        self.param, self.replacement, self.Unsupported = param, replacement, Unsupported

    def visit_Subscript(self, node):
        if isinstance(node.value, ast.Name) and node.value.id == self.param:
            if (isinstance(node.slice, ast.Constant) and type(node.slice.value) is int
                    and node.slice.value in (0, 1)):
                return copy.deepcopy(self.replacement[node.slice.value])
            raise self.Unsupported('a sort key over d.items() reads kv[0] (the key) and kv[1] '
                                   '(the value) only')
        return self.generic_visit(node)

    def visit_Name(self, node):
        if node.id == self.param:
            raise self.Unsupported('a sort key over d.items() reads kv[0] (the key) and kv[1] '
                                   '(the value) only; the pair itself is not a value here')
        return node


class _Rewriter:
    def __init__(self, stage, old_shape, Unsupported):
        self.stage, self.old_shape, self.Unsupported = stage, old_shape, Unsupported
        self.count = 0
        self.serial = 0
        self.structs = False
        self.struct_names = set()
        self.dicts = set()

    # -- site pieces ---------------------------------------------------------------------------
    def options(self, call, what):
        key, reverse = None, False
        seen = set()
        for kw in call.keywords:
            if kw.arg in seen:
                raise self.Unsupported('%s given the %r keyword twice' % (what, kw.arg))
            seen.add(kw.arg)
            if kw.arg == 'key':
                key = kw.value
            elif kw.arg == 'reverse':
                if not (isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, bool)):
                    raise self.Unsupported("%s: reverse= must be a literal True or False" % what)
                reverse = kw.value.value
            else:
                raise self.Unsupported('%s with a %r keyword; only key= and reverse= are accepted'
                                       % (what, kw.arg))
        return key, reverse

    def key_parts(self, key):
        """(parameter name, body expression) of a key= value."""
        if isinstance(key, ast.Lambda):
            a = key.args
            if (len(a.posonlyargs) + len(a.args) != 1 or a.vararg or a.kwarg or a.kwonlyargs
                    or a.defaults or a.kw_defaults):
                raise self.Unsupported('a sort key lambda takes exactly one argument')
            return (a.posonlyargs + a.args)[0].arg, key.body
        param = '_ail_key_arg'
        if isinstance(key, ast.Name):
            return param, ast.Call(func=_name(key.id), args=[_name(param)], keywords=[])
        if (isinstance(key, ast.Attribute) and isinstance(key.value, ast.Name)
                and key.value.id == 'str'):
            return param, ast.Call(func=ast.Attribute(value=_name(param), attr=key.attr,
                                                      ctx=ast.Load()), args=[], keywords=[])
        raise self.Unsupported('key= must be a lambda or a function name')

    def components(self, body):
        if isinstance(body, ast.Tuple):
            if not 1 <= len(body.elts) <= MAX_COMPONENTS:
                raise self.Unsupported('a sort key tuple has 1 to %d components' % MAX_COMPONENTS)
            return list(body.elts)
        return [body]

    def next_id(self):
        self.serial += 1
        return self.serial

    def perm_statements(self, n, reverse, columns):
        perm = '_ail_sk%d_p' % n
        annotation = ast.Subscript(value=_name('list'), slice=_name('int'), ctx=ast.Load())
        return perm, [
            ast.AnnAssign(target=_name(perm, True), annotation=annotation,
                          value=ast.List(elts=[], ctx=ast.Load()), simple=1),
            ast.Expr(value=_call(PERM, _name(perm), ast.Constant(value=reverse),
                                 *[_name(c) for c in columns]))]

    @staticmethod
    def mark_columns(n, pre):
        """Give every key column comprehension of site `n` all of the site's key expressions:
        when none of them runs user code, pyfunc.py may read list[str] field elements in a column
        as views (nothing can change the list before the permutation sort has read them)."""
        prefix = '_ail_sk%d_c' % n
        comps = [st.value for st in pre
                 if isinstance(st, ast.Assign) and isinstance(st.value, ast.ListComp)
                 and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name)
                 and st.targets[0].id.startswith(prefix)]
        elts = [c.elt for c in comps]
        for c in comps:
            c._ail_sort_columns = elts

    @staticmethod
    def element_column(name, element, expr, source):
        return ast.Assign(targets=[_name(name, True)], value=ast.ListComp(
            elt=expr, generators=[ast.comprehension(
                target=_name(element, True), iter=_name(source), ifs=[], is_async=0)]))

    @staticmethod
    def index_column(name, index, expr, source):
        return ast.Assign(targets=[_name(name, True)], value=ast.ListComp(
            elt=expr, generators=[ast.comprehension(
                target=_name(index, True),
                iter=_call('range', _call('len', _name(source))), ifs=[], is_async=0)]))

    # -- keyed list sorts ----------------------------------------------------------------------
    def keyed(self, source_expr, key, reverse, pre):
        """Statements computing the permutation for `source_expr`; returns (id, source, perm)."""
        n = self.next_id()
        if isinstance(source_expr, ast.Name):
            source = source_expr.id
        else:
            source = '_ail_sk%d_src' % n
            if (isinstance(source_expr, ast.Call) and isinstance(source_expr.func, ast.Name)
                    and source_expr.func.id == 'range'):
                # `sorted(range(n), key=...)`: a range is not a list (it has no .copy()); the
                # comprehension makes the list[int] the rest of the rewrite indexes and copies.
                element = '_ail_sk%d_r' % n
                source_expr = ast.ListComp(elt=_name(element), generators=[ast.comprehension(
                    target=_name(element, True), iter=source_expr, ifs=[], is_async=0)])
            pre.append(ast.Assign(targets=[_name(source, True)], value=source_expr))
        param, body = self.key_parts(key)
        columns = []
        structs = False
        for j, comp in enumerate(self.components(body)):
            if isinstance(comp, ast.Name) and comp.id == param:
                columns.append(source)
                continue
            name = '_ail_sk%d_c%d' % (n, j)
            if _field_style(comp, param):
                structs = True
                # struct elements: read the field off `source[i]`; a comprehension over a struct
                # list can only produce numbers, but an indexed element can feed any expression
                index = '_ail_sk%d_i%d' % (n, j)
                element = ast.Subscript(value=_name(source), slice=_name(index), ctx=ast.Load())
                pre.append(self.index_column(
                    name, index, _Substitute(param, element).visit(copy.deepcopy(comp)), source))
            else:
                element = '_ail_sk%d_e%d' % (n, j)
                pre.append(self.element_column(
                    name, element, _Substitute(param, _name(element)).visit(copy.deepcopy(comp)),
                    source))
            columns.append(name)
        self.mark_columns(n, pre)
        perm, statements = self.perm_statements(n, reverse, columns)
        pre.extend(statements)
        self.count += 1
        self.structs = structs or source in self.struct_names
        return n, source, perm

    def gather(self, source):
        """A new list holding the elements of `source`. A comprehension types a list of int, float
        or str reliably wherever it came from; a list of structs can only be copied (and a plain
        copy of a list built by a comprehension is mistyped as int by the compiler)."""
        if self.structs or self.stage >= 3:
            return _method(source, 'copy')
        element = '_ail_sk%d_g' % self.next_id()
        return ast.ListComp(elt=_name(element), generators=[ast.comprehension(
            target=_name(element, True), iter=_name(source), ifs=[], is_async=0)])

    def sorted_site(self, call, pre, assignment=None):
        """Replacement for `sorted(...)`. With `assignment` (an Assign/AnnAssign to a plain name
        whose whole value is this call) the copy is made straight into that name and DONE is
        returned after the statement and the reordering have been appended to `pre`."""
        what = 'sorted()'
        if len(call.args) != 1:
            return call
        source = call.args[0]
        if _items_receiver(source) is not None:
            raise self.Unsupported('sorted(d.items()) is supported only as the iterable of '
                                   '`for k, v in sorted(d.items(), ...)`; this language has no '
                                   'tuple values (use sorted(d.keys(), key=lambda k: ...) and '
                                   'index d[k])')
        key, reverse = self.options(call, what)
        if key is None:
            if self.stage >= 1 and isinstance(source, ast.Name) and source.id in self.dicts:
                call.args[0] = _method(source.id, 'keys')
                self.count += 1
            return call
        if self.stage == 1 and self.old_shape(key):
            return call
        if isinstance(source, ast.Name) and source.id in self.dicts:
            source = _method(source.id, 'keys')
        n, src, perm = self.keyed(source, key, reverse, pre)
        if assignment is not None:
            target = (assignment.targets[0] if isinstance(assignment, ast.Assign)
                      else assignment.target).id
            assignment.value = self.gather(src)
            pre.append(assignment)
            pre.append(ast.Expr(value=_call(APPLY, _name(target), _name(perm))))
            return DONE
        target = '_ail_sk%d_s' % n
        pre.append(ast.Assign(targets=[_name(target, True)], value=self.gather(src)))
        pre.append(ast.Expr(value=_call(APPLY, _name(target), _name(perm))))
        return _name(target)

    def sort_statement(self, st):
        """`xs.sort(key=..., reverse=...)` -> statements, or None to leave it alone."""
        call = st.value
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                and call.func.attr == 'sort' and isinstance(call.func.value, ast.Name)
                and not call.args):
            return None
        key, reverse = self.options(call, 'sort()')
        if key is None:
            return None
        if self.stage == 1 and self.old_shape(key):
            return None
        pre = []
        n, src, perm = self.keyed(call.func.value, key, reverse, pre)
        pre.append(ast.Expr(value=_call(APPLY, _name(src), _name(perm))))
        return pre

    # -- for k, v in sorted(d.items(), ...) -----------------------------------------------------
    def for_items(self, st):
        it = st.iter
        if not (_is_sorted_call(it) and len(it.args) == 1):
            return None
        receiver = _items_receiver(it.args[0])
        if receiver is None:
            return None
        if not (isinstance(st.target, ast.Tuple) and len(st.target.elts) == 2
                and all(isinstance(e, ast.Name) for e in st.target.elts)):
            raise self.Unsupported('for ... in sorted(d.items(), ...) binds exactly two names: '
                                   '`for k, v in sorted(d.items())`')
        key, reverse = self.options(it, 'sorted()')
        n = self.next_id()
        keys, values = '_ail_sk%d_k' % n, '_ail_sk%d_v' % n
        pre = [ast.Assign(targets=[_name(keys, True)], value=_method(receiver, 'keys')),
               ast.Assign(targets=[_name(values, True)], value=_method(receiver, 'values'))]
        columns = []
        if key is None:
            # tuples compare by (k, v); keys are unique, so the key alone decides
            columns.append(keys)
        else:
            param, body = self.key_parts(key)
            for j, comp in enumerate(self.components(body)):
                reads = _pair_reads(comp, param)
                if (isinstance(comp, ast.Subscript) and isinstance(comp.value, ast.Name)
                        and comp.value.id == param and len(reads) == 1):
                    columns.append(keys if 0 in reads else values)
                    continue
                name = '_ail_sk%d_c%d' % (n, j)
                if reads == {1}:
                    element = '_ail_sk%d_e%d' % (n, j)
                    expr = _SubstituteItem(param, {1: _name(element)}, self.Unsupported).visit(
                        copy.deepcopy(comp))
                    pre.append(self.element_column(name, element, expr, values))
                elif reads <= {0}:
                    element = '_ail_sk%d_e%d' % (n, j)
                    expr = _SubstituteItem(param, {0: _name(element)}, self.Unsupported).visit(
                        copy.deepcopy(comp))
                    pre.append(self.element_column(name, element, expr, keys))
                else:
                    index = '_ail_sk%d_i%d' % (n, j)
                    at = lambda source: ast.Subscript(value=_name(source), slice=_name(index),
                                                      ctx=ast.Load())
                    expr = _SubstituteItem(param, {0: at(keys), 1: at(values)},
                                           self.Unsupported).visit(copy.deepcopy(comp))
                    pre.append(self.index_column(name, index, expr, keys))
                columns.append(name)
        self.mark_columns(n, pre)
        perm, statements = self.perm_statements(n, reverse, columns)
        pre.extend(statements)
        step = '_ail_sk%d_t' % n
        k, v = st.target.elts
        prologue = [
            ast.Assign(targets=[_name(k.id, True)],
                       value=ast.Subscript(value=_name(keys), slice=_name(step), ctx=ast.Load())),
            ast.Assign(targets=[_name(v.id, True)],
                       value=ast.Subscript(value=_name(values), slice=_name(step), ctx=ast.Load()))]
        for k, item in enumerate(pre + prologue):
            stamp(item, st.lineno, -100000 + k)
        loop = ast.For(target=_name(step, True), iter=_name(perm),
                       body=prologue + self.block(st.body), orelse=self.block(st.orelse),
                       type_comment=None)
        ast.copy_location(loop, st)
        self.count += 1
        return pre + [loop]

    # -- walking ---------------------------------------------------------------------------------
    def expr(self, node, pre):
        if node is None:
            return None
        if isinstance(node, (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp,
                             ast.GeneratorExp, ast.BoolOp, ast.IfExp)):
            return node            # evaluated conditionally or repeatedly: never hoisted
        for field, value in ast.iter_fields(node):
            if isinstance(value, list):
                setattr(node, field, [self.expr(v, pre) if isinstance(v, ast.expr) else v
                                      for v in value])
            elif isinstance(value, ast.expr):
                setattr(node, field, self.expr(value, pre))
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                kw.value = self.expr(kw.value, pre)
            if _is_sorted_call(node):
                return self.sorted_site(node, pre)
        return node

    def block(self, statements):
        out = []
        for st in statements:
            out.extend(self.statement(st))
        return out

    def place(self, items, st):
        """Give each synthesized statement a position on the line of `st`, ordered before it
        (columns below zero) or after it. The last-use analysis in pyfunc.py orders a name's
        mentions by (line, column), so a hoisted statement must not look later than `st` itself,
        whatever columns the user's key expression happened to sit at."""
        before = True
        for k, item in enumerate(items):
            if item is st:
                before = False
                continue
            stamp(item, st.lineno, -100000 + k if before else 100000 + k)
        return items

    def statement(self, st):
        pre = []
        if isinstance(st, ast.For):
            replaced = self.for_items(st)
            if replaced is not None:
                return replaced
            st.iter = self.expr(st.iter, pre)
            st.body, st.orelse = self.block(st.body), self.block(st.orelse)
        elif isinstance(st, ast.While):
            st.body, st.orelse = self.block(st.body), self.block(st.orelse)
        elif isinstance(st, ast.If):
            st.test = self.expr(st.test, pre)
            st.body, st.orelse = self.block(st.body), self.block(st.orelse)
        elif isinstance(st, ast.Try):
            st.body, st.orelse, st.finalbody = (self.block(st.body), self.block(st.orelse),
                                                self.block(st.finalbody))
            for handler in st.handlers:
                handler.body = self.block(handler.body)
        elif isinstance(st, ast.With):
            st.body = self.block(st.body)
        elif isinstance(st, ast.Expr):
            replaced = self.sort_statement(st)
            if replaced is not None:
                return self.place(replaced, st)
            st.value = self.expr(st.value, pre)
        elif isinstance(st, (ast.Assign, ast.AnnAssign)) and st.value is not None:
            target = st.targets[0] if isinstance(st, ast.Assign) else st.target
            if (_is_sorted_call(st.value) and len(st.value.args) == 1
                    and isinstance(target, ast.Name)
                    and (not isinstance(st, ast.Assign) or len(st.targets) == 1)):
                st.value.args[0] = self.expr(st.value.args[0], pre)
                result = self.sorted_site(st.value, pre, assignment=st)
                if result is DONE:
                    return self.place(pre, st)
                st.value = result
            else:
                st.value = self.expr(st.value, pre)
        elif isinstance(st, ast.AugAssign):
            st.value = self.expr(st.value, pre)
        elif isinstance(st, ast.Return):
            st.value = self.expr(st.value, pre)
        return self.place(pre, st) + [st]


def rewrite(tree, stage, old_shape, Unsupported):
    """Rewrite keyed-sort sites in `tree` in place; returns how many sites changed."""
    total = serial = 0
    classes = {n.name for n in tree.body if isinstance(n, ast.ClassDef)}
    for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        rewriter = _Rewriter(stage, old_shape, Unsupported)
        rewriter.serial = serial        # names are unique across the whole program, not per function
        rewriter.dicts = _dict_names(fn)
        rewriter.struct_names = _struct_list_names(fn, classes)
        fn.body = rewriter.block(fn.body)
        total += rewriter.count
        serial = rewriter.serial
    if total:
        ast.fix_missing_locations(tree)
    return total
