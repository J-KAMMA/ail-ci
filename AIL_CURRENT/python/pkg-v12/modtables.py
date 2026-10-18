"""Module-level set and dict tables: `STOP = {"a", "the"}`, `TABLE = {"x": 1, "y": 2}`, `PAIRS = {(0, 1), ...}`.

A function cannot read a module-level container on the typed path (the compiler has no global
containers), so this pass lowers one before compilation, on the AST:

    STOP = {"a", "the"}                     # removed from the module
    def is_stop(w): return w in STOP        # def is_stop(STOP: set[str], w): ...
    def main(): ... is_stop(w) ...          # main builds `STOP: set[str] = {...}` once and passes it down

The table is built once, in the entry function (or in whichever function reads it and cannot take
an extra parameter: an exported library function, a method, a function used as a value, the
entry itself, a function the module's own statements call), and handed to every function below
as a hidden first parameter, which the typed path borrows (no copy). A table with bytes in it is
a local of every function that reads it (the typed path has no bytes-keyed parameters), so it is
rebuilt on each call.

The promise is CPython's: a table is shared, one object. So the pass only accepts a table that is
read in place -- `w in STOP`, `STOP[k]`, `STOP.get(k)`, `for w in STOP`, `len(STOP)`,
`sorted(STOP)`, `STOP.items()`. Everything that could change it, or hand out a second reference
to it, is refused by name: `STOP.add(x)`, `STOP[k] = v`, `del STOP[k]`, `STOP |= ...`,
`global STOP`, `xs = STOP`, `return STOP`, `f(STOP)`, `[STOP]`. A set of ints (or of tuples of
ints) is also refused where its iteration order shows (`for x in PRIMES`, `list(PRIMES)`): CPython
walks it in hash order, this compiler in insertion order; `sorted(PRIMES)` is the spelling.

Two entry points. `rewrite` runs inside the typed compiler (pyfunc.py) on tables of str, int and
bytes, where positions in messages are the program's own. `rewrite_text` runs in the front end,
before the tuple lowering (tuplib.py), on tables with tuples in them, and returns source text.
A program with no such table is not touched.
"""
import ast
import copy

MUTATORS = frozenset(('add', 'discard', 'remove', 'pop', 'popitem', 'clear', 'update', 'setdefault',
                      'append', 'extend', 'insert', 'sort', 'reverse', 'difference_update',
                      'intersection_update', 'symmetric_difference_update'))
# methods that read the table and return a new value, never the table itself
READ_METHODS = frozenset(('get', 'items', 'keys', 'values', 'copy', 'union', 'intersection', 'difference',
                          'symmetric_difference', 'issubset', 'issuperset', 'isdisjoint'))
# built-ins that read their argument and hand back a new value (or an iterator over it)
SAFE_FUNCS = frozenset(('len', 'sorted', 'list', 'tuple', 'set', 'frozenset', 'dict', 'min', 'max', 'sum',
                        'any', 'all', 'enumerate', 'reversed', 'iter', 'zip', 'map', 'filter'))
# the ones whose result does not depend on the order the table is walked in
ORDER_FREE = frozenset(('len', 'sorted', 'set', 'frozenset', 'min', 'max', 'sum', 'any', 'all'))


class Refusal(Exception):
    """What `rewrite_text` raises, where `rewrite` raises the compiler's own Unsupported."""


class Table:
    def __init__(self, name, node, annotation, has_bytes, what, literal):
        self.name = name
        self.node = node                # the module-level statement
        self.annotation = annotation    # 'set[str]', 'dict[str, int]', ...
        self.has_bytes = has_bytes
        self.what = what                # 'set' or 'dict'
        self.literal = literal          # the (deduplicated) ast.Set / ast.Dict
        # CPython walks a set of ints in hash order (a str set in a per-run random one, which no
        # program can rely on); the compiler walks any set in insertion order
        self.ordered_by_hash = what == 'set' and 'int' in annotation


# ---------------------------------------------------------------- the literal

def _int_value(e):
    if isinstance(e, ast.Constant) and type(e.value) is int:
        return e.value
    if (isinstance(e, ast.UnaryOp) and isinstance(e.op, (ast.USub, ast.UAdd))
            and isinstance(e.operand, ast.Constant) and type(e.operand.value) is int):
        return -e.operand.value if isinstance(e.op, ast.USub) else e.operand.value
    return None


