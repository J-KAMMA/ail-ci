"""G1: Python-syntax programs made of several files in one directory (docs/design/GENERAL_PURPOSE.md s1).

`merge_program` reads the entry file and every sibling `m.py` / `m.ail` it imports (`import m`,
`import m as x`, `from m import f, C, K`, `from m import f as g`), and returns ONE Python module
text with the same behaviour as CPython running `python3 entry.py`:

* each module body is spliced in at its first import statement, so module-level code runs once,
  in CPython's order (depth first, at the position of the importing statement);
* top-level functions and variables of an imported module `m` are renamed `m__name`; classes keep
  their names (a class name is printed by repr, and it is refused when two modules define the
  same one); the entry module keeps all its names;
* `m.f` and names bound by `from m import f` become plain references to the merged name, using a
  scope analysis, so a local variable or parameter named like a module global is left alone;
* `__name__` is `"__main__"` in the entry module and the module name elsewhere; an
  `if __name__ == "__main__":` in an imported module is removed;
* a program with no import of a sibling file is not touched at all (the caller gets None), so
  single-file programs compile to the same C as before.

Everything this does not model is refused by name with a `write instead:` hint: packages and
dotted imports, relative imports, `from m import *`, `from m import _private`, imports below the
top level, a module used as a value, assignment to another module's attribute, names rebound
after their module ran (module globals come with G2), and import cycles that CPython only
survives through partly initialised modules.
"""
import ast
import builtins
import copy
from pathlib import Path

# modules the compiler models itself; a sibling `.ail` in the brace syntax never shadows them
MODELLED = frozenset(('math', 'sys', 'collections', 'itertools', 'functools', 'heapq', 'bisect', 're', 'json',
                      'random', 'dataclasses', 'typing', 'time', 'os', 'string', 'operator', '__future__'))
BUILTINS = frozenset(dir(builtins))
NEVER = 10 ** 9


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


class Mod:
    def __init__(self, name, path, tree, entry):
        self.name = name
        self.path = path
        self.tree = tree
        self.entry = entry
        self.kinds = {}        # own top-level name -> func | class | var | multi
        self.first = {}        # own top-level name -> index of the first statement binding it
        self.std = {}          # name bound by a non-local import -> signature
        self.alias = {}        # name bound by a local import -> ('mod', Mod) | ('member', Mod, original name)
        self.edges = []        # (statement index, node, [Mod, ...]) for each top-level local import
        self.merged = {}       # own top-level name -> merged name
        self.done = False


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


# ---------------------------------------------------------------- loading and analysis

