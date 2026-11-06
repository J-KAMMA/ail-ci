"""G5a: the standard-library `difflib` module, shipped as AIL source.

Derived from CPython 3.12 Lib/difflib.py; PSF License, see stdlib/LICENSE-PSF.txt.

`import difflib` finds this file in the bundled `stdlib/` directory when the
program's own directory and `AIL_PATH` have no `difflib.py` (see `ail_modules.py`).
The algorithms follow CPython 3.12's `Lib/difflib.py`: `SequenceMatcher` (with
`isjunk`, `autojunk`, `find_longest_match`, `get_matching_blocks`, `get_opcodes`,
`get_grouped_opcodes`, `ratio`, `quick_ratio`, `real_quick_ratio`), `Match`,
`get_close_matches`, `Differ`, `ndiff`, `restore`, `unified_diff`, `context_diff`,
`diff_bytes`, `IS_LINE_JUNK` and `IS_CHARACTER_JUNK`.

Rewrites for the AIL compiler, with the behaviour kept:

* `Match` is a small class with `a`, `b`, `size`, iteration, indexing, equality,
  ordering, hashing and CPython's repr, instead of `collections.namedtuple`,
  which the compiler does not build here.  The compiler refuses tuple
  subclasses, so `isinstance(match, tuple)` is False where CPython's is True.
* `SequenceMatcher.set_seq2` calls `_chain_b` directly instead of the private
  name-mangled `__chain_b`.
* `get_matching_blocks` builds the `Match` objects with a loop instead of
  `map(Match._make, ...)`.
* `Differ.compare`, `_plain_replace`, `_fancy_replace`, `_fancy_helper` and
  `_qformat` return or yield ordinary lists instead of using `yield from`.
* `get_close_matches` sorts the `(score, item)` pairs directly instead of calling
  `heapq.nlargest`; the order is the same because `nlargest` compares the same
  tuples.
* `IS_LINE_JUNK` uses `strip()` instead of the compiled regular expression, and
  raises `TypeError` for bytes-like input.
* `unified_diff`, `context_diff`, `seq_ratio` and friends use plain string
  concatenation instead of `str.format`/f-strings.
* `unified_diff` and `context_diff` are classes whose instances are iterators,
  not generator functions: the general path refuses to use a function that has
  default arguments as a first-class value, and program 11 passes them to
  `diff_bytes`.  Calling them with the same arguments, iterating, `list()` and
  `next()` behave as with CPython's generators.
* `IS_CHARACTER_JUNK` takes one argument.  CPython also accepts an optional
  `ws` argument; the programs do not use it, and a one-argument function has to
  be usable as a first-class value by the general path.

Behaviour differences:

* `diff_bytes` decodes and re-encodes with `latin-1` instead of CPython's
  `ascii` + `surrogateescape`.  For byte strings whose bytes are unchanged by
  that round trip (the usual case) the output is identical.  It calls the given
  `dfunc` with the decoded lines, as CPython does, so a custom `dfunc` works.
* `HtmlDiff` and `_mdiff` are not included, so `difflib.HtmlDiff` is still
  refused by name.

"""

__all__ = ['get_close_matches', 'ndiff', 'restore', 'SequenceMatcher', 'Differ',
           'IS_CHARACTER_JUNK', 'IS_LINE_JUNK', 'context_diff', 'unified_diff',
           'diff_bytes', 'Match']


def _calculate_ratio(matches, length):
    if length:
        return 2.0 * matches / length
    return 1.0