def _scalar(e):
    """(kind, value) of an int / str / bytes / float literal, else None."""
    v = _int_value(e)
    if v is not None:
        return ('int', v) if -(1 << 63) <= v < (1 << 63) else None
    if isinstance(e, ast.Constant):
        if type(e.value) is str:
            return ('str', e.value)
        if type(e.value) is bytes:
            return ('bytes', e.value)
        if type(e.value) is float:
            return ('float', e.value)
    return None


def _item(e, allow_float):
    """(type text, hashable identity, has_bytes) of a key / element / value literal, else None."""
    s = _scalar(e)
    if s is not None:
        if s[0] == 'float' and not allow_float:
            return None
        return s[0], (s[0], s[1]), s[0] == 'bytes'
    if isinstance(e, ast.Tuple) and e.elts:
        parts = [_item(x, False) for x in e.elts]
        if any(p is None or p[0] not in ('int', 'str') for p in parts):
            return None
        return ('tuple[%s]' % ', '.join(p[0] for p in parts),
                ('tuple',) + tuple(p[1] for p in parts), False)
    return None


def _classify(value):
    if isinstance(value, ast.Set) and value.elts:
        items = [_item(e, False) for e in value.elts]
        if any(i is None for i in items) or len({i[0] for i in items}) != 1:
            return None
        seen, kept = set(), []
        for e, i in zip(value.elts, items):
            if i[1] not in seen:
                seen.add(i[1])
                kept.append(e)
        lit = ast.Set(elts=[copy.deepcopy(e) for e in kept])
        return 'set', 'set[%s]' % items[0][0], any(i[2] for i in items), lit
    if isinstance(value, ast.Dict) and value.keys and all(k is not None for k in value.keys):
        keys = [_item(k, False) for k in value.keys]
        vals = [_item(v, True) for v in value.values]
        if any(i is None for i in keys + vals) or len({i[0] for i in keys}) != 1 \
                or len({i[0] for i in vals}) != 1:
            return None
        order, last = [], {}
        for k, v, ki in zip(value.keys, value.values, keys):
            if ki[1] not in last:
                order.append(ki[1])
            last[ki[1]] = (k, v)
        lit = ast.Dict(keys=[copy.deepcopy(last[i][0]) for i in order],
                       values=[copy.deepcopy(last[i][1]) for i in order])
        return ('dict', 'dict[%s, %s]' % (keys[0][0], vals[0][0]),
                any(i[2] for i in keys + vals), lit)
    return None


def classify(value, tuples_ok=True):
    """`(what, annotation, has_bytes, deduplicated literal)` for a non-empty set / dict display of
    literals of ONE kind (a dict: one key kind, one value kind), else None."""
    found = _classify(value)
    if found is not None and not tuples_ok and 'tuple[' in found[1]:
        return None
    return found


def display(value):
    """The set / dict display `value` stands for: itself, or the elements of `set([...])` /
    `frozenset({...})` / `frozenset((...))` written with a literal argument; else None."""
    if isinstance(value, (ast.Set, ast.Dict)):
        return value
    if (isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
            and value.func.id in ('set', 'frozenset') and len(value.args) == 1 and not value.keywords
            and isinstance(value.args[0], (ast.Set, ast.List, ast.Tuple)) and value.args[0].elts
            and not any(isinstance(e, ast.Starred) for e in value.args[0].elts)):
        return ast.Set(elts=value.args[0].elts)
    return None


def table_assign(node, tuples_ok=True):
    """`(name, display)` when `node` is `NAME = <set/dict display>` (or `set([...])` / `frozenset({...})`)
    or `NAME: T = <display>` that `classify` accepts, else None."""
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        name, value = node.targets[0].id, display(node.value)
    elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
        name, value = node.target.id, display(node.value)
    else:
        return None
    if value is None:
        return None
    if classify(value, tuples_ok) is None:
        return None
    return name, value


# ---------------------------------------------------------------- scopes

def _bound_names(fn):
    """Every name `fn` can bind anywhere inside it (parameters, targets, nested defs, imports):
    over-approximate on purpose -- a table whose name is bound in a function is never treated as
    read there."""
    out = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.arg):
            out.add(n.arg)
        elif isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            out.add(n.id)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n is not fn:
            out.add(n.name)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            out.add(n.name)
        elif isinstance(n, ast.alias):
            out.add((n.asname or n.name).split('.')[0])
    return out


def _parents(root):
    parent = {}
    for n in ast.walk(root):
        for c in ast.iter_child_nodes(n):
            parent[c] = n
    return parent


