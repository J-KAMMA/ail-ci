# -*- coding: utf-8 -*-
"""pathlib_prelude.py -- the Python source pathlower.py injects for `pathlib.Path` (stage G10).

Ordinary Python in the subset both compile paths build (no default arguments, no tuples, no
properties). A path is an instance of `_AilPath` holding its normalized text `s`, exactly the
string CPython's `str(PurePosixPath(...))` gives; every operation is a function on `str` (so a chain
such as `p.parent / "x"` builds one object, not one per step) and `_AilPath(...)` wraps the result.
The functions follow CPython 3.12's pathlib.py and posixpath.py; the comment above each says which.
The snippets register themselves in filelib_prelude.SNIPPETS, so the file layer injects only the
ones a program reaches (and only after pathlower has asked for them).
"""
import ast

from filelib_prelude import snippet

_TEXT = []
# the snippets of the file layer that the functions below call
_EXTERNAL = {'_ail_pjoin': 'pjoin', '_ail_phead': 'phead', '_ail_ptail': 'ptail', '_ail_pabspath': 'pabs'}


def _group(source):
    _TEXT.append(source)

CLASS_PLAIN = '''
class _AilPath:
    def __init__(self, s: str):
        self.s = s
'''

# the general path can print an instance: give it the text CPython shows, so that a path the pass
# did not recognise as one still prints as CPython prints it
CLASS_GENERAL = CLASS_PLAIN + '''
    def __str__(self) -> str:
        return self.s

    def __repr__(self) -> str:
        return "PosixPath(" + _ail_pp_repr(self.s) + ")"

    def __eq__(self, other: _AilPath) -> bool:
        return self.s == other.s

    def __lt__(self, other: _AilPath) -> bool:
        return self.s.replace("/", "\\0") < other.s.replace("/", "\\0")
'''

snippet('pl_class', CLASS_PLAIN)

_group('''
def _ail_pl_norm(raw: str) -> str:
    if raw == "":
        return "."
    root = ""
    if raw.startswith("/"):
        root = "/"
        if raw.startswith("//") and not raw.startswith("///"):
            root = "//"
    parts: list[str] = []
    for comp in raw.split("/"):
        if comp != "" and comp != ".":
            parts.append(comp)
    out = root + "/".join(parts)
    if out == "":
        return "."
    return out


def _ail_pl_joins(a: str, b: str) -> str:
    return _ail_pl_norm(_ail_pjoin(a, b))


def _ail_pl_rootlen(s: str) -> int:
    if s.startswith("//"):
        return 2
    if s.startswith("/"):
        return 1
    return 0


def _ail_pl_name(s: str) -> str:
    if s == ".":
        return ""
    body = s[_ail_pl_rootlen(s):]
    return body[body.rfind("/") + 1:]


def _ail_pl_suffix_of(name: str) -> str:
    i = name.rfind(".")
    if i > 0 and i < len(name) - 1:
        return name[i:]
    return ""


def _ail_pl_suffix(s: str) -> str:
    return _ail_pl_suffix_of(_ail_pl_name(s))


def _ail_pl_stem(s: str) -> str:
    name = _ail_pl_name(s)
    i = name.rfind(".")
    if i > 0 and i < len(name) - 1:
        return name[:i]
    return name


def _ail_pl_suffixes(s: str) -> list[str]:
    name = _ail_pl_name(s)
    out: list[str] = []
    if name.endswith("."):
        return out
    k = 0
    while k < len(name) and name[k] == ".":
        k += 1
    pieces = name[k:].split(".")
    i = 1
    while i < len(pieces):
        out.append("." + pieces[i])
        i += 1
    return out


def _ail_pl_child(ps: str, name: str) -> str:
    if ps == ".":
        return name
    if ps.endswith("/"):
        return ps + name
    return ps + "/" + name


def _ail_pl_parent(s: str) -> str:
    r = _ail_pl_rootlen(s)
    body = s[r:]
    if s == "." or body == "":
        return s
    i = body.rfind("/")
    if i < 0:
        if r == 0:
            return "."
        return s[:r]
    return s[:r + i]


def _ail_pl_parts(s: str) -> list[str]:
    out: list[str] = []
    r = _ail_pl_rootlen(s)
    if r > 0:
        out.append(s[:r])
    if s == ".":
        return out
    body = s[r:]
    if body != "":
        for c in body.split("/"):
            out.append(c)
    return out


def _ail_pl_root(s: str) -> str:
    return s[:_ail_pl_rootlen(s)]


def _ail_pl_isabs(s: str) -> bool:
    return s.startswith("/")


def _ail_pl_repr(s: str) -> str:
    return "PosixPath(" + _ail_pp_repr(s) + ")"


def _ail_pl_reprs(ps: list[_AilPath]) -> str:
    out = "["
    first = True
    for p in ps:
        if not first:
            out = out + ", "
        first = False
        out = out + _ail_pl_repr(p.s)
    return out + "]"
''')

