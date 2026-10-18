# -*- coding: utf-8 -*-
"""urllower.py -- stage G12: `urllib.request`, `urllib.error` and `urllib.parse`
(docs/design/GENERAL_PURPOSE.md s4.8; the owner decision is libcurl for HTTPS, Q11).

A tree-to-tree pass in the manner of proclib.py / pathlower.py, run by the typed compile path just before
the file layer. It lowers

  * `urlopen(url_or_request, data=None, timeout=...)`      onto `_ail_ul_open_url` / `_ail_ul_open`
                                                          (urllib_prelude.py: CPython's handler chain as Python
                                                          text over the libcurl hop in ailhttp_core.h);
  * `Request(url, data=None, headers={}, method=None)`     onto `_ail_ul_request` and the methods of its class;
  * the response: `r.read()`, `r.read(n)`, `r.status`, `r.reason`, `r.url`, `r.getcode()`, `r.geturl()`,
    `r.headers.get(name, default)`, `r.getheader(name, default)`, `name in r.headers`, `r.close()`, and
    `with urlopen(...) as r:` (a try/finally that closes);
  * `except urllib.error.HTTPError / URLError [as e]`      onto the exception names of the typed runtime, with
                                                          `e.code`, `e.reason`, `e.url`, `e.msg`, `e.read()`,
                                                          `e.headers.get(...)`, `e.getcode()`, `str(e)`, `print(e)`
                                                          read from the last-error record of the C layer;
  * `urllib.parse.urlencode(d)`, `quote`, `quote_plus`, `unquote`, `unquote_plus`, `urljoin`.

Everything the pass does not build is refused by name with a `write instead:` line. A program that does not
import urllib is not touched, so its C stays byte for byte what it was, and a program that uses urllib.parse
only does not link libcurl.
"""
import ast
import copy
import os
import subprocess
import sys

import iterlower

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------------------------
# The primitives: name -> (result kind, argument kinds). The C behind them is ailhttp_core.h (`_ail_ht_`)
# and ailurl_core.h (`_ail_ur_`); filert.py holds the adapters.

HTTP_PRIMS = {
    '_ail_ht_begin': ('int', ('str', 'str', 'int')),
    '_ail_ht_hdr': ('int', ('str', 'str')),
    '_ail_ht_body': ('int', ('bytes',)),
    '_ail_ht_perform': ('int', ()),
    '_ail_ht_failed': ('int', ('int',)),
    '_ail_ht_errtext': ('str', ('int',)),
    '_ail_ht_status': ('int', ('int',)),
    '_ail_ht_reason': ('str', ('int',)),
    '_ail_ht_nhdr': ('int', ('int',)),
    '_ail_ht_hname': ('str', ('int', 'int')),
    '_ail_ht_hval': ('str', ('int', 'int')),
    '_ail_ht_hfind': ('int', ('int', 'str')),
    '_ail_ht_read': ('bytes', ('int', 'int')),
    '_ail_ht_close': ('int', ('int',)),
    '_ail_ht_free': ('int', ('int',)),
    '_ail_ht_eset': ('int', ('int', 'int', 'int', 'str', 'str', 'str')),
    '_ail_ht_ecode': ('int', ()),
    '_ail_ht_eh': ('int', ()),
    '_ail_ht_eurl': ('str', ()),
    '_ail_ht_ereason': ('str', ()),
    '_ail_ht_emsg': ('str', ()),
}
URL_PRIMS = {
    '_ail_ur_unquote': ('str', ('str', 'int')),
    '_ail_ur_repr': ('str', ('str',)),
}
PRIMS = dict(HTTP_PRIMS)
PRIMS.update(URL_PRIMS)

ACTIVE = False          # set when the last pass lowered a program that reaches libcurl (urllib.request / urllib.error)
USED = False            # set when the last pass lowered any urllib use at all

_REQUEST_BUILT = 'urllib.request.urlopen(url or Request, data=None, timeout=) and urllib.request.Request(url, data=None, ' \
                 'headers={}, method=None)'
_BUILT = 'Built: %s, the response (read status reason url getcode geturl headers.get getheader close with), ' \
         'urllib.error.HTTPError / URLError in except, urllib.parse.urlencode quote quote_plus unquote unquote_plus urljoin' \
         % _REQUEST_BUILT

_REQUEST_REFUSED = {
    'build_opener': 'an opener with handlers is not built; urlopen(Request(url, headers={...})) sends headers, and the proxy comes from the '
                    'environment (http_proxy, https_proxy, no_proxy)',
    'install_opener': 'openers are not built; urlopen(Request(url, headers={...})) sends headers',
    'urlretrieve': 'read the body and write it yourself: data = urlopen(url).read(); open(path, "wb").write(data)',
    'urlcleanup': 'nothing to clean up',
    'ProxyHandler': 'set http_proxy / https_proxy / no_proxy in the environment',
    'HTTPBasicAuthHandler': 'send the header yourself: headers={"Authorization": "Basic " + token}',
    'HTTPPasswordMgrWithDefaultRealm': 'send the header yourself: headers={"Authorization": "Basic " + token}',
    'HTTPCookieProcessor': 'send the Cookie header yourself: headers={"Cookie": "a=b"}',
    'HTTPHandler': 'handlers are not built', 'HTTPSHandler': 'handlers are not built',
    'HTTPRedirectHandler': 'redirects are followed as urlopen follows them by default',
    'OpenerDirector': 'openers are not built', 'BaseHandler': 'handlers are not built',
    'pathname2url': 'not built', 'url2pathname': 'not built', 'getproxies': 'read the environment with os.getenv',
}
_PARSE_REFUSED = {
    'urlparse': 'split the text yourself with find() / split() ("://", "/", "?", "#")',
    'urlsplit': 'split the text yourself with find() / split() ("://", "/", "?", "#")',
    'urlunparse': 'join the parts yourself with +',
    'urlunsplit': 'join the parts yourself with +',
    'urldefrag': 'url.split("#")[0]',
    'parse_qs': 'split the query on "&" and "=" and unquote() each part',
    'parse_qsl': 'split the query on "&" and "=" and unquote() each part',
    'quote_from_bytes': 'quote(data.decode()) for text; bytes are not built',
    'unquote_to_bytes': 'not built',
    'splitquery': 'not built', 'splittype': 'not built', 'splithost': 'not built',
}
_PARSE_OK = ('urlencode', 'quote', 'quote_plus', 'unquote', 'unquote_plus', 'urljoin')


