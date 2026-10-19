# -*- coding: utf-8 -*-
"""unified.py -- AIL_UNIFIED=1 prototype: type inference and unboxing on the general path
(docs/design/UNIFIED_IR.md).

The general path (pyboxed2.py) accepts the program as it is and gives every value the boxed
representation (`ail_obj` in a GC-rooted frame slot, every operation a runtime call). This pass
runs before the general path emits any function and proves, for each local variable of each
function it can analyse, one of

    int    an int64 (the general path's own int: an overflow is the same AIL_LIMIT stop)
    float  a C double (the general path heap-boxes every float)
    bool   a C int 0/1
    obj    anything else: stays boxed, as today

A proven variable lives in a C local instead of a frame slot; operations whose operands are
all proven are emitted as C (with the general runtime's own checks: overflow, division by
zero, shifts); everything else is the general path's code, unchanged. Boxing happens at the
edges: a proven value read where a boxed one is needed (a call argument, a container element,
print) is boxed there (`ail_box_int` does not allocate, `ail_box_float` does); a value whose
result type is fixed by the language (`len()`, `not`, `in`, `int()`, ...) is computed boxed and
unboxed.

Top-level functions whose every reference is a direct positional call also get their
parameters and result specialised from the types at their call sites (one specialisation per
function: the join of every call site; one boxed call site makes the parameter boxed).

The analysis is a forward abstract interpretation over a flat lattice, run to a whole-program
fixed point: bottom (no information yet) < int, float, bool < obj (widened). A variable's
storage is the join of every value assigned to it (one representation per variable for the
whole function), and a variable is only unboxed when every read of it is definitely assigned
(an unbound read must still raise UnboundLocalError, which only the frame slot can tell).

Anything the emitter reaches that this pass did not plan for (a name read through a path that
bypasses the hooks) raises `Conflict`; pyboxed2.build() then demotes that variable or function to
boxed and compiles again. Without AIL_UNIFIED nothing here runs and the C is byte-identical.
"""
import ast
import os

INT, FLOAT, BOOL, OBJ = 'int', 'float', 'bool', 'obj'
BOT = None
SCALAR = (INT, FLOAT, BOOL)
CTYPE = {INT: 'int64_t', FLOAT: 'double', BOOL: 'int'}
KIND = {INT: 'int', FLOAT: 'float', BOOL: 'bool'}       # pyboxed2's own kind names
_I64_MIN, _I64_MAX = -(1 << 63), (1 << 63) - 1
_EXACT = 1 << 53


def enabled():
    return os.environ.get('AIL_UNIFIED', '').strip().lower() in ('1', 'on', 'yes', 'true')


class Conflict(Exception):
    """The emitter reached a proven variable (or a specialised function) through a path this pass
    does not handle: build() demotes `key` ((function, variable) or (function, '*')) and retries."""

    def __init__(self, key, why=''):
        Exception.__init__(self, '%s: %s' % (key, why))
        self.key = key
        _REASONS.append('%s:%s %s' % (key[0], key[1], why))


_REASONS = []


def join(a, b):
    if a is BOT:
        return b
    if b is BOT:
        return a
    return a if a == b else OBJ


STATS = []          # one dict per compiled program (AIL_UNIFIED_STATS=path appends JSON lines)


# ============================================================================== the analysis

class FnPlan(object):
    def __init__(self, name, info, node):
        self.name = name                 # key: the C name (unique across functions and methods)
        self.info = info
        self.node = node
        self.params = list(info['params'])
        self.locals = set()              # every local name of the function
        self.bad = set()                 # locals that stay boxed whatever their values
        self.vtype = {}                  # local -> lattice value
        self.spec = False                # parameters / result specialised
        self.ptypes = [OBJ] * len(self.params)
        self.ret = OBJ
        self.calls_in = []               # (caller plan or None, call node)

    def unboxed(self, name):
        t = self.vtype.get(name)
        return t in SCALAR and name not in self.bad

    def cvar(self, name):
        return 'u_' + name


def _parents(node):
    par = {}
    for p in ast.walk(node):
        for c in ast.iter_child_nodes(p):
            par[id(c)] = p
    return par


def _is_range_call(n, plan_names):
    return (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'range'
            and 'range' not in plan_names and 1 <= len(n.args) <= 3 and not n.keywords
            and not any(isinstance(a, ast.Starred) for a in n.args))


