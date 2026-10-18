"""Small library forms that need no import (library batch 4): `int.bit_length()` and `int.bit_count()`.

Each call `x.bit_length()` becomes `_ail_bit_length(x)`, a helper function in the Python subset appended to
the program (only the ones used), so the C of a program that does not use them is unchanged. The helpers
take an `int` (64-bit, like every int here): a float or str receiver is the compiler's own type refusal
for the helper's parameter, which is also CPython's AttributeError turned into a refusal. A program that
defines its own `bit_length` / `bit_count` (a method, a field, a function) is left alone.
"""
import ast
import copy

NAMES = ('bit_length', 'bit_count')

BIT_LENGTH = '''
def _ail_bit_length(x: int) -> int:
    n = 0
    y = x
    if y < 0:
        if y == -9223372036854775807 - 1:
            return 64
        y = -y
    while y >= 4294967296:
        y = y >> 32
        n += 32
    while y > 0:
        y = y >> 1
        n += 1
    return n
'''

BIT_COUNT = '''
def _ail_bit_count(x: int) -> int:
    n = 0
    y = x
    if y < 0:
        if y == -9223372036854775807 - 1:
            return 1
        y = -y
    while y > 0:
        y = y & (y - 1)
        n += 1
    return n
'''

SOURCES = {'bit_length': BIT_LENGTH, 'bit_count': BIT_COUNT}


def defined_here(tree, name):
    for each in ast.walk(tree):
        if isinstance(each, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and each.name == name:
            return True
        if isinstance(each, ast.Attribute) and each.attr == name and not isinstance(each.ctx, ast.Load):
            return True
        if isinstance(each, ast.Name) and each.id == name and not isinstance(each.ctx, ast.Load):
            return True
    return False


def str_literals(node):
    """The str constants of a tuple / list / set display made only of them (at least one), else None."""
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)) and node.elts and (
            all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in node.elts)
            or all(isinstance(e, ast.Constant) and isinstance(e.value, int) and not isinstance(e.value, bool)
                   for e in node.elts)):
        return [e.value for e in node.elts]
    return None


def pure_operand(node):
    return isinstance(node, (ast.Name, ast.Constant)) or (
        isinstance(node, ast.Attribute) and pure_operand(node.value))


def rewrite(tree, inject):
    """Lower the calls and tests in place; `inject(tree, text)` adds the helper functions. Returns whether
    anything changed.

    * `x.bit_length()` / `x.bit_count()` (see above);
    * `x in ("a", "b")` / `not in` over a display of str (or int) constants: `x == "a" or x == "b"` (a name or an
      attribute chain), or a call of a small helper `_ail_in_N(x)` that does the same with x evaluated once.
      The compiler builds a str test against a str display only where it can tell the left side is a str
      (not in a comprehension, nor after a method call)."""
    from iterlower import _name, _call
    wanted = {each.func.attr for each in ast.walk(tree)
              if isinstance(each, ast.Call) and isinstance(each.func, ast.Attribute) and each.func.attr in NAMES
              and not each.args and not each.keywords}
    wanted = {name for name in wanted if not defined_here(tree, name)}
    helpers = []
    state = {'count': 0, 'changed': False}

    class Visitor(ast.NodeTransformer):
        def visit_Call(self, node):
            self.generic_visit(node)
            func = node.func
            if (isinstance(func, ast.Attribute) and func.attr in wanted and not node.args and not node.keywords):
                return ast.copy_location(_call(_name('_ail_' + func.attr), func.value), node)
            return node

        def visit_Compare(self, node):
            self.generic_visit(node)
            if len(node.ops) == 1 and isinstance(node.ops[0], (ast.In, ast.NotIn)):
                values = str_literals(node.comparators[0])
                if values is not None:
                    negate = isinstance(node.ops[0], ast.NotIn)
                    left = node.left
                    if isinstance(left, ast.Constant):
                        return node
                    state['changed'] = True
                    if pure_operand(left):
                        tests = [ast.Compare(left=copy.deepcopy(left), ops=[ast.NotEq() if negate else ast.Eq()],
                                             comparators=[ast.Constant(value=v)]) for v in values]
                        if len(tests) == 1:
                            return ast.copy_location(tests[0], node)
                        return ast.copy_location(ast.BoolOp(op=ast.And() if negate else ast.Or(), values=tests), node)
                    state['count'] += 1
                    name = '_ail_in_%d' % state['count']
                    body = ' or '.join('x == %r' % v for v in values)
                    kind = 'str' if isinstance(values[0], str) else 'int'
                    helpers.append('def %s(x: %s) -> bool:\n    return %s\n' % (name, kind, body))
                    call = _call(_name(name), left)
                    if negate:
                        call = ast.UnaryOp(op=ast.Not(), operand=call)
                    return ast.copy_location(call, node)
            return node

    Visitor().visit(tree)
    ast.fix_missing_locations(tree)
    if wanted:
        helpers.extend(SOURCES[name] for name in sorted(wanted))
    if helpers:
        inject(tree, '\n\n'.join(helpers))
        return True
    return state['changed']
