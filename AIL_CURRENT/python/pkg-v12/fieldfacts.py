"""Whole-program field facts (bce s4): parallel list groups and non-negative int fields.

The pass runs once, over every function of the program, before any function is lowered --
from `pyfunc._to_c_once`, beside the whole-program call graph.  It changes no code: it
only computes facts (bce s5/s6 consume them) and, under `AIL_BCE_FACTS=<path>`, dumps them
as JSON.

The facts are intentionally conservative.  A use this pass does not recognise invalidates
the group (or field) it could affect, so the only facts reported are those every use in the
whole program supports.  `--separate`, `--object`, `--module`, libraries and `@extern`
programs get empty facts (see `compute`).
"""
import ast


_LIST_FIELD_KINDS = frozenset(('list', 'flist', 'slist', 'blist'))
_ISTORE_METHODS = frozenset(('append', 'pop', 'clear'))
_MUTATORS = frozenset(('append', 'pop', 'clear', 'insert', 'extend', 'remove'))
_READ_BUILTINS = frozenset(('sum', 'min', 'max', 'sorted', 'str'))


def _is_list_kind(kind):
    if kind in _LIST_FIELD_KINDS:
        return True
    return isinstance(kind, tuple) and len(kind) == 2 and kind[0] in ('olist', 'hlist')


def _is_int_kind(kind):
    return kind == 'int'


def _is_numeric_constant(node):
    if isinstance(node, ast.Constant) and not isinstance(node.value, bool):
        return isinstance(node.value, (int, float))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        return _is_numeric_constant(node.operand)
    return False


def _is_simple_arg(node):
    """A value a group block may pass to `append`: a name or a constant (cannot raise)."""
    if isinstance(node, ast.Name):
        return True
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        return _is_numeric_constant(node)
    return False


class _Struct:
    def __init__(self, name):
        self.name = name
        self.fields = []          # [(field, kind)]
        self.field_kind = {}
        self.params = []          # __init__ parameters after self
        self.init_expr = {}       # field -> expression assigned in __init__


class _Run:
    def __init__(self, fn, kind, obj):
        self.fn = fn
        self.kind = kind
        self.obj = obj
        self.members = []         # [(key, call_node)]
        self.ok = True