_group('''
def _ail_pl_with_name(s: str, name: str) -> str:
    if _ail_pl_name(s) == "":
        raise ValueError(_ail_pl_repr(s) + " has an empty name")
    if name == "" or "/" in name or name == ".":
        raise ValueError("Invalid name " + _ail_pp_repr(name))
    return _ail_pl_child(_ail_pl_parent(s), name)


def _ail_pl_with_stem(s: str, stem: str) -> str:
    return _ail_pl_with_name(s, stem + _ail_pl_suffix(s))


def _ail_pl_with_suffix(s: str, suffix: str) -> str:
    if "/" in suffix:
        raise ValueError("Invalid suffix " + _ail_pp_repr(suffix))
    if (suffix != "" and not suffix.startswith(".")) or suffix == ".":
        raise ValueError("Invalid suffix " + _ail_pp_repr(suffix))
    name = _ail_pl_name(s)
    if name == "":
        raise ValueError(_ail_pl_repr(s) + " has an empty name")
    old = _ail_pl_suffix_of(name)
    if old == "":
        name = name + suffix
    else:
        name = name[:len(name) - len(old)] + suffix
    return _ail_pl_child(_ail_pl_parent(s), name)
''')

_group('''
def _ail_pl_sorted(ps: list[_AilPath], reverse: bool) -> list[_AilPath]:
    keys: list[str] = []
    for p in ps:
        keys.append(p.s.replace("/", "\\0"))
    keys.sort()
    if reverse:
        keys.reverse()
    out: list[_AilPath] = []
    for k in keys:
        out.append(_AilPath(k.replace("\\0", "/")))
    return out
''')

_group('''
def _ail_pl_probe(s: str) -> None:
    e = _ail_pp_staterr(s)
    if e != 0 and e != 2 and e != 20 and e != 9 and e != 40 and e != -1:
        _ail_u = _ail_os_getsize(s)


def _ail_pl_exists(s: str) -> bool:
    if _ail_os_kind(s, 1) != 0:
        return True
    _ail_pl_probe(s)
    return False


def _ail_pl_isfile(s: str) -> bool:
    k = _ail_os_kind(s, 1)
    if k == 1:
        return True
    if k == 0:
        _ail_pl_probe(s)
    return False


def _ail_pl_isdir(s: str) -> bool:
    k = _ail_os_kind(s, 1)
    if k == 2:
        return True
    if k == 0:
        _ail_pl_probe(s)
    return False


def _ail_pl_mkdir(s: str, mode: int, parents: bool, exist_ok: bool) -> None:
    # (a failure that has to propagate is raised again by repeating the call: a bare `raise` inside a
    # handler is not built on the general path)
    again = False
    try:
        _ail_u = _ail_os_mkdir(s, mode)
    except FileNotFoundError:
        up = _ail_pl_parent(s)
        if not parents or up == s:
            again = True
        else:
            _ail_pl_mkdir(up, 511, True, True)
            _ail_pl_mkdir(s, mode, False, exist_ok)
    except OSError:
        if not exist_ok or not _ail_pl_isdir(s):
            again = True
    if again:
        _ail_u = _ail_os_mkdir(s, mode)


def _ail_pl_unlink(s: str, missing_ok: bool) -> None:
    if not missing_ok:
        _ail_u = _ail_os_unlink(s)
        return
    try:
        _ail_u = _ail_os_unlink(s)
    except FileNotFoundError:
        pass


def _ail_pl_rename(s: str, target: str) -> str:
    _ail_u = _ail_os_rename(s, target)
    return _ail_pl_norm(target)


def _ail_pl_replace(s: str, target: str) -> str:
    _ail_u = _ail_os_replace(s, target)
    return _ail_pl_norm(target)


def _ail_pl_iterdir(s: str) -> list[_AilPath]:
    out: list[_AilPath] = []
    listing = _ail_os_scandir(s, 0)
    if listing == "":
        return out
    for name in listing.split("\\0"):
        out.append(_AilPath(_ail_pl_child(s, name)))
    return out


def _ail_pl_absolute(s: str) -> str:
    if s.startswith("/"):
        return s
    cwd = _ail_os_getcwd()
    if s == ".":
        return cwd
    return _ail_pl_joins(cwd, s)
''')

