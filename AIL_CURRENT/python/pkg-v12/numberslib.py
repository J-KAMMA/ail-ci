"""`numbers` (library batch 5, called from stdlib5).

CPython's `numbers` module publishes five ABCs: Number, Complex, Real, Rational and Integral.
The hierarchy is injected from prelude_numbers.py as plain classes (this runtime has no ABCMeta).
The uses ordinary code makes are lowered here:

    isinstance(x, numbers.Integral)          ->  _ail_num_isinstance(x, 5)
    isinstance(x, (numbers.Real, numbers.Integral))
                                             ->  _ail_num_in(x, [3, 5])
    issubclass(type(x), numbers.Number)      ->  _ail_num_isinstance(x, 1)
    issubclass(int, numbers.Integral)        ->  True      (known statically)
    issubclass(MyClass, numbers.Real)        ->  _ail_num_issubclass(MyClass, 3)   (at run time)
    numbers.Real.register(MyClass)           ->  _ail_num_register(MyClass, 3, [...])  (the expression is MyClass)
    @numbers.Real.register                   (a decorator: the class is registered when it is defined)

The classification of the builtin types matches CPython: bool and int are Integral, float is Real,
complex is Complex; a Fraction is Rational and a Decimal is Number.  A user class that inherits one
of the ABCs is classified by that inheritance.  `register` is virtual: it records the class in a
run-time table (so its position in the control flow is respected) and does not add a base, so a
registered class does not gain the ABC's `real` / `imag` / `conjugate` methods.

Not built, refused by name: `numbers` used as a value, other attributes of the ABCs, a class
value that is not a name defined in this program (issubclass of a run-time class object), a
register decorator combined with another decorator, and registration of a name that is not a
class defined here.  CPython's ABCMeta also refuses to instantiate a subclass that leaves
abstract methods unimplemented; that check is not made here.
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
REGISTER_HELPER = '_ail_num_register'
ISSUBCLASS_HELPER = '_ail_num_issubclass'
ISSUBCLASS_IN_HELPER = '_ail_num_issubclass_in'


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


def class_kinds(tree, binder, actual_kind):
    """For every class defined at the top level, the set of numbers kinds it is a subclass of through
    its bases (registration is virtual and is looked up at run time, not here)."""
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
        memo[name] = out
        return out

    return lambda name: of(name, set())


def run(tree, text):
    binder = stdlib5.take_imports(tree, 'numbers', set(NAMES), unknown=WHAT)
    if not binder:
        return
    for each in ast.walk(tree):
        bound = None
        if isinstance(each, ast.arg) and each.arg in NAMES:
            bound = each.arg
        elif isinstance(each, (ast.FunctionDef, ast.ClassDef)) and each.name in NAMES:
            bound = each.name
        elif isinstance(each, ast.Name) and each.id in NAMES and not isinstance(each.ctx, ast.Load):
            bound = each.id
        if bound is not None:
            refuse(binder.first, 'the program binds the name %s itself and also imports numbers; rename one' % bound)

    defs = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
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

    def ancestor_names(name, seen=None):
        """The user classes `name` inherits from, directly or through another user class."""
        seen = set() if seen is None else seen
        if name in seen or name not in defs:
            return set()
        seen = seen | {name}
        out = set()
        for base in defs[name].bases:
            if isinstance(base, ast.Name) and base.id in defs:
                out.add(base.id)
                out |= ancestor_names(base.id, seen)
        return out

    def descendants(name):
        """`name` and every user class that inherits from it (registration is virtual, so an instance of a
        subclass is registered too).  Names are used, so a class defined later in the file is covered."""
        out = [name]
        for other in defs:
            if other != name and name in ancestor_names(other):
                out.append(other)
        return out

    def register_expression(target, kind):
        return ast.Call(func=ast.Name(id=REGISTER_HELPER, ctx=ast.Load()),
                        args=[ast.Name(id=target, ctx=ast.Load()), ast.Constant(kind),
                              ast.List(elts=[ast.Constant(n) for n in descendants(target)], ctx=ast.Load())],
                        keywords=[])

    # A register decorator runs when the class is defined: keep the class statement and put the run-time
    # registration immediately after it, so its position in the control flow is respected.  Combining it
    # with another decorator is refused rather than guessed at (the decorator order could change which
    # class object is registered).
    used = set()
    body = []
    for stmt in tree.body:
        if isinstance(stmt, ast.ClassDef):
            kinds = []
            keep = []
            for dec in stmt.decorator_list:
                kind = kind_of(dec.value, binder) if isinstance(dec, ast.Attribute) and dec.attr == 'register' else None
                if kind is not None:
                    kinds.append(kind)
                else:
                    keep.append(dec)
            if kinds:
                if len(kinds) != 1 or keep:
                    refuse(stmt, 'a numbers register decorator combined with other decorators is not built; '
                           'call numbers.X.register(Cls) after the class definition instead')
                stmt.decorator_list = []
                body.append(stmt)
                body.append(ast.Expr(value=register_expression(stmt.name, kinds[0])))
                used.add('register')
                continue
        body.append(stmt)
    tree.body = body

    kinds_of = class_kinds(tree, binder, actual_kind)
    kinds_map = {name: kinds_of(name) for name in defs}

    def static_issubclass(first, target_kinds):
        """True/False when the first argument names a class known at compile time, else None (a user class
        is checked at run time, so registration before or after the call is respected)."""
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
            else:
                return None
        else:
            return None
        return bool(have & set(target_kinds))

    def issubclass_expression(first, target_kinds):
        if len(target_kinds) == 1:
            return ast.Call(func=ast.Name(id=ISSUBCLASS_HELPER, ctx=ast.Load()),
                            args=[first, ast.Constant(target_kinds[0])], keywords=[])
        return ast.Call(func=ast.Name(id=ISSUBCLASS_IN_HELPER, ctx=ast.Load()),
                        args=[first, ast.List(elts=[ast.Constant(k) for k in target_kinds], ctx=ast.Load())],
                        keywords=[])

    class Fix(ast.NodeTransformer):
        def visit_Call(self, node):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == 'register' and kind_of(func.value, binder) is not None:
                target = register_target(node.args[0]) if len(node.args) == 1 and not node.keywords else None
                if target is None:
                    refuse(node, 'register() of a name that is not a class defined in this program is not built; '
                           'define the class here or inherit the ABC directly')
                if node.lineno < defs[target].lineno:
                    refuse(node, 'register() written before the class %s is defined is not built; move the '
                           'registration after the class definition, where CPython binds the name' % target)
                used.add('register')
                return ast.copy_location(register_expression(target, kind_of(func.value, binder)), node)
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
                    first = node.args[0]
                    if isinstance(first, ast.Call) and isinstance(first.func, ast.Name) \
                            and first.func.id == 'type' and len(first.args) == 1 and not first.keywords:
                        used.add('isinstance')
                        value = self.visit(first.args[0])
                        return ast.copy_location(kinds_expression(targets, value, node.lineno), node)
                    if isinstance(first, ast.Name) and first.id in defs:
                        used.add('issubclass')
                        return ast.copy_location(issubclass_expression(first, targets), node)
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
    class_kinds_literal = '{' + ', '.join(
        '%r: %r' % (name, tuple(sorted(kinds_map[name]))) for name in defs if kinds_map[name]) + '}'
    registry_helper = (
        '_ail_num_virtual = []\n'
        '_ail_num_class_kinds = ' + class_kinds_literal + '\n\n'
        'def %s(cls, k: int, names: list[str]):\n'
        '    _ail_num_virtual.append((k, names))\n'
        '    return cls\n\n'
        'def %s(cls, k: int) -> bool:\n'
        '    name = cls.__name__\n'
        '    if k in _ail_num_class_kinds.get(name, ()):\n'
        '        return True\n'
        '    for e in _ail_num_virtual:\n'
        '        if k <= e[0] and name in e[1]:\n'
        '            return True\n'
        '    return False\n\n'
        'def %s(cls, ks: list[int]) -> bool:\n'
        '    for k in ks:\n'
        '        if %s(cls, k):\n'
        '            return True\n'
        '    return False\n\n'
    ) % (REGISTER_HELPER, ISSUBCLASS_HELPER, ISSUBCLASS_IN_HELPER, ISSUBCLASS_HELPER)
    kinds_helper = (
        'def {h}(v, k: int) -> bool:\n'
        '    t = type(v).__name__\n'
        '    if k == 5:\n'
        '        if isinstance(v, int) or isinstance(v, Integral):\n'
        '            return True\n'
        '    elif k == 4:\n'
        '        if {h}(v, 5){frac} or isinstance(v, Rational):\n'
        '            return True\n'
        '    elif k == 3:\n'
        '        if {h}(v, 4) or isinstance(v, float) or isinstance(v, Real):\n'
        '            return True\n'
        '    elif k == 2:\n'
        '        if {h}(v, 3) or t == "complex" or isinstance(v, Complex):\n'
        '            return True\n'
        '    elif {h}(v, 2){dec} or isinstance(v, Number):\n'
        '        return True\n'
        '    for e in _ail_num_virtual:\n'
        '        if k <= e[0] and t in e[1]:\n'
        '            return True\n'
        '    return False\n\n'
        'def {i}(v, ks: list[int]) -> bool:\n'
        '    for k in ks:\n'
        '        if {h}(v, k):\n'
        '            return True\n'
        '    return False\n'
    ).format(h=HELPER, i=IN_HELPER, frac=fractions_check, dec=decimal_check)
    if not used:
        # no classification or registration call was lowered: the helpers would be dead code
        registry_helper = kinds_helper = ''
    stdlib5.add_once(text, stdlib5.prelude('numbers') + '\n' + registry_helper + kinds_helper)
