# -*- coding: utf-8 -*-
"""socklib.py -- ffsock1: `import socket` on POSIX, blocking TCP over AF_INET / AF_INET6.

A tree-to-tree pass in the manner of proclib.py, run by both compile paths just before the file
pass. It lowers the Python `socket` surface onto

  * the primitives of `SOCKS` (their C is ailsock_core.h; sockrt.py holds the adapters, one set
    for the typed runtime and one for the general runtime);
  * a tiny prelude of ordinary Python (`_ail_sock_*`) that names the constants, converts the
    payload between bytes and the latin-1 text the general path can carry, and opens a connection
    or a listening server the way create_connection / create_server do.

A socket is an int handle (CPython's object identity is not part of the surface). `with` closes
it on every way out. Everything the pass does not build is refused by name with a
`write instead:` line. A program that does not import socket is not touched, so its C stays byte
for byte what it was. `--target windows` refuses the import by name (Winsock is a later job).
"""
import ast
import copy

import iterlower
import sockrt

ACTIVE = False

SOCKS = {
    '_ail_sp_sock_new': ('int', ('int', 'int')),
    '_ail_sp_sock_bind': ('int', ('int', 'str', 'int')),
    '_ail_sp_sock_listen': ('int', ('int', 'int')),
    '_ail_sp_sock_accept': ('int', ('int',)),
    '_ail_sp_sock_connect': ('int', ('int', 'str', 'int')),
    '_ail_sp_sock_send': ('int', ('int', 'str')),
    '_ail_sp_sock_sendall': ('int', ('int', 'str')),
    '_ail_sp_sock_recv': ('str', ('int', 'int')),
    '_ail_sp_sock_sendb': ('int', ('int', 'bytes')),
    '_ail_sp_sock_sendallb': ('int', ('int', 'bytes')),
    '_ail_sp_sock_recvb': ('bytes', ('int', 'int')),
    '_ail_sp_sock_close': ('int', ('int',)),
    '_ail_sp_sock_shutdown': ('int', ('int', 'int')),
    '_ail_sp_sock_settimeout': ('int', ('int', 'int')),
    '_ail_sp_sock_gettimeout': ('int', ('int',)),
    '_ail_sp_sock_addr_count': ('int', ('int',)),
    '_ail_sp_sock_setsockopt': ('int', ('int', 'int', 'int', 'int')),
    '_ail_sp_sock_local_host': ('str', ('int',)),
    '_ail_sp_sock_local_port': ('int', ('int',)),
    '_ail_sp_sock_peer_host': ('str', ('int',)),
    '_ail_sp_sock_peer_port': ('int', ('int',)),
    '_ail_sp_sock_gethostname': ('str', ()),
    '_ail_sp_sock_gethostbyname': ('str', ('str',)),
}

CONSTS = {
    'socket.AF_INET': 2, 'socket.AF_INET6': 10, 'socket.SOCK_STREAM': 1,
    'socket.SOL_SOCKET': 1, 'socket.SO_REUSEADDR': 2, 'socket.IPPROTO_TCP': 6,
    'socket.TCP_NODELAY': 1, 'socket.SHUT_RD': 0, 'socket.SHUT_WR': 1, 'socket.SHUT_RDWR': 2,
}
_ALIASES = {'socket.timeout': 'TimeoutError', 'socket.error': 'OSError'}
_FUNCS = {'socket.socket', 'socket.create_connection', 'socket.create_server',
          'socket.gethostname', 'socket.gethostbyname'}
# Calls that can never produce a socket: a receiver built by one of these is not lowered as a socket.
_NON_SOCKET_CALLS = {
    'int', 'float', 'str', 'bool', 'bytes', 'bytearray', 'list', 'dict', 'set', 'frozenset',
    'tuple', 'range', 'open', 'len', 'repr', 'abs', 'min', 'max', 'sum', 'sorted', 'reversed',
    'enumerate', 'zip', 'map', 'filter', 'object', 'super', 'print', 'input', 'format', 'chr',
    'ord', 'hex', 'oct', 'bin', 'round', 'divmod', 'pow', 'isinstance', 'type', 'id', 'hash',
    'iter', 'next',
}
_NON_SOCKET_EXPRS = (ast.Constant, ast.List, ast.Dict, ast.Set, ast.Tuple, ast.JoinedStr,
                     ast.BinOp, ast.BoolOp, ast.Compare, ast.UnaryOp, ast.ListComp,
                     ast.DictComp, ast.SetComp, ast.GeneratorExp, ast.Lambda)
