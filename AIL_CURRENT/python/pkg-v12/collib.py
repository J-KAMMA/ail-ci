"""`from collections import defaultdict, Counter, deque, OrderedDict`: rewritten, before the rest of the
Python surface runs, onto what the compiler already builds (dict, list[list[T]], classes), so a program that
does not import collections is untouched and the C runtime gets nothing new.

* Counter[str|int], defaultdict(int|float|str), defaultdict(lambda: <constant>), OrderedDict: a plain
  insertion-ordered `dict[K, V]` (the runtime's compact hash).  `d[k]` on a defaultdict is `d.setdefault(k,
  default)` (a read inserts, as in CPython), `c[k]` on a Counter is `c.get(k, 0)` (no insert), `d[k] += v`
  is the upsert `d[k] = d.get(k, default) + v`.  Counter(iterable), update, most_common, elements, total,
  + - & | and printing go through small typed helpers appended to the program.
* defaultdict(list): a class holding a key -> slot dict, the keys in order and the rows (list[list[T]]);
  `d[k]` is `d.vals[slot(d, k)]` (the slot is created on first use, in insertion order).
* deque: a ring buffer class (power-of-two capacity, head index, optional maxlen) with typed helper
  functions; O(1) at both ends.
* Anything else is refused by name with a note (ReRefused-style), and the source is left as written so
  the compiler's import refusal prints the notes.
"""
import ast
import re
import copy

SCALARS = ('int', 'float', 'str', 'bool')
ZERO = {'int': '0', 'float': '0.0', 'str': '""', 'bool': 'False'}
KEYS = ('int', 'str')
ELEMS = ('int', 'float', 'str', 'bool')
ROWS = ('int', 'float', 'str')
NAMES = ('defaultdict', 'Counter', 'deque', 'OrderedDict')
BUILT = ('Counter(iterable or mapping) / update(iterable or mapping) / most_common / elements / total / + - & | / '
         'print; defaultdict(int|float|str|list|lambda: <constant>) with str or int keys; deque with int, float, '
         'str or bool elements (append, appendleft, pop, popleft, extend, extendleft, rotate, clear, count, '
         'index, remove, insert, reverse, copy, len, indexing, in, iteration, maxlen=); OrderedDict with '
         'move_to_end(k) and popitem(); str or int keys, int, float or str values (list[int|float|str] rows for '
         'defaultdict(list)). Not built: namedtuple, ChainMap, UserDict, defaultdict(set|bool|<container>), '
         'tuple keys or elements, deque slicing, == on collections, collections in class fields or module '
         'globals')


KIND_NAMES = {'ctr': 'Counter', 'dds': 'defaultdict', 'ddl': 'defaultdict(list)', 'od': 'OrderedDict',
              'dq': 'deque'}


def tname(t):
    if isinstance(t, tuple):
        return {'tuple': 'a tuple', 'list': 'a list', 'set': 'a set', 'dict': 'a dict', 'obj': 'an object'}.get(
            t[0], t[0])
    return str(t)


def kind_name(c):
    return 'defaultdict(set)' if c.kind == 'ddl' and c.sets else KIND_NAMES[c.kind]


class Refused(Exception):
    pass


class C:
    """A collections object: kind ctr | dds (defaultdict of scalars) | ddl (defaultdict(list)) | od | dq."""
    def __init__(self, kind, K=None, V=None, default=None, sets=False):
        self.kind, self.K, self.V, self.default, self.sets = kind, K, V, default, sets

    def sig(self):
        return (self.kind, self.K, self.V, self.sets)

    def __repr__(self):
        return 'C%r' % (self.sig(),)

    def complete(self):
        if self.kind == 'dq':
            return self.V is not None
        return self.K is not None and self.V is not None


# --------------------------------------------------------------------------------------------------
# the typed helpers appended to a program (Python subset; @K key type, @T element type, @V value type,
# @Z zero of T, @ZK zero of K)
T_CTR_NEW = '''def _ail_ctr_new_@K(xs: list[@K]) -> dict[@K, int]:
    c: dict[@K, int] = {}
    for x in xs:
        c[x] = c.get(x, 0) + 1
    return c
'''
T_CTR_CHARS = '''def _ail_ctr_chars(s: str) -> dict[str, int]:
    c: dict[str, int] = {}
    for x in s:
        c[x] = c.get(x, 0) + 1
    return c
'''
T_CTR_MC = '''def _ail_ctr_mc_@K(c: dict[@K, int], n: int) -> list[@K]:
    ks = list(c)
    vs = list(c.values())
    order = [i for i in range(len(ks))]
    order.sort(key=lambda i: -vs[i])
    out: list[@K] = []
    m = len(ks)
    if n < m:
        m = n
    for j in range(m):
        out.append(ks[order[j]])
    return out
'''
T_CTR_ELEMS = '''def _ail_ctr_elems_@K(c: dict[@K, int]) -> list[@K]:
    out: list[@K] = []
    for k in c:
        for i in range(c[k]):
            out.append(k)
    return out
'''
T_CTR_ARITH = {
    '+': '''def _ail_ctr_add_@K(a: dict[@K, int], b: dict[@K, int]) -> dict[@K, int]:
    r: dict[@K, int] = {}
    for k in a:
        n = a[k] + b.get(k, 0)
        if n > 0:
            r[k] = n
    for k in b:
        if k not in a and b[k] > 0:
            r[k] = b[k]
    return r
''',
    '-': '''def _ail_ctr_sub_@K(a: dict[@K, int], b: dict[@K, int]) -> dict[@K, int]:
    r: dict[@K, int] = {}
    for k in a:
        n = a[k] - b.get(k, 0)
        if n > 0:
            r[k] = n
    for k in b:
        if k not in a and b[k] < 0:
            r[k] = 0 - b[k]
    return r
''',
    '&': '''def _ail_ctr_and_@K(a: dict[@K, int], b: dict[@K, int]) -> dict[@K, int]:
    r: dict[@K, int] = {}
    for k in a:
        o = b.get(k, 0)
        n = a[k]
        if o < n:
            n = o
        if n > 0:
            r[k] = n
    return r
''',
    '|': '''def _ail_ctr_or_@K(a: dict[@K, int], b: dict[@K, int]) -> dict[@K, int]:
    r: dict[@K, int] = {}
    for k in a:
        o = b.get(k, 0)
        n = a[k]
        if n < o:
            n = o
        if n > 0:
            r[k] = n
    for k in b:
        if k not in a and b[k] > 0:
            r[k] = b[k]
    return r
'''}
T_CTR_EQ = '''def _ail_ctr_eq_@K(a: dict[@K, int], b: dict[@K, int]) -> bool:
    for k in a:
        if a[k] != b.get(k, 0):
            return False
    for k in b:
        if b[k] != a.get(k, 0):
            return False
    return True
'''
T_CTR_REPR = '''def _ail_ctr_repr_@K(c: dict[@K, int]) -> str:
    if len(c) == 0:
        return "Counter()"
    ks = _ail_ctr_mc_@K(c, len(c))
    parts: list[str] = []
    for k in ks:
        parts.append(f"{k@R}: {c[k]}")
    return "Counter({" + ", ".join(parts) + "})"
'''
T_OD_FIRST = '''def _ail_od_first_@K_@V(d: dict[@K, @V]) -> @K:
    for k in d:
        return k
    raise KeyError("dictionary is empty")
'''
T_OD_LAST = '''def _ail_od_last_@K_@V(d: dict[@K, @V]) -> @K:
    r = @ZK
    found = False
    for k in d:
        r = k
        found = True
    if not found:
        raise KeyError("dictionary is empty")
    return r
'''

T_DQ = '''class _AilDeque_@T:
    def __init__(self, buf: list[@T], head: int, n: int, maxlen: int):
        self.buf = buf
        self.head = head
        self.n = n
        self.maxlen = maxlen


def _ail_dq_alloc_@T(n: int) -> list[@T]:
    return @ALLOC


def _ail_dq_new_@T(maxlen: int) -> _AilDeque_@T:
    return _AilDeque_@T(_ail_dq_alloc_@T(8), 0, 0, maxlen)


def _ail_dq_grow_@T(q: _AilDeque_@T) -> None:
    cap = len(q.buf)
    nb = _ail_dq_alloc_@T(cap * 2)
    j = q.head
    for i in range(q.n):
        nb[i] = q.buf[j]
        j = (j + 1) & (cap - 1)
    q.buf = nb
    q.head = 0


def _ail_dq_append_@T(q: _AilDeque_@T, x: @T) -> None:
    if q.maxlen >= 0:
        if q.maxlen == 0:
            return
        if q.n == q.maxlen:
            q.head = (q.head + 1) & (len(q.buf) - 1)
            q.n -= 1
    if q.n == len(q.buf):
        _ail_dq_grow_@T(q)
    q.buf[(q.head + q.n) & (len(q.buf) - 1)] = x
    q.n += 1


def _ail_dq_appendleft_@T(q: _AilDeque_@T, x: @T) -> None:
    if q.maxlen >= 0:
        if q.maxlen == 0:
            return
        if q.n == q.maxlen:
            q.n -= 1
    if q.n == len(q.buf):
        _ail_dq_grow_@T(q)
    q.head = (q.head - 1) & (len(q.buf) - 1)
    q.buf[q.head] = x
    q.n += 1


def _ail_dq_pop_@T(q: _AilDeque_@T) -> @T:
    if q.n == 0:
        raise IndexError("pop from an empty deque")
    q.n -= 1
    return q.buf[(q.head + q.n) & (len(q.buf) - 1)]


def _ail_dq_popleft_@T(q: _AilDeque_@T) -> @T:
    if q.n == 0:
        raise IndexError("pop from an empty deque")
    x = q.buf[q.head]
    q.head = (q.head + 1) & (len(q.buf) - 1)
    q.n -= 1
    return x


def _ail_dq_get_@T(q: _AilDeque_@T, i: int) -> @T:
    j = i
    if j < 0:
        j += q.n
    if j < 0 or j >= q.n:
        raise IndexError("deque index out of range")
    return q.buf[(q.head + j) & (len(q.buf) - 1)]


def _ail_dq_set_@T(q: _AilDeque_@T, i: int, x: @T) -> None:
    j = i
    if j < 0:
        j += q.n
    if j < 0 or j >= q.n:
        raise IndexError("deque index out of range")
    q.buf[(q.head + j) & (len(q.buf) - 1)] = x


def _ail_dq_list_@T(q: _AilDeque_@T) -> list[@T]:
    out = _ail_dq_alloc_@T(q.n)
    j = q.head
    mask = len(q.buf) - 1
    for i in range(q.n):
        out[i] = q.buf[j]
        j = (j + 1) & mask
    return out


def _ail_dq_fill_@T(q: _AilDeque_@T, xs: list[@T]) -> None:
    q.n = 0
    q.head = 0
    for x in xs:
        _ail_dq_append_@T(q, x)


def _ail_dq_from_@T(xs: list[@T], maxlen: int) -> _AilDeque_@T:
    q = _ail_dq_new_@T(maxlen)
    for x in xs:
        _ail_dq_append_@T(q, x)
    return q


def _ail_dq_extend_@T(q: _AilDeque_@T, xs: list[@T]) -> None:
    for x in xs:
        _ail_dq_append_@T(q, x)


def _ail_dq_extendleft_@T(q: _AilDeque_@T, xs: list[@T]) -> None:
    for x in xs:
        _ail_dq_appendleft_@T(q, x)


def _ail_dq_clear_@T(q: _AilDeque_@T) -> None:
    q.n = 0
    q.head = 0


def _ail_dq_rotate_@T(q: _AilDeque_@T, k: int) -> None:
    if q.n < 2:
        return
    r = k % q.n
    if r == 0:
        return
    if r <= q.n - r:
        for i in range(r):
            _ail_dq_appendleft_@T(q, _ail_dq_pop_@T(q))
    else:
        for i in range(q.n - r):
            _ail_dq_append_@T(q, _ail_dq_popleft_@T(q))


def _ail_dq_in_@T(q: _AilDeque_@T, x: @T) -> bool:
    j = q.head
    mask = len(q.buf) - 1
    for i in range(q.n):
        if q.buf[j] == x:
            return True
        j = (j + 1) & mask
    return False


def _ail_dq_count_@T(q: _AilDeque_@T, x: @T) -> int:
    c = 0
    j = q.head
    mask = len(q.buf) - 1
    for i in range(q.n):
        if q.buf[j] == x:
            c += 1
        j = (j + 1) & mask
    return c


def _ail_dq_index_@T(q: _AilDeque_@T, x: @T) -> int:
    j = q.head
    mask = len(q.buf) - 1
    for i in range(q.n):
        if q.buf[j] == x:
            return i
        j = (j + 1) & mask
    raise ValueError(f"{x@R} is not in deque")


def _ail_dq_remove_@T(q: _AilDeque_@T, x: @T) -> None:
    xs = _ail_dq_list_@T(q)
    for i in range(len(xs)):
        if xs[i] == x:
            xs.pop(i)
            _ail_dq_fill_@T(q, xs)
            return
    raise ValueError("deque.remove(x): x not in deque")


def _ail_dq_insert_@T(q: _AilDeque_@T, i: int, x: @T) -> None:
    if q.maxlen >= 0 and q.n >= q.maxlen:
        raise IndexError("deque already at its maximum size")
    xs = _ail_dq_list_@T(q)
    xs.insert(i, x)
    _ail_dq_fill_@T(q, xs)


def _ail_dq_del_@T(q: _AilDeque_@T, i: int) -> None:
    j = i
    if j < 0:
        j += q.n
    if j < 0 or j >= q.n:
        raise IndexError("deque index out of range")
    xs = _ail_dq_list_@T(q)
    xs.pop(j)
    _ail_dq_fill_@T(q, xs)


def _ail_dq_reverse_@T(q: _AilDeque_@T) -> None:
    xs = _ail_dq_list_@T(q)
    xs.reverse()
    _ail_dq_fill_@T(q, xs)


def _ail_dq_copy_@T(q: _AilDeque_@T) -> _AilDeque_@T:
    return _ail_dq_from_@T(_ail_dq_list_@T(q), q.maxlen)


def _ail_dq_repr_@T(q: _AilDeque_@T) -> str:
    parts: list[str] = []
    xs = _ail_dq_list_@T(q)
    for x in xs:
        parts.append(f"{x@R}")
    s = "deque([" + ", ".join(parts) + "]"
    if q.maxlen >= 0:
        s += f", maxlen={q.maxlen}"
    return s + ")"
'''