def _own_nodes(fn):
    """The nodes of `fn`'s own scope: not the bodies of nested lambdas / defs / classes."""
    out = []
    stack = list(fn.body)
    while stack:
        n = stack.pop()
        out.append(n)
        if isinstance(n, (ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        stack.extend(ast.iter_child_nodes(n))
    return out


def _always_returns(stmts):
    for s in stmts:
        if isinstance(s, (ast.Return, ast.Raise)):
            return True
        if isinstance(s, ast.If) and s.orelse and _always_returns(s.body) and _always_returns(s.orelse):
            return True
    return False


ALL = object()      # the definitely-assigned set after a statement that does not complete


def _inter(a, b):
    if a is ALL:
        return b
    if b is ALL:
        return a
    return a & b


class _DefAssign(object):
    """Definite assignment over a function body: every local read where it may be unbound."""

    def __init__(self, locals_):
        self.locals = locals_
        self.maybe = set()

    def reads(self, node, assigned):
        if node is None:
            return
        for n in ast.walk(node):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id in self.locals:
                if assigned is not ALL and n.id not in assigned:
                    self.maybe.add(n.id)

    def targets(self, t):
        return {n.id for n in ast.walk(t) if isinstance(n, ast.Name)}

    def block(self, stmts, assigned):
        for s in stmts:
            if assigned is ALL:
                return ALL
            assigned = self.stmt(s, assigned)
        return assigned

    def stmt(self, s, a):
        if isinstance(s, ast.Assign):
            self.reads(s.value, a)
            for t in s.targets:
                if not isinstance(t, ast.Name):
                    self.reads(t, a)
            return a | set().union(*[self.targets(t) for t in s.targets])
        if isinstance(s, ast.AnnAssign):
            self.reads(s.value, a)
            return a | self.targets(s.target) if s.value is not None else a
        if isinstance(s, ast.AugAssign):
            self.reads(s.value, a)
            self.reads(ast.Name(id=s.target.id, ctx=ast.Load()) if isinstance(s.target, ast.Name) else s.target, a)
            return a | self.targets(s.target)
        if isinstance(s, ast.If):
            self.reads(s.test, a)
            return _inter(self.block(s.body, set(a)), self.block(s.orelse, set(a)))
        if isinstance(s, ast.While):
            self.reads(s.test, a)
            self.block(s.body, set(a))
            self.block(s.orelse, set(a))
            return a
        if isinstance(s, ast.For):
            self.reads(s.iter, a)
            self.block(s.body, a | self.targets(s.target))
            self.block(s.orelse, set(a))
            return a
        if isinstance(s, (ast.Return, ast.Raise)):
            for c in ast.iter_child_nodes(s):
                self.reads(c, a)
            return ALL
        if isinstance(s, (ast.Break, ast.Continue)):
            return ALL
        if isinstance(s, ast.Try):
            body = self.block(s.body, set(a))
            body = self.block(s.orelse, body) if body is not ALL else ALL
            out = body
            for h in s.handlers:
                out = _inter(out, self.block(h.body, set(a)))
            if s.finalbody:
                self.block(s.finalbody, set(a))
            return a if out is ALL else out
        if isinstance(s, ast.With):
            for item in s.items:
                self.reads(item.context_expr, a)
            body = self.block(s.body, set(a))
            return a if body is ALL else body
        if isinstance(s, ast.Match):
            self.reads(s.subject, a)
            for case in s.cases:
                self.block(case.body, set(a))
            return a
        # anything else (Expr, Assert, Delete, Pass, Global, ...): reads with `a`, no new binding
        for c in ast.iter_child_nodes(s):
            if isinstance(c, ast.expr):
                self.reads(c, a)
        return a


class Plan(object):
    """The whole-program result: the FnPlans by C name, the specialised functions by Python name,
    the module constants."""

    def __init__(self):
        self.fns = {}            # cname -> FnPlan
        self.spec = {}           # python name of a specialised top-level function -> FnPlan
        self.gconst = {}         # module constant name -> lattice value
        self.need_generic = set()  # specialised functions whose boxed body is still reachable
        self.stats = {}


def analyze(comp, tree, demote):
    """`comp` is the pyboxed2 Compiler with every function and class registered."""
    plan = Plan()
    names_all = set(comp.functions)
    plan.fn_names = set(comp.functions)
    plan.module_names = (set(comp.module_names) | set(comp.from_imports) | set(comp.module_aliases)
                         | set(comp.classes))
    demote = set(demote or ())

    # ---- module constants: one top-level `NAME = <int/float/bool literal>`, never stored elsewhere
    stores = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            stores[n.id] = stores.get(n.id, 0) + 1
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            for nm in n.names:
                stores[nm] = stores.get(nm, 0) + 2
    for s in tree.body:
        tgt = val = None
        if isinstance(s, ast.Assign) and len(s.targets) == 1 and isinstance(s.targets[0], ast.Name):
            tgt, val = s.targets[0].id, s.value
        elif isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name) and s.value is not None:
            tgt, val = s.target.id, s.value
        if tgt is None or stores.get(tgt) != 1 or tgt in comp.functions or tgt in comp.classes:
            continue
        neg = False
        if isinstance(val, ast.UnaryOp) and isinstance(val.op, ast.USub):
            neg, val = True, val.operand
        if isinstance(val, ast.Constant):
            v = val.value
            if isinstance(v, bool):
                if not neg:
                    plan.gconst[tgt] = BOOL
            elif isinstance(v, int) and _I64_MIN <= (-v if neg else v) <= _I64_MAX:
                plan.gconst[tgt] = INT
            elif isinstance(v, float):
                plan.gconst[tgt] = FLOAT
    plan.gconst = {k: v for k, v in plan.gconst.items() if ('<module>', k) not in demote}

    # ---- the functions this pass analyses
    infos = [(name, info) for name, info in comp.functions.items()]
    for cname in comp.class_order:
        for mname, info in comp.classes[cname]['methods'].items():
            infos.append((info['cname'], info))
    for key, info in infos:
        node = info['node']
        cname = info['cname']
        if (cname, '*') in demote or info.get('generator') or info.get('lru_cache'):
            continue
        own = _own_nodes(node)
        if any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Yield, ast.YieldFrom,
                              ast.Await)) for n in own):
            continue
        if any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
               and n.func.id in ('locals', 'vars', 'eval', 'exec', 'globals') for n in own):
            continue
        fp = FnPlan(cname, info, node)
        fp.is_method = info.get('is_method', False)
        fp.pyname = node.name
        par = _parents(node)
        params = set(info['all_params'])
        assigned = set()
        for n in own:
            if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
                assigned.add(n.id)
            elif isinstance(n, ast.ExceptHandler) and n.name:
                assigned.add(n.name)
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                assigned.update((a.asname or a.name).split('.')[0] for a in n.names)
            elif isinstance(n, (ast.MatchAs, ast.MatchStar)) and n.name:
                assigned.add(n.name)
            elif isinstance(n, ast.MatchMapping) and n.rest:
                assigned.add(n.rest)
        globals_ = set()
        for n in own:
            if isinstance(n, (ast.Global, ast.Nonlocal)):
                globals_.update(n.names)
        fp.locals = (params | assigned) - globals_
        fp.bad = set(globals_)
        # binding sites this pass can lower; any other one keeps the name boxed
        for n in own:
            if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
                p = par.get(id(n))
                ok = False
                if isinstance(n.ctx, ast.Store):
                    if isinstance(p, ast.Assign) and any(t is n for t in p.targets):
                        ok = True
                    elif isinstance(p, ast.AnnAssign) and p.target is n and p.value is not None:
                        ok = True
                    elif isinstance(p, ast.AugAssign) and p.target is n:
                        ok = True
                    elif isinstance(p, ast.For) and p.target is n and _is_range_call(p.iter, names_all):
                        ok = True
                if not ok:
                    fp.bad.add(n.id)
            elif isinstance(n, ast.ExceptHandler) and n.name:
                fp.bad.add(n.name)
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                fp.bad.update((a.asname or a.name).split('.')[0] for a in n.names)
            elif isinstance(n, (ast.MatchAs, ast.MatchStar)) and n.name:
                fp.bad.add(n.name)
            elif isinstance(n, ast.MatchMapping) and n.rest:
                fp.bad.add(n.rest)
            elif isinstance(n, (ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                fp.bad.update(x.id for x in ast.walk(n) if isinstance(x, ast.Name))
        # the parameters that are not plain positional ones (keyword-only, *args, **kwargs) stay boxed
        fp.bad.update(set(info['all_params']) - set(info['params']))
        da = _DefAssign(fp.locals)
        da.block(node.body, set(params))
        fp.bad |= da.maybe
        fp.bad |= {v for (f, v) in demote if f == cname}
        for v in fp.locals:
            fp.vtype[v] = OBJ if v in fp.bad else BOT
        fp.own = own
        plan.fns[cname] = fp

    # ---- specialised variants. A top-level function with plain positional parameters gets, beside its
    # boxed body (still called by every boxed caller), a second body `pfu_<name>` with unboxed parameters and
    # result, for the types its analysed direct call sites pass. The boxed body starts with a guard: when the
    # arguments it receives carry those types it calls the specialised body (so a call from module code, a
    # generator, map(f, ...) or a function value also gets it); otherwise it runs as today.
    for name, info in comp.functions.items():
        base = plan.fns.get(info['cname'])
        if base is None or info['kwonly'] or info['vararg'] or info['kwarg'] or info['defaults']:
            continue
        if info['node'].decorator_list or name in comp.module_names or name in getattr(comp, 'mix_typed', {}):
            continue
        if not info['params'] and not _always_returns(info['node'].body):
            continue
        if any(isinstance(n, (ast.Try, ast.With)) for n in base.own):
            continue        # a return through a finally keeps its value in a frame slot
        if ('pfu_' + name, '*') in demote:
            continue
        # a local of some function with the same name would make the call go elsewhere
        if any(name in p.locals for p in plan.fns.values()):
            continue
        sp = FnPlan('pfu_' + name, info, info['node'])
        sp.is_method = False
        sp.pyname = name
        sp.locals = set(base.locals)
        sp.bad = set(base.bad) | {v for (f, v) in demote if f == sp.name}
        sp.vtype = {v: (OBJ if v in sp.bad else BOT) for v in sp.locals}
        sp.own = base.own
        sp.spec = True
        sp.ptypes = [BOT] * len(sp.params)
        sp.ret = BOT
        # a parameter annotation is a hint, not a proof: it is used only when no analysed call site says more,
        # and the entry guard of the boxed body checks it on every call that comes in boxed
        sp.hints = [_ann_type(a.annotation) for a in info['node'].args.args]
        plan.fns[sp.name] = sp
        plan.spec[name] = sp
    plan.generic_sites = set()       # (caller C name, id(call)): calls that go to the boxed body
    owner = {}
    for fp in plan.fns.values():
        for n in fp.own:
            owner.setdefault(id(n), []).append(fp)
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in plan.spec:
            sp = plan.spec[n.func.id]
            if n.keywords or len(n.args) != len(sp.params) or any(isinstance(a, ast.Starred) for a in n.args):
                for caller in owner.get(id(n), []):
                    plan.generic_sites.add((caller.name, id(n)))
                continue
            for caller in owner.get(id(n), []):
                sp.calls_in.append((caller, n))

    # ---- the fixed point
    def env_of(fp):
        return lambda nm: _name_type(plan, fp, nm)

    for _round in range(200):
        changed = False
        for fp in plan.fns.values():
            env = env_of(fp)
            new = dict(fp.vtype)
            for i, p in enumerate(fp.params):
                if p in fp.locals:
                    new[p] = join(new[p], fp.ptypes[i] if fp.spec else OBJ)
            for n in fp.own:
                if isinstance(n, ast.Assign):
                    t = etype(plan, fp, n.value, env)
                    for tg in n.targets:
                        if isinstance(tg, ast.Name) and tg.id in new:
                            new[tg.id] = join(new[tg.id], t)
                elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.value is not None:
                    if n.target.id in new:
                        new[n.target.id] = join(new[n.target.id], etype(plan, fp, n.value, env))
                elif isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name) and n.target.id in new:
                    virt = ast.BinOp(left=ast.Name(id=n.target.id, ctx=ast.Load()), op=n.op, right=n.value)
                    new[n.target.id] = join(new[n.target.id], etype(plan, fp, virt, env))
                elif isinstance(n, ast.For) and isinstance(n.target, ast.Name) and n.target.id in new \
                        and _is_range_call(n.iter, names_all):
                    new[n.target.id] = join(new[n.target.id], INT)
            for v in fp.bad:
                if v in new:
                    new[v] = OBJ
            if new != fp.vtype:
                fp.vtype = new
                changed = True
            if fp.spec:
                r = fp.ret
                if not _always_returns(fp.node.body):
                    r = join(r, OBJ)
                for n in fp.own:
                    if isinstance(n, ast.Return):
                        r = join(r, OBJ if n.value is None else etype(plan, fp, n.value, env))
                if r != fp.ret:
                    fp.ret = r
                    changed = True
        for name, sp in plan.spec.items():
            pt = list(sp.ptypes)
            for caller, call in sp.calls_in:
                if (caller.name, id(call)) in plan.generic_sites:
                    continue
                for i, a in enumerate(call.args):
                    t = etype(plan, caller, a, env_of(caller))
                    if t is not OBJ:
                        pt[i] = join(pt[i], t)       # a boxed argument sends its call to the boxed body
            if pt != sp.ptypes:
                sp.ptypes = pt
                changed = True
            for caller, call in sp.calls_in:
                key = (caller.name, id(call))
                if key in plan.generic_sites:
                    continue
                for i, a in enumerate(call.args):
                    t = etype(plan, caller, a, env_of(caller))
                    if pt[i] in SCALAR and t is not BOT and t != pt[i]:
                        plan.generic_sites.add(key)     # sticky: the result type of this call only rises
                        changed = True
                        break
        if not changed:
            # what is still bottom has no evidence (dead code, a function never called): widen it
            # parameters first (an annotation hint may give them a type), then the variables that depend on them
            widened = False
            for fp in plan.fns.values():
                if fp.spec:
                    for i, t in enumerate(fp.ptypes):
                        if t is BOT:
                            fp.ptypes[i] = fp.hints[i] if fp.hints[i] in SCALAR else OBJ
                            widened = True
            if widened:
                continue
            for fp in plan.fns.values():
                for v, t in fp.vtype.items():
                    if t is BOT:
                        fp.vtype[v] = OBJ
                        widened = True
                if fp.spec and fp.ret is BOT:
                    fp.ret = OBJ
                    widened = True
            if not widened:
                break
    else:
        raise Conflict(('<module>', '*'), 'the type analysis did not settle')
    # a specialisation that changes nothing, or that no call reaches with its types, is dropped
    for name in list(plan.spec):
        sp = plan.spec[name]
        if sp.ret not in SCALAR and not any(t in SCALAR for t in sp.ptypes):
            del plan.spec[name]
            del plan.fns[sp.name]
    # the boxed body of a specialised function is emitted only when something can reach it: a call from
    # code this pass does not analyse, the function used as a value, or a call whose arguments do not match
    # (from any body that is itself emitted). Otherwise the specialised body is the only one (binary size).
    calls_by_owner = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in plan.spec:
            if id(n) not in owner:
                plan.need_generic.add(n.func.id)
    callee_names = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id in plan.spec and id(n) not in callee_names:
            plan.need_generic.add(n.id)
    generic_of = {sp.info['cname']: name for name, sp in plan.spec.items()}
    bodies = [fp for fp in plan.fns.values() if fp.name not in generic_of]
    bodies += [plan.fns[sp.info['cname']] for name, sp in plan.spec.items()
               if name in plan.need_generic and sp.info['cname'] in plan.fns]
    seen = set()
    while bodies:
        fp = bodies.pop()
        if fp.name in seen:
            continue
        seen.add(fp.name)
        for n in fp.own:
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in plan.spec:
                if not site_matches(plan, fp, n) and n.func.id not in plan.need_generic:
                    plan.need_generic.add(n.func.id)
                    g = plan.fns.get(plan.spec[n.func.id].info['cname'])
                    if g is not None:
                        bodies.append(g)
    # a library function the compiler added (json, re, ...) is not worth two bodies: when its boxed body
    # must stay, it is not specialised at all (its locals are still unboxed)
    twice = {('pfu_' + name, '*') for name in plan.need_generic if name.startswith('_ail')}
    if twice - demote:
        return analyze(comp, tree, demote | twice)
    plan.stats = {
        'functions': len(plan.fns),
        'generic_bodies_kept': sorted(plan.need_generic),
        'unboxed_vars': sum(1 for fp in plan.fns.values() for v in fp.locals if fp.unboxed(v)),
        'boxed_vars': sum(1 for fp in plan.fns.values() for v in fp.locals if not fp.unboxed(v)),
        'specialised': sorted(plan.spec),
        'constants': sorted(plan.gconst),
    }
    return plan


def _ann_type(a):
    if isinstance(a, ast.Name):
        return {'int': INT, 'float': FLOAT, 'bool': BOOL}.get(a.id, OBJ)
    if isinstance(a, ast.Constant) and isinstance(a.value, str):
        return {'int': INT, 'float': FLOAT, 'bool': BOOL}.get(a.value, OBJ)
    return OBJ


def site_matches(plan, fp, call):
    """Whether the call `call` (to a specialised function) in function plan `fp` goes to the unboxed body."""
    sp = plan.spec[call.func.id]
    if call.keywords or len(call.args) != len(sp.params) or any(isinstance(a, ast.Starred) for a in call.args):
        return False
    if fp is None:
        return not any(t in SCALAR for t in sp.ptypes)
    if (fp.name, id(call)) in plan.generic_sites:
        return False
    env = lambda nm: _name_type(plan, fp, nm)
    return all(t not in SCALAR or etype(plan, fp, a, env) == t for a, t in zip(call.args, sp.ptypes))


def _name_type(plan, fp, nm):
    if nm in fp.locals:
        t = fp.vtype.get(nm)
        return OBJ if nm in fp.bad else t
    if nm in plan.gconst:
        return plan.gconst[nm]
    return OBJ


_ARITH = (ast.Add, ast.Sub, ast.Mult)
_BITS = (ast.BitAnd, ast.BitOr, ast.BitXor, ast.LShift, ast.RShift)
_ORDER = (ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq)


def _builtin(plan, fp, name):
    """`name` called here is the builtin (not a local, a module name or a function of the program)."""
    return ((fp is None or name not in fp.locals) and name not in plan.module_names
            and name not in plan.fn_names)


def etype(plan, fp, n, env):
    """The lattice value of expression `n` in function `fp`, under the variable types `env`.
    A scalar answer means the emitter can produce the value unboxed (`Emit.nexpr`)."""
    if isinstance(n, ast.Constant):
        v = n.value
        if isinstance(v, bool):
            return BOOL
        if isinstance(v, int):
            return INT if _I64_MIN <= v <= _I64_MAX else OBJ
        if isinstance(v, float):
            return FLOAT
        return OBJ
    if isinstance(n, ast.Name):
        return env(n.id)
    if isinstance(n, ast.BinOp):
        a, b = etype(plan, fp, n.left, env), etype(plan, fp, n.right, env)
        if a is BOT or b is BOT:
            return BOT if OBJ not in (a, b) else OBJ
        op = n.op
        if a == INT and b == INT:
            if isinstance(op, _ARITH + _BITS + (ast.FloorDiv, ast.Mod)):
                return INT
            if isinstance(op, ast.Div):
                return FLOAT
            return OBJ
        if a in (INT, FLOAT) and b in (INT, FLOAT):
            if isinstance(op, _ARITH + (ast.Div, ast.FloorDiv, ast.Mod)):
                return FLOAT
            return OBJ
        return OBJ
    if isinstance(n, ast.UnaryOp):
        if isinstance(n.op, ast.Not):
            return BOOL
        a = etype(plan, fp, n.operand, env)
        if a is BOT:
            return BOT
        if isinstance(n.op, (ast.USub, ast.UAdd)) and a in (INT, FLOAT):
            return a
        if isinstance(n.op, ast.Invert) and a == INT:
            return INT
        return OBJ
    if isinstance(n, ast.Compare):
        if any(isinstance(o, (ast.In, ast.NotIn, ast.Is, ast.IsNot)) for o in n.ops):
            if len(n.ops) == 1:
                return BOOL           # `in` and `is` always give a bool
            return OBJ
        ts = [etype(plan, fp, x, env) for x in [n.left] + n.comparators]
        if any(t is BOT for t in ts) and OBJ not in ts:
            return BOT
        if all(t in (INT, FLOAT, BOOL) for t in ts):
            # bool compares as an int; the result of a numeric comparison is a bool
            return BOOL
        return OBJ
    if isinstance(n, ast.BoolOp):
        ts = [etype(plan, fp, x, env) for x in n.values]
        if any(t is BOT for t in ts) and OBJ not in ts:
            return BOT
        return BOOL if all(t == BOOL for t in ts) else OBJ
    if isinstance(n, ast.IfExp):
        a, b = etype(plan, fp, n.body, env), etype(plan, fp, n.orelse, env)
        return join(a, b)
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and not n.keywords \
            and not any(isinstance(a, ast.Starred) for a in n.args):
        f = n.func.id
        if f in plan.spec:
            sp = plan.spec[f]
            if (fp is None or (fp.name, id(n)) in plan.generic_sites or len(n.args) != len(sp.params)):
                return OBJ
            return sp.ret
        if not _builtin(plan, fp, f):
            return OBJ
        k = len(n.args)
        if f in ('len', 'ord') and k == 1:
            return INT
        if f == 'int' and k in (1, 2):
            return INT
        if f == 'float' and k == 1:
            return FLOAT
        if f in ('bool', 'isinstance', 'callable') and k in ((1,) if f != 'isinstance' else (2,)):
            return BOOL
        if f == 'round' and k == 1:
            a = etype(plan, fp, n.args[0], env)
            return INT if a in (INT, FLOAT) else (BOT if a is BOT else OBJ)
        if f == 'abs' and k == 1:
            a = etype(plan, fp, n.args[0], env)
            return a if a in (INT, FLOAT, BOT) else OBJ
        if f in ('min', 'max') and k >= 2:
            ts = [etype(plan, fp, x, env) for x in n.args]
            if any(t is BOT for t in ts) and OBJ not in ts:
                return BOT
            if all(t == INT for t in ts):
                return INT
            if all(t == FLOAT for t in ts):
                return FLOAT
        return OBJ
    return OBJ


# ============================================================================== emission
#
# Hooks called by pyboxed2 when `comp.uplan` is set (AIL_UNIFIED=1). `ctx.u` is the FnPlan of the
# function being emitted (None for module code, lambdas, nested functions and functions this pass
# left alone). Every native value is a C local (`u_<name>` for a variable, `_u<n>` for a
# temporary) declared at the top of the function, so no jump of the general path's error edges
# crosses a declaration.

_CMP_C = {ast.Lt: '<', ast.LtE: '<=', ast.Gt: '>', ast.GtE: '>=', ast.Eq: '==', ast.NotEq: '!='}
_CMP_RT = {ast.Lt: 'ail_op_lt', ast.LtE: 'ail_op_le', ast.Gt: 'ail_op_gt', ast.GtE: 'ail_op_ge',
           ast.Eq: 'ail_op_eq', ast.NotEq: 'ail_op_ne'}
_BIN_RT = {ast.Add: 'ail_op_add', ast.Sub: 'ail_op_sub', ast.Mult: 'ail_op_mul', ast.Div: 'ail_op_truediv',
           ast.FloorDiv: 'ail_op_floordiv', ast.Mod: 'ail_op_mod', ast.BitAnd: 'ail_op_bitand',
           ast.BitOr: 'ail_op_bitor', ast.BitXor: 'ail_op_bitxor', ast.LShift: 'ail_op_lshift',
           ast.RShift: 'ail_op_rshift'}
_OVF = {ast.Add: 'add', ast.Sub: 'sub', ast.Mult: 'mul'}


def begin_function(comp, info, ctx):
    """Attach the plan of the function to its emission context; the C declarations of its native locals."""
    plan = comp.uplan
    fp = plan.fns.get(info['cname']) if plan is not None else None
    ctx.u = fp
    ctx.u_decls = []
    ctx.u_n = 0
    if fp is None:
        return
    for v in sorted(fp.locals):
        if fp.unboxed(v):
            ctx.u_decls.append('%s %s = 0;' % (CTYPE[fp.vtype[v]], fp.cvar(v)))
            ctx.var_kind[v] = KIND[fp.vtype[v]]


def _spec_of(plan, info):
    if plan is None or info.get('is_method'):
        return None
    sp = plan.spec.get(info['node'].name)
    return sp if sp is not None and sp.info is not None and sp.info['node'] is info['node'] else None


def signature(plan, info):
    """(C name, parameter list after `ail_ctx *cx`) of the specialised body of the function, or None."""
    sp = _spec_of(plan, info)
    if sp is None:
        return None
    out = '%s *out' % (CTYPE[sp.ret] if sp.ret in SCALAR else 'ail_obj')
    ps = ''.join(', %s pv_%s' % (CTYPE[t] if t in SCALAR else 'ail_obj', p) for p, t in zip(sp.params, sp.ptypes))
    return sp.name, out + ps


def entry_guard(plan, info):
    """The first lines of the boxed body of a specialised function: arguments that carry the specialised
    types go to the unboxed body."""
    sp = _spec_of(plan, info)
    if sp is None or info['cname'] == sp.name:
        return ''
    tag = {INT: 'AIL_T_INT', FLOAT: 'AIL_T_FLOAT', BOOL: 'AIL_T_BOOL'}
    conds, args = [], []
    for p, t in zip(sp.params, sp.ptypes):
        if t in SCALAR:
            conds.append('pv_%s.tag == %s' % (p, tag[t]))
            args.append('ail_float_val(pv_%s)' % p if t == FLOAT else ('pv_%s.i' % p))
        else:
            args.append('pv_' + p)
    call = '%s(cx, %%s%s)' % (sp.name, ''.join(', ' + a for a in args))
    if sp.ret in SCALAR:
        body = ('        %s _ur; ail_st _st = %s;\n'
                '        if (_st == AIL_OK) *out = %s;\n'
                '        return _st;\n') % (CTYPE[sp.ret], call % '&_ur', _box_rv(sp.ret, '_ur'))
    else:
        body = '        return %s;\n' % (call % 'out')
    return '    if (%s) {\n%s    }\n' % (' && '.join(conds) or '1', body)


def param_preamble(comp, info, ctx):
    """The lines that move the C parameters into their storage, or None for the general path's own."""
    fp = ctx.u
    if fp is None:
        return None
    lines = []
    for i, p in enumerate(info['all_params']):
        pt = fp.ptypes[i] if fp.spec and i < len(fp.ptypes) else OBJ
        if fp.unboxed(p):
            if pt != fp.vtype[p]:
                raise Conflict((fp.name, p), 'parameter type %s, variable %s' % (pt, fp.vtype[p]))
            lines.append('    %s = pv_%s;' % (fp.cvar(p), p))
        elif pt in SCALAR:
            lines.append('    f.slots[%d] = %s;' % (ctx.slot_of[p], _box_rv(pt, 'pv_' + p)))
        else:
            lines.append('    f.slots[%d] = pv_%s;' % (ctx.slot_of[p], p))
    return lines


def _box_rv(t, v):
    return {INT: 'ail_box_int(%s)', BOOL: 'ail_box_bool(%s)', FLOAT: 'ail_box_float(cx, %s)'}[t] % v


def ntype(comp, ctx, node):
    fp = ctx.u
    plan = comp.uplan
    return etype(plan, fp, node, lambda nm: _name_type(plan, fp, nm))


def utmp(ctx, t):
    ctx.u_n += 1
    name = '_u%d' % ctx.u_n
    ctx.u_decls.append('%s %s = 0;' % (CTYPE[t], name))
    return name


def box(comp, ctx, v, t):
    if t != FLOAT:
        # an int or bool box is a value with no heap part: no slot, no store (the general path's own
        # True/False are such rvalues too); a float box is a heap object and is rooted in a slot
        return _box_rv(t, v)
    s = ctx.tmp()
    ctx.emit('%s = %s;' % (s, _box_rv(t, v)))
    return s


def _unbox_rv(s, t):
    if t == FLOAT:
        return '((%s).tag == AIL_T_FLOAT ? ail_float_val(%s) : (double)(%s).i)' % (s, s, s)
    if t == BOOL:
        return '((%s).i != 0)' % s
    return '(%s).i' % s


def unbox(ctx, s, t):
    r = utmp(ctx, t)
    ctx.emit('%s = %s;' % (r, _unbox_rv(s, t)))
    return r


def _c_const(v):
    if isinstance(v, bool):
        return '1' if v else '0'
    if isinstance(v, int):
        return '(-9223372036854775807LL - 1)' if v == _I64_MIN else '(%dLL)' % v
    if v != v:
        return '__builtin_nan("")'
    if v in (float('inf'), float('-inf')):
        return '__builtin_inf()' if v > 0 else '(-__builtin_inf())'
    return '(%s)' % float.hex(v)


def _natively_computed(comp, ctx, node):
    """Whether emitting `node` unboxed and boxing the result beats the general path's own code."""
    fp = ctx.u
    if isinstance(node, ast.Name):
        return node.id in fp.locals and fp.unboxed(node.id)
    if isinstance(node, (ast.BinOp, ast.BoolOp, ast.IfExp)):
        return True
    if isinstance(node, ast.UnaryOp):
        return not isinstance(node.op, ast.Not) or ntype(comp, ctx, node.operand) in SCALAR
    if isinstance(node, ast.Compare):
        return not any(isinstance(o, (ast.In, ast.NotIn, ast.Is, ast.IsNot)) for o in node.ops)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        f = node.func.id
        return f in comp.uplan.spec or (f in ('min', 'max') and _builtin(comp.uplan, fp, f))
    return False


def expr_hook(comp, node, ctx):
    """pyboxed2.expr: the boxed value of a proven expression computed unboxed, or None."""
    fp = getattr(ctx, 'u', None)
    if fp is None or isinstance(node, ast.Constant):
        return None
    plan = comp.uplan
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in plan.spec
            and site_matches(plan, fp, node)):
        v, t = call_spec(comp, node.func.id, node.args, ctx)
        return box(comp, ctx, v, t) if t in SCALAR else v
    t = ntype(comp, ctx, node)
    if t not in SCALAR or not _natively_computed(comp, ctx, node):
        return None
    return box(comp, ctx, nexpr(comp, node, ctx), t)


