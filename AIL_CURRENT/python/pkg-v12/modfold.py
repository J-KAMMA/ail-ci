"""Module-level constants built from pure builtins, evaluated once at compile time (pyreach11).

AI-written Python builds its read-only tables at module level with a call or a short loop:

    STOP_WORDS = frozenset(b"an and are ...".split())          STOP = set(w.encode() for w in "...".split())
    LOWER = bytes.maketrans(bytes(range(65, 91)), bytes(range(97, 123)))
    DIGIT_VALUE = {}
    for _c in "0123456789":
        DIGIT_VALUE[_c] = len(DIGIT_VALUE)

The typed path accepts a module constant only when it is a literal (pyfunc `_scan_module_consts`,
modtables.py), so each of these sent the whole program to the general path. This pass runs such an
initializer once, here, with CPython itself -- the compiler is a CPython program, and these builtins
are the very ones the program would run -- and writes the value back as the literal it equals:

    LOWER = b'\\x00\\x01...'               DIGIT_VALUE = {'0': 0, '1': 1, ...}

The literal replaces the same lines (padded with blank lines, so every later line number is
unchanged), so the name is still bound at the same point of the module and the existing literal
rules decide the rest: what a function may do with the table, and every refusal by name.

It runs on the typed path only (`pyc.to_c`): when the typed path still refuses, the general path
builds the program from the source as written, so this pass can never change a general-path build.

Folded only when nothing can tell the difference:
- the statements use nothing but literals, already-known immutable module constants, the names
  they bind themselves, and a fixed set of pure builtins and methods (no user function, no import,
  no attribute that starts with `_`, no lambda, no `while`); a builtin the module rebinds is not one;
- the module never reaches its names dynamically (`globals`, `vars`, `eval`, `exec`, `__dict__`);
- the name is bound once at module level and no function declares it `global`;
- a loop variable the fill loop binds is read nowhere else (CPython leaves it bound at module level);
- the value is plain data (str, bytes, int, finite float, bool, None, tuple, list, dict, set,
  frozenset) with no mutable object reachable twice (a literal would split shared rows);
- a mutable value (list, dict, set) is only read after its run: never changed, passed on, stored,
  returned or rebound, so a literal and the built object can never be told apart. A program that
  changes it keeps its old route (the literal rules or the general path), never a new one;
- a set is only read in ways whose answer does not depend on its iteration order (`in`, `len`,
  `sorted`, `min`, `max`), because the literal is written in sorted order;
- evaluation finishes within a step and size budget and does not raise (a program whose
  initializer raises keeps CPython's error by not being folded).
Anything else leaves the source exactly as it was.
"""
import ast
import math
import os
import sys

STEP_BUDGET = 2_000_000          # trace events while evaluating one run
MAX_ITEMS = 20_000               # elements in one folded value
MAX_TEXT = 400_000               # characters of one folded literal
MAX_SEQ = 1_000_000              # length of a range / repeated sequence / sized bytes() while evaluating

_DYNAMIC = frozenset(('globals', 'vars', 'eval', 'exec', 'locals', '__import__', 'compile', 'getattr',
                      'setattr', 'delattr', '__dict__', 'dir'))

STR_METHODS = frozenset(('split', 'rsplit', 'splitlines', 'strip', 'lstrip', 'rstrip', 'lower', 'upper',
                         'casefold', 'title', 'capitalize', 'swapcase', 'replace', 'encode', 'decode', 'join',
                         'startswith', 'endswith', 'find', 'rfind', 'index', 'rindex', 'count', 'isdigit',
                         'isalpha', 'isalnum', 'isspace', 'isupper', 'islower', 'isdecimal', 'isnumeric',
                         'isascii', 'maketrans', 'translate', 'partition', 'rpartition', 'removeprefix',
                         'removesuffix', 'fromhex', 'hex', 'fromkeys'))
CONTAINER_METHODS = frozenset(('add', 'append', 'extend', 'update', 'setdefault', 'insert', 'get', 'keys',
                               'values', 'items', 'copy', 'union', 'intersection', 'difference',
                               'symmetric_difference', 'discard', 'remove', 'pop', 'sort', 'reverse',
                               'issubset', 'issuperset', 'isdisjoint'))
