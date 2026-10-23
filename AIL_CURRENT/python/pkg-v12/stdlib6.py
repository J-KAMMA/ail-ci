"""Library batch 6: `ipaddress.IPv4Address` and the pure-Python pieces of `urllib.parse`.

One entry point, `rewrite_text(source, notes)`, run from ail_syntax.python_surface before the collection
and tuple passes. A program that imports neither module is returned as it was written (the same string),
so its C does not change. Every use is either lowered to the AIL-written Python source of
prelude_ipaddress.py / prelude_urlparse.py (the same pattern as prelude_fraction.py and the other
prelude files) or refused here by name with what to write instead.

* ipaddress: IPv4Address (int, bytes or a dotted string, with CPython 3.12's parse errors, ordering,
  packing and the address properties), AddressValueError and NetmaskValueError (both ValueError here,
  as csv.Error is ValueError). IPv4Network / IPv4Interface / ip_address and IPv6 are refused by name.
* urllib.parse: urlsplit, urlparse, urlunsplit, parse_qs, parse_qsl, quote, quote_plus, unquote,
  unquote_plus, urljoin and urlencode, on both compile paths. Other names are refused by name. The
  result objects expose scheme, netloc, path, params, query, fragment, username, password, hostname,
  port, indexing and geturl().
"""
import ast

import stdlib5
from stdlib4 import Refused, refuse

WORDS = ('ipaddress', 'urllib.parse')

IP_HANDLED = {'IPv4Address', 'AddressValueError', 'NetmaskValueError'}
IP_BUILT = 'IPv4Address is built (AddressValueError and NetmaskValueError are ValueError)'

PARSE_HELP = {
    'urlsplit': '_AilUrlSplit',
    'urlparse': '_AilUrlParse',
    'urlunsplit': '_AilUrlUnsplit',
    'parse_qs': '_AilParseQs',
    'parse_qsl': '_AilParseQsl',
    'quote': '_AilQuote',
    'quote_plus': '_AilQuotePlus',
    'unquote': '_AilUnquote',
    'unquote_plus': '_AilUnquotePlus',
    'urljoin': '_AilUrlJoin',
    'urlencode': '_AilUrlEncode',
}
PARSE_BUILT = ('urlsplit, urlparse, urlunsplit, parse_qs, parse_qsl, quote, quote_plus, unquote, '
               'unquote_plus, urljoin and urlencode are built')


def prelude(name):
    return stdlib5.prelude(name)


# ---------------------------------------------------------------------------------------------------------------
# ipaddress
# ---------------------------------------------------------------------------------------------------------------
def run_ipaddress(tree, text):
    binder = stdlib5.take_imports(tree, 'ipaddress', IP_HANDLED, unknown=IP_BUILT)
    if not binder:
        return
    used = set()

    def fix(node):
        found = binder.attr(node)
        if found is not None:
            if found == 'IPv4Address':
                used.add('_AilIPv4Address')
                return stdlib5.name('_AilIPv4Address')
            if found in ('AddressValueError', 'NetmaskValueError'):
                return stdlib5.name('ValueError')
            refuse(node, 'ipaddress.%s is not built; %s' % (found, IP_BUILT))
        return None

    tree.body = [stdlib5.Replace(fix).visit(stmt) for stmt in tree.body]
    binder.names.clear()
    stdlib5.leftover(tree, binder, IP_BUILT)
    text.append(stdlib5.shake(prelude('ipaddress'), used))


# ---------------------------------------------------------------------------------------------------------------
# urllib.parse
# ---------------------------------------------------------------------------------------------------------------
class ParseBinder:
    def __init__(self):
        self.module_names = set()       # local names bound to `urllib` by `import urllib.parse`
        self.direct = set()             # local names bound to `urllib.parse` by `import urllib.parse as x`
        self.names = {}                 # from-imported local name -> attribute
        self.first = None

    def __bool__(self):
        return bool(self.module_names or self.direct or self.names)

    def attr(self, node):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in self.names:
            return self.names[node.id]
        if isinstance(node, ast.Attribute):
            value = node.value
            if isinstance(value, ast.Attribute) and value.attr == 'parse' \
                    and isinstance(value.value, ast.Name) and value.value.id in self.module_names:
                return node.attr
            if isinstance(value, ast.Name) and value.id in self.direct:
                return node.attr
        return None


def take_parse_imports(tree):
    binder = ParseBinder()
    body = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            rest = []
            for alias in node.names:
                if alias.name == 'urllib.parse':
                    binder.first = binder.first or node
                    if alias.asname:
                        binder.direct.add(alias.asname)
                    else:
                        binder.module_names.add('urllib')
                else:
                    rest.append(alias)
            if rest:
                node.names = rest
                body.append(node)
            continue
        if isinstance(node, ast.ImportFrom) and not node.level and node.module == 'urllib.parse':
            binder.first = binder.first or node
            for alias in node.names:
                if alias.name == '*':
                    refuse(node, 'from urllib.parse import *: name what you use')
                binder.names[alias.asname or alias.name] = alias.name
            continue
        body.append(node)
    tree.body = body
    return binder


def run_urllib_parse(tree, text):
    binder = take_parse_imports(tree)
    if not binder:
        return
    used = set()

    def fix(node):
        found = binder.attr(node)
        if found is not None:
            helper = PARSE_HELP.get(found)
            if helper is None:
                refuse(node, 'urllib.parse.%s is not built; %s' % (found, PARSE_BUILT))
            used.add(helper)
            return stdlib5.name(helper)
        return None

    tree.body = [stdlib5.Replace(fix).visit(stmt) for stmt in tree.body]
    for each in ast.walk(tree):
        if isinstance(each, ast.Attribute) and each.attr == 'parse' and isinstance(each.value, ast.Name) \
                and each.value.id in binder.module_names:
            refuse(each, 'urllib.parse used as a value is not built; call one of its functions (%s)' % PARSE_BUILT)
        if isinstance(each, ast.Name) and isinstance(each.ctx, ast.Load) and each.id in binder.direct:
            refuse(each, 'urllib.parse used as a value is not built; call one of its functions (%s)' % PARSE_BUILT)
    text.append(stdlib5.shake(prelude('urlparse'), used))


# ---------------------------------------------------------------------------------------------------------------
def rewrite_text(source, notes=None):
    """The program text with the batch-6 modules lowered; the source as written (and `notes` filled) when a
    use is not built."""
    if not any(word in source for word in WORDS):
        return source
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    mods = stdlib5.imported_modules(tree)
    if 'ipaddress' not in mods and 'urllib' not in mods:
        return source
    text = []
    try:
        before = ast.dump(tree)
        if 'ipaddress' in mods:
            run_ipaddress(tree, text)
        if 'urllib' in mods:
            run_urllib_parse(tree, text)
        changed = ast.dump(tree) != before or bool(text)
        if not changed:
            return source
        if text:
            stdlib5.insert_after_imports(tree, '\n\n'.join(text))
        ast.fix_missing_locations(tree)
        out = ast.unparse(tree)
    except Refused as exc:
        if notes is not None:
            notes.append((exc.line, exc.text))
        return source
    except (AttributeError, KeyError, IndexError, TypeError, ValueError, RecursionError) as exc:
        if notes is not None:
            notes.append((1, 'the batch-6 library rewrite could not handle this program (%s: %s); simplify the '
                          'use or report it' % (type(exc).__name__, exc)))
        return source
    return out.rstrip('\n') + '\n'
