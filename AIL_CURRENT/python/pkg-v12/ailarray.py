"""`import ail_array` (docs/design/TYPED_ARRAY.md, stage T2): f64 and int32 arrays lowered onto native loops.

Called from ail_syntax.python_surface (as stdlib5 is) on the program text. A program that does not import `ail_array`
is returned as it was written (the same string), so its C does not change. Otherwise:

* every array has a static dtype: the `ta.f64` / `ta.int32` literal of its construction, a `ta.Array[ta.f64]` annotation,
  or what flows from those through assignments, calls (parameters take what every call site passes) and returns. An f64
  array becomes a `_AilTAF` (a list[float]), an int32 array a `_AilTAI` (a list[int]); prelude_ailarray.py holds the
  functions and is plain Python as well, so CPython runs the lowered text and the tests compare it with the reference
  `ail_array.py` before any C is involved;
* operators, indexing, slices, `len`, iteration and printing on a value of known array kind become direct calls of those
  functions (typed path, no dispatch); an array whose kind cannot be told where the lowering needs it is refused with
  file:line and what to write instead; the dtypes f32, f16 and int8 are stage T3 and refused by name.

A refusal leaves the program as written and adds a `note:` line (the same convention as stdlib5), after which the build
fails because the program's own `ail_array.py` is not in the subset.
"""
import ast
import sys
from pathlib import Path

_here = str(Path(__file__).parent)
if _here not in sys.path:
    sys.path.insert(0, _here)

import stdlib5
from stdlib4 import Refused, refuse

MODULE = 'ail_array'
API = {'DType', 'Array', 'f64', 'f32', 'f16', 'int8', 'int32', 'array', 'zeros', 'full', 'arange', 'frombytes', 'sqrt',
       'exp', 'log', 'tanh', 'minimum', 'maximum', 'clip', 'wrapping_add', 'wrapping_sub', 'wrapping_mul',
       'saturating_add', 'saturating_sub', 'sum', 'dot', 'min', 'max', 'argmin', 'argmax'}
DTYPES = {'f64': 'F', 'int32': 'I'}
LATER = {'f32', 'f16', 'int8'}          # stage T3
OUTSIDE = {'bf16', 'uint8', 'int16', 'int64', 'bool_', 'uint16', 'uint32', 'uint64', 'float32', 'float16'}
ARR = ('AF', 'AI')
SCALAR = ('F', 'I', 'B')
CLASS = {'F': '_AilTAF', 'I': '_AilTAI'}
P = {'F': '_ail_taf_', 'I': '_ail_tai_'}
AKIND = {'F': 'AF', 'I': 'AI'}
MATH_FLOAT = {'sqrt', 'exp', 'log', 'log2', 'log10', 'sin', 'cos', 'tan', 'fabs', 'pow', 'tanh', 'atan', 'atan2', 'hypot',
              'fmod', 'copysign', 'cbrt', 'exp2', 'expm1', 'log1p', 'asin', 'acos', 'sinh', 'cosh', 'degrees', 'radians'}
MATH_INT = {'floor', 'ceil', 'trunc', 'isqrt', 'gcd', 'lcm', 'factorial', 'comb', 'perm'}
SIG = {
    'array': ('values', 'dtype'), 'zeros': ('shape', 'dtype'), 'full': ('shape', 'value', 'dtype'),
    'arange': ('n', 'dtype'), 'frombytes': ('data', 'dtype'),
    'sqrt': ('a',), 'exp': ('a',), 'log': ('a',), 'tanh': ('a',),
    'minimum': ('a', 'b'), 'maximum': ('a', 'b'), 'clip': ('a', 'lo', 'hi'),
    'wrapping_add': ('a', 'b'), 'wrapping_sub': ('a', 'b'), 'wrapping_mul': ('a', 'b'),
    'saturating_add': ('a', 'b'), 'saturating_sub': ('a', 'b'),
    'sum': ('a', 'acc', 'order'), 'dot': ('a', 'b', 'acc', 'order'), 'min': ('a', 'order'), 'max': ('a', 'order'),
    'argmin': ('a',), 'argmax': ('a',),
}
OPS = {ast.Add: (0, '+'), ast.Sub: (1, '-'), ast.Mult: (2, '*'), ast.Div: (3, '/'), ast.FloorDiv: (3, '//'),
       ast.Mod: (4, '%')}
BUILTIN_ITER = {'list', 'sorted', 'sum', 'min', 'max', 'enumerate', 'zip', 'reversed'}
BUILTIN_SHOW = {'print', 'str', 'repr'}
UNSUPPORTED_METHODS = {'append': 'ail_array arrays have a fixed length; write instead: ta.zeros(n, ...) and index, or a list',
                       'extend': None, 'insert': None, 'pop': None, 'remove': None, 'resize': None}
PRELUDE_SOURCE = []


def no(node, what, instead):
    refuse(node, 'ail_array: %s; write instead: %s' % (what, instead))


def n(identifier):
    return ast.Name(id=identifier, ctx=ast.Load())


def call(fn, *args):
    return ast.Call(func=n(fn), args=list(args), keywords=[])


def const(value):
    return ast.Constant(value=value)


def prelude_source():
    if not PRELUDE_SOURCE:
        PRELUDE_SOURCE.append(stdlib5.prelude('ailarray'))
    return PRELUDE_SOURCE[0]


# ---------------------------------------------------------------------------------------------------------------------
# kinds: AF AI (arrays), F I B S (float int bool str), LF LI (lists), BY BA (bytes, bytearray), R (range), None (unknown)
# ---------------------------------------------------------------------------------------------------------------------
CONFLICT = object()


def target_names(target):
    """The plain names an assignment target binds (not the names inside `a[i]` or `x.y` targets)."""
    if isinstance(target, ast.Name):
        return [target]
    if isinstance(target, (ast.Tuple, ast.List)):
        return [x for e in target.elts for x in target_names(e)]
    if isinstance(target, ast.Starred):
        return target_names(target.value)
    return []


