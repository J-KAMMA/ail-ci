"""G1 + G2: Python-syntax programs made of several files, packages included
(docs/design/GENERAL_PURPOSE.md s1, G1 and G2).

`merge_program` reads the entry file and every module it imports from the search path (the entry
file's directory, then the `AIL_PATH` directories, which mirror `PYTHONPATH`) and returns ONE Python
module text with the same behaviour as CPython running `python3 entry.py`:

* a module is `m.py` / `m.ail` (Python syntax); a package is a directory `p/` with an
  `__init__.py` (or `__init__.ail`), or, as in CPython 3.12, a directory without one (a namespace
  package: no body, and portions in several search directories are one package);
* `import p.m`, `import p.m as x`, `from p import m`, `from p.m import f`, `from . import m`,
  `from .m import f`, `from .. import y` and `from m import *` (honouring `__all__` and the
  underscore rule) are understood; parent packages run before their children, each module body runs
  once, spliced in at its first import, in CPython's order (depth first);
* top-level functions and variables of an imported module `p.m` are renamed `p__m__name`; classes
  keep their names (a class name is printed by repr, and it is refused when two modules define the
  same one); the entry module keeps all its names;
* module state is shared the way CPython shares it: there is one variable per module global, so a
  function that says `global x`, a module that writes `m.x = v`, and every reader of `m.x` see the
  same variable. `from m import x` copies the value at that moment, so a global that changes after
  the import gets its own copy in the importing module (a "snapshot");
* `__name__` is `"__main__"` in the entry module and the dotted module name elsewhere; an
  `if __name__ == "__main__":` in an imported module is removed;
* a program with no import of a local module is not touched at all (the caller gets None), so
  single-file programs compile to the same C as before.

A local import inside a function (the usual way to break an import cycle) is moved to the module's top
level when the modules it runs have no side effects at import time (only definitions and constants); the
function then reads the name as a module alias. Otherwise it is refused, naming the effect's file:line.

Everything this does not model is refused by name with a `write instead:` hint: imports in a class body,
condition or `try` and function-level imports of a module with effects, a module used as a value, relative imports in the entry file, a submodule attribute read
before the import that binds it, names rebound in a way that cannot be told apart after the merge,
and import cycles that CPython only survives through partly initialised modules. (`importlib` and
`__import__` are not modelled by the front end and are refused there.)
"""
import ast
import builtins
import collections
import copy
import itertools
import operator
import os
import sys
from pathlib import Path

# modules the compiler models itself; a sibling `.ail` in the brace syntax never shadows them
MODELLED = frozenset(('math', 'sys', 'collections', 'itertools', 'functools', 'heapq', 'bisect', 're', 'json',
                      'random', 'dataclasses', 'typing', 'time', 'os', 'string', 'operator', '__future__'))
STDLIB = frozenset(getattr(sys, 'stdlib_module_names', ())) | MODELLED
BUILTINS = frozenset(dir(builtins))
MODULE_DUNDERS = frozenset(('__file__', '__package__', '__path__', '__spec__', '__loader__', '__cached__',
                            '__builtins__'))
NEVER = 10 ** 9
_UNKNOWN = object()                     # a module-level name bound to something the compiler cannot evaluate


class _Unfoldable(Exception):
    pass


class _Raises(Exception):
    def __init__(self, node):
        Exception.__init__(self)
        self.node = node
# G5a: standard modules the compiler ships as AIL source over the C FFI (stdlib/*.py). They are searched
# after the entry directory and AIL_PATH, so a program's own `zlib.py` still wins.
BUNDLED_DIR = Path(__file__).resolve().parent / 'stdlib'
# module attributes of a bundled module that name an exception kind the typed path can raise; CPython's
# zlib.error is a class of its own, the compiler spells it RuntimeError (as csv.Error is ValueError)
BUNDLED_NAMES = {('zlib', 'error'): 'RuntimeError'}


class ModuleRefusal(ValueError):
    """A named refusal; `refusal` is (path, line, column, text) as ail_chatgpt._refuse_load prints it."""

    def __init__(self, path, line, column, text):
        super().__init__('%s:%d:%d: %s' % (path, line, column, text))
        self.refusal = (str(path), line, column, text)
        self.source_position = (str(path), line, column)


class Merged:
    def __init__(self, text, positions, notes, names):
        self.text = text
        self.positions = positions      # merged line -> (path, line, column)
        self.notes = notes
        self.names = names              # renamed top-level name -> 'module.name', for messages


def unmangle(text, names):
    """`util__helper` back to `util.helper` in a message that quotes the merged program."""
    if not names:
        return text
    import re
    pattern = re.compile(r'(?<![\w.])(%s)(?!\w)' % '|'.join(map(re.escape, sorted(names, key=len, reverse=True))))
    return pattern.sub(lambda found: names[found.group(1)], text)


def _is_brace_or_sexpr(text):
    from ail_syntax import detect
    import ail_sexpr
    return ail_sexpr.detect(text) or detect(text)


def _uses_file_dunder(tree):
    return any((isinstance(n, ast.Name) and n.id == '__file__')
               or (isinstance(n, ast.Attribute) and n.attr == '__file__') for n in ast.walk(tree))


def _file_dunder_assignment(mod):
    """CPython's implicit module-level `__file__`, as a normal assignment at the start of the body.

    The value is the module's own absolute path (a namespace package has None, as CPython sets
    it); a later user assignment rebinds it and a function-local name shadows it exactly as the
    interpreter's binding does."""
    value = None if mod.kind == 'namespace' else str(mod.path)
    node = ast.Assign(targets=[ast.Name(id='__file__', ctx=ast.Store())], value=ast.Constant(value))
    node.lineno, node.col_offset = 1, 0
    ast.fix_missing_locations(node)
    return node


class Mod:
    def __init__(self, name, path, tree, entry, kind='module', dirs=None):
        self.name = name                # dotted name; '__main__' for the entry
        self.path = path                # the file; for a namespace package, its first directory
        self.tree = tree
        self.entry = entry
        self.kind = kind                # module | package | namespace
        self.dirs = list(dirs or [])    # directories searched for submodules
        self.package = '' if entry else (name if kind != 'module' else name.rpartition('.')[0])
        self.prefix = 'main' if entry else name.replace('.', '__')
        self.all_names = None           # a literal __all__ (list of str), else None
        self.all_dynamic = None         # node of an __all__ the compiler cannot read
        self.imps = {}                  # id(statement) -> Imp, in statement order
        self.kinds = {}                 # own top-level name -> func | class | var | multi
        self.first = {}                 # own top-level name -> index of the first statement binding it
        self.std = {}                   # name bound by a non-local import -> signature
        self.alias = {}                 # name bound by a local import -> ('mod', Mod) | ('member', Mod, original name)
        self.merged = {}                # own top-level name -> merged name
        self.snaps = {}                 # imported name -> merged name of this module's own copy
        self.bound = None               # names bound in the module namespace (None: unknown)
        self.bound_done = False
        self.bound_busy = False
        self.bound_partial = set()
        self.analysed = False
        self.done = False
        self.lazy = {}                  # id(synthetic top-level import) -> the function-level import it stands for
        self.lazy_only = set()          # names bound only by function-level local imports (not module attributes)
        self.pure_cache = False


class Imp:
    """One top-level import statement, resolved."""

    def __init__(self, node):
        self.node = node
        self.local = False
        self.chain = []                 # modules to run, parents first
        self.binds = []                 # (name, ('mod', Mod) | ('member', Mod, orig) | ('std', signature))
        self.members = []               # (Mod, original name) read from a module at import time
        self.stars = []                 # modules star-imported here
        self.star_keys = set()


# ---------------------------------------------------------------- scope scanning

def _defaults(args):
    return args.defaults + [d for d in args.kw_defaults if d is not None]


def _scan_scope(nodes):
    """Names bound directly in a scope (not in nested functions/classes/comprehension targets):
    (stores, global_names, nonlocal_names, sites) where sites lists (name, binding node)."""
    stores, globals_, nonlocals, sites = set(), set(), set(), []

    def bind(name, node):
        stores.add(name)
        sites.append((name, node))

    def walk(node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bind(node.name, node)
            for d in node.decorator_list:
                walk(d)
            if not isinstance(node, ast.ClassDef):
                for d in _defaults(node.args):
                    walk(d)
            return
        if isinstance(node, ast.Lambda):
            for d in _defaults(node.args):
                walk(d)
            return
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            for child in ast.walk(node):          # only walrus targets leak out of a comprehension
                if isinstance(child, ast.NamedExpr) and isinstance(child.target, ast.Name):
                    bind(child.target.id, child)
            return
        if isinstance(node, ast.Name):
            if isinstance(node.ctx, (ast.Store, ast.Del)):
                bind(node.id, node)
            return
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                if a.name != '*':
                    bind(a.asname or a.name.split('.')[0], node)
            return
        if isinstance(node, ast.ExceptHandler) and node.name:
            bind(node.name, node)
        elif isinstance(node, ast.Global):
            globals_.update(node.names)
        elif isinstance(node, ast.Nonlocal):
            nonlocals.update(node.names)
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            bind(node.name, node)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            bind(node.rest, node)
        for child in ast.iter_child_nodes(node):
            walk(child)

    for n in nodes:
        walk(n)
    return stores, globals_, nonlocals, sites


def _function_locals(node):
    body = [node.body] if isinstance(node, ast.Lambda) else node.body
    stores, globals_, nonlocals, _ = _scan_scope(body)
    a = node.args
    params = {x.arg for x in a.posonlyargs + a.args + a.kwonlyargs}
    for extra in (a.vararg, a.kwarg):
        if extra:
            params.add(extra.arg)
    return (stores | params | nonlocals) - globals_, globals_


def _static_main_test(test):
    """'main' for `__name__ == "__main__"`, 'not-main' for `!=`, else None."""
    if (isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.left, ast.Name)
            and test.left.id == '__name__' and isinstance(test.comparators[0], ast.Constant)
            and test.comparators[0].value == '__main__'):
        if isinstance(test.ops[0], ast.Eq):
            return 'main'
        if isinstance(test.ops[0], ast.NotEq):
            return 'not-main'
    return None


def _str_list(node):
    if isinstance(node, (ast.List, ast.Tuple)) and all(
            isinstance(e, ast.Constant) and isinstance(e.value, str) for e in node.elts):
        return [e.value for e in node.elts]
    return None


# ---------------------------------------------------------------- loading and analysis

