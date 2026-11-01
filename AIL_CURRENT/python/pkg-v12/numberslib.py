"""`numbers` (library batch 5, called from stdlib5).

CPython's `numbers` module publishes five ABCs: Number, Complex, Real, Rational and Integral.
The hierarchy is injected from prelude_numbers.py as plain classes (this runtime has no ABCMeta).
The uses ordinary code makes are lowered here:

    isinstance(x, numbers.Integral)          ->  _ail_num_isinstance(x, 5)
    isinstance(x, (numbers.Real, numbers.Integral))
                                             ->  _ail_num_in(x, [3, 5])
    issubclass(type(x), numbers.Number)      ->  _ail_num_isinstance(x, 1)
    issubclass(int, numbers.Integral)        ->  True      (known statically)
    numbers.Real.register(MyClass)           ->  MyClass gains Real as a base  (the expression is MyClass)
    @numbers.Real.register                   (a decorator: the class gains Real as a base)

The classification of the builtin types matches CPython: bool and int are Integral, float is Real,
complex is Complex; a Fraction is Rational and a Decimal is Number.  A user class that inherits one
of the ABCs is classified by that inheritance, and one registered with `register` gains the base.

Not built, refused by name: `numbers` used as a value, other attributes of the ABCs, a class
value that is not a name defined in this program (issubclass of a run-time class object) and
registration of a name that is not a class defined here.  CPython's ABCMeta also refuses to
instantiate a subclass that leaves abstract methods unimplemented; that check is not made here.
"""
import ast

import stdlib5
from stdlib4 import refuse

NAMES = ('Number', 'Complex', 'Real', 'Rational', 'Integral')
KIND = {'Number': 1, 'Complex': 2, 'Real': 3, 'Rational': 4, 'Integral': 5}
KIND_NAME = {v: k for k, v in KIND.items()}
ANCESTORS = {1: {1}, 2: {2, 1}, 3: {3, 2, 1}, 4: {4, 3, 2, 1}, 5: {5, 4, 3, 2, 1}}
BUILTIN = {'int': 5, 'bool': 5, 'float': 3, 'complex': 2}
NONNUM = {'str', 'list', 'dict', 'tuple', 'set', 'frozenset', 'bytes', 'bytearray', 'object', 'type', 'range'}
WHAT = 'Number, Complex, Real, Rational and Integral are the names of the module that are built'
HELPER = '_ail_num_isinstance'
IN_HELPER = '_ail_num_in'


def kind_of(node, binder):
    found = binder.attr(node)
    return KIND.get(found) if found is not None else None


def kinds_expression(kinds, value, line):
    """The call that classifies `value` against one or more numbers kinds (the value is evaluated once)."""
    if len(kinds) == 1:
        return ast.Call(func=ast.Name(id=HELPER, ctx=ast.Load()), args=[value, ast.Constant(kinds[0])],
                        keywords=[])
    return ast.Call(func=ast.Name(id=IN_HELPER, ctx=ast.Load()), args=[value, ast.List(
        elts=[ast.Constant(k) for k in kinds], ctx=ast.Load())], keywords=[])


def simple(node):
    """A value that can be evaluated twice without changing the program (a name, a constant, an attribute
    chain of names): a mixed isinstance() tuple is duplicated only for these."""
    while isinstance(node, ast.Attribute):
        node = node.value
    return isinstance(node, (ast.Name, ast.Constant))


def class_kinds(tree, binder, extra, actual_kind):
    """For every class defined at the top level, the set of numbers kinds it is a subclass of.  `extra`
    maps a class name to kinds added by register()."""
    defs = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
    memo = {}

    def of(name, seen):
        if name in memo:
            return memo[name]
        if name in seen or name not in defs:
            return set()
        seen = seen | {name}
        out = set()
        for base in defs[name].bases:
            k = actual_kind(base)
            if k is not None:
                out |= ANCESTORS[k]
                continue
            if isinstance(base, ast.Name) and base.id in defs:
                out |= of(base.id, seen)
        out |= extra.get(name, set())
        memo[name] = out
        return out

    return lambda name: of(name, set())


