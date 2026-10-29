# -*- coding: utf-8 -*-
"""gpu.py -- stage G1 of docs/design/GPU.md: the `# ail: gpu` marker, the eligibility proof, the kernel IR and its
CPU emulation.

What it does (and what it does not):

* `compile --gpu` (env AIL_GPU_BUILD=1) turns the feature on.  Without it nothing in this module runs and the generated
  C is byte for byte what it was (a `# ail: gpu` comment is only a comment).
* A comment `# ail: gpu` on the line before a loop, or at the end of its first line, marks the loop.  The marked
  statement must be one of the shapes of GPU.md 1.1 that G1 builds:
      for i in range(a, b): ... out[i] = <expr>          (the last statement of the body; `out` sized before the loop)
      ys = [<expr> for x in xs] / for x, y in zip(xs, ys) / for i in range(a, b)   (no `if`, one `for`; the typed
                                                                  path has no zip comprehension, so those run on the CPU)
  Anything else under the marker is refused at compile time, by name, with file:line, the reason and a
  `write instead:` hint (`GpuRefusal`).  The proof has two halves: the syntactic half (`sites_of`, run by ail_chatgpt on
  the file as written, and `check_source`, run by pyc.build before either code path is tried, so a refusal never depends
  on which path would have built the program or on how the surface layer lowered the text) and the typed half
  (`outline`, run on the typed path when the function's C is known, because int versus float, and which names are lists,
  is decided by the typed path's own declarations).  A marked loop in a program built on the general path is not
  offloaded (GPU.md 1: the general path never offloads); the build says so in a note.
* The loop body is lowered to a small kernel IR (`Kernel`), and the kernel IR to a C function that runs on the CPU
  (`emit_c`): the emulation of GPU.md 5.1 "Semantics without Vulkan".  The emulation computes into a result buffer,
  sets a flag word instead of raising (index, zero division, int64 overflow, float guards of GPU.md 3.2) and the glue
  around it either commits the buffer (flag == 0) or throws it away and runs the original CPU loop, which is the C the
  build would have produced without the marker (CPU replay, GPU.md 3.1).  So the program prints what the CPU build
  prints, whatever the kernel does.
* No SPIR-V, no Vulkan, no cost model (G2, G3, G7).  `AIL_GPU=0` at run time skips the kernel;
  `AIL_GPU_TRACE=1` prints one line per launch on stderr.

Names used for the rewrite: `_gpu_lo<k>` / `_gpu_hi<k>` hold the evaluated bounds of the range of site k.
"""
import ast
import io
import os
import re
import sys
import tokenize

from pyfront import Unsupported

INT64_MIN, INT64_MAX = -(1 << 63), (1 << 63) - 1
MARK = re.compile(r'^#\s*ail\s*:\s*gpu\s*$', re.I)
GIVE_UP = "drop '# ail: gpu' (the loop then runs on the CPU)"


class GpuRefusal(Unsupported):
    """A marked loop that is not provably eligible.  pyc.build never turns it into a general-path fallback."""


def enabled():
    return os.environ.get('AIL_GPU_BUILD', '').strip().lower() in ('1', 'on', 'yes', 'true')


def line_of(node):
    """The line of `node` in the program the user wrote (pyc's script rewrite renumbers the lines; `carry` keeps them)."""
    return getattr(node, '_ail_line', None) or getattr(node, 'lineno', None)


def refuse(node, why, hint=None):
    error = GpuRefusal('GPU loop: %s; write instead: %s' % (why, hint or GIVE_UP))
    line = line_of(node)
    if line is not None:
        error.source_line = line
    return error


# ---------------------------------------------------------------------------------------------------------------------
# the marker
# ---------------------------------------------------------------------------------------------------------------------
def marker_lines(text):
    """{line of the comment: True when the comment stands alone on its line} for every `# ail: gpu` in `text`."""
    found = {}
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.COMMENT and MARK.match(tok.string.strip()):
                found[tok.start[0]] = tok.line.strip().startswith('#')
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    return found


def _statements(tree):
    return [n for n in ast.walk(tree) if isinstance(n, ast.stmt)]


def _target_of(marks, lines, stmts):
    """{comment line: the statement it marks}.  A comment on a line of its own marks the next line with code; a comment
    after code marks the innermost statement that spans its line."""
    out = {}
    for line, own in sorted(marks.items()):
        if own:
            t = line
            while t < len(lines) and (not lines[t].strip() or lines[t].strip().startswith('#')):
                t += 1
            t += 1                                            # lines[] is 0-based, t is now the 1-based line of the code
            hits = [s for s in stmts if s.lineno == t]
            hits.sort(key=lambda s: -(s.end_lineno - s.lineno))
        else:
            hits = [s for s in stmts if s.lineno <= line <= (s.end_lineno or s.lineno)]
            hits.sort(key=lambda s: (-s.lineno, (s.end_lineno or s.lineno)))
        out[line] = hits[0] if hits else None
    return out


# ---------------------------------------------------------------------------------------------------------------------
# kernel IR.  Expressions are tuples whose first item is the op and second the type ('i' int64, 'f' binary64, 'b' bool,
# '?' unknown in the syntactic pass); statements are tuples too.
#   ('c', t, value)  ('v', t, cname)  ('ld', t, list, index)  ('len', 'i', list)
#   ('neg'|'abs'|'pos', t, a)  ('bin', t, op, a, b)  ('cmp', 'b', op, a, b, mode)  ('truth', 'b', t, a)  ('not', 'b', a)
#   ('and'|'or', 'b', a, b) boolean  ('vand'|'vor', t, a, b) value-yielding  ('sel', t, c, a, b)
#   ('cvt', t, kind, a)  ('mm', t, 'min'|'max', [args])  ('blk', t, stmts, expr)
#   ('set', cname, t, e)  ('if', c, then, else)  ('for', cname, lo, hi, body)
# ---------------------------------------------------------------------------------------------------------------------
_NUM = ('i', 'f', 'b')


class Kernel:
    def __init__(self, site):
        self.site = site
        self.lists = {}                  # python list name -> element type, in first-use order
        self.scalars = {}                # captured scalar name -> type
        self.consts = {}                 # captured module constant -> (type, value)
        self.locals = {}                 # C name -> type of every kernel local
        self.body = []
        self.result = None
        self.res_type = None
        self.elems = []                  # comp over lists: [(cname, type, list name)]
        self.loop_var = None             # (cname, type) of the counter (range loops)
        self.reads = set()               # names of lists read in the body

    def dump(self):
        """The kernel IR as text (tests and debugging)."""
        out = ['kernel %s k%d' % (self.site['kind'], self.site['k'])]
        out.append('  lists   ' + ', '.join('%s:%s' % kv for kv in self.lists.items()))
        out.append('  scalars ' + ', '.join('%s:%s' % kv for kv in self.scalars.items()))
        for s in self.body:
            out.extend(_dump_stmt(s, 1))
        out.append('  yield ' + _dump(self.result))
        return '\n'.join(out)


def _dump(e):
    if e[0] == 'c':
        return repr(e[2])
    if e[0] == 'v':
        return e[2]
    if e[0] == 'blk':
        return '{%s; %s}' % ('; '.join(' '.join(_dump_stmt(s, 0)) for s in e[2]), _dump(e[3]))
    def item(a):
        if isinstance(a, tuple):
            return _dump(a)
        if isinstance(a, list):
            return ' '.join(_dump(x) for x in a)
        return str(a)
    return '(%s %s %s)' % (e[0], e[1], ' '.join(item(a) for a in e[2:]))


def _dump_stmt(s, depth):
    pad = '  ' * (depth + 1)
    if s[0] == 'set':
        return [pad + '%s:%s = %s' % (s[1], s[2], _dump(s[3]))]
    if s[0] == 'if':
        out = [pad + 'if ' + _dump(s[1])]
        for t in s[2]:
            out.extend(_dump_stmt(t, depth + 1))
        if s[3]:
            out.append(pad + 'else')
            for t in s[3]:
                out.extend(_dump_stmt(t, depth + 1))
        return out
    out = [pad + 'for %s in %s..%s' % (s[1], _dump(s[2]), _dump(s[3]))]
    for t in s[4]:
        out.extend(_dump_stmt(t, depth + 1))
    return out


# ---------------------------------------------------------------------------------------------------------------------
# the proof and the lowering to kernel IR (one pass; `oracle` None = syntactic half, types unknown)
# ---------------------------------------------------------------------------------------------------------------------
_STMT_NAMES = {
    ast.Expr: 'a call or expression statement (print, append, a helper)', ast.Return: 'return',
    ast.Break: 'break', ast.Continue: 'continue', ast.While: 'a while loop', ast.Try: 'try', ast.With: 'with',
    ast.Raise: 'raise', ast.Assert: 'assert', ast.Delete: 'del', ast.Global: 'global', ast.Nonlocal: 'nonlocal',
    ast.Import: 'import', ast.ImportFrom: 'import', ast.FunctionDef: 'a nested def', ast.ClassDef: 'a class',
}
_FLOAT_MATH_G5 = {'sqrt': 'math.sqrt needs the correctly rounded GPU square root of stage G5'}
_FLOAT_MATH = {'exp', 'log', 'log2', 'log10', 'pow', 'sin', 'cos', 'tan', 'asin', 'acos', 'atan', 'atan2', 'sinh',
               'cosh', 'tanh', 'hypot', 'fmod', 'fabs', 'copysign', 'fsum', 'isnan', 'isinf', 'isfinite', 'cbrt',
               'expm1', 'log1p', 'erf', 'gamma', 'lgamma', 'degrees', 'radians', 'ldexp', 'frexp', 'modf',
               'factorial', 'comb', 'perm', 'gcd', 'lcm', 'isqrt', 'remainder', 'dist', 'prod'}
