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

from pyfront import int_constant
from . import ir as I
from . import effects as E
from . import ownership
from . import flowtypes
from . import ifadd
from .lower_text import TextLowering, NotS0
from .emit_text import allocates_bytes

BYTES = I.T('bytes')
BYTEARRAY = I.T('obj', I.T('bytearray'))
LIST_I64 = I.T('obj', I.T('list', I.I64))
LIST_F64 = I.T('obj', I.T('list', I.F64))
LIST_STR = I.T('obj', I.T('list', I.STRV))
PLIST = I.PLIST
# list-valued methods the S3a lowering recognises as changing a list's length or contents
_LIST_MUTATORS = ('append', 'pop', 'clear', 'extend', 'insert', 'remove', 'sort', 'reverse')


def is_list(t):
    """An owned-list type: obj<list<i64>> or obj<list<f64>>."""
    return t in (LIST_I64, LIST_F64)


def is_slist(t):
    """An owned list of str (S3c-1): obj<list<strv>>, the legacy `ail_slist`."""
    return t == LIST_STR


class _Builder(object):
    def __init__(self):
        self.region = None
        self.where = None             # --debug: (file, line) of the statement being lowered

    def emit(self, op, operands=(), types=(), attrs=None, regions=()):
        ins = I.Instr(op, operands, [I.Value(t) for t in types], attrs, regions)
        if self.where:
            I.SRC[id(ins)] = (ins, self.where)
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