class Match:
    def __init__(self, a, b, size):
        self.a = a
        self.b = b
        self.size = size

    def __iter__(self):
        yield self.a
        yield self.b
        yield self.size

    def __len__(self):
        return 3

    def __getitem__(self, index):
        if type(index).__name__ == 'slice':
            return (self.a, self.b, self.size)[index]
        if not isinstance(index, int):
            raise TypeError('tuple indices must be integers or slices, not ' + type(index).__name__)
        if index < 0:
            index = index + 3
        if index == 0:
            return self.a
        if index == 1:
            return self.b
        if index == 2:
            return self.size
        raise IndexError('tuple index out of range')

    def __eq__(self, other):
        if isinstance(other, Match):
            return self.a == other.a and self.b == other.b and self.size == other.size
        if isinstance(other, tuple):
            return len(other) == 3 and self.a == other[0] and self.b == other[1] and self.size == other[2]
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def _other_tuple(self, other):
        if isinstance(other, Match):
            return (other.a, other.b, other.size)
        if isinstance(other, tuple) and len(other) == 3:
            return (other[0], other[1], other[2])
        return None

    def __lt__(self, other):
        t = self._other_tuple(other)
        if t is None:
            return NotImplemented
        return (self.a, self.b, self.size) < t

    def __le__(self, other):
        t = self._other_tuple(other)
        if t is None:
            return NotImplemented
        return (self.a, self.b, self.size) <= t

    def __gt__(self, other):
        t = self._other_tuple(other)
        if t is None:
            return NotImplemented
        return (self.a, self.b, self.size) > t

    def __ge__(self, other):
        t = self._other_tuple(other)
        if t is None:
            return NotImplemented
        return (self.a, self.b, self.size) >= t

    def __hash__(self):
        return hash((self.a, self.b, self.size))

    def __repr__(self):
        return 'Match(a=' + repr(self.a) + ', b=' + repr(self.b) + ', size=' + repr(self.size) + ')'