_BAD_BIN = {ast.Div: ('`/` needs the correctly rounded GPU division of stage G5',
                      'compute with `*` and `//`, or drop the marker (the loop runs on the CPU)'),
            ast.Pow: ('`**` has no exact GPU form (floats: libm; ints: big integers)',
                      'write the product out (`x * x`), or drop the marker'),
            ast.LShift: ('`<<` is not available on the GPU yet', 'use `* 2` or drop the marker'),
            ast.RShift: ('`>>` is not available on the GPU yet', 'use `// 2` or drop the marker'),
            ast.BitAnd: ('`&` is not available on the GPU yet', 'drop the marker'),
            ast.BitOr: ('`|` is not available on the GPU yet', 'drop the marker'),
            ast.BitXor: ('`^` is not available on the GPU yet', 'drop the marker'),
            ast.MatMult: ('`@` is not available on the GPU', 'drop the marker')}
_OPS = {ast.Add: 'add', ast.Sub: 'sub', ast.Mult: 'mul', ast.FloorDiv: 'floordiv', ast.Mod: 'mod'}
_CMPS = {ast.Lt: '<', ast.LtE: '<=', ast.Gt: '>', ast.GtE: '>=', ast.Eq: '==', ast.NotEq: '!='}


class Frame:
    """Names of one body (the kernel's own, or an inlined function's)."""

    def __init__(self, prefix, stored, top):
        self.prefix, self.stored, self.top = prefix, stored, top
        self.vars = {}             # python name -> (C name, type)
        self.defined = set()


def _stored_names(stmts):
    out = set()
    for n in ast.walk(ast.Module(body=list(stmts), type_ignores=[])):
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            out.add(n.id)
    return out


