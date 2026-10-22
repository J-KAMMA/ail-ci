# -*- coding: utf-8 -*-
# prelude_genlib.py -- library functions of the general (boxed) path as Python source: json.dumps / json.loads,
# itertools (chain islice cycle product count repeat pairwise compress filterfalse batched),
# math.isclose, statistics, datetime (see genlib.py, which picks the pieces a program uses and renames the library names
# to these). The file is importable by CPython, so the tests can compare each function with the library.
#
# Integers are 64-bit; strings are 16-bit (a \ud800 escape or a character beyond U+FFFF is not built).
import math


# ------------------------------------------------------------------------------------------------ json
class JSONDecodeError(ValueError):
    def __init__(self, msg, doc, pos):
        line = 1
        last = -1
        i = 0
        while i < pos:
            if doc[i] == '\n':
                line = line + 1
                last = i
            i = i + 1
        if line > 1:
            col = pos - last
        else:
            col = pos + 1
        super().__init__(msg + ': line ' + str(line) + ' column ' + str(col) + ' (char ' + str(pos) + ')')
        self.msg = msg
        self.doc = doc
        self.pos = pos
        self.lineno = line
        self.colno = col


_AIL_HEX = '0123456789abcdef'


def _ail_json_u(n):
    return '\\u' + _AIL_HEX[(n >> 12) & 15] + _AIL_HEX[(n >> 8) & 15] + _AIL_HEX[(n >> 4) & 15] + _AIL_HEX[n & 15]


def _ail_json_quote(s, ascii_only):
    out = ['"']
    for ch in s:
        o = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == '\\':
            out.append('\\\\')
        elif ch == '\n':
            out.append('\\n')
        elif ch == '\r':
            out.append('\\r')
        elif ch == '\t':
            out.append('\\t')
        elif ch == '\b':
            out.append('\\b')
        elif ch == '\f':
            out.append('\\f')
        elif o < 32:
            out.append(_ail_json_u(o))
        elif ascii_only and o > 126:
            if o > 65535:
                o = o - 65536
                out.append(_ail_json_u(55296 | (o >> 10)))
                out.append(_ail_json_u(56320 | (o & 1023)))
            else:
                out.append(_ail_json_u(o))
        else:
            out.append(ch)
    out.append('"')
    return ''.join(out)


def _ail_json_float(o, allow_nan):
    if o != o:
        text = 'NaN'
    elif o > 1.7976931348623157e308:
        text = 'Infinity'
    elif o < -1.7976931348623157e308:
        text = '-Infinity'
    else:
        return repr(o)
    if not allow_nan:
        raise ValueError('Out of range float values are not JSON compliant: ' + repr(o))
    return text


def _ail_json_enc(o, out, level, cfg, stack):
    # cfg: [indent_str or None, item_sep, key_sep, sort_keys, ascii_only, skipkeys, allow_nan, default, check]
    if isinstance(o, str):
        out.append(_ail_json_quote(o, cfg[4]))
    elif o is None:
        out.append('null')
    elif isinstance(o, bool):
        if o:
            out.append('true')
        else:
            out.append('false')
    elif isinstance(o, int):
        out.append(str(o))
    elif isinstance(o, float):
        out.append(_ail_json_float(o, cfg[6]))
    elif isinstance(o, (list, tuple)):
        if len(o) == 0:
            out.append('[]')
            return
        if cfg[8]:
            for each in stack:
                if each is o:
                    raise ValueError('Circular reference detected')
            stack.append(o)
        out.append('[')
        indent = cfg[0]
        sep = cfg[1]
        if indent is not None:
            level = level + 1
            nl = '\n' + indent * level
            sep = sep + nl
            out.append(nl)
        first = True
        for v in o:
            if first:
                first = False
            else:
                out.append(sep)
            _ail_json_enc(v, out, level, cfg, stack)
        if indent is not None:
            level = level - 1
            out.append('\n' + indent * level)
        out.append(']')
        if cfg[8]:
            stack.pop()
    elif isinstance(o, dict):
        if len(o) == 0:
            out.append('{}')
            return
        if cfg[8]:
            for each in stack:
                if each is o:
                    raise ValueError('Circular reference detected')
            stack.append(o)
        out.append('{')
        indent = cfg[0]
        sep = cfg[1]
        if indent is not None:
            level = level + 1
            nl = '\n' + indent * level
            sep = sep + nl
            out.append(nl)
        keys = list(o.keys())
        if cfg[3]:
            keys = sorted(keys)
        first = True
        for k in keys:
            if isinstance(k, str):
                ks = k
            elif isinstance(k, float):
                ks = _ail_json_float(k, cfg[6])
            elif k is True:
                ks = 'true'
            elif k is False:
                ks = 'false'
            elif k is None:
                ks = 'null'
            elif isinstance(k, int):
                ks = str(k)
            elif cfg[5]:
                continue
            else:
                raise TypeError('keys must be str, int, float, bool or None, not ' + type(k).__name__)
            if first:
                first = False
            else:
                out.append(sep)
            out.append(_ail_json_quote(ks, cfg[4]))
            out.append(cfg[2])
            _ail_json_enc(o[k], out, level, cfg, stack)
        if indent is not None:
            level = level - 1
            out.append('\n' + indent * level)
        out.append('}')
        if cfg[8]:
            stack.pop()
    else:
        if cfg[7] is None:
            raise TypeError('Object of type ' + type(o).__name__ + ' is not JSON serializable')
        _ail_json_enc(cfg[7](o), out, level, cfg, stack)


def _ail_json_dumps(obj, skipkeys=False, ensure_ascii=True, check_circular=True, allow_nan=True, indent=None,
                    separators=None, default=None, sort_keys=False):
    item_sep = ', '
    key_sep = ': '
    ind = None
    if indent is not None:
        if isinstance(indent, str):
            ind = indent
        else:
            ind = ' ' * indent
        item_sep = ','
    if separators is not None:
        item_sep = separators[0]
        key_sep = separators[1]
    out = []
    _ail_json_enc(obj, out, 0, [ind, item_sep, key_sep, sort_keys, ensure_ascii, skipkeys, allow_nan, default,
                                check_circular], [])
    return ''.join(out)


def _ail_json_fail(msg, s, pos):
    raise JSONDecodeError(msg, s, pos)


def _ail_json_ws(s, n, i):
    while i < n:
        c = s[i]
        if c == ' ' or c == '\t' or c == '\n' or c == '\r':
            i = i + 1
        else:
            break
    return i


def _ail_json_hexval(s, i):
    # the value of the 4 hex digits at s[i:i+4], or -1
    v = 0
    j = 0
    while j < 4:
        c = s[i + j]
        v = v * 16
        if c >= '0' and c <= '9':
            v = v + ord(c) - 48
        elif c >= 'a' and c <= 'f':
            v = v + ord(c) - 87
        elif c >= 'A' and c <= 'F':
            v = v + ord(c) - 55
        else:
            return -1
        j = j + 1
    return v


def _ail_json_string(s, n, end):
    # end: the index after the opening quote. Returns (text, index after the closing quote).
    begin = end - 1
    parts = []
    while True:
        nxt = end
        c = ''
        while nxt < n:
            c = s[nxt]
            if c == '"' or c == '\\':
                break
            if ord(c) <= 31:
                _ail_json_fail('Invalid control character at', s, nxt)
            nxt = nxt + 1
        if nxt >= n:
            _ail_json_fail('Unterminated string starting at', s, begin)
        if nxt > end:
            parts.append(s[end:nxt])
        nxt = nxt + 1
        if c == '"':
            end = nxt
            break
        if nxt == n:
            _ail_json_fail('Unterminated string starting at', s, begin)
        c = s[nxt]
        if c != 'u':
            end = nxt + 1
            if c == '"' or c == '\\' or c == '/':
                parts.append(c)
            elif c == 'b':
                parts.append('\b')
            elif c == 'f':
                parts.append('\f')
            elif c == 'n':
                parts.append('\n')
            elif c == 'r':
                parts.append('\r')
            elif c == 't':
                parts.append('\t')
            else:
                _ail_json_fail('Invalid \\escape', s, end - 2)
        else:
            nxt = nxt + 1
            end = nxt + 4
            if end >= n:
                _ail_json_fail('Invalid \\uXXXX escape', s, nxt - 1)
            v = _ail_json_hexval(s, nxt)
            if v < 0:
                _ail_json_fail('Invalid \\uXXXX escape', s, end - 5)
            nxt = end
            if v >= 55296 and v <= 57343:
                raise ValueError('a surrogate escape in JSON text is not supported on the general path (strings are 16-bit)')
            parts.append(chr(v))
    return (''.join(parts), end)


