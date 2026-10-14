"""Advisory report of commonly quadratic patterns in AIL source; never changes or fails a build.

`check` adds the lines to its JSON report (`slow_patterns`); `compile` prints them on stderr after a
successful build. At most LIMIT lines, each `file:line: slow: <pattern>; <fix>`. The rules are
syntactic and run on the Python-shaped text the AIL loader produces (the same text the compiler
reads), so they see `let`-free assignments, `for`/`while` and method calls exactly as written.

What is reported, inside a loop whose trip count is not a small constant:
- linear search of a list: `x in xs`, `xs.index(x)`, `xs.count(x)`, `xs.remove(x)`;
- front operations that shift the whole list: `xs.pop(0)`, `xs.insert(0, x)`;
- `min`/`max`/`sorted`/`.sort()` of a list that the same loop also changes (a heap's job);
- a scan of a whole collection for the rows whose key equals the outer loop's current value
  (`for e in range(m) { if src[e] == u {...} }`), the O(V*E) graph walk;
- a loop over a collection nested inside a loop over the same collection.
Not reported: `s += t` on str (linear in AIL: the buffer grows geometrically, measured), `in` on a
dict/set/str, constant literal lists, and calls into other functions (no interprocedural cost).
"""
import ast

LIMIT = 3
_MUTATORS = {'append', 'extend', 'insert', 'remove', 'pop', 'clear'}
_SMALL_RANGE = 64


def _kind(annotation):
    """'list' / 'dict' / 'set' / 'str' / None for an annotation text."""
    if not annotation:
        return None
    for name in ('list', 'dict', 'set'):
        if annotation == name or annotation.startswith(name + '['):
            return name
    return 'str' if annotation in ('str', '__ail_checked_str__') else None


def _element(annotation):
    if annotation and annotation.startswith('list[') and annotation.endswith(']'):
        return annotation[5:-1]
    return None


class _Types:
    """Per-function local types from annotations and obvious initialisers; fields from classes."""

    def __init__(self, tree):
        fields = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == '__init__':
                        for arg in item.args.args[1:]:
                            if arg.annotation is not None:
                                fields.setdefault(arg.arg, set()).add(ast.unparse(arg.annotation))
        self.fields = {name: next(iter(kinds)) for name, kinds in fields.items() if len(kinds) == 1}
        self.locals = {}

    def enter(self, function):
        local = {}
        conflict = set()

        def bind(name, annotation):
            if name in local and local[name] != annotation:
                conflict.add(name)
            local.setdefault(name, annotation)

        for arg in function.args.args:
            if arg.annotation is not None:
                bind(arg.arg, ast.unparse(arg.annotation))
        for node in ast.walk(function):
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                bind(node.target.id, ast.unparse(node.annotation))
            elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                guess = self._guess(node.value)
                if guess is not None:
                    bind(node.targets[0].id, guess)
        self.locals = {name: value for name, value in local.items() if name not in conflict}

    def _guess(self, value):
        if isinstance(value, (ast.List, ast.ListComp)):
            return 'list'
        if isinstance(value, ast.BinOp) and isinstance(value.op, ast.Mult) and isinstance(value.left, ast.List):
            return 'list'
        if isinstance(value, (ast.Dict, ast.DictComp)):
            return 'dict'
        if isinstance(value, (ast.Set, ast.SetComp)):
            return 'set'
        if isinstance(value, ast.JoinedStr) or (isinstance(value, ast.Constant) and isinstance(value.value, str)):
            return 'str'
        if isinstance(value, ast.Call):
            func = value.func
            if isinstance(func, ast.Name) and func.id in ('list', 'sorted'):
                return 'list'
            if isinstance(func, ast.Name) and func.id in ('dict', 'set', 'str'):
                return func.id
            if isinstance(func, ast.Attribute) and func.attr in ('split', 'splitlines'):
                return 'list[str]'
        return self.annotation(value) if isinstance(value, (ast.Name, ast.Attribute, ast.Subscript)) else None

    def annotation(self, expr):
        if isinstance(expr, ast.Name):
            return self.locals.get(expr.id)
        if isinstance(expr, ast.Attribute):
            return self.fields.get(expr.attr)
        if isinstance(expr, ast.Subscript) and not isinstance(expr.slice, ast.Slice):
            return _element(self.annotation(expr.value))
        return None

    def kind(self, expr):
        return _kind(self.annotation(expr))


def _small_loop(node):
    """True for a loop whose trip count is a small constant (or a literal sequence)."""
    if isinstance(node, ast.While):
        return False
    it = node.iter
    if isinstance(it, (ast.List, ast.Tuple, ast.Set, ast.Constant)):
        return True
    if isinstance(it, ast.Call) and isinstance(it.func, ast.Attribute) and it.func.attr == 'split' \
            and isinstance(it.func.value, ast.Constant):
        return True
    if isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == 'range':
        args = it.args
        if args and all(isinstance(a, ast.Constant) and isinstance(a.value, int) for a in args):
            start, stop = (0, args[0].value) if len(args) == 1 else (args[0].value, args[1].value)
            return stop - start <= _SMALL_RANGE
    return False


