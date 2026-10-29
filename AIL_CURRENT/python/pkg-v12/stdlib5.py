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
* struct.pack / unpack / calcsize / unpack_from / pack_into over integer, x, ?, c and s formats (prelude_struct.py).
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
         'random', 'string', 'io', 'statistics', 'typing', 'struct')


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
# struct
# ---------------------------------------------------------------------------------------------------------------
STRUCT_FUNCTIONS = {'pack': '_ail_st_pack', 'unpack': '_ail_st_unpack', 'calcsize': '_ail_st_calcsize',
                    'unpack_from': '_ail_st_unpack_from', 'pack_into': '_ail_st_pack_into'}
STRUCT_FORMAT_ARG = {'pack': 0, 'unpack': 0, 'calcsize': 0, 'unpack_from': 0, 'pack_into': 0}
STRUCT_CODES = 'x?bBhHiIlLqQcs'
STRUCT_SPACE = ' \t\n\r\x0b\x0c'


def struct_format_error(fmt):
    """A reason the literal format string `fmt` is not built, or None. CPython's standard sizes only, with an
    explicit byte-order prefix ('@'/no prefix aligns to the C compiler's layout, which this is not)."""
    if not fmt or fmt[0] not in '<>=!':
        return ("the format string must start with '<', '>', '=' or '!': native alignment (the default or '@') "
                "is not built")
    i = 1
    while i < len(fmt):
        while i < len(fmt) and fmt[i] in STRUCT_SPACE:
            i += 1
        if i >= len(fmt):
            break
        while i < len(fmt) and fmt[i].isdigit():
            i += 1
        if i >= len(fmt):
            return 'the repeat count at the end of the format string has no code'
        code = fmt[i]
        i += 1
        if code not in STRUCT_CODES:
            return ("format code %r is not built; use an integer code (b B h H i I l L q Q), x, ?, c or s"
                    % code)
    return None


