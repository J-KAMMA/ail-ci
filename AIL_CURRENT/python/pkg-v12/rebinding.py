"""Block-scoped typing for loop variables and `except ... as` names.

Python lets one name hold an int in one loop and a str in a later loop, and lets `except E as e`
reuse a name that already holds something else. The typed compiler gives each local ONE kind, so
those programs were refused ("'x' is an int and is being assigned a str", "exception handler
binding 'e' conflicts ..."). This module renames such a binding region -- a `for` loop's target
plus its body, or a handler's name plus its body -- to a fresh name, but ONLY when no read outside
the region can observe the value bound inside it, so the renamed program prints exactly what
CPython prints:

* after a `for` loop Python keeps the last element in the loop variable (or the old value when
  the loop ran zero times); after a handler Python UNBINDS the name. A read of the name after the
  region, or anywhere in a loop around it, observes that -- unless a plain assignment to the name
  sits between the region and the read in a block that encloses the read (`e = 3` then
  `print(e)`), which every path to the read executes first;
* a lambda or nested function inside the region that mentions the name may run later and see a
  later binding, so such a region is left alone.

Regions that cannot be split are reported by line, so the refusal names exactly what to rename.
The rename works on the source text at the AST's own positions, so every line number (and so
every diagnostic location) stays where it was.
"""
import ast
import re

_CONFLICT_PATTERNS = (
    re.compile(r"'([A-Za-z_]\w*)' is an? [\w ]+? and is being assigned"),
    re.compile(r"exception handler binding '([A-Za-z_]\w*)' conflicts"),
)


def conflict_name(message):
    """The local a kind-conflict refusal is about, or None for any other refusal."""
    for pattern in _CONFLICT_PATTERNS:
        match = pattern.search(message)
        if match:
            return match.group(1)
    return None


def _span(node):
    return ((node.lineno, node.col_offset), (node.end_lineno, node.end_col_offset))


def _inside(inner, outer):
    (a, b), (c, d) = _span(inner), _span(outer)
    return a >= c and b <= d


class _Region:
    def __init__(self, node, kind):
        self.node = node              # the For or the ExceptHandler
        self.kind = kind              # 'for' or 'except'
        if kind == 'for':
            self.parts = [node.target] + list(node.body)
        else:
            self.parts = list(node.body)
        self.start = (node.lineno, node.col_offset)
        last = node.body[-1]
        self.end = (last.end_lineno, last.end_col_offset)

    def contains(self, node):
        if self.kind == 'for' and _inside(node, self.node.target):
            return True
        return any(_inside(node, part) for part in self.node.body)

    @property
    def line(self):
        return self.node.lineno


def _parents(fn):
    parent = {}
    for node in ast.walk(fn):
        for child in ast.iter_child_nodes(node):
            parent[child] = node
    return parent


def _statement_lists(node):
    for field in ('body', 'orelse', 'finalbody', 'handlers'):
        value = getattr(node, field, None)
        if isinstance(value, list) and value and isinstance(value[0], (ast.stmt, ast.ExceptHandler)):
            yield value


def _covered(read, region, stores, parent):
    """A plain store of the name, after the region and before `read`, in a statement list that
    encloses `read`, so every path from the region to the read rebinds the name first."""
    read_at = (read.lineno, read.col_offset)
    for store in stores:
        statement = store
        while statement in parent and not isinstance(statement, ast.stmt):
            statement = parent[statement]
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        if (statement.lineno, statement.col_offset) <= region.end:
            continue
        if (statement.end_lineno, statement.end_col_offset) > read_at:
            continue
        owner = parent.get(statement)
        if owner is None:
            continue
        for block in _statement_lists(owner):
            if statement in block:
                index = block.index(statement)
                if any(_inside(read, later) for later in block[index + 1:]):
                    if not region.contains(statement):
                        return True
    return False