T_DDL = '''class _AilDDL_@K_@T:
    def __init__(self, idx: dict[@K, int], keys: list[@K], vals: list[list[@T]]):
        self.idx = idx
        self.keys = keys
        self.vals = vals


def _ail_ddl_new_@K_@T() -> _AilDDL_@K_@T:
    return _AilDDL_@K_@T({}, [], [])


def _ail_ddl_slot_@K_@T(d: _AilDDL_@K_@T, k: @K) -> int:
    s = d.idx.get(k, -1)
    if s < 0:
        s = len(d.keys)
        d.idx[k] = s
        d.keys.append(k)
        d.vals.append([])
    return s


def _ail_ddl_get_@K_@T(d: _AilDDL_@K_@T, k: @K, default: list[@T]) -> list[@T]:
    s = d.idx.get(k, -1)
    if s < 0:
        return default
    return d.vals[s]


def _ail_ddl_clear_@K_@T(d: _AilDDL_@K_@T) -> None:
    d.idx.clear()
    d.keys.clear()
    d.vals.clear()
'''

# defaultdict(set): the rows are lists in insertion order, membership is a set of "slot:element" strings
T_DSS = '''class _AilDSS_@K_@T:
    def __init__(self, idx: dict[@K, int], keys: list[@K], vals: list[list[@T]], members: set[str]):
        self.idx = idx
        self.keys = keys
        self.vals = vals
        self.members = members


def _ail_dss_new_@K_@T() -> _AilDSS_@K_@T:
    return _AilDSS_@K_@T({}, [], [], set())


def _ail_dss_slot_@K_@T(d: _AilDSS_@K_@T, k: @K) -> int:
    s = d.idx.get(k, -1)
    if s < 0:
        s = len(d.keys)
        d.idx[k] = s
        d.keys.append(k)
        d.vals.append([])
    return s


def _ail_dss_add_@K_@T(d: _AilDSS_@K_@T, k: @K, x: @T) -> None:
    s = _ail_dss_slot_@K_@T(d, k)
    m = str(s) + ":" + @XS
    if m not in d.members:
        d.members.add(m)
        d.vals[s].append(x)


def _ail_dss_has_@K_@T(d: _AilDSS_@K_@T, k: @K, x: @T) -> bool:
    s = _ail_dss_slot_@K_@T(d, k)
    return (str(s) + ":" + @XS) in d.members


def _ail_dss_discard_@K_@T(d: _AilDSS_@K_@T, k: @K, x: @T) -> None:
    s = _ail_dss_slot_@K_@T(d, k)
    m = str(s) + ":" + @XS
    if m in d.members:
        d.members.remove(m)
        d.vals[s].remove(x)


def _ail_dss_remove_@K_@T(d: _AilDSS_@K_@T, k: @K, x: @T) -> None:
    s = _ail_dss_slot_@K_@T(d, k)
    m = str(s) + ":" + @XS
    if m not in d.members:
        raise KeyError(f"{x@R}")
    d.members.remove(m)
    d.vals[s].remove(x)


def _ail_dss_update_@K_@T(d: _AilDSS_@K_@T, k: @K, xs: list[@T]) -> None:
    for x in xs:
        _ail_dss_add_@K_@T(d, k, x)


def _ail_dss_clear_@K_@T(d: _AilDSS_@K_@T) -> None:
    d.idx.clear()
    d.keys.clear()
    d.vals.clear()
    d.members.clear()
'''


def _blocks(template):
    out = {}
    for block in template.split('\n\n\n'):
        m = re.match(r'(?:def|class) ([\w@]+)', block)
        out[m.group(1)] = block
    return out


DQ_BLOCKS = _blocks(T_DQ)
DDL_BLOCKS = _blocks(T_DDL)
DSS_BLOCKS = _blocks(T_DSS)


def fill(template, **names):
    for key in sorted(names, key=len, reverse=True):
        template = template.replace('@' + key, names[key])
    return template


def _reprsuffix(t):
    return '!r' if t == 'str' else ''


# --------------------------------------------------------------------------------------------------
def _offsets(data):
    starts = [0]
    starts.extend(i + 1 for i, byte in enumerate(data) if byte == 10)
    return starts


