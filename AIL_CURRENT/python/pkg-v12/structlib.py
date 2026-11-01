"""`struct`: pack / unpack / calcsize / pack_into / unpack_from / iter_unpack and the Struct class (library batch 5).

The format parser, the IEEE 754 bit conversions, the native alignment and the error texts are
prelude_struct.py (ordinary Python source the compiler builds). A program importing none of the module is not
touched; a use that is not built is refused here by name.
"""
import ast

import stdlib5
from stdlib4 import refuse

MODULE = 'struct'
FUNCS = {'pack': '_ail_struct_pack', 'unpack': '_ail_struct_unpack', 'calcsize': '_ail_struct_calcsize',
         'pack_into': '_ail_struct_pack_into', 'unpack_from': '_ail_struct_unpack_from',
         'iter_unpack': '_ail_struct_iter_unpack'}
NAMES = set(FUNCS) | {'Struct', 'error'}
WHAT = ('pack, unpack, calcsize, pack_into, unpack_from, iter_unpack and Struct are built; the format '
        'characters x c b B ? h H i I l L q Q n N e f d s p are built, with the @ = < > ! byte orders')


def run(tree, text):
    binder = stdlib5.take_imports(tree, MODULE, NAMES, unknown=WHAT)
    if not binder:
        return

    def expanded(args):
        parts = []
        for arg in args:
            if isinstance(arg, ast.Starred):
                parts.append(stdlib5.Replace(fix).visit(arg.value))
            else:
                parts.append(ast.List(elts=[stdlib5.Replace(fix).visit(arg)], ctx=ast.Load()))
        return stdlib5.call(stdlib5.name('_ail_struct_expand'), parts)

    def fix(node):
        if isinstance(node, ast.Call) and binder.attr(node.func) in FUNCS:
            name = FUNCS[binder.attr(node.func)]
            found = binder.attr(node.func)
            if found == 'pack' and any(isinstance(arg, ast.Starred) for arg in node.args):
                if not node.args or isinstance(node.args[0], ast.Starred):
                    return None
                return stdlib5.call(stdlib5.name('_ail_struct_pack_seq'),
                                    [stdlib5.Replace(fix).visit(node.args[0]), expanded(node.args[1:])])
            if found == 'pack_into' and any(isinstance(arg, ast.Starred) for arg in node.args):
                if len(node.args) < 4 or any(isinstance(arg, ast.Starred) for arg in node.args[:3]):
                    return None
                return stdlib5.call(stdlib5.name('_ail_struct_pack_into_seq'),
                                    [stdlib5.Replace(fix).visit(arg) for arg in node.args[:3]]
                                    + [expanded(node.args[3:])])
            return stdlib5.call(stdlib5.name(name),
                                [stdlib5.Replace(fix).visit(arg) for arg in node.args])
        found = binder.attr(node)
        if found == 'Struct':
            return stdlib5.name('_AilStruct')
        if found == 'error':
            return stdlib5.name('error')
        return None

    tree.body = [stdlib5.Replace(fix).visit(stmt) for stmt in tree.body]
    binder.names.clear()
    stdlib5.leftover(tree, binder, WHAT)
    source = stdlib5.prelude('struct')
    if any('class _AilArray' in chunk for chunk in text):
        source = source.replace(
            'def _ail_struct_is_array(buffer) -> bool:\n    return False\n',
            'def _ail_struct_is_array(buffer) -> bool:\n    return isinstance(buffer, _AilArray)\n')
    stdlib5.add_once(text, source)