class Program:
    def __init__(self, entry_path, read):
        self.entry_path = Path(entry_path).resolve()
        self.dir = self.entry_path.parent
        self.read = read
        self.roots = [self.dir]
        for part in os.environ.get('AIL_PATH', '').split(os.pathsep):
            if part and Path(part).is_dir():
                root = Path(part).resolve()
                if root not in self.roots:
                    self.roots.append(root)
        if BUNDLED_DIR.is_dir() and BUNDLED_DIR not in self.roots:
            self.roots.append(BUNDLED_DIR)
        self.mods = {}                  # dotted module name -> Mod
        self.notes = []
        self.entry = None
        self.kept = {}
        self.ext = {}                   # (Mod, attr) -> (writer Mod, node): `m.attr = v` somewhere
        self.top_cache = {}

    def refuse(self, mod, node, text):
        raise ModuleRefusal(mod.path, getattr(node, 'lineno', 1), getattr(node, 'col_offset', 0) + 1, text)

    # -- the search path

    def local_top(self, name):
        """True when `name` (a top-level module name) is provided by the search path."""
        if not name:
            return False
        got = self.top_cache.get(name)
        if got is None:
            got = False
            for d in self.roots:
                if any((d / part).is_file() for part in (name + '.py', name + '.ail', name + '/__init__.py',
                                                          name + '/__init__.ail')):
                    got = True
                    break
                if (d / name).is_dir() and name not in STDLIB:
                    got = True
                    break
            self.top_cache[name] = got
        return got

    def spec(self, fullname, dirs, importer, node):
        """(kind, file, directories) of module `fullname` searched in `dirs`, or None. CPython's order
        in each directory: a regular package, then a module file, then a namespace portion; the
        portions of all directories make one namespace package unless a later directory has the
        module. A regular package beside a module file of the same name is refused as ambiguous."""
        leaf = fullname.rpartition('.')[2]
        top = '.' not in fullname
        portions = []
        for d in dirs:
            inits = [p for p in (d / leaf / '__init__.py', d / leaf / '__init__.ail') if p.is_file()]
            files = [p for p in (d / (leaf + '.py'), d / (leaf + '.ail')) if p.is_file()]
            if inits:
                if len(inits) > 1 or files:
                    self.refuse(importer, node, "import of %r is ambiguous: %s all exist, and CPython would pick the "
                                "package and ignore the others.\n  write instead: delete or rename all but one of them"
                                % (fullname, ', '.join(str(p.relative_to(d)) for p in inits + files)))
                self.check_syntax_file(inits[0], fullname, importer, node, False)
                return 'package', inits[0], [d / leaf]
            kept = [p for p in files if self.check_syntax_file(p, fullname, importer, node, top and leaf in MODELLED)]
            if len(kept) > 1:
                self.refuse(importer, node, "import of %r is ambiguous: %s both exist, and CPython would pick the "
                            ".py file and ignore the .ail one.\n  write instead: delete or rename one of them"
                            % (fullname, ' and '.join(p.name for p in kept)))
            if kept:
                return 'module', kept[0], []
            if (d / leaf).is_dir():
                portions.append(d / leaf)
        if portions and not (top and leaf in STDLIB):
            return 'namespace', None, portions
        return None

    def check_syntax_file(self, path, fullname, importer, node, modelled):
        """True when `path` is a Python-syntax module; False for a brace `.ail` that shadows nothing
        (a modelled standard module); a brace `.ail` otherwise is refused."""
        if path.suffix != '.ail':
            return True
        if not _is_brace_or_sexpr(self.read(path)):
            return True
        if modelled:
            return False
        self.refuse(importer, node, "module %r is %s, which is written in the brace syntax; a Python "
                    "`import` takes Python-syntax modules (.py, or .ail written like Python).\n"
                    "  write instead: rename the module to %s written in Python syntax"
                    % (fullname, path.name, path.with_suffix('.py').name))

    def load(self, fullname, importer, node):
        """The Mod for dotted module `fullname`, loaded with its parents; None when the search path has none."""
        got = self.mods.get(fullname)
        if got is not None:
            return got
        parent_name, _, leaf = fullname.rpartition('.')
        if parent_name:
            parent = self.load(parent_name, importer, node)
            if parent is None:
                return None
            if parent.kind == 'module':
                self.refuse(importer, node, "import of %r: %s is a module (%s), not a package, so it has no "
                            "submodules.\n  write instead: make %s a package (a directory with an __init__.py) "
                            "or import the names from the module itself"
                            % (fullname, parent_name, parent.path.name, parent_name))
            dirs = parent.dirs
        else:
            dirs = self.roots
        found = self.spec(fullname, dirs, importer, node)
        if found is None:
            return None
        kind, path, mdirs = found
        if path is not None and path.resolve() == self.entry_path:
            self.refuse(importer, node, "import of %r would load the entry file a second time as a module "
                        "(CPython runs its body twice).\n  write instead: move the shared code into its own "
                        "module and import that" % fullname)
        if '.' not in fullname and fullname in STDLIB and kind != 'namespace' and (
                path is None or path.resolve().parent != BUNDLED_DIR):
            self.notes.append('note: %s shadows the standard library module %s, as it does in CPython'
                              % (path.name if path.name != '__init__.py' else path.parent.name + '/__init__.py',
                                 fullname))
        if path is None:
            tree = ast.Module(body=[], type_ignores=[])
        else:
            try:
                tree = ast.parse(self.read(path), filename=str(path))
            except SyntaxError as error:
                raise ModuleRefusal(path, error.lineno or 1, error.offset or 1, error.msg)
        mod = Mod(fullname, path if path is not None else mdirs[0], tree, False, kind, mdirs if kind != 'module' else [])
        self.mods[fullname] = mod
        self.drop_main_guards(mod)
        self.take_all(mod)
        self.discover(mod)
        return mod

    def drop_main_guards(self, mod):
        """In an imported module `if __name__ == "__main__":` is false: replace it by its else branch."""
        def flat(body):
            out = []
            for node in body:
                kind = _static_main_test(node.test) if isinstance(node, ast.If) else None
                if kind == 'main':
                    out.extend(flat(node.orelse))
                elif kind == 'not-main':
                    out.extend(flat(node.body))
                else:
                    out.append(node)
            return out
        mod.tree.body = flat(mod.tree.body)

    def take_all(self, mod):
        """A literal `__all__` (assignment, `+=`, `.append`/`.extend` of literals) is read here and its
        statements dropped; any other use of `__all__` leaves everything as written (and a star-import
        of this module is then refused)."""
        names, keep, taken = None, [], []
        for node in mod.tree.body:
            literal = None
            if (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id == '__all__'):
                literal = _str_list(node.value)
                if literal is not None:
                    names = list(literal)
            elif (isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) and node.target.id == '__all__'
                  and isinstance(node.op, ast.Add) and names is not None):
                literal = _str_list(node.value)
                if literal is not None:
                    names += literal
            elif (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                  and isinstance(node.value.func, ast.Attribute) and isinstance(node.value.func.value, ast.Name)
                  and node.value.func.value.id == '__all__' and names is not None and not node.value.keywords
                  and len(node.value.args) == 1):
                if node.value.func.attr == 'extend':
                    literal = _str_list(node.value.args[0])
                    if literal is not None:
                        names += literal
                elif node.value.func.attr == 'append':
                    arg = node.value.args[0]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        literal = [arg.value]
                        names.append(arg.value)
            (taken if literal is not None else keep).append(node)
        offender = next((n for k in keep for n in ast.walk(k) if isinstance(n, ast.Name) and n.id == '__all__'), None)
        if offender is not None:
            mod.all_dynamic = offender
        elif taken:
            mod.tree.body = keep
            mod.all_names = names

    def prepare_entry(self, entry):
        """`if __name__ == "__main__":` in the entry is always taken: when its body holds a local
        import, the block is spliced into the top level, where the import is understood."""
        def holds_local_import(body):
            return any(isinstance(node, (ast.Import, ast.ImportFrom)) and self.is_local_import(node)
                       for stmt in body for node in ast.walk(stmt))

        def flat(body):
            out = []
            for node in body:
                if isinstance(node, ast.If) and _static_main_test(node.test) == 'main' and holds_local_import(node.body):
                    out.extend(flat(node.body))
                else:
                    out.append(node)
            return out
        entry.tree.body = flat(entry.tree.body)

    def is_local_import(self, node):
        if isinstance(node, ast.ImportFrom):
            return bool(node.level) or self.local_top((node.module or '').split('.')[0])
        return any(self.local_top(a.name.split('.')[0]) for a in node.names)

    # -- discovery: which modules does each statement import

    def discover(self, mod):
        self.lift_lazy(mod)
        for node in mod.tree.body:
            if isinstance(node, ast.Import):
                self.d_import(mod, node)
            elif isinstance(node, ast.ImportFrom):
                self.d_from(mod, node)

    def lift_lazy(self, mod):
        """A local import inside a function is moved to the module's top level: a synthetic copy goes
        at the end of the module body (at the start for the entry file) and the statement itself
        becomes `pass`; the function then reads the name as a module-level alias. That is the same
        program as CPython's when the imported modules have no side effects at import time (checked
        when the module is spliced in: see `impure`); any other local import below the top level is
        refused."""
        top = {id(n) for n in mod.tree.body}
        found = []

        def refuse(node, why):
            self.refuse(mod, node, "import of a local module or package below the top level (%s) is not "
                        "supported: CPython runs it when that code runs, and the program is built before it runs.\n"
                        "  write instead: move the import to the top of the file" % why)

        def handle(parent, field, items, index, child, scope, tried):
            if isinstance(child, (ast.Import, ast.ImportFrom)):
                if id(child) in top or not self.is_local_import(child):
                    return
                if isinstance(child, ast.ImportFrom) and child.level and mod.entry:
                    self.absolute(mod, child)       # the entry-file relative-import refusal is specific
                if scope != 'func':
                    if tried:
                        refuse(child, "inside a try block, whose ImportError handler the compiler cannot model")
                    refuse(child, "inside a condition or loop at module level" if scope == 'module'
                           else "inside a class body")
                if tried:
                    refuse(child, "inside a try block, whose ImportError handler the compiler cannot model")
                for a in child.names:
                    name = a.asname or a.name.split('.')[0]
                    if name in BUILTINS:
                        refuse(child, "in a function, binding the builtin name %r: every reader of %r in the "
                               "module would change meaning" % (name, name))
                found.append((items, index, child))
                return
            kind = scope
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                kind, tried = 'func', False
            elif isinstance(child, ast.ClassDef):
                kind = 'class'
            elif isinstance(child, (ast.Try, getattr(ast, 'TryStar', ast.Try))):
                tried = True
            visit(child, kind, tried)

        def visit(node, scope, tried):
            for field, value in ast.iter_fields(node):
                if isinstance(value, list):
                    for index, child in enumerate(value):
                        if isinstance(child, ast.AST):
                            handle(node, field, value, index, child, scope, tried)
                elif isinstance(value, ast.AST):
                    handle(node, field, [value], 0, value, scope, tried)
        visit(mod.tree, 'module', False)
        if not found:
            return
        self.check_init_calls(mod, [n for _, _, n in found])
        synthetic = []
        for items, index, node in found:
            clone = copy.deepcopy(node)
            ast.copy_location(clone, node)
            mod.lazy[id(clone)] = node
            synthetic.append(clone)
            items[index] = ast.copy_location(ast.Pass(), node)
        body = mod.tree.body
        if mod.entry:
            at = 0                    # after the docstring and the leading imports: those run first
            while at < len(body) and (isinstance(body[at], (ast.Import, ast.ImportFrom))
                                      or at == 0 and isinstance(body[at], ast.Expr)
                                      and isinstance(body[at].value, ast.Constant)
                                      and isinstance(body[at].value.value, str)):
                at += 1
            body[at:at] = synthetic
        else:
            body.extend(synthetic)
        others = {n for n in _scan_scope([x for x in body if id(x) not in mod.lazy])[0]}
        for x in ast.walk(mod.tree):
            if isinstance(x, ast.Global):
                others.update(x.names)
        for clone in synthetic:
            mod.lazy_only.update((a.asname or a.name.split('.')[0]) for a in clone.names)
        mod.lazy_only -= others

    def check_init_calls(self, mod, nodes):
        """A function with a function-level import that the module's own top-level code calls (or reaches
        through another function) would run that import while the module is still starting, before the
        point where the merged program has it: refused. A class counts when it is called (`C()`,
        `C.make()`), not when it is only named as a base. (The entry file needs no check: its imports
        go first.)"""
        if mod.entry:
            return
        ids = {id(n) for n in nodes}
        defs = {n.name: n for n in mod.tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}

        def used(node, whole):
            """Name nodes read when `node` runs as part of the module body (`whole`: its function bodies too);
            a class name only when it is called."""
            out = []

            def walk(n, called):
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)) and not whole:
                    for d in (n.decorator_list if not isinstance(n, ast.Lambda) else []) + _defaults(n.args):
                        walk(d, False)
                    return
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                    if called or not isinstance(defs.get(n.id), ast.ClassDef):
                        out.append(n)
                    return
                if isinstance(n, ast.Call):
                    walk(n.func, True)
                    for c in n.args + [k.value for k in n.keywords]:
                        walk(c, False)
                    return
                for c in ast.iter_child_nodes(n):
                    walk(c, called and isinstance(n, (ast.Attribute, ast.Subscript)))
            walk(node, False)
            return out
        tainted = {name for name, n in defs.items() if any(id(x) in ids for x in ast.walk(n))}
        changed = True
        while changed:
            changed = False
            for name, n in defs.items():
                if name not in tainted and any(x.id in tainted for x in used(n, True)):
                    tainted.add(name)
                    changed = True
        if not tainted:
            return
        for n in mod.tree.body:
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                continue
            for x in used(n, False):
                if x.id in tainted:
                    self.refuse(mod, x, "%r is used while %s is still starting, and it (or something it calls) "
                                "has a function-level import of a local module: the compiler runs that import when "
                                "%s has finished starting, so the module would not be there yet.\n"
                                "  write instead: move the import to the top of the file, or call %r from the "
                                "entry file's code" % (x.id, mod.name, mod.name, x.id))

    # -- import-time side effects of a module spliced in by a function-level import

    PURE_DECORATORS = frozenset(('dataclass', 'unique'))

    def reads_state(self, mod, n, skip):
        """`n` reads a value of another local module that may differ between the end of the importing
        module and the first call of the function (`cfg.level`, a `from cfg import level` name), or
        passes a module object around: such a read is an effect of the module body. A name that no
        module rebinds is settled by then, so a default argument may read it."""
        if isinstance(n, ast.Attribute) and id(n) not in skip:
            chain = []
            cur = n
            while isinstance(cur, ast.Attribute):
                skip.add(id(cur))
                chain.append(cur.attr)
                cur = cur.value
            entry = mod.alias.get(cur.id) if isinstance(cur, ast.Name) else None
            if entry is None or entry[0] != 'mod':
                return None
            if isinstance(cur, ast.Name):
                skip.add(id(cur))
            owner = entry[1]
            for index, attr in enumerate(reversed(chain)):
                kind = owner.kinds.get(attr)
                last = index == len(chain) - 1
                if last and not self.mutable(owner, attr) and kind in ('func', 'class', 'var'):
                    return None
                if last and kind is None:
                    found = self.resolve(owner, attr, 0, True)
                    if found[0] == 'var' and not self.mutable(found[1], found[2]):
                        return None
                sub = self.child(owner, attr) if kind is None else None
                if sub is None:
                    return n
                owner = sub
            return None
        if isinstance(n, ast.Name) and id(n) not in skip and isinstance(n.ctx, ast.Load):
            entry = mod.alias.get(n.id)
            if entry is None:
                return None
            if entry[0] == 'mod':
                return n
            kind = entry[1].kinds.get(entry[2])
            if kind in ('func', 'class', 'var') and not self.mutable(entry[1], entry[2]):
                return None
            if kind is None:
                found = self.resolve(mod, n.id, 0, True)
                if found[0] == 'var' and not self.mutable(found[1], found[2]):
                    return None
            return n
        return None

    def ext_names(self, owner):
        return {key for (o, key) in self.ext if o is owner}

    def hooked(self, mod, seen=None):
        """`mod` (or a local module it imports) defines a class hook that runs code when a class is
        created: `__init_subclass__`, `__set_name__`, a metaclass keyword."""
        seen = set() if seen is None else seen
        if mod in seen:
            return None
        seen.add(mod)
        for n in ast.walk(mod.tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in ('__init_subclass__',
                                                                                    '__set_name__'):
                return n
            if isinstance(n, ast.ClassDef) and any(k.arg == 'metaclass' for k in n.keywords):
                return n
        for entry in mod.alias.values():
            bad = self.hooked(entry[1], seen)
            if bad is not None:
                return bad
        return None

    def impure_expr(self, mod, node, env=None):
        """The first sub-expression of `node` that may do something when evaluated (a call, a read of another
        module's state) or may raise (a division by zero, an index out of range, an unbound name), else None.
        The expression is first evaluated here when it only holds constants and names bound to constants; a
        result means it cannot raise, an exception means it does."""
        if node is None:
            return None
        env = self.module_env(mod) if env is None else env
        try:
            self.fold(mod, node, env)
            return None
        except _Raises as exc:
            return exc.node
        except _Unfoldable:
            pass
        return self.check_expr(mod, node, env)

    def module_env(self, mod):
        return collections.ChainMap({})

    # -- constant folding of module-level expressions (to decide whether they can raise)

    FOLD_CALLS = {'range': range, 'len': len, 'list': list, 'tuple': tuple, 'set': set, 'frozenset': frozenset,
                  'dict': dict, 'int': int, 'float': float, 'str': str, 'bool': bool, 'abs': abs, 'min': min,
                  'max': max, 'sum': sum, 'sorted': sorted, 'ord': ord, 'chr': chr}
    FOLD_BINOPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
                   ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow,
                   ast.LShift: operator.lshift, ast.RShift: operator.rshift, ast.BitOr: operator.or_,
                   ast.BitAnd: operator.and_, ast.BitXor: operator.xor}
    FOLD_COMPARE = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt, ast.LtE: operator.le,
                    ast.Gt: operator.gt, ast.GtE: operator.ge, ast.Is: operator.is_, ast.IsNot: operator.is_not,
                    ast.In: lambda a, b: a in b, ast.NotIn: lambda a, b: a not in b}
    FOLD_LIMIT = 10000

    def fold_check(self, value):
        """A value the evaluation may keep: integers that fit 64 bits, containers of bounded size."""
        if isinstance(value, int) and not -(1 << 63) <= value < (1 << 63):
            raise _Unfoldable()
        if isinstance(value, (str, bytes, list, tuple, set, frozenset, dict)) and len(value) > self.FOLD_LIMIT:
            raise _Unfoldable()
        return value

    def fold_apply(self, node, func, *args):
        try:
            return self.fold_check(func(*args))
        except (_Unfoldable, _Raises):
            raise
        except Exception:
            raise _Raises(node)

    def fold(self, mod, node, env):
        """The value of `node` when it is made of constants, names bound to constants, containers, operators,
        comprehensions and total builtins; _Raises if CPython would raise; _Unfoldable if not known."""
        kind = type(node)
        if kind is ast.Constant:
            return self.fold_check(node.value)
        if kind is ast.Name:
            value = env.get(node.id, _UNKNOWN)
            if value is _UNKNOWN:
                raise _Unfoldable()
            return value
        if kind in (ast.Tuple, ast.List, ast.Set):
            items = []
            for e in node.elts:
                if isinstance(e, ast.Starred):
                    raise _Unfoldable()
                items.append(self.fold(mod, e, env))
            if kind is ast.Tuple:
                return tuple(items)
            return self.fold_apply(node, list if kind is ast.List else set, items)
        if kind is ast.Dict:
            if any(k is None for k in node.keys):
                raise _Unfoldable()
            result = {}
            for k, v in zip(node.keys, node.values):
                key, value = self.fold(mod, k, env), self.fold(mod, v, env)
                self.fold_apply(node, result.__setitem__, key, value)
            return result
        if kind is ast.BinOp:
            op = self.FOLD_BINOPS.get(type(node.op))
            left, right = self.fold(mod, node.left, env), self.fold(mod, node.right, env)
            if op is None:
                raise _Unfoldable()
            if isinstance(node.op, (ast.Pow, ast.LShift)) and isinstance(right, int) and abs(right) > 256:
                raise _Unfoldable()
            if isinstance(node.op, ast.Mult) and isinstance(right, int) and isinstance(left, (str, bytes, list, tuple)):
                if len(left) * max(right, 0) > self.FOLD_LIMIT:
                    raise _Unfoldable()
            if isinstance(node.op, ast.Mult) and isinstance(left, int) and isinstance(right, (str, bytes, list, tuple)):
                if len(right) * max(left, 0) > self.FOLD_LIMIT:
                    raise _Unfoldable()
            return self.fold_apply(node, op, left, right)
        if kind is ast.UnaryOp:
            value = self.fold(mod, node.operand, env)
            op = {ast.Not: operator.not_, ast.USub: operator.neg, ast.UAdd: operator.pos,
                  ast.Invert: operator.invert}[type(node.op)]
            return self.fold_apply(node, op, value)
        if kind is ast.BoolOp:
            is_and = isinstance(node.op, ast.And)
            value = None
            for e in node.values:
                value = self.fold(mod, e, env)
                if bool(value) != is_and:
                    break
            return value
        if kind is ast.IfExp:
            return self.fold(mod, node.body if self.fold(mod, node.test, env) else node.orelse, env)
        if kind is ast.Compare:
            left = self.fold(mod, node.left, env)
            result = True
            for op, comparator in zip(node.ops, node.comparators):
                right = self.fold(mod, comparator, env)
                result = self.fold_apply(node, self.FOLD_COMPARE[type(op)], left, right)
                if not result:
                    break
                left = right
            return result
        if kind is ast.Subscript:
            value = self.fold(mod, node.value, env)
            if isinstance(node.slice, ast.Slice):
                parts = [None if p is None else self.fold(mod, p, env)
                         for p in (node.slice.lower, node.slice.upper, node.slice.step)]
                index = slice(*parts)
            else:
                index = self.fold(mod, node.slice, env)
            return self.fold_apply(node, operator.getitem, value, index)
        if kind is ast.JoinedStr:
            out = []
            for part in node.values:
                if isinstance(part, ast.Constant):
                    out.append(part.value)
                    continue
                value = self.fold(mod, part.value, env)
                value = {-1: lambda v: v, 115: str, 114: repr, 97: ascii}[part.conversion](value)
                spec = self.fold(mod, part.format_spec, env) if part.format_spec is not None else ''
                out.append(self.fold_apply(node, format, value, spec))
            return self.fold_check(''.join(out))
        if kind is ast.Call:
            func = node.func
            if (not isinstance(func, ast.Name) or func.id not in self.FOLD_CALLS or func.id in env
                    or func.id in mod.kinds or func.id in mod.alias or func.id in mod.std):
                raise _Unfoldable()
            if any(isinstance(a, ast.Starred) for a in node.args) or any(k.arg is None for k in node.keywords):
                raise _Unfoldable()
            args = [self.fold(mod, a, env) for a in node.args]
            kwargs = {k.arg: self.fold(mod, k.value, env) for k in node.keywords}
            return self.fold_apply(node, self.FOLD_CALLS[func.id], *args, **kwargs)
        if kind in (ast.ListComp, ast.SetComp, ast.DictComp):
            out = []
            self.fold_generators(mod, node, node.generators, 0, env.new_child(), out)
            if kind is ast.ListComp:
                return out
            if kind is ast.SetComp:
                return self.fold_apply(node, set, out)
            result = {}
            for k, v in out:
                self.fold_apply(node, result.__setitem__, k, v)
            return result
        raise _Unfoldable()

    def fold_generators(self, mod, node, generators, depth, env, out):
        if depth == len(generators):
            if isinstance(node, ast.DictComp):
                out.append((self.fold(mod, node.key, env), self.fold(mod, node.value, env)))
            else:
                out.append(self.fold(mod, node.elt, env))
            self.fold_check(out)
            return
        gen = generators[depth]
        if gen.is_async:
            raise _Unfoldable()
        source = self.fold(mod, gen.iter, env if depth else env.parents)
        try:
            items = list(itertools.islice(iter(source), self.FOLD_LIMIT + 1))
        except Exception:
            raise _Raises(gen.iter)
        if len(items) > self.FOLD_LIMIT:
            raise _Unfoldable()
        for item in items:
            inner = env.new_child()
            if not self.fold_target(gen.target, item, inner):
                raise _Unfoldable()
            if all(self.fold(mod, cond, inner) for cond in gen.ifs):
                self.fold_generators(mod, node, generators, depth + 1, inner, out)

    def fold_target(self, target, item, env):
        if isinstance(target, ast.Name):
            env[target.id] = item
            return True
        if isinstance(target, (ast.Tuple, ast.List)) and not any(isinstance(e, ast.Starred) for e in target.elts):
            try:
                values = list(item)
            except Exception:
                return False
            return len(values) == len(target.elts) and all(self.fold_target(t, v, env)
                                                           for t, v in zip(target.elts, values))
        return False

    # -- the expressions that are not folded

    SAFE_CALLS = frozenset(('dataclass', 'field', 'auto', 'namedtuple', 'Enum', 'IntEnum'))
    STD_ATTRS = frozenset(('math.pi', 'math.e', 'math.inf', 'math.tau', 'math.nan', 'sys.maxsize', 'os.sep',
                           'os.linesep'))

    def unhashable_name(self, mod, name):
        for n in mod.tree.body:
            if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in n.targets):
                if isinstance(n.value, (ast.List, ast.Set, ast.Dict, ast.ListComp, ast.SetComp, ast.DictComp)):
                    return True
        return False

    def check_expr(self, mod, node, env):
        """The expression is not a known constant: accept the forms that cannot raise or run code."""
        if node is None or isinstance(node, ast.Constant):
            return None
        kind = type(node)
        if kind is ast.Name:
            if node.id not in env and not hasattr(builtins, node.id):
                return node
            return self.reads_state(mod, node, set())
        if kind is ast.Attribute:
            bad = self.reads_state(mod, node, set())
            if bad is not None:
                return bad
            chain, cur = [], node
            while isinstance(cur, ast.Attribute):
                chain.append(cur.attr)
                cur = cur.value
            if not isinstance(cur, ast.Name):
                return node
            entry = mod.alias.get(cur.id)
            if entry is not None and entry[0] == 'mod':
                return None
            if cur.id in mod.std and cur.id not in mod.kinds and '.'.join([cur.id] + chain[::-1]) in self.STD_ATTRS:
                return None
            if len(chain) == 1 and mod.kinds.get(cur.id) == 'class':
                for c in mod.tree.body:
                    if isinstance(c, ast.ClassDef) and c.name == cur.id and not c.keywords:
                        names = {t.id for s in c.body if isinstance(s, ast.Assign) for t in s.targets
                                 if isinstance(t, ast.Name)}
                        names |= {s.target.id for s in c.body if isinstance(s, ast.AnnAssign)}
                        names |= {s.name for s in c.body if isinstance(s, (ast.FunctionDef, ast.ClassDef))}
                        if chain[0] in names:
                            return None
            return node
        if kind in (ast.Tuple, ast.List, ast.Set, ast.Dict):
            parts = node.elts if kind is not ast.Dict else node.values
            if kind is ast.Dict and any(k is None for k in node.keys):
                return node
            keys = node.elts if kind is ast.Set else (node.keys if kind is ast.Dict else [])
            for k in keys:
                if isinstance(k, (ast.List, ast.Set, ast.Dict, ast.ListComp, ast.SetComp, ast.DictComp)):
                    return k
                if isinstance(k, ast.Name) and self.unhashable_name(mod, k.id):
                    return k
            for e in list(keys) + list(parts):
                if isinstance(e, ast.Starred):
                    return e
                bad = self.impure_expr(mod, e, env)
                if bad is not None:
                    return bad
            return None
        if kind in (ast.BoolOp, ast.IfExp) or (kind is ast.UnaryOp and isinstance(node.op, ast.Not)):
            for e in ast.iter_child_nodes(node):
                if isinstance(e, ast.expr):
                    bad = self.impure_expr(mod, e, env)
                    if bad is not None:
                        return bad
            return None
        if kind is ast.Compare and all(isinstance(o, (ast.Eq, ast.NotEq, ast.Is, ast.IsNot)) for o in node.ops):
            for e in [node.left] + node.comparators:
                bad = self.impure_expr(mod, e, env)
                if bad is not None:
                    return bad
            return None
        if kind is ast.JoinedStr:
            for part in node.values:
                if isinstance(part, ast.FormattedValue):
                    if part.format_spec is not None or part.conversion != -1:
                        return part
                    bad = self.impure_expr(mod, part.value, env)
                    if bad is not None:
                        return bad
            return None
        if kind is ast.Lambda:
            for d in _defaults(node.args):
                bad = self.impure_expr(mod, d, env)
                if bad is not None:
                    return bad
            return None
        if kind is ast.Call:
            if not (isinstance(node.func, ast.Name) and node.func.id in self.SAFE_CALLS
                    and env.get(node.func.id, _UNKNOWN) is _UNKNOWN and node.func.id not in mod.kinds and node.func.id not in mod.alias):
                return node
            for a in node.args + [k.value for k in node.keywords]:
                if isinstance(a, ast.Starred) or any(k.arg is None for k in node.keywords):
                    return a
                bad = self.impure_expr(mod, a, env)
                if bad is not None:
                    return bad
            return None
        return node

    def annotation_bad(self, mod, ann, env):
        """A def/variable annotation is evaluated when the definition runs: accept names, dotted names,
        subscripts of the standard generics and `|`."""
        if ann is None or isinstance(ann, ast.Constant):
            return None
        if isinstance(ann, ast.Name):
            return None if ann.id in env or hasattr(builtins, ann.id) else ann
        if isinstance(ann, ast.Attribute):
            root = ann
            while isinstance(root, ast.Attribute):
                root = root.value
            return None if isinstance(root, ast.Name) and root.id in env else ann
        if isinstance(ann, ast.Subscript):
            root = ann.value
            if not (isinstance(root, ast.Name) and (root.id in mod.std or root.id in
                                                    ('list', 'dict', 'set', 'tuple', 'frozenset', 'type'))
                    and root.id not in mod.kinds):
                return ann
            elts = ann.slice.elts if isinstance(ann.slice, ast.Tuple) else [ann.slice]
            return next((b for b in (self.annotation_bad(mod, e, env) for e in elts) if b is not None), None)
        if isinstance(ann, ast.BinOp) and isinstance(ann.op, ast.BitOr):
            return self.annotation_bad(mod, ann.left, env) or self.annotation_bad(mod, ann.right, env)
        return ann

    def impure_decorator(self, mod, d, env=None):
        """Only `@dataclass`, `@dataclass(...)` and `@unique` (from the standard library) are known to do
        nothing but build the class or function; any other decorator is a call into code the compiler
        has not read."""
        target = d.func if isinstance(d, ast.Call) else d
        root = target
        while isinstance(root, ast.Attribute):
            root = root.value
        name = target.attr if isinstance(target, ast.Attribute) else getattr(target, 'id', None)
        if (name not in self.PURE_DECORATORS or not isinstance(root, ast.Name) or root.id in mod.kinds
                or root.id in mod.alias):
            return d
        if isinstance(d, ast.Call):
            for a in d.args + [k.value for k in d.keywords]:
                bad = self.impure_expr(mod, a, env)
                if bad is not None:
                    return bad
        return None

    def impure(self, mod):
        """The first top-level statement or expression of `mod` with an effect other than binding names (a
        call, a print, a loop, an assert...) or that can raise (`1 // 0`, `d['k']`, an unbound name),
        else None."""
        if mod.pure_cache is not False:
            return mod.pure_cache
        future = any(isinstance(n, ast.ImportFrom) and n.module == '__future__'
                     and any(a.name == 'annotations' for a in n.names) for n in mod.tree.body)

        def bind_import(node, env):
            imp = mod.imps.get(id(node))
            if imp is not None:
                for name, _ in imp.binds:
                    env[name] = _UNKNOWN
            for a in node.names:
                if a.name == '*':
                    continue
                env[a.asname or a.name.partition('.')[0]] = _UNKNOWN

        def fn(node, env):
            for d in node.decorator_list:
                bad = self.impure_decorator(mod, d, env)
                if bad is not None:
                    return bad
            for d in _defaults(node.args):
                bad = self.impure_expr(mod, d, env)
                if bad is not None:
                    return bad
            if not future:
                a = node.args
                for arg in a.posonlyargs + a.args + a.kwonlyargs + [a.vararg, a.kwarg]:
                    if arg is not None:
                        bad = self.annotation_bad(mod, arg.annotation, env)
                        if bad is not None:
                            return bad
                bad = self.annotation_bad(mod, node.returns, env)
                if bad is not None:
                    return bad
            env[node.name] = _UNKNOWN
            return None

        def assign(target, value, node, env):
            try:
                env[target.id] = self.fold(mod, value, env)
            except (_Unfoldable, _Raises):
                env[target.id] = _UNKNOWN

        def stmt(node, in_class, env):
            if isinstance(node, ast.ImportFrom):
                imp = mod.imps.get(id(node))
                for name, entry in (imp.binds if imp is not None else ()):
                    if entry[0] == 'member':
                        inner = self.resolve(entry[1], entry[2], 0, True)
                        if inner[0] == 'var' and self.mutable(inner[1], inner[2]):
                            return node         # copies a value another module changes: see check_lazy_values
                bind_import(node, env)
                return None
            if isinstance(node, (ast.Import, ast.Pass)):
                if isinstance(node, ast.Import):
                    bind_import(node, env)
                return None
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return fn(node, env)
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                return None
            if isinstance(node, ast.Assign):
                bad = self.impure_expr(mod, node.value, env) or next(
                    (t for t in node.targets if not isinstance(t, ast.Name)), None)
                if bad is None:
                    for t in node.targets:
                        assign(t, node.value, node, env)
                return bad
            if isinstance(node, ast.AnnAssign):
                bad = (self.impure_expr(mod, node.value, env)
                       or (None if future else self.annotation_bad(mod, node.annotation, env))
                       or (None if isinstance(node.target, ast.Name) else node.target))
                if bad is None and node.value is not None:
                    assign(node.target, node.value, node, env)
                return bad
            if isinstance(node, ast.ClassDef) and not in_class:
                for e in node.decorator_list:
                    bad = self.impure_decorator(mod, e, env)
                    if bad is not None:
                        return bad
                for e in node.bases + [k.value for k in node.keywords]:
                    bad = self.impure_expr(mod, e, env)
                    if bad is not None:
                        return bad
                if node.bases or node.keywords:
                    bad = self.hooked(mod)
                    if bad is not None:
                        return bad
                inner_env = env.new_child()
                for inner in node.body:
                    bad = stmt(inner, True, inner_env)
                    if bad is not None:
                        return bad
                env[node.name] = _UNKNOWN
                return None
            return node
        got = None
        env = collections.ChainMap({})
        for node in mod.tree.body:
            if id(node) in mod.lazy:
                continue
            bad = stmt(node, False, env)
            if bad is not None:
                got = bad
                break
        mod.pure_cache = got
        return got

    def missing(self, mod, node, name):
        self.refuse(mod, node, "no module named %r: the search path (%s) has no such file or directory.\n"
                    "  write instead: create %s, or import a module that exists"
                    % (name, ', '.join(str(r) for r in self.roots), name.replace('.', '/') + '.py'))

    def d_import(self, mod, node):
        imp = Imp(node)
        local = 0
        for a in node.names:
            first = a.name.split('.')[0]
            top = self.load(first, mod, node) if self.local_top(first) else None
            if top is None:
                imp.binds.append((a.asname or first, ('std', ('import', a.name))))
                continue
            local += 1
            chain = [top]
            parts = a.name.split('.')
            for i in range(2, len(parts) + 1):
                sub = self.load('.'.join(parts[:i]), mod, node)
                if sub is None:
                    self.missing(mod, node, '.'.join(parts[:i]))
                chain.append(sub)
            imp.chain.extend(chain)
            imp.binds.append((a.asname or first, ('mod', chain[-1] if a.asname else top)))
        if local and local != len(node.names):
            self.refuse(mod, node, "one `import` statement mixes local modules and others; the compiler "
                        "needs them apart.\n  write instead: one `import` line for the local modules")
        imp.local = bool(local)
        mod.imps[id(node)] = imp

    def absolute(self, mod, node):
        if not node.level:
            return node.module
        dots = '.' * node.level + (node.module or '')
        if mod.entry:
            self.refuse(mod, node, "relative import (`from %s import ...`) in the entry file: CPython raises "
                        "ImportError (attempted relative import with no known parent package) for a script.\n"
                        "  write instead: `import pkg.mod` / `from pkg import mod` with absolute names" % dots)
        parts = mod.package.split('.') if mod.package else []
        if not parts:
            self.refuse(mod, node, "relative import (`from %s import ...`) in %s, which is not inside a package: "
                        "CPython raises ImportError (attempted relative import with no known parent package).\n"
                        "  write instead: `from %s import ...` with an absolute name"
                        % (dots, mod.path.name, node.module or 'module'))
        if node.level > len(parts):
            self.refuse(mod, node, "relative import (`from %s import ...`) goes beyond the top-level package "
                        "%r: CPython raises ImportError.\n  write instead: use an absolute import" % (dots, parts[0]))
        base = parts[:len(parts) - node.level + 1]
        return '.'.join(base + ([node.module] if node.module else []))

    def from_target(self, mod, node):
        """(absolute name, target Mod or None for a standard module, chain of modules to run)."""
        absname = self.absolute(mod, node)
        first = absname.split('.')[0]
        if not node.level and not self.local_top(first):
            return absname, None, []
        chain = []
        parts = absname.split('.')
        for i in range(1, len(parts) + 1):
            found = self.load('.'.join(parts[:i]), mod, node)
            if found is None:
                if i == 1 and not node.level:
                    return absname, None, []           # a brace .ail that shadows a modelled module
                self.missing(mod, node, '.'.join(parts[:i]))
            chain.append(found)
        return absname, chain[-1], chain

    def bound_except(self, mod, node):
        """Names `mod` binds apart from the import statement `node` (for a package importing from itself)."""
        rest = [s for s in mod.tree.body if s is not node]
        names = set(_scan_scope(rest)[0])
        for n in ast.walk(mod.tree):
            if isinstance(n, ast.Global):
                names.update(n.names)
        return names

    def d_from(self, mod, node):
        imp = Imp(node)
        mod.imps[id(node)] = imp
        absname, target, chain = self.from_target(mod, node)
        if target is None:
            for a in node.names:
                if a.name != '*':
                    imp.binds.append((a.asname or a.name, ('std', ('from', node.module, a.name))))
            return
        imp.local = True
        imp.chain.extend(chain)
        for a in node.names:
            if a.name == '*':
                self.d_star(mod, imp, target, node)
                continue
            if a.name.startswith('_') and not (a.name.startswith('__') and a.name.endswith('__')):
                self.refuse(mod, node, "`from %s import %s` imports a private name (a leading underscore); "
                            "this compiler refuses it even though CPython allows it.\n"
                            "  write instead: rename it without the underscore in %s"
                            % (absname, a.name, target.path.name))
            bound = self.bound_except(mod, node) if target is mod else self.bound_names(target)
            if bound is not None and a.name in bound:
                imp.members.append((target, a.name))
                imp.binds.append((a.asname or a.name, ('member', target, a.name)))
                continue
            child = self.load(target.name + '.' + a.name, mod, node) if target.kind != 'module' else None
            if child is None:
                names = sorted(n for n in (bound or ()) if not n.startswith('_'))
                self.refuse(mod, node, "module %r has no top-level name %r (it defines: %s).\n"
                            "  write instead: use one of those names, or define %r in %s"
                            % (target.name, a.name, ', '.join(names) or 'nothing', a.name, target.path.name))
            imp.chain.append(child)
            imp.binds.append((a.asname or a.name, ('mod', child)))

    def star_list(self, target, mod, node):
        if target.all_names is not None:
            return list(target.all_names)
        if target.all_dynamic is not None:
            self.refuse(mod, node, "`from %s import *`: %s uses __all__ in a way the compiler cannot read "
                        "at build time.\n  write instead: `__all__ = [\"a\", \"b\"]` as a literal list of "
                        "strings, or `from %s import name1, name2`" % (target.name, target.path.name, target.name))
        bound = self.bound_names(target)
        if bound is None:
            self.refuse(mod, node, "`from %s import *`: %s itself star-imports a standard-library module, so the "
                        "names it exports are not known.\n  write instead: name what you use "
                        "(`from %s import name1, name2`)" % (target.name, target.path.name, target.name))
        return sorted(n for n in bound | set(self.init_children(target)) if not n.startswith('_'))

    def init_children(self, target):
        """Submodules of package `target` that are bound as its attributes when its own body has run:
        the ones it imports, directly or through the modules it imports."""
        if target.kind == 'module':
            return []
        seen = set()

        def walk(mod):
            for imp in mod.imps.values():
                for t in imp.chain:
                    if t not in seen:
                        seen.add(t)
                        walk(t)
        walk(target)
        prefix = target.name + '.'
        return sorted(t.name[len(prefix):] for t in seen if t.name.startswith(prefix) and '.' not in t.name[len(prefix):])

    def d_star(self, mod, imp, target, node):
        if target is mod:
            self.refuse(mod, node, "`from %s import *` inside %s itself.\n  write instead: name what you use"
                        % (target.name, mod.path.name))
        imp.stars.append(target)
        bound = self.bound_names(target)
        for name in self.star_list(target, mod, node):
            if name.startswith('_'):
                self.refuse(mod, node, "`from %s import *` would bind the private name %s (it is listed in "
                            "__all__); this compiler refuses private names even though CPython allows them.\n"
                            "  write instead: rename it without the underscore in %s"
                            % (target.name, name, target.path.name))
            imp.star_keys.add(name)
            if bound is not None and name in bound:
                imp.members.append((target, name))
                imp.binds.append((name, ('member', target, name)))
                continue
            child = self.load(target.name + '.' + name, mod, node) if target.kind != 'module' else None
            if child is None:
                self.refuse(mod, node, "`from %s import *`: __all__ of %s lists %r, which is neither a name it "
                            "defines nor a submodule (CPython raises AttributeError).\n"
                            "  write instead: remove %r from __all__ or define it"
                            % (target.name, target.path.name, name, name))
            imp.chain.append(child)
            imp.binds.append((name, ('mod', child)))

    def bound_names(self, mod):
        """Names bound in the namespace of `mod` when its body has run (None: not known)."""
        if mod.bound_done:
            return mod.bound
        if mod.bound_busy:
            return mod.bound_partial
        mod.bound_busy = True
        names = set(_scan_scope(mod.tree.body)[0]) - mod.lazy_only
        for node in ast.walk(mod.tree):
            if isinstance(node, ast.Global):
                names.update(node.names)
        mod.bound_partial = names
        unknown = False
        for node in mod.tree.body:
            if isinstance(node, ast.ImportFrom) and any(a.name == '*' for a in node.names):
                _, target, _ = self.from_target(mod, node)
                if target is None:
                    unknown = True
                elif target is not mod:
                    names.update(self.star_list(target, mod, node))
        mod.bound = None if unknown else names
        mod.bound_busy = False
        mod.bound_done = True
        return mod.bound

    def check_star_packages(self):
        """`from pkg import *` without `__all__` binds the submodules imported so far, which depends on
        the order of imports elsewhere: refused when the package has a submodule it does not bind itself."""
        for mod in list(self.mods.values()):
            for imp in mod.imps.values():
                for target in imp.stars:
                    if target.kind == 'module' or target.all_names is not None:
                        continue
                    bound = (self.bound_names(target) or set()) | set(self.init_children(target))
                    prefix = target.name + '.'
                    for name in self.mods:
                        if name.startswith(prefix) and '.' not in name[len(prefix):] and name[len(prefix):] not in bound:
                            self.refuse(mod, imp.node, "`from %s import *` without __all__: it would also bind the "
                                        "submodules imported before this line (such as %s), which depends on the order "
                                        "of imports elsewhere.\n  write instead: define __all__ in %s, or name what "
                                        "you use" % (target.name, name, target.path.name))

    # -- analysis: what each module binds

    def analyse_all(self, entry):
        order, seen = [], set()

        def visit(mod):
            if mod in seen:
                return
            seen.add(mod)
            for imp in mod.imps.values():
                for target in imp.chain:
                    visit(target)
            order.append(mod)
        visit(entry)
        for mod in order:
            self.analyse(mod)
        return order

    def std_sig(self, target, name):
        """The standard-library signature a re-exported name ends in, else None."""
        if name in target.std:
            return target.std[name]
        entry = target.alias.get(name)
        if entry is not None and entry[0] == 'member':
            return self.std_sig(entry[1], entry[2])
        return None

    def bind(self, mod, imp, index, key, entry):
        node = imp.node
        if entry[0] == 'std':
            self._std(mod, key, entry[1], node)
            return
        if entry[0] == 'member' and key in imp.star_keys:
            if not entry[1].analysed:
                self.refuse(mod, node, "`from %s import *` in an import cycle: %s has not been read yet when %s "
                            "star-imports it.\n  write instead: name what you use, or break the cycle"
                            % (entry[1].name, entry[1].name, mod.path.name))
            sig = self.std_sig(entry[1], entry[2])
            if sig is not None:
                self._std(mod, key, sig, node)
                mod.first.setdefault(key, index)
                return
        old = mod.alias.get(key)
        if (old is not None and old != entry) or key in mod.std:
            self.refuse(mod, node, "%r is bound to two different imports in %s.\n"
                        "  write instead: give one of them another name with `as`" % (key, mod.path.name))
        mod.alias[key] = entry
        mod.first.setdefault(key, index)

    def analyse(self, mod):
        body = mod.tree.body
        stores, _, _, sites = _scan_scope(body)
        counts, imports = {}, {}
        for name, site in sites:
            counts[name] = counts.get(name, 0) + 1
            if isinstance(site, (ast.Import, ast.ImportFrom)):
                imports[name] = imports.get(name, 0) + 1
        globalled = {n for f in ast.walk(mod.tree) if isinstance(f, ast.Global) for n in f.names}
        direct = {}
        for index, node in enumerate(body):
            for name, site in _scan_scope([node])[3]:
                direct.setdefault(name, (index, node))
                mod.first.setdefault(name, index)
        for index, node in enumerate(body):
            imp = mod.imps.get(id(node))
            if imp is None:
                continue
            for key, entry in imp.binds:
                self.bind(mod, imp, index, key, entry)
        for name in stores | globalled:
            if name in mod.std or name in mod.alias:
                if counts.get(name, 0) > imports.get(name, 0):
                    self.refuse(mod, direct[name][1], "%r is imported and also assigned or defined again in %s; "
                                "this compiler does not guess which binding a reader meant.\n"
                                "  write instead: import it under another name (`from ... import %s as other`)"
                                % (name, mod.path.name, name))
                continue
            index, node = direct.get(name, (0, None))
            single = (counts.get(name, 0) == 1 and name not in globalled and node is not None
                      and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Assign, ast.AnnAssign)))
            if single and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                kind = 'func'
            elif single and isinstance(node, ast.ClassDef):
                kind = 'class'
            elif single:
                kind = 'var'
            else:
                kind = 'multi'
            mod.kinds[name] = kind
        mod.analysed = True

    def _std(self, mod, name, signature, node):
        if mod.std.get(name, signature) != signature or name in mod.alias:
            self.refuse(mod, node, "%r is bound to two different imports in %s.\n"
                        "  write instead: give one of them another name with `as`" % (name, mod.path.name))
        mod.std[name] = signature

    # -- what a name denotes after the merge

    def mutable(self, owner, key):
        return owner.kinds.get(key) == 'multi' or (owner, key) in self.ext

    def resolve(self, mod, name, depth=0, outside=False):
        """('module', Mod) | ('var', owner, key) | ('std', signature) | ('none',) for `name` in `mod`.
        A name imported with `from m import x` whose source can change gets its own copy in `mod`."""
        if depth > 60:
            self.refuse(mod, mod.tree, "imports of %r form a loop" % name)
        if outside and name in mod.lazy_only:
            return ('none',)             # bound inside a function only: not an attribute of the module
        entry = mod.alias.get(name)
        if entry is not None:
            if entry[0] == 'mod':
                return ('module', entry[1])
            inner = self.resolve(entry[1], entry[2], depth + 1, True)
            if inner[0] == 'var' and self.mutable(inner[1], inner[2]):
                return ('var', mod, name)
            return inner
        if name in mod.std:
            return ('std', mod.std[name])
        if name in mod.kinds:
            return ('var', mod, name)
        return ('none',)

    def merged_name(self, owner, key):
        return owner.merged[key] if key in owner.merged else owner.snaps[key]

    def child(self, base, attr):
        """The submodule `base.attr` when the program loads one."""
        return self.mods.get(base.name + '.' + attr) if base.kind != 'module' else None

    def export(self, target, attr, importer, node):
        """Merged name of `attr` in module `target` (following re-exports)."""
        if attr == '__all__' and target.all_names is not None:
            self.refuse(importer, node, "%s.__all__ is read by the compiler and not kept in the program.\n"
                        "  write instead: do not read __all__ at run time" % target.name)
        found = self.resolve(target, attr, 0, True)
        sub = found[1] if found[0] == 'module' else (self.child(target, attr) if found[0] == 'none' else None)
        if sub is not None:
            self.refuse(importer, node, "%s.%s is a module, used as a value; this compiler needs a module to be "
                        "named in the source.\n  write instead: `import %s` in the importing file"
                        % (target.name, attr, sub.name))
        if found[0] == 'std':
            self.refuse(importer, node, "%s.%s is a standard-library name that %s imported; reading it through %s "
                        "is not supported.\n  write instead: import it in the importing file"
                        % (target.name, attr, target.name, target.name))
        if found[0] == 'none' and any((d / (attr + '.py')).is_file() or (d / (attr + '.ail')).is_file()
                                      or (d / attr).is_dir() for d in target.dirs):
            self.refuse(importer, node, "package %r has no attribute %r: a submodule of that name exists but nothing "
                        "imports it, and CPython binds a submodule on its package only when it is imported.\n"
                        "  write instead: `import %s.%s` in the importing file" % (target.name, attr, target.name, attr))
        if found[0] == 'none':
            names = sorted(n for n in target.kinds if not n.startswith('_'))
            self.refuse(importer, node, "module %r has no top-level name %r (it defines: %s).\n"
                        "  write instead: use one of those names, or define %r in %s"
                        % (target.name, attr, ', '.join(names) or 'nothing', attr, target.path.name))
        return self.merged_name(found[1], found[2])

    def check_lazy_values(self, mods):
        """`from m import x` inside a function reads x when the function runs; the merged program copies
        it once, so it is refused for a variable that changes."""
        for mod in mods:
            for key, orig in mod.lazy.items():
                for name, entry in mod.imps[key].binds:
                    if entry[0] != 'member':
                        continue
                    inner = self.resolve(entry[1], entry[2], 0, True)
                    if inner[0] == 'var' and self.mutable(inner[1], inner[2]):
                        self.refuse(mod, orig, "`from %s import %s` inside a function: %s.%s is a variable that "
                                    "changes while the program runs, and CPython copies its value when the "
                                    "function runs, which the merged program cannot do.\n"
                                    "  write instead: `import %s` in the function and read `%s.%s`, or move the "
                                    "import to the top of the file" % (entry[1].name, entry[2], entry[1].name,
                                                                       entry[2], entry[1].name,
                                                                       entry[1].name.rpartition('.')[2], entry[2]))

    def prepare_stores(self, mods):
        """Find every `m.attr = v` in the program: a name written from outside is a module global that
        changes (and a name nobody defined becomes one)."""
        for mod in mods:
            finder = Rewriter(self, mod, set(), {}, dry=True)
            for stmt in copy.deepcopy(mod.tree.body):
                finder.visit(stmt)
        for (target, attr), (writer, node) in list(self.ext.items()):
            what = ('an import of %s' % target.name if attr in target.alias else
                    'a submodule' if self.child(target, attr) is not None else
                    'a standard-library import of %s' % target.name if attr in target.std else None)
            if what is not None:
                self.refuse(writer, node, "assignment to %s.%s: that name is %s, not a variable %s defines; this "
                            "compiler cannot tell which binding readers should see.\n"
                            "  write instead: call a function in %s that does the update"
                            % (target.name, attr, what, target.name, target.path.name))
            if attr not in target.kinds:
                target.kinds[attr] = 'multi'
                target.first.setdefault(attr, NEVER)