_group('''
class _AilRealpath:
    def __init__(self):
        self.keys: list[str] = []
        self.vals: list[str] = []
        self.done: list[int] = []
        self.ok = True


def _ail_pl_joinreal(st: _AilRealpath, start: str, rest0: str) -> str:
    path = start
    rest = rest0
    if rest.startswith("/"):
        rest = rest[1:]
        path = "/"
    while rest != "":
        i = rest.find("/")
        name = rest
        if i < 0:
            rest = ""
        else:
            name = rest[:i]
            rest = rest[i + 1:]
        if name == "" or name == ".":
            continue
        if name == "..":
            if path != "":
                if _ail_ptail(path) == "..":
                    path = _ail_pjoin(_ail_pjoin(_ail_phead(path), ".."), "..")
                else:
                    path = _ail_phead(path)
            else:
                path = ".."
            continue
        newpath = _ail_pjoin(path, name)
        if _ail_os_kind(newpath, 0) != 4:
            path = newpath
            continue
        found = -1
        k = 0
        while k < len(st.keys):
            if st.keys[k] == newpath:
                found = k
            k += 1
        if found >= 0:
            if st.done[found] == 1:
                path = st.vals[found]
                continue
            st.ok = False
            return _ail_pjoin(newpath, rest)
        st.keys.append(newpath)
        st.vals.append("")
        st.done.append(0)
        slot = len(st.keys) - 1
        path = _ail_pl_joinreal(st, path, _ail_pp_readlink(newpath))
        if not st.ok:
            return _ail_pjoin(path, rest)
        st.vals[slot] = path
        st.done[slot] = 1
    return path


def _ail_pl_resolve(s: str) -> str:
    st = _AilRealpath()
    path = _ail_pl_joinreal(st, "", s)
    out = _ail_pabspath(path)
    if not st.ok:
        raise RuntimeError("Symlink loop from " + _ail_pp_repr(out))
    return _ail_pl_norm(out)
''')