class _Pass:
    def __init__(self, fns, classes, classdefs):
        self.fns = fns
        self.classes = classes or {}
        self.classdefs = {c.name: c for c in (classdefs or ())}
        self.structs = {}
        self.field_struct = {}    # unique field name -> struct name
        self.field_kind = {}
        self.list_fields = set()
        self.int_fields = {}      # field -> struct (only unique names)
        self.runs = []
        self.mutations = []       # (key, call_node, method)
        self.body_of = {}
        self.stmt_body = {}
        self.local_lists = {}     # fn name -> set of list local names
        self.local_members = {}   # fn name -> set of component candidate names (filled later)
        self._build_structs()

    # ---------------------------------------------------------------- struct shape
    def _build_structs(self):
        for name, info in getattr(self.classes, 'items', lambda: [])():
            st = _Struct(name)
            field_order = list(getattr(info, 'field_order', ()) or ())
            field_types = dict(getattr(info, 'field_types', {}) or {})
            cdef = self.classdefs.get(name)
            init = None
            if cdef is not None:
                for stmt in cdef.body:
                    if isinstance(stmt, ast.FunctionDef) and stmt.name == '__init__':
                        init = stmt
                        break
            if init is not None:
                st.params = [a.arg for a in init.args.args[1:]]
                for stmt in init.body:
                    target, value = None, None
                    if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                        target, value = stmt.targets[0], stmt.value
                    elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
                        target, value = stmt.target, stmt.value
                    if (isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
                            and target.value.id == 'self'):
                        st.init_expr[target.attr] = value
            for field in field_order:
                kind = field_types.get(field)
                st.fields.append((field, kind))
                st.field_kind[field] = kind
            self.structs[name] = st
        for name, st in self.structs.items():
            for field, kind in st.fields:
                if not (field in self.field_struct):
                    self.field_struct[field] = name
                elif self.field_struct[field] != name:
                    self.field_struct[field] = None
                if _is_list_kind(kind):
                    self.list_fields.add(field)
                if _is_int_kind(kind):
                    self.int_fields[field] = None
        # duplicate names are ambiguous: keep them out of both analyses
        for field, owner in list(self.field_struct.items()):
            if owner is None:
                self.list_fields.discard(field)
                self.int_fields.pop(field, None)
            else:
                if field in self.int_fields:
                    self.int_fields[field] = owner

    # ---------------------------------------------------------------- statement trees
    def _walk_bodies(self, fn_name):
        """Yield every statement-list of every function once, in source order."""
        for fn in self.fns:
            if fn.name != fn_name:
                continue
            yield from self._bodies(fn.body)

    def _bodies(self, body):
        self.body_of[id(body)] = body
        for stmt in body:
            self.stmt_body[id(stmt)] = body
        yield body
        for stmt in body:
            for field in ('body', 'orelse', 'finalbody'):
                inner = getattr(stmt, field, None)
                if isinstance(inner, list) and inner and isinstance(inner[0], ast.stmt):
                    yield from self._bodies(inner)
            if isinstance(stmt, (ast.Try,)) or hasattr(ast, 'TryStar') and isinstance(stmt, ast.TryStar):
                for handler in stmt.handlers:
                    yield from self._bodies(handler.body)
            if isinstance(stmt, ast.Match):
                for case in stmt.cases:
                    yield from self._bodies(case.body)

    def _scan_local_lists(self, fn):
        names = set()
        for arg in fn.args.args:
            if _annotation_is_list(arg.annotation):
                names.add(arg.arg)
        for node in ast.walk(fn):
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if _annotation_is_list(node.annotation):
                    names.add(node.target.id)
            elif isinstance(node, ast.Assign) and len(node.targets) == 1 \
                    and isinstance(node.targets[0], ast.Name) \
                    and isinstance(node.value, ast.List):
                names.add(node.targets[0].id)
        self.local_lists[fn.name] = names

    def _member_of(self, target, fn_name):
        if isinstance(target, ast.Attribute):
            if target.attr in self.list_fields:
                return ('field', target.attr), ast.dump(target.value)
            return None, None
        if isinstance(target, ast.Name) and target.id in self.local_lists.get(fn_name, ()):
            return ('local', fn_name, target.id), None
        return None, None

    def _stmt_mutation(self, stmt, fn_name):
        value = None
        if isinstance(stmt, ast.Expr):
            value = stmt.value
        elif isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 \
                and isinstance(stmt.targets[0], ast.Name):
            value = stmt.value
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) \
                and stmt.value is not None:
            value = stmt.value
        if not (isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute)):
            return None
        method = value.func.attr
        if method not in _MUTATORS:
            return None
        key, obj = self._member_of(value.func.value, fn_name)
        if key is None:
            return None
        ok = method in _ISTORE_METHODS
        if method in ('append',):
            ok = ok and len(value.args) == 1 and not value.keywords \
                and _is_simple_arg(value.args[0])
        elif method in ('pop', 'clear'):
            ok = ok and not value.args and not value.keywords
        return {'key': key, 'obj': obj, 'kind': method, 'call': value, 'ok': ok}

    def _collect_runs(self):
        for fn in self.fns:
            self._scan_local_lists(fn)
        for fn in self.fns:
            for body in self._bodies(fn.body):
                run = None
                for stmt in body:
                    m = self._stmt_mutation(stmt, fn.name)
                    if m is None:
                        if run is not None:
                            self._close_run(run)
                            run = None
                        continue
                    if run is None:
                        run = _Run(fn.name, m['kind'], m['obj'])
                    if m['kind'] != run.kind or m['obj'] != run.obj:
                        self._close_run(run)
                        run = _Run(fn.name, m['kind'], m['obj'])
                    run.members.append((m['key'], m['call']))
                    if not m['ok']:
                        run.ok = False
                    self.mutations.append((m['key'], m['call'], m['kind']))
                if run is not None:
                    self._close_run(run)

    def _close_run(self, run):
        if run.members:
            self.runs.append(run)

    # ---------------------------------------------------------------- components
    def _components(self):
        parent = {}

        def find(x):
            parent.setdefault(x, x)
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        for run in self.runs:
            keys = [k for k, _ in run.members]
            distinct = set(keys)
            if not run.ok or run.kind not in _ISTORE_METHODS or len(distinct) < 2:
                continue
            if len(keys) != len(distinct):
                continue
            first = keys[0]
            for key in keys[1:]:
                union(first, key)
        groups = {}
        for key in parent:
            groups.setdefault(find(key), set()).add(key)
        return [g for g in groups.values() if len(g) >= 2]

    # ---------------------------------------------------------------- validation
    def _same_initial_length(self, comp, members):
        struct = None
        for key in comp:
            if key[0] != 'field':
                return False
            s = self.field_struct.get(key[1])
            if s is None:
                return False
            if struct is None:
                struct = s
            elif struct != s:
                return False
        st = self.structs.get(struct)
        if st is None:
            return False
        calls = []
        for fn in self.fns:
            for node in ast.walk(fn):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                        and node.func.id == struct:
                    calls.append(node)
        for call in calls:
            forms = []
            for key in comp:
                field = key[1]
                expr = st.init_expr.get(field)
                if expr is None:
                    return False
                if isinstance(expr, ast.Name) and expr.id in st.params:
                    index = st.params.index(expr.id)
                    arg = None
                    if index < len(call.args):
                        arg = call.args[index]
                    for kw in call.keywords:
                        if kw.arg == expr.id:
                            arg = kw.value
                    if arg is None:
                        return False
                    expr = arg
                form = _length_form(expr)
                if form is None:
                    return False
                forms.append(form)
            if len(set(forms)) != 1:
                return False
        return True

    def _local_initialisation(self, comp, members):
        fn_names = {key[1] for key in comp}
        if len(fn_names) != 1:
            return False, None
        fn_name = next(iter(fn_names))
        init_stmts = {}
        for key in comp:
            name = key[2]
            found = []
            other = []
            for node in ast.walk(self._fn_by_name(fn_name)):
                if isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, ast.Store):
                    target = node
                    stmt = self._stmt_owning(fn_name, target)
                    if (isinstance(stmt, ast.AnnAssign) and stmt.target is target
                            and isinstance(stmt.value, ast.List) and not stmt.value.elts):
                        found.append(stmt)
                    elif (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1
                          and stmt.targets[0] is target
                          and isinstance(stmt.value, ast.List) and not stmt.value.elts):
                        found.append(stmt)
                    else:
                        other.append(node)
            if other or len(found) != 1:
                return False, None
            init_stmts[key] = found[0]
        # every init statement must live in the same statement list
        holders = [self.stmt_body.get(id(init_stmts[key])) for key in comp]
        if any(h is None for h in holders) \
                or len({id(h) for h in holders}) != 1:
            return False, None
        last_pos = max((s.lineno, s.col_offset) for s in init_stmts.values())
        uses = []
        for key in comp:
            name = key[2]
            for node in ast.walk(self._fn_by_name(fn_name)):
                if isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, ast.Load):
                    uses.append((node.lineno, node.col_offset))
        if any(pos <= last_pos for pos in uses):
            return False, None
        targets = set()
        for stmt in init_stmts.values():
            targets.add(id(stmt.target if isinstance(stmt, ast.AnnAssign) else stmt.targets[0]))
        return True, targets

    def _fn_by_name(self, name):
        for fn in self.fns:
            if fn.name == name:
                return fn
        return None

    def _stmt_owning(self, fn_name, target):
        fn = self._fn_by_name(fn_name)
        for node in ast.walk(fn):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(target is t for t in targets):
                    return node
        return None

    def _validate_component(self, comp):
        keys = set(comp)
        if all(k[0] == 'field' for k in comp):
            init_ok = self._same_initial_length(comp, keys)
            init_ids = set()
        elif all(k[0] == 'local' for k in comp):
            init_ok, init_ids = self._local_initialisation(comp, keys)
        else:
            return None
        if not init_ok:
            return None
        accepted = set()
        kinds = set()
        for run in self.runs:
            run_keys = {k for k, _ in run.members}
            if not (run_keys & keys):
                continue
            if not run.ok or run.kind not in _ISTORE_METHODS:
                return None
            listed = [k for k, _ in run.members]
            if len(listed) != len(set(listed)) or set(listed) != keys:
                return None
            kinds.add(run.kind)
            for _, call in run.members:
                accepted.add(id(call))
        if not kinds:
            return None
        grow_only = kinds == {'append'}
        # every occurrence of a member must be one the group rules allow
        for key in keys:
            if key[0] == 'field':
                field = key[1]
                for fn in self.fns:
                    if not self._field_occurrences_ok(fn, field, accepted, init_ids):
                        return None
            else:
                fn = self._fn_by_name(key[1])
                if fn is None or not self._local_occurrences_ok(fn, key[2], accepted, init_ids):
                    return None
        return grow_only

    def _field_occurrences_ok(self, fn, field, accepted, init_ids):
        parents = _parent_map(fn)
        for node in ast.walk(fn):
            if isinstance(node, ast.Attribute) and node.attr == field:
                if not _occurrence_ok(node, parents, accepted, init_ids):
                    return False
        return True

    def _local_occurrences_ok(self, fn, name, accepted, init_ids):
        for node in ast.walk(fn):
            if isinstance(node, ast.Global) and name in node.names:
                return False
        parents = _parent_map(fn)
        for node in ast.walk(fn):
            if isinstance(node, ast.Name) and node.id == name:
                if not _occurrence_ok(node, parents, accepted, init_ids):
                    return False
        return True

    # ---------------------------------------------------------------- groups
    def groups(self):
        self._collect_runs()
        out = []
        for comp in self._components():
            grow_only = self._validate_component(comp)
            if grow_only is None:
                continue
            if all(k[0] == 'field' for k in comp):
                struct = self.field_struct[next(iter(comp))[1]]
                members = sorted(k[1] for k in comp)
                out.append({'struct': struct, 'fn': None, 'members': members,
                            'grow_only': grow_only})
            else:
                fn = next(iter(comp))[1]
                members = sorted(k[2] for k in comp)
                out.append({'struct': None, 'fn': fn, 'members': members,
                            'grow_only': grow_only})
        out.sort(key=lambda g: (g['struct'] or '', g['fn'] or '', g['members']))
        return out

    # ---------------------------------------------------------------- non-negative ints
    def nonneg(self):
        if not self.int_fields:
            return []
        fields = dict(self.int_fields)
        bytes_fields = {f for f, st in self.structs.items() for fld, kind in st.fields
                        if self.field_struct.get(fld) == f and kind == 'bytes'}
        fn_locals = {}
        result_nonneg = {fn.name: False for fn in self.fns}
        for _ in range(32):
            changed = False
            new_results = {}
            for fn in self.fns:
                locals_nn = _local_nonneg(fn, result_nonneg, bytes_fields, self.field_struct)
                fn_locals[fn.name] = locals_nn
                rets = [n.value for n in ast.walk(fn)
                        if isinstance(n, ast.Return) and n.value is not None]
                new_results[fn.name] = bool(rets) and all(
                    _expr_nonneg(e, locals_nn, result_nonneg, {}, fn.name,
                                 bytes_fields, self.field_struct) for e in rets)
            for name, value in new_results.items():
                if value and not result_nonneg[name]:
                    result_nonneg[name] = True
                    changed = True
            if not changed:
                break
        # fields start non-negative and are only retired
        for _ in range(32):
            changed = False
            for field, struct in fields.items():
                if not field:
                    continue
                if not _field_still_nonneg(self, struct, field, fn_locals, result_nonneg,
                                           bytes_fields):
                    fields[field] = None
                    changed = True
            if not changed:
                break
        return sorted((struct, field) for field, struct in fields.items() if struct is not None)


