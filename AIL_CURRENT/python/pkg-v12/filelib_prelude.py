# -*- coding: utf-8 -*-
"""filelib_prelude.py -- the Python source filelib.py injects (stage G7).

Every entry is ordinary Python in the subset both compile paths build, with no default arguments
(the typed path takes none on methods): the lowering fills the defaults in at the call site.
`SNIPPETS` maps a name to (source, names it needs). Only the snippets a program reaches are added.
"""

SNIPPETS = {}


def snippet(name, source, needs=()):
    SNIPPETS[name] = (source, tuple(needs))


snippet('text_io', '''
class _AilTextIO:
    def __init__(self, h: int, name: str, mode: str, encoding: str, errors: str):
        self.h = h
        self.name = name
        self.mode = mode
        self.encoding = encoding
        self.errors = errors
        self.done = False

    def read(self, size: int) -> str:
        return _ail_f_tread(self.h, size)

    def readline(self, size: int) -> str:
        return _ail_f_treadline(self.h, size)

    def readlines(self, hint: int) -> list[str]:
        out: list[str] = []
        total = 0
        while True:
            line = _ail_f_tnext(self.h)
            if len(line) == 0:
                break
            out.append(line)
            total += len(line)
            if hint > 0 and total >= hint:
                break
        return out

    def write(self, s: str) -> int:
        return _ail_f_twrite(self.h, s)

    def writelines(self, lines: list[str]) -> None:
        for line in lines:
            _ail_u = _ail_f_twrite(self.h, line)

    def seek(self, offset: int, whence: int) -> int:
        return _ail_f_seek(self.h, offset, whence)

    def tell(self) -> int:
        return _ail_f_tell(self.h)

    def flush(self) -> None:
        _ail_u = _ail_f_flush(self.h)

    def close(self) -> None:
        if not self.done:
            self.done = True
            _ail_u = _ail_f_close(self.h)

    def readable(self) -> bool:
        return _ail_f_readable(self.h) != 0

    def writable(self) -> bool:
        return _ail_f_writable(self.h) != 0

    def seekable(self) -> bool:
        return _ail_f_seekable(self.h) != 0

    def isatty(self) -> bool:
        return False

    def _closed(self) -> bool:
        return self.done != 0

    def _next(self) -> str:
        return _ail_f_tnext(self.h)

    def _next_value(self) -> str:
        line = _ail_f_tnext(self.h)
        if len(line) == 0:
            raise RuntimeError("StopIteration")
        return line

    def _next_default(self, default: str) -> str:
        line = _ail_f_tnext(self.h)
        if len(line) == 0:
            return default
        return line


def _ail_open_text(path: str, mode: str, buffering: int, enc: str, hasenc: int, err: str, haserr: int, nl: str, hasnl: int, encattr: str) -> _AilTextIO:
    h = _ail_f_open(path, mode, buffering, enc, hasenc, err, haserr, nl, hasnl)
    encoding = "utf-8"
    if hasenc != 0:
        encoding = encattr
    errors = "strict"
    if haserr != 0:
        errors = err
    return _AilTextIO(h, path, mode, encoding, errors)
''')

