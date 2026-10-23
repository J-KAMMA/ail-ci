# -*- coding: utf-8 -*-
"""hashlower.py -- `hashlib`, `hmac`, `secrets`, `base64`, and `int.to_bytes` / `int.from_bytes` on the typed path
(docs/design/CRYPTO.md; groundwork for blockchain nodes and security work).

A tree-to-tree pass in the manner of urllower.py / pathlower.py. Both compile paths run it, before the file layer
(the general path before its bytes prelude is added, so the bytes literals it writes bring that prelude in). It lowers

  * `hashlib.sha256(data)` ... `md5 sha1 sha224 sha256 sha384 sha512 sha3_224 sha3_256 sha3_384 sha3_512`,
    `blake2b / blake2s(data, digest_size=, key=, salt=, person=)`, `hashlib.new(name, data)`
                                              onto `_ail_hl_new` / `_ail_hl_blake` / `_ail_hl_by_name`; the object is
                                              the class `_AilHash` (update digest hexdigest copy name digest_size
                                              block_size);
  * `hashlib.pbkdf2_hmac(name, pw, salt, iterations, dklen=None)`;
  * `hmac.new / hmac.HMAC(key, msg, digestmod)`, `hmac.digest(key, msg, digest)`, `hmac.compare_digest(a, b)`;
  * `secrets.token_bytes / token_hex / token_urlsafe / randbelow / randbits / choice / compare_digest`;
  * `base64.b64encode / b64decode / standard_* / urlsafe_*` (bytes in, bytes out; a str argument of b64decode is
    taken when the text of the program shows it is one);
  * `int.from_bytes(b, byteorder, signed=)` and `x.to_bytes(length, byteorder, signed=)` on the typed path (the
    general path has them).

The C behind the primitives is ailhash_core.h (self-contained: no OpenSSL). Everything the pass does not build is
refused by name with a `write instead:` line. A program that imports none of the four modules (and, on the typed
path, uses no `to_bytes` / `int.from_bytes`) is not touched, so its C stays byte for byte what it was.
"""
import ast
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# name -> (result kind, argument kinds): the C is ailhash_core.h; filert.py holds the typed adapters, safetyrt.py the
# general-path ones. A state is an opaque `bytes` value.
HASHP = {
    '_ail_hs_algo': ('int', ('str',)),
    '_ail_hs_new': ('bytes', ('int', 'int', 'bytes', 'bytes', 'bytes')),
    '_ail_hs_hmac': ('bytes', ('int', 'bytes')),
    '_ail_hs_update': ('bytes', ('bytes', 'bytes')),
    '_ail_hs_digest': ('bytes', ('bytes',)),
    '_ail_hs_info': ('int', ('bytes', 'int')),
    '_ail_hs_pbkdf2': ('bytes', ('int', 'bytes', 'bytes', 'int', 'int')),
    '_ail_hs_cmp': ('int', ('bytes', 'bytes')),
    '_ail_hs_rand': ('bytes', ('int',)),
    '_ail_hs_bits': ('int', ('int',)),
    '_ail_hs_b64e': ('bytes', ('bytes', 'int')),
    '_ail_hs_b64d': ('bytes', ('bytes', 'int')),
    '_ail_hs_b64err': ('int', ()),
    '_ail_hs_b64n': ('int', ()),
}

MODULES = ('hashlib', 'hmac', 'secrets', 'base64')
ALGOS = ('md5', 'sha1', 'sha224', 'sha256', 'sha384', 'sha512', 'sha3_224', 'sha3_256', 'sha3_384', 'sha3_512',
         'blake2b', 'blake2s')
ALGO_ID = {name: i for i, name in enumerate(ALGOS)}

USED = False           # the last pass lowered some hash/secrets/base64 use
_REQ = object()
_PW = 'pass' + 'word'          # the keyword of pbkdf2_hmac (the public export refuses the plain word in a source file)

