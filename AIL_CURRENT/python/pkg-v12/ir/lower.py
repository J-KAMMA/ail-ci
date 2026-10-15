"""Lowering of the S0 subset: one function's Python AST (as the legacy front end leaves it, after
its own AST passes) -> an IR function.

S0 subset (design §4.2 S0; anything else raises NotS0 and the function stays on the legacy
emitter):
  * parameters and locals of kind int or float (bool locals are ints, as in the legacy path),
    result int, float or none;
  * statements: assignment / augmented assignment / annotated assignment to a name, `if`,
    `while`, `for <name> in range(...)` (1-3 arguments), `break`, `continue`, `return`, `pass`,
    expression statements, docstrings;
  * expressions: int/float/bool constants, names (locals, parameters, int/float module
    constants), + - * / // % ** & | ^ << >> ~, unary - + not, comparisons (chained), and/or,
    conditional expressions, calls to compiled functions whose parameters are int/float, and the
    builtins abs, min/max (two arguments), int(), float(), ord('<one character>').

Types and the C representation of every value follow the legacy path's own decisions (its
`ctx.types` / `ctx.params` / `_etype`), so both paths agree on every int/float distinction;
lowering cross-checks its own type of every source expression against `_etype` and refuses on
any disagreement. Overflow checks the legacy range analysis (rangecheck.py) proved unnecessary
lower with mode `nsw`; every other int + - * is `ck`. Clone dispatch (monomorphised callees,
SEMANTICS.md section 26) uses the legacy plan.

Locals are `local.alloc` places (S0 has no mem2reg; the C compiler promotes them, as it does
the legacy path's locals). A parameter that is never assigned stays an SSA value.
"""
import ast
import os

from . import ir as I
from . import effects as E

BYTES = I.T('bytes')
BYTEARRAY = I.T('obj', I.T('bytearray'))


class NotS0(Exception):
    """The function is outside the S0 subset; the message says why."""


class _Builder(object):
    def __init__(self):
        self.region = None

    def emit(self, op, operands=(), types=(), attrs=None, regions=()):
        ins = I.Instr(op, operands, [I.Value(t) for t in types], attrs, regions)
        self.region.instrs.append(ins)
        return ins

    def value(self, op, operands, t, attrs=None, regions=()):
        return self.emit(op, operands, [t], attrs, regions).result

    def terminated(self):
        return bool(self.region.instrs) and I.OPS.get(self.region.instrs[-1].op, (0, 0, 0, False))[3]


def _linkage(sig):
    if sig.startswith('__attribute__((always_inline)) static inline\n'):
        return 'inline_always'
    if sig.startswith('static\n'):
        return 'static'
    return 'extern'