snippet('bin_io', '''
class _AilBinaryIO:
    def __init__(self, h: int, name: str, mode: str):
        self.h = h
        self.name = name
        self.mode = mode
        self.done = False

    def read(self, size: int) -> bytes:
        return _ail_f_bread(self.h, size)

    def readline(self, size: int) -> bytes:
        return _ail_f_breadline(self.h, size)

    def readlines(self, hint: int) -> list[bytes]:
        out: list[bytes] = []
        total = 0
        while True:
            line = _ail_f_bnext(self.h)
            if len(line) == 0:
                break
            out.append(line)
            total += len(line)
            if hint > 0 and total >= hint:
                break
        return out

    def write(self, data: bytes) -> int:
        return _ail_f_bwrite(self.h, data)

    def writelines(self, lines: list[bytes]) -> None:
        for line in lines:
            _ail_u = _ail_f_bwrite(self.h, line)

    def seek(self, offset: int, whence: int) -> int:
        return _ail_f_seek(self.h, offset, whence)

    def tell(self) -> int:
        return _ail_f_tell(self.h)

    def flush(self) -> None:
        _ail_u = _ail_f_flush(self.h)

    def close(self) -> None:
        if not self.done:
            self.done = True
            _ail_u = _ail_f_close(self.h)

    def readable(self) -> bool:
        return _ail_f_readable(self.h) != 0

    def writable(self) -> bool:
        return _ail_f_writable(self.h) != 0

    def seekable(self) -> bool:
        return _ail_f_seekable(self.h) != 0

    def isatty(self) -> bool:
        return False

    def _closed(self) -> bool:
        return self.done != 0

    def _next(self) -> bytes:
        return _ail_f_bnext(self.h)

    def _next_value(self) -> bytes:
        line = _ail_f_bnext(self.h)
        if len(line) == 0:
            raise RuntimeError("StopIteration")
        return line

    def _next_default(self, default: bytes) -> bytes:
        line = _ail_f_bnext(self.h)
        if len(line) == 0:
            return default
        return line


def _ail_open_bin(path: str, mode: str, buffering: int, enc: str, hasenc: int, err: str, haserr: int, nl: str, hasnl: int) -> _AilBinaryIO:
    h = _ail_f_open(path, mode, buffering, enc, hasenc, err, haserr, nl, hasnl)
    return _AilBinaryIO(h, path, mode)
''')

# one-shot helpers for `open(...).read()` and friends on a temporary file (CPython closes it at once)
snippet('text_once', '''
def _ail_text_once_read(path: str, mode: str, buffering: int, enc: str, hasenc: int, err: str, haserr: int, nl: str, hasnl: int, encattr: str, size: int) -> str:
    f = _ail_open_text(path, mode, buffering, enc, hasenc, err, haserr, nl, hasnl, encattr)
    try:
        return f.read(size)
    finally:
        f.close()


def _ail_text_once_readline(path: str, mode: str, buffering: int, enc: str, hasenc: int, err: str, haserr: int, nl: str, hasnl: int, encattr: str, size: int) -> str:
    f = _ail_open_text(path, mode, buffering, enc, hasenc, err, haserr, nl, hasnl, encattr)
    try:
        return f.readline(size)
    finally:
        f.close()


def _ail_text_once_readlines(path: str, mode: str, buffering: int, enc: str, hasenc: int, err: str, haserr: int, nl: str, hasnl: int, encattr: str, hint: int) -> list[str]:
    f = _ail_open_text(path, mode, buffering, enc, hasenc, err, haserr, nl, hasnl, encattr)
    try:
        return f.readlines(hint)
    finally:
        f.close()


def _ail_text_once_write(path: str, mode: str, buffering: int, enc: str, hasenc: int, err: str, haserr: int, nl: str, hasnl: int, encattr: str, s: str) -> int:
    f = _ail_open_text(path, mode, buffering, enc, hasenc, err, haserr, nl, hasnl, encattr)
    try:
        return f.write(s)
    finally:
        f.close()
''', ('text_io',))

snippet('bin_once', '''
def _ail_bin_once_read(path: str, mode: str, buffering: int, enc: str, hasenc: int, err: str, haserr: int, nl: str, hasnl: int, size: int) -> bytes:
    f = _ail_open_bin(path, mode, buffering, enc, hasenc, err, haserr, nl, hasnl)
    try:
        return f.read(size)
    finally:
        f.close()


def _ail_bin_once_readline(path: str, mode: str, buffering: int, enc: str, hasenc: int, err: str, haserr: int, nl: str, hasnl: int, size: int) -> bytes:
    f = _ail_open_bin(path, mode, buffering, enc, hasenc, err, haserr, nl, hasnl)
    try:
        return f.readline(size)
    finally:
        f.close()


def _ail_bin_once_readlines(path: str, mode: str, buffering: int, enc: str, hasenc: int, err: str, haserr: int, nl: str, hasnl: int, hint: int) -> list[bytes]:
    f = _ail_open_bin(path, mode, buffering, enc, hasenc, err, haserr, nl, hasnl)
    try:
        return f.readlines(hint)
    finally:
        f.close()


def _ail_bin_once_write(path: str, mode: str, buffering: int, enc: str, hasenc: int, err: str, haserr: int, nl: str, hasnl: int, data: bytes) -> int:
    f = _ail_open_bin(path, mode, buffering, enc, hasenc, err, haserr, nl, hasnl)
    try:
        return f.write(data)
    finally:
        f.close()
''', ('bin_io',))