def _annotation_is_list(annotation):
    return isinstance(annotation, ast.Subscript) and isinstance(annotation.value, ast.Name) \
        and annotation.value.id in ('list', '__ail_checked_list') \
        or isinstance(annotation, ast.Name) and annotation.id in ('list', 'flist', 'slist')


def _length_form(node):
    if isinstance(node, ast.List) and not node.elts:
        return ('empty',)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult) \
            and isinstance(node.left, ast.List) and len(node.left.elts) == 1:
        return ('repeat', ast.dump(node.right))
    return None


def _parent_map(fn):
    parents = {}
    for node in ast.walk(fn):
        for child in ast.iter_child_nodes(node):
            parents[id(child)] = node
    return parents


def _occ_parent(parents, node):
    return parents.get(id(node))


def _occurrence_ok(node, parents, accepted, init_ids):
    if id(node) in init_ids:
        return True
    # a lambda (or any closure) may capture the list and keep it: not a read this pass can see
    ancestor = parents.get(id(node))
    while ancestor is not None:
        if isinstance(ancestor, ast.Lambda):
            return False
        ancestor = parents.get(id(ancestor))
    parent = parents.get(id(node))
    if parent is None:
        return False
    grand = parents.get(id(parent))
    if isinstance(parent, ast.Attribute) and parent.value is node:
        if parent.attr in _ISTORE_METHODS:
            return isinstance(grand, ast.Call) and grand.func is parent and id(grand) in accepted
        if parent.attr == 'sort':
            return isinstance(grand, ast.Call) and grand.func is parent \
                and not grand.args and not grand.keywords
        return False
    if isinstance(parent, ast.Subscript) and parent.value is node:
        if isinstance(parent.slice, ast.Slice):
            return False
        return isinstance(parent.ctx, (ast.Load, ast.Store))
    if isinstance(parent, ast.Call) and parent.func is not node:
        if isinstance(parent.func, ast.Name) and parent.func.id == 'len' \
                and node in parent.args:
            return True
        if isinstance(parent.func, ast.Name) and parent.func.id in _READ_BUILTINS \
                and node in parent.args:
            return True
        return False
    if isinstance(parent, (ast.For, ast.AsyncFor)) and parent.iter is node:
        return True
    if isinstance(parent, ast.Compare):
        if node in parent.comparators:
            index = parent.comparators.index(node)
            return isinstance(parent.ops[index], (ast.In, ast.NotIn))
        return False
    if isinstance(parent, (ast.Assign, ast.AnnAssign)):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            return id(node) in init_ids
        return False
    return False


