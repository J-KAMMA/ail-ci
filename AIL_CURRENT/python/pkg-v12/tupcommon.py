"""Shared names and small AST helpers of the tuple lowering (tuplib.py and its mixins)."""
import ast
import copy
import sys
from pathlib import Path

_here = str(Path(__file__).parent)
if _here not in sys.path:
    sys.path.insert(0, _here)

import tuplegen as G  # noqa: E402
from tuplegen import (INT, FLT, STR, BOOL, BYTES, Refused, Hole, R, deep, is_tuple, has_tuple,  # noqa: E402,F401
                      is_table_dict, is_table_set, is_table, known, code, tcode, tname, ann_text, table_name,
                      leaves, fld)

BUILT = ('tuples of int, float, bool, str and of tuples (not variable-length tuple[int, ...]) as return values, '
         'parameters, locals, list / set / dict elements, dict keys and values; unpacking (also nested and in for '
         'loops, comprehensions, enumerate, zip, dict.items()); t[k] with a constant k; divmod; str.partition; '
         '== != < <= > >= and `in`; print / str / repr / f-string; sort, sorted, min, max, heapq with tuple '
         'items; dict[tuple, V] / set[tuple] with get, setdefault, pop, del, update, items, keys, values, set '
         'operators. Not built: tuple concatenation or repetition, slices, a variable index, iterating a tuple, '
         'float dict keys, defaultdict / Counter / deque with tuples')

NUMERIC = (INT, FLT, BOOL)
STR_RET_STR = {'strip', 'lstrip', 'rstrip', 'lower', 'upper', 'title', 'capitalize', 'replace', 'join', 'format',
               'zfill', 'center', 'ljust', 'rjust', 'swapcase', 'casefold', 'removeprefix', 'removesuffix',
               'expandtabs'}
STR_RET_INT = {'find', 'rfind', 'index', 'rindex', 'count'}
STR_RET_BOOL = {'startswith', 'endswith', 'isdigit', 'isalpha', 'isalnum', 'isspace', 'isupper', 'islower',
                'isnumeric', 'isdecimal', 'isidentifier', 'istitle', 'isprintable', 'isascii'}
STR_RET_LIST = {'split', 'rsplit', 'splitlines'}
MATH_FLOAT = {'sqrt', 'sin', 'cos', 'tan', 'asin', 'acos', 'atan', 'atan2', 'exp', 'log', 'log2', 'log10', 'pow',
              'hypot', 'fmod', 'radians', 'degrees', 'fabs', 'sinh', 'cosh', 'tanh', 'copysign', 'ldexp'}
MATH_INT = {'floor', 'ceil', 'trunc', 'isqrt', 'gcd', 'factorial', 'lcm', 'comb', 'perm'}
MATH_VALUES = {'pi': FLT, 'e': FLT, 'tau': FLT, 'inf': FLT, 'nan': FLT}
HEAP_FUNCS = ('heappush', 'heappop', 'heapify', 'heappushpop', 'heapreplace')
LIST_MUTATORS = {'append', 'extend', 'insert', 'pop', 'remove', 'clear', 'sort', 'reverse'}
TABLE_MUTATORS = {'pop', 'popitem', 'setdefault', 'update', 'clear', 'add', 'discard', 'remove',
                  'difference_update', 'intersection_update', 'symmetric_difference_update'}


class Sig:
    def __init__(self, node, owner=None):
        self.node, self.owner = node, owner
        self.params = []        # [(name, type, has_default)]
        self.ret = None
        self.kwonly = []


def name(id_):
    return ast.Name(id=id_, ctx=ast.Load())


def attr(value, field):
    return ast.Attribute(value=value, attr=field, ctx=ast.Load())


def call(func, *args, keywords=()):
    if isinstance(func, str):
        func = name(func)
    return ast.Call(func=func, args=list(args), keywords=list(keywords))


def const(v):
    return ast.Constant(value=v)