# ---------------------------------------------------------------------------------- posixpath

snippet('pjoin', '''
def _ail_pjoin(a: str, b: str) -> str:
    if b.startswith("/"):
        return b
    if a == "" or a.endswith("/"):
        return a + b
    return a + "/" + b
''')

snippet('phead', '''
def _ail_phead(p: str) -> str:
    i = p.rfind("/") + 1
    head = p[:i]
    only_slashes = True
    for ch in head:
        if ch != "/":
            only_slashes = False
    if head != "" and not only_slashes:
        k = len(head)
        while k > 0 and head[k - 1] == "/":
            k -= 1
        head = head[:k]
    return head
''')

snippet('ptail', '''
def _ail_ptail(p: str) -> str:
    return p[p.rfind("/") + 1:]
''')

snippet('pext', '''
def _ail_psplitext_i(p: str) -> int:
    sep = p.rfind("/")
    dot = p.rfind(".")
    if dot > sep:
        k = sep + 1
        while k < dot:
            if p[k] != ".":
                return dot
            k += 1
    return len(p)


def _ail_proot(p: str) -> str:
    return p[:_ail_psplitext_i(p)]


def _ail_pext(p: str) -> str:
    return p[_ail_psplitext_i(p):]
''')

snippet('pnorm', '''
def _ail_pnormpath(path: str) -> str:
    initial = 0
    if path.startswith("/"):
        initial = 1
        if path.startswith("//") and not path.startswith("///"):
            initial = 2
    new: list[str] = []
    for comp in path.split("/"):
        if comp == "" or comp == ".":
            continue
        if comp != ".." or (initial == 0 and len(new) == 0) or (len(new) > 0 and new[len(new) - 1] == ".."):
            new.append(comp)
        elif len(new) > 0:
            new.pop()
    out = "/".join(new)
    if initial > 0:
        out = "/" * initial + out
    if out == "":
        return "."
    return out
''')

snippet('pabs', '''
def _ail_pisabs(p: str) -> bool:
    return p.startswith("/")


def _ail_pabspath(p: str) -> str:
    q = p
    if not p.startswith("/"):
        q = _ail_pjoin(_ail_os_getcwd(), p)
    return _ail_pnormpath(q)
''', ('pjoin', 'pnorm'))

snippet('prel', '''
def _ail_prelpath(path: str, start: str) -> str:
    if path == "":
        raise ValueError("no path specified")
    a: list[str] = []
    for x in _ail_pabspath(start).split("/"):
        if x != "":
            a.append(x)
    b: list[str] = []
    for x in _ail_pabspath(path).split("/"):
        if x != "":
            b.append(x)
    i = 0
    while i < len(a) and i < len(b) and a[i] == b[i]:
        i += 1
    rel: list[str] = []
    k = 0
    while k < len(a) - i:
        rel.append("..")
        k += 1
    j = i
    while j < len(b):
        rel.append(b[j])
        j += 1
    if len(rel) == 0:
        return "."
    return "/".join(rel)
''', ('pabs',))

snippet('pexists', '''
def _ail_pexists(p: str) -> bool:
    return _ail_os_kind(p, 1) != 0


def _ail_pisfile(p: str) -> bool:
    return _ail_os_kind(p, 1) == 1


def _ail_pisdir(p: str) -> bool:
    return _ail_os_kind(p, 1) == 2


def _ail_pislink(p: str) -> bool:
    return _ail_os_kind(p, 0) == 4


def _ail_plexists(p: str) -> bool:
    return _ail_os_kind(p, 0) != 0
''')

# ---------------------------------------------------------------------------------- os

snippet('listdir', '''
def _ail_listdir(path: str) -> list[str]:
    s = _ail_os_scandir(path, 0)
    if s == "":
        return []
    return s.split("\\0")
''')

