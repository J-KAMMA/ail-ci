# -*- coding: utf-8 -*-
"""csv on the general path (the fallback of stdlib4 when csvlib's list-and-cursor lowering refuses a program).

csvlib lowers `csv.reader(lines)` / `DictReader` / `writer(sys.stdout)` onto lists of rows for the typed path, and refuses
what that cannot hold (a writer to an io.StringIO, `DictWriter.writerows`, `reader.line_num`, `strict=True` with `csv.Error`
caught, a reader passed around ...). Those programs get prelude_csv.py instead: the names `csv.reader`, `csv.writer`,
`csv.DictReader`, `csv.DictWriter`, `csv.Error` and `csv.QUOTE_*` become the prelude's classes (a port of _csv.c and csv.py),
and `sys.stdout` as the file of a writer becomes an object that prints. Dialect classes, `register_dialect`, `Sniffer`,
`field_size_limit` and the other names are refused by name.
"""
import ast
import os

import stdlib4
import stdlib5

HERE = os.path.dirname(os.path.abspath(__file__))
NAMES = {'reader': '_ail_csv_reader', 'writer': '_ail_csv_writer', 'DictReader': '_ail_csv_DictReader',
         'DictWriter': '_ail_csv_DictWriter', 'Error': '_AilCsvError'}
QUOTING = {'QUOTE_MINIMAL': 0, 'QUOTE_ALL': 1, 'QUOTE_NONNUMERIC': 2, 'QUOTE_NONE': 3}


def is_stdout(node):
    return (isinstance(node, ast.Attribute) and node.attr == 'stdout' and isinstance(node.value, ast.Name)
            and node.value.id == 'sys')


def run(imports, tree, helpers):
    roots = set()

    class Lower(ast.NodeTransformer):
        def swap(self, attr, node):
            if attr in QUOTING:
                return ast.copy_location(ast.Constant(value=QUOTING[attr]), node)
            if attr in NAMES:
                roots.add(NAMES[attr])
                return ast.copy_location(ast.Name(id=NAMES[attr], ctx=ast.Load()), node)
            stdlib4.refuse(node, 'csv.%s is not built (reader, writer, DictReader, DictWriter, Error and the QUOTE_ '
                           'constants are)' % attr)

        def visit_Attribute(self, node):
            found = imports.resolve(node)
            if found is not None and found[0] == 'csv':
                return self.swap(found[1], node)
            return self.generic_visit(node)

        def visit_Name(self, node):
            if isinstance(node.ctx, ast.Load) and node.id in imports.names and imports.names[node.id][0] == 'csv':
                return self.swap(imports.names[node.id][1], node)
            return node

        def visit_Call(self, node):
            self.generic_visit(node)
            if isinstance(node.func, ast.Name) and node.func.id in ('_ail_csv_writer', '_ail_csv_DictWriter'):
                args = list(node.args)
                if args and is_stdout(args[0]):
                    roots.add('_AilCsvStdout')
                    args[0] = ast.copy_location(ast.Call(func=ast.Name(id='_AilCsvStdout', ctx=ast.Load()), args=[],
                                                         keywords=[]), args[0])
                    node.args = args
            return node

    tree.body = [Lower().visit(s) for s in tree.body]
    for each in ast.walk(tree):
        if isinstance(each, ast.Name) and each.id in imports.aliases and isinstance(each.ctx, ast.Load):
            stdlib4.refuse(each, '%s used as a value is not built' % imports.aliases[each.id])
    if roots:
        helpers.append(stdlib5.shake(open(os.path.join(HERE, 'prelude_csv.py'), encoding='utf-8').read(), roots))