class Builder:
    def __init__(self, site, funcs, oracle=None):
        self.site, self.funcs, self.oracle = site, funcs, oracle
        self.k = Kernel(site)
        self.stack = []
        self.counter = 0
        self.out_name = None
        self.call_site = None

    # -- helpers ------------------------------------------------------------------------------------------------
    def fail(self, node, why, hint=None):
        if self.call_site is not None:                  # inside an inlined function: say where the loop calls it
            node = self.call_site
        return refuse(node if getattr(node, 'lineno', None) else self.site['node'], why, hint)

    def fresh(self, prefix, py, t):
        self.counter += 1
        name = '%s%s' % (prefix, py)
        if name in self.k.locals and self.k.locals[name] != t:
            name = '%s_%d' % (name, self.counter)
        return name

    def declare(self, cname, t):
        self.k.locals[cname] = t

    def num(self, node, t, what):
        if t not in _NUM and t != '?':
            raise self.fail(node, '%s is not an int, float or bool' % what)

    # -- entry points ---------------------------------------------------------------------------------------------
    def build_for(self):
        s = self.site
        node, var = s['node'], s['var']
        frame = Frame('k_', _stored_names(node.body) | {var}, True)
        frame.vars[var] = ('k_' + var, 'i')
        frame.defined.add(var)
        self.k.loop_var = ('k_' + var, 'i')
        self.declare('k_' + var, 'i')
        body = node.body
        last = body[-1] if body else None
        out = s['out']
        if not (isinstance(last, ast.Assign) and len(last.targets) == 1 and isinstance(last.targets[0], ast.Subscript)
                and isinstance(last.targets[0].value, ast.Name) and last.targets[0].value.id == out
                and isinstance(last.targets[0].slice, ast.Name) and last.targets[0].slice.id == var):
            raise self.fail(node, 'the body must end with `%s[%s] = <expr>`' % (out, var),
                            'compute the value in locals and store it once, as the last statement: `%s[%s] = value`'
                            % (out, var))
        self.out_name = out
        self.k.body = self.block(body[:-1], frame)
        self.k.result = self.ex(last.value, frame)
        self.k.res_type = 'i' if self.k.result[1] == 'b' else self.k.result[1]      # a bool is stored as 0/1
        return self.k

    def build_comp(self):
        s = self.site
        comp = s['comp']
        frame = Frame('k_', set(), True)
        self.out_name = None
        for name in s['targets']:
            frame.defined.add(name)
        if s['source'] == 'range':
            name = s['targets'][0]
            frame.vars[name] = ('k_' + name, 'i')
            self.k.loop_var = ('k_' + name, 'i')
            self.declare('k_' + name, 'i')
        else:
            for name, lst in zip(s['targets'], s['lists']):
                t = self.list_type(comp, lst)
                frame.vars[name] = ('k_' + name, t)
                self.declare('k_' + name, t)
                self.k.elems.append(('k_' + name, t, lst))
                self.k.lists.setdefault(lst, t)
        self.k.result = self.ex(comp.elt, frame)
        self.k.res_type = 'i' if self.k.result[1] == 'b' else self.k.result[1]      # a bool is stored as 0/1
        return self.k

    # -- types of captured names -----------------------------------------------------------------------------------
    def list_type(self, node, name):
        if self.oracle is None:
            return '?'
        t = self.oracle('list', name, node)
        if t not in ('i', 'f'):
            raise self.fail(node, '%r is not a list[int] or list[float] the typed path holds contiguously' % name,
                            'use list[float] / list[int] data, or drop the marker')
        return t

    def scalar_type(self, node, name):
        if self.oracle is None:
            return '?'
        got = self.oracle('scalar', name, node)
        if isinstance(got, tuple):                    # a module constant: ('const', type, value)
            self.k.consts[name] = (got[1], got[2])
            return got[1]
        if got not in ('i', 'f'):
            raise self.fail(node, '%r is not an int or float scalar' % name)
        return got

    # -- statements -------------------------------------------------------------------------------------------------
    def block(self, stmts, frame):
        out = []
        for st in stmts:
            out.extend(self.stmt(st, frame))
        return out

    def assign_local(self, node, frame, name, value_ir, aug=False):
        if name in self.k.lists:
            raise self.fail(node, '%r is a list read by the body, so it cannot also be assigned' % name)
        t = value_ir[1]
        if t == 'b':
            t = 'i'
            value_ir = ('cvt', 'i', 'b2i', value_ir)
        cur = frame.vars.get(name)
        if cur is None:
            cname = self.fresh(frame.prefix, name, t)
            frame.vars[name] = (cname, t)
            self.declare(cname, t)
        else:
            cname, ct = cur
            if ct != t and '?' not in (ct, t):
                raise self.fail(node, '%r holds an %s and then a %s' % (name, 'int' if ct == 'i' else 'float',
                                                                        'int' if t == 'i' else 'float'),
                                'use one type for %r (write 0.0 for a float, float(...) to convert)' % name)
        frame.defined.add(name)
        return ('set', frame.vars[name][0], frame.vars[name][1], value_ir)

    def stmt(self, s, frame):
        if isinstance(s, ast.Assign):
            if len(s.targets) != 1:
                raise self.fail(s, 'chained assignment is not available')
            tgt = s.targets[0]
            if isinstance(tgt, ast.Subscript):
                raise self.fail(s, 'a store other than the last statement `out[i] = <expr>`',
                                'compute the value in a local and store it once, as the last statement')
            if not isinstance(tgt, ast.Name):
                raise self.fail(s, 'only a local name can be assigned (no tuple unpacking, no attribute)')
            return [self.assign_local(s, frame, tgt.id, self.ex(s.value, frame))]
        if isinstance(s, ast.AnnAssign):
            ann = s.annotation
            if not (isinstance(ann, ast.Name) and ann.id in ('int', 'float')) or s.value is None \
                    or not isinstance(s.target, ast.Name):
                raise self.fail(s, 'a local declared in the body must be `name: int|float = value`')
            return [self.assign_local(s, frame, s.target.id, self.ex(s.value, frame))]
        if isinstance(s, ast.AugAssign):
            if not isinstance(s.target, ast.Name):
                raise self.fail(s, 'only a local name can be assigned')
            op = type(s.op)
            if op in _BAD_BIN:
                raise self.fail(s, *_BAD_BIN[op])
            if op not in _OPS:
                raise self.fail(s, 'unsupported operator')
            name = s.target.id
            self.check_defined(s, name, frame, aug=True)
            cur = self.ex(ast.Name(id=name, ctx=ast.Load(), lineno=s.lineno, col_offset=0), frame)
            return [self.assign_local(s, frame, name, self.binop(s, op, cur, self.ex(s.value, frame)))]
        if isinstance(s, ast.If):
            c = self.cond(s.test, frame)
            d0 = set(frame.defined)
            then = self.block(s.body, frame)
            d1, frame.defined = frame.defined, set(d0)
            other = self.block(s.orelse, frame)
            frame.defined = d1 & frame.defined
            return [('if', c, then, other)]
        if isinstance(s, ast.For):
            return [self.inner_for(s, frame)]
        if isinstance(s, ast.Pass):
            return []
        for cls, what in _STMT_NAMES.items():
            if isinstance(s, cls):
                if isinstance(s, (ast.Break, ast.Continue)):
                    raise self.fail(s, '%s is not available in a GPU loop body' % what,
                                    'make the loop body a straight computation (use `if`/`else` or a conditional '
                                    'expression), or drop the marker')
                if isinstance(s, ast.Expr):
                    raise self.fail(s, '%s is not allowed; the body may only compute values' % what,
                                    'compute values into locals and store `out[i]`; do printing and appending '
                                    'after the loop, or drop the marker')
                raise self.fail(s, '%s is not allowed in a GPU loop body' % what)
        raise self.fail(s, '%s is not allowed in a GPU loop body' % type(s).__name__.lower())

    def inner_for(self, s, frame):
        it = s.iter
        if (s.orelse or not isinstance(s.target, ast.Name) or not isinstance(it, ast.Call)
                or not isinstance(it.func, ast.Name) or it.func.id != 'range' or it.keywords
                or not 1 <= len(it.args) <= 2):
            raise self.fail(s, 'an inner loop must be `for j in range(K)` or `range(a, b)` (no step, no else)')
        lo, hi = ((ast.Constant(value=0), it.args[0]) if len(it.args) == 1 else (it.args[0], it.args[1]))
        for bound in (lo, hi):
            self.invariant(bound, frame)
        lo_ir, hi_ir = self.ex(lo, frame), self.ex(hi, frame)
        for e in (lo_ir, hi_ir):
            if e[1] in ('f',):
                raise self.fail(s, 'a range bound must be an int')
        name = s.target.id
        var = frame.vars.get(name)
        if var is None:
            cname = self.fresh(frame.prefix, name, 'i')
            frame.vars[name] = (cname, 'i')
            self.declare(cname, 'i')
        elif var[1] not in ('i', '?'):
            raise self.fail(s, '%r holds a float and an int' % name)
        d0 = set(frame.defined)
        frame.defined.add(name)
        body = self.block(s.body, frame)
        frame.defined = d0
        return ('for', frame.vars[name][0], lo_ir, hi_ir, body)

    def invariant(self, node, frame):
        """Inner loop bounds are loop-invariant (GPU.md 1.1): constants, captured scalars, len() of a list."""
        for n in ast.walk(node):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id in frame.stored:
                raise self.fail(node, 'the bound of an inner loop depends on %r, which the loop or its body assigns' % n.id,
                                'use a bound that does not change inside the loop (a constant, a scalar defined '
                                'before it, len(xs)), or drop the marker')

    def check_defined(self, node, name, frame, aug=False):
        if name in frame.stored and name not in frame.defined:
            raise self.fail(node, '%r is read before the body assigns it. Each iteration starts with fresh locals, '
                                  'so a running total or a counter carried between iterations is not available '
                                  '(sums and counters are stage G6)' % name,
                            'assign %r at the top of the body, or compute per-element values with the GPU loop and '
                            'combine them in an ordinary loop afterwards' % name)

    # -- expressions -------------------------------------------------------------------------------------------------
    def cond(self, node, frame):
        if isinstance(node, ast.BoolOp):
            parts = [self.cond(v, frame) for v in node.values]
            op = 'and' if isinstance(node.op, ast.And) else 'or'
            out = parts[-1]
            for p in reversed(parts[:-1]):
                out = (op, 'b', p, out)
            return out
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return ('not', 'b', self.cond(node.operand, frame))
        e = self.ex(node, frame)
        if e[1] == 'b':
            return e
        return ('truth', 'b', e[1], e)

    def ex(self, node, frame):
        if isinstance(node, ast.Constant):
            v = node.value
            if isinstance(v, bool):
                return ('c', 'b', 1 if v else 0)
            if isinstance(v, int):
                if not INT64_MIN <= v <= INT64_MAX:
                    raise self.fail(node, 'the int constant %d does not fit in 64 bits' % v)
                return ('c', 'i', v)
            if isinstance(v, float):
                return ('c', 'f', v)
            raise self.fail(node, 'only int, float and bool constants are allowed (no str, bytes or None)')
        if isinstance(node, ast.Name):
            return self.name(node, frame)
        if isinstance(node, ast.BinOp):
            op = type(node.op)
            if op in _BAD_BIN:
                raise self.fail(node, *_BAD_BIN[op])
            if op not in _OPS:
                raise self.fail(node, 'unsupported operator')
            return self.binop(node, op, self.ex(node.left, frame), self.ex(node.right, frame))
        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.Not):
                return ('not', 'b', self.cond(node.operand, frame))
            if isinstance(node.op, ast.Invert):
                raise self.fail(node, '`~` is not available on the GPU yet', 'drop the marker')
            a = self.ex(node.operand, frame)
            self.num(node, a[1], 'the operand')
            t = 'i' if a[1] == 'b' else a[1]
            if isinstance(node.op, ast.USub):
                if a[0] == 'c' and a[1] in ('i', 'f'):                    # -5 and -0.0 are constants
                    v = -a[2]
                    if a[1] == 'i' and not INT64_MIN <= v <= INT64_MAX:
                        raise self.fail(node, 'the int constant %d does not fit in 64 bits' % v)
                    return ('c', a[1], v)
                return ('neg', t, self.as_(a, t))
            return ('pos', t, self.as_(a, t))
        if isinstance(node, ast.BoolOp):
            vals = [self.ex(v, frame) for v in node.values]
            t = vals[0][1]
            for v in vals:
                if v[1] != t and '?' not in (v[1], t):
                    raise self.fail(node, 'the operands of `and`/`or` have different types (%s and %s), so the type '
                                          'of the result depends on the data' % (_tname(t), _tname(v[1])),
                                    'use a conditional expression with operands of one type, or drop the marker')
            op = 'vand' if isinstance(node.op, ast.And) else 'vor'
            out = vals[-1]
            for v in reversed(vals[:-1]):
                out = (op, t, v, out)
            return out
        if isinstance(node, ast.Compare):
            return self.compare(node, frame)
        if isinstance(node, ast.IfExp):
            c = self.cond(node.test, frame)
            a, b = self.ex(node.body, frame), self.ex(node.orelse, frame)
            if a[1] != b[1] and '?' not in (a[1], b[1]):
                raise self.fail(node, 'the two branches of the conditional expression have different types (%s and '
                                      '%s), so the type of the result depends on the data'
                                % (_tname(a[1]), _tname(b[1])),
                                'give both branches one type (write 0.0 for a float, float(...) to convert), or '
                                'drop the marker')
            return ('sel', a[1], c, a, b)
        if isinstance(node, ast.Subscript):
            if not isinstance(node.value, ast.Name) or isinstance(node.slice, ast.Slice):
                raise self.fail(node, 'only xs[index] on a plain list name is allowed (no slices, fields or nested '
                                      'indexing)')
            name = node.value.id
            if not frame.top:
                raise self.fail(node, 'the function %s() indexes a list; a function called from a GPU loop may only '
                                      'use its int/float parameters' % self.stack[-1])
            if name == self.out_name:
                raise self.fail(node, 'the output list %r is also read in the body' % name,
                                'read from a separate input list, or drop the marker (a loop that reads what it writes '
                                'has an order the GPU would change)')
            if name in frame.vars or (name in frame.stored):
                raise self.fail(node, '%r is assigned in the body, so it cannot be indexed' % name)
            idx = self.ex(node.slice, frame)
            if idx[1] not in ('i', 'b', '?'):
                raise self.fail(node, 'a list index must be an int')
            t = self.list_type(node, name)
            self.k.lists.setdefault(name, t)
            self.k.reads.add(name)
            return ('ld', t, name, self.as_(idx, 'i'))
        if isinstance(node, ast.Call):
            return self.call(node, frame)
        what = type(node).__name__
        names = {'Attribute': 'an attribute (a field, math.pi)', 'Lambda': 'a lambda', 'Tuple': 'a tuple',
                 'List': 'a list display', 'ListComp': 'a nested comprehension', 'GeneratorExp': 'a generator',
                 'JoinedStr': 'an f-string', 'Dict': 'a dict', 'Set': 'a set', 'NamedExpr': 'an assignment expression',
                 'Starred': 'a starred expression', 'Await': 'await', 'Yield': 'yield', 'Slice': 'a slice'}
        raise self.fail(node, '%s is not allowed in a GPU loop body' % names.get(what, what.lower()))

    def as_(self, e, t):
        """Convert e (i, b or f) to type t for arithmetic."""
        if e[1] == t or e[1] == '?' or t == '?':
            return e
        if t == 'f':
            return ('cvt', 'f', 'i2f', e)
        if t == 'i' and e[1] == 'b':
            return e                              # bool is 0/1 in an int64
        return e

    def name(self, node, frame):
        n = node.id
        if n in frame.vars:
            self.check_defined(node, n, frame)
            cname, t = frame.vars[n]
            return ('v', t, cname)
        if n in frame.stored:
            self.check_defined(node, n, frame)
        if n in self.funcs:
            raise self.fail(node, 'the function %r is used as a value' % n)
        if not frame.top:
            raise self.fail(node, 'the function %r reads %r, which is not its parameter or local; a function called '
                                  'from a GPU loop may only use its own parameters and locals'
                            % (self.stack[-1], n))
        if n in self.k.lists or n == self.out_name:
            raise self.fail(node, 'the list %r is used as a value' % n, 'index it (%s[j]) or take len(%s)' % (n, n))
        t = self.scalar_type(node, n)
        if n not in self.k.consts:
            self.k.scalars.setdefault(n, t)
        return ('v', t, 's_' + n)

    def binop(self, node, op, a, b):
        self.num(node, a[1], 'the left operand')
        self.num(node, b[1], 'the right operand')
        if op is ast.FloorDiv and a[1] == 'f' and b[0] == 'c' and b[1] in ('i', 'f') and b[2] == 1:
            return ('cvt', 'f', 'ffloor', a)          # math.floor(x) is written int(x // 1) (ail_syntax.py): exact
        if op in (ast.FloorDiv, ast.Mod) and 'f' in (a[1], b[1]):
            raise self.fail(node, 'float `%s` has no exact GPU form (libm)' % ('//' if op is ast.FloorDiv else '%'),
                            'use int operands, or drop the marker (the loop runs on the CPU)')
        if a[1] == '?' or b[1] == '?':
            return ('bin', '?', _OPS[op], a, b)
        if op in (ast.FloorDiv, ast.Mod):
            return ('bin', 'i', _OPS[op], a, b)
        t = 'f' if 'f' in (a[1], b[1]) else 'i'
        return ('bin', t, _OPS[op], self.as_(a, t), self.as_(b, t))

    def compare(self, node, frame):
        parts = []
        left = self.ex(node.left, frame)
        for op, right_node in zip(node.ops, node.comparators):
            if type(op) not in _CMPS:
                raise self.fail(node, '`in`/`is` comparisons are not allowed', 'compare numbers with < <= > >= == !=')
            right = self.ex(right_node, frame)
            self.num(node, left[1], 'an operand'), self.num(node, right[1], 'an operand')
            if '?' in (left[1], right[1]):
                mode = '?'
            elif left[1] == right[1] or 'f' not in (left[1], right[1]):
                mode = 'f' if left[1] == 'f' else 'i'
            else:
                mode = 'if'                      # int against float: exact only below 2**53, else the flag
            parts.append(('cmp', 'b', _CMPS[type(op)], left, right, mode))
            left = right
        out = parts[-1]
        for p in reversed(parts[:-1]):
            out = ('and', 'b', p, out)
        return out

    def call(self, node, frame):
        f = node.func
        if node.keywords:
            raise self.fail(node, 'keyword arguments are not allowed in a call')
        if isinstance(f, ast.Attribute):
            if isinstance(f.value, ast.Name) and f.value.id == 'math':
                fn = f.attr
                if fn in ('floor', 'ceil', 'trunc'):
                    if len(node.args) != 1:
                        raise self.fail(node, 'math.%s() takes one argument' % fn)
                    a = self.ex(node.args[0], frame)
                    self.num(node, a[1], 'the argument')
                    if a[1] in ('i', 'b'):
                        return self.as_(a, 'i')
                    return ('cvt', 'i', fn, a)
                if fn in _FLOAT_MATH_G5:
                    raise self.fail(node, _FLOAT_MATH_G5[fn], 'drop the marker, or wait for stage G5')
                if fn in _FLOAT_MATH or True:
                    raise self.fail(node, 'math.%s has no exact GPU form (CPython uses the C library\'s result)' % fn,
                                    "drop '# ail: gpu' (the loop runs on the CPU) or move the math.%s call out of the "
                                    'loop' % fn)
            raise self.fail(node, 'a method call (.%s) is not allowed in a GPU loop body' % f.attr)
        if not isinstance(f, ast.Name):
            raise self.fail(node, 'only plain calls are allowed')
        n = f.id
        if n.startswith('_ail_math_'):
            fn = n[len('_ail_math_'):]
            if fn in _FLOAT_MATH_G5:
                raise self.fail(node, _FLOAT_MATH_G5[fn], 'drop the marker, or wait for stage G5')
            raise self.fail(node, 'math.%s has no exact GPU form (CPython uses the C library\'s result)' % fn,
                            "drop '# ail: gpu' (the loop runs on the CPU) or move the math.%s call out of the loop" % fn)
        if n in self.funcs:
            return self.inline(node, frame)
        args = node.args
        if n == 'len':
            if len(args) != 1 or not isinstance(args[0], ast.Name) or args[0].id in frame.stored:
                raise self.fail(node, 'len() takes a list name')
            name = args[0].id
            if not frame.top:
                raise self.fail(node, 'len() of a list inside %s(); a function called from a GPU loop may only use '
                                      'its int/float parameters' % self.stack[-1])
            if name == self.out_name:
                raise self.fail(node, 'the output list %r is also read in the body' % name,
                                'read its length before the loop and use that scalar')
            t = self.list_type(node, name)
            self.k.lists.setdefault(name, t)
            self.k.reads.add(name)
            return ('len', 'i', name)
        if n == 'abs':
            if len(args) != 1:
                raise self.fail(node, 'abs() takes one argument')
            a = self.ex(args[0], frame)
            self.num(node, a[1], 'the argument')
            t = 'i' if a[1] == 'b' else a[1]
            return ('abs', t, self.as_(a, t))
        if n in ('min', 'max'):
            if not 2 <= len(args) <= 3:
                raise self.fail(node, '%s() of a list or generator is a reduction (stage G6); here it takes two or '
                                      'three scalars' % n, 'compare the scalars, or drop the marker')
            vals = [self.ex(a, frame) for a in args]
            t = vals[0][1]
            for v in vals:
                if v[1] not in ('i', 'f', '?') or (v[1] != t and '?' not in (v[1], t)):
                    raise self.fail(node, 'the arguments of %s() are not all ints or all floats, so the type of the '
                                          'result depends on the data' % n,
                                    'convert them to one type (float(...)), or drop the marker')
            return ('mm', t, n, vals)
        if n == 'float':
            if len(args) != 1:
                raise self.fail(node, 'float() takes one numeric argument')
            a = self.ex(args[0], frame)
            self.num(node, a[1], 'the argument')
            return a if a[1] in ('f', '?') else ('cvt', 'f', 'i2f', a)
        if n == 'int':
            if len(args) != 1:
                raise self.fail(node, 'int() takes one numeric argument')
            a = self.ex(args[0], frame)
            self.num(node, a[1], 'the argument')
            if a[1] == 'f':
                return ('cvt', 'i', 'trunc', a)
            return self.as_(a, 'i') if a[1] != '?' else a
        if n == 'round':
            raise self.fail(node, 'round() has no exact GPU form', 'use math.floor(x + 0.5) when that is what you '
                                                                    'mean, or drop the marker')
        if n in ('sum', 'any', 'all', 'sorted', 'list', 'range', 'zip', 'map', 'filter', 'enumerate', 'reversed'):
            raise self.fail(node, '%s() is not allowed in a GPU loop body (reductions are stage G6)' % n)
        if n == 'print':
            raise self.fail(node, 'print is not allowed in a GPU loop body', 'print after the loop')
        raise self.fail(node, '%s() is not a function a GPU loop body can call (int/float/abs/min/max/len, '
                              'math.floor/ceil/trunc, or a top-level function over int and float)' % n)

    # -- calls of top-level functions: inlined ------------------------------------------------------------------------
    def inline(self, node, frame):
        name = node.func.id
        fn = self.funcs[name]
        if name in self.stack:
            raise self.fail(node, '%s() is recursive, so it cannot run in a GPU loop' % name)
        if (fn.decorator_list or fn.args.defaults or fn.args.vararg or fn.args.kwonlyargs or fn.args.kwarg
                or fn.args.posonlyargs):
            raise self.fail(node, '%s() has decorators, defaults or variadic parameters' % name)
        if len(node.args) != len(fn.args.args):
            raise self.fail(node, '%s() takes %d arguments' % (name, len(fn.args.args)))
        types = []
        for a in fn.args.args:
            if not (isinstance(a.annotation, ast.Name) and a.annotation.id in ('int', 'float')):
                raise self.fail(node, '%s() is called in a GPU loop, so its parameters must be annotated int or float '
                                      '(%s is not)' % (name, a.arg),
                                'annotate the parameters of %s() as int or float' % name)
            types.append('i' if a.annotation.id == 'int' else 'f')
        ret = fn.returns
        if not (isinstance(ret, ast.Name) and ret.id in ('int', 'float', '__ail_checked_int__',
                                                         '__ail_checked_float__')):
            raise self.fail(node, '%s() is called in a GPU loop, so it must return int or float' % name,
                            'annotate %s() as returning int or float' % name)
        rtype = 'f' if 'float' in ret.id else 'i'
        body = [s for i, s in enumerate(fn.body)
                if not (i == 0 and isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant)
                        and isinstance(s.value.value, str))]
        returns = [n for n in ast.walk(ast.Module(body=body, type_ignores=[])) if isinstance(n, ast.Return)]
        if not body or not isinstance(body[-1], ast.Return) or body[-1].value is None or len(returns) != 1:
            raise self.fail(node, '%s() must have a single `return <expr>` as its last statement to run in a GPU loop'
                            % name, 'rewrite %s() with one return at the end (use a conditional expression)' % name)
        self.counter += 1
        callee = Frame('c%d_' % self.counter, _stored_names(body) | {a.arg for a in fn.args.args}, False)
        pre = []
        for a, want, arg in zip(fn.args.args, types, node.args):
            e = self.ex(arg, frame)
            if e[1] != want and '?' not in (e[1], want):
                if not (e[1] == 'b' and want == 'i'):
                    raise self.fail(node, 'argument %r of %s() is %s but the parameter is %s'
                                    % (a.arg, name, _tname(e[1]), _tname(want)),
                                    'pass %s' % ('float(...)' if want == 'f' else 'an int'))
            cname = '%s%s' % (callee.prefix, a.arg)
            callee.vars[a.arg] = (cname, want)
            callee.defined.add(a.arg)
            self.declare(cname, want)
            pre.append(('set', cname, want, self.as_(e, want) if e[1] != 'b' else e))
        self.stack.append(name)
        outer, self.call_site = self.call_site, self.call_site or node
        try:
            stmts = pre + self.block(body[:-1], callee)
            value = self.ex(body[-1].value, callee)
        finally:
            self.stack.pop()
            self.call_site = outer
        if value[1] == 'b':
            value = ('cvt', 'i', 'b2i', value)
        if value[1] != rtype and '?' not in (value[1], rtype):
            raise self.fail(node, '%s() is declared to return %s but returns %s'
                            % (name, _tname(rtype), _tname(value[1])))
        return ('blk', rtype, stmts, value)