def _ail_json_isdigit(c):
    return c >= '0' and c <= '9'


def _ail_json_number(s, n, start, hooks):
    end_idx = n - 1
    idx = start
    if idx > end_idx:
        _ail_json_fail('Expecting value', s, start)
    if s[idx] == '-':
        idx = idx + 1
        if idx > end_idx:
            _ail_json_fail('Expecting value', s, start)
    if s[idx] >= '1' and s[idx] <= '9':
        idx = idx + 1
        while idx <= end_idx and _ail_json_isdigit(s[idx]):
            idx = idx + 1
    elif s[idx] == '0':
        idx = idx + 1
    else:
        _ail_json_fail('Expecting value', s, start)
    is_float = False
    if idx < end_idx and s[idx] == '.' and _ail_json_isdigit(s[idx + 1]):
        is_float = True
        idx = idx + 2
        while idx <= end_idx and _ail_json_isdigit(s[idx]):
            idx = idx + 1
    if idx < end_idx and (s[idx] == 'e' or s[idx] == 'E'):
        e_start = idx
        idx = idx + 1
        if idx < end_idx and (s[idx] == '-' or s[idx] == '+'):
            idx = idx + 1
        while idx <= end_idx and _ail_json_isdigit(s[idx]):
            idx = idx + 1
        if _ail_json_isdigit(s[idx - 1]):
            is_float = True
        else:
            idx = e_start
    text = s[start:idx]
    if is_float:
        if hooks[2] is not None:
            return (hooks[2](text), idx)
        return (float(text), idx)
    if hooks[3] is not None:
        return (hooks[3](text), idx)
    return (int(text), idx)


def _ail_json_value(s, n, idx, hooks):
    # CPython's scan_once: the value at s[idx] and the index after it
    if idx >= n:
        _ail_json_fail('Expecting value', s, idx)
    c = s[idx]
    if c == '"':
        return _ail_json_string(s, n, idx + 1)
    if c == '{':
        return _ail_json_object(s, n, idx + 1, hooks)
    if c == '[':
        return _ail_json_array(s, n, idx + 1, hooks)
    if c == 'n' and idx + 3 < n and s[idx + 1] == 'u' and s[idx + 2] == 'l' and s[idx + 3] == 'l':
        return (None, idx + 4)
    if c == 't' and idx + 3 < n and s[idx + 1] == 'r' and s[idx + 2] == 'u' and s[idx + 3] == 'e':
        return (True, idx + 4)
    if c == 'f' and idx + 4 < n and s[idx + 1] == 'a' and s[idx + 2] == 'l' and s[idx + 3] == 's' and s[idx + 4] == 'e':
        return (False, idx + 5)
    if c == 'N' and idx + 2 < n and s[idx + 1] == 'a' and s[idx + 2] == 'N':
        if hooks[4] is not None:
            return (hooks[4]('NaN'), idx + 3)
        return (float('nan'), idx + 3)
    if c == 'I' and idx + 7 < n and s[idx:idx + 8] == 'Infinity':
        if hooks[4] is not None:
            return (hooks[4]('Infinity'), idx + 8)
        return (float('inf'), idx + 8)
    if c == '-' and idx + 8 < n and s[idx + 1:idx + 9] == 'Infinity':
        if hooks[4] is not None:
            return (hooks[4]('-Infinity'), idx + 9)
        return (float('-inf'), idx + 9)
    return _ail_json_number(s, n, idx, hooks)


def _ail_json_object(s, n, idx, hooks):
    end_idx = n - 1
    keys = []
    vals = []
    idx = _ail_json_ws(s, n, idx)
    if idx > end_idx or s[idx] != '}':
        while True:
            if idx > end_idx or s[idx] != '"':
                _ail_json_fail('Expecting property name enclosed in double quotes', s, idx)
            kv = _ail_json_string(s, n, idx + 1)
            idx = _ail_json_ws(s, n, kv[1])
            if idx > end_idx or s[idx] != ':':
                _ail_json_fail("Expecting ':' delimiter", s, idx)
            idx = _ail_json_ws(s, n, idx + 1)
            vv = _ail_json_value(s, n, idx, hooks)
            keys.append(kv[0])
            vals.append(vv[0])
            idx = _ail_json_ws(s, n, vv[1])
            if idx <= end_idx and s[idx] == '}':
                break
            if idx > end_idx or s[idx] != ',':
                _ail_json_fail("Expecting ',' delimiter", s, idx)
            idx = _ail_json_ws(s, n, idx + 1)
    if hooks[1] is not None:
        pairs = []
        for i in range(len(keys)):
            pairs.append((keys[i], vals[i]))
        return (hooks[1](pairs), idx + 1)
    d = {}
    for i in range(len(keys)):
        d[keys[i]] = vals[i]
    if hooks[0] is not None:
        return (hooks[0](d), idx + 1)
    return (d, idx + 1)


def _ail_json_array(s, n, idx, hooks):
    end_idx = n - 1
    out = []
    idx = _ail_json_ws(s, n, idx)
    if idx > end_idx or s[idx] != ']':
        while True:
            vv = _ail_json_value(s, n, idx, hooks)
            out.append(vv[0])
            idx = _ail_json_ws(s, n, vv[1])
            if idx <= end_idx and s[idx] == ']':
                break
            if idx > end_idx or s[idx] != ',':
                _ail_json_fail("Expecting ',' delimiter", s, idx)
            idx = _ail_json_ws(s, n, idx + 1)
    if idx > end_idx or s[idx] != ']':
        _ail_json_fail('Expecting value', s, end_idx)
    return (out, idx + 1)


def _ail_json_loads(s, object_hook=None, parse_float=None, parse_int=None, parse_constant=None,
                    object_pairs_hook=None):
    if not isinstance(s, str):
        raise TypeError('the JSON object must be str, bytes or bytearray, not ' + type(s).__name__)
    n = len(s)
    if n > 0 and ord(s[0]) == 65279:
        _ail_json_fail('Unexpected UTF-8 BOM (decode using utf-8-sig)', s, 0)
    hooks = [object_hook, object_pairs_hook, parse_float, parse_int, parse_constant]
    start = _ail_json_ws(s, n, 0)
    vv = _ail_json_value(s, n, start, hooks)
    end = _ail_json_ws(s, n, vv[1])
    if end != n:
        _ail_json_fail('Extra data', s, end)
    return vv[0]


# ------------------------------------------------------------------------------------------------ itertools
def _ail_chain(*iterables):
    for it in iterables:
        for x in it:
            yield x


def _ail_chain_from_iterable(iterables):
    for it in iterables:
        for x in it:
            yield x


def _ail_islice(iterable, *args):
    if len(args) == 0 or len(args) > 3:
        raise TypeError('islice expected 2 to 4 arguments, got ' + str(len(args) + 1))
    start = 0
    step = 1
    if len(args) == 1:
        stop = args[0]
    else:
        stop = args[1]
        if args[0] is not None:
            start = args[0]
        if len(args) == 3 and args[2] is not None:
            step = args[2]
    if stop is not None and (not isinstance(stop, int) or stop < 0):
        raise ValueError('Stop argument for islice() must be None or an integer: 0 <= x <= sys.maxsize.')
    if not isinstance(start, int) or start < 0:
        raise ValueError('Indices for islice() must be None or an integer: 0 <= x <= sys.maxsize.')
    if not isinstance(step, int) or step < 1:
        raise ValueError('Step for islice() must be a positive integer or None.')
    if stop is not None and start >= stop:
        return
    i = 0
    nxt = start
    for x in iterable:
        if i == nxt:
            yield x
            nxt = nxt + step
            if stop is not None and nxt >= stop:
                return
        i = i + 1


def _ail_cycle(iterable):
    saved = []
    for x in iterable:
        yield x
        saved.append(x)
    if len(saved) == 0:
        return
    while True:
        for x in saved:
            yield x


def _ail_product(*iterables):
    return _ail_product_core(iterables, 1)


def _ail_product_rep(repeat, iterables):
    return _ail_product_core(iterables, repeat)


def _ail_product_core(iterables, repeat):
    if repeat < 0:
        raise ValueError('repeat argument cannot be negative')
    pools = []
    for it in iterables:
        pools.append(tuple(it))
    base = pools
    pools = []
    for r in range(repeat):
        for p in base:
            pools.append(p)
    n = len(pools)
    for p in pools:
        if len(p) == 0:
            return
    idx = [0] * n
    while True:
        row = []
        for k in range(n):
            row.append(pools[k][idx[k]])
        yield tuple(row)
        k = n - 1
        while k >= 0:
            idx[k] = idx[k] + 1
            if idx[k] < len(pools[k]):
                break
            idx[k] = 0
            k = k - 1
        if k < 0:
            return