def _err(ctx):
    ctx.uses_st = True
    return ctx.cur_err_target()


def _slot_of(comp, ctx, v, t):
    """A boxed copy of native `v` in a frame slot (a float box must be rooted while a runtime call allocates)."""
    return box(comp, ctx, v, t)


def _fallback(comp, ctx, fn, operands, rtype, r):
    """Run the general path's own operation on boxed operands (the rare edge: overflow, a zero divisor,
    a shift out of range) and unbox its result into `r`."""
    # three scratch slots per function, shared by every fallback: each is dead once its result is unboxed
    if not getattr(ctx, 'u_scratch', None):
        ctx.u_scratch = [ctx.tmp() for _ in range(3)]
    boxed = []
    for (v, t), s in zip(operands, ctx.u_scratch):
        ctx.emit('%s = %s;' % (s, _box_rv(t, v)))
        boxed.append(s)
    out = ctx.u_scratch[2]
    ctx.emit('st = %s(cx, &%s%s);' % (fn, out, ''.join(', ' + b for b in boxed)))
    ctx.emit('if (st != AIL_OK) goto %s;' % _err(ctx))
    ctx.emit('%s = %s;' % (r, _unbox_rv(out, rtype)))


def _open(ctx, line):
    ctx.emit(line)
    ctx.indent += 1