def _tname(t):
    return {'i': 'int', 'f': 'float', 'b': 'bool', '?': 'unknown'}.get(t, t)


# ---------------------------------------------------------------------------------------------------------------------
# the syntactic half: sites, rewrites, flow
# ---------------------------------------------------------------------------------------------------------------------
_NEXT = [0]
_FUNCS = {}
APPLIED = set()          # lines of the sites whose kernel was built
MARKED = {}              # line -> text of the site, for the end-of-build notes


def _funcs_of(tree):
    return {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}


def _classify(stmt, funcs):
    """The site description of a marked statement, or a refusal naming why it is not a candidate."""
    if isinstance(stmt, ast.For):
        it = stmt.iter
        if stmt.orelse:
            raise refuse(stmt, 'a `for ... else` loop', 'remove the else branch, or drop the marker')
        if not isinstance(stmt.target, ast.Name):
            raise refuse(stmt, 'the loop variable must be a single name', 'use `for i in range(...)`')
        if not (isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == 'range'
                and not it.keywords and 1 <= len(it.args) <= 2):
            raise refuse(stmt, 'only `for i in range(a)` and `for i in range(a, b)` can be GPU loops (a step, a '
                               'list or another iterator cannot)',
                         'loop over the index: `for i in range(len(xs)): ... xs[i] ...`')
        if not stmt.body:
            raise refuse(stmt, 'the loop body is empty')
        last = stmt.body[-1]
        if not (isinstance(last, ast.Assign) and len(last.targets) == 1 and isinstance(last.targets[0], ast.Subscript)
                and isinstance(last.targets[0].value, ast.Name)):
            raise refuse(stmt, 'the loop does not end with a store `out[i] = <expr>` into a list; a loop that only '
                               'accumulates is a reduction (stage G6)',
                         'end the body with `out[i] = <expr>` into a list sized before the loop, or drop the marker')
        return dict(kind='for', node=stmt, var=stmt.target.id, out=last.targets[0].value.id)
    if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
        v = stmt.value
        if isinstance(v, ast.ListComp):
            if len(v.generators) != 1:
                raise refuse(stmt, 'a comprehension with %d `for` clauses' % len(v.generators),
                             'use one `for` clause, or nest the work in a function, or drop the marker')
            g = v.generators[0]
            if g.is_async:
                raise refuse(stmt, 'an async comprehension')
            if g.ifs:
                raise refuse(stmt, 'a comprehension with `if` builds a list of data-dependent length, which a map '
                                   'kernel cannot fill', 'compute a value for every element, then filter in an '
                                   'ordinary loop, or drop the marker')
            it = g.iter
            if (isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == 'range'
                    and not it.keywords and 1 <= len(it.args) <= 2 and isinstance(g.target, ast.Name)):
                return dict(kind='comp', node=stmt, comp=v, source='range', targets=[g.target.id], lists=[],
                            target=stmt.targets[0].id)
            if isinstance(it, ast.Name) and isinstance(g.target, ast.Name):
                return dict(kind='comp', node=stmt, comp=v, source='list', targets=[g.target.id], lists=[it.id],
                            target=stmt.targets[0].id)
            if (isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == 'zip' and not it.keywords
                    and 2 <= len(it.args) <= 3 and all(isinstance(a, ast.Name) for a in it.args)
                    and isinstance(g.target, ast.Tuple) and len(g.target.elts) == len(it.args)
                    and all(isinstance(e, ast.Name) for e in g.target.elts)):
                return dict(kind='comp', node=stmt, comp=v, source='list', targets=[e.id for e in g.target.elts],
                            lists=[a.id for a in it.args], target=stmt.targets[0].id)
            raise refuse(stmt, 'the comprehension must run over range(a, b), a list name, or zip() of list names',
                         'iterate `range(len(xs))` or the list itself, or drop the marker')
        if isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and v.func.id in ('sum', 'min', 'max', 'any', 'all'):
            raise refuse(stmt, '%s(...) is a reduction (stage G6)' % v.func.id,
                         'build the list of values with a marked comprehension, then reduce it in an ordinary line')
    if isinstance(stmt, ast.AugAssign):
        raise refuse(stmt, 'an accumulation `%s %s= ...` is a reduction (stage G6)'
                     % (ast.unparse(stmt.target), ast.unparse(stmt.op)),
                     'mark the loop that computes the per-element values and add them up in an ordinary loop')
    if isinstance(stmt, ast.While):
        raise refuse(stmt, 'a while loop (its trip count is data-dependent)', 'use `for i in range(n)`')
    raise refuse(stmt, 'the marker is not on a `for` loop or a list-comprehension assignment (it is on %s)'
                 % _STMT_WORDS.get(type(stmt), type(stmt).__name__.lower()),
                 'put `# ail: gpu` on the line before a `for i in range(...)` loop, or at the end of '
                 '`ys = [<expr> for x in xs]`')