def _ail_count(start=0, step=1):
    n = start
    while True:
        yield n
        n = n + step


def _ail_repeat(obj, times=None):
    if times is None:
        while True:
            yield obj
    else:
        for i in range(times):
            yield obj


def _ail_zip_longest_star(iterables, fillvalue):
    its = [iter(x) for x in iterables]
    live = len(its)
    while live:
        row = []
        for i in range(len(its)):
            if its[i] is None:
                row.append(fillvalue)
                continue
            try:
                row.append(next(its[i]))
            except StopIteration:
                live -= 1
                its[i] = None
                row.append(fillvalue)
        if live == 0:
            return
        yield tuple(row)


def _ail_takewhile(pred, iterable):
    for x in iterable:
        if not pred(x):
            return
        yield x


def _ail_dropwhile(pred, iterable):
    dropping = True
    for x in iterable:
        if dropping and pred(x):
            continue
        dropping = False
        yield x


def _ail_reduce(function, iterable):
    it = iter(iterable)
    try:
        acc = next(it)
    except StopIteration:
        raise TypeError("reduce() of empty iterable with no initial value")
    for x in it:
        acc = function(acc, x)
    return acc


def _ail_reduce_init(function, iterable, initial):
    acc = initial
    for x in iterable:
        acc = function(acc, x)
    return acc


def _ail_pairwise(iterable):
    prev = None
    first = True
    for x in iterable:
        if first:
            first = False
        else:
            yield (prev, x)
        prev = x


def _ail_compress(data, selectors):
    it = iter(selectors)
    for d in data:
        try:
            s = next(it)
        except StopIteration:
            return
        if s:
            yield d


def _ail_takewhile_iter(predicate, it):
    for x in it:
        if not predicate(x):
            return
        yield x


def _ail_takewhile(predicate, iterable):
    # CPython's takewhile raises a non-iterable at CALL time (a generator function would raise it late, or
    # not at all when nothing iterates it), so the iterable is opened here, in a plain function, and only
    # the walk is lazy.
    return _ail_takewhile_iter(predicate, iter(iterable))


def _ail_dropwhile_iter(predicate, it):
    dropping = True
    for x in it:
        if dropping:
            if predicate(x):
                continue
            dropping = False
        yield x


def _ail_dropwhile(predicate, iterable):
    return _ail_dropwhile_iter(predicate, iter(iterable))


def _ail_filterfalse(predicate, iterable):
    for x in iterable:
        if predicate is None:
            if not x:
                yield x
        elif not predicate(x):
            yield x


def _ail_batched(iterable, n):
    if n < 1:
        raise ValueError('n must be at least one')
    batch = []
    for x in iterable:
        batch.append(x)
        if len(batch) == n:
            yield tuple(batch)
            batch = []
    if len(batch) > 0:
        yield tuple(batch)


# ------------------------------------------------------------------------------------------------ functools, math
def _ail_isclose(a, b, rel_tol=1e-09, abs_tol=0.0):
    if rel_tol < 0.0 or abs_tol < 0.0:
        raise ValueError('tolerances must be non-negative')
    x = float(a)
    y = float(b)
    if x != x or y != y:
        return False
    if x == y:
        return True
    if abs(x) > 1.7976931348623157e308 or abs(y) > 1.7976931348623157e308:
        return False
    diff = abs(y - x)
    return diff <= abs(rel_tol * y) or diff <= abs(rel_tol * x) or diff <= abs_tol


# ------------------------------------------------------------------------------------------------ statistics
# Exact results for ints (64-bit arithmetic while the sums fit) and "double-double" results for floats: CPython sums
# floats as exact fractions; here the exact sum is kept as non-overlapping partials (the recipe of math.fsum) and the
# division, the squares and the square root run in two doubles (about 106 bits), so the double that comes out is the
# one CPython gives except when the exact value lies within ~2**-50 (relative) of a rounding boundary.
class StatisticsError(ValueError):
    pass


try:
    _ail_c_sqrt
except NameError:
    _ail_c_sqrt = math.sqrt
    _ail_c_log = math.log
    _ail_c_exp = math.exp


def _ail_st_data(data):
    xs = list(data)
    for x in xs:
        if not isinstance(x, (int, float)):
            raise TypeError("can't convert type '" + type(x).__name__ + "' to numerator/denominator")
    return xs


def _ail_st_finite(xs):
    for x in xs:
        if x - x != 0.0:
            return False
    return True


def _ail_st_partials(xs):
    partials = []
    for v in xs:
        x = float(v)
        keep = []
        for y in partials:
            if abs(x) < abs(y):
                t = x
                x = y
                y = t
            hi = x + y
            lo = y - (hi - x)
            if lo != 0.0:
                keep.append(lo)
            x = hi
        if x != 0.0:      # math.fsum drops a zero: fsum([-0.0]) is 0.0
            keep.append(x)
        partials = keep
    return partials


def _ail_st_round(partials):
    # math.fsum's last step: the correctly rounded sum of the partials
    n = len(partials)
    hi = 0.0
    if n > 0:
        n = n - 1
        hi = partials[n]
        lo = 0.0
        while n > 0:
            x = hi
            n = n - 1
            y = partials[n]
            hi = x + y
            yr = hi - x
            lo = y - yr
            if lo != 0.0:
                break
        if n > 0 and ((lo < 0.0 and partials[n - 1] < 0.0) or (lo > 0.0 and partials[n - 1] > 0.0)):
            y = lo * 2.0
            x = hi + y
            yr = x - hi
            if y == yr:
                hi = x
    return hi


def _ail_st_fsum(xs):
    if not _ail_st_finite(xs):
        total = 0.0
        for x in xs:
            total = total + x
        return total
    return _ail_st_round(_ail_st_partials(xs))


def _ail_st_dd_of(partials):
    # the exact sum of the partials as two doubles (hi + lo)
    hi = _ail_st_round(partials)
    rest = list(partials)
    rest.append(-hi)
    lo = _ail_st_round(_ail_st_partials(rest))
    return (hi, lo)


def _ail_st_twosum(a, b):
    s = a + b
    bb = s - a
    e = (a - (s - bb)) + (b - bb)
    return (s, e)


def _ail_st_twoprod(a, b):
    p = a * b
    c = 134217729.0 * a
    ah = c - (c - a)
    al = a - ah
    c = 134217729.0 * b
    bh = c - (c - b)
    bl = b - bh
    e = ((ah * bh - p) + ah * bl + al * bh) + al * bl
    return (p, e)


def _ail_st_ddiv_int(hi, lo, n):
    # (hi + lo) / n as two doubles
    d = float(n)
    q1 = hi / d
    pe = _ail_st_twoprod(q1, d)
    r = ((hi - pe[0]) - pe[1]) + lo
    q2 = r / d
    s = q1 + q2
    return (s, q2 - (s - q1))


def _ail_st_dd_sqrt(hi, lo):
    if hi <= 0.0:
        return 0.0
    s = _ail_c_sqrt(hi)
    pe = _ail_st_twoprod(s, s)
    r = ((hi - pe[0]) - pe[1]) + lo
    return s + r / (2.0 * s)


def _ail_st_mean_dd(xs):
    # the mean of floats (ints are converted) as two doubles
    n = len(xs)
    dd = _ail_st_dd_of(_ail_st_partials(xs))
    return _ail_st_ddiv_int(dd[0], dd[1], n)


def _ail_st_ssd_dd(xs, ch, cl):
    # sum of (x - c)**2 as two doubles, c = ch + cl
    ah = 0.0
    al = 0.0
    for v in xs:
        x = float(v)
        t = _ail_st_twosum(x, -ch)
        dh = t[0]
        dl = t[1] - cl
        s = _ail_st_twosum(dh, dl)
        dh = s[0]
        dl = s[1]
        pe = _ail_st_twoprod(dh, dh)
        p = pe[0]
        e = pe[1] + 2.0 * dh * dl
        u = _ail_st_twosum(ah, p)
        w = u[1] + (al + e)
        z = _ail_st_twosum(u[0], w)
        ah = z[0]
        al = z[1]
    return (ah, al)


def _ail_st_ints_sums(xs):
    # (sum, sum of squares) of ints when the exact arithmetic fits in 64 bits, else None
    n = len(xs)
    big = 0
    for x in xs:
        a = abs(x)
        if a > big:
            big = a
    if big > 1000000000 or n > 1000000000 or big * n > 3000000000:
        return None
    s = 0
    q = 0
    for x in xs:
        s = s + x
        q = q + x * x
    return (s, q)


def _ail_st_isint(xs):
    for x in xs:
        if not isinstance(x, int):
            return False
    return True