class Lowering(TextLowering):
    def __init__(self, P, fn, ctx, sig, recursive, cname, pending=(), link_units=False, summaries=None):
        """`P` is the legacy compiler module (pyfunc), `ctx` its finished Ctx for this function,
        `sig` the legacy C signature text (linkage and inlining decisions are kept as they are).
        `pending` lists the C symbols of already compiled IR functions that can return with an
        exception pending (S2); `link_units` is set when the program is compiled as separate units
        (an IR function with an exception entry point needs to share a unit with its callers)."""
        self.P = P
        self.fn = fn
        self.ctx = ctx
        self.recursive = recursive
        self.cname = cname
        self.pending = frozenset(pending)
        self.link_units = link_units
        self.summaries = summaries or {}
        self.handler_depth = 0        # enclosing except handlers (a bare `raise` needs one)
        self.loop_depth = 0           # enclosing loops
        self.finally_loops = []       # loop_depth at the entry of each enclosing finally body
        self.alloc_end = 0            # leading local.alloc instructions of the body
        self.hidden = 0
        self.strict = ctx.need is not None
        self.b = _Builder()
        self.program = I.Program()
        self.places = {}
        self.params = {}
        self.proofs = None
        self.linkage = _linkage(sig)
        self.iter_loops = []          # (for.range, list ref) of the `for x in xs` loops over a list
        self.cur_stmt = None
        self.scope_vars = {}          # comprehension variables in scope -> their SSA value
        self.fieldba = set()          # values that are the bytearray a struct field held when read
        self.onecp = set()            # names that hold exactly one character (a str loop variable)
        self.kind_places = {}         # tracked name -> {IR type: place} (flowtypes.py)
        self.tracked = set()
        self.flow = None

    # ------------------------------------------------------------------ kinds and types
    def kind_type(self, kind, what, views=False, owned=False, local=False):
        """The IR type of a legacy kind. : read-only views (bytes) are allowed -- for
        parameters and call arguments, which the callee borrows; `owned` admits the numeric lists
        a function owns (locals and results, stage S3a)."""
        P = self.P
        if kind == P.INT:
            return I.I64
        if kind == P.FLT:
            return I.F64
        if owned and kind == P.LIST:
            return LIST_I64
        if owned and kind == P.FLIST:
            return LIST_F64
        if owned and local and kind == 'bytearray':
            return BYTEARRAY
        if owned and local and kind == P.SLIST:
            return LIST_STR
        if owned and local and kind == 'idict':
            return I.DICT_II
        if owned and local and isinstance(kind, tuple) and len(kind) == 2 and kind[0] == 'olist':
            t = self.rec_list_type(kind[1])
            if t is not None:
                return t
        if kind == P.STR:
            return I.STRV
        if (views or owned) and kind == P.BYTES:
            return BYTES
        if views and kind == 'bytearray':
            return I.T('obj', I.T('bytearray'))
        if views and kind == 'array':
            return I.T('span', I.I64)
        if views and kind == P.FLIST:
            return I.T('span', I.F64)
        if (views or (owned and local)) and isinstance(kind, tuple) and len(kind) == 2 and kind[0] == 'obj' \
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
        if getattr(ctx, 'par_regions', None):
            raise NotS0('parallel region')
        self.tracked = set(P._numeric_mixed_bindings(ctx))
        self.tracked |= {n for n, _, _ in (getattr(ctx, 'numeric_assignments', None) or {}).values()}
        self.tracked |= {n for n, _, _ in (getattr(ctx, 'numeric_tokens', None) or {}).values()}
        self.flow = None
        self.saved_types = {n: ctx.types.get(n) for n in self.tracked}
        if self.tracked:
            # names that hold an int at one point and a float at another: the kind at every statement
            # (flowtypes.py), one place per (name, kind)
            try:
                self.flow = flowtypes.Flow(P, fn, ctx, self.tracked)
                self.flow_snap = self.flow.run()
            except flowtypes.Ambiguous as error:
                raise NotS0('int-or-float bindings: %s' % error)
        if getattr(ctx, 'builders', None):
            raise NotS0('builder locals')
        ret_kind = ctx.ret
        if ret_kind == 'bytearray':
            results = [BYTEARRAY]       # the owner's reference is handed to the caller (retained at the return)
        else:
            results = [] if ret_kind == P.NORET else [self.kind_type(ret_kind, 'the result', owned=True)]
        param_types = [self.kind_type(k, 'parameter %r' % n, views=True) for n, k in ctx.params]
        param_names = [n for n, _ in ctx.params]
        if param_names != [p.arg for p in a.args]:
            raise NotS0('parameter list differs from the source')
        # A bytearray parameter of a function that calls user functions is retained for the whole
        # call, as the legacy path does (a callee may drop the caller's other reference to it), with
        # a cleanup frame so that a longjmp over this function releases it.
        retain = []
        if BYTEARRAY in param_types and any(
                isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id in ctx.funcs
                for c in ast.walk(fn)):
            retain = [n for n, t in zip(param_names, param_types) if t == BYTEARRAY]
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
                                 ast.ClassDef, ast.Nonlocal, ast.SetComp,
                                 ast.DictComp, ast.GeneratorExp, ast.Await, ast.Yield, ast.YieldFrom,
                                 ast.With, ast.Delete, ast.Starred, getattr(ast, 'TryStar', ast.With))) \
                    and node is not fn:
                raise NotS0('%s in the body' % type(node).__name__)
        for node in ast.walk(fn):
            if isinstance(node, ast.Global) and not all(n in ctx.modconsts for n in node.names):
                raise NotS0('global of a name that is not a module variable')
        params = [I.Value(t, hint=n) for n, t in zip(param_names, param_types)]
        attrs = {'sym': self.cname, 'linkage': self.linkage}
        if any(x != 'value' for x in abi):
            attrs['abi'] = abi
        if self.recursive:
            attrs['recursive'] = True
        if retain:
            attrs['retain'] = retain
        f = I.Function(fn.name, params, param_names, results, I.Region(), attrs)
        self.program.add(f)
        self.function = f
        self.b.region = f.body
        self.split_struct_locals(param_names)
        assigned = self.assigned_names()
        for name, value in zip(param_names, params):
            if name not in assigned:
                self.params[name] = value
        self.recs = {}                # scalar-replaced struct locals: name -> {field: place}
        self.rec_lists = {}           # record-list locals: name -> class name
        rec_names = self.scan_recs(param_names)
        for name in sorted(assigned, key=lambda n: (n not in param_names, n)):
            if name in rec_names:
                cls = ctx.types[name][1]
                info = ctx.classes[cls]
                self.recs[name] = {}
                for fld in info.field_order:
                    pname = '%s__%s' % (name, fld)
                    if pname in ctx.locals:
                        raise NotS0('name clash with %s' % pname)
                    t = I.I64 if info.field_types[fld] == P.INT else I.F64
                    self.recs[name][fld] = self.b.value('local.alloc', [], I.place(t), {'name': pname})
                continue
            if name in self.tracked:
                self.make_tracked_places(name, param_names, params)
                continue
            if name in param_names:
                t = value_type = params[param_names.index(name)].type
                if not t.is_scalar and t not in (I.STRV, BYTES):
                    raise NotS0('parameter %r of type %s is reassigned' % (name, t))
            else:
                kind = ctx.types.get(name)
                if kind in (P.LIST, P.FLIST):
                    self.check_list_local(name)
                elif kind == P.SLIST:
                    self.check_slist_local(name)
                t = value_type = self.kind_type(kind, 'local %r' % name, owned=True, local=True)
            if name in getattr(ctx, 'optional', ()) or (name in getattr(ctx, 'stdin_unbound', ())
                                                         and not self.stdin_loop_only(name)):
                raise NotS0('local %r is optional or special' % name)
            self.places[name] = self.b.value('local.alloc', [], I.place(value_type), {'name': name})
            if I.rec_elem(value_type) is not None:
                self.rec_lists[name] = ctx.types[name][1]
        for name, value in zip(param_names, params):
            if name in self.kind_places:
                self.store(name, value)
            elif name in self.places:
                self.b.emit('store', [self.places[name], value])
        self.alloc_end = sum(1 for i in f.body.instrs if i.op == 'local.alloc')
        if self.recursive:
            self.b.emit('rt', [], [], {'callee': 'ail_depth_enter'})
        self.stmts(fn.body)
        if not self.b.terminated():
            self.fallthrough()
        try:
            resolved = ownership.resolve(f, self.program, self.summaries, self.iter_loops,
                                         value=os.environ.get('AIL_SURFACE') != 'python')
        except ownership.NeedsBox as box:
            raise NotS0('Rule X (needs a box, stage S3e): %s' % box)
        self.check_bytes_loops(f.body, False)
        f.sharing = dict(resolved.stats)
        f.walias = list(resolved.walias)
        ops = [i for i in I.walk(f.body)]
        if any(i.op == 'try' for i in ops):
            f.attrs['frame'] = True
            if any(i.op == 'local.alloc' and is_slist(i.result.type.pointee) for i in ops) \
                    and self.try_in_loop(f.body, False):
                # priced on tally-ail-4 `run` (an interpreter loop with a try in each iteration): the
                # outlined try body and the frame in memory cost +20% of the function against the legacy
                # inline setjmp; the function stays legacy until the IR's try is cheaper (design section 17)
                raise NotS0('a try inside a loop in a function with a list of str (the outlined try costs more '
                            'than the legacy inline one, section 17)')
            if results and (is_list(results[0]) or results[0] == BYTEARRAY):
                raise NotS0('a function that returns a container and has a try')
        owned = [i.attrs['name'] for i in f.body.instrs
                 if i.op == 'local.alloc' and (is_list(i.result.type.pointee) or is_slist(i.result.type.pointee)
                                               or I.rec_elem(i.result.type.pointee) is not None
                                               or i.result.type.pointee in (BYTEARRAY, I.DICT_II))]
        if owned:
            f.attrs['owned'] = owned
        if results and is_list(results[0]):
            f.attrs['ret_list'] = 'flist' if results[0] == LIST_F64 else 'list'
        # a function that raises, or calls one that can return with an exception pending, has the
        # exception entry point `<sym>__ir` and a wrapper under its own name (emit_c)
        if any(i.op in ('raise', 'reraise', 'try') or (i.op == 'call' and i.attrs.get('callee') in self.pending)
               for i in ops):
            f.attrs['pending'] = True
        E.summarize_program(self.program)
        return f

    def try_in_loop(self, region, in_loop):
        for ins in region.instrs:
            if ins.op == 'try' and in_loop:
                return True
            for r in ins.regions:
                if self.try_in_loop(r, in_loop or ins.op in I.LOOP_OPS):
                    return True
        return False

    def check_bytes_loops(self, region, in_loop):
        """A bytes block allocated by an iteration is held until the function returns (the bytes arena has
        no per-iteration reset in the IR yet; the legacy path resets it only for a few shapes): such a
        function stays on the legacy emitter (stage S4c: regions)."""
        for ins in region.instrs:
            if in_loop and allocates_bytes(ins):
                raise NotS0('a bytes block allocated inside a loop (stage S4c: regions)')
            for r in ins.regions:
                self.check_bytes_loops(r, in_loop or ins.op in I.LOOP_OPS)

    def make_tracked_places(self, name, param_names, params):
        """Places of a name that holds both kinds: one per kind it ever holds (flowtypes.py)."""
        P = self.P
        kinds = self.flow.kinds_ever[name]
        types = [t for t, k in ((I.I64, P.INT), (I.F64, P.FLT)) if k in kinds]
        if name in param_names:
            types = sorted(set(types) | {params[param_names.index(name)].type}, key=lambda t: t != I.I64)
        if not types or any(t not in (I.I64, I.F64) for t in types):
            raise NotS0('local %r of kind %r' % (name, kinds))
        if name in getattr(self.ctx, 'optional', ()) or name in getattr(self.ctx, 'stdin_unbound', ()):
            raise NotS0('local %r is optional or special' % name)
        self.kind_places[name] = {}
        for t in types:
            pname = name if (t == types[0]) else name + '__f'
            if pname != name and pname in self.ctx.locals:
                raise NotS0('name clash with %s' % pname)
            self.kind_places[name][t] = self.b.value('local.alloc', [], I.place(t), {'name': pname})
        self.places[name] = self.kind_places[name][types[0]]

    def apply_flow(self, s):
        """The kinds the tracked names hold at the start of statement `s`."""
        snap = self.flow_snap.get(id(s)) if self.flow is not None else None
        if not snap:
            return
        P = self.P
        for n, kinds in snap.items():
            if len(kinds) == 1 and n in self.kind_places:
                k = next(iter(kinds))
                self.ctx.types[n] = k
                place = self.kind_places[n].get(I.I64 if k == P.INT else I.F64)
                if place is not None:
                    self.places[n] = place

    def assigned_names(self):
        out = set()
        comp_targets = set()
        for node in ast.walk(self.fn):
            if isinstance(node, ast.ListComp):
                for g in node.generators:
                    comp_targets.update(id(n) for n in ast.walk(g.target))
        for node in ast.walk(self.fn):
            if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)) \
                    and id(node) not in comp_targets:
                out.add(node.id)
            elif isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.For)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for t in targets:
                    if isinstance(t, (ast.Attribute, ast.Subscript)) and not isinstance(node, ast.For):
                        continue          # a field or element store (checked where it is lowered)
                    if not isinstance(t, ast.Name):
                        raise NotS0('assignment to %s' % type(t).__name__)
        modconsts = getattr(self.ctx, 'modconsts', {})
        gdecl = getattr(self.ctx, 'gdecl', ())
        for name in out:
            if name in modconsts and name not in gdecl:
                raise NotS0('module constant %r rebound' % name)
        return out - set(gdecl)           # a module variable is a global, not a local place

    def leave(self):
        if self.recursive:
            self.b.emit('rt', [], [], {'callee': 'ail_depth_leave'})

    def fallthrough(self):
        """The legacy path's fall-off-the-end return: 0 (or nothing for a void function)."""
        self.leave()
        if self.function.results:
            t = self.function.results[0]
            if is_list(t) or t == BYTEARRAY or t in (I.STRV, BYTES):
                raise NotS0('a function returning a container or text that can fall off its end')
            self.b.emit('return', [self.const(t, 0.0 if t == I.F64 else 0)])
        else:
            self.b.emit('return', [])

    # ------------------------------------------------------------------ statements
    def stmts(self, body):
        for s in body:
            if self.b.terminated():
                return            # dead code after return/break/continue
            outer = self.b.where
            self.b.where = self.P._debug_where(s) or outer       # None outside --debug
            self.stmt(s)
            self.drop_after(s)
            self.b.where = outer

    def drop_after(self, s):
        """An owned list whose last mention is statement `s` is dropped when `s` completes (the
        legacy path frees a numeric-list local at the same point, so a pipeline of whole-array
        steps holds two arrays at a time, not all of them until the function returns)."""
        names = (getattr(self.ctx, 'free_points', None) or {}).get(id(s), ())
        for name in names:
            place = self.places.get(name)
            if place is None or not is_list(place.type.pointee) or name in self.ctx.kind \
                    or self.b.terminated():
                continue
            self.b.emit('list.reset', [self.list_ref(place)], [], {'drop': True})

    def list_ref(self, place):
        return self.b.value('list.ref', [place], place.type.pointee)

    def check_list_local(self, name):
        """The numeric-list locals the S3a lowering owns: flat lists of int or float, none of the
        legacy path's special representations (handles, tuples, rows, bools, str)."""
        ctx = self.ctx
        for attr in ('nlist', 'blist', 'strlist', 'bool_lists', 'tstride', 'srowtypes', 'rowof', 'rowparam',
                     'trowsf', 'handles', 'dhandles', 'hstride', 'borrowed_aliases'):
            if name in (getattr(ctx, attr, None) or ()):
                raise NotS0('list %r is a %s list' % (name, attr))
        if name in ctx.kind:
            raise NotS0('list %r is a special parameter' % name)

    # ------------------------------------------------------------------ owned lists (S3a)
    #
    # Every list is owned by exactly one place (a local, a struct field, or a hidden temporary) and
    # every other reference to it is a borrow that lives for one instruction (or, after LICM, a
    # span over a loop that cannot resize it). No operation here makes a second name for a list:
    # `ys = xs`, `ys = xs[:]`, `t.f = xs` with `xs` read afterwards and similar shapes are refused
    # (the function stays on the legacy emitter, which copies), because under sharing semantics
    # they would mean something else. The one store of a named list that is accepted is a move
    # into a struct field where the program cannot tell a copy from the original (design section
    # 12: Rule M, and Rule M' when the local is still read afterwards).
    def is_list_name(self, name):
        place = self.places.get(name)
        return place is not None and is_list(place.type.pointee)

    def guard_field_ba(self, base, *nodes):
        """A bytearray read from a field is the reference the field held at that moment; a user
        function called while the rest of the access is evaluated may rebind the field, so such
        accesses are not lowered (the legacy path takes the same reference first and has the same
        exposure; the IR does not extend it)."""
        if base not in self.fieldba:
            return
        for node in nodes:
            for n in ast.walk(node):
                if isinstance(n, ast.Call) and not (isinstance(n.func, ast.Name) and n.func.id not in self.ctx.funcs
                                                   and n.func.id not in getattr(self.ctx, 'classes', {})):
                    raise NotS0('a bytearray field accessed while a function is called')

    def is_ba_name(self, name):
        place = self.places.get(name)
        return place is not None and place.type.pointee == BYTEARRAY

    def assign_ba(self, name, node):
        """`b = bytearray()` / `b = bytearray(n)`: the place takes a fresh object (the old one is
        released). `b = a` for a bytearray local or parameter `a`: the place takes a second reference to
        a's object (`ba.copyref`; one object with two names, which is what Python and the legacy path
        mean). Any other source would be a conversion or a reference read from a field."""
        if isinstance(node, ast.Name) and node.id != name and (
                self.is_ba_name(node.id) or (node.id in self.params and self.params[node.id].type == BYTEARRAY)):
            self.b.emit('ba.copyref', [self.places[name], self.container(node)])
            return
        if isinstance(node, ast.Name) and node.id == name and self.is_ba_name(name):
            return              # `b = b`
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in self.ctx.funcs \
                and node.func.id not in self.places and node.func.id not in self.params:
            self.user_call(node.func.id, node, False, ba_dst=self.places[name])
            return
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'bytearray'
                and self.is_builtin('bytearray') and not node.keywords and len(node.args) <= 1):
            raise NotS0('a bytearray built from %s (a second name for one, or a conversion: stage S3b)'
                        % type(node).__name__)
        n = self.as_int(self.expr(node.args[0])) if node.args else self.const(I.I64, 0)
        self.b.emit('ba.new', [self.places[name], n])

    def list_kind_of(self, t):
        return self.P.FLIST if t == LIST_F64 else self.P.LIST

    def same_kind(self, node, kind):
        try:
            got = self.P._etype(node, self.ctx)
        except Exception as error:
            raise NotS0('no legacy type for a list expression: %s' % error)
        if got != kind:
            raise NotS0('list kind disagreement at line %s: legacy %r, IR %r'
                        % (getattr(node, 'lineno', '?'), got, kind))

    def new_list_place(self, kind, tag):
        return self.new_place(tag, LIST_STR if kind == self.P.SLIST else LIST_F64 if kind == self.P.FLIST else LIST_I64)

    # ------------------------------------------------------------------ the stdin line loop (S3c-3)
    def stdin_loop_only(self, name):
        """Whether `name` is the variable of exactly one `for name in sys.stdin` loop and is mentioned nowhere outside
        its body (the legacy NameError for an unbound `name` after an empty input cannot happen)."""
        loops = [n for n in ast.walk(self.fn) if isinstance(n, ast.For) and isinstance(n.target, ast.Name)
                 and n.target.id == name and self.P._sys_attr_path(n.iter) == 'sys.stdin' and not n.orelse]
        if len(loops) != 1:
            return False
        inside = set(id(x) for st in loops[0].body for x in ast.walk(st))
        stores = [n for n in ast.walk(self.fn) if isinstance(n, ast.Name) and n.id == name]
        return all(id(n) in inside or n is loops[0].target for n in stores)

    def for_stdin(self, s):
        """`for line in sys.stdin`: the legacy loop's own steps, one `readline` per iteration until it returns the empty
        text (end of input); every line includes its newline."""
        target = s.target.id
        if s.orelse or target in self.params or target not in self.places or self.places[target].type.pointee != I.STRV:
            raise NotS0('for target %r' % target)
        body = I.Region()

        def loop_body():
            line = self.rt('stdin_readline', [])
            n = self.rt('str_bytes', [line])
            c = self.b.value('cmp.gt', [n, self.const(I.I64, 0)], I.I1)
            go, stop = I.Region(), I.Region()
            self.in_region(go, fill=lambda: self.b.emit('yield'))
            self.in_region(stop, fill=lambda: self.b.emit('break'))
            self.b.emit('if', [c], [], None, [go, stop])
            self.b.emit('store', [self.places[target], line])
            self.stmts(s.body)
            if not self.b.terminated():
                self.b.emit('continue')
        self.loop_depth += 1
        try:
            self.in_region(body, fill=loop_body)
        finally:
            self.loop_depth -= 1
        self.b.emit('loop', [], [], None, [body])

    # ------------------------------------------------------------------ int dictionaries (S3d-1)
    def is_dict_name(self, name):
        place = self.places.get(name)
        return place is not None and place.type.pointee == I.DICT_II

    def dict_key(self, node):
        if self.text_kind(node) is not None or self.P._etype(node, self.ctx) != self.P.INT:
            raise NotS0('a dictionary key that is not an int')
        return self.as_int(self.expr(node))

    def assign_dict(self, name, node):
        """`d = {}`: the only way to give a dictionary a value besides `d[k] = v`."""
        if not (isinstance(node, ast.Dict) and not node.keys):
            raise NotS0('a dictionary built from %s' % type(node).__name__)
        self.b.emit('dict.reset', [self.places[name]])

    def dict_in(self, node):
        """`k in d` / `k not in d`."""
        key = self.dict_key(node.left)
        found = self.b.value('dict.has', [self.places[node.comparators[0].id], key], I.I1)
        if isinstance(node.ops[0], ast.NotIn):
            return self.b.value('cmp.eq', [found, self.const(I.I1, False)], I.I1)
        return found

    # ------------------------------------------------------------------ lists of scalar records (S3c-3)
    #
    # A local `list[C]` where C is a struct with only int and float fields is held inline (`obj<list<tup<..>>>`,
    # the C struct `ail_rec_<sig>`); the struct locals that only receive a popped record (`it = heappop(h, ..)`) and
    # are only read through their fields are scalar-replaced: one place per field, no object. Anything else the
    # program does with such a list or record keeps the function on the legacy emitter.
    def split_struct_locals(self, param_names):
        """`st = Q([], ..)` where every field of Q is a list of scalar records, `st` is assigned once and only
        used as `st.field`: the fields become locals of their own (`st__field`), so the lists can be held inline."""
        P, ctx = self.P, self.ctx
        cands = {}
        for n, k in ctx.types.items():
            if isinstance(k, tuple) and k[0] == 'obj' and n not in param_names:
                info = getattr(ctx, 'classes', {}).get(k[1])
                if info is not None and info.field_order and k[1] not in (getattr(P, '_NULLABLE', None) or ()) \
                        and all(isinstance(info.field_types.get(f), tuple) and info.field_types[f][0] == 'olist'
                                and self.rec_class_ok(info.field_types[f][1]) is not None
                                for f in info.field_order) \
                        and [a for a, _ in info.init_params] == list(info.field_order):
                    cands[n] = info
        if not cands:
            return
        parents = {}
        for node in ast.walk(self.fn):
            for child in ast.iter_child_nodes(node):
                parents[id(child)] = node
        ctors = {}
        for n in list(cands):
            uses = [x for x in ast.walk(self.fn) if isinstance(x, ast.Name) and x.id == n]
            good = True
            sites = []
            for x in uses:
                par = parents.get(id(x))
                if isinstance(par, ast.Attribute) and par.value is x and isinstance(par.ctx, ast.Load):
                    sites.append(par)
                elif isinstance(par, ast.Assign) and len(par.targets) == 1 and par.targets[0] is x \
                        and isinstance(par.value, ast.Call) and isinstance(par.value.func, ast.Name) \
                        and par.value.func.id == ctx.types[n][1] and not par.value.keywords \
                        and len(par.value.args) == len(cands[n].field_order) \
                        and all(isinstance(a, ast.List) and not a.elts for a in par.value.args) and n not in ctors:
                    ctors[n] = par
                else:
                    good = False
            if not good or n not in ctors:
                del cands[n]
                continue
            cands[n] = (cands[n], sites)
        for n, (info, sites) in cands.items():
            for site in sites:
                if site.attr not in info.field_order:
                    raise NotS0('unknown field %s' % site.attr)
                new = ast.Name(id='%s__%s' % (n, site.attr), ctx=ast.Load())
                ast.copy_location(new, site)
                parent = parents[id(site)]
                for fld, value in ast.iter_fields(parent):
                    if value is site:
                        setattr(parent, fld, new)
                    elif isinstance(value, list):
                        for k, item in enumerate(value):
                            if item is site:
                                value[k] = new
            assign = ctors[n]
            body_owner = parents[id(assign)]
            repl = []
            for f in info.field_order:
                name = '%s__%s' % (n, f)
                if name in ctx.locals or name in ctx.types:
                    raise NotS0('name clash with %s' % name)
                ctx.types[name] = info.field_types[f]
                st = ast.Assign(targets=[ast.Name(id=name, ctx=ast.Store())], value=ast.List(elts=[], ctx=ast.Load()))
                ast.copy_location(st, assign)
                ast.fix_missing_locations(st)
                repl.append(st)
            for fld, value in ast.iter_fields(body_owner):
                if isinstance(value, list) and assign in value:
                    k = value.index(assign)
                    value[k:k + 1] = repl

    def rec_class_ok(self, cls):
        P, ctx = self.P, self.ctx
        info = getattr(ctx, 'classes', {}).get(cls)
        if info is None or cls in (getattr(P, '_NULLABLE', None) or ()) or not info.field_order:
            return None
        if any(info.field_types.get(f) not in (P.INT, P.FLT) for f in info.field_order):
            return None
        if [n for n, _ in info.init_params] != list(info.field_order):
            return None
        return info

    def rec_list_type(self, cls):
        info = self.rec_class_ok(cls)
        if info is None:
            return None
        return I.T('obj', I.T('list', I.T('tup', *[I.I64 if info.field_types[f] == self.P.INT else I.F64
                                                   for f in info.field_order])))

    def scan_recs(self, param_names):
        """The struct locals to scalar-replace: assigned only from the pop of a record-list local (or from each other)
        and used only as `x.field`."""
        P, ctx = self.P, self.ctx
        rl = {n for n, k in ctx.types.items()
              if isinstance(k, tuple) and k[0] == 'olist' and self.rec_class_ok(k[1]) is not None
              and n not in param_names}
        cands = {n for n, k in ctx.types.items()
                 if isinstance(k, tuple) and k[0] == 'obj' and self.rec_class_ok(k[1]) is not None
                 and n not in param_names}
        parents = {}
        for node in ast.walk(self.fn):
            for child in ast.iter_child_nodes(node):
                parents[id(child)] = node
        names = [n for n in ast.walk(self.fn) if isinstance(n, ast.Name)]
        cands &= {n.id for n in names}

        def is_pop(v):
            return isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute) and v.func.attr == 'pop' \
                and isinstance(v.func.value, ast.Name) and v.func.value.id in rl \
                and any(k.arg == '_ail_heap' for k in v.keywords)
        changed = True
        while changed:
            changed = False
            for n in names:
                if n.id not in cands:
                    continue
                par = parents.get(id(n))
                ok = False
                if isinstance(par, ast.Attribute) and par.value is n and isinstance(par.ctx, ast.Load):
                    ok = True
                elif isinstance(par, ast.Assign) and len(par.targets) == 1:
                    if par.targets[0] is n:
                        v = par.value
                        ok = is_pop(v) or (isinstance(v, ast.Name) and v.id in cands
                                           and ctx.types.get(v.id) == ctx.types.get(n.id))
                    elif par.value is n:
                        t = par.targets[0]
                        ok = isinstance(t, ast.Name) and t.id in cands and ctx.types.get(t.id) == ctx.types.get(n.id)
                if not ok:
                    cands.discard(n.id)
                    changed = True
        # every remaining name must be fed by a pop (directly or through other names): an unset one is not ours
        fed = set()
        for node in ast.walk(self.fn):
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                    and node.targets[0].id in cands and is_pop(node.value):
                fed.add(node.targets[0].id)
        grew = True
        while grew:
            grew = False
            for node in ast.walk(self.fn):
                if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                        and node.targets[0].id in cands and isinstance(node.value, ast.Name) \
                        and node.value.id in fed and node.targets[0].id not in fed:
                    fed.add(node.targets[0].id)
                    grew = True
        return cands & fed

    def assign_rlist(self, name, node):
        """`h: list[C] = []`: the only way to give a record list a value besides appending."""
        if not (isinstance(node, ast.List) and not node.elts):
            raise NotS0('a list of records built from %s' % type(node).__name__)
        self.b.emit('list.reset', [self.list_ref(self.places[name])])

    def heap_key(self, name, node, want):
        """The field indices of a legacy heap marker `_ail_heap='up d b n'` on the record list `name`."""
        cls = self.rec_lists[name]
        info = self.ctx.classes[cls]
        marks = [k for k in node.keywords if k.arg == '_ail_heap']
        if len(node.keywords) != 1 or len(marks) != 1 or not isinstance(marks[0].value, ast.Constant) \
                or not isinstance(marks[0].value.value, str):
            raise NotS0('a list method with keywords')
        words = marks[0].value.value.split()
        if words[0] != want or len(words) < 2 or any(w not in info.field_order for w in words[1:]):
            raise NotS0('heap marker %r' % marks[0].value.value)
        return [info.field_order.index(w) for w in words[1:]]

    def rlist_method(self, name, node, statement):
        func = node.func
        ref = self.list_ref(self.places[name])
        cls = self.rec_lists[name]
        info = self.ctx.classes[cls]
        if func.attr == 'append' and len(node.args) == 1 and not node.keywords and statement:
            a = node.args[0]
            if not (isinstance(a, ast.Call) and isinstance(a.func, ast.Name) and a.func.id == cls
                    and not a.keywords and len(a.args) == len(info.field_order)):
                raise NotS0('a record appended that is not a constructor call')
            vals = []
            for arg, f in zip(a.args, info.field_order):
                v = self.expr(arg)
                vals.append(self.as_int(v) if info.field_types[f] == self.P.INT else self.coerce(v, I.F64))
            self.b.emit('rec.push', [self.list_ref(self.places[name])] + vals)
            return None
        if func.attr == 'sort' and not node.args and statement:
            self.b.emit('rec.up', [ref], [], {'key': self.heap_key(name, node, 'up')})
            return None
        if func.attr == 'pop' and not node.args and statement:
            key = self.heap_key(name, node, 'pop')
            types = [I.I64 if info.field_types[f] == self.P.INT else I.F64 for f in info.field_order]
            self.b.emit('rec.pop', [ref], types, {'key': key})
            return None
        if func.attr == 'clear' and not node.args and not node.keywords and statement:
            self.b.emit('list.clear', [ref])
            return None
        raise NotS0('list of records method %s()' % func.attr)

    def assign_rec(self, name, node):
        """`it = h.pop(_ail_heap=..)` or `it = other`: the fields go to the places of `it`."""
        P = self.P
        if isinstance(node, ast.Name) and node.id in self.recs:
            for f, place in self.recs[name].items():
                self.b.emit('store', [place, self.b.value('load', [self.recs[node.id][f]], place.type.pointee)])
            return
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'pop' \
                and isinstance(node.func.value, ast.Name) and node.func.value.id in self.rec_lists:
            src = node.func.value.id
            if self.rec_lists[src] != self.ctx.types[name][1]:
                raise NotS0('a record of another class')
            info = self.ctx.classes[self.rec_lists[src]]
            key = self.heap_key(src, node, 'pop')
            types = [I.I64 if info.field_types[f] == P.INT else I.F64 for f in info.field_order]
            ins = self.b.emit('rec.pop', [self.list_ref(self.places[src])], types, {'key': key})
            for f, v in zip(info.field_order, ins.results):
                self.b.emit('store', [self.recs[name][f], v])
            return
        raise NotS0('a record assigned from %s' % type(node).__name__)

    # ------------------------------------------------------------------ owned lists of str (S3c-1)
    #
    # `ail_slist`: a spine of `ail_str` views over the function's text arena, owned by one local place (no
    # count, no sharing: `ys = xs`, `ys = xs[:]`, a list handed to a call or a field, a list returned, an element
    # store and every other shape that is not below keep the function on the legacy emitter). What the lowering
    # takes: `[]` and `[a, b, ...]` of str, `s.split()`, `s.split(sep)`, `s.splitlines()`, `xs.append(s)`,
    # `xs.clear()`, `xs.sort()`, `xs[i]`, `len(xs)`, `for x in xs`, `x in xs`, `x not in xs`, `sep.join(xs)`.
    # Its elements are views: emit_text.py does not reset the str arena at the top of a loop in which a list of
    # str could hold a block that the reset releases (design section 17).
    def is_slist_name(self, name):
        place = self.places.get(name)
        return place is not None and is_slist(place.type.pointee)

    def check_slist_local(self, name):
        ctx = self.ctx
        for attr in ('nlist', 'blist', 'bool_lists', 'tstride', 'srowtypes', 'rowof', 'rowparam', 'trowsf',
                     'handles', 'dhandles', 'hstride', 'borrowed_aliases', 'hrowof', 'skeys', 'sdict_values'):
            if name in (getattr(ctx, attr, None) or ()):
                raise NotS0('list of str %r is a %s list' % (name, attr))
        if name in ctx.kind:
            raise NotS0('list of str %r is a special parameter' % name)

    def assign_slist_name(self, name, node):
        place = self.places[name]
        self.assign_slist(lambda: self.list_ref(place), node, name)

    def assign_slist(self, ref_fn, node, dst='?'):
        """Replace the content of the list of str `ref_fn()` names with the list `node` builds."""
        P = self.P
        if isinstance(node, ast.List):
            if any(isinstance(e, ast.Starred) for e in node.elts):
                raise NotS0('a starred list display')
            if not node.elts:
                self.b.emit('list.reset', [ref_fn()])
                return
            vals = []
            for e in node.elts:
                if self.text_kind(e) != 'str':
                    raise NotS0('a list of str with an element that is not a str')
                vals.append(self.expr(e))
            self.b.emit('list.lit', [ref_fn()] + vals)
            return
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and not node.keywords \
                and node.func.attr in ('split', 'splitlines') and self.text_kind(node.func.value) == 'str':
            if node.func.attr == 'splitlines' and not node.args:
                callee, args = 'str_splitlines', []
            elif node.func.attr == 'split' and not node.args:
                callee, args = 'str_split_ws', []
            elif node.func.attr == 'split' and len(node.args) == 1 and self.text_kind(node.args[0]) == 'str':
                callee, args = 'str_split_sep', [node.args[0]]
            else:
                raise NotS0('%s() with this argument shape' % node.func.attr)
            self.same_kind(node, P.SLIST)
            recv = self.expr(node.func.value)
            vals = [recv] + [self.expr(a) for a in args]
            self.b.emit('list.rt', [ref_fn()] + vals, [], {'callee': callee})
            return
        if isinstance(node, ast.ListComp):
            tmp = self.comprehension(node, P.SLIST)
            self.b.emit('list.move', [ref_fn(), self.list_ref(tmp)])
            return
        inner = None
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice) and node.slice.lower is None \
                and node.slice.upper is None and node.slice.step is None:
            inner = node.value
        elif isinstance(node, ast.Call) and not node.keywords:
            if isinstance(node.func, ast.Name) and node.func.id == 'list' and len(node.args) == 1 \
                    and self.is_builtin('list'):
                inner = node.args[0]
            elif isinstance(node.func, ast.Attribute) and node.func.attr == 'copy' and not node.args:
                inner = node.func.value
        if isinstance(inner, ast.Name) and self.is_slist_name(inner.id):
            self.b.emit('list.copy', [ref_fn(), self.container(inner)], [], {'dst': dst, 'line': getattr(node, 'lineno', 0)})
            return
        raise NotS0('a list of str built from %s' % type(node).__name__)

    def is_slist_expr(self, node):
        """Whether `node` is a split()/splitlines() call or a display of str values (a list of str that nothing
        names)."""
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and not node.keywords \
                and node.func.attr in ('split', 'splitlines'):
            return self.text_kind(node.func.value) == 'str'
        return isinstance(node, ast.List) and bool(node.elts) \
            and all(self.text_kind(e) == 'str' for e in node.elts)

    def slist_method(self, base, name, node, statement):
        """A method call on a list of str: `append`, `clear`, `sort`."""
        if name == 'append' and len(node.args) == 1 and statement:
            if self.text_kind(node.args[0]) != 'str':
                raise NotS0('append of something that is not a str to a list of str')
            self.b.emit('list.push', [base, self.expr(node.args[0])])
            return None
        if name == 'clear' and not node.args and statement:
            self.b.emit('list.clear', [base])
            return None
        if name == 'sort' and not node.args and statement:
            self.b.emit('list.sort', [base])
            return None
        raise NotS0('list of str method %s()' % name)

    def assign_list_name(self, name, node):
        place = self.places[name]
        self.assign_list(lambda: self.list_ref(place), node, self.list_kind_of(place.type.pointee), dst=name)

    def list_source(self, node, kind):
        """(reference, name) when `node` names an existing list of element kind `kind`: an owned list
        local or a struct field's list; None for any other expression."""
        P = self.P
        t = LIST_F64 if kind == P.FLIST else LIST_I64
        if isinstance(node, ast.Name):
            if node.id in self.params and self.params[node.id].type.head == 'span':
                raise NotS0('a read-only list parameter %r is shared with its caller (stage S3e)' % node.id)
            if self.is_list_name(node.id):
                place = self.places[node.id]
                if place.type.pointee != t:
                    raise NotS0('a list assigned to a list of the other element type')
                return self.list_ref(place), node.id
            return None
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            obj, cls, fkind = self.field_of(node)
            if fkind not in (P.LIST, P.FLIST):
                return None
            if fkind != kind:
                raise NotS0('a list assigned to a list of the other element type')
            return (self.b.value('field.list', [obj], t, {'cls': cls, 'name': node.attr}),
                    '%s.%s' % (node.value.id, node.attr))
        return None

    def copy_source(self, node, kind):
        """The list value an explicit copy `xs[:]`, `list(xs)` or `xs.copy()` reads, else None."""
        P = self.P
        inner = None
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice):
            sl = node.slice
            if sl.lower is None and sl.upper is None and sl.step is None:
                inner = node.value
        elif isinstance(node, ast.Call) and not node.keywords:
            if isinstance(node.func, ast.Name) and node.func.id == 'list' and len(node.args) == 1                     and self.is_builtin('list'):
                inner = node.args[0]
            elif isinstance(node.func, ast.Attribute) and node.func.attr == 'copy' and not node.args:
                inner = node.func.value
        if inner is None or not isinstance(inner, (ast.Name, ast.Attribute)):
            return None
        v = self.container(inner)
        elem = I.F64 if kind == P.FLIST else I.I64
        if not (v.type == (LIST_F64 if kind == P.FLIST else LIST_I64) or v.type == I.T('span', elem)):
            raise NotS0('a copy of something that is not a list of the target kind')
        return v

    def assign_list(self, ref_fn, node, kind, dst='?'):
        """Replace the content of the list `ref_fn()` names with the list `node` builds or names."""
        P = self.P
        elem = I.F64 if kind == P.FLIST else I.I64
        src = self.list_source(node, kind)
        if src is not None:
            # Python's `dst = src`: one list, two names. The ownership analysis (ownership.py)
            # decides move, rename or box
            self.b.emit('list.share', [ref_fn(), src[0]], [], {'dst': dst, 'src': src[1],
                                                               'line': getattr(node, 'lineno', 0)})
            return
        copy = self.copy_source(node, kind)
        if copy is not None:
            self.b.emit('list.copy', [ref_fn(), copy], [], {'dst': dst, 'line': getattr(node, 'lineno', 0)})
            return
        if isinstance(node, ast.List):
            if any(isinstance(e, ast.Starred) for e in node.elts):
                raise NotS0('a starred list display')
            if not node.elts:
                self.b.emit('list.reset', [ref_fn()])
                return
            vals = [self.field_value(self.expr(e), elem) for e in node.elts]
            self.b.emit('list.lit', [ref_fn()] + vals)
            return
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
            for lst, cnt, first in ((node.left, node.right, True), (node.right, node.left, False)):
                if isinstance(lst, ast.List) and len(lst.elts) == 1 and not isinstance(lst.elts[0], ast.Starred):
                    if first:
                        v = self.field_value(self.expr(lst.elts[0]), elem)
                        n = self.as_int(self.expr(cnt))
                    else:
                        n = self.as_int(self.expr(cnt))
                        v = self.field_value(self.expr(lst.elts[0]), elem)
                    self.b.emit('list.repeat', [ref_fn(), v, n])
                    return
            raise NotS0('a list product that is not [v] * n')
        if isinstance(node, ast.ListComp):
            tmp = self.comprehension(node, kind)
            self.b.emit('list.move', [ref_fn(), self.list_ref(tmp)])
            return
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in self.ctx.funcs \
                and node.func.id not in self.places and node.func.id not in self.params:
            self.user_call(node.func.id, node, False, list_dst=ref_fn, list_kind=kind)
            return
        raise NotS0('a list built from %s' % type(node).__name__)

    def mentions_outside(self, name, inner):
        inside = set(id(n) for n in ast.walk(inner))
        # (another comprehension that binds the same name has a scope of its own: its mentions are not outside)
        for c in ast.walk(self.fn):
            if isinstance(c, ast.ListComp) and any(isinstance(g.target, ast.Name) and g.target.id == name
                                                   for g in c.generators):
                inside.update(id(n) for n in ast.walk(c))
        return any(isinstance(n, ast.Name) and n.id == name and id(n) not in inside for n in ast.walk(self.fn))

    def comprehension(self, node, kind):
        """`[elt for v in range(..) if c ...]` or `[elt for v in xs if c ...]` (xs an owned list of any element
        type), built in a hidden list place that the caller moves into its target (the old target stays readable
        while the new list is built). `kind` is the legacy kind of the result list (int, float or str elements)."""
        P = self.P
        elem = I.F64 if kind == P.FLIST else I.STRV if kind == P.SLIST else I.I64
        if len(node.generators) != 1:
            raise NotS0('a comprehension with several generators')
        g = node.generators[0]
        it = g.iter
        over_range = isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == 'range' \
            and not it.keywords and 1 <= len(it.args) <= 3 and self.is_builtin('range')
        over_list = isinstance(it, ast.Name) and (self.is_list_name(it.id) or self.is_slist_name(it.id))
        if g.is_async or not isinstance(g.target, ast.Name) or not (over_range or over_list):
            raise NotS0('a comprehension that is not over range() or an owned list')
        name = g.target.id
        # (a comprehension has a scope of its own: an outer variable of the same name is another variable, as in
        # Python 3 and in the legacy build -- as long as the legacy types agree)
        if over_range:
            var_type, var_kind = I.I64, P.INT
        else:
            src_t = self.places[it.id].type.pointee
            var_type = src_t.args[0].args[0]
            var_kind = P.STR if var_type == I.STRV else P.FLT if var_type == I.F64 else P.INT
        outer = self.places.get(name)
        if name in self.params or name in self.scope_vars \
                or (outer is not None and outer.type.pointee != var_type) \
                or (outer is None and self.mentions_outside(name, node)) \
                or name in self.tracked:
            raise NotS0('a comprehension variable that is also used outside it')
        tmp = self.new_list_place(kind, 'comp')
        self.b.emit('list.reset', [self.list_ref(tmp)])
        if over_range:
            args = [self.as_int(self.expr(a)) for a in it.args]
            if len(args) == 1:
                lo, hi, step = self.const(I.I64, 0), args[0], self.const(I.I64, 1)
            elif len(args) == 2:
                lo, hi, step = args[0], args[1], self.const(I.I64, 1)
            else:
                lo, hi, step = args
            nargs = len(args)
            src = None
        else:
            src = self.container(it)
            lo, hi, step = self.const(I.I64, 0), self.b.value('list.len', [src], I.I64), self.const(I.I64, 1)
            nargs = 1
        ref = self.list_ref(tmp)
        if nargs < 3 and not g.ifs:
            # one allocation for a comprehension of known length (the legacy path reserves too)
            if elem != I.STRV:
                self.b.emit('list.reserve', [ref, self.b.value('sub', [hi, lo], I.I64, {'mode': 'nsw'})])
        index = I.Value(I.I64, hint=name if over_range else 'k')
        body = I.Region([index])

        def push():
            v = self.field_value(self.expr(node.elt), elem)
            self.b.emit('list.push', [ref, v])

        def conds(k):
            if k == len(g.ifs):
                push()
                return
            c = self.truthy(g.ifs[k])
            then, other = I.Region(), I.Region()
            self.in_region(then, fill=lambda: (conds(k + 1), self.b.emit('yield')))
            self.in_region(other, fill=lambda: self.b.emit('yield'))
            self.b.emit('if', [c], [], None, [then, other])

        def fill():
            # the variable exists only here: it is an SSA value in scope, and (for the legacy
            # type queries, which key on names) the kind of the elements for the duration
            if over_range:
                self.scope_vars[name] = index
            else:
                self.scope_vars[name] = self.b.value('list.get', [src, index], var_type, {'mode': 'nck', 'iter': True})
            had = self.ctx.types.get(name)
            self.ctx.types[name] = var_kind
            try:
                conds(0)
            finally:
                del self.scope_vars[name]
                if had is None:
                    del self.ctx.types[name]
                else:
                    self.ctx.types[name] = had
            self.b.emit('continue')
        self.loop_depth += 1
        try:
            self.in_region(body, fill=fill)
        finally:
            self.loop_depth -= 1
        self.b.emit('for.range', [lo, hi, step], [], {'args': nargs}, [body])
        return tmp

    def return_list(self, node):
        t = self.function.results[0]
        kind = self.list_kind_of(t)
        if isinstance(node, ast.Name) and self.is_list_name(node.id) and self.places[node.id].type.pointee == t:
            ref = self.container(node)
        else:
            if isinstance(node, (ast.Name, ast.Attribute)):
                raise NotS0('a list that something else names is returned (shared with its owner)')
            tmp = self.new_list_place(kind, 'ret')
            self.assign_list(lambda: self.list_ref(tmp), node, kind, dst='<return>')
            ref = self.list_ref(tmp)
        self.leave()
        self.b.emit('return', [ref])

    def store_field_list(self, target, value_node):
        """`t.f = <list>` for a numeric-list field of a struct parameter."""
        obj, cls, fkind = self.field_of(target)
        attrs = {'cls': cls, 'name': target.attr}

        def ref_fn():
            return self.b.value('field.list', [obj], LIST_F64 if fkind == self.P.FLIST else LIST_I64, dict(attrs))
        self.assign_list(ref_fn, value_node, fkind, dst='%s.%s' % (getattr(target.value, 'id', '?'), target.attr))

    def body_mutates(self, body, name, field=None):
        """Whether `body` rebinds or resizes the list `name` (or a list held in a field `field`)."""
        for st in body:
            for n in ast.walk(st):
                if isinstance(n, (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.For)):
                    ts = n.targets if isinstance(n, ast.Assign) else [n.target]
                    for t in ts:
                        if isinstance(t, ast.Subscript):
                            continue                  # an element store keeps the length
                        if isinstance(t, ast.Name) and t.id == name:
                            return True
                        if field is not None and isinstance(t, ast.Attribute) and t.attr == field:
                            return True
                if isinstance(n, ast.Delete):
                    return True
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in _LIST_MUTATORS:
                    v = n.func.value
                    if isinstance(v, ast.Name) and v.id == name:
                        return True
                    if field is not None and isinstance(v, ast.Attribute) and v.attr == field:
                        return True
        return False

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

    def global_type(self, name):
        """The IR type of a module variable (an int or a float, as the legacy path typed it)."""
        kind = self.ctx.modconsts.vars[name][0]
        if kind not in (self.P.INT, self.P.FLT):
            raise NotS0('the module variable %r is a %s' % (name, kind))
        return I.I64 if kind == self.P.INT else I.F64

    def store(self, name, v):
        if name in getattr(self.ctx, 'gdecl', ()):
            self.b.emit('global.store', [self.coerce(v, self.global_type(name))], [], {'name': name})
            return
        kp = self.kind_places.get(name)
        if kp is not None:
            t = I.I64 if v.type in (I.I64, I.I1) else v.type
            if t not in kp:
                raise NotS0('no place for %s of kind %s' % (name, t))
            self.b.emit('store', [kp[t], self.coerce(v, t)])
            return
        place = self.places.get(name)
        if place is None:
            raise NotS0('store to %r' % name)
        if place.type.pointee == BYTEARRAY:
            raise NotS0('a bytearray %r rebound to something other than bytearray()' % name)
        self.b.emit('store', [place, self.coerce(v, place.type.pointee)])

    def if_add(self, s):
        """`if t { x += K }` on an int local as `x += select(t, K, 0)` (ifadd.py); False when `s` is not that."""
        m = ifadd.match(s)
        if m is None:
            return False
        name, op, k, aug = m
        place = self.places.get(name)
        if name in self.kind_places or place is None or place.type.pointee != I.I64:
            return False
        c = self.truthy(s.test)
        amount = self.b.value('select', [c, self.const(I.I64, k), self.const(I.I64, 0)], I.I64)
        fake = ast.BinOp(left=ast.Name(id=name, ctx=ast.Load()), op=op, right=ast.Constant(value=k))
        ast.copy_location(fake, aug)
        ast.copy_location(fake.left, aug.target)
        ast.copy_location(fake.right, aug.value)
        fake._ail_range_src = aug
        self.store(name, self.binop_values(fake, self.expr(fake.left), amount))
        return True

    def stmt(self, s):
        self.cur_stmt = s
        self.apply_flow(s)
        if isinstance(s, ast.Assign):
            if len(s.targets) != 1:
                raise NotS0('assignment shape')
            if getattr(s, '_ail_member_check', None) and self.P._member_nan_applies(s, self.ctx):
                # a float list searched by count / index / remove: the run-time stop for a NaN argument (DIFFERENCES C119)
                # is emitted by the legacy lowering; the IR has no stop operation
                raise NotS0('list.count / index / remove of a float: NaN-argument stop (C119)')
            target = s.targets[0]
            if isinstance(target, (ast.Attribute, ast.Subscript)):
                return self.store_target(target, s.value)
            if not isinstance(target, ast.Name):
                raise NotS0('assignment shape')
            if self.is_dict_name(target.id):
                return self.assign_dict(target.id, s.value)
            if target.id in self.recs:
                return self.assign_rec(target.id, s.value)
            if target.id in self.rec_lists:
                return self.assign_rlist(target.id, s.value)
            if self.is_list_name(target.id):
                return self.assign_list_name(target.id, s.value)
            if self.is_slist_name(target.id):
                return self.assign_slist_name(target.id, s.value)
            if self.is_ba_name(target.id):
                return self.assign_ba(target.id, s.value)
            if self.is_obj_name(target.id):
                return self.assign_obj(target.id, s.value)
            self.store(target.id, self.expr(s.value))
        elif isinstance(s, ast.AnnAssign):
            if not isinstance(s.target, ast.Name):
                raise NotS0('annotated assignment shape')
            if s.value is not None:
                if self.is_dict_name(s.target.id):
                    return self.assign_dict(s.target.id, s.value)
                if s.target.id in self.rec_lists:
                    return self.assign_rlist(s.target.id, s.value)
                if self.is_list_name(s.target.id):
                    return self.assign_list_name(s.target.id, s.value)
                if self.is_slist_name(s.target.id):
                    return self.assign_slist_name(s.target.id, s.value)
                if self.is_ba_name(s.target.id):
                    return self.assign_ba(s.target.id, s.value)
                if self.is_obj_name(s.target.id):
                    return self.assign_obj(s.target.id, s.value)
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
        elif isinstance(s, (ast.Pass, ast.Global)):
            pass
        elif isinstance(s, ast.If) and self.if_add(s):
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
            self.loop_depth += 1
            try:
                self.in_region(body, fill=loop_body)
            finally:
                self.loop_depth -= 1
            self.b.emit('loop', [], [], None, [body])
        elif isinstance(s, ast.For):
            self.for_range(s)
        elif isinstance(s, ast.Return):
            if self.finally_loops:
                raise NotS0('return inside a finally body')
            if s.value is None:
                if self.function.results:
                    raise NotS0('bare return in a valued function')
                self.leave()
                self.b.emit('return', [])
                return
            if not self.function.results:
                raise NotS0('return with a value in a void function')
            if is_list(self.function.results[0]):
                return self.return_list(s.value)
            if self.function.results[0] == BYTEARRAY:
                if not (isinstance(s.value, ast.Name) and self.is_ba_name(s.value.id)):
                    raise NotS0('a bytearray result that is not an owned local')
                v = self.expr(s.value)
                self.leave()
                self.b.emit('return', [v])
                return
            v = self.coerce(self.expr(s.value), self.function.results[0])
            self.leave()
            self.b.emit('return', [v])
        elif isinstance(s, ast.Break):
            self.leaves_finally()
            self.b.emit('break')
        elif isinstance(s, ast.Continue):
            self.leaves_finally()
            self.b.emit('continue')
        elif isinstance(s, ast.Raise):
            self.raise_stmt(s)
        elif isinstance(s, ast.Assert):
            self.assert_stmt(s)
        elif isinstance(s, ast.Try):
            self.try_stmt(s)
        else:
            raise NotS0('statement %s' % type(s).__name__)

    def _close_yield(self):
        if not self.b.terminated():
            self.b.emit('yield')

    # ------------------------------------------------------------------ exceptions (S2)
    def leaves_finally(self):
        """break/continue may not leave a finally body (it would drop the exception or exit being
        carried out); a loop inside the finally body is fine."""
        if self.finally_loops and self.loop_depth <= self.finally_loops[-1]:
            raise NotS0('break/continue out of a finally body')

    def exception_code(self, name):
        code = self.P.EXC_NAMES.get(name)
        if code is None or not self.is_builtin(name):
            raise NotS0('exception %r' % name)
        if code >= 28:
            raise NotS0('the exception class %r (Exception and the user classes are caught by the legacy path)' % name)
        return code

    def raise_stmt(self, s):
        """`raise`, `raise E`, `raise E()`, `raise E("literal")`."""
        if self.link_units:
            raise NotS0('a raise in separately linked units')
        if s.cause is not None:
            raise NotS0('raise ... from')
        if s.exc is None:
            if self.handler_depth == 0:
                raise NotS0('a bare raise outside an except handler')
            self.b.emit('reraise')
            return
        e = s.exc
        if isinstance(e, ast.Name):
            self.b.emit('raise', [], [], {'code': self.exception_code(e.id), 'name': e.id, 'form': 'name'})
            return
        if isinstance(e, ast.Call) and isinstance(e.func, ast.Name) and not e.keywords \
                and e.func.id in self.P.EXC_NAMES:
            code = self.exception_code(e.func.id)
            if not e.args:
                self.b.emit('raise', [], [], {'code': code, 'name': e.func.id, 'form': 'new'})
                return
            if len(e.args) == 1 and isinstance(e.args[0], ast.Constant) and isinstance(e.args[0].value, str):
                if not e.args[0].value and self.P.exctext.ACTIVE:
                    raise NotS0('an empty message in a program that reads exception text (ValueError("") has one argument)')
                try:
                    e.args[0].value.encode('utf-8')
                except UnicodeEncodeError:
                    raise NotS0('a message that is not UTF-8')
                self.b.emit('raise', [], [], {'code': code, 'name': e.func.id, 'form': 'msg',
                                              'msg': e.args[0].value})
                return
            raise NotS0('an exception message that is not a str literal')
        raise NotS0('raise of %s' % type(e).__name__)

    def assert_stmt(self, s):
        """`assert c` / `assert c, "literal"`: AssertionError (code 9) when c is false."""
        if self.link_units:
            raise NotS0('an assert in separately linked units')
        code = self.exception_code('AssertionError')
        attrs = {'code': code, 'name': 'AssertionError', 'form': 'name'}
        if s.msg is not None:
            if not (isinstance(s.msg, ast.Constant) and isinstance(s.msg.value, str)):
                raise NotS0('an assert message that is not a str literal')
            if not s.msg.value and self.P.exctext.ACTIVE:
                raise NotS0('an empty assert message in a program that reads exception text')
            attrs.update(form='msg', msg=s.msg.value)
        c = self.truthy(s.test)
        ok, fail = I.Region(), I.Region()
        self.in_region(ok, fill=lambda: self.b.emit('yield'))
        self.in_region(fail, fill=lambda: self.b.emit('raise', [], [], attrs))
        self.b.emit('if', [c], [], None, [ok, fail])

    def new_place(self, name, t):
        """A hidden local (a flag): a place allocated at the head of the function body."""
        self.hidden += 1
        pname = '__ir_%s%d' % (name, self.hidden)
        if pname in self.ctx.locals:
            raise NotS0('name clash with %s' % pname)
        ins = I.Instr('local.alloc', [], [I.Value(I.place(t))], {'name': pname})
        self.function.body.instrs.insert(self.alloc_end, ins)
        self.alloc_end += 1
        return ins.result

    def try_stmt(self, s):
        if self.link_units:
            raise NotS0('a try in separately linked units')
        if s.finalbody:
            return self.try_finally(s)
        return self.try_except(s.body, s.handlers, s.orelse)

    def try_except(self, body, handlers, orelse):
        """try / except [as nothing] / else. A named handler (`except E as e`) needs the exception
        as a value (S4); the else body runs, outside the handlers' reach, after a body that did not
        raise (a flag set at the end of the body, as the legacy path does)."""
        P = self.P
        codes = []
        for h in handlers:
            if h.name and any(isinstance(n, ast.Name) and n.id == h.name for st in h.body for n in ast.walk(st)):
                raise NotS0('a named exception handler that reads the exception (stage S4e)')
            types = h.type.elts if isinstance(h.type, ast.Tuple) else [h.type]
            hc = []
            for t in types:
                if not isinstance(t, ast.Name):
                    raise NotS0('except %s' % type(t).__name__)
                hc.append(self.exception_code(t.id))
            codes.append(hc)
        if not handlers:
            raise NotS0('a try with no handler')
        flag = None
        if orelse:
            flag = self.new_place('else', I.I64)
            self.b.emit('store', [flag, self.const(I.I64, 0)])
        regions = []
        body_region = I.Region()

        def fill_body():
            self.stmts(body)
            if not self.b.terminated():
                if flag is not None:
                    self.b.emit('store', [flag, self.const(I.I64, 1)])
                self.b.emit('yield')
        self.in_region(body_region, fill=fill_body)
        regions.append(body_region)
        for h in handlers:
            region = I.Region()
            self.handler_depth += 1
            try:
                self.in_region(region, h.body, self._close_yield)
            finally:
                self.handler_depth -= 1
            regions.append(region)
        self.b.emit('try', [], [], {'kind': 'catch', 'codes': codes}, regions)
        if flag is not None:
            done = self.b.value('load', [flag], I.I64)
            ran = self.b.value('cmp.ne', [done, self.const(I.I64, 0)], I.I1)
            then, other = I.Region(), I.Region()
            self.in_region(then, orelse, self._close_yield)
            self.in_region(other, fill=lambda: self.b.emit('yield'))
            self.b.emit('if', [ran], [], None, [then, other])

    def try_finally(self, s):
        """try [/ except / else] / finally: the finally body runs once, after the protected part
        (its own region), whatever way that part was left; see emit_c for how the way is kept."""
        body_region, fin_region = I.Region(), I.Region()

        def fill_body():
            if s.handlers:
                self.try_except(s.body, s.handlers, s.orelse)
            else:
                self.stmts(s.body)
            if not self.b.terminated():
                self.b.emit('yield')
        self.in_region(body_region, fill=fill_body)
        self.finally_loops.append(self.loop_depth)
        try:
            self.in_region(fin_region, s.finalbody, self._close_yield)
        finally:
            self.finally_loops.pop()
        self.b.emit('try', [], [], {'kind': 'finally'}, [body_region, fin_region])

    def for_range(self, s):
        if s.orelse or getattr(s, 'par', None) is not None:
            raise NotS0('for ... else or a parallel for')
        it = s.iter
        if isinstance(s.target, ast.Name) and isinstance(it, ast.Name) and it.id in self.params \
                and self.params[it.id].type == BYTES:
            return self.for_bytes(s, self.params[it.id])
        if isinstance(s.target, ast.Name) and self.P._sys_attr_path(it) == 'sys.stdin':
            return self.for_stdin(s)
        if isinstance(s.target, ast.Name) and self.text_kind(it) == 'str':
            return self.for_str(s)
        if isinstance(s.target, ast.Name) and isinstance(it, (ast.List, ast.Tuple)) and it.elts \
                and self.literal_kind(it.elts) is not None:
            return self.for_literals(s)
        if isinstance(s.target, ast.Name) and not isinstance(it, ast.Name) and self.text_kind(it) == 'bytes':
            return self.for_bytes(s, self.bytes_arg(it))
        if isinstance(s.target, ast.Name) and isinstance(it, (ast.Name, ast.Attribute)) \
                and self.text_kind(it) is None and self.ba_expr(it):
            return self.for_bytearray(s, it)
        if isinstance(s.target, ast.Name) and isinstance(it, ast.Name) and it.id in self.places \
                and self.places[it.id].type.pointee == BYTES:
            return self.for_bytes(s, self.b.value('load', [self.places[it.id]], BYTES))
        if isinstance(s.target, ast.Name) and isinstance(it, ast.Name):
            found = self.list_iterable(it, s)
            if found is not None:
                return self.for_list(s, *found)
        if isinstance(s.target, ast.Name) and isinstance(it, ast.Attribute) and isinstance(it.value, ast.Name) \
                and self.object_param(it.value) is not None and self.field_list_arg(it):
            # `for x in t.order`: a numeric list field of a struct; the body must not resize or replace it (here, or in
            # a call: ownership.check_loops, Field(..) roots)
            if self.body_mutates(s.body, None, it.attr):
                raise NotS0('a loop over a field list that its body resizes or rebinds')
            return self.for_list(s, 'ref', self.container(it))
        if isinstance(s.target, ast.Name) and self.is_slist_expr(it):
            # `for w in line.split()`: the list lives in a hidden place for the duration of the loop
            tmp = self.new_place('it', LIST_STR)
            self.assign_slist(lambda: self.list_ref(tmp), it, '<for>')
            self.for_list(s, 'ref', self.list_ref(tmp))
            self.b.emit('list.reset', [self.list_ref(tmp)], [], {'drop': True})
            return
        if not (isinstance(s.target, ast.Name) and isinstance(it, ast.Call)
                and isinstance(it.func, ast.Name) and it.func.id == 'range' and not it.keywords
                and 1 <= len(it.args) <= 3 and self.is_builtin('range')):
            raise NotS0('for over something other than range(): %s' % self.src(it))
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
        self.loop_depth += 1
        try:
            self.in_region(body, fill=fill)
        finally:
            self.loop_depth -= 1
        self.b.emit('for.range', [lo, hi, step], [], {'args': len(args)}, [body])

    def list_iterable(self, it, s):
        """(kind, container value) of a `for x in <name>` over a numeric list the loop cannot
        resize: a read-only list parameter (a span), an owned local, or a local that became a borrow
        of a field. None when `it` names something else."""
        name = it.id
        if name in self.params and self.params[name].type.head == 'span':
            return 'span', self.params[name]
        if self.is_list_name(name) or self.is_slist_name(name):
            if self.body_mutates(s.body, name):
                raise NotS0('a loop over a list that its body resizes or rebinds')
            return 'ref', self.container(it)
        return None

    def for_list(self, s, how, base):
        """`for x in xs` over a list that cannot change length during the loop is
        `for k in range(len(xs)): x = xs[k]` with the read proven in range."""
        if s.target.id in self.params or s.target.id not in self.places:
            raise NotS0('for target %r' % s.target.id)
        if how == 'ref':
            n = self.b.value('list.len', [base], I.I64)
            elem = base.type.args[0].args[0]
        else:
            n = self.b.value('span.len', [base], I.I64)
            elem = base.type.args[0]
        lo, step = self.const(I.I64, 0), self.const(I.I64, 1)
        index = I.Value(I.I64, hint='k')
        body = I.Region([index])

        def fill():
            op = 'list.get' if how == 'ref' else 'span.get'
            self.store(s.target.id, self.b.value(op, [base, index], elem, {'mode': 'nck', 'iter': True}))
            self.stmts(s.body)
            if not self.b.terminated():
                self.b.emit('continue')
        self.loop_depth += 1
        try:
            self.in_region(body, fill=fill)
        finally:
            self.loop_depth -= 1
        loop = self.b.emit('for.range', [lo, n, step], [], {'args': 1}, [body])
        if how == 'ref':
            self.iter_loops.append((loop, base))

    def ba_expr(self, node):
        try:
            return self.P._etype(node, self.ctx) == 'bytearray'
        except Exception:
            return False

    def for_bytearray(self, s, it):
        """`for b in ba`: the legacy loop reads the data pointer and length once, before the first iteration."""
        if s.target.id in self.params or s.target.id not in self.places:
            raise NotS0('for target %r' % s.target.id)
        ba = self.container(it)
        if ba.type != BYTEARRAY:
            raise NotS0('for over %s' % ba.type)
        sp = self.b.value('span.of', [ba], I.T('span', I.T('u8')))
        n = self.b.value('span.len', [sp], I.I64)
        lo, step = self.const(I.I64, 0), self.const(I.I64, 1)
        index = I.Value(I.I64, hint='k')
        body = I.Region([index])

        def fill():
            self.store(s.target.id, self.b.value('span.get', [sp, index], I.I64, {'mode': 'nck'}))
            self.stmts(s.body)
            if not self.b.terminated():
                self.b.emit('continue')
        self.loop_depth += 1
        try:
            self.in_region(body, fill=fill)
        finally:
            self.loop_depth -= 1
        self.b.emit('for.range', [lo, n, step], [], {'args': 1}, [body])

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
        self.loop_depth += 1
        try:
            self.in_region(body, fill=fill)
        finally:
            self.loop_depth -= 1
        self.b.emit('for.range', [lo, n, step], [], {'args': 1}, [body])

    # ------------------------------------------------------------------ expressions
    def is_builtin(self, name):
        ctx = self.ctx
        return (name not in ctx.funcs and name not in getattr(ctx, 'classes', {})
                and name not in self.places and name not in self.params
                and name not in getattr(ctx, 'modconsts', {}))

    def truthy(self, node):
        if isinstance(node, ast.BoolOp):
            return self.boolop(node)            # a test, not a value: the plain bool
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
        if isinstance(node, (ast.BinOp, ast.UnaryOp)):
            folded = self.P.fold_int_constant(node)
            if folded is not None:
                return self.const(I.I64, folded)
        tk = self.text_kind(node)
        if tk is not None:
            return self.text_expr(node, tk)
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
            if node.id in self.scope_vars:
                return self.scope_vars[node.id]
            if self.is_list_name(node.id) or self.is_slist_name(node.id) or node.id in self.rec_lists \
                    or node.id in self.recs or self.is_dict_name(node.id):
                raise NotS0('a list %r used as a value (only list assignments, calls and returns take one)' % node.id)
            if node.id in self.places:
                place = self.places[node.id]
                return self.b.value('load', [place], place.type.pointee)
            if node.id in self.params:
                return self.params[node.id]
            if node.id in getattr(getattr(self.ctx, 'modconsts', None), 'vars', ()):
                return self.b.value('global.load', [], self.global_type(node.id), {'name': node.id})
            entry = getattr(self.ctx, 'modconsts', {}).get(node.id)
            if entry is not None and entry[0] in (self.P.INT, self.P.FLT):
                value = entry[1]
                if entry[0] == self.P.INT and isinstance(value, int) and not isinstance(value, bool):
                    return self.const(I.I64, value)
                if entry[0] == self.P.FLT and isinstance(value, float):
                    return self.const(I.F64, value)
            raise NotS0('name %r' % node.id)
        if isinstance(node, ast.BinOp):
            constant = int_constant(node)
            if type(constant) is int and -(1 << 63) <= constant < (1 << 63):
                return self.const(I.I64, constant)
            return self.binop(node)
        if isinstance(node, ast.UnaryOp):
            return self.unary(node)
        if isinstance(node, ast.BoolOp):
            if os.environ.get('AIL_SURFACE') == 'python' and not all(self.P._is_bool_expr(v, self.ctx)
                                                                    for v in node.values):
                raise NotS0('and/or used as a value on the Python surface (the operand that decided it)')
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
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in self.recs:
            place = self.recs[node.value.id].get(node.attr)
            if place is None:
                raise NotS0('unknown field %s' % node.attr)
            return self.b.value('load', [place], place.type.pointee)
        if isinstance(node, ast.Attribute):
            obj, cls, kind = self.field_of(node)
            if kind not in (self.P.INT, self.P.FLT):
                raise NotS0('field %s.%s of kind %r used as a value' % (cls, node.attr, kind))
            t = I.I64 if kind == self.P.INT else I.F64
            return self.b.value('field.get', [obj], t, {'cls': cls, 'name': node.attr})
        raise NotS0('expression %s' % type(node).__name__)

    # ------------------------------------------------------------------ objects and containers (S1)
    def object_param(self, node):
        """The IR value of `node` when it names a (non-optional) struct parameter or a struct local, else None."""
        if isinstance(node, ast.Name) and node.id in self.params:
            v = self.params[node.id]
            if v.type.head == 'obj' and v.type.args[0].head == 'class':
                return v
        if isinstance(node, ast.Name) and self.is_obj_name(node.id):
            return self.b.value('load', [self.places[node.id]], self.places[node.id].type.pointee)
        return None

    def is_obj_name(self, name):
        place = self.places.get(name)
        t = place.type.pointee if place is not None else None
        return t is not None and t.head == 'obj' and t.args[0].head == 'class'

    def assign_obj(self, name, node):
        """`p = Cls(args)` or `p = q` for a struct local: the legacy reference counts (a constructor result is
        adopted, another name is retained)."""
        place = self.places[name]
        cls = place.type.pointee.args[0].name
        if isinstance(node, ast.Name):
            src = self.object_param(node)
            if src is None or src.type != place.type.pointee:
                raise NotS0('a struct assigned from %s' % type(node).__name__)
            self.b.emit('obj.copyref', [place, src])
            return
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == cls
                and self.is_builtin(cls) is False and cls in getattr(self.ctx, 'classes', {})):
            raise NotS0('a struct built from %s' % type(node).__name__)
        self.construct(place, cls, node)

    def construct(self, place, cls, node):
        P, ctx = self.P, self.ctx
        info = ctx.classes[cls]
        if node.keywords or len(node.args) != len(info.init_params):
            raise NotS0('constructor %s() arguments' % cls)
        adopted = getattr(info, 'adopted_params', {}) or {}
        numeric = getattr(info, 'numeric_list_params', set()) or set()
        operands, abi = [], []
        for arg, (pname, kind) in zip(node.args, info.init_params):
            if kind in (P.LIST, P.FLIST, 'array') or pname in numeric:
                lk = adopted.get(pname)
                if lk not in (P.LIST, P.FLIST):
                    raise NotS0('constructor %s(%s): a list the constructor copies' % (cls, pname))
                if isinstance(arg, (ast.Name, ast.Attribute)):
                    raise NotS0('constructor %s(%s): a named list (stage S3e)' % (cls, pname))
                tmp = self.new_list_place(lk, 'ctor')
                self.assign_list(lambda tmp=tmp: self.list_ref(tmp), arg, lk, dst='<ctor>')
                operands.append(self.list_ref(tmp))
                abi.append('list')
            elif kind == P.INT:
                if P._etype(arg, ctx) != P.INT:
                    raise NotS0('constructor %s(%s): a float for an int' % (cls, pname))
                operands.append(self.as_int(self.expr(arg)))
                abi.append('value')
            elif kind == P.FLT:
                if P._etype(arg, ctx) not in (P.INT, P.FLT):
                    raise NotS0('constructor %s(%s) argument' % (cls, pname))
                operands.append(self.coerce(self.expr(arg), I.F64))
                abi.append('value')
            elif kind == P.BYTES:
                if self.text_kind(arg) != 'bytes':
                    raise NotS0('constructor %s(%s) argument' % (cls, pname))
                operands.append(self.expr(arg))
                abi.append('value')
            elif kind == P.STR:
                if self.text_kind(arg) != 'str':
                    raise NotS0('constructor %s(%s) argument' % (cls, pname))
                operands.append(self.expr(arg))
                abi.append('value')
            else:
                raise NotS0('constructor %s(%s): a field of kind %r' % (cls, pname, kind))
        self.b.emit('obj.init', [place] + operands, [], {'cls': cls, 'abi': abi})

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
        struct parameter (a borrow of the field's list), or an owned numeric-list local."""
        if isinstance(node, ast.Name):
            if self.is_list_name(node.id) or self.is_slist_name(node.id) or node.id in self.rec_lists:
                return self.list_ref(self.places[node.id])
            if self.is_ba_name(node.id):
                return self.b.value('load', [self.places[node.id]], BYTEARRAY)
            if node.id in self.places and self.places[node.id].type.pointee == BYTES:
                return self.b.value('load', [self.places[node.id]], BYTES)
        if isinstance(node, ast.Name) and node.id in self.params and (
                self.params[node.id].type in (BYTES, BYTEARRAY) or self.params[node.id].type.head == 'span'):
            return self.params[node.id]
        if isinstance(node, ast.Attribute):
            obj, cls, kind = self.field_of(node)
            if kind in (self.P.LIST, self.P.FLIST):
                elem = I.I64 if kind == self.P.LIST else I.F64
                return self.b.value('field.list', [obj], I.T('obj', I.T('list', elem)),
                                    {'cls': cls, 'name': node.attr})
            if kind == self.P.SLIST:
                return self.b.value('field.plist', [obj], PLIST, {'cls': cls, 'name': node.attr})
            if kind == 'bytearray':
                v = self.b.value('field.ba', [obj], BYTEARRAY, {'cls': cls, 'name': node.attr})
                self.fieldba.add(v)
                return v
            if kind == self.P.BYTES:
                return self.b.value('field.get', [obj], BYTES, {'cls': cls, 'name': node.attr})
            raise NotS0('field %s.%s of kind %r as a container' % (cls, node.attr, kind))
        raise NotS0('container operand %s' % (ast.dump(node)[:60],))

    def is_list(self, v):
        return v.type.head == 'obj' and v.type.args[0].head == 'list'

    def store_target(self, target, value_node):
        """`p.f = v` (scalar field) or `c[i] = v` (numeric list element). Python evaluates the
        right side first, then the target's parts."""
        if isinstance(target, ast.Attribute) and self.field_of(target)[2] in (self.P.LIST, self.P.FLIST):
            return self.store_field_list(target, value_node)
        v = self.expr(value_node)
        if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name) \
                and self.is_dict_name(target.value.id):
            if isinstance(target.slice, ast.Slice):
                raise NotS0('slice assignment')
            key = self.dict_key(target.slice)
            self.b.emit('dict.put', [self.places[target.value.id], key, self.as_int(v)])
            return
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
        self.guard_field_ba(base, target.slice)
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
        if isinstance(target.value, ast.Name) and self.is_dict_name(target.value.id):
            place = self.places[target.value.id]
            key = self.dict_key(target.slice)
            old = self.b.value('dict.need', [place, key], I.I64)
            new = self.apply_binop(s, old, self.expr(s.value))
            self.b.emit('dict.put', [place, key, self.as_int(new)])
            return
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
        if isinstance(node.value, ast.Name) and self.is_dict_name(node.value.id):
            return self.b.value('dict.need', [self.places[node.value.id], self.dict_key(node.slice)], I.I64)
        base = self.container(node.value)
        self.guard_field_ba(base, node.slice)
        if I.rec_elem(base.type) is not None:
            raise NotS0('an element of a list of records read as a value')
        index = self.as_int(self.expr(node.slice))
        if base.type == BYTES:
            return self.b.value('bytes.get', [base, index], I.I64, {'mode': self.index_mode(node)})
        if self.is_list(base):
            elem = base.type.args[0].args[0]
            return self.b.value('list.get', [base, index], elem,
                                {'mode': 'ck' if elem == I.STRV else self.index_mode(node)})
        if base.type == BYTEARRAY:
            return self.b.value('ba.get', [base, index], I.I64, {'mode': self.index_mode(node)})
        if base.type.head == 'span':
            mode = self.index_mode(node)
            if base.type == I.T('span', I.I64) and not getattr(self.ctx, 'checked_arrays', False):
                mode = 'nck'      # the legacy path reads an unchecked array parameter directly
            return self.b.value('span.get', [base, index], base.type.args[0], {'mode': mode})
        raise NotS0('subscript of %s' % base.type)

    def length(self, node):
        if isinstance(node, ast.Name) and self.is_dict_name(node.id):
            return self.b.value('dict.len', [self.places[node.id]], I.I64)
        if self.text_kind(node) == 'bytes' and not isinstance(node, ast.Name):
            return self.b.value('bytes.len', [self.expr(node)], I.I64)
        base = self.container(node)
        if base.type == BYTES:
            return self.b.value('bytes.len', [base], I.I64)
        if self.is_list(base):
            return self.b.value('list.len', [base], I.I64)
        if base.type == PLIST:
            return self.b.value('plist.len', [base], I.I64)
        if base.type.head == 'span':
            return self.b.value('span.len', [base], I.I64)
        if base.type == BYTEARRAY:
            return self.b.value('ba.len', [base], I.I64)
        raise NotS0('len() of %s' % base.type)

    def method_call(self, node, statement):
        """`c.append(v)`, `c.pop()`, `c.clear()` on a numeric list field."""
        func = node.func
        if isinstance(func.value, ast.Name) and func.value.id in self.rec_lists:
            return self.rlist_method(func.value.id, node, statement)
        if isinstance(func.value, ast.Name) and self.is_dict_name(func.value.id):
            if func.attr == 'get' and len(node.args) == 2 and not node.keywords:
                key = self.dict_key(node.args[0])
                default = self.as_int(self.expr(node.args[1]))
                return self.b.value('dict.get', [self.places[func.value.id], key, default], I.I64)
            raise NotS0('dictionary method %s()' % func.attr)
        if self.P._is_sys_exit_call(node) and statement:
            self.sys_exit_stmt(node)
            return None
        if func.attr in ('isdigit', 'isalpha', 'isalnum', 'isspace', 'isupper', 'islower', 'isdecimal',
                         'isnumeric') and self.text_kind(func.value) == 'str' and not node.args \
                and not node.keywords:
            return self.rt('str_' + func.attr, [self.expr(func.value)])
        if func.attr in ('startswith', 'endswith') and self.text_kind(func.value) == 'str' \
                and len(node.args) == 1 and not node.keywords and self.text_kind(node.args[0]) == 'str':
            return self.rt('str_' + func.attr, [self.expr(func.value), self.expr(node.args[0])])
        if node.keywords:
            raise NotS0('keywords to a method')
        if not isinstance(func.value, (ast.Attribute, ast.Name)):
            raise NotS0('method call on %s' % type(func.value).__name__)
        base = self.container(func.value)
        self.guard_field_ba(base, *node.args)
        if base.type == BYTEARRAY and func.attr == 'extend' and len(node.args) == 1 and statement \
                and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, bytes):
            self.b.emit('ba.extend_lit', [base], [], {'data': list(node.args[0].value)})
            return None
        if func.attr in ('find', 'rfind') and self.text_kind(func.value) == 'bytes' and 1 <= len(node.args) <= 3 \
                and not node.keywords:
            return self.bytes_search(node)
        if base.type == BYTEARRAY and func.attr == 'extend' and len(node.args) == 1 and statement \
                and self.text_kind(node.args[0]) == 'bytes':
            self.b.emit('ba.extend', [base, self.bytes_arg(node.args[0])])
            return None
        if base.type == BYTEARRAY and func.attr == 'clear' and not node.args and statement:
            self.b.emit('ba.clear', [base])
            return None
        if base.type == BYTEARRAY and func.attr == 'append' and len(node.args) == 1 and statement:
            v = self.field_value(self.expr(node.args[0]), I.I64)
            self.b.emit('ba.push', [base, v])
            return None
        if not self.is_list(base):
            raise NotS0('method of %s: %s' % (base.type, self.src(node)))
        elem = base.type.args[0].args[0]
        name = func.attr
        if elem == I.STRV:
            return self.slist_method(base, name, node, statement)
        if name == 'sort' and not node.args and statement and elem in (I.I64, I.F64):
            self.b.emit('list.sort', [base])
            return None
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
        if isinstance(op, (ast.In, ast.NotIn)) and a.type == I.STRV and b.type == I.STRV:
            return self.str_in(op, a, b)
        pred = {ast.Eq: 'eq', ast.NotEq: 'ne', ast.Lt: 'lt', ast.LtE: 'le', ast.Gt: 'gt',
                ast.GtE: 'ge'}.get(type(op))
        if pred is None:
            raise NotS0('comparison %s' % type(op).__name__)
        if a.type == I.STRV and b.type == I.STRV:
            return self.str_compare(op, a, b)
        if not (a.type.is_scalar and b.type.is_scalar):
            raise NotS0('comparison of %s and %s' % (a.type, b.type))
        if {a.type, b.type} == {I.I64, I.F64}:
            return self.b.value('cmp.' + pred, [a, b], I.I1)
        if I.F64 in (a.type, b.type):
            a, b = self.coerce(a, I.F64), self.coerce(b, I.F64)
        elif I.I64 in (a.type, b.type):
            a, b = self.coerce(a, I.I64), self.coerce(b, I.I64)
        return self.b.value('cmp.' + pred, [a, b], I.I1)

    def compare(self, node):
        """`a < b < c`: b evaluated once, c only when a < b (nested regions, so every later
        comparison sits inside the region where its left operand is defined)."""
        if len(node.ops) == 1 and isinstance(node.ops[0], (ast.In, ast.NotIn)) \
                and isinstance(node.comparators[0], ast.Name) and self.is_dict_name(node.comparators[0].id):
            return self.dict_in(node)
        if len(node.ops) == 1 and isinstance(node.ops[0], (ast.In, ast.NotIn)) \
                and isinstance(node.comparators[0], ast.Name) and self.is_slist_name(node.comparators[0].id):
            return self.slist_in(node)
        if len(node.ops) == 1 and isinstance(node.ops[0], (ast.In, ast.NotIn)) \
                and self.plist_field(node.comparators[0]) is not None:
            return self.plist_in(node)
        return self._chain(self.expr(node.left), node.ops, node.comparators)

    def plist_field(self, node):
        """(object, class, name) when `node` is `p.f` for a struct parameter or local `p` and a list[str] field `f`."""
        if not (isinstance(node, ast.Attribute) and self.object_param(node.value) is not None):
            return None
        obj, cls, kind = self.field_of(node)
        return (obj, cls, node.attr) if kind == self.P.SLIST else None

    def plist_in(self, node):
        """`x in o.f` / `x not in o.f` for a list[str] field: a scan by value (`ail_pslist_has`)."""
        if self.text_kind(node.left) != 'str':
            raise NotS0('membership of something that is not a str in a list of str')
        item = self.expr(node.left)
        found = self.b.value('plist.has', [self.container(node.comparators[0]), item], I.I1)
        if isinstance(node.ops[0], ast.NotIn):
            return self.b.value('cmp.eq', [found, self.const(I.I1, False)], I.I1)
        return found

    def slist_in(self, node):
        """`x in xs` / `x not in xs` for a list of str: a scan by value (`ail_slist_has`)."""
        if self.text_kind(node.left) != 'str':
            raise NotS0('membership of something that is not a str in a list of str')
        item = self.expr(node.left)
        found = self.b.value('list.has', [self.container(node.comparators[0]), item], I.I1)
        if isinstance(node.ops[0], ast.NotIn):
            return self.b.value('cmp.eq', [found, self.const(I.I1, False)], I.I1)
        return found

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
        if types[0] == types[1] and types[0] in (I.STRV, BYTES):
            t = types[0]
        else:
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
        if f == 'print' and statement:
            self.print_stmt(node)
            return None
        if f in ('_ail_sort_perm', '_ail_sort_apply') and statement:
            return self.keyed_sort(f, node)
        if node.keywords:
            raise NotS0('keywords to %s()' % f)
        if f == 'ord' and len(args) == 1 and isinstance(args[0], ast.Constant) \
                and isinstance(args[0].value, str) and len(args[0].value) == 1:
            return self.const(I.I64, ord(args[0].value))
        if f == 'abs' and len(args) == 1:
            v = self.expr(args[0])
            if v.type == I.F64:
                return self.b.value('fabs', [v], I.F64)
            v = self.coerce(v, I.I64)
            neg = self.b.value('neg', [v], I.I64, {'mode': 'ck' if self.strict else 'nsw'})
            zero = self.const(v.type, 0)
            c = self.b.value('cmp.lt', [v, zero], I.I1)
            return self.b.value('select', [c, neg, v], v.type)
        if f in ('min', 'max') and len(args) == 2:
            a, b = self.expr(args[0]), self.expr(args[1])
            t = I.F64 if I.F64 in (a.type, b.type) else I.I64
            a, b = self.coerce(a, t), self.coerce(b, t)
            if t == I.F64:
                # CPython keeps the first argument unless the second is smaller (larger): NaN stays first (silent6)
                c = self.b.value('cmp.lt' if f == 'min' else 'cmp.gt', [b, a], I.I1)
                return self.b.value('select', [c, b, a], t)
            c = self.b.value('cmp.lt' if f == 'min' else 'cmp.gt', [a, b], I.I1)
            return self.b.value('select', [c, a, b], t)
        if f == 'print' and statement:
            self.print_stmt(node)
            return None
        if f == 'len' and len(args) == 1 and self.text_kind(args[0]) == 'str':
            return self.text_len(args[0])
        if f == 'len' and len(args) == 1 and P._is_sys_argv(args[0]):
            return self.rt('argv_len', [])
        if f == 'len' and len(args) == 1 and self.text_kind(args[0]) == 'bytes' \
                and not isinstance(args[0], ast.Name):
            return self.b.value('bytes.len', [self.bytes_arg(args[0])], I.I64)
        if f == 'len' and len(args) == 1:
            return self.length(args[0])
        if f in ('wrapping_add', 'wrapping_sub', 'wrapping_mul') and len(args) == 2:
            a, b = self.as_int(self.expr(args[0])), self.as_int(self.expr(args[1]))
            return self.b.value(f.split('_')[1], [a, b], I.I64, {'mode': 'wrap'})
        if f == 'ord' and len(args) == 1 and self.text_kind(args[0]) == 'str' \
                and (isinstance(args[0], ast.Subscript)
                     or (isinstance(args[0], ast.Name) and args[0].id in self.onecp)):
            return self.rt('str_point', [self.expr(args[0])])
        if f == 'float' and len(args) == 1:
            v = self.expr(args[0])
            if v.type == I.STRV:
                return self.rt('str_to_float', [v])
            return self.coerce(v, I.F64)
        if f == 'int' and len(args) == 1:
            v = self.expr(args[0])
            if v.type == I.STRV:
                return self.rt('str_to_int', [v])
            if v.type == BYTES:
                return self.rt('bytes_to_int', [v])
            if v.type == I.F64:
                return self.b.value('fptosi', [v], I.I64, {'mode': 'ck'})
            return self.coerce(v, I.I64)
        if f == 'write_stdout_bytes' and len(args) == 1 and statement and isinstance(args[0], ast.Call) \
                and isinstance(args[0].func, ast.Name) and args[0].func.id in ctx.funcs \
                and args[0].func.id not in self.places and args[0].func.id not in self.params \
                and ctx.funcs[args[0].func.id][1] == 'bytearray':
            # the bytearray a call returns, written and released at once
            tmp = self.new_place('bat', BYTEARRAY)
            self.user_call(args[0].func.id, args[0], False, ba_dst=tmp)
            self.b.emit('ba.write', [self.b.value('load', [tmp], BYTEARRAY)])
            self.b.emit('ba.drop', [tmp])
            return None
        if f == 'write_stdout_bytes' and len(args) == 1 and statement:
            v = self.bytes_arg(args[0]) if self.text_kind(args[0]) == 'bytes' else self.expr(args[0])
            if v.type == BYTES:
                self.rt('write_stdout_bytes', [v])
                return None
            if v.type != BYTEARRAY:
                raise NotS0('write_stdout_bytes() of %s' % v.type)
            self.b.emit('ba.write', [v])
            return None
        raise NotS0('builtin %s()' % f)

    def keyed_sort(self, f, node):
        """The two statements sortkeys.py leaves for `xs.sort(key=...)` / `sorted(xs, key=...)`: the permutation
        of the key columns, and the reorder of the list by it (the legacy KEYSORT runtime)."""
        def owned(arg, what, numeric_only=False):
            if not (isinstance(arg, ast.Name) and (self.is_list_name(arg.id) or self.is_slist_name(arg.id))):
                raise NotS0('%s is not an owned local list' % what)
            if arg.id in self.ctx.kind:
                raise NotS0('%s is a parameter' % what)
            return arg
        if node.keywords:
            raise NotS0('keywords to %s()' % f)
        if f == '_ail_sort_perm':
            if len(node.args) < 3 or not isinstance(node.args[1], ast.Constant) \
                    or not isinstance(node.args[1].value, bool):
                raise NotS0('a malformed sort permutation call')
            perm = owned(node.args[0], 'the sort permutation')
            if self.places[perm.id].type.pointee != LIST_I64:
                raise NotS0('the sort permutation is not a list of int')
            cols = [owned(a, 'a sort key column') for a in node.args[2:]]
            refs = [self.container(perm)] + [self.container(c) for c in cols]
            self.b.emit('list.sortperm', refs, [], {'rev': 1 if node.args[1].value else 0})
            return None
        if len(node.args) != 2:
            raise NotS0('a malformed sort reorder call')
        xs = owned(node.args[0], 'the sorted list')
        perm = owned(node.args[1], 'the sort permutation')
        if self.places[perm.id].type.pointee != LIST_I64 or xs.id == perm.id:
            raise NotS0('the sort permutation is not a list of int')
        self.b.emit('list.permute', [self.container(xs), self.container(perm)])
        return None

    def user_call(self, f, node, statement, list_dst=None, list_kind=None, ba_dst=None):
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
        elif ret == 'bytearray':
            if ba_dst is None:
                raise NotS0('the bytearray %s() returns is used as a value (stage S3b)' % f)
            results = [BYTEARRAY]
        else:
            results = [self.kind_type(ret, '%s() result' % f, owned=True)]
        if ba_dst is not None and results != [BYTEARRAY]:
            raise NotS0('%s() does not return a bytearray' % f)
        if results and is_list(results[0]) and list_dst is None:
            raise NotS0('the list %s() returns is used as a value (stage S3b)' % f)
        if list_dst is not None and not (results and is_list(results[0])
                                         and results[0] == (LIST_F64 if list_kind == P.FLIST else LIST_I64)):
            raise NotS0("%s() does not return a list of the target's kind" % f)
        order = sorted(range(len(arg_nodes)), key=lambda i: (getattr(arg_nodes[i], 'lineno', 0),
                                                              getattr(arg_nodes[i], 'col_offset', 0)))
        values = [None] * len(arg_nodes)
        temps = []
        for i in order:
            a = arg_nodes[i]
            if isinstance(a, ast.Name) and self.is_list_name(a.id):
                # an owned list passed to a read-only list parameter: the callee gets a view of it
                # for the duration of the call and cannot resize it (it has no way to name it)
                if params[i][1] not in ('array', P.FLIST):
                    raise NotS0('list argument to a parameter of kind %r' % (params[i][1],))
                values[i] = self.container(a)
            elif isinstance(a, ast.Attribute) and isinstance(a.value, ast.Name) and self.field_list_arg(a):
                # a struct field's list lent to a read-only list parameter (S3b): fine while the callee
                # can neither resize nor replace that field's list behind the view
                if params[i][1] not in ('array', P.FLIST):
                    raise NotS0('list argument to a parameter of kind %r' % (params[i][1],))
                obj, cls, fkind = self.field_of(a)
                summary = self.summaries.get(symbol)
                tag = 'Field(%s,%s)' % (cls, a.attr)
                if summary is None or summary.unknown                         or any(w in ('Spine(%s)' % tag, 'Rebind(%s)' % tag) for w in summary.writes):
                    raise NotS0('the field list %s.%s is lent to %s(), which may resize or replace it'
                                % (a.value.id, a.attr, f))
                values[i] = self.container(a)
            elif isinstance(a, ast.Call) and isinstance(a.func, ast.Name) and a.func.id in ctx.funcs                     and a.func.id not in self.places and a.func.id not in self.params                     and ctx.funcs[a.func.id][1] in (P.LIST, P.FLIST):
                # the list a call returns, passed straight on: a temporary this call owns, lent to the
                # callee and dropped once the call is over
                if params[i][1] not in ('array', P.FLIST):
                    raise NotS0('list argument to a parameter of kind %r' % (params[i][1],))
                tkind = ctx.funcs[a.func.id][1]
                tmp = self.new_list_place(tkind, 'arg')
                self.user_call(a.func.id, a, False, list_dst=lambda tmp=tmp: self.list_ref(tmp), list_kind=tkind)
                temps.append(tmp)
                values[i] = self.list_ref(tmp)
            else:
                values[i] = self.expr(a)
        if any(is_list(v.type) for v in values):
            for a in arg_nodes:
                if any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                       and n.func.attr in _LIST_MUTATORS for n in ast.walk(a)):
                    raise NotS0('a list passed in a call whose other arguments change a list')
        args = []
        arg_abi = []
        own_abi = dict(zip(self.function.params, self.function.attrs.get('abi') or []))
        for v, t, (pname, pkind) in zip(values, param_types, params):
            if v.type == I.F64 and t != I.F64:
                raise NotS0('float argument to an int parameter of %s()' % f)
            if t.head == 'span':
                want = 'array' if pkind == 'array' else 'flist'
                if is_list(v.type) and v.type.args[0].args[0] == t.args[0]:
                    arg_abi.append(want)
                    args.append(v)
                    continue
                if v.type != t or own_abi.get(v) != want:
                    raise NotS0('list argument to %s() is not a parameter passed through' % f)
                arg_abi.append(want)
                args.append(v)
                continue
            if is_list(v.type):
                raise NotS0('list argument to a non-list parameter of %s()' % f)
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
        if ba_dst is not None:
            if 'abi' in attrs:
                raise NotS0('a bytearray result with list arguments')
            self.b.emit('ba.call', [ba_dst] + args, [], attrs)
            self.drop_temps(temps)
            return None
        if list_dst is not None:
            # the destination is named after the arguments are evaluated; the call comes first, the
            # old content of the destination is freed once the new list has been adopted
            self.b.emit('list.call', [list_dst()] + args, [], attrs)
            self.drop_temps(temps)
            return None
        ins = self.b.emit('call', args, results, attrs)
        self.drop_temps(temps)
        return ins.results[0] if results else None

    def field_list_arg(self, node):
        """Whether `node` is `p.f` for a struct parameter `p` whose field `f` is a numeric list."""
        try:
            obj, cls, kind = self.field_of(node)
        except NotS0:
            return False
        return kind in (self.P.LIST, self.P.FLIST)

    def drop_temps(self, temps):
        for t in temps:
            self.b.emit('list.reset', [self.list_ref(t)], [], {'drop': True})


def lower(P, fn, ctx, sig, recursive, cname, pending=(), link_units=False, summaries=None):
    """(IR function, its one-function program) for the S0 subset; NotS0 otherwise."""
    lowering = Lowering(P, fn, ctx, sig, recursive, cname, pending, link_units, summaries)
    try:
        f = lowering.run()
    finally:
        # the kinds the flow analysis put in the legacy context are the IR's own business
        for n, t in lowering.__dict__.get('saved_types', {}).items():
            if t is None:
                ctx.types.pop(n, None)
            else:
                ctx.types[n] = t
    return f, lowering.program