def _close(ctx, line='}'):
    ctx.indent -= 1
    ctx.emit(line)


def ntest(comp, node, ctx):
    t = ntype(comp, ctx, node)
    v = nexpr(comp, node, ctx)
    if t == BOOL:
        return v
    if t == INT:
        return '(%s != 0)' % v
    return '(%s != 0.0)' % v


def _f(v, t):
    return '((double)%s)' % v if t != FLOAT else v


def nexpr(comp, node, ctx):
    """The C value (a constant or a C local) of proven expression `node`; its statements are emitted."""
    fp = ctx.u
    t = ntype(comp, ctx, node)
    if t not in SCALAR:
        raise Conflict((fp.name, '*'), 'unboxed value of a boxed expression %s' % ast.dump(node)[:80])
    if isinstance(node, ast.Constant):
        return _c_const(node.value)
    if isinstance(node, ast.Name):
        if node.id in fp.locals:
            return fp.cvar(node.id)
        g = comp.name_ref(node.id, ctx)
        ctx.emit('if ((%s).tag == AIL_T_UNBOUND) { st = ail_raise_c(cx, AIL_B_NAMEERROR, '
                 '"name \'%s\' is not defined"); goto %s; }' % (g, node.id, _err(ctx)))
        return unbox(ctx, g, t)
    if isinstance(node, ast.BinOp):
        return _binop(comp, node, ctx, t)
    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.Not):
            if ntype(comp, ctx, node.operand) in SCALAR:
                r = utmp(ctx, BOOL)
                ctx.emit('%s = !%s;' % (r, ntest(comp, node.operand, ctx)))
                return r
            return unbox(ctx, comp._expr_plain(node, ctx), BOOL)
        a = nexpr(comp, node.operand, ctx)
        if isinstance(node.op, ast.UAdd):
            return a
        r = utmp(ctx, t)
        if isinstance(node.op, ast.Invert):
            ctx.emit('%s = ~%s;' % (r, a))
        elif t == FLOAT:
            ctx.emit('%s = -%s;' % (r, a))
        else:
            _open(ctx, 'if (%s == INT64_MIN) {' % a)
            _fallback(comp, ctx, 'ail_op_neg', [(a, INT)], INT, r)
            _close(ctx, '} else {')
            ctx.indent += 1
            ctx.emit('%s = -%s;' % (r, a))
            _close(ctx)
        return r
    if isinstance(node, ast.Compare):
        if any(isinstance(o, (ast.In, ast.NotIn, ast.Is, ast.IsNot)) for o in node.ops):
            return unbox(ctx, comp._expr_plain(node, ctx), BOOL)
        r = utmp(ctx, BOOL)
        left = node.left
        lv = nexpr(comp, left, ctx)
        lt = ntype(comp, ctx, left)
        depth = 0
        for i, (op, right) in enumerate(zip(node.ops, node.comparators)):
            if i:
                _open(ctx, 'if (%s) {' % r)
                depth += 1
            rv = nexpr(comp, right, ctx)
            rt = ntype(comp, ctx, right)
            if (lt == FLOAT) == (rt == FLOAT):
                ctx.emit('%s = (%s %s %s);' % (r, lv, _CMP_C[type(op)], rv))
            else:
                _fallback(comp, ctx, _CMP_RT[type(op)], [(lv, lt), (rv, rt)], BOOL, r)
            lv, lt = rv, rt
        for _ in range(depth):
            _close(ctx)
        return r
    if isinstance(node, ast.BoolOp):
        r = utmp(ctx, BOOL)
        is_and = isinstance(node.op, ast.And)
        ctx.emit('%s = %s;' % (r, nexpr(comp, node.values[0], ctx)))
        for v in node.values[1:]:
            _open(ctx, 'if (%s%s) {' % ('' if is_and else '!', r))
            ctx.emit('%s = %s;' % (r, nexpr(comp, v, ctx)))
        for _ in node.values[1:]:
            _close(ctx)
        return r
    if isinstance(node, ast.IfExp):
        r = utmp(ctx, t)
        if ntype(comp, ctx, node.test) in SCALAR:
            cond = ntest(comp, node.test, ctx)
        else:
            cond = 'ail_obj_truthy(%s)' % comp.expr(node.test, ctx)
        _open(ctx, 'if (%s) {' % cond)
        ctx.emit('%s = %s;' % (r, nexpr(comp, node.body, ctx)))
        _close(ctx, '} else {')
        ctx.indent += 1
        ctx.emit('%s = %s;' % (r, nexpr(comp, node.orelse, ctx)))
        _close(ctx)
        return r
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        f = node.func.id
        if f in comp.uplan.spec:
            v, vt = call_spec(comp, f, node.args, ctx)
            return v
        if f in ('min', 'max') and _builtin(comp.uplan, fp, f):
            vals = [nexpr(comp, a, ctx) for a in node.args]
            r = utmp(ctx, t)
            ctx.emit('%s = %s;' % (r, vals[0]))
            for v in vals[1:]:
                ctx.emit('if (%s %s %s) %s = %s;' % (v, '<' if f == 'min' else '>', r, r, v))
            return r
        return unbox(ctx, comp._expr_plain(node, ctx), t)
    raise Conflict((fp.name, '*'), 'no unboxed form for %s' % type(node).__name__)