def _def_node(mod, name):
    for node in mod.tree.body:
        if getattr(node, 'name', None) == name:
            return node
    return mod.tree


def _import_node(mod, name):
    for node in mod.tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)) and any(
                (a.asname or a.name.split('.')[0]) == name for a in node.names):
            return node
    return mod.tree


def _rebound_by_submodule(program, mods):
    """`pkg/__init__.py` binds a name (`a = 5`, `def a`, `from .x import a`) that is also the name of a submodule the
    program imports: CPython's import of `pkg.a` stores the module over that attribute, wherever it happens, so what
    `pkg.a` means depends on the order of the imports."""
    for mod in mods:
        if mod.kind == 'module':
            continue
        for name in sorted(set(mod.kinds) | set(mod.std) | set(mod.alias)):
            child = program.mods.get(mod.name + '.' + name)
            if child is None:
                continue
            entry = mod.alias.get(name)
            if entry is not None and entry[0] == 'mod' and entry[1] is child:
                continue                # `from . import a` binds the module itself
            program.refuse(mod, _binding_node(mod, name),
                           "%s binds the name %r and %s is also a submodule that the program imports: CPython's "
                           "import of %s stores the module over that attribute, so what %s.%s means depends on the "
                           "order of the imports.\n"
                           "  write instead: give the %s variable or function another name"
                           % (mod.path.name, name, child.name, child.name, mod.name, name, mod.name))