METHODS = STR_METHODS | CONTAINER_METHODS

# a read of a folded mutable table that hands back a new value, never the table itself
_READ_METHODS = frozenset(('get', 'items', 'keys', 'values', 'count', 'index', 'copy'))
_READ_FUNCS = frozenset(('len', 'sorted', 'list', 'tuple', 'set', 'frozenset', 'dict', 'min', 'max', 'sum',
                         'any', 'all', 'enumerate', 'reversed', 'zip', 'str', 'repr', 'print'))
_SET_READ_FUNCS = frozenset(('len', 'sorted', 'min', 'max'))
_SET_READ_METHODS = frozenset(('issubset', 'issuperset', 'isdisjoint'))

_EXPR_NODES = (ast.Constant, ast.Name, ast.Attribute, ast.Call, ast.keyword, ast.Subscript, ast.Slice,
               ast.Tuple, ast.List, ast.Set, ast.Dict, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare,
               ast.IfExp, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.comprehension,
               ast.Starred, ast.JoinedStr, ast.FormattedValue,
               ast.expr_context, ast.operator, ast.unaryop, ast.boolop, ast.cmpop)
_STMT_NODES = (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.For, ast.If, ast.Expr, ast.Pass)


class _Stop(Exception):
    pass


def _guard_len(n):
    if n > MAX_SEQ:
        raise _Stop('too large')


def _range(*args):
    r = range(*args)
    _guard_len(len(r))
    return r


class _BytesType:
    """`bytes` for the evaluator: the same type, but a sized `bytes(n)` is bounded."""
    maketrans = staticmethod(bytes.maketrans)
    fromhex = staticmethod(bytes.fromhex)

    def __call__(self, *args, **kwargs):
        if args and isinstance(args[0], int) and not isinstance(args[0], bool):
            _guard_len(args[0])
        return bytes(*args, **kwargs)


class _BytearrayType(_BytesType):
    def __call__(self, *args, **kwargs):
        if args and isinstance(args[0], int) and not isinstance(args[0], bool):
            _guard_len(args[0])
        return bytearray(*args, **kwargs)


def _seq_len(v):
    return len(v) if isinstance(v, (str, bytes, bytearray, list, tuple)) else None


def _mul(a, b):
    for seq, count in ((a, b), (b, a)):
        n = _seq_len(seq)
        if n is not None and isinstance(count, int):
            _guard_len(n * max(count, 0))
    if isinstance(a, int) and isinstance(b, int) and a.bit_length() + b.bit_length() > 65536:
        raise _Stop('too large')
    return a * b


def _pow(a, b):
    if isinstance(a, int) and isinstance(b, int) and b > 0 and a.bit_length() * b > 65536:
        raise _Stop('too large')
    return a ** b


def _lshift(a, b):
    if isinstance(b, int) and b > 65536:
        raise _Stop('too large')
    return a << b


_BUILTINS = {
    'set': set, 'frozenset': frozenset, 'dict': dict, 'list': list, 'tuple': tuple, 'str': str,
    'bytes': _BytesType(), 'bytearray': _BytearrayType(), 'int': int, 'float': float, 'bool': bool,
    'len': len, 'range': _range, 'sorted': sorted, 'reversed': reversed, 'enumerate': enumerate,
    'zip': zip, 'min': min, 'max': max, 'sum': sum, 'abs': abs, 'ord': ord, 'chr': chr, 'any': any,
    'all': all, 'divmod': divmod, 'map': map, 'filter': filter, 'repr': repr, 'hex': hex, 'oct': oct,
    'bin': bin, 'True': True, 'False': False, 'None': None,
}
_HELPERS = {'_ail_fold_mul': _mul, '_ail_fold_pow': _pow, '_ail_fold_lshift': _lshift}


# ---------------------------------------------------------------- scopes

def _target_names(t):
    return {n.id for n in ast.walk(t) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}


