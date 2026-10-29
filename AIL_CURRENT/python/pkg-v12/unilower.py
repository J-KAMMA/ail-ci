# -*- coding: utf-8 -*-
"""unilower.py -- `unicodedata.name`, `unicodedata.category` and `unicodedata.normalize` (Unicode 15.0).

A tree-to-tree pass in the manner of hashlower.py, run by both compile paths before the library preludes.
CPython 3.12.3's own unicodedata is the oracle, so the data in ailuni_core.h is generated from it by
tools/gen_unicodedata.py (categories, names, canonical/compatibility decompositions, combining classes and
composition pairs; CJK/Khitan/Nushu names and Hangul syllables are algorithmic).

Built:

  * unicodedata.name(ch) / unicodedata.name(ch, default)   (default: a string constant)
  * unicodedata.category(ch)
  * unicodedata.normalize(form, text)   form NFC NFD NFKC NFKD

Everything else in the module (lookup, decomposition, combining, digit, ... and unidata_version) is refused
by name with a `write instead:` line. A program that imports none of the module is not touched.
"""
import ast

MODULES = ('unicodedata',)
BUILT = ('unicodedata.name(ch[, default]), unicodedata.category(ch), '
         'unicodedata.normalize("NFC"|"NFD"|"NFKC"|"NFKD", text)')
_REFUSED = ('unicodedata.lookup', 'unicodedata.decomposition', 'unicodedata.combining', 'unicodedata.digit',
            'unicodedata.decimal', 'unicodedata.numeric', 'unicodedata.bidirectional',
            'unicodedata.east_asian_width', 'unicodedata.mirrored', 'unicodedata.unidata_version')

# name -> (result kind, argument kinds). The C is ailuni_core.h (filert.py typed, safetyrt.py general).
UNIP = {
    '_ail_uni_name1': ('str', ('str',)),
    '_ail_uni_name2': ('str', ('str', 'str')),
    '_ail_uni_category': ('str', ('str',)),
    '_ail_uni_normalize': ('str', ('str', 'str')),
}


def _call(name, args):
    return ast.Call(func=ast.Name(id=name, ctx=ast.Load()), args=list(args), keywords=[])


class _Lowerer(ast.NodeTransformer):
    def __init__(self, tree, Unsupported):
        self.tree = tree
        self.U = Unsupported
        self.aliases = {}          # local module name -> 'unicodedata'
        self.names = {}            # name imported with `from unicodedata import ...`
        self.import_nodes = []
        self.used = False

    def scan(self):
        for node in self.tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == 'unicodedata':
                        self.aliases[alias.asname or alias.name] = 'unicodedata'
                        self.import_nodes.append(node)
            elif isinstance(node, ast.ImportFrom) and not node.level and node.module == 'unicodedata':
                for alias in node.names:
                    if alias.name == '*':
                        self.refuse(node, 'from unicodedata import *: name what you use')
                    self.names[alias.asname or alias.name] = alias.name
                self.import_nodes.append(node)

    def wants(self):
        return bool(self.aliases or self.names)

    def refuse(self, node, text):
        if 'write instead:' not in text:
            text += '\n  write instead: ' + BUILT
        error = self.U(text)
        error.source_line = getattr(node, 'lineno', None)
        raise error

    def resolve(self, node):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                and node.value.id in self.aliases:
            return node.attr
        if isinstance(node, ast.Name) and node.id in self.names:
            return self.names[node.id]
        return None

    def check_char(self, node, attr):
        """A literal argument is checked here; a value known only at run time keeps CPython's runtime error."""
        arg = node.args[0]
        if isinstance(arg, ast.Constant):
            if not isinstance(arg.value, str):
                self.refuse(node, 'unicodedata.%s argument must be a unicode character, not a non-string constant' % attr)
            if len(arg.value) != 1:
                self.refuse(node, 'unicodedata.%s argument must be a single character' % attr)

    def visit_Call(self, node):
        self.generic_visit(node)
        attr = self.resolve(node.func)
        if attr is None:
            return node
        if node.keywords:
            self.refuse(node, 'unicodedata.%s takes positional arguments only' % attr)
        self.used = True
        if attr == 'name':
            if len(node.args) == 1:
                self.check_char(node, 'name')
                return ast.copy_location(_call('_ail_uni_name1', node.args), node)
            if len(node.args) == 2:
                self.check_char(node, 'name')
                default = node.args[1]
                if not (isinstance(default, ast.Constant) and isinstance(default.value, str)):
                    self.refuse(node, 'unicodedata.name default must be a string constant to be built')
                return ast.copy_location(_call('_ail_uni_name2', node.args), node)
            self.refuse(node, 'unicodedata.name takes 1 or 2 positional arguments')
        if attr == 'category':
            if len(node.args) != 1:
                self.refuse(node, 'unicodedata.category takes 1 positional argument')
            self.check_char(node, 'category')
            return ast.copy_location(_call('_ail_uni_category', node.args), node)
        if attr == 'normalize':
            if len(node.args) != 2:
                self.refuse(node, 'unicodedata.normalize takes 2 positional arguments')
            return ast.copy_location(_call('_ail_uni_normalize', node.args), node)
        self.refuse(node, 'unicodedata.%s is not built' % attr)

    def run(self):
        self.tree.body = [self.visit(node) for node in self.tree.body]
        # everything this pass did not lower is a named refusal, not a generic "import not available"
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                    and node.value.id in self.aliases:
                self.refuse(node, 'unicodedata.%s is not built' % node.attr)
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in self.names:
                self.refuse(node, 'unicodedata.%s is not built' % self.names[node.id])
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in self.aliases:
                self.refuse(node, 'unicodedata used as a value is not built')
        self.tree.body = [node for node in self.tree.body if node not in self.import_nodes]
        ast.fix_missing_locations(self.tree)


def rewrite_tree(tree, Unsupported):
    """Lower the three supported calls in `tree` (in place). Returns whether the module is used."""
    lowerer = _Lowerer(tree, Unsupported)
    lowerer.scan()
    if not lowerer.wants():
        return False
    lowerer.run()
    return lowerer.used
