"""Expression lowering of the tuple pass: types and rewrites in one walk (ex returns (node, type))."""
import ast

from tupcommon import *  # noqa: F401,F403
from tupcommon import _here  # noqa: F401


def unopt(t):
    t = R(t)
    if isinstance(t, tuple) and t[0] == 'opt':
        return R(t[1])
    return t


# read-only sequence annotations of a parameter or a result, read as a list (see `Exprs.sig_ann`)
SIGNATURE_SEQUENCES = frozenset(('Sequence', 'Collection'))


class Exprs:
    # ------------------------------------------------------------------------------------------
    # plumbing
    def refuse(self, node, message):
        raise Refused((getattr(node, 'lineno', 1), message))

    def force(self):
        if not self.quiet:
            self.forced = True

    def fresh(self, base='tu'):
        while True:
            self.counter += 1
            nm = '_%s%d' % (base, self.counter)
            if nm not in self.names:
                self.names.add(nm)
                self.fresh_names.add(nm)
                return nm

    def use_type(self, t):
        """Make sure every class / table a (lowered) type spells exists."""
        t = deep(t)
        if not isinstance(t, tuple):
            return
        if t[0] == 'tuple':
            self.gen.tcls(t)
            for e in t[1]:
                self.use_type(e)
        elif t[0] in ('list', 'opt', 'iter'):
            self.use_type(t[1])
        elif t[0] == 'set':
            self.use_type(t[1])
            if is_table_set(t):
                self.gen.table(t[1], None)
        elif t[0] == 'dict':
            self.use_type(t[1])
            self.use_type(t[2])
            if is_table_dict(t):
                self.gen.table(t[1], t[2])

    def table(self, t):
        t = deep(t)
        return self.gen.table(t[1], t[2] if t[0] == 'dict' else None)

    # ------------------------------------------------------------------------------------------
    # annotations
    def ann(self, node):
        if node is None:
            return None
        if isinstance(node, ast.Constant):
            if node.value is None:
                return 'none'
            if isinstance(node.value, str):
                try:
                    return self.ann(ast.parse(node.value, mode='eval').body)
                except SyntaxError:
                    return None
            return None
        if isinstance(node, ast.Name):
            if node.id in (INT, FLT, STR, BOOL, BYTES):
                return node.id
            if node.id in ('list', 'List'):
                return ('list', Hole())
            if node.id in ('tuple', 'Tuple'):
                self.refuse(node, 'a bare `tuple` annotation; spell the element types (tuple[int, int])')
            if node.id in self.classes:
                return ('cls', node.id)
            return ('other', node.id)
        if isinstance(node, ast.Attribute):
            return ('other', node.attr)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            left, right = self.ann(node.left), self.ann(node.right)
            if right == 'none':
                return ('opt', left)
            if left == 'none':
                return ('opt', right)
            return None
        if isinstance(node, ast.Subscript):
            base = node.value.id if isinstance(node.value, ast.Name) else (
                node.value.attr if isinstance(node.value, ast.Attribute) else None)
            sl = node.slice
            args = list(sl.elts) if isinstance(sl, ast.Tuple) else [sl]
            if base in ('list', 'List') or (base in SIGNATURE_SEQUENCES and getattr(self, 'in_signature', False)
                                             and isinstance(node.value, ast.Name) and node.value.id not in self.classes):
                return ('list', self.ann(args[0]))
            if base in ('set', 'Set', 'frozenset', 'FrozenSet'):
                return ('set', self.ann(args[0]))
            if base in ('dict', 'Dict') and len(args) == 2:
                return ('dict', self.ann(args[0]), self.ann(args[1]))
            if base in ('tuple', 'Tuple'):
                if any(isinstance(a, ast.Constant) and a.value is Ellipsis for a in args):
                    self.refuse(node, 'a variable-length tuple (tuple[int, ...]); a fixed tuple[int, int] or a '
                                'list is built')
                if isinstance(sl, ast.Tuple) and not sl.elts:
                    self.refuse(node, 'the empty tuple type tuple[()]')
                return ('tuple', tuple(self.ann(a) for a in args))
            if base == 'Optional':
                return ('opt', self.ann(args[0]))
            if base == 'Callable' and len(args) == 2 and isinstance(args[0], ast.List):
                return ('callable', tuple(self.ann(a) for a in args[0].elts), self.ann(args[1]))
            return ('other', base)
        return None

    def map_ann(self, node):
        """The annotation as the lowered program must spell it (unchanged when no tuple is mentioned)."""
        t = self.ann(node)
        if node is None or not has_tuple(t):
            return node, t
        self.use_type(t)
        return ast.parse(ann_text(t), mode='eval').body, t

    def sig_ann(self, node):
        """`ann` of a parameter's or a result's annotation, where a read-only `Sequence[T]` /
        `Collection[T]` is the list it is on the typed path (pyfunc._read_only_sequence_annotations: a
        caller must pass a list there)."""
        saved, self.in_signature = getattr(self, 'in_signature', False), True
        try:
            return self.ann(node)
        finally:
            self.in_signature = saved

    def sig_map_ann(self, node):
        """`map_ann` in a signature; a `Sequence[...]` keeps its own name outside."""
        saved, self.in_signature = getattr(self, 'in_signature', False), True
        try:
            new, t = self.map_ann(node)
        finally:
            self.in_signature = saved
        if (new is not node and isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
                and node.value.id in SIGNATURE_SEQUENCES and isinstance(new, ast.Subscript)):
            new.value = ast.Name(id=node.value.id, ctx=ast.Load())
        return new, t

    # ------------------------------------------------------------------------------------------
    # the walk
    def ex(self, node, want=None, ctx=None):
        method = getattr(self, 'ex_' + type(node).__name__, None)
        if method is None:
            return self.ex_generic(node)
        return method(node, want, ctx)

    def exv(self, node, want=None, ctx=None):
        """An expression in value position: a dict.items() view becomes a real list of pairs."""
        n, t = self.ex(node, want, ctx)
        return self.realize(n, t)

    def realize(self, n, t):
        r = R(t)
        if isinstance(r, tuple) and r[0] == 'items':
            self.force()
            pair = ('tuple', (r[1], r[2]))
            self.gen.tcls(pair)
            return call(self.gen.bitems(r[1], r[2]), n.func.value), ('list', pair)
        return n, t

    def ex_generic(self, node):
        for field, value in ast.iter_fields(node):
            if isinstance(value, ast.expr):
                setattr(node, field, self.exv(value)[0])
            elif isinstance(value, list):
                setattr(node, field, [self.exv(v)[0] if isinstance(v, ast.expr) else v for v in value])
        return node, None

    def test(self, node):
        """An expression used as a condition."""
        n, t = self.exv(node)
        t = deep(t)
        if is_table(t):
            return ast.Compare(left=attr(n, 'n'), ops=[ast.Gt()], comparators=[const(0)])
        if is_tuple(t):
            self.refuse(node, 'the truth value of a tuple (it is true whenever it is non-empty); test a field or '
                        'a length instead')
        return n

    def coerce(self, n, t, want, math=False):
        """An int where a float is expected: CPython keeps the int (annotations convert nothing), so converting
        it here would make a later print or str() show 3.0 where CPython shows 3, and the lowered source is what
        the general path compiles too.  Refused by name (the source is left as written, so the typed path refuses
        it and the default build takes the general path, which keeps the int).  `math=True` is a call into a
        math function, which converts its argument whatever the int's later use (silent6, C39 as found on the
        tuple pass)."""
        w, d = deep(want), deep(t)
        if w == FLT and d in (INT, BOOL):
            if math:
                if isinstance(n, ast.Constant) and type(n.value) is int:
                    return const(float(n.value)), FLT
                return call('float', n), FLT
            self.refuse(n, 'an int where a float is expected (%s); CPython keeps the int (annotations convert '
                        'nothing), so a later print or str() of it shows 3 where this build would show 3.0. '
                        'Write instead: a float (`%s`) if the value is meant to be a float.'
                        % (ast.unparse(n), ast.unparse(n) + '.0' if isinstance(n, ast.Constant) else 'float(%s)' % ast.unparse(n)))
        return n, t

    def ex_Constant(self, node, want=None, ctx=None):
        return node, const_type(node.value)

    def ex_Name(self, node, want=None, ctx=None):
        if node.id in self.alias:
            n, t = self.alias[node.id]
            return fresh_copy(n), t
        if node.id in self.lam_alias:
            self.refuse(node, 'the lambda %s is used as a value; a lambda is built only to be called, passed to a '
                        'function that takes a Callable, or used as a key=' % node.id)
        t = self.env.get(node.id)
        if t is None:
            t = self.consts.get(node.id)
            if node.id in self.rowconst and node.id not in self.env:
                self.force()
                return call('_ail_rc_' + node.id), t
            if node.id in self.tupconst and node.id not in self.env:
                self.force()
                return call(self.gen.tcls(t), *[name('%s__c%d' % (node.id, i)) for i in range(len(t[1]))]), t
        return node, t

    def ex_Attribute(self, node, want=None, ctx=None):
        value = node.value
        if isinstance(value, ast.Name) and self.modalias.get(value.id) == 'math' and node.attr in MATH_VALUES:
            return node, MATH_VALUES[node.attr]
        if isinstance(value, ast.Name) and self.modalias.get(value.id) == 'sys' and node.attr == 'argv':
            return node, ('list', STR)
        v, vt = self.exv(value)
        node.value = v
        vt = unopt(vt)
        if isinstance(vt, tuple) and vt[0] == 'cls':
            return node, self.classes.get(vt[1], {}).get(node.attr)
        return node, None

    def leaf_nodes(self, node, t):
        """The scalar leaves of a tuple-typed pure expression, as (node, type)."""
        out = []
        for i, e in enumerate(deep(t)[1]):
            sub_ = attr(fresh_copy(node), fld(e, i))
            if is_tuple(e):
                out.extend(self.leaf_nodes(sub_, e))
            else:
                out.append((sub_, deep(e)))
        return out

    def ex_Tuple(self, node, want=None, ctx=None):
        elts = node.elts
        if any(isinstance(e, ast.Starred) for e in elts):
            self.refuse(node, 'a starred element in a tuple display')
        w = deep(want)
        wants = list(w[1]) if is_tuple(w) and len(w[1]) == len(elts) else [None] * len(elts)
        new, ts = [], []
        for e, we in zip(elts, wants):
            ne, te = self.exv(e, we, 'row' if ctx == 'row' else None)
            ne, te = self.coerce(ne, te, we)
            new.append(ne)
            ts.append(te)
        if ctx in ('key', 'fmt', 'swap', 'rawkey'):
            out = []
            for ne, te in zip(new, ts):
                if is_tuple(te):
                    if ctx == 'fmt':
                        self.refuse(node, 'a tuple inside the tuple of a % format (%s of a tuple)')
                    if not pure(ne):
                        self.refuse(node, 'a sort key part that is a tuple must be a plain name or field '
                                    '(its fields are compared in turn)')
                    for ln, lt in self.leaf_nodes(ne, te):
                        out.append(call('int', ln) if lt == BOOL else ln)
                elif ctx == 'key' and deep(te) == BOOL:
                    out.append(call('int', ne))
                else:
                    out.append(ne)
            return ast.Tuple(elts=out, ctx=ast.Load()), ('tuple', tuple(ts))
        for i, te in enumerate(ts):
            if not known(te):
                self.refuse(node, 'cannot tell the type of element %d of this tuple (an empty list or a value '
                            'of unknown type); give it a name with an annotation' % i)
            if deep(te) == 'none':
                self.refuse(node, 'None inside a tuple is not built')
        t = ('tuple', tuple(ts))
        if ctx != 'row':
            self.force()
        return call(self.gen.tcls(t), *new), t

    def seq_type(self, ts, want_elem, node=None, where='list'):
        """The element type of a display whose element types are `ts`."""
        elem = None
        for t in ts:
            t = deep(t)
            if t is None:
                continue
            if t == 'none':
                if deep(want_elem) is None:
                    return None
                continue
            if elem is None:
                elem = t
            elif elem == INT and t == FLT:
                elem = FLT
            elif is_tuple(elem) or is_tuple(t):
                # A list / set / dict cannot hold two different tuple classes: CPython's list of
                # tuples of different shapes (the empty tuple beside a non-empty one included) is
                # not lowered here; the typed path builds it as its generic tuples instead.
                if deep(elem) != t:
                    self.refuse(node, 'a %s holding tuples of different shapes is not built; '
                                      'keep one tuple shape in the %s' % (where, where))
            elif deep(elem) != t and not ({deep(elem), t} <= {INT, FLT, BOOL}):
                return None
        if elem is None and deep(want_elem) is not None:
            elem = want_elem
        return elem

    def ex_List(self, node, want=None, ctx=None):
        w = deep(want)
        we = w[1] if isinstance(w, tuple) and w[0] == 'list' else None
        new, ts = [], []
        for e in node.elts:
            ne, te = self.exv(e, we, 'row')
            ne, te = self.coerce(ne, te, we)
            new.append(ne)
            ts.append(te)
        node.elts = new
        elem = self.seq_type(ts, we, node, 'list')
        return node, ('list', elem if elem is not None else (we if we is not None else Hole()))

    def ex_Set(self, node, want=None, ctx=None):
        w = deep(want)
        we = w[1] if isinstance(w, tuple) and w[0] == 'set' else None
        new, ts = [], []
        for e in node.elts:
            ne, te = self.exv(e, we, 'row')
            new.append(ne)
            ts.append(te)
        elem = self.seq_type(ts, we, node, 'set')
        t = ('set', elem if elem is not None else Hole())
        if is_table_set(t):
            self.force()
            tbl = self.table(t)
            return call(tbl.fn('fromlist'), ast.List(elts=new, ctx=ast.Load())), t
        node.elts = new
        return node, t

    def ex_Dict(self, node, want=None, ctx=None):
        w = deep(want)
        wk, wv = (w[1], w[2]) if isinstance(w, tuple) and w[0] == 'dict' else (None, None)
        if any(k is None for k in node.keys):
            self.refuse(node, 'a dict display with ** unpacking')
        keys, vals, kts, vts = [], [], [], []
        for k, v in zip(node.keys, node.values):
            nk, tk = self.exv(k, wk, 'row')
            nv, tv = self.exv(v, wv, 'row')
            nv, tv = self.coerce(nv, tv, wv)
            keys.append(nk)
            vals.append(nv)
            kts.append(tk)
            vts.append(tv)
        kt = self.seq_type(kts, wk, node, 'dict')
        vt = self.seq_type(vts, wv, node, 'dict')
        t = ('dict', kt if kt is not None else Hole(), vt if vt is not None else Hole())
        if is_table_dict(t):
            self.force()
            if not known(t):
                self.refuse(node, 'cannot tell the key / value type of this dict; annotate it')
            tbl = self.table(t)
            if not keys:
                return call(tbl.fn('new')), t
            pair = ('tuple', (t[1], t[2]))
            ctor = self.gen.tcls(pair)
            items = ast.List(elts=[call(ctor, k, v) for k, v in zip(keys, vals)], ctx=ast.Load())
            return call(tbl.fn('dfromlist'), items), t
        node.keys, node.values = keys, vals
        return node, t

    def is_rowconst(self, node):
        return isinstance(node, ast.Name) and node.id in self.rowconst and node.id not in self.env \
            and node.id not in self.alias

    def ex_Subscript(self, node, want=None, ctx=None):
        if self.is_rowconst(node.value) and not isinstance(node.slice, ast.Slice):
            t = self.rowconst[node.value.id]
            idx, _ = self.exv(node.slice, INT)
            self.force()
            cols = [ast.Subscript(value=name('%s__c%d' % (node.value.id, i)), slice=fresh_copy(idx), ctx=ast.Load())
                    for i in range(len(t[1]))]
            return call(self.gen.tcls(t), *cols), t
        if isinstance(node.value, ast.Subscript) and self.is_rowconst(node.value.value) \
                and not isinstance(node.value.slice, ast.Slice) and const_int(node.slice) is not None:
            t = self.rowconst[node.value.value.id]
            k = const_int(node.slice)
            if -len(t[1]) <= k < len(t[1]):
                idx, _ = self.exv(node.value.slice, INT)
                self.force()
                return ast.Subscript(value=name('%s__c%d' % (node.value.value.id, k % len(t[1]))), slice=idx,
                                     ctx=ast.Load()), t[1][k % len(t[1])]
        vn, vt = self.exv(node.value)
        vt = unopt(vt)
        sl = node.slice
        if is_tuple(vt):
            k = const_int(sl)
            if isinstance(sl, ast.Slice):
                self.refuse(node, 'a slice of a tuple')
            if k is None:
                self.refuse(node, 'a tuple is indexed with a constant (t[0]); a variable index is not built')
            n = len(vt[1])
            if not -n <= k < n:
                self.refuse(node, 'tuple index out of range')
            if not isinstance(node.value, ast.Subscript) and not self.quiet:
                self.force()
            return attr(vn, fld(vt[1][k % n], k % n)), vt[1][k % n]
        if is_table_dict(vt):
            self.force()
            kn, kt = self.exv(sl, vt[1])
            tbl = self.table(vt)
            if tbl.rows and pure(vn):
                # a row is read in place (no copy), as CPython hands out the list itself
                return ast.Subscript(value=attr(fresh_copy(vn), 'vs'), slice=call(tbl.fn('ent'), vn, kn),
                                     ctx=ast.Load()), vt[2]
            return call(tbl.fn('get'), vn, kn), vt[2]
        if isinstance(sl, ast.Slice):
            node.value = vn
            node.slice = ast.Slice(lower=self.exv(sl.lower)[0] if sl.lower else None,
                                   upper=self.exv(sl.upper)[0] if sl.upper else None,
                                   step=self.exv(sl.step)[0] if sl.step else None)
            if isinstance(vt, tuple) and vt[0] == 'list':
                return node, vt
            if vt in (STR, BYTES):
                return node, vt
            return node, None
        # A set / frozenset of tuples read out of a container that is not a table dict cannot be lowered:
        # the table class it would build never matches the plain-key dictionary (or other plain object) it is
        # read from. Refuse by name so the program is left as written and the general path keeps it boxed.
        if not is_table_dict(vt) and is_table_set(deep(self.typeof(sl))):
            self.refuse(node, 'a set / frozenset of tuples used as a dict key is not built here; build the dict '
                              'and its frozenset key as module-level names, or use a frozenset of int / str')
        wk = vt[1] if isinstance(vt, tuple) and vt[0] == 'dict' else None
        kn, kt = self.exv(sl, wk)
        node.value, node.slice = vn, kn
        if isinstance(vt, tuple):
            if vt[0] == 'list':
                return node, vt[1]
            if vt[0] == 'dict':
                return node, vt[2]
        if vt == STR:
            return node, STR
        if vt == BYTES:
            return node, INT
        return node, None

    def arith(self, op, lt, rt):
        lt, rt = deep(lt), deep(rt)
        if isinstance(op, ast.Div):
            return FLT if lt in NUMERIC and rt in NUMERIC else None
        if isinstance(op, ast.Mod) and lt == STR:
            return STR
        if lt in NUMERIC and rt in NUMERIC:
            if FLT in (lt, rt):
                return FLT
            if isinstance(op, ast.Pow):
                return INT
            return INT
        if isinstance(op, ast.Add):
            if lt == rt and (lt in (STR, BYTES) or (isinstance(lt, tuple) and lt[0] == 'list')):
                return lt
        if isinstance(op, ast.Mult):
            for a, b in ((lt, rt), (rt, lt)):
                if b in (INT, BOOL) and (a in (STR, BYTES) or (isinstance(a, tuple) and a[0] == 'list')):
                    return a
        if isinstance(op, (ast.BitOr, ast.BitAnd, ast.Sub, ast.BitXor)) and isinstance(lt, tuple) \
                and lt[0] == 'set':
            return lt
        return None

    def ex_BinOp(self, node, want=None, ctx=None):
        if isinstance(node.op, ast.Mod):
            left, lt = self.exv(node.left)
            if deep(lt) == STR:
                right, rt = self.ex(node.right, None, 'fmt')
                node.left, node.right = left, right
                if is_tuple(rt) and not isinstance(node.right, ast.Tuple):
                    self.refuse(node, 'a tuple-valued name as the right side of a % format; unpack it into the '
                                'format (fmt % (t[0], t[1]))')
                return node, STR
            right, rt = self.exv(node.right)
        else:
            left, lt = self.exv(node.left)
            right, rt = self.exv(node.right)
        lt, rt = deep(lt), deep(rt)
        if (is_table_set(lt) or is_table_set(rt)) and isinstance(node.op, (ast.BitOr, ast.BitAnd, ast.Sub, ast.BitXor)):
            if not (is_table_set(lt) and is_table_set(rt) and code(lt) == code(rt)):
                self.refuse(node, 'a set operator on sets of different element types')
            self.force()
            op = {ast.BitOr: 'union', ast.BitAnd: 'inter', ast.Sub: 'diff', ast.BitXor: 'symdiff'}[type(node.op)]
            return call(self.table(lt).fn(op), left, right), lt
        if is_tuple(lt) or is_tuple(rt):
            self.refuse(node, 'tuple concatenation or repetition (a + b, t * n) is not built; build the new tuple '
                        'from the fields')
        node.left, node.right = left, right
        return node, self.arith(node.op, lt, rt)

    def ex_UnaryOp(self, node, want=None, ctx=None):
        if isinstance(node.op, ast.Not):
            node.operand = self.test(node.operand)
            return node, BOOL
        n, t = self.exv(node.operand)
        node.operand = n
        t = deep(t)
        return node, (INT if t == BOOL else t)

    def ex_BoolOp(self, node, want=None, ctx=None):
        vals, ts = [], []
        for i, v in enumerate(node.values):
            self.nohoist += i > 0
            try:
                n, t = self.exv(v, want)
            finally:
                self.nohoist -= i > 0
            if is_table(t):
                n = ast.Compare(left=attr(n, 'n'), ops=[ast.Gt()], comparators=[const(0)])
                t = BOOL
            elif is_tuple(t):
                self.refuse(node, 'the truth value of a tuple (it is true whenever it is non-empty)')
            vals.append(n)
            ts.append(deep(t))
        node.values = vals
        known_ = [t for t in ts if t is not None]
        return node, (BOOL if all(t == BOOL for t in known_) and known_ else (known_[0] if known_ else None))

    def ex_IfExp(self, node, want=None, ctx=None):
        node.test = self.test(node.test)
        self.nohoist += 1
        try:
            body, bt = self.exv(node.body, want)
            other, ot = self.exv(node.orelse, want)
        finally:
            self.nohoist -= 1
        node.body, node.orelse = body, other
        t = deep(bt)
        if t is None or t == 'none':
            t = deep(ot)
        elif deep(ot) == FLT and t == INT:
            t = FLT
        if is_tuple(t) and not ctx == 'key':
            self.force()
            if ctx not in ('rawkey', 'fmt'):
                # the compiler has no conditional class value: an if / else statement fills a temporary
                if self.nohoist:
                    self.refuse(node, 'a conditional expression whose value is a tuple inside a condition, a lambda '
                                'or a comprehension; use an if / else statement')
                tmp = self.fresh()
                self.env[tmp] = t
                tgt = ast.Name(id=tmp, ctx=ast.Store())
                self.pre.append(ast.If(test=node.test, body=[ast.Assign(targets=[tgt], value=node.body, lineno=0)],
                                       orelse=[ast.Assign(targets=[ast.Name(id=tmp, ctx=ast.Store())],
                                                          value=node.orelse, lineno=0)]))
                return name(tmp), t
        return node, t

    def ex_Starred(self, node, want=None, ctx=None):
        node.value, _ = self.exv(node.value)
        return node, None

    def ex_Slice(self, node, want=None, ctx=None):
        for f in ('lower', 'upper', 'step'):
            v = getattr(node, f)
            if v is not None:
                setattr(node, f, self.exv(v)[0])
        return node, None

    def ex_JoinedStr(self, node, want=None, ctx=None):
        values = []
        for v in node.values:
            if isinstance(v, ast.FormattedValue):
                n, t = self.exv(v.value)
                t = deep(t)
                if is_tuple(t) or (isinstance(t, tuple) and t[0] in ('list', 'opt') and has_tuple(t)):
                    if v.format_spec is not None:
                        self.refuse(node, 'a format spec on a tuple (CPython raises TypeError)')
                    self.force()
                    n = call(self.repr_fn(t), n)
                    v = ast.FormattedValue(value=n, conversion=-1, format_spec=None)
                else:
                    v = ast.FormattedValue(value=n, conversion=v.conversion,
                                           format_spec=self.ex(v.format_spec)[0] if v.format_spec else None)
            values.append(v)
        node.values = values
        return node, STR

    def ex_FormattedValue(self, node, want=None, ctx=None):
        node.value = self.exv(node.value)[0]
        return node, STR

    def repr_fn(self, t):
        t = deep(t)
        if is_tuple(t):
            return self.gen.trepr(t)
        if isinstance(t, tuple) and t[0] == 'list':
            return self.gen.lrepr(t)
        if isinstance(t, tuple) and t[0] == 'opt':
            return self.gen.orepr(t)
        raise Refused((1, 'no repr for this type'))

    # ------------------------------------------------------------------------------------------
    # comparisons
    def ex_Compare(self, node, want=None, ctx=None):
        left, lt = self.exv(node.left)
        parts = []
        operands = [(left, lt)]
        for op, comp in zip(node.ops, node.comparators):
            if isinstance(op, (ast.In, ast.NotIn)) and isinstance(comp, (ast.Tuple, ast.List, ast.Set)) \
                    and is_tuple(lt):
                right, rt = self.ex(ast.List(elts=comp.elts, ctx=ast.Load()), ('list', lt), None)
            elif isinstance(op, (ast.In, ast.NotIn)) and isinstance(comp, (ast.Tuple, ast.List, ast.Set)) \
                    and comp.elts and all(isinstance(e, ast.Constant) and isinstance(e.value, (str, int, float))
                                          for e in comp.elts):
                # `x in ("a", "b")`: a display of constants stays a display (not a tuple value)
                right, rt = comp, None
            elif isinstance(op, (ast.In, ast.NotIn)) and isinstance(comp, ast.Tuple) and comp.elts:
                # `op in ("size", "peek")` -- a tuple literal as the container is a list of its
                # elements for a membership test (the tuple type class has no `in`)
                right, rt = self.exv(ast.List(elts=comp.elts, ctx=ast.Load()))
            else:
                right, rt = self.exv(comp, lt if isinstance(op, (ast.Eq, ast.NotEq)) else None)
            parts.append((op, operands[-1], (right, rt)))
            operands.append((right, rt))
        out = []
        for op, (a, at), (b, bt) in parts:
            out.append(self.compare_one(node, op, a, deep(at), b, deep(bt)))
        if len(out) == 1:
            return out[0], BOOL
        if any(is_tuple(t) or is_table(t) for _, t in operands):
            self.refuse(node, 'a chained comparison of tuples (a < b < c); write it as two comparisons')
        return ast.BoolOp(op=ast.And(), values=out), BOOL

    def compare_one(self, node, op, a, at, b, bt):
        if isinstance(op, (ast.Is, ast.IsNot)):
            return ast.Compare(left=a, ops=[op], comparators=[b])
        if isinstance(op, (ast.In, ast.NotIn)):
            neg = isinstance(op, ast.NotIn)
            bt_ = deep(bt)
            if is_table_dict(bt_) or is_table_set(bt_):
                self.force()
                res = call(self.table(bt_).fn('has'), b, a)
            elif isinstance(bt_, tuple) and bt_[0] == 'list' and is_tuple(bt_[1]):
                self.force()
                if code(at) != code(bt_[1]):
                    self.refuse(node, 'membership of a tuple in a list of tuples of another shape')
                res = call(self.gen.list_helper('in', bt_[1]), b, a)
            elif is_tuple(bt_) and not is_tuple(at) and bt_[1]:
                # `x in t` with t a tuple value: the fields as a list (CPython compares x with
                # each in order)
                if not pure(b):
                    self.refuse(node, 'membership in a tuple expression; bind the tuple to a name '
                                'first')
                res = ast.Compare(left=a, ops=[ast.In()], comparators=[ast.List(
                    elts=[attr(fresh_copy(b), 'f%d' % i) for i in range(len(bt_[1]))],
                    ctx=ast.Load())])
            else:
                return ast.Compare(left=a, ops=[op], comparators=[b])
            return ast.UnaryOp(op=ast.Not(), operand=res) if neg else res
        eqop = isinstance(op, (ast.Eq, ast.NotEq))
        if is_tuple(at) or is_tuple(bt):
            self.force()
            if not (is_tuple(at) and is_tuple(bt)) or code(at) != code(bt):
                if at == 'none' or bt == 'none':
                    return ast.Compare(left=a, ops=[op], comparators=[b])
                self.refuse(node, 'a comparison of tuples of different shapes (or of a tuple with something '
                            'else); compare field by field')
            if eqop:
                res = call(self.gen.teq(at), a, b)
                return ast.UnaryOp(op=ast.Not(), operand=res) if isinstance(op, ast.NotEq) else res
            return ast.Compare(left=call(self.gen.tcmp(at), a, b), ops=[op], comparators=[const(0)])
        if isinstance(at, tuple) and at[0] == 'list' and is_tuple(at[1]) and eqop:
            self.force()
            res = call(self.gen.list_helper('leq', at[1]), a, b)
            return ast.UnaryOp(op=ast.Not(), operand=res) if isinstance(op, ast.NotEq) else res
        if is_table_set(at) and is_table_set(bt):
            self.force()
            t = self.table(at)
            if eqop:
                res = call(t.fn('seq'), a, b)
                return ast.UnaryOp(op=ast.Not(), operand=res) if isinstance(op, ast.NotEq) else res
            fn = t.fn('subset')
            if isinstance(op, ast.LtE):
                return call(fn, a, b)
            if isinstance(op, ast.GtE):
                return call(fn, b, a)
            if isinstance(op, ast.Lt):
                return ast.BoolOp(op=ast.And(), values=[call(fn, a, b), ast.Compare(
                    left=attr(a, 'n'), ops=[ast.Lt()], comparators=[attr(fresh_copy(b), 'n')])])
            return ast.BoolOp(op=ast.And(), values=[call(fn, b, a), ast.Compare(
                left=attr(b, 'n'), ops=[ast.Lt()], comparators=[attr(fresh_copy(a), 'n')])])
        if is_table(at) or is_table(bt):
            self.refuse(node, 'comparing dicts / sets of tuples this way is not built (sets: == <= >= < >)')
        return ast.Compare(left=a, ops=[op], comparators=[b])

    # ------------------------------------------------------------------------------------------
    # lambdas and comprehensions
    def lambda_(self, node, params, ctx=None):
        """Lower a lambda whose parameters have the given types (None entries: unknown)."""
        saved_env, saved_alias = self.env, self.alias
        self.env = dict(self.env)
        self.alias = {k: v for k, v in self.alias.items() if k not in {a.arg for a in node.args.args}}
        try:
            for a, t in zip(node.args.args, list(params) + [None] * len(node.args.args)):
                self.env[a.arg] = t
            self.nohoist += 1
            try:
                body, bt = self.exv(node.body, None, ctx)
            finally:
                self.nohoist -= 1
            node.body = body
        finally:
            self.env, self.alias = saved_env, saved_alias
        return node, ('callable', tuple(params), bt)

    def ex_Lambda(self, node, want=None, ctx=None):
        self.refuse(node, 'a lambda used as a value here; a lambda is built only to be called, passed to a '
                    'function that takes a Callable, used as key=, or given to map / filter / reduce')

    def ex_ListComp(self, node, want=None, ctx=None):
        return self.comp(node, want, 'list')

    def ex_SetComp(self, node, want=None, ctx=None):
        return self.comp(node, want, 'set')

    def ex_GeneratorExp(self, node, want=None, ctx=None):
        return self.comp(node, want, 'iter')

    def ex_DictComp(self, node, want=None, ctx=None):
        return self.comp(node, want, 'dict')

    def comp(self, node, want, kind, hoist=False):
        orig = fresh_copy(node)
        saved_env, saved_alias = self.env, self.alias
        self.env, self.alias = dict(self.env), dict(self.alias)
        self.nohoist += 1
        gens = []
        iter_tuple = False
        try:
            for g in node.generators:
                if g.is_async:
                    self.refuse(node, 'an async comprehension')
                h = self.header(g.target, g.iter, True)
                tgt = h.target
                if h.unpacks or (isinstance(tgt, ast.Name) and has_tuple(self.env.get(tgt.id))):
                    iter_tuple = True
                for target, access, t in h.unpacks:
                    if not isinstance(target, ast.Name):
                        self.refuse(node, 'a comprehension target that is not a plain name')
                    self.alias[target.id] = (access, t)
                    self.env.pop(target.id, None)
                if hoist and isinstance(tgt, ast.Name) and tgt.id not in self.fresh_names:
                    fresh = self.fresh()
                    self.alias[tgt.id] = (name(fresh), self.env.get(tgt.id))
                    self.env.pop(tgt.id, None)
                    tgt = ast.Name(id=fresh, ctx=ast.Store())
                elif hoist and isinstance(tgt, ast.Tuple) and all(isinstance(e, ast.Name) for e in tgt.elts):
                    elts = []
                    for e in tgt.elts:
                        if e.id in self.fresh_names or e.id == "_":
                            elts.append(e)
                            continue
                        fresh = self.fresh()
                        self.alias[e.id] = (name(fresh), self.env.get(e.id))
                        self.env.pop(e.id, None)
                        elts.append(ast.Name(id=fresh, ctx=ast.Store()))
                    tgt = ast.Tuple(elts=elts, ctx=ast.Store())
                elif hoist and isinstance(tgt, ast.Tuple):
                    self.refuse(node, "this comprehension target")
                ifs = h.ifs + [self.test(c) for c in g.ifs]
                gens.append(ast.comprehension(target=tgt, iter=h.iter, ifs=ifs, is_async=0))
            key_n = kt = None
            if kind == 'dict':
                key_n, kt = self.exv(node.key, None, 'row')
                elt_n, et = self.exv(node.value, None, 'row')
                t = ('dict', kt, et)
            else:
                w = deep(want)
                we = w[1] if isinstance(w, tuple) and w[0] in ('list', 'set', 'iter') else None
                elt_n, et = self.exv(node.elt, we, 'row')
                t = (kind, et if et is not None else Hole())
        finally:
            self.nohoist -= 1
            self.env, self.alias = saved_env, saved_alias
        need = has_tuple(et) or (kind == 'dict' and has_tuple(kt)) or iter_tuple
        if kind == 'dict' and is_table_dict(t) or kind == 'set' and is_table_set(t):
            need = True
        if need and not hoist:
            node2 = orig
            return self.comp(node2, want, kind, True)
        if need:
            if self.nohoist:
                self.refuse(node, 'a comprehension building tuples inside a condition, a lambda or another '
                            'comprehension; build the list in a statement first')
            self.force()
            return self.hoist_comp(kind, gens, key_n, elt_n, kt, et, t)
        if kind == 'dict':
            node.key, node.value = key_n, elt_n
        else:
            node.elt = elt_n
        node.generators = gens
        return node, t

    def hoist_comp(self, kind, gens, key_n, elt_n, kt, et, t):
        """A comprehension whose items are tuples: classes cannot be built inside comprehensions by the
        compiler, so the loops are statements and the comprehension is the list they fill."""
        tmp = self.fresh()
        if kind == 'dict':
            if not known(t):
                self.refuse(gens[0].iter, 'cannot tell the key / value type of this comprehension')
            if is_table_dict(t):
                tbl = self.table(t)
                init = ast.Assign(targets=[ast.Name(id=tmp, ctx=ast.Store())], value=call(tbl.fn('new')), lineno=0)
                step = ast.Expr(value=call(tbl.fn('set'), name(tmp), key_n, elt_n))
            else:
                self.use_type(t)
                init = ast.AnnAssign(target=ast.Name(id=tmp, ctx=ast.Store()),
                                     annotation=ast.parse(ann_text(t), mode='eval').body,
                                     value=ast.Dict(keys=[], values=[]), simple=1, lineno=0)
                step = ast.Assign(targets=[ast.Subscript(value=name(tmp), slice=key_n, ctx=ast.Store())],
                                  value=elt_n, lineno=0)
        elif kind == 'set' and is_table_set(t):
            tbl = self.table(t)
            init = ast.Assign(targets=[ast.Name(id=tmp, ctx=ast.Store())], value=call(tbl.fn('new')), lineno=0)
            step = ast.Expr(value=call(tbl.fn('add'), name(tmp), elt_n))
        else:
            t = ('list', et) if kind != 'set' else t
            if not known(t):
                self.refuse(gens[0].iter, 'cannot tell the element type of this comprehension')
            self.use_type(t)
            init = ast.AnnAssign(target=ast.Name(id=tmp, ctx=ast.Store()),
                                 annotation=ast.parse(ann_text(t), mode='eval').body,
                                 value=ast.List(elts=[], ctx=ast.Load()) if t[0] == 'list' else call('set'),
                                 simple=1, lineno=0)
            step = ast.Expr(value=call(attr(name(tmp), 'append' if t[0] == 'list' else 'add'), elt_n))
        body = [step]
        for g in reversed(gens):
            for cond in reversed(g.ifs):
                body = [ast.If(test=cond, body=body, orelse=[])]
            body = [ast.For(target=g.target, iter=g.iter, body=body, orelse=[])]
        self.pre.extend([init] + body)
        self.env[tmp] = t
        return name(tmp), t

    # ------------------------------------------------------------------------------------------
    # for / comprehension headers
    def bind_pattern(self, pat, t):
        """Give the names of a target pattern the types of the parts of t."""
        t = R(t)
        if isinstance(pat, ast.Name):
            if pat.id != '_':
                self.env[pat.id] = t
            return
        if isinstance(pat, (ast.Tuple, ast.List)):
            for i, e in enumerate(pat.elts):
                self.bind_pattern(e, t[1][i] if is_tuple(t) and len(t[1]) == len(pat.elts) else None)

    def plan(self, pat, src, t):
        """Unpacking of tuple-typed `src` (a pure expression) into the pattern: [(target, access, type)]."""
        t = deep(t)
        if not is_tuple(t):
            self.refuse(pat, 'unpacking something that is not a tuple of known shape')
        if len(pat.elts) != len(t[1]):
            self.refuse(pat, 'unpacking %d names from a tuple of %d' % (len(pat.elts), len(t[1])))
        out = []
        for i, e in enumerate(pat.elts):
            te = deep(t[1][i])
            access = attr(fresh_copy(src), fld(te, i))
            if isinstance(e, ast.Starred):
                self.refuse(pat, 'a starred name in an unpacking target')
            if isinstance(e, (ast.Tuple, ast.List)):
                out.extend(self.plan(e, access, te))
            elif isinstance(e, ast.Name) and e.id == '_':
                continue
            else:
                out.append((e, access, te))
        return out

    def is_call(self, node, fname):
        return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == fname
                and fname not in self.funcs and fname not in self.classes and fname not in self.env)

    def iter_source(self, node):
        """The iterable of a loop in value form: a table walks a snapshot list of its keys."""
        n, t = self.ex(node)
        t = R(t)
        if is_table_dict(t) or is_table_set(t):
            self.force()
            return call(self.table(t).fn('keys'), n), ('list', t[1]), n
        return n, t, n

    def header(self, target, it, in_comp):
        """Lower the header of `for target in it` (or of one comprehension generator)."""
        pre = []
        if isinstance(target, ast.List):
            target = ast.Tuple(elts=target.elts, ctx=ast.Store())
        # -- enumerate(x[, start]) ------------------------------------------------------------------
        if self.is_call(it, 'enumerate') and isinstance(target, ast.Tuple) and len(target.elts) == 2 \
                and 1 <= len(it.args) <= 2 and not it.keywords:
            src, st, _ = self.iter_source(it.args[0])
            src, st = self.realize(src, st)
            et = elem_of(st)
            ti, tp = target.elts
            args = [src] + [self.exv(a, INT)[0] for a in it.args[1:]]
            new_iter = call('enumerate', *args)
            unpacks = []
            if isinstance(ti, ast.Name):
                self.env[ti.id] = INT
            if is_tuple(et) and isinstance(tp, ast.Tuple):
                self.force()
                fresh = self.fresh()
                self.env[fresh] = et
                unpacks = self.plan(tp, name(fresh), et)
                new_target = ast.Tuple(elts=[ti, ast.Name(id=fresh, ctx=ast.Store())], ctx=ast.Store())
            else:
                self.bind_pattern(tp, et)
                new_target = ast.Tuple(elts=[ti, tp], ctx=ast.Store())
            return Header(new_iter, new_target, unpacks)
        # -- zip(a, b, ...) ----------------------------------------------------------------------------
        if self.is_call(it, 'zip') and isinstance(target, ast.Tuple) and len(target.elts) == len(it.args) \
                and not it.keywords and it.args:
            srcs, ets, kinds = [], [], []
            for a in it.args:
                n, t, _ = self.iter_source(a)
                n, t = self.realize(n, t)
                t = deep(t)
                srcs.append(n)
                ets.append(elem_of(t))
                kinds.append(t)
            need = any(has_tuple(e) for e in ets) or any(isinstance(e, ast.Tuple) for e in target.elts)
            ok = all(isinstance(k, tuple) and k[0] in ('list', 'range') or k in (STR, BYTES) for k in kinds)
            if not need or not ok:
                if need:
                    self.refuse(it, 'zip over something that is not a list or a str')
                for e, et in zip(target.elts, ets):
                    self.bind_pattern(e, et)
                it.args = srcs
                return Header(it, target)
            self.force()
            lens = []
            for i, s in enumerate(srcs):
                if not pure(s):
                    tmp = self.fresh()
                    pre.append(ast.Assign(targets=[ast.Name(id=tmp, ctx=ast.Store())], value=s, lineno=0))
                    self.env[tmp] = kinds[i]
                    s = name(tmp)
                    srcs[i] = s
                lens.append(call('len', fresh_copy(s)))
            bound = lens[0] if len(lens) == 1 else call('min', *lens)
            idx = self.fresh('zi')
            self.env[idx] = INT
            unpacks = []
            for e, s, et in zip(target.elts, srcs, ets):
                access = ast.Subscript(value=fresh_copy(s), slice=name(idx), ctx=ast.Load())
                if isinstance(e, ast.Tuple):
                    if not is_tuple(et):
                        self.refuse(it, 'unpacking an element that is not a tuple')
                    tmp = self.fresh()
                    self.env[tmp] = et
                    unpacks.append((ast.Name(id=tmp, ctx=ast.Store()), access, et))
                    unpacks.extend(self.plan(e, name(tmp), et))
                elif isinstance(e, ast.Name) and e.id == '_':
                    continue
                else:
                    unpacks.append((e, access, et))
            return Header(call('range', bound), ast.Name(id=idx, ctx=ast.Store()), unpacks, pre)
        # -- d.items() ---------------------------------------------------------------------------------
        if isinstance(it, ast.Call) and isinstance(it.func, ast.Attribute) and it.func.attr == 'items' \
                and not it.args and isinstance(target, ast.Tuple) and len(target.elts) == 2:
            recv, rt = self.exv(it.func.value)
            rt = deep(rt)
            if is_table_dict(rt):
                self.force()
                pair = ('tuple', (rt[1], rt[2]))
                fresh = self.fresh()
                self.env[fresh] = pair
                unpacks = self.plan(target, name(fresh), pair)
                return Header(call(self.table(rt).fn('items'), recv), ast.Name(id=fresh, ctx=ast.Store()), unpacks)
            if isinstance(rt, tuple) and rt[0] == 'dict':
                it.func.value = recv
                self.bind_pattern(target, ('tuple', (rt[1], rt[2])))
                return Header(it, target)
        # -- sorted(d.items(), key=...) kept for the compiler's own form ----------------------------------
        if self.is_call(it, 'sorted') and it.args and isinstance(it.args[0], ast.Call) \
                and isinstance(it.args[0].func, ast.Attribute) and it.args[0].func.attr == 'items' \
                and isinstance(target, ast.Tuple) and len(target.elts) == 2:
            recv, rt = self.exv(it.args[0].func.value)
            rt = deep(rt)
            if isinstance(rt, tuple) and rt[0] == 'dict' and not is_table_dict(rt):
                it.args[0].func.value = recv
                kws = []
                for kw in it.keywords:
                    if kw.arg == 'key' and isinstance(kw.value, ast.Lambda):
                        kw = ast.keyword(arg='key', value=self.lambda_(kw.value, [('raw',)], 'rawkey')[0])
                    else:
                        kw = ast.keyword(arg=kw.arg, value=self.exv(kw.value)[0])
                    kws.append(kw)
                it.keywords = kws
                self.bind_pattern(target, ('tuple', (rt[1], rt[2])))
                return Header(it, target)
        # -- map(f, xs) / filter(f, xs) fused into the loop ------------------------------------------------
        if self.is_call(it, 'map') and len(it.args) == 2 and not it.keywords and self.lam_involved(it.args[0]):
            src, st, _ = self.iter_source(it.args[1])
            src, st = self.realize(src, st)
            var = self.fresh('mv')
            self.env[var] = elem_of(st)
            en, ety = self.exv(self.fn_call_node(it.args[0], [name(var)], it))
            if self.lam_involved(it.args[0]):
                self.force()
            if isinstance(target, ast.Tuple):
                if not is_tuple(ety):
                    self.refuse(it, 'unpacking the result of map(...), which is not a tuple')
                t2 = self.fresh()
                self.env[t2] = ety
                unpacks = [(ast.Name(id=t2, ctx=ast.Store()), en, ety)] + self.plan(target, name(t2), ety)
            else:
                unpacks = [(target, en, ety)]
            return Header(src, ast.Name(id=var, ctx=ast.Store()), unpacks)
        if self.is_call(it, 'filter') and len(it.args) == 2 and not it.keywords and self.lam_involved(it.args[0]):
            src, st, _ = self.iter_source(it.args[1])
            src, st = self.realize(src, st)
            et = elem_of(st)
            var = target.id if isinstance(target, ast.Name) else self.fresh('mv')
            self.env[var] = et
            if isinstance(it.args[0], ast.Constant) and it.args[0].value is None:
                cond = self.test(name(var))
            else:
                cond = self.test(self.fn_call_node(it.args[0], [name(var)], it))
            if self.lam_involved(it.args[0]):
                self.force()
            unpacks = []
            if isinstance(target, ast.Tuple):
                if not is_tuple(et):
                    self.refuse(it, 'unpacking an item of filter(...) that is not a tuple')
                unpacks = self.plan(target, name(var), et)
            return Header(src, ast.Name(id=var, ctx=ast.Store()), unpacks, ifs=[cond])
        # -- a module-level list of number tuples ---------------------------------------------------------
        if self.is_rowconst(it):
            rt = self.rowconst[it.id]
            self.force()
            idx = self.fresh('zi')
            self.env[idx] = INT
            cols = [ast.Subscript(value=name('%s__c%d' % (it.id, i)), slice=name(idx), ctx=ast.Load())
                    for i in range(len(rt[1]))]
            if isinstance(target, ast.Tuple) and len(target.elts) == len(rt[1]) and all(
                    isinstance(e, ast.Name) for e in target.elts):
                unpacks = [(e, c, ty) for e, c, ty in zip(target.elts, cols, rt[1]) if e.id != '_']
            elif isinstance(target, ast.Name):
                unpacks = [(target, call(self.gen.tcls(rt), *cols), rt)]
            else:
                self.refuse(it, 'this loop target over a constant list of tuples')
            return Header(call('range', call('len', name(it.id + '__c0'))), ast.Name(id=idx, ctx=ast.Store()),
                          unpacks)
        # -- general -----------------------------------------------------------------------------------
        src, st, orig = self.iter_source(it)
        src, st = self.realize(src, st)
        st = R(st)
        et = elem_of(st)
        if is_tuple(st):
            self.refuse(it, 'iterating over a tuple')
        if isinstance(target, ast.Tuple):
            if is_tuple(et):
                self.force()
                fresh = self.fresh()
                self.env[fresh] = et
                unpacks = self.plan(target, name(fresh), et)
                return Header(src, ast.Name(id=fresh, ctx=ast.Store()), unpacks)
            self.bind_pattern(target, et)
            return Header(src, target)
        if isinstance(target, ast.Name):
            self.env[target.id] = et
            if is_tuple(et):
                pass
        return Header(src, target)