def run(tree, text):
    binder = stdlib5.take_imports(tree, 'numbers', set(NAMES), unknown=WHAT)
    if not binder:
        return
    for each in ast.walk(tree):
        if isinstance(each, (ast.FunctionDef, ast.ClassDef)) and each.name in NAMES or (
                isinstance(each, ast.Name) and each.id in NAMES and not isinstance(each.ctx, ast.Load)):
            refuse(binder.first, 'the program binds the name %s itself and also imports numbers; rename one' % each.id
                   if isinstance(each, ast.Name) else
                   'the program defines %s itself and also imports numbers; rename one' % each.name)

    defs = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
    extra = {}
    mods = stdlib5.imported_modules(tree)
    frac_binder = stdlib5.peek_imports(tree, 'fractions') if 'fractions' in mods else None
    decimal_binder = stdlib5.peek_imports(tree, 'decimal') if 'decimal' in mods else None

    def actual_kind(node):
        """The numbers kind a class expression names: an ABC, or the real Fraction / Decimal class."""
        found = kind_of(node, binder)
        if found is not None:
            return found
        if frac_binder is not None and frac_binder.attr(node) == 'Fraction':
            return 4
        if decimal_binder is not None and decimal_binder.attr(node) == 'Decimal':
            return 1
        return None

    def register_target(node):
        if isinstance(node, ast.Name) and node.id in defs:
            return node.id
        return None

    def add_base(name, kind):
        cls = defs[name]
        existing = []
        for old in cls.bases:
            found = binder.attr(old)
            if found in KIND:
                existing.append(KIND[found])
            elif isinstance(old, ast.Name) and old.id in KIND:
                existing.append(KIND[old.id])
        if existing:
            if any(kind in ANCESTORS[k] for k in existing) or kind in existing:
                extra.setdefault(name, set()).update(ANCESTORS[kind])
                return
            if all(k in ANCESTORS[kind] for k in existing):
                cls.bases = [b for b in cls.bases
                             if binder.attr(b) not in KIND and not (isinstance(b, ast.Name) and b.id in KIND)]
                cls.bases.append(ast.Name(id=KIND_NAME[kind], ctx=ast.Load()))
                extra.setdefault(name, set()).update(ANCESTORS[kind])
                return
        if cls.bases:
            refuse(cls, 'register() of class %s is not built: it already has a base class and adding the '
                   'numbers class would need multiple inheritance; inherit the numbers class directly'
                   % name)
        cls.bases.append(ast.Name(id=KIND_NAME[kind], ctx=ast.Load()))
        extra.setdefault(name, set()).update(ANCESTORS[kind])

    def register_call(node):
        """The target class name of a `numbers.X.register(Cls)` call, or None."""
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != 'register' or node.keywords or len(node.args) != 1:
            return None
        if kind_of(func.value, binder) is None:
            return None
        return register_target(node.args[0])

    # registration, before the classification tables are built
    for stmt in tree.body:
        if isinstance(stmt, ast.ClassDef):
            keep = []
            for dec in stmt.decorator_list:
                if isinstance(dec, ast.Attribute) and dec.attr == 'register' and kind_of(dec.value, binder) is not None:
                    add_base(stmt.name, kind_of(dec.value, binder))
                else:
                    keep.append(dec)
            stmt.decorator_list = keep
    for each in ast.walk(tree):
        if isinstance(each, ast.Call):
            target = register_call(each)
            if target is not None:
                add_base(target, kind_of(each.func.value, binder))

    kinds_of = class_kinds(tree, binder, extra, actual_kind)
    used = set()

    def static_issubclass(first, target_kinds):
        """True/False when the first argument names a class known at compile time, else None."""
        k = actual_kind(first)
        if k is not None:
            have = ANCESTORS[k]
        elif isinstance(first, ast.Name):
            name = first.id
            if name in BUILTIN:
                have = ANCESTORS[BUILTIN[name]]
            elif name in NONNUM:
                have = set()
            elif name in KIND:
                have = ANCESTORS[KIND[name]]
            elif name in defs:
                have = kinds_of(name)
            else:
                return None
        else:
            return None
        return bool(have & set(target_kinds))

    class Fix(ast.NodeTransformer):
        def visit_Call(self, node):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == 'register' and kind_of(func.value, binder) is not None:
                target = register_target(node.args[0]) if len(node.args) == 1 and not node.keywords else None
                if target is None:
                    refuse(node, 'register() of a name that is not a class defined in this program is not built; '
                           'define the class here or inherit the ABC directly')
                return ast.copy_location(ast.Name(id=target, ctx=ast.Load()), node)
            # isinstance(value, numbers-kind or a tuple of them)
            if isinstance(node.func, ast.Name) and node.func.id == 'isinstance' and len(node.args) == 2 \
                    and not node.keywords:
                kinds = []
                rest = []

                def split(spec):
                    if isinstance(spec, ast.Tuple):
                        for elt in spec.elts:
                            split(elt)
                        return
                    k = kind_of(spec, binder)
                    if k is None:
                        rest.append(self.visit(spec))
                    else:
                        kinds.append(k)

                split(node.args[1])
                if not kinds:
                    return self.generic_visit(node)
                value = self.visit(node.args[0])
                used.add('isinstance')
                if not rest:
                    return ast.copy_location(kinds_expression(kinds, value, node.lineno), node)
                if simple(node.args[0]):
                    other = rest[0] if len(rest) == 1 else ast.Tuple(elts=rest, ctx=ast.Load())
                    parts = [kinds_expression(kinds, value, node.lineno),
                             ast.Call(func=ast.Name(id='isinstance', ctx=ast.Load()), args=[value, other],
                                      keywords=[])]
                    return ast.copy_location(ast.BoolOp(op=ast.Or(), values=parts), node)
                refuse(node, 'isinstance() with a numbers class mixed with other types needs a plain name as '
                       'its value here; test the numbers classes in a separate isinstance() call')
            # issubclass(first, numbers-kind or a tuple of only them)
            if isinstance(node.func, ast.Name) and node.func.id == 'issubclass' and len(node.args) == 2 \
                    and not node.keywords:
                targets = []
                if isinstance(node.args[1], ast.Tuple):
                    for elt in node.args[1].elts:
                        k = kind_of(elt, binder)
                        if k is None:
                            refuse(elt, 'issubclass() with a numbers class mixed with other types is not built; '
                                   'test the numbers classes in a separate call')
                        targets.append(k)
                else:
                    k = kind_of(node.args[1], binder)
                    if k is not None:
                        targets.append(k)
                if targets:
                    used.add('isinstance')
                    first = node.args[0]
                    if isinstance(first, ast.Call) and isinstance(first.func, ast.Name) \
                            and first.func.id == 'type' and len(first.args) == 1 and not first.keywords:
                        value = self.visit(first.args[0])
                        return ast.copy_location(kinds_expression(targets, value, node.lineno), node)
                    result = static_issubclass(first, targets)
                    if result is None:
                        refuse(node, 'issubclass() of a class value that is not a name defined in this program is '
                               'not built; write issubclass(type(x), numbers.X) or a class defined here')
                    return ast.copy_location(ast.Constant(value=result), node)
            return self.generic_visit(node)

    tree.body = [Fix().visit(stmt) for stmt in tree.body]

    # The injected classes are only the values of class bases and annotations.  Any other use of a
    # numbers name is refused: the injected classes are plain classes, so their repr and module would not
    # be CPython's.
    def class_name(node):
        found = binder.attr(node)
        if found in KIND:
            return ast.Name(id=found, ctx=ast.Load())
        return None

    def check_values(node):
        if isinstance(node, ast.ClassDef):
            for dec in node.decorator_list:
                check_values(dec)
            for kw in node.keywords:
                check_values(kw)
            for stmt in node.body:
                check_values(stmt)
            return
        if isinstance(node, ast.arg):
            return
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                check_values(dec)
            check_values(node.args)
            for stmt in node.body:
                check_values(stmt)
            return
        if isinstance(node, ast.AnnAssign):
            check_values(node.target)
            if node.value is not None:
                check_values(node.value)
            return
        found = binder.attr(node)
        if found is not None:
            refuse(node, 'numbers.%s used as a plain value is not built: use it in isinstance(), issubclass(), '
                   'register(), a class base or an annotation' % found)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in binder.aliases:
            refuse(node, 'numbers used as a value is not built')
        for child in ast.iter_child_nodes(node):
            check_values(child)

    class Allowed(ast.NodeTransformer):
        def fix(self, node):
            return stdlib5.Replace(lambda n: class_name(n)).visit(node)

        def visit_ClassDef(self, node):
            node.bases = [self.fix(base) for base in node.bases]
            self.generic_visit(node)
            return node

        def visit_arg(self, node):
            if node.annotation is not None:
                node.annotation = self.fix(node.annotation)
            return node

        def visit_FunctionDef(self, node):
            if node.returns is not None:
                node.returns = self.fix(node.returns)
            self.generic_visit(node)
            return node

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_AnnAssign(self, node):
            node.annotation = self.fix(node.annotation)
            self.generic_visit(node)
            return node

    for stmt in tree.body:
        check_values(stmt)
    tree.body = [Allowed().visit(stmt) for stmt in tree.body]

    fractions_check = ' or isinstance(v, Fraction)' if frac_binder is not None else ''
    decimal_check = ' or isinstance(v, Decimal)' if decimal_binder is not None else ''
    kinds_helper = (
        'def {h}(v, k: int) -> bool:\n'
        '    t = type(v).__name__\n'
        '    if k == 5:\n'
        '        return isinstance(v, int) or isinstance(v, Integral)\n'
        '    if k == 4:\n'
        '        return {h}(v, 5){frac} or isinstance(v, Rational)\n'
        '    if k == 3:\n'
        '        return {h}(v, 4) or isinstance(v, float) or isinstance(v, Real)\n'
        '    if k == 2:\n'
        '        return {h}(v, 3) or t == "complex" or isinstance(v, Complex)\n'
        '    return {h}(v, 2){dec} or isinstance(v, Number)\n\n'
        'def {i}(v, ks: list[int]) -> bool:\n'
        '    for k in ks:\n'
        '        if {h}(v, k):\n'
        '            return True\n'
        '    return False\n'
    ).format(h=HELPER, i=IN_HELPER, frac=fractions_check, dec=decimal_check)
    if 'isinstance' not in used:
        # no classification call was lowered: the helper functions would be dead code
        kinds_helper = ''
    stdlib5.add_once(text, stdlib5.prelude('numbers') + '\n' + kinds_helper)
