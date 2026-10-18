"""Library batch 4: `csv`, `datetime`, ... lowered onto what the compiler builds.

Two entry points. `rewrite_text(source, notes)` runs from ail_syntax.python_surface on the program text
before the other source passes (collib, tuplib), so the tuple and collection passes see ordinary code, and
the helper functions this pass appends to the program go through the same passes as the program itself.
`rewrite(tree, Unsupported)` runs from pyfunc on the parsed module (the forms that need no import and no
other pass: smalllib.py).

A program that imports none of these modules is not touched, so its C does not change. Every use is either
lowered to code that produces what CPython 3.12 produces or refused here by name (`module.name: why`, with
what to write instead): a refusal leaves the program as written and adds a `note:` line, and the import the
compiler then meets is reported by its first note (ail_chatgpt._python_notes).

* csv: see csvlib.py.
* datetime: see dtlib.py.
* int.bit_length() / bit_count(): see smalllib.py.
"""
import ast
import sys
from pathlib import Path

_here = str(Path(__file__).parent)
if _here not in sys.path:
    sys.path.insert(0, _here)

import stdlib3

TEXT_MODULES = ('csv', 'datetime')
# modules that are named and refused, with what to write instead (module -> text; the text starts with the module)
UNBUILT = {
    'zoneinfo': 'zoneinfo: a named time zone needs the tz database (and its rules), which is not built, so use a fixed '
                'offset: datetime.timezone(datetime.timedelta(hours=9), "JST"), or datetime.timezone.utc',
    'decimal': 'decimal: Decimal needs decimal arithmetic with a context precision and rounding modes, which is not '
               'built, so keep money as integers scaled by 100 (cents) and print them with divmod, or use a float with '
               'round() / f"{x:.2f}", or fractions.Fraction for exact rational arithmetic',
}


class Refused(Exception):
    def __init__(self, line, text):
        super().__init__(text)
        self.line, self.text = line, text


def refuse(node, text):
    raise Refused(getattr(node, 'lineno', None) or 1, text)


def inject(tree, text):
    """Add helper functions written in Python syntax to the program (AST level, from pyfunc): run through
    the same surface pass as the program itself (return annotations become the `__ail_checked_*` forms),
    marked as written by the rewrite, placed after the imports."""
    from iterlower import _mark
    surface = sys.modules.get('ail_syntax')
    if surface is None:
        import importlib.util
        path = Path(__file__).resolve().parents[2] / 'ail_syntax.py'
        spec = importlib.util.spec_from_file_location('ail_syntax', path)
        surface = importlib.util.module_from_spec(spec)
        sys.modules['ail_syntax'] = surface
        spec.loader.exec_module(surface)
    module = ast.parse(surface.python_surface(text))
    for stmt in module.body:
        _mark(stmt)
        for each in ast.walk(stmt):
            if 'lineno' in getattr(each, '_attributes', ()):
                each.lineno = each.end_lineno = 1
                each.col_offset = each.end_col_offset = 0
    body = tree.body
    index = 0
    while index < len(body) and (isinstance(body[index], (ast.Import, ast.ImportFrom))
                                 or (isinstance(body[index], ast.Expr)
                                     and isinstance(body[index].value, ast.Constant))):
        index += 1
    tree.body = body[:index] + module.body + body[index:]


class Imports(stdlib3.Imports):
    """The names a program binds to the batch-4 modules, found at the top level."""

    def __init__(self, tree, modules):
        self.aliases = {}          # local name -> module
        self.names = {}            # local name -> (module, attribute)
        self.nodes = []
        body = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                rest = []
                for alias in node.names:
                    if alias.name in modules:
                        self.aliases[alias.asname or alias.name] = alias.name
                    else:
                        rest.append(alias)
                if len(rest) != len(node.names):
                    self.nodes.append(node)
                    if rest:
                        node.names = rest
                        body.append(node)
                    continue
            elif isinstance(node, ast.ImportFrom) and not node.level and node.module in modules:
                for alias in node.names:
                    if alias.name == '*':
                        refuse(node, 'from %s import *: name what you use' % node.module)
                    self.names[alias.asname or alias.name] = (node.module, alias.name)
                self.nodes.append(node)
                continue
            body.append(node)
        tree.body = body