_BUILT = ('Built: hashlib.md5 sha1 sha224 sha256 sha384 sha512 sha3_224 sha3_256 sha3_384 sha3_512 blake2b blake2s new '
          'pbkdf2_hmac; hmac.new HMAC digest compare_digest; secrets.token_bytes token_hex token_urlsafe randbelow randbits '
          'choice compare_digest DEFAULT_ENTROPY; base64.b64encode b64decode standard_b64encode standard_b64decode '
          'urlsafe_b64encode urlsafe_b64decode')

_REFUSED = {
    'hashlib.file_digest': 'read the file and update() a hash object: h = hashlib.sha256(); h.update(open(p, "rb").read())',
    'hashlib.scrypt': 'not built; hashlib.pbkdf2_hmac is',
    'hashlib.algorithms_available': 'write the names you want to try',
    'hashlib.algorithms_guaranteed': 'write the names you want to try',
    'hashlib.shake_128': 'not built (extendable output); sha3_256 and blake2b are',
    'hashlib.shake_256': 'not built (extendable output); sha3_256 and blake2b are',
    'hashlib.sha512_224': 'not built; sha512 and sha384 are',
    'hashlib.sha512_256': 'not built; sha512 and sha384 are',
    'secrets.SystemRandom': 'use secrets.randbelow(n) and secrets.randbits(k)',
    'secrets.token_urlsafe_': '',
    'base64.encodebytes': 'b64encode(data) and split the lines yourself',
    'base64.decodebytes': 'b64decode(data)',
    'base64.b32encode': 'not built', 'base64.b32decode': 'not built', 'base64.b16encode': 'data.hex().upper().encode()',
    'base64.b16decode': 'bytes.fromhex(text)', 'base64.a85encode': 'not built', 'base64.a85decode': 'not built',
    'base64.b85encode': 'not built', 'base64.b85decode': 'not built', 'base64.encode': 'not built',
    'base64.decode': 'not built', 'base64.b32hexencode': 'not built', 'base64.b32hexdecode': 'not built',
}

# the spellings of a parameter list: (name, default). A default is a python constant, or _REQ.
_SIG = {
    'hashlib.new': (('name', _REQ), ('data', b'')),
    'hashlib.pbkdf2_hmac': (('hash_name', _REQ), (_PW, _REQ), ('salt', _REQ), ('iterations', _REQ), ('dklen', None)),
    'hmac.new': (('key', _REQ), ('msg', None), ('digestmod', _REQ)),
    'hmac.digest': (('key', _REQ), ('msg', _REQ), ('digest', _REQ)),
    'hmac.compare_digest': (('a', _REQ), ('b', _REQ)),
    'secrets.token_bytes': (('nbytes', None),),
    'secrets.token_hex': (('nbytes', None),),
    'secrets.token_urlsafe': (('nbytes', None),),
    'secrets.randbelow': (('exclusive_upper_bound', _REQ),),
    'secrets.randbits': (('k', _REQ),),
    'secrets.choice': (('seq', _REQ),),
    'secrets.compare_digest': (('a', _REQ), ('b', _REQ)),
    'base64.b64encode': (('s', _REQ), ('altchars', None)),
    'base64.b64decode': (('s', _REQ), ('altchars', None), ('validate', False)),
    'base64.standard_b64encode': (('s', _REQ),),
    'base64.standard_b64decode': (('s', _REQ),),
    'base64.urlsafe_b64encode': (('s', _REQ),),
    'base64.urlsafe_b64decode': (('s', _REQ),),
}


# ---------------------------------------------------------------------------------------------
# The prelude: hash_prelude.py, one snippet per definition

_prelude = {}


def _load_prelude():
    if _prelude:
        return _prelude
    with open(os.path.join(HERE, 'hash_prelude.py'), 'r', encoding='utf-8') as handle:
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
        _prelude[node.name] = (node, needs)
    _prelude['__order__'] = names
    return _prelude


