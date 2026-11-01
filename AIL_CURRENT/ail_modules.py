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
* top-level functions, variables and classes of an imported module `p.m` are renamed `p__m__name`; the
  entry module keeps all its names. A class keeps its printed name: `Merged.classes` maps the merged
  name to (name, module), and `python/pkg-v12/classname.py` gives every place that prints a class
  name (repr, `__name__`, exception text) the name CPython prints;
* module state is shared the way CPython shares it: there is one variable per module global, so a
  function that says `global x`, a module that writes `m.x = v`, and every reader of `m.x` see the
  same variable. `from m import x` copies the value at that moment, so a global that changes after
  the import gets its own copy in the importing module (a "snapshot");
* `__name__` is `"__main__"` in the entry module and the dotted module name elsewhere; an
  `if __name__ == "__main__":` in an imported module is removed;
* a program with no import of a local module, no `try:` around an import and no `__file__` / `__package__`
  is not touched at all (the caller gets None), so single-file programs compile to the same C as before.

A local import inside a function (the usual way to break an import cycle) is moved to the module's top
level when the modules it runs have no side effects at import time (only definitions and constants); the
function then reads the name as a module alias. When the module has effects (a print, a table built by a call,
a read of the environment), or the importing module calls the function while it starts, the module body is
split instead: its definitions (def, class) are hoisted, and every other statement goes into a function
`_ail_init_<module>` that the import statement calls the first time it runs, so the effects happen when CPython
has them. A definition whose decorators, defaults or bases need a value that the module only computes when it
runs is refused by name.

`try: import m / except ImportError:` is decided when the program is built (`resolve_guarded`): a module the
search path or the build machine's Python has is found (the handler never runs), anything else is not (the
handler runs). A C accelerator (`_bisect`, `_decimal`...) counts as not found: the library falls back to the
same code in Python. An import in a function inside a `try:` whose module is found is a plain function-level
import. `__file__` is the absolute path of the source file at build time (the program is one executable, so
there is no other path), `__package__` and `__name__` have CPython's values, `__path__` of a package lists its
directories; `from m import _x` and `m._x` are plain Python (a name with two leading underscores is refused
inside a class body, where CPython mangles it). Importing the entry file by name loads it a second time, with
its own globals, as CPython does.