class SequenceMatcher:
    def __init__(self, isjunk=None, a='', b='', autojunk=True):
        self.isjunk = isjunk
        self.a = None
        self.b = None
        self.autojunk = autojunk
        self.matching_blocks = None
        self.opcodes = None
        self.fullbcount = None
        self.b2j = {}
        self.bjunk = set()
        self.bpopular = set()
        self.set_seqs(a, b)

    def set_seqs(self, a, b):
        self.set_seq1(a)
        self.set_seq2(b)

    def set_seq1(self, a):
        if a is self.a:
            return
        self.a = a
        self.matching_blocks = None
        self.opcodes = None

    def set_seq2(self, b):
        if b is self.b:
            return
        self.b = b
        self.matching_blocks = None
        self.opcodes = None
        self.fullbcount = None
        self._chain_b()

    def _chain_b(self):
        b = self.b
        b2j = {}
        for i, elt in enumerate(b):
            if elt in b2j:
                indices = b2j[elt]
            else:
                indices = []
                b2j[elt] = indices
            indices.append(i)
        self.b2j = b2j
        junk = set()
        isjunk = self.isjunk
        if isjunk is not None:
            for elt in list(b2j.keys()):
                if isjunk(elt):
                    junk.add(elt)
            for elt in junk:
                del b2j[elt]
        self.bjunk = junk
        popular = set()
        n = len(b)
        if self.autojunk and n >= 200:
            ntest = n // 100 + 1
            for elt in list(b2j.keys()):
                if len(b2j[elt]) > ntest:
                    popular.add(elt)
            for elt in popular:
                del b2j[elt]
        self.bpopular = popular

    def find_longest_match(self, alo=0, ahi=None, blo=0, bhi=None):
        a = self.a
        b = self.b
        b2j = self.b2j
        junk = self.bjunk
        if ahi is None:
            ahi = len(a)
        if bhi is None:
            bhi = len(b)
        besti = alo
        bestj = blo
        bestsize = 0
        j2len = {}
        nothing = []
        for i in range(alo, ahi):
            newj2len = {}
            if a[i] in b2j:
                positions = b2j[a[i]]
            else:
                positions = nothing
            for j in positions:
                if j < blo:
                    continue
                if j >= bhi:
                    break
                k = j2len.get(j - 1, 0) + 1
                newj2len[j] = k
                if k > bestsize:
                    besti = i - k + 1
                    bestj = j - k + 1
                    bestsize = k
            j2len = newj2len
        while besti > alo and bestj > blo and b[bestj - 1] not in junk and a[besti - 1] == b[bestj - 1]:
            besti = besti - 1
            bestj = bestj - 1
            bestsize = bestsize + 1
        while besti + bestsize < ahi and bestj + bestsize < bhi and b[bestj + bestsize] not in junk \
                and a[besti + bestsize] == b[bestj + bestsize]:
            bestsize = bestsize + 1
        while besti > alo and bestj > blo and b[bestj - 1] in junk and a[besti - 1] == b[bestj - 1]:
            besti = besti - 1
            bestj = bestj - 1
            bestsize = bestsize + 1
        while besti + bestsize < ahi and bestj + bestsize < bhi and b[bestj + bestsize] in junk \
                and a[besti + bestsize] == b[bestj + bestsize]:
            bestsize = bestsize + 1
        return Match(besti, bestj, bestsize)

    def get_matching_blocks(self):
        if self.matching_blocks is not None:
            return self.matching_blocks
        la = len(self.a)
        lb = len(self.b)
        queue = [(0, la, 0, lb)]
        matching_blocks = []
        while queue:
            alo, ahi, blo, bhi = queue.pop()
            match = self.find_longest_match(alo, ahi, blo, bhi)
            i = match.a
            j = match.b
            k = match.size
            if k:
                matching_blocks.append((i, j, k))
                if alo < i and blo < j:
                    queue.append((alo, i, blo, j))
                if i + k < ahi and j + k < bhi:
                    queue.append((i + k, ahi, j + k, bhi))
        matching_blocks.sort()
        i1 = 0
        j1 = 0
        k1 = 0
        non_adjacent = []
        for i2, j2, k2 in matching_blocks:
            if i1 + k1 == i2 and j1 + k1 == j2:
                k1 = k1 + k2
            else:
                if k1:
                    non_adjacent.append((i1, j1, k1))
                i1 = i2
                j1 = j2
                k1 = k2
        if k1:
            non_adjacent.append((i1, j1, k1))
        non_adjacent.append((la, lb, 0))
        self.matching_blocks = []
        for i, j, k in non_adjacent:
            self.matching_blocks.append(Match(i, j, k))
        return self.matching_blocks

    def get_opcodes(self):
        if self.opcodes is not None:
            return self.opcodes
        i = 0
        j = 0
        answer = []
        for match in self.get_matching_blocks():
            ai = match.a
            bj = match.b
            size = match.size
            tag = ''
            if i < ai and j < bj:
                tag = 'replace'
            elif i < ai:
                tag = 'delete'
            elif j < bj:
                tag = 'insert'
            if tag:
                answer.append((tag, i, ai, j, bj))
            i = ai + size
            j = bj + size
            if size:
                answer.append(('equal', ai, i, bj, j))
        self.opcodes = answer
        return answer

    def get_grouped_opcodes(self, n=3):
        codes = self.get_opcodes()
        if not codes:
            codes = [('equal', 0, 1, 0, 1)]
        if codes[0][0] == 'equal':
            tag, i1, i2, j1, j2 = codes[0]
            codes[0] = (tag, max(i1, i2 - n), i2, max(j1, j2 - n), j2)
        if codes[-1][0] == 'equal':
            tag, i1, i2, j1, j2 = codes[-1]
            codes[-1] = (tag, i1, min(i2, i1 + n), j1, min(j2, j1 + n))
        nn = n + n
        group = []
        for tag, i1, i2, j1, j2 in codes:
            if tag == 'equal' and i2 - i1 > nn:
                group.append((tag, i1, min(i2, i1 + n), j1, min(j2, j1 + n)))
                yield group
                group = []
                i1 = max(i1, i2 - n)
                j1 = max(j1, j2 - n)
            group.append((tag, i1, i2, j1, j2))
        if group and not (len(group) == 1 and group[0][0] == 'equal'):
            yield group

    def ratio(self):
        matches = 0
        for match in self.get_matching_blocks():
            matches = matches + match.size
        return _calculate_ratio(matches, len(self.a) + len(self.b))

    def quick_ratio(self):
        if self.fullbcount is None:
            fullbcount = {}
            for elt in self.b:
                if elt in fullbcount:
                    fullbcount[elt] = fullbcount[elt] + 1
                else:
                    fullbcount[elt] = 1
            self.fullbcount = fullbcount
        fullbcount = self.fullbcount
        avail = {}
        matches = 0
        for elt in self.a:
            if elt in avail:
                numb = avail[elt]
            else:
                numb = fullbcount.get(elt, 0)
            avail[elt] = numb - 1
            if numb > 0:
                matches = matches + 1
        return _calculate_ratio(matches, len(self.a) + len(self.b))

    def real_quick_ratio(self):
        la = len(self.a)
        lb = len(self.b)
        return _calculate_ratio(min(la, lb), la + lb)