def _refuse(Unsupported, line, text):
    error = Unsupported(text)
    error.source_line = line
    return error


def _snippet(node):
    try:
        return ast.unparse(node)[:48].split('\n')[0]
    except Exception:
        return '...'


def _passive(node):
    """A top-level statement that runs nothing a table's position could matter to."""
    if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom, ast.Pass)):
        return True
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
        return True
    if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
        return not any(isinstance(n, ast.Call) for n in ast.walk(node.value))
    return False


# ---------------------------------------------------------------- the pass

def value_name(node):
    call = node.value
    return call.func.id if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) else None


def _find_tables(tree, select):
    """Module-level literal tables bound exactly once, by a single statement that runs before any
    other module-level code, with a name no def, class or import also takes. `select` is 'plain'
    (no tuple in it) or 'tuples'."""
    taken = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    for n in tree.body:
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            taken.update((a.asname or a.name).split('.')[0] for a in n.names)
    stores = {}
    for top in tree.body:
        if isinstance(top, (ast.FunctionDef, ast.ClassDef)):
            continue
        for n in ast.walk(top):
            if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
                stores[n.id] = stores.get(n.id, 0) + 1
            elif isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in MUTATORS:
                base = n.func.value
                while isinstance(base, (ast.Attribute, ast.Subscript)):
                    base = base.value
                if isinstance(base, ast.Name):
                    stores[base.id] = stores.get(base.id, 0) + 1
    tables = {}
    active = False
    for node in tree.body:
        found = table_assign(node)
        if found is None:
            if not _passive(node):
                active = True
            continue
        name, value = found
        what, annotation, has_bytes, literal = classify(value)
        if ('tuple[' in annotation) != (select == 'tuples'):
            continue
        if isinstance(getattr(node, 'value', None), ast.Call) and value_name(node) in taken:
            continue        # `set` / `frozenset` is the program's own function
        if active or name in taken or stores.get(name, 0) != 1 or name in tables:
            continue
        tables[name] = Table(name, node, annotation, has_bytes, what, literal)
    return tables


def _order_free(n, parents):
    """Whether the order a table is walked in cannot show in the result."""
    p = parents.get(n)
    if isinstance(p, ast.comprehension):
        owner = parents.get(p)
        if isinstance(owner, ast.SetComp):
            return True
        if isinstance(owner, ast.GeneratorExp):
            call = parents.get(owner)
            return (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                    and call.func.id in ORDER_FREE and owner in call.args)
        return False
    if isinstance(p, ast.Call) and isinstance(p.func, ast.Name):
        return p.func.id in ORDER_FREE
    return False