def _basename(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _elts(node):
    return node.elts if isinstance(node, ast.Tuple) else [node]


def _pure(node):
    """No call except the cheap str/int builtins and methods: evaluating it twice changes nothing."""
    ok_calls = {'str', 'int', 'len', 'abs', 'min', 'max', 'ord', 'chr', 'float'}
    ok_methods = {'lower', 'upper', 'strip', 'lstrip', 'rstrip', 'title', 'casefold', 'capitalize', 'join',
                  'replace', 'rjust', 'ljust', 'zfill', 'format'}
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            if isinstance(n.func, ast.Name) and n.func.id in ok_calls:
                continue
            if isinstance(n.func, ast.Attribute) and n.func.attr in ok_methods:
                continue
            return False
        if isinstance(n, (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.NamedExpr,
                          ast.Await, ast.Yield)):
            return False
    return True


def _stores(node, name):
    """The statements of `node` that rebind `name`."""
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and n.id == name and not isinstance(n.ctx, ast.Load):
            return True
    return False


class Rewriter:
    def __init__(self, source, tree):
        self.source = source
        self.data = source.encode('utf8')
        self.starts = _offsets(self.data)
        self.tree = tree
        self.edits = []
        self.notes = []
        self.helpers = {}
        self.alias = {}           # local name -> collections/typing class name
        self.modules = {}         # local module name -> 'collections' | 'typing'
        self.classes = {}         # class name -> {field: type}
        self.sigs = {}            # function name -> ([param annotation nodes], return node)
        self.ddl_sigs = set()     # (K, T) of the defaultdict(list)s, for params written as Dict[K, List[T]]
        self.fresh = 0

    # -- notes / edits ------------------------------------------------------------------------
    def note(self, node, message):
        entry = (getattr(node, 'lineno', 1), message)
        if entry not in self.notes:
            self.notes.append(entry)

    def refuse(self, node, message):
        raise Refused((getattr(node, 'lineno', 1), message))

    def span(self, node):
        return (self.starts[node.lineno - 1] + node.col_offset, self.starts[node.end_lineno - 1] + node.end_col_offset)

    def replace(self, node, text, statement=False):
        start, end = self.span(node)
        self.edits.append((start, end, text, statement))

    def apply(self):
        data = self.data
        floor = len(data) + 1
        for start, end, text, statement in sorted(self.edits, key=lambda e: (e[0], e[1]), reverse=True):
            if end > floor:
                continue
            missing = data[start:end].count(b'\n') - text.count('\n')
            if missing > 0:
                text = text + '\n' * missing if statement else '(' + text + '\n' * missing + ')'
            data = data[:start] + text.encode('utf8') + data[end:]
            floor = start
        out = data.decode('utf8')
        if self.helpers:
            out = out.rstrip('\n') + '\n\n\n' + '\n\n'.join(self.helpers.values())
        return out

    def helper(self, name, text):
        if name not in self.helpers:
            self.helpers[name] = text.rstrip('\n') + '\n'
        return name

    def new_name(self, base):
        self.fresh += 1
        return '_ail_%s%d' % (base, self.fresh)

    # -- imports ------------------------------------------------------------------------------
    def collect_imports(self):
        found = False
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name in ('collections', 'typing'):
                        self.modules[a.asname or a.name] = a.name
                    if a.name == 'collections':
                        found = True
                    if a.name.startswith('collections.'):
                        found = True
                        self.note(node, 'import %s: only `import collections` or `from collections import ...` '
                                  'is built' % a.name)
            elif isinstance(node, ast.ImportFrom) and not node.level:
                if node.module == 'collections':
                    found = True
                    for a in node.names:
                        if a.name in NAMES:
                            self.alias[a.asname or a.name] = a.name
                        elif a.name == 'namedtuple':
                            self.note(node, 'from collections import namedtuple: namedtuple is not built -- its '
                                      'fields carry no types and a tuple is not a value here; write a @dataclass '
                                      'with annotated fields (or a class with __init__)')
                        else:
                            self.note(node, 'from collections import %s: not built; ' % a.name + BUILT)
                elif node.module == 'typing':
                    for a in node.names:
                        if a.name in ('Counter', 'DefaultDict', 'Deque', 'OrderedDict'):
                            self.alias.setdefault(a.asname or a.name,
                                                  {'DefaultDict': 'defaultdict', 'Deque': 'deque'}.get(a.name, a.name))
        return found

    def kind_of(self, node):
        """'defaultdict' | 'Counter' | 'deque' | 'OrderedDict' for a name that stands for it, else None."""
        if isinstance(node, ast.Name):
            return self.alias.get(node.id)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            module = self.modules.get(node.value.id)
            if module == 'collections' and node.attr in NAMES:
                return node.attr
            if module == 'typing' and node.attr in ('Counter', 'DefaultDict', 'Deque', 'OrderedDict'):
                return {'DefaultDict': 'defaultdict', 'Deque': 'deque'}.get(node.attr, node.attr)
        return None

    # -- types --------------------------------------------------------------------------------
    def ann_type(self, node):
        """The type an annotation spells (scalars, ('list', T), ('set', T), ('dict', K, V), a C), else None."""
        if node is None:
            return None
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            try:
                node = ast.parse(node.value, mode='eval').body
            except SyntaxError:
                return None
        if isinstance(node, ast.Name):
            kind = self.kind_of(node)
            if kind:
                return self.bare_type(kind)
            if node.id in SCALARS:
                return node.id
            if node.id in self.classes:
                return ('obj', node.id)
            return None
        if isinstance(node, ast.Attribute):
            kind = self.kind_of(node)
            return self.bare_type(kind) if kind else None
        if not isinstance(node, ast.Subscript):
            return None
        kind = self.kind_of(node.value)
        base = _basename(node.value)
        args = [self.ann_type(a) for a in _elts(node.slice)]
        if kind == 'Counter':
            return C('ctr', args[0], 'int') if len(args) == 1 else None
        if kind == 'deque':
            return C('dq', None, args[0]) if len(args) == 1 else None
        if kind == 'OrderedDict':
            return C('od', args[0], args[1]) if len(args) == 2 else None
        if kind == 'defaultdict':
            if len(args) != 2:
                return None
            if isinstance(args[1], tuple) and args[1][0] == 'list':
                return C('ddl', args[0], args[1][1])
            if isinstance(args[1], tuple) and args[1][0] == 'set':
                return C('ddl', args[0], args[1][1], sets=True)
            return C('dds', args[0], args[1], ZERO.get(args[1]) if isinstance(args[1], str) else None)
        if base in ('list', 'List') and len(args) == 1:
            return ('list', args[0])
        if base in ('set', 'Set') and len(args) == 1:
            return ('set', args[0])
        if base in ('dict', 'Dict') and len(args) == 2:
            if isinstance(args[1], tuple) and args[1][0] in ('list', 'set') \
                    and (args[0], args[1][1], args[1][0] == 'set') in self.ddl_sigs:
                return C('ddl', args[0], args[1][1], sets=args[1][0] == 'set')
            return ('dict', args[0], args[1])
        return None

    def bare_type(self, kind):
        if kind == 'Counter':
            return C('ctr', None, 'int')
        if kind == 'deque':
            return C('dq')
        if kind == 'OrderedDict':
            return C('od')
        return C('dds')

    def type_text(self, c):
        """The annotation text a collection variable gets after the rewrite."""
        if c.kind in ('ctr', 'dds', 'od'):
            return 'dict[%s, %s]' % (c.K, c.V)
        if c.kind == 'dq':
            return '_AilDeque_%s' % c.V
        return '_Ail%s_%s_%s' % ('DSS' if c.sets else 'DDL', c.K, c.V)

    def check_c(self, node, c):
        """Refuse the element types that are not built."""
        if c.kind == 'dq':
            if c.V not in ELEMS:
                self.refuse(node, 'deque elements must be int, float, str or bool (found %s); tuples and '
                            'containers as deque elements are not built -- encode a pair as one int '
                            '(r * width + c) or keep two deques' % tname(c.V))
            return
        if c.K not in KEYS:
            self.refuse(node, '%s keys must be str or int (found %s); a tuple or float key is not built -- '
                        'use an int or a str built from the parts' % (
                            {'ctr': 'Counter', 'dds': 'defaultdict', 'ddl': 'defaultdict', 'od': 'OrderedDict'}[c.kind],
                            tname(c.K)))
        if c.kind == 'ddl' and c.sets and c.V not in KEYS:
            self.refuse(node, 'defaultdict(set) elements must be int or str (found %s)' % tname(c.V))
        if c.kind == 'ddl' and not c.sets and c.V not in ROWS:
            self.refuse(node, 'defaultdict(list) rows must be list[int], list[float] or list[str] (found %s)' % tname(c.V))
        if c.kind in ('dds', 'od') and c.V not in ('int', 'float', 'str'):
            self.refuse(node, '%s values must be int, float or str (found %s); defaultdict(bool), nested '
                        'containers and other value types are not built' % (
                            'defaultdict' if c.kind == 'dds' else 'OrderedDict', tname(c.V)))

    # -- expression types ---------------------------------------------------------------------
    def elem_of(self, t):
        if isinstance(t, C):
            return t.V if t.kind == 'dq' else t.K
        if t == 'str':
            return 'str'
        if isinstance(t, tuple):
            if t[0] in ('list', 'set'):
                return t[1]
            if t[0] == 'range':
                return 'int'
            if t[0] == 'dict':
                return t[1]
        return None

    def infer(self, e, env):
        t = type(e)
        if t is ast.Constant:
            v = e.value
            if isinstance(v, bool):
                return 'bool'
            if isinstance(v, int):
                return 'int'
            if isinstance(v, float):
                return 'float'
            if isinstance(v, str):
                return 'str'
            return None
        if t is ast.JoinedStr:
            return 'str'
        if t is ast.Name:
            return env.get(e.id)
        if t is ast.UnaryOp:
            if isinstance(e.op, ast.Not):
                return 'bool'
            x = self.infer(e.operand, env)
            return 'int' if x == 'bool' else x if x in ('int', 'float') else None
        if t is ast.BinOp:
            a, b = self.infer(e.left, env), self.infer(e.right, env)
            if isinstance(a, C) and isinstance(b, C) and a.kind == 'ctr' == b.kind \
                    and isinstance(e.op, (ast.Add, ast.Sub, ast.BitAnd, ast.BitOr)):
                return C('ctr', a.K, 'int')
            num = ('int', 'float', 'bool')
            if a == 'str' and isinstance(e.op, ast.Mod):
                return 'str'
            if a == 'str' and b == 'str' and isinstance(e.op, ast.Add):
                return 'str'
            if a == 'str' and b in ('int', 'bool') and isinstance(e.op, ast.Mult):
                return 'str'
            if isinstance(a, tuple) and a[0] == 'list' and a == b and isinstance(e.op, ast.Add):
                return a
            if a in num and b in num:
                if isinstance(e.op, ast.Div):
                    return 'float'
                return 'float' if 'float' in (a, b) else 'int'
            return None
        if t in (ast.Compare,):
            return 'bool'
        if t is ast.BoolOp:
            ts = [self.infer(v, env) for v in e.values]
            return ts[0] if all(x == ts[0] for x in ts) else None
        if t is ast.IfExp:
            return self.infer(e.body, env) or self.infer(e.orelse, env)
        if t is ast.List:
            for x in e.elts:
                tx = self.infer(x, env)
                if tx in SCALARS or (isinstance(tx, tuple) and tx[0] in ('list', 'tuple')):
                    return ('list', tx)
            return None
        if t is ast.Tuple:
            return ('tuple',)
        if t is ast.Set:
            tx = self.infer(e.elts[0], env) if e.elts else None
            return ('set', tx) if tx in SCALARS else None
        if t in (ast.ListComp, ast.SetComp, ast.GeneratorExp):
            inner = dict(env)
            for g in e.generators:
                self.bind(g.target, g.iter, inner)
            tx = self.infer(e.elt, inner)
            if tx in SCALARS:
                return ('set' if t is ast.SetComp else 'list', tx)
            return None
        if t is ast.Subscript:
            base = self.infer(e.value, env)
            if isinstance(base, C):
                if base.kind == 'ddl':
                    return ('list', base.V)
                if base.kind in ('dq',):
                    return base.V
                return base.V
            if base == 'str':
                return 'str'
            if isinstance(base, tuple):
                if base[0] == 'list':
                    return base if isinstance(e.slice, ast.Slice) else base[1]
                if base[0] == 'dict':
                    return base[2]
            return None
        if t is ast.Attribute:
            base = self.infer(e.value, env)
            if isinstance(base, tuple) and base[0] == 'obj':
                return self.classes.get(base[1], {}).get(e.attr)
            if isinstance(e.value, ast.Name) and e.value.id == 'sys' and e.attr == 'maxsize':
                return 'int'
            return None
        if t is ast.Call:
            return self.infer_call(e, env)
        return None

    def infer_call(self, e, env):
        f = e.func
        args = e.args
        if self.kind_of(f) is not None:
            try:
                return self.ctor_c(e, env)
            except Refused:
                return None
        if isinstance(f, ast.Name):
            n = f.id
            if n in ('len', 'int', 'ord', 'hash') or (n == 'round' and len(args) == 1):
                return 'int'
            if n in ('float',):
                return 'float'
            if n in ('str', 'chr', 'repr', 'input', 'format', 'ascii', 'bin', 'hex', 'oct'):
                return 'str'
            if n in ('bool', 'any', 'all', 'isinstance', 'callable'):
                return 'bool'
            if n == 'abs' and args:
                return self.infer(args[0], env)
            if n in ('min', 'max', 'sum') and args:
                if len(args) == 1:
                    return self.elem_of(self.infer(args[0], env)) or ('int' if n == 'sum' else None)
                return self.infer(args[0], env)
            if n in ('sorted', 'list', 'reversed') and args:
                el = self.elem_of(self.infer(args[0], env))
                return ('list', el) if el in SCALARS else None
            if n == 'set' and args:
                el = self.elem_of(self.infer(args[0], env))
                return ('set', el) if el in SCALARS else None
            if n == 'range':
                return ('range',)
            if n in self.sigs:
                return self.ann_type(self.sigs[n][1])
            if n in self.classes:
                return ('obj', n)
            return None
        if isinstance(f, ast.Attribute):
            m = f.attr
            if isinstance(f.value, ast.Name) and f.value.id == 'math':
                return 'int' if m in ('floor', 'ceil', 'gcd', 'isqrt', 'factorial', 'trunc') else 'float'
            if isinstance(f.value, ast.Attribute) and isinstance(f.value.value, ast.Name) \
                    and f.value.value.id == 'sys' and f.value.attr == 'stdin' and m in ('read', 'readline'):
                return 'str'
            base = self.infer(f.value, env)
            if isinstance(base, C):
                if m == 'copy':
                    return copy.copy(base)
                if m in ('get', 'pop', 'popleft', 'setdefault') and base.kind != 'ddl':
                    return base.V
                if m == 'total':
                    return 'int'
                if m == 'elements':
                    return ('list', base.K)
                if m in ('index', 'count'):
                    return 'int'
                if m in ('keys',):
                    return ('list', base.K)
                if m in ('values',):
                    return ('list', base.V) if base.kind != 'ddl' else None
                return None
            if base == 'str' or (isinstance(f.value, ast.Constant) and isinstance(f.value.value, str)):
                if m in ('split', 'rsplit', 'splitlines'):
                    return ('list', 'str')
                if m in ('strip', 'lstrip', 'rstrip', 'lower', 'upper', 'title', 'capitalize', 'replace', 'join',
                         'format', 'center', 'ljust', 'rjust', 'zfill', 'removeprefix', 'removesuffix',
                         'swapcase', 'casefold'):
                    return 'str'
                if m in ('find', 'rfind', 'index', 'rindex', 'count'):
                    return 'int'
                if m.startswith('is') or m in ('startswith', 'endswith'):
                    return 'bool'
                return None
            if isinstance(base, tuple):
                if base[0] == 'list':
                    if m == 'pop':
                        return base[1]
                    if m in ('index', 'count'):
                        return 'int'
                    if m == 'copy':
                        return base
                if base[0] == 'dict':
                    if m == 'get' and len(args) == 2:
                        return base[2]
                if base[0] == 'obj':
                    return None
        return None

    def bind(self, target, iterable, env):
        """Types of loop variables."""
        itype = self.infer(iterable, env)
        if isinstance(iterable, ast.Attribute) and isinstance(iterable.value, ast.Name) \
                and iterable.value.id == 'sys' and iterable.attr == 'stdin':
            itype = ('list', 'str')
        if isinstance(target, ast.Name):
            el = None
            if isinstance(iterable, ast.Call) and isinstance(iterable.func, ast.Attribute):
                base = self.infer(iterable.func.value, env)
                m = iterable.func.attr
                if isinstance(base, C):
                    if m == 'keys':
                        el = base.K
                    elif m == 'values':
                        el = base.V if base.kind != 'ddl' else None
            if el is None:
                el = self.elem_of(itype)
            if el is not None:
                env.setdefault(target.id, el)
            return
        if isinstance(target, ast.Tuple) and len(target.elts) == 2 and all(isinstance(x, ast.Name) for x in target.elts):
            a, b = target.elts
            pair = None
            if isinstance(iterable, ast.Call):
                f = iterable.func
                if isinstance(f, ast.Attribute) and f.attr in ('items', 'most_common'):
                    base = self.infer(f.value, env)
                    if isinstance(base, C):
                        pair = (base.K, base.V if base.kind != 'ddl' else None)
                    elif isinstance(base, tuple) and base[0] == 'dict':
                        pair = (base[1], base[2])
                elif isinstance(f, ast.Name) and f.id == 'enumerate' and iterable.args:
                    pair = ('int', self.elem_of(self.infer(iterable.args[0], env)))
            for name, t in zip((a, b), pair or (None, None)):
                if t is not None:
                    env.setdefault(name.id, t)

    # -- collections constructors -------------------------------------------------------------
    def factory(self, node, call):
        """(kind, V, default text) for the first argument of defaultdict(...)."""
        if call is None:
            self.refuse(node, 'defaultdict() without a factory is a plain dict that raises KeyError; write {}')
        if isinstance(call, ast.Constant) and call.value is None:
            self.refuse(node, 'defaultdict(None) is a plain dict; write {}')
        if isinstance(call, ast.Name):
            if call.id in ('int', 'float', 'str'):
                return ('dds', call.id, ZERO[call.id], False)
            if call.id == 'list':
                return ('ddl', None, None, False)
            if call.id == 'set':
                return ('ddl', None, None, True)
            if call.id == 'bool':
                self.refuse(node, 'defaultdict(bool): bool values in a dict are not built; count with int')
            if call.id in ('dict', 'deque', 'Counter', 'defaultdict'):
                self.refuse(node, 'defaultdict(%s): a container as the default value is not built here; only '
                            'defaultdict(int|float|str|list|set) and lambda: <constant> are (use a dict from the '
                            'key to an index into a list of such containers)' % call.id)
            self.refuse(node, 'defaultdict(%s): the factory is not built; the factories built are int, float, str, '
                        'list and lambda: <constant>' % call.id)
        if isinstance(call, ast.Lambda) and not call.args.args:
            body = call.body
            if isinstance(body, ast.List) and not body.elts:
                return ('ddl', None, None, False)
            if isinstance(body, ast.Call) and isinstance(body.func, ast.Name) and body.func.id == 'set' \
                    and not body.args and not body.keywords:
                return ('ddl', None, None, True)
            if isinstance(body, ast.UnaryOp) and isinstance(body.op, (ast.USub, ast.UAdd)) \
                    and isinstance(body.operand, ast.Constant) and type(body.operand.value) in (int, float):
                v = -body.operand.value if isinstance(body.op, ast.USub) else body.operand.value
                return ('dds', type(v).__name__, repr(v), False)
            if isinstance(body, ast.Constant) and type(body.value) in (int, float, str):
                return ('dds', type(body.value).__name__, repr(body.value), False)
        self.refuse(node, 'defaultdict(%s): only int, float, str, list and lambda: <constant> (or lambda: []) are '
                    'built as the factory' % ast.unparse(call))

    def ctor_c(self, call, env, ctx=None):
        """The C a constructor call builds; K / V parts unknown stay None."""
        kind = self.kind_of(call.func)
        args = call.args
        if kind == 'Counter':
            if call.keywords:
                self.refuse(call, 'Counter(key=count, ...) is not built')
            if len(args) > 1:
                self.refuse(call, 'Counter takes one iterable or mapping')
            c = C('ctr', None, 'int')
            if args:
                t = self.infer(args[0], env)
                if isinstance(t, C) and t.kind in ('ctr', 'dds', 'od'):
                    c.K = t.K
                elif isinstance(t, tuple) and t[0] == 'dict':
                    c.K = t[1]
                else:
                    c.K = self.elem_of(t)
            return c
        if kind == 'OrderedDict':
            if args or call.keywords:
                self.refuse(call, 'OrderedDict(...) with arguments is not built; start from OrderedDict() and '
                            'assign')
            return C('od')
        if kind == 'defaultdict':
            if call.keywords:
                self.refuse(call, 'defaultdict(..., key=...) is not built')
            if len(args) > 1:
                self.refuse(call, 'defaultdict(factory, mapping) is not built; build it empty and assign')
            k, v, default, sets = self.factory(call, args[0] if args else None)
            return C(k, None, v, default, sets)
        if kind == 'deque':
            c = C('dq')
            if len(args) > 2:
                self.refuse(call, 'deque takes an iterable and maxlen')
            if args:
                c.V = self.elem_of(self.infer(args[0], env))
            return c
        return None

    # -- helper registry per C ----------------------------------------------------------------
    def emit(self, blocks, key, **subs):
        """Register the helper block `key` (a name with @-placeholders) and what it uses."""
        name = fill(key, **subs)
        if name in self.helpers:
            return name
        text = blocks[key]
        self.helpers[name] = None             # claimed (breaks cycles)
        self.helpers[name] = fill(text, **subs).rstrip('\n') + '\n'
        for other in blocks:
            if other != key and other in text:
                self.emit(blocks, other, **subs)
        return name

    def need_dq(self, t):
        return self.emit(DQ_BLOCKS, '_AilDeque_@T', **self.dq_subs(t))

    def dq_subs(self, t):
        alloc = '["" for i in range(n)]' if t == 'str' else '[%s] * n' % ZERO[t]
        return dict(T=t, Z=ZERO[t], R=_reprsuffix(t), ALLOC=alloc)

    def dq(self, c, op):
        return self.emit(DQ_BLOCKS, '_ail_dq_%s_@T' % op, **self.dq_subs(c.V))

    def ddl(self, c, op):
        self.ddl_sigs.add((c.K, c.V, c.sets))
        if c.sets:
            return self.emit(DSS_BLOCKS, '_ail_dss_%s_@K_@T' % op, K=c.K, T=c.V,
                             XS='str(x)' if c.V == 'int' else 'x', R=_reprsuffix(c.V))
        return self.emit(DDL_BLOCKS, '_ail_ddl_%s_@K_@T' % op, K=c.K, T=c.V)

    def ctr(self, k, op, text):
        name = '_ail_ctr_%s_%s' % (op, k)
        self.helper(name, fill(text, K=k, R=_reprsuffix(k)))
        return name

    def ctr_mc(self, c):
        return self.ctr(c.K, 'mc', T_CTR_MC)

    # -- run ----------------------------------------------------------------------------------
    def run(self):
        found = self.collect_imports()
        if not found:
            return None
        for node in self.tree.body:
            if isinstance(node, ast.ClassDef):
                self.classes[node.name] = self.class_fields(node)
        for node in self.tree.body:
            if isinstance(node, ast.FunctionDef):
                self.sigs[node.name] = ([a.annotation for a in node.args.args], node.returns)
        # analysis to a fixpoint (a Dict[K, List[T]] parameter is a defaultdict(list) once one is built)
        for _ in range(3):
            before = set(self.ddl_sigs)
            self.scopes = {}
            for node in self.functions():
                self.scopes[node] = Scope(self, node)
                self.scopes[node].analyse()
            if self.ddl_sigs == before:
                break
        self.module_check()
        for node, scope in self.scopes.items():
            scope.rewrite()
        self.imports()
        return self.apply()

    def functions(self):
        out = []

        def walk(body):
            for node in body:
                if isinstance(node, ast.FunctionDef):
                    out.append(node)
                elif isinstance(node, ast.ClassDef):
                    walk(node.body)
        walk(self.tree.body)
        return out

    def class_fields(self, node):
        fields = {}
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                if self.mentions_collection(item.annotation) or (
                        item.value is not None and self.mentions_collection(item.value)):
                    self.note(item, 'a collections type in a class field is not built: keep the collection in a '
                              'local variable (or a list / dict / dataclass of plain types)')
                fields[item.target.id] = self.ann_type(item.annotation)
            elif isinstance(item, ast.FunctionDef) and item.name == '__init__':
                params = {a.arg: a.annotation for a in item.args.args[1:]}
                for st in ast.walk(item):
                    if isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Attribute) \
                            and isinstance(st.targets[0].value, ast.Name) and st.targets[0].value.id == 'self':
                        if self.mentions_collection(st.value):
                            self.note(st, 'a collections object stored in an attribute is not built: keep the '
                                      'collection in a local variable')
                        v = st.value
                        if isinstance(v, ast.Name) and v.id in params:
                            fields[st.targets[0].attr] = self.ann_type(params[v.id])
        return fields

    def mentions_collection(self, node):
        for n in ast.walk(node):
            if (isinstance(n, (ast.Name, ast.Attribute)) and self.kind_of(n)):
                return True
        return False

    def module_check(self):
        """Collections at module level / in decorators are not built."""
        for node in self.tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)):
                continue
            if self.mentions_collection(node):
                self.note(node, 'a collections object at module level is not built (module scope is constants '
                          'only): create it inside a function')

    def imports(self):
        for node in self.tree.body:
            if isinstance(node, ast.Import):
                kept = [a for a in node.names if a.name not in ('collections',)]
                if len(kept) != len(node.names):
                    self.replace(node, 'import ' + ', '.join(
                        a.name + (' as ' + a.asname if a.asname else '') for a in kept) if kept else 'pass', True)
            elif isinstance(node, ast.ImportFrom) and not node.level and node.module == 'collections':
                self.replace(node, 'pass', True)
            elif isinstance(node, ast.ImportFrom) and not node.level and node.module == 'typing':
                names = [a for a in node.names if a.name not in ('Counter', 'DefaultDict', 'Deque', 'OrderedDict')]
                if len(names) != len(node.names):
                    self.replace(node, 'from typing import ' + ', '.join(
                        a.name + (' as ' + a.asname if a.asname else '') for a in names) if names else 'pass', True)


