"""Functions as values on the general path (pyboxed2.py): closures with cells, lambdas, calls through a value.

A nested `def` whose name is used other than as the function of a call (returned, stored, passed,
assigned), a `def` written inside a loop or an `if`, and a lambda outside the key=/map()/filter()
positions the emitter reads directly, are FUNC objects (`ail_funcobj`, the runtime's own shape). Its
`cells` array holds, after a tag word (`cells[0]`: the arity range), one CELL object
(`ail_cellobj`) per name it shares with the function that defines it, then the values of its
defaults, evaluated when the `def` or `lambda` runs, as CPython does.

A name shared with such a function lives in a cell for the whole activation of the function that
binds it: the frame slot holds the cell, every read and write of the name goes through the cell's
`val`, so a `nonlocal` write inside the closure is seen by the enclosing function and the closure sees
the current value of the name, also after the enclosing function has returned (CPython's late binding:
`[lambda: i for i in range(3)]` gives three functions that all return 2). Which names need a cell is
found while compiling: the first compile of a function that meets a closure over a plain local raises
`NeedCells`, and `pyboxed2.build` compiles the program again with that name in a cell from the start.

A call whose function is not a name the emitter knows (a local holding a function, `fs[i](x)`,
`make()()`) goes through `ail__callv`, which checks the arity against the tag word and raises
CPython's TypeError otherwise. The calling convention of the adapter (`ail_cfunc1`) is the runtime's:
a function of one parameter receives its argument directly (so a FUNC value also serves as a sort
key), any other receives a tuple of the arguments (UNBOUND stands for "no argument" when a
one-parameter function with a default is called with none).
"""
import ast

TAG = 0x41494C          # "AIL": cells[0] = (TAG << 32) | (lo << 16) | hi


def _c_name(qual, params):
    """The C string for `_fo->name`: the qualified name, then each parameter after a \\x01."""
    text = qual + ''.join('\x01' + p for p in params)
    return ''.join(ch if ch.isalnum() or ch in '_.<>' else '\\001' if ch == '\x01' else '_' for ch in text)


class NeedCells(Exception):
    """A closure captures `names`, which `fname` keeps in plain frame slots: compile again."""

    def __init__(self, fname, names):
        super().__init__(fname, names)
        self.fname = fname
        self.names = set(names)


def bound_names(fn):
    """Names a def or lambda binds itself (parameters, assignments, loop and comprehension targets,
    nested def names), without the names it declares nonlocal or global."""
    out = set()
    args = fn.args
    for a in args.posonlyargs + args.args + args.kwonlyargs:
        out.add(a.arg)
    if args.vararg:
        out.add(args.vararg.arg)
    if args.kwarg:
        out.add(args.kwarg.arg)
    declared = set()
    body = fn.body if isinstance(fn, ast.FunctionDef) else [ast.Expr(value=fn.body)]

    def walk(n):
        if isinstance(n, (ast.Nonlocal, ast.Global)):
            declared.update(n.names)
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            out.add(n.id)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            out.add(n.name)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                out.add((a.asname or a.name).split('.')[0])
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            out.add(n.name)
            return
        if isinstance(n, ast.Lambda):
            return
        for c in ast.iter_child_nodes(n):
            walk(c)
    for s in body:
        walk(s)
    return out - declared, declared