def get_close_matches(word, possibilities, n=3, cutoff=0.6):
    if not n > 0:
        raise ValueError('n must be > 0: ' + repr(n))
    if not 0.0 <= cutoff <= 1.0:
        raise ValueError('cutoff must be in [0.0, 1.0]: ' + repr(cutoff))
    result = []
    s = SequenceMatcher()
    s.set_seq2(word)
    for x in possibilities:
        s.set_seq1(x)
        if s.real_quick_ratio() >= cutoff and s.quick_ratio() >= cutoff and s.ratio() >= cutoff:
            result.append((s.ratio(), x))
    result = sorted(result, reverse=True)
    out = []
    for score, x in result[:n]:
        out.append(x)
    return out


def _keep_original_ws(s, tag_s):
    out = ''
    for c, tag_c in zip(s, tag_s):
        if tag_c == ' ' and c.isspace():
            out = out + c
        else:
            out = out + tag_c
    return out


class Differ:
    def __init__(self, linejunk=None, charjunk=None):
        self.linejunk = linejunk
        self.charjunk = charjunk

    def compare(self, a, b):
        cruncher = SequenceMatcher(self.linejunk, a, b)
        for tag, alo, ahi, blo, bhi in cruncher.get_opcodes():
            if tag == 'replace':
                g = self._fancy_replace(a, alo, ahi, b, blo, bhi)
            elif tag == 'delete':
                g = self._dump('-', a, alo, ahi)
            elif tag == 'insert':
                g = self._dump('+', b, blo, bhi)
            elif tag == 'equal':
                g = self._dump(' ', a, alo, ahi)
            else:
                raise ValueError('unknown tag ' + repr(tag))
            for line in g:
                yield line

    def _dump(self, tag, x, lo, hi):
        out = []
        for i in range(lo, hi):
            out.append(tag + ' ' + x[i])
        return out

    def _plain_replace(self, a, alo, ahi, b, blo, bhi):
        if bhi - blo < ahi - alo:
            first = self._dump('+', b, blo, bhi)
            second = self._dump('-', a, alo, ahi)
        else:
            first = self._dump('-', a, alo, ahi)
            second = self._dump('+', b, blo, bhi)
        return first + second

    def _fancy_replace(self, a, alo, ahi, b, blo, bhi):
        best_ratio = 0.74
        cutoff = 0.75
        cruncher = SequenceMatcher(self.charjunk)
        eqi = None
        eqj = None
        best_i = 0
        best_j = 0
        for j in range(blo, bhi):
            bj = b[j]
            cruncher.set_seq2(bj)
            for i in range(alo, ahi):
                ai = a[i]
                if ai == bj:
                    if eqi is None:
                        eqi = i
                        eqj = j
                    continue
                cruncher.set_seq1(ai)
                if cruncher.real_quick_ratio() > best_ratio and cruncher.quick_ratio() > best_ratio \
                        and cruncher.ratio() > best_ratio:
                    best_ratio = cruncher.ratio()
                    best_i = i
                    best_j = j
        if best_ratio < cutoff:
            if eqi is None:
                return self._plain_replace(a, alo, ahi, b, blo, bhi)
            best_i = eqi
            best_j = eqj
            best_ratio = 1.0
        else:
            eqi = None
        out = self._fancy_helper(a, alo, best_i, b, blo, best_j)
        aelt = a[best_i]
        belt = b[best_j]
        if eqi is None:
            atags = ''
            btags = ''
            cruncher.set_seqs(aelt, belt)
            for tag, ai1, ai2, bj1, bj2 in cruncher.get_opcodes():
                la = ai2 - ai1
                lb = bj2 - bj1
                if tag == 'replace':
                    atags = atags + '^' * la
                    btags = btags + '^' * lb
                elif tag == 'delete':
                    atags = atags + '-' * la
                elif tag == 'insert':
                    btags = btags + '+' * lb
                elif tag == 'equal':
                    atags = atags + ' ' * la
                    btags = btags + ' ' * lb
                else:
                    raise ValueError('unknown tag ' + repr(tag))
            out = out + self._qformat(aelt, belt, atags, btags)
        else:
            out.append('  ' + aelt)
        out = out + self._fancy_helper(a, best_i + 1, ahi, b, best_j + 1, bhi)
        return out

    def _fancy_helper(self, a, alo, ahi, b, blo, bhi):
        if alo < ahi:
            if blo < bhi:
                return self._fancy_replace(a, alo, ahi, b, blo, bhi)
            return self._dump('-', a, alo, ahi)
        if blo < bhi:
            return self._dump('+', b, blo, bhi)
        return []

    def _qformat(self, aline, bline, atags, btags):
        atags = _keep_original_ws(aline, atags).rstrip()
        btags = _keep_original_ws(bline, btags).rstrip()
        out = ['- ' + aline]
        if atags:
            out.append('? ' + atags + '\n')
        out.append('+ ' + bline)
        if btags:
            out.append('? ' + btags + '\n')
        return out