_group('''
def _ail_pl_find(s: str, ch: str, start: int, end: int) -> int:
    i = start
    while i < end:
        if s[i] == ch:
            return i
        i += 1
    return -1


def _ail_pl_set_end(pat: str, i: int) -> int:
    n = len(pat)
    j = i + 1
    if j < n and pat[j] == "!":
        j += 1
    if j < n and pat[j] == "]":
        j += 1
    while j < n and pat[j] != "]":
        j += 1
    if j >= n:
        return -1
    return j


def _ail_pl_without(xs: list[str], drop: int) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(xs):
        if i != drop:
            out.append(xs[i])
        i += 1
    return out


def _ail_pl_class_stuff(pat: str, i: int, j: int) -> str:
    start = i + 1
    stuff = pat[start:j]
    if "-" not in stuff:
        return stuff.replace("\\\\", "\\\\\\\\")
    chunks: list[str] = []
    k = start + 1
    if pat[start] == "!":
        k = start + 2
    ii = start
    while True:
        k = _ail_pl_find(pat, "-", k, j)
        if k < 0:
            break
        chunks.append(pat[ii:k])
        ii = k + 1
        k = k + 3
    chunk = pat[ii:j]
    if chunk != "":
        chunks.append(chunk)
    else:
        last = len(chunks) - 1
        chunks[last] = chunks[last] + "-"
    m = len(chunks) - 1
    while m > 0:
        a = chunks[m - 1]
        b = chunks[m]
        if a == "" or b == "":
            raise IndexError("string index out of range")
        if a[len(a) - 1:] > b[:1]:
            chunks[m - 1] = a[:len(a) - 1] + b[1:]
            chunks = _ail_pl_without(chunks, m)
        m -= 1
    out: list[str] = []
    for each in chunks:
        out.append(each.replace("\\\\", "\\\\\\\\").replace("-", "\\\\-"))
    return "-".join(out)


def _ail_pl_class_has(stuff0: str, ch: str) -> bool:
    stuff = stuff0
    neg = False
    if stuff.startswith("!"):
        neg = True
        stuff = stuff[1:]
    units: list[str] = []
    escaped: list[int] = []
    p = 0
    while p < len(stuff):
        if stuff[p] == "\\\\" and p + 1 < len(stuff):
            units.append(stuff[p + 1])
            escaped.append(1)
            p += 2
        else:
            units.append(stuff[p])
            escaped.append(0)
            p += 1
    hit = False
    q = 0
    while q < len(units):
        if q + 2 < len(units) and units[q + 1] == "-" and escaped[q + 1] == 0:
            if units[q] <= ch and ch <= units[q + 2]:
                hit = True
            q += 3
        else:
            if units[q] == ch:
                hit = True
            q += 1
    if neg:
        return not hit
    return hit


def _ail_pl_match(pat: str, name: str) -> bool:
    pi = 0
    ni = 0
    star_pi = -1
    star_ni = 0
    while ni < len(name):
        ok = False
        step = 1
        if pi < len(pat):
            c = pat[pi]
            if c == "*":
                star_pi = pi
                star_ni = ni
                pi += 1
                continue
            if c == "?":
                ok = True
            elif c == "[":
                e = _ail_pl_set_end(pat, pi)
                if e < 0:
                    ok = name[ni] == "["
                else:
                    ok = _ail_pl_class_has(_ail_pl_class_stuff(pat, pi, e), name[ni])
                    step = e - pi + 1
            else:
                ok = name[ni] == c
        if ok:
            pi += step
            ni += 1
        elif star_pi >= 0:
            pi = star_pi + 1
            star_ni += 1
            ni = star_ni
        else:
            return False
    while pi < len(pat) and pat[pi] == "*":
        pi += 1
    return pi == len(pat)


def _ail_pl_glob_parts(pattern: str) -> list[str]:
    parts: list[str] = []
    for comp in pattern.split("/"):
        if comp != "" and comp != ".":
            parts.append(comp)
    if pattern.endswith("/"):
        parts.append("")
    return parts


class _AilBag:
    def __init__(self):
        self.items: list[str] = []


def _ail_pl_select(parts: list[str], idx: int, cur: str, out: _AilBag) -> None:
    if idx >= len(parts) or parts[idx] == "":
        out.items.append(cur)
        return
    pat = parts[idx]
    if pat == "..":
        _ail_pl_select(parts, idx + 1, _ail_pl_child(cur, ".."), out)
        return
    if pat == "**":
        nxt = idx + 1
        while nxt < len(parts) and parts[nxt] == "**":
            nxt += 1
        again = False
        k = nxt
        while k < len(parts):
            if parts[k] == "**":
                again = True
            k += 1
        starts: list[str] = [cur]
        stack: list[str] = [cur]
        while len(stack) > 0:
            d = stack.pop()
            listing = ""
            try:
                listing = _ail_os_scandir(d, 0)
            except OSError:
                continue
            kids: list[str] = []
            if listing != "":
                for name in listing.split("\\0"):
                    kid = _ail_pl_child(d, name)
                    if _ail_os_kind(kid, 0) == 2:
                        kids.append(kid)
            for kid in kids:
                starts.append(kid)
            j = len(kids) - 1
            while j >= 0:
                stack.append(kids[j])
                j -= 1
        if again:
            tmp = _AilBag()
            for st in starts:
                _ail_pl_select(parts, nxt, st, tmp)
            seen: dict[str, int] = {}
            for each in tmp.items:
                if each not in seen:
                    seen[each] = 1
                    out.items.append(each)
        else:
            for st in starts:
                _ail_pl_select(parts, nxt, st, out)
        return
    if "**" in pat:
        raise ValueError("Invalid pattern: '**' can only be an entire path component")
    listing2 = ""
    try:
        listing2 = _ail_os_scandir(cur, 1)
    except OSError:
        return
    if listing2 == "":
        return
    dironly = idx + 1 < len(parts)
    for entry in listing2.split("\\0"):
        if dironly and not entry.startswith("d"):
            continue
        nm = entry[1:]
        if _ail_pl_match(pat, nm):
            _ail_pl_select(parts, idx + 1, _ail_pl_child(cur, nm), out)


def _ail_pl_check_parts(parts: list[str], idx: int) -> None:
    i = idx
    while i < len(parts):
        if parts[i] != "**" and parts[i] != ".." and "**" in parts[i]:
            raise ValueError("Invalid pattern: '**' can only be an entire path component")
        i += 1


def _ail_pl_glob(root: str, pattern: str) -> list[_AilPath]:
    if pattern == "":
        raise ValueError("Unacceptable pattern: " + _ail_pp_repr(pattern))
    if pattern.startswith("/"):
        raise RuntimeError("Non-relative patterns are unsupported")
    parts = _ail_pl_glob_parts(pattern)
    if len(parts) == 0:
        raise IndexError("tuple index out of range")
    if len(parts) == 1 and parts[0] == "":
        raise RuntimeError("'_TerminatingSelector' object has no attribute 'select_from'")
    _ail_pl_check_parts(parts, 0)
    found = _AilBag()
    if _ail_pl_isdir(root):
        _ail_pl_select(parts, 0, root, found)
    out: list[_AilPath] = []
    for each in found.items:
        out.append(_AilPath(each))
    return out


def _ail_pl_rglob(root: str, pattern: str) -> list[_AilPath]:
    if pattern.startswith("/"):
        raise RuntimeError("Non-relative patterns are unsupported")
    parts: list[str] = ["**"]
    for each in _ail_pl_glob_parts(pattern):
        parts.append(each)
    _ail_pl_check_parts(parts, 0)
    found = _AilBag()
    if _ail_pl_isdir(root):
        _ail_pl_select(parts, 0, root, found)
    out: list[_AilPath] = []
    for each in found.items:
        out.append(_AilPath(each))
    return out
''')