# ---------------------------------------------------------------------------------------------
# libcurl: where its header and libraries are. Probed once, and only for a program that reaches it.

_probe_cache = {}


def _run(cmd, **kw):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=60, **kw)
    except (OSError, subprocess.SubprocessError):
        return None


def _probe(static=False):
    """(cflags, libs) for libcurl, or None when its header cannot be compiled against."""
    key = (os.environ.get('PIPE_CC', ''), static, os.environ.get('AIL_NO_CURL', ''))
    if key in _probe_cache:
        return _probe_cache[key]
    found = None
    if not os.environ.get('AIL_NO_CURL'):
        cflags, libs = [], ['-lcurl']
        import shlex
        for tool in (['pkg-config'], ['curl-config']):
            if tool == ['pkg-config']:
                a = _run(tool + ['--cflags', 'libcurl'])
                b = _run(tool + ['--static'] * static + ['--libs', 'libcurl'])
            else:
                a = _run(tool + ['--cflags'])
                b = _run(tool + ['--static-libs' if static else '--libs'])
            if a is not None and b is not None and a.returncode == 0 and b.returncode == 0 and b.stdout.strip():
                cflags, libs = shlex.split(a.stdout), shlex.split(b.stdout)
                break
        import pipeline
        try:
            cc = pipeline.compiler()
        except Exception:
            cc = None
        if cc:
            try:
                r = subprocess.run([cc, *cflags, '-fsyntax-only', '-x', 'c', '-'], input='#include <curl/curl.h>\n',
                                   capture_output=True, text=True, timeout=60)
                ok = r.returncode == 0
            except (OSError, subprocess.SubprocessError):
                ok = False
            if ok:
                found = (cflags, libs)
    _probe_cache[key] = found
    return found


def available():
    """Whether a program using urllib.request can be built here (the libcurl header is found)."""
    return _probe() is not None


def cflags():
    """Compiler flags (include paths) of libcurl for the program being built; empty unless it uses urllib.request."""
    if not ACTIVE:
        return []
    found = _probe()
    return list(found[0]) if found else []


def libs(static=False):
    """Link arguments of libcurl, to come after the objects; empty unless the program being built uses urllib.request."""
    if not ACTIVE:
        return []
    found = _probe(static)
    return list(found[1]) if found else ['-lcurl']


NO_CURL_TEXT = ('urllib.request needs libcurl and its header curl/curl.h was not found.\n'
                '  install it: Debian/Ubuntu: sudo apt install libcurl4-openssl-dev; Fedora: sudo dnf install libcurl-devel;\n'
                '  macOS: brew install curl; MSYS2: pacman -S mingw-w64-ucrt-x86_64-curl\n'
                '  write instead: nothing in this language fetches a URL without libcurl; run the fetch outside the program')


# ---------------------------------------------------------------------------------------------
# The prelude: urllib_prelude.py, kept as one snippet per definition

_prelude = {}


def _load_prelude():
    if _prelude:
        return _prelude
    with open(os.path.join(HERE, 'urllib_prelude.py'), 'r', encoding='utf-8') as handle:
        tree = ast.parse(handle.read())
    defs = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
    names = [n.name for n in defs]
    for node in defs:
        if isinstance(node, ast.FunctionDef):
            _prefix_locals(node)
        needs = set()
        for each in ast.walk(node):
            if isinstance(each, ast.Name) and each.id in names and each.id != node.name:
                needs.add(each.id)
        _prelude[node.name] = (ast.unparse(node), needs)
    _prelude['__order__'] = names
    return _prelude


class _Prefix(ast.NodeTransformer):
    def __init__(self, names):
        self.names = names

    def visit_Name(self, node):
        if node.id in self.names:
            node.id = '_ul_' + node.id
        return node

    def visit_arg(self, node):
        if node.arg in self.names:
            node.arg = '_ul_' + node.arg
        return self.generic_visit(node)


def _prefix_locals(fn):
    """Every local of a prelude function gets a `_ul_` prefix: a user function named `names` or `host` must not
    meet a local of the same name."""
    names = {a.arg for a in fn.args.args + fn.args.kwonlyargs}
    for each in ast.walk(fn):
        if isinstance(each, ast.Name) and isinstance(each.ctx, ast.Store):
            names.add(each.id)
    names = {n for n in names if not n.startswith('_')}
    _Prefix(names).visit(fn)


# ---------------------------------------------------------------------------------------------

def _simple(node):
    return isinstance(node, (ast.Constant, ast.Name)) or (isinstance(node, ast.Attribute) and _simple(node.value))