def _function_regions(fn, name):
    """Every region of `name` in `fn`, split into the ones a rename can separate and the ones it
    cannot (each with the line of a read that observes it)."""
    parent = _parents(fn)
    regions = []
    for node in ast.walk(fn):
        if node is not fn and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if (isinstance(node, ast.For) and node.body
                and any(isinstance(t, ast.Name) and t.id == name for t in ast.walk(node.target))):
            regions.append(_Region(node, 'for'))
        elif isinstance(node, ast.ExceptHandler) and node.name == name and node.body:
            regions.append(_Region(node, 'except'))
    # outermost regions only: a region nested in another one is renamed along with it
    regions = [r for r in regions
               if not any(o is not r and o.contains(r.node) for o in regions)]
    names = [n for n in ast.walk(fn) if isinstance(n, ast.Name) and n.id == name]
    loads = [n for n in names if isinstance(n.ctx, ast.Load)]
    stores = [n for n in names if isinstance(n.ctx, ast.Store)]
    loops = [n for n in ast.walk(fn) if isinstance(n, (ast.For, ast.While))]
    late = [n for n in ast.walk(fn) if isinstance(n, (ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef))
            and n is not fn]
    splittable, blocked = [], []
    for region in regions:
        observer = None
        if any(region.contains(f) and any(isinstance(m, ast.Name) and m.id == name for m in ast.walk(f))
               for f in late):
            observer = "a lambda in it (it may run later)"
        enclosing = [loop for loop in loops if loop is not region.node and region.contains(loop) is False
                     and _inside(region.node, loop)]
        for read in loads:
            if observer is not None:
                break
            if any(r.contains(read) for r in regions):
                continue              # its own region, or another one that binds the name first
            at = (read.lineno, read.col_offset)
            after = at > region.end
            in_loop = any(_inside(read, loop) for loop in enclosing)
            if region.kind == 'for' and any(_inside(read, part) for part in region.node.orelse):
                after = True
            if not (after or in_loop):
                continue
            if after and _covered(read, region, stores, parent):
                continue
            statement = read
            while statement in parent and not isinstance(statement, ast.stmt):
                statement = parent[statement]
            text = ast.unparse(statement).split(chr(10))[0]
            observer = "`%s`" % (text if len(text) <= 40 else text[:37] + "...")
        if observer is None:
            splittable.append(region)
        else:
            blocked.append((region, observer))
    return splittable, blocked


def _rename_text(source, edits):
    """Apply (line, byte_start, byte_end, text) edits; columns are UTF-8 byte offsets, the unit
    the AST reports, and edits on one line are applied right to left so offsets stay valid."""
    lines = source.split('\n')
    by_line = {}
    for line, start, end, text in edits:
        by_line.setdefault(line, []).append((start, end, text))
    for line, items in by_line.items():
        raw = lines[line - 1].encode('utf8')
        for start, end, text in sorted(items, reverse=True):
            raw = raw[:start] + text.encode('utf8') + raw[end:]
        lines[line - 1] = raw.decode('utf8')
    return '\n'.join(lines)


def split(source, name, taken=()):
    """`source` with every separable region of `name` renamed, a map {fresh name: name}, and the
    blocked regions as (region, text of the read that observes it) pairs."""
    text = source.strip()
    tree = ast.parse(text)
    lines = text.split('\n')
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | set(taken)
    edits, fresh, blocked = [], {}, []
    functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    for fn in functions:
        separable, stuck = _function_regions(fn, name)
        blocked += stuck
        for region in separable:
            new = '%s__b%d' % (name, region.line)
            while new in used:
                new += '_'
            used.add(new)
            fresh[new] = name
            for node in ast.walk(region.node):
                if isinstance(node, ast.Name) and node.id == name and region.contains(node):
                    edits.append((node.lineno, node.col_offset, node.end_col_offset, new))
            if region.kind == 'except':
                raw = lines[region.node.lineno - 1].encode('utf8')
                match = re.compile(rb'\bas\s+(' + re.escape(name.encode()) + rb')\b').search(
                    raw, region.node.col_offset)
                if match is None:
                    return None, {}, blocked
                edits.append((region.node.lineno, match.start(1), match.end(1), new))
    if not edits:
        return None, {}, blocked
    return _rename_text(text, edits), fresh, blocked