def _module_bindings(tree):
    """{name: number of module-level binding statements}, and the names any function makes `global`."""
    counts = {}
    globals_ = set()

    def add(name):
        counts[name] = counts.get(name, 0) + 1

    def walk_module(stmts):
        for s in stmts:
            if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                add(s.name)
                for n in ast.walk(s):
                    if isinstance(n, (ast.Global, ast.Nonlocal)):
                        globals_.update(n.names)
                continue
            if isinstance(s, (ast.Import, ast.ImportFrom)):
                for a in s.names:
                    add((a.asname or a.name).split('.')[0])
                continue
            for n in ast.walk(s):
                if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
                    add(n.id)
                elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    add(n.name)
                elif isinstance(n, (ast.Global, ast.Nonlocal)):
                    globals_.update(n.names)
                elif isinstance(n, ast.alias):
                    add((n.asname or n.name).split('.')[0])
    walk_module(tree.body)
    return counts, globals_


def _locals_of(fn):
    """Names local to a function or lambda (its parameters and what it binds), minus `global` ones."""
    a = fn.args
    names = {x.arg for x in a.posonlyargs + a.args + a.kwonlyargs}
    if a.vararg:
        names.add(a.vararg.arg)
    if a.kwarg:
        names.add(a.kwarg.arg)
    declared = set()
    body = fn.body if isinstance(fn.body, list) else [fn.body]
    stack = list(body)
    while stack:
        n = stack.pop()
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(n.name)
            continue                     # its own body is its own scope
        if isinstance(n, ast.Lambda):
            continue
        if isinstance(n, (ast.Global, ast.Nonlocal)):
            declared.update(n.names)
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            names.add(n.id)
        if isinstance(n, ast.alias):
            names.add((n.asname or n.name).split('.')[0])
        if isinstance(n, ast.ExceptHandler) and n.name:
            names.add(n.name)
        stack.extend(ast.iter_child_nodes(n))
    return names - declared


def _global_uses(tree, name):
    """Every `ast.Name` node of `name` that resolves to the module binding, with its parent chain.
    Comprehension variables and function locals that shadow it are skipped."""
    out = []

    def visit(node, shadowed, chain):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            if not isinstance(node, ast.Lambda):
                for d in node.decorator_list:
                    visit(d, shadowed, chain + [node])
                if node.returns:
                    visit(node.returns, shadowed, chain + [node])
            for d in node.args.defaults + [d for d in node.args.kw_defaults if d is not None]:
                visit(d, shadowed, chain + [node])
            inner = shadowed or name in _locals_of(node)
            body = node.body if isinstance(node.body, list) else [node.body]
            for s in body:
                visit(s, inner, chain + [node])
            return
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            bound = set()
            for g in node.generators:
                bound |= _target_names(g.target)
            inner = shadowed or name in bound
            for i, g in enumerate(node.generators):
                visit(g.iter, shadowed if i == 0 else inner, chain + [node, g])
                for c in g.ifs:
                    visit(c, inner, chain + [node, g])
            for part in ([node.key, node.value] if isinstance(node, ast.DictComp) else [node.elt]):
                visit(part, inner, chain + [node])
            return
        if isinstance(node, ast.Name) and node.id == name and not shadowed:
            out.append((node, chain))
        for child in ast.iter_child_nodes(node):
            visit(child, shadowed, chain + [node])

    for s in tree.body:
        visit(s, False, [tree])
    return out


# ---------------------------------------------------------------- the runs

def _check_nodes(stmts):
    """Every node is one this evaluator gives a meaning to; returns the names the statements load."""
    loads = set()
    for s in stmts:
        for n in ast.walk(s):
            if isinstance(n, ast.stmt):
                if not isinstance(n, _STMT_NODES):
                    raise _Stop('statement')
                if isinstance(n, ast.For) and (n.orelse or getattr(n, 'type_comment', None)):
                    raise _Stop('for-else')
                continue
            if not isinstance(n, _EXPR_NODES):
                raise _Stop('node')
            if isinstance(n, ast.Attribute):
                if n.attr.startswith('_') or n.attr not in METHODS:
                    raise _Stop('attribute')
            elif isinstance(n, ast.Name):
                if n.id.startswith('__') or n.id in _DYNAMIC:
                    raise _Stop('name')
                if isinstance(n.ctx, ast.Load):
                    loads.add(n.id)
            elif isinstance(n, ast.FormattedValue) and n.conversion not in (-1, 115, 114, 97):
                raise _Stop('format')
    return loads