def _binop(comp, node, ctx, t):
    op = node.op
    lt, rt = ntype(comp, ctx, node.left), ntype(comp, ctx, node.right)
    a = nexpr(comp, node.left, ctx)
    b = nexpr(comp, node.right, ctx)
    r = utmp(ctx, t)
    fn = _BIN_RT[type(op)]
    ops = [(a, lt), (b, rt)]

    def guarded(cond, fast):
        _open(ctx, 'if (%s) {' % cond)
        _fallback(comp, ctx, fn, ops, t, r)
        _close(ctx, '} else {')
        ctx.indent += 1
        for line in fast:
            ctx.emit(line)
        _close(ctx)

    if lt == INT and rt == INT:
        c = node.right.value if isinstance(node.right, ast.Constant) and isinstance(node.right.value, int) \
            and not isinstance(node.right.value, bool) else None
        if c is not None and c > 0 and c & (c - 1) == 0 and isinstance(op, (ast.FloorDiv, ast.Mod)):
            # floor semantics on two's complement: x // 2**k is the arithmetic shift, x % 2**k the mask
            k = c.bit_length() - 1
            if isinstance(op, ast.FloorDiv):
                ctx.emit('%s = %s >> %d;' % (r, a, k))
            else:
                ctx.emit('%s = %s & %dLL;' % (r, a, c - 1))
            return r
        if type(op) in _OVF:
            _open(ctx, 'if (__builtin_%s_overflow(%s, %s, &%s)) {' % (_OVF[type(op)], a, b, r))
            _fallback(comp, ctx, fn, ops, t, r)
            _close(ctx)
        elif isinstance(op, ast.FloorDiv):
            guarded('%s == 0 || (%s == INT64_MIN && %s == -1)' % (b, a, b),
                    ['%s = %s / %s;' % (r, a, b),
                     'if ((%s %% %s != 0) && (((%s %% %s) < 0) != (%s < 0))) %s -= 1;' % (a, b, a, b, b, r)])
        elif isinstance(op, ast.Mod):
            guarded('%s == 0 || %s == -1' % (b, b),
                    ['%s = %s %% %s;' % (r, a, b),
                     'if (%s != 0 && ((%s < 0) != (%s < 0))) %s += %s;' % (r, r, b, r, b)])
        elif isinstance(op, (ast.BitAnd, ast.BitOr, ast.BitXor)):
            ctx.emit('%s = %s %s %s;' % (r, a, {ast.BitAnd: '&', ast.BitOr: '|', ast.BitXor: '^'}[type(op)], b))
        elif isinstance(op, ast.LShift):
            guarded('!(%s >= 0 && %s < 63) || (((int64_t)((uint64_t)%s << %s)) >> %s) != %s' % (b, b, a, b, b, a),
                    ['%s = (int64_t)((uint64_t)%s << %s);' % (r, a, b)])
        elif isinstance(op, ast.RShift):
            guarded('%s < 0' % b, ['%s = %s >= 63 ? (%s < 0 ? -1 : 0) : (%s >> %s);' % (r, b, a, a, b)])
        elif isinstance(op, ast.Div):
            guarded('%s == 0' % b, ['%s = (double)%s / (double)%s;' % (r, a, b)])
        else:
            raise Conflict((ctx.u.name, '*'), 'int operator %s' % type(op).__name__)
        return r
    # float (an int operand converts, as the runtime's ail__as_double does)
    x, y = _f(a, lt), _f(b, rt)
    if isinstance(op, (ast.Add, ast.Sub, ast.Mult)):
        ctx.emit('%s = %s %s %s;' % (r, x, {ast.Add: '+', ast.Sub: '-', ast.Mult: '*'}[type(op)], y))
    elif isinstance(op, ast.Div):
        guarded('%s == 0.0' % y, ['%s = %s / %s;' % (r, x, y)])
    elif isinstance(op, ast.FloorDiv):
        guarded('%s == 0.0' % y, ['%s = floor(%s / %s);' % (r, x, y)])
    elif isinstance(op, ast.Mod):
        guarded('%s == 0.0' % y, ['%s = fmod(%s, %s);' % (r, x, y),
                                  'if (%s != 0.0 && ((%s < 0) != (%s < 0))) %s += %s;' % (r, r, y, r, y)])
    else:
        raise Conflict((ctx.u.name, '*'), 'float operator %s' % type(op).__name__)
    return r