class Program:
    def __init__(self, entry_path, read):
        self.entry_path = Path(entry_path).resolve()
        self.dir = self.entry_path.parent
        self.read = read
        self.mods = {}                  # module name -> Mod
        self.notes = []
        self.entry = None
        self.kept = {}

    def refuse(self, mod, node, text):
        raise ModuleRefusal(mod.path, getattr(node, 'lineno', 1), getattr(node, 'col_offset', 0) + 1, text)

    def local(self, name):
        return ((self.dir / (name + '.py')).is_file() or (self.dir / (name + '.ail')).is_file()
                or (self.dir / name / '__init__.py').is_file())

    def find(self, name, importer, node):
        """The Mod for sibling module `name`, or None when no sibling file provides it."""
        if name in self.mods:
            return self.mods[name]
        found = [self.dir / (name + s) for s in ('.py', '.ail') if (self.dir / (name + s)).is_file()]
        if (self.dir / name / '__init__.py').is_file():
            self.refuse(importer, node, "import of package %r is not supported yet: a directory with __init__.py "
                        "is a package, and packages come in a later stage.\n"
                        "  write instead: put the code in a flat module next to the entry file (%s.py) and "
                        "`import %s`" % (name, name, name))
        texts = {p: self.read(p) for p in found}
        kept = []
        for p in found:
            if p.suffix == '.ail' and _is_brace_or_sexpr(texts[p]):
                if name in MODELLED:
                    continue
                self.refuse(importer, node, "module %r is %s, which is written in the brace syntax; a Python "
                            "`import` takes Python-syntax modules (.py, or .ail written like Python).\n"
                            "  write instead: rename the module to %s.py written in Python syntax"
                            % (name, p.name, name))
            kept.append(p)
        if not kept:
            return None
        if len(kept) > 1:
            self.refuse(importer, node, "import of %r is ambiguous: %s both exist, and CPython would pick the "
                        ".py file and ignore the .ail one.\n  write instead: delete or rename one of them"
                        % (name, ' and '.join(p.name for p in kept)))
        path = kept[0]
        if path.resolve() == self.entry_path:
            self.refuse(importer, node, "import of %r would load the entry file a second time as a module "
                        "(CPython runs its body twice).\n  write instead: move the shared code into its own "
                        "module and import that" % name)
        if name in MODELLED:
            self.notes.append('note: %s shadows the standard library module %s, as it does in CPython'
                              % (path.name, name))
        try:
            tree = ast.parse(texts[path], filename=str(path))
        except SyntaxError as error:
            raise ModuleRefusal(path, error.lineno or 1, error.offset or 1, error.msg)
        mod = Mod(name, path, tree, False)
        self.mods[name] = mod
        self.analyse(mod)
        return mod

    def analyse(self, mod):
        body = mod.tree.body
        top = {id(n) for n in body}
        for node in ast.walk(mod.tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)) and id(node) not in top:
                names = [node.module or ''] if isinstance(node, ast.ImportFrom) else [a.name for a in node.names]
                if getattr(node, 'level', 0) or any(self.local(n.split('.')[0]) for n in names):
                    self.refuse(mod, node, "import of a sibling module below the top level (inside a function, "
                                "class or condition) is not supported: CPython runs it when that code runs, "
                                "and the program is built before it runs.\n"
                                "  write instead: move the import to the top of the file")
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
            if isinstance(node, ast.ImportFrom):
                self._from_import(mod, index, node)
            elif isinstance(node, ast.Import):
                self._import(mod, index, node)
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

    def _import(self, mod, index, node):
        targets = []
        for a in node.names:
            first = a.name.split('.')[0]
            if '.' in a.name and self.local(first):
                self.refuse(mod, node, "import of %r: dotted names are packages, which are not supported yet.\n"
                            "  write instead: flat modules in the entry file's directory (`import %s`)"
                            % (a.name, first))
            target = self.find(a.name, mod, node) if '.' not in a.name else None
            if target is None:
                self._std(mod, a.asname or first, ('import', a.name), node)
            else:
                mod.alias[a.asname or a.name] = ('mod', target)
                targets.append(target)
        if targets:
            if len(targets) != len(node.names):
                self.refuse(mod, node, "one `import` statement mixes sibling modules and others; the compiler "
                            "needs them apart.\n  write instead: one `import` line for the sibling modules")
            mod.edges.append((index, node, targets))

    def _from_import(self, mod, index, node):
        if node.level:
            self.refuse(mod, node, "relative import (`from %s%s import ...`) is not supported yet: relative "
                        "imports belong to packages, which come in a later stage.\n"
                        "  write instead: `from %s import ...` with a flat module in the entry file's directory"
                        % ('.' * node.level, node.module or '', node.module or 'module'))
        first = node.module.split('.')[0]
        if '.' in node.module and self.local(first):
            self.refuse(mod, node, "import from %r: dotted names are packages, which are not supported yet.\n"
                        "  write instead: flat modules in the entry file's directory (`from %s import ...`)"
                        % (node.module, first))
        target = self.find(node.module, mod, node) if '.' not in node.module else None
        if target is None:
            for a in node.names:
                if a.name != '*':
                    self._std(mod, a.asname or a.name, ('from', node.module, a.name), node)
            return
        for a in node.names:
            if a.name == '*':
                self.refuse(mod, node, "`from %s import *` is not supported: it binds names the compiler cannot "
                            "see in the source.\n  write instead: `from %s import name1, name2` naming what you "
                            "use" % (node.module, node.module))
            if a.name.startswith('_') and not (a.name.startswith('__') and a.name.endswith('__')):
                self.refuse(mod, node, "`from %s import %s` imports a private name (a leading underscore); "
                            "this compiler refuses it even though CPython allows it.\n"
                            "  write instead: rename it without the underscore in %s"
                            % (node.module, a.name, target.path.name))
            mod.alias[a.asname or a.name] = ('member', target, a.name)
        mod.edges.append((index, node, [target]))

    def _std(self, mod, name, signature, node):
        if mod.std.get(name, signature) != signature:
            self.refuse(mod, node, "%r is bound to two different imports in %s.\n"
                        "  write instead: give one of them another name with `as`" % (name, mod.path.name))
        mod.std[name] = signature

    def export(self, target, attr, importer, node):
        """Merged name of `attr` in module `target` (following re-exports)."""
        if attr in target.alias:
            kind = target.alias[attr]
            if kind[0] == 'member':
                return self.export(kind[1], kind[2], importer, node)
            self.refuse(importer, node, "%s.%s is a module, used as a value; this compiler needs a module to be "
                        "named in the source.\n  write instead: `import %s` in the importing file"
                        % (target.name, attr, kind[1].name))
        if attr in target.std:
            self.refuse(importer, node, "%s.%s is a standard-library name that %s imported; reading it through %s "
                        "is not supported.\n  write instead: import it in the importing file"
                        % (target.name, attr, target.name, target.name))
        kind = target.kinds.get(attr)
        if kind is None:
            names = sorted(n for n, k in target.kinds.items() if not n.startswith('_'))
            self.refuse(importer, node, "module %r has no top-level name %r (it defines: %s).\n"
                        "  write instead: use one of those names, or define %r in %s"
                        % (target.name, attr, ', '.join(names) or 'nothing', attr, target.path.name))
        if kind == 'multi':
            self.refuse(importer, node, "%s.%s is rebound after it is first defined (assigned more than once, in a "
                        "loop or condition, or through `global`); module globals that change come in a later "
                        "stage.\n  write instead: keep %s a constant, assigned once at the top level of %s"
                        % (target.name, attr, attr, target.path.name))
        return target.merged[attr]


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