_STMT_WORDS = {ast.Assign: 'an assignment', ast.AugAssign: 'an assignment', ast.AnnAssign: 'an assignment',
               ast.Expr: 'an expression statement', ast.If: 'an if statement', ast.With: 'a with statement',
               ast.Return: 'a return', ast.FunctionDef: 'a def', ast.ClassDef: 'a class', ast.Try: 'a try statement',
               ast.Import: 'an import', ast.ImportFrom: 'an import'}


# pyc._rewrite_script unparses the program (a top-level `main()` call is enough), which drops the comments and renumbers the
# lines.  Before the unparse it records which statements were marked, by their place in the walk of the new tree and keyed
# by the text the unparse made; `prepare` finds them again in the parse of that text.
CARRY = {}


def marked_statements(tree, text):
    """The statements of `tree` (parsed from `text`) that carry a marker; [] unless the feature is on."""
    if not enabled():
        return []
    marks = marker_lines(text)
    if not marks:
        return []
    targets = _target_of(marks, text.splitlines(), _statements(tree))
    return [s for s in targets.values() if s is not None]


def remember(new_tree, marked, text):
    """After `ast.unparse(new_tree)` made `text`: keep where the marked statements are."""
    if not marked:
        return
    nodes = list(ast.walk(new_tree))
    ids = {id(m) for m in marked}
    CARRY[text] = ([type(n).__name__ for n in nodes], [getattr(n, 'lineno', None) for n in nodes],
                   [i for i, n in enumerate(nodes) if id(n) in ids])


def _carried(tree, text):
    kept = CARRY.get(text)
    if kept is None:
        return None
    nodes = list(ast.walk(tree))
    if [type(n).__name__ for n in nodes] != kept[0]:
        return None
    for n, line in zip(nodes, kept[1]):
        if line is not None and hasattr(n, 'lineno'):
            n._ail_line = line
    return [nodes[i] for i in kept[2]]


def tag(tree, text):
    """pyfunc._to_c_once, right after `ast.parse(text)` and before any rewrite: tag the marked statements
    (`_ail_gpu`) and, when `text` came from pyc's unparse, the user's line numbers (`_ail_line`).  Later passes rewrite
    the tree in place and keep the statement nodes, so `prepare` finds them by the tag."""
    if not enabled():
        return
    marks = marker_lines(text)
    if marks:
        found = [s for s in _target_of(marks, text.splitlines(), _statements(tree)).values() if s is not None]
    else:
        found = _carried(tree, text) or []
    for s in found:
        s._ail_gpu = True


def analyze(tree, text, targets=None):
    """Find the marked statements of `tree`, prove the syntactic half of eligibility for each (refusing by name), and
    return the list of sites.  `tree` is not modified (apart from `_ail_line` tags).  `targets`: the marked statements,
    when the text no longer has its comments."""
    funcs = _funcs_of(tree)
    if targets is None:
        marks = marker_lines(text)
        if not marks:
            return []
        by_line = _target_of(marks, text.splitlines(), _statements(tree))
    else:
        by_line = {line_of(t): t for t in targets}
    sites, seen = [], set()
    marked_nodes = [s for s in by_line.values() if s is not None]
    for outer in marked_nodes:                     # a marked loop cannot contain another marked loop
        inside = {id(n) for n in ast.walk(outer)} - {id(outer)}
        for inner in marked_nodes:
            if id(inner) in inside:
                raise refuse(inner, 'a GPU loop inside another GPU loop',
                             'mark only the outer loop; an inner `for j in range(K)` is part of its kernel')
    for line in sorted(by_line):
        stmt = by_line[line]
        if stmt is None:
            err = GpuRefusal("GPU loop: '# ail: gpu' is not followed by a statement; write instead: put the comment on "
                             'the line before a for loop')
            err.source_line = line
            raise err
        if id(stmt) in seen:
            continue
        seen.add(id(stmt))
        site = _classify(stmt, funcs)
        site['marker_line'] = line
        Builder(site, funcs, None).build_for() if site['kind'] == 'for' else Builder(site, funcs, None).build_comp()
        sites.append(site)
    private = {id(s['node']): _stored_names(s['node'].body) | {s['var']} for s in sites if s['kind'] == 'for'}
    if private:
        for fn in ast.walk(tree):
            if isinstance(fn, ast.FunctionDef) and any(id(n) in private for n in ast.walk(fn)):
                _flow(fn.body, set(), private)
    return sites


def check_source(source):
    """pyc.build, before either path: the syntactic half of the proof on the program text, so that a refusal does not
    depend on which path would have built the program.  Also remembers the marked lines for the end-of-build note."""
    MARKED.clear()
    APPLIED.clear()
    if not enabled() or 'ail' not in source:
        return
    text = source.strip()
    marks = marker_lines(text)
    if not marks:
        return
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return
    for site in analyze(tree, text):
        MARKED[site['marker_line']] = line_of(site['node'])


IGNORED = ("'# ail: gpu' ignored: the loop is not on the typed path (the general path never offloads), so it runs on "
           'the CPU')


def sites_of(text):
    """The statement lines of the marked loops in the program text the user wrote (raises GpuRefusal): ail_chatgpt runs
    this on the file itself, because the surface layer may lower a marked statement away before pyc sees it."""
    text = text.strip()
    marks = marker_lines(text)
    if not marks:
        return []
    return sorted(line_of(site['node']) for site in analyze(ast.parse(text), text))


def applied_line():
    """pyc's report to ail_chatgpt: the lines of the loops a kernel was built for."""
    return 'ail-gpu-applied: ' + ' '.join(str(line) for line in sorted(APPLIED))


def prepare(tree, text):
    """pyfunc._to_c_once: attach the sites to the tree (tags and bound temporaries).  A no-op without the switch."""
    global _FUNCS
    _NEXT[0] = 0
    APPLIED.clear()
    if not enabled():
        return 0
    tagged = [n for n in ast.walk(tree) if isinstance(n, ast.stmt) and getattr(n, '_ail_gpu', False)]
    if not tagged:
        return 0
    sites = analyze(tree, text, tagged)
    _FUNCS = _funcs_of(tree)
    if not sites:
        return 0
    by_node = {id(s['node']): s for s in sites}
    for s in sites:
        s['k'] = _NEXT[0]
        _NEXT[0] += 1
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    for n in tree.body:
        if isinstance(n, ast.ClassDef) and any(id(m) in by_node for m in ast.walk(n)):
            raise refuse(n, 'not available in struct methods yet', 'move the loop into a top-level function')
    for fn in funcs:
        if any(id(m) in by_node for m in ast.walk(fn)):
            fn.body = _transform(fn.body, by_node)
    return len(sites)