def IS_LINE_JUNK(line):
    name = type(line).__name__
    if name in ('bytes', 'bytearray', 'memoryview'):
        raise TypeError('cannot use a string pattern on a bytes-like object')
    if not isinstance(line, str):
        raise TypeError('expected string or bytes-like object, got ' + repr(name))
    s = line.strip()
    return s == '' or s == '#'


def _is_character_junk(ch, ws):
    return ch in ws


def IS_CHARACTER_JUNK(ch):
    return _is_character_junk(ch, ' \t')


def _format_range_unified(start, stop):
    beginning = start + 1
    length = stop - start
    if length == 1:
        return str(beginning)
    if not length:
        beginning = beginning - 1
    return str(beginning) + ',' + str(length)


def _unified_diff(a, b, fromfile='', tofile='', fromfiledate='', tofiledate='', n=3, lineterm='\n'):
    _check_types(a, b, fromfile, tofile, fromfiledate, tofiledate, lineterm)
    started = False
    for group in SequenceMatcher(None, a, b).get_grouped_opcodes(n):
        if not started:
            started = True
            fromdate = ''
            todate = ''
            if fromfiledate:
                fromdate = '\t' + fromfiledate
            if tofiledate:
                todate = '\t' + tofiledate
            yield '--- ' + fromfile + fromdate + lineterm
            yield '+++ ' + tofile + todate + lineterm
        first = group[0]
        last = group[-1]
        file1_range = _format_range_unified(first[1], last[2])
        file2_range = _format_range_unified(first[3], last[4])
        yield '@@ -' + file1_range + ' +' + file2_range + ' @@' + lineterm
        for tag, i1, i2, j1, j2 in group:
            if tag == 'equal':
                for line in a[i1:i2]:
                    yield ' ' + line
                continue
            if tag == 'replace' or tag == 'delete':
                for line in a[i1:i2]:
                    yield '-' + line
            if tag == 'replace' or tag == 'insert':
                for line in b[j1:j2]:
                    yield '+' + line


class unified_diff:
    def __init__(self, a, b, fromfile='', tofile='', fromfiledate='', tofiledate='', n=3, lineterm='\n'):
        self.a = a
        self.b = b
        self.fromfile = fromfile
        self.tofile = tofile
        self.fromfiledate = fromfiledate
        self.tofiledate = tofiledate
        self.n = n
        self.lineterm = lineterm
        self._lines = None

    def _start(self):
        if self._lines is None:
            self._lines = _unified_diff(self.a, self.b, self.fromfile, self.tofile,
                                        self.fromfiledate, self.tofiledate, self.n, self.lineterm)
        return self._lines

    def __iter__(self):
        return self._start()

    def __next__(self):
        return next(self._start())


def _format_range_context(start, stop):
    beginning = start + 1
    length = stop - start
    if not length:
        beginning = beginning - 1
    if length <= 1:
        return str(beginning)
    return str(beginning) + ',' + str(beginning + length - 1)