def _assign_names(program, mods):
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
    for mod in mods:
        if mod.entry:
            continue
        for name, kind in mod.kinds.items():
            if kind == 'class':
                continue
            new = '%s__%s' % (mod.name, name)
            while new in ids or new in used or new in kept:
                new += '_'
            used.add(new)
            mod.merged[name] = new


# ---------------------------------------------------------------- rewriting

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


class Rewriter(ast.NodeTransformer):
    def __init__(self, program, mod, partial, positions):
        self.program = program
        self.mod = mod
        self.scopes = []              # [kind, names, globals]
        self.partial = partial        # modules still running their body (import cycle)
        self.positions = positions    # module -> index of the statement it is executing
        self.running = 0              # 0 while code runs at definition time; > 0 inside function bodies
        self.free = []

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
        if target not in self.partial or self.running:
            return
        if target.first.get(attr, NEVER) >= self.positions[target]:
            self.program.refuse(self.mod, node, "import cycle: %s reads %s.%s while %s is still running its own "
                                "body, before %s is defined (%s -> %s -> %s); CPython would expose a partly "
                                "initialised module here.\n"
                                "  write instead: move %s into a module that both import, or read it inside a "
                                "function" % (self.mod.path.name, target.name, attr, target.name, attr,
                                              target.name, self.mod.name, target.name, attr))

    def module_ref(self, node):
        if isinstance(node, ast.Name):
            entry = self.mod.alias.get(node.id)
            if entry and entry[0] == 'mod' and self.module_level(node.id):
                return entry[1]
        elif isinstance(node, ast.Attribute):
            base = self.module_ref(node.value)
            if base is not None and base.alias.get(node.attr, ('',))[0] == 'mod':
                return base.alias[node.attr][1]
        return None

    def visit_Name(self, node):
        name = node.id
        if not self.module_level(name):
            return node
        if name == '__name__' and isinstance(node.ctx, ast.Load):
            return ast.copy_location(ast.Constant('__main__' if self.mod.entry else self.mod.name), node)
        if name in self.mod.std:
            return node
        if name in self.mod.alias:
            entry = self.mod.alias[name]
            if entry[0] == 'mod':
                self.program.refuse(self.mod, node, "module %r used as a value (passed, stored or compared); this "
                                    "compiler needs a module to be named at each use.\n  write instead: use "
                                    "`%s.name` directly" % (entry[1].name, name))
            if not isinstance(node.ctx, ast.Load):
                self.program.refuse(self.mod, node, "%r is imported from %s and cannot be rebound here.\n"
                                    "  write instead: use another name for your own variable"
                                    % (name, entry[1].name))
            self.check_partial(entry[1], entry[2], node)
            return ast.copy_location(ast.Name(self.program.export(entry[1], entry[2], self.mod, node), node.ctx), node)
        if name in self.mod.merged:
            if self.mod.merged[name] != name:
                return ast.copy_location(ast.Name(self.mod.merged[name], node.ctx), node)
            return node
        if isinstance(node.ctx, ast.Load):
            self.free.append((name, node))
        return node

    def visit_Attribute(self, node):
        target = self.module_ref(node.value)
        if target is None:
            self.generic_visit(node)
            return node
        attr = node.attr
        if not isinstance(node.ctx, ast.Load):
            self.program.refuse(self.mod, node, "assignment to another module's attribute (`%s.%s = ...`) is not "
                                "supported; every module's names are fixed after its body has run.\n"
                                "  write instead: call a function in %s that does the update"
                                % (target.name, attr, target.path.name))
        if attr == '__name__':
            return ast.copy_location(ast.Constant(target.name), node)
        if attr.startswith('_'):
            self.program.refuse(self.mod, node, "`%s.%s` reads a private name (a leading underscore); this compiler "
                                "refuses it even though CPython allows it.\n  write instead: rename it without "
                                "the underscore in %s" % (target.name, attr, target.path.name))
        self.check_partial(target, attr, node)
        return ast.copy_location(ast.Name(self.program.export(target, attr, self.mod, node), ast.Load()), node)

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
        node.names = [self.mod.merged.get(n, n) for n in node.names]
        return node

    def visit_ExceptHandler(self, node):
        if node.name:
            node.name = self.rename_binding(node.name)
        self.generic_visit(node)
        return node

    def visit_MatchAs(self, node):
        if node.name:
            node.name = self.rename_binding(node.name)
        self.generic_visit(node)
        return node

    visit_MatchStar = visit_MatchAs

    def visit_MatchMapping(self, node):
        if node.rest:
            node.rest = self.rename_binding(node.rest)
        self.generic_visit(node)
        return node

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
        if not isinstance(node, ast.Lambda):
            node.name = self.rename_binding(node.name)
        names, global_names = _function_locals(node)
        self.scopes.append(['func', names, global_names])
        self.running += 1
        if isinstance(node, ast.Lambda):
            node.body = self.visit(node.body)
        else:
            node.body = [self.visit(s) for s in node.body]
        self.running -= 1
        self.scopes.pop()
        return node

    visit_FunctionDef = visit_AsyncFunctionDef = visit_Lambda = visit_function

    def visit_ClassDef(self, node):
        node.decorator_list = [self.visit(d) for d in node.decorator_list]
        node.bases = [self.visit(b) for b in node.bases]
        node.keywords = [self.visit(k) for k in node.keywords]
        node.name = self.rename_binding(node.name)
        stores, globals_, _, _ = _scan_scope(node.body)
        self.scopes.append(['class', stores - globals_, globals_])
        node.body = [self.visit(s) for s in node.body]
        self.scopes.pop()
        return node

    def visit_comprehension_scope(self, node):
        generators = node.generators
        generators[0].iter = self.visit(generators[0].iter)
        names = {c.id for g in generators for c in ast.walk(g.target) if isinstance(c, ast.Name)}
        self.scopes.append(['func', names, set()])
        for index, g in enumerate(generators):
            g.target = self.visit(g.target)
            if index:
                g.iter = self.visit(g.iter)
            g.ifs = [self.visit(i) for i in g.ifs]
        if isinstance(node, ast.DictComp):
            node.key, node.value = self.visit(node.key), self.visit(node.value)
        else:
            node.elt = self.visit(node.elt)
        self.scopes.pop()
        return node

    visit_ListComp = visit_SetComp = visit_DictComp = visit_GeneratorExp = visit_comprehension_scope