def _bound_assign(name, value, at):
    stmt = ast.Assign(targets=[ast.Name(id=name, ctx=ast.Store())], value=value)
    ast.copy_location(stmt, at)
    ast.fix_missing_locations(stmt)
    return stmt


def _transform(stmts, by_node):
    out = []
    for s in stmts:
        site = by_node.get(id(s))
        if site is not None:
            out.extend(_attach(s, site))
            continue
        for field in ('body', 'orelse', 'finalbody'):
            if isinstance(getattr(s, field, None), list):
                setattr(s, field, _transform(getattr(s, field), by_node))
        if isinstance(s, ast.Try):
            for h in s.handlers:
                h.body = _transform(h.body, by_node)
        out.append(s)
    return out


def _attach(stmt, site):
    k = site['k']
    pre = []
    it = stmt.iter if site['kind'] == 'for' else stmt.value.generators[0].iter
    if site['kind'] == 'comp' and site['source'] == 'list':
        stmt.value.gpu = site
        site['bounds'] = None
        return [stmt]
    lo, hi = (it.args[0], it.args[1]) if len(it.args) == 2 else (ast.Constant(value=0), it.args[0])
    lo_name, hi_name = '_gpu_lo%d' % k, '_gpu_hi%d' % k
    pre = [_bound_assign(lo_name, lo, stmt), _bound_assign(hi_name, hi, stmt)]
    it.args = [ast.Name(id=lo_name, ctx=ast.Load()), ast.Name(id=hi_name, ctx=ast.Load())]
    ast.copy_location(it.args[0], it)
    ast.copy_location(it.args[1], it)
    site['bounds'] = (lo_name, hi_name)
    if site['kind'] == 'for':
        stmt.gpu = dict(site, private=_stored_names(stmt.body) | {site['var']})
    else:
        stmt.value.gpu = site
    return pre + [stmt]


# reads after the loop: a private local has no value there (GPU path does not run the body in the CPU's variables)
def _flow(stmts, poisoned, private):
    for s in stmts:
        poisoned = _flow_stmt(s, poisoned, private)
    return poisoned


def _loads(node, poisoned):
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id in poisoned:
            raise refuse(n, '%r is assigned inside a GPU loop, so it is private to each iteration and has no value '
                            'after the loop' % n.id,
                         'store what you need in a list element (out[i]) and read that after the loop, or drop the '
                         'marker')


def _flow_stmt(s, poisoned, private):
    if isinstance(s, ast.For) and id(s) in private:
        _loads(s.iter, poisoned)
        return poisoned | private[id(s)]
    if isinstance(s, (ast.Assign, ast.AnnAssign)):
        if s.value is not None:
            _loads(s.value, poisoned)
        targets = s.targets if isinstance(s, ast.Assign) else [s.target]
        cleared = set()
        for t in targets:
            if isinstance(t, ast.Name):
                cleared.add(t.id)
            else:
                _loads(t, poisoned)
        return poisoned - cleared
    if isinstance(s, ast.If):
        _loads(s.test, poisoned)
        return _flow(s.body, set(poisoned), private) | _flow(s.orelse, set(poisoned), private)
    if isinstance(s, (ast.While, ast.For)):
        head = s.test if isinstance(s, ast.While) else s.iter
        _loads(head, poisoned)
        target = set() if isinstance(s, ast.While) else {n.id for n in ast.walk(s.target) if isinstance(n, ast.Name)}
        first = _flow(s.body, poisoned - target, private)
        again = (poisoned | first) - target
        _loads(head, again)
        second = _flow(s.body, again, private)
        return _flow(s.orelse, poisoned | first | second, private)
    if isinstance(s, ast.Try):
        after = _flow(s.body, set(poisoned), private)
        for h in s.handlers:
            after = after | _flow(h.body, poisoned | after, private)
        after = after | _flow(s.orelse, set(after), private)
        return after | _flow(s.finalbody, poisoned | after, private)
    if isinstance(s, (ast.FunctionDef, ast.ClassDef)):
        return poisoned
    _loads(s, poisoned)
    return poisoned


# ---------------------------------------------------------------------------------------------------------------------
# pyfunc hooks (the legacy emitter compiles the loop as it always did, between two markers)
# ---------------------------------------------------------------------------------------------------------------------
BEGIN, END = '/*@gpu:begin:%d*/', '/*@gpu:end:%d*/'


def region(ctx, site, text, **facts):
    """Wrap the finished C of a marked statement in markers; `outline` finds them when the function is complete."""
    if ctx.exc_frame:
        raise refuse(site['node'], 'the function has try/except', 'move the loop into a function without try')
    if ctx.par_depth:
        raise refuse(site['node'], 'a GPU loop inside a parallel for')
    ctx.gpu_regions[site['k']] = dict(site=site, line=site['node'].lineno, **facts)
    return '%s\n%s\n%s' % (BEGIN % site['k'], text.rstrip('\n'), END % site['k'])


_REGION = re.compile(r'/\*@gpu:begin:(\d+)\*/\n(.*?)\n/\*@gpu:end:\1\*/', re.S)


def _kind_of(ctype):
    """('list', 'f'|'i', accessor) / ('scalar', 'f'|'i') of a C declaration type, else None."""
    ctype = re.sub(r'\s+', ' ', ctype or '').strip()
    return {'ail_flist': ('list', 'f'), 'ail_list': ('list', 'i'), 'int64_t': ('scalar', 'i'),
            'double': ('scalar', 'f'), 'const double *': ('view', 'f'), 'double *': ('view', 'f'),
            'const int64_t *': ('view', 'i'), 'int64_t *': ('view', 'i'),
            'ail_flist *': ('listp', 'f'), 'ail_list *': ('listp', 'i')}.get(ctype)


def outline(generated, sig, decls, ctx, cname, par_decls):
    """Run last on the finished C of a function with marked loops: prove the typed half, build the kernels, and replace
    each region by `kernel launch or the original loop`."""
    local, params = par_decls(decls, sig)
    kernels = []
    funcs = _FUNCS

    def lift(match):
        k, text = int(match[1]), match[2]
        facts = ctx.gpu_regions.get(k)
        if facts is None:
            raise Unsupported('GPU loop: internal error, region %d was not recorded' % k)
        site = facts['site']
        where = site['node']

        decl = _decl_of(ctx, local, params)

        def oracle(what, name, node):
            ctype, c = decl(name)
            kind = _kind_of(ctype)
            if what == 'list':
                if kind is None or kind[0] not in ('list', 'view', 'listp'):
                    raise refuse(node, '%r is not a list[float] or list[int] the typed path keeps contiguously '
                                       '(its C type is %s)' % (name, ctype or 'not a local'),
                                 'use list[float] / list[int] data, or drop the marker')
                return kind[1]
            if kind is not None and kind[0] == 'scalar':
                return kind[1]
            if ctype is None and name in getattr(ctx, 'modconsts', {}):
                ck, value = ctx.modconsts[name]
                if ck in ('int', 'float') and isinstance(value, (int, float)) and not isinstance(value, bool):
                    return ('const', 'i' if ck == 'int' else 'f', value)
            raise refuse(node, '%r is not an int64 or float64 value the typed path keeps in a C scalar (its C type is '
                               '%s)' % (name, ctype or 'unknown'),
                         'use an int or float local, or drop the marker')

        builder = Builder(site, funcs, oracle)
        kernel = builder.build_for() if site['kind'] == 'for' else builder.build_comp()
        return _glue(k, kernel, facts, text, decl, kernels, where)

    generated = _REGION.sub(lift, generated)
    marker = '%s {\n' % sig
    at = generated.index(marker)
    APPLIED.update(line_of(r['site']['node']) for r in ctx.gpu_regions.values())
    return generated[:at] + RUNTIME + ''.join(kernels) + generated[at:]


def _decl_of(ctx, local, params):
    """name -> (C type, C name) of a Python name the function can see: a local, a parameter, a module-level list
    constant (`static const ail_flist v_xs`, pyfunc SEMANTICS section 29); C type None when there is none."""
    consts = getattr(ctx, 'modconsts', None) or {}

    def decl(name):
        c = 'v_' + name
        if c in local:
            return local[c][0], c
        if c in params:
            return params[c], c
        if name in consts and consts[name][0] in ('list', 'flist'):
            return ('ail_flist' if consts[name][0] == 'flist' else 'ail_list'), c
        return None, c
    return decl


def _acc(ctype, c):
    """(data pointer, length) C expressions of the list stored as `c` of C type `ctype`."""
    kind = _kind_of(ctype)
    if kind[0] == 'list':
        return '%s.p' % c, '%s.n' % c
    if kind[0] == 'listp':
        return '%s->p' % c, '%s->n' % c
    return c, '%s_len' % c