class Scope:
    """One function: the types of its names, its collections, and the rewrite of its statements."""
    MUTATORS_DICT = ('pop', 'popitem', 'clear', 'update', 'setdefault', 'move_to_end', 'subtract')
    MUTATORS_DQ = ('append', 'appendleft', 'pop', 'popleft', 'extend', 'extendleft', 'clear', 'rotate', 'remove',
                   'insert', 'reverse')
    ITER_FUNCS = ('list', 'sorted', 'set', 'sum', 'min', 'max', 'any', 'all', 'enumerate', 'reversed', 'tuple',
                  'zip', 'map', 'filter', 'frozenset')

    def __init__(self, r, fn):
        self.r = r
        self.fn = fn
        self.env = {}
        self.params = set()
        self.first = {}           # name -> the first binding statement (gets the annotation)
        self.subst = {}
        self.boolnames = set()

    # -- analysis -----------------------------------------------------------------------------
    def own(self):
        """Statements of the function, nested blocks included, not nested defs."""
        out = []

        def walk(body):
            for st in body:
                out.append(st)
                if isinstance(st, (ast.FunctionDef, ast.ClassDef)):
                    continue
                for field in ('body', 'orelse', 'finalbody'):
                    walk(getattr(st, field, []) or [])
                for h in getattr(st, 'handlers', []) or []:
                    walk(h.body)
        walk(self.fn.body)
        return out

    def analyse(self):
        r = self.r
        args = self.fn.args
        for a in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
            t = r.ann_type(a.annotation)
            if t is not None:
                self.env[a.arg] = copy.copy(t) if isinstance(t, C) else t
            self.params.add(a.arg)
        stmts = self.own()
        # two sweeps: types of names in order, then the collections' missing parts from their uses
        for sweep in range(3):
            for st in stmts:
                self.declare(st)
            for c in self.colls():
                self.resolve(c)
        for c in self.colls():
            if c.kind == 'ddl' and c.complete():
                r.ddl_sigs.add((c.K, c.V, c.sets))

    def colls(self):
        seen = []
        for v in self.env.values():
            if isinstance(v, C) and v not in seen:
                seen.append(v)
        return seen

    def declare(self, st):
        r, env = self.r, self.env
        if isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name):
            name = st.targets[0].id
            value = st.value
            t = None
            if isinstance(value, ast.Call) and r.kind_of(value.func):
                try:
                    old = env.get(name)
                    t = old if isinstance(old, C) else r.ctor_c(value, env)
                    if isinstance(old, C):
                        fresh = r.ctor_c(value, env)
                        self.merge(old, fresh)
                except Refused as exc:
                    r.note(st, exc.args[0][1])
                    return
                self.first.setdefault(name, st)
            else:
                t = r.infer(value, env)
                if isinstance(t, C):
                    t = t if name in env and env[name] is t else copy.copy(t) if isinstance(value, ast.Call) else t
                if t is not None:
                    self.first.setdefault(name, st)
            if t is not None and name not in env:
                env[name] = t
        elif isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name):
            name = st.target.id
            t = r.ann_type(st.annotation)
            if st.value is not None and isinstance(st.value, ast.Call) and r.kind_of(st.value.func):
                # the constructor decides the kind; the annotation (also a plain Dict[K, V]) gives its types
                try:
                    c = r.ctor_c(st.value, env)
                except Refused as exc:
                    r.note(st, exc.args[0][1])
                    return
                if isinstance(t, tuple) and t[0] == 'dict':
                    t = C(c.kind, t[1], t[2][1] if c.kind == 'ddl' and isinstance(t[2], tuple) else t[2],
                          c.default, c.sets)
                elif isinstance(t, tuple) and t[0] == 'list':
                    t = None
                if isinstance(t, C):
                    if t.kind == 'dds' and c.kind == 'dds':
                        t.default = c.default
                    self.merge(c, t)
                old = env.get(name)
                if isinstance(old, C):
                    self.merge(old, c)
                else:
                    env[name] = c
                self.first.setdefault(name, st)
            elif isinstance(t, C):
                if name in env and isinstance(env[name], C):
                    self.merge(env[name], t)
                else:
                    env[name] = t
                self.first.setdefault(name, st)
            elif t is not None:
                env.setdefault(name, t)
        elif isinstance(st, ast.For):
            self.r.bind(st.target, st.iter, env)
        elif isinstance(st, ast.With):
            pass

    def merge(self, old, new):
        if new is None or old is new:
            return
        if old.kind != new.kind or old.sets != new.sets:
            self.r.note(self.fn, 'a name is bound to a %s and to a %s in %s(); give them different names' % (
                old.kind, new.kind, self.fn.name))
            return
        for field in ('K', 'V', 'default'):
            a, b = getattr(old, field), getattr(new, field)
            if a is None and b is not None:
                setattr(old, field, b)
            elif b is not None and a != b and field != 'default':
                self.r.note(self.fn, 'one collection is used with two %s types (%s and %s) in %s()' % (
                    'element' if field == 'V' else 'key', a, b, self.fn.name))

    def hint(self, c, field, t, node):
        if t in SCALARS or t == ('tuple',) or (field == 'K' and t is not None and not isinstance(t, C)):
            cur = getattr(c, field)
            if cur is None:
                setattr(c, field, t)

    def resolve(self, c):
        """Fill the key / element type of `c` from the way the function uses it."""
        r, env = self.r, self.env
        names = [n for n, v in env.items() if v is c]
        if not names or c.complete():
            return
        for n in ast.walk(self.fn):
            # c[k] ... : the key
            if isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name) and n.value.id in names \
                    and c.kind != 'dq':
                if c.K is None:
                    self.hint(c, 'K', r.infer(n.slice, env), n)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
                f = n.func
                recv = f.value
                if isinstance(recv, ast.Name) and recv.id in names:
                    m = f.attr
                    if c.kind == 'dq' and n.args:
                        if m in ('append', 'appendleft', 'remove', 'count', 'index'):
                            self.hint(c, 'V', r.infer(n.args[0], env), n)
                        elif m in ('extend', 'extendleft'):
                            self.hint(c, 'V', r.elem_of(r.infer(n.args[0], env)), n)
                        elif m == 'insert' and len(n.args) == 2:
                            self.hint(c, 'V', r.infer(n.args[1], env), n)
                    if c.kind == 'ctr' and m == 'update' and n.args:
                        t = r.infer(n.args[0], env)
                        if isinstance(t, C) and t.kind in ('ctr', 'dds', 'od'):
                            self.hint(c, 'K', t.K, n)
                        elif isinstance(t, tuple) and t[0] == 'dict':
                            self.hint(c, 'K', t[1], n)
                        else:
                            self.hint(c, 'K', r.elem_of(t), n)
                    if c.kind in ('dds', 'od', 'ctr') and m in ('get', 'setdefault', 'pop') and n.args:
                        self.hint(c, 'K', r.infer(n.args[0], env), n)
                        if c.kind == 'od' and len(n.args) == 2:
                            self.hint(c, 'V', r.infer(n.args[1], env), n)
                    if c.kind == 'ddl' and m in ('get', 'setdefault') and n.args:
                        self.hint(c, 'K', r.infer(n.args[0], env), n)
                # c[k].append(x) / .extend(xs) on a defaultdict(list)
                if c.kind == 'ddl' and isinstance(recv, ast.Subscript) and isinstance(recv.value, ast.Name) \
                        and recv.value.id in names and n.args:
                    if f.attr in ('append', 'add', 'discard', 'remove'):
                        self.hint(c, 'V', r.infer(n.args[0], env), n)
                    elif f.attr == 'update':
                        self.hint(c, 'V', r.elem_of(r.infer(n.args[0], env)), n)
                    elif f.attr in ('extend', 'insert'):
                        arg = n.args[-1] if f.attr == 'insert' else n.args[0]
                        t = r.infer(arg, env)
                        self.hint(c, 'V', t if f.attr == 'insert' else r.elem_of(t), n)
            if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Subscript):
                tg = n.targets[0]
                if isinstance(tg.value, ast.Name) and tg.value.id in names:
                    if c.kind == 'od':
                        self.hint(c, 'V', r.infer(n.value, env), n)
                    if c.kind == 'ddl':
                        t = r.infer(n.value, env)
                        if isinstance(t, tuple) and t[0] == 'list':
                            self.hint(c, 'V', t[1], n)
                    if c.kind == 'dds' and c.V is None:
                        pass
            if isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Subscript) \
                    and isinstance(n.target.value, ast.Name) and n.target.value.id in names:
                if c.kind == 'ddl' and isinstance(n.op, ast.Add):
                    t = r.infer(n.value, env)
                    if isinstance(t, tuple) and t[0] == 'list':
                        self.hint(c, 'V', t[1], n)
                if c.kind == 'od':
                    self.hint(c, 'V', r.infer(n.value, env), n)
        if c.kind in ('dds', 'ctr') and c.V is None:
            c.V = 'int' if c.kind == 'ctr' else c.V

    # -- rewriting ----------------------------------------------------------------------------
    def rewrite(self):
        r = self.r
        fn = self.fn
        try:
            for c in self.colls():
                if not c.complete():
                    r.refuse(fn, 'the element / key type of a collection in %s() cannot be told from how it is '
                             'used; annotate it (for example `counts: Counter[str] = Counter()`)' % fn.name)
                r.check_c(fn, c)
            self.signature()
            self.block(fn.body)
        except Refused as exc:
            entry = exc.args[0]
            if entry not in r.notes:
                r.notes.append(entry)

    def signature(self):
        r = self.r
        args = self.fn.args
        for a in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
            self.annotation(a.annotation)
        self.annotation(self.fn.returns)

    def annotation(self, node):
        r = self.r
        if node is None:
            return
        t = r.ann_type(node)
        if isinstance(t, C):
            if not t.complete():
                r.refuse(node, 'a collections annotation needs its type arguments (for example Counter[str], '
                         'deque[int], defaultdict[str, int])')
            r.check_c(node, t)
            r.replace(node, self.type_name(t))
        elif r.mentions_collection(node):
            r.refuse(node, 'a collection inside another container type (%s) is not built' % ast.unparse(node))

    def type_name(self, c):
        r = self.r
        if c.kind == 'dq':
            r.need_dq(c.V)
        elif c.kind == 'ddl':
            r.ddl(c, 'new')
        return r.type_text(c)

    # statements
    def block(self, body):
        for st in body:
            self.stmt(st)

    def mark_test(self, e):
        if isinstance(e, ast.Name):
            self.boolnames.add(id(e))
        elif isinstance(e, ast.UnaryOp) and isinstance(e.op, ast.Not):
            self.mark_test(e.operand)
        elif isinstance(e, ast.BoolOp):
            for v in e.values:
                self.mark_test(v)

    def mark(self, tree):
        """Names of collections in a boolean position, and the ddl.get() calls whose result is only read."""
        test = self.mark_test
        for n in ast.walk(tree):
            if isinstance(n, (ast.If, ast.While, ast.IfExp, ast.Assert)):
                test(n.test)
            elif isinstance(n, ast.comprehension):
                for t in n.ifs:
                    test(t)
                if isinstance(n.iter, ast.Call):
                    self.readonly.add(id(n.iter))
            elif isinstance(n, ast.For) and isinstance(n.iter, ast.Call):
                self.readonly.add(id(n.iter))
            elif isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not):
                test(n.operand)
            elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and (
                    n.func.id in self.ITER_FUNCS or n.func.id == 'len'):
                for a in n.args:
                    if isinstance(a, ast.Call):
                        self.readonly.add(id(a))
            elif isinstance(n, ast.Compare):
                for op, comp in zip(n.ops, n.comparators):
                    if isinstance(op, (ast.In, ast.NotIn)) and isinstance(comp, ast.Call):
                        self.readonly.add(id(comp))
            elif isinstance(n, ast.Subscript) and isinstance(n.ctx, ast.Load) and isinstance(n.value, ast.Call):
                self.readonly.add(id(n.value))

    boolnames = None
    readonly = None

    def hoist_counters(self, tree):
        """Counter(...) in the middle of an expression becomes a temporary bound just before the statement (a dict
        built by a call cannot be walked or indexed inline)."""
        scope = self

        class Hoist(ast.NodeTransformer):
            depth = 0

            def nested(self, node):
                self.depth += 1
                self.generic_visit(node)
                self.depth -= 1
                return node

            visit_Lambda = nested

            def comprehension(self, node):
                # the first iterable is evaluated once, in the enclosing scope
                node.generators[0].iter = self.visit(node.generators[0].iter)
                self.depth += 1
                for i, g in enumerate(node.generators):
                    if i:
                        g.iter = self.visit(g.iter)
                    g.ifs = [self.visit(c) for c in g.ifs]
                for field in ('elt', 'key', 'value'):
                    if hasattr(node, field):
                        setattr(node, field, self.visit(getattr(node, field)))
                self.depth -= 1
                return node

            visit_ListComp = visit_SetComp = visit_DictComp = visit_GeneratorExp = comprehension

            def visit_Call(self, node):
                if scope.r.kind_of(node.func) != 'Counter':
                    self.generic_visit(node)
                    return node
                node.args = [self.visit(a) for a in node.args]
                if self.depth:
                    scope.r.refuse(node, 'Counter(...) inside a comprehension or lambda is built when it is bound '
                                   'to a name outside it')
                return scope.bind_counter(node)

        return Hoist().visit(tree)

    def bind_counter(self, call):
        r = self.r
        c = r.ctor_c(call, self.env)
        if c is None or not c.complete():
            r.refuse(call, 'the key type of this Counter cannot be told; bind it to an annotated name first '
                     '(for example `counts: Counter[str] = Counter(...)`)')
        r.check_c(call, c)
        name = r.new_name('c')
        self.env[name] = c
        expr = _X(self).visit_ctor(copy.deepcopy(call), c, self)
        self.pre.append('%s: %s = %s' % (name, r.type_text(c), ast.unparse(expr)))
        return ast.Name(id=name, ctx=ast.Load())

    def xform(self, node, boolean=False, read_only=False):
        self.boolnames = set()
        self.readonly = set()
        new = self.hoist_counters(copy.deepcopy(node))
        self.mark(new)
        if boolean:
            self.mark_test(new)
        if read_only:
            self.readonly.add(id(new))
        out = _X(self).visit(new)
        return out

    def put(self, node, new):
        text = ast.unparse(new)
        if not isinstance(new, _ATOMIC):
            text = '(' + text + ')'
        self.r.replace(node, text)

    def put_stmt(self, st, text):
        """Replace a simple statement; bindings hoisted out of its expressions go first on the same line."""
        if self.pre:
            text = '; '.join([*self.pre, text])
            self.pre = []
        self.r.replace(st, text, True)

    def whole(self, st):
        new = self.xform(st)
        if ast.dump(new) != ast.dump(st) or self.pre:
            self.put_stmt(st, ast.unparse(new))

    def part(self, node, boolean=False):
        """Rewrite one expression of a compound statement's header in place."""
        if node is None:
            return
        new = self.xform(node, boolean)
        if self.pre:
            self.r.refuse(node, 'this expression needs a temporary (a helper result walked inline); bind the '
                          'collection to a name first and use that in the condition')
        if ast.dump(new) != ast.dump(node):
            self.put(node, new)

    pre = ()

    def stmt(self, st):
        r = self.r
        self.pre = []
        if isinstance(st, (ast.FunctionDef, ast.ClassDef)):
            return
        if isinstance(st, ast.Assign):
            return self.assign(st)
        if isinstance(st, ast.AnnAssign):
            return self.annassign(st)
        if isinstance(st, ast.AugAssign):
            return self.augassign(st)
        if isinstance(st, ast.Expr):
            return self.expr_stmt(st)
        if isinstance(st, ast.Delete):
            return self.delete(st)
        if isinstance(st, ast.For):
            return self.for_(st)
        if isinstance(st, (ast.If, ast.While)):
            self.part(st.test, True)
            self.block(st.body)
            self.block(st.orelse)
            return
        if isinstance(st, ast.Return):
            return self.return_(st)
        if isinstance(st, ast.With):
            for item in st.items:
                self.part(item.context_expr)
            self.block(st.body)
            return
        if isinstance(st, ast.Try):
            self.block(st.body)
            for h in st.handlers:
                self.block(h.body)
            self.block(st.orelse)
            self.block(st.finalbody)
            return
        self.whole(st)

    def coll(self, node):
        if isinstance(node, ast.Name):
            v = self.env.get(node.id)
            if isinstance(v, C):
                return v
        return None

    def is_ctor(self, node):
        return isinstance(node, ast.Call) and self.r.kind_of(node.func) is not None

    def keytext(self, node, k):
        if not _pure(k):
            self.r.refuse(node, 'the key expression %s is evaluated twice by this rewrite; bind it to a name first '
                          '(key = ...; d[key] ...)' % ast.unparse(k))

    # -- assignment ---------------------------------------------------------------------------
    def annotated(self, st, name):
        return self.first.get(name) is st

    def assign(self, st):
        r = self.r
        if len(st.targets) != 1:
            return self.whole(st)
        tg = st.targets[0]
        value = st.value
        if isinstance(tg, ast.Name):
            c = self.env.get(tg.id)
            if self.is_ctor(value) and isinstance(c, C):
                expr = _X(self, ctor_for=c).visit_ctor(copy.deepcopy(value), c, self)
                text = ast.unparse(expr)
                if self.annotated(st, tg.id):
                    text = '%s: %s = %s' % (tg.id, self.type_name(c), text)
                else:
                    text = '%s = %s' % (tg.id, text)
                self.put_stmt(st, text)
                return
            if isinstance(c, C) and not self.is_ctor(value):
                # an alias, a copy(), a call returning a collection, a Counter sum
                if isinstance(value, ast.Name) and self.coll(value) is not None:
                    text = value.id                      # y = x : the same object under two names
                else:
                    text = ast.unparse(self.xform(value))
                if self.annotated(st, tg.id) and c.kind in ('ctr', 'dds', 'od'):
                    text = '%s: %s = %s' % (tg.id, self.type_name(c), text)
                else:
                    text = '%s = %s' % (tg.id, text)
                self.put_stmt(st, text)
                return
            return self.whole(st)
        if isinstance(tg, ast.Subscript):
            c = self.coll(tg.value)
            if c is not None and c.kind in ('ddl', 'dq'):
                return self.subscript_store(st, tg, c, value)
            return self.whole(st)
        if isinstance(tg, ast.Tuple) and isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute) \
                and value.func.attr == 'popitem' and self.coll(value.func.value) is not None:
            return self.popitem_unpack(st, tg, value)
        return self.whole(st)

    def subscript_store(self, st, tg, c, value):
        r = self.r
        if c.kind == 'ddl' and c.sets:
            r.refuse(st, 'assigning to d[k] on a defaultdict(set) is not built; use d[k].add(x) / d[k].update(xs)')
        if c.kind == 'ddl':
            if not isinstance(value, (ast.List, ast.ListComp, ast.Call, ast.BinOp)):
                r.refuse(st, 'd[k] = <list name>: CPython stores the same list object, so later changes through '
                         'either name show in both; store a copy (d[k] = list(xs)) or build it in place')
            new = self.xform(ast.Assign(targets=[tg], value=value, lineno=st.lineno))
            return self.put_stmt(st, ast.unparse(new))
        # deque item store
        self.keytext(st, tg.slice)
        x = self.xform(value)
        k = self.xform(tg.slice)
        recv = tg.value
        call = ast.Expr(value=ast.Call(func=ast.Name(id=r.dq(c, 'set'), ctx=ast.Load()), args=[recv, k, x], keywords=[]))
        self.put_stmt(st, ast.unparse(call))

    def annassign(self, st):
        r = self.r
        tg = st.target
        if not isinstance(tg, ast.Name):
            return self.whole(st)
        c = self.env.get(tg.id)
        if isinstance(c, C):
            if st.value is None:
                r.refuse(st, 'a collections variable declared without a value is not built: assign the %s' % (
                    'constructor'))
            if self.is_ctor(st.value):
                expr = _X(self).visit_ctor(copy.deepcopy(st.value), c, self)
            else:
                expr = self.xform(st.value)
            text = '%s: %s = %s' % (tg.id, self.type_name(c), ast.unparse(expr))
            self.put_stmt(st, text)
            return
        if r.mentions_collection(st.annotation):
            r.refuse(st, 'a collection inside another container type (%s) is not built' % ast.unparse(st.annotation))
        self.whole(st)

    def augassign(self, st):
        r = self.r
        tg = st.target
        op = st.op
        if isinstance(tg, ast.Subscript):
            c = self.coll(tg.value)
            if c is not None:
                recv = tg.value
                if c.kind in ('ctr', 'dds'):
                    self.keytext(st, tg.slice)
                    k = self.xform(tg.slice)
                    v = self.xform(st.value)
                    default = ast.parse(c.default if c.kind == 'dds' else '0', mode='eval').body
                    if c.kind == 'dds' and tg.value.id in self.params:
                        r.refuse(st, 'd[k] += v on a defaultdict parameter changes the caller\'s dict; a dict '
                                 'parameter is read-only here -- return the new values or keep the dict in the caller')
                    new = ast.Assign(targets=[ast.Subscript(value=recv, slice=k, ctx=ast.Store())],
                                     value=ast.BinOp(left=ast.Call(func=ast.Attribute(value=recv, attr='get', ctx=ast.Load()),
                                                                   args=[k, default], keywords=[]),
                                                     op=op, right=v), lineno=st.lineno)
                    return self.put_stmt(st, ast.unparse(new))
                if c.kind == 'ddl' and c.sets:
                    r.refuse(st, 'd[k] |= ... on a defaultdict(set) is not built; use d[k].update(xs)')
                if c.kind == 'ddl':
                    if not isinstance(op, ast.Add):
                        r.refuse(st, 'only d[k] += <list> is built on a defaultdict(list) row')
                    k = self.xform(tg.slice)
                    v = self.xform(st.value)
                    row = ast.Subscript(value=ast.Attribute(value=recv, attr='vals', ctx=ast.Load()),
                                        slice=ast.Call(func=ast.Name(id=r.ddl(c, 'slot'), ctx=ast.Load()),
                                                       args=[recv, k], keywords=[]), ctx=ast.Load())
                    new = ast.Expr(value=ast.Call(func=ast.Attribute(value=row, attr='extend', ctx=ast.Load()),
                                                  args=[v], keywords=[]))
                    return self.put_stmt(st, ast.unparse(new))
                if c.kind == 'dq':
                    self.keytext(st, tg.slice)
                    k = self.xform(tg.slice)
                    v = self.xform(st.value)
                    get = ast.Call(func=ast.Name(id=r.dq(c, 'get'), ctx=ast.Load()), args=[recv, k], keywords=[])
                    new = ast.Expr(value=ast.Call(func=ast.Name(id=r.dq(c, 'set'), ctx=ast.Load()),
                                                  args=[recv, k, ast.BinOp(left=get, op=op, right=v)], keywords=[]))
                    return self.put_stmt(st, ast.unparse(new))
            return self.whole(st)
        if isinstance(tg, ast.Name):
            c = self.env.get(tg.id)
            if isinstance(c, C):
                if c.kind == 'ctr' and isinstance(op, (ast.Add, ast.Sub, ast.BitAnd, ast.BitOr)):
                    v = self.xform(st.value)
                    new = ast.Assign(targets=[ast.Name(id=tg.id, ctx=ast.Store())],
                                     value=ast.BinOp(left=ast.Name(id=tg.id, ctx=ast.Load()), op=op, right=v),
                                     lineno=st.lineno)
                    new = _X(self).visit(new)
                    return self.put_stmt(st, ast.unparse(new))
                r.refuse(st, '%s= on a %s is not built' % (ast.unparse(op), c.kind))
        self.whole(st)

    def delete(self, st):
        r = self.r
        if len(st.targets) == 1 and isinstance(st.targets[0], ast.Subscript):
            tg = st.targets[0]
            c = self.coll(tg.value)
            if c is not None:
                k = self.xform(tg.slice)
                if c.kind == 'ctr':
                    # Counter.__delitem__ ignores a missing key
                    new = ast.Expr(value=ast.Call(func=ast.Attribute(value=tg.value, attr='pop', ctx=ast.Load()),
                                                  args=[k, ast.Constant(value=0)], keywords=[]))
                    return self.put_stmt(st, ast.unparse(new))
                if c.kind == 'dq':
                    new = ast.Expr(value=ast.Call(func=ast.Name(id=r.dq(c, 'del'), ctx=ast.Load()),
                                                  args=[tg.value, k], keywords=[]))
                    return self.put_stmt(st, ast.unparse(new))
                if c.kind == 'ddl':
                    r.refuse(st, 'del d[k] on a defaultdict(list) is not built (the rows are kept by slot)')
        if len(st.targets) > 1 and any(isinstance(tg, ast.Subscript) and self.coll(tg.value) is not None
                                       for tg in st.targets):
            r.refuse(st, 'del of several items at once on a collection is not built')
        self.whole(st)

    def return_(self, st):
        r = self.r
        v = st.value
        c = self.coll(v) if v is not None else None
        if c is None and self.is_ctor(v):
            c = r.ctor_c(v, self.env)
            if c is not None and c.complete():
                self.put_stmt(st, 'return ' + ast.unparse(_X(self).visit_ctor(copy.deepcopy(v), c, self)))
        if c is not None:
            t = r.ann_type(self.fn.returns)
            if not isinstance(t, C) or t.kind != c.kind or (t.K, t.V) != (c.K, c.V):
                r.refuse(st, '%s() returns a %s: annotate its result with the same collections type (for example '
                         '-> Counter[str]) so the caller gets the same kind of object' % (self.fn.name, c.kind))
            return
        self.whole(st)

    def expr_stmt(self, st):
        r = self.r
        call = st.value
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute):
            c = self.coll(call.func.value)
            if c is not None:
                m = call.func.attr
                recv = call.func.value
                if c.kind == 'ctr' and m == 'update':
                    return self.ctr_update(st, c, call)
                if c.kind == 'od' and m == 'move_to_end':
                    return self.move_to_end(st, c, call)
                if c.kind in ('od', 'dds', 'ctr') and m == 'popitem':
                    last = self.popitem_last(st, call)
                    k = ast.Call(func=ast.Name(id=self.od_helper(c, last), ctx=ast.Load()), args=[recv], keywords=[])
                    new = ast.Delete(targets=[ast.Subscript(value=recv, slice=k, ctx=ast.Del())])
                    return self.put_stmt(st, ast.unparse(new))
        self.whole(st)

    def od_helper(self, c, last):
        r = self.r
        if last:
            name = '_ail_od_last_%s_%s' % (c.K, c.V)
            r.helper(name, fill(T_OD_LAST, K=c.K, V=c.V, ZK=ZERO[c.K]))
        else:
            name = '_ail_od_first_%s_%s' % (c.K, c.V)
            r.helper(name, fill(T_OD_FIRST, K=c.K, V=c.V))
        return name

    def popitem_last(self, st, call):
        r = self.r
        last = True
        if call.args and call.keywords or len(call.args) > 1:
            r.refuse(st, 'popitem(last=...) takes the keyword or one positional argument')
        node = call.args[0] if call.args else None
        for kw in call.keywords:
            if kw.arg != 'last':
                r.refuse(st, 'popitem takes only last=')
            node = kw.value
        if node is not None:
            if not (isinstance(node, ast.Constant) and isinstance(node.value, bool)):
                r.refuse(st, 'popitem(last=...) needs True or False written out')
            last = node.value
        return last

    def popitem_unpack(self, st, tg, call):
        r = self.r
        c = self.coll(call.func.value)
        if c.kind not in ('od', 'dds', 'ctr') or len(tg.elts) != 2 or not all(isinstance(x, ast.Name) for x in tg.elts):
            r.refuse(st, 'popitem() is built as `k, v = d.popitem(last=...)` or as a statement on a dict-like '
                     'collections object')
        last = self.popitem_last(st, call)
        recv = call.func.value
        k, v = tg.elts
        first = ast.Assign(targets=[ast.Name(id=k.id, ctx=ast.Store())],
                           value=ast.Call(func=ast.Name(id=self.od_helper(c, last), ctx=ast.Load()), args=[recv], keywords=[]),
                           lineno=st.lineno)
        second = ast.Assign(targets=[ast.Name(id=v.id, ctx=ast.Store())],
                            value=ast.Call(func=ast.Attribute(value=recv, attr='pop', ctx=ast.Load()),
                                           args=[ast.Name(id=k.id, ctx=ast.Load())], keywords=[]), lineno=st.lineno)
        self.put_stmt(st, ast.unparse(first) + '; ' + ast.unparse(second))

    def ctr_update(self, st, c, call):
        r = self.r
        recv = call.func.value
        if call.keywords or len(call.args) != 1:
            r.refuse(st, 'Counter.update takes one iterable or mapping')
        arg = call.args[0]
        t = r.infer(arg, self.env)
        tmp = r.new_name('t')
        name = recv.id
        if (isinstance(t, C) and t.kind in ('ctr', 'dds', 'od')) or (isinstance(t, tuple) and t[0] == 'dict'):
            if not isinstance(arg, ast.Name):
                r.refuse(st, 'Counter.update(mapping) needs the mapping in a name')
            text = 'for %s in %s: %s[%s] = %s.get(%s, 0) + %s[%s]' % (tmp, arg.id, name, tmp, name, tmp, arg.id, tmp)
        else:
            it = self.iter_expr(arg)
            text = 'for %s in %s: %s[%s] = %s.get(%s, 0) + 1' % (tmp, ast.unparse(it), name, tmp, name, tmp)
        self.put_stmt(st, text)

    def iter_expr(self, node):
        """An iterable expression, a bare collection read as its snapshot / keys."""
        c = self.coll(node)
        if c is not None:
            return self.as_iter(c, node)
        return self.xform(node)

    def as_iter(self, c, node):
        r = self.r
        if c.kind == 'dq':
            return ast.Call(func=ast.Name(id=r.dq(c, 'list'), ctx=ast.Load()), args=[node], keywords=[])
        if c.kind == 'ddl':
            return ast.Attribute(value=node, attr='keys', ctx=ast.Load())
        return node

    def move_to_end(self, st, c, call):
        r = self.r
        if call.keywords or len(call.args) != 1:
            r.refuse(st, 'move_to_end(k) is built (last=False is not)')
        k = call.args[0]
        self.keytext(st, k)
        recv = call.func.value
        kk = self.xform(k)
        new = ast.Assign(targets=[ast.Subscript(value=recv, slice=kk, ctx=ast.Store())],
                         value=ast.Call(func=ast.Attribute(value=recv, attr='pop', ctx=ast.Load()), args=[kk], keywords=[]),
                         lineno=st.lineno)
        self.put_stmt(st, ast.unparse(new))

    # -- loops --------------------------------------------------------------------------------
    def loop_source(self, it):
        """(C, name node, how, call) when `it` loops over a collection."""
        c = self.coll(it)
        if c is not None:
            return c, it, 'bare', None
        if isinstance(it, ast.Call) and isinstance(it.func, ast.Attribute):
            c = self.coll(it.func.value)
            if c is not None and it.func.attr in ('items', 'keys', 'values', 'most_common'):
                return c, it.func.value, it.func.attr, it
        return None

    def unsafe_body(self, body, name, c, keyvars):
        """The way a loop body changes `name` (CPython raises RuntimeError), or None."""
        mut = self.MUTATORS_DQ if c.kind == 'dq' else self.MUTATORS_DICT
        for st in body:
            for n in ast.walk(st):
                if isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name) and n.value.id == name:
                    key_ok = isinstance(n.slice, ast.Name) and n.slice.id in keyvars
                    if isinstance(n.ctx, ast.Del):
                        return 'del %s[...]' % name
                    if isinstance(n.ctx, ast.Store):
                        if c.kind == 'dq':
                            continue
                        if not key_ok:
                            return '%s[...] = ... with a key that may be new' % name
                    elif c.kind in ('dds', 'ddl') and not key_ok:
                        return 'a read %s[k], which inserts a missing key' % name
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                        and isinstance(n.func.value, ast.Name) and n.func.value.id == name:
                    if n.func.attr in mut or (c.kind == 'ddl' and n.func.attr in ('clear', 'setdefault')):
                        return '%s.%s(...)' % (name, n.func.attr)
                if isinstance(n, ast.Call) and c.kind in ('dq', 'ddl') and any(
                        isinstance(a, ast.Name) and a.id == name for a in n.args):
                    if not (isinstance(n.func, ast.Name) and (n.func.id in self.ITER_FUNCS or n.func.id in ('len', 'print'))):
                        return '%s passed to a function' % name
        return None

    def for_(self, st):
        r = self.r
        it = st.iter
        if isinstance(it, ast.Call) and isinstance(it.func, ast.Attribute) and isinstance(it.func.value, ast.Call) \
                and r.kind_of(it.func.value.func) == 'Counter':
            r.refuse(st, 'a loop over Counter(...).most_common(n) is built when the Counter has a name: write '
                     '`c = Counter(...)` first, then `for key, count in c.most_common(n):`')
        src = self.loop_source(it)
        subst = {}
        new_target = st.target
        new_iter = None
        if src is not None:
            c, nm, how, call = src
            name = nm.id
            keyvars = set()
            tgt = st.target
            if how == 'items':
                if isinstance(tgt, ast.Tuple) and len(tgt.elts) == 2 and isinstance(tgt.elts[0], ast.Name):
                    keyvars.add(tgt.elts[0].id)
            elif how in ('bare', 'keys') and isinstance(tgt, ast.Name):
                keyvars.add(tgt.id)
            if c.kind == 'dq' and how != 'bare':
                r.refuse(st, 'loops over a deque are built as `for x in q:`')
            bad = self.unsafe_body(st.body, name, c, keyvars)
            if bad is not None and not (how == 'most_common'):
                r.refuse(st, 'the loop body does %s while looping over %s (CPython raises RuntimeError: '
                         'dictionary/deque changed size during iteration); loop over list(%s) instead' % (bad, name, name))
            if how == 'most_common':
                if c.kind != 'ctr':
                    r.refuse(st, 'most_common is a Counter method')
                bad = self.unsafe_body(st.body, name, c, set())
                if bad is not None:
                    r.refuse(st, 'the loop body does %s while looping over %s.most_common(): the count of the item '
                             'would be read after the change here; copy the pairs first' % (bad, name))
                if not (isinstance(tgt, ast.Tuple) and len(tgt.elts) == 2 and all(isinstance(x, ast.Name) for x in tgt.elts)):
                    r.refuse(st, 'a most_common() loop is built as `for key, count in c.most_common(n):`')
                a, b = tgt.elts
                n = self.mc_n(call)
                new_target = ast.Name(id=a.id, ctx=ast.Store())
                new_iter = ast.Call(func=ast.Name(id=r.ctr_mc(c), ctx=ast.Load()), args=[nm, n], keywords=[])
                for v in (a, b):
                    if any(_stores(s, v.id) for s in st.body):
                        r.refuse(st, 'the loop variable %s is assigned in the body; most_common loops read it' % v.id)
                subst[b.id] = ast.Call(func=ast.Attribute(value=nm, attr='get', ctx=ast.Load()),
                                       args=[ast.Name(id=a.id, ctx=ast.Load()), ast.Constant(value=0)], keywords=[])
            elif c.kind == 'ddl':
                if c.sets and how in ('items', 'values'):
                    r.refuse(st, 'looping over d.%s() of a defaultdict(set) is not built; loop `for k in d:` and use '
                             'len(d[k]) / sorted(d[k])' % how)
                if how == 'items':
                    if not (isinstance(tgt, ast.Tuple) and len(tgt.elts) == 2 and all(isinstance(x, ast.Name) for x in tgt.elts)):
                        r.refuse(st, 'items() of a defaultdict(list) is built as `for k, v in d.items():`')
                    a, b = tgt.elts
                    for v in (a, b):
                        if any(_stores(s, v.id) for s in st.body):
                            r.refuse(st, 'the loop variable %s is assigned in the body' % v.id)
                    idx = r.new_name('i')
                    new_target = ast.Name(id=idx, ctx=ast.Store())
                    new_iter = ast.Call(func=ast.Name(id='range', ctx=ast.Load()),
                                        args=[ast.Call(func=ast.Name(id='len', ctx=ast.Load()),
                                                       args=[ast.Attribute(value=nm, attr='keys', ctx=ast.Load())], keywords=[])],
                                        keywords=[])
                    subst[a.id] = ast.Subscript(value=ast.Attribute(value=nm, attr='keys', ctx=ast.Load()),
                                                slice=ast.Name(id=idx, ctx=ast.Load()), ctx=ast.Load())
                    subst[b.id] = ast.Subscript(value=ast.Attribute(value=nm, attr='vals', ctx=ast.Load()),
                                                slice=ast.Name(id=idx, ctx=ast.Load()), ctx=ast.Load())
                elif how == 'values':
                    new_iter = ast.Attribute(value=nm, attr='vals', ctx=ast.Load())
                else:
                    new_iter = ast.Attribute(value=nm, attr='keys', ctx=ast.Load())
            elif c.kind == 'dq':
                new_iter = self.as_iter(c, nm)
            elif how == 'bare':
                new_iter = copy.deepcopy(nm)
        if new_iter is None:
            new_iter = self.xform(it, read_only=True)
        else:
            self.boolnames = set()
        if self.pre:
            r.refuse(st, 'this loop header needs a temporary (for example a Counter(...) built inline); bind it '
                     'to a name on the line before')
        # rewrite the new iter's inner expressions (a most_common(n) argument ...)
        if src is not None and new_iter is not None and isinstance(new_iter, ast.Call) and src[2] == 'most_common':
            new_iter.args[1] = self.xform(new_iter.args[1])
        # the target
        t_new = st.target if new_target is st.target else new_target
        changed = ast.dump(t_new) != ast.dump(st.target) or ast.dump(new_iter) != ast.dump(it)
        if changed:
            s0 = self.r.span(st.target)[0]
            e0 = self.r.span(it)[1]
            text = '%s in %s' % (ast.unparse(t_new), ast.unparse(new_iter))
            self.r.edits.append((s0, e0, text, False))
        saved = dict(self.subst)
        self.subst.update(subst)
        self.block(st.body)
        self.subst = saved
        self.block(st.orelse)

    def mc_n(self, call):
        r = self.r
        if call.keywords:
            r.refuse(call, 'most_common(n) takes n positionally')
        if len(call.args) > 1:
            r.refuse(call, 'most_common takes at most one argument')
        if call.args:
            return _X(self).visit(copy.deepcopy(call.args[0]))
        return ast.Call(func=ast.Name(id='len', ctx=ast.Load()), args=[copy.deepcopy(call.func.value)], keywords=[])