def _assigned(body):
    names = set()
    for stmt in body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                names.add(node.id)
    return names


def _mutated(body):
    """Unparsed receivers of list-changing calls (and heappush/heappop) anywhere in body."""
    out = set()
    for stmt in body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr in _MUTATORS:
                    out.add(ast.unparse(func.value))
                elif isinstance(func, ast.Name) and func.id in ('heappush', 'heappop') and node.args:
                    out.add(ast.unparse(node.args[0]))
            elif isinstance(node, ast.AugAssign):
                out.add(ast.unparse(node.target))
    return out


def _grows(name, body):
    """`name` is changed in body and survives from one pass to the next (not re-bound or cleared)."""
    rebound = set()
    for stmt in body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Assign):
                rebound.update(ast.unparse(t) for t in node.targets)
            elif isinstance(node, ast.AnnAssign):
                rebound.add(ast.unparse(node.target))
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'clear':
                rebound.add(ast.unparse(node.func.value))
    return name in _mutated(body) and name not in rebound


def _constant_lists(function):
    """Locals bound once to a literal list of constants and never changed: small fixed tables."""
    literal, other = set(), set()
    for node in ast.walk(function):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            value = node.value
            if isinstance(value, ast.List) and all(isinstance(e, ast.Constant) for e in value.elts):
                literal.add(node.targets[0].id)
            elif isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute) \
                    and value.func.attr == 'split' and isinstance(value.func.value, ast.Constant):
                literal.add(node.targets[0].id)
            else:
                other.add(node.targets[0].id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            other.add(node.target.id)
    return literal - other - _mutated(function.body)


def _collection(loop):
    """The collection a `for` walks: `xs` for `for x in xs` / `range(len(xs))`; else None."""
    if not isinstance(loop, ast.For):
        return None
    it = loop.iter
    if isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == 'range' and it.args:
        stop = it.args[0] if len(it.args) == 1 else it.args[1]
        if isinstance(stop, ast.Call) and isinstance(stop.func, ast.Name) and stop.func.id == 'len' and stop.args:
            return ast.unparse(stop.args[0])
        return None
    if isinstance(it, (ast.Name, ast.Attribute)):
        return ast.unparse(it)
    return None


class _Scanner:
    def __init__(self, tree):
        self.types = _Types(tree)
        self.found = []

    def add(self, rank, node, pattern, fix):
        self.found.append((rank, node.lineno, pattern, fix))

    def function(self, function):
        self.types.enter(function)
        self.constant_lists = _constant_lists(function)
        self.block(function.body, [])

    def block(self, body, loops):
        for stmt in body:
            self.statement(stmt, loops)

    def statement(self, stmt, loops):
        if isinstance(stmt, (ast.FunctionDef, ast.ClassDef)):
            return
        if isinstance(stmt, (ast.For, ast.While)):
            for part in ([stmt.iter] if isinstance(stmt, ast.For) else [stmt.test]):
                self.expressions(part, loops)
            if loops and isinstance(stmt, ast.For):
                self.nested_scan(stmt, loops)
            inner = loops if _small_loop(stmt) else loops + [stmt]
            self.block(stmt.body, inner)
            self.block(stmt.orelse, loops)
            return
        for field, value in ast.iter_fields(stmt):
            if isinstance(value, list) and value and isinstance(value[0], ast.stmt):
                self.block(value, loops)
            elif isinstance(value, ast.expr):
                self.expressions(value, loops)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.expr):
                        self.expressions(item, loops)
                    elif isinstance(item, ast.ExceptHandler):
                        self.block(item.body, loops)

    def is_list(self, expr):
        if isinstance(expr, ast.Name) and expr.id in self.constant_lists:
            return False
        return self.types.kind(expr) == 'list'

    def expressions(self, expr, loops):
        if not loops:
            return
        loop = loops[-1]
        for node in ast.walk(expr):
            if isinstance(node, ast.Compare):
                for op, right in zip(node.ops, node.comparators):
                    if isinstance(op, (ast.In, ast.NotIn)) and self.is_list(right):
                        name = ast.unparse(right)
                        self.add(0, node, f'`in {name}` scans the list each pass', 'use a set or a [False] * n table')
            elif isinstance(node, ast.ListComp) and self.key_filter(node, loop):
                self.add(2, node, 'this comprehension scans a whole list for the current key each pass',
                         'group once before the loop (list[list[int]] or dict key -> indices)')
            elif isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == 'heappush' and any(k.arg == 'key' for k in node.keywords):
                    self.add(5, node, 'a heap of structs allocates every entry',
                             'push one int `(d << 20) | v` if it fits (5.5x fewer instructions on a route-search program)')
                elif isinstance(func, ast.Attribute) and self.is_list(func.value):
                    name = ast.unparse(func.value)
                    first = node.args[0] if node.args else None
                    zero = isinstance(first, ast.Constant) and first.value == 0
                    if func.attr in ('index', 'count', 'remove') and node.args:
                        self.add(0, node, f'`{name}.{func.attr}()` scans the list each pass',
                                 'keep a dict (value -> index/count) or a [False] * n table')
                    elif func.attr == 'pop' and zero:
                        self.add(1, node, f'`{name}.pop(0)` shifts the whole list each pass',
                                 f'use a head index: `{name}[head]; head += 1` (MORE: BFS)')
                    elif func.attr == 'insert' and zero:
                        self.add(1, node, f'`{name}.insert(0, x)` shifts the whole list each pass',
                                 'append, then reverse once after the loop')
                    elif func.attr == 'sort' and _grows(name, loop.body):
                        self.add(3, node, f'`{name}.sort()` re-sorts a list the loop keeps changing',
                                 'use heappush/heappop (MORE: Heaps)')
                elif isinstance(func, ast.Name) and func.id in ('min', 'max', 'sorted') and len(node.args) == 1 \
                        and self.is_list(node.args[0]) and _grows(ast.unparse(node.args[0]), loop.body):
                    name = ast.unparse(node.args[0])
                    self.add(3, node, f'`{func.id}({name})` rescans a list the loop keeps changing',
                             'use heappush/heappop (MORE: Heaps)')

    def key_filter(self, node, loop):
        """`[.. for e in COLL if E[e] == k]` / `for e in COLL { if E[e] == k {..} }` with k set in loop."""
        if isinstance(node, ast.ListComp):
            if len(node.generators) != 1:
                return False
            gen = node.generators[0]
            target, tests, walk = gen.target, gen.ifs, gen.iter
        else:
            if not node.body or not isinstance(node.body[0], ast.If):
                return False
            target, tests, walk = node.target, [node.body[0].test], node.iter
        if not isinstance(target, ast.Name):
            return False
        if isinstance(walk, ast.Call) and isinstance(walk.func, ast.Name) and walk.func.id == 'range':
            if len(walk.args) != 1:
                return False  # range(a, b) is already a slice of the rows: CSR, buckets
        elif not isinstance(walk, (ast.Name, ast.Attribute)):
            return False
        changing = _assigned(loop.body) | ({loop.target.id} if isinstance(loop, ast.For)
                                           and isinstance(loop.target, ast.Name) else set())
        for test in tests:
            for cmp in ast.walk(test):
                if not isinstance(cmp, ast.Compare) or len(cmp.ops) != 1 or not isinstance(cmp.ops[0], ast.Eq):
                    continue
                sides = [cmp.left, cmp.comparators[0]]
                for mine, other in (sides, sides[::-1]):
                    uses_element = any(isinstance(n, ast.Name) and n.id == target.id for n in ast.walk(mine))
                    root = other
                    while isinstance(root, ast.Attribute):
                        root = root.value
                    if uses_element and isinstance(root, ast.Name) and root.id in changing \
                            and root.id != target.id:
                        return True
        return False

    def nested_scan(self, stmt, loops):
        loop = loops[-1]
        if self.key_filter(stmt, loop):
            self.add(2, stmt, 'this loop scans a whole list for the current key each outer pass',
                     'group once before the outer loop (list[list[int]] or dict key -> indices)')
            return
        inner = _collection(stmt)
        if inner is None:
            return
        for outer in loops:
            if _collection(outer) == inner and inner not in _mutated(outer.body):
                self.add(4, stmt, f'nested loops both walk `{inner}` (O(n^2))',
                         'if n is large: sort + two pointers/bisect, or a dict')
                return