def _sources(fn):
    """Every statement body of `fn`, for the local non-negative fixed point."""
    out = []
    seen = set()

    def walk(body):
        if id(body) in seen:
            return
        seen.add(id(body))
        out.append(body)
        for stmt in body:
            for field in ('body', 'orelse', 'finalbody'):
                inner = getattr(stmt, field, None)
                if isinstance(inner, list) and inner and isinstance(inner[0], ast.stmt):
                    walk(inner)
            if isinstance(stmt, ast.Try) or hasattr(ast, 'TryStar') and isinstance(stmt, ast.TryStar):
                for handler in stmt.handlers:
                    walk(handler.body)
            if isinstance(stmt, ast.Match):
                for case in stmt.cases:
                    walk(case.body)
    walk(fn.body)
    return out


def _definitions(fn):
    defs = {}
    params = {a.arg for a in fn.args.args}

    def add(name, kind, expr=None):
        defs.setdefault(name, []).append((kind, expr))

    for body in _sources(fn):
        for stmt in body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        add(target.id, 'assign', stmt.value)
                    else:
                        for sub in ast.walk(target):
                            if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                                add(sub.id, 'other')
            elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                add(stmt.target.id, 'assign' if stmt.value is not None else 'other', stmt.value)
            elif isinstance(stmt, ast.AugAssign) and isinstance(stmt.target, ast.Name):
                op = 'aug_add' if isinstance(stmt.op, ast.Add) else (
                    'aug_sub' if isinstance(stmt.op, ast.Sub) else 'other')
                add(stmt.target.id, op, stmt.value)
            elif isinstance(stmt, (ast.For, ast.AsyncFor)):
                for sub in ast.walk(stmt.target):
                    if isinstance(sub, ast.Name):
                        add(sub.id, 'other')
            elif isinstance(stmt, ast.With):
                for item in stmt.items:
                    if item.optional_vars is not None:
                        for sub in ast.walk(item.optional_vars):
                            if isinstance(sub, ast.Name):
                                add(sub.id, 'other')
            elif isinstance(stmt, ast.ExceptHandler) and stmt.name:
                add(stmt.name, 'other')
    return defs, params