_BUILT = ('Built: socket(AF_INET|AF_INET6, SOCK_STREAM), connect, bind, listen, accept, send, '
          'sendall, recv, close, shutdown, settimeout, gettimeout, setsockopt(SO_REUSEADDR|TCP_NODELAY), '
          'getsockname, getpeername, create_connection, create_server, gethostname, gethostbyname')
_USE = ('use what is built: ' + _BUILT[len('Built: '):])

# Socket methods the pass knows about but does not build: each is refused by name with a way out.
_REFUSED_METHODS = {
    'sendfile': 'data = open(path, "rb").read(n)\ns.sendall(data)',
    'sendto': 's.sendall(data)',
    'recvfrom': 'data = s.recv(n)',
    'recvmsg': 'data = s.recv(n)',
    'sendmsg': 's.sendall(data)',
    'makefile': 'data = s.recv(n)',
    'dup': 'open a second socket and connect it to the same address',
    'fileno': 'a socket is already an int handle in a compiled program',
    'detach': 'a socket is already an int handle in a compiled program',
    'setblocking': 's.settimeout(None) or s.settimeout(seconds)',
    'getblocking': 's.gettimeout() is not None',
    'set_inheritable': 'nothing: handles are not inherited here',
    'get_inheritable': 'nothing: handles are not inherited here',
}

_PRELUDE = '''
AF_INET = 2
AF_INET6 = 10
SOCK_STREAM = 1
SOL_SOCKET = 1
SO_REUSEADDR = 2
IPPROTO_TCP = 6
TCP_NODELAY = 1
SHUT_RD = 0
SHUT_WR = 1
SHUT_RDWR = 2


def _ail_sock_new(family: int, kind: int) -> int:
    return _ail_sp_sock_new(family, kind)


def _ail_sock_bind(s: int, host: str, port: int) -> None:
    _ail_sp_sock_bind(s, host, port)


def _ail_sock_listen(s: int, backlog: int) -> None:
    _ail_sp_sock_listen(s, backlog)


def _ail_sock_connect(s: int, host: str, port: int) -> None:
    _ail_sp_sock_connect(s, host, port)


#SPLICE#
def _ail_sock_close(s: int) -> None:
    _ail_sp_sock_close(s)


def _ail_sock_shutdown(s: int, how: int) -> None:
    _ail_sp_sock_shutdown(s, how)


def _ail_sock_settimeout(s: int, seconds: float) -> None:
    if seconds < 0.0:
        raise ValueError("Timeout value out of range")
    _ail_sp_sock_settimeout(s, int(seconds * 1000000.0))


def _ail_sock_settimeout_none(s: int) -> None:
    _ail_sp_sock_settimeout(s, -1)


class _AilSockTimeout:
    def __init__(self, seconds: float) -> None:
        self.seconds = seconds

    def __str__(self) -> str:
        return str(self.seconds)

    def __add__(self, other: float) -> float:
        return self.seconds + other

    def __lt__(self, other: float) -> bool:
        return self.seconds < other

    def __gt__(self, other: float) -> bool:
        return self.seconds > other

    def __le__(self, other: float) -> bool:
        return self.seconds <= other

    def __ge__(self, other: float) -> bool:
        return self.seconds >= other

    def __eq__(self, other: float) -> bool:
        return self.seconds == other


def _ail_sock_gettimeout(s: int) -> _AilSockTimeout | None:
    us: int = _ail_sp_sock_gettimeout(s)
    if us < 0:
        return None
    return _AilSockTimeout(float(us) / 1000000.0)


def _ail_sock_gettimeout_float(s: int) -> float:
    us: int = _ail_sp_sock_gettimeout(s)
    return float(us) / 1000000.0


def _ail_sock_unpack(s: int, want: int) -> None:
    got: int = _ail_sp_sock_addr_count(s)
    if got > want:
        raise ValueError("too many values to unpack")
    if got < want:
        raise ValueError("not enough values to unpack")


def _ail_sock_setsockopt(s: int, level: int, opt: int, value: int) -> None:
    _ail_sp_sock_setsockopt(s, level, opt, value)


def _ail_sock_create_connection(host: str, port: int, timeout: float, has_timeout: bool) -> int:
    family: int = AF_INET
    if ':' in host:
        family = AF_INET6
    s: int = _ail_sp_sock_new(family, SOCK_STREAM)
    if has_timeout:
        _ail_sock_settimeout(s, timeout)
    _ail_sock_connect(s, host, port)
    return s


def _ail_sock_create_server(host: str, port: int, backlog: int) -> int:
    family: int = AF_INET
    if ':' in host:
        family = AF_INET6
    s: int = _ail_sp_sock_new(family, SOCK_STREAM)
    _ail_sp_sock_setsockopt(s, SOL_SOCKET, SO_REUSEADDR, 1)
    _ail_sock_bind(s, host, port)
    _ail_sock_listen(s, backlog)
    return s
'''