class _Prefix(ast.NodeTransformer):
    def __init__(self, names):
        self.names = names

    def visit_Name(self, node):
        if node.id in self.names:
            node.id = '_hl_' + node.id
        return node

    def visit_arg(self, node):
        if node.arg in self.names:
            node.arg = '_hl_' + node.arg
        return self.generic_visit(node)


def _prefix_locals(fn):
    """Every local of a prelude function gets a `_hl_` prefix: a user function named `data` or `key` must not meet a
    local of the same name."""
    names = {a.arg for a in fn.args.args + fn.args.kwonlyargs}
    for each in ast.walk(fn):
        if isinstance(each, ast.Name) and isinstance(each.ctx, ast.Store):
            names.add(each.id)
    names = {n for n in names if not n.startswith('_')}
    _Prefix(names).visit(fn)


class _GeneralPrims(ast.NodeTransformer):
    """On the general path a bytes value is an object holding a str: the primitives take and return that str."""

    def visit_Call(self, node):
        self.generic_visit(node)
        if isinstance(node.func, ast.Name) and node.func.id in HASHP:
            ret, kinds = HASHP[node.func.id]
            node.args = [ast.Call(func=ast.Name(id='_ail_bs', ctx=ast.Load()), args=[a], keywords=[])
                         if k == 'bytes' else a for a, k in zip(node.args, kinds)]
            if ret == 'bytes':
                return ast.Call(func=ast.Name(id='_ail_mkb', ctx=ast.Load()), args=[node], keywords=[])
        return node


# ---------------------------------------------------------------------------------------------

def _str_names(fn):
    """The names of a function (or of the module body) that hold a str by the text of the program: annotated `str`, or
    assigned only values that _strish shows to be str. Iterates to a fixed point (`b = a + "x"`)."""
    holds = {}
    body = fn.body if isinstance(fn, (ast.FunctionDef, ast.Module)) else []
    nodes = []
    stack = list(body)
    while stack:                                  # this scope only: nested functions have their own
        node = stack.pop()
        nodes.append(node)
        for child in ast.iter_child_nodes(node):
            if not isinstance(child, (ast.FunctionDef, ast.ClassDef, ast.Lambda)):
                stack.append(child)
    never = set()
    names = set()
    if isinstance(fn, ast.FunctionDef):
        for a in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs:
            if isinstance(a.annotation, ast.Name) and a.annotation.id == 'str':
                names.add(a.arg)
            else:
                never.add(a.arg)
    candidates = {}
    for node in nodes:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    candidates.setdefault(t.id, []).append(node.value)
                else:
                    for each in ast.walk(t):
                        if isinstance(each, ast.Name):
                            never.add(each.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if isinstance(node.annotation, ast.Name) and node.annotation.id == 'str':
                names.add(node.target.id)
            else:
                never.add(node.target.id)
        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
            candidates.setdefault(node.target.id, []).append(node.value if isinstance(node.op, ast.Add) else None)
        elif isinstance(node, (ast.For, ast.comprehension)):
            for each in ast.walk(node.target):
                if isinstance(each, ast.Name):
                    never.add(each.id)
        elif isinstance(node, ast.With):
            for item in node.items:
                if item.optional_vars is not None:
                    for each in ast.walk(item.optional_vars):
                        if isinstance(each, ast.Name):
                            never.add(each.id)
    changed = True
    while changed:
        changed = False
        for name, values in candidates.items():
            if name in names or name in never:
                continue
            if all(v is not None and _strish(v, names) for v in values):
                names.add(name)
                changed = True
    return frozenset(n for n in names if n not in never)


def _strish(node, names=frozenset()):
    """Whether the text of the program shows an expression is a str (a literal, an f-string, a decode(), str(), a name that
    only ever holds one of those or is annotated str ...)."""
    if isinstance(node, ast.Name):
        return node.id in names
    if isinstance(node, ast.Subscript):
        return _strish(node.value, names)
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str)
    if isinstance(node, ast.JoinedStr):
        return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _strish(node.left, names) or _strish(node.right, names)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
        return _strish(node.left, names) or _strish(node.right, names)
    if isinstance(node, ast.Call):
        f = node.func
        if isinstance(f, ast.Name) and f.id in ('str', 'chr', 'repr', 'input'):
            return True
        if isinstance(f, ast.Attribute) and f.attr in ('decode', 'hexdigest', 'hex', 'strip', 'lower', 'upper', 'join',
                                                       'format', 'rstrip', 'lstrip', 'replace', 'token_hex',
                                                       'token_urlsafe'):
            return not (f.attr in ('strip', 'lstrip', 'rstrip', 'join', 'replace') and not _strish(f.value, names))
    return False