def _glue(k, kernel, facts, text, decl, kernels, where):
    site = kernel.site
    name = 'ail_gk%d' % k

    def cdecl(py):
        ctype, c = decl(py)
        if ctype is None:
            raise refuse(where, 'cannot find the C declaration of %r' % py)
        return c, ctype

    # the kernel function
    kernels.append(emit_c(kernel, name))
    args, setup = [], []
    for lst in kernel.lists:
        c, ct = cdecl(lst)
        p, n = _acc(ct, c)
        args += ['(%s)%s' % ('const double *' if kernel.lists[lst] == 'f' else 'const int64_t *', p), n]
    for sc, t in kernel.scalars.items():
        c, ct = cdecl(sc)
        args.append(c)
    for sc, (t, value) in kernel.consts.items():
        args.append(_cconst(t, value))
    res_t = kernel.res_type
    ctype = 'double' if res_t == 'f' else 'int64_t'
    if res_t not in ('i', 'f'):
        raise refuse(where, 'the loop produces %s elements; only int and float elements can be stored' % _tname(res_t),
                     'convert to int or float: `1 if cond else 0`, `float(x)`')
    first = ('lo, ' if kernel.loop_var else '')
    if site['kind'] == 'for':
        lo_name, hi_name = site['bounds']
        out_c, out_ct = cdecl(site['out'])
        ok = _kind_of(out_ct)
        if ok is None or ok[0] not in ('list',) or ok[1] != res_t:
            raise refuse(where, 'the output %r is not a list[%s] (C type %s)' % (site['out'], _tname(res_t), out_ct),
                         'size the output before the loop: `out = [%s] * n`' % ('0.0' if res_t == 'f' else '0'))
        if site['out'] in kernel.reads:
            raise refuse(where, 'the output list %r is also read in the body' % site['out'])
        lines = ['{ /* gpu loop k%d: %s (CPU emulation, GPU.md G1) */' % (k, name),
                 '    int _gk_ok = 0;',
                 '    int64_t _gk_lo = v_%s, _gk_hi = v_%s;' % (lo_name, hi_name),
                 '    int64_t _gk_n = 0;',
                 '    if (_gk_hi > _gk_lo && __builtin_sub_overflow(_gk_hi, _gk_lo, &_gk_n)) _gk_n = 0;',
                 '    if (_gk_n > 0 && gk_on()) {',
                 '        %s *_gk_res = 0;' % ctype]
        inputs = [(_acc(cdecl(l)[1], cdecl(l)[0]), kernel.lists[l]) for l in kernel.lists]
        out_p, out_n = _acc(out_ct, out_c)
        cond = ['_gk_lo >= 0', '_gk_hi <= %s' % out_n, '_gk_n < (INT64_MAX / 16)']
        cond += ['gk_disjoint((const void *)%s, %s, (const void *)%s, %s, %d)'
                 % (p, n, out_p, out_n, 8) for (p, n), _ in inputs]
        lines.append('        if (%s) _gk_res = (%s *)malloc((size_t)_gk_n * sizeof(%s));' % (' && '.join(cond), ctype, ctype))
        lines.append('        else gk_trace_cpu(%d, "the range does not fit the output list, or it overlaps an input");' % k)
        lines += ['        if (_gk_res) {',
                  '            unsigned _gk_f = %s(%s%s_gk_lo, _gk_n, _gk_res);' % (name, ', '.join(args) + (', ' if args else ''), ''),
                  '            if (_gk_f == 0) {',
                  '                memcpy(%s + _gk_lo, _gk_res, (size_t)_gk_n * sizeof(%s));' % (out_p, ctype),
                  '                _gk_ok = 1; gk_trace_run(%d, _gk_n);' % k,
                  '            } else gk_trace_replay(%d, _gk_f);' % k,
                  '            free(_gk_res);',
                  '        }',
                  '    }',
                  '    if (!_gk_ok) {',
                  text,
                  '    }',
                  '}']
        return '\n'.join(lines)
    # a comprehension: the kernel fills the (empty) destination temporary
    dest = facts['dest']
    dct = decl(dest[2:])[0]
    dk = _kind_of(dct)
    if dk is None or dk[0] != 'list' or dk[1] != res_t:
        raise refuse(where, 'the comprehension builds a %s list but the typed path holds it as %s'
                     % (_tname(res_t), dct), 'use one element type in the comprehension')
    if site['source'] == 'range':
        lo_name, hi_name = site['bounds']
        count = ['int64_t _gk_lo = v_%s, _gk_hi = v_%s, _gk_n = 0;' % (lo_name, hi_name),
                 'if (_gk_hi > _gk_lo && __builtin_sub_overflow(_gk_hi, _gk_lo, &_gk_n)) _gk_n = 0;']
        call_lo = '_gk_lo, '
    else:
        lens = []
        for lst in site['lists']:
            c, ct = cdecl(lst)
            lens.append(_acc(ct, c)[1])
        count = ['int64_t _gk_lo = 0, _gk_n = %s;' % lens[0]]
        for ln in lens[1:]:
            count.append('if (%s < _gk_n) _gk_n = %s;' % (ln, ln))
        call_lo = ''
    lines = ['{ /* gpu loop k%d: %s (CPU emulation, GPU.md G1) */' % (k, name),
             '    int _gk_ok = 0;']
    lines += ['    ' + c for c in count]
    lines += ['    (void)_gk_lo;',
              '    if (_gk_n > 0 && _gk_n < (INT64_MAX / 16) && gk_on()) {',
              '        %s_reserve(&%s, _gk_n);' % ('ail_flist' if res_t == 'f' else 'ail_list', dest),
              '        if (%s.p) {' % dest,
              '            unsigned _gk_f = %s(%s%s_gk_n, %s.p);' % (name, (', '.join(args) + ', ') if args else '',
                                                                 call_lo if kernel.loop_var else '', dest),
              '            if (_gk_f == 0) { %s.n = _gk_n; _gk_ok = 1; gk_trace_run(%d, _gk_n); }' % (dest, k),
              '            else gk_trace_replay(%d, _gk_f);' % k,
              '        }',
              '    }',
              '    if (!_gk_ok) %s' % text,
              '}']
    return '\n'.join(lines)


# ---------------------------------------------------------------------------------------------------------------------
# kernel IR -> C (the emulation)
# ---------------------------------------------------------------------------------------------------------------------
RUNTIME = r'''
#ifndef AIL_GK_RT
#define AIL_GK_RT
/* GPU.md stage G1: the emulation of a kernel on the CPU.  A kernel never raises: it ORs a bit into a flag word, and the
   caller discards the result and runs the original loop when the word is not 0 (CPU replay, GPU.md 3.1). */
#include <math.h>
#include <string.h>
#define GK_INDEX    1u   /* list index out of range                       */
#define GK_ZERODIV  2u   /* int // or % by zero                           */
#define GK_OVERFLOW 4u   /* int64 overflow (also INT64_MIN // -1, -INT64_MIN) */
#define GK_DENORM   8u   /* a float operand or result below 2**-1000      */
#define GK_NAN     16u   /* a NaN operand, or a NaN made from numbers     */
#define GK_RANGE   32u   /* int(float) outside int64; int vs float compare beyond 2**53 */
static inline int64_t gk_add(int64_t a, int64_t b, unsigned *f) { int64_t r; if (__builtin_add_overflow(a, b, &r)) { *f |= GK_OVERFLOW; return 0; } return r; }
static inline int64_t gk_sub(int64_t a, int64_t b, unsigned *f) { int64_t r; if (__builtin_sub_overflow(a, b, &r)) { *f |= GK_OVERFLOW; return 0; } return r; }
static inline int64_t gk_mul(int64_t a, int64_t b, unsigned *f) { int64_t r; if (__builtin_mul_overflow(a, b, &r)) { *f |= GK_OVERFLOW; return 0; } return r; }
static inline int64_t gk_neg(int64_t a, unsigned *f) { if (a == INT64_MIN) { *f |= GK_OVERFLOW; return 0; } return -a; }
static inline int64_t gk_abs(int64_t a, unsigned *f) { if (a == INT64_MIN) { *f |= GK_OVERFLOW; return 0; } return a < 0 ? -a : a; }
static inline int64_t gk_floordiv(int64_t a, int64_t b, unsigned *f) {
    if (b == 0) { *f |= GK_ZERODIV; return 0; }
    if (b == -1) { if (a == INT64_MIN) { *f |= GK_OVERFLOW; return 0; } return -a; }
    int64_t q = a / b; if ((a % b != 0) && ((a < 0) != (b < 0))) q--; return q; }
static inline int64_t gk_mod(int64_t a, int64_t b, unsigned *f) {
    if (b == 0) { *f |= GK_ZERODIV; return 0; }
    if (b == -1) return 0;
    int64_t r = a % b; if (r != 0 && ((r < 0) != (b < 0))) r += b; return r; }
static inline double gk_chk(double r, unsigned *f) {
    if (r != r) { *f |= GK_NAN; return 0.0; }
    double m = fabs(r);
    if (m != 0.0 && m < 0x1p-1000) { *f |= GK_DENORM; return 0.0; }
    return r; }
static inline double gk_fadd(double a, double b, unsigned *f) { return gk_chk(a + b, f); }
static inline double gk_fsub(double a, double b, unsigned *f) { return gk_chk(a - b, f); }
static inline double gk_fmul(double a, double b, unsigned *f) {
    if (a != 0.0 && b != 0.0 && isfinite(a) && isfinite(b)) { int ea, eb; frexp(a, &ea); frexp(b, &eb); if (ea + eb < -1000) { *f |= GK_DENORM; return 0.0; } }
    return gk_chk(a * b, f); }
static inline int64_t gk_f2i(double x, unsigned *f) { if (!(x >= -9223372036854775808.0 && x < 9223372036854775808.0)) { *f |= GK_RANGE; return 0; } return (int64_t)x; }
static inline int64_t gk_floor(double x, unsigned *f) { return gk_f2i(floor(x), f); }
static inline double gk_ffloor(double x, unsigned *f) { if (!isfinite(x)) { *f |= GK_RANGE; return 0.0; } return floor(x); }
static inline int64_t gk_ceil(double x, unsigned *f) { return gk_f2i(ceil(x), f); }
static inline double gk_i2fx(int64_t i, unsigned *f) { if (i > 9007199254740992LL || i < -9007199254740992LL) { *f |= GK_RANGE; return 0.0; } return (double)i; }
static inline double gk_ldf(const double *p, int64_t n, int64_t i, unsigned *f) {
    if (i < 0) i += n;
    if (i < 0 || i >= n) { *f |= GK_INDEX; return 0.0; }
    return gk_chk(p[i], f); }
static inline int64_t gk_ldi(const int64_t *p, int64_t n, int64_t i, unsigned *f) {
    if (i < 0) i += n;
    if (i < 0 || i >= n) { *f |= GK_INDEX; return 0; }
    return p[i]; }
static inline int gk_disjoint(const void *a, int64_t an, const void *b, int64_t bn, int w) {
    uintptr_t x = (uintptr_t)a, y = (uintptr_t)b;
    return an <= 0 || bn <= 0 || x + (uintptr_t)an * (uintptr_t)w <= y || y + (uintptr_t)bn * (uintptr_t)w <= x; }
static inline int gk_on(void) { static int v = -1; if (v < 0) { const char *e = getenv("AIL_GPU"); v = !(e && e[0] == '0' && e[1] == 0); } return v; }
static inline int gk_tracing(void) { static int v = -1; if (v < 0) { const char *e = getenv("AIL_GPU_TRACE"); v = e && e[0] && !(e[0] == '0' && e[1] == 0); } return v; }
static inline void gk_trace_run(int k, int64_t n) { if (gk_tracing()) fprintf(stderr, "gpu: k%d n=%lld device=emulation\n", k, (long long)n); }
static inline void gk_trace_cpu(int k, const char *why) { if (gk_tracing()) fprintf(stderr, "gpu: k%d cpu (%s)\n", k, why); }
static inline void gk_trace_replay(int k, unsigned f) {
    if (!gk_tracing()) return;
    fprintf(stderr, "gpu: k%d replay flags=0x%x (%s%s%s%s%s%s)\n", k, f, f & GK_INDEX ? "index " : "", f & GK_ZERODIV ? "zero-division " : "",
            f & GK_OVERFLOW ? "overflow " : "", f & GK_DENORM ? "denormal " : "", f & GK_NAN ? "nan " : "", f & GK_RANGE ? "range " : ""); }
#endif
'''