# The typed path has a real bytes type and its primitives carry the payload as bytes; the general
# path has no bytes, so there the payload travels as a latin-1 str (one char per octet).
_IO_TYPED = '''
def _ail_sock_peer(conn: int) -> tuple[str, int]:
    host: str = _ail_sp_sock_peer_host(conn)
    port: int = _ail_sp_sock_peer_port(conn)
    return (host, port)


def _ail_sock_send(s: int, data: bytes) -> int:
    return _ail_sp_sock_sendb(s, data)


def _ail_sock_sendall(s: int, data: bytes) -> None:
    _ail_sp_sock_sendallb(s, data)


def _ail_sock_recv(s: int, n: int) -> bytes:
    return _ail_sp_sock_recvb(s, n)


def _ail_sock_recv_len(s: int, n: int) -> int:
    data: bytes = _ail_sp_sock_recvb(s, n)
    return len(data)
'''

_IO_GENERAL_BYTES = '''
def _ail_sock_bytes_text(data: bytes) -> str:
    return data.decode('latin-1')


def _ail_sock_text_bytes(text: str) -> bytes:
    known: str = str(text)
    return bytes(known, 'latin-1')


def _ail_sock_send(s: int, data: bytes) -> int:
    return _ail_sp_sock_send(s, _ail_sock_bytes_text(data))


def _ail_sock_sendall(s: int, data: bytes) -> None:
    _ail_sp_sock_sendall(s, _ail_sock_bytes_text(data))


def _ail_sock_recv(s: int, n: int) -> bytes:
    return _ail_sock_text_bytes(_ail_sp_sock_recv(s, n))


def _ail_sock_recv_len(s: int, n: int) -> int:
    data: bytes = _ail_sock_text_bytes(_ail_sp_sock_recv(s, n))
    return len(data)
'''

# A general-path program with no bytes literal has no bytes class at all, so the socket prelude
# carries the payload as the latin-1 text the general path already uses (one char per octet).
_IO_GENERAL_STR = '''
def _ail_sock_send(s: int, data: str) -> int:
    return _ail_sp_sock_send(s, data)


def _ail_sock_sendall(s: int, data: str) -> None:
    _ail_sp_sock_sendall(s, data)


def _ail_sock_recv(s: int, n: int) -> str:
    return _ail_sp_sock_recv(s, n)


def _ail_sock_recv_len(s: int, n: int) -> int:
    data: str = _ail_sp_sock_recv(s, n)
    return len(data)
'''