class _Lowerer(ast.NodeTransformer):
    def __init__(self, tree, Unsupported, general=False):
        self.tree = tree
        self.U = Unsupported
        self.general = general
        self.mods = {}                  # local name -> 'urllib' | 'urllib.request' | 'urllib.error' | 'urllib.parse'
        self.names = {}                 # local name -> 'urllib.request.urlopen' ...
        self.import_nodes = []
        self.user_defs = set()
        self.synth = set()
        self.need = set()
        self.resp_names = set()
        self.req_names = set()
        self.req_funcs = set()
        self.exc_seen = False
        self.http = False               # reaches libcurl
        self.used = False
        self.counter = 0

    # ---- helpers ---------------------------------------------------------------------------
    def refuse(self, node, text):
        error = self.U(text)
        error.source_line = getattr(node, 'lineno', None)
        raise error

    def N(self, id_, store=False):
        node = iterlower._name(id_, store)
        self.synth.add(id(node))
        return node

    @staticmethod
    def C(value):
        if isinstance(value, int) and not isinstance(value, bool) and value < 0:
            return ast.UnaryOp(op=ast.USub(), operand=ast.Constant(value=-value))
        return ast.Constant(value=value)

    def fn(self, name, *args):
        """A call of a prelude function (its definitions are injected, and what they use with them)."""
        self.need.add(name)
        return ast.Call(func=self.N(name), args=list(args), keywords=[])

    def call(self, func, *args):
        if isinstance(func, str):
            func = self.N(func)
        return ast.Call(func=func, args=list(args), keywords=[])

    @staticmethod
    def method(obj, name, *args):
        return ast.Call(func=ast.Attribute(value=obj, attr=name, ctx=ast.Load()), args=list(args), keywords=[])

    @staticmethod
    def at(node, origin):
        ast.copy_location(node, origin)
        ast.fix_missing_locations(node)
        return node

    def fresh(self, stem):
        self.counter += 1
        return '_ail_ul_%s%d' % (stem, self.counter)

    # ---- scanning --------------------------------------------------------------------------
    def scan(self):
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)) and node not in self.tree.body:
                names = [node.module] if isinstance(node, ast.ImportFrom) else [a.name for a in node.names]
                if any(n and n.split('.')[0] == 'urllib' for n in names):
                    self.refuse(node, 'import urllib at the top of the file, not inside a function or block')
        for node in self.tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                self.user_defs.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    for each in ast.walk(target):
                        if isinstance(each, ast.Name):
                            self.user_defs.add(each.id)
            if isinstance(node, ast.Import):
                hit = [a for a in node.names if a.name.split('.')[0] == 'urllib']
                if hit and len(hit) != len(node.names):
                    self.refuse(node, 'import urllib.request together with other modules on one line: write one import per line')
                for alias in hit:
                    if alias.name not in ('urllib', 'urllib.request', 'urllib.error', 'urllib.parse'):
                        self.refuse(node, '%s is not built. %s' % (alias.name, _BUILT))
                    if alias.asname:
                        self.mods[alias.asname] = alias.name
                    else:
                        self.mods['urllib'] = 'urllib'
                if hit:
                    self.import_nodes.append(node)
            elif isinstance(node, ast.ImportFrom) and not node.level and node.module and node.module.split('.')[0] == 'urllib':
                for alias in node.names:
                    if alias.name == '*':
                        self.refuse(node, 'from %s import *: name what you use' % node.module)
                    local = alias.asname or alias.name
                    if node.module == 'urllib':
                        if alias.name in ('request', 'error', 'parse'):
                            self.mods[local] = 'urllib.' + alias.name
                        else:
                            self.refuse(node, 'urllib.%s is not built. %s' % (alias.name, _BUILT))
                    elif node.module in ('urllib.request', 'urllib.error', 'urllib.parse'):
                        self.names[local] = node.module + '.' + alias.name
                    else:
                        self.refuse(node, '%s is not built. %s' % (node.module, _BUILT))
                self.import_nodes.append(node)

    def wants(self):
        return bool(self.mods or self.names)

    def qual(self, node):
        """`urllib.request.urlopen`, `ur.urlopen`, `urlopen` ... through the imports, else None."""
        if isinstance(node, ast.Name):
            if node.id in self.user_defs and node.id not in self.names and node.id not in self.mods:
                return None
            if node.id in self.names:
                return self.names[node.id]
            if node.id in self.mods:
                return self.mods[node.id]
            return None
        if isinstance(node, ast.Attribute):
            inner = self.qual(node.value)
            if inner is not None:
                return inner + '.' + node.attr
        return None

    # ---- analysis: which names hold a response / a request ---------------------------------
    def is_urlopen(self, node):
        return isinstance(node, ast.Call) and self.qual(node.func) == 'urllib.request.urlopen'

    def is_request_ctor(self, node):
        return isinstance(node, ast.Call) and self.qual(node.func) == 'urllib.request.Request'

    def analyse(self):
        stores, resp, req = {}, {}, {}
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                stores[node.id] = stores.get(node.id, 0) + 1
            elif isinstance(node, ast.arg):
                stores[node.arg] = stores.get(node.arg, 0) + 1
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                if self.is_urlopen(node.value):
                    resp[node.targets[0].id] = resp.get(node.targets[0].id, 0) + 1
                elif self.is_request_ctor(node.value):
                    req[node.targets[0].id] = req.get(node.targets[0].id, 0) + 1
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) \
                    and self.qual(node.annotation) == 'urllib.request.Request':
                req[node.target.id] = req.get(node.target.id, 0) + 1
                node.annotation = self.N('_AilRequest')
                self.need.add('_AilRequest')
            elif isinstance(node, ast.With):
                for item in node.items:
                    if isinstance(item.optional_vars, ast.Name) and self.is_urlopen(item.context_expr):
                        resp[item.optional_vars.id] = resp.get(item.optional_vars.id, 0) + 1
        # user functions annotated `-> Request`: what they return is a request too
        self.req_funcs = {node.name for node in self.tree.body if isinstance(node, ast.FunctionDef)
                          and node.returns is not None and self.qual(node.returns) == 'urllib.request.Request'}
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                    and self.is_req_call(node.value):
                req[node.targets[0].id] = req.get(node.targets[0].id, 0) + 1
        self.resp_names = {name for name, count in resp.items() if stores.get(name, 0) == count}
        self.req_names = {name for name, count in req.items() if stores.get(name, 0) == count}
        # an annotation `urllib.request.Request` / `Request` on a parameter makes that name a request too
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef):
                for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs:
                    if arg.annotation is not None and self.qual(arg.annotation) == 'urllib.request.Request':
                        arg.annotation = self.N('_AilRequest')
                        self.need.add('_AilRequest')
                        self.req_names.add(arg.arg)
                if node.returns is not None and self.qual(node.returns) == 'urllib.request.Request':
                    node.returns = self.N('_AilRequest')
                    self.need.add('_AilRequest')

    def is_resp(self, node):
        return (isinstance(node, ast.Name) and node.id in self.resp_names) or self.is_urlopen(node)

    def is_req_call(self, node):
        return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in self.req_funcs \
            and node.func.id in self.user_defs

    def is_req(self, node):
        return (isinstance(node, ast.Name) and node.id in self.req_names) or self.is_request_ctor(node) \
            or self.is_req_call(node)

    # ---- visiting --------------------------------------------------------------------------
    def visit_Call(self, node):
        name = self.qual(node.func)
        if name is not None:
            low = self.lower_named_call(node, name)
            if low is not None:
                return self.at(low, node)
        func = node.func
        if isinstance(func, ast.Attribute):
            # response and request methods
            if self.is_resp(func.value):
                return self.at(self.resp_method(node), node)
            if isinstance(func.value, ast.Attribute) and func.value.attr == 'headers' and self.is_resp(func.value.value):
                return self.at(self.headers_method(node, func.value.value, 'resp'), node)
            if self.is_req(func.value):
                return self.at(self.req_method(node), node)
        return self.generic_visit(node)

    def lower_named_call(self, node, name):
        if name == 'urllib.request.urlopen':
            return self.lower_urlopen(node)
        if name == 'urllib.request.Request':
            return self.lower_request(node)
        if name.startswith('urllib.request.'):
            member = name.split('.')[2]
            self.refuse(node, '%s is not built: %s.\n  write instead: %s'
                        % (name, _BUILT, _REQUEST_REFUSED.get(member, 'urlopen(Request(url, headers={...}))')))
        if name.startswith('urllib.parse.'):
            return self.lower_parse(node, name.split('.', 2)[2])
        if name in ('urllib.error.HTTPError', 'urllib.error.URLError'):
            self.refuse(node, '%s(...) is not built: the program cannot construct one.\n  write instead: let urlopen raise it' % name)
        if name.startswith('urllib.error.'):
            self.refuse(node, '%s is not built. Built: HTTPError and URLError in `except`' % name)
        return None

    def lower_urlopen(self, call):
        if any(isinstance(a, ast.Starred) for a in call.args) or any(k.arg is None for k in call.keywords):
            self.refuse(call, 'urlopen() with * or ** arguments is not built.\n  write instead: name each argument')
        if len(call.args) > 3:
            self.refuse(call, 'urlopen() takes at most url, data and timeout')
        given = {}
        for key, value in zip(('url', 'data', 'timeout'), call.args):
            given[key] = value
        for keyword in call.keywords:
            if keyword.arg in given:
                self.refuse(call, "urlopen() got multiple values for argument '%s'" % keyword.arg)
            if keyword.arg in ('cafile', 'capath', 'cadefault', 'context'):
                self.refuse(call, 'urlopen(%s=...) is not built: certificates are checked against the system store and SSL_CERT_FILE / '
                                  'SSL_CERT_DIR, as ssl.create_default_context() does.\n'
                                  '  write instead: set SSL_CERT_FILE in the environment' % keyword.arg)
            if keyword.arg not in ('url', 'data', 'timeout'):
                self.refuse(call, "urlopen() got an unexpected keyword argument '%s'" % keyword.arg)
            given[keyword.arg] = keyword.value
        if 'url' not in given:
            self.refuse(call, "urlopen() missing required argument 'url'")
        self.http = self.used = True
        self.check_literal_url(call, given['url'])
        tmo = self.timeout_value(call, given.get('timeout'))
        target = self.visit(copy.deepcopy(given['url']))
        data = given.get('data')
        has_data = data is not None and not (isinstance(data, ast.Constant) and data.value is None)
        if self.is_req(given['url']):
            if has_data:
                self.refuse(call, 'urlopen(request, data) replaces request.data: not built.\n  write instead: Request(url, data=data) and urlopen(request)')
            return self.fn('_ail_ul_open', target, tmo)
        return self.fn('_ail_ul_open_url', target, self.visit(copy.deepcopy(data)) if has_data else self.C(b''),
                       self.C(bool(has_data)), tmo)

    _OTHER_SCHEMES = {'ftp': 'ftp', 'ftps': 'ftp', 'file': 'file', 'data': 'data'}

    def check_literal_url(self, call, node):
        """A URL written out with a scheme CPython handles on its own (ftp, file, data) is refused: this build speaks http and https."""
        text = node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None
        if text is None and isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add) \
                and isinstance(node.left, ast.Constant) and isinstance(node.left.value, str):
            text = node.left.value
        if text is None and isinstance(node, ast.JoinedStr) and node.values and isinstance(node.values[0], ast.Constant) \
                and isinstance(node.values[0].value, str):
            text = node.values[0].value
        if text is None:
            return
        scheme = text.strip().split(':', 1)[0].lower() if ':' in text else ''
        if scheme in self._OTHER_SCHEMES:
            hint = {'ftp': 'ftplib is not built; fetch the file another way',
                    'file': 'read the file with open(path, "rb")',
                    'data': 'decode the data: URL yourself'}[self._OTHER_SCHEMES[scheme]]
            self.refuse(call, 'a %s: URL is not built: urllib.request here speaks http:// and https:// only.\n  write instead: %s'
                        % (scheme, hint))

    def timeout_value(self, call, node):
        if node is None or (isinstance(node, ast.Constant) and node.value is None):
            return self.C(-1)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                self.refuse(call, 'urlopen(timeout=...) must be a number')
            return self.C(int(node.value * 1000000))
        expr = self.visit(copy.deepcopy(node))
        return self.call('int', ast.BinOp(left=self.call('float', expr), op=ast.Mult(), right=ast.Constant(value=1000000.0)))

    def header_lists(self, call, node):
        if node is None or (isinstance(node, ast.Constant) and node.value is None):
            return ast.List(elts=[], ctx=ast.Load()), ast.List(elts=[], ctx=ast.Load())
        if isinstance(node, ast.Dict):
            if any(key is None for key in node.keys):
                self.refuse(call, 'headers={**...} is not built.\n  write instead: name each header, headers={"Accept": "text/html"}')
            return (ast.List(elts=[self.visit(copy.deepcopy(k)) for k in node.keys], ctx=ast.Load()),
                    ast.List(elts=[self.visit(copy.deepcopy(v)) for v in node.values], ctx=ast.Load()))
        if _simple(node):
            return (self.call('list', self.method(self.visit(copy.deepcopy(node)), 'keys')),
                    self.call('list', self.method(self.visit(copy.deepcopy(node)), 'values')))
        self.refuse(call, 'headers= is built for a dict written out or a name.\n  write instead: bind the dict to a variable first')

    def lower_request(self, call):
        if any(isinstance(a, ast.Starred) for a in call.args) or any(k.arg is None for k in call.keywords):
            self.refuse(call, 'Request() with * or ** arguments is not built.\n  write instead: name each argument')
        keys = ('url', 'data', 'headers', 'origin_req_host', 'unverifiable', 'method')
        if len(call.args) > len(keys):
            self.refuse(call, 'Request() takes at most url, data, headers, origin_req_host, unverifiable and method')
        given = dict(zip(keys, call.args))
        for keyword in call.keywords:
            if keyword.arg in given:
                self.refuse(call, "Request() got multiple values for argument '%s'" % keyword.arg)
            if keyword.arg not in keys:
                self.refuse(call, "Request() got an unexpected keyword argument '%s'" % keyword.arg)
            given[keyword.arg] = keyword.value
        if 'url' not in given:
            self.refuse(call, "Request() missing required argument 'url'")
        for extra in ('origin_req_host', 'unverifiable'):
            value = given.get(extra)
            if value is not None and not (isinstance(value, ast.Constant) and value.value in (None, False)):
                self.refuse(call, 'Request(%s=...) is not built (it only matters to cookie handling)' % extra)
        self.http = self.used = True
        self.check_literal_url(call, given['url'])
        data = given.get('data')
        has_data = data is not None and not (isinstance(data, ast.Constant) and data.value is None)
        method = given.get('method')
        if method is None or (isinstance(method, ast.Constant) and method.value is None):
            method = self.C('')
        else:
            method = self.visit(copy.deepcopy(method))
        hk, hv = self.header_lists(call, given.get('headers'))
        return self.fn('_ail_ul_request', self.visit(copy.deepcopy(given['url'])),
                       self.visit(copy.deepcopy(data)) if has_data else self.C(b''), self.C(bool(has_data)), method, hk, hv)

    def lower_parse(self, call, member):
        if member not in _PARSE_OK:
            self.refuse(call, 'urllib.parse.%s is not built. %s\n  write instead: %s'
                        % (member, _BUILT, _PARSE_REFUSED.get(member, 'not built')))
        if any(isinstance(a, ast.Starred) for a in call.args) or any(k.arg is None for k in call.keywords):
            self.refuse(call, 'urllib.parse.%s() with * or ** arguments is not built.\n  write instead: name each argument' % member)
        self.used = True
        given = {}
        order = {'quote': ('string', 'safe'), 'quote_plus': ('string', 'safe'), 'unquote': ('string',),
                 'unquote_plus': ('string',), 'urlencode': ('query',), 'urljoin': ('base', 'url')}[member]
        if len(call.args) > len(order):
            self.refuse(call, 'urllib.parse.%s(...) with more than %s is not built (no encoding=, errors=, doseq=, quote_via=)'
                        % (member, ', '.join(order)))
        for key, value in zip(order, call.args):
            given[key] = value
        for keyword in call.keywords:
            if keyword.arg in given:
                self.refuse(call, "urllib.parse.%s() got multiple values for argument '%s'" % (member, keyword.arg))
            if keyword.arg not in order:
                self.refuse(call, 'urllib.parse.%s(%s=...) is not built. Built arguments: %s' % (member, keyword.arg, ', '.join(order)))
            given[keyword.arg] = keyword.value
        for key in order:
            if key not in given and not (member in ('quote', 'quote_plus') and key == 'safe'):
                self.refuse(call, "urllib.parse.%s() missing required argument '%s'" % (member, key))
        visit = lambda n: self.visit(copy.deepcopy(n))
        if member in ('quote', 'quote_plus'):
            safe = visit(given['safe']) if 'safe' in given else self.C('/' if member == 'quote' else '')
            return self.fn('_ail_ul_quote', visit(given['string']), safe, self.C(member == 'quote_plus'))
        if member in ('unquote', 'unquote_plus'):
            return self.fn('_ail_ul_unquote', visit(given['string']), self.C(member == 'unquote_plus'))
        if member == 'urljoin':
            return self.fn('_ail_ul_urljoin', visit(given['base']), visit(given['url']))
        query = given['query']
        if isinstance(query, ast.Dict):
            if any(key is None for key in query.keys):
                self.refuse(call, 'urlencode({**...}) is not built.\n  write instead: name each key')
            keys = ast.List(elts=[self.as_str(visit(k)) for k in query.keys], ctx=ast.Load())
            vals = ast.List(elts=[self.as_str(visit(v)) for v in query.values], ctx=ast.Load())
        elif _simple(query):
            keys = self.call('list', self.method(visit(query), 'keys'))
            vals = self.call('list', self.method(visit(query), 'values'))
        else:
            self.refuse(call, 'urlencode() is built for a dict written out or a name of a dict[str, str].\n  write instead: bind the dict to a variable first')
        return self.fn('_ail_ul_urlencode', keys, vals)

    @staticmethod
    def as_str(node):
        """A number or bool written out in a urlencode dict is str()-ed as urlencode does; anything else is taken to be a str."""
        inner = node.operand if isinstance(node, ast.UnaryOp) else node
        if isinstance(inner, ast.Constant) and not isinstance(inner.value, (str, bytes)):
            return ast.Call(func=iterlower._name('str'), args=[node], keywords=[])
        return node

    # ---- the response ----------------------------------------------------------------------
    def resp_method(self, node):
        func = node.func
        attr = func.attr
        target = self.visit(copy.deepcopy(func.value))
        args = [self.visit(copy.deepcopy(a)) for a in node.args]
        if node.keywords:
            self.refuse(node, 'r.%s(...) with keyword arguments is not built. %s' % (attr, _BUILT))
        if attr == 'read':
            if len(args) == 0:
                return self.method(target, 'read', self.C(-1))
            if len(args) == 1:
                return self.method(target, 'read', args[0])
            self.refuse(node, 'r.read() takes at most one argument')
        if attr == 'close' and not args:
            return self.method(target, 'close')
        if attr == 'getcode' and not args:
            return ast.Attribute(value=target, attr='status', ctx=ast.Load())
        if attr == 'geturl' and not args:
            return ast.Attribute(value=target, attr='url', ctx=ast.Load())
        if attr == 'getheader':
            if len(args) != 2:
                self.refuse(node, 'r.getheader(name) is None when the header is missing, and there is no None str here.\n'
                                  '  write instead: r.getheader(name, "")')
            return self.method(target, 'hjoin', *args)
        self.refuse(node, 'r.%s(...) is not built. Built on a response: read(), read(n), close(), getcode(), geturl(), '
                          'getheader(name, default), headers.get(name, default), status, reason, url\n'
                          '  write instead: r.read() for the body (r.read().decode().split(chr(10)) for lines), '
                          'r.headers.get(name, "") for a header' % attr)

    def headers_method(self, node, resp, kind):
        attr = node.func.attr
        args = [self.visit(copy.deepcopy(a)) for a in node.args]
        if node.keywords or attr != 'get' or len(args) != 2:
            if attr == 'get' and len(args) == 1 and not node.keywords:
                self.refuse(node, 'headers.get(name) is None when the header is missing, and there is no None str here.\n'
                                  '  write instead: headers.get(name, "")')
            self.refuse(node, 'only headers.get(name, default) is built on the headers (and `name in headers`).\n'
                              '  write instead: headers.get("Content-Type", "")')
        if kind == 'resp':
            return self.method(self.visit(copy.deepcopy(resp)), 'hget', *args)
        return self.fn('_ail_ul_hget', self.call('_ail_ht_eh'), *args)

    def req_method(self, node):
        func = node.func
        attr = func.attr
        target = self.visit(copy.deepcopy(func.value))
        args = [self.visit(copy.deepcopy(a)) for a in node.args]
        if node.keywords:
            self.refuse(node, 'req.%s(...) with keyword arguments is not built' % attr)
        if attr in ('add_header', 'add_unredirected_header') and len(args) == 2:
            return self.method(target, attr, *args)
        if attr in ('get_method', 'get_full_url') and not args:
            return self.method(target, attr)
        if attr == 'has_header' and len(args) == 1:
            return self.method(target, 'has_header', args[0])
        if attr == 'get_header' and len(args) == 2:
            return self.method(target, 'get_header', args[0], args[1])
        if attr == 'remove_header' and len(args) == 1:
            return self.method(target, 'remove_header', args[0])
        self.refuse(node, 'req.%s(...) is not built. Built on a Request: add_header(k, v), add_unredirected_header(k, v), has_header(k), '
                          'get_header(k, default), remove_header(k), get_method(), get_full_url(), full_url, data, method' % attr)

    def visit_Attribute(self, node):
        name = self.qual(node)
        if name is not None and isinstance(node.ctx, ast.Load):
            if name.startswith('urllib.') and name.count('.') >= 2:
                self.refuse(node, '%s used here is not built. %s' % (name, _BUILT))
        if isinstance(node.ctx, ast.Load):
            if self.is_resp(node.value):
                attr = node.attr
                if attr in ('status', 'reason', 'url'):
                    return self.at(ast.Attribute(value=self.visit(node.value), attr=attr, ctx=node.ctx), node)
                if attr == 'code':
                    return self.at(ast.Attribute(value=self.visit(node.value), attr='status', ctx=node.ctx), node)
                if attr == 'msg':
                    return self.at(ast.Attribute(value=self.visit(node.value), attr='reason', ctx=node.ctx), node)
                if attr == 'headers':
                    self.refuse(node, 'r.headers is built as headers.get(name, default) and `name in r.headers`.\n'
                                      '  write instead: r.headers.get("Content-Type", "")')
                self.refuse(node, 'r.%s is not built. Built on a response: status, reason, url, headers.get(), read(), close(), '
                                  'getcode(), geturl(), getheader()' % attr)
            if self.is_req(node.value):
                if node.attr == 'full_url':
                    return self.at(ast.Attribute(value=self.visit(node.value), attr='url', ctx=node.ctx), node)
                if node.attr in ('data', 'method'):
                    return self.at(ast.Attribute(value=self.visit(node.value), attr=node.attr, ctx=node.ctx), node)
                if node.attr == 'headers':
                    self.refuse(node, 'req.headers is not built.\n  write instead: req.get_header(name, "") and req.has_header(name)')
                self.refuse(node, 'req.%s is not built. Built on a Request: add_header, has_header, get_header, remove_header, '
                                  'get_method, get_full_url, full_url, data, method' % node.attr)
        elif isinstance(node.ctx, ast.Store) and self.is_req(node.value):
            if node.attr == 'method':
                return self.at(ast.Attribute(value=self.visit(node.value), attr='method', ctx=node.ctx), node)
            self.refuse(node, 'assigning req.%s is not built.\n  write instead: build the Request with the data, url and headers you want' % node.attr)
        return self.generic_visit(node)

    def visit_For(self, node):
        if self.is_resp(node.iter):
            self.refuse(node, 'iterating over a response is not built.\n'
                              '  write instead: for line in r.read().decode().split(chr(10)):')
        return self.generic_visit(node)

    def visit_comprehension(self, node):
        if self.is_resp(node.iter):
            self.refuse(node.iter, 'iterating over a response is not built.\n'
                                   '  write instead: for line in r.read().decode().split(chr(10)):')
        return self.generic_visit(node)

    def visit_Compare(self, node):
        if len(node.ops) == 1 and isinstance(node.ops[0], (ast.In, ast.NotIn)):
            right = node.comparators[0]
            if isinstance(right, ast.Attribute) and right.attr == 'headers' and self.is_resp(right.value):
                test = self.method(self.visit(copy.deepcopy(right.value)), 'hhas', self.visit(copy.deepcopy(node.left)))
                if isinstance(node.ops[0], ast.NotIn):
                    test = ast.UnaryOp(op=ast.Not(), operand=test)
                return self.at(test, node)
        return self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load) and id(node) not in self.synth:
            if node.id in self.names and node.id not in self.user_defs:
                self.refuse(node, '%s used here is not built. %s' % (self.names[node.id], _BUILT))
            if node.id in self.mods:
                self.refuse(node, 'the module name %s used as a value is not built. %s' % (node.id, _BUILT))
        return node

    def block(self, stmts):
        out = []
        for stmt in stmts:
            result = self.visit(stmt)
            if isinstance(result, list):
                out.extend(result)
            elif result is not None:
                out.append(result)
        return out

    def visit_With(self, node):
        if not any(self.is_urlopen(item.context_expr) for item in node.items):
            return self.generic_visit(node)
        body = self.block(node.body)
        for item in reversed(node.items):
            context = item.context_expr
            if not self.is_urlopen(context):
                self.refuse(node, 'a `with` statement mixing urlopen() with another context manager.\n  write instead: nest the statements')
            call = self.visit(context)
            if item.optional_vars is None:
                name = self.fresh('w')
                target, shown = self.N(name, True), self.N(name)
            elif isinstance(item.optional_vars, ast.Name):
                target, shown = self.N(item.optional_vars.id, True), self.N(item.optional_vars.id)
            else:
                self.refuse(node, 'with urlopen(...) as %s: bind the response to a plain name.\n  write instead: with urlopen(url) as r:'
                            % type(item.optional_vars).__name__.lower())
            guarded = ast.Try(body=body, handlers=[], orelse=[], finalbody=[ast.Expr(value=self.method(shown, 'close'))])
            body = [ast.Assign(targets=[target], value=call), guarded]
        return [self.at(s, node) for s in body]

    # ---- try / except ----------------------------------------------------------------------
    _EXC = {'urllib.error.HTTPError': 'HTTPError', 'urllib.error.URLError': 'URLError'}

    def visit_ExceptHandler(self, node):
        if node.type is None:
            return self.generic_visit(node)
        types = node.type.elts if isinstance(node.type, ast.Tuple) else [node.type]
        found, elements, other = [], [], False
        for each in types:
            name = self.qual(each)
            if name in self._EXC:
                found.append(self._EXC[name])
                elements.append(self.at(self.N(self._EXC[name]), each))
            else:
                other = True
                elements.append(self.visit(each))
        if not found:
            return self.generic_visit(node)
        self.http = self.used = True
        self.exc_seen = True
        node.type = elements[0] if len(elements) == 1 else self.at(ast.Tuple(elts=elements, ctx=ast.Load()), node.type)
        if node.name:
            node.body = _ExcAttrs(self, node.name, set(found), other).apply(node.body)
        node.body = self.block(node.body)
        return node

    # ---- the driver ------------------------------------------------------------------------
    def run(self):
        self.analyse()
        self.visit(self.tree)
        for node in self.import_nodes:
            if node in self.tree.body:
                self.tree.body[self.tree.body.index(node)] = self.at(ast.Pass(), node)
        self.inject()
        ast.fix_missing_locations(self.tree)

    def inject(self):
        import filelower
        snippets = _load_prelude()
        order = []
        seen = set()

        def add(name):
            if name in seen:
                return
            seen.add(name)
            for need in snippets[name][1]:
                add(need)

        for name in sorted(self.need):
            add(name)
        statements = []
        for name in snippets['__order__']:
            if name not in seen:
                continue
            parsed = ast.parse(filelower._Lowerer.surface(snippets[name][0]))
            for each in ast.walk(parsed):
                if 'lineno' in getattr(each, '_attributes', ()):
                    each.lineno = 1
                    each.end_lineno = 1
                    each.col_offset = 0
                    each.end_col_offset = 0
                if isinstance(each, ast.Name):
                    each._ail_synth = True
            statements.extend(parsed.body)
        body = self.tree.body
        index = 0
        while index < len(body) and (
                isinstance(body[index], (ast.Import, ast.ImportFrom, ast.Pass))
                or (isinstance(body[index], ast.Expr) and isinstance(body[index].value, ast.Constant))):
            index += 1
        self.tree.body = body[:index] + statements + body[index:]