class _GuardOps(ast.NodeTransformer):
    """`a * b`, `a ** b` and `a << b` become bounded helper calls while evaluating."""
    OPS = {ast.Mult: '_ail_fold_mul', ast.Pow: '_ail_fold_pow', ast.LShift: '_ail_fold_lshift'}

    def visit_BinOp(self, node):
        self.generic_visit(node)
        helper = self.OPS.get(type(node.op))
        if helper is None:
            return node
        return ast.copy_location(ast.Call(func=ast.Name(id=helper, ctx=ast.Load()),
                                          args=[node.left, node.right], keywords=[]), node)

    def visit_AugAssign(self, node):
        self.generic_visit(node)
        helper = self.OPS.get(type(node.op))
        if helper is None:
            return node
        load = ast.parse(ast.unparse(node.target), mode='eval').body
        return ast.copy_location(ast.Assign(targets=[node.target], value=ast.Call(
            func=ast.Name(id=helper, ctx=ast.Load()), args=[load, node.value], keywords=[])), node)


def _evaluate(stmts, env):
    module = ast.Module(body=[_GuardOps().visit(ast.parse(ast.unparse(s)).body[0]) for s in stmts],
                        type_ignores=[])
    ast.fix_missing_locations(module)
    code = compile(module, '<ail-fold>', 'exec')
    scope = dict(env)
    scope.update(_HELPERS)
    scope['__builtins__'] = dict(_BUILTINS)
    steps = [0]

    def tracer(frame, event, arg):
        if frame.f_code.co_filename != '<ail-fold>':
            return None
        steps[0] += 1
        if steps[0] > STEP_BUDGET:
            raise _Stop('budget')
        return tracer

    old = sys.gettrace()
    sys.settrace(tracer)
    try:
        exec(code, scope)
    finally:
        sys.settrace(old)
    return scope


def _immutable(v):
    if v is None or isinstance(v, (bool, int, str, bytes)):
        return True
    if isinstance(v, float):
        return math.isfinite(v)
    if isinstance(v, (tuple, frozenset)):
        return all(_immutable(x) for x in v)
    return False


def _sort_key(v):
    return (type(v).__name__, repr(v))


def _literal(v, seen, count):
    """Source text for the plain-data value `v`; raises _Stop for anything a literal cannot be."""
    count[0] += 1
    if count[0] > MAX_ITEMS:
        raise _Stop('too many')
    if v is None or isinstance(v, (bool, str, bytes)):
        return repr(v)
    if isinstance(v, int):
        return repr(v)
    if isinstance(v, float):
        if not math.isfinite(v):
            raise _Stop('float')
        return repr(v)
    if isinstance(v, (list, dict, set)):
        if id(v) in seen:
            raise _Stop('shared')       # a literal would make two objects of one
        seen.add(id(v))
    if isinstance(v, tuple):
        inner = [_literal(x, seen, count) for x in v]
        return '(' + ', '.join(inner) + (',)' if len(inner) == 1 else ')')
    if isinstance(v, list):
        return '[' + ', '.join(_literal(x, seen, count) for x in v) + ']'
    if isinstance(v, dict):
        return '{' + ', '.join('%s: %s' % (_literal(k, seen, count), _literal(x, seen, count))
                               for k, x in v.items()) + '}'
    if isinstance(v, (set, frozenset)):
        items = sorted(v, key=_sort_key)
        body = ', '.join(_literal(x, seen, count) for x in items)
        if isinstance(v, frozenset):
            return 'frozenset({%s})' % body if items else 'frozenset()'
        return '{%s}' % body if items else 'set()'
    raise _Stop('kind')