def _ail_st_ratio(num, den):
    # num / den for ints as CPython's _convert(Fraction(num, den), int): an int when whole, else the float
    if num % den == 0:
        return num // den
    return num / den


def _ail_st_var(data, mu, sample, root, name):
    xs = _ail_st_data(data)
    n = len(xs)
    if sample:
        if n < 2:
            raise StatisticsError(name + ' requires at least two data points')
        dfree = n - 1
    else:
        if n < 1:
            raise StatisticsError(name + ' requires at least one data point')
        dfree = n
    if not _ail_st_finite(xs):
        return float('nan')
    if mu is None and _ail_st_isint(xs):
        sums = _ail_st_ints_sums(xs)
        if sums is not None:
            top = n * sums[1] - sums[0] * sums[0]
            den = n * dfree
            if top < 9007199254740992 and den < 9007199254740992:
                if not root:
                    return _ail_st_ratio(top, den)
                q = _ail_st_ddiv_int(float(top), 0.0, den)
                return _ail_st_dd_sqrt(q[0], q[1])
    if mu is not None:
        if _ail_st_isint(xs) and isinstance(mu, int):
            ss = 0
            for x in xs:
                d = x - mu
                ss = ss + d * d
            if not root:
                return _ail_st_ratio(ss, dfree)
            q = _ail_st_ddiv_int(float(ss), 0.0, dfree)
            return _ail_st_dd_sqrt(q[0], q[1])
        sq = []
        for x in xs:
            d = x - mu
            sq.append(d * d)
        dd = _ail_st_dd_of(_ail_st_partials(sq))
        q = _ail_st_ddiv_int(dd[0], dd[1], dfree)
    else:
        c = _ail_st_mean_dd(xs)
        ssd = _ail_st_ssd_dd(xs, c[0], c[1])
        q = _ail_st_ddiv_int(ssd[0], ssd[1], dfree)
    if root:
        return _ail_st_dd_sqrt(q[0], q[1])
    return q[0]


def _ail_st_mean(data):
    xs = _ail_st_data(data)
    n = len(xs)
    if n < 1:
        raise StatisticsError('mean requires at least one data point')
    if not _ail_st_finite(xs):
        total = 0.0
        for x in xs:
            if x - x != 0.0:
                total = total + x
        return total / n
    if _ail_st_isint(xs):
        sums = _ail_st_ints_sums(xs)
        if sums is not None:
            return _ail_st_ratio(sums[0], n)
    return _ail_st_mean_dd(xs)[0]


def _ail_st_fmean(data):
    xs = list(data)
    n = len(xs)
    if n < 1:
        raise StatisticsError('fmean requires at least one data point')
    return _ail_st_fsum(xs) / n


def _ail_st_variance(data, xbar=None):
    return _ail_st_var(data, xbar, True, False, 'variance')


def _ail_st_pvariance(data, mu=None):
    return _ail_st_var(data, mu, False, False, 'pvariance')


def _ail_st_stdev(data, xbar=None):
    return _ail_st_var(data, xbar, True, True, 'stdev')


def _ail_st_pstdev(data, mu=None):
    return _ail_st_var(data, mu, False, True, 'pstdev')