snippet('makedirs', '''
def _ail_makedirs(name: str, mode: int, exist_ok: bool) -> None:
    head = _ail_phead(name)
    tail = _ail_ptail(name)
    if tail == "":
        tail = _ail_ptail(head)
        head = _ail_phead(head)
    if head != "" and tail != "" and _ail_os_kind(head, 1) == 0:
        try:
            _ail_makedirs(head, 511, exist_ok)
        except FileExistsError:
            pass
        if tail == ".":
            return
    try:
        _ail_u = _ail_os_mkdir(name, mode)
    except OSError:
        if not exist_ok or _ail_os_kind(name, 1) != 2:
            raise
''', ('phead', 'ptail'))

snippet('environ', '''
def _ail_environ_get(k: str, d: str) -> str:
    if _ail_os_hasenv(k) != 0:
        return _ail_os_getenv(k)
    return d


def _ail_environ_item(k: str) -> str:
    if _ail_os_hasenv(k) != 0:
        return _ail_os_getenv(k)
    raise KeyError(k)


def _ail_environ_has(k: str) -> bool:
    return _ail_os_hasenv(k) != 0
''')

snippet('walk', '''
class _AilWalk:
    def __init__(self, top: str):
        self.stack: list[str] = [top]
        self.root = ""
        self.d: list[str] = []
        self.f: list[str] = []
        self.pending = False

    def advance(self, dirs: list[str]) -> bool:
        if self.pending:
            self.pending = False
            i = len(dirs) - 1
            while i >= 0:
                new_path = _ail_pjoin(self.root, dirs[i])
                if _ail_os_kind(new_path, 0) != 4:
                    self.stack.append(new_path)
                i -= 1
        while len(self.stack) > 0:
            top = self.stack.pop()
            try:
                listing = _ail_os_scandir(top, 1)
            except OSError:
                continue
            nd: list[str] = []
            nf: list[str] = []
            if listing != "":
                for entry in listing.split("\\0"):
                    if entry.startswith("d"):
                        nd.append(entry[1:])
                    else:
                        nf.append(entry[1:])
            self.root = top
            self.d = nd
            self.f = nf
            self.pending = True
            return True
        return False

    def dirs(self) -> list[str]:
        return self.d

    def files(self) -> list[str]:
        return self.f
''', ('pjoin',))

snippet('psplit_pair', """
def _ail_psplit_pair(p: str):
    return _ail_phead(p), _ail_ptail(p)
""", ('phead', 'ptail'))

snippet('psplitext_pair', """
def _ail_psplitext_pair(p: str):
    return _ail_proot(p), _ail_pext(p)
""", ('pext',))

snippet('nt_split_pair', '''
def _ail_ntsplit_pair(p: str):
    return _ail_nthead(p), _ail_nttail(p)
''', ('nt_split',))

snippet('nt_ext_pair', '''
def _ail_ntsplitext_pair(p: str):
    return _ail_ntroot(p), _ail_ntext(p)
''', ('nt_ext',))


# ---------------------------------------------------------------------------------- ntpath
# (CPython 3.12's ntpath, written without tuples: the drive/root/rest split is two numbers)

snippet('nt_code', '''
def _ail_nt_code(p: str) -> int:
    normp = p.replace("/", "\\\\")
    if normp[:1] == "\\\\":
        if normp[1:2] == "\\\\":
            start = 2
            if normp[:8].upper() == "\\\\\\\\?\\\\UNC\\\\":
                start = 8
            index = normp.find("\\\\", start)
            if index == -1:
                return len(p) * 2
            index2 = normp.find("\\\\", index + 1)
            if index2 == -1:
                return len(p) * 2
            return index2 * 2 + 1
        return 1
    if normp[1:2] == ":":
        if normp[2:3] == "\\\\":
            return 5
        return 4
    return 0
''')