def call_spec(comp, name, args, ctx):
    """A call of specialised function `name`: (C value, lattice value of the result). Boxed parameters get
    the general path's boxed argument; unboxed ones the native value."""
    callee = comp.uplan.spec[name]
    fp = getattr(ctx, 'u', None)
    argcs = []
    for a, pt in zip(args, callee.ptypes):
        if pt in SCALAR:
            if fp is None or ntype(comp, ctx, a) != pt:
                raise Conflict((callee.name, '*'), 'argument of another type at a call site')
            argcs.append(nexpr(comp, a, ctx))
        else:
            argcs.append(comp.expr(a, ctx))
    call = '%s(cx, &%%s%s)' % (callee.name, ''.join(', ' + x for x in argcs))
    if callee.ret in SCALAR and fp is None:
        # module code (or a function left boxed) calling a function with an unboxed result: box it here
        s = ctx.tmp()
        ctx.emit('{ %s _ur; st = %s;' % (CTYPE[callee.ret], call % '_ur'))
        ctx.emit('  if (st != AIL_OK) goto %s;' % _err(ctx))
        ctx.emit('  %s = %s; }' % (s, _box_rv(callee.ret, '_ur')))
        return s, OBJ
    r = utmp(ctx, callee.ret) if callee.ret in SCALAR else ctx.tmp()
    ctx.emit('st = %s;' % (call % r))
    ctx.check()
    return r, callee.ret