def _ail_st_median(data):
    xs = sorted(data)
    n = len(xs)
    if n == 0:
        raise StatisticsError('no median for empty data')
    if n % 2 == 1:
        return xs[n // 2]
    i = n // 2
    return (xs[i - 1] + xs[i]) / 2


def _ail_st_median_low(data):
    xs = sorted(data)
    n = len(xs)
    if n == 0:
        raise StatisticsError('no median for empty data')
    if n % 2 == 1:
        return xs[n // 2]
    return xs[n // 2 - 1]


def _ail_st_median_high(data):
    xs = sorted(data)
    n = len(xs)
    if n == 0:
        raise StatisticsError('no median for empty data')
    return xs[n // 2]


def _ail_st_mode(data):
    counts = {}
    best = None
    bestn = 0
    for x in data:
        if x in counts:
            counts[x] = counts[x] + 1
        else:
            counts[x] = 1
    for k in counts:
        if counts[k] > bestn:
            best = k
            bestn = counts[k]
    if bestn == 0:
        raise StatisticsError('no mode for empty data')
    return best


def _ail_st_multimode(data):
    counts = {}
    for x in data:
        if x in counts:
            counts[x] = counts[x] + 1
        else:
            counts[x] = 1
    bestn = 0
    for k in counts:
        if counts[k] > bestn:
            bestn = counts[k]
    out = []
    for k in counts:
        if counts[k] == bestn:
            out.append(k)
    return out


def _ail_st_geometric_mean(data):
    # exp(fmean(map(log, data))); a log of zero or a negative number is the ValueError that becomes the StatisticsError
    logs = []
    for x in data:
        if x <= 0 and x == x:
            raise StatisticsError('geometric mean requires a non-empty dataset containing positive numbers')
        logs.append(_ail_c_log(float(x)))
    if len(logs) == 0:
        raise StatisticsError('geometric mean requires a non-empty dataset containing positive numbers')
    return _ail_c_exp(_ail_st_fsum(logs) / len(logs))


def _ail_st_harmonic_mean(data):
    xs = _ail_st_data(data)
    n = len(xs)
    errmsg = 'harmonic mean does not support negative values'
    if n < 1:
        raise StatisticsError('harmonic_mean requires at least one data point')
    if n == 1:
        x = xs[0]
        if x < 0:
            raise StatisticsError(errmsg)
        return x
    inv = []
    for x in xs:
        # CPython sums 1/x over a generator that refuses a negative value, in this order: a zero before a negative
        # value gives 0, a negative value before a zero gives the error
        if x < 0:
            raise StatisticsError(errmsg)
        if x == 0:
            return 0
        inv.append(1 / x)
    if not _ail_st_finite(inv):
        total = 0.0
        for v in inv:
            total = total + v
        return n / total
    dd = _ail_st_dd_of(_ail_st_partials(inv))
    hi = dd[0]
    lo = dd[1]
    if hi + lo <= 0:
        raise StatisticsError('Weighted sum must be positive')
    q1 = n / hi
    pe = _ail_st_twoprod(q1, hi)
    r = ((float(n) - pe[0]) - pe[1]) - q1 * lo
    return q1 + r / hi


# ------------------------------------------------------------------------------------------------ datetime
# Naive date, datetime and timedelta (no tzinfo, no time class, no now() / today()); the text forms, arithmetic and
# comparisons are CPython's.
_AIL_DIM = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
_AIL_DBM = [0, 0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
_AIL_MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
               'November', 'December']
_AIL_DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


def _ail_dt_leap(y):
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


def _ail_dt_dim(y, m):
    if m == 2 and _ail_dt_leap(y):
        return 29
    return _AIL_DIM[m]


def _ail_dt_dbm(y, m):
    if m > 2 and _ail_dt_leap(y):
        return _AIL_DBM[m] + 1
    return _AIL_DBM[m]


def _ail_dt_ymd2ord(y, m, d):
    y1 = y - 1
    return y1 * 365 + y1 // 4 - y1 // 100 + y1 // 400 + _ail_dt_dbm(y, m) + d


def _ail_dt_ord2ymd(n):
    n = n - 1
    n400 = n // 146097
    n = n % 146097
    year = n400 * 400 + 1
    n100 = n // 36524
    n = n % 36524
    n4 = n // 1461
    n = n % 1461
    n1 = n // 365
    n = n % 365
    year = year + n100 * 100 + n4 * 4 + n1
    if n1 == 4 or n100 == 4:
        return (year - 1, 12, 31)
    leap = n1 == 3 and (n4 != 24 or n100 == 3)
    month = (n + 50) >> 5
    preceding = _AIL_DBM[month]
    if month > 2 and leap:
        preceding = preceding + 1
    if preceding > n:
        month = month - 1
        preceding = preceding - _AIL_DIM[month]
        if month == 2 and leap:
            preceding = preceding - 1
    return (year, month, n - preceding + 1)


def _ail_dt_check_date(year, month, day):
    if year < 1 or year > 9999:
        raise ValueError('year ' + str(year) + ' is out of range')
    if month < 1 or month > 12:
        raise ValueError('month must be in 1..12')
    if day < 1 or day > _ail_dt_dim(year, month):
        raise ValueError('day is out of range for month')


def _ail_dt_check_time(hour, minute, second, microsecond):
    if hour < 0 or hour > 23:
        raise ValueError('hour must be in 0..23')
    if minute < 0 or minute > 59:
        raise ValueError('minute must be in 0..59')
    if second < 0 or second > 59:
        raise ValueError('second must be in 0..59')
    if microsecond < 0 or microsecond > 999999:
        raise ValueError('microsecond must be in 0..999999')


def _ail_dt_plural(n):
    if n == 1 or n == -1:
        return ''
    return 's'


def _ail_dt_pad(n, width, flag):
    # a number for strftime: zero padded to width, or as is after the glibc flag '-'
    text = str(n)
    if flag == '-':
        return text
    if flag == '_':
        return ' ' * (width - len(text)) + text
    return '0' * (width - len(text)) + text


def _ail_dt_strftime(year, month, day, hour, minute, second, micro, fmt):
    out = []
    i = 0
    n = len(fmt)
    ordinal = _ail_dt_ymd2ord(year, month, day)
    wday = (ordinal + 6) % 7
    yday = _ail_dt_dbm(year, month) + day
    while i < n:
        ch = fmt[i]
        if ch != '%' or i + 1 >= n:
            out.append(ch)
            i = i + 1
            continue
        i = i + 1
        flag = ''
        c = fmt[i]
        if (c == '-' or c == '_' or c == '0') and i + 1 < n:
            flag = c
            i = i + 1
            c = fmt[i]
        i = i + 1
        if c == 'Y':
            out.append(_ail_dt_pad(year, 4, flag) if flag != '' else str(year))
        elif c == 'm':
            out.append(_ail_dt_pad(month, 2, flag))
        elif c == 'd':
            out.append(_ail_dt_pad(day, 2, flag))
        elif c == 'e':
            if flag == '':
                out.append(_ail_dt_pad(day, 2, '_'))
            else:
                out.append(_ail_dt_pad(day, 2, flag))
        elif c == 'H':
            out.append(_ail_dt_pad(hour, 2, flag))
        elif c == 'I':
            h12 = hour % 12
            if h12 == 0:
                h12 = 12
            out.append(_ail_dt_pad(h12, 2, flag))
        elif c == 'M':
            out.append(_ail_dt_pad(minute, 2, flag))
        elif c == 'S':
            out.append(_ail_dt_pad(second, 2, flag))
        elif c == 'f':
            out.append(_ail_dt_pad(micro, 6, ''))
        elif c == 'y':
            out.append(_ail_dt_pad(year % 100, 2, flag))
        elif c == 'j':
            out.append(_ail_dt_pad(yday, 3, flag))
        elif c == 'p':
            if hour < 12:
                out.append('AM')
            else:
                out.append('PM')
        elif c == 'A':
            out.append(_AIL_DAYS[wday])
        elif c == 'a':
            out.append(_AIL_DAYS[wday][0:3])
        elif c == 'B':
            out.append(_AIL_MONTHS[month - 1])
        elif c == 'b' or c == 'h':
            out.append(_AIL_MONTHS[month - 1][0:3])
        elif c == 'w':
            out.append(str((wday + 1) % 7))
        elif c == 'u':
            out.append(str(wday + 1))
        elif c == 'U':
            out.append(_ail_dt_pad((yday - 1 + 7 - (wday + 1) % 7) // 7, 2, flag))
        elif c == 'W':
            out.append(_ail_dt_pad((yday - 1 + 7 - wday) // 7, 2, flag))
        elif c == 'c':
            out.append(_ail_dt_strftime(year, month, day, hour, minute, second, micro, '%a %b %e %H:%M:%S %Y'))
        elif c == 'x':
            out.append(_ail_dt_strftime(year, month, day, hour, minute, second, micro, '%m/%d/%y'))
        elif c == 'X' or c == 'T':
            out.append(_ail_dt_strftime(year, month, day, hour, minute, second, micro, '%H:%M:%S'))
        elif c == 'D':
            out.append(_ail_dt_strftime(year, month, day, hour, minute, second, micro, '%m/%d/%y'))
        elif c == 'F':
            out.append(_ail_dt_strftime(year, month, day, hour, minute, second, micro, '%Y-%m-%d'))
        elif c == 'R':
            out.append(_ail_dt_strftime(year, month, day, hour, minute, second, micro, '%H:%M'))
        elif c == 'Z' or c == 'z':
            pass
        elif c == '%':
            out.append('%')
        elif c == 'n':
            out.append('\n')
        elif c == 't':
            out.append('\t')
        else:
            out.append('%' + flag + c)
    return ''.join(out)


def _ail_dt_isoweek1monday(year):
    firstday = _ail_dt_ymd2ord(year, 1, 1)
    firstweekday = (firstday + 6) % 7
    week1monday = firstday - firstweekday
    if firstweekday > 3:
        week1monday = week1monday + 7
    return week1monday


class IsoCalendarDate:
    def __init__(self, year, week, weekday):
        self.year = year
        self.week = week
        self.weekday = weekday

    def __iter__(self):
        return iter((self.year, self.week, self.weekday))

    def __len__(self):
        return 3

    def __getitem__(self, i):
        return (self.year, self.week, self.weekday)[i]

    def __repr__(self):
        return 'datetime.IsoCalendarDate(year=' + str(self.year) + ', week=' + str(self.week) + ', weekday=' + str(self.weekday) + ')'

    def __eq__(self, other):
        return tuple(self) == tuple(other)


class timedelta:
    def __init__(self, days=0, seconds=0, microseconds=0, milliseconds=0, minutes=0, hours=0, weeks=0):
        d = 0
        s = 0
        us = 0
        extra = 0
        if isinstance(days, float):
            extra = extra + round(days * 86400000000.0)
        else:
            d = d + days
        if isinstance(weeks, float):
            extra = extra + round(weeks * 604800000000.0)
        else:
            d = d + weeks * 7
        if isinstance(hours, float):
            extra = extra + round(hours * 3600000000.0)
        else:
            s = s + hours * 3600
        if isinstance(minutes, float):
            extra = extra + round(minutes * 60000000.0)
        else:
            s = s + minutes * 60
        if isinstance(seconds, float):
            extra = extra + round(seconds * 1000000.0)
        else:
            s = s + seconds
        if isinstance(milliseconds, float):
            extra = extra + round(milliseconds * 1000.0)
        else:
            us = us + milliseconds * 1000
        if isinstance(microseconds, float):
            extra = extra + round(microseconds)
        else:
            us = us + microseconds
        us = us + extra
        s = s + us // 1000000
        us = us % 1000000
        d = d + s // 86400
        s = s % 86400
        if d > 999999999 or d < -999999999:
            raise OverflowError('days=' + str(d) + '; must have magnitude <= 999999999')
        self.days = d
        self.seconds = s
        self.microseconds = us

    def total_seconds(self):
        secs = self.days * 86400 + self.seconds
        if self.days > 100000000 or self.days < -100000000:
            return secs * 1.0 + self.microseconds / 1000000.0
        return (secs * 1000000 + self.microseconds) / 1000000

    def __add__(self, other):
        if not isinstance(other, timedelta):
            raise TypeError("unsupported operand type(s) for +: 'datetime.timedelta' and '" + type(other).__name__ + "'")
        return timedelta(self.days + other.days, self.seconds + other.seconds, self.microseconds + other.microseconds)

    def __sub__(self, other):
        if not isinstance(other, timedelta):
            raise TypeError("unsupported operand type(s) for -: 'datetime.timedelta' and '" + type(other).__name__ + "'")
        return timedelta(self.days - other.days, self.seconds - other.seconds, self.microseconds - other.microseconds)

    def __neg__(self):
        return timedelta(-self.days, -self.seconds, -self.microseconds)

    def __abs__(self):
        if self.days < 0:
            return timedelta(-self.days, -self.seconds, -self.microseconds)
        return timedelta(self.days, self.seconds, self.microseconds)

    def __mul__(self, k):
        if isinstance(k, float):
            return _ail_td_from_us_float(self, k)
        if not isinstance(k, int):
            raise TypeError("unsupported operand type(s) for *: 'datetime.timedelta' and '" + type(k).__name__ + "'")
        return timedelta(self.days * k, self.seconds * k, self.microseconds * k)

    def __rmul__(self, k):
        if isinstance(k, float):
            return _ail_td_from_us_float(self, k)
        if not isinstance(k, int):
            raise TypeError("unsupported operand type(s) for *: '" + type(k).__name__ + "' and 'datetime.timedelta'")
        return timedelta(self.days * k, self.seconds * k, self.microseconds * k)

    def _us(self):
        return (self.days * 86400 + self.seconds) * 1000000 + self.microseconds

    def __truediv__(self, other):
        if isinstance(other, timedelta):
            if other.days == 0 and other.seconds == 0 and other.microseconds == 0:
                raise ZeroDivisionError('division by zero')
            return self._us() / other._us()
        if isinstance(other, float):
            if other == 0.0:
                raise ZeroDivisionError('division by zero')
            return timedelta(0, 0, _ail_td_round_div(self._us(), other))
        if not isinstance(other, int):
            raise TypeError("unsupported operand type(s) for /: 'datetime.timedelta' and '" + type(other).__name__ + "'")
        if other == 0:
            raise ZeroDivisionError('division by zero')
        return timedelta(0, 0, _ail_td_round_div(self._us(), other))

    def __floordiv__(self, other):
        if isinstance(other, timedelta):
            if other.days == 0 and other.seconds == 0 and other.microseconds == 0:
                raise ZeroDivisionError('integer division or modulo by zero')
            return self._us() // other._us()
        if not isinstance(other, int):
            raise TypeError("unsupported operand type(s) for //: 'datetime.timedelta' and '" + type(other).__name__ + "'")
        if other == 0:
            raise ZeroDivisionError('integer division or modulo by zero')
        return timedelta(0, 0, self._us() // other)

    def __mod__(self, other):
        if not isinstance(other, timedelta):
            raise TypeError("unsupported operand type(s) for %: 'datetime.timedelta' and '" + type(other).__name__ + "'")
        if other.days == 0 and other.seconds == 0 and other.microseconds == 0:
            raise ZeroDivisionError('integer division or modulo by zero')
        return timedelta(0, 0, self._us() % other._us())

    def __eq__(self, other):
        if not isinstance(other, timedelta):
            return False
        return self.days == other.days and self.seconds == other.seconds and self.microseconds == other.microseconds

    def __ne__(self, other):
        if not isinstance(other, timedelta):
            return True
        return not (self.days == other.days and self.seconds == other.seconds and self.microseconds == other.microseconds)

    def _cmp(self, other, op):
        if not isinstance(other, timedelta):
            raise TypeError("'" + op + "' not supported between instances of 'datetime.timedelta' and '" + type(other).__name__ + "'")
        if self.days != other.days:
            return self.days - other.days
        if self.seconds != other.seconds:
            return self.seconds - other.seconds
        return self.microseconds - other.microseconds

    def __lt__(self, other):
        return self._cmp(other, '<') < 0

    def __le__(self, other):
        return self._cmp(other, '<=') <= 0

    def __gt__(self, other):
        return self._cmp(other, '>') > 0

    def __ge__(self, other):
        return self._cmp(other, '>=') >= 0

    def __hash__(self):
        return hash((self.days, self.seconds, self.microseconds))

    def __bool__(self):
        return self.days != 0 or self.seconds != 0 or self.microseconds != 0

    def __repr__(self):
        parts = []
        if self.days != 0:
            parts.append('days=' + str(self.days))
        if self.seconds != 0:
            parts.append('seconds=' + str(self.seconds))
        if self.microseconds != 0:
            parts.append('microseconds=' + str(self.microseconds))
        if len(parts) == 0:
            return 'datetime.timedelta(0)'
        return 'datetime.timedelta(' + ', '.join(parts) + ')'

    def __str__(self):
        mm = self.seconds // 60
        ss = self.seconds % 60
        hh = mm // 60
        mm = mm % 60
        text = str(hh) + ':' + _ail_dt_pad(mm, 2, '') + ':' + _ail_dt_pad(ss, 2, '')
        if self.days != 0:
            text = str(self.days) + ' day' + _ail_dt_plural(self.days) + ', ' + text
        if self.microseconds != 0:
            text = text + '.' + _ail_dt_pad(self.microseconds, 6, '')
        return text


def _ail_td_round_div(us, k):
    # us / k rounded to the nearest integer, ties to even (CPython's timedelta / number)
    if isinstance(k, float):
        return round(us / k)
    q = us // k
    r = us - q * k
    twice = 2 * r
    if k < 0:
        twice = -twice
        kk = -k
    else:
        kk = k
    if twice > kk or (twice == kk and q % 2 == 1):
        q = q + 1
    return q


def _ail_td_from_us_float(td, k):
    return timedelta(0, 0, round(td._us() * k))


class date:
    def __init__(self, year, month, day):
        _ail_dt_check_date(year, month, day)
        self.year = year
        self.month = month
        self.day = day

    def toordinal(self):
        return _ail_dt_ymd2ord(self.year, self.month, self.day)

    def weekday(self):
        return (self.toordinal() + 6) % 7

    def isoweekday(self):
        return (self.toordinal() + 6) % 7 + 1

    def isocalendar(self):
        year = self.year
        week1monday = _ail_dt_isoweek1monday(year)
        today = self.toordinal()
        week = (today - week1monday) // 7
        day = (today - week1monday) % 7
        if week < 0:
            year = year - 1
            week1monday = _ail_dt_isoweek1monday(year)
            week = (today - week1monday) // 7
            day = (today - week1monday) % 7
        elif week >= 52:
            if today >= _ail_dt_isoweek1monday(year + 1):
                year = year + 1
                week = 0
        return IsoCalendarDate(year, week + 1, day + 1)

    def isoformat(self):
        return _ail_dt_pad(self.year, 4, '') + '-' + _ail_dt_pad(self.month, 2, '') + '-' + _ail_dt_pad(self.day, 2, '')

    def __str__(self):
        return self.isoformat()

    def __repr__(self):
        return 'datetime.date(' + str(self.year) + ', ' + str(self.month) + ', ' + str(self.day) + ')'

    def strftime(self, fmt):
        return _ail_dt_strftime(self.year, self.month, self.day, 0, 0, 0, 0, fmt)

    def replace(self, year=None, month=None, day=None):
        y = self.year
        m = self.month
        d = self.day
        if year is not None:
            y = year
        if month is not None:
            m = month
        if day is not None:
            d = day
        return date(y, m, d)

    def __add__(self, other):
        if not isinstance(other, timedelta):
            raise TypeError("unsupported operand type(s) for +: 'datetime.date' and '" + type(other).__name__ + "'")
        return _ail_date_fromordinal_ovf(self.toordinal() + other.days)

    def __radd__(self, other):
        return self.__add__(other)

    def __sub__(self, other):
        if isinstance(other, timedelta):
            return _ail_date_fromordinal_ovf(self.toordinal() - other.days)
        if isinstance(other, date):
            return timedelta(self.toordinal() - other.toordinal())
        raise TypeError("unsupported operand type(s) for -: 'datetime.date' and '" + type(other).__name__ + "'")

    def __eq__(self, other):
        if not isinstance(other, date):
            return False
        return self.toordinal() == other.toordinal()

    def __ne__(self, other):
        if not isinstance(other, date):
            return True
        return self.toordinal() != other.toordinal()

    def __lt__(self, other):
        if not isinstance(other, date):
            raise TypeError("'<' not supported between instances of 'datetime.date' and '" + type(other).__name__ + "'")
        return self.toordinal() < other.toordinal()

    def __le__(self, other):
        if not isinstance(other, date):
            raise TypeError("'<=' not supported between instances of 'datetime.date' and '" + type(other).__name__ + "'")
        return self.toordinal() <= other.toordinal()

    def __gt__(self, other):
        if not isinstance(other, date):
            raise TypeError("'>' not supported between instances of 'datetime.date' and '" + type(other).__name__ + "'")
        return self.toordinal() > other.toordinal()

    def __ge__(self, other):
        if not isinstance(other, date):
            raise TypeError("'>=' not supported between instances of 'datetime.date' and '" + type(other).__name__ + "'")
        return self.toordinal() >= other.toordinal()

    def __hash__(self):
        return hash((self.year, self.month, self.day))


def _ail_date_fromordinal_ovf(n):
    if n < 1 or n > 3652059:
        raise OverflowError('date value out of range')
    t = _ail_dt_ord2ymd(n)
    return date(t[0], t[1], t[2])


def _ail_date_fromordinal(n):
    if n < 1 or n > 3652059:
        raise ValueError('ordinal must be >= 1')
    t = _ail_dt_ord2ymd(n)
    return date(t[0], t[1], t[2])


class datetime(date):
    def __init__(self, year, month, day, hour=0, minute=0, second=0, microsecond=0):
        _ail_dt_check_date(year, month, day)
        _ail_dt_check_time(hour, minute, second, microsecond)
        self.year = year
        self.month = month
        self.day = day
        self.hour = hour
        self.minute = minute
        self.second = second
        self.microsecond = microsecond

    def date(self):
        return _ail_make_date(self.year, self.month, self.day)

    def _us(self):
        return ((self.toordinal() * 24 + self.hour) * 60 + self.minute) * 60 + self.second

    def isoformat(self, sep='T', timespec='auto'):
        text = _ail_dt_pad(self.year, 4, '') + '-' + _ail_dt_pad(self.month, 2, '') + '-' + _ail_dt_pad(self.day, 2, '') + sep
        if timespec == 'auto':
            text = text + _ail_dt_pad(self.hour, 2, '') + ':' + _ail_dt_pad(self.minute, 2, '') + ':' + _ail_dt_pad(self.second, 2, '')
            if self.microsecond != 0:
                text = text + '.' + _ail_dt_pad(self.microsecond, 6, '')
        elif timespec == 'hours':
            text = text + _ail_dt_pad(self.hour, 2, '')
        elif timespec == 'minutes':
            text = text + _ail_dt_pad(self.hour, 2, '') + ':' + _ail_dt_pad(self.minute, 2, '')
        elif timespec == 'seconds':
            text = text + _ail_dt_pad(self.hour, 2, '') + ':' + _ail_dt_pad(self.minute, 2, '') + ':' + _ail_dt_pad(self.second, 2, '')
        elif timespec == 'milliseconds':
            text = text + _ail_dt_pad(self.hour, 2, '') + ':' + _ail_dt_pad(self.minute, 2, '') + ':' + _ail_dt_pad(self.second, 2, '') + '.' + _ail_dt_pad(self.microsecond // 1000, 3, '')
        elif timespec == 'microseconds':
            text = text + _ail_dt_pad(self.hour, 2, '') + ':' + _ail_dt_pad(self.minute, 2, '') + ':' + _ail_dt_pad(self.second, 2, '') + '.' + _ail_dt_pad(self.microsecond, 6, '')
        else:
            raise ValueError('Unknown timespec value')
        return text

    def __str__(self):
        return self.isoformat(' ')

    def __repr__(self):
        text = 'datetime.datetime(' + str(self.year) + ', ' + str(self.month) + ', ' + str(self.day) + ', ' + str(self.hour) + ', ' + str(self.minute)
        if self.second != 0 or self.microsecond != 0:
            text = text + ', ' + str(self.second)
        if self.microsecond != 0:
            text = text + ', ' + str(self.microsecond)
        return text + ')'

    def strftime(self, fmt):
        return _ail_dt_strftime(self.year, self.month, self.day, self.hour, self.minute, self.second, self.microsecond, fmt)

    def replace(self, year=None, month=None, day=None, hour=None, minute=None, second=None, microsecond=None):
        y = self.year
        mo = self.month
        d = self.day
        h = self.hour
        mi = self.minute
        s = self.second
        us = self.microsecond
        if year is not None:
            y = year
        if month is not None:
            mo = month
        if day is not None:
            d = day
        if hour is not None:
            h = hour
        if minute is not None:
            mi = minute
        if second is not None:
            s = second
        if microsecond is not None:
            us = microsecond
        return datetime(y, mo, d, h, mi, s, us)

    def __add__(self, other):
        if not isinstance(other, timedelta):
            raise TypeError("unsupported operand type(s) for +: 'datetime.datetime' and '" + type(other).__name__ + "'")
        return _ail_dt_shift(self, other.days, other.seconds, other.microseconds)

    def __radd__(self, other):
        return self.__add__(other)

    def __sub__(self, other):
        if isinstance(other, timedelta):
            return _ail_dt_shift(self, -other.days, -other.seconds, -other.microseconds)
        if isinstance(other, datetime):
            days = self.toordinal() - other.toordinal()
            secs = (self.hour - other.hour) * 3600 + (self.minute - other.minute) * 60 + (self.second - other.second)
            return timedelta(days, secs, self.microsecond - other.microsecond)
        raise TypeError("unsupported operand type(s) for -: 'datetime.datetime' and '" + type(other).__name__ + "'")

    def _key(self):
        return ((self.toordinal() * 24 + self.hour) * 60 + self.minute) * 60 + self.second

    def __eq__(self, other):
        if not isinstance(other, datetime):
            return False
        return self._key() == other._key() and self.microsecond == other.microsecond

    def __ne__(self, other):
        if not isinstance(other, datetime):
            return True
        return not (self._key() == other._key() and self.microsecond == other.microsecond)

    def __lt__(self, other):
        if not isinstance(other, datetime):
            raise TypeError("'<' not supported between instances of 'datetime.datetime' and '" + type(other).__name__ + "'")
        a = self._key()
        b = other._key()
        return a < b or (a == b and self.microsecond < other.microsecond)

    def __le__(self, other):
        if not isinstance(other, datetime):
            raise TypeError("'<=' not supported between instances of 'datetime.datetime' and '" + type(other).__name__ + "'")
        a = self._key()
        b = other._key()
        return a < b or (a == b and self.microsecond <= other.microsecond)

    def __gt__(self, other):
        if not isinstance(other, datetime):
            raise TypeError("'>' not supported between instances of 'datetime.datetime' and '" + type(other).__name__ + "'")
        a = self._key()
        b = other._key()
        return a > b or (a == b and self.microsecond > other.microsecond)

    def __ge__(self, other):
        if not isinstance(other, datetime):
            raise TypeError("'>=' not supported between instances of 'datetime.datetime' and '" + type(other).__name__ + "'")
        a = self._key()
        b = other._key()
        return a > b or (a == b and self.microsecond >= other.microsecond)

    def __hash__(self):
        return hash((self.year, self.month, self.day, self.hour, self.minute, self.second, self.microsecond))


def _ail_make_date(y, m, d):
    return date(y, m, d)


def _ail_dt_shift(dt, days, seconds, micros):
    us = dt.microsecond + micros
    s = dt.hour * 3600 + dt.minute * 60 + dt.second + seconds + us // 1000000
    us = us % 1000000
    n = dt.toordinal() + days + s // 86400
    s = s % 86400
    if n < 1 or n > 3652059:
        raise OverflowError('date value out of range')
    t = _ail_dt_ord2ymd(n)
    return datetime(t[0], t[1], t[2], s // 3600, (s % 3600) // 60, s % 60, us)


def _ail_dt_digits(s, i, count):
    # count digits at s[i:], or -1
    if i + count > len(s):
        return -1
    v = 0
    for k in range(count):
        c = s[i + k]
        if c < '0' or c > '9':
            return -1
        v = v * 10 + ord(c) - 48
    return v


def _ail_dt_bad_iso(s):
    raise ValueError('Invalid isoformat string: ' + repr(s))


def _ail_dt_parse_date(s, text):
    # YYYY-MM-DD or YYYYMMDD at the start of s: (year, month, day, index after it)
    y = _ail_dt_digits(s, 0, 4)
    if y < 0:
        _ail_dt_bad_iso(text)
    if len(s) > 4 and s[4] == '-':
        m = _ail_dt_digits(s, 5, 2)
        if m < 0 or len(s) < 8 or s[7] != '-':
            _ail_dt_bad_iso(text)
        d = _ail_dt_digits(s, 8, 2)
        if d < 0:
            _ail_dt_bad_iso(text)
        return (y, m, d, 10)
    m = _ail_dt_digits(s, 4, 2)
    d = _ail_dt_digits(s, 6, 2)
    if m < 0 or d < 0:
        _ail_dt_bad_iso(text)
    return (y, m, d, 8)


def _ail_date_fromisoformat(text):
    if not isinstance(text, str):
        raise TypeError('fromisoformat: argument must be str')
    t = _ail_dt_parse_date(text, text)
    if t[3] != len(text):
        _ail_dt_bad_iso(text)
    return date(t[0], t[1], t[2])


def _ail_datetime_fromisoformat(text):
    if not isinstance(text, str):
        raise TypeError('fromisoformat: argument must be str')
    t = _ail_dt_parse_date(text, text)
    i = t[3]
    n = len(text)
    hour = 0
    minute = 0
    second = 0
    micro = 0
    if i < n:
        i = i + 1
        hour = _ail_dt_digits(text, i, 2)
        if hour < 0:
            _ail_dt_bad_iso(text)
        i = i + 2
        if i < n and text[i] == ':':
            i = i + 1
            minute = _ail_dt_digits(text, i, 2)
            if minute < 0:
                _ail_dt_bad_iso(text)
            i = i + 2
            if i < n and text[i] == ':':
                i = i + 1
                second = _ail_dt_digits(text, i, 2)
                if second < 0:
                    _ail_dt_bad_iso(text)
                i = i + 2
        elif i < n and text[i] >= '0' and text[i] <= '9':
            minute = _ail_dt_digits(text, i, 2)
            if minute < 0:
                _ail_dt_bad_iso(text)
            i = i + 2
            if i < n and text[i] >= '0' and text[i] <= '9':
                second = _ail_dt_digits(text, i, 2)
                if second < 0:
                    _ail_dt_bad_iso(text)
                i = i + 2
        if i < n and (text[i] == '.' or text[i] == ','):
            i = i + 1
            j = i
            frac = 0
            while j < n and text[j] >= '0' and text[j] <= '9':
                if j - i < 6:
                    frac = frac * 10 + ord(text[j]) - 48
                j = j + 1
            if j == i:
                _ail_dt_bad_iso(text)
            digits = j - i
            if digits > 6:
                digits = 6
            while digits < 6:
                frac = frac * 10
                digits = digits + 1
            micro = frac
            i = j
        if i < n:
            if text[i] == 'Z' or text[i] == '+' or text[i] == '-':
                raise ValueError('timezone-aware datetimes are not supported on the general path')
            _ail_dt_bad_iso(text)
    return datetime(t[0], t[1], t[2], hour, minute, second, micro)


def _ail_dt_alt_match(alts, s, pos):
    # the first alternative (a tuple of character sets) that matches at s[pos:], as the end index; -1 if none
    for alt in alts:
        p = pos
        ok = True
        for cs in alt:
            if p < len(s) and cs.find(s[p]) >= 0:
                p = p + 1
            else:
                ok = False
                break
        if ok:
            return p
    return -1


_AIL_DIG = '0123456789'


def _ail_dt_alts(c):
    if c == 'd':
        return [('3', '01'), ('12', _AIL_DIG), ('0', '123456789'), ('123456789',), (' ', '123456789')]
    if c == 'f':
        return [(_AIL_DIG,) * 6, (_AIL_DIG,) * 5, (_AIL_DIG,) * 4, (_AIL_DIG,) * 3, (_AIL_DIG,) * 2, (_AIL_DIG,)]
    if c == 'H':
        return [('2', '0123'), ('01', _AIL_DIG), (_AIL_DIG,)]
    if c == 'I':
        return [('1', '012'), ('0', '123456789'), ('123456789',)]
    if c == 'j':
        return [('3', '6', '0123456'), ('3', '012345', _AIL_DIG), ('12', _AIL_DIG, _AIL_DIG), ('0', '123456789', _AIL_DIG),
                ('0', '0', '123456789'), ('123456789', _AIL_DIG), ('0', '123456789'), ('123456789',)]
    if c == 'm':
        return [('1', '012'), ('0', '123456789'), ('123456789',)]
    if c == 'M':
        return [('012345', _AIL_DIG), (_AIL_DIG,)]
    if c == 'S':
        return [('6', '01'), ('012345', _AIL_DIG), (_AIL_DIG,)]
    if c == 'y':
        return [(_AIL_DIG, _AIL_DIG)]
    if c == 'Y':
        return [(_AIL_DIG, _AIL_DIG, _AIL_DIG, _AIL_DIG)]
    return None


def _ail_dt_name_match(names, s, pos, short):
    # a month or weekday name (case-insensitive) at s[pos:]: (index, end) or (-1, -1)
    low = s[pos:].lower()
    k = 0
    for name in names:
        want = name.lower()
        if short:
            want = want[0:3]
        if low.startswith(want):
            return (k, pos + len(want))
        k = k + 1
    return (-1, -1)


def _ail_dt_strptime_match(fmt, fi, s, pos, vals):
    # CPython's _strptime regular expression, matched with backtracking: the end index of the match or -1.
    # vals: the dict that collects the fields (entries added after fi are dropped on a backtrack)
    n = len(fmt)
    if fi >= n:
        return pos
    ch = fmt[fi]
    if ch == '%':
        if fi + 1 >= n:
            raise ValueError("stray % in format '" + fmt + "'")
        c = fmt[fi + 1]
        alts = _ail_dt_alts(c)
        if alts is not None:
            for alt in alts:
                end = _ail_dt_alt_match([alt], s, pos)
                if end < 0:
                    continue
                old = vals.get(c)
                vals[c] = s[pos:end]
                res = _ail_dt_strptime_match(fmt, fi + 2, s, end, vals)
                if res >= 0:
                    return res
                if old is None:
                    del vals[c]
                else:
                    vals[c] = old
            return -1
        if c == 'B' or c == 'b' or c == 'A' or c == 'a':
            if c == 'B' or c == 'b':
                names = _AIL_MONTHS
            else:
                names = _AIL_DAYS
            # the regex alternation lists full names (or the three letter forms) in order
            k = 0
            while k < len(names):
                full = names[k].lower()
                if c == 'b' or c == 'a':
                    full = full[0:3]
                if s[pos:].lower().startswith(full):
                    old = vals.get(c)
                    vals[c] = k
                    res = _ail_dt_strptime_match(fmt, fi + 2, s, pos + len(full), vals)
                    if res >= 0:
                        return res
                    if old is None:
                        del vals[c]
                    else:
                        vals[c] = old
                k = k + 1
            return -1
        if c == 'p':
            low = s[pos:pos + 2].lower()
            if low == 'am' or low == 'pm':
                old = vals.get('p')
                vals['p'] = low
                res = _ail_dt_strptime_match(fmt, fi + 2, s, pos + 2, vals)
                if res >= 0:
                    return res
                if old is None:
                    del vals['p']
                else:
                    vals['p'] = old
            return -1
        if c == '%':
            if pos < len(s) and s[pos] == '%':
                return _ail_dt_strptime_match(fmt, fi + 2, s, pos + 1, vals)
            return -1
        raise ValueError("'" + c + "' is a bad directive in format '" + fmt + "'")
    if ch == ' ' or ch == '\t' or ch == '\n' or ch == '\r' or ch == '\f' or ch == '\v':
        # a run of whitespace in the format is \s+
        fj = fi
        while fj < n and (fmt[fj] == ' ' or fmt[fj] == '\t' or fmt[fj] == '\n' or fmt[fj] == '\r' or fmt[fj] == '\f' or fmt[fj] == '\v'):
            fj = fj + 1
        p = pos
        while p < len(s) and (s[p] == ' ' or s[p] == '\t' or s[p] == '\n' or s[p] == '\r' or s[p] == '\f' or s[p] == '\v'):
            p = p + 1
        if p == pos:
            return -1
        # \s+ is greedy and may give characters back
        q = p
        while q > pos:
            res = _ail_dt_strptime_match(fmt, fj, s, q, vals)
            if res >= 0:
                return res
            q = q - 1
        return -1
    if pos < len(s) and s[pos].lower() == ch.lower():
        return _ail_dt_strptime_match(fmt, fi + 1, s, pos + 1, vals)
    return -1


def _ail_datetime_strptime(text, fmt):
    if not isinstance(text, str) or not isinstance(fmt, str):
        raise TypeError('strptime() argument 1 must be str, not ' + type(text).__name__)
    vals = {}
    end = _ail_dt_strptime_match(fmt, 0, text, 0, vals)
    if end < 0:
        raise ValueError('time data ' + repr(text) + ' does not match format ' + repr(fmt))
    if end != len(text):
        raise ValueError('unconverted data remains: ' + text[end:])
    year = 1900
    month = 1
    day = 1
    hour = 0
    minute = 0
    second = 0
    micro = 0
    julian = -1
    if 'Y' in vals:
        year = int(vals['Y'])
    elif 'y' in vals:
        yy = int(vals['y'])
        if yy <= 68:
            year = 2000 + yy
        else:
            year = 1900 + yy
    if 'm' in vals:
        month = int(vals['m'])
    elif 'B' in vals:
        month = vals['B'] + 1
    elif 'b' in vals:
        month = vals['b'] + 1
    if 'd' in vals:
        day = int(vals['d'])
    if 'H' in vals:
        hour = int(vals['H'])
    elif 'I' in vals:
        hour = int(vals['I'])
        ampm = 'am'
        if 'p' in vals:
            ampm = vals['p']
        if ampm == 'am':
            if hour == 12:
                hour = 0
        elif hour != 12:
            hour = hour + 12
    if 'M' in vals:
        minute = int(vals['M'])
    if 'S' in vals:
        second = int(vals['S'])
    if 'f' in vals:
        digits = vals['f']
        while len(digits) < 6:
            digits = digits + '0'
        micro = int(digits)
    if 'j' in vals:
        julian = int(vals['j'])
    if julian >= 0 and 'm' not in vals and 'B' not in vals and 'b' not in vals and 'd' not in vals:
        t = _ail_dt_ord2ymd(_ail_dt_ymd2ord(year, 1, 1) + julian - 1)
        year = t[0]
        month = t[1]
        day = t[2]
    if second > 59:
        raise ValueError('second must be in 0..59')
    return datetime(year, month, day, hour, minute, second, micro)


def _ail_dt_format(v, spec):
    # format(value, spec) / f"{value:spec}" for a date or datetime with a strftime spec
    if isinstance(v, date):
        if spec == '':
            return str(v)
        return v.strftime(spec)
    raise ValueError('Invalid format specifier')

