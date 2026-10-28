"""Library batch 5: `fractions`, `enum`, `namedtuple` / `NamedTuple`, `random.Random`, ... lowered onto what the compiler builds.

One entry point, `rewrite_text(source, notes)`, run from ail_syntax.python_surface on the program text before the
batch-4 and collections passes. A program that imports none of the modules is returned as it was written (the same
string), so its C does not change. Every use is either lowered to code that produces what CPython 3.12 produces or
refused here by name (`module.name: why`, with what to write instead): a refusal leaves the program as written and
adds a `note:` line, as stdlib4 does.

The classes (Fraction, the enum bases, ...) are ordinary Python source (prelude_*.py, importable by CPython for the
differential tests) added to the program after its imports; they use operator methods, so a program using them is
built on the general path, whose runtime dispatches operator methods by class (dunderrt.py).

* fractions: Fraction (prelude_fraction.py).
* enum: Enum, IntEnum, StrEnum, auto, unique (enumlib.py).
* collections.namedtuple, typing.NamedTuple, collections.ChainMap (ntlib.py).
* random.Random(seed) (randlib.py).
* keyword, string constants, calendar, abc, array, io.StringIO, statistics.fmean (smalllib5.py).
"""
import ast
import sys
from pathlib import Path

_here = str(Path(__file__).parent)
if _here not in sys.path:
    sys.path.insert(0, _here)

from stdlib4 import Refused, refuse

HERE = Path(__file__).parent

# a word of the program text that can mean one of the modules (the quick test before parsing)
WORDS = ('fractions', 'enum', 'namedtuple', 'NamedTuple', 'ChainMap', 'keyword', 'calendar', 'abc', 'array',
         'random', 'string', 'io', 'statistics', 'typing', 'argparse', 'tempfile')


def prelude(name):
    """The source of prelude_<name>.py without its leading comment block."""
    lines = (HERE / ('prelude_%s.py' % name)).read_text(encoding='utf-8').splitlines()
    start = 0
    while start < len(lines) and (lines[start].startswith('#') or not lines[start].strip()):
        start += 1
    return '\n'.join(lines[start:]) + '\n'


class Binder:
    """What a program calls the names of one module: `import m [as a]` and `from m import x [as y]`."""

    def __init__(self, module):
        self.module = module
        self.aliases = set()
        self.names = {}                 # local name -> attribute
        self.first = None               # the first import node, for a refusal's line

    def __bool__(self):
        return bool(self.aliases or self.names)

    def attr(self, node):
        """The attribute of the module that `node` names (`m.x`, `a.x`, a from-imported `y`), else None."""
        if isinstance(node, ast.Name) and node.id in self.names:
            return self.names[node.id]
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in self.aliases:
            return node.attr
        return None


def take_imports(tree, module, handled, whole=True, unknown=None):
    """Remove from the top level of `tree` the imports of `module` this pass handles. Names in `handled` are
    removed from `from module import ...` (the rest stays unless `whole`, which refuses a name that is not
    handled); `import module` is removed when `whole`. Returns the Binder."""
    binder = Binder(module)
    body = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            rest = []
            for alias in node.names:
                if alias.name == module:
                    binder.aliases.add(alias.asname or alias.name)
                    binder.first = binder.first or node
                    if not whole:
                        rest.append(alias)
                else:
                    rest.append(alias)
            if rest:
                node.names = rest
                body.append(node)
            continue
        if isinstance(node, ast.ImportFrom) and not node.level and node.module == module:
            rest = []
            for alias in node.names:
                if alias.name == '*':
                    refuse(node, 'from %s import *: name what you use' % module)
                if alias.name in handled:
                    binder.names[alias.asname or alias.name] = alias.name
                    binder.first = binder.first or node
                elif whole:
                    refuse(node, '%s.%s is not built%s' % (module, alias.name, (': ' + unknown) if unknown else ''))
                else:
                    rest.append(alias)
            if rest:
                node.names = rest
                body.append(node)
            continue
        body.append(node)
    tree.body = body
    return binder


def peek_imports(tree, module):
    """The Binder of `module`'s names in the program, the imports left in place."""
    binder = Binder(module)
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == module:
                    binder.aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module == module:
            for alias in node.names:
                binder.names[alias.asname or alias.name] = alias.name
    return binder


def shake(source, roots):
    """The top-level definitions of the prelude `source` that the names in `roots` reach (a definition is reached
    when another kept one mentions its name), in source order."""
    module = ast.parse(source)
    defs = {}
    for node in module.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            defs[node.name] = node
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            defs[node.targets[0].id] = node
    keep = set()
    todo = [r for r in roots if r in defs]
    while todo:
        n = todo.pop()
        if n in keep:
            continue
        keep.add(n)
        for each in ast.walk(defs[n]):
            if isinstance(each, ast.Name) and each.id in defs and each.id not in keep:
                todo.append(each.id)
    return '\n\n'.join(ast.unparse(node) for node in module.body
                        if (isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in keep) or (
                            isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                            and node.targets[0].id in keep)) + '\n'