class _ExcAttrs(ast.NodeTransformer):
    """`e.code` and friends inside `except urllib.error.X as e:`, read from the last-error record of the C layer."""

    def __init__(self, low, name, found, other):
        self.low, self.name, self.found, self.other = low, name, found, other

    def apply(self, body):
        return [self.visit(s) for s in body]

    def is_exc(self, node):
        return isinstance(node, ast.Name) and node.id == self.name and isinstance(node.ctx, ast.Load)

    def msg(self, origin):
        if self.other:
            self.low.refuse(origin, 'str(e) / print(e): this handler also catches other exceptions, whose text is not the last-error record.\n'
                                    '  write instead: a handler of its own for the urllib exception')
        return self.low.at(self.low.call('_ail_ht_emsg'), origin)

    def visit_Call(self, node):
        low = self.low
        func = node.func
        if isinstance(func, ast.Name) and func.id in ('str', 'print') and func.id not in low.user_defs \
                and not any(isinstance(a, ast.Starred) for a in node.args):
            if func.id == 'str' and len(node.args) == 1 and not node.keywords and self.is_exc(node.args[0]):
                return self.msg(node)
            if func.id == 'str' and len(node.args) == 1 and not node.keywords and isinstance(node.args[0], ast.Attribute) \
                    and self.is_exc(node.args[0].value) and node.args[0].attr in ('reason', 'msg', 'url', 'filename'):
                return self.visit(node.args[0])          # e.reason is text here: str(e.reason) is e.reason
            if func.id == 'print':
                node.args = [self.msg(a) if self.is_exc(a) else self.visit(a) for a in node.args]
                node.keywords = [self.visit(k) for k in node.keywords]
                return node
        if isinstance(func, ast.Attribute):
            if self.is_exc(func.value):
                return self.method_call(node)
            if isinstance(func.value, ast.Attribute) and func.value.attr == 'headers' and self.is_exc(func.value.value):
                self.need_http(node, 'headers')
                node.args = [self.visit(a) for a in node.args]
                return low.at(low.headers_method(node, None, 'exc'), node)
        return self.generic_visit(node)

    def need_http(self, node, what):
        if 'HTTPError' not in self.found or self.other:
            self.low.refuse(node, 'e.%s: the handler has to name urllib.error.HTTPError alone (a URLError has no response).\n'
                                  '  write instead: a handler of its own, `except urllib.error.HTTPError as e:`' % what)

    def method_call(self, node):
        low = self.low
        attr = node.func.attr
        args = [self.visit(a) for a in node.args]
        if node.keywords:
            low.refuse(node, 'e.%s(...) with keyword arguments is not built' % attr)
        if attr == 'read':
            self.need_http(node, 'read()')
            return low.at(low.call('_ail_ht_read', low.call('_ail_ht_eh'), args[0] if args else low.C(-1)), node)
        if attr == 'getcode' and not args:
            self.need_http(node, 'getcode()')
            return low.at(low.call('_ail_ht_ecode'), node)
        if attr == 'geturl' and not args:
            return low.at(low.call('_ail_ht_eurl'), node)
        low.refuse(node, 'e.%s(...) is not built. Built on the exception: read(), getcode(), geturl(), '
                         'code, reason, url, msg, headers.get(name, default)\n'
                         '  write instead: e.read() for the body, e.code, e.reason' % attr)

    def visit_FormattedValue(self, node):
        if self.is_exc(node.value):
            node.value = self.msg(node.value)
            return node
        return self.generic_visit(node)

    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name) and node.value.id == self.name and isinstance(node.ctx, ast.Load):
            low = self.low
            attr = node.attr
            if self.other:
                low.refuse(node, 'e.%s: this handler also catches other exceptions, which do not have it.\n'
                                 '  write instead: a handler of its own for the urllib exception' % attr)
            if attr in ('code', 'status'):
                self.need_http(node, attr)
                return low.at(low.call('_ail_ht_ecode'), node)
            if attr in ('reason', 'msg'):
                return low.at(low.call('_ail_ht_ereason'), node)
            if attr in ('url', 'filename'):
                return low.at(low.call('_ail_ht_eurl'), node)
            if attr == 'headers':
                self.need_http(node, 'headers')
                low.refuse(node, 'e.headers is built as e.headers.get(name, default).\n  write instead: e.headers.get("Content-Type", "")')
            low.refuse(node, 'e.%s is not built. Built on the exception: code, reason, url, msg, headers.get(), read(), getcode(), geturl()\n'
                             '  write instead: print(e) for the whole message, e.code and e.reason' % attr)
        return self.generic_visit(node)

    def visit_Name(self, node):
        if self.is_exc(node):
            self.low.refuse(node, 'the exception %s used as a value is not built: use e.code, e.reason, str(e) or print(e).\n'
                                  '  write instead: print(e)' % self.name)
        return node


