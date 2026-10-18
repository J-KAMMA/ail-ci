"""random.Random(seed) as a class (library batch 5, called from stdlib5).

`rng = random.Random(seed)` makes an object with its own Mersenne Twister state (prelude_random.py: CPython 3.12's
MT19937 and the methods built on it, bit for bit): `random randint randrange choice shuffle sample uniform gauss
getrandbits choices expovariate triangular seed`. Any number of generators, kept in variables, fields, lists or
passed to functions.

A program that also calls the module-level functions (`random.seed(1)`, `random.randint(1, 6)`) keeps their state
apart from every `Random` object, as CPython does: they become calls of one hidden generator, `_ail_rng`, which the
program seeds with `random.seed(<int>)` (without a seed it starts from 0, where CPython starts from the OS).
A program that only uses the module-level functions is not touched here (stdlib3 builds those on the typed path).

Not built, refused by name: `random.Random()` without a seed (not reproducible), a seed that is a str / bytes /
float / None (CPython hashes those), `random.SystemRandom`, `getstate` / `setstate`, `randbytes`, the other
distributions. getrandbits(k) beyond 62 bits is a RuntimeError (integers are 64-bit).
"""
import ast

import stdlib5
from stdlib4 import refuse

MODULE_FUNCS = {'seed', 'random', 'randint', 'randrange', 'uniform', 'gauss', 'choice', 'shuffle', 'sample',
                'getrandbits', 'choices', 'expovariate', 'triangular'}


def run(tree, text):
    peek = stdlib5.peek_imports(tree, 'random')
    if not peek:
        return
    if not any(peek.attr(n) == 'Random' for n in ast.walk(tree) if isinstance(n, (ast.Attribute, ast.Name))):
        return                                     # only the module-level functions: stdlib3's
    for each in ast.walk(tree):
        if isinstance(each, ast.ClassDef) and each.name in ('Random', '_ail_rng') or (
                isinstance(each, ast.Name) and each.id in ('Random', '_ail_rng') and isinstance(each.ctx, ast.Store)):
            refuse(tree.body[0] if tree.body else tree, 'the program binds the name Random itself; rename it')
    rb = stdlib5.take_imports(tree, 'random', set(), whole=False)
    module_used = {'yes': False}

    def fix(node):
        if isinstance(node, ast.Call) and peek.attr(node.func) == 'Random':
            if len(node.args) != 1 or node.keywords:
                refuse(node, 'random.Random() without exactly one seed is not built: an unseeded generator is not '
                       'reproducible; write random.Random(<int>)')
            seed = node.args[0]
            if isinstance(seed, ast.Constant) and not isinstance(seed.value, int):
                refuse(node, 'random.Random(seed): a seed that is a str, bytes, float or None is not built (CPython '
                       'hashes it); use an int')
            return ast.Call(func=stdlib5.name('Random'), args=[stdlib5.Replace(fix).visit(seed)], keywords=[])
        found = peek.attr(node)
        if found == 'Random':
            return stdlib5.name('Random')
        if found in MODULE_FUNCS:
            module_used['yes'] = True
            return ast.Attribute(value=stdlib5.name('_ail_rng'), attr=found, ctx=ast.Load())
        return None
    tree.body = [stdlib5.Replace(fix).visit(s) for s in tree.body]
    # what is left of the module's names is not a call we can send to the hidden generator
    for each in ast.walk(tree):
        if isinstance(each, ast.Attribute) and isinstance(each.value, ast.Name) and each.value.id in peek.aliases:
            refuse(each, 'random.%s is not built next to random.Random (use a Random object for it)' % each.attr)
        if isinstance(each, ast.Name) and each.id in peek.aliases and isinstance(each.ctx, ast.Load):
            refuse(each, 'random used as a value is not built')
    # drop the imports of the module (the class replaces them), keeping other names of a from-import
    body = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            node.names = [a for a in node.names if a.name != 'random']
            if not node.names:
                continue
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module == 'random':
            continue
        body.append(node)
    tree.body = body
    if not any(isinstance(n, ast.Import) and any(a.name == 'math' and not a.asname for a in n.names) for n in tree.body):
        index = 0
        while index < len(tree.body) and isinstance(tree.body[index], ast.Expr) and isinstance(
                tree.body[index].value, ast.Constant):
            index += 1
        tree.body.insert(index, ast.Import(names=[ast.alias(name='math', asname=None)]))
    chunk = stdlib5.prelude('random')
    if module_used['yes']:
        chunk += '\n_ail_rng = Random(0)\n'
    text.append(chunk)