def _scope_bindings(body):
    """The names a scope binds: assignments and definitions in `body`, not inside a nested function or class."""
    names = set()

    def visit(node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
            return
        if isinstance(node, ast.Lambda):
            return
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            names.add(node.id)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.name != '*':
                    names.add(alias.asname or alias.name.split('.')[0])
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
        elif isinstance(node, ast.MatchAs) and node.name:
            names.add(node.name)
        elif isinstance(node, ast.MatchStar) and node.name:
            names.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            names.add(node.rest)
        for child in ast.iter_child_nodes(node):
            visit(child)
    for statement in body:
        visit(statement)
    return names


def _argument_names(arguments):
    out = {arg.arg for arg in list(arguments.posonlyargs) + list(arguments.args) + list(arguments.kwonlyargs)}
    if arguments.vararg is not None:
        out.add(arguments.vararg.arg)
    if arguments.kwarg is not None:
        out.add(arguments.kwarg.arg)
    return out


def _scope_declarations(body):
    """The `global` and `nonlocal` names declared in a scope, not inside a nested function or class."""
    glob, nonloc = set(), set()

    def visit(node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            return
        if isinstance(node, ast.Global):
            glob.update(node.names)
        elif isinstance(node, ast.Nonlocal):
            nonloc.update(node.names)
        for child in ast.iter_child_nodes(node):
            visit(child)
    for statement in body:
        visit(statement)
    return glob, nonloc


class _RenameNames(ast.NodeTransformer):
    """Rename a set of identifiers in place (every binding and every use). Attribute names and keyword names are
    not identifiers, so `o.error` and `f(error=1)` keep their spelling."""

    def __init__(self, mapping):
        self.mapping = mapping

    def name(self, text):
        return self.mapping.get(text, text)

    def visit_Name(self, node):
        node.id = self.name(node.id)
        return node

    def visit_arg(self, node):
        node.arg = self.name(node.arg)
        return self.generic_visit(node)

    def visit_FunctionDef(self, node):
        node.name = self.name(node.name)
        return self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        node.name = self.name(node.name)
        return self.generic_visit(node)

    def visit_ClassDef(self, node):
        node.name = self.name(node.name)
        return self.generic_visit(node)

    def visit_alias(self, node):
        local = node.asname or node.name.split('.')[0]
        if local in self.mapping:
            node.asname = self.mapping[local]
        return node

    def visit_Global(self, node):
        node.names = [self.name(each) for each in node.names]
        return node

    def visit_Nonlocal(self, node):
        node.names = [self.name(each) for each in node.names]
        return node

    def visit_ExceptHandler(self, node):
        if node.name:
            node.name = self.name(node.name)
        return self.generic_visit(node)

    def visit_MatchAs(self, node):
        if node.name:
            node.name = self.name(node.name)
        return self.generic_visit(node)

    def visit_MatchStar(self, node):
        if node.name:
            node.name = self.name(node.name)
        return self.generic_visit(node)

    def visit_MatchMapping(self, node):
        if node.rest:
            node.rest = self.name(node.rest)
        return self.generic_visit(node)


class _HideNames(ast.NodeTransformer):
    """Replace a load of a name the prelude would otherwise put in the program's global namespace, when the load
    has no binding of its own, by a call that raises CPython's NameError."""

    def __init__(self, hidden, raise_name, module_bindings):
        self.hidden = hidden
        self.raise_name = raise_name
        self.module_bindings = module_bindings
        self.scopes = [('module', set(module_bindings), set(), set())]

    def bound(self, text):
        for index in range(len(self.scopes) - 1, -1, -1):
            kind, local, glob, nonloc = self.scopes[index]
            if kind == 'module':
                return text in local
            if text in glob:
                return text in self.module_bindings
            if kind == 'class' and index != len(self.scopes) - 1:
                continue
            if text in local or text in nonloc:
                return True
        return text in self.module_bindings

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load) and node.id in self.hidden and not self.bound(node.id):
            call = ast.Call(func=name(self.raise_name), args=[ast.Constant(node.id)], keywords=[])
            return ast.copy_location(call, node)
        return node

    def function(self, node, arguments, body):
        for each in node.decorator_list:
            self.visit(each)
        for each in list(arguments.defaults) + [d for d in arguments.kw_defaults if d is not None]:
            self.visit(each)
        glob, nonloc = _scope_declarations(body)
        local = _argument_names(arguments) | _scope_bindings(body)
        local -= glob
        local -= nonloc
        self.scopes.append(('function', local, glob, nonloc))
        node.body = [self.visit(statement) for statement in body]
        self.scopes.pop()
        return node

    def visit_FunctionDef(self, node):
        return self.function(node, node.args, node.body)

    def visit_AsyncFunctionDef(self, node):
        return self.function(node, node.args, node.body)

    def visit_Lambda(self, node):
        self.scopes.append(('function', _argument_names(node.args), set(), set()))
        node.body = self.visit(node.body)
        self.scopes.pop()
        return node

    def visit_ClassDef(self, node):
        for each in list(node.decorator_list) + list(node.bases) + [word.value for word in node.keywords]:
            self.visit(each)
        local = _scope_bindings(node.body)
        self.scopes.append(('class', local, set(), set()))
        node.body = [self.visit(statement) for statement in node.body]
        self.scopes.pop()
        return node

    def comprehension(self, node, elements):
        targets = set()
        for generator in node.generators:
            targets |= _scope_bindings([ast.Expr(value=generator.target)])
        self.scopes.append(('function', targets, set(), set()))
        for index, generator in enumerate(node.generators):
            generator.iter = self.visit(generator.iter)
            generator.target = self.visit(generator.target)
            if index == 0:
                generator.ifs = [self.visit(each) for each in generator.ifs]
        node.generators[-1].ifs = [self.visit(each) for each in node.generators[-1].ifs]
        for element in elements:
            self.visit(element)
        self.scopes.pop()
        return node

    def visit_ListComp(self, node):
        return self.comprehension(node, [node.elt])

    def visit_SetComp(self, node):
        return self.comprehension(node, [node.elt])

    def visit_GeneratorExp(self, node):
        return self.comprehension(node, [node.elt])

    def visit_DictComp(self, node):
        return self.comprehension(node, [node.key, node.value])


def _prelude_names(tree):
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names


def run_struct(tree, text, source):
    binder = take_imports(tree, 'struct', set(STRUCT_FUNCTIONS) | {'error'},
                          unknown='pack, unpack, calcsize, unpack_from and pack_into are built')
    if not binder:
        return
    prelude_tree = ast.parse(prelude('struct'))
    prelude_names = _prelude_names(prelude_tree)
    base = '_ail_s45_'
    prefix = base
    count = 0
    while prefix in source:
        count += 1
        prefix = '_ail_s45_%d_' % count
    mapped = {each: prefix + each for each in prelude_names}
    _RenameNames(mapped).visit(prelude_tree)
    functions = {each: mapped[each] for each in STRUCT_FUNCTIONS.values()}
    raise_name = mapped['_ail_st_name_error']
    hidden = set(prelude_names) | {'error'}

    user_bindings = _scope_bindings(tree.body)
    for each in [name for name in binder.names if name in user_bindings]:
        del binder.names[each]          # a later `error = ...` (or `def error`) is the binding CPython uses
    module_bindings = set(user_bindings) | set(binder.aliases)
    module_bindings.update(each for each, value in binder.names.items() if value in hidden)
    _HideNames(hidden, raise_name, module_bindings).visit(tree)

    def fix(node):
        attr = binder.attr(node.func) if isinstance(node, ast.Call) else binder.attr(node)
        if attr == 'error':
            return name(mapped['_AilStructError'])
        if attr in STRUCT_FUNCTIONS:
            if not isinstance(node, ast.Call):
                refuse(node, 'struct.%s used as a value is not built' % attr)
            args = [Replace(fix).visit(arg) for arg in node.args]
            keywords = [Replace(fix).visit(word) for word in node.keywords]
            if keywords:
                refuse(node, 'struct.%s does not take keyword arguments' % attr)
            where = STRUCT_FORMAT_ARG[attr]
            if len(args) <= where or not isinstance(args[where], ast.Constant) or not isinstance(
                    args[where].value, str):
                refuse(node, 'struct.%s: the format string must be a literal string' % attr)
            literal = args[where]
            why = struct_format_error(literal.value)
            if why is not None:
                refuse(literal, 'struct.%s: %s' % (attr, why))
            if attr == 'pack' or attr == 'pack_into':
                start = 1 if attr == 'pack' else 3
                values = ast.Tuple(elts=list(args[start:]), ctx=ast.Load())
                packed = list(args[:start]) + [values]
                return ast.Call(func=name(functions[STRUCT_FUNCTIONS[attr]]), args=packed, keywords=[])
            return ast.Call(func=name(functions[STRUCT_FUNCTIONS[attr]]), args=args, keywords=keywords)
        return None
    tree.body = [Replace(fix).visit(stmt) for stmt in tree.body]
    for alias in [each for each, handled in binder.names.items() if handled == 'error']:
        del binder.names[alias]
    leftover(tree, binder, 'pack, unpack, calcsize, unpack_from and pack_into are built; '
                           'the Struct class, iter_unpack, the float formats and n/N/P are not')
    ast.fix_missing_locations(prelude_tree)
    text.append(ast.unparse(prelude_tree) + '\n')


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
                    'string', 'io', 'statistics', 'struct'}):
        return source
    text = []
    changed = False
    try:
        before = ast.dump(tree)
        if 'fractions' in mods:
            run_fractions(tree, text)
        if 'struct' in mods:
            run_struct(tree, text, source)
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