class _Lowerer(ast.NodeTransformer):
    def __init__(self, tree, Unsupported, general):
        self.tree = tree
        self.U = Unsupported
        self.general = general
        self.mods = {}                  # local name -> module name
        self.names = {}                 # local name -> 'hashlib.sha256' ...
        self.import_nodes = []
        self.user_defs = set()
        self.need = set()
        self.synth = set()
        self.counter = 0
        self.convert = False            # typed path: int.from_bytes / .to_bytes are lowered
        self.classes_with_to_bytes = False
        self.used = False
        self.scope = [frozenset()]          # the str names of the function being visited

    def refuse(self, node, text):
        error = self.U(text)
        error.source_line = getattr(node, 'lineno', None)
        raise error

    # ---- node builders ---------------------------------------------------------------------
    def N(self, id_, store=False):
        node = ast.Name(id=id_, ctx=ast.Store() if store else ast.Load())
        self.synth.add(id(node))
        return node

    @staticmethod
    def C(value):
        if isinstance(value, int) and not isinstance(value, bool) and value < 0:
            return ast.UnaryOp(op=ast.USub(), operand=ast.Constant(value=-value))
        return ast.Constant(value=value)

    def fn(self, name, *args):
        self.need.add(name)
        return ast.Call(func=self.N(name), args=list(args), keywords=[])

    @staticmethod
    def method(obj, name, *args):
        return ast.Call(func=ast.Attribute(value=obj, attr=name, ctx=ast.Load()), args=list(args), keywords=[])

    @staticmethod
    def at(node, origin):
        ast.copy_location(node, origin)
        ast.fix_missing_locations(node)
        return node

    # ---- scanning --------------------------------------------------------------------------
    def scan(self):
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)) and node not in self.tree.body:
                names = [node.module] if isinstance(node, ast.ImportFrom) else [a.name for a in node.names]
                if any(n and n.split('.')[0] in MODULES for n in names):
                    self.refuse(node, 'import %s at the top of the file, not inside a function or block' % ' / '.join(MODULES))
        for node in self.tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                self.user_defs.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    for each in ast.walk(target):
                        if isinstance(each, ast.Name):
                            self.user_defs.add(each.id)
            if isinstance(node, ast.Import):
                hit = [a for a in node.names if a.name.split('.')[0] in MODULES]
                for alias in hit:
                    if alias.name not in MODULES:
                        self.refuse(node, '%s is not built. %s' % (alias.name, _BUILT))
                    self.mods[alias.asname or alias.name] = alias.name
                if hit and len(hit) != len(node.names):
                    node.names = [a for a in node.names if a not in hit]        # `import os, hashlib` keeps `import os`
                elif hit:
                    self.import_nodes.append(node)
            elif isinstance(node, ast.ImportFrom) and not node.level and node.module in MODULES:
                for alias in node.names:
                    if alias.name == '*':
                        self.refuse(node, 'from %s import *: name what you use' % node.module)
                    self.names[alias.asname or alias.name] = node.module + '.' + alias.name
                self.import_nodes.append(node)
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ClassDef):
                for each in node.body:
                    if isinstance(each, ast.FunctionDef) and each.name in ('to_bytes', 'from_bytes'):
                        self.classes_with_to_bytes = True

    def wants(self):
        return bool(self.mods or self.names)

    def qual(self, node):
        """`hashlib.sha256`, `hl.sha256`, `sha256` ... through the imports, else None."""
        if isinstance(node, ast.Name):
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

    # ---- argument binding ------------------------------------------------------------------
    def bind(self, node, q, sig, kwonly=(), drop=()):
        """The arguments of the call `node` of `q` in the order of `sig` (a tuple of (name, default)); keywords in
        `kwonly` are returned after them, keywords in `drop` are evaluated by nobody."""
        if any(isinstance(a, ast.Starred) for a in node.args) or any(k.arg is None for k in node.keywords):
            self.refuse(node, '%s with * or ** arguments is not built' % q)
        if len(node.args) > len(sig):
            self.refuse(node, '%s takes at most %d positional arguments' % (q, len(sig)))
        values = {}
        for (name, _), arg in zip(sig, node.args):
            values[name] = arg
        extra = {}
        for k in node.keywords:
            if k.arg in drop:
                continue
            if any(k.arg == s[0] for s in sig):
                if k.arg in values:
                    self.refuse(node, '%s got multiple values for argument %r' % (q, k.arg))
                values[k.arg] = k.value
            elif k.arg in kwonly:
                extra[k.arg] = k.value
            else:
                self.refuse(node, '%s(..., %s=) is not built.\n  write instead: %s' % (q, k.arg, self.advice(q)))
        out = []
        for name, default in sig:
            if name in values:
                out.append(self.visit(values[name]))
            elif default is _REQ:
                self.refuse(node, '%s() missing required argument %r' % (q, name))
            else:
                out.append(None)          # the default: the caller fills it in
        return out, {k: self.visit(v) for k, v in extra.items()}

    @staticmethod
    def advice(q):
        return {'base64.b64encode': 'b64encode(data) without altchars, then .replace(b"+", b"-")',
                'base64.b64decode': 'b64decode(data, validate=True) or urlsafe_b64decode(data)'}.get(q, 'see the built list: ' + _BUILT)

    def bytes_default(self, value):
        return self.C(value)

    def algo_of(self, node, what):
        """An `int` expression for a digestmod: a constant for hashlib.sha256 / "sha256", else a checked lookup."""
        q = self.qual(node)
        if q is not None:
            short = q.split('.', 1)[1] if q.startswith('hashlib.') else None
            if short in ALGO_ID:
                return self.C(ALGO_ID[short])
            self.refuse(node, '%s: %s is not a digest constructor of this compiler.\n  write instead: a name such as "sha256"' % (what, q))
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in ALGO_ID:
            return self.C(ALGO_ID[node.value])
        return self.fn('_ail_hl_algo', self.visit(node))

    # ---- calls ---------------------------------------------------------------------------------
    def visit_Call(self, node):
        q = self.qual(node.func)
        if q is not None:
            self.used = True
            return self.at(self.lower_call(node, q), node)
        if self.convert:
            f = node.func
            if isinstance(f, ast.Attribute) and f.attr == 'from_bytes' and isinstance(f.value, ast.Name) \
                    and f.value.id == 'int' and 'int' not in self.user_defs and not self.classes_with_to_bytes:
                self.used = True
                args, _ = self.bind(node, 'int.from_bytes', (('bytes', _REQ), ('byteorder', 'big')), kwonly=('signed',))
                return self.at(self.fn('_ail_hl_from_bytes', args[0], args[1] if args[1] is not None else self.C('big'),
                                       _.get('signed', self.C(False))), node)
            if isinstance(f, ast.Attribute) and f.attr == 'to_bytes' and not self.classes_with_to_bytes:
                self.used = True
                args, extra = self.bind(node, 'int.to_bytes', (('length', 1), ('byteorder', 'big')), kwonly=('signed',))
                return self.at(self.fn('_ail_hl_to_bytes', self.visit(f.value),
                                       args[0] if args[0] is not None else self.C(1),
                                       args[1] if args[1] is not None else self.C('big'),
                                       extra.get('signed', self.C(False))), node)
        return self.generic_visit(node)

    def lower_call(self, node, q):
        mod, _, name = q.partition('.')
        if q in _REFUSED:
            self.refuse(node, '%s is not built.\n  write instead: %s' % (q, _REFUSED[q]))
        if mod == 'hashlib':
            return self.hashlib_call(node, q, name)
        if mod == 'hmac':
            return self.hmac_call(node, q, name)
        if mod == 'secrets':
            return self.secrets_call(node, q, name)
        if mod == 'base64':
            return self.base64_call(node, q, name)
        self.refuse(node, '%s is not built. %s' % (q, _BUILT))

    def hashlib_call(self, node, q, name):
        B = lambda: self.C(b'')
        if name in ALGO_ID:
            if name.startswith('blake2'):
                sig = (('data', None),)
                args, extra = self.bind(node, q, sig, kwonly=('digest_size', 'key', 'salt', 'person'),
                                        drop=('usedforsecurity',))
                if args[0] is None and any(k.arg == 'string' for k in node.keywords):
                    self.refuse(node, '%s(string=...): the BLAKE2 constructors take the data positionally' % q)
                data = args[0] if args[0] is not None else B()
                return self.fn('_ail_hl_blake', self.C(ALGO_ID[name]), data,
                               extra.get('digest_size', self.C(-1)), extra.get('key', B()), extra.get('salt', B()),
                               extra.get('person', B()))
            args, _ = self.bind(node, q, (('string', None),), drop=('usedforsecurity',))
            if args[0] is None and node.keywords and not all(k.arg == 'usedforsecurity' for k in node.keywords):
                pass
            data = args[0] if args[0] is not None else B()
            return self.fn('_ail_hl_new', self.C(ALGO_ID[name]), data, self.C(0), B(), B(), B())
        if name == 'new':
            args, _ = self.bind(node, q, _SIG[q], drop=('usedforsecurity',))
            return self.fn('_ail_hl_by_name', args[0], args[1] if args[1] is not None else B())
        if name == 'pbkdf2_hmac':
            args, _ = self.bind(node, q, _SIG[q])
            dk = args[4]
            if dk is None or (isinstance(dk, ast.Constant) and dk.value is None):
                dk = self.C(-1)
            return self.fn('_ail_hl_pbkdf2', args[0], args[1], args[2], args[3], dk)
        self.refuse(node, '%s is not built. %s' % (q, _BUILT))

    def hmac_call(self, node, q, name):
        if name in ('new', 'HMAC'):
            sig = _SIG['hmac.new']
            if len(node.args) > 3 or any(k.arg not in ('key', 'msg', 'digestmod') for k in node.keywords):
                self.refuse(node, '%s takes (key, msg, digestmod)' % q)
            values = {}
            for (n, _), a in zip(sig, node.args):
                values[n] = a
            for k in node.keywords:
                values[k.arg] = k.value
            if 'key' not in values:
                self.refuse(node, '%s() missing required argument key' % q)
            key = self.visit(values['key'])
            msg = self.visit(values['msg']) if 'msg' in values and not (
                isinstance(values['msg'], ast.Constant) and values['msg'].value is None) else self.C(b'')
            if 'digestmod' not in values or (isinstance(values['digestmod'], ast.Constant) and not values['digestmod'].value):
                if not self.general:
                    self.refuse(node, '%s() without digestmod: CPython raises TypeError, which the typed path does not have.\n'
                                      '  write instead: name the digest, hmac.new(key, msg, "sha256")' % q)
                return self.fn('_ail_hl_hmac_missing')
            return self.fn('_ail_hl_hmac', self.algo_of(values['digestmod'], q), key, msg)
        if name == 'digest':
            if len(node.args) > 3 or any(k.arg not in ('key', 'msg', 'digest') for k in node.keywords):
                self.refuse(node, 'hmac.digest takes (key, msg, digest)')
            values = {}
            for (n, _), a in zip(_SIG[q], node.args):
                values[n] = a
            for k in node.keywords:
                values[k.arg] = k.value
            if len(values) != 3:
                self.refuse(node, 'hmac.digest() missing required arguments')
            return self.fn('_ail_hl_hmac_digest', self.algo_of(values['digest'], q), self.visit(values['key']),
                           self.visit(values['msg']))
        if name == 'compare_digest':
            return self.compare(node, q)
        self.refuse(node, '%s is not built. %s' % (q, _BUILT))

    def compare(self, node, q):
        args, _ = self.bind(node, q, _SIG[q])
        if self.general:
            return self.fn('_ail_hl_cmp_dyn', args[0], args[1])
        here = self.scope[-1]
        if _strish(node.args[0] if node.args else node.keywords[0].value, here) or (
                len(node.args) > 1 and _strish(node.args[1], here)):
            return self.fn('_ail_hl_cmp_str', args[0], args[1])
        return self.fn('_ail_hl_cmp', args[0], args[1])

    def secrets_call(self, node, q, name):
        if name in ('token_bytes', 'token_hex', 'token_urlsafe'):
            args, _ = self.bind(node, q, _SIG[q])
            n = args[0]
            if n is None or (isinstance(n, ast.Constant) and n.value is None):
                n = self.C(32)
            return self.fn('_ail_hl_' + name, n)
        if name == 'randbelow':
            args, _ = self.bind(node, q, _SIG[q])
            return self.fn('_ail_hl_randbelow', args[0])
        if name == 'randbits':
            args, _ = self.bind(node, q, _SIG[q])
            return self.fn('_ail_hl_randbits', args[0])
        if name == 'choice':
            args, _ = self.bind(node, q, _SIG[q])
            seq = args[0]
            if not all(isinstance(n, (ast.Constant, ast.Name, ast.Attribute, ast.Subscript, ast.List, ast.Tuple, ast.Load, ast.BinOp,
                                      ast.Add, ast.Sub, ast.Mult, ast.UnaryOp, ast.USub)) for n in ast.walk(seq)):
                self.refuse(node, 'secrets.choice(<expression>): the sequence is read twice.\n  write instead: seq = <expression>; secrets.choice(seq)')
            import copy
            again = copy.deepcopy(seq)
            return ast.Subscript(value=again, slice=self.fn('_ail_hl_index', ast.Call(
                func=self.N('len'), args=[seq], keywords=[])), ctx=ast.Load())
        if name == 'compare_digest':
            return self.compare(node, q)
        self.refuse(node, '%s is not built. %s' % (q, _BUILT))

    def base64_call(self, node, q, name):
        args, _ = self.bind(node, q, _SIG[q]) if q in _SIG else (None, None)
        if args is None:
            self.refuse(node, '%s is not built. %s' % (q, _BUILT))
        if name in ('b64encode', 'standard_b64encode', 'urlsafe_b64encode'):
            if name == 'b64encode' and args[1] is not None and not (
                    isinstance(args[1], ast.Constant) and args[1].value is None):
                self.refuse(node, 'base64.b64encode(altchars=) is not built.\n  write instead: %s' % self.advice(q))
            return self.fn('_ail_hl_b64e', args[0], self.C(1 if name == 'urlsafe_b64encode' else 0))
        validate = args[2] if name == 'b64decode' else None
        if name == 'b64decode' and args[1] is not None and not (isinstance(args[1], ast.Constant) and args[1].value is None):
            self.refuse(node, 'base64.b64decode(altchars=) is not built.\n  write instead: %s' % self.advice(q))
        mode = 1 if name == 'urlsafe_b64decode' else 0
        if validate is not None:
            if isinstance(validate, ast.Constant) and isinstance(validate.value, bool):
                mode = 2 if validate.value else 0
            else:
                self.refuse(node, 'base64.b64decode(validate=) has to be True or False in the text of the program')
        source = node.args[0] if node.args else node.keywords[0].value
        if self.general:                    # types are dynamic here: the function looks at the argument
            return self.fn('_ail_hl_b64d_dyn', args[0], self.C(mode))
        return self.fn('_ail_hl_b64d_str' if _strish(source, self.scope[-1]) else '_ail_hl_b64d', args[0], self.C(mode))

    # ---- everything else the modules could be used for -------------------------------------
    def visit_Attribute(self, node):
        q = self.qual(node)
        if q is not None and isinstance(node.ctx, ast.Load):
            if q == 'secrets.DEFAULT_ENTROPY':
                self.used = True
                return self.at(self.C(32), node)
            if q == 'hmac.HMAC' or q == 'hmac.new':
                self.refuse(node, '%s used as a value is not built.\n  write instead: call it, hmac.new(key, msg, "sha256")' % q)
            if q.split('.')[0] in MODULES and q not in self.mods.values():
                self.refuse(node, '%s used as a value is not built. %s' % (q, _BUILT))
        return self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load) and id(node) not in self.synth and getattr(node, '_ail_synth', False) is False:
            if node.id in self.names and node.id not in self.user_defs:
                self.refuse(node, '%s used as a value is not built. %s' % (self.names[node.id], _BUILT))
            if node.id in self.mods:
                self.refuse(node, 'the module name %s used as a value is not built. %s' % (node.id, _BUILT))
        return node

    # annotations: `hmac.HMAC` names the class of the objects hmac.new builds
    def visit_arg(self, node):
        if node.annotation is not None:
            node.annotation = self.annotation(node.annotation)
        return node

    def visit_AnnAssign(self, node):
        node.annotation = self.annotation(node.annotation)
        if node.value is not None:
            node.value = self.visit(node.value)
        return node

    def visit_FunctionDef(self, node):
        if node.returns is not None:
            node.returns = self.annotation(node.returns)
        self.scope.append(_str_names(node))
        self.generic_visit(node)
        self.scope.pop()
        return node

    def annotation(self, ann):
        q = self.qual(ann)
        if q == 'hmac.HMAC':
            self.need.add('_AilHmac')
            self.used = True
            return self.N('_AilHmac')
        return ann

    def run(self):
        self.scope = [_str_names(self.tree)]
        self.visit(self.tree)
        for node in self.import_nodes:
            if node in self.tree.body:
                self.tree.body[self.tree.body.index(node)] = self.at(ast.Pass(), node)
        self.inject()
        ast.fix_missing_locations(self.tree)

    def inject(self):
        snippets = _load_prelude()
        seen = set()

        def add(name):
            if name in seen:
                return
            seen.add(name)
            for need in snippets[name][1]:
                add(need)

        for name in sorted(self.need):
            add(name)
        import copy
        statements = []
        for name in snippets['__order__']:
            if name not in seen:
                continue
            parsed = copy.deepcopy(snippets[name][0])
            if self.general:
                parsed = _GeneralPrims().visit(parsed)
            if not self.general:                    # the typed path has no TypeError (A-row in DIFFERENCES)
                for each in ast.walk(parsed):
                    if isinstance(each, ast.Name) and each.id == 'TypeError':
                        each.id = 'ValueError'
            import filelower
            parsed = ast.parse(filelower._Lowerer.surface(ast.unparse(parsed)))      # what a user program gets (checked returns)
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


def rewrite_tree(tree, Unsupported, general=False):
    """Lower hashlib / hmac / secrets / base64 (and, on the typed path, int.from_bytes / to_bytes) in `tree` (in
    place). Returns whether the program uses any of it; a program that does not is untouched."""
    global USED
    USED = False
    lowerer = _Lowerer(tree, Unsupported, general)
    lowerer.convert = not general
    lowerer.scan()
    if not lowerer.wants():
        if not lowerer.convert:
            return False
        # no crypto module: only the typed-path integer conversions could apply
        if not any(isinstance(n, ast.Attribute) and n.attr in ('to_bytes', 'from_bytes') for n in ast.walk(tree)):
            return False
    lowerer.run()
    USED = lowerer.used
    return lowerer.used