def _local_nonneg(fn, result_nonneg, bytes_fields, field_struct):
    defs, params = _definitions(fn)
    names = set(defs)
    nonneg = {name: name not in params for name in names}
    for _ in range(32):
        changed = False
        for name in names:
            if not nonneg[name]:
                continue
            ok = True
            for kind, expr in defs.get(name, ()):
                if kind == 'assign':
                    ok = _expr_nonneg(expr, nonneg, result_nonneg, {}, fn.name,
                                      bytes_fields, field_struct)
                elif kind == 'aug_add':
                    ok = (nonneg.get(name, False) and
                          _expr_nonneg(expr, nonneg, result_nonneg, {}, fn.name,
                                       bytes_fields, field_struct))
                elif kind == 'aug_sub':
                    ok = nonneg.get(name, False) and _is_zero(expr)
                else:
                    ok = False
                if not ok:
                    break
            if not ok:
                nonneg[name] = False
                changed = True
        if not changed:
            break
    return nonneg


def _is_zero(node):
    return isinstance(node, ast.Constant) and not isinstance(node.value, bool) and node.value == 0


def _expr_nonneg(node, locals_nn, result_nonneg, fields_nn, fn_name, bytes_fields, field_struct):
    if node is None:
        return False
    if isinstance(node, ast.Constant):
        return not isinstance(node.value, bool) and isinstance(node.value, (int, float)) \
            and node.value >= 0
    if isinstance(node, ast.Name):
        return bool(locals_nn.get(node.id, False))
    if isinstance(node, ast.Attribute):
        return bool(fields_nn.get(node.attr, False))
    if isinstance(node, ast.Subscript):
        return _bytes_expr(node.value, locals_nn, bytes_fields, field_struct)
    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.UAdd):
            return _expr_nonneg(node.operand, locals_nn, result_nonneg, fields_nn,
                                fn_name, bytes_fields, field_struct)
        return False
    if isinstance(node, ast.BinOp):
        left = _expr_nonneg(node.left, locals_nn, result_nonneg, fields_nn,
                            fn_name, bytes_fields, field_struct)
        right = _expr_nonneg(node.right, locals_nn, result_nonneg, fields_nn,
                             fn_name, bytes_fields, field_struct)
        if isinstance(node.op, (ast.Add, ast.Mult, ast.BitOr, ast.BitXor,
                                ast.Mod, ast.FloorDiv)):
            return left and right
        if isinstance(node.op, (ast.LShift, ast.RShift)):
            return left
        if isinstance(node.op, ast.BitAnd):
            if left and right:
                return True
            return _nonneg_mask(node.left) or _nonneg_mask(node.right)
        return False
    if isinstance(node, ast.IfExp):
        return _expr_nonneg(node.body, locals_nn, result_nonneg, fields_nn,
                            fn_name, bytes_fields, field_struct) and \
            _expr_nonneg(node.orelse, locals_nn, result_nonneg, fields_nn,
                         fn_name, bytes_fields, field_struct)
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            if node.func.id == 'len':
                return True
            if node.func.id == 'ord':
                return True
            return bool(result_nonneg.get(node.func.id, False))
        return False
    return False