def _uses_ok(tree, name, value, run_ids):
    """Whether every use of the folded name outside its own run only reads it (see the docstring)."""
    if _immutable(value) and not isinstance(value, frozenset):
        return True
    is_set = isinstance(value, (set, frozenset))
    for node, chain in _global_uses(tree, name):
        if any(id(c) in run_ids for c in chain):
            continue
        if not isinstance(node.ctx, ast.Load):
            return False
        parent = chain[-1]
        if isinstance(parent, ast.Compare) and node is not parent.left \
                and isinstance(parent.ops[[id(c) for c in parent.comparators].index(id(node))], (ast.In, ast.NotIn)):
            continue
        if isinstance(parent, ast.Compare) and node is parent.left and len(parent.ops) == 1 \
                and isinstance(parent.ops[0], (ast.In, ast.NotIn)) and not is_set:
            continue        # `X in Y` reads X; only Y could be changed by it
        if isinstance(parent, ast.Call) and isinstance(parent.func, ast.Name) and node in parent.args \
                and parent.func.id in (_SET_READ_FUNCS if is_set else _READ_FUNCS):
            continue
        if isinstance(parent, ast.Call) and isinstance(parent.func, ast.Attribute) \
                and parent.func.attr == 'translate' and parent.args == [node] and not is_set:
            continue        # `s.translate(TABLE)` reads the table
        if isinstance(parent, ast.Attribute) and parent.value is node and len(chain) >= 2 \
                and isinstance(chain[-2], ast.Call) and chain[-2].func is parent \
                and parent.attr in (_SET_READ_METHODS if is_set else _READ_METHODS):
            continue
        if is_set:
            return False
        if isinstance(parent, ast.Subscript) and parent.value is node and isinstance(parent.ctx, ast.Load):
            continue
        if isinstance(parent, (ast.For, ast.comprehension)) and parent.iter is node:
            continue
        return False
    return True