def pure(node):
    """An expression that can be evaluated twice: names, constants, attribute chains, constant subscripts."""
    if isinstance(node, (ast.Name, ast.Constant)):
        return True
    if isinstance(node, ast.Attribute):
        return pure(node.value)
    if isinstance(node, ast.Subscript):
        return pure(node.value) and pure(node.slice)
    if isinstance(node, ast.UnaryOp):
        return pure(node.operand)
    if isinstance(node, ast.BinOp):
        return pure(node.left) and pure(node.right)
    return False


def const_int(node):
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        v = const_int(node.operand)
        return None if v is None else -v
    return None


def stores(body, nm):
    """Does this statement list assign to, delete from or call a mutator on the name `nm`?"""
    for st in body:
        for node in ast.walk(st):
            if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.Delete)):
                targets = node.targets if isinstance(node, (ast.Assign, ast.Delete)) else [node.target]
                for t in targets:
                    for sub in ast.walk(t):
                        if isinstance(sub, ast.Name) and sub.id == nm:
                            return True
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name) and node.func.value.id == nm
                    and node.func.attr in LIST_MUTATORS | TABLE_MUTATORS | {'__setitem__'}):
                return True
    return False


def const_type(v):
    if v is None:
        return 'none'
    if isinstance(v, bool):
        return BOOL
    if isinstance(v, int):
        return INT
    if isinstance(v, float):
        return FLT
    if isinstance(v, str):
        return STR
    if isinstance(v, bytes):
        return BYTES
    return None


def elem_of(t):
    """The element type of an iterable; holes are kept (an empty list's element may be settled later)."""
    t = R(t)
    if isinstance(t, tuple):
        if t[0] in ('list', 'set', 'iter'):
            return t[1]
        if t[0] == 'dict':
            return t[1]
        if t[0] == 'range':
            return INT
    if t == STR:
        return STR
    if t == BYTES:
        return INT
    return None


def fresh_copy(node):
    return copy.deepcopy(node)


class Header:
    """A for / comprehension header after lowering: the iterable, the target, and the unpacking that follows.

    unpacks: [(target node, access expression node, type)] -- statements `target = access` in a for loop,
    aliases in a comprehension.  pre: statements to run before the loop."""
    def __init__(self, iter_node, target, unpacks=(), pre=(), ifs=()):
        self.iter, self.target, self.unpacks, self.pre = iter_node, target, list(unpacks), list(pre)
        self.ifs = list(ifs)       # lowered conditions every item must satisfy (filter(...) fused into the loop)


# built-ins that read a list and hand back something new: a module-level number-tuple list rebuilt for them
# (`_ail_rc_NAME()`) gives them the same answer
ROWCONST_READERS = frozenset(('len', 'sorted', 'list', 'sum', 'min', 'max', 'any', 'all', 'enumerate', 'zip',
                              'reversed', 'set', 'frozenset', 'tuple', 'iter', 'map', 'filter'))


def rowconst_in_place(tree, nm):
    """Whether every mention of the module-level list NAME (a list of number tuples) inside a function reads
    it in place: walked by for / a comprehension, indexed, tested with `in`, or handed to a built-in that
    reads it (ROWCONST_READERS). Anything else -- an argument of the program's own function, a name bound
    to it, a method call on it, a return -- would get a rebuilt copy where CPython shares the one list."""
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        parents = {c: p for p in ast.walk(fn) for c in ast.iter_child_nodes(p)}
        for n in ast.walk(fn):
            if not (isinstance(n, ast.Name) and n.id == nm):
                continue
            p = parents.get(n)
            if isinstance(p, (ast.For, ast.AsyncFor, ast.comprehension)) and p.iter is n:
                continue
            if isinstance(p, ast.Subscript) and p.value is n and isinstance(p.ctx, ast.Load):
                continue
            if (isinstance(p, ast.Compare) and n in p.comparators
                    and isinstance(p.ops[p.comparators.index(n)], (ast.In, ast.NotIn))):
                continue
            if (isinstance(p, ast.Call) and n in p.args and isinstance(p.func, ast.Name)
                    and p.func.id in ROWCONST_READERS):
                continue
            return False
    return True