def _nonneg_mask(node):
    if isinstance(node, ast.Constant) and not isinstance(node.value, bool) \
            and isinstance(node.value, int) and node.value >= 0:
        return True
    return False


def _bytes_expr(node, locals_nn, bytes_fields, field_struct):
    if isinstance(node, ast.Attribute):
        return node.attr in bytes_fields
    if isinstance(node, ast.Name):
        return False
    return False


def _field_still_nonneg(pass_, struct, field, fn_locals, result_nonneg, bytes_fields):
    st = pass_.structs.get(struct)
    if st is None:
        return False
    # constructor values
    for fn in pass_.fns:
        locals_nn = fn_locals.get(fn.name, {})
        for node in ast.walk(fn):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == struct):
                continue
            expr = st.init_expr.get(field)
            if expr is None:
                return False
            if isinstance(expr, ast.Name) and expr.id in st.params:
                index = st.params.index(expr.id)
                arg = None
                if index < len(node.args):
                    arg = node.args[index]
                for kw in node.keywords:
                    if kw.arg == expr.id:
                        arg = kw.value
                if arg is None:
                    return False
                expr = arg
            if not _expr_nonneg(expr, locals_nn, result_nonneg, {}, fn.name,
                                bytes_fields, pass_.field_struct):
                return False
    # direct stores, in every function except __init__ (which is the shape above)
    for fn in pass_.fns:
        locals_nn = fn_locals.get(fn.name, {})
        nn = {f: (f == field) for f in pass_.int_fields}
        nn[field] = True
        for node in ast.walk(fn):
            target, value, kind = None, None, None
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target, value = node.targets[0], node.value
                kind = 'assign'
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                target, value = node.target, node.value
                kind = 'assign'
            elif isinstance(node, ast.AugAssign):
                target, value = node.target, node.value
                kind = 'aug_add' if isinstance(node.op, ast.Add) else (
                    'aug_sub' if isinstance(node.op, ast.Sub) else 'other')
            if not (isinstance(target, ast.Attribute) and target.attr == field):
                continue
            if kind == 'assign':
                ok = _expr_nonneg(value, locals_nn, result_nonneg, nn, fn.name,
                                  bytes_fields, pass_.field_struct)
            elif kind == 'aug_add':
                ok = _expr_nonneg(value, locals_nn, result_nonneg, nn, fn.name,
                                  bytes_fields, pass_.field_struct)
            elif kind == 'aug_sub':
                ok = _is_zero(value)
            else:
                ok = False
            if not ok:
                return False
    return True


