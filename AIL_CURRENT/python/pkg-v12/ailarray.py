"""`import ail_array` (docs/design/TYPED_ARRAY.md, stages T2 and T3b): f64, int32, int64 and bool_ arrays lowered onto native loops.

Called from ail_syntax.python_surface (as stdlib5 is) on the program text. A program that does not import `ail_array`
is returned as it was written (the same string), so its C does not change. Otherwise:

* every array has a static dtype: the `ta.f64` / `ta.int32` literal of its construction, a `ta.Array[ta.f64]` annotation,
  or what flows from those through assignments, calls (parameters take what every call site passes) and returns. An f64
  array becomes a `_AilTAF` (a list[float]), an int32 array a `_AilTAI` (a list[int]), an int64 array a `_AilTAL` (a
  list[int]) and a bool_ array a `_AilTAO` (a list[bool]); prelude_ailarray.py holds the
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
API = {'DType', 'Array', 'f64', 'f32', 'f16', 'int8', 'int32', 'int64', 'bool_', 'array', 'zeros', 'full', 'arange',
       'frombytes', 'sqrt', 'exp', 'log', 'tanh', 'minimum', 'maximum', 'clip', 'wrapping_add', 'wrapping_sub',
       'wrapping_mul', 'saturating_add', 'saturating_sub', 'sum', 'dot', 'min', 'max', 'argmin', 'argmax',
       'wrapping_neg', 'wrapping_abs', 'wrapping_floordiv', 'wrapping_sum', 'wrapping_dot', 'eq', 'ne', 'lt', 'le', 'gt',
       'ge', 'logical_and', 'logical_or', 'logical_xor', 'logical_not', 'where', 'any', 'all', 'take', 'put',
       'gather_strided', 'scatter_strided', 'segment_sum', 'segment_min', 'segment_max', 'segment_argmin',
       'segment_argmax', 'wrapping_segment_sum', 'mm', 'promote_types', 'promote_scalar'}
DTYPES = {'f64': 'F', 'int32': 'I', 'int64': 'L', 'bool_': 'O'}
LATER = {'f32', 'f16', 'int8'}          # stage T3
OUTSIDE = {'bf16', 'uint8', 'int16', 'uint16', 'uint32', 'uint64', 'float32', 'float16'}
ARR = ('AF', 'AI', 'AL', 'AO')
SCALAR = ('F', 'I', 'B')
CLASS = {'F': '_AilTAF', 'I': '_AilTAI', 'L': '_AilTAL', 'O': '_AilTAO'}
P = {'F': '_ail_taf_', 'I': '_ail_tai_', 'L': '_ail_tal_', 'O': '_ail_tao_'}
AKIND = {'F': 'AF', 'I': 'AI', 'L': 'AL', 'O': 'AO'}
DN = {'F': 'f64', 'I': 'int32', 'L': 'int64', 'O': 'bool_'}         # dtype letter -> name in messages
ELEM = {'AF': 'F', 'AI': 'I', 'AL': 'I', 'AO': 'B'}                  # array kind -> kind of an element
LISTK = {'AF': 'LF', 'AI': 'LI', 'AL': 'LI', 'AO': 'LB'}             # array kind -> kind of its tolist()
CMPS = {'eq': 0, 'ne': 1, 'lt': 2, 'le': 3, 'gt': 4, 'ge': 5}
T3B_CALLS = {'wrapping_neg', 'wrapping_abs', 'wrapping_floordiv', 'wrapping_sum', 'wrapping_dot', 'eq', 'ne', 'lt', 'le',
             'gt', 'ge', 'logical_and', 'logical_or', 'logical_xor', 'logical_not', 'where', 'any', 'all', 'take', 'put',
             'gather_strided', 'scatter_strided', 'segment_sum', 'segment_min', 'segment_max', 'segment_argmin',
             'segment_argmax', 'wrapping_segment_sum', 'mm', 'promote_types', 'promote_scalar'}
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
    'wrapping_neg': ('a',), 'wrapping_abs': ('a',), 'wrapping_floordiv': ('a', 'b'), 'wrapping_sum': ('a',),
    'wrapping_dot': ('a', 'b'),
    'eq': ('a', 'b'), 'ne': ('a', 'b'), 'lt': ('a', 'b'), 'le': ('a', 'b'), 'gt': ('a', 'b'), 'ge': ('a', 'b'),
    'logical_and': ('a', 'b'), 'logical_or': ('a', 'b'), 'logical_xor': ('a', 'b'), 'logical_not': ('a',),
    'where': ('mask', 'a', 'b'), 'any': ('a',), 'all': ('a',), 'take': ('a', 'idx'),
    'put': ('a', 'idx', 'src', 'accumulate', 'overflow'),
    'gather_strided': ('a', 'offset', 'shape', 'strides'), 'scatter_strided': ('dst', 'offset', 'shape', 'strides', 'src'),
    'segment_sum': ('a', 'offsets'), 'segment_min': ('a', 'offsets'), 'segment_max': ('a', 'offsets'),
    'segment_argmin': ('a', 'offsets'), 'segment_argmax': ('a', 'offsets'), 'wrapping_segment_sum': ('a', 'offsets'),
    'mm': ('a', 'b', 'm', 'k', 'n'), 'promote_types': ('a', 'b'), 'promote_scalar': ('dtype', 'scalar', 'default_float'),
}
OPS = {ast.Add: (0, '+'), ast.Sub: (1, '-'), ast.Mult: (2, '*'), ast.Div: (3, '/'), ast.FloorDiv: (3, '//'),
       ast.Mod: (4, '%')}
BUILTIN_ITER = {'list', 'sorted', 'sum', 'min', 'max', 'enumerate', 'zip', 'reversed'}
BUILTIN_SHOW = {'print', 'str', 'repr'}
UNSUPPORTED_METHODS = {'append': 'ail_array arrays have a fixed length; write instead: ta.zeros(n, ...) and index, or a list',
                       'extend': None, 'insert': None, 'pop': None, 'remove': None, 'resize': None}
NOBOOL = 'ail_array: %s on bool_ arrays is not defined; write a.astype(ta.int64) (or ta.logical_and/or/xor/not)'
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
        """'F', 'I', 'L' or 'O' for a `ta.f64` / `ta.int32` / `ta.int64` / `ta.bool_` expression; a refusal for the other dtypes."""
        found = self.b.attr(node)
        if found in DTYPES:
            return DTYPES[found]
        if found in LATER:
            no(node, '%s arrays are stage T3 of the typed arrays and not built here' % found,
               'ta.f64, ta.int32, ta.int64 or ta.bool_ (the program runs unchanged under CPython)')
        if found in OUTSIDE or found == 'DType':
            no(node, 'ail_array has f64, f32, f16, int8, int32, int64, bool_', 'ta.int32 (or a list)')
        if found is not None:
            no(node, 'ta.%s is not a dtype' % found, 'ta.f64, ta.int32, ta.int64 or ta.bool_')
        no(node, 'the dtype is not known at compile time', 'a literal ta.f64, ta.int32, ta.int64 or ta.bool_ here')

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
            return {'float': 'LF', 'int': 'LI', 'bool': 'LB'}.get(node.slice.id)
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
                return v if isinstance(node.slice, ast.Slice) else ELEM[v] \
                    if not isinstance(node.slice, ast.Tuple) else None
            if v in ('LF', 'LI', 'LB'):
                return v if isinstance(node.slice, ast.Slice) else {'LF': 'F', 'LI': 'I', 'LB': 'B'}[v]
            return None
        if isinstance(node, ast.List):
            ks = {k(e, env) for e in node.elts}
            if ks == {'F'}:
                return 'LF'
            if ks == {'I'}:
                return 'LI'
            if ks == {'B'}:
                return 'LB'
            return None
        if isinstance(node, ast.ListComp) and len(node.generators) == 1:
            sub = self.comp_env(node.generators, env)
            e = k(node.elt, sub)
            return {'F': 'LF', 'I': 'LI', 'B': 'LB'}.get(e)
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
        if v in ('AI', 'AL', 'LI', 'R'):
            return 'I'
        if v in ('AO', 'LB'):
            return 'B'
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
                got = {'AF': 'F', 'AI': 'I', 'AL': 'I', 'LF': 'F', 'LI': 'I'}.get(first)
                if got is None and first in ('AO', 'LB'):
                    got = 'I' if f.id == 'sum' else 'B'
                return got
            if f.id == 'sorted' and len(args) == 1:
                return {'AF': 'LF', 'AI': 'LI', 'AL': 'LI', 'AO': 'LB', 'LF': 'LF', 'LI': 'LI', 'LB': 'LB'}.get(first)
            if f.id == 'list' and len(args) == 1:
                return {'AF': 'LF', 'AI': 'LI', 'AL': 'LI', 'AO': 'LB', 'LF': 'LF', 'LI': 'LI', 'LB': 'LB'}.get(first)
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
                    return LISTK[v]
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
        if found in T3B_CALLS:
            return self.t3b_kind(found, args, a, env)
        if found in ('sqrt', 'exp', 'log', 'tanh'):
            return 'AF'
        if found in ('minimum', 'maximum', 'clip'):
            return a if a in ARR else None
        if found.startswith('wrapping') or found.startswith('saturating'):
            return a if a in ARR else 'AI'
        if found in ('sum', 'dot', 'min', 'max'):
            if a == 'AO':
                return 'I' if found == 'sum' else 'B' if found != 'dot' else None
            return {'AF': 'F', 'AI': 'I', 'AL': 'I'}.get(a)
        if found in ('argmin', 'argmax'):
            return 'I'
        return None

    def t3b_kind(self, found, args, a, env):
        """The kind of a call of a function that stage T3b added."""
        if found in CMPS or found in ('logical_and', 'logical_or', 'logical_xor', 'logical_not'):
            return 'AO'
        if found == 'where':
            b = self.kind(args['b'], env) if 'b' in args else None
            return a if a in ARR else b if b in ARR else None
        if found in ('any', 'all'):
            return 'B'
        if found in ('take', 'gather_strided', 'segment_min', 'segment_max', 'wrapping_neg', 'wrapping_abs',
                     'wrapping_floordiv'):
            return a if a in ARR else None
        if found in ('segment_sum', 'wrapping_segment_sum'):
            return 'AF' if a == 'AF' and found == 'segment_sum' else 'AL' if a in ARR else None
        if found in ('segment_argmin', 'segment_argmax'):
            return 'AL'
        if found in ('wrapping_sum', 'wrapping_dot'):
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
                        arg.arg, name, ('both f64 and int32 arrays' if arrays == {'AF', 'AI'} else
                                        'arrays of different dtypes') if len(arrays) > 1 else
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
            if dt == 'O':
                return new if kd == 'B' else ast.Compare(left=new, ops=[ast.NotEq()], comparators=[const(0)])
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
                return ast.Expr(value=call('_ail_ta_te_a' + dt.lower(),
                                           const('ail_array: can only assign an ail_array.Array to a slice, not %s' %
                                                 {'F': 'float', 'I': 'int', 'B': 'bool', 'S': 'str', 'LF': 'list',
                                                  'LI': 'list', 'LB': 'list', 'BY': 'bytes', 'BA': 'bytearray'}.get(vkind, 'object'))))
            if vkind != kd:
                return ast.Expr(value=call('_ail_ta_te_a' + dt.lower(),
                                           const('ail_array: slice assignment: dtypes differ (%s and %s)' %
                                                 (DN[dt], DN[vkind[1]]))))
            lo, hi, st, flags = self.slice_args(idx)
            return ast.Expr(value=call(P[dt] + 'setslice', arr, lo, hi, st, flags, self.visit(value)))
        ik = self.k(idx)
        if ik in ARR or ik in ('LF', 'LI'):
            no(node, 'fancy indexing or a mask', 'ta.take(a, idx) / ta.put(a, idx, src), ta.where(mask, a, b), a loop, or ta.minimum/ta.maximum/ta.clip')
        if ik in ('F', 'S'):
            no(node, 'an index that is not an int', 'an int index')
        index = self.visit(idx)
        if dt == 'F':
            if vkind not in SCALAR:
                no(node, 'cannot tell whether the stored value is a number', 'annotate it (x: float)')
            val = self.visit(value) if vkind == 'F' else call('float' if vkind == 'I' else '_ail_ta_b2f', self.visit(value))
            return ast.Expr(value=call('_ail_taf_set', arr, index, val))
        if dt == 'O':
            if vkind == 'F':
                return ast.Expr(value=call('_ail_tao_set_bad', arr, index, const('float')))
            if vkind not in ('I', 'B'):
                no(node, 'cannot tell whether the stored value is an int or a bool', 'annotate it (x: bool)')
            val = self.visit(value) if vkind == 'B' else ast.Compare(left=self.visit(value), ops=[ast.NotEq()],
                                                                     comparators=[const(0)])
            return ast.Expr(value=call('_ail_tao_set', arr, index, val))
        if vkind in ('I', 'B'):
            val = self.visit(value) if vkind == 'I' else call('_ail_ta_b2i', self.visit(value))
            return ast.Expr(value=call(P[dt] + 'set', arr, index, val))
        if vkind == 'F':
            return ast.Expr(value=call(P[dt] + 'set_bad', arr, index, const('float')))
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
                if kd == 'AO':
                    self.need_pure(node.operand, 'neg of a bool_ array')
                    return call('_ail_ta_te_ao', const(NOBOOL % 'neg'))
                return call(P[kd[1]] + 'unary', self.visit(node.operand), const(False))
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
            if dt == 'O':
                self.need_pure(left, 'an operator on a bool_ array')
                self.need_pure(right, 'an operator on a bool_ array')
                return call('_ail_ta_te_ao', const(NOBOOL % sym))
            if dt == 'F' and sym in ('//', '%'):
                no(where, '%s on f64 arrays' % sym, 'a loop over a.tolist()')
            if dt != 'F' and sym == '/':
                no(where, '/ on %s arrays' % DN[dt], 'a.astype(ta.f64) / b.astype(ta.f64)')
            if rk in ARR:
                if rk != lk:
                    self.need_pure(left, 'a dtype mismatch')
                    self.need_pure(right, 'a dtype mismatch')
                    return call('_ail_ta_te_a' + dt.lower(), const(
                        'ail_array: %s %s %s: dtypes differ; write a.astype(ta.%s) or b.astype(ta.%s)' %
                        (DN[dt], sym, DN[rk[1]], DN[rk[1]], DN[dt])))
                a, b = self.visit(left), self.visit(right)
                return call(P[dt] + ('ibin' if inplace else 'bin'), a, b, const(code))
            if dt in 'IL' and rk == 'F':
                self.need_pure(left, 'an int array and a float')
                self.need_pure(right, 'an int array and a float')
                return call('_ail_ta_te_a' + dt.lower(), const(
                    'ail_array: %s %s float: write a.astype(ta.f64) (no implicit int-to-float)' % (DN[dt], sym)))
            a = self.visit(left)
            x = self.scalar(right, rk, dt, 'operand')
            if inplace:
                return call(P[dt] + 'ibin_s', a, x, const(code))
            return call(P[dt] + 'bin_s', a, x, const(code), const(False))
        # scalar op array
        dt = rk[1]
        if inplace:
            no(where, 'an in-place operator with an array on the right', 'a = a op b')
        if dt == 'O':
            self.need_pure(left, 'an operator on a bool_ array')
            self.need_pure(right, 'an operator on a bool_ array')
            return call('_ail_ta_te_ao', const(NOBOOL % sym))
        if dt == 'F' and sym in ('//', '%'):
            no(where, '%s on f64 arrays' % sym, 'a loop over a.tolist()')
        if dt != 'F' and sym == '/':
            no(where, '/ on %s arrays' % DN[dt], 'a.astype(ta.f64) / b.astype(ta.f64)')
        if dt in 'IL' and lk == 'F':
            no(where, 'a float and an %s array' % DN[dt], 'a.astype(ta.f64)')
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
            no(node, 'element-wise comparison or ordering of arrays',
               'ta.eq/ta.ne/ta.lt/ta.le/ta.gt/ta.ge(a, b) (a bool_ array), a loop, or ta.minimum/ta.maximum/ta.clip')
        lk, rk = kinds
        if lk not in ARR or rk not in ARR:
            no(node, 'comparing an array with something that is not an array of known dtype',
               'len(a) == len(b) and a loop, or annotate the other operand')
        if lk == rk:
            res = call(P[lk[1]] + 'eq', self.visit(node.left), self.visit(node.comparators[0]))
        elif (lk, rk) in (('AF', 'AI'), ('AI', 'AF')):
            first, second = (node.left, node.comparators[0])
            res = call('_ail_ta_ne_dtype' if lk == 'AF' else '_ail_ta_ne_dtype2', self.visit(first), self.visit(second))
        else:       # arrays of different dtypes are never equal: len(a.d) + len(b.d) < 0 is False, and evaluates both
            both = ast.BinOp(left=call('len', ast.Attribute(value=self.visit(node.left), attr='d', ctx=ast.Load())),
                             op=ast.Add(),
                             right=call('len', ast.Attribute(value=self.visit(node.comparators[0]), attr='d', ctx=ast.Load())))
            res = ast.Compare(left=both, ops=[ast.Lt()], comparators=[const(0)])
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
            no(node, 'fancy indexing or a mask', 'ta.take(a, idx), a loop, or ta.minimum/ta.maximum/ta.clip')
        if ik in ('F', 'S'):
            self.need_pure(node.value, 'an index that is not an int')
            return call({'F': '_ail_ta_te_f', 'O': '_ail_ta_te_b'}.get(dt, '_ail_ta_te_i'), const('array indices must be integers'))
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
                if kd == 'AO':
                    self.need_pure(node.args[0], 'abs of a bool_ array')
                    return call('_ail_ta_te_ao', const(NOBOOL % 'abs'))
                return call(P[kd[1]] + 'unary', self.visit(node.args[0]), const(True))
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
        mk = 'a' + dst.lower()
        if opts['rounding'] not in ('trunc', 'nearest'):
            return call('_ail_ta_ve_' + mk, const("ail_array: rounding must be 'trunc' or 'nearest', not %r" % opts['rounding']))
        if opts['overflow'] not in ('raise', 'saturate', 'wrap'):
            return call('_ail_ta_ve_' + mk, const("ail_array: overflow must be 'raise', 'saturate' or 'wrap', not %r" % opts['overflow']))
        mode = {'raise': 0, 'saturate': 1, 'wrap': 2}[opts['overflow']]
        if dst == 'O':
            return call({'F': '_ail_taf_to_bool', 'I': '_ail_tai_to_bool', 'L': '_ail_tal_to_bool', 'O': '_ail_tao_copy'}[src], recv)
        if dst == 'F':
            return call({'F': '_ail_taf_to_f64', 'I': '_ail_tai_to_f64', 'L': '_ail_tal_to_f64', 'O': '_ail_tao_to_f64'}[src], recv)
        if src == 'F':
            if opts['overflow'] == 'wrap':
                return call('_ail_ta_ve_' + mk, const("ail_array: overflow='wrap' is for int-to-int casts; use 'raise' or 'saturate'"))
            return call('_ail_taf_to_i32' if dst == 'I' else '_ail_taf_to_i64', recv, const(opts['rounding'] == 'nearest'),
                        const(1 if opts['overflow'] == 'saturate' else 0))
        if dst == 'I':
            if src == 'L':
                return call('_ail_tal_to_i32', recv, const(mode))
            if src == 'O':
                return call('_ail_tao_to_i32', recv)
            return call('_ail_tai_copy', recv)
        if src == 'I':
            return call('_ail_tai_to_i64', recv)
        if src == 'O':
            return call('_ail_tao_to_i64', recv)
        return call('_ail_tal_copy', recv)

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
        elif dt == 'O':
            if kd == 'B':
                return self.visit(node)
            if kd == 'I':
                return ast.Compare(left=self.visit(node), ops=[ast.NotEq()], comparators=[const(0)])
        else:
            if kd == 'I':
                return self.visit(node)
            if kd == 'B':
                return call('_ail_ta_b2i', self.visit(node))
        no(node, 'cannot tell that this list element is %s' % ('a number' if dt == 'F' else 'a bool' if dt == 'O' else 'an int'),
           'annotate it, or build the array from a list of %s' % ('floats' if dt == 'F' else 'bools' if dt == 'O' else 'ints'))

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
        want = {'F': 'LF', 'I': 'LI', 'L': 'LI', 'O': 'LB'}[dt]
        if kd == want:
            return self.visit(node)
        if kd in ARR:
            if kd[1] == dt or (dt == 'L' and kd == 'AI'):
                return ast.Attribute(value=self.visit(node), attr='d', ctx=ast.Load())
            if dt == 'F':
                return ast.ListComp(elt=call('float', n('_ail_v')), generators=[ast.comprehension(
                    target=ast.Name(id='_ail_v', ctx=ast.Store()), iter=ast.Attribute(value=self.visit(node), attr='d',
                                                                                     ctx=ast.Load()), ifs=[], is_async=0)])
        if kd in ('LI', 'R') and dt == 'F':
            return ast.ListComp(elt=call('float', n('_ail_v')), generators=[ast.comprehension(
                target=ast.Name(id='_ail_v', ctx=ast.Store()), iter=self.visit(node), ifs=[], is_async=0)])
        if kd in ('LI', 'R') and dt == 'O':
            return ast.ListComp(elt=ast.Compare(left=n('_ail_v'), ops=[ast.NotEq()], comparators=[const(0)]),
                                generators=[ast.comprehension(target=ast.Name(id='_ail_v', ctx=ast.Store()),
                                                              iter=self.visit(node), ifs=[], is_async=0)])
        if kd == 'R' and dt in ('I', 'L'):
            return call('list', self.visit(node))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'range':
            if dt == 'F':
                return ast.ListComp(elt=call('float', n('_ail_v')), generators=[ast.comprehension(
                    target=ast.Name(id='_ail_v', ctx=ast.Store()), iter=self.visit(node), ifs=[], is_async=0)])
            if dt == 'O':
                return ast.ListComp(elt=ast.Compare(left=n('_ail_v'), ops=[ast.NotEq()], comparators=[const(0)]),
                                    generators=[ast.comprehension(target=ast.Name(id='_ail_v', ctx=ast.Store()),
                                                                  iter=self.visit(node), ifs=[], is_async=0)])
            return call('list', self.visit(node))
        no(node, 'cannot tell the element type of these values for an array of dtype %s' % DN[dt],
           'a list literal, a comprehension, or a list annotated as list[%s]' % ('float' if dt == 'F' else 'bool' if dt == 'O' else 'int'))

    def module_call(self, node, found):
        if found not in SIG:
            if found in DTYPES or found in LATER or found in OUTSIDE or found == 'DType':
                self.t.dtype_kind(node.func)
            no(node, 'ta.%s is not a function' % found, 'a call of one of its functions')
        args = self.t.bind(node, found)
        if found in T3B_CALLS:
            return self.t3b_call(node, found, args)
        if found in ('array', 'zeros', 'full', 'arange', 'frombytes'):
            dt = self.dtype_arg(node, args, found)
            mk = 'a' + dt.lower()
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
                        return call(P[dt] + 'full_bad', m, const('float'))
                    if vk not in ('I', 'B'):
                        no(args['value'], 'cannot tell whether the fill value is an int', 'annotate it (x: int)')
                    if dt == 'O':
                        val = self.visit(args['value']) if vk == 'B' else ast.Compare(
                            left=self.visit(args['value']), ops=[ast.NotEq()], comparators=[const(0)])
                    else:
                        val = self.visit(args['value']) if vk == 'I' else call('_ail_ta_b2i', self.visit(args['value']))
                return call(P[dt] + 'full', m, val)
            if found == 'arange':
                if 'n' not in args:
                    no(node, 'ta.arange without a length', 'ta.arange(n, ta.int32)')
                if dt == 'F':
                    return call('_ail_ta_te_af', const('ail_array: arange() makes int arrays; write arange(n, ta.int32).astype(ta.f64)'))
                if dt == 'O':
                    return call('_ail_ta_te_ao', const('ail_array: arange() makes int arrays, not bool_; '
                                                       'write ta.arange(n, ta.int64).astype(ta.bool_)'))
                m = self.length(args['n'])
                if m is None:
                    return call('_ail_ta_te_a' + dt.lower(), const('ail_array: a length must be an int, not bool'))
                return call(P[dt] + 'arange', m)
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
            if dt != 'F':
                self.need_pure(a, 'ta.%s of an %s array' % (found, DN[dt]))
                return call('_ail_ta_te_af', const('ail_array.%s() is defined for float arrays, not %s' % (found, DN[dt])))
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
                    if dt != 'F' or accd != 'F':
                        self.need_pure(a, 'acc= on an int array')
                        return call('_ail_ta_ve_f', const('ail_array.%s(): acc= is for float arrays; %s sums are exact' % (
                            found, DN[dt] if dt != 'F' else 'int32')))
        if found == 'sum':
            return call(P[dt] + 'sum', self.visit(a))
        if found == 'dot':
            if 'b' not in args:
                no(node, 'ta.dot needs two arrays', 'ta.dot(a, b)')
            bk = self.k(args['b'])
            if bk not in ARR:
                no(args['b'], 'ta.dot of something that is not an array of known dtype', 'annotate it')
            if dt == 'O':
                self.need_pure(a, 'ta.dot of bool_ arrays')
                self.need_pure(args['b'], 'ta.dot of bool_ arrays')
                return call('_ail_ta_te_i', const('ail_array.dot() is defined for numeric arrays, not bool_'))
            if dt == 'L':
                no(node, 'ta.dot of int64 arrays (an exact int64 dot needs 128-bit sums)',
                   'ta.wrapping_dot(a, b) (modulo 2^64), or a loop')
            if bk != kd:
                self.need_pure(a, 'a dtype mismatch')
                self.need_pure(args['b'], 'a dtype mismatch')
                return call('_ail_ta_te_f' if dt == 'F' else '_ail_ta_te_i', const(
                    'ail_array: %s dot %s: dtypes differ; write a.astype(ta.%s) or b.astype(ta.%s)' %
                    (DN[dt], DN[bk[1]], DN[bk[1]], DN[dt])))
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
                    (DN[dt], name, DN[bk[1]], DN[bk[1]], DN[dt])))
            return call(P[dt] + 'pick_aa', left, self.visit(b), const(smaller))
        if dt != 'F' and bk == 'F':
            return call('_ail_ta_te_a' + dt.lower(), const(
                'ail_array: %s %s float: write a.astype(ta.f64) (no implicit int-to-float)' % (DN[dt], name)))
        x = self.scalar(b, bk, dt, 'operand')
        return call(P[dt] + 'pick_as', left, x, const(smaller))

    def explicit(self, node, found, args, kd):
        dt = kd[1]
        if dt in ('F', 'O'):
            self.need_pure(args['a'], 'ta.%s of a %s array' % (found, DN[dt]))
            return call('_ail_ta_te_a' + dt.lower(), const('ail_array.%s() is defined for int arrays, not %s' % (found, DN[dt])))
        if 'b' not in args:
            no(node, 'ta.%s needs two operands' % found, 'ta.%s(a, b)' % found)
        op = {'add': 0, 'sub': 1, 'mul': 2}[found.split('_')[1]]
        wrap = found.startswith('wrapping')
        b = args['b']
        bk = self.k(b)
        left = self.visit(args['a'])
        if bk in ARR:
            if bk != kd:
                return call('_ail_ta_te_a' + dt.lower(), const(
                    'ail_array: %s %s %s: dtypes differ; write a.astype(ta.%s) or b.astype(ta.%s)' %
                    (DN[dt], found, DN[bk[1]], DN[bk[1]], DN[dt])))
            return call(P[dt] + 'explicit', left, self.visit(b), const(op), const(wrap))
        if bk == 'F':
            return call('_ail_ta_te_a' + dt.lower(), const(
                'ail_array: %s %s float: write a.astype(ta.f64) (no implicit int-to-float)' % (DN[dt], found)))
        x = self.scalar(b, bk, dt, 'operand')
        return call(P[dt] + 'explicit_s', left, x, const(op), const(wrap))

    # -- stage T3b: comparisons, bool_ logic, where, gather and scatter, segments --------------------------------------------------
    def te(self, dt):
        return '_ail_ta_te_a' + dt.lower()

    def stored(self, node, kd, dt):
        """A scalar `node` stored into an array of dtype `dt` (the store rule), or None for a float into an int array."""
        x = self.scalar(node, kd, dt, 'operand')
        if x is None:
            return None
        if dt == 'I':
            return call('_ail_tai_store', x)
        if dt == 'L':
            return call('_ail_tal_store', x)
        if dt == 'F':
            return call('_ail_ta_canon', x)
        return x

    def idx_list(self, arg, what):
        """An int64 array for an int32/int64 index array (int32 is converted), or None for another dtype."""
        kd = self.k(arg)
        if kd == 'AL':
            return self.visit(arg)
        if kd == 'AI':
            return call('_ail_tai_to_i64', self.visit(arg))
        if kd in ARR:
            return None
        no(arg, '%s with indices that are not an array of known dtype' % what,
           'ta.array(idx, ta.int64) bound to a name with its dtype visible')

    def int_list(self, arg, what):
        if isinstance(arg, (ast.List, ast.Tuple)):
            for e in arg.elts:
                if self.k(e) != 'I':
                    no(e, '%s with an element that is not known to be an int' % what, 'ints, or a list[int] name')
            return ast.List(elts=[self.visit(e) for e in arg.elts], ctx=ast.Load())
        if self.k(arg) == 'LI':
            return self.visit(arg)
        no(arg, '%s that is not a list or tuple of ints' % what, 'a tuple literal such as (2, 3) or a list[int]')

    def int_arg(self, arg, what):
        if self.k(arg) != 'I':
            no(arg, '%s that is not known to be an int' % what, 'an int expression')
        return self.visit(arg)

    def literal(self, arg, kind, default, what):
        if arg is None:
            return default
        if isinstance(arg, ast.Constant) and type(arg.value) is kind:
            return arg.value
        no(arg, '%s that is not a literal' % what, 'a literal such as %r' % (default,))

    def t3b_call(self, node, found, args):
        if found == 'mm':
            no(node, 'ta.mm (reference only: f32 arrays are stage T3 and the 2-D kernel is stage T6)',
               'ta.dot on a row and a column, or the 2-D ta.matmul of stage T6')
        if found in ('promote_types', 'promote_scalar'):
            no(node, 'ta.%s (dtypes are not values on the typed path)' % found, 'choose the dtype where you write the code')
        if found in CMPS:
            return self.t3b_compare(node, found, args)
        if found in ('logical_and', 'logical_or', 'logical_xor', 'logical_not'):
            return self.t3b_logic(node, found, args)
        if found == 'where':
            return self.t3b_where(node, args)
        if found in ('take', 'put', 'gather_strided', 'scatter_strided'):
            return self.t3b_move(node, found, args)
        if found.startswith('segment') or found == 'wrapping_segment_sum':
            return self.t3b_segment(node, found, args)
        a = args.get('a')
        if a is None:
            no(node, 'ta.%s needs an array' % found, 'ta.%s(a)' % found)
        kd = self.array_arg(a, 'ta.%s' % found)
        dt = kd[1]
        if found in ('any', 'all'):
            return call(P[dt] + found, self.visit(a))
        if found in ('wrapping_neg', 'wrapping_abs'):
            if dt in ('F', 'O'):
                self.need_pure(a, 'ta.%s of a %s array' % (found, DN[dt]))
                return call(self.te(dt), const('ail_array.%s() is defined for int arrays, not %s' % (found, DN[dt])))
            return call(P[dt] + 'wneg', self.visit(a), const(found == 'wrapping_abs'))
        if found == 'wrapping_sum':
            if dt != 'L':
                self.need_pure(a, 'ta.wrapping_sum of a %s array' % DN[dt])
                return call('_ail_ta_te_i', const('ail_array.wrapping_sum() is for int64 arrays, not %s (int8/int32 sums are '
                                                  'exact and cannot leave int64)' % DN[dt]))
            return call('_ail_tal_wsum', self.visit(a))
        if 'b' not in args:
            no(node, 'ta.%s needs two operands' % found, 'ta.%s(a, b)' % found)
        b = args['b']
        bk = self.k(b)
        if found == 'wrapping_dot':
            if dt != 'L':
                self.need_pure(a, 'ta.wrapping_dot of a %s array' % DN[dt])
                return call('_ail_ta_te_i', const('ail_array.wrapping_dot() is for int64 arrays, not %s (int8/int32 sums are '
                                                  'exact and cannot leave int64)' % DN[dt]))
            if bk not in ARR:
                no(b, 'ta.wrapping_dot of something that is not an array of known dtype', 'annotate it')
            if bk != kd:
                self.need_pure(a, 'a dtype mismatch')
                self.need_pure(b, 'a dtype mismatch')
                return call('_ail_ta_te_i', const(
                    'ail_array: int64 wrapping_dot %s: dtypes differ; write a.astype(ta.%s) or b.astype(ta.int64)' %
                    (DN[bk[1]], DN[bk[1]])))
            return call('_ail_tal_wdot', self.visit(a), self.visit(b))
        # wrapping_floordiv
        if dt in ('F', 'O'):
            self.need_pure(a, 'ta.wrapping_floordiv of a %s array' % DN[dt])
            return call(self.te(dt), const('ail_array.wrapping_floordiv() is defined for int arrays, not %s' % DN[dt]))
        left = self.visit(a)
        if bk in ARR:
            if bk != kd:
                return call(self.te(dt), const(
                    'ail_array: %s wrapping_floordiv %s: dtypes differ; write a.astype(ta.%s) or b.astype(ta.%s)' %
                    (DN[dt], DN[bk[1]], DN[bk[1]], DN[dt])))
            return call(P[dt] + 'wfloordiv', left, self.visit(b))
        if bk == 'F':
            return call(self.te(dt), const('ail_array: %s wrapping_floordiv float: write a.astype(ta.f64) '
                                           '(no implicit int-to-float)' % DN[dt]))
        return call(P[dt] + 'wfloordiv_s', left, self.stored(b, bk, dt))

    def t3b_compare(self, node, found, args):
        a, b = args.get('a'), args.get('b')
        if a is None or b is None:
            no(node, 'ta.%s needs two operands' % found, 'ta.%s(a, b)' % found)
        kd = self.array_arg(a, 'ta.%s' % found)
        dt = kd[1]
        bk = self.k(b)
        code = const(CMPS[found])
        if bk in ARR:
            if bk != kd:
                self.need_pure(a, 'a dtype mismatch')
                self.need_pure(b, 'a dtype mismatch')
                return call('_ail_ta_te_ao', const(
                    'ail_array: %s %s %s: dtypes differ; write a.astype(ta.%s) or b.astype(ta.%s)' %
                    (DN[dt], found, DN[bk[1]], DN[bk[1]], DN[dt])))
            return call(P[dt] + 'cmp', self.visit(a), self.visit(b), code)
        if dt != 'F' and bk == 'F':
            self.need_pure(a, 'an int array and a float')
            self.need_pure(b, 'an int array and a float')
            return call('_ail_ta_te_ao', const('ail_array: %s %s float: write a.astype(ta.f64) (no implicit int-to-float)'
                                               % (DN[dt], found)))
        left = self.visit(a)
        x = self.stored(b, bk, dt)
        return call(P[dt] + 'cmp_s', left, x, code)

    def t3b_logic(self, node, found, args):
        a = args.get('a')
        if a is None:
            no(node, 'ta.%s needs an array' % found, 'ta.%s(a)' % found)
        kd = self.array_arg(a, 'ta.%s' % found)
        two = found != 'logical_not'
        if kd != 'AO':
            if two:
                self.need_pure(a, 'ta.%s of a non-bool array' % found)
                return call('_ail_ta_te_ao', const('ail_array.%s() needs bool_ arrays; write ta.ne(a, 0) or a.astype(ta.bool_)'
                                                   % found))
            self.need_pure(a, 'ta.logical_not of a non-bool array')
            return call('_ail_ta_te_ao', const('ail_array.logical_not() needs a bool_ array; write ta.eq(a, 0) or '
                                               'a.astype(ta.bool_)'))
        if not two:
            return call('_ail_tao_not', self.visit(a))
        if 'b' not in args:
            no(node, 'ta.%s needs two operands' % found, 'ta.%s(a, b)' % found)
        b = args['b']
        bk = self.k(b)
        op = {'logical_and': 0, 'logical_or': 1, 'logical_xor': 2}[found]
        if bk in ARR:
            if bk != 'AO':
                self.need_pure(a, 'a dtype mismatch')
                self.need_pure(b, 'a dtype mismatch')
                return call('_ail_ta_te_ao', const(
                    'ail_array: bool_ %s %s: dtypes differ; write a.astype(ta.%s) or b.astype(ta.bool_)' %
                    (found, DN[bk[1]], DN[bk[1]])))
            return call('_ail_tao_logic', self.visit(a), self.visit(b), const(op))
        if bk == 'F':
            self.need_pure(a, 'a bool_ array and a float')
            self.need_pure(b, 'a bool_ array and a float')
            return call('_ail_ta_te_ao', const('ail_array: bool_ %s float: write a.astype(ta.f64) (no implicit int-to-float)'
                                               % found))
        left = self.visit(a)
        return call('_ail_tao_logic_s', left, self.stored(b, bk, 'O'), const(op))

    def t3b_where(self, node, args):
        m, a, b = args.get('mask'), args.get('a'), args.get('b')
        if m is None or a is None or b is None:
            no(node, 'ta.where needs a mask and two operands', 'ta.where(mask, a, b)')
        mk = self.k(m)
        if mk not in ARR:
            no(m, 'ta.where with a mask whose dtype is not known at compile time', 'annotate it (m: ta.Array[ta.bool_])')
        ak, bk = self.k(a), self.k(b)
        if ak not in ARR and bk not in ARR:
            no(node, 'ta.where with neither operand an array of known dtype', 'annotate one of them')
        if mk != 'AO':
            self.need_pure(m, 'a non-bool mask')
            self.need_pure(a, 'a non-bool mask')
            self.need_pure(b, 'a non-bool mask')
            return call(self.te((ak if ak in ARR else bk)[1]), const('ail_array.where() needs a bool_ array as the mask, not %s'
                                                                      % DN[mk[1]]))
        if ak in ARR:
            dt = ak[1]
            if bk in ARR:
                if bk != ak:
                    self.need_pure(m, 'a dtype mismatch')
                    self.need_pure(a, 'a dtype mismatch')
                    self.need_pure(b, 'a dtype mismatch')
                    return call(self.te(dt), const(
                        'ail_array: %s where %s: dtypes differ; write a.astype(ta.%s) or b.astype(ta.%s)' %
                        (DN[dt], DN[bk[1]], DN[bk[1]], DN[dt])))
                return call(P[dt] + 'where_aa', self.visit(m), self.visit(a), self.visit(b))
            if dt != 'F' and bk == 'F':
                self.need_pure(m, 'an int array and a float')
                self.need_pure(a, 'an int array and a float')
                self.need_pure(b, 'an int array and a float')
                return call(self.te(dt), const('ail_array: %s where float: write a.astype(ta.f64) (no implicit int-to-float)'
                                               % DN[dt]))
            return call(P[dt] + 'where_as', self.visit(m), self.visit(a), self.stored(b, bk, dt))
        dt = bk[1]
        if dt != 'F' and ak == 'F':
            self.need_pure(m, 'an int array and a float')
            self.need_pure(a, 'an int array and a float')
            self.need_pure(b, 'an int array and a float')
            return call(self.te(dt), const('ail_array: %s where float: write a.astype(ta.f64) (no implicit int-to-float)'
                                           % DN[dt]))
        return call(P[dt] + 'where_sa', self.visit(m), self.stored(a, ak, dt), self.visit(b))

    def t3b_move(self, node, found, args):
        first = 'dst' if found == 'scatter_strided' else 'a'
        a = args.get(first)
        if a is None:
            no(node, 'ta.%s needs an array' % found, 'ta.%s(...)' % found)
        kd = self.array_arg(a, 'ta.%s' % found)
        dt = kd[1]
        if found == 'take':
            if 'idx' not in args:
                no(node, 'ta.take needs indices', 'ta.take(a, idx)')
            idx = self.idx_list(args['idx'], 'ta.take')
            if idx is None:
                self.need_pure(a, 'indices that are not an int array')
                self.need_pure(args['idx'], 'indices that are not an int array')
                return call(self.te(dt), const('ail_array.take(): indices must be an int array, not %s'
                                               % DN[self.k(args['idx'])[1]]))
            return call(P[dt] + 'take', self.visit(a), idx)
        if found == 'put':
            if 'idx' not in args or 'src' not in args:
                no(node, 'ta.put needs a, idx and src', 'ta.put(a, idx, src)')
            acc = self.literal(args.get('accumulate'), bool, False, 'accumulate=')
            ov = self.literal(args.get('overflow'), str, 'raise', 'overflow=')
            if ov not in ('raise', 'wrap'):
                no(args['overflow'], "ta.put(overflow=%r)" % ov, "overflow='raise' or overflow='wrap'")
            if acc and dt == 'O':
                no(node, 'ta.put(accumulate=True) on a bool_ array', 'accumulate on an int array and compare with ta.ne(a, 0)')
            if acc and dt == 'F' and ov == 'wrap':
                no(node, "ta.put(overflow='wrap') on a float array", "drop overflow= (floats never raise)")
            idx = self.idx_list(args['idx'], 'ta.put')
            sk = self.k(args['src'])
            if idx is None:
                self.need_pure(a, 'indices that are not an int array')
                self.need_pure(args['idx'], 'indices that are not an int array')
                self.need_pure(args['src'], 'indices that are not an int array')
                return call(self.te(dt), const('ail_array.put(): indices must be an int array, not %s'
                                               % DN[self.k(args['idx'])[1]]))
            if sk in ARR:
                if sk != kd:
                    self.need_pure(a, 'a dtype mismatch')
                    self.need_pure(args['idx'], 'a dtype mismatch')
                    self.need_pure(args['src'], 'a dtype mismatch')
                    return call(self.te(dt), const('ail_array: %s put %s: dtypes differ; write a.astype(ta.%s) or b.astype(ta.%s)'
                                                   % (DN[dt], DN[sk[1]], DN[sk[1]], DN[dt])))
                if acc:
                    return call(P[dt] + 'put_add', self.visit(a), idx, self.visit(args['src']), const(ov == 'wrap'))
                return call(P[dt] + 'put', self.visit(a), idx, self.visit(args['src']))
            if dt != 'F' and sk == 'F':
                self.need_pure(a, 'a float stored into an int array')
                self.need_pure(args['idx'], 'a float stored into an int array')
                self.need_pure(args['src'], 'a float stored into an int array')
                return call(self.te(dt), const("'float' object cannot be interpreted as an integer"))
            left = self.visit(a)
            x = self.stored(args['src'], sk, dt)
            if acc:
                return call(P[dt] + 'put_add_s', left, idx, x, const(ov == 'wrap'))
            return call(P[dt] + 'put_s', left, idx, x)
        # gather_strided / scatter_strided
        for need in ('offset', 'shape', 'strides') + (('src',) if found == 'scatter_strided' else ()):
            if need not in args:
                no(node, 'ta.%s without %s' % (found, need), 'ta.%s(...) with all its arguments' % found)
        off = self.int_arg(args['offset'], 'ta.%s with an offset' % found)
        shape = self.int_list(args['shape'], 'ta.%s with a shape' % found)
        strides = self.int_list(args['strides'], 'ta.%s with strides' % found)
        if found == 'gather_strided':
            return call(P[dt] + 'gstride', self.visit(a), off, shape, strides)
        sk = self.k(args['src'])
        if sk in ARR:
            if sk != kd:
                self.need_pure(a, 'a dtype mismatch')
                self.need_pure(args['src'], 'a dtype mismatch')
                return call(self.te(dt), const('ail_array: %s scatter %s: dtypes differ; write a.astype(ta.%s) or b.astype(ta.%s)'
                                               % (DN[dt], DN[sk[1]], DN[sk[1]], DN[dt])))
            return call(P[dt] + 'sstride', self.visit(a), off, shape, strides, self.visit(args['src']))
        if dt != 'F' and sk == 'F':
            self.need_pure(a, 'a float stored into an int array')
            return call(self.te(dt), const("'float' object cannot be interpreted as an integer"))
        left = self.visit(a)
        return call(P[dt] + 'sstride_s', left, off, shape, strides, self.stored(args['src'], sk, dt))

    def t3b_segment(self, node, found, args):
        a = args.get('a')
        if a is None or 'offsets' not in args:
            no(node, 'ta.%s needs an array and offsets' % found, 'ta.%s(a, offsets)' % found)
        kd = self.array_arg(a, 'ta.%s' % found)
        dt = kd[1]
        offs = self.idx_list(args['offsets'], 'ta.%s' % found)
        if offs is None:
            self.need_pure(a, 'offsets that are not an int array')
            self.need_pure(args['offsets'], 'offsets that are not an int array')
            return call(self.te(dt), const('ail_array.%s(): indices must be an int array, not %s'
                                           % (found, DN[self.k(args['offsets'])[1]])))
        if found in ('segment_sum', 'wrapping_segment_sum'):
            if dt == 'F':
                if found == 'wrapping_segment_sum':
                    self.need_pure(a, 'wrapping_segment_sum of a float array')
                    self.need_pure(args['offsets'], 'wrapping_segment_sum of a float array')
                    return call('_ail_ta_te_al', const('ail_array.wrapping_segment_sum() is defined for int arrays, not f64'))
                return call('_ail_taf_segsum', self.visit(a), offs)
            return call(P[dt] + 'segsum', self.visit(a), offs, const(found == 'wrapping_segment_sum'), const(found))
        short = found.split('_', 1)[1]          # min max argmin argmax
        return call(P[dt] + 'seg' + short, self.visit(a), offs)


# ---------------------------------------------------------------------------------------------------------------------
# ---------------------------------------------------------------------------------------------------------------------
# Fusion of f64 element-wise code (docs/design/TYPED_ARRAY.md 5.2a).
#
# The lowering above turns `a * b + a` into `_ail_taf_bin(_ail_taf_bin(a, b, 2), a, 0)`: one pass over memory per operation, each with
# an array allocated and filled for its result.  This pass (every build) rewrites such a tree into ONE call of a generated function
# whose loop computes the whole expression for one element at a time:
#
#   map        `_ail_taf_fu<N>`  a tree of f64 `+ - * /`, unary minus, `abs`, `minimum`, `maximum`, `clip` (any scalar operand)
#   in place   `_ail_taf_fi<N>`  `a += <tree>`, `a -= ...`, `a *= ...`, `a /= ...`: the loop reads and writes `a`
#   sum        `_ail_taf_fs<N>`  `ta.sum(<tree>)`: the tree is evaluated one block of 1024 elements at a time into a scratch array of
#                                the block, which `_ail_ta_bsum` adds in the fixed order of design 3.5 (16 lanes, then 8-4-2-1);
#                                no array of n elements is made
#   dot        `_ail_taf_fd<N>`  `ta.dot(x, y)` with a tree on either side: the same, the scratch array holds the products
#
# Why the bits are the same as T2's one pass per operation (every claim has a test in test_ail_array_fuse.py):
# * every operation is the same binary64 operation on the same operands in the same order; the build says -ffp-contract=off, so a
#   multiply and an add are never fused;
# * T2 makes a NaN canonical after every operation.  Every operation here (+ - * /, neg, abs, minimum, maximum) gives a NaN when an
#   operand is a NaN, so a NaN that appears stays a NaN down to the end of the tree and is made canonical there, once: the same
#   bits.  A tree whose last operation is minimum/maximum/clip needs no canonicalisation at all: it only returns a NaN through the
#   explicit canonical NaN of its NaN branch;
# * `x / y` is IEEE and never raises (T2's rule, decision TA2): y == 0 goes through `_ail_ta_fdiv0` exactly as T2 does it;
# * `ta.sum` / `ta.dot` skip the per-element canonicalisation too: a NaN element makes the sum a NaN, and the result is made canonical
#   at the end as before; the products of `ta.dot` are rounded to binary64 before they are added (they are stored in the scratch array);
# * the shape checks are made first, in the order the unfused code made them, with the same text; a tree with an operand that is
#   a call, a subscript or anything but a name, a constant or an attribute chain is not fused as a whole (evaluating all operands
#   first could change which error comes first, or which side effect happens first): only its top operation is, when that is
#   worth it, with its operands evaluated where they stood.
#
# -----------------------------------------------------------------------------------------------------
MAX_FUSED = 256
FSYM = {0: '+', 1: '-', 2: '*', 3: '/'}
MAPFN = ('_ail_taf_bin', '_ail_taf_bin_s', '_ail_taf_neg', '_ail_taf_abs', '_ail_taf_pick_aa', '_ail_taf_pick_as')
BINARY = ('op', 'pk')       # ('op', code, L, R)   ('pk', smaller, L, R)
SCALAR_NODES = ('sc', 'ps')       # ('sc', code, A, scalar, refl)   ('ps', smaller, A, scalar)
UNARY = ('neg', 'abs')      # ('neg', A)   ('abs', A)


def _is_call(node, name, nargs):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == name and not node.keywords
            and len(node.args) == nargs)


def _small_int(node, allowed):
    return isinstance(node, ast.Constant) and type(node.value) is int and node.value in allowed


def _small_bool(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, bool)


def _kids(t):
    k = t[0]
    if k in BINARY:
        return [t[2], t[3]]
    if k in SCALAR_NODES:
        return [t[2]]
    if k in UNARY:
        return [t[1]]
    return []


class Fuser(ast.NodeTransformer):
    def __init__(self):
        self.defs = []          # Python source of the generated functions
        self.made = {}          # shape key -> function name
        self.counter = 0

    # -- what may be a leaf -------------------------------------------------------------------------------------------------
    def pure(self, node):
        if isinstance(node, (ast.Name, ast.Constant)):
            return True
        if isinstance(node, ast.Attribute):
            return self.pure(node.value)
        return False

    def pure_scalar(self, node):
        if self.pure(node):
            return True
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            return self.pure_scalar(node.operand)
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult)):
            return self.pure_scalar(node.left) and self.pure_scalar(node.right)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ('float', '_ail_ta_b2f') \
                and len(node.args) == 1 and not node.keywords:
            return self.pure_scalar(node.args[0])
        return False

    def leafkey(self, node):
        """Two occurrences of the same name (a Store and a Load of `a` in `a += ...`) are the same leaf."""
        if isinstance(node, ast.Name):
            return ('n', node.id)
        if isinstance(node, ast.Attribute):
            return ('a', self.leafkey(node.value), node.attr)
        return ('d', ast.dump(node))

    # -- the tree of one f64 expression --------------------------------------------------------------------------------------
    def tree(self, node, deep):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords):
            return None
        f, a = node.func.id, node.args
        if f == '_ail_taf_bin' and len(a) == 3 and _small_int(a[2], FSYM):
            return ('op', a[2].value, self.sub(a[0], deep), self.sub(a[1], deep))
        if f == '_ail_taf_bin_s' and len(a) == 4 and _small_int(a[2], FSYM) and _small_bool(a[3]):
            return ('sc', a[2].value, self.sub(a[0], deep), a[1], a[3].value)
        if f == '_ail_taf_neg' and len(a) == 1:
            return ('neg', self.sub(a[0], deep))
        if f == '_ail_taf_abs' and len(a) == 1:
            return ('abs', self.sub(a[0], deep))
        if f == '_ail_taf_pick_aa' and len(a) == 3 and _small_bool(a[2]):
            return ('pk', a[2].value, self.sub(a[0], deep), self.sub(a[1], deep))
        if f == '_ail_taf_pick_as' and len(a) == 3 and _small_bool(a[2]):
            return ('ps', a[2].value, self.sub(a[0], deep), a[1])
        return None

    def sub(self, node, deep):
        """A child: part of the tree when `deep`, else an opaque leaf (the expression as it stands)."""
        t = self.tree(node, True) if deep else None
        return t if t is not None else ('leaf', node)

    def ok(self, t, deep):
        """Every leaf of a deep tree must be plain; a scalar operand must be a plain number expression."""
        k = t[0]
        if k == 'leaf':
            return not deep or self.pure(t[1])
        if k in SCALAR_NODES:
            return self.ok(t[2], deep) and (not deep or self.pure_scalar(t[3]))
        return all(self.ok(x, deep) for x in _kids(t))

    def count(self, t):
        return 0 if t[0] == 'leaf' else 1 + sum(self.count(x) for x in _kids(t))

    # -- the shape of a tree with its leaves and scalars numbered ------------------------------------------------------------
    def number(self, t, arrays, scalars):
        """The shape of `t` (a hashable tuple); `arrays` and `scalars` collect the expressions in order of first use."""
        k = t[0]
        if k == 'leaf':
            key = self.leafkey(t[1]) if self.pure(t[1]) else None        # an opaque operand is evaluated where it stood, once
            for i, (kk, _) in enumerate(arrays):
                if kk is not None and kk == key:
                    return ('leaf', i)
            arrays.append((key, t[1]))
            return ('leaf', len(arrays) - 1)
        if k in BINARY:
            left = self.number(t[2], arrays, scalars)
            return (k, t[1], left, self.number(t[3], arrays, scalars))
        if k in SCALAR_NODES:
            left = self.number(t[2], arrays, scalars)
            key = ast.dump(t[3]) if self.pure_scalar(t[3]) else None
            for i, (kk, _) in enumerate(scalars):
                if kk is not None and kk == key:
                    return (k, t[1], left, i) + tuple(t[4:])
            scalars.append((key, t[3]))
            return (k, t[1], left, len(scalars) - 1) + tuple(t[4:])
        return (k, self.number(t[1], arrays, scalars))

    def first(self, s):
        while s[0] != 'leaf':
            s = _kids(s)[0]
        return s[1]

    def checks(self, s, out):
        """The shape checks of the unfused code, in its order: the operands of an operation, then its own check."""
        if s[0] == 'leaf':
            return
        for x in _kids(s):
            self.checks(x, out)
        if s[0] in BINARY:
            out.append((self.first(s[2]), self.first(s[3])))

    def check_lines(self, pairs):
        lines, seen = [], set()
        for l, r in pairs:
            if l == r or (l, r) in seen:                    # the same array against itself cannot differ
                continue
            seen.add((l, r))
            lines.append('    if len(a%d.d) != len(a%d.d):' % (r, l))
            lines.append('        _ail_ta_shapes(len(a%d.d), len(a%d.d))' % (l, r))
        return lines

    # -- the CPU loops: one element at a time, straight-line statements -------------------------------------------------------------
    def emit(self, s, out, cnt):
        """Appends to `out` the statements that compute the shape `s` for one element; returns the name of the value."""
        k = s[0]
        if k == 'leaf':
            return 'p%d' % s[1]
        if k in UNARY:
            a = self.emit(s[1], out, cnt)
            cnt[0] += 1
            t = 't%d' % cnt[0]
            out.append('%s = %s' % (t, ('-' + a) if k == 'neg' else 'math.fabs(%s)' % a))
            return t
        if k in ('op', 'sc'):
            if k == 'op':
                l = self.emit(s[2], out, cnt)
                r = self.emit(s[3], out, cnt)
            else:
                a = self.emit(s[2], out, cnt)
                x = 's%d' % s[3]
                l, r = (x, a) if s[4] else (a, x)
            cnt[0] += 1
            t = 't%d' % cnt[0]
            if s[1] < 3:
                out.append('%s = %s %s %s' % (t, l, FSYM[s[1]], r))
            else:                                   # T2's rule: no ZeroDivisionError, IEEE (decision TA2)
                out += ['if %s == 0.0:' % r, '    %s = _ail_ta_fdiv0(%s, %s)' % (t, l, r), 'else:', '    %s = %s / %s' % (t, l, r)]
            return t
        l = self.emit(s[2], out, cnt)               # minimum / maximum: T2's _ail_taf_pick_aa / _ail_taf_pick_as, line by line
        r = self.emit(s[3], out, cnt) if k == 'pk' else 's%d' % s[3]
        cnt[0] += 1
        t = 't%d' % cnt[0]
        out += ['if %s != %s or %s != %s:' % (l, l, r, r), '    %s = nan' % t,
                'elif %s_ail_ta_fless(%s, %s):' % ('' if s[1] else 'not ', r, l), '    %s = %s' % (t, r),
                'else:', '    %s = %s' % (t, l)]
        return t

    @staticmethod
    def canon_free(s):
        """minimum / maximum return a NaN only through their explicit canonical NaN."""
        return s[0] in ('pk', 'ps')

    @staticmethod
    def indent(lines, n):
        return [(' ' * n + l) if l else l for l in lines]

    def loads(self, na, form):
        return ['p%d = %s' % (i, form % i) for i in range(na)]

    def head(self, name, na, ns, ret):
        params = ['a%d: _AilTAF' % i for i in range(na)] + ['s%d: float' % i for i in range(ns)]
        return 'def %s(%s) -> %s:' % (name, ', '.join(params), ret)

    def make_map(self, shape, na, ns):
        key = ('f', False, shape)
        if key in self.made:
            return self.made[key]
        n = self.counter
        self.counter += 1
        name, kname = '_ail_taf_fu%d' % n, '_ail_taf_fk%d' % n
        body, cnt = [], [0]
        res = self.emit(shape, body, cnt)
        if not self.canon_free(shape):
            body += ['if %s != %s:' % (res, res), '    %s = nan' % res]
        kparams = ['x%d: list[float]' % i for i in range(na)] + ['s%d: float' % i for i in range(ns)]
        lines = ['def %s(%s) -> list[float]:' % (kname, ', '.join(kparams)),
                 '    n = len(x0)', '    nan = math.nan', '    o = [0.0] * n', '    for k in range(n):']
        lines += self.indent(self.loads(na, 'x%d[k]') + body + ['o[k] = %s' % res], 8)
        lines += ['    return o', '', '']
        lines.append(self.head(name, na, ns, '_AilTAF'))
        lines.append('    n = len(a0.d)')
        checks = []
        self.checks(shape, checks)
        lines += self.check_lines(checks)
        lines += ['    out = _AilTAF(0)',
                  '    out.d = %s(%s)' % (kname, ', '.join(['a%d.d' % i for i in range(na)] + ['s%d' % i for i in range(ns)])),
                  '    return out']
        self.defs.append('\n'.join(lines) + '\n')
        self.made[key] = name
        return name

    def make_inplace(self, shape, na, ns):
        key = ('i', shape)
        if key in self.made:
            return self.made[key]
        n = self.counter
        self.counter += 1
        name, kname = '_ail_taf_fi%d' % n, '_ail_taf_fk%d' % n
        body, cnt = [], [0]
        res = self.emit(shape, body, cnt)
        if not self.canon_free(shape):
            body += ['if %s != %s:' % (res, res), '    %s = nan' % res]
        # the loop is a function of its own that returns nothing: a function that returns an array is not compiled by the IR
        lines = [self.head(kname, na, ns, 'None'), '    n = len(a0.d)', '    nan = math.nan', '    for k in range(n):']
        lines += self.indent(self.loads(na, 'a%d.d[k]') + body + ['a0.d[k] = %s' % res], 8)
        lines += ['', '']
        lines.append(self.head(name, na, ns, '_AilTAF'))
        lines.append('    n = len(a0.d)')
        checks = []
        self.checks(shape, checks)
        lines += self.check_lines(checks)
        lines += ['    %s(%s)' % (kname, ', '.join(['a%d' % i for i in range(na)] + ['s%d' % i for i in range(ns)])), '    return a0']
        self.defs.append(chr(10).join(lines) + chr(10))
        self.made[key] = name
        return name

    def make_reduce(self, shapes, na, ns, dot):
        """sum of `shapes[0]`, or the dot of `shapes[0]` and `shapes[1]`, one block of 1024 elements at a time."""
        key = ('d' if dot else 's',) + tuple(shapes)
        if key in self.made:
            return self.made[key]
        name = '_ail_taf_f%s%d' % ('d' if dot else 's', self.counter)
        self.counter += 1
        body, cnt = [], [0]
        res = [self.emit(s, body, cnt) for s in shapes]
        value = '%s * %s' % (res[0], res[1]) if dot else res[0]
        lines = [self.head(name, na, ns, 'float'), '    n = len(a0.d)']
        checks = []
        for s in shapes:
            self.checks(s, checks)
        if dot:
            checks.append((self.first(shapes[0]), self.first(shapes[1])))
        lines += self.check_lines(checks)
        lines += ['    if n == 0:', '        return 0.0',
                  '    nb = (n + 1023) // 1024', '    blocks = [0.0] * nb', '    m = 1024', '    if n < 1024:', '        m = n',
                  '    buf = _AilTAF(m)'] + (['    nan = math.nan'] if any(l.endswith('= nan') for l in body) else []) + [
                  '    for b in range(nb):', '        s = b * 1024', '        t = s + 1024', '        if t > n:', '            t = n',
                  '        if t - s != len(buf.d):', '            buf = _AilTAF(t - s)',
                  '        for k in range(s, t):']
        lines += self.indent(self.loads(na, 'a%d.d[k]') + body + ['buf.d[k - s] = %s' % value], 12)
        lines += ['        blocks[b] = _ail_ta_bsum(buf)',
                  '    r = _ail_ta_tree(blocks, 0, nb)', '    if r != r:', '        return math.nan', '    return r']
        self.defs.append('\n'.join(lines) + '\n')
        self.made[key] = name
        return name

    # -- the rewrite ------------------------------------------------------------------------------------------------------------
    def call_of(self, name, arrays, scalars, node):
        new = ast.Call(func=ast.Name(id=name, ctx=ast.Load()), args=[self.load(e) for _, e in arrays] + [e for _, e in scalars],
                       keywords=[])
        return ast.copy_location(new, node)

    @staticmethod
    def load(e):
        return ast.Name(id=e.id, ctx=ast.Load()) if isinstance(e, ast.Name) else e

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            fn = node.func.id
            fused = None
            if fn in MAPFN:
                fused = self.fuse(node)
            elif fn == '_ail_taf_ibin' and len(node.args) == 3 and not node.keywords:
                fused = self.fuse_inplace(node)
            elif fn == '_ail_taf_sum' and len(node.args) == 1 and not node.keywords:
                fused = self.fuse_reduce(node, [node.args[0]], False)
            elif fn == '_ail_taf_dot' and len(node.args) == 2 and not node.keywords:
                fused = self.fuse_reduce(node, node.args, True)
            if fused is not None:
                return fused
        return self.generic_visit(node)

    def fuse(self, node):
        for deep in (True, False):
            t = self.tree(node, deep)
            if t is None or not self.ok(t, deep):
                continue
            c = self.count(t)
            if c > MAX_FUSED or c < 1:
                continue
            arrays, scalars = [], []
            shape = self.number(t, arrays, scalars)
            name = self.make_map(shape, len(arrays), len(scalars))
            new = self.call_of(name, arrays, scalars, node)
            return new if deep else self.generic_visit(new)      # opaque operands may hold more of the same
        return None

    def fuse_inplace(self, node):
        """`a = _ail_taf_ibin(a, <tree>, code)`: the loop reads and writes `a`."""
        target, rhs, code = node.args
        if not (isinstance(target, ast.Name) and _small_int(code, FSYM)):
            return None
        t = self.tree(rhs, True)
        if t is None or not self.ok(t, True) or self.count(t) + 1 > MAX_FUSED:
            return None
        whole = ('op', code.value, ('leaf', target), t)
        arrays, scalars = [], []
        shape = self.number(whole, arrays, scalars)
        return self.call_of(self.make_inplace(shape, len(arrays), len(scalars)), arrays, scalars, node)

    def fuse_reduce(self, node, args, dot):
        """`ta.sum(<tree>)`, `ta.dot(x, y)` with a tree among x, y."""
        for deep in (True, False):
            trees = []
            for i, a in enumerate(args):
                t = self.tree(a, deep)
                if t is None or not self.ok(t, deep):
                    if deep and self.pure(a):
                        t = ('leaf', a)
                    elif dot and deep and i == 0 and len(args) == 2:
                        t = ('leaf', a)         # an opaque first operand is evaluated first, as it was
                    else:
                        trees = None
                        break
                trees.append(t)
            if trees is None:
                continue
            if not dot and not deep and trees[0][0] == 'leaf':
                continue
            if dot and not deep:
                continue                        # the second operand would be evaluated before the first one's checks
            c = sum(self.count(t) for t in trees)
            if c < 1 or c > MAX_FUSED:
                continue
            arrays, scalars = [], []
            shapes = [self.number(t, arrays, scalars) for t in trees]
            name = self.make_reduce(shapes, len(arrays), len(scalars), dot)
            new = self.call_of(name, arrays, scalars, node)
            return new if deep else self.generic_visit(new)
        return None


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
        fuser = Fuser()                                    # element-wise fusion (docs/design/TYPED_ARRAY.md 5.2a)
        tree.body = [fuser.visit(st) for st in tree.body]
        ast.fix_missing_locations(tree)
        used = set()
        for each in ast.walk(tree):
            if isinstance(each, ast.Name) and (each.id.startswith('_ail_ta') or each.id.startswith('_AilTA')):
                used.add(each.id)
        stdlib5.leftover(tree, binder, 'the dtypes are literals ta.f64 / ta.int32, and the functions are called directly')
        for each in ast.walk(tree):
            if isinstance(each, ast.Name) and each.id in binder.aliases:
                refuse(each, 'ail_array used as a value is not built')
        body = stdlib5.shake(prelude_source() + ('\n\n' + '\n\n'.join(fuser.defs) if fuser is not None else ''), used)
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