def free_names(fn):
    """Names `fn` refers to that it does not bind, including those of the functions nested in it,
    in first-appearance order; the names it declares nonlocal are free too."""
    own, declared = bound_names(fn)
    nonlocal_names = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Nonlocal):
            nonlocal_names.update(n.names)
    globals_ = declared - nonlocal_names
    order = []

    def add(name):
        if name not in own and name not in globals_ and name not in order:
            order.append(name)

    body = fn.body if isinstance(fn, ast.FunctionDef) else [fn.body]
    for d in fn.args.defaults + [d for d in fn.args.kw_defaults if d is not None]:
        pass        # defaults are evaluated by the enclosing function
    for nm in sorted(nonlocal_names):
        add(nm)

    def walk(n, hidden):
        if isinstance(n, ast.Name):
            if isinstance(n.ctx, ast.Load) and n.id not in hidden:
                add(n.id)
            return
        if isinstance(n, (ast.FunctionDef, ast.Lambda)):
            for d in n.args.defaults + [d for d in n.args.kw_defaults if d is not None]:
                walk(d, hidden)
            for name in free_names(n):
                if name not in hidden:
                    add(name)
            return
        if isinstance(n, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            inner = set(hidden)
            for k, g in enumerate(n.generators):
                walk(g.iter, inner if k else hidden)
                inner |= {t.id for t in ast.walk(g.target) if isinstance(t, ast.Name)}
                for c in g.ifs:
                    walk(c, inner)
            if isinstance(n, ast.DictComp):
                walk(n.key, inner)
                walk(n.value, inner)
            else:
                walk(n.elt, inner)
            return
        if isinstance(n, ast.ClassDef):
            return
        for c in ast.iter_child_nodes(n):
            walk(c, hidden)
    for s in body:
        walk(s, set())
    return order


def escaping_defs(body):
    """The defs of `body` (a function body) that are values: written inside a compound statement,
    or named anywhere other than as the function of a call. The others are compiled in place."""
    direct = {id(s) for s in body if isinstance(s, ast.FunctionDef)}
    defs = []

    def collect(stmts):
        for s in stmts:
            if isinstance(s, ast.FunctionDef):
                defs.append(s)
                continue
            if isinstance(s, ast.ClassDef):
                continue
            for field in ('body', 'orelse', 'finalbody'):
                collect(getattr(s, field, []) or [])
            for h in getattr(s, 'handlers', []) or []:
                collect(h.body)
            for c in getattr(s, 'cases', []) or []:
                collect(c.body)
    collect(body)
    names = {d.name for d in defs}
    counts = {}
    for d in defs:
        counts[d.name] = counts.get(d.name, 0) + 1
    escaping = set()
    for d in defs:
        if id(d) not in direct or counts[d.name] > 1:
            escaping.add(d.name)
    module = ast.Module(body=list(body), type_ignores=[])
    parents = {}
    for p in ast.walk(module):
        for c in ast.iter_child_nodes(p):
            parents[id(c)] = p
    for n in ast.walk(module):
        if isinstance(n, ast.Name) and n.id in names:
            p = parents.get(id(n))
            if isinstance(n.ctx, ast.Load) and isinstance(p, ast.Call) and p.func is n:
                continue
            escaping.add(n.id)
        elif isinstance(n, (ast.Nonlocal, ast.Global)) and set(n.names) & names:
            escaping.update(set(n.names) & names)
    return escaping


class ClosureMixin:
    cell_hints = {}

    # -- cells of the current activation --------------------------------------------------------------
    def cell_preamble(self, ctx):
        """C lines that put each cell variable of `ctx` into a fresh cell (its current slot value,
        a parameter or UNBOUND, becomes the cell's value)."""
        lines = []
        for name in sorted(ctx.cell_slots):
            if name not in ctx.slot_of:
                ctx.declare_local(name)
            slot = ctx.slot_expr(ctx.slot_of[name])
            lines.append('    { ail_cellobj *_c = (ail_cellobj *)ail_gc_alloc(cx, AIL_K_CELL, sizeof(ail_cellobj)); '
                         '_c->val = %s; %s.tag = AIL_T_CELL; %s.o = (ail_gcobj *)_c; }' % (slot, slot, slot))
        return lines

    def init_cells(self, ctx):
        ctx.cell_slots = set(self.cell_hints.get(ctx.fname, ()))
        for name in ctx.cell_slots:
            if name not in ctx.slot_of:
                ctx.declare_local(name)

    def cell_object(self, name, ctx):
        """The CELL ail_obj that holds `name` in `ctx` (to hand to a closure)."""
        if name in ctx.clo_index:
            return 'clo[%d]' % ctx.clo_index[name]
        return ctx.slot_expr(ctx.slot_of[name])

    # -- making a function value ----------------------------------------------------------------------
    def closure_value(self, node, ctx, name=None):
        """The C expression (a frame slot) of a new FUNC object for the def or lambda `node`."""
        from pyfront import Unsupported
        a = node.args
        if a.vararg or a.kwarg or a.kwonlyargs or a.posonlyargs:
            raise Unsupported('a function value with *args, **kwargs or keyword-only parameters')
        if any(isinstance(n, (ast.Yield, ast.YieldFrom, ast.Await)) for n in ast.walk(node)):
            raise Unsupported('yield (generator functions are not modelled by the general path)')
        if isinstance(node, ast.FunctionDef) and node.decorator_list:
            raise Unsupported('a decorator on a nested def that is used as a value (%s)' % node.name)
        label = name or 'lambda'
        qual = (ctx.qualname + '.<locals>.' if ctx.qualname else '') + (name or '<lambda>')
        captured, missing = [], []
        for nm in free_names(node):
            if nm in ctx.clo_index or nm in ctx.cell_slots:
                captured.append(nm)
            elif nm in ctx.ptr_names:
                raise Unsupported('a function value that captures %r, which %s itself shares by '
                                  'nonlocal with its enclosing function' % (nm, ctx.fname))
            elif nm in ctx.slot_of and not self._is_global_name(nm, ctx):
                missing.append(nm)
        if missing:
            raise NeedCells(ctx.fname, missing)
        params = [x.arg for x in a.args]
        nd = len(a.defaults)
        lo, hi = len(params) - nd, len(params)
        default_cs = []
        for d in a.defaults:
            v = self.expr(d, ctx)
            t = ctx.tmp()
            ctx.emit('%s = %s;' % (t, v))
            default_cs.append(t)
        self.closure_n = getattr(self, 'closure_n', 0) + 1
        cname = 'pc_%d_%s' % (self.closure_n, ''.join(ch if ch.isalnum() else '_' for ch in label))
        self._emit_closure_function(node, cname, captured, params, nd, qual)
        cells = ['ail_box_int((int64_t)((0x%XLL << 32) | (%dLL << 16) | %dLL))' % (TAG, lo, hi)]
        cells += [self.cell_object(nm, ctx) for nm in captured]
        cells += default_cs
        t = ctx.tmp()
        ctx.emit('{ ail_funcobj *_fo = (ail_funcobj *)ail_gc_alloc(cx, AIL_K_FUNC, sizeof(ail_funcobj)); '
                 '_fo->fn = %s_v; _fo->n_cells = 0; _fo->name = "%s";%s '
                 '_fo->cells = (ail_obj *)ail_xmalloc(%d * sizeof(ail_obj)); %s _fo->n_cells = %d; '
                 '%s.tag = AIL_T_FUNC; %s.o = (ail_gcobj *)_fo; }'
                 % (cname, _c_name(qual, params),
                    ' _fo->builtin_fn = 1;' if getattr(node, '_ail_builtin_fn', False) else '',
                    len(cells), ' '.join('_fo->cells[%d] = %s;' % (i, c) for i, c in enumerate(cells)),
                    len(cells), t, t))
        return t

    def _emit_closure_function(self, node, cname, captured, params, nd, qual):
        import pyboxed2
        from pyfront import Unsupported
        cid = pyboxed2.cid
        cctx = pyboxed2.Ctx(cname)
        cctx.qualname = qual
        cctx.clo_index = {nm: i + 1 for i, nm in enumerate(captured)}
        nonlocal_names = set()
        for n in ast.walk(node):
            if isinstance(n, ast.Nonlocal):
                nonlocal_names.update(n.names)
            if isinstance(n, ast.Global):
                cctx.global_decls.update(n.names)
        for p in params:
            cctx.declare_local(p)
        body = node.body if isinstance(node, ast.FunctionDef) else None
        if body is not None:
            locals_ = (pyboxed2._scan_assigned_names(body) - set(params) - nonlocal_names
                       - cctx.global_decls - set(captured))
            for nm in sorted(locals_):
                cctx.declare_local(nm)
            escaping = escaping_defs(body)
            cctx.closure_defs = escaping
            for nm in escaping:
                cctx.declare_local(nm)
            for n in body:
                if isinstance(n, ast.FunctionDef) and n.name not in escaping:
                    self._register_nested(n, cctx)
        self.init_cells(cctx)
        if body is not None:
            self.block(body, cctx)
        else:
            v = self.expr(node.body, cctx)
            cctx.emit('*out = %s;' % v)
        pre = ['    f.slots[%d] = %s;' % (cctx.slot_of[p], cid(p)) for p in params]
        pre += self.cell_preamble(cctx)
        n_slots = max(cctx.next_slot, 1)
        sig = ''.join(', ail_obj %s' % cid(p) for p in params)
        self.top_decls.append('static ail_st %s(ail_ctx *cx, ail_obj *out, ail_obj *clo%s);\n' % (cname, sig))
        self.top_decls.append('static ail_st %s_v(ail_ctx *cx, ail_obj *out, ail_obj arg, void *closure);\n' % cname)
        self.top_defs.append(
            'static ail_st %s(ail_ctx *cx, ail_obj *out, ail_obj *clo%s) {\n'
            '    AIL_FRAME_ENTER(cx, f, %d);\n'
            '    ail_st st = AIL_OK; (void)st; (void)clo;\n'
            '    ail_completion comp = AIL_COMPLETE_NORMAL; (void)comp;\n'
            '    *out = ail_box_none();\n%s\n%s\n'
            '    AIL_FRAME_LEAVE(cx, f);\n    return AIL_OK;\n'
            'L_leave:\n'
            '    AIL_FRAME_LEAVE(cx, f);\n    return st;\n'
            '}\n\n' % (cname, sig, n_slots, '\n'.join(pre), cctx.body_text()))
        # the adapter: the runtime's one-argument calling convention
        k = len(captured)
        n = len(params)
        lines = ['    ail_obj *clo = (ail_obj *)closure;']
        if n:
            lines.append('    ail_obj a[%d];' % n)
        if n == 1:
            if nd:
                lines.append('    a[0] = arg.tag == AIL_T_UNBOUND ? clo[%d] : arg;' % (1 + k))
            else:
                lines.append('    a[0] = arg;')
        elif n:
            lines.append('    ail_vecobj *v = (ail_vecobj *)arg.o;')
            lines.append('    for (int64_t i = 0; i < %d; i++) a[i] = i < v->n ? v->p[i] : clo[%d + i - %d];'
                         % (n, 1 + k, n - nd))
        else:
            lines.append('    (void)arg;')
        lines.append('    return %s(cx, out, clo%s);' % (cname, ''.join(', a[%d]' % i for i in range(n))))
        self.top_defs.append('static ail_st %s_v(ail_ctx *cx, ail_obj *out, ail_obj arg, void *closure) {\n%s\n}\n\n'
                             % (cname, '\n'.join(lines)))

    def function_value(self, name, ctx):
        """A FUNC object for the top-level function `name` (plain positional parameters only)."""
        from pyfront import Unsupported
        if getattr(self, 'uplan', None) is not None:
            import unified
            unified.boxed_body_hook(self, name)
        info = self.functions[name]
        if info.get('vararg') or info.get('kwarg') or info.get('kwonly') or info.get('defaults') \
                or info.get('is_method'):
            raise Unsupported('using function %s as a first-class value (it has defaults, *args or '
                              '**kwargs)' % name)
        n = len(info['params'])
        adapter = 'pfv_%s' % info['cname']
        if adapter not in getattr(self, 'value_adapters', set()):
            self.value_adapters = getattr(self, 'value_adapters', set()) | {adapter}
            if n == 1:
                call = '%s(cx, out, arg)' % info['cname']
                pre = ''
            elif n == 0:
                call = '%s(cx, out)' % info['cname']
                pre = '(void)arg; '
            else:
                pre = 'ail_vecobj *v = (ail_vecobj *)arg.o; '
                call = '%s(cx, out%s)' % (info['cname'], ''.join(', v->p[%d]' % i for i in range(n)))
            self.top_decls.append('static ail_st %s(ail_ctx *cx, ail_obj *out, ail_obj arg, void *closure);\n' % adapter)
            self.top_defs.append('static ail_st %s(ail_ctx *cx, ail_obj *out, ail_obj arg, void *closure) {\n'
                                 '    (void)closure; %sreturn %s;\n}\n\n' % (adapter, pre, call))
        t = ctx.tmp()
        ctx.emit('{ ail_funcobj *_fo = (ail_funcobj *)ail_gc_alloc(cx, AIL_K_FUNC, sizeof(ail_funcobj)); '
                 '_fo->fn = %s; _fo->n_cells = 0; _fo->name = "%s"; '
                 '_fo->cells = (ail_obj *)ail_xmalloc(sizeof(ail_obj)); '
                 '_fo->cells[0] = ail_box_int((int64_t)((0x%XLL << 32) | (%dLL << 16) | %dLL)); _fo->n_cells = 1; '
                 '%s.tag = AIL_T_FUNC; %s.o = (ail_gcobj *)_fo; }' % (adapter, _c_name(name, info['params']),
                                                                     TAG, n, n, t, t))
        return t

    # -- calling a value --------------------------------------------------------------------------------
    def call_value(self, func_c, args, kwargs, ctx):
        from pyfront import Unsupported
        if kwargs:
            raise Unsupported('keyword arguments in a call through a function value')
        if any(isinstance(x, ast.Starred) for x in args):
            raise Unsupported('a starred argument in a call through a function value')
        fv = ctx.tmp()
        ctx.emit('%s = %s;' % (fv, func_c))
        argcs = [self.expr(x, ctx) for x in args]
        slots = [ctx.tmp() for _ in argcs]
        for s, c in zip(slots, argcs):
            ctx.emit('%s = %s;' % (s, c))
        self._need_callv()
        t = ctx.tmp()
        classes = getattr(self, 'class_values', ())
        if classes:
            from pyboxed2 import _PreC
            # a class held in a variable: construct it, as calling the class by name does
            ctx.emit('if (%s.tag == AIL_T_CLASS) {' % fv)
            ctx.indent += 1
            first = True
            for cname in classes:
                ctx.emit('%sif (%s.o == g_slots_arr[%d].o) {' % ('' if first else '} else ', fv,
                                                                  self.global_slots['class:' + cname]))
                first = False
                ctx.indent += 1
                mark = len(ctx.lines)
                try:
                    r = self._call_class(cname, [_PreC(x) for x in slots], {}, ctx)
                    ctx.emit('%s = %s;' % (t, r))
                except Unsupported:
                    del ctx.lines[mark:]
                    ctx.emit('st = ail_raise_c(cx, AIL_B_TYPEERROR, "%s() takes other arguments"); goto %s;'
                             % (cname, ctx.cur_err_target()))
                    ctx.uses_st = True
                ctx.indent -= 1
            ctx.emit('} else {')
            ctx.indent += 1
            ctx.emit('st = ail__callv(cx, &%s, %s, %s, %d);' % (t, fv, ('&' + slots[0]) if slots else 'NULL', len(slots)))
            ctx.check()
            ctx.indent -= 1
            ctx.emit('}')
            ctx.indent -= 1
            ctx.emit('} else {')
            ctx.indent += 1
            ctx.emit('st = ail__callv(cx, &%s, %s, %s, %d);' % (t, fv, ('&' + slots[0]) if slots else 'NULL', len(slots)))
            ctx.check()
            ctx.indent -= 1
            ctx.emit('}')
            return t
        ctx.emit('st = ail__callv(cx, &%s, %s, %s, %d);' % (t, fv, ('&' + slots[0]) if slots else 'NULL', len(slots)))
        ctx.check()
        return t

    def _need_callv(self):
        if getattr(self, 'has_callv', False):
            return
        self.has_callv = True
        self.top_decls.append(
            'static ail_st ail__callv(ail_ctx *cx, ail_obj *out, ail_obj fv, ail_obj *args, int64_t n) {\n'
            '    char msg[200];\n'
            '    if (fv.tag != AIL_T_FUNC) {\n'
            '        snprintf(msg, sizeof msg, "\'%%s\' object is not callable", ail_type_name(fv.tag));\n'
            '        return ail_raise_c(cx, AIL_B_TYPEERROR, msg);\n'
            '    }\n'
            '    ail_funcobj *f = (ail_funcobj *)fv.o;\n'
            '    int64_t lo = 1, hi = 1;\n'
            '    if (f->n_cells > 0 && f->cells[0].tag == AIL_T_INT && (f->cells[0].i >> 32) == 0x%XLL) {\n'
            '        lo = (f->cells[0].i >> 16) & 0xffff; hi = f->cells[0].i & 0xffff;\n'
            '    }\n'
            '    int nl = 0;\n'
            '    while (f->name[nl] && f->name[nl] != 1) nl++;\n'
            '    if (n > hi) {\n'
            '        if (lo < hi)\n'
            '            snprintf(msg, sizeof msg, "%%.*s() takes from %%lld to %%lld positional arguments but %%lld %%s given",\n'
            '                     nl, f->name, (long long)lo, (long long)hi, (long long)n, n == 1 ? "was" : "were");\n'
            '        else\n'
            '            snprintf(msg, sizeof msg, "%%.*s() takes %%lld positional argument%%s but %%lld %%s given", nl, f->name,\n'
            '                     (long long)hi, hi == 1 ? "" : "s", (long long)n, n == 1 ? "was" : "were");\n'
            '        return ail_raise_c(cx, AIL_B_TYPEERROR, msg);\n'
            '    }\n'
            '    if (n < lo) {\n'
            '        /* CPython names the missing parameters: \'a\', \'b\' and \'c\' */\n'
            '        const char *p = f->name + nl; int64_t k = 0;\n'
            '        int len = snprintf(msg, sizeof msg, "%%.*s() missing %%lld required positional argument%%s: ",\n'
            '                           nl, f->name, (long long)(lo - n), lo - n == 1 ? "" : "s");\n'
            '        while (*p == 1) {\n'
            '            const char *q = ++p; while (*p && *p != 1) p++;\n'
            '            if (k >= n && k < lo && len < (int)sizeof msg) {\n'
            '                int64_t left = lo - k - 1;\n'
            '                len += snprintf(msg + len, sizeof msg - len, "\'%%.*s\'%%s", (int)(p - q), q,\n'
            '                                left == 0 ? "" : left == 1 ? (lo - n > 2 ? ", and " : " and ") : ", ");\n'
            '            }\n'
            '            k++;\n'
            '        }\n'
            '        return ail_raise_c(cx, AIL_B_TYPEERROR, msg);\n'
            '    }\n'
            '    if (hi == 1) return f->fn(cx, out, n == 1 ? args[0] : ail_box_unbound(), f->cells);\n'
            '    return f->fn(cx, out, ail_tuple_new(cx, args, n), f->cells);\n'
            '}\n' % TAG)