class _Prefix(ast.NodeTransformer):
    def __init__(self, names):
        self.names = names

    def visit_Name(self, node):
        if node.id in self.names:
            node.id = '_pl_' + node.id
        return node

    def visit_arg(self, node):
        if node.arg in self.names:
            node.arg = '_pl_' + node.arg
        return self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        if node.name in self.names:
            node.name = '_pl_' + node.name
        return self.generic_visit(node)


def _prefix_locals(fn):
    """Every local of a prelude function gets a `_pl_` prefix: a user function named `listing` or `parts` must not
    meet a local of the same name (the general path reads that as a function used as a value)."""
    names = {a.arg for a in fn.args.args + fn.args.kwonlyargs}
    for each in ast.walk(fn):
        if isinstance(each, ast.Name) and isinstance(each.ctx, ast.Store):
            names.add(each.id)
        elif isinstance(each, ast.ExceptHandler) and each.name:
            names.add(each.name)
    names = {n for n in names if not n.startswith('_')}
    _Prefix(names).visit(fn)


def _register_all():
    """One snippet per def, named after it, with the defs it mentions as its needs: a program gets exactly the
    functions it reaches (the compiler does not drop an unused one)."""
    source = '\n'.join(_TEXT)
    tree = ast.parse(source)
    defs = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
    names = {n.name for n in defs}
    for node in defs:
        if isinstance(node, ast.FunctionDef):
            _prefix_locals(node)
        text = ast.unparse(node)
        needs = set()
        for each in ast.walk(node):
            if isinstance(each, ast.Name):
                if each.id in names and each.id != node.name:
                    needs.add(each.id)
                elif each.id == '_AilPath':
                    needs.add('pl_class')
                elif each.id in _EXTERNAL:
                    needs.add(_EXTERNAL[each.id])
        snippet(node.name, '\n' + text + '\n', tuple(sorted(needs)))
    FUNCTIONS.update(names)


FUNCTIONS = set()
_registered = []


def register():
    """Register the snippets (pathlower calls this when a program imports pathlib: parsing the prelude costs
    milliseconds that every other compile should not pay)."""
    if not _registered:
        _registered.append(True)
        _register_all()