class Lowering(object):
    def __init__(self, P, fn, ctx, sig, recursive, cname):
        """`P` is the legacy compiler module (pyfunc), `ctx` its finished Ctx for this function,
        `sig` the legacy C signature text (linkage and inlining decisions are kept as they are)."""
        self.P = P
        self.fn = fn
        self.ctx = ctx
        self.recursive = recursive
        self.cname = cname
        self.strict = ctx.need is not None
        self.b = _Builder()
        self.program = I.Program()
        self.places = {}
        self.params = {}
        self.proofs = None
        self.linkage = _linkage(sig)

    # ------------------------------------------------------------------ kinds and types
    def kind_type(self, kind, what, views=False):
        """The IR type of a legacy kind. : read-only views (bytes) are allowed -- for
        parameters and call arguments, which the callee borrows."""
        P = self.P
        if kind == P.INT:
            return I.I64
        if kind == P.FLT:
            return I.F64
        if views and kind == P.BYTES:
            return BYTES
        if views and kind == 'bytearray':
            return I.T('obj', I.T('bytearray'))
        if views and kind == 'array':
            return I.T('span', I.I64)
        if views and kind == P.FLIST:
            return I.T('span', I.F64)
        if views and isinstance(kind, tuple) and len(kind) == 2 and kind[0] == 'obj' \
                and kind[1] in getattr(self.ctx, 'classes', {}):
            if kind[1] in (getattr(P, '_NULLABLE', None) or ()):
                raise NotS0('%s may be None (class %s is optional somewhere)' % (what, kind[1]))
            return I.T('obj', I.class_type(kind[1]))
        raise NotS0('%s has kind %r' % (what, kind))

    def check_kind(self, node, value):
        """The legacy path's type of `node` must agree with the IR type of its value."""
        try:
            kind = self.P._etype(node, self.ctx)
        except Exception as error:
            raise NotS0('no legacy type for %s: %s' % (type(node).__name__, error))
        try:
            want = self.kind_type(kind, 'expression', views=True)
        except NotS0:
            want = None
        have = I.I64 if value.type == I.I1 else value.type
        if want != have:
            raise NotS0('type disagreement at line %s: legacy %r, IR %s'
                        % (getattr(node, 'lineno', '?'), kind, value.type))

    def proven(self, node):
        """Whether rangecheck.py proved `node`'s int + - * cannot overflow (as the legacy path
        asks it: on the node the check marker would carry)."""
        if self.proofs is None and os.environ.get('AIL_IR_NO_RANGECHECK'):
            self.proofs = False           # measure the SSA range pass alone
        if self.proofs is None:
            try:
                self.proofs = self.P._range_proofs(self.ctx)
            except Exception:
                self.proofs = False
        if not self.proofs:
            return False
        return bool(self.proofs.ok_arith(getattr(node, '_ail_range_src', node)))

    def coerce(self, v, t):
        if v.type == t:
            return v
        if v.type == I.I1 and t in (I.I64, I.F64):
            v = self.b.value('zext', [v], I.I64)
            return self.coerce(v, t)
        if v.type == I.I64 and t == I.F64:
            return self.b.value('sitofp', [v], I.F64)
        raise NotS0('no implicit conversion from %s to %s' % (v.type, t))

    def as_int(self, v):
        if v.type == I.F64:
            raise NotS0('a float where an int is required')
        return self.coerce(v, I.I64)

    def const(self, t, value):
        return self.b.value('const', [], t, {'value': value})

    # ------------------------------------------------------------------ entry
    def run(self):
        P, ctx, fn = self.P, self.ctx, self.fn
        a = fn.args
        if a.posonlyargs or a.kwonlyargs or a.vararg or a.kwarg:
            raise NotS0('parameter shape')
        if getattr(ctx, 'exc_frame', False) or getattr(ctx, 'par_regions', None):
            raise NotS0('try frame or parallel region')
        if P._numeric_mixed_bindings(ctx) or getattr(ctx, 'numeric_assignments', None) \
                or getattr(ctx, 'numeric_tokens', None):
            raise NotS0('int-or-float bindings')
        if getattr(ctx, 'builders', None):
            raise NotS0('builder locals')
        ret_kind = ctx.ret
        results = [] if ret_kind == P.NORET else [self.kind_type(ret_kind, 'the result')]
        param_types = [self.kind_type(k, 'parameter %r' % n, views=True) for n, k in ctx.params]
        param_names = [n for n, _ in ctx.params]
        if param_names != [p.arg for p in a.args]:
            raise NotS0('parameter list differs from the source')
        if BYTEARRAY in param_types and any(
                isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id in ctx.funcs
                for c in ast.walk(fn)):
            raise NotS0('a bytearray parameter in a function that calls user functions')
        abi = []
        for (n, k), t in zip(ctx.params, param_types):
            if k == 'array':
                for special in ('tstride', 'rowparam', 'gridparam', 'byterow', 'nlist', 'blist', 'trowsf'):
                    if n in (getattr(ctx, special, None) or ()):
                        raise NotS0('parameter %r is a %s array' % (n, special))
                abi.append('array')
            elif k == P.FLIST:
                abi.append('flist')
            else:
                abi.append('value')
        for node in ast.walk(fn):
            if isinstance(node, (ast.NamedExpr, ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef, ast.Global, ast.Nonlocal, ast.ListComp, ast.SetComp,
                                 ast.DictComp, ast.GeneratorExp, ast.Await, ast.Yield, ast.YieldFrom,
                                 ast.Try, ast.With, ast.Raise, ast.Assert, ast.Delete, ast.Starred)) \
                    and node is not fn:
                raise NotS0('%s in the body' % type(node).__name__)
        params = [I.Value(t, hint=n) for n, t in zip(param_names, param_types)]
        attrs = {'sym': self.cname, 'linkage': self.linkage}
        if any(x != 'value' for x in abi):
            attrs['abi'] = abi
        if self.recursive:
            attrs['recursive'] = True
        f = I.Function(fn.name, params, param_names, results, I.Region(), attrs)
        self.program.add(f)
        self.function = f
        self.b.region = f.body
        assigned = self.assigned_names()
        for name, value in zip(param_names, params):
            if name not in assigned:
                self.params[name] = value
        for name in sorted(assigned, key=lambda n: (n not in param_names, n)):
            if name in param_names:
                t = value_type = params[param_names.index(name)].type
                if not t.is_scalar:
                    raise NotS0('parameter %r of type %s is reassigned' % (name, t))
            else:
                kind = ctx.types.get(name)
                t = value_type = self.kind_type(kind, 'local %r' % name)
            if name in getattr(ctx, 'optional', ()) or name in getattr(ctx, 'stdin_unbound', ()):
                raise NotS0('local %r is optional or special' % name)
            self.places[name] = self.b.value('local.alloc', [], I.place(value_type), {'name': name})
        for name, value in zip(param_names, params):
            if name in self.places:
                self.b.emit('store', [self.places[name], value])
        if self.recursive:
            self.b.emit('rt', [], [], {'callee': 'ail_depth_enter'})
        self.stmts(fn.body)
        if not self.b.terminated():
            self.fallthrough()
        E.summarize_program(self.program)
        return f

    def assigned_names(self):
        out = set()
        for node in ast.walk(self.fn):
            if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
                out.add(node.id)
            elif isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.For)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for t in targets:
                    if isinstance(t, (ast.Attribute, ast.Subscript)) and not isinstance(node, ast.For):
                        continue          # a field or element store (checked where it is lowered)
                    if not isinstance(t, ast.Name):
                        raise NotS0('assignment to %s' % type(t).__name__)
        modconsts = getattr(self.ctx, 'modconsts', {})
        for name in out:
            if name in modconsts:
                raise NotS0('module constant %r rebound' % name)
        return out

    def leave(self):
        if self.recursive:
            self.b.emit('rt', [], [], {'callee': 'ail_depth_leave'})

    def fallthrough(self):
        """The legacy path's fall-off-the-end return: 0 (or nothing for a void function)."""
        self.leave()
        if self.function.results:
            t = self.function.results[0]
            self.b.emit('return', [self.const(t, 0.0 if t == I.F64 else 0)])
        else:
            self.b.emit('return', [])

    # ------------------------------------------------------------------ statements
    def stmts(self, body):
        for s in body:
            if self.b.terminated():
                return            # dead code after return/break/continue
            self.stmt(s)

    def in_region(self, region, body=None, fill=None):
        saved = self.b.region
        self.b.region = region
        try:
            if body is not None:
                self.stmts(body)
            if fill is not None:
                fill()
        finally:
            self.b.region = saved

    def store(self, name, v):
        place = self.places.get(name)
        if place is None:
            raise NotS0('store to %r' % name)
        self.b.emit('store', [place, self.coerce(v, place.type.pointee)])

    def stmt(self, s):
        if isinstance(s, ast.Assign):
            if len(s.targets) != 1:
                raise NotS0('assignment shape')
            target = s.targets[0]
            if isinstance(target, (ast.Attribute, ast.Subscript)):
                return self.store_target(target, s.value)
            if not isinstance(target, ast.Name):
                raise NotS0('assignment shape')
            self.store(target.id, self.expr(s.value))
        elif isinstance(s, ast.AnnAssign):
            if not isinstance(s.target, ast.Name):
                raise NotS0('annotated assignment shape')
            if s.value is not None:
                self.store(s.target.id, self.expr(s.value))
        elif isinstance(s, ast.AugAssign):
            if isinstance(s.target, (ast.Attribute, ast.Subscript)):
                return self.aug_target(s)
            if not isinstance(s.target, ast.Name):
                raise NotS0('augmented assignment shape')
            fake = ast.BinOp(left=ast.Name(id=s.target.id, ctx=ast.Load()), op=s.op, right=s.value)
            ast.copy_location(fake, s)
            ast.copy_location(fake.left, s.target)
            fake._ail_range_src = s
            self.store(s.target.id, self.expr(fake))
        elif isinstance(s, ast.Expr):
            if isinstance(s.value, ast.Constant) and isinstance(s.value.value, str):
                return                                        # docstring
            if isinstance(s.value, ast.Call):
                self.call(s.value, statement=True)
            else:
                self.expr(s.value)
        elif isinstance(s, ast.Pass):
            pass
        elif isinstance(s, ast.If):
            c = self.truthy(s.test)
            then, other = I.Region(), I.Region()
            self.in_region(then, s.body, self._close_yield)
            self.in_region(other, s.orelse, self._close_yield)
            self.b.emit('if', [c], [], None, [then, other])
        elif isinstance(s, ast.While):
            if s.orelse:
                raise NotS0('while ... else')
            body = I.Region()

            def loop_body():
                c = self.truthy(s.test)
                go, stop = I.Region(), I.Region()
                self.in_region(go, fill=lambda: self.b.emit('yield'))
                self.in_region(stop, fill=lambda: self.b.emit('break'))
                self.b.emit('if', [c], [], None, [go, stop])
                self.stmts(s.body)
                if not self.b.terminated():
                    self.b.emit('continue')
            self.in_region(body, fill=loop_body)
            self.b.emit('loop', [], [], None, [body])
        elif isinstance(s, ast.For):
            self.for_range(s)
        elif isinstance(s, ast.Return):
            if s.value is None:
                if self.function.results:
                    raise NotS0('bare return in a valued function')
                self.leave()
                self.b.emit('return', [])
                return
            if not self.function.results:
                raise NotS0('return with a value in a void function')
            v = self.coerce(self.expr(s.value), self.function.results[0])
            self.leave()
            self.b.emit('return', [v])
        elif isinstance(s, ast.Break):
            self.b.emit('break')
        elif isinstance(s, ast.Continue):
            self.b.emit('continue')
        else:
            raise NotS0('statement %s' % type(s).__name__)

    def _close_yield(self):
        if not self.b.terminated():
            self.b.emit('yield')

    def for_range(self, s):
        if s.orelse or getattr(s, 'par', None) is not None:
            raise NotS0('for ... else or a parallel for')
        it = s.iter
        if isinstance(s.target, ast.Name) and isinstance(it, ast.Name) and it.id in self.params \
                and self.params[it.id].type == BYTES:
            return self.for_bytes(s, self.params[it.id])
        if not (isinstance(s.target, ast.Name) and isinstance(it, ast.Call)
                and isinstance(it.func, ast.Name) and it.func.id == 'range' and not it.keywords
                and 1 <= len(it.args) <= 3 and self.is_builtin('range')):
            raise NotS0('for over something other than range()')
        args = [self.as_int(self.expr(a)) for a in it.args]
        if len(args) == 1:
            lo, hi, step = self.const(I.I64, 0), args[0], self.const(I.I64, 1)
        elif len(args) == 2:
            lo, hi, step = args[0], args[1], self.const(I.I64, 1)
        else:
            lo, hi, step = args
        index = I.Value(I.I64, hint=s.target.id)
        body = I.Region([index])

        def fill():
            self.store(s.target.id, index)
            self.stmts(s.body)
            if not self.b.terminated():
                self.b.emit('continue')
        self.in_region(body, fill=fill)
        self.b.emit('for.range', [lo, hi, step], [], {'args': len(args)}, [body])

    def for_bytes(self, s, base):
        """`for c in d` over a bytes parameter (immutable: its length is fixed) is
        `for k in range(len(d)): c = d[k]` with the read proven in range."""
        if s.target.id in self.params or s.target.id not in self.places:
            raise NotS0('for target %r' % s.target.id)
        n = self.b.value('bytes.len', [base], I.I64)
        lo, step = self.const(I.I64, 0), self.const(I.I64, 1)
        index = I.Value(I.I64, hint='k')
        body = I.Region([index])

        def fill():
            self.store(s.target.id, self.b.value('bytes.get', [base, index], I.I64, {'mode': 'nck'}))
            self.stmts(s.body)
            if not self.b.terminated():
                self.b.emit('continue')
        self.in_region(body, fill=fill)
        self.b.emit('for.range', [lo, n, step], [], {'args': 1}, [body])

    # ------------------------------------------------------------------ expressions
    def is_builtin(self, name):
        ctx = self.ctx
        return (name not in ctx.funcs and name not in getattr(ctx, 'classes', {})
                and name not in self.places and name not in self.params
                and name not in getattr(ctx, 'modconsts', {}))

    def truthy(self, node):
        v = self.expr(node)
        if not v.type.is_scalar:
            raise NotS0('truth value of %s' % v.type)
        if v.type == I.I1:
            return v
        zero = self.const(v.type, 0.0 if v.type == I.F64 else 0)
        return self.b.value('cmp.ne', [v, zero], I.I1)

    def expr(self, node):
        v = self._expr(node)
        self.check_kind(node, v)
        return v

    def _expr(self, node):
        if isinstance(node, ast.Constant):
            value = node.value
            if isinstance(value, bool):
                return self.const(I.I64, int(value))
            if isinstance(value, int):
                if not -(1 << 63) <= value < (1 << 63):
                    raise NotS0('integer literal out of range')
                return self.const(I.I64, value)
            if isinstance(value, float):
                return self.const(I.F64, value)
            raise NotS0('constant %r' % (value,))
        if isinstance(node, ast.Name):
            if node.id in self.places:
                place = self.places[node.id]
                return self.b.value('load', [place], place.type.pointee)
            if node.id in self.params:
                return self.params[node.id]
            entry = getattr(self.ctx, 'modconsts', {}).get(node.id)
            if entry is not None and entry[0] in (self.P.INT, self.P.FLT):
                value = entry[1]
                if entry[0] == self.P.INT and isinstance(value, int) and not isinstance(value, bool):
                    return self.const(I.I64, value)
                if entry[0] == self.P.FLT and isinstance(value, float):
                    return self.const(I.F64, value)
            raise NotS0('name %r' % node.id)
        if isinstance(node, ast.UnaryOp):
            return self.unary(node)
        if isinstance(node, ast.BinOp):
            return self.binop(node)
        if isinstance(node, ast.BoolOp):
            return self.boolop(node)
        if isinstance(node, ast.Compare):
            return self.compare(node)
        if isinstance(node, ast.IfExp):
            return self.ifexp(node)
        if isinstance(node, ast.Call):
            v = self.call(node)
            if v is None:
                raise NotS0('a void call used as a value')
            return v
        if isinstance(node, ast.Subscript):
            return self.subscript(node)
        if isinstance(node, ast.Attribute):
            obj, cls, kind = self.field_of(node)
            if kind not in (self.P.INT, self.P.FLT):
                raise NotS0('field %s.%s of kind %r used as a value' % (cls, node.attr, kind))
            t = I.I64 if kind == self.P.INT else I.F64
            return self.b.value('field.get', [obj], t, {'cls': cls, 'name': node.attr})
        raise NotS0('expression %s' % type(node).__name__)

    # ------------------------------------------------------------------ objects and containers (S1)
    def object_param(self, node):
        """The IR value of `node` when it names a (non-optional) struct parameter, else None."""
        if isinstance(node, ast.Name) and node.id in self.params:
            v = self.params[node.id]
            if v.type.head == 'obj' and v.type.args[0].head == 'class':
                return v
        return None

    def field_of(self, node):
        """(object value, class name, field kind) of `p.f` for a struct parameter `p`."""
        obj = self.object_param(node.value)
        if obj is None:
            raise NotS0('attribute of %s' % type(node.value).__name__)
        cls = obj.type.args[0].name
        info = getattr(self.ctx, 'classes', {}).get(cls)
        if info is None or node.attr not in info.field_types:
            raise NotS0('unknown field %s.%s' % (cls, node.attr))
        return obj, cls, info.field_types[node.attr]

    def container(self, node):
        """The IR value of a container operand: a bytes parameter, or a numeric list field of a
        struct parameter (a borrow of the field's list)."""
        if isinstance(node, ast.Name) and node.id in self.params and (
                self.params[node.id].type in (BYTES, BYTEARRAY) or self.params[node.id].type.head == 'span'):
            return self.params[node.id]
        if isinstance(node, ast.Attribute):
            obj, cls, kind = self.field_of(node)
            if kind in (self.P.LIST, self.P.FLIST):
                elem = I.I64 if kind == self.P.LIST else I.F64
                return self.b.value('field.list', [obj], I.T('obj', I.T('list', elem)),
                                    {'cls': cls, 'name': node.attr})
            raise NotS0('field %s.%s of kind %r as a container' % (cls, node.attr, kind))
        raise NotS0('container operand %s' % (ast.dump(node)[:60],))

    def is_list(self, v):
        return v.type.head == 'obj' and v.type.args[0].head == 'list'

    def store_target(self, target, value_node):
        """`p.f = v` (scalar field) or `c[i] = v` (numeric list element). Python evaluates the
        right side first, then the target's parts."""
        v = self.expr(value_node)
        if isinstance(target, ast.Attribute):
            obj, cls, kind = self.field_of(target)
            if kind not in (self.P.INT, self.P.FLT):
                raise NotS0('store to field %s.%s of kind %r' % (cls, target.attr, kind))
            t = I.I64 if kind == self.P.INT else I.F64
            self.b.emit('field.set', [obj, self.field_value(v, t)], [], {'cls': cls, 'name': target.attr})
            return
        if isinstance(target.slice, ast.Slice):
            raise NotS0('slice assignment')
        base = self.container(target.value)
        if base.type == BYTEARRAY:
            index = self.as_int(self.expr(target.slice))
            self.b.emit('ba.set', [base, index, self.field_value(v, I.I64)], [], {'mode': 'ck'})
            return
        if not self.is_list(base):
            raise NotS0('element store into %s' % base.type)
        index = self.as_int(self.expr(target.slice))
        elem = base.type.args[0].args[0]
        self.b.emit('list.set', [base, index, self.field_value(v, elem)], [], {'mode': self.index_mode(target)})

    def field_value(self, v, t):
        if v.type == I.F64 and t != I.F64:
            raise NotS0('a float stored into an int slot')
        return self.coerce(v, t)

    def aug_target(self, s):
        """`p.f op= v` / `c[i] op= v`: the target's parts once, then read, operate, write."""
        target = s.target
        if isinstance(target, ast.Attribute):
            obj, cls, kind = self.field_of(target)
            if kind not in (self.P.INT, self.P.FLT):
                raise NotS0('augmented store to field of kind %r' % (kind,))
            t = I.I64 if kind == self.P.INT else I.F64
            attrs = {'cls': cls, 'name': target.attr}
            old = self.b.value('field.get', [obj], t, dict(attrs))
            new = self.apply_binop(s, old, self.expr(s.value))
            self.b.emit('field.set', [obj, self.field_value(new, t)], [], attrs)
            return
        if isinstance(target.slice, ast.Slice):
            raise NotS0('slice augmented assignment')
        base = self.container(target.value)
        if not self.is_list(base):
            raise NotS0('element store into %s' % base.type)
        index = self.as_int(self.expr(target.slice))
        elem = base.type.args[0].args[0]
        mode = self.index_mode(target)
        old = self.b.value('list.get', [base, index], elem, {'mode': mode})
        new = self.apply_binop(s, old, self.expr(s.value))
        self.b.emit('list.set', [base, index, self.field_value(new, elem)], [], {'mode': 'nck'})

    def apply_binop(self, s, left, right):
        """`left <op> right` for an augmented assignment, typed as the legacy path types the
        equivalent BinOp (on the AugAssign node, as rangecheck.py keys its proofs)."""
        fake = ast.BinOp(left=s.target, op=s.op, right=s.value)
        ast.copy_location(fake, s)
        fake._ail_range_src = s
        v = self.binop_values(fake, left, right)
        self.check_kind(fake, v)
        return v

    def index_mode(self, node):
        """'nck' when rangecheck.py proved the subscript in range (the legacy path's own proof
        on the same node), else 'ck'; the range pass may still prove it."""
        if self.proofs is None:
            self.proven(node)
        if self.proofs and self.proofs.ok_index(getattr(node, '_ail_range_src', node)):
            return 'nck'
        return 'ck'

    def subscript(self, node):
        if isinstance(node.slice, ast.Slice):
            raise NotS0('a slice')
        base = self.container(node.value)
        index = self.as_int(self.expr(node.slice))
        if base.type == BYTES:
            return self.b.value('bytes.get', [base, index], I.I64, {'mode': self.index_mode(node)})
        if self.is_list(base):
            return self.b.value('list.get', [base, index], base.type.args[0].args[0],
                                {'mode': self.index_mode(node)})
        if base.type == BYTEARRAY:
            return self.b.value('ba.get', [base, index], I.I64, {'mode': self.index_mode(node)})
        if base.type.head == 'span':
            mode = self.index_mode(node)
            if base.type == I.T('span', I.I64) and not getattr(self.ctx, 'checked_arrays', False):
                mode = 'nck'      # the legacy path reads an unchecked array parameter directly
            return self.b.value('span.get', [base, index], base.type.args[0], {'mode': mode})
        raise NotS0('subscript of %s' % base.type)

    def length(self, node):
        base = self.container(node)
        if base.type == BYTES:
            return self.b.value('bytes.len', [base], I.I64)
        if self.is_list(base):
            return self.b.value('list.len', [base], I.I64)
        if base.type.head == 'span':
            return self.b.value('span.len', [base], I.I64)
        if base.type == BYTEARRAY:
            return self.b.value('ba.len', [base], I.I64)
        raise NotS0('len() of %s' % base.type)

    def method_call(self, node, statement):
        """`c.append(v)`, `c.pop()`, `c.clear()` on a numeric list field."""
        func = node.func
        if node.keywords:
            raise NotS0('keywords to a method')
        if not isinstance(func.value, (ast.Attribute, ast.Name)):
            raise NotS0('method call on %s' % type(func.value).__name__)
        base = self.container(func.value)
        if base.type == BYTEARRAY and func.attr == 'append' and len(node.args) == 1 and statement:
            v = self.field_value(self.expr(node.args[0]), I.I64)
            self.b.emit('ba.push', [base, v])
            return None
        if not self.is_list(base):
            raise NotS0('method of %s' % base.type)
        elem = base.type.args[0].args[0]
        name = func.attr
        if name == 'append' and len(node.args) == 1:
            if not statement:
                raise NotS0('append() used as a value')
            v = self.field_value(self.expr(node.args[0]), elem)
            self.b.emit('list.push', [base, v])
            return None
        if name == 'pop' and not node.args:
            return self.b.value('list.pop', [base], elem)
        if name == 'clear' and not node.args and statement:
            self.b.emit('list.clear', [base])
            return None
        raise NotS0('list method %s()' % name)

    def unary(self, node):
        op = node.op
        if isinstance(op, ast.USub):
            operand = node.operand
            if isinstance(operand, ast.Constant) and type(operand.value) in (int, float):
                value = -operand.value
                if isinstance(value, int):
                    if not -(1 << 63) <= value < (1 << 63):
                        raise NotS0('integer literal out of range')
                    return self.const(I.I64, value)
                return self.const(I.F64, value)
            v = self.expr(operand)
            if v.type == I.F64:
                return self.b.value('fneg', [v], I.F64)
            v = self.coerce(v, I.I64)
            return self.b.value('neg', [v], I.I64, {'mode': 'ck' if self.strict else 'nsw'})
        if isinstance(op, ast.UAdd):
            return self.expr(node.operand)
        if isinstance(op, ast.Not):
            b = self.truthy(node.operand)
            return self.b.value('cmp.eq', [b, self.const(I.I1, False)], I.I1)
        if isinstance(op, ast.Invert):
            v = self.as_int(self.expr(node.operand))
            return self.b.value('inv', [v], I.I64)
        raise NotS0('unary %s' % type(op).__name__)

    def binop(self, node):
        return self.binop_values(node, self.expr(node.left), self.expr(node.right))

    def binop_values(self, node, left, right):
        op = node.op
        floating = I.F64 in (left.type, right.type)
        if isinstance(op, ast.Div):
            return self.b.value('fdiv', [self.coerce(left, I.F64), self.coerce(right, I.F64)], I.F64)
        if isinstance(op, ast.Pow):
            try:
                kind = self.P._etype(node, self.ctx)
            except Exception as error:
                raise NotS0('no legacy type for **: %s' % error)
            if kind == self.P.INT and not floating:
                return self.b.value('pow', [self.as_int(left), self.as_int(right)], I.I64, {'mode': 'ck'})
            return self.b.value('fpow', [self.coerce(left, I.F64), self.coerce(right, I.F64)], I.F64)
        if isinstance(op, (ast.FloorDiv, ast.Mod)):
            name = 'floordiv' if isinstance(op, ast.FloorDiv) else 'floormod'
            if floating:
                return self.b.value('f' + name, [self.coerce(left, I.F64), self.coerce(right, I.F64)], I.F64)
            return self.b.value(name, [self.as_int(left), self.as_int(right)], I.I64, {'mode': 'ck'})
        if isinstance(op, (ast.Add, ast.Sub, ast.Mult)):
            name = {ast.Add: 'add', ast.Sub: 'sub', ast.Mult: 'mul'}[type(op)]
            if floating:
                return self.b.value('f' + name, [self.coerce(left, I.F64), self.coerce(right, I.F64)], I.F64)
            mode = 'ck' if self.strict and not self.proven(node) else 'nsw'
            return self.b.value(name, [self.as_int(left), self.as_int(right)], I.I64, {'mode': mode})
        if isinstance(op, (ast.BitAnd, ast.BitOr, ast.BitXor)):
            name = {ast.BitAnd: 'and', ast.BitOr: 'or', ast.BitXor: 'xor'}[type(op)]
            return self.b.value(name, [self.as_int(left), self.as_int(right)], I.I64)
        if isinstance(op, (ast.LShift, ast.RShift)):
            name = 'shl' if isinstance(op, ast.LShift) else 'shr'
            return self.b.value(name, [self.as_int(left), self.as_int(right)], I.I64,
                                {'mode': 'ck' if self.strict else 'nsw'})
        raise NotS0('binary %s' % type(op).__name__)

    def cmp(self, op, a, b):
        pred = {ast.Eq: 'eq', ast.NotEq: 'ne', ast.Lt: 'lt', ast.LtE: 'le', ast.Gt: 'gt',
                ast.GtE: 'ge'}.get(type(op))
        if pred is None:
            raise NotS0('comparison %s' % type(op).__name__)
        if not (a.type.is_scalar and b.type.is_scalar):
            raise NotS0('comparison of %s and %s' % (a.type, b.type))
        if I.F64 in (a.type, b.type):
            a, b = self.coerce(a, I.F64), self.coerce(b, I.F64)
        elif I.I64 in (a.type, b.type):
            a, b = self.coerce(a, I.I64), self.coerce(b, I.I64)
        return self.b.value('cmp.' + pred, [a, b], I.I1)

    def compare(self, node):
        """`a < b < c`: b evaluated once, c only when a < b (nested regions, so every later
        comparison sits inside the region where its left operand is defined)."""
        return self._chain(self.expr(node.left), node.ops, node.comparators)

    def _chain(self, prev, ops, comparators):
        nxt = self.expr(comparators[0])
        result = self.cmp(ops[0], prev, nxt)
        if len(ops) == 1:
            return result
        go, stop = I.Region(), I.Region()
        self.in_region(go, fill=lambda: self.b.emit('yield', [self._chain(nxt, ops[1:], comparators[1:])]))
        self.in_region(stop, fill=lambda: self.b.emit('yield', [self.const(I.I1, False)]))
        return self.b.value('if', [result], I.I1, None, [go, stop])

    def boolop(self, node):
        is_and = isinstance(node.op, ast.And)
        acc = self.truthy(node.values[0])
        for operand in node.values[1:]:
            evaluate, short = I.Region(), I.Region()
            self.in_region(evaluate, fill=lambda o=operand: self.b.emit('yield', [self.truthy(o)]))
            self.in_region(short, fill=lambda: self.b.emit('yield', [self.const(I.I1, not is_and)]))
            regions = [evaluate, short] if is_and else [short, evaluate]
            acc = self.b.value('if', [acc], I.I1, None, regions)
        return acc

    def ifexp(self, node):
        c = self.truthy(node.test)
        then, other = I.Region(), I.Region()
        values = {}
        self.in_region(then, fill=lambda: values.__setitem__('then', self.expr(node.body)))
        self.in_region(other, fill=lambda: values.__setitem__('else', self.expr(node.orelse)))
        types = (values['then'].type, values['else'].type)
        t = I.F64 if I.F64 in types else I.I64 if I.I64 in types else I.I1
        self.in_region(then, fill=lambda: self.b.emit('yield', [self.coerce(values['then'], t)]))
        self.in_region(other, fill=lambda: self.b.emit('yield', [self.coerce(values['else'], t)]))
        return self.b.value('if', [c], t, None, [then, other])

    # ------------------------------------------------------------------ calls
    def call(self, node, statement=False):
        P, ctx = self.P, self.ctx
        if isinstance(node.func, ast.Attribute):
            return self.method_call(node, statement)
        if not isinstance(node.func, ast.Name):
            raise NotS0('call of a non-name')
        f = node.func.id
        if f in ctx.funcs and f not in self.places and f not in self.params:
            return self.user_call(f, node, statement)
        if not self.is_builtin(f):
            raise NotS0('call of %r' % f)
        args = node.args
        if node.keywords:
            raise NotS0('keywords to %s()' % f)
        if f == 'ord' and len(args) == 1 and isinstance(args[0], ast.Constant) \
                and isinstance(args[0].value, str) and len(args[0].value) == 1:
            return self.const(I.I64, ord(args[0].value))
        if f == 'abs' and len(args) == 1:
            v = self.expr(args[0])
            if v.type == I.F64:
                neg = self.b.value('fneg', [v], I.F64)
            else:
                v = self.coerce(v, I.I64)
                neg = self.b.value('neg', [v], I.I64, {'mode': 'ck' if self.strict else 'nsw'})
            zero = self.const(v.type, 0.0 if v.type == I.F64 else 0)
            c = self.b.value('cmp.lt', [v, zero], I.I1)
            return self.b.value('select', [c, neg, v], v.type)
        if f in ('min', 'max') and len(args) == 2:
            a, b = self.expr(args[0]), self.expr(args[1])
            t = I.F64 if I.F64 in (a.type, b.type) else I.I64
            a, b = self.coerce(a, t), self.coerce(b, t)
            c = self.b.value('cmp.lt' if f == 'min' else 'cmp.gt', [a, b], I.I1)
            return self.b.value('select', [c, a, b], t)
        if f == 'len' and len(args) == 1:
            return self.length(args[0])
        if f in ('wrapping_add', 'wrapping_sub', 'wrapping_mul') and len(args) == 2:
            a, b = self.as_int(self.expr(args[0])), self.as_int(self.expr(args[1]))
            return self.b.value(f.split('_')[1], [a, b], I.I64, {'mode': 'wrap'})
        if f == 'float' and len(args) == 1:
            return self.coerce(self.expr(args[0]), I.F64)
        if f == 'int' and len(args) == 1:
            v = self.expr(args[0])
            if v.type == I.F64:
                return self.b.value('fptosi', [v], I.I64, {'mode': 'ck'})
            return self.coerce(v, I.I64)
        raise NotS0('builtin %s()' % f)

    def user_call(self, f, node, statement):
        P, ctx = self.P, self.ctx
        try:
            arg_nodes = P._bind_call_args(f, node, ctx)
        except Exception as error:
            raise NotS0('call binding of %s(): %s' % (f, error))
        params, ret = ctx.funcs[f]
        symbol = ctx.csym.get(f, f)
        if f in getattr(ctx, 'clones', {}):
            try:
                site = P._call_site_signature(arg_nodes, params, ctx.base_ctx)
                variant = ctx.clones[f].get(P._claim_key(site))
            except Exception as error:
                raise NotS0('clone dispatch for %s(): %s' % (f, error))
            if variant is not None:
                symbol, params = variant[0], variant[1]
        if len(arg_nodes) != len(params):
            raise NotS0('%s() arity' % f)
        param_types = [self.kind_type(k, '%s() parameter %r' % (f, n), views=True) for n, k in params]
        if ret == P.NORET:
            if not statement:
                raise NotS0('void %s() used as a value' % f)
            results = []
        else:
            results = [self.kind_type(ret, '%s() result' % f)]
        order = sorted(range(len(arg_nodes)), key=lambda i: (getattr(arg_nodes[i], 'lineno', 0),
                                                              getattr(arg_nodes[i], 'col_offset', 0)))
        values = [None] * len(arg_nodes)
        for i in order:
            values[i] = self.expr(arg_nodes[i])
        args = []
        arg_abi = []
        own_abi = dict(zip(self.function.params, self.function.attrs.get('abi') or []))
        for v, t, (pname, pkind) in zip(values, param_types, params):
            if v.type == I.F64 and t != I.F64:
                raise NotS0('float argument to an int parameter of %s()' % f)
            if t.head == 'span':
                want = 'array' if pkind == 'array' else 'flist'
                if v.type != t or own_abi.get(v) != want:
                    raise NotS0('list argument to %s() is not a parameter passed through' % f)
                arg_abi.append(want)
                args.append(v)
                continue
            arg_abi.append('value')
            args.append(self.coerce(v, t))
        sig = I.fn_type(param_types, results)
        known = self.program.callee_type(symbol)
        if known is not None and known != sig:
            raise NotS0('two signatures for %s' % symbol)
        if symbol not in self.program.functions:
            self.program.externs[symbol] = sig
        attrs = {'callee': symbol}
        if any(x != 'value' for x in arg_abi):
            attrs['abi'] = arg_abi
        ins = self.b.emit('call', args, results, attrs)
        return ins.results[0] if results else None


def lower(P, fn, ctx, sig, recursive, cname):
    """(IR function, its one-function program) for the S0 subset; NotS0 otherwise."""
    lowering = Lowering(P, fn, ctx, sig, recursive, cname)
    f = lowering.run()
    return f, lowering.program