def _check_uses(tables, functions, Unsupported):
    """Refuse, by name, every use of a table that could change it or share it; return, per function,
    the tables it reads."""
    reads = {}
    for fn, owner in functions:
        bound = _bound_names(fn)
        parents = _parents(fn)
        mine = set()
        for n in ast.walk(fn):
            if isinstance(n, (ast.Global, ast.Nonlocal)):
                for t in n.names:
                    if t in tables:
                        raise _refuse(Unsupported, n.lineno,
                                      "%r is a module-level %s; `global %s` would let a function rebind or "
                                      "change it.\n  write instead: leave the table read-only, and keep what "
                                      "changes in a dataclass field or a local" % (t, tables[t].what, t))
            if not (isinstance(n, ast.Name) and n.id in tables and n.id not in bound):
                continue
            t = tables[n.id]
            p = parents.get(n)
            ok = False
            if isinstance(p, ast.Compare) and n in p.comparators:
                ok = isinstance(p.ops[p.comparators.index(n)], (ast.In, ast.NotIn))
            elif isinstance(p, ast.Subscript) and p.value is n:
                ok = isinstance(p.ctx, ast.Load) and not isinstance(p.slice, ast.Slice)
                if isinstance(p.ctx, (ast.Store, ast.Del)):
                    raise _refuse(Unsupported, n.lineno,
                                  "%r is a module-level %s; `%s` would change a table every other function "
                                  "reads.\n  write instead: leave the table read-only; a table that changes is "
                                  "a local (`%s = %s(%s)` for a copy), or a dataclass field"
                                  % (n.id, t.what, _snippet(p), n.id.lower(), t.what, n.id))
            elif isinstance(p, ast.Attribute) and p.value is n:
                call = parents.get(p)
                if p.attr in MUTATORS:
                    raise _refuse(Unsupported, n.lineno,
                                  "%r is a module-level %s; `%s.%s(...)` would change a table every other "
                                  "function reads.\n  write instead: leave the table read-only; a table that "
                                  "changes is a local (`%s = %s(%s)` for a copy), or a dataclass field"
                                  % (n.id, t.what, n.id, p.attr, n.id.lower(), t.what, n.id))
                ok = p.attr in READ_METHODS and isinstance(call, ast.Call) and call.func is p
            elif isinstance(p, ast.BinOp) and isinstance(p.op, (ast.BitOr, ast.BitAnd, ast.Sub, ast.BitXor)):
                ok = True       # a new set (a new dict for `|`)
            elif isinstance(p, ast.AugAssign) and p.target is n:
                raise _refuse(Unsupported, n.lineno,
                              "%r is a module-level %s; `%s` would change a table every other function "
                              "reads.\n  write instead: leave the table read-only, or build a new one "
                              "(`%s = %s | other`)" % (n.id, t.what, _snippet(p), n.id.lower(), n.id))
            elif isinstance(p, ast.Call) and n in p.args and isinstance(p.func, ast.Name):
                ok = p.func.id in SAFE_FUNCS and p.func.id not in bound
            elif isinstance(p, ast.Call) and n in p.args and isinstance(p.func, ast.Attribute) \
                    and p.func.attr == 'join' and isinstance(p.func.value, ast.Constant):
                ok = True
            elif isinstance(p, (ast.For, ast.AsyncFor)) and p.iter is n:
                ok = True
            elif isinstance(p, ast.comprehension) and p.iter is n:
                ok = True
            elif isinstance(p, (ast.If, ast.While, ast.IfExp)) and p.test is n:
                ok = True
            elif isinstance(p, ast.UnaryOp) and isinstance(p.op, ast.Not):
                ok = True
            if not ok:
                raise _refuse(Unsupported, n.lineno,
                              "%r is a module-level %s; `%s` uses the whole table as a value, which would "
                              "make a second reference where CPython shares the one object.\n"
                              "  write instead: read it in place (`x in %s`, `%s[k]`, `for x in %s`, "
                              "`len(%s)`), or `%s(%s)` for a copy"
                              % (n.id, t.what, _snippet(p), n.id, n.id, n.id, n.id, t.what, n.id))
            walked = isinstance(p, (ast.For, ast.AsyncFor, ast.comprehension)) or (
                isinstance(p, ast.Call) and isinstance(p.func, ast.Name) and p.func.id in SAFE_FUNCS)
            if t.ordered_by_hash and walked and not _order_free(n, parents):
                raise _refuse(Unsupported, n.lineno,
                              "%r is a module-level set of ints; `%s` walks it in hash order in CPython and "
                              "in insertion order here, so the two can differ.\n"
                              "  write instead: `sorted(%s)` for a fixed order" % (n.id, _snippet(p), n.id))
            mine.add(n.id)
        for n in ast.walk(fn):
            if n is not fn and isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                inner = {m.id for m in ast.walk(n) if isinstance(m, ast.Name) and m.id in tables
                         and m.id not in bound}
                if inner:
                    t = sorted(inner)[0]
                    raise _refuse(Unsupported, n.lineno,
                                  "%r is a module-level %s read inside a nested def; a nested def cannot "
                                  "hold a table.\n  write instead: define the helper at module level and "
                                  "read %s there" % (t, tables[t].what, t))
        reads[fn] = mine
    return reads