def _binding_node(mod, name):
    for node in mod.tree.body:
        if getattr(node, 'name', None) == name:
            return node
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Name) and t.id == name for t in targets):
                return node
        if isinstance(node, (ast.Import, ast.ImportFrom)) and any(
                (a.asname or a.name.split('.')[0]) == name for a in node.names):
            return node
    return mod.tree


def _assign_names(program, mods):
    _rebound_by_submodule(program, mods)
    ids = set(BUILTINS)
    for mod in mods:
        for node in ast.walk(mod.tree):
            for field in ('id', 'name', 'arg', 'attr'):
                value = getattr(node, field, None)
                if isinstance(value, str):
                    ids.add(value)
            if isinstance(node, ast.alias):
                ids.add(node.asname or node.name)
            if isinstance(node, ast.ClassDef):
                ids.update('%s__%s' % (node.name, m.name) for m in node.body
                           if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)))
    kept = program.kept
    for mod in mods:
        for name, kind in mod.kinds.items():
            if mod.entry or kind == 'class':
                other = kept.get(name)
                if other is not None and other[0] is not mod:
                    program.refuse(mod, _def_node(mod, name),
                                   "name %r is defined in both %s and %s; classes keep their names (a class name is "
                                   "printed by repr) and the entry module keeps all of its names, so this compiler "
                                   "cannot tell them apart.\n  write instead: rename one of them"
                                   % (name, other[0].path.name, mod.path.name))
                kept[name] = (mod, 'def')
                mod.merged[name] = name
    for mod in mods:
        for name, signature in mod.std.items():
            other = kept.get(name)
            if other is None:
                kept[name] = (mod, signature)
            elif other[1] == 'def' or other[1] != signature:
                program.refuse(mod, _import_node(mod, name),
                               "name %r is bound by an import in %s and by %s in %s; this compiler keeps "
                               "standard-library names unrenamed, so the two would collide.\n"
                               "  write instead: import it under another name (`import ... as ...`)"
                               % (name, mod.path.name, 'a definition' if other[1] == 'def' else 'another import',
                                  other[0].path.name))
    used = set()

    def fresh(new):
        while new in ids or new in used or new in kept:
            new += '_'
        used.add(new)
        return new
    for mod in mods:
        if mod.entry:
            continue
        for name, kind in mod.kinds.items():
            if kind != 'class':
                mod.merged[name] = fresh('%s__%s' % (mod.prefix, name))
    for mod in mods:
        for key, entry in mod.alias.items():
            if entry[0] == 'member' and program.resolve(mod, key)[1:] == (mod, key):
                mod.snaps[key] = fresh('%s__%s' % (mod.prefix, key))