LEFT_NOTE = {
    'csv': 'csv.reader / DictReader over sys.stdin or a list of lines and csv.writer / DictWriter to '
           'sys.stdout are built, where the reader is assigned to a name, iterated by a for statement or '
           'comprehension, or passed to next() / list()',
    'datetime': 'see the reference for the datetime forms that are built',
}


def leftovers(tree, imports):
    """Name the first use of one of the modules' names that is still in the tree."""
    for each in ast.walk(tree):
        if isinstance(each, ast.Attribute):
            found = imports.resolve(each)
            if found is not None:
                refuse(each, '%s.%s used here is not built: %s' % (found[0], found[1], LEFT_NOTE.get(found[0], '')))
        elif isinstance(each, ast.Name) and isinstance(each.ctx, ast.Load) and each.id in imports.names:
            module, attr = imports.names[each.id]
            refuse(each, '%s.%s used here is not built: %s' % (module, attr, LEFT_NOTE.get(module, '')))
        elif isinstance(each, ast.Name) and isinstance(each.ctx, ast.Load) and each.id in imports.aliases:
            refuse(each, '%s used as a value is not built' % imports.aliases[each.id])


def rewrite_text(source, notes=None):
    """The program text with the batch-4 modules lowered; the source as written (and `notes` filled) when a
    use is not built."""
    if not any(name in source for name in TEXT_MODULES + tuple(UNBUILT) + ('time',)):
        return source
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    if not any(isinstance(n, (ast.Import, ast.ImportFrom)) for n in tree.body):
        return source
    for node in tree.body:
        names = [a.name.split('.')[0] for a in node.names] if isinstance(node, ast.Import) else (
            [node.module.split('.')[0]] if isinstance(node, ast.ImportFrom) and node.module and not node.level else [])
        for name in names:
            if name in UNBUILT:
                if notes is not None:
                    notes.append((node.lineno, UNBUILT[name]))
                return source
    imports = Imports(tree, TEXT_MODULES)
    import timelib
    time_on = "time" in source and timelib.uses_any(tree, bool(imports))
    if not imports and not time_on:
        return source
    helpers = []
    time_used = set()
    try:
        if time_on:
            import dtlib
            timelib.run(tree, time_used, dtlib.rt_name)
        for alias in list(imports.aliases) + list(imports.names):
            if stdlib3.binds(tree, alias):
                refuse(tree.body[0] if tree.body else tree, '%s is also bound by the program itself; rename it '
                       '(the name stands for an imported module here)' % alias)
        modules = imports.modules()
        if 'csv' in modules:
            import csvlib
            csvlib.Csv(imports, tree, helpers).run()
        if 'datetime' in modules:
            import dtlib
            dtlib.rewrite(imports, tree, helpers, time_used)
        elif time_used:
            import dtlib
            dtlib.attach_only(tree, helpers, time_used)
        leftovers(tree, imports)
        # the helper functions go in after the imports, before the program's own definitions
        added = []
        for chunk in helpers:
            added.extend(ast.parse(chunk).body)
        index = 0
        while index < len(tree.body) and (isinstance(tree.body[index], (ast.Import, ast.ImportFrom)) or (
                isinstance(tree.body[index], ast.Expr) and isinstance(tree.body[index].value, ast.Constant))):
            index += 1
        tree.body[index:index] = added
        ast.fix_missing_locations(tree)
        text = ast.unparse(tree)
    except Refused as exc:
        if notes is not None:
            notes.append((exc.line, exc.text))
        return source
    except (AttributeError, KeyError, IndexError, TypeError, ValueError, RecursionError) as exc:
        if notes is not None:
            notes.append((1, 'the library rewrite could not handle this program (%s: %s); simplify the use or '
                          'report it' % (type(exc).__name__, exc)))
        return source
    return text.rstrip('\n') + '\n'


def rewrite(tree, Unsupported):
    """Lower the forms that need no other source pass in `tree` in place (smalllib: bit_length, `in` over a
    display of constants; statlib: statistics); returns whether anything changed."""
    stdlib3._Unsupported = Unsupported
    import smalllib
    try:
        changed = smalllib.rewrite(tree, inject)
        if any(isinstance(n, (ast.Import, ast.ImportFrom)) for n in tree.body):
            import statlib
            changed = statlib.rewrite(tree, inject) or changed
        return changed
    except Refused as exc:
        error = Unsupported(exc.text)
        error.source_line = exc.line
        raise error