def compute(fns, classes, classdefs, *, library=False, external=None, info=None,
            enabled=True, closures=False):
    """The facts for one whole program, or empty facts when they would not be sound."""
    empty = {'groups': [], 'nonneg': []}
    if not enabled or not fns:
        return empty
    # A captured list (a lambda or a lifted nested function) can be kept and changed after this
    # pass looked: no fact survives a closure in the program. The Python front end's `nestfn.py`
    # hoists a nested def to `outer__inner`, pyfunc lifts one to `outer__inner__N`, and `tuplam.py`
    # names a lambda `_ail_lamN`; any of those is a closure here. `ail_modules.py` renames an
    # imported module's top-level names to `module__name` (a class keeps its printed name); those
    # are user modules too, and their module bodies may still run later.
    names = {f.name for f in fns}
    class_names = set(getattr(classes, 'keys', lambda: ())())
    if closures:
        return empty
    for name in names:
        if name.startswith('_ail_lam'):
            return empty
        if '__' in name:
            head = name.split('__', 1)[0]
            if head in names or head not in class_names:
                return empty
    if any('__' in name for name in class_names):
        return empty
    if library or (info is not None and (info.get('_want_units') or info.get('_link_units'))):
        return empty
    if external and any(external.get(section) for section in ('exports', 'constants', 'structs')):
        return empty
    try:
        pass_ = _Pass(fns, classes, classdefs)
        return {'groups': pass_.groups(), 'nonneg': pass_.nonneg()}
    except Exception:
        # The facts are an optimisation input only; anything unexpected means "no facts".
        return empty