# ---------------------------------------------------------------- rewriting

class Rewriter(ast.NodeTransformer):
    def __init__(self, program, mod, partial, positions, dry=False):
        self.program = program
        self.mod = mod
        self.scopes = []              # [kind, names, globals]
        self.partial = partial        # modules still running their body (import cycle)
        self.positions = positions    # module -> index of the statement it is executing
        self.running = 0              # 0 while code runs at definition time; > 0 inside function bodies
        self.free = []
        self.dry = dry                # only collect `m.attr = v` writes
        self.frames = []              # one set of module globals to declare per function / class body
        self.comp = 0

    def module_level(self, name):
        for position in range(len(self.scopes) - 1, -1, -1):
            kind, names, global_names = self.scopes[position]
            if kind == 'class' and position != len(self.scopes) - 1:
                continue
            if name in global_names:
                return True
            if name in names:
                return False
        return True

    def check_partial(self, target, attr, node):
        """Reading target.attr while `target` has not finished its body (an import cycle)."""
        if self.dry or target not in self.partial or self.running:
            return
        if target.first.get(attr, NEVER) >= self.positions[target]:
            self.program.refuse(self.mod, node, "import cycle: %s reads %s.%s while %s is still running its own "
                                "body, before %s is defined (%s -> %s -> %s); CPython would expose a partly "
                                "initialised module here.\n"
                                "  write instead: move %s into a module that both import, or read it inside a "
                                "function" % (self.mod.path.name, target.name, attr, target.name, attr,
                                              target.name, self.mod.name, target.name, attr))

    def module_value(self, base, attr, node):
        """The module that `base.attr` denotes: an imported name, or a submodule already imported."""
        found = self.program.resolve(base, attr, 0, True)
        if found[0] == 'module':
            return found[1]
        if found[0] != 'none':
            return None
        sub = self.program.child(base, attr)
        if sub is None:
            return None
        if not self.dry and not self.running and not sub.done:
            self.program.refuse(self.mod, node, "%s.%s is read before the import that binds it has run: in CPython a "
                                "package gets the attribute for a submodule only once that submodule has been "
                                "imported, so this raises AttributeError here.\n"
                                "  write instead: `import %s` (or `from %s import %s`) before this line"
                                % (base.name, attr, sub.name, base.name, attr))
        if not self.dry and self.running and not sub.done:
            # a function runs whenever it is called: if that is before the import, CPython raises AttributeError
            # (a program may catch it), and the merged program has no such global yet
            self.program.refuse(self.mod, node, "%s.%s is read inside a function that is defined before the import "
                                "that binds it: CPython raises AttributeError if the function runs first, and this "
                                "compiler cannot tell when it runs.\n"
                                "  write instead: `import %s` (or `from %s import %s`) above this function"
                                % (base.name, attr, sub.name, base.name, attr))
        return sub

    def module_ref(self, node):
        if isinstance(node, ast.Name):
            if node.id in self.mod.alias and self.module_level(node.id):
                found = self.program.resolve(self.mod, node.id)
                if found[0] == 'module':
                    return found[1]
        elif isinstance(node, ast.Attribute):
            base = self.module_ref(node.value)
            if base is not None:
                return self.module_value(base, node.attr, node)
        return None

    def visit_Name(self, node):
        name = node.id
        if self.dry or not self.module_level(name):
            return node
        if name == '__name__' and isinstance(node.ctx, ast.Load):
            return ast.copy_location(ast.Constant('__main__' if self.mod.entry else self.mod.name), node)
        if name in self.mod.std:
            return node
        if name in self.mod.alias:
            found = self.program.resolve(self.mod, name)
            if found[0] == 'module':
                self.program.refuse(self.mod, node, "module %r used as a value (passed, stored or compared); this "
                                    "compiler needs a module to be named at each use.\n  write instead: use "
                                    "`%s.name` directly" % (found[1].name, name))
            entry = self.mod.alias[name]
            if not isinstance(node.ctx, ast.Load):
                self.program.refuse(self.mod, node, "%r is imported from %s and cannot be rebound here.\n"
                                    "  write instead: use another name for your own variable"
                                    % (name, entry[1].name))
            self.check_partial(entry[1], entry[2], node)
            merged = (self.program.merged_name(found[1], found[2]) if found[0] == 'var'
                      else self.program.export(entry[1], entry[2], self.mod, node))
            return ast.copy_location(ast.Name(merged, node.ctx), node)
        if name in self.mod.merged:
            if self.mod.merged[name] != name:
                return ast.copy_location(ast.Name(self.mod.merged[name], node.ctx), node)
            return node
        if isinstance(node.ctx, ast.Load):
            if name in MODULE_DUNDERS:
                self.program.refuse(self.mod, node, "%s is not available: the program is built into one executable, "
                                    "so a module has no file, package or search path at run time.\n"
                                    "  write instead: pass the value in as a constant or an argument" % name)
            self.free.append((name, node))
        return node

    def visit_Attribute(self, node):
        target = self.module_ref(node.value)
        if target is None:
            self.generic_visit(node)
            return node
        attr = node.attr
        stored = not isinstance(node.ctx, ast.Load)
        if self.dry:
            if stored:
                self.program.ext.setdefault((target, attr), (self.mod, node))
            return node
        if not stored and (target.name, attr) in BUNDLED_NAMES and target.path.resolve().parent == BUNDLED_DIR:
            return ast.copy_location(ast.Name(BUNDLED_NAMES[(target.name, attr)], ast.Load()), node)
        if isinstance(node.ctx, ast.Del):
            self.program.refuse(self.mod, node, "`del %s.%s` removes a module attribute; the compiler fixes every "
                                "module's names at build time.\n  write instead: assign a placeholder value "
                                "(`%s.%s = None`)" % (target.name, attr, target.name, attr))
        if attr == '__name__' and not stored:
            return ast.copy_location(ast.Constant(target.name), node)
        if attr in MODULE_DUNDERS and not stored and not (attr == '__file__' and attr in target.merged):
            self.program.refuse(self.mod, node, "%s.%s is not available: the program is built into one executable.\n"
                                "  write instead: pass the value in as a constant or an argument" % (target.name, attr))
        if attr.startswith('_') and not (attr.startswith('__') and attr.endswith('__')):
            self.program.refuse(self.mod, node, "`%s.%s` reads or writes a private name (a leading underscore); this "
                                "compiler refuses it even though CPython allows it.\n  write instead: rename it "
                                "without the underscore in %s" % (target.name, attr, target.path.name))
        if self.module_value(target, attr, node) is not None:
            self.program.refuse(self.mod, node, "%s.%s is a module, used as a value; this compiler needs a module "
                                "to be named in the source.\n  write instead: use `%s.%s.name` directly"
                                % (target.name, attr, target.name, attr))
        if stored:
            if self.comp:
                self.program.refuse(self.mod, node, "`%s.%s` is assigned inside a comprehension.\n"
                                    "  write instead: assign it in a plain statement" % (target.name, attr))
            name = target.merged[attr]
            if self.frames:
                if self.frames[-1] is None:
                    self.program.refuse(self.mod, node, "`%s.%s` is assigned in a class body, where a module "
                                        "variable cannot be written without a `global` line the class body "
                                        "does not allow.\n  write instead: assign it at module level or in a "
                                        "function" % (target.name, attr))
                self.frames[-1].add(name)
            return ast.copy_location(ast.Name(name, node.ctx), node)
        self.check_partial(target, attr, node)
        return ast.copy_location(ast.Name(self.program.export(target, attr, self.mod, node), ast.Load()), node)

    def visit_AnnAssign(self, node):
        if isinstance(node.target, ast.Attribute) and self.module_ref(node.target.value) is not None:
            self.program.refuse(self.mod, node, "an annotated assignment to a module attribute is not supported.\n"
                                "  write instead: drop the annotation (`m.x = v`)")
        self.generic_visit(node)
        return node

    def visit_If(self, node):
        if self.mod.entry and not self.scopes and _static_main_test(node.test):
            node.body = [self.visit(s) for s in node.body]       # the idiom stays as written
            node.orelse = [self.visit(s) for s in node.orelse]
            return node
        self.generic_visit(node)
        return node

    def rename_binding(self, name):
        if self.module_level(name) and name in self.mod.merged:
            return self.mod.merged[name]
        return name

    def visit_Global(self, node):
        if not self.dry:
            node.names = [self.mod.merged.get(n, n) for n in node.names]
        return node

    def visit_ExceptHandler(self, node):
        if node.name and not self.dry:
            node.name = self.rename_binding(node.name)
        self.generic_visit(node)
        return node

    def visit_MatchAs(self, node):
        if node.name and not self.dry:
            node.name = self.rename_binding(node.name)
        self.generic_visit(node)
        return node

    visit_MatchStar = visit_MatchAs

    def visit_MatchMapping(self, node):
        if node.rest and not self.dry:
            node.rest = self.rename_binding(node.rest)
        self.generic_visit(node)
        return node

    def declare_globals(self, node, names):
        if names and not self.dry:
            node.body.insert(0, ast.copy_location(ast.Global(names=sorted(names)), node.body[0]))

    def visit_function(self, node):
        if not isinstance(node, ast.Lambda):
            node.decorator_list = [self.visit(d) for d in node.decorator_list]
            if node.returns is not None:
                node.returns = self.visit(node.returns)
        a = node.args
        for arg in a.posonlyargs + a.args + a.kwonlyargs + [x for x in (a.vararg, a.kwarg) if x]:
            if arg.annotation is not None:
                arg.annotation = self.visit(arg.annotation)
        a.defaults = [self.visit(d) for d in a.defaults]
        a.kw_defaults = [self.visit(d) if d is not None else None for d in a.kw_defaults]
        if not isinstance(node, ast.Lambda) and not self.dry:
            node.name = self.rename_binding(node.name)
        names, global_names = _function_locals(node)
        self.scopes.append(['func', names, global_names])
        self.running += 1
        self.frames.append(set())
        if isinstance(node, ast.Lambda):
            node.body = self.visit(node.body)
        else:
            node.body = [self.visit(s) for s in node.body]
        needed = self.frames.pop()
        self.running -= 1
        self.scopes.pop()
        if not isinstance(node, ast.Lambda):
            self.declare_globals(node, needed)
        return node

    visit_FunctionDef = visit_AsyncFunctionDef = visit_Lambda = visit_function

    def visit_ClassDef(self, node):
        node.decorator_list = [self.visit(d) for d in node.decorator_list]
        node.bases = [self.visit(b) for b in node.bases]
        node.keywords = [self.visit(k) for k in node.keywords]
        if not self.dry:
            node.name = self.rename_binding(node.name)
        stores, globals_, _, _ = _scan_scope(node.body)
        self.scopes.append(['class', stores - globals_, globals_])
        self.frames.append(None)
        node.body = [self.visit(s) for s in node.body]
        self.frames.pop()
        self.scopes.pop()
        return node

    def visit_comprehension_scope(self, node):
        generators = node.generators
        generators[0].iter = self.visit(generators[0].iter)
        names = {c.id for g in generators for c in ast.walk(g.target)
                 if isinstance(c, ast.Name) and isinstance(c.ctx, ast.Store)}
        self.scopes.append(['func', names, set()])
        self.comp += 1
        for index, g in enumerate(generators):
            g.target = self.visit(g.target)
            if index:
                g.iter = self.visit(g.iter)
            g.ifs = [self.visit(i) for i in g.ifs]
        if isinstance(node, ast.DictComp):
            node.key, node.value = self.visit(node.key), self.visit(node.value)
        else:
            node.elt = self.visit(node.elt)
        self.comp -= 1
        self.scopes.pop()
        return node

    visit_ListComp = visit_SetComp = visit_DictComp = visit_GeneratorExp = visit_comprehension_scope