def imported_modules(tree):
    """The top-level module names the program imports."""
    out = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            out.update(a.name.split('.')[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            out.add(node.module.split('.')[0])
    return out


def leftover(tree, binder, what, only=None):
    """Refuse the first use of a name of the module that is still in the tree (only the names in `only`, when given:
    the module has other names that other passes build)."""
    for each in ast.walk(tree):
        found = binder.attr(each)
        if found is not None and (only is None or found in only):
            refuse(each, '%s.%s used here is not built: %s' % (binder.module, found, what))
        if only is None and isinstance(each, ast.Name) and isinstance(each.ctx, ast.Load) and each.id in binder.aliases:
            refuse(each, '%s used as a value is not built' % binder.module)


def add_once(text, chunk):
    """Add the prelude `chunk` to the list unless it is there already."""
    if chunk not in text:
        text.append(chunk)


def insert_after_imports(tree, text):
    """Add the source `text` (classes and functions) after the program's imports and docstring."""
    added = ast.parse(text).body
    index = 0
    while index < len(tree.body) and (isinstance(tree.body[index], (ast.Import, ast.ImportFrom)) or (
            isinstance(tree.body[index], ast.Expr) and isinstance(tree.body[index].value, ast.Constant))):
        index += 1
    tree.body[index:index] = added


class Replace(ast.NodeTransformer):
    """Replace expression nodes: `fn(node)` gives the new node or None to keep descending."""

    def __init__(self, fn):
        self.fn = fn

    def visit(self, node):
        if isinstance(node, ast.expr):
            new = self.fn(node)
            if new is not None:
                return ast.copy_location(new, node)
        return super().visit(node)


def name(identifier, ctx=None):
    return ast.Name(id=identifier, ctx=ctx or ast.Load())


def call(func, args):
    return ast.Call(func=func, args=list(args), keywords=[])


# ---------------------------------------------------------------------------------------------------------------
# fractions
# ---------------------------------------------------------------------------------------------------------------
def run_fractions(tree, text):
    binder = take_imports(tree, 'fractions', {'Fraction'}, unknown='Fraction is the one name of the module that is built')
    if not binder:
        return
    for each in ast.walk(tree):
        if isinstance(each, (ast.FunctionDef, ast.ClassDef)) and each.name == 'Fraction' or (
                isinstance(each, ast.Name) and each.id == 'Fraction' and not isinstance(each.ctx, ast.Load)):
            refuse(binder.first, 'the program binds the name Fraction itself and also imports it; rename one')

    def fix(node):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and binder.attr(node.func.value) == 'Fraction':
            if node.func.attr == 'from_float' and len(node.args) == 1 and not node.keywords:
                return call(name('Fraction'), node.args)
            refuse(node, 'Fraction.%s is not built: Fraction(x) takes an int, a float, a str or a Fraction' % node.func.attr)
        if binder.attr(node) == 'Fraction':
            return name('Fraction')
        return None
    tree.body = [Replace(fix).visit(stmt) for stmt in tree.body]
    binder.names.pop('Fraction', None)          # the class itself is now an ordinary name of the program
    leftover(tree, binder, 'Fraction(a, b) is the form that is built')
    text.append(prelude('fraction'))


# ---------------------------------------------------------------------------------------------------------------
def rewrite_text(source, notes=None):
    """The program text with the batch-5 modules lowered; the source as written (and `notes` filled) when a use is
    not built."""
    if not any(word in source for word in WORDS):
        return source
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    mods = imported_modules(tree)
    if not (mods & {'fractions', 'enum', 'collections', 'typing', 'random', 'keyword', 'calendar', 'abc', 'array',
                    'string', 'io', 'statistics', 'argparse', 'tempfile'}):
        return source
    text = []
    changed = False
    try:
        before = ast.dump(tree)
        if 'fractions' in mods:
            run_fractions(tree, text)
        if 'enum' in mods:
            import enumlib
            enumlib.run(tree, text)
        if mods & {'collections', 'typing'}:
            import ntlib
            ntlib.run(tree, text)
        if 'random' in mods:
            import randlib
            randlib.run(tree, text)
        if mods & {'keyword', 'calendar', 'abc', 'array', 'string', 'io', 'statistics'}:
            import smalllib5
            smalllib5.run(tree, text, mods)
        if 'argparse' in mods:
            import argparselib
            argparselib.run(tree, text)
        if 'tempfile' in mods:
            import tempfilelib
            tempfilelib.run(tree, text)
        changed = ast.dump(tree) != before or bool(text)
        if not changed:
            return source
        if text:
            insert_after_imports(tree, '\n\n'.join(text))            # in the order they were added
        ast.fix_missing_locations(tree)
        out = ast.unparse(tree)
    except Refused as exc:
        if notes is not None:
            notes.append((exc.line, exc.text))
        return source
    except (AttributeError, KeyError, IndexError, TypeError, ValueError, RecursionError) as exc:
        if notes is not None:
            notes.append((1, 'the batch-5 library rewrite could not handle this program (%s: %s); simplify the use or '
                          'report it' % (type(exc).__name__, exc)))
        return source
    return out.rstrip('\n') + '\n'