Everything this does not model is refused by name with a `write instead:` hint: imports in a class body or
condition, a module used as a value, relative imports in the entry file, a submodule attribute read before
the import that binds it, names rebound in a way that cannot be told apart after the merge, a module-level
`from a import b` of a name `a` has not defined yet (CPython raises ImportError), and import cycles that
CPython only survives through partly initialised modules. (`importlib` and `__import__` are not modelled by
the front end and are refused there.)
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
    def __init__(self, text, positions, notes, names, classes=None):
        self.text = text
        self.positions = positions      # merged line -> (path, line, column)
        self.notes = notes
        self.names = names              # renamed top-level name -> 'module.name', for messages
        self.classes = classes or {}    # merged class name -> (class name, module name), for printing


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
        self.lazy_slot = {}             # id(synthetic top-level import) -> the `pass` standing in its function
        self.force_init = set()         # ids of synthetic imports whose module must start when the function runs
        self.init_name = None           # name of the function that runs this module's body (lazy start), if any
        self.hoisted = set()            # ids of the constant assignments placed with the definitions (lazy start)


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
        self.getters = {}
        self.after_name = None
        self.uses_after = False

    def dunder_node(self, mod, name):
        """The value of `__file__` / `__package__` / `__path__` of `mod` as a constant expression, else None.
        The program is one executable, so `__file__` is the absolute path of the source file at build time (and
        None for a namespace package, as in CPython); `__package__` is None in the entry, else the package name."""
        if name == '__file__':
            return ast.Constant(None if mod.kind == 'namespace' else str(mod.path))
        if name == '__package__':
            return ast.Constant(None if mod.entry else mod.package)
        if name == '__path__' and mod.kind != 'module' and not mod.entry:
            return ast.List(elts=[ast.Constant(str(d)) for d in mod.dirs], ctx=ast.Load())
        return None

    def find_getters(self, mods):
        """Functions of the form `def f(): import m; return m` (the usual lazy import of a module that is used
        through a getter): a call `f().name` is the module's `name`. {(module name, function): (Mod, node)}."""
        self.getters = {}
        for mod in mods:
            slots = {id(s) for s in mod.lazy_slot.values()}
            for node in mod.tree.body:
                if not isinstance(node, ast.FunctionDef) or node.decorator_list:
                    continue
                a = node.args
                if a.posonlyargs or a.args or a.kwonlyargs or a.vararg or a.kwarg:
                    continue
                body = [s for s in node.body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant)
                                                     and isinstance(s.value.value, str))]
                if len(body) < 2 or not isinstance(body[-1], ast.Return) or not isinstance(body[-1].value, ast.Name):
                    continue
                if not all(isinstance(s, ast.Pass) and id(s) in slots for s in body[:-1]):
                    continue
                entry = mod.alias.get(body[-1].value.id)
                if entry is not None and entry[0] == 'mod' and mod.kinds.get(node.name) == 'func':
                    self.getters[(mod.name, node.name)] = (entry[1], node)

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
        # an import of the entry file's own module name loads it a second time under that name, as CPython does
        # (the entry is `__main__`; this copy has its own globals and its body runs again)
        if '.' not in fullname and fullname in STDLIB and kind != 'namespace' and (
                path is None or path.resolve().parent != BUNDLED_DIR):
            self.notes.append('note: %s shadows the standard library module %s, as it does in CPython'
                              % (path.name if path.name != '__init__.py' else path.parent.name + '/__init__.py',
                                 fullname))
        text = ''
        if path is None:
            tree = ast.Module(body=[], type_ignores=[])
        else:
            try:
                text = self.read(path)
                tree = ast.parse(text, filename=str(path))
            except SyntaxError as error:
                raise ModuleRefusal(path, error.lineno or 1, error.offset or 1, error.msg)
        mod = Mod(fullname, path if path is not None else mdirs[0], tree, False, kind, mdirs if kind != 'module' else [])
        self.mods[fullname] = mod
        self.drop_main_guards(mod)
        if '__all__' in text:
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

    # -- `try: import m / except ImportError:` decided at build time

    IMPORT_ERRORS = frozenset(('ImportError', 'ModuleNotFoundError', 'Exception', 'BaseException'))

    def handler_catches(self, handler, missing_module):
        """True when `except <handler.type>` catches the error of a failed import (`missing_module`: the whole
        module is absent, ModuleNotFoundError; else a name missing from a module, ImportError)."""
        if handler.type is None:
            return True
        types = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
        for t in types:
            if isinstance(t, ast.Name) and t.id in self.IMPORT_ERRORS and (
                    missing_module or t.id != 'ModuleNotFoundError'):
                return True
        return False

    def cpython_has(self, top):
        """The build machine's CPython can import top-level module `top` (the program runs on the machine
        that built it, so this is what the guarded import would see at run time)."""
        if top in STDLIB:
            return True
        try:
            import importlib.util
            return importlib.util.find_spec(top) is not None
        except Exception:
            return False

    def accelerator(self, top):
        """`top` is a CPython C accelerator (`_bisect`, `_heapq`, `_decimal`...): a compiled twin of a pure-Python
        module that the library imports under `try:` and replaces by the same code in Python when it is missing.
        The two are equal by the library's contract, so the guarded import takes the fallback."""
        if not top.startswith('_') or top.startswith('__') or top in MODELLED:
            return False
        if top in sys.builtin_module_names:
            return True
        try:
            import importlib.util
            spec = importlib.util.find_spec(top)
        except Exception:
            return False
        return spec is not None and (spec.origin in ('built-in', 'frozen') or str(spec.origin).endswith(('.so', '.pyd')))

    def import_failure(self, mod, node):
        """None when the import statement `node` (in a `try:` that catches ImportError) succeeds, else the text
        of the ModuleNotFoundError / ImportError CPython would raise. Local modules are searched like `load`;
        any other module succeeds when the build machine's CPython has it (the compiler then refuses it by
        name later if it cannot build it), except a C accelerator, which is taken as absent (`accel_failure` tells
        the caller, which then checks that the handler defines what the import would have bound)."""
        self.accel_failure = False
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        else:
            names = [self.absolute(mod, node)]
        for name in names:
            top = name.split('.')[0]
            if (isinstance(node, ast.ImportFrom) and node.level) or self.local_top(top):
                parts = name.split('.')
                for i in range(1, len(parts) + 1):
                    if self.load('.'.join(parts[:i]), mod, node) is None:
                        if i == 1 and not (isinstance(node, ast.ImportFrom) and node.level) and top in STDLIB:
                            break                       # a brace .ail that shadows a modelled module: a std import
                        return "No module named %r" % '.'.join(parts[:i])
                continue
            if self.accelerator(top):
                self.accel_failure = True
                return "No module named %r" % name
            if not self.cpython_has(top):
                return "No module named %r" % name
        return None

    TARGETS = {'linux': ('linux', 'posix'), 'linux-arm64': ('linux', 'posix'), 'macos': ('darwin', 'posix'),
               'macos-x86_64': ('darwin', 'posix'), 'windows': ('win32', 'nt')}

    def target_values(self):
        """(sys.platform, os.name) of the program being built: the host, or the --target of a cross build."""
        target = os.environ.get('AIL_TARGET')
        if not target and '--target' in sys.argv[:-1]:
            target = sys.argv[sys.argv.index('--target') + 1]
        return self.TARGETS.get(target, (sys.platform, os.name) if not target else (None, None))

    def std_bindings(self, mod):
        """Names bound by the standard-library imports at the top of `mod` (the analysis has not run yet when a
        condition is folded): name -> ('import', module) | ('from', module, name)."""
        found = {}
        for node in mod.tree.body:
            if isinstance(node, ast.Import) and not self.is_local_import(node):
                for a in node.names:
                    found[a.asname or a.name.split('.')[0]] = ('import', a.name)
            elif isinstance(node, ast.ImportFrom) and not node.level and not self.is_local_import(node):
                for a in node.names:
                    found[a.asname or a.name] = ('from', node.module, a.name)
        return found

    def static_value(self, mod, n, std=None):
        """The value of expression `n` when it only depends on the build: constants, `sys.platform`, `os.name`,
        `sys.version_info`, `sys.implementation.name`, `TYPE_CHECKING`, and comparisons, `not`, `and` / `or`, str
        `startswith` / `endswith` of those. _UNKNOWN otherwise."""
        if std is None:
            std = self.std_bindings(mod)
        if isinstance(n, ast.Constant):
            return n.value
        if isinstance(n, ast.Tuple):
            vals = [self.static_value(mod, e, std) for e in n.elts]
            return _UNKNOWN if any(v is _UNKNOWN for v in vals) else tuple(vals)
        if isinstance(n, ast.Name):
            if n.id == 'TYPE_CHECKING' and std.get(n.id) == ('from', 'typing', 'TYPE_CHECKING'):
                return False
            if n.id == '__debug__' and n.id not in mod.kinds:
                return True
            return _UNKNOWN
        if isinstance(n, ast.Attribute):
            chain, cur = [n.attr], n.value
            while isinstance(cur, ast.Attribute):
                chain.append(cur.attr)
                cur = cur.value
            if not isinstance(cur, ast.Name) or cur.id in mod.kinds or cur.id in mod.alias:
                return _UNKNOWN
            chain.reverse()
            signature = std.get(cur.id)
            if signature is None or signature[0] != 'import':
                return _UNKNOWN
            first = signature[1].split('.')[0]
            dotted = '.'.join([first] + chain) if (cur.id == first or '.' not in signature[1]) else None
            platform, osname = self.target_values()
            if dotted == 'sys.platform':
                return platform if platform is not None else _UNKNOWN
            if dotted == 'os.name':
                return osname if osname is not None else _UNKNOWN
            if dotted == 'sys.version_info':
                return tuple(sys.version_info)
            if dotted == 'sys.implementation.name':
                return 'cpython'
            if dotted == 'typing.TYPE_CHECKING':
                return False
            return _UNKNOWN
        if isinstance(n, ast.Subscript):
            base = self.static_value(mod, n.value, std)
            if base is _UNKNOWN or not isinstance(base, tuple):
                return _UNKNOWN
            if isinstance(n.slice, ast.Slice):
                parts = [None if x is None else self.static_value(mod, x, std) for x in (n.slice.lower, n.slice.upper, n.slice.step)]
                return _UNKNOWN if any(x is _UNKNOWN for x in parts) else base[slice(*parts)]
            index = self.static_value(mod, n.slice, std)
            return base[index] if isinstance(index, int) and -len(base) <= index < len(base) else _UNKNOWN
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not):
            v = self.static_value(mod, n.operand, std)
            return _UNKNOWN if v is _UNKNOWN else (not v)
        if isinstance(n, ast.BoolOp):
            vals = [self.static_value(mod, e, std) for e in n.values]
            is_and = isinstance(n.op, ast.And)
            for v in vals:
                if v is _UNKNOWN:
                    return _UNKNOWN
                if bool(v) != is_and:
                    return v
            return vals[-1]
        if isinstance(n, ast.Compare):
            left = self.static_value(mod, n.left, std)
            if left is _UNKNOWN:
                return _UNKNOWN
            ops = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt, ast.LtE: operator.le,
                   ast.Gt: operator.gt, ast.GtE: operator.ge, ast.In: lambda a, b: a in b,
                   ast.NotIn: lambda a, b: a not in b}
            for op, comparator in zip(n.ops, n.comparators):
                right = self.static_value(mod, comparator, std)
                if right is _UNKNOWN or type(op) not in ops:
                    return _UNKNOWN
                try:
                    if not ops[type(op)](left, right):
                        return False
                except TypeError:
                    return _UNKNOWN
                left = right
            return True
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ('startswith', 'endswith')
                and len(n.args) == 1 and not n.keywords):
            base, arg = self.static_value(mod, n.func.value, std), self.static_value(mod, n.args[0], std)
            if isinstance(base, str) and isinstance(arg, (str, tuple)):
                return getattr(base, n.func.attr)(arg)
        return _UNKNOWN

    def resolve_guarded(self, mod):
        """Replace each `try:` whose body only imports (and binds constants) and has a handler for ImportError by
        the branch CPython would take: the body (and `else`) when every import succeeds, else the imports before the
        first failing one and the first handler that catches it. The handler name, if any, is bound to the error."""
        def simple(s):
            if isinstance(s, (ast.Import, ast.ImportFrom, ast.Pass)):
                return True
            if isinstance(s, ast.Assign):
                return isinstance(s.value, (ast.Constant, ast.Name)) and all(isinstance(t, ast.Name) for t in s.targets)
            return False

        def own_imports(stmts):
            """The import statements in `stmts`, not looking into nested functions and classes."""
            out = []
            for s in stmts:
                if isinstance(s, (ast.Import, ast.ImportFrom)):
                    out.append(s)
                elif not isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    for field in ('body', 'orelse', 'finalbody'):
                        if isinstance(getattr(s, field, None), list):
                            out.extend(own_imports(getattr(s, field)))
                    for sub in list(getattr(s, 'handlers', None) or ()) + list(getattr(s, 'cases', None) or ()):
                        out.extend(own_imports(sub.body))
            return out

        def prune(node):
            """Drop what only ImportError handlers would catch: the imports of the body all succeed."""
            kept = []
            for h in node.handlers:
                if h.type is not None:
                    types = h.type.elts if isinstance(h.type, ast.Tuple) else [h.type]
                    rest = [t for t in types if not (isinstance(t, ast.Name)
                                                     and t.id in ('ImportError', 'ModuleNotFoundError'))]
                    if not rest:
                        continue
                    if len(rest) != len(types):
                        h.type = rest[0] if len(rest) == 1 else ast.Tuple(rest, ast.Load())
                kept.append(h)
            node.handlers = kept
            if not kept and not node.finalbody:
                return node.body + node.orelse
            return None

        def needed(stmt):
            """The names a successful import statement would bind (a star import: none)."""
            if isinstance(stmt, ast.Import):
                return {a.asname or a.name.split('.')[0] for a in stmt.names}
            return {a.asname or a.name for a in stmt.names if a.name != '*'}

        def fallback_defines(stmt, handler):
            """A C accelerator that is taken as absent needs a handler that defines what the import would have bound."""
            if not self.accel_failure:
                return
            missing = needed(stmt) - set(_scan_scope(handler.body)[0])
            if missing:
                self.refuse(mod, stmt, "import of the CPython C module %r guarded by `except ImportError`: this compiler "
                            "does not provide it, and the handler does not define %s, so there is no Python fallback.\n"
                            "  write instead: define %s in the handler, or import it without `try:`"
                            % (stmt.module if isinstance(stmt, ast.ImportFrom) else stmt.names[0].name,
                               ', '.join(sorted(missing)), ', '.join(sorted(missing))))

        def handlers_without_import_errors(handlers):
            kept = []
            for h in handlers:
                if h.type is not None:
                    types = h.type.elts if isinstance(h.type, ast.Tuple) else [h.type]
                    rest = [t for t in types if not (isinstance(t, ast.Name)
                                                     and t.id in ('ImportError', 'ModuleNotFoundError'))]
                    if not rest:
                        continue
                    if len(rest) != len(types):
                        h = copy.copy(h)
                        h.type = rest[0] if len(rest) == 1 else ast.Tuple(rest, ast.Load())
                kept.append(h)
            return kept

        def replace(node):
            imports = own_imports(node.body)
            if not imports:
                return None
            if not all(map(simple, node.body)):
                direct = [i for i, st in enumerate(node.body) if isinstance(st, (ast.Import, ast.ImportFrom))]
                for i in direct:
                    text = self.import_failure(mod, node.body[i])
                    if text is None:
                        continue
                    stmt = node.body[i]
                    for h in node.handlers:
                        if self.handler_catches(h, text.startswith('No module named')):
                            fallback_defines(stmt, h)
                            # the statements before the import run; then (no exception) the handler's body
                            body = list(h.body)
                            if h.name:
                                error = ast.Call(ast.Name('ImportError', ast.Load()), [ast.Constant(text)], [])
                                body.insert(0, ast.copy_location(ast.Assign([ast.Name(h.name, ast.Store())], error), h))
                            pre = node.body[:i] or [ast.copy_location(ast.Pass(), node)]
                            others = handlers_without_import_errors(node.handlers)
                            if not others and not node.finalbody:
                                return node.body[:i] + body
                            if not others:
                                return [ast.copy_location(ast.Try(body=node.body[:i] + body, handlers=[], orelse=[],
                                                                   finalbody=node.finalbody), node)]
                            return [ast.copy_location(ast.Try(body=pre, handlers=others, orelse=body,
                                                               finalbody=node.finalbody), node)]
                    self.refuse(mod, stmt, "the import fails here (%s) and no handler of this `try` catches ImportError: "
                                "CPython stops with ModuleNotFoundError.\n  write instead: remove the import, or provide "
                                "the module" % text)
                for stmt in imports:
                    text = self.import_failure(mod, stmt)
                    if text is not None:
                        self.refuse(mod, stmt, "the import fails here (%s), inside a `try:` in a nested statement; "
                                    "CPython would run the handler, and the compiler can only choose a branch for an "
                                    "import that is a direct statement of the `try:`.\n  write instead: put the "
                                    "import directly in the `try:` body" % text)
                return prune(node)
            if not node.handlers or not any(self.handler_catches(h, True) or self.handler_catches(h, False)
                                            for h in node.handlers):
                for stmt in imports:
                    text = self.import_failure(mod, stmt)
                    if text is not None:
                        self.refuse(mod, stmt, "the import fails here (%s) and no handler of this `try` catches "
                                    "ImportError: CPython stops with ModuleNotFoundError.\n  write instead: remove "
                                    "the import, or provide the module" % text)
                return None
            pre, failed = [], None
            for s in node.body:
                if isinstance(s, (ast.Import, ast.ImportFrom)):
                    text = self.import_failure(mod, s)
                    if text is not None:
                        failed = (s, text)
                        accelerated = self.accel_failure
                        break
                pre.append(s)
            if failed is not None:
                self.accel_failure = accelerated
            if failed is None:
                return pre + node.orelse + node.finalbody
            stmt, text = failed
            for h in node.handlers:
                if self.handler_catches(h, text.startswith('No module named')):
                    fallback_defines(stmt, h)
                    body = list(h.body)
                    if h.name:
                        error = ast.Call(ast.Name('ImportError', ast.Load()), [ast.Constant(text)], [])
                        body.insert(0, ast.copy_location(ast.Assign([ast.Name(h.name, ast.Store())], error), h))
                    return pre + body + node.finalbody
            self.refuse(mod, stmt, "the import fails here (%s) and no handler of this `try` catches ImportError: "
                        "CPython stops with ModuleNotFoundError.\n  write instead: remove the import, or provide the "
                        "module" % text)

        def block(stmts):
            out = []
            for s in stmts:
                if isinstance(s, ast.If):
                    value = self.static_value(mod, s.test)
                    if value is not _UNKNOWN and (own_imports(s.body) or own_imports(s.orelse)):
                        out.extend(block(s.body if value else s.orelse))
                        continue
                if isinstance(s, ast.Try):
                    got = replace(s)
                    if got is not None:
                        out.extend(block(got))
                        continue
                for field in ('body', 'orelse', 'finalbody'):
                    old = getattr(s, field, None)
                    if isinstance(old, list) and old:
                        setattr(s, field, block(old) or [ast.copy_location(ast.Pass(), s)])
                for h in getattr(s, 'handlers', None) or ():
                    h.body = block(h.body) or [ast.copy_location(ast.Pass(), h)]
                for case in getattr(s, 'cases', None) or ():
                    case.body = block(case.body) or [ast.copy_location(ast.Pass(), case)]
                out.append(s)
            return out
        mod.tree.body = block(mod.tree.body)

    def hoist_try_imports(self, mod):
        """A module-level `try:` that starts with local imports that succeed: the imports run first in CPython
        too, so they are moved in front of the `try:` where the module system understands them."""
        body, out = mod.tree.body, []
        for node in body:
            if isinstance(node, ast.Try):
                lead = 0
                while (lead < len(node.body) and isinstance(node.body[lead], (ast.Import, ast.ImportFrom))
                       and self.is_local_import(node.body[lead])
                       and self.import_failure(mod, node.body[lead]) is None):
                    lead += 1
                if lead:
                    out.extend(node.body[:lead])
                    node.body = node.body[lead:] or [ast.copy_location(ast.Pass(), node)]
            out.append(node)
        mod.tree.body = out

    def split_conflicting_imports(self, mod):
        """A function that binds one name to different local modules in different branches
        (`if c: import a as impl` / `else: import b as impl`) and only reads attributes of it (`impl.f(x)`): each
        import gets a name of its own, the branch records which one ran in `impl` (a number), and each
        `impl.f` becomes `a.f if impl == 0 else b.f`. A function that uses `impl` in any other way keeps the
        conflict, which is refused by name later."""
        def functions(stmts):
            for st in stmts:
                if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield st
                for field in ('body', 'orelse', 'finalbody'):
                    if isinstance(getattr(st, field, None), list):
                        yield from functions(getattr(st, field))
                for sub_node in list(getattr(st, 'handlers', None) or ()) + list(getattr(st, 'cases', None) or ()):
                    yield from functions(sub_node.body)
        for fn in list(functions(mod.tree.body)):
            groups, todo = {}, list(fn.body)
            while todo:
                st = todo.pop(0)
                if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    continue
                if isinstance(st, ast.Import) and len(st.names) == 1 and st.names[0].asname and self.is_local_import(st):
                    groups.setdefault(st.names[0].asname, []).append(st)
                for field in ('body', 'orelse', 'finalbody'):
                    if isinstance(getattr(st, field, None), list):
                        todo.extend(getattr(st, field))
                for sub_node in list(getattr(st, 'handlers', None) or ()) + list(getattr(st, 'cases', None) or ()):
                    todo.extend(sub_node.body)
            for name, group in groups.items():
                if len({st.names[0].name for st in group}) < 2:
                    continue
                reads = sum(1 for x in ast.walk(fn) if isinstance(x, ast.Name) and x.id == name)
                attrs = [x for x in ast.walk(fn) if isinstance(x, ast.Attribute) and isinstance(x.value, ast.Name)
                         and x.value.id == name and isinstance(x.ctx, ast.Load)]
                if reads != len(attrs) or any(isinstance(x, ast.Name) and x.id == name and not isinstance(x.ctx, ast.Load)
                                              for x in ast.walk(fn)):
                    continue
                aliases = ['_ail_alt%d_%s' % (k, name) for k in range(len(group))]
                by_id = {id(st): k for k, st in enumerate(group)}

                class Split(ast.NodeTransformer):
                    def visit_Import(self, node):
                        k = by_id.get(id(node))
                        if k is None:
                            return node
                        node.names[0].asname = aliases[k]
                        record = ast.Assign([ast.Name(name, ast.Store())], ast.Constant(k))
                        ast.copy_location(record, node)
                        return [node, record]

                    def visit_Attribute(self, node):
                        self.generic_visit(node)
                        if isinstance(node.value, ast.Name) and node.value.id == name and isinstance(node.ctx, ast.Load):
                            chosen = ast.Attribute(ast.Name(aliases[-1], ast.Load()), node.attr, ast.Load())
                            for k in range(len(aliases) - 2, -1, -1):
                                test = ast.Compare(ast.Name(name, ast.Load()), [ast.Eq()], [ast.Constant(k)])
                                chosen = ast.IfExp(test, ast.Attribute(ast.Name(aliases[k], ast.Load()), node.attr,
                                                                       ast.Load()), chosen)
                            return ast.copy_location(chosen, node)
                        return node
                Split().visit(fn)

    def rename_conflicting_function_imports(self, mod):
        """Two functions that import the same name from different places (`from pyfunc import to_c` in one,
        `from pyc import to_c` in another) have two local names in CPython. The lifted imports share one module-level
        alias table, so each of them gets a name of its own: the name is renamed inside the function."""
        def functions(stmts):
            for st in stmts:
                if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield st
                for field in ('body', 'orelse', 'finalbody'):
                    if isinstance(getattr(st, field, None), list):
                        yield from functions(getattr(st, field))
                for sub_node in list(getattr(st, 'handlers', None) or ()) + list(getattr(st, 'cases', None) or ()):
                    yield from functions(sub_node.body)

        def own_imports(fn):
            out, todo = [], list(fn.body)
            while todo:
                st = todo.pop(0)
                if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    continue
                if isinstance(st, (ast.Import, ast.ImportFrom)) and self.is_local_import(st):
                    out.append(st)
                for field in ('body', 'orelse', 'finalbody'):
                    if isinstance(getattr(st, field, None), list):
                        todo.extend(getattr(st, field))
                for sub_node in list(getattr(st, 'handlers', None) or ()) + list(getattr(st, 'cases', None) or ()):
                    todo.extend(sub_node.body)
            return out

        bindings = {}                    # bound name -> {target: [(function, alias node)]}
        for fn in functions(mod.tree.body):
            for st in own_imports(fn):
                try:
                    where = self.absolute(mod, st) if isinstance(st, ast.ImportFrom) else None
                except ModuleRefusal:
                    continue
                for a in st.names:
                    if a.name == '*':
                        continue
                    if isinstance(st, ast.ImportFrom):
                        bound, target = a.asname or a.name, ('from', where, a.name)
                    elif a.asname:
                        bound, target = a.asname, ('import', a.name)
                    else:
                        continue
                    bindings.setdefault(bound, {}).setdefault(target, []).append((fn, a))
        top_names = set(_scan_scope([x for x in mod.tree.body if not (id(x) in mod.lazy)])[0])
        for name, targets in bindings.items():
            if len(targets) < 2 or name in top_names:
                continue
            owners = [fn for entries in targets.values() for fn, _ in entries]
            if len(set(map(id, owners))) != len(owners):
                continue                 # one function binds the name twice: the other split handles `import as`
            for fn in owners:
                if any((isinstance(x, ast.Name) and x.id == name and not isinstance(x.ctx, ast.Load))
                       or (isinstance(x, ast.arg) and x.arg == name)
                       or (isinstance(x, (ast.Global, ast.Nonlocal)) and name in x.names) for x in ast.walk(fn)):
                    break
            else:
                for k, entries in enumerate(targets.values()):
                    new = '_ail_f%d_%s' % (k, name)
                    for fn, alias in entries:
                        alias.asname = new
                        for x in ast.walk(fn):
                            if isinstance(x, ast.Name) and x.id == name:
                                x.id = new

    # standard modules that the front end's source passes rewrite and only accept imported at the top of the file
    TOP_ONLY = frozenset(('pathlib', 'hashlib', 'hmac', 'secrets', 'base64', 'sqlite3', 'urllib'))

    def hoist_std_imports(self, mod):
        """`import pathlib` / `from hashlib import sha256` inside a function of a merged program: the front end wants
        these at the top of the file, and importing a standard module has no effect that depends on when it runs, so
        the import moves to the top of the module (a name that the module also assigns is left alone)."""
        found, stores = [], None

        def walk(stmts, in_function):
            for st in stmts:
                if in_function and isinstance(st, (ast.Import, ast.ImportFrom)) and not self.is_local_import(st):
                    names = [st.module or ''] if isinstance(st, ast.ImportFrom) and not st.level else (
                        [a.name for a in st.names] if isinstance(st, ast.Import) else [])
                    if names and all(n.split('.')[0] in self.TOP_ONLY for n in names):
                        found.append(st)
                inner = in_function or isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef))
                for field in ('body', 'orelse', 'finalbody'):
                    if isinstance(getattr(st, field, None), list):
                        walk(getattr(st, field), inner)
                for sub_node in list(getattr(st, 'handlers', None) or ()) + list(getattr(st, 'cases', None) or ()):
                    walk(sub_node.body, inner)
        walk(mod.tree.body, False)
        if not found:
            return
        stores = set(_scan_scope(mod.tree.body)[0])
        for x in ast.walk(mod.tree):
            if isinstance(x, ast.Global):
                stores.update(x.names)
        body = mod.tree.body
        at = 0
        while at < len(body) and (isinstance(body[at], (ast.Import, ast.ImportFrom)) or at == 0 and isinstance(
                body[at], ast.Expr) and isinstance(body[at].value, ast.Constant) and isinstance(body[at].value.value, str)):
            at += 1
        seen, add = set(), []
        for st in found:
            bound = [(a.asname or a.name.split('.')[0]) for a in st.names]
            if any(b in stores for b in bound):
                continue
            key = ast.dump(st)
            clone = copy.deepcopy(st)
            ast.copy_location(clone, st)
            st.__class__ = ast.Pass
            st.__dict__.clear()
            ast.copy_location(st, clone)
            if key not in seen:
                seen.add(key)
                add.append(clone)
        body[at:at] = add

    def lift_lazy(self, mod):
        self.resolve_guarded(mod)
        self.hoist_try_imports(mod)
        self.hoist_std_imports(mod)
        self.split_conflicting_imports(mod)
        self.rename_conflicting_function_imports(mod)
        """A local import inside a function is moved to the module's top level: a synthetic copy goes
        at the end of the module body (at the start for the entry file) and the statement itself
        becomes `pass`; the function then reads the name as a module-level alias. That is the same
        program as CPython's when the imported modules have no side effects at import time (checked
        when the module is spliced in: see `impure`); any other local import below the top level is
        refused."""
        top = {id(n) for n in mod.tree.body}
        found = []
        module_level = set()           # ids of imports under a condition, loop or try at module level
        cur_top = [None]                # the top-level statement being visited

        def module_reads(stmt):
            """Names read by `stmt` when the module body runs (function bodies do not run then)."""
            names, todo = set(), [stmt]
            while todo:
                n = todo.pop()
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                    todo.extend(n.decorator_list if not isinstance(n, ast.Lambda) else [])
                    todo.extend(_defaults(n.args))
                    continue
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                    names.add(n.id)
                todo.extend(ast.iter_child_nodes(n))
            return names

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
                if scope == 'class':
                    refuse(child, "inside a class body")
                if scope != 'func':
                    # started where it stands, like a function-level import, when no module-level code outside the
                    # statement that holds it reads what it binds (CPython would fail there when the import did not run)
                    bound = {a.asname or a.name.split('.')[0] for a in child.names}
                    dotted = isinstance(child, ast.Import) and any('.' in a.name and not a.asname for a in child.names)
                    if dotted or any(bound & module_reads(x) for x in mod.tree.body if x is not cur_top[0]):
                        refuse(child, "inside a condition, loop or try block at module level, and the code after it "
                               "reads %s (or binds a submodule)" % ', '.join(sorted(bound)))
                    module_level.add(id(child))
                if tried:
                    # the module is found (its import cannot raise ImportError), so the handlers never see it
                    failure = self.import_failure(mod, child)
                    if failure is not None:
                        refuse(child, "inside a try block, and the import fails there (%s), which this try's "
                               "handlers would catch; the code that runs then is more than an import" % failure)
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
            # imports are statements: walk the statement lists only (not the expressions in between)
            for field in ('body', 'orelse', 'finalbody'):
                value = getattr(node, field, None)
                if isinstance(value, list):
                    for index, child in enumerate(value):
                        if isinstance(child, ast.stmt):
                            if node is mod.tree:
                                cur_top[0] = child
                            handle(node, field, value, index, child, scope, tried)
            for sub in list(getattr(node, 'handlers', None) or ()) + list(getattr(node, 'cases', None) or ()):
                visit(sub, scope, tried)
        visit(mod.tree, 'module', False)
        if not found:
            return
        forced = self.check_init_calls(mod, [n for _, _, n in found])
        synthetic = []
        for items, index, node in found:
            clone = copy.deepcopy(node)
            ast.copy_location(clone, node)
            mod.lazy[id(clone)] = node
            synthetic.append(clone)
            slot = ast.copy_location(ast.Pass(), node)
            mod.lazy_slot[id(clone)] = slot
            if forced or id(node) in module_level:
                mod.force_init.add(id(clone))
            items[index] = slot
        body = mod.tree.body
        if mod.entry or forced or module_level:
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
        point where the merged program has it. A class counts when it is called (`C()`, `C.make()`), not when
        it is only named as a base. True in that case: the imports are then started by the function that holds
        them (see `lazy_init`) and placed at the start of the module. (The entry file needs no check: its
        imports go first.)"""
        if mod.entry:
            return False
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
        def holds(n):
            """A statement under `n` (statement lists only) is one of `ids`."""
            if id(n) in ids:
                return True
            for field in ('body', 'orelse', 'finalbody', 'handlers', 'cases'):
                value = getattr(n, field, None)
                if isinstance(value, list) and any(holds(c) for c in value):
                    return True
            return False
        tainted = {name for name, n in defs.items() if holds(n)}
        reads = {name: {x.id for x in used(n, True)} for name, n in defs.items()} if tainted else {}
        changed = True
        while changed:
            changed = False
            for name, names in reads.items():
                if name not in tainted and not names.isdisjoint(tainted):
                    tainted.add(name)
                    changed = True
        if not tainted:
            return False
        for n in mod.tree.body:
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                continue
            if any(x.id in tainted for x in used(n, False)):
                return True
        return False

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

    def fold_apply(self, node, func, /, *args, **kwargs):
        try:
            return self.fold_check(func(*args, **kwargs))
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
            if (cur.id in mod.std and cur.id not in mod.kinds and mod.std[cur.id][0] == 'import'
                    and cur.id not in mod.alias):
                return None             # `ast.NodeTransformer`, `os.sep`: a name of a standard module, which does not change
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
        # the builtin method decorators, and `@prop.setter` on a property of the same class body
        if (isinstance(d, ast.Name) and d.id in ('staticmethod', 'classmethod', 'property')
                and d.id not in mod.kinds and d.id not in mod.alias and d.id not in mod.std):
            return None
        if (isinstance(d, ast.Attribute) and d.attr in ('setter', 'getter', 'deleter') and isinstance(d.value, ast.Name)
                and d.value.id not in mod.kinds and d.value.id not in mod.alias and d.value.id not in mod.std):
            return None
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
                bad = self.impure_expr(mod, node.value, env)
                if bad is None:
                    for t in node.targets:
                        if not isinstance(t, ast.Name) and not self.literal_unpack(t, node.value):
                            bad = t
                            break
                if bad is None:
                    for t in node.targets:
                        if isinstance(t, ast.Name):
                            assign(t, node.value, node, env)
                        else:                   # `A, B = 1, 2`
                            for e, v in zip(t.elts, node.value.elts):
                                assign(e, v, node, env)
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

    @staticmethod
    def literal_unpack(target, value):
        """`A, B = x, y`: names on the left, a literal of the same length on the right."""
        return (isinstance(target, (ast.Tuple, ast.List)) and all(isinstance(e, ast.Name) for e in target.elts)
                and isinstance(value, (ast.Tuple, ast.List)) and len(value.elts) == len(target.elts)
                and not any(isinstance(e, ast.Starred) for e in value.elts))

    MOVE_EFFECT_BUILTINS = frozenset(('print', 'input', 'open', 'exec', 'eval', 'compile', '__import__',
                                      'breakpoint', 'exit', 'quit', 'help', 'setattr', 'delattr'))
    MOVE_SAFE_BUILTINS = frozenset(('len', 'bool', 'abs', 'min', 'max', 'sum', 'sorted', 'tuple', 'list', 'dict',
                                    'set', 'frozenset', 'str', 'int', 'float', 'range', 'ord', 'chr', 'repr',
                                    'bytes', 'bytearray', 'round'))
    MOVE_EFFECT_METHODS = frozenset(('append', 'extend', 'insert', 'remove', 'pop', 'clear', 'sort', 'reverse',
                                     'update', 'setdefault', 'popitem', 'write', 'writelines', 'flush', 'close',
                                     'readline', 'readlines', 'seek', 'truncate', 'add', 'discard',
                                     'difference_update', 'intersection_update', 'symmetric_difference_update',
                                     'shuffle', 'seed'))
    MOVE_SAFE_METHODS = frozenset(('upper', 'lower', 'strip', 'lstrip', 'rstrip', 'split', 'rsplit', 'join',
                                   'replace', 'startswith', 'endswith', 'find', 'rfind', 'index', 'rindex', 'count',
                                   'format', 'encode', 'decode', 'isdigit', 'isalpha', 'isalnum', 'isspace',
                                   'islower', 'isupper', 'istitle', 'isnumeric', 'isdecimal', 'isidentifier',
                                   'title', 'capitalize', 'casefold', 'zfill', 'center', 'ljust', 'rjust',
                                   'partition', 'rpartition', 'splitlines', 'keys', 'values', 'items', 'get',
                                   'copy', 'union', 'intersection', 'difference', 'issubset', 'issuperset',
                                   'isdisjoint', 'bit_length', 'conjugate', 'hex', 'as_integer_ratio',
                                   'is_integer'))
    MOVE_EFFECT_STD = frozenset(('os.remove', 'os.unlink', 'os.rmdir', 'os.removedirs', 'os.mkdir', 'os.makedirs',
                                 'os.rename', 'os.renames', 'os.replace', 'os.chdir', 'os.system', 'os.popen',
                                 'os.putenv', 'os.unsetenv', 'os.chmod', 'os.chown', 'os.kill', 'os.abort',
                                 'os._exit', 'os.fork', 'os.execv', 'os.execve', 'os.spawnv', 'os.startfile',
                                 'sys.exit', 'sys.settrace', 'sys.setprofile', 'sys.stdout.write',
                                 'sys.stderr.write', 'shutil.copy', 'shutil.copy2', 'shutil.copyfile',
                                 'shutil.copytree', 'shutil.move', 'shutil.rmtree', 'time.sleep'))

    @staticmethod
    def exec_reads(node):
        """Names read when `node` runs as a module-level statement: a function body does not run at its
        definition, but its decorators, defaults and annotations do; a class body does run."""
        out = set()

        def walk(n):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for d in n.decorator_list:
                    walk(d)
                for d in _defaults(n.args):
                    walk(d)
                for arg in n.args.posonlyargs + n.args.args + n.args.kwonlyargs + [n.args.vararg, n.args.kwarg]:
                    if arg is not None and arg.annotation is not None:
                        walk(arg.annotation)
                if n.returns is not None:
                    walk(n.returns)
                return
            if isinstance(n, ast.Lambda):
                for d in _defaults(n.args):
                    walk(d)
                return
            if isinstance(n, ast.ClassDef):
                for d in n.decorator_list:
                    walk(d)
                for b in n.bases:
                    walk(b)
                for k in n.keywords:
                    walk(k.value)
                for s in n.body:
                    walk(s)
                return
            if isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name):
                out.add(n.target.id)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                out.add(n.id)
            for c in ast.iter_child_nodes(n):
                walk(c)
        walk(node)
        return out

    def function_node(self, mod, name):
        entry = mod.alias.get(name)
        if entry is not None:
            if entry[0] != 'member':
                return None
            owner, orig = entry[1], entry[2]
            kind = owner.kinds.get(orig)
        else:
            owner, orig = mod, name
            kind = mod.kinds.get(name)
        if kind != 'func':
            return None
        for node in owner.tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == orig:
                return owner, node
        return None

    def class_node(self, mod, name):
        entry = mod.alias.get(name)
        if entry is not None:
            if entry[0] != 'member':
                return None
            owner, orig = entry[1], entry[2]
            kind = owner.kinds.get(orig)
        else:
            owner, orig = mod, name
            kind = mod.kinds.get(name)
        if kind != 'class':
            return None
        for node in owner.tree.body:
            if isinstance(node, ast.ClassDef) and node.name == orig:
                return owner, node
        return None

    def resolve_def(self, mod, name, seen=None):
        """The function or class `name` means, following module-level aliases (`DEC = deco`)."""
        seen = set() if seen is None else seen
        key = (id(mod), name)
        if key in seen:
            return None
        seen.add(key)
        found = self.function_node(mod, name)
        if found is not None:
            return ('func',) + found
        found = self.class_node(mod, name)
        if found is not None:
            return ('class',) + found
        values = []
        for node in mod.tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                    and isinstance(node.targets[0], ast.Name) and node.targets[0].id == name:
                values.append(node.value)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) \
                    and node.target.id == name and node.value is not None:
                values.append(node.value)
        if len(values) == 1 and isinstance(values[0], ast.Name):
            return self.resolve_def(mod, values[0].id, seen)
        return None

    def function_reads(self, mod, name, seen):
        found = self.resolve_def(mod, name)
        if found is None or found[0] != 'func':
            return set()
        _, owner, fn = found
        key = ('func', id(owner), id(fn))
        if key in seen:
            return set()
        seen.add(key)
        out = set()
        local, _ = _function_locals(fn)
        for stmt in fn.body:
            names = self.exec_reads(stmt) - local
            out |= names
            for inner in names:
                out |= self.call_reads(owner, inner, seen)
        return out

    def class_init_reads(self, mod, name, seen):
        found = self.resolve_def(mod, name)
        if found is None or found[0] != 'class':
            return set()
        _, owner, cls = found
        key = ('class', id(owner), id(cls))
        if key in seen:
            return set()
        seen.add(key)
        init = next((s for s in cls.body if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef))
                     and s.name == '__init__'), None)
        if init is None:
            out = set()
            for base in cls.bases:
                if isinstance(base, ast.Name):
                    out |= self.class_init_reads(owner, base.id, seen)
            return out
        local, _ = _function_locals(init)
        out = set()
        for stmt in init.body:
            names = self.exec_reads(stmt) - local
            out |= names
            for inner in names:
                out |= self.call_reads(owner, inner, seen)
        return out

    def call_reads(self, mod, name, seen):
        found = self.resolve_def(mod, name)
        if found is None:
            return set()
        kind, owner, node = found
        if kind == 'func':
            key = ('func', id(owner), id(node))
            if key in seen:
                return set()
            seen.add(key)
            out = set()
            local, _ = _function_locals(node)
            for stmt in node.body:
                names = self.exec_reads(stmt) - local
                out |= names
                for inner in names:
                    out |= self.call_reads(owner, inner, seen)
            return out
        return self.class_init_reads(owner, node.name, seen)

    def std_call_name(self, mod, node):
        chain, cur = [], node
        while isinstance(cur, ast.Attribute):
            chain.append(cur.attr)
            cur = cur.value
        if not isinstance(cur, ast.Name):
            return None
        entry = mod.alias.get(cur.id)
        if entry is not None and entry[0] == 'mod':
            return ('local', entry[1], '.'.join(reversed(chain)))
        sig = mod.std.get(cur.id)
        if sig is None or cur.id in mod.kinds:
            return None
        if sig[0] == 'import':
            base = sig[1]
        elif sig[0] == 'from':
            base = (sig[1] or '') + '.' + sig[2]
        else:
            return None
        return ('std', '.'.join([base] + list(reversed(chain))))

    def move_bad_function(self, mod, owner, fn, seen):
        key = (id(owner), id(fn))
        if key in seen:
            return None
        seen.add(key)
        for stmt in fn.body:
            bad = self.move_bad_stmt(owner, stmt, seen)
            if bad is not None:
                return bad
        return None

    def move_bad_class_call(self, mod, owner, cls, seen):
        """Constructing a class defined here runs its `__init__`; accept a constructor that only binds
        names and attributes of its first parameter (the new instance) from values that are safe."""
        key = ('classcall', id(owner), id(cls))
        if key in seen:
            return None
        seen.add(key)
        if cls.keywords:
            return cls
        init = next((s for s in cls.body if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef))
                     and s.name == '__init__'), None)
        if init is None:
            for base in cls.bases:
                if not isinstance(base, ast.Name):
                    return base
                found = self.resolve_def(owner, base.id)
                if found is not None and found[0] == 'class':
                    bad = self.move_bad_class_call(owner, found[1], found[2], seen)
                    if bad is not None:
                        return bad
            return None
        args = init.args.posonlyargs + init.args.args
        first = args[0].arg if args else None
        local, _ = _function_locals(init)
        safe = {first} if first else set()

        def root_name(target):
            while isinstance(target, (ast.Attribute, ast.Subscript)):
                target = target.value
            return target.id if isinstance(target, ast.Name) else None

        def target_ok(target):
            if isinstance(target, ast.Name):
                return True
            if isinstance(target, (ast.Attribute, ast.Subscript)):
                return root_name(target) == first
            if isinstance(target, (ast.Tuple, ast.List)):
                return all(target_ok(e) for e in target.elts)
            return False

        def stmt_bad(node):
            kind = type(node)
            if kind is ast.Pass:
                return None
            if kind is ast.Assign:
                for t in node.targets:
                    if not target_ok(t):
                        return t
                return self.move_bad_expr(owner, node.value, seen)
            if kind is ast.AnnAssign:
                if not target_ok(node.target):
                    return node.target
                return self.move_bad_expr(owner, node.value, seen)
            if kind is ast.AugAssign:
                if not target_ok(node.target):
                    return node.target
                return self.move_bad_expr(owner, node.value, seen)
            if kind is ast.Expr:
                return self.move_bad_expr(owner, node.value, seen)
            if kind is ast.Return:
                return self.move_bad_expr(owner, node.value, seen)
            if kind is ast.If:
                bad = self.move_bad_expr(owner, node.test, seen)
                if bad is not None:
                    return bad
                for inner in node.body + node.orelse:
                    bad = stmt_bad(inner)
                    if bad is not None:
                        return bad
                return None
            if kind in (ast.For, ast.AsyncFor, ast.While):
                if kind is not ast.While:
                    bad = self.move_bad_expr(owner, node.iter, seen)
                    if bad is not None:
                        return bad
                if kind is ast.While:
                    bad = self.move_bad_expr(owner, node.test, seen)
                    if bad is not None:
                        return bad
                for inner in node.body + node.orelse:
                    bad = stmt_bad(inner)
                    if bad is not None:
                        return bad
                return None
            return node

        for stmt in init.body:
            bad = stmt_bad(stmt)
            if bad is not None:
                return bad
        return None

    @staticmethod
    def class_bound_names(cls):
        """The names a class body binds as plain class attributes (a method or a property is not one)."""
        names = set()
        for stmt in cls.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(stmt.name)
            elif isinstance(stmt, ast.Assign):
                for t in stmt.targets:
                    if isinstance(t, ast.Name):
                        names.add(t.id)
                    elif isinstance(t, (ast.Tuple, ast.List)):
                        names.update(e.id for e in t.elts if isinstance(e, ast.Name))
            elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                names.add(stmt.target.id)
        return names

    def instance_class(self, mod, name):
        """The local class whose constructor the module body binds to `name` once (otherwise None)."""
        values = []
        for node in mod.tree.body:
            if name not in _scan_scope([node])[0]:
                continue
            if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                    and isinstance(node.targets[0], ast.Name) and node.targets[0].id == name:
                values.append(node.value)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) \
                    and node.target.id == name and node.value is not None:
                values.append(node.value)
            else:
                return None
        if len(values) != 1 or not isinstance(values[0], ast.Call) \
                or not isinstance(values[0].func, ast.Name):
            return None
        found = self.resolve_def(mod, values[0].func.id)
        if found is not None and found[0] == 'class':
            return found[1], found[2]
        return None

    def instance_attr_safe(self, mod, owner, cls, attr):
        """Reading `instance.attr` is a plain lookup: the class binds it as a value, or its `__init__`
        assigns it from a safe expression, and no hook or property runs for it."""
        for node in ast.walk(cls):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and node.name in ('__getattr__', '__getattribute__'):
                return False
        for stmt in cls.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and stmt.name == attr:
                return False
            if isinstance(stmt, ast.ClassDef) and stmt.name == attr:
                return True
            if isinstance(stmt, ast.Assign):
                for t in stmt.targets:
                    if isinstance(t, ast.Name) and t.id == attr:
                        return True
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) \
                    and stmt.target.id == attr:
                return stmt.value is not None
        init = next((s for s in cls.body if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef))
                     and s.name == '__init__'), None)
        if init is not None:
            args = init.args.posonlyargs + init.args.args
            first = args[0].arg if args else None
            for node in ast.walk(init):
                if isinstance(node, ast.Assign):
                    targets = node.targets
                elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
                    targets = [node.target]
                else:
                    continue
                for t in targets:
                    if isinstance(t, ast.Attribute) and t.attr == attr \
                            and isinstance(t.value, ast.Name) and t.value.id == first:
                        return True
        for base in cls.bases:
            if isinstance(base, ast.Name):
                found = self.resolve_def(owner, base.id)
                if found is not None and found[0] == 'class' \
                        and self.instance_attr_safe(owner, found[1], found[2], attr):
                    return True
        return False

    def move_bad_attr(self, mod, node, seen):
        """A load of `expr.name`: only a settled module value, a known standard constant, a plain class
        attribute, or an instance attribute a local constructor binds is safe to compute early."""
        chain, cur = [], node
        while isinstance(cur, ast.Attribute):
            chain.append(cur.attr)
            cur = cur.value
        if not isinstance(cur, ast.Name):
            return node
        name = cur.id
        entry = mod.alias.get(name)
        if entry is not None and entry[0] == 'mod':
            return None
        if entry is not None:
            found = self.class_node(mod, name)
            if len(chain) == 1 and found is not None and not found[1].keywords \
                    and not self.hooked(mod) and chain[0] in self.class_bound_names(found[1]):
                return None
            return node
        if name in mod.std and name not in mod.kinds and name not in mod.alias:
            dotted = '.'.join([name] + list(reversed(chain)))
            return None if dotted in self.STD_ATTRS else node
        if mod.kinds.get(name) == 'class':
            found = self.class_node(mod, name)
            if len(chain) == 1 and found is not None and not found[1].keywords \
                    and not self.hooked(mod) and chain[0] in self.class_bound_names(found[1]):
                return None
            return node
        env = getattr(self, '_move_env', None)
        if env is not None:
            try:
                value = self.fold(mod, cur, env)
            except (_Unfoldable, _Raises):
                value = _UNKNOWN
            if value is not _UNKNOWN:
                obj = value
                for attr in reversed(chain):
                    if not hasattr(obj, attr):
                        return node
                    obj = getattr(obj, attr)
                return None
        found = self.instance_class(mod, name)
        if found is not None and len(chain) == 1 \
                and self.instance_attr_safe(mod, found[0], found[1], chain[0]):
            return None
        return node

    def move_safe_method(self, mod, node):
        """A method call that cannot run user code: the receiver is a value this module builds from
        constants, and the method is one of the built-in text/container operations."""
        env = getattr(self, '_move_env', None)
        if env is None:
            return False
        try:
            value = self.fold(mod, node, env)
        except (_Unfoldable, _Raises):
            return False
        return isinstance(value, (str, bytes, list, tuple, dict, set, frozenset, int, float, bool))

    def move_bad_call(self, mod, node, seen):
        func = node.func
        if isinstance(func, ast.Name):
            name = func.id
            found = self.function_node(mod, name)
            if found is not None:
                return self.move_bad_function(mod, found[0], found[1], seen)
            resolved = self.resolve_def(mod, name)
            if resolved is not None:
                kind, owner, item = resolved
                if kind == 'func':
                    return self.move_bad_function(owner, owner, item, seen)
                return self.move_bad_class_call(owner, owner, item, seen)
            if name in mod.std and name not in mod.kinds:
                sig = mod.std[name]
                dotted = ((sig[1] if sig[0] == 'import' else (sig[1] or '') + '.' + sig[2])
                          if len(sig) > 1 else name)
                if dotted in self.MOVE_EFFECT_STD or name in self.MOVE_EFFECT_BUILTINS:
                    return node
                return node             # a standard function may read state or raise
            if hasattr(builtins, name) and name not in mod.kinds and name not in mod.alias:
                return node if name not in self.MOVE_SAFE_BUILTINS else None
            return node
        if isinstance(func, ast.Attribute):
            info = self.std_call_name(mod, func)
            if info is not None:
                if info[0] == 'std':
                    return node        # only a known pure function would be safe, and none is listed
                owner, attr = info[1], info[2]
                if '.' not in attr and owner.kinds.get(attr) == 'func':
                    for inner in owner.tree.body:
                        if isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef)) and inner.name == attr:
                            return self.move_bad_function(mod, owner, inner, seen)
                return node
            attr = func.attr
            if attr in self.MOVE_EFFECT_METHODS:
                return node
            if attr in self.MOVE_SAFE_METHODS and self.move_safe_method(mod, func.value):
                return None
            return node
        return node

    def move_bad_expr(self, mod, node, seen, annotation=False):
        if node is None:
            return None
        env = getattr(self, '_move_env', None)
        folded = False
        if env is not None:
            try:
                self.fold(mod, node, env)
                folded = True
            except _Raises as exc:
                return exc.node
            except _Unfoldable:
                pass
        kind = type(node)
        if kind is ast.Subscript and not annotation and not folded:
            return node
        if kind is ast.Constant:
            return None
        if kind is ast.Name:
            if isinstance(node.ctx, ast.Load):
                if mod.alias.get(node.id) is None and mod.kinds.get(node.id) == 'var' \
                        and self.runtime_written(mod, node.id):
                    return node
                return self.reads_state(mod, node, set())
            return None
        if kind is ast.Attribute:
            if isinstance(node.ctx, ast.Load):
                bad = self.reads_state(mod, node, set())
                if bad is not None:
                    return bad
                bad = self.move_bad_attr(mod, node, seen)
                if bad is not None:
                    return bad
            return self.move_bad_expr(mod, node.value, seen, annotation)
        if kind is ast.Call:
            for a in node.args:
                bad = self.move_bad_expr(mod, a, seen, annotation)
                if bad is not None:
                    return bad
            for k in node.keywords:
                bad = self.move_bad_expr(mod, k.value, seen, annotation)
                if bad is not None:
                    return bad
            return self.move_bad_call(mod, node, seen)
        if kind is ast.Lambda:
            for d in _defaults(node.args):
                bad = self.move_bad_expr(mod, d, seen)
                if bad is not None:
                    return bad
            return None
        if kind is ast.GeneratorExp:
            return None
        if kind in (ast.Await, ast.Yield, ast.YieldFrom, ast.NamedExpr):
            return node
        for c in ast.iter_child_nodes(node):
            if isinstance(c, ast.expr):
                bad = self.move_bad_expr(mod, c, seen, annotation)
                if bad is not None:
                    return bad
        return None

    def decorator_bad(self, mod, d):
        bad = self.impure_decorator(mod, d)
        if bad is None:
            return None
        target = d.func if isinstance(d, ast.Call) else d
        found = None
        if isinstance(target, ast.Name):
            resolved = self.resolve_def(mod, target.id)
            if resolved is not None and resolved[0] == 'func':
                found = (resolved[1], resolved[2])
        elif isinstance(target, ast.Attribute):
            info = self.std_call_name(mod, target)
            if info is not None and info[0] == 'local' and '.' not in info[2] \
                    and info[1].kinds.get(info[2]) == 'func':
                for inner in info[1].tree.body:
                    if isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef)) and inner.name == info[2]:
                        found = (info[1], inner)
                        break
        if found is not None:
            return self.move_bad_function(mod, found[0], found[1], set())
        return bad

    def move_bad_stmt(self, mod, node, seen):
        kind = type(node)
        if kind in (ast.Pass, ast.FunctionDef, ast.AsyncFunctionDef):
            if kind is not ast.Pass:
                for d in node.decorator_list:
                    bad = self.decorator_bad(mod, d)
                    if bad is not None:
                        return bad
                for d in _defaults(node.args):
                    bad = self.move_bad_expr(mod, d, seen)
                    if bad is not None:
                        return bad
            return None
        if kind is ast.ClassDef:
            for d in node.decorator_list:
                bad = self.decorator_bad(mod, d)
                if bad is not None:
                    return bad
            for b in node.bases:
                bad = self.move_bad_expr(mod, b, seen)
                if bad is not None:
                    return bad
            for k in node.keywords:
                bad = self.move_bad_expr(mod, k.value, seen)
                if bad is not None:
                    return bad
            for stmt in node.body:
                bad = self.move_bad_stmt(mod, stmt, seen)
                if bad is not None:
                    return bad
            return None
        if kind is ast.Assign:
            for t in node.targets:
                if isinstance(t, ast.Name):
                    continue
                if isinstance(t, (ast.Tuple, ast.List)) and all(isinstance(e, ast.Name) for e in t.elts):
                    continue
                return t
            return self.move_bad_expr(mod, node.value, seen)
        if kind is ast.AnnAssign:
            if not isinstance(node.target, ast.Name):
                return node.target
            bad = self.move_bad_expr(mod, node.annotation, seen, True)
            if bad is not None:
                return bad
            return self.move_bad_expr(mod, node.value, seen)
        if kind is ast.AugAssign:
            if not isinstance(node.target, ast.Name):
                return node.target
            return self.move_bad_expr(mod, node.value, seen)
        if kind is ast.Expr:
            return self.move_bad_expr(mod, node.value, seen)
        if kind is ast.If:
            bad = self.move_bad_expr(mod, node.test, seen)
            if bad is not None:
                return bad
            for stmt in node.body + node.orelse:
                bad = self.move_bad_stmt(mod, stmt, seen)
                if bad is not None:
                    return bad
            return None
        if kind in (ast.For, ast.AsyncFor, ast.While):
            if kind is not ast.While:
                bad = self.move_bad_expr(mod, node.iter, seen)
                if bad is not None:
                    return bad
            bad = self.move_bad_expr(mod, node.test, seen) if kind is ast.While else None
            if bad is not None:
                return bad
            for stmt in node.body + node.orelse:
                bad = self.move_bad_stmt(mod, stmt, seen)
                if bad is not None:
                    return bad
            return None
        if kind in (ast.Try, getattr(ast, 'TryStar', ast.Try)):
            for stmt in node.body + node.orelse + node.finalbody:
                bad = self.move_bad_stmt(mod, stmt, seen)
                if bad is not None:
                    return bad
            for handler in node.handlers:
                for stmt in handler.body:
                    bad = self.move_bad_stmt(mod, stmt, seen)
                    if bad is not None:
                        return bad
            return None
        if kind is ast.Match:
            bad = self.move_bad_expr(mod, node.subject, seen)
            if bad is not None:
                return bad
            for case in node.cases:
                if case.guard is not None:
                    bad = self.move_bad_expr(mod, case.guard, seen)
                    if bad is not None:
                        return bad
                for stmt in case.body:
                    bad = self.move_bad_stmt(mod, stmt, seen)
                    if bad is not None:
                        return bad
            return None
        if kind is ast.Return:
            return self.move_bad_expr(mod, node.value, seen)
        if kind in (ast.Global, ast.Nonlocal, ast.Import, ast.ImportFrom, ast.Delete, ast.Raise, ast.Assert,
                    ast.Break, ast.Continue, ast.With, ast.AsyncWith):
            return node
        return node

    def init_split(self, mod, where, orig):
        """For a module that a function starts when it runs (see `merge_program`): the top-level statements that go
        into the start function. Definitions (def, class) and imports are placed where the module is spliced in;
        every other statement goes into a function that runs when the import statement runs. A value a definition
        needs when it is defined is placed before the definitions, so its decorators, defaults and bases can read
        it; a statement that does something when it runs is still refused."""
        order = [n for n in mod.tree.body if id(n) not in mod.lazy]
        definitions = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)
        index = {id(n): i for i, n in enumerate(order)}

        def fold_value(value, env):
            try:
                return self.fold(mod, value, env)
            except (_Unfoldable, _Raises):
                return _UNKNOWN

        def apply_env(node, env):
            """Follow the constant module values a statement binds, so a later fold can tell whether a
            computation would raise (and would then have to keep its place among the effects)."""
            kind = type(node)
            if kind is ast.Assign:
                value = fold_value(node.value, env)
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        env[target.id] = value
                    elif self.literal_unpack(target, node.value):
                        for e, v in zip(target.elts, node.value.elts):
                            env[e.id] = fold_value(v, env)
                    else:
                        for name in _scan_scope([target])[0]:
                            env[name] = _UNKNOWN
            elif kind is ast.AnnAssign and isinstance(node.target, ast.Name):
                env[node.target.id] = fold_value(node.value, env) if node.value is not None else _UNKNOWN
            elif kind is ast.AugAssign and isinstance(node.target, ast.Name):
                old = env.get(node.target.id, _UNKNOWN)
                right = fold_value(node.value, env)
                op = self.FOLD_BINOPS.get(type(node.op))
                if old is _UNKNOWN or right is _UNKNOWN or op is None:
                    env[node.target.id] = _UNKNOWN
                else:
                    try:
                        env[node.target.id] = self.fold_apply(node, op, old, right)
                    except (_Unfoldable, _Raises):
                        env[node.target.id] = _UNKNOWN
            elif kind is ast.If:
                test = fold_value(node.test, env)
                if test is not _UNKNOWN:
                    for inner in (node.body if bool(test) else node.orelse):
                        apply_env(inner, env)
                else:
                    for name in _scan_scope(node.body + node.orelse)[0]:
                        env[name] = _UNKNOWN
            elif kind in (ast.For, ast.AsyncFor, ast.While, ast.Try, getattr(ast, 'TryStar', ast.Try),
                          ast.Match, ast.With, ast.AsyncWith):
                for name in _scan_scope([node])[0]:
                    env[name] = _UNKNOWN
            elif kind in (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef):
                env[node.name] = _UNKNOWN
            elif kind in (ast.Import, ast.ImportFrom):
                for a in node.names:
                    if a.name != '*':
                        env[a.asname or a.name.split('.')[0]] = _UNKNOWN
            elif kind is ast.Delete:
                for name in _scan_scope([node])[0]:
                    env[name] = _UNKNOWN

        env = collections.ChainMap({})
        envs = []
        for node in order:
            envs.append(dict(env))
            apply_env(node, env)

        bindings = {}
        for i, n in enumerate(order):
            for name in _scan_scope([n])[0]:
                bindings.setdefault(name, []).append(i)

        def latest(name, before):
            found = None
            for i in bindings.get(name, ()):
                if i < before:
                    found = i
                else:
                    break
            return found

        needed, unresolved, seen = set(), [], set()

        def read_names(node):
            names = self.exec_reads(node)
            extra = set()
            for name in names:
                extra |= self.call_reads(mod, name, seen)
            return names | extra

        def immutable(value):
            if isinstance(value, (int, float, complex, str, bytes, bool, range, type(None))):
                return True
            if isinstance(value, (tuple, frozenset)):
                return all(immutable(v) for v in value)
            return False

        effect_cache = {}

        def effectful(i):
            """The statement at `i` may change a value that is already bound (a call, a print, an
            in-place augmented assignment of a container, a loop, ...)."""
            if i in effect_cache:
                return effect_cache[i]
            node = order[i]
            if isinstance(node, definitions):
                effect_cache[i] = False
                return False
            result = None
            if type(node) is ast.AugAssign and isinstance(node.target, ast.Name):
                before = envs[i].get(node.target.id, _UNKNOWN)
                after = envs[i + 1].get(node.target.id, _UNKNOWN) if i + 1 < len(envs) else _UNKNOWN
                result = not immutable(before) or after is _UNKNOWN
            if not result:
                self._move_env = collections.ChainMap(dict(envs[i]))
                result = self.move_bad_stmt(mod, node, set()) is not None
            effect_cache[i] = result
            return result

        origin_cache = {}

        def origin(i, trail=None):
            """The earliest statement whose value the binding at `i` is made from (following aliases)."""
            if i in origin_cache:
                return origin_cache[i]
            trail = set() if trail is None else trail
            if i in trail:
                return i
            trail.add(i)
            node = order[i]
            if not isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                origin_cache[i] = i
                return i
            names = self.exec_reads(node)
            extra = set()
            local = set()
            for name in names:
                extra |= self.call_reads(mod, name, local)
            sources = [latest(name, i) for name in names | extra]
            sources = [j for j in sources if j is not None]
            got = min([i] + [origin(j, trail) for j in sources])
            origin_cache[i] = got
            return got

        def need_name(name, before, use):
            i = latest(name, before)
            if i is None:
                if not hasattr(builtins, name):
                    unresolved.append(use)
                return
            stmt = order[i]
            if not isinstance(stmt, definitions):
                value = envs[i + 1].get(name, _UNKNOWN) if i + 1 < len(envs) else _UNKNOWN
                if not immutable(value):
                    start = origin(i)
                    if any(effectful(j) for j in range(start + 1, before)):
                        unresolved.append(use)
                        return
                for j in bindings.get(name, ()):
                    if j >= i:
                        break
                    earlier = order[j]
                    if isinstance(earlier, definitions) or id(earlier) in needed:
                        continue
                    if effectful(j):
                        unresolved.append(use)
                        return
                    needed.add(id(earlier))
                    for inner in read_names(earlier):
                        need_name(inner, j, earlier)
            if isinstance(stmt, definitions) or id(stmt) in needed:
                return
            needed.add(id(stmt))
            for inner in read_names(stmt):
                need_name(inner, i, stmt)

        for i, node in enumerate(order):
            if isinstance(node, definitions):
                for name in read_names(node):
                    need_name(name, i, node)

        def statement_reads(node):
            names = set(self.exec_reads(node))
            extra = set()
            for name in names:
                extra |= self.call_reads(mod, name, set())
            return names | extra

        hoisted_bindings = {}
        for i, node in enumerate(order):
            if id(node) in needed and not isinstance(node, definitions):
                for name in _scan_scope([node])[0]:
                    hoisted_bindings.setdefault(name, []).append(i)

        for i, node in enumerate(order):
            if isinstance(node, definitions) or id(node) in needed:
                continue
            touched = statement_reads(node) | _scan_scope([node])[0]
            if any(hoisted_bindings.get(name) and hoisted_bindings[name][-1] > i
                   for name in touched):
                unresolved.append(node)
                break

        for i, node in enumerate(order):
            if id(node) in needed:
                self._move_env = collections.ChainMap(dict(envs[i]))
                bad = self.move_bad_stmt(mod, node, set())
                if bad is not None:
                    self.refuse(where, orig, "function-level `%s`: %s defines %s at import time (line %d), which uses a "
                                "value the module only computes when it runs, or does something when it is defined; the "
                                "compiler hoists definitions out of the code that a function-level import starts.\n"
                                "  write instead: move the import to the top of the file, or keep %s to definitions "
                                "whose decorators, defaults and bases are constants"
                                % (ast.unparse(orig), mod.path.name, ast.unparse(bad).split('\n')[0][:50],
                                   getattr(bad, 'lineno', -1), mod.path.name))
        if unresolved:
            bad = unresolved[0]
            self.refuse(where, orig, "function-level `%s`: %s defines %s at import time (line %d), which uses a "
                        "value the module only computes when it runs, or does something when it is defined; the "
                        "compiler hoists definitions out of the code that a function-level import starts.\n"
                        "  write instead: move the import to the top of the file, or keep %s to definitions "
                        "whose decorators, defaults and bases are constants"
                        % (ast.unparse(orig), mod.path.name, ast.unparse(bad).split('\n')[0][:50],
                           getattr(bad, 'lineno', -1), mod.path.name))
        def definition_bad(node):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for d in node.decorator_list:
                    bad = self.decorator_bad(mod, d)
                    if bad is not None:
                        return bad
                for d in _defaults(node.args):
                    bad = self.move_bad_expr(mod, d, set())
                    if bad is not None:
                        return bad
                for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs + [node.args.vararg, node.args.kwarg]:
                    if arg is not None and arg.annotation is not None:
                        bad = self.move_bad_expr(mod, arg.annotation, set(), True)
                        if bad is not None:
                            return bad
                return self.move_bad_expr(mod, node.returns, set(), True)
            if isinstance(node, ast.ClassDef):
                for d in node.decorator_list:
                    bad = self.decorator_bad(mod, d)
                    if bad is not None:
                        return bad
                for b in node.bases:
                    bad = self.move_bad_expr(mod, b, set())
                    if bad is not None:
                        return bad
                for k in node.keywords:
                    bad = self.move_bad_expr(mod, k.value, set())
                    if bad is not None:
                        return bad
                for stmt in node.body:
                    bad = self.move_bad_stmt(mod, stmt, set())
                    if bad is not None:
                        return bad
            return None

        bad = None
        for i, node in enumerate(order):
            if not isinstance(node, definitions):
                continue
            self._move_env = collections.ChainMap(dict(envs[i]))
            bad = definition_bad(node)
            if bad is not None:
                break
        if bad is not None:
            self.refuse(where, orig, "function-level `%s`: %s defines %s at import time (line %d), which uses a "
                        "value the module only computes when it runs, or does something when it is defined; the "
                        "compiler hoists definitions out of the code that a function-level import starts.\n"
                        "  write instead: move the import to the top of the file, or keep %s to definitions "
                        "whose decorators, defaults and bases are constants"
                        % (ast.unparse(orig), mod.path.name, ast.unparse(bad).split('\n')[0][:50],
                           getattr(bad, 'lineno', -1), mod.path.name))
        mod.hoisted = needed
        return [n for n in order if not isinstance(n, definitions) and id(n) not in needed
                and not (n is mod.tree.body[0] and isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)
                         and isinstance(n.value.value, str))]

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

    def origin(self, entry):
        """(module, name) a ('member', module, name) import ends up at, following re-exports of analysed modules."""
        owner, name = entry[1], entry[2]
        for _ in range(30):
            nxt = owner.alias.get(name) if owner.analysed else None
            if nxt is None or nxt[0] != 'member':
                break
            owner, name = nxt[1], nxt[2]
        return owner, name

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
        if (old is not None and old != entry and old[0] == 'member' and entry[0] == 'member'
                and self.origin(old) == self.origin(entry) and key not in mod.std):
            return                  # two function-level imports of one object (`pyc.to_c` is `pyfunc.to_c`)
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
            if inner[0] == 'var' and self.mutable(inner[1], inner[2]) and not (
                    name in mod.lazy_only and not self.runtime_written(inner[1], inner[2])):
                return ('var', mod, name)       # a function-level import of a name that only the module body sets
            return inner                        # reads the variable itself: its value is settled when the function runs
        if name in mod.std:
            return ('std', mod.std[name])
        if name in mod.kinds:
            return ('var', mod, name)
        return ('none',)

    def runtime_written(self, owner, key):
        """The variable `owner.key` is written after the module body has run: by a function that says `global`, or
        by `m.key = v` somewhere. (A name that the module body assigns more than once is settled when it ends.)"""
        if (owner, key) in self.ext:
            return True
        names = getattr(owner, 'global_names', None)
        if names is None:
            names = owner.global_names = {n for g in ast.walk(owner.tree) if isinstance(g, ast.Global) for n in g.names}
        return key in names

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
                    if inner[0] == 'var' and self.runtime_written(inner[1], inner[2]):
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
            if mod.entry:
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
            if kind == 'class':
                mod.merged[name] = fresh('%s__%s' % (mod.prefix, name))
    for mod in mods:
        if mod.entry:
            continue
        for node in mod.tree.body:
            # the compiler flattens a method to `Class__method`: keep the renamed class's from colliding
            if isinstance(node, ast.ClassDef) and mod.kinds.get(node.name) == 'class':
                used.update('%s__%s' % (mod.merged[node.name], m.name) for m in node.body
                            if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)))
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
        self.getter_fn = False        # inside a function of the form `def f(): import m; return m`
        self.ok_calls = set()         # ids of getter calls used as `f().name` or as a statement

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
        elif isinstance(node, ast.Call):
            return self.getter_of(node)
        return None

    def getter_of(self, call):
        """The module that `f()` returns when `f` is a getter (`def f(): import m; return m`), else None."""
        if call.args or call.keywords or not self.program.getters:
            return None
        func, found = call.func, None
        if isinstance(func, ast.Name) and self.module_level(func.id):
            found = self.program.resolve(self.mod, func.id)
        elif isinstance(func, ast.Attribute):
            base = self.module_ref(func.value)
            if base is not None:
                found = self.program.resolve(base, func.attr, 0, True)
        if found is None or found[0] != 'var':
            return None
        got = self.program.getters.get((found[1].name, found[2]))
        return None if got is None else got[0]

    def visit_Call(self, node):
        if not self.dry and id(node) not in self.ok_calls:
            target = self.getter_of(node)
            if target is not None:
                self.program.refuse(self.mod, node, "module %r returned by a call and used as a value (passed, stored "
                                    "or compared); this compiler needs a module to be named at each use.\n"
                                    "  write instead: use `%s().name` directly, or `import %s` where you use it"
                                    % (target.name, ast.unparse(node.func), target.name))
        self.generic_visit(node)
        return node

    def visit_Expr(self, node):
        if isinstance(node.value, ast.Call):
            self.ok_calls.add(id(node.value))
        self.generic_visit(node)
        return node

    def visit_Return(self, node):
        if (self.getter_fn and not self.dry and isinstance(node.value, ast.Name) and self.scopes
                and len(self.scopes) == 1):
            return ast.copy_location(ast.Return(ast.Constant(None)), node)
        self.generic_visit(node)
        return node

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
                value = self.program.dunder_node(self.mod, name)
                if value is None:
                    self.program.refuse(self.mod, node, "%s is not available: the program is built into one "
                                        "executable, so a module has no loader, spec or cache file at run time.\n"
                                        "  write instead: pass the value in as a constant or an argument" % name)
                return ast.copy_location(value, node)
            self.free.append((name, node))
        return node

    def visit_Attribute(self, node):
        target = self.module_ref(node.value)
        if target is None:
            self.generic_visit(node)
            return node
        if isinstance(node.value, ast.Call):
            return self.getter_attribute(node, target)
        return self.module_attribute(node, target)

    def getter_attribute(self, node, target):
        """`f().name` where `f` returns a module: the call still runs (it starts the module), then the name."""
        if self.dry:
            return node
        if not isinstance(node.ctx, ast.Load):
            self.program.refuse(self.mod, node, "`%s().%s` is assigned or deleted through a function that returns "
                                "module %s.\n  write instead: `import %s` and assign `%s.%s`"
                                % (ast.unparse(node.value.func), node.attr, target.name, target.name,
                                   target.name, node.attr))
        self.ok_calls.add(id(node.value))
        call = self.visit(node.value)
        value = self.module_attribute(ast.copy_location(ast.Attribute(ast.Name('_', ast.Load()), node.attr,
                                                                        ast.Load()), node), target)
        self.program.uses_after = True
        after = ast.Call(ast.Name(self.program.after_name, ast.Load()), [call, value], [])
        return ast.copy_location(after, node)

    def module_attribute(self, node, target):
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
        if attr in MODULE_DUNDERS and not stored:
            value = self.program.dunder_node(target, attr)
            if value is None:
                self.program.refuse(self.mod, node, "%s.%s is not available: the program is built into one "
                                    "executable.\n  write instead: pass the value in as a constant or an argument"
                                    % (target.name, attr))
            return ast.copy_location(value, node)
        if attr.startswith('__') and not attr.endswith('__') and any(s[0] == 'class' for s in self.scopes):
            # CPython rewrites `m.__x` in a class body to `m._Class__x`: a different (usually missing) attribute
            self.program.refuse(self.mod, node, "`%s.%s` inside a class body: CPython mangles a double-underscore "
                                "name there (to `_Class%s`), so it names a different attribute.\n  write instead: "
                                "read it outside the class" % (target.name, attr, attr))
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
        original_name = getattr(node, 'name', None)
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
        was_getter = self.getter_fn
        self.getter_fn = (not isinstance(node, ast.Lambda) and not self.scopes
                          and (self.program.getters.get((self.mod.name, original_name)) or (0, 0))[1]
                          is node)
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
        self.getter_fn = was_getter
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
               or isinstance(node, ast.Name) and node.id in ('__file__', '__package__')
               or isinstance(node, ast.Try) and any(isinstance(x, (ast.Import, ast.ImportFrom))
                                                    for b in node.body for x in ast.walk(b))
               for node in ast.walk(tree)):
        return None
    entry = Mod('__main__', program.entry_path, tree, True)
    program.entry = entry
    program.mods['__main__'] = entry
    program.prepare_entry(entry)
    program.discover(entry)
    program.check_star_packages()
    order = program.analyse_all(entry)
    reachable = [m for m in order if m is not entry]
    if not reachable and any(isinstance(node, (ast.Import, ast.ImportFrom)) and program.is_local_import(node)
                             for node in ast.walk(tree)):
        return None
    mods = [entry] + reachable
    program.prepare_stores(mods)
    program.check_lazy_values(mods)
    program.find_getters(mods)
    _assign_names(program, mods)
    classes = {}
    for mod in mods:
        if not mod.entry:
            for node in _module_classes(mod.tree):
                if node.name in mod.merged:
                    classes[mod.merged[node.name]] = (node.name, mod.name)

    output, std_seen, future, stack, positions = [], {}, [], [], {}
    program_ids = {getattr(n, f) for m in mods for n in ast.walk(m.tree) for f in ('id', 'name', 'arg', 'attr')
                   if isinstance(getattr(n, f, None), str)}

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

    def rewrite(mod, node, sink=None, lazily=False):
        """Rewrite one top-level statement of `mod` into `sink` (default: the program). `lazily`: the statement runs
        when a function starts the module, not while the importers' bodies run: the import-cycle checks that
        compare statement positions do not apply."""
        partial = set() if lazily else {m for m in stack if m is not mod}
        rewriter = Rewriter(program, mod, partial, positions)
        new = rewriter.visit(node)
        for name, use in rewriter.free:
            other = program.kept.get(name)
            if other is not None and other[0] is not mod and name in BUILTINS:
                program.refuse(mod, use, "%r means the builtin here, but %s binds its own %r and every module shares "
                               "one namespace after the merge.\n  write instead: rename %r in %s"
                               % (name, other[0].path.name, name, name, other[0].path.name))
        stamp(new, mod)
        (output if sink is None else sink).append(new)

    def snapshots(mod, imp, sink=None):
        for key, entry in imp.binds:
            if entry[0] == 'member' and key in mod.snaps:
                found = program.resolve(entry[1], entry[2])
                copy_stmt = ast.Assign(targets=[ast.Name(mod.snaps[key], ast.Store())],
                                       value=ast.Name(program.merged_name(found[1], found[2]), ast.Load()))
                ast.copy_location(copy_stmt, imp.node)
                stamp(copy_stmt, mod)
                (output if sink is None else sink).append(copy_stmt)

    lazy_ctx = []
    init_names = set()

    def call_stmt(name, mod, at):
        call = ast.Expr(ast.Call(ast.Name(name, ast.Load()), [], []))
        ast.copy_location(call, at)
        stamp(call, mod)
        return call

    def define_init(mod, body, first):
        """The function that runs `body` (the statements of `mod` that are not definitions) the first time it is
        called, with the module's globals declared; nothing when there is nothing to run."""
        calls = []
        for t in program.mods.values():
            if t.init_name and mod.name.startswith(t.name + '.') and t.kind != 'module':
                calls.append(call_stmt(t.init_name, mod, first))
        if not body and not calls:
            return
        base = '_ail_init_' + mod.prefix
        flag = '_ail_done_' + mod.prefix
        while base in init_names or base in program.kept or base in program_ids:
            base += '_'
            flag += '_'
        init_names.add(base)
        mod.init_name = base
        stores = _scan_scope(body)[0] if body else set()
        stores |= {n for stmt in body for x in ast.walk(stmt) if isinstance(x, ast.Global) for n in x.names}
        head = [ast.Global(names=[flag] + sorted(stores)),
                ast.If(ast.Name(flag, ast.Load()), [ast.Return(None)], []),
                ast.Assign([ast.Name(flag, ast.Store())], ast.Constant(True))]
        fn = ast.FunctionDef(name=base, args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[],
                                                          defaults=[]),
                             body=head + calls + body, decorator_list=[], returns=None, type_params=[])
        flag_stmt = ast.Assign([ast.Name(flag, ast.Store())], ast.Constant(False))
        for node in (flag_stmt, fn):
            ast.copy_location(node, first)
            stamp(node, mod)
            output.append(node)

    def patch_slot(mod, node, names):
        """The function-level import `node` (its stand-in `pass`) starts the module(s) in `names`, parents first
        (each start function calls its parents' first, so the last one is enough)."""
        slot = mod.lazy_slot[id(node)]
        slot.__class__ = ast.Expr
        slot.value = ast.Call(ast.Name(names[-1], ast.Load()), [], [])

    def imports_init_module(mod, seen):
        """A module that `mod` imports at its top level (directly or through the modules those import) starts by a
        function, so `mod` must start by a function too: its import runs when the function that holds it runs."""
        if mod in seen:
            return False
        seen.add(mod)
        for node in mod.tree.body:
            imp = mod.imps.get(id(node))
            if imp is None or not imp.local or id(node) in mod.lazy:
                continue
            for t in imp.chain:
                if t.done:
                    if t.init_name:
                        return True
                elif t not in stack and (program.impure(t) is not None or imports_init_module(t, seen)):
                    return True
        return False

    def expand(mod):
        init_mode = False
        where_orig = None
        if lazy_ctx and not mod.entry:
            where, orig, forced = lazy_ctx[-1]
            where_orig = (where, orig)
            init_mode = forced or program.impure(mod) is not None or imports_init_module(mod, set())
        init_body = None
        if init_mode:
            init_body = []
            program.init_split(mod, *where_orig)
        stack.append(mod)
        for index, node in enumerate(mod.tree.body):
            positions[mod] = index
            imp = mod.imps.get(id(node))
            if imp is not None and imp.local:
                lazy = id(node) in mod.lazy
                if lazy:
                    lazy_ctx.append((mod, mod.lazy[id(node)], id(node) in mod.force_init))
                touched = list(imp.chain)
                for target in imp.chain:
                    if target in stack:
                        if target in imp.stars:
                            program.refuse(mod, node, "`from %s import *` while %s is still running its own body "
                                           "(an import cycle).\n  write instead: name what you use, or break the "
                                           "cycle" % (target.name, target.name))
                    elif not target.done:
                        expand(target)
                for owner, orig in imp.members:
                    if owner in stack and owner.first.get(orig, NEVER) >= positions[owner] and not lazy:
                        child = program.child(owner, orig)
                        if child is None:
                            cycle = ' -> '.join(m.name for m in stack[stack.index(owner):] + [owner])
                            program.refuse(mod, node, "import cycle %s: `from %s import %s` runs before %s "
                                           "has defined %s, so CPython raises ImportError.\n"
                                           "  write instead: move %s into a module that both import"
                                           % (cycle, owner.name, orig, owner.name, orig, orig))
                        # the name is not bound yet, so CPython imports the submodule of that name
                        for key, entry in imp.binds:
                            if entry == ('member', owner, orig):
                                mod.alias[key] = ('mod', child)
                        touched.append(child)
                        if child not in stack and not child.done:
                            expand(child)
                if lazy:
                    lazy_ctx.pop()
                names = [t.init_name for t in touched if t.init_name]
                sink = init_body if init_mode else output
                if lazy:
                    if names:
                        patch_slot(mod, node, names)
                elif names:
                    for name in dict.fromkeys(names):
                        sink.append(call_stmt(name, mod, node))
                snapshots(mod, imp, sink)
                continue
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                emit_import(mod, node)
            elif mod.entry:
                rewrite(mod, node)
            elif index == 0 and isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) \
                    and isinstance(node.value.value, str):
                continue                                          # module docstring
            elif init_mode and not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) \
                    and id(node) not in mod.hoisted:
                rewrite(mod, node, init_body, True)
            else:
                rewrite(mod, node)
        if init_mode:
            define_init(mod, init_body, mod.tree.body[0] if mod.tree.body else mod.tree)
        mod.done = True
        stack.pop()

    program.after_name = '_ail_after'
    while program.after_name in program_ids or program.after_name in program.kept:
        program.after_name += '_'
    expand(entry)
    if program.uses_after:
        helper = ast.parse('def %s(_ail_a, _ail_b):\n    return _ail_b\n' % program.after_name).body[0]
        helper._ail_path = entry.path
        output.insert(0, helper)
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
    return Merged(text, _positions(module, text), program.notes, names, classes)


def _module_classes(tree):
    """The classes defined at a module's top level (also under `if` / `try` / `with`, not in a def or class)."""
    found, todo = [], list(tree.body)
    while todo:
        node = todo.pop()
        if isinstance(node, ast.ClassDef):
            found.append(node)
        elif not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for field in ('body', 'orelse', 'finalbody', 'handlers'):
                todo.extend(getattr(node, field, None) or [])
    return found


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