def scan(text, source_map, skip_prefixes=()):
    """Warnings for the translated program text; positions via the loader's source_map."""
    tree = ast.parse(text)
    scanner = _Scanner(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            scanner.function(node)
    lines = sorted(source_map)
    results, seen = [], set()
    for rank, line, pattern, fix in sorted(scanner.found):
        position = source_map.get(line)
        if position is None:
            earlier = [key for key in lines if key <= line]
            position = source_map.get(earlier[-1]) if earlier else None
        if position is None:
            continue
        path = str(position[0])
        if any(path.startswith(prefix) for prefix in skip_prefixes):
            continue
        key = (path, position[1])
        if key in seen:
            continue
        seen.add(key)
        results.append(dict(path=path, line=position[1], rank=rank, pattern=pattern, fix=fix))
    # One line per kind (the first; the count of the others in `more`), rank order, at most LIMIT.
    picked = {}
    for item in sorted(results, key=lambda w: (w['rank'], w['path'], w['line'])):
        if item['rank'] in picked:
            picked[item['rank']]['more'] += 1
        else:
            picked[item['rank']] = dict(item, more=0)
    chosen = [picked[rank] for rank in sorted(picked)][:LIMIT]
    return sorted(chosen, key=lambda w: (w['path'], w['line']))


def format_warning(warning, base=None):
    path = warning['path']
    if base is not None:
        try:
            from pathlib import Path
            path = str(Path(path).relative_to(base))
        except ValueError:
            pass
    more = f" (+{warning['more']} more)" if warning.get('more') else ''
    return f"{path}:{warning['line']}: slow: {warning['pattern']}; {warning['fix']}{more}"