class _Lowerer(ast.NodeTransformer):
    def __init__(self, tree, Unsupported, general=False):
        self.tree = tree
        self.U = Unsupported
        self.general = general
        self.mods = {}
        self.names = {}
        self.import_nodes = []
        self.user_defs = set()
        self.used = False
        self.synth = set()
        self.sock_names = set()
        self.non_sock_names = set()
        self.class_names = set()
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

    def call(self, func, *args):
        if isinstance(func, str):
            func = self.N(func)
        return ast.Call(func=func, args=list(args), keywords=[])

    @staticmethod
    def at(node, origin):
        ast.copy_location(node, origin)
        ast.fix_missing_locations(node)
        return node

    @staticmethod
    def load(node):
        node = copy.deepcopy(node)
        for each in ast.walk(node):
            if isinstance(each, ast.Name):
                each.ctx = ast.Load()
        return node

    def tmp(self, stem):
        self.counter += 1
        return '_ail_%s%d' % (stem, self.counter)

    # ---- scanning --------------------------------------------------------------------------
    def scan(self):
        for node in self.tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == 'socket':
                        self.mods[alias.asname or 'socket'] = 'socket'
                if any(a.name == 'socket' for a in node.names):
                    if any(a.name != 'socket' for a in node.names):
                        self.refuse(node, 'import socket together with other modules on one line: write one import per line')
                    self.import_nodes.append(node)
            elif isinstance(node, ast.ImportFrom) and not node.level and node.module == 'socket':
                for alias in node.names:
                    if alias.name == '*':
                        self.refuse(node, 'from socket import *: name what you use')
                    self.names[alias.asname or alias.name] = 'socket.' + alias.name
                self.import_nodes.append(node)
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                self.user_defs.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    for each in ast.walk(target):
                        if isinstance(each, ast.Name):
                            self.user_defs.add(each.id)
        self.classify()

    def expr_kind(self, value, kinds):
        """`sock`, `nonsock` or `unknown`: what a value assigned to a plain name can be."""
        if isinstance(value, ast.Name):
            seen = kinds.get(value.id, ())
            if 'sock' in seen:
                return 'sock'
            if seen == {'nonsock'}:
                return 'nonsock'
            return 'unknown'
        if isinstance(value, ast.Call):
            if self.qual(value.func) in _FUNCS:
                return 'sock'
            func = value.func
            name = func.id if isinstance(func, ast.Name) else (
                func.attr if isinstance(func, ast.Attribute) else None)
            if name in self.class_names or name in _NON_SOCKET_CALLS:
                return 'nonsock'
            return 'unknown'
        if isinstance(value, _NON_SOCKET_EXPRS):
            return 'nonsock'
        return 'unknown'

    def classify(self):
        """Names that are provably not sockets, even when their static kind is unknown.

        A socket reaches a method through an argument, a list item, an attribute, a dict value
        or a user function's return: those receivers stay eligible for lowering. A name that is
        always built from a literal or a user class instance (p1_classmethods) is not."""
        self.class_names = {n.name for n in ast.walk(self.tree) if isinstance(n, ast.ClassDef)}
        funcs = {}
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef):
                params = [a.arg for a in node.args.posonlyargs + node.args.args]
                funcs.setdefault(node.name, []).append(params)
        assignments = []
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Assign):
                targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
                if targets:
                    assignments.append((targets, node.value))
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) \
                    and node.value is not None:
                assignments.append(([node.target.id], node.value))
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                for params in funcs.get(node.func.id, ()):
                    for index, arg in enumerate(node.args):
                        if isinstance(arg, ast.Starred):
                            break
                        if index < len(params):
                            assignments.append(([params[index]], arg))
                    for kw in node.keywords:
                        if kw.arg is not None and kw.arg in params:
                            assignments.append(([kw.arg], kw.value))
        kinds = {}
        for _ in range(8):
            changed = False
            for targets, value in assignments:
                kind = self.expr_kind(value, kinds)
                for target in targets:
                    seen = kinds.setdefault(target, set())
                    if kind not in seen:
                        seen.add(kind)
                        changed = True
            if not changed:
                break
        self.non_sock_names = {name for name, seen in kinds.items() if seen == {'nonsock'}}

    def wants(self):
        return bool(self.mods or self.names)

    def qual(self, node):
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

    def is_sock(self, node):
        """Whether `node` can be a socket (so `.close()` etc. are lowered to our primitives).

        A name this pass created is a socket; a name built only from literals or a user class
        instance is not. Everything else -- an argument, a list item, an attribute, a dict value
        or a user function's return -- stays eligible, because a socket can reach it that way."""
        if isinstance(node, ast.Name):
            if node.id in self.sock_names:
                return True
            if node.id in self.non_sock_names:
                return False
            return True
        if isinstance(node, ast.Call):
            if self.qual(node.func) in _FUNCS:
                return True
            func = node.func
            name = func.id if isinstance(func, ast.Name) else (
                func.attr if isinstance(func, ast.Attribute) else None)
            if name in self.class_names:
                return False
            return True
        return True

    def name_read(self, name):
        """Whether `name` is read anywhere: an unused accept() peer name need not be built."""
        return any(isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, ast.Load)
                   for n in ast.walk(self.tree))

    # ---- addresses -------------------------------------------------------------------------
    def address(self, node):
        if isinstance(node, ast.Tuple) and len(node.elts) == 2:
            return self.visit(node.elts[0]), self.visit(node.elts[1])
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id.startswith('_AilT_') and len(node.args) == 2 and not node.keywords:
            return self.visit(node.args[0]), self.visit(node.args[1])
        self.refuse(node, 'a socket address must be a (host, port) tuple written out.\n'
                          '  write instead: s.connect(("127.0.0.1", 8080))')

    def keyword(self, call, name, default=None):
        for kw in call.keywords:
            if kw.arg == name:
                return kw.value
        return default

    def only_keywords(self, call, allowed):
        for kw in call.keywords:
            if kw.arg is None or kw.arg not in allowed:
                self.refuse(call, '%s() got an unexpected keyword argument %r' % (self.qual(call.func), kw.arg))

    # ---- calls -----------------------------------------------------------------------------
    def visit_Call(self, node):
        name = self.qual(node.func)
        if isinstance(node.func, ast.Name) and node.func.id == 'len' and 'len' not in self.user_defs \
                and len(node.args) == 1 and not node.keywords:
            inner = node.args[0]
            if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute) \
                    and inner.func.attr == 'recv' and self.is_sock(inner.func.value) \
                    and len(inner.args) == 1 and not inner.keywords:
                self.used = True
                return self.at(self.call('_ail_sock_recv_len', self.visit(inner.func.value),
                                         self.visit(inner.args[0])), node)
        if name == 'socket.socket':
            self.used = True
            family = node.args[0] if len(node.args) > 0 else self.keyword(node, 'family', self.C(2))
            kind = node.args[1] if len(node.args) > 1 else self.keyword(node, 'type', self.C(1))
            self.only_keywords(node, {'family', 'type', 'proto'})
            if len(node.args) > 2 or self.keyword(node, 'proto') is not None:
                proto = node.args[2] if len(node.args) > 2 else self.keyword(node, 'proto')
                if not (isinstance(proto, ast.Constant) and proto.value == 0):
                    self.refuse(node, 'socket(proto=...) is not built: only TCP (proto 0 / IPPROTO_TCP)')
            return self.at(self.call('_ail_sock_new', self.visit(family), self.visit(kind)), node)
        if name == 'socket.create_connection':
            self.used = True
            self.only_keywords(node, {'timeout', 'source_address', 'all_errors'})
            if self.keyword(node, 'source_address') is not None:
                self.refuse(node, 'create_connection(source_address=...) is not built.\n'
                                  '  write instead: s = socket.socket(...); s.bind(...); s.connect(...)')
            if len(node.args) != 1:
                self.refuse(node, 'create_connection() takes one (host, port) argument')
            host, port = self.address(node.args[0])
            timeout = self.keyword(node, 'timeout')
            if timeout is None or (isinstance(timeout, ast.Constant) and timeout.value is None):
                return self.at(self.call('_ail_sock_create_connection', host, port, self.C(0.0), self.C(False)), node)
            return self.at(self.call('_ail_sock_create_connection', host, port, self.visit(timeout), self.C(True)), node)
        if name == 'socket.create_server':
            self.used = True
            self.only_keywords(node, {'family', 'backlog', 'reuse_port', 'dualstack_ipv6'})
            if len(node.args) != 1:
                self.refuse(node, 'create_server() takes one (host, port) argument')
            for bad in ('reuse_port', 'dualstack_ipv6'):
                value = self.keyword(node, bad)
                if value is not None and not (isinstance(value, ast.Constant) and value.value is False):
                    self.refuse(node, 'create_server(%s=...) is not built.\n'
                                      '  write instead: s = socket.socket(...); s.setsockopt(...); s.bind(...); s.listen(...)' % bad)
            host, port = self.address(node.args[0])
            backlog = self.keyword(node, 'backlog')
            backlog = self.visit(backlog) if backlog is not None else self.C(128)
            return self.at(self.call('_ail_sock_create_server', host, port, backlog), node)
        if name == 'socket.gethostname':
            self.used = True
            if node.args or node.keywords:
                self.refuse(node, 'gethostname() takes no arguments')
            return self.at(self.call('_ail_sp_sock_gethostname'), node)
        if name == 'socket.gethostbyname':
            self.used = True
            if len(node.args) != 1 or node.keywords:
                self.refuse(node, 'gethostbyname() takes one host name')
            return self.at(self.call('_ail_sp_sock_gethostbyname', self.visit(node.args[0])), node)
        if name in _FUNCS:
            self.refuse(node, '%s is not built.\n  write instead: %s' % (name, _USE))
        if isinstance(node.func, ast.Attribute):
            method = node.func.attr
            if method in _REFUSED_METHODS:
                if not self.is_sock(node.func.value):
                    return self.generic_visit(node)
                self.refuse(node, 'socket.%s() is refused by name.\n  write instead: %s'
                            % (method, _REFUSED_METHODS[method]))
            if method in ('connect', 'bind', 'listen', 'send', 'sendall', 'recv', 'close', 'shutdown',
                          'settimeout', 'gettimeout', 'setsockopt', 'accept', 'getsockname', 'getpeername',
                          'recv_into'):
                if not self.is_sock(node.func.value):
                    return self.generic_visit(node)
                return self.lower_method(node, method)
        return self.generic_visit(node)

    def lower_method(self, node, method):
        self.used = True
        receiver = self.visit(node.func.value)
        if method == 'recv_into':
            self.refuse(node, 'socket.recv_into() is refused by name.\n'
                              '  write instead: data = s.recv(n)')
        if method in ('accept', 'getsockname', 'getpeername'):
            self.refuse(node, '%s() has to be unpacked: write `a, b = s.%s()`' % (method, method))
        args = node.args
        if method in ('connect', 'bind'):
            if len(args) != 1 or node.keywords:
                self.refuse(node, '%s() takes one (host, port) tuple' % method)
            host, port = self.address(args[0])
            return self.at(self.call('_ail_sock_' + method, receiver, host, port), node)
        if method == 'listen':
            backlog = args[0] if args else self.C(128)
            if len(args) > 1 or node.keywords:
                self.refuse(node, 'listen() takes one optional backlog')
            return self.at(self.call('_ail_sock_listen', receiver, self.visit(backlog)), node)
        if method in ('send', 'sendall', 'recv'):
            if len(args) != 1 or node.keywords:
                self.refuse(node, '%s() takes one argument' % method)
            return self.at(self.call('_ail_sock_' + method, receiver, self.visit(args[0])), node)
        if method in ('close', 'gettimeout'):
            if args or node.keywords:
                self.refuse(node, '%s() takes no arguments' % method)
            return self.at(self.call('_ail_sock_' + method, receiver), node)
        if method == 'shutdown':
            if len(args) != 1 or node.keywords:
                self.refuse(node, 'shutdown() takes one how argument')
            return self.at(self.call('_ail_sock_shutdown', receiver, self.visit(args[0])), node)
        if method == 'settimeout':
            if len(args) != 1 or node.keywords:
                self.refuse(node, 'settimeout() takes one value')
            value = args[0]
            if isinstance(value, ast.Constant) and value.value is None:
                return self.at(self.call('_ail_sock_settimeout_none', receiver), node)
            return self.at(self.call('_ail_sock_settimeout', receiver, self.visit(value)), node)
        if method == 'setsockopt':
            if len(args) != 3 or node.keywords:
                self.refuse(node, 'setsockopt() takes level, option and value')
            return self.at(self.call('_ail_sock_setsockopt', receiver, self.visit(args[0]),
                                     self.visit(args[1]), self.visit(args[2])), node)
        self.refuse(node, 'socket.%s is not built.\n  write instead: %s' % (method, _USE))

    # ---- the special assignments ------------------------------------------------------------
    def visit_Assign(self, node):
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and isinstance(node.value, ast.Call) and self.qual(node.value.func) in _FUNCS:
            self.sock_names.add(node.targets[0].id)
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and isinstance(node.value, ast.Name) and node.value.id in self.sock_names:
            self.sock_names.add(node.targets[0].id)
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Tuple) \
                and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute) \
                and self.is_sock(node.value.func.value):
            method = node.value.func.attr
            target = node.targets[0]
            widths = (2, 4) if method in ('getsockname', 'getpeername') else (2,)
            if method in ('accept', 'getsockname', 'getpeername') and len(target.elts) in widths \
                    and all(isinstance(e, ast.Name) for e in target.elts):
                self.used = True
                receiver = self.visit(node.value.func.value)
                left, right = target.elts[0], target.elts[1]
                if method == 'accept':
                    self.sock_names.add(left.id)
                    first = ast.Assign(targets=[left], value=self.at(self.call('_ail_sp_sock_accept', receiver), node))
                    conn = self.load(left)
                    if self.general:
                        peer = self.at(ast.Tuple(elts=[
                            self.at(self.call('_ail_sp_sock_peer_host', copy.deepcopy(conn)), node),
                            self.at(self.call('_ail_sp_sock_peer_port', copy.deepcopy(conn)), node)], ctx=ast.Load()), node)
                    else:
                        peer = self.at(self.call('_ail_sock_peer', conn), node)
                    second = ast.Assign(targets=[right], value=peer)
                    out = [self.at(first, node)]
                    if self.name_read(right.id):
                        out.append(self.at(second, node))
                    return out
                stem = 'local' if method == 'getsockname' else 'peer'
                check = ast.Expr(value=self.at(self.call('_ail_sock_unpack', copy.deepcopy(receiver),
                                                         self.C(len(target.elts))), node))
                first = ast.Assign(targets=[left], value=self.at(self.call('_ail_sp_sock_' + stem + '_host', receiver), node))
                second = ast.Assign(targets=[right], value=self.at(
                    self.call('_ail_sp_sock_' + stem + '_port', copy.deepcopy(receiver)), node))
                out = [self.at(check, node), self.at(first, node), self.at(second, node)]
                if len(target.elts) == 4:          # CPython's AF_INET6 address: flowinfo and scope_id are 0 here
                    for extra in target.elts[2:]:
                        out.append(self.at(ast.Assign(targets=[extra], value=self.C(0)), node))
                return out
        return self.generic_visit(node)

    # ---- with ------------------------------------------------------------------------------
    def visit_With(self, node):
        worth = any((isinstance(item.context_expr, ast.Call) and self.qual(item.context_expr.func) in _FUNCS)
                    or (isinstance(item.context_expr, ast.Name) and item.context_expr.id in self.sock_names)
                    for item in node.items)
        if not worth:
            return self.generic_visit(node)
        for item in node.items:
            if isinstance(item.optional_vars, ast.Name):
                self.sock_names.add(item.optional_vars.id)
        body = []
        for s in node.body:
            visited = self.visit(s)
            body.extend(visited if isinstance(visited, list) else [visited])
        for item in reversed(node.items):
            expr = self.visit(item.context_expr)
            if item.optional_vars is not None:
                target = item.optional_vars
            else:
                target = self.N(self.tmp('with_sock'), store=True)
            assign = self.at(ast.Assign(targets=[target], value=expr), item.context_expr)
            close = self.at(ast.Expr(value=self.call('_ail_sock_close', self.load(target))), item.context_expr)
            body = [assign, self.at(ast.Try(body=body, handlers=[], orelse=[], finalbody=[close]), item.context_expr)]
        return body

    # ---- names and attributes --------------------------------------------------------------
    def visit_Attribute(self, node):
        name = self.qual(node)
        if name is not None and isinstance(node.ctx, ast.Load):
            if name in CONSTS:
                return self.at(self.C(CONSTS[name]), node)
            if name in _ALIASES:
                return self.at(self.N(_ALIASES[name]), node)
            if name == 'socket.socket':
                self.refuse(node, 'socket.socket used as a value is not built.\n  write instead: s = socket.socket(...)')
            if name.startswith('socket.'):
                self.refuse(node, '%s is not built.\n  write instead: %s' % (name, _USE))
        return self.generic_visit(node)

    def visit_Name(self, node):
        full = self.names.get(node.id)
        if full is not None and isinstance(node.ctx, ast.Load) and node.id not in self.user_defs:
            if full in CONSTS:
                return self.at(self.C(CONSTS[full]), node)
            if full in _ALIASES:
                return self.at(self.N(_ALIASES[full]), node)
            if full in _FUNCS:
                return node
            self.refuse(node, '%s used here is not built.\n  write instead: %s' % (full, _USE))
        if node.id in self.mods and isinstance(node.ctx, ast.Load):
            self.refuse(node, 'the module name %s used as a value is not built.\n  write instead: %s'
                        % (node.id, _USE))
        return node

    # ---- driver ----------------------------------------------------------------------------
    def run(self):
        self.visit(self.tree)
        for node in self.import_nodes:
            if node in self.tree.body:
                self.tree.body[self.tree.body.index(node)] = self.at(ast.Pass(), node)
        self.leftovers()
        self.inject()
        ast.fix_missing_locations(self.tree)

    def leftovers(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and id(node) not in self.synth \
                    and (node.id in self.mods or node.id in self.names) and node.id not in self.user_defs:
                self.refuse(node, '%s used here is not built.\n  write instead: %s' % (self.qual(node), _USE))

    def inject(self):
        import filelower
        import stdlib5
        roots = {n.id for n in ast.walk(self.tree) if isinstance(n, ast.Name) and n.id.startswith('_ail_sock_')}
        statements = []
        if not self.general:
            io = _IO_TYPED
        elif any(isinstance(n, ast.FunctionDef) and n.name == '_ail_mkb' for n in ast.walk(self.tree)):
            io = _IO_GENERAL_BYTES
        else:
            io = _IO_GENERAL_STR
        prelude = _PRELUDE.replace('#SPLICE#', io)
        source = stdlib5.shake(prelude, roots)
        parsed = ast.parse(filelower._Lowerer.surface(source) if self.general else source)
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


def _install_all():
    import filelib
    filelib.PRIMS.update(SOCKS)      # after filert has checked its own adapters (sockrt supplies these)
    sockrt.install()
    _patch_cruntime()
    _patch_pyfunc()


def rewrite_tree(tree, Unsupported, general=False):
    """Lower socket in `tree` (in place). Returns whether the program uses it."""
    global ACTIVE
    ACTIVE = False
    _deactivate()
    if any(isinstance(n, (ast.Import, ast.ImportFrom)) and
           (any(a.name == 'socket' for a in n.names) if isinstance(n, ast.Import) else n.module == 'socket')
           for n in tree.body):
        import filelib
        if filelib.target_windows():
            for n in tree.body:
                if isinstance(n, (ast.Import, ast.ImportFrom)) and (
                        (isinstance(n, ast.Import) and any(a.name == 'socket' for a in n.names)) or
                        (isinstance(n, ast.ImportFrom) and n.module == 'socket')):
                    error = Unsupported('import socket under --target windows is not built (Winsock is a later job).\n'
                                        '  write instead: run this program on a POSIX target')
                    error.source_line = getattr(n, 'lineno', None)
                    raise error
    if not any(isinstance(n, (ast.Import, ast.ImportFrom)) and
               (any(a.name == 'socket' for a in n.names) if isinstance(n, ast.Import) else n.module == 'socket')
               for n in tree.body):
        return False
    lowerer = _Lowerer(tree, Unsupported, general)
    lowerer.scan()
    if not lowerer.wants():
        return False
    uses = False
    for node in ast.walk(tree):
        if isinstance(node, (ast.Name, ast.Attribute)) and lowerer.qual(node) is not None \
                and node not in lowerer.import_nodes:
            uses = True
            break
    if not uses:
        return False
    _install_all()
    lowerer.run()
    ACTIVE = True
    _activate()
    return True


_BASE_PROCIO = None
_ORIG_GPT = None


def _activate():
    global _BASE_PROCIO, _ORIG_GPT
    import cruntime
    import filert
    import pyfunc
    if _BASE_PROCIO is None:
        _BASE_PROCIO = list(cruntime.REQUIRES['PROCIO'])
        _ORIG_GPT = filert.general_proc_text
    cruntime.REQUIRES['PROCIO'] = _BASE_PROCIO + ['SOCKIO', 'SOCKEXC']
    for name, code in sockrt.SOCK_CODES.items():
        pyfunc._BUILTIN_EXC_NAMES[name] = code
        pyfunc.EXC_NAMES[name] = code
    if not getattr(filert.general_proc_text, '_ail_sock', False):
        base = _ORIG_GPT
        def general_proc_text():
            return base() + '\n' + sockrt.CORE + sockrt.GENERAL_C
        general_proc_text._ail_sock = True
        filert.general_proc_text = general_proc_text


def _deactivate():
    global _BASE_PROCIO
    if _BASE_PROCIO is None:
        return
    import cruntime
    import filert
    cruntime.REQUIRES['PROCIO'] = list(_BASE_PROCIO)
    if getattr(filert.general_proc_text, '_ail_sock', False):
        filert.general_proc_text = _ORIG_GPT


def _patch_cruntime():
    import cruntime
    if getattr(cruntime._piece_text, '_ail_sock', False):
        return
    original = cruntime._piece_text

    def _piece_text(p, want):
        text = original(p, want)
        if p == 'DIE' and 'SOCKEXC' in want and ACTIVE:
            text = sockrt.patch_die(text)
        return text
    _piece_text._ail_sock = True
    cruntime._piece_text = _piece_text


def _patch_pyfunc():
    import pyfunc
    if getattr(pyfunc._exc_parts, '_ail_sock', False):
        return
    original = pyfunc._exc_parts

    def _exc_parts(ctx, code):
        if code in sockrt.SOCK_CODES.values():
            ctx.parts.update(('ASSERTEXC', 'OVERFLOWEXC', 'FILEEXC', 'SOCKEXC'))
            return
        return original(ctx, code)
    _exc_parts._ail_sock = True
    pyfunc._exc_parts = _exc_parts

    original_codes = pyfunc._builtin_handler_codes

    def _builtin_handler_codes(code):
        base = original_codes(code)
        if ACTIVE and code == pyfunc.EXC_NAMES.get('OSError'):
            return tuple(base) + tuple(sockrt.SOCK_CODES.values())
        return base
    _builtin_handler_codes._ail_sock = True
    pyfunc._builtin_handler_codes = _builtin_handler_codes