def rewrite_tree(tree, Unsupported, general=False):
    """Lower urllib in `tree` (in place). Returns whether the program uses it; a program that does not is untouched."""
    global ACTIVE, USED
    ACTIVE = USED = False
    lowerer = _Lowerer(tree, Unsupported, general)
    lowerer.scan()
    if not lowerer.wants():
        return False
    uses = False
    for node in ast.walk(tree):
        if isinstance(node, (ast.Name, ast.Attribute)) and lowerer.qual(node) is not None and node not in lowerer.import_nodes:
            uses = True
            break
    if not uses:
        return False
    if general:
        lowerer.refuse(tree.body[0] if tree.body else tree,
                       'urllib is built on the typed path only (bytes and the exception records are not on the general path).\n'
                       '  write instead: keep the program inside the typed subset (AIL_NO_GENERAL=1 shows what stops it)')
    if os.environ.get('AIL_TARGET'):
        lowerer.refuse(tree.body[0] if tree.body else tree,
                       'urllib.request is built for the host platform only: libcurl is linked from the build machine.\n'
                       '  write instead: build on the target, or fetch outside the program')
    lowerer.run()
    if lowerer.http:
        if not available():
            lowerer.refuse(tree.body[0] if tree.body else tree, NO_CURL_TEXT)
        ACTIVE = True
    USED = lowerer.used or lowerer.http
    return True