def blocked_refusal(message, name, blocked):
    """(refusal text, line of the loop or handler to rename) when a region could not be
    separated; the caller attaches the line, so the location prefix points at that binding."""
    if not blocked:
        return message, None
    region, read = blocked[0]
    head = re.split(r';| -- ', message, maxsplit=1)[0].strip()
    if region.kind == 'except':
        return ('%s, and %s reads %r after this handler, where Python unbinds it: rename the '
                'handler name and its uses, e.g. `as %s`' % (head, read, name, name + '2'),
                region.line)
    return ('%s, and %s reads %r after this loop, where Python keeps its last value: rename this '
            'loop variable and its uses, e.g. `for %s in ...`' % (head, read, name, name + '2'),
            region.line)


_PARAM_PATTERN = re.compile(r"\x27([A-Za-z_]\w*)\x27 is a parameter and cannot be reassigned")
_SCALAR_ANNOTATIONS = ("int", "float", "bool")


def param_name(message):
    """The parameter a "cannot be reassigned" refusal is about, or None for any other refusal."""
    match = _PARAM_PATTERN.search(message)
    return match.group(1) if match else None


def _binds_elsewhere(fn, name):
    """True when something inside  other than a plain Name could bind or scope 
    (nested scopes, global/nonlocal, handler names, imports, def/class names): those cases are
    not copied, because renaming only the Name nodes would not be exact."""
    for node in ast.walk(fn):
        if node is fn:
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == name:
                return True
            if any(isinstance(n, ast.Name) and n.id == name for n in ast.walk(node)):
                return True
        elif isinstance(node, ast.Lambda):
            if any(isinstance(n, ast.Name) and n.id == name for n in ast.walk(node)):
                return True
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            if name in node.names:
                return True
        elif isinstance(node, ast.ExceptHandler):
            if node.name == name:
                return True
        elif isinstance(node, ast.alias):
            if (node.asname or node.name.split(".")[0]) == name:
                return True
    return False


def copy_param(source, name, taken=()):
    """Python lets a function rebind its own parameter; the typed compiler gives a parameter one
    fixed kind and refuses the store. For a scalar (int/float/bool annotated) parameter the
    rebinding is exactly a local copy, so every use of the name in the body is renamed to a fresh
    local that starts as the argument: (new source, fresh name, inserted line numbers), or None
    when no function qualifies. The parameter keeps its own name, so keyword calls still bind.
    The copy shares the first statement\x27s line when that statement is simple, so line numbers
    stay put; otherwise it is a new line and the caller shifts line numbers back."""
    text = source.strip()
    tree = ast.parse(text)
    lines = text.split("\n")
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | set(taken)
    new = "%s__p" % name
    while new in used:
        new += "_"
    edits, inserts = [], []
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef):
            continue
        args = fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs
        arg = next((a for a in args if a.arg == name), None)
        if arg is None or not (isinstance(arg.annotation, ast.Name)
                               and arg.annotation.id in _SCALAR_ANNOTATIONS):
            continue
        if _binds_elsewhere(fn, name) or fn.args.vararg and fn.args.vararg.arg == name                 or fn.args.kwarg and fn.args.kwarg.arg == name:
            continue
        if not any(isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, (ast.Store, ast.Del))
                   for n in ast.walk(fn)):
            continue
        body = fn.body
        start = 1 if (isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
                      and isinstance(body[0].value.value, str) and len(body) > 1) else 0
        first = body[start]
        for stmt in body:
            for node in ast.walk(stmt):
                if isinstance(node, ast.Name) and node.id == name:
                    edits.append((node.lineno, node.col_offset, node.end_col_offset, new))
        simple = not isinstance(first, (ast.If, ast.For, ast.While, ast.Try, ast.With,
                                        ast.AsyncFor, ast.AsyncWith, ast.Match,
                                        ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        indent = lines[first.lineno - 1][:first.col_offset]
        # a simple one-line statement takes the copy before it on the same line; a multi-line
        # or compound one gets a line of its own
        if simple and first.lineno == first.end_lineno:
            edits.append((first.lineno, first.col_offset, first.col_offset,
                          "%s = %s; " % (new, name)))
        else:
            inserts.append((first.lineno, "%s%s = %s" % (indent, new, name)))
    if not edits and not inserts:
        return None
    text = _rename_text(text, edits)
    out = text.split("\n")
    shifted = []
    for line, stmt in sorted(inserts, reverse=True):
        out.insert(line - 1, stmt)
        shifted.append(line)
    return "\n".join(out), new, sorted(shifted)