def rewrite(tree, Unsupported, library=False, entry=None, select='plain'):
    tables = _find_tables(tree, select)
    if not tables:
        return
    functions = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            functions.append((node, None))
        elif isinstance(node, ast.ClassDef):
            functions.extend((m, node) for m in node.body if isinstance(m, ast.FunctionDef))
    # a table read outside every function body (class attribute, module statement) has no home
    inside = set()
    for fn, _ in functions:
        inside.update(id(n) for n in ast.walk(fn))
    table_nodes = {id(t.node) for t in tables.values()}
    module_calls = set()
    for top in tree.body:
        if isinstance(top, ast.FunctionDef) or id(top) in table_nodes:
            continue
        for n in ast.walk(top):
            if id(n) in inside:
                continue
            if isinstance(n, ast.Name) and n.id in tables:
                raise _refuse(Unsupported, n.lineno,
                              "%r is a module-level %s used outside a function; a table can only be read "
                              "inside a function.\n  write instead: read it inside a function"
                              % (n.id, tables[n.id].what))
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
                module_calls.add(n.func.id)
    reads = _check_uses(tables, functions, Unsupported)
    # drop the table statements: the readers get it from the parameter or the local below
    tree.body = [n for n in tree.body if id(n) not in table_nodes]

    top_fns = [fn for fn, owner in functions if owner is None]
    names = [fn.name for fn in top_fns]
    unique = len(set(names)) == len(names)
    by_name = {fn.name: fn for fn in top_fns} if unique else {}
    entry_name = entry if entry is not None else (top_fns[-1].name if top_fns else None)
    bound = {fn: _bound_names(fn) for fn, _ in functions}
    parents = {fn: _parents(fn) for fn, _ in functions}

    calls = {fn: [] for fn, _ in functions}      # (call node, callee name)
    escaped = set(module_calls)                   # called from module-level code: no parameter to pass
    for fn, _ in functions:
        for n in ast.walk(fn):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id in by_name \
                    and n.id not in bound[fn]:
                p = parents[fn].get(n)
                if isinstance(p, ast.Call) and p.func is n:
                    calls[fn].append((p, n.id))
                else:
                    escaped.add(n.id)
    for fn in top_fns:
        if fn.decorator_list:
            escaped.add(fn.name)
    eligible = {name for name in by_name
                if not library and name != entry_name and name not in escaped}

    threadable = {t for t, tab in tables.items() if not tab.has_bytes}
    need = {fn: {t for t in reads[fn] if t in threadable} for fn, _ in functions}
    changed = True
    while changed:
        changed = False
        for fn, _ in functions:
            for _, callee in calls[fn]:
                if callee in eligible:
                    extra = need[by_name[callee]] - need[fn]
                    if extra:
                        need[fn] |= extra
                        changed = True

    threaded = {name for name in eligible if need[by_name[name]]}
    for fn, _ in functions:
        for call, callee in calls[fn]:
            if callee in threaded:
                clash = sorted(need[by_name[callee]] & bound[fn])
                if clash:
                    raise _refuse(Unsupported, call.lineno,
                                  "%r is a module-level %s, but %s uses the same name for something "
                                  "else and still calls %s, which reads the table.\n"
                                  "  write instead: rename the local %r" % (
                                      clash[0], tables[clash[0]].what, fn.name, callee, clash[0]))

    def annotation(t):
        return ast.parse(tables[t].annotation, mode='eval').body

    for fn, owner in functions:
        if owner is None and fn.name in threaded:
            hidden = sorted(need[fn])
            lead = [ast.arg(arg=t, annotation=annotation(t)) for t in hidden]
            if fn.args.posonlyargs:
                fn.args.posonlyargs = lead + fn.args.posonlyargs
            else:
                fn.args.args = lead + fn.args.args
            local = sorted(t for t in reads[fn] if t not in threadable)
        else:
            local = sorted(need[fn] | {t for t in reads[fn] if t not in threadable})
        statements = []
        for t in local:
            tab = tables[t]
            statements.append(ast.copy_location(ast.AnnAssign(
                target=ast.Name(id=t, ctx=ast.Store()), annotation=annotation(t),
                value=copy.deepcopy(tab.literal), simple=1), tab.node))
        if statements:
            at = 1 if (fn.body and isinstance(fn.body[0], ast.Expr)
                       and isinstance(fn.body[0].value, ast.Constant)
                       and isinstance(fn.body[0].value.value, str)) else 0
            fn.body[at:at] = statements
    for fn, _ in functions:
        for call, callee in calls[fn]:
            if callee in threaded:
                call.args = [ast.Name(id=t, ctx=ast.Load()) for t in sorted(need[by_name[callee]])] + call.args
    ast.fix_missing_locations(tree)


def rewrite_text(source, library=False, notes=None):
    """The program with its tuple tables lowered, as source text; `source` itself when it has none (or
    one cannot be lowered -- the reason is then added to `notes`, and the tuple lowering refuses the
    table in its own words)."""
    if '(' not in source or ('{' not in source and 'set' not in source):
        return source
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    if not _find_tables(tree, 'tuples'):
        return source
    try:
        rewrite(tree, Refusal, library, None, 'tuples')
    except Refusal as refusal:
        if notes is not None:
            notes.append((getattr(refusal, 'source_line', 1) or 1, str(refusal).splitlines()[0]))
        return source
    return ast.unparse(tree) + '\n'