# ---------------------------------------------------------------- the merge

def merge_program(entry_path, entry_text, read=None):
    """None when the entry imports no local module; else a Merged program (see the module docstring)."""
    if read is None:
        def read(path):
            return Path(path).read_bytes().decode('utf-8').replace('\r\n', '\n').replace('\r', '\n')
    program = Program(entry_path, read)
    try:
        tree = ast.parse(entry_text, filename=str(program.entry_path))
    except SyntaxError:
        return None                    # the caller's own parse reports it
    if not any(isinstance(node, (ast.Import, ast.ImportFrom)) and program.is_local_import(node)
               for node in ast.walk(tree)):
        return None
    entry = Mod('__main__', program.entry_path, tree, True)
    program.entry = entry
    program.mods['__main__'] = entry
    program.prepare_entry(entry)
    program.discover(entry)
    program.check_star_packages()
    if any(_uses_file_dunder(mod.tree) for mod in program.mods.values()):
        for mod in program.mods.values():
            mod.tree.body.insert(0, _file_dunder_assignment(mod))
    order = program.analyse_all(entry)
    reachable = [m for m in order if m is not entry]
    if not reachable:
        return None
    mods = [entry] + reachable
    program.prepare_stores(mods)
    program.check_lazy_values(mods)
    _assign_names(program, mods)

    output, std_seen, future, stack, positions = [], {}, [], [], {}

    def stamp(node, mod):
        for child in ast.walk(node):
            child._ail_path = mod.path

    def emit_import(mod, node):
        if isinstance(node, ast.ImportFrom) and node.module == '__future__':
            future.extend(a.name for a in node.names if a.name not in future)
            return
        keep = []
        for a in node.names:
            name = a.asname or a.name.split('.')[0]
            if std_seen.get(name) != mod.std.get(name) or name not in std_seen:
                std_seen[name] = mod.std.get(name)
                keep.append(a)
        if keep:
            clone = copy.copy(node)
            clone.names = keep
            stamp(clone, mod)
            output.append(clone)

    def rewrite(mod, node):
        rewriter = Rewriter(program, mod, {m for m in stack if m is not mod}, positions)
        new = rewriter.visit(node)
        for name, use in rewriter.free:
            other = program.kept.get(name)
            if other is not None and other[0] is not mod and name in BUILTINS:
                program.refuse(mod, use, "%r means the builtin here, but %s binds its own %r and every module shares "
                               "one namespace after the merge.\n  write instead: rename %r in %s"
                               % (name, other[0].path.name, name, name, other[0].path.name))
        stamp(new, mod)
        output.append(new)

    def snapshots(mod, imp):
        for key, entry in imp.binds:
            if entry[0] == 'member' and key in mod.snaps:
                found = program.resolve(entry[1], entry[2])
                copy_stmt = ast.Assign(targets=[ast.Name(mod.snaps[key], ast.Store())],
                                       value=ast.Name(program.merged_name(found[1], found[2]), ast.Load()))
                ast.copy_location(copy_stmt, imp.node)
                stamp(copy_stmt, mod)
                output.append(copy_stmt)

    lazy_ctx = []

    def expand(mod):
        if lazy_ctx and not mod.entry:
            bad = program.impure(mod)
            if bad is not None:
                where, orig = lazy_ctx[-1]
                line = getattr(bad, 'lineno', 1)
                what = ("copies (`%s`) a variable that another module changes while the program runs"
                        % ast.unparse(bad) if isinstance(bad, ast.ImportFrom) else
                        "runs code with an effect or an expression that can raise (`%s`)"
                        % ast.unparse(bad).split('\n')[0][:60])
                program.refuse(where, orig, "function-level `%s`: the module body %s at import time (%s:%d), "
                               "and the compiler runs it when the importing module has finished, not when "
                               "the function first runs.\n"
                               "  write instead: move the import to the top of the file, or keep %s to "
                               "definitions and constants"
                               % (ast.unparse(orig), what, mod.path, line, mod.path.name))
        stack.append(mod)
        for index, node in enumerate(mod.tree.body):
            positions[mod] = index
            imp = mod.imps.get(id(node))
            if imp is not None and imp.local:
                if id(node) in mod.lazy:
                    lazy_ctx.append((mod, mod.lazy[id(node)]))
                for target in imp.chain:
                    if target in stack:
                        if target in imp.stars:
                            program.refuse(mod, node, "`from %s import *` while %s is still running its own body "
                                           "(an import cycle).\n  write instead: name what you use, or break the "
                                           "cycle" % (target.name, target.name))
                    elif not target.done:
                        expand(target)
                for owner, orig in imp.members:
                    if owner in stack and owner.first.get(orig, NEVER) >= positions[owner]:
                        child = program.child(owner, orig)
                        if child is None:
                            cycle = ' -> '.join(m.name for m in stack[stack.index(owner):] + [owner])
                            if id(node) in mod.lazy:
                                # a function-level import: CPython binds the name when the function runs, which is
                                # valid; AIL resolves imports at build time and cannot order this cycle
                                program.refuse(mod, node, "import cycle %s: `from %s import %s` inside a function "
                                               "is valid Python (it runs when the function is called), but AIL "
                                               "resolves imports when it builds and cannot order this cycle.\n"
                                               "  write instead: `import %s` and use `%s.%s`, or move %s into a "
                                               "module that both import"
                                               % (cycle, owner.name, orig, owner.name, owner.name, orig, orig))
                            else:
                                program.refuse(mod, node, "import cycle %s: `from %s import %s` runs before %s "
                                               "has defined %s, so CPython raises ImportError.\n"
                                               "  write instead: move %s into a module that both import"
                                               % (cycle, owner.name, orig, owner.name, orig, orig))
                        # the name is not bound yet, so CPython imports the submodule of that name
                        for key, entry in imp.binds:
                            if entry == ('member', owner, orig):
                                mod.alias[key] = ('mod', child)
                        if child not in stack and not child.done:
                            expand(child)
                if id(node) in mod.lazy:
                    lazy_ctx.pop()
                snapshots(mod, imp)
                continue
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                emit_import(mod, node)
            elif mod.entry:
                rewrite(mod, node)
            elif index == 0 and isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) \
                    and isinstance(node.value.value, str):
                continue                                          # module docstring
            else:
                rewrite(mod, node)
        mod.done = True
        stack.pop()

    expand(entry)
    if future:
        head = ast.ImportFrom('__future__', [ast.alias(n) for n in future], 0)
        head._ail_path = entry.path
        output.insert(0, head)
    module = ast.Module(body=output, type_ignores=[])
    ast.fix_missing_locations(module)
    text = ast.unparse(module) + '\n'
    names = {}
    for mod in mods:
        for old, new in mod.merged.items():
            if new != old:
                names[new] = '%s.%s' % (mod.name, old)
        for key, new in mod.snaps.items():
            names[new] = key if mod.entry else '%s.%s' % (mod.name, key)
    return Merged(text, _positions(module, text), program.notes, names)


def _positions(module, text):
    """merged line -> (path, line, column) of the statement that produced it, by walking the merged
    tree and its re-parse in step (they have the same shape)."""
    try:
        again = ast.parse(text)
    except SyntaxError:
        return {}
    old = [n for n in ast.walk(module) if isinstance(n, ast.stmt)]
    new = [n for n in ast.walk(again) if isinstance(n, ast.stmt)]
    if len(old) != len(new) or any(type(a) is not type(b) for a, b in zip(old, new)):
        return {}
    positions = {}
    for a, b in zip(old, new):
        path = getattr(a, '_ail_path', None)
        if path is not None and getattr(a, 'lineno', None) and b.lineno not in positions:
            positions[b.lineno] = (str(path), a.lineno, a.col_offset + 1)
    return positions