def _cconst(t, value):
    if t == 'f':
        v = float(value)
        if v != v:
            return 'NAN'
        if v in (float('inf'), float('-inf')):
            return 'INFINITY' if v > 0 else '(-INFINITY)'
        return v.hex() if v.hex().startswith('-') is False else '(%s)' % v.hex()
    v = int(value)
    return 'INT64_MIN' if v == INT64_MIN else ('(%dLL)' % v if v < 0 else '%dLL' % v)


class _Emit:
    def __init__(self, kernel):
        self.k = kernel
        self.n = 0

    def tmp(self):
        self.n += 1
        return '_t%d' % self.n

    def ct(self, t):
        return 'double' if t == 'f' else 'int64_t'

    def ex(self, e):
        op, t = e[0], e[1]
        if op == 'c':
            if t == 'f':
                c = _cconst('f', e[2])
                if e[2] != 0 and abs(e[2]) < 2.0 ** -1000:
                    return 'gk_chk(%s, &_f)' % c
                return c
            return _cconst('i', e[2])
        if op == 'v':
            return e[2]
        if op == 'ld':
            return 'gk_ld%s(p_%s, n_%s, %s, &_f)' % (t, e[2], e[2], self.ex(e[3]))
        if op == 'len':
            return 'n_%s' % e[2]
        if op == 'neg':
            return '(-(%s))' % self.ex(e[2]) if t == 'f' else 'gk_neg(%s, &_f)' % self.ex(e[2])
        if op == 'pos':
            return self.ex(e[2])
        if op == 'abs':
            return 'fabs(%s)' % self.ex(e[2]) if t == 'f' else 'gk_abs(%s, &_f)' % self.ex(e[2])
        if op == 'bin':
            a, b = self.ex(e[3]), self.ex(e[4])
            name = {'add': 'add', 'sub': 'sub', 'mul': 'mul', 'floordiv': 'floordiv', 'mod': 'mod'}[e[2]]
            return 'gk_%s%s(%s, %s, &_f)' % ('f' if t == 'f' else '', name, a, b)
        if op == 'cmp':
            a, b, mode = self.ex(e[3]), self.ex(e[4]), e[5]
            if mode == 'if':
                if e[3][1] != 'f':
                    a = 'gk_i2fx(%s, &_f)' % a
                if e[4][1] != 'f':
                    b = 'gk_i2fx(%s, &_f)' % b
            return '((int64_t)(%s %s %s))' % (a, e[2], b)
        if op == 'truth':
            return '((int64_t)(%s != %s))' % (self.ex(e[3]), '0.0' if e[2] == 'f' else '0')
        if op == 'not':
            return '((int64_t)!(%s))' % self.ex(e[2])
        if op in ('and', 'or'):
            return '((int64_t)((%s) %s (%s)))' % (self.ex(e[2]), '&&' if op == 'and' else '||', self.ex(e[3]))
        if op in ('vand', 'vor'):
            tmp = self.tmp()
            test = '%s != %s' % (tmp, '0.0' if t == 'f' else '0')
            a, b = self.ex(e[2]), self.ex(e[3])
            if op == 'vand':
                return '({ %s %s = %s; (%s) ? (%s) : %s; })' % (self.ct(t), tmp, a, test, b, tmp)
            return '({ %s %s = %s; (%s) ? %s : (%s); })' % (self.ct(t), tmp, a, test, tmp, b)
        if op == 'sel':
            return '((%s) ? (%s) : (%s))' % (self.ex(e[2]), self.ex(e[3]), self.ex(e[4]))
        if op == 'cvt':
            kind, a = e[2], self.ex(e[3])
            if kind == 'i2f':
                return '((double)(%s))' % a
            if kind == 'ffloor':
                return 'gk_ffloor(%s, &_f)' % a
            if kind == 'b2i':
                return a
            return 'gk_%s(%s, &_f)' % ({'trunc': 'f2i', 'floor': 'floor', 'ceil': 'ceil'}[kind], a)
        if op == 'mm':
            args = e[3]
            tmps = [self.tmp() for _ in args]
            decl = ' '.join('%s %s = %s;' % (self.ct(t), tm, self.ex(a)) for tm, a in zip(tmps, args))
            body = tmps[0]
            for tm in tmps[1:]:
                body = '((%s %s %s) ? %s : %s)' % (tm, '>' if e[2] == 'max' else '<', body, tm, body)
            return '({ %s %s; })' % (decl, body)
        if op == 'blk':
            return '({ %s %s; })' % (self.stmts(e[2], 0, inline=True), self.ex(e[3]))
        raise AssertionError(op)

    def stmts(self, stmts, depth, inline=False):
        pad = '    ' * (depth + 2)
        out = []
        for s in stmts:
            if s[0] == 'set':
                out.append('%s%s = %s;%s' % (pad, s[1], self.ex(s[3]), ' if (_f) return _f;'))
            elif s[0] == 'if':
                out.append('%sif (%s) {' % (pad, self.cond(s[1])))
                out.append(self.stmts(s[2], depth + 1))
                if s[3]:
                    out.append('%s} else {' % pad)
                    out.append(self.stmts(s[3], depth + 1))
                out.append('%s}' % pad)
            else:
                _, var, lo, hi, body = s
                a, b = self.tmp(), self.tmp()
                out.append('%s{ int64_t %s = %s, %s = %s; if (_f) return _f;' % (pad, a, self.ex(lo), b, self.ex(hi)))
                out.append('%s  for (%s = %s; %s < %s; %s++) {' % (pad, var, a, var, b, var))
                out.append(self.stmts(body, depth + 2))
                out.append('%s  } }' % pad)
        return '\n'.join(out) if not inline else ' '.join(x.strip() for x in out)

    def cond(self, e):
        return '(%s) && !_f' % self.ex(e) if False else self.ex(e)


def emit_c(kernel, name):
    """The C text of the emulation function of `kernel` (and the shared runtime block, once per translation unit)."""
    em = _Emit(kernel)
    params = []
    for lst, t in kernel.lists.items():
        params += ['const %s *p_%s' % ('double' if t == 'f' else 'int64_t', lst), 'int64_t n_%s' % lst]
    for sc, t in kernel.scalars.items():
        params.append('%s s_%s' % (em.ct(t), sc))
    for sc, (t, value) in kernel.consts.items():
        params.append('%s s_%s' % (em.ct(t), sc))
    if kernel.loop_var:
        params.append('int64_t _lo')
    params += ['int64_t _cnt', '%s *_res' % em.ct(kernel.res_type)]
    lines = ['static unsigned %s(%s) {' % (name, ', '.join(params)), '    unsigned _f = 0;']
    for sc, t in kernel.scalars.items():
        if t == 'f':
            lines.append('    s_%s = gk_chk(s_%s, &_f); if (_f) return _f;' % (sc, sc))
    for sc, (t, value) in kernel.consts.items():
        if t == 'f':
            lines.append('    s_%s = gk_chk(s_%s, &_f); if (_f) return _f;' % (sc, sc))
    for cname, t in sorted(kernel.locals.items()):
        lines.append('    %s %s = %s;' % (em.ct(t), cname, '0.0' if t == 'f' else '0'))
    lines.append('    for (int64_t _k = 0; _k < _cnt; _k++) {')
    if kernel.loop_var:
        lines.append('        %s = _lo + _k;' % kernel.loop_var[0])
    for cname, t, lst in kernel.elems:
        lines.append('        %s = %s;' % (cname, 'gk_chk(p_%s[_k], &_f)' % lst if t == 'f' else 'p_%s[_k]' % lst))
    if kernel.elems:
        lines.append('        if (_f) return _f;')
    body = em.stmts(kernel.body, 0)
    if body:
        lines.append(body)
    lines.append('        _res[_k] = %s;' % em.ex(kernel.result))
    lines.append('        if (_f) return _f;')
    lines.append('    }')
    lines.append('    return _f;')
    lines.append('}')
    return '\n'.join(lines) + '\n'