# ---------------------------------------------------------------- the merge

def merge_program(entry_path, entry_text, read=None):
    """None when the entry imports no sibling module; else a Merged program (see the module docstring)."""
    if read is None:
        def read(path):
            return Path(path).read_bytes().decode('utf-8').replace('\r\n', '\n').replace('\r', '\n')
    program = Program(entry_path, read)
    try:
        tree = ast.parse(entry_text, filename=str(program.entry_path))
    except SyntaxError:
        return None                    # the caller's own parse reports it
    for node in ast.walk(tree):
        if (isinstance(node, ast.ImportFrom) and node.level) or (
                isinstance(node, ast.ImportFrom) and node.module and program.local(node.module.split('.')[0])) or (
                isinstance(node, ast.Import) and any(program.local(a.name.split('.')[0]) for a in node.names)):
            break
    else:
        return None
    entry = Mod('__main__', program.entry_path, tree, True)
    program.entry = entry
    program.mods['__main__'] = entry
    program.analyse(entry)
    reachable = []

    def collect(mod):
        for _, _, targets in mod.edges:
            for target in targets:
                if target not in reachable:
                    reachable.append(target)
                    collect(target)
    collect(entry)
    if not reachable:
        return None
    _assign_names(program, [entry] + reachable)

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

    def expand(mod):
        stack.append(mod)
        edges = {id(e[1]): e for e in mod.edges}
        for index, node in enumerate(mod.tree.body):
            positions[mod] = index
            edge = edges.get(id(node))
            if edge is not None:
                for target in edge[2]:
                    if target in stack:
                        if isinstance(node, ast.ImportFrom):
                            for a in node.names:
                                if target.first.get(a.name, NEVER) >= positions[target]:
                                    cycle = ' -> '.join(m.name for m in stack[stack.index(target):] + [target])
                                    program.refuse(mod, node, "import cycle %s: `from %s import %s` runs before %s "
                                                   "has defined %s, so CPython raises ImportError.\n"
                                                   "  write instead: move %s into a module that both import"
                                                   % (cycle, target.name, a.name, target.name, a.name, a.name))
                    elif not target.done:
                        expand(target)
                continue
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                emit_import(mod, node)
            elif mod.entry:
                rewrite(mod, node)
            elif index == 0 and isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) \
                    and isinstance(node.value.value, str):
                continue                                          # module docstring
            elif isinstance(node, ast.If) and _static_main_test(node.test):
                for sub in (node.orelse if _static_main_test(node.test) == 'main' else node.body):
                    rewrite(mod, sub)                             # `if __name__ == "__main__"` is false here
            elif (isinstance(node, ast.Assign) and len(node.targets) == 1
                  and isinstance(node.targets[0], ast.Name) and node.targets[0].id == '__all__'):
                continue
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
    names = {new: '%s.%s' % (mod.name, old) for mod in reachable for old, new in mod.merged.items() if new != old}
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