def boxed_body_hook(comp, name):
    """The general path is about to call (or take the value of) the boxed body of `name`."""
    plan = comp.uplan
    if name in plan.spec and name not in plan.need_generic:
        raise Conflict((plan.spec[name].name, '*'), 'the boxed body was left out but is called')


def name_ref_hook(comp, name, ctx):
    fp = getattr(ctx, 'u', None)
    if fp is not None and name in fp.locals and fp.unboxed(name):
        raise Conflict((fp.name, name), 'the frame slot of an unboxed variable was asked for')


def _assign_native(comp, ctx, target, v, t):
    fp = ctx.u
    if fp.unboxed(target.id):
        if fp.vtype[target.id] != t:
            raise Conflict((fp.name, target.id), 'a %s stored in a %s variable' % (t, fp.vtype[target.id]))
        ctx.emit('%s = %s;' % (fp.cvar(target.id), v))
    else:
        comp._assign_target(target, box(comp, ctx, v, t), ctx, value_kind=KIND[t])
        comp.set_kind(target.id, KIND[t], ctx)
        comp.set_elem_kind(target.id, None, ctx)


def stmt_hook(comp, node, ctx):
    """pyboxed2.stmt: True when the statement was emitted here."""
    fp = getattr(ctx, 'u', None)
    if fp is None:
        return False
    if isinstance(node, (ast.Assign, ast.AnnAssign)):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if node.value is None or not all(isinstance(x, ast.Name) for x in targets):
            return False
        if not any(x.id in fp.locals and fp.unboxed(x.id) for x in targets):
            return False
        t = ntype(comp, ctx, node.value)
        if t not in SCALAR:
            raise Conflict((fp.name, targets[0].id), 'a boxed value stored in an unboxed variable')
        if isinstance(node, ast.AnnAssign):
            comp._declare_if_local(node.target.id, ctx)
        v = nexpr(comp, node.value, ctx)
        for x in targets:
            _assign_native(comp, ctx, x, v, t)
        return True
    if isinstance(node, ast.AugAssign):
        if not (isinstance(node.target, ast.Name) and node.target.id in fp.locals and fp.unboxed(node.target.id)):
            return False
        virt = ast.copy_location(ast.BinOp(left=ast.Name(id=node.target.id, ctx=ast.Load()), op=node.op,
                                           right=node.value), node)
        t = ntype(comp, ctx, virt)
        if t != fp.vtype[node.target.id]:
            raise Conflict((fp.name, node.target.id), 'augmented assignment changes the type')
        ctx.emit('%s = %s;' % (fp.cvar(node.target.id), nexpr(comp, virt, ctx)))
        return True
    if isinstance(node, ast.If):
        if comp._is_main_guard(node) or ntype(comp, ctx, node.test) not in SCALAR:
            return False
        _open(ctx, 'if (%s) {' % ntest(comp, node.test, ctx))
        comp.block(node.body, ctx)
        if node.orelse:
            _close(ctx, '} else {')
            ctx.indent += 1
            comp.block(node.orelse, ctx)
        _close(ctx)
        return True
    if isinstance(node, ast.While):
        if ntype(comp, ctx, node.test) not in SCALAR:
            return False
        has_else = bool(node.orelse)
        broke = ctx.new_cvar('broke') if has_else else None
        if has_else:
            ctx.emit('int %s = 0;' % broke)
        ctx.loop_stack.append({'has_else': has_else, 'broke': broke, 'finally_depth': len(ctx.finally_stack)})
        _open(ctx, 'while (1) {')
        comp._gil_check(ctx)
        ctx.emit('if (!%s) break;' % ntest(comp, node.test, ctx))
        comp.block(node.body, ctx)
        _close(ctx)
        ctx.loop_stack.pop()
        if has_else:
            _open(ctx, 'if (!%s) {' % broke)
            comp.block(node.orelse, ctx)
            _close(ctx)
        return True
    if isinstance(node, ast.For):
        tg = node.target
        if not (isinstance(tg, ast.Name) and tg.id in fp.locals and fp.unboxed(tg.id)
                and _is_range_call(node.iter, comp.uplan.fn_names)):
            return False
        if fp.vtype[tg.id] != INT:
            raise Conflict((fp.name, tg.id), 'a range loop variable that is not an int')
        args = node.iter.args
        native = all(ntype(comp, ctx, a) == INT for a in args)
        step = 1
        if len(args) == 3:
            s = args[2]
            if isinstance(s, ast.UnaryOp) and isinstance(s.op, ast.USub) and isinstance(s.operand, ast.Constant):
                step = -s.operand.value if isinstance(s.operand.value, int) else 0
            elif isinstance(s, ast.Constant) and isinstance(s.value, int) and not isinstance(s.value, bool):
                step = s.value
            else:
                step = 0
            if step == 0 or isinstance(step, bool):
                native = False
        has_else = bool(node.orelse)
        broke = ctx.new_cvar('broke') if has_else else None
        if has_else:
            ctx.emit('int %s = 0;' % broke)
        ctx.loop_stack.append({'has_else': has_else, 'broke': broke, 'finally_depth': len(ctx.finally_stack)})
        if native:
            vals = [nexpr(comp, a, ctx) for a in args[:2]]
            lo, hi = ('0', vals[0]) if len(args) == 1 else (vals[0], vals[1])
            n = ctx.new_cvar('un')
            k = ctx.new_cvar('uk')
            lo_v = ctx.new_cvar('ulo')
            ctx.emit('int64_t %s = %s;' % (lo_v, lo))
            if step > 0:
                ctx.emit('uint64_t %s = %s < %s ? ((uint64_t)%s - (uint64_t)%s - 1) / %dULL + 1 : 0;'
                         % (n, lo_v, hi, hi, lo_v, step))
            else:
                ctx.emit('uint64_t %s = %s > %s ? ((uint64_t)%s - (uint64_t)%s - 1) / %dULL + 1 : 0;'
                         % (n, lo_v, hi, lo_v, hi, -step))
            _open(ctx, 'for (uint64_t %s = 0; %s < %s; %s++) {' % (k, k, n, k))
            comp._gil_check(ctx)
            if step == 1:
                ctx.emit('%s = (int64_t)((uint64_t)%s + %s);' % (fp.cvar(tg.id), lo_v, k))
            else:
                ctx.emit('%s = (int64_t)((uint64_t)%s + %s * (uint64_t)(%dLL));' % (fp.cvar(tg.id), lo_v, k, step))
        else:
            val = comp._open_iter_loop(node.iter, ctx)
            ctx.emit('%s = (%s).i;' % (fp.cvar(tg.id), val))
        comp.block(node.body, ctx)
        _close(ctx)
        ctx.loop_stack.pop()
        if has_else:
            _open(ctx, 'if (!%s) {' % broke)
            comp.block(node.orelse, ctx)
            _close(ctx)
        return True
    if isinstance(node, ast.Return):
        if not (fp.spec and fp.ret in SCALAR):
            return False
        if node.value is None or ctx.finally_stack or ntype(comp, ctx, node.value) != fp.ret:
            raise Conflict((fp.name, '*'), 'a return of another type')
        ctx.emit('*out = %s;' % nexpr(comp, node.value, ctx))
        ctx.emit('AIL_FRAME_LEAVE(cx, f);')
        ctx.emit('return AIL_OK;')
        return True
    return False


def record(plan, demoted):
    entry = dict(plan.stats, demoted=sorted('%s:%s' % k for k in demoted), reasons=list(_REASONS))
    del _REASONS[:]
    STATS.append(entry)
    target = os.environ.get('AIL_UNIFIED_STATS')
    if target:
        import json
        with open(target, 'a') as handle:
            handle.write(json.dumps(entry) + '\n')