_ATOMIC = (ast.Name, ast.Constant, ast.Call, ast.Attribute, ast.Subscript, ast.List, ast.Dict,
           ast.Set, ast.ListComp, ast.SetComp, ast.DictComp, ast.JoinedStr)
DICT_METHODS = ('get', 'setdefault', 'pop', 'keys', 'values', 'items', 'copy', 'clear')


def mk(name):
    return ast.Name(id=name, ctx=ast.Load())


def call(func, *args):
    return ast.Call(func=mk(func) if isinstance(func, str) else func, args=list(args), keywords=[])


def attr(value, name):
    return ast.Attribute(value=value, attr=name, ctx=ast.Load())


class _X(ast.NodeTransformer):
    """The expression rewrite of one statement (a deep copy) in the scope `s`."""
    def __init__(self, scope, ctor_for=None):
        self.s = scope
        self.r = scope.r
        self.env = scope.env
        if scope.boolnames is None:
            scope.boolnames = set()
        if scope.readonly is None:
            scope.readonly = set()
        self.okbare = set()

    def coll(self, node):
        return self.s.coll(node)

    def refuse(self, node, message):
        self.r.refuse(node, message)

    # names -------------------------------------------------------------------------------------
    def visit_Name(self, node):
        if not isinstance(node.ctx, ast.Load):
            return node
        if node.id in self.s.subst:
            return copy.deepcopy(self.s.subst[node.id])
        c = self.coll(node)
        if c is None:
            return node
        if id(node) in self.s.boolnames:
            return self.truth(c, node)
        if id(node) in self.okbare:
            return node
        self.refuse(node, 'the %s `%s` is used here as a plain value; a collections object is built only through '
                    'its methods, indexing, len(), in, loops, and the calls named in the reference '
                    '(%s)' % ({'ctr': 'Counter', 'dds': 'defaultdict', 'ddl': 'defaultdict(list)', 'od': 'OrderedDict',
                               'dq': 'deque'}[c.kind], node.id, 'AIL_REFERENCE_MORE.md, Collections'))

    def truth(self, c, node):
        if c.kind == 'dq':
            sub = attr(node, 'n')
        elif c.kind == 'ddl':
            sub = call('len', attr(node, 'keys'))
        else:
            sub = call('len', node)
        return ast.Compare(left=sub, ops=[ast.NotEq()], comparators=[ast.Constant(value=0)])

    def visit_Attribute(self, node):
        c = self.coll(node.value)
        if c is not None:
            if id(node.value) in self.okbare:
                return node
            if c.kind in ('ctr', 'dds', 'od') and node.attr in DICT_METHODS:
                return node
            self.refuse(node, '%s.%s used as a value is not built' % (node.value.id, node.attr))
        self.generic_visit(node)
        return node

    # constructors ------------------------------------------------------------------------------
    def visit_ctor(self, node, c, scope):
        r = self.r
        kind = r.kind_of(node.func)
        args = [self.visit_argument(a) for a in node.args]
        if c.kind == 'ctr':
            if not node.args:
                return ast.Dict(keys=[], values=[])
            t = r.infer(node.args[0], self.env)
            a = node.args[0]
            if (isinstance(t, C) and t.kind in ('ctr', 'dds', 'od')) or (isinstance(t, tuple) and t[0] == 'dict'):
                if t.kind != 'ctr' if isinstance(t, C) else t[2] != 'int':
                    r.refuse(node, 'Counter(mapping) needs int values')
                return call(attr(self.visit_argument(a), 'copy'))
            if t == 'str':
                if c.K != 'str':
                    r.refuse(node, 'Counter(str) counts characters (str keys)')
                return call(self.chars_helper(), self.visit_argument(a))
            return call(r.ctr(c.K, 'new', T_CTR_NEW), self.as_list(a, t))
        if c.kind in ('dds', 'od'):
            return ast.Dict(keys=[], values=[])
        if c.kind == 'ddl':
            return call(r.ddl(c, 'new'))
        if c.kind == 'dq':
            ml = self.maxlen(node)
            if node.args and node.args[0] is not None and len(node.args) >= 1:
                a = node.args[0]
                return call(r.dq(c, 'from'), self.as_list(a, r.infer(a, self.env)), ml)
            return call(r.dq(c, 'new'), ml)
        self.refuse(node, 'unsupported constructor')

    def chars_helper(self):
        self.r.helper('_ail_ctr_chars', T_CTR_CHARS)
        return '_ail_ctr_chars'

    def maxlen(self, node):
        r = self.r
        expr = None
        if len(node.args) == 2:
            expr = node.args[1]
        for kw in node.keywords:
            if kw.arg != 'maxlen':
                r.refuse(node, 'deque takes an iterable and maxlen=')
            expr = kw.value
        if expr is None or (isinstance(expr, ast.Constant) and expr.value is None):
            return ast.Constant(value=-1)
        if isinstance(expr, ast.Constant) and type(expr.value) is int:
            if expr.value < 0:
                r.refuse(node, 'maxlen must be non-negative')
            return expr
        r.helper('_ail_dq_maxlen', '''def _ail_dq_maxlen(n: int) -> int:
    if n < 0:
        raise ValueError("maxlen must be non-negative")
    return n
''')
        return call('_ail_dq_maxlen', self.visit(copy.deepcopy(expr)))

    def as_list(self, a, t):
        """`a` as a list expression for a helper."""
        c = self.coll(a)
        if c is not None:
            return self.visit_argument(a)
        new = self.visit(copy.deepcopy(a))
        if isinstance(a, ast.GeneratorExp):
            return ast.ListComp(elt=new.elt, generators=new.generators)
        if isinstance(a, (ast.List, ast.ListComp)) or (isinstance(t, tuple) and t[0] == 'list'):
            return new
        return call('list', new)

    def visit_argument(self, a):
        """An argument that may be a bare collection: its iterable form."""
        c = self.coll(a)
        if c is not None:
            return self.s.as_iter(c, a)
        return self.visit(a)

    # subscripts --------------------------------------------------------------------------------
    def mc_call(self, node):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'most_common':
            c = self.coll(node.func.value)
            if c is not None and c.kind == 'ctr':
                return c, node.func.value
        return None

    def visit_Subscript(self, node):
        r = self.r
        # most_common(n)[i][0] / [1]
        if isinstance(node.value, ast.Subscript) and self.mc_call(node.value.value):
            c, nm = self.mc_call(node.value.value)
            if isinstance(node.slice, ast.Constant) and node.slice.value in (0, 1) and type(node.slice.value) is int:
                n = self.s.mc_n(node.value.value)
                keys = ast.Subscript(value=call(r.ctr_mc(c), nm, n), slice=self.visit(node.value.slice), ctx=ast.Load())
                if node.slice.value == 0:
                    return keys
                return call(attr(nm, 'get'), keys, ast.Constant(value=0))
            self.refuse(node, 'most_common(n)[i] is built only as most_common(n)[i][0] (the key) or [i][1] (the count)')
        if self.mc_call(node.value):
            self.refuse(node, 'most_common(n) used as a list of pairs is built only in `for key, count in '
                        'c.most_common(n):`, comprehensions of that form, most_common(n)[i][0|1], len(), dict() and print()')
        c = self.coll(node.value)
        if c is None:
            self.generic_visit(node)
            return node
        recv = node.value
        if c.kind == 'ddl' and c.sets:
            self.refuse(node, self.SET_ROW_NOTE)
        if isinstance(node.slice, ast.Slice):
            self.refuse(node, 'slicing a %s is not built' % KIND_NAMES[c.kind])
        k = self.visit(node.slice)
        if c.kind == 'ctr':
            if isinstance(node.ctx, ast.Load):
                return call(attr(recv, 'get'), k, ast.Constant(value=0))
            node.slice = k
            return node
        if c.kind == 'dds':
            if isinstance(node.ctx, ast.Load):
                if recv.id in self.s.params:
                    self.refuse(node, 'd[k] on a defaultdict parameter would insert the missing key into the '
                                'caller\'s dict, and a dict parameter is read-only here; use d.get(k, default)')
                return call(attr(recv, 'setdefault'), k, ast.parse(c.default, mode='eval').body)
            node.slice = k
            return node
        if c.kind == 'od':
            node.slice = k
            return node
        if c.kind == 'ddl':
            if isinstance(node.ctx, ast.Del):
                self.refuse(node, 'del d[k] on a defaultdict(list) is not built')
            return ast.Subscript(value=attr(recv, 'vals'), slice=call(r.ddl(c, 'slot'), recv, k), ctx=node.ctx)
        if c.kind == 'dq':
            if isinstance(node.ctx, ast.Load):
                return call(r.dq(c, 'get'), recv, k)
            self.refuse(node, 'item assignment on a deque is built as a statement `q[i] = x`')
        return node

    # comparisons ---------------------------------------------------------------------------------
    def visit_Compare(self, node):
        r = self.r
        if len(node.ops) == 1 and isinstance(node.ops[0], (ast.Eq, ast.NotEq)):
            a = r.infer(node.left, self.env)
            b = r.infer(node.comparators[0], self.env)
            if isinstance(a, C) and isinstance(b, C) and a.kind == 'ctr' == b.kind and a.K == b.K:
                helper = '_ail_ctr_eq_%s' % a.K
                r.helper(helper, fill(T_CTR_EQ, K=a.K))
                res = call(helper, self.visit_dictlike(node.left), self.visit_dictlike(node.comparators[0]))
                return ast.UnaryOp(op=ast.Not(), operand=res) if isinstance(node.ops[0], ast.NotEq) else res
        if any(isinstance(op, (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE)) for op in node.ops):
            for side in (node.left, *node.comparators):
                if isinstance(r.infer(side, self.env), C):
                    self.refuse(node, 'comparing collections with %s is not built (== and != between two Counters '
                                'are); compare their items or lengths' % type(node.ops[0]).__name__)
        if len(node.ops) == 1 and isinstance(node.ops[0], (ast.In, ast.NotIn)) and self.set_row(node.comparators[0]):
            c, recv, key = self.set_row(node.comparators[0])
            res = call(r.ddl(c, 'has'), recv, self.visit(copy.deepcopy(key)), self.visit(node.left))
            return ast.UnaryOp(op=ast.Not(), operand=res) if isinstance(node.ops[0], ast.NotIn) else res
        if len(node.ops) == 1 and isinstance(node.ops[0], (ast.In, ast.NotIn)):
            c = self.coll(node.comparators[0])
            if c is not None:
                left = self.visit(node.left)
                recv = node.comparators[0]
                neg = isinstance(node.ops[0], ast.NotIn)
                if c.kind == 'dq':
                    res = call(r.dq(c, 'in'), recv, left)
                    return ast.UnaryOp(op=ast.Not(), operand=res) if neg else res
                if c.kind == 'ddl':
                    return ast.Compare(left=left, ops=node.ops, comparators=[attr(recv, 'idx')])
                return ast.Compare(left=left, ops=node.ops, comparators=[recv])
        self.generic_visit(node)
        return node

    def visit_BinOp(self, node):
        r = self.r
        a = r.infer(node.left, self.env)
        b = r.infer(node.right, self.env)
        if isinstance(a, C) and isinstance(b, C) and a.kind == 'ctr' == b.kind:
            op = {ast.Add: '+', ast.Sub: '-', ast.BitAnd: '&', ast.BitOr: '|'}.get(type(node.op))
            if op is None:
                self.refuse(node, 'Counter %s is not built (+ - & | are)' % type(node.op).__name__)
            if a.K != b.K:
                self.refuse(node, 'Counters with different key types')
            name = {'+': 'add', '-': 'sub', '&': 'and', '|': 'or'}[op]
            helper = '_ail_ctr_%s_%s' % (name, a.K)
            r.helper(helper, fill(T_CTR_ARITH[op], K=a.K))
            return call(helper, self.visit_dictlike(node.left), self.visit_dictlike(node.right))
        self.generic_visit(node)
        return node

    def visit_dictlike(self, node):
        c = self.coll(node)
        if c is not None:
            return node
        return self.visit(node)

    # comprehensions -----------------------------------------------------------------------------
    def hoist(self, node):
        """Bind a helper's list result to a temporary just before the statement (it cannot be walked inline)."""
        name = self.r.new_name('h')
        self.s.pre.append('%s = %s' % (name, ast.unparse(node)))
        return mk(name)

    def fix_generators(self, node):
        """`for w, n in c.most_common(k)` inside a comprehension."""
        r = self.r
        added = {}
        for g in node.generators:
            loop = self.s.loop_source(g.iter)
            if loop is not None and loop[0].kind == 'ddl':
                # a defaultdict(list) walked by position: the key / row names read the keys / vals lists
                c, nm, how, _ = loop
                if c.sets and how in ('items', 'values'):
                    self.refuse(node, 'a comprehension over d.%s() of a defaultdict(set) is not built' % how)
                idx = r.new_name('i')
                key = ast.Subscript(value=attr(nm, 'keys'), slice=mk(idx), ctx=ast.Load())
                row = ast.Subscript(value=attr(nm, 'vals'), slice=mk(idx), ctx=ast.Load())
                tgt = g.target
                if how in ('bare', 'keys') and isinstance(tgt, ast.Name):
                    added[tgt.id] = key
                elif how == 'values' and isinstance(tgt, ast.Name):
                    added[tgt.id] = row
                elif how == 'items' and isinstance(tgt, ast.Tuple) and len(tgt.elts) == 2 \
                        and all(isinstance(x, ast.Name) for x in tgt.elts):
                    added[tgt.elts[0].id] = key
                    added[tgt.elts[1].id] = row
                else:
                    self.refuse(node, 'a comprehension over a defaultdict(list) is built as `for k in d`, '
                                '`for v in d.values()` or `for k, v in d.items()`')
                self.okbare.add(id(nm))
                g.target = ast.Name(id=idx, ctx=ast.Store())
                g.iter = call('range', call('len', attr(nm, 'keys')))
                continue
            m = self.mc_call(g.iter)
            if m is not None:
                c, nm = m
                if not (isinstance(g.target, ast.Tuple) and len(g.target.elts) == 2
                        and all(isinstance(x, ast.Name) for x in g.target.elts)):
                    self.refuse(node, 'a comprehension over most_common() is built as `for key, count in c.most_common(n)`')
                a, b = g.target.elts
                n = self.s.mc_n(g.iter)
                g.iter = call(r.ctr_mc(c), nm, n)
                self.okbare.add(id(nm))
                g.target = ast.Name(id=a.id, ctx=ast.Store())
                added[b.id] = call(attr(nm, 'get'), ast.Name(id=a.id, ctx=ast.Load()), ast.Constant(value=0))
        return added

    def visit_comprehension_like(self, node):
        added = self.fix_generators(node)
        saved = dict(self.s.subst)
        self.s.subst.update(added)
        try:
            for g in node.generators:
                c = self.coll(g.iter)
                if c is not None:
                    g.iter = self.s.as_iter(c, g.iter)
                else:
                    g.iter = self.visit(g.iter)
                if isinstance(g.iter, ast.Call) and not (isinstance(g.iter.func, ast.Name) and g.iter.func.id in (
                        'range', 'enumerate', 'sorted', 'reversed', 'list', 'zip')):
                    g.iter = self.hoist(g.iter)
                elif isinstance(g.iter, ast.Attribute) and g.iter.attr in ('keys', 'vals') \
                        and self.coll(g.iter.value) is not None:
                    g.iter = self.hoist(g.iter)         # a typed local: the field's element type is not seen here
                g.ifs = [self.visit(i) for i in g.ifs]
            if isinstance(node, ast.DictComp):
                node.key = self.visit(node.key)
                node.value = self.visit(node.value)
            else:
                node.elt = self.visit(node.elt)
        finally:
            self.s.subst = saved
        return node

    visit_ListComp = visit_SetComp = visit_GeneratorExp = visit_DictComp = visit_comprehension_like

    # calls -------------------------------------------------------------------------------------
    def visit_Call(self, node):
        r = self.r
        f = node.func
        for kw in node.keywords:
            v = kw.value
            if kw.arg == 'key' and isinstance(v, ast.Attribute) and v.attr == 'get' and self.coll(v.value) is not None:
                c = self.coll(v.value)
                if c.kind in ('ctr', 'dds', 'od'):
                    # key=c.get : the keys come from c, so the lookup never misses
                    k = r.new_name('k')
                    zero = ast.parse(c.default if c.kind == 'dds' else ZERO[c.V], mode='eval').body
                    kw.value = ast.Lambda(
                        args=ast.arguments(posonlyargs=[], args=[ast.arg(arg=k)], vararg=None, kwonlyargs=[],
                                           kw_defaults=[], kwarg=None, defaults=[]),
                        body=call(attr(v.value, 'get'), mk(k), zero))
        if r.kind_of(f) is not None:
            c = r.ctor_c(node, self.env)
            if c is None or not c.complete():
                self.refuse(node, 'the element / key type of this %s cannot be told from the code around it; '
                            'assign it to an annotated name (for example `counts: Counter[str] = Counter()`)'
                            % r.kind_of(f))
            r.check_c(node, c)
            return self.visit_ctor(node, c, self.s)
        if isinstance(f, ast.Attribute):
            sr = self.set_row(f.value)
            if sr is not None:
                return self.set_method(node, sr, f.attr)
            c = self.coll(f.value)
            if c is not None:
                return self.method(node, c)
        if isinstance(f, ast.Name):
            return self.call_name(node, f.id)
        if isinstance(f, ast.Attribute) and f.attr == 'join' and len(node.args) == 1 and self.coll(node.args[0]):
            node.func = self.visit(f)
            node.args = [self.visit_argument(node.args[0])]
            return node
        self.generic_visit(node)
        return node

    def call_name(self, node, fname):
        r = self.r
        args = node.args
        # the builtins applied to the result of most_common(n)
        if len(args) == 1 and self.mc_call(args[0]):
            c, nm = self.mc_call(args[0])
            n = self.s.mc_n(args[0])
            if fname == 'len':
                return call('len', call(r.ctr_mc(c), nm, n))
            if fname == 'print':
                r.helper('_ail_ctr_mcrepr_%s' % c.K, fill(T_CTR_MCREPR, K=c.K, R=_reprsuffix(c.K)))
                r.ctr(c.K, 'mc', T_CTR_MC)
                return call('print', call('_ail_ctr_mcrepr_%s' % c.K, nm, n))
            if fname == 'dict':
                k = r.new_name('k')
                gen = ast.comprehension(target=ast.Name(id=k, ctx=ast.Store()),
                                        iter=call(r.ctr_mc(c), nm, n), ifs=[], is_async=0)
                return ast.DictComp(key=mk(k), value=call(attr(nm, 'get'), mk(k), ast.Constant(value=0)),
                                    generators=[gen])
            self.refuse(node, '%s(c.most_common(n)) is not built' % fname)
        new_args = []
        for a in args:
            sr = self.set_row(a)
            if sr is not None:
                if fname in ('len', 'sorted', 'sum', 'min', 'max', 'any', 'all'):
                    new_args.append(self.set_row_expr(*sr))
                    continue
                self.refuse(node, '%s(d[k]) of a defaultdict(set) row is not built; %s' % (fname, self.SET_ROW_NOTE))
            c = self.coll(a)
            if c is None or id(a) in self.okbare:
                new_args.append(self.visit(a))
                continue
            res = self.arg_use(node, fname, c, a)
            if isinstance(res, tuple):
                return res[0]
            new_args.append(res)
        node.args = new_args
        for kw in node.keywords:
            kc = self.coll(kw.value)
            if kc is not None:
                if fname in self.s.ITER_FUNCS or fname in r.sigs:
                    kw.value = self.arg_use(node, fname, kc, kw.value)
                else:
                    self.refuse(node, 'a collection passed as %s= to %s() is not built' % (kw.arg, fname))
            else:
                kw.value = self.visit(kw.value)
        return node

    def arg_use(self, node, fname, c, a):
        r = self.r
        if fname == 'len':
            if len(node.args) != 1 or node.keywords:
                self.refuse(node, 'len() takes one argument')
            if c.kind == 'dq':
                return (attr(a, 'n'),)
            if c.kind == 'ddl':
                return (call('len', attr(a, 'keys')),)
            return a
        if fname == 'list' and c.kind == 'dq' and len(node.args) == 1 and not node.keywords:
            return (self.s.as_iter(c, a),)
        if fname in self.s.ITER_FUNCS:
            if c.kind == 'ddl' and any(kw.arg == 'key' for kw in node.keywords):
                return self.hoist(self.s.as_iter(c, a))     # a typed local: a key lambda reads the element type
            return self.s.as_iter(c, a)
        if fname == 'bool' and len(node.args) == 1 and not node.keywords:
            return (self.truth(c, a),)
        if fname == 'print':
            if c.kind == 'ctr':
                r.helper('_ail_ctr_repr_%s' % c.K, fill(T_CTR_REPR, K=c.K, R=_reprsuffix(c.K)))
                r.ctr(c.K, 'mc', T_CTR_MC)
                return call('_ail_ctr_repr_%s' % c.K, a)
            if c.kind == 'dq':
                return call(r.dq(c, 'repr'), a)
            self.refuse(node, 'print() of a %s is not built; print its items' % (
                {'dds': 'defaultdict', 'ddl': 'defaultdict', 'od': 'OrderedDict'}[c.kind]))
        if fname == 'dict' and len(node.args) == 1 and not node.keywords:
            if c.kind in ('ctr', 'dds', 'od'):
                return (call(attr(a, 'copy')),)
            self.refuse(node, 'dict(%s) is not built' % ('defaultdict(list)' if c.kind == 'ddl' else 'deque'))
        if fname in r.sigs:
            params = r.sigs[fname][0]
            idx = [i for i, x in enumerate(node.args) if x is a]
            if not idx or idx[0] >= len(params):
                self.refuse(node, 'the %s passed to %s() must be a positional argument' % (c.kind, fname))
            t = r.ann_type(params[idx[0]])
            if not isinstance(t, C) or t.kind != c.kind or (t.K, t.V) != (c.K, c.V):
                self.refuse(node, 'parameter %d of %s() must be annotated with the same collections type as the '
                            'object passed (%s), so the callee keeps its behaviour' % (idx[0] + 1, fname, c.kind))
            self.okbare.add(id(a))
            return a
        self.refuse(node, 'a %s passed to %s() is not built' % (
            {'ctr': 'Counter', 'dds': 'defaultdict', 'ddl': 'defaultdict(list)', 'od': 'OrderedDict',
             'dq': 'deque'}[c.kind], fname))

    # defaultdict(set) rows ---------------------------------------------------------------------
    def set_row(self, node):
        """(C, receiver, key) when `node` is d[k] of a defaultdict(set)."""
        if isinstance(node, ast.Subscript) and not isinstance(node.slice, ast.Slice):
            c = self.coll(node.value)
            if c is not None and c.kind == 'ddl' and c.sets:
                return c, node.value, node.slice
        return None

    SET_ROW_NOTE = ('a defaultdict(set) row d[k] is built as d[k].add(x) / discard(x) / remove(x) / update(xs), '
                    'x in d[k], and len / sorted / sum / min / max / any / all of it; iterating it directly is '
                    'not built because the order of a set is unspecified in CPython -- use sorted(d[k])')

    def set_method(self, node, sr, m):
        r = self.r
        c, recv, key = sr
        if node.keywords:
            self.refuse(node, 'keyword arguments to a set method are not built')
        k = self.visit(copy.deepcopy(key))
        if m in ('add', 'discard', 'remove') and len(node.args) == 1:
            return call(r.ddl(c, m), recv, k, self.visit(node.args[0]))
        if m == 'update' and len(node.args) == 1:
            return call(r.ddl(c, 'update'), recv, k, self.as_list(node.args[0], r.infer(node.args[0], self.env)))
        self.refuse(node, 'd[k].%s(...) on a defaultdict(set) is not built; %s' % (m, self.SET_ROW_NOTE))

    def set_row_expr(self, c, recv, key):
        return ast.Subscript(value=attr(recv, 'vals'), slice=call(self.r.ddl(c, 'slot'), recv, self.visit(copy.deepcopy(key))),
                             ctx=ast.Load())

    # methods -----------------------------------------------------------------------------------
    def method(self, node, c):
        r = self.r
        f = node.func
        recv = f.value
        m = f.attr
        args = [self.visit_argument(a) if self.coll(a) is not None and c.kind in ('ctr', 'dds', 'od') and m == 'update'
                else self.visit(a) for a in node.args]
        for kw in node.keywords:
            kw.value = self.visit(kw.value)
        if c.kind in ('ctr', 'dds', 'od'):
            if m in DICT_METHODS or (m == 'update' and c.kind != 'ctr'):
                if node.keywords:
                    self.refuse(node, '%s(%s=...) is not built' % (m, node.keywords[0].arg))
                node.args = args
                return node
            if c.kind == 'ctr':
                if m == 'elements':
                    return call(r.ctr(c.K, 'elems', T_CTR_ELEMS), recv)
                if m == 'total':
                    return call('sum', call(attr(recv, 'values')))
                if m == 'most_common':
                    self.refuse(node, 'most_common(n) used as a list of pairs is built only in `for key, count in '
                                'c.most_common(n):`, comprehensions of that form, most_common(n)[i][0|1], len(), '
                                'dict() and print()')
                if m in ('update', 'subtract'):
                    self.refuse(node, 'Counter.%s is built only as a statement on its own line%s' % (
                        m, '' if m == 'update' else ' (subtract is not built)'))
            if c.kind == 'od' and m in ('move_to_end', 'popitem'):
                self.refuse(node, 'OrderedDict.%s is built only as a statement (`d.move_to_end(k)`, '
                            '`k, v = d.popitem(last=False)`)' % m)
            if m == 'popitem':
                self.refuse(node, 'popitem() is built only as a statement or as `k, v = d.popitem(last=...)`')
            self.refuse(node, '%s.%s() is not built (the dict methods get, setdefault, pop, keys, values, items, '
                        'copy, clear%s are)' % (recv.id, m, ', update' if c.kind != 'ctr' else ''))
        if c.kind == 'dq':
            return self.dq_method(node, c, recv, m, args)
        if c.kind == 'ddl':
            return self.ddl_method(node, c, recv, m, args)
        return node

    def dq_method(self, node, c, recv, m, args):
        r = self.r
        if node.keywords:
            self.refuse(node, 'keyword arguments to deque.%s are not built' % m)
        n = len(args)
        want = {'append': 1, 'appendleft': 1, 'pop': 0, 'popleft': 0, 'extend': 1, 'extendleft': 1, 'clear': 0,
                'count': 1, 'index': 1, 'remove': 1, 'insert': 2, 'reverse': 0, 'copy': 0}
        if m == 'rotate':
            if n > 1:
                self.refuse(node, 'rotate takes one count')
            return call(r.dq(c, 'rotate'), recv, args[0] if args else ast.Constant(value=1))
        if m not in want or n != want[m]:
            self.refuse(node, 'deque.%s(%d arguments) is not built (the built methods: append, appendleft, pop, '
                        'popleft, extend, extendleft, rotate, clear, count, index, remove, insert, reverse, '
                        'copy, and len / indexing / in / iteration)' % (m, n))
        if m in ('extend', 'extendleft'):
            a = node.args[0]
            return call(r.dq(c, m), recv, self.as_list(a, r.infer(a, self.env)))
        return call(r.dq(c, m), recv, *args)

    def ddl_method(self, node, c, recv, m, args):
        r = self.r
        if node.keywords:
            self.refuse(node, 'keyword arguments to a defaultdict(list) method are not built')
        if c.sets and m in ('get', 'setdefault', 'values', 'items'):
            self.refuse(node, 'd.%s() on a defaultdict(set) is not built; loop `for k in d:` and use d[k]' % m)
        if m == 'get':
            if len(args) != 2:
                self.refuse(node, 'd.get(k) with no default returns None; use d.get(k, [])')
            if id(node) not in self.s.readonly and True:
                pass
            if not isinstance(node.args[1], ast.List) or node.args[1].elts:
                self.refuse(node, 'get(k, default) on a defaultdict(list) is built with an empty list default (d.get(k, []))')
            self.check_readonly_get(node)
            return call(r.ddl(c, 'get'), recv, args[0], args[1])
        if m == 'setdefault':
            if len(args) == 2 and isinstance(node.args[1], ast.List) and not node.args[1].elts:
                return ast.Subscript(value=attr(recv, 'vals'), slice=call(r.ddl(c, 'slot'), recv, args[0]), ctx=ast.Load())
            self.refuse(node, 'setdefault(k, []) is the form built on a defaultdict(list)')
        if m == 'keys' and not args:
            return attr(recv, 'keys')
        if m == 'values' and not args:
            return attr(recv, 'vals')
        if m == 'clear' and not args:
            return call(r.ddl(c, 'clear'), recv)
        if m == 'items':
            self.refuse(node, 'items() of a defaultdict(list) is built only as `for k, v in d.items():`')
        self.refuse(node, '%s() on a defaultdict(list) is not built (get, setdefault(k, []), keys, values, clear, '
                    'indexing, in, len and loops are)' % m)

    def check_readonly_get(self, node):
        if id(node) not in self.s.readonly:
            self.refuse(node, 'd.get(k, []) on a defaultdict(list) returns a copy here, so it is built only where '
                        'the result is just read: a for loop, len / sum / min / max / sorted / list / any / all, '
                        'in, or an index; write `if k in d:` and use d[k] to change the row')


T_CTR_MCREPR = '''def _ail_ctr_mcrepr_@K(c: dict[@K, int], n: int) -> str:
    ks = _ail_ctr_mc_@K(c, n)
    parts: list[str] = []
    for k in ks:
        parts.append(f"({k@R}, {c[k]})")
    return "[" + ", ".join(parts) + "]"
'''


def rewrite(source, notes=None):
    """The program with its collections lowered, or the source as written (and `notes` filled) when a use is
    not built."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    rw = Rewriter(source, tree)
    try:
        out = rw.run()
    except Refused as exc:
        rw.notes.append(exc.args[0])
        out = None
    except (AttributeError, KeyError, IndexError, TypeError, ValueError, RecursionError) as exc:
        # a shape this rewrite did not foresee: refuse the program, never guess at what it meant
        rw.notes.append((1, 'the collections rewrite could not handle this program (%s: %s); simplify the use of '
                         'collections or report it' % (type(exc).__name__, exc)))
        out = None
    if out is None and not rw.notes:
        return source
    if rw.notes:
        if notes is not None:
            notes.extend(sorted(rw.notes))
        return source
    return out