def _fill_stmt(stmt, name):
    """Whether `stmt` (right after `name`'s binding) only fills `name`; returns the names it binds."""
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)):
        return None
    refs = {n.id for n in ast.walk(stmt) if isinstance(n, ast.Name)}
    if name not in refs:
        return None
    binds = set()
    for n in ast.walk(stmt):
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            binds.add(n.id)
    for n in ast.walk(stmt):
        if isinstance(n, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            for g in n.generators:
                binds -= _target_names(g.target) - _loop_targets(stmt)
    if name in binds:
        return None              # a second binding of the name itself
    if binds - _loop_targets(stmt):
        return None
    return binds


def _loop_targets(stmt):
    out = set()
    for n in ast.walk(stmt):
        if isinstance(n, ast.For):
            out |= _target_names(n.target)
    return out


def _read_outside(tree, var, run_ids):
    return any(not any(id(c) in run_ids for c in chain) for _node, chain in _global_uses(tree, var))


def fold(source):
    """The source with every foldable module-level constant written as its literal value, or the
    source unchanged. Never raises. AIL_MODFOLD=0 turns the pass off (the way back)."""
    if os.environ.get('AIL_MODFOLD') == '0':
        return source
    try:
        return _fold(source)
    except Exception:
        return source


_SAFE_DECORATORS = frozenset(('staticmethod', 'classmethod', 'property'))


def _module_code_may_read(stmts, name, user_defs):
    """Whether the module-level statements before a run may run user code or read `name` (a call
    of a name that is not a builtin, any reference to a module-level def or class, a decorator, a
    direct read): then the name could be seen unbound, and the source is left alone so that
    whichever route handles it today still does."""
    for s in stmts:
        nodes = []
        if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for d in s.decorator_list:
                if not (isinstance(d, ast.Name) and d.id in _SAFE_DECORATORS):
                    return True
            nodes = list(s.args.defaults) + [d for d in s.args.kw_defaults if d is not None]
        elif isinstance(s, ast.ClassDef):
            if s.decorator_list or s.bases or s.keywords:
                nodes = list(s.decorator_list) + list(s.bases) + [k.value for k in s.keywords]
            if any(not (isinstance(d, ast.Name) and d.id in ('dataclass',)) for d in s.decorator_list):
                return True
            if _module_code_may_read(s.body, name, user_defs):
                return True
        elif isinstance(s, (ast.Import, ast.ImportFrom)):
            continue
        else:
            nodes = [s]
        for root in nodes:
            stack = [root]
            while stack:
                n = stack.pop()
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                    continue
                if isinstance(n, ast.Name) and (n.id == name or n.id in user_defs):
                    return True
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
                        and (n.func.id not in _BUILTINS or n.func.id in user_defs):
                    return True
                stack.extend(ast.iter_child_nodes(n))
    return False


def _fold(source):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    if any(isinstance(n, ast.Name) and n.id in _DYNAMIC or isinstance(n, ast.Attribute) and n.attr == '__dict__'
           for n in ast.walk(tree)):
        return source
    counts, globals_ = _module_bindings(tree)
    shadowed = {b for b in _BUILTINS if counts.get(b)}
    consts = {}                          # immutable module constants known so far, by name
    edits = []                           # (first line, last line, text)
    body = tree.body
    i = 0
    while i < len(body):
        stmt = body[i]
        i += 1
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            name, value_node, ann = stmt.targets[0].id, stmt.value, None
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.value is not None \
                and stmt.simple:
            name, value_node, ann = stmt.target.id, stmt.value, stmt.annotation
        else:
            continue
        if counts.get(name) != 1 or name in globals_ or name.startswith('__'):
            continue
        try:
            literal_value = ast.literal_eval(value_node)
        except Exception:
            literal_value = _Stop
        # the run: the binding plus the statements right after it that only fill this name
        run = [stmt]
        loop_vars = set()
        while i < len(body):
            binds = _fill_stmt(body[i], name)
            if binds is None:
                break
            run.append(body[i])
            loop_vars |= binds
            i += 1
        if literal_value is not _Stop and len(run) == 1:
            if _immutable(literal_value):
                consts[name] = literal_value
            continue
        try:
            folded = _try_fold(tree, source, run, name, ann, consts, counts, globals_, shadowed, loop_vars)
        except (_Stop, Exception):
            folded = None
        if folded is None:
            i = body.index(stmt) + 1     # the fill statements are left alone, as written
            continue
        value, text = folded
        if _immutable(value):
            consts[name] = value
        edits.append((run[0].lineno, run[-1].end_lineno, text))
    if not edits:
        return source
    lines = source.splitlines(keepends=True)
    for first, last, text in reversed(edits):
        newline = '\n'
        lines[first - 1:last] = [text + newline] + [newline] * (last - first)
    return ''.join(lines)


def _try_fold(tree, source, run, name, ann, consts, counts, globals_, shadowed, loop_vars):
    first, last = run[0].lineno, run[-1].end_lineno
    if run[0].col_offset != 0:
        return None
    user_defs = {s.name for s in tree.body if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    if _module_code_may_read(tree.body[:tree.body.index(run[0])], name, user_defs):
        return None
    for s in tree.body:
        if any(s is r for r in run):
            continue
        if not (s.end_lineno < first or s.lineno > last):
            return None                      # another statement shares these lines (`;`)
    allowed = set(_BUILTINS) - shadowed
    loads = _check_nodes(run)
    run_ids = {id(s) for s in run}
    bound_here = {name} | loop_vars
    for s in run:
        for n in ast.walk(s):
            if isinstance(n, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                for g in n.generators:
                    bound_here |= _target_names(g.target)
    for load in loads:
        if load in bound_here:
            continue
        if load in consts or load in allowed:
            continue
        return None
    if loads & shadowed:
        return None
    for var in loop_vars:
        if var == name or counts.get(var, 0) == 0 or var in globals_ or _read_outside(tree, var, run_ids):
            return None
    env = {k: v for k, v in consts.items() if k in loads}
    scope = _evaluate(run, env)
    if name not in scope:
        return None
    value = scope[name]
    if isinstance(value, bytearray):
        return None
    if isinstance(value, (list, dict, set, frozenset, tuple)) and not value:
        return None             # an empty table is refused as a literal too: nothing to gain
    text = _literal(value, set(), [0])
    if len(text) > MAX_TEXT:
        return None
    # the literal must read back as the value it was written from (our own text, two names only)
    back = eval(compile(text, '<ail-fold-check>', 'eval'),
                {'__builtins__': {'frozenset': frozenset, 'set': set}})
    if type(back) is not type(value) or back != value:
        return None
    if not _uses_ok(tree, name, value, run_ids):
        return None
    if ann is not None:
        head = '%s: %s = ' % (name, ast.get_source_segment(source, ann) or ast.unparse(ann))
    else:
        head = '%s = ' % name
    return value, head + text