snippet('nt_join', '''
def _ail_ntjoin_init(a: str) -> str:
    ca = _ail_nt_code(a)
    da = ca // 2
    ra = ca % 2
    return a[:da] + "\\0" + a[da:da + ra] + "\\0" + a[da + ra:]


def _ail_ntjoin_step(state: str, b: str) -> str:
    parts = state.split("\\0")
    result_drive = parts[0]
    result_root = parts[1]
    result_path = parts[2]
    cb = _ail_nt_code(b)
    db = cb // 2
    rb = cb % 2
    p_drive = b[:db]
    p_root = b[db:db + rb]
    p_path = b[db + rb:]
    if rb == 1:
        if db > 0 or result_drive == "":
            result_drive = p_drive
        result_root = p_root
        result_path = p_path
    else:
        different = False
        if db > 0 and p_drive != result_drive:
            if p_drive.lower() != result_drive.lower():
                result_drive = p_drive
                result_root = p_root
                result_path = p_path
                different = True
            else:
                result_drive = p_drive
        if not different:
            n = len(result_path)
            if n > 0 and result_path[n - 1] != "\\\\" and result_path[n - 1] != "/":
                result_path = result_path + "\\\\"
            result_path = result_path + p_path
    return result_drive + "\\0" + result_root + "\\0" + result_path


def _ail_ntjoin_end(state: str) -> str:
    parts = state.split("\\0")
    result_drive = parts[0]
    result_root = parts[1]
    result_path = parts[2]
    if len(result_path) > 0 and result_root == "" and len(result_drive) > 0:
        last = result_drive[len(result_drive) - 1]
        if last != ":" and last != "\\\\" and last != "/":
            return result_drive + "\\\\" + result_path
    return result_drive + result_root + result_path
''', ('nt_code',))

snippet('nt_split', '''
def _ail_nt_split_i(p: str) -> int:
    c = _ail_nt_code(p)
    a = c // 2 + c % 2
    i = len(p)
    while i > a and p[i - 1] != "\\\\" and p[i - 1] != "/":
        i -= 1
    return i


def _ail_nthead(p: str) -> str:
    c = _ail_nt_code(p)
    a = c // 2 + c % 2
    i = _ail_nt_split_i(p)
    head = p[a:i]
    k = len(head)
    while k > 0 and (head[k - 1] == "\\\\" or head[k - 1] == "/"):
        k -= 1
    return p[:a] + head[:k]


def _ail_nttail(p: str) -> str:
    return p[_ail_nt_split_i(p):]
''', ('nt_code',))

snippet('nt_ext', '''
def _ail_ntsplitext_i(p: str) -> int:
    sep = p.rfind("\\\\")
    alt = p.rfind("/")
    if alt > sep:
        sep = alt
    dot = p.rfind(".")
    if dot > sep:
        k = sep + 1
        while k < dot:
            if p[k] != ".":
                return dot
            k += 1
    return len(p)


def _ail_ntroot(p: str) -> str:
    return p[:_ail_ntsplitext_i(p)]


def _ail_ntext(p: str) -> str:
    return p[_ail_ntsplitext_i(p):]
''')

snippet('nt_norm', '''
def _ail_ntnormpath(path: str) -> str:
    q = path.replace("/", "\\\\")
    c = _ail_nt_code(q)
    d = c // 2
    r = c % 2
    prefix = q[:d]
    root = q[d:d + r]
    new: list[str] = []
    for comp in q[d + r:].split("\\\\"):
        if comp == "" or comp == ".":
            continue
        if comp == "..":
            if len(new) > 0 and new[len(new) - 1] != "..":
                new.pop()
            elif len(new) == 0 and r == 1:
                pass
            else:
                new.append("..")
        else:
            new.append(comp)
    if d + r == 0 and len(new) == 0:
        new.append(".")
    return prefix + root + "\\\\".join(new)
''', ('nt_code',))

snippet('nt_abs', '''
def _ail_ntisabs(s: str) -> bool:
    t = s[:3].replace("/", "\\\\")
    return t.startswith("\\\\") or t[1:2] == ":" and t[2:3] == "\\\\"


def _ail_ntabspath(p: str) -> str:
    q = p
    if not _ail_ntisabs(p):
        q = _ail_ntjoin_end(_ail_ntjoin_step(_ail_ntjoin_init(_ail_os_getcwd()), p))
    return _ail_ntnormpath(q)
''', ('nt_join', 'nt_norm'))