class Typer:
    def __init__(self, tree, binder):
        self.tree = tree
        self.b = binder
        self.funcs = {s.name: s for s in tree.body if isinstance(s, ast.FunctionDef)}
        self.ret = {}
        self.param = {}         # function name -> {param name: kind}
        self.seen = {}          # function name -> {param name: set of kinds passed}
        self.genv = {}          # module level names
        self.fenv = {}          # function name -> env
        self.memo = {}
        self.seed = {}
        self.math = self.math_aliases()

    def math_aliases(self):
        out = set()
        for s in self.tree.body:
            if isinstance(s, ast.Import):
                out.update(a.asname or a.name for a in s.names if a.name == 'math')
        return out

    # -- annotations -------------------------------------------------------------------------------------------------
    def dtype_kind(self, node):
        """'F' or 'I' for a `ta.f64` / `ta.int32` expression; a refusal for the other dtypes."""
        found = self.b.attr(node)
        if found in DTYPES:
            return DTYPES[found]
        if found in LATER:
            no(node, '%s arrays are stage T3 of the typed arrays and not built here' % found,
               'ta.f64 or ta.int32 (the program runs unchanged under CPython)')
        if found in OUTSIDE or found == 'DType':
            no(node, 'ail_array has f64, f32, f16, int8, int32', 'ta.int32 (or a list)')
        if found is not None:
            no(node, 'ta.%s is not a dtype' % found, 'ta.f64 or ta.int32')
        no(node, 'the dtype is not known at compile time', 'a literal ta.f64 or ta.int32 here')

    def annot_kind(self, node):
        if node is None:
            return None
        if isinstance(node, ast.Subscript) and self.b.attr(node.value) == 'Array':
            return AKIND[self.dtype_kind(node.slice)]
        if self.b.attr(node) == 'Array':
            no(node, 'the dtype of this array annotation is not known', 'ta.Array[ta.f64] or ta.Array[ta.int32]')
        if isinstance(node, ast.Name):
            return {'float': 'F', 'int': 'I', 'bool': 'B', 'str': 'S', 'bytes': 'BY', 'bytearray': 'BA'}.get(node.id)
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == 'list' \
                and isinstance(node.slice, ast.Name):
            return {'float': 'LF', 'int': 'LI'}.get(node.slice.id)
        return None

    # -- expression kinds --------------------------------------------------------------------------------------------
    def kind(self, node, env):
        key = (id(node), id(env))
        if key not in self.memo:
            self.memo[key] = (node, env, self.kind_of(node, env))      # keeps node and env alive: ids are not reused
        return self.memo[key][2]

    def lookup(self, name, env):
        if name in env:
            v = env[name]
        elif name in self.seed:
            v = self.seed[name]
        else:
            v = self.genv.get(name)
        return None if v is CONFLICT else v

    def kind_of(self, node, env):
        k = self.kind
        if isinstance(node, ast.Constant):
            v = node.value
            if isinstance(v, bool):
                return 'B'
            return {int: 'I', float: 'F', str: 'S', bytes: 'BY'}.get(type(v))
        if isinstance(node, ast.Name):
            return self.lookup(node.id, env)
        if isinstance(node, ast.UnaryOp):
            v = k(node.operand, env)
            if isinstance(node.op, ast.Not):
                return 'B'
            if v == 'B':
                return 'I'
            return v if v in ARR + ('F', 'I') else None
        if isinstance(node, ast.BinOp):
            return self.binop_kind(node, env)
        if isinstance(node, (ast.Compare,)):
            return 'B'
        if isinstance(node, ast.BoolOp):
            ks = {k(v, env) for v in node.values}
            return ks.pop() if len(ks) == 1 else None
        if isinstance(node, ast.IfExp):
            a, b = k(node.body, env), k(node.orelse, env)
            return a if a == b else None
        if isinstance(node, ast.JoinedStr):
            return 'S'
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in self.math                 and node.attr in ('inf', 'nan', 'pi', 'e', 'tau'):
            return 'F'
        if isinstance(node, ast.Subscript):
            v = k(node.value, env)
            if v in ARR:
                return v if isinstance(node.slice, ast.Slice) else ('F' if v == 'AF' else 'I') \
                    if not isinstance(node.slice, ast.Tuple) else None
            if v in ('LF', 'LI'):
                return v if isinstance(node.slice, ast.Slice) else ('F' if v == 'LF' else 'I')
            return None
        if isinstance(node, ast.List):
            ks = {k(e, env) for e in node.elts}
            if ks == {'F'}:
                return 'LF'
            if ks == {'I'}:
                return 'LI'
            return None
        if isinstance(node, ast.ListComp) and len(node.generators) == 1:
            sub = self.comp_env(node.generators, env)
            e = k(node.elt, sub)
            return {'F': 'LF', 'I': 'LI'}.get(e)
        if isinstance(node, ast.Call):
            return self.call_kind(node, env)
        return None

    def comp_env(self, gens, env):
        sub = dict(env)
        for g in gens:
            fresh = {}
            self.bind_target(g.target, g.iter, fresh)
            sub.update({k: (None if v is CONFLICT else v) for k, v in fresh.items()})
        return sub

    def elem_kind(self, it, env):
        if isinstance(it, (ast.Tuple, ast.List)) and it.elts:
            ks = {self.kind(e, env) for e in it.elts}
            if len(ks) == 1:
                k = ks.pop()
                return 'I' if k == 'B' else k if k in ('F', 'I', 'S') else None
            return None
        v = self.kind(it, env)
        if v in ('AF', 'LF'):
            return 'F'
        if v in ('AI', 'LI', 'R'):
            return 'I'
        if isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == 'range':
            return 'I'
        return None

    def binop_kind(self, node, env):
        l, r = self.kind(node.left, env), self.kind(node.right, env)
        op = type(node.op)
        if l in ARR or r in ARR:
            if op not in OPS:
                return None
            if l in ARR:
                return l
            return r
        num = ('F', 'I', 'B')
        if l in num and r in num:
            if op is ast.Div:
                return 'F'
            if 'F' in (l, r):
                return 'F' if op in (ast.Add, ast.Sub, ast.Mult, ast.Mod, ast.FloorDiv, ast.Pow) else None
            if op in (ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Mod, ast.LShift, ast.RShift, ast.BitAnd, ast.BitOr,
                      ast.BitXor):
                return 'I'
            if op is ast.Pow and isinstance(node.right, ast.Constant) and isinstance(node.right.value, int)                     and node.right.value >= 0:
                return 'I'
            return None
        if l == 'S' and r == 'S' and op is ast.Add:
            return 'S'
        if l in ('LF', 'LI') and r in ('I', 'B') and op is ast.Mult:
            return l
        return None

    def call_kind(self, node, env):
        found = self.b.attr(node.func)
        if found is not None:
            return self.module_call_kind(node, found, env)
        f = node.func
        if isinstance(f, ast.Name):
            args = [self.kind(a, env) for a in node.args]
            if f.id in self.funcs:
                return self.ret.get(f.id)
            first = args[0] if args else None
            if f.id in ('len', 'int', 'round', 'ord'):
                return 'I'
            if f.id == 'float':
                return 'F'
            if f.id in ('str', 'repr', 'chr'):
                return 'S'
            if f.id == 'bool':
                return 'B'
            if f.id == 'abs':
                return first if first in ARR + ('F', 'I') else ('I' if first == 'B' else None)
            if f.id in ('sum', 'min', 'max') and len(args) == 1 and not node.keywords:
                return {'AF': 'F', 'AI': 'I', 'LF': 'F', 'LI': 'I'}.get(first)
            if f.id == 'sorted' and len(args) == 1:
                return {'AF': 'LF', 'AI': 'LI', 'LF': 'LF', 'LI': 'LI'}.get(first)
            if f.id == 'list' and len(args) == 1:
                return {'AF': 'LF', 'AI': 'LI', 'LF': 'LF', 'LI': 'LI'}.get(first)
            if f.id == 'range':
                return 'R'
            if f.id == 'bytearray':
                return 'BA'
            if f.id == 'bytes':
                return 'BY'
            return None
        if isinstance(f, ast.Attribute):
            if isinstance(f.value, ast.Name) and f.value.id in self.math:
                if f.attr in MATH_FLOAT:
                    return 'F'
                if f.attr in MATH_INT:
                    return 'I'
                return None
            v = self.kind(f.value, env)
            if v in ARR:
                if f.attr == 'copy':
                    return v
                if f.attr == 'tolist':
                    return 'LF' if v == 'AF' else 'LI'
                if f.attr == 'tobytes':
                    return 'BY'
                if f.attr == 'astype' and node.args:
                    try:
                        return AKIND[self.dtype_kind(node.args[0])]
                    except Refused:
                        return None
            return None
        return None

    def module_call_kind(self, node, found, env):
        if found not in SIG:
            return None
        try:
            args = self.bind(node, found)
        except Refused:
            return None
        if found in ('array', 'zeros', 'full', 'arange', 'frombytes'):
            if 'dtype' not in args:
                return None
            try:
                return AKIND[self.dtype_kind(args['dtype'])]
            except Refused:
                return None
        a = self.kind(args['a'], env) if 'a' in args else None
        if found in ('sqrt', 'exp', 'log', 'tanh'):
            return 'AF'
        if found in ('minimum', 'maximum', 'clip'):
            return a if a in ARR else None
        if found.startswith('wrapping') or found.startswith('saturating'):
            return 'AI'
        if found in ('sum', 'dot', 'min', 'max'):
            return {'AF': 'F', 'AI': 'I'}.get(a)
        if found in ('argmin', 'argmax'):
            return 'I'
        return None

    def bind(self, node, found):
        """{parameter name: argument node} of a call of a module function."""
        names = SIG[found]
        out = {}
        if any(isinstance(a, ast.Starred) for a in node.args) or any(k.arg is None for k in node.keywords):
            no(node, 'ta.%s with * or ** arguments' % found, 'the arguments written out')
        if len(node.args) > len(names):
            no(node, 'ta.%s given too many arguments' % found, 'ta.%s(%s)' % (found, ', '.join(names)))
        for name, arg in zip(names, node.args):
            out[name] = arg
        for kw in node.keywords:
            if kw.arg not in names or kw.arg in out:
                no(node, 'ta.%s(%s=...) is not a parameter it takes' % (found, kw.arg), 'ta.%s(%s)' % (found, ', '.join(names)))
            out[kw.arg] = kw.value
        return out

    # -- fixpoint over bindings ---------------------------------------------------------------------------------------
    def analyze(self):
        for _ in range(8):
            before = (dict(self.ret), {k: dict(v) for k, v in self.param.items()},
                      {k: dict(v) for k, v in self.fenv.items()}, dict(self.genv))
            self.memo.clear()
            self.seen = {name: {} for name in self.funcs}
            genv = {}
            self.seed = self.genv
            self.bindings(self.tree.body, genv, None)
            self.genv = genv
            for name, fn in self.funcs.items():
                self.seed = self.fenv.get(name, {})
                env = {}
                for arg in fn.args.args + fn.args.kwonlyargs:
                    kd = self.annot_kind(arg.annotation)
                    if kd is None:
                        kd = self.param.get(name, {}).get(arg.arg)
                    env[arg.arg] = kd
                rets = []
                self.bindings(fn.body, env, rets)
                self.fenv[name] = env
                declared = self.annot_kind(fn.returns)
                if declared is not None:
                    self.ret[name] = declared
                else:
                    ks = set(rets)
                    self.ret[name] = ks.pop() if len(ks) == 1 else None
            self.seed = {}
            for name, fn in self.funcs.items():
                params = {}
                for arg in fn.args.args:
                    got = self.seen[name].get(arg.arg)
                    if got and None not in got and len(got) == 1:
                        params[arg.arg] = next(iter(got))
                self.param[name] = params
            after = (dict(self.ret), {k: dict(v) for k, v in self.param.items()},
                     {k: dict(v) for k, v in self.fenv.items()}, dict(self.genv))
            if before == after:
                break
        self.memo.clear()
        self.check_params()

    def check_params(self):
        """A parameter without an annotation that receives arrays must receive one array kind from every call."""
        for name, fn in self.funcs.items():
            for arg in fn.args.args:
                got = self.seen.get(name, {}).get(arg.arg, set())
                arrays = {k for k in got if k in ARR}
                if arrays and arg.annotation is None and (len(arrays) > 1 or got != arrays):
                    no(fn, "parameter '%s' of %s() receives %s from the calls in this program" % (
                        arg.arg, name, 'both f64 and int32 arrays' if len(arrays) > 1 else
                        'an array from one call and something else (or something unknown) from another'),
                       "one function per dtype, or annotate it (%s: ta.Array[ta.f64])" % arg.arg)

    def bind_target(self, target, it, env):
        """The kinds a `for target in it` binds: elements of a sequence, (index, element) of enumerate, zip's columns."""
        if isinstance(target, ast.Name):
            self.bind_name(env, target.id, self.elem_kind(it, env))
            return
        kinds = None
        if isinstance(target, ast.Tuple) and isinstance(it, ast.Call) and isinstance(it.func, ast.Name)                 and not it.keywords and all(isinstance(e, ast.Name) for e in target.elts):
            if it.func.id == 'enumerate' and len(it.args) == 1 and len(target.elts) == 2:
                kinds = ['I', self.elem_kind(it.args[0], env)]
            elif it.func.id == 'zip' and len(it.args) == len(target.elts):
                kinds = [self.elem_kind(a, env) for a in it.args]
        if kinds is not None:
            for e, kd in zip(target.elts, kinds):
                self.bind_name(env, e.id, kd)
            return
        for e in target_names(target):
            self.bind_name(env, e.id, None)

    def bind_name(self, env, name, kd):
        if name not in env:
            env[name] = kd
        elif env[name] != kd:
            env[name] = CONFLICT

    def bindings(self, stmts, env, rets):
        """Record the kind of every name the statements bind (not descending into nested functions or classes)."""
        for st in stmts:
            self.statement(st, env, rets)

    def statement(self, st, env, rets):
        if isinstance(st, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
            return
        self.calls_in(st, env)
        if isinstance(st, ast.Assign):
            kd = self.kind(st.value, env)
            for t in st.targets:
                if isinstance(t, ast.Name):
                    self.bind_name(env, t.id, kd)
                elif isinstance(t, (ast.Tuple, ast.List)):
                    for e in target_names(t):
                        self.bind_name(env, e.id, None)
        elif isinstance(st, ast.AnnAssign):
            if isinstance(st.target, ast.Name):
                kd = self.annot_kind(st.annotation)
                if kd is None and st.value is not None:
                    kd = self.kind(st.value, env)
                self.bind_name(env, st.target.id, kd)
        elif isinstance(st, ast.AugAssign):
            if isinstance(st.target, ast.Name):
                cur = self.lookup(st.target.id, env)
                if cur in ARR:
                    kd = cur
                else:
                    kd = self.binop_kind(ast.BinOp(left=st.target, op=st.op, right=st.value), env)
                self.bind_name(env, st.target.id, kd)
        elif isinstance(st, ast.For):
            self.bind_target(st.target, st.iter, env)
        elif isinstance(st, ast.Return) and rets is not None:
            rets.append(self.kind(st.value, env) if st.value is not None else None)
        elif isinstance(st, (ast.With, ast.AsyncWith)):
            for item in st.items:
                if isinstance(item.optional_vars, ast.Name):
                    self.bind_name(env, item.optional_vars.id, None)
        elif isinstance(st, ast.Try):
            for h in st.handlers:
                if h.name:
                    self.bind_name(env, h.name, None)
        for field in ('body', 'orelse', 'finalbody'):
            sub = getattr(st, field, None)
            if isinstance(sub, list) and sub and isinstance(sub[0], ast.stmt):
                self.bindings(sub, env, rets)
        if isinstance(st, ast.Try):
            for h in st.handlers:
                self.bindings(h.body, env, rets)
        if isinstance(st, ast.Match):
            for case in st.cases:
                self.bindings(case.body, env, rets)

    def calls_in(self, st, env):
        """Record what the calls of module functions in this statement's own expressions pass."""
        exprs = []
        for field, value in ast.iter_fields(st):
            if field in ('body', 'orelse', 'finalbody', 'handlers', 'cases'):
                continue
            if isinstance(value, ast.expr):
                exprs.append(value)
            elif isinstance(value, list):
                exprs.extend(v for v in value if isinstance(v, ast.expr))
        for top in exprs:
            for each in ast.walk(top):
                if isinstance(each, ast.Call) and isinstance(each.func, ast.Name) and each.func.id in self.funcs:
                    fn = self.funcs[each.func.id]
                    names = [a.arg for a in fn.args.args]
                    seen = self.seen[each.func.id]
                    for name, arg in zip(names, each.args):
                        seen.setdefault(name, set()).add(self.kind(arg, env))
                    for kw in each.keywords:
                        if kw.arg in names:
                            seen.setdefault(kw.arg, set()).add(self.kind(kw.value, env))
                    for name in names[len(each.args):]:
                        if name not in {kw.arg for kw in each.keywords}:
                            seen.setdefault(name, set()).add(None)


# ---------------------------------------------------------------------------------------------------------------------
class Lower(ast.NodeTransformer):
    def __init__(self, typer):
        self.t = typer
        self.b = typer.b
        self.env = typer.genv
        self.temp = 0

    # -- helpers ---------------------------------------------------------------------------------------------------------
    def k(self, node):
        return self.t.kind(node, self.env)

    def pure(self, node):
        if isinstance(node, (ast.Name, ast.Constant)):
            return True
        if isinstance(node, ast.Attribute):
            return self.pure(node.value)
        if isinstance(node, ast.UnaryOp):
            return self.pure(node.operand)
        if isinstance(node, ast.BinOp):
            return self.pure(node.left) and self.pure(node.right)
        if isinstance(node, ast.Subscript):
            return self.pure(node.value) and self.pure(node.slice)
        return False

    def need_pure(self, node, what):
        if not self.pure(node):
            no(node, what + ' with an operand that is more than a name, a constant or a subscript of them',
               'bind the operand to a name first')

    def scalar(self, node, kd, dt, what):
        """The visited operand `node` of kind `kd` stored into an array of dtype `dt` ('F' or 'I')."""
        new = self.visit(node)
        if kd == 'F':
            return new if dt == 'F' else None
        if kd in ('I', 'B'):
            if dt == 'F':
                return call('float', new) if kd == 'I' else call('_ail_ta_b2f', new)
            return new if kd == 'I' else call('_ail_ta_b2i', new)
        no(node, 'cannot tell whether this operand is a number or an array', 'annotate it (x: float, x: int or x: ta.Array[ta.f64])')

    def shown(self, node):
        """str(array) of the visited array expression."""
        kd = self.k(node)
        return call(P[kd[1]] + 'repr', self.visit(node))

    def array_arg(self, node, what):
        kd = self.k(node)
        if kd not in ARR:
            no(node, '%s needs an array whose dtype is known at compile time' % what,
               'annotate the argument (a: ta.Array[ta.f64]) or build it with ta.array(..., ta.f64)')
        return kd

    def truth(self, test):
        if test is not None and self.k(test) in ARR:
            no(test, 'the truth value of an array', 'len(a) > 0')

    # -- statements ----------------------------------------------------------------------------------------------------------
    def visit_FunctionDef(self, node):
        saved = self.env
        self.env = self.t.fenv.get(node.name) if node.name in self.t.funcs and node in self.t.tree.body else None
        if self.env is None:
            env = {}
            for arg in node.args.args + node.args.kwonlyargs:
                env[arg.arg] = self.t.annot_kind(arg.annotation)
            rets = []
            self.t.bindings(node.body, env, rets)
            self.env = env
        for arg in node.args.args + node.args.kwonlyargs + ([node.args.vararg] if node.args.vararg else []) + \
                ([node.args.kwarg] if node.args.kwarg else []):
            arg.annotation = self.annot(arg.annotation)
        node.returns = self.annot(node.returns)
        node.decorator_list = [self.visit(d) for d in node.decorator_list]
        node.args.defaults = [self.visit(d) for d in node.args.defaults]
        node.body = self.block(node.body)
        self.env = saved
        return node

    def annot(self, node):
        if node is None:
            return None
        if self.b.attr(node) == 'Array':
            no(node, 'the dtype of this array annotation is not known', 'ta.Array[ta.f64] or ta.Array[ta.int32]')
        if isinstance(node, ast.Subscript) and self.b.attr(node.value) == 'Array':
            return n(CLASS[self.t.dtype_kind(node.slice)])
        if isinstance(node, ast.Subscript):
            node.slice = self.annot(node.slice)
            return node
        if isinstance(node, ast.Tuple):
            node.elts = [self.annot(e) for e in node.elts]
        return node

    def block(self, stmts):
        out = []
        for st in stmts:
            new = self.visit(st)
            if new is None:
                continue
            if isinstance(new, list):
                out.extend(new)
            else:
                out.append(new)
        return out or [ast.Pass()]

    def visit_ClassDef(self, node):
        saved = self.env
        self.env = {}
        node.body = self.block(node.body)
        node.bases = [self.visit(x) for x in node.bases]
        self.env = saved
        return node

    def visit_AnnAssign(self, node):
        kd = self.t.annot_kind(node.annotation)
        node.annotation = self.annot(node.annotation)
        if node.value is not None:
            node.value = self.visit(node.value)
        return node

    def visit_If(self, node):
        self.truth(node.test)
        self.generic_visit(node)
        return node

    visit_While = visit_If

    def visit_Assert(self, node):
        self.truth(node.test)
        self.generic_visit(node)
        return node

    def visit_IfExp(self, node):
        self.truth(node.test)
        self.generic_visit(node)
        return node

    def visit_BoolOp(self, node):
        for v in node.values:
            if self.k(v) in ARR:
                no(v, 'an array as an operand of and/or', 'len(a) > 0')
        self.generic_visit(node)
        return node

    def print_hazard(self, call_node):
        """print(a, f(a)): CPython evaluates every argument and only then calls str() on each, so an array shown
        before a later argument mutates it must be shown after; true when an impure argument follows an array one."""
        ks = [self.k(a) in ARR for a in call_node.args]
        if not any(ks):
            return None
        first = ks.index(True)
        last = max([i for i, a in enumerate(call_node.args) if not self.pure(a)] or [-1])
        return last if last > first else None

    def visit_Expr(self, node):
        v = node.value
        if isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and v.func.id == 'print'                 and 'print' not in self.t.funcs and not any(isinstance(a, ast.Starred) for a in v.args):
            last = self.print_hazard(v)
            if last is not None:
                stmts, args = [], []
                self.env = dict(self.env)
                for i, a in enumerate(v.args[:last + 1]):
                    self.temp += 1
                    name = '_ail_ta_t%d' % self.temp
                    kd = self.k(a)
                    stmts.append(ast.Assign(targets=[ast.Name(id=name, ctx=ast.Store())], value=self.visit(a)))
                    self.env[name] = kd
                    args.append(ast.Name(id=name, ctx=ast.Load()))
                args += v.args[last + 1:]
                stmts.append(ast.Expr(value=ast.Call(func=v.func, args=args, keywords=v.keywords)))
                return [self.visit(x) if isinstance(x, ast.Expr) else x for x in stmts]
        self.generic_visit(node)
        return node

    def visit_Delete(self, node):
        for t in node.targets:
            if isinstance(t, ast.Subscript) and self.k(t.value) in ARR:
                no(node, 'del on an array element', 'ail_array arrays have a fixed length; write instead: a list')
        self.generic_visit(node)
        return node

    def visit_For(self, node):
        if self.k(node.iter) in ARR:
            node.iter = self.iter_of(node.iter)
        else:
            node.iter = self.visit(node.iter)
        node.target = self.visit(node.target)
        node.body = self.block(node.body)
        node.orelse = [self.visit(s) for s in node.orelse] if node.orelse else []
        return node

    def iter_of(self, node):
        return ast.Attribute(value=self.visit(node), attr='d', ctx=ast.Load())

    def visit_comprehension(self, node):
        if self.k(node.iter) in ARR:
            node.iter = self.iter_of(node.iter)
        else:
            node.iter = self.visit(node.iter)
        node.ifs = [self.visit(x) for x in node.ifs]
        return node

    def comp(self, node):
        saved = self.env
        self.env = self.t.comp_env(node.generators, self.env)
        node.generators = [self.visit_comprehension(g) for g in node.generators]
        for field in ('elt', 'key', 'value'):
            if hasattr(node, field):
                setattr(node, field, self.visit(getattr(node, field)))
        self.env = saved
        return node

    visit_ListComp = visit_SetComp = visit_GeneratorExp = visit_DictComp = comp

    def visit_Lambda(self, node):
        saved = self.env
        self.env = dict(self.env)
        for arg in node.args.args:
            self.env[arg.arg] = None
        node.body = self.visit(node.body)
        self.env = saved
        return node

    def visit_Return(self, node):
        if node.value is not None:
            node.value = self.visit(node.value)
        return node

    def visit_Assign(self, node):
        targets = node.targets
        if len(targets) == 1 and isinstance(targets[0], (ast.Tuple, ast.List)):
            return self.tuple_assign(node)
        out = []
        value = node.value
        subs = [t for t in targets if isinstance(t, ast.Subscript) and self.k(t.value) in ARR]
        if subs:
            if len(targets) != 1:
                no(node, 'a chained assignment into array elements', 'one assignment per target')
            return self.store(targets[0], value, node)
        node.targets = [self.visit(t) for t in targets]
        node.value = self.visit(value)
        return node

    def tuple_assign(self, node):
        t = node.targets[0]
        if not any(isinstance(e, ast.Subscript) and self.k(e.value) in ARR for e in ast.walk(t)):
            node.targets = [self.visit(t)]
            node.value = self.visit(node.value)
            return node
        if not isinstance(node.value, (ast.Tuple, ast.List)) or len(node.value.elts) != len(t.elts) or \
                any(isinstance(e, ast.Starred) for e in t.elts + node.value.elts):
            no(node, 'a tuple assignment into array elements from something other than a tuple of the same length',
               'one assignment per element')
        temps = []
        stmts = []
        for k, e in enumerate(t.elts):
            self.temp += 1
            temps.append('_ail_ta_t%d' % self.temp)
        first = ast.Assign(targets=[ast.Tuple(elts=[ast.Name(id=x, ctx=ast.Store()) for x in temps], ctx=ast.Store())],
                           value=ast.Tuple(elts=[self.visit(v) for v in node.value.elts], ctx=ast.Load()))
        stmts.append(first)
        for e, x, v in zip(t.elts, temps, node.value.elts):
            tmp = ast.Name(id=x, ctx=ast.Load())
            kd = self.k(v)
            self.env = dict(self.env)
            self.env[x] = kd
            if isinstance(e, ast.Subscript) and self.k(e.value) in ARR:
                got = self.store(e, tmp, node)
                stmts.append(got)
            else:
                stmts.append(ast.Assign(targets=[self.visit(e)], value=tmp))
        return [ast.copy_location(s, node) for s in stmts]

    def store(self, target, value, node):
        """`a[i] = value`, `a[i:j] = value` on an array."""
        kd = self.k(target.value)
        dt = kd[1]
        arr = self.visit(target.value)
        idx = target.slice
        if isinstance(idx, ast.Tuple):
            no(node, 'an index with several parts (2-D arrays are a later stage)', 'a 1-D array and a computed index')
        vkind = self.k(value)
        if isinstance(idx, ast.Slice):
            if vkind not in ARR:
                if vkind is None:
                    no(node, 'cannot tell the type of the value assigned to a slice', 'annotate it (b: ta.Array[ta.f64])')
                return ast.Expr(value=call('_ail_ta_te_' + ('af' if dt == 'F' else 'ai'),
                                           const('ail_array: can only assign an ail_array.Array to a slice, not %s' %
                                                 {'F': 'float', 'I': 'int', 'B': 'bool', 'S': 'str', 'LF': 'list',
                                                  'LI': 'list', 'BY': 'bytes', 'BA': 'bytearray'}.get(vkind, 'object'))))
            if vkind != kd:
                return ast.Expr(value=call('_ail_ta_te_' + ('af' if dt == 'F' else 'ai'),
                                           const('ail_array: slice assignment: dtypes differ (%s and %s)' %
                                                 ('f64' if dt == 'F' else 'int32', 'f64' if vkind == 'AF' else 'int32'))))
            lo, hi, st, flags = self.slice_args(idx)
            return ast.Expr(value=call(P[dt] + 'setslice', arr, lo, hi, st, flags, self.visit(value)))
        ik = self.k(idx)
        if ik in ARR or ik in ('LF', 'LI'):
            no(node, 'fancy indexing or a mask', 'a loop, or ta.minimum/ta.maximum/ta.clip')
        if ik in ('F', 'S'):
            no(node, 'an index that is not an int', 'an int index')
        index = self.visit(idx)
        if dt == 'F':
            if vkind not in SCALAR:
                no(node, 'cannot tell whether the stored value is a number', 'annotate it (x: float)')
            val = self.visit(value) if vkind == 'F' else call('float' if vkind == 'I' else '_ail_ta_b2f', self.visit(value))
            return ast.Expr(value=call('_ail_taf_set', arr, index, val))
        if vkind in ('I', 'B'):
            val = self.visit(value) if vkind == 'I' else call('_ail_ta_b2i', self.visit(value))
            return ast.Expr(value=call('_ail_tai_set', arr, index, val))
        if vkind == 'F':
            return ast.Expr(value=call('_ail_tai_set_bad', arr, index, const('float')))
        no(node, 'cannot tell whether the stored value is an int', 'annotate it (x: int)')

    def slice_args(self, sl):
        flags = 0
        parts = []
        for bit, part in ((1, sl.lower), (2, sl.upper), (4, sl.step)):
            if part is None:
                parts.append(const(0))
            else:
                pk = self.k(part)
                if pk in ('F', 'S') or pk in ARR:
                    no(part, 'a slice bound that is not an int', 'an int bound')
                flags |= bit
                parts.append(self.visit(part))
        return parts[0], parts[1], parts[2], const(flags)

    def visit_AugAssign(self, node):
        target = node.target
        if isinstance(target, ast.Name):
            kd = self.t.lookup(target.id, self.env)
            if kd in ARR:
                return ast.Assign(targets=[ast.Name(id=target.id, ctx=ast.Store())],
                                  value=self.arith(target, node.op, node.value, node, True))
        if isinstance(target, ast.Subscript) and self.k(target.value) in ARR:
            if not self.pure(target.slice) or isinstance(target.slice, ast.Slice):
                no(node, 'an augmented assignment into an array element with a slice or a computed index',
                   'a[i] = a[i] + x with i bound to a name')
            load = ast.Subscript(value=target.value, slice=target.slice, ctx=ast.Load())
            assign = ast.Assign(targets=[ast.Subscript(value=target.value, slice=target.slice, ctx=ast.Store())],
                                value=ast.BinOp(left=load, op=node.op, right=node.value))
            ast.copy_location(assign, node)
            ast.fix_missing_locations(assign)
            return self.visit(assign)
        self.generic_visit(node)
        return node

    # -- expressions --------------------------------------------------------------------------------------------------------
    def visit_Name(self, node):
        return node

    def visit_Attribute(self, node):
        if self.k(node.value) in ARR:
            if node.attr in ('dtype', 'shape'):
                no(node, 'a.%s' % node.attr, 'len(a) for the length; keep the dtype in your code')
            no(node, 'a.%s' % node.attr, 'a loop over the elements, or the functions of ail_array')
        self.generic_visit(node)
        return node

    def visit_UnaryOp(self, node):
        kd = self.k(node.operand)
        if kd in ARR:
            if isinstance(node.op, ast.USub):
                if kd == 'AF':
                    return call('_ail_taf_neg', self.visit(node.operand))
                return call('_ail_tai_unary', self.visit(node.operand), const(False))
            if isinstance(node.op, ast.Not):
                no(node, 'the truth value of an array', 'len(a) > 0')
            no(node, 'unary operator on an array', 'a loop over the elements')
        self.generic_visit(node)
        return node

    def visit_BinOp(self, node):
        lk, rk = self.k(node.left), self.k(node.right)
        if lk in ARR or rk in ARR:
            return self.arith(node.left, node.op, node.right, node, False)
        self.generic_visit(node)
        return node

    def arith(self, left, op, right, where, inplace):
        lk, rk = self.k(left), self.k(right)
        if isinstance(op, ast.MatMult):
            no(where, 'matrix multiply on arrays (2-D arrays are stage T6)', 'a loop, or ta.dot(a, b)')
        if type(op) not in OPS:
            no(where, 'this operator on arrays (** and the bit operators are not built)', 'a loop over a.tolist()')
        code, sym = OPS[type(op)]
        if lk in ARR:
            dt = lk[1]
            if dt == 'F' and sym in ('//', '%'):
                no(where, '%s on f64 arrays' % sym, 'a loop over a.tolist()')
            if dt == 'I' and sym == '/':
                no(where, '/ on int32 arrays', 'a.astype(ta.f64) / b.astype(ta.f64)')
            if rk in ARR:
                if rk != lk:
                    self.need_pure(left, 'a dtype mismatch')
                    self.need_pure(right, 'a dtype mismatch')
                    return call('_ail_ta_te_a' + dt.lower(), const(
                        'ail_array: %s %s %s: dtypes differ; write a.astype(ta.%s) or b.astype(ta.%s)' %
                        ('f64' if dt == 'F' else 'int32', sym, 'f64' if rk == 'AF' else 'int32',
                         'f64' if rk == 'AF' else 'int32', 'f64' if dt == 'F' else 'int32')))
                a, b = self.visit(left), self.visit(right)
                return call(P[dt] + ('ibin' if inplace else 'bin'), a, b, const(code))
            if dt == 'I' and rk == 'F':
                self.need_pure(left, 'an int32 array and a float')
                self.need_pure(right, 'an int32 array and a float')
                return call('_ail_ta_te_ai', const('ail_array: int32 %s float: write a.astype(ta.f64) (no implicit int-to-float)' % sym))
            a = self.visit(left)
            x = self.scalar(right, rk, dt, 'operand')
            if inplace:
                return call(P[dt] + 'ibin_s', a, x, const(code))
            return call(P[dt] + 'bin_s', a, x, const(code), const(False))
        # scalar op array
        dt = rk[1]
        if inplace:
            no(where, 'an in-place operator with an array on the right', 'a = a op b')
        if dt == 'F' and sym in ('//', '%'):
            no(where, '%s on f64 arrays' % sym, 'a loop over a.tolist()')
        if dt == 'I' and sym == '/':
            no(where, '/ on int32 arrays', 'a.astype(ta.f64) / b.astype(ta.f64)')
        if dt == 'I' and lk == 'F':
            no(where, 'a float and an int32 array', 'a.astype(ta.f64)')
        x = self.scalar(left, lk, dt, 'operand')
        a = self.visit(right)
        return call(P[dt] + 'bin_s', a, x, const(code), const(True))

    def visit_Compare(self, node):
        kinds = [self.k(node.left)] + [self.k(c) for c in node.comparators]
        if not any(k in ARR for k in kinds):
            self.generic_visit(node)
            return node
        if len(node.ops) != 1:
            no(node, 'a chained comparison of arrays', 'separate comparisons')
        op = node.ops[0]
        if isinstance(op, (ast.Is, ast.IsNot)):
            self.generic_visit(node)
            return node
        if isinstance(op, (ast.In, ast.NotIn)):
            no(node, 'membership in an array', 'a loop over the elements')
        if not isinstance(op, (ast.Eq, ast.NotEq)):
            no(node, 'element-wise comparison or ordering of arrays', 'a loop, or ta.minimum/ta.maximum/ta.clip')
        lk, rk = kinds
        if lk not in ARR or rk not in ARR:
            no(node, 'comparing an array with something that is not an array of known dtype',
               'len(a) == len(b) and a loop, or annotate the other operand')
        if lk == rk:
            res = call(P[lk[1]] + 'eq', self.visit(node.left), self.visit(node.comparators[0]))
        else:
            first, second = (node.left, node.comparators[0])
            res = call('_ail_ta_ne_dtype' if lk == 'AF' else '_ail_ta_ne_dtype2', self.visit(first), self.visit(second))
        if isinstance(op, ast.NotEq):
            return ast.UnaryOp(op=ast.Not(), operand=res)
        return res

    def visit_Subscript(self, node):
        kd = self.k(node.value)
        if kd not in ARR:
            self.generic_visit(node)
            return node
        dt = kd[1]
        idx = node.slice
        if isinstance(idx, ast.Tuple):
            no(node, 'an index with several parts (2-D arrays are a later stage)', 'a 1-D array and a computed index')
        arr = self.visit(node.value)
        if isinstance(idx, ast.Slice):
            lo, hi, st, flags = self.slice_args(idx)
            return call(P[dt] + 'slice', arr, lo, hi, st, flags)
        ik = self.k(idx)
        if ik in ARR or ik in ('LF', 'LI'):
            no(node, 'fancy indexing or a mask', 'a loop, or ta.minimum/ta.maximum/ta.clip')
        if ik in ('F', 'S'):
            self.need_pure(node.value, 'an index that is not an int')
            return call('_ail_ta_te_f' if dt == 'F' else '_ail_ta_te_i', const('array indices must be integers'))
        return call(P[dt] + 'get', arr, self.visit(idx))

    def visit_JoinedStr(self, node):
        vals = []
        for v in node.values:
            if isinstance(v, ast.FormattedValue) and self.k(v.value) in ARR:
                if v.format_spec is not None:
                    no(v, 'a format specification on an array', 'f"{a}" or a loop over the elements')
                vals.append(ast.FormattedValue(value=self.shown(v.value), conversion=-1, format_spec=None))
            else:
                vals.append(self.visit(v))
        node.values = vals
        return node

    # -- calls ------------------------------------------------------------------------------------------------------------------
    def visit_Call(self, node):
        found = self.b.attr(node.func)
        if found is not None:
            return self.module_call(node, found)
        f = node.func
        if isinstance(f, ast.Attribute) and self.k(f.value) in ARR:
            return self.method_call(node)
        argk = [self.k(a) for a in node.args] + [self.k(k.value) for k in node.keywords]
        if isinstance(f, ast.Name) and any(x in ARR for x in argk) and f.id not in self.t.funcs:
            if f.id == 'len' and len(node.args) == 1 and not node.keywords:
                return call('len', ast.Attribute(value=self.visit(node.args[0]), attr='d', ctx=ast.Load()))
            if f.id in ('str', 'repr') and len(node.args) == 1 and not node.keywords and self.k(node.args[0]) in ARR:
                return self.shown(node.args[0])
            if f.id == 'print' and self.print_hazard(node) is not None:
                no(node, 'print() of an array together with an argument that runs code after it (CPython shows the array after '
                   'that code ran)', 'bind the arguments to names first, then print')
            if f.id in BUILTIN_SHOW and all(k.arg in ('sep', 'end', 'file', 'flush') for k in node.keywords):
                node.args = [self.shown(a) if self.k(a) in ARR else self.visit(a) for a in node.args]
                node.keywords = [ast.keyword(arg=k.arg, value=self.visit(k.value)) for k in node.keywords]
                return node
            if f.id == 'abs' and len(node.args) == 1 and not node.keywords:
                kd = self.k(node.args[0])
                if kd == 'AF':
                    return call('_ail_taf_abs', self.visit(node.args[0]))
                return call('_ail_tai_unary', self.visit(node.args[0]), const(True))
            if f.id == 'list' and len(node.args) == 1 and not node.keywords:
                return call(P[self.k(node.args[0])[1]] + 'tolist', self.visit(node.args[0]))
            if f.id in BUILTIN_ITER:
                node.args = [self.iter_of(a) if self.k(a) in ARR else self.visit(a) for a in node.args]
                node.keywords = [ast.keyword(arg=k.arg, value=self.visit(k.value)) for k in node.keywords]
                return node
            no(node, '%s() applied to an array' % f.id, '%s(a.tolist())' % f.id)
        self.generic_visit(node)
        return node

    def method_call(self, node):
        f = node.func
        kd = self.k(f.value)
        dt = kd[1]
        attr = f.attr
        if attr in UNSUPPORTED_METHODS:
            no(node, 'arrays have a fixed length (a.%s)' % attr, 'ta.zeros(n, ...) and index, or a list')
        recv = self.visit(f.value)
        if attr == 'copy' and not node.args and not node.keywords:
            return call(P[dt] + 'copy', recv)
        if attr == 'tolist' and not node.args and not node.keywords:
            return call(P[dt] + 'tolist', recv)
        if attr == 'tobytes' and not node.args and not node.keywords:
            return call(P[dt] + 'tobytes', recv)
        if attr == 'astype':
            return self.astype(node, kd, recv)
        no(node, 'a.%s() is not built' % attr, 'the functions of ail_array, or a loop')

    def astype(self, node, kd, recv):
        names = ('dtype', 'rounding', 'overflow')
        args = {}
        for name, a in zip(names, node.args):
            args[name] = a
        for kw in node.keywords:
            if kw.arg not in names or kw.arg in args:
                no(node, 'astype(%s=...)' % kw.arg, 'astype(dtype, rounding, overflow)')
            args[kw.arg] = kw.value
        if 'dtype' not in args:
            no(node, 'astype without a dtype', 'a.astype(ta.f64)')
        dst = self.t.dtype_kind(args['dtype'])
        opts = {}
        for name, default in (('rounding', 'trunc'), ('overflow', 'raise')):
            v = args.get(name)
            if v is None:
                opts[name] = default
            elif isinstance(v, ast.Constant) and isinstance(v.value, str):
                opts[name] = v.value
            else:
                no(v, 'astype(%s=...) that is not a string literal' % name, "a literal such as 'trunc'")
        src = kd[1]
        mk = 'af' if dst == 'F' else 'ai'
        if opts['rounding'] not in ('trunc', 'nearest'):
            return call('_ail_ta_ve_' + mk, const("ail_array: rounding must be 'trunc' or 'nearest', not %r" % opts['rounding']))
        if opts['overflow'] not in ('raise', 'saturate', 'wrap'):
            return call('_ail_ta_ve_' + mk, const("ail_array: overflow must be 'raise', 'saturate' or 'wrap', not %r" % opts['overflow']))
        if dst == 'F':
            return call('_ail_taf_to_f64' if src == 'F' else '_ail_tai_to_f64', recv)
        if src == 'F':
            if opts['overflow'] == 'wrap':
                return call('_ail_ta_ve_ai', const("ail_array: overflow='wrap' is for int-to-int casts; use 'raise' or 'saturate'"))
            return call('_ail_taf_to_i32', recv, const(opts['rounding'] == 'nearest'),
                        const(1 if opts['overflow'] == 'saturate' else 0))
        return call('_ail_tai_copy', recv)

    def dtype_arg(self, node, args, found):
        if 'dtype' not in args:
            no(node, 'ta.%s without a dtype' % found, 'ta.%s(..., ta.f64)' % found)
        return self.t.dtype_kind(args['dtype'])

    def length(self, arg):
        if isinstance(arg, ast.Tuple):
            no(arg, 'a shape tuple (2-D arrays are stage T6, 3-D and more are not planned)', 'a length: ta.zeros(n, ta.f64)')
        kd = self.k(arg)
        if kd == 'B':
            return None
        if kd in ('F', 'S') or kd in ARR:
            no(arg, 'a length that is not an int', 'an int length')
        return self.visit(arg)

    def element(self, node, dt):
        """The visited list element `node` as a value of the dtype's element type."""
        kd = self.k(node)
        if dt == 'F':
            if kd == 'F':
                return self.visit(node)
            if kd == 'I':
                return call('float', self.visit(node))
            if kd == 'B':
                return call('_ail_ta_b2f', self.visit(node))
        else:
            if kd == 'I':
                return self.visit(node)
            if kd == 'B':
                return call('_ail_ta_b2i', self.visit(node))
        no(node, 'cannot tell that this list element is %s' % ('a number' if dt == 'F' else 'an int'),
           'annotate it, or build the array from a list of %s' % ('floats' if dt == 'F' else 'ints'))

    def values_of(self, node, dt):
        """A list expression of the elements of dtype `dt` made from the `values` argument of ta.array."""
        if isinstance(node, (ast.List, ast.Tuple)):
            return ast.List(elts=[self.element(e, dt) for e in node.elts], ctx=ast.Load())
        if isinstance(node, ast.ListComp) and len(node.generators) == 1:
            saved = self.env
            self.env = self.t.comp_env(node.generators, self.env)
            gens = [self.visit_comprehension(g) for g in node.generators]
            elt = self.element(node.elt, dt)
            self.env = saved
            return ast.ListComp(elt=elt, generators=gens)
        kd = self.k(node)
        want = 'LF' if dt == 'F' else 'LI'
        if kd == want:
            return self.visit(node)
        if kd in ARR:
            if kd[1] == dt:
                return ast.Attribute(value=self.visit(node), attr='d', ctx=ast.Load())
            if dt == 'F':
                return ast.ListComp(elt=call('float', n('_ail_v')), generators=[ast.comprehension(
                    target=ast.Name(id='_ail_v', ctx=ast.Store()), iter=ast.Attribute(value=self.visit(node), attr='d',
                                                                                     ctx=ast.Load()), ifs=[], is_async=0)])
        if kd in ('LI', 'R') and dt == 'F':
            return ast.ListComp(elt=call('float', n('_ail_v')), generators=[ast.comprehension(
                target=ast.Name(id='_ail_v', ctx=ast.Store()), iter=self.visit(node), ifs=[], is_async=0)])
        if kd == 'R' and dt == 'I':
            return call('list', self.visit(node))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'range':
            if dt == 'F':
                return ast.ListComp(elt=call('float', n('_ail_v')), generators=[ast.comprehension(
                    target=ast.Name(id='_ail_v', ctx=ast.Store()), iter=self.visit(node), ifs=[], is_async=0)])
            return call('list', self.visit(node))
        no(node, 'cannot tell the element type of these values for a%s array' % ('n f64' if dt == 'F' else 'n int32'),
           'a list literal, a comprehension, or a list annotated as list[%s]' % ('float' if dt == 'F' else 'int'))

    def module_call(self, node, found):
        if found not in SIG:
            if found in DTYPES or found in LATER or found in OUTSIDE or found == 'DType':
                self.t.dtype_kind(node.func)
            no(node, 'ta.%s is not a function' % found, 'a call of one of its functions')
        args = self.t.bind(node, found)
        if found in ('array', 'zeros', 'full', 'arange', 'frombytes'):
            dt = self.dtype_arg(node, args, found)
            mk = 'af' if dt == 'F' else 'ai'
            if found == 'array':
                if 'values' not in args:
                    no(node, 'ta.array without values', 'ta.array(xs, ta.f64)')
                return call(P[dt] + 'from', self.values_of(args['values'], dt))
            if found == 'zeros':
                m = self.length(args['shape']) if 'shape' in args else None
                if 'shape' not in args:
                    no(node, 'ta.zeros without a length', 'ta.zeros(n, ta.f64)')
                if m is None:
                    return call('_ail_ta_te_' + mk, const('ail_array: a length must be an int, not bool'))
                return call(P[dt] + 'zeros', m)
            if found == 'full':
                if 'shape' not in args or 'value' not in args:
                    no(node, 'ta.full needs a length and a value', 'ta.full(n, x, ta.f64)')
                m = self.length(args['shape'])
                if m is None:
                    return call('_ail_ta_te_' + mk, const('ail_array: a length must be an int, not bool'))
                vk = self.k(args['value'])
                if dt == 'F':
                    if vk not in SCALAR:
                        no(args['value'], 'cannot tell whether the fill value is a number', 'annotate it (x: float)')
                    val = self.visit(args['value']) if vk == 'F' else call('float' if vk == 'I' else '_ail_ta_b2f', self.visit(args['value']))
                else:
                    if vk == 'F':
                        return call('_ail_tai_full_bad', m, const('float'))
                    if vk not in ('I', 'B'):
                        no(args['value'], 'cannot tell whether the fill value is an int', 'annotate it (x: int)')
                    val = self.visit(args['value']) if vk == 'I' else call('_ail_ta_b2i', self.visit(args['value']))
                return call(P[dt] + 'full', m, val)
            if found == 'arange':
                if 'n' not in args:
                    no(node, 'ta.arange without a length', 'ta.arange(n, ta.int32)')
                if dt == 'F':
                    return call('_ail_ta_te_af', const('ail_array: arange() makes int arrays; write arange(n, ta.int32).astype(ta.f64)'))
                m = self.length(args['n'])
                if m is None:
                    return call('_ail_ta_te_ai', const('ail_array: a length must be an int, not bool'))
                return call('_ail_tai_arange', m)
            if 'data' not in args:
                no(node, 'ta.frombytes without data', 'ta.frombytes(b, ta.f64)')
            dk = self.k(args['data'])
            if dk not in ('BY', 'BA', None):
                no(args['data'], 'ta.frombytes of something that is not bytes', 'bytes(...)')
            data = self.visit(args['data'])
            if dk == 'BA':
                data = call('bytes', data)
            return call(P[dt] + 'frombytes', data)
        a = args['a']
        kd = self.array_arg(a, 'ta.%s' % found)
        dt = kd[1]
        if found in ('sqrt', 'exp', 'log', 'tanh'):
            if dt == 'I':
                self.need_pure(a, 'ta.%s of an int32 array' % found)
                return call('_ail_ta_te_af', const('ail_array.%s() is defined for float arrays, not int32' % found))
            return call('_ail_taf_fn', self.visit(a), const(('sqrt', 'exp', 'log', 'tanh').index(found)))
        if found in ('minimum', 'maximum', 'clip'):
            return self.pick(node, found, args, kd)
        if found.startswith('wrapping') or found.startswith('saturating'):
            return self.explicit(node, found, args, kd)
        # reductions
        for opt in ('acc', 'order'):
            if opt in args:
                if opt == 'order' and found in ('min', 'max'):
                    no(args[opt], "order='any' on ta.%s (it has no inexact form)" % found, 'drop order=')
                if opt == 'order':
                    v = args[opt]
                    if not (isinstance(v, ast.Constant) and (v.value == 'any' or v.value is None)):
                        no(v, "order= other than 'any'", "order='any' or nothing")
                else:
                    accd = self.t.dtype_kind(args['acc'])
                    if dt == 'I' or accd == 'I':
                        self.need_pure(a, 'acc= on an int32 array')
                        return call('_ail_ta_ve_f', const('ail_array.%s(): acc= is for float arrays; int32 sums are exact' % found))
        if found == 'sum':
            return call(P[dt] + 'sum', self.visit(a))
        if found == 'dot':
            if 'b' not in args:
                no(node, 'ta.dot needs two arrays', 'ta.dot(a, b)')
            bk = self.k(args['b'])
            if bk not in ARR:
                no(args['b'], 'ta.dot of something that is not an array of known dtype', 'annotate it')
            if bk != kd:
                self.need_pure(a, 'a dtype mismatch')
                self.need_pure(args['b'], 'a dtype mismatch')
                return call('_ail_ta_te_f' if dt == 'F' else '_ail_ta_te_i', const(
                    'ail_array: %s dot %s: dtypes differ; write a.astype(ta.%s) or b.astype(ta.%s)' %
                    ('f64' if dt == 'F' else 'int32', 'f64' if bk == 'AF' else 'int32', 'f64' if bk == 'AF' else 'int32',
                     'f64' if dt == 'F' else 'int32')))
            return call(P[dt] + 'dot', self.visit(a), self.visit(args['b']))
        return call(P[dt] + found, self.visit(a))

    def pick(self, node, found, args, kd):
        dt = kd[1]
        smaller = found != 'maximum'
        if found == 'clip':
            if 'lo' not in args or 'hi' not in args:
                no(node, 'ta.clip needs a, lo and hi', 'ta.clip(a, lo, hi)')
            inner = self.pick1(args['a'], args['lo'], False, kd, node, 'maximum')
            return self.pick_on(inner, args['hi'], True, kd, node, 'minimum')
        if 'b' not in args:
            no(node, 'ta.%s needs two operands' % found, 'ta.%s(a, b)' % found)
        return self.pick1(args['a'], args['b'], smaller, kd, node, found)

    def pick1(self, a, b, smaller, kd, node, name):
        return self.pick_on(self.visit(a), b, smaller, kd, node, name)

    def pick_on(self, left, b, smaller, kd, node, name):
        dt = kd[1]
        bk = self.k(b)
        if bk in ARR:
            if bk != kd:
                return call('_ail_ta_te_a' + dt.lower(), const(
                    'ail_array: %s %s %s: dtypes differ; write a.astype(ta.%s) or b.astype(ta.%s)' %
                    ('f64' if dt == 'F' else 'int32', name, 'f64' if bk == 'AF' else 'int32',
                     'f64' if bk == 'AF' else 'int32', 'f64' if dt == 'F' else 'int32')))
            return call(P[dt] + 'pick_aa', left, self.visit(b), const(smaller))
        if dt == 'I' and bk == 'F':
            return call('_ail_ta_te_ai', const('ail_array: int32 %s float: write a.astype(ta.f64) (no implicit int-to-float)' % name))
        x = self.scalar(b, bk, dt, 'operand')
        return call(P[dt] + 'pick_as', left, x, const(smaller))

    def explicit(self, node, found, args, kd):
        dt = kd[1]
        if dt == 'F':
            return call('_ail_ta_te_af', const('ail_array.%s() is defined for int arrays, not f64' % found))
        if 'b' not in args:
            no(node, 'ta.%s needs two operands' % found, 'ta.%s(a, b)' % found)
        op = {'add': 0, 'sub': 1, 'mul': 2}[found.split('_')[1]]
        wrap = found.startswith('wrapping')
        b = args['b']
        bk = self.k(b)
        left = self.visit(args['a'])
        if bk in ARR:
            if bk != kd:
                return call('_ail_ta_te_ai', const(
                    'ail_array: int32 %s f64: dtypes differ; write a.astype(ta.f64) or b.astype(ta.int32)' % found))
            return call('_ail_tai_explicit', left, self.visit(b), const(op), const(wrap))
        if bk == 'F':
            return call('_ail_ta_te_ai', const('ail_array: int32 %s float: write a.astype(ta.f64) (no implicit int-to-float)' % found))
        x = self.scalar(b, bk, 'I', 'operand')
        return call('_ail_tai_explicit_s', left, x, const(op), const(wrap))


# ---------------------------------------------------------------------------------------------------------------------
def rewrite_text(source, notes=None):
    """The program text with `ail_array` lowered; the source as written (and `notes` filled) when a use is not built."""
    if MODULE not in source:
        return source
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    if MODULE not in stdlib5.imported_modules(tree):
        return source
    try:
        binder = stdlib5.take_imports(tree, MODULE, API, unknown='the names of ail_array are listed in its docstring')
        if not binder:
            return source
        typer = Typer(tree, binder)
        typer.analyze()
        lower = Lower(typer)
        tree.body = [s for st in tree.body for s in _flat(lower.visit(st))]
        used = set()
        for each in ast.walk(tree):
            if isinstance(each, ast.Name) and (each.id.startswith('_ail_ta') or each.id.startswith('_AilTA')):
                used.add(each.id)
        stdlib5.leftover(tree, binder, 'the dtypes are literals ta.f64 / ta.int32, and the functions are called directly')
        for each in ast.walk(tree):
            if isinstance(each, ast.Name) and each.id in binder.aliases:
                refuse(each, 'ail_array used as a value is not built')
        body = stdlib5.shake(prelude_source(), used)
        math_imported = any(isinstance(s, ast.Import) and any(a.name == 'math' and not a.asname for a in s.names)
                            for s in tree.body)
        extra = [] if math_imported else [ast.Import(names=[ast.alias(name='math', asname=None)])]
        index = 0
        while index < len(tree.body) and (isinstance(tree.body[index], (ast.Import, ast.ImportFrom)) or (
                isinstance(tree.body[index], ast.Expr) and isinstance(tree.body[index].value, ast.Constant))):
            index += 1
        tree.body[index:index] = extra + ast.parse(body).body
        ast.fix_missing_locations(tree)
        out = ast.unparse(tree)
    except Refused as exc:
        if notes is not None:
            notes.append((exc.line, exc.text))
        return source
    except (AttributeError, KeyError, IndexError, TypeError, ValueError, RecursionError) as exc:
        if notes is not None:
            notes.append((1, 'the ail_array lowering could not handle this program (%s: %s); simplify the use or report it'
                          % (type(exc).__name__, exc)))
        return source
    return out.rstrip('\n') + '\n'


def _flat(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]