def _context_diff(a, b, fromfile='', tofile='', fromfiledate='', tofiledate='', n=3, lineterm='\n'):
    _check_types(a, b, fromfile, tofile, fromfiledate, tofiledate, lineterm)
    prefix = {'insert': '+ ', 'delete': '- ', 'replace': '! ', 'equal': '  '}
    started = False
    for group in SequenceMatcher(None, a, b).get_grouped_opcodes(n):
        if not started:
            started = True
            fromdate = ''
            todate = ''
            if fromfiledate:
                fromdate = '\t' + fromfiledate
            if tofiledate:
                todate = '\t' + tofiledate
            yield '*** ' + fromfile + fromdate + lineterm
            yield '--- ' + tofile + todate + lineterm
        first = group[0]
        last = group[-1]
        yield '***************' + lineterm
        file1_range = _format_range_context(first[1], last[2])
        yield '*** ' + file1_range + ' ****' + lineterm
        changed_a = False
        for tag, i1, i2, j1, j2 in group:
            if tag == 'replace' or tag == 'delete':
                changed_a = True
        if changed_a:
            for tag, i1, i2, j1, j2 in group:
                if tag != 'insert':
                    for line in a[i1:i2]:
                        yield prefix[tag] + line
        file2_range = _format_range_context(first[3], last[4])
        yield '--- ' + file2_range + ' ----' + lineterm
        changed_b = False
        for tag, i1, i2, j1, j2 in group:
            if tag == 'replace' or tag == 'insert':
                changed_b = True
        if changed_b:
            for tag, i1, i2, j1, j2 in group:
                if tag != 'delete':
                    for line in b[j1:j2]:
                        yield prefix[tag] + line


class context_diff:
    def __init__(self, a, b, fromfile='', tofile='', fromfiledate='', tofiledate='', n=3, lineterm='\n'):
        self.a = a
        self.b = b
        self.fromfile = fromfile
        self.tofile = tofile
        self.fromfiledate = fromfiledate
        self.tofiledate = tofiledate
        self.n = n
        self.lineterm = lineterm
        self._lines = None

    def _start(self):
        if self._lines is None:
            self._lines = _context_diff(self.a, self.b, self.fromfile, self.tofile,
                                        self.fromfiledate, self.tofiledate, self.n, self.lineterm)
        return self._lines

    def __iter__(self):
        return self._start()

    def __next__(self):
        return next(self._start())


def _check_types(a, b, fromfile, tofile, fromfiledate, tofiledate, lineterm):
    if a and not isinstance(a[0], str):
        raise TypeError('lines to compare must be str, not ' + type(a[0]).__name__ + ' (' + repr(a[0]) + ')')
    if b and not isinstance(b[0], str):
        raise TypeError('lines to compare must be str, not ' + type(b[0]).__name__ + ' (' + repr(b[0]) + ')')
    for arg in (fromfile, tofile, fromfiledate, tofiledate, lineterm):
        if not isinstance(arg, str):
            raise TypeError('all arguments must be str, not: ' + repr(arg))


def _decode_bytes(s):
    try:
        return s.decode('latin-1')
    except AttributeError:
        raise TypeError('all arguments must be bytes, not ' + type(s).__name__ + ' (' + repr(s) + ')')


def diff_bytes(dfunc, a, b, fromfile=b'', tofile=b'', fromfiledate=b'', tofiledate=b'', n=3, lineterm=b'\n'):
    new_a = []
    for x in a:
        new_a.append(_decode_bytes(x))
    new_b = []
    for x in b:
        new_b.append(_decode_bytes(x))
    fromfile = _decode_bytes(fromfile)
    tofile = _decode_bytes(tofile)
    fromfiledate = _decode_bytes(fromfiledate)
    tofiledate = _decode_bytes(tofiledate)
    lineterm = _decode_bytes(lineterm)
    lines = dfunc(new_a, new_b, fromfile, tofile, fromfiledate, tofiledate, n, lineterm)
    for line in lines:
        yield line.encode('latin-1')


def _default_charjunk(ch):
    return _is_character_junk(ch, ' \t')


def ndiff(a, b, linejunk=None, charjunk=_default_charjunk):
    return Differ(linejunk, charjunk).compare(a, b)


def restore(delta, which):
    tag = ''
    try:
        tag = {1: '- ', 2: '+ '}[int(which)]
    except KeyError:
        raise ValueError('unknown delta choice (must be 1 or 2): ' + repr(which))
    prefixes = ('  ', tag)
    for line in delta:
        if line[:2] in prefixes:
            yield line[2:]
