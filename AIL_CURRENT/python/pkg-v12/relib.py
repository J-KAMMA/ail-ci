"""`import re`: a literal pattern is parsed here, at compile time, and the module gets a small Pike-VM
matcher written in the language's own Python subset (so nothing is added to the C runtime and a
program that does not import re is untouched).

* Parser: the sre_parse grammar for literals, `.`, classes (ranges, negation, \\d \\w \\s \\D \\W \\S),
  anchors `^ $ \\A \\Z \\b \\B`, `* + ? {m} {m,} {,n} {m,n}` (greedy and lazy), alternation, capturing
  / `(?:...)` / `(?P<name>...)` groups, `(?#...)`, and the flags I M S X A (also as a leading
  `(?imsxau)`), lookahead / lookbehind without groups inside (fixed width behind).  Backreferences,
  atomic groups, possessive quantifiers, conditionals, scoped flags, groups inside lookaround, a quantified group that can match the empty string and a non-ASCII character under
  IGNORECASE are refused by name (ReRefused), because the engine could not give CPython's answer.
* Engine: leftmost-first Pike VM (thread priority = backtracking order, so groups and spans are the
  ones CPython's backtracker reports) in O(len(pattern) * len(text)).  Subjects are code-point lists,
  so non-ASCII text works; \\d \\w \\s use str.isdecimal / isalnum / isspace for code points >= 128,
  which is CPython's own definition for str patterns.
* Fast path: for an ASCII str (or any bytes) subject and a pattern without lookaround, `build_dfa` makes
  a byte-class DFA at build time (state = priority-ordered thread list + what the previous character
  was, so \\b ^ $ are decided when the next character is known; the MATCH cut gives leftmost-first ends;
  a second table answers fullmatch).  It finds the span of the first match from each start the first
  character allows; the Pike VM (bytes flavour) then runs anchored on that span, with its end forced,
  only when groups are wanted.  Everything it cannot answer identically goes to the Pike VM: non-ASCII
  text, a `$` before a final newline, an empty match followed by a search that may not be empty, and
  starts that fail after a long scan (work budget 4n + 2048 bytes, so the whole call stays linear).
"""
import re as _re

# opcodes
CHAR, ANY, ANYNL, CLASS, NCLASS, SPLIT, JMP, SAVE, ASSERT, MATCH, LOOK, LMATCH = range(12)
A_BOL, A_MBOL, A_EOL, A_MEOL, A_BOS, A_EOS, A_WB, A_NWB = range(8)

I, M, S, X, A, U = 2, 8, 16, 64, 256, 32
FLAG_NAMES = {'I': I, 'IGNORECASE': I, 'M': M, 'MULTILINE': M, 'S': S, 'DOTALL': S, 'X': X, 'VERBOSE': X,
              'A': A, 'ASCII': A, 'U': U, 'UNICODE': U}
_PROG_LIMIT = 30000
_DFA_MAX_STATES = 256
_DFA_MAX_CELLS = 4096
_DFA_MAX_QUICK = 1600
_MAXGROUPS = 99
_ASCII_LETTERS = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'


class ReRefused(Exception):
    pass


def _refuse(what):
    raise ReRefused(what)


class _Parser:
    def __init__(self, pattern, flags, bytes_mode=False):
        self.bytes_mode = bytes_mode
        self.s = pattern
        self.i = 0
        self.flags = flags
        self.ngroups = 0
        self.names = {}

    def peek(self):
        return self.s[self.i] if self.i < len(self.s) else None

    def parse(self):
        s = self.s
        if s.startswith('(?') and self.i == 0:
            m = _re.match(r'\(\?([aiLmsux]+)\)', s)
            if m:
                for ch in m.group(1):
                    if ch == 'L':
                        _refuse('the locale flag (?L) is not built')
                    self.flags |= {'a': A, 'i': I, 'm': M, 's': S, 'x': X, 'u': U}[ch]
                self.i = m.end()
        node = self.alt()
        if self.i < len(s):
            _refuse('unbalanced parenthesis in the pattern')
        return node

    def skip_verbose(self):
        if not self.flags & X:
            return
        s = self.s
        while self.i < len(s):
            c = s[self.i]
            if c in ' \t\n\r\f\v':
                self.i += 1
            elif c == '#':
                while self.i < len(s) and s[self.i] != '\n':
                    self.i += 1
            else:
                break

    def alt(self):
        branches = [self.seq()]
        while self.peek() == '|':
            self.i += 1
            branches.append(self.seq())
        return branches[0] if len(branches) == 1 else ('alt', branches)

    def seq(self):
        items = []
        while True:
            self.skip_verbose()
            c = self.peek()
            if c is None or c in '|)':
                break
            atom = self.atom()
            if atom is None:                     # a comment group
                continue
            self.skip_verbose()
            c = self.peek()
            quant = None
            if c in ('*', '+', '?'):
                self.i += 1
                quant = {'*': (0, None), '+': (1, None), '?': (0, 1)}[c]
            elif c == '{':
                quant = self.brace()
            if quant is not None:
                if atom[0] in ('assert', 'look'):
                    _refuse('a quantifier on an anchor or a lookaround is not built')
                lo, hi = quant
                greedy = True
                if self.peek() == '?':
                    self.i += 1
                    greedy = False
                elif self.peek() == '+':
                    _refuse('possessive quantifiers are not built')
                self.skip_verbose()
                nxt = self.peek()
                if nxt in ('*', '+', '?') or (nxt == '{' and self.brace(peek=True) is not None):
                    _refuse('multiple repeat in the pattern')
                if hi is not None and hi < lo:
                    _refuse('min repeat greater than max repeat')
                if (lo, hi) != (1, 1) and _nullable(atom) and (hi is None or (hi > lo and hi > 1)):
                    _refuse('a quantified subpattern that can match the empty string is not built '
                            '(CPython special-cases the empty iteration)')
                if lo > 1000 or (hi is not None and hi > 1000):
                    _refuse('a repeat count above 1000 is not built')
                atom = ('rep', atom, lo, hi, greedy)
            items.append(atom)
        return items[0] if len(items) == 1 else ('seq', items)

    def brace(self, peek=False):
        """At `{`: (lo, hi) of a valid quantifier (consumed unless peek), else None (a literal `{`)."""
        m = _re.compile(r'\{([0-9]*)(?:(,)([0-9]*))?\}').match(self.s, self.i)
        if not m or m.group(0) == '{}':
            return None
        lo, comma, hi = m.groups()
        a = int(lo) if lo else 0
        b = (int(hi) if hi else None) if comma else a
        if not peek:
            self.i = m.end()
        return a, b

    def atom(self):
        s = self.s
        c = s[self.i]
        if c == '(':
            return self.group()
        if c == '[':
            return self.charset()
        if c == '.':
            self.i += 1
            return ('any',)
        if c == '^':
            self.i += 1
            return ('assert', A_MBOL if self.flags & M else A_BOL)
        if c == '$':
            self.i += 1
            return ('assert', A_MEOL if self.flags & M else A_EOL)
        if c == '\\':
            return self.escape()
        if c in '*+?':
            _refuse('nothing to repeat in the pattern')
        if c == '{':
            if self.brace(peek=True) is not None:
                _refuse('nothing to repeat in the pattern')
        self.i += 1
        return self.literal(ord(c))

    def literal(self, cp):
        if self.flags & I and cp > 127 and not self.bytes_mode:
            _refuse('IGNORECASE with a non-ASCII pattern character is not built (no Unicode case table)')
        return ('char', cp)

    def group(self):
        s = self.s
        self.i += 1
        capture = True
        name = None
        if self.peek() == '?':
            rest = s[self.i + 1:self.i + 3]
            c = rest[:1]
            if c == ':':
                self.i += 2
                capture = False
            elif c == 'P':
                if rest == 'P<':
                    m = _re.compile(r'\?P<([^\W\d]\w*)>').match(s, self.i)
                    if not m or not m.group(1).isidentifier():
                        _refuse('a bad group name in (?P<...>)')
                    name = m.group(1)
                    self.i = m.end()
                else:
                    _refuse('a named backreference (?P=name) is not built')
            elif c == '#':
                end = s.find(')', self.i)
                if end < 0:
                    _refuse('a missing ) after (?#')
                self.i = end + 1
                return None
            elif c in ('=', '!'):
                return self.look(True, c == '!')
            elif c == '<' and rest[1:2] in ('=', '!'):
                return self.look(False, rest[1] == '!')
            elif c == '>':
                _refuse('an atomic group (?>...) is not built')
            elif c == '(':
                _refuse('a conditional group (?(id)yes|no) is not built')
            elif c and (c in 'aiLmsux-'):
                _refuse('inline flags other than a leading (?aimsux) are not built')
            else:
                _refuse('an unknown extension (?%s in the pattern' % c)
        index = None
        if capture:
            self.ngroups += 1
            if self.ngroups > _MAXGROUPS:
                _refuse('more than %d groups are not built' % _MAXGROUPS)
            index = self.ngroups
            if name is not None:
                if name in self.names:
                    _refuse('redefinition of group name %r' % name)
                self.names[name] = index
        body = self.alt()
        if self.peek() != ')':
            _refuse('missing ) in the pattern')
        self.i += 1
        return ('group', index, body) if capture else ('ncgroup', body)

    def look(self, ahead, neg):
        """At the `?` of (?=  (?!  (?<=  (?<! : the zero-width node ('look', ahead, neg, body, width)."""
        self.i += 2 if ahead else 3
        before = self.ngroups
        body = self.alt()
        if self.peek() != ')':
            _refuse('missing ) in the pattern')
        self.i += 1
        if self.ngroups != before:
            _refuse('a capturing group inside a lookahead / lookbehind is not built (use (?:...))')
        width = None
        if not ahead:
            lo, hi = _width(body)
            if lo != hi:
                _refuse('look-behind requires a fixed-width pattern')
            width = lo
        return ('look', ahead, neg, body, width)

    # -- escapes ------------------------------------------------------------------------------
    def hexescape(self, count):
        text = self.s[self.i:self.i + count]
        if len(text) != count or not all(ch in '0123456789abcdefABCDEF' for ch in text):
            _refuse('an incomplete \\x \\u \\U escape')
        self.i += count
        cp = int(text, 16)
        if cp > 0x10FFFF:
            _refuse('a code point above U+10FFFF')
        return cp

    def simple_escape(self, c, in_class):
        """The code point of a one-character escape, or None."""
        table = {'n': 10, 't': 9, 'r': 13, 'f': 12, 'v': 11, 'a': 7}
        if c in table:
            return table[c]
        if c == 'x':
            return self.hexescape(2)
        if c == 'u':
            return self.hexescape(4)
        if c == 'U':
            return self.hexescape(8)
        if c == 'N':
            _refuse('\\N{name} is not built')
        if c in '01234567' and (c == '0' or in_class):
            digits = c
            while len(digits) < 3 and self.peek() is not None and self.peek() in '01234567':
                digits += self.s[self.i]
                self.i += 1
            cp = int(digits, 8)
            if cp > 0o377:
                _refuse('an octal escape above \\377')
            return cp
        return None

    def escape(self):
        self.i += 1
        c = self.peek()
        if c is None:
            _refuse('a trailing backslash in the pattern')
        self.i += 1
        if c in 'dDwWsS':
            return ('set', False, [('e', c)])
        if c in 'bB':
            return ('assert', A_WB if c == 'b' else A_NWB)
        if c == 'A':
            return ('assert', A_BOS)
        if c == 'Z':
            return ('assert', A_EOS)
        if c in '123456789':
            _refuse('a backreference (\\1 ...) is not built')
        cp = self.simple_escape(c, False)
        if cp is not None:
            return self.literal(cp)
        if c in _ASCII_LETTERS or c.isdigit():
            _refuse('a bad escape \\%s' % c)
        return self.literal(ord(c))

    def class_atom(self):
        """One class element: ('c', cp) or ('e', letter)."""
        c = self.s[self.i]
        self.i += 1
        if c != '\\':
            return ('c', ord(c))
        e = self.peek()
        if e is None:
            _refuse('a trailing backslash in the pattern')
        self.i += 1
        if e in 'dDwWsS':
            return ('e', e)
        if e == 'b':
            return ('c', 8)
        cp = self.simple_escape(e, True)
        if cp is not None:
            return ('c', cp)
        if e in _ASCII_LETTERS or e.isdigit():
            _refuse('a bad escape \\%s in a character class' % e)
        return ('c', ord(e))

    def charset(self):
        s = self.s
        self.i += 1
        neg = False
        if self.peek() == '^':
            neg = True
            self.i += 1
        items = []
        first = True
        while True:
            c = self.peek()
            if c is None:
                _refuse('an unterminated character set')
            if c == ']' and not first:
                self.i += 1
                break
            first = False
            lo = self.class_atom()
            if self.peek() == '-':
                self.i += 1
                if self.peek() == ']':
                    items.append(lo)
                    items.append(('c', ord('-')))
                    continue
                if self.peek() is None:
                    _refuse('an unterminated character set')
                hi = self.class_atom()
                if lo[0] != 'c' or hi[0] != 'c':
                    _refuse('a bad character range')
                if hi[1] < lo[1]:
                    _refuse('a bad character range (end before start)')
                items.append(('r', lo[1], hi[1]))
            else:
                items.append(lo)
        if self.flags & I and not self.bytes_mode:
            for it in items:
                if (it[0] == 'c' and it[1] > 127) or (it[0] == 'r' and it[2] > 127):
                    _refuse('IGNORECASE with a non-ASCII character class is not built (no Unicode case table)')
        return ('set', neg, items)


def _width(node):
    """(min, max) characters a node consumes."""
    kind = node[0]
    if kind in ('char', 'any', 'set'):
        return 1, 1
    if kind in ('assert', 'look'):
        return 0, 0
    if kind == 'seq':
        parts = [_width(n) for n in node[1]]
        return sum(p[0] for p in parts), sum(p[1] for p in parts)
    if kind == 'alt':
        parts = [_width(n) for n in node[1]]
        return min(p[0] for p in parts), max(p[1] for p in parts)
    if kind == 'rep':
        lo, hi = _width(node[1])
        return lo * node[2], (hi * node[3] if node[3] is not None else 10 ** 9)
    if kind == 'group':
        return _width(node[2])
    if kind == 'ncgroup':
        return _width(node[1])
    raise AssertionError(kind)


def _nullable(node):
    kind = node[0]
    if kind in ('char', 'any', 'set'):
        return False
    if kind in ('assert', 'look'):
        return True
    if kind == 'seq':
        return all(_nullable(n) for n in node[1])
    if kind == 'alt':
        return any(_nullable(n) for n in node[1])
    if kind == 'rep':
        return node[2] == 0 or _nullable(node[1])
    if kind == 'group':
        return _nullable(node[2])
    if kind == 'ncgroup':
        return _nullable(node[1])
    raise AssertionError(kind)


# -- classes -----------------------------------------------------------------------------------
def _escape_ascii(letter, c, ascii_mode):
    """Whether ASCII code point c is matched by \\d \\w \\s (or the negation) under the flags."""
    ch = chr(c)
    base = letter.lower()
    if base == 'd':
        hit = '0' <= ch <= '9'
    elif base == 'w':
        hit = ch.isalnum() or ch == '_'
    else:
        hit = ch in ' \t\n\r\f\v' if ascii_mode else ch.isspace()
    return hit if letter.islower() else not hit


def _class_tables(neg, items, flags):
    """(ascii table of 128 ints with the negation folded in, non-ASCII item list)."""
    ascii_mode = bool(flags & A)
    fold = bool(flags & I)
    table = []
    for c in range(128):
        trials = [c]
        if fold and chr(c) in _ASCII_LETTERS:
            trials.append(ord(chr(c).swapcase()))
        hit = False
        for t in trials:
            for it in items:
                if it[0] == 'c' and it[1] == t:
                    hit = True
                elif it[0] == 'r' and it[1] <= t <= it[2]:
                    hit = True
                elif it[0] == 'e' and _escape_ascii(it[1], t, ascii_mode):
                    hit = True
        table.append(int(hit != neg))
    flat = []
    codes = {'d': -1, 'D': -2, 'w': -3, 'W': -4, 's': -5, 'S': -6}
    for it in items:
        if it[0] == 'c':
            if it[1] > 127:
                flat += [it[1], it[1]]
        elif it[0] == 'r':
            if it[2] > 127:
                flat += [max(it[1], 128), it[2]]
        else:
            letter = it[1]
            if not ascii_mode:
                flat += [codes[letter], 0]
            elif letter.isupper():
                flat += [128, 0x10FFFF]
    return table, flat


class Program:
    def __init__(self, pattern, flags, is_bytes=False):
        if is_bytes:
            pattern = pattern.decode('latin-1')
            flags |= A              # a bytes pattern is ASCII-only: \w \d \s and case folding
        parser = _Parser(pattern, flags, is_bytes)
        tree = parser.parse()
        self.is_bytes = is_bytes
        self.flags = parser.flags
        self.pattern = pattern
        self.ngroups = parser.ngroups
        self.names = parser.names
        self.ops, self.xs, self.ys = [], [], []
        self.classes = []                    # (neg, table, flat items)
        self.pending = []                    # lookaround bodies, placed after the main program
        self.emit(SAVE, 0)
        self.gen(tree)
        self.emit(SAVE, 1)
        self.emit(MATCH)
        while self.pending:
            pc, node = self.pending.pop(0)
            start = len(self.ops)
            self.gen(node[3])
            self.emit(LMATCH)
            self.xs[pc] = start
            self.ys[pc] = (1 if node[2] else 0) + (0 if node[1] else 2) + 4 * (node[4] or 0)
        if len(self.ops) > _PROG_LIMIT:
            _refuse('the compiled pattern is larger than %d instructions' % _PROG_LIMIT)

    def emit(self, op, x=0, y=0):
        self.ops.append(op)
        self.xs.append(x)
        self.ys.append(y)
        if len(self.ops) > _PROG_LIMIT:
            _refuse('the compiled pattern is larger than %d instructions' % _PROG_LIMIT)
        return len(self.ops) - 1

    def add_class(self, neg, items):
        table, flat = _class_tables(neg, items, self.flags)
        key = (neg, tuple(table), tuple(flat))
        for k, existing in enumerate(self.classes):
            if existing == key:
                return k
        self.classes.append(key)
        return len(self.classes) - 1

    def gen(self, node):
        kind = node[0]
        if kind == 'char':
            cp = node[1]
            if self.flags & I and chr(cp) in _ASCII_LETTERS:
                self.emit(CLASS, self.add_class(False, [('c', cp)]))
            else:
                self.emit(CHAR, cp)
        elif kind == 'any':
            self.emit(ANYNL if self.flags & S else ANY)
        elif kind == 'set':
            neg = node[1]
            self.emit(NCLASS if neg else CLASS, self.add_class(neg, node[2]))
        elif kind == 'assert':
            self.emit(ASSERT, node[1])
        elif kind == 'look':
            self.pending.append((self.emit(LOOK), node))
        elif kind == 'seq':
            for sub in node[1]:
                self.gen(sub)
        elif kind == 'ncgroup':
            self.gen(node[1])
        elif kind == 'group':
            self.emit(SAVE, 2 * node[1])
            self.gen(node[2])
            self.emit(SAVE, 2 * node[1] + 1)
        elif kind == 'alt':
            jumps = []
            branches = node[1]
            for n, branch in enumerate(branches):
                if n < len(branches) - 1:
                    split = self.emit(SPLIT)
                    self.xs[split] = len(self.ops)
                    self.gen(branch)
                    jumps.append(self.emit(JMP))
                    self.ys[split] = len(self.ops)
                else:
                    self.gen(branch)
            for j in jumps:
                self.xs[j] = len(self.ops)
        elif kind == 'rep':
            self.gen_rep(*node[1:])
        else:
            raise AssertionError(kind)

    def split(self, greedy):
        pc = self.emit(SPLIT)
        return pc

    def set_split(self, pc, body, exit_, greedy):
        if greedy:
            self.xs[pc], self.ys[pc] = body, exit_
        else:
            self.xs[pc], self.ys[pc] = exit_, body

    def gen_rep(self, body, lo, hi, greedy):
        if hi is None and lo >= 1:
            for _ in range(lo - 1):
                self.gen(body)
            top = len(self.ops)
            self.gen(body)
            pc = self.emit(SPLIT)
            self.set_split(pc, top, len(self.ops), greedy)
            return
        for _ in range(lo):
            self.gen(body)
        if hi is None:
            pc = self.emit(SPLIT)
            self.gen(body)
            self.emit(JMP, pc)
            self.set_split(pc, pc + 1, len(self.ops), greedy)
            return
        splits = []
        for _ in range(hi - lo):
            pc = self.emit(SPLIT)
            splits.append(pc)
            self.gen(body)
        for pc in splits:
            # body begins right after the split
            self.set_split(pc, pc + 1, len(self.ops), greedy)

    def first_set(self):
        """(can match empty, can start with a non-ASCII character, 128-entry table of ASCII starters),
        reading every assertion as true (an over-approximation, which is all that skipping needs)."""
        seen = set()
        stack = [0]
        table = [0] * 128
        empty = nonascii = False
        while stack:
            pc = stack.pop()
            if pc in seen:
                continue
            seen.add(pc)
            op = self.ops[pc]
            if op == JMP:
                stack.append(self.xs[pc])
            elif op == SPLIT:
                stack += [self.xs[pc], self.ys[pc]]
            elif op in (SAVE, ASSERT, LOOK):
                stack.append(pc + 1)
            elif op == MATCH:
                empty = True
            elif op == CHAR:
                if self.xs[pc] < 128:
                    table[self.xs[pc]] = 1
                else:
                    nonascii = True
            elif op in (ANY, ANYNL):
                nonascii = True
                for c in range(128):
                    if op == ANYNL or c != 10:
                        table[c] = 1
            else:
                neg, tab, flat = self.classes[self.xs[pc]]
                for c in range(128):
                    if tab[c]:
                        table[c] = 1
                if op == NCLASS or flat:
                    nonascii = True
        return empty, nonascii, table

    # -- DFA (compile-time subset construction) -------------------------------------------------
    def _byte_hit(self, pc, c):
        """Whether the consuming instruction at pc takes the character / byte value c."""
        op = self.ops[pc]
        if op == CHAR:
            return c == self.xs[pc]
        if op == ANY:
            return c != 10
        if op == ANYNL:
            return True
        _neg, tab, flat = self.classes[self.xs[pc]]
        if c < 128:
            return bool(tab[c])
        hit = False
        for i in range(0, len(flat), 2):
            lo = flat[i]
            if lo >= 0:
                hit = hit or lo <= c <= flat[i + 1]
            elif lo == -1:
                hit = hit or chr(c).isdecimal()
            elif lo == -2:
                hit = hit or not chr(c).isdecimal()
            elif lo == -3:
                hit = hit or chr(c).isalnum()
            elif lo == -4:
                hit = hit or not chr(c).isalnum()
            elif lo == -5:
                hit = hit or chr(c).isspace()
            else:
                hit = hit or not chr(c).isspace()
        return hit != (op == NCLASS)

    def build_dfa(self):
        """Tables of a DFA over byte classes that answers "where does the leftmost-first match from here
        end" (and, for fullmatch, "does any thread end at the end of the text") for subjects whose
        characters are single bytes (ASCII str, or bytes).  The state is the priority-ordered list of
        parked threads plus what is known about the previous character (start / newline / word), so \\b,
        \\B, ^, $ and \\A \\Z are decided when the next character is known.  None when the pattern has
        a lookaround or the automaton is larger than the limits."""
        ops, xs, ys = self.ops, self.xs, self.ys
        if LOOK in ops:
            return None
        alpha = 256 if self.is_bytes else 128
        kinds = {xs[pc] for pc in range(len(ops)) if ops[pc] == ASSERT}
        need_word = bool(kinds & {A_WB, A_NWB})
        need_nl = bool(kinds & {A_MBOL, A_MEOL})
        need_none = bool(kinds & {A_BOL, A_MBOL, A_BOS, A_WB, A_NWB})

        def isw(c):
            return 48 <= c <= 57 or 65 <= c <= 90 or c == 95 or 97 <= c <= 122

        # consuming instructions, and the characters a match can start with (assertions read as true)
        consumers = []
        nullable = False
        seen = set()
        stack = [0]
        while stack:
            pc = stack.pop()
            if pc in seen:
                continue
            seen.add(pc)
            op = ops[pc]
            if op == JMP:
                stack.append(xs[pc])
            elif op == SPLIT:
                stack += [xs[pc], ys[pc]]
            elif op in (SAVE, ASSERT, LOOK):
                stack.append(pc + 1)
            elif op == MATCH:
                nullable = True
            else:
                consumers.append(pc)
        def distinct(pcs):
            first = {}
            for pc in pcs:
                first.setdefault((ops[pc], xs[pc] if ops[pc] in (CHAR, CLASS, NCLASS) else 0), pc)
            return list(first.values())

        starters = set(c for c in range(alpha) if any(self._byte_hit(pc, c) for pc in distinct(consumers)))
        splitters = distinct(pc for pc in range(len(ops)) if ops[pc] in (CHAR, ANY, ANYNL, CLASS, NCLASS))
        # byte classes: equal behaviour for every instruction, for word-ness and for newline
        sigs = {}
        cls = []
        reps = []
        for c in range(alpha):
            sig = (tuple(self._byte_hit(pc, c) for pc in splitters), nullable or c in starters,
                   need_word and isw(c), need_nl and c == 10)
            if sig not in sigs:
                sigs[sig] = len(sigs)
                reps.append(c)
            cls.append(sigs[sig])
        # renumber: bytes that cannot start a match first, so that "class >= k" means "may start"
        cand_of = {v: k[1] for k, v in sigs.items()}
        order = sorted(range(len(reps)), key=lambda k: (cand_of[k], k))
        renum = {old: new for new, old in enumerate(order)}
        cls = [renum[k] for k in cls]
        reps = [reps[old] for old in order]
        ncls = len(reps)
        firstk = 0 if nullable else sum(1 for r in reps if r not in starters)
        width = ncls + 1

        def keyfn(prev):
            return (need_none and prev is None, need_nl and prev == 10,
                    need_word and prev is not None and isw(prev))

        def holds(kind, key, c):
            none, nl, word = key
            if kind in (A_BOL, A_BOS):
                return none
            if kind == A_MBOL:
                return none or nl
            if kind in (A_EOL, A_EOS):
                return c is None
            if kind == A_MEOL:
                return c is None or c == 10
            if none and c is None:
                return False                # the engine answers False for \b and \B on an empty subject
            after = c is not None and isw(c)
            return (word != after) if kind == A_WB else (word == after)

        def visit(roots, flags, out):
            seen = set()
            stack = list(reversed(roots))
            while stack:
                pc = stack.pop()
                if pc in seen:
                    continue
                seen.add(pc)
                op = ops[pc]
                if op == JMP:
                    stack.append(xs[pc])
                elif op == SPLIT:
                    stack.append(ys[pc])
                    stack.append(xs[pc])
                elif op == SAVE:
                    stack.append(pc + 1)
                elif op == ASSERT:
                    if flags is None:
                        out.append(pc)
                    elif flags(xs[pc]):
                        stack.append(pc + 1)
                else:
                    out.append(pc)
            return out

        cut = [False]

        def build(membership):
            ids = {}
            states = [None]                      # id 0 is the dead state
            rows = [[0] * width]

            def state_of(listing, key):
                if not listing:
                    return 0
                k = (tuple(listing), key)
                if k not in ids:
                    ids[k] = len(states)
                    states.append(k)
                    rows.append(None)
                return ids[k]

            start = visit([0], None, [])
            init = [state_of(start, keyfn(r)) for r in reps] + [state_of(start, keyfn(None))]
            done = 1
            while done < len(states):
                if len(states) > _DFA_MAX_STATES:
                    return None
                listing, key = states[done]
                row = []
                for c in reps + [None]:
                    resolved = visit(listing, lambda kind: holds(kind, key, c), [])
                    matched = False
                    nxt = []
                    for pc in resolved:
                        if ops[pc] == MATCH:
                            matched = True
                            if not membership:
                                if pc != resolved[-1]:
                                    cut[0] = True
                                break
                            continue
                        if c is not None and self._byte_hit(pc, c):
                            nxt.append(pc + 1)
                    target = 0 if c is None else state_of(visit(nxt, None, []), keyfn(c))
                    row.append(((target * width) << 1) | (1 if matched else 0))
                rows[done] = row
                done += 1
            if len(rows) * width > _DFA_MAX_CELLS:
                return None
            flat = [v for row in rows for v in row]
            return flat, [i * width for i in init]

        priority = build(False)
        if priority is None:
            return None
        member = build(True) if cut[0] else priority
        if member is None:
            return None
        # a start can be rejected from the previous and the next class alone when the start state
        # depends on the previous character (\\b, ^ with MULTILINE ...): quick[prev * ncls + next]
        quick = None
        table, init = priority
        if firstk > 0 and len(set(init)) > 1 and (ncls + 1) * ncls <= _DFA_MAX_QUICK:
            quick = []
            for prev in range(ncls + 1):
                for c in range(ncls):
                    cell = table[init[prev] + c]
                    quick.append(0 if (cell >> 1) == 0 and (cell & 1) == 0 else 1)
        return {'ncls': ncls, 'width': width, 'firstk': firstk, 'cls': cls, 'priority': priority,
                'member': member, 'eol': A_EOL in kinds, 'quick': quick}

    def literal_prefix(self):
        """The ASCII characters every match starts with (consecutive CHAR instructions at the start of the
        program, groups opened on the way allowed); '' when there is none or the pattern is a bytes one."""
        if self.is_bytes:
            return ''
        pc = 0
        while self.ops[pc] == SAVE:
            pc += 1
        chars = []
        while self.ops[pc] == CHAR and self.xs[pc] < 128:
            chars.append(chr(self.xs[pc]))
            pc += 1
        return ''.join(chars)

    # -- packing ------------------------------------------------------------------------------
    def pack(self, pid):
        n = len(self.ops)
        ncap = 2 * (self.ngroups + 1)
        header = 17
        offop = header
        offx = offop + n
        offy = offx + n
        offasc = offy + n
        offcl = offasc + 128 * len(self.classes)
        offitems = offcl + len(self.classes)
        starts, items = [], []
        for _neg, _table, flat in self.classes:
            starts.append(offitems + len(items))
            items += list(flat) + [-100, 0]
        out = [0] * header
        out[0], out[1], out[2] = ncap, n, pid
        out[3] = 1 if self.flags & I else 0
        out[4] = self.ngroups
        out[5], out[6], out[7], out[8], out[9] = offop, offx, offy, offasc, offcl
        out[10] = 1 if self.flags & A else 0
        empty, nonascii, first = self.first_set()
        out[11] = 1 if empty else 0
        out[12] = 1 if nonascii else 0
        out += self.ops + self.xs + self.ys
        for _neg, table, _flat in self.classes:
            out += list(table)
        out += starts + items
        out[16] = 1 if self.literal_prefix() else 0
        out[13] = len(out)
        out += first
        dfa = self.build_dfa()
        if dfa is not None:
            d = len(out)
            out[14] = d
            out[15] = 1 if dfa['eol'] else 0
            out += [0] * 10
            out[d], out[d + 1], out[d + 2] = dfa['ncls'], dfa['width'], dfa['firstk']
            out[d + 3] = len(out)
            out += dfa['cls']
            table, init = dfa['priority']
            out[d + 4] = len(out)
            out += table
            out[d + 6] = len(out)
            out += init
            if dfa['member'] is dfa['priority']:
                out[d + 5], out[d + 7] = out[d + 4], out[d + 6]
            else:
                table, init = dfa['member']
                out[d + 5] = len(out)
                out += table
                out[d + 7] = len(out)
                out += init
            if dfa['quick'] is not None:
                out[d + 8] = len(out)
                out += dfa['quick']
        return out


class _Shadow:
    def __init__(self, program):
        self.names, self.ngroups, self.is_bytes = program.names, program.ngroups, False


# -- replacement templates ---------------------------------------------------------------------
def parse_template(repl, program):
    """re.sub's template as parts: ('lit', text) or ('grp', index).  Mirrors sre_parse.parse_template."""
    if program.is_bytes:
        parts = parse_template(repl.decode('latin-1'), _Shadow(program))
        return [(k, v.encode('latin-1') if k == 'lit' else v) for k, v in parts]
    parts = []
    lit = []
    i = 0
    n = len(repl)
    escapes = {'a': '\a', 'b': '\b', 'f': '\f', 'n': '\n', 'r': '\r', 't': '\t', 'v': '\v', '\\': '\\'}
    while i < n:
        c = repl[i]
        if c != '\\':
            lit.append(c)
            i += 1
            continue
        if i + 1 >= n:
            _refuse('a bad replacement template (trailing backslash)')
        c = repl[i + 1]
        i += 2
        if c == 'g':
            m = _re.compile(r'<([^>]*)>').match(repl, i)
            if not m:
                _refuse('a bad replacement template (\\g needs <name or number>)')
            ref = m.group(1)
            i = m.end()
            if ref.isidentifier():
                if ref not in program.names:
                    _refuse('an unknown group name %r in the replacement' % ref)
                idx = program.names[ref]
            elif ref.isascii() and ref.isdigit():
                idx = int(ref)
                if idx > program.ngroups:
                    _refuse('an invalid group reference in the replacement')
            else:
                _refuse('a bad group name in the replacement')
            if lit:
                parts.append(('lit', ''.join(lit)))
                lit = []
            parts.append(('grp', idx))
        elif c == '0':
            digits = '0'
            while i < n and len(digits) < 3 and repl[i] in '01234567':
                digits += repl[i]
                i += 1
            lit.append(chr(int(digits, 8) & 0xFF))
        elif c in '123456789':
            digits = c
            if i < n and repl[i] in '0123456789':
                digits += repl[i]
                i += 1
                if c in '0123' and digits[1] in '01234567' and i < n and repl[i] in '01234567':
                    _refuse('an octal escape in the replacement template is not built')
            idx = int(digits)
            if idx > program.ngroups:
                _refuse('an invalid group reference in the replacement')
            if lit:
                parts.append(('lit', ''.join(lit)))
                lit = []
            parts.append(('grp', idx))
        elif c in escapes:
            lit.append(escapes[c])
        elif c in _ASCII_LETTERS:
            _refuse('a bad escape \\%s in the replacement template' % c)
        else:
            lit.append('\\' + c)
    if lit:
        parts.append(('lit', ''.join(lit)))
    return parts


# -- generated module text ---------------------------------------------------------------------
_ENGINE = r'''
class _ail_re_Vm:
    def __init__(self, pcs: list[int], caps: list[int], mark: list[int], cnt: list[int], gens: list[int],
                 work: list[int], res: list[int], stack: list[int]):
        self.pcs = pcs
        self.caps = caps
        self.mark = mark
        self.cnt = cnt
        self.gens = gens
        self.work = work
        self.res = res
        self.stack = stack


class _ail_re_Wk:
    def __init__(self, v: list[int]):
        self.v = v


class _ail_re_Match:
    def __init__(self, s: str, g: list[int], pid: int):
        self.s = s
        self.g = g
        self.pid = pid

    def group(self, i: int) -> str:
        if i < 0 or 2 * i + 1 >= len(self.g):
            raise IndexError("no such group")
        a = self.g[2 * i]
        if a < 0:
            raise ValueError("re: the group did not take part in the match (None is not built)")
        return self.s[a - self.g[0]:self.g[2 * i + 1] - self.g[0]]

    def start(self, i: int) -> int:
        if i < 0 or 2 * i + 1 >= len(self.g):
            raise IndexError("no such group")
        return self.g[2 * i]

    def end(self, i: int) -> int:
        if i < 0 or 2 * i + 1 >= len(self.g):
            raise IndexError("no such group")
        return self.g[2 * i + 1]

    def gs(self, i: int) -> str:
        a = self.g[2 * i]
        if a < 0:
            return ""
        return self.s[a - self.g[0]:self.g[2 * i + 1] - self.g[0]]

    def named(self, name: str) -> int:
@NAMED@
        raise IndexError("no such group")

    def groupn(self, name: str) -> str:
        return self.group(self.named(name))

    def startn(self, name: str) -> int:
        return self.start(self.named(name))

    def endn(self, name: str) -> int:
        return self.end(self.named(name))


def _ail_re_new(p: list[int]) -> _ail_re_Vm:
    nprog = p[1]
    ncap = p[0]
    return _ail_re_Vm([0] * (2 * nprog), [0] * (2 * nprog * ncap), [0] * (2 * nprog), [0, 0], [0, 0],
                      [0] * ncap, [0] * ncap, [0] * (2 * nprog + 8))


def _ail_re_cps(p: list[int], s: str) -> list[int]:
    cps = [ord(c) for c in s]
    if p[3] == 1:
        for c in cps:
            if c > 127:
                raise ValueError("re.IGNORECASE on text with non-ASCII characters is not built")
    return cps


def _ail_re_isw(c: int, asc: int) -> int:
    if c < 0:
        return 0
    if c < 128:
        if (c >= 48 and c <= 57) or (c >= 65 and c <= 90) or c == 95 or (c >= 97 and c <= 122):
            return 1
        return 0
    if asc == 1:
        return 0
    if chr(c).isalnum():
        return 1
    return 0


def _ail_re_assert(kind: int, p: list[int], cps: list[int], n: int, pos: int) -> bool:
    if kind == 0 or kind == 4:
        return pos == 0
    if kind == 1:
        return pos == 0 or cps[pos - 1] == 10
    if kind == 2:
        return pos == n or (pos == n - 1 and cps[pos] == 10)
    if kind == 3:
        return pos == n or cps[pos] == 10
    if kind == 5:
        return pos == n
    if n == 0:
        return False
    before = 0
    after = 0
    if pos > 0:
        before = _ail_re_isw(cps[pos - 1], p[10])
    if pos < n:
        after = _ail_re_isw(cps[pos], p[10])
    if kind == 6:
        return before != after
    return before == after


def _ail_re_nonascii(p: list[int], off: int, c: int) -> int:
    i = off
    while p[i] != -100:
        lo = p[i]
        if lo >= 0:
            if lo <= c and c <= p[i + 1]:
                return 1
        elif lo == -1:
            if chr(c).isdecimal():
                return 1
        elif lo == -2:
            if not chr(c).isdecimal():
                return 1
        elif lo == -3:
            if chr(c).isalnum():
                return 1
        elif lo == -4:
            if not chr(c).isalnum():
                return 1
        elif lo == -5:
            if chr(c).isspace():
                return 1
        else:
            if not chr(c).isspace():
                return 1
        i += 2
    return 0


def _ail_re_look(p: list[int], cps: list[int], n: int, pc: int, pos: int) -> bool:
    y = p[p[7] + pc]
    sub = _ail_re_new(p)
    found = 0
    if (y // 2) % 2 == 1:
        width = y // 4
        if pos >= width:
            if _ail_re_run(sub, p, cps, n, pos - width, 0, 0, p[p[6] + pc], pos):
                found = 1
    else:
        if _ail_re_run(sub, p, cps, n, pos, 0, 0, p[p[6] + pc], -1):
            found = 1
    if y % 2 == 1:
        return found == 0
    return found == 1


def _ail_re_add(vm: _ail_re_Vm, p: list[int], cps: list[int], n: int, buf: int, pc0: int, pos: int, src: int) -> None:
    ncap = p[0]
    nprog = p[1]
    opo = p[5]
    xo = p[6]
    yo = p[7]
    if src < 0:
        for k in range(ncap):
            vm.work[k] = -1
    else:
        for k in range(ncap):
            vm.work[k] = vm.caps[src + k]
    gen = vm.gens[buf]
    base = buf * nprog
    vm.stack[0] = pc0
    vm.stack[1] = 0
    sp = 2
    while sp > 0:
        sp -= 2
        a = vm.stack[sp]
        if vm.stack[sp + 1] == 1:
            vm.work[a % 1024] = a // 1024 - 1
            continue
        pc = a
        while True:
            if vm.mark[base + pc] == gen:
                break
            vm.mark[base + pc] = gen
            op = p[opo + pc]
            if op == 6:
                pc = p[xo + pc]
            elif op == 5:
                vm.stack[sp] = p[yo + pc]
                vm.stack[sp + 1] = 0
                sp += 2
                pc = p[xo + pc]
            elif op == 7:
                slot = p[xo + pc]
                vm.stack[sp] = (vm.work[slot] + 1) * 1024 + slot
                vm.stack[sp + 1] = 1
                sp += 2
                vm.work[slot] = pos
                pc += 1
            elif op == 8:
                if _ail_re_assert(p[xo + pc], p, cps, n, pos):
                    pc += 1
                else:
                    break
            elif op == 10:
                if _ail_re_look(p, cps, n, pc, pos):
                    pc += 1
                else:
                    break
            else:
                idx = vm.cnt[buf]
                vm.pcs[base + idx] = pc
                dst = (base + idx) * ncap
                for k in range(ncap):
                    vm.caps[dst + k] = vm.work[k]
                vm.cnt[buf] = idx + 1
                break


def _ail_re_exec(vm: _ail_re_Vm, p: list[int], cps: list[int], n: int, start: int, mode: int, mustadv: int) -> bool:
    if mode == 1:
        return _ail_re_run(vm, p, cps, n, start, mode, mustadv, 0, n)
    return _ail_re_run(vm, p, cps, n, start, mode, mustadv, 0, -1)


def _ail_re_run(vm: _ail_re_Vm, p: list[int], cps: list[int], n: int, start: int, mode: int, mustadv: int,
                pc0: int, mustend: int) -> bool:
    ncap = p[0]
    nprog = p[1]
    opo = p[5]
    xo = p[6]
    offasc = p[8]
    offcl = p[9]
    skip = 0
    if mode == 2 and p[11] == 0 and pc0 == 0:
        skip = 1
    cb = 0
    vm.cnt[0] = 0
    vm.gens[0] += 1
    matched = 0
    pos = start
    while True:
        if skip == 1 and matched == 0 and vm.cnt[cb] == 0:
            while pos < n:
                c = cps[pos]
                if c < 128:
                    if p[p[13] + c] != 0:
                        break
                elif p[12] != 0:
                    break
                pos += 1
            if pos >= n:
                break
            vm.gens[cb] += 1
        if matched == 0 and (mode == 2 or pos == start):
            _ail_re_add(vm, p, cps, n, cb, pc0, pos, -1)
        if vm.cnt[cb] == 0:
            if matched != 0 or mode != 2 or pos >= n:
                break
            pos += 1
            vm.gens[cb] += 1
            continue
        nb = 1 - cb
        vm.cnt[nb] = 0
        vm.gens[nb] += 1
        c = -1
        if pos < n:
            c = cps[pos]
        i = 0
        cnt = vm.cnt[cb]
        while i < cnt:
            idx = cb * nprog + i
            pc = vm.pcs[idx]
            op = p[opo + pc]
            ok = 0
            if op == 0:
                if c == p[xo + pc]:
                    ok = 1
            elif op == 3 or op == 4:
                if c >= 0:
                    k = p[xo + pc]
                    if c < 128:
                        ok = p[offasc + k * 128 + c]
                    else:
                        ok = _ail_re_nonascii(p, p[offcl + k], c)
                        if op == 4:
                            ok = 1 - ok
            elif op == 1:
                if c >= 0 and c != 10:
                    ok = 1
            elif op == 2:
                if c >= 0:
                    ok = 1
            else:
                if (mustend >= 0 and pos != mustend) or (mustadv != 0 and pos == start):
                    ok = 0
                else:
                    for k in range(ncap):
                        vm.res[k] = vm.caps[idx * ncap + k]
                    matched = 1
                    break
            if ok != 0:
                tpc = pc + 1
                top = p[opo + tpc]
                if top <= 4 or top == 9 or top == 11:
                    if vm.mark[nb * nprog + tpc] != vm.gens[nb]:
                        vm.mark[nb * nprog + tpc] = vm.gens[nb]
                        j = vm.cnt[nb]
                        vm.pcs[nb * nprog + j] = tpc
                        src = idx * ncap
                        dst = (nb * nprog + j) * ncap
                        for k in range(ncap):
                            vm.caps[dst + k] = vm.caps[src + k]
                        vm.cnt[nb] = j + 1
                else:
                    _ail_re_add(vm, p, cps, n, nb, tpc, pos + 1, idx * ncap)
            i += 1
        cb = nb
        if pos >= n:
            break
        pos += 1
    return matched != 0


def _ail_re_dok(p: list[int], sb: bytes, n: int) -> bool:
    if p[14] == 0:
        return False
    if p[15] == 0 or n == 0:
        return True
    return sb[n - 1] != 10


def _ail_re_dp(p: list[int], sb: bytes, n: int, s: int, wk: _ail_re_Wk) -> int:
    d = p[14]
    ncls = p[d]
    co = p[d + 3]
    tb = p[d + 4]
    ib = p[d + 6]
    st = p[ib + ncls]
    if s > 0:
        st = p[ib + p[co + sb[s - 1]]]
    last = -1
    pos = s
    while pos < n:
        v = p[tb + st + p[co + sb[pos]]]
        if (v & 1) == 1:
            last = pos
        st = v >> 1
        if st == 0:
            wk.v[3] = pos + 1 - s
            return last
        pos += 1
    if (p[tb + st + ncls] & 1) == 1:
        last = n
    wk.v[3] = pos - s
    return last


def _ail_re_dm(p: list[int], sb: bytes, n: int) -> bool:
    d = p[14]
    ncls = p[d]
    co = p[d + 3]
    tb = p[d + 5]
    st = p[p[d + 7] + ncls]
    pos = 0
    while pos < n:
        st = p[tb + st + p[co + sb[pos]]] >> 1
        if st == 0:
            return False
        pos += 1
    return (p[tb + st + ncls] & 1) == 1


def _ail_re_ds(p: list[int], sb: bytes, n: int, pos: int, wk: _ail_re_Wk) -> int:
    d = p[14]
    co = p[d + 3]
    k = p[d + 2]
    qo = p[d + 8]
    ncls = p[d]
    s = pos
    while s <= n:
        if k > 0:
            if qo > 0:
                if s == 0 and n > 0:
                    if p[qo + ncls * ncls + p[co + sb[0]]] == 0:
                        s = 1
                while s > 0 and s < n and p[qo + p[co + sb[s - 1]] * ncls + p[co + sb[s]]] == 0:
                    s += 1
            else:
                while s < n and p[co + sb[s]] < k:
                    s += 1
            if s >= n:
                return -1
        e = _ail_re_dp(p, sb, n, s, wk)
        if e >= 0:
            wk.v[1] = e
            wk.v[2] = wk.v[2] - (wk.v[3] - (e - s))
            return s
        wk.v[2] = wk.v[2] - wk.v[3]
        if wk.v[2] < 0:
            wk.v[0] = s + 1
            return -2
        s += 1
    return -1


def _ail_re_span(p: list[int], sb: bytes, n: int, mode: int, wk: _ail_re_Wk) -> int:
    if mode == 1:
        if _ail_re_dm(p, sb, n):
            wk.v[1] = n
            return 0
        return -1
    if mode == 0:
        e = _ail_re_dp(p, sb, n, 0, wk)
        if e < 0:
            return -1
        wk.v[1] = e
        return 0
    return _ail_re_ds(p, sb, n, 0, wk)


def _ail_re_find(vm: _ail_re_Vm, p: list[int], sb: bytes, cps: list[int], asc: int, n: int, pos: int,
                 mustadv: int, wk: _ail_re_Wk, needg: int) -> int:
    start = pos
    if wk.v[2] >= 0 and (mustadv == 0 or p[11] == 0):
        s0 = _ail_re_ds(p, sb, n, start, wk)
        if s0 == -1:
            return -1
        if s0 >= 0:
            if needg != 0 and p[4] > 0:
                _ail_re_runY(vm, p, sb, n, s0, 0, 0, 0, wk.v[1])
            return s0
        wk.v[2] = -1
        start = wk.v[0]
    ok = False
    if asc == 1:
        ok = _ail_re_execY(vm, p, sb, n, start, 2, mustadv)
    if asc == 0:  #L
        ok = _ail_re_exec(vm, p, cps, n, start, 2, mustadv)  #L
    if not ok:
        return -1
    wk.v[1] = vm.res[1]
    return vm.res[0]


def _ail_re_do(p: list[int], s: str, mode: int) -> _ail_re_Match | None:
    @PREP@
    if mode == 2 and p[16] != 0:  #P
        if _ail_re_pre(p[2], s, 0) < 0:  #P
            return None  #P
    if asc == 1 and _ail_re_dok(p, sb, n):
        wk = _ail_re_Wk([0, 0, 4 * n + 2048, 0])
        r = _ail_re_span(p, sb, n, mode, wk)
        if r == -1:
            return None
        if r >= 0:
            if p[0] == 2:
                return _ail_re_Match(s[r:wk.v[1]], [r, wk.v[1]], p[2])
            vm = _ail_re_new(p)
            _ail_re_runY(vm, p, sb, n, r, 0, 0, 0, wk.v[1])
            g = [0] * p[0]
            for k in range(p[0]):
                g[k] = vm.res[k]
            return _ail_re_Match(s[g[0]:g[1]], g, p[2])
    vm = _ail_re_new(p)
    ok = False
    if asc == 1:
        ok = _ail_re_execY(vm, p, sb, n, 0, mode, 0)
    if asc == 0:  #L
        ok = _ail_re_exec(vm, p, cps, n, 0, mode, 0)  #L
    if ok:
        g = [0] * p[0]
        for k in range(p[0]):
            g[k] = vm.res[k]
        return _ail_re_Match(s[g[0]:g[1]], g, p[2])
    return None


def _ail_re_test(p: list[int], s: str, mode: int) -> bool:
    @PREP@
    if mode == 2 and p[16] != 0:  #P
        if _ail_re_pre(p[2], s, 0) < 0:  #P
            return False  #P
    if asc == 1 and _ail_re_dok(p, sb, n):
        wk = _ail_re_Wk([0, 0, 4 * n + 2048, 0])
        r = _ail_re_span(p, sb, n, mode, wk)
        if r >= 0:
            return True
        if r == -1:
            return False
    vm = _ail_re_new(p)
    ok = False
    if asc == 1:
        ok = _ail_re_execY(vm, p, sb, n, 0, mode, 0)
    if asc == 0:  #L
        ok = _ail_re_exec(vm, p, cps, n, 0, mode, 0)  #L
    return ok


def _ail_re_findall(p: list[int], s: str) -> list[str]:
    @PREP@
    @TEXT@
    @WK@
    vm = _ail_re_new(p)
    out: list[str] = []
    pos = 0
    mustadv = 0
    while pos <= n:
        if p[16] != 0 and asc == 1:  #P
            pos = _ail_re_pre(p[2], t2 if dec == 1 else t, pos)  #P
            if pos < 0:  #P
                break  #P
        a = _ail_re_find(vm, p, sb, cps, asc, n, pos, mustadv, wk, 1)
        if a < 0:
            break
        nm += 1
        if nm == 64 and dec == 0 and asc == 1 and n >= 4096 and pos < 1536:  #S
            t2 = sb.decode()  #S
            dec = 1  #S
        b = wk.v[1]
        if p[4] == 0:
            out.append(t[a:b])
        else:
            ga = vm.res[2]
            if ga < 0:
                out.append("")
            else:
                out.append(t[ga:vm.res[3]])
        pos = b
        mustadv = 0
        if b == a:
            mustadv = 1
    return out


def _ail_re_finditer(p: list[int], s: str) -> list[_ail_re_Match]:
    @PREP@
    @TEXT@
    @WK@
    vm = _ail_re_new(p)
    out: list[_ail_re_Match] = []
    pos = 0
    mustadv = 0
    while pos <= n:
        if p[16] != 0 and asc == 1:  #P
            pos = _ail_re_pre(p[2], t2 if dec == 1 else t, pos)  #P
            if pos < 0:  #P
                break  #P
        a = _ail_re_find(vm, p, sb, cps, asc, n, pos, mustadv, wk, 1)
        if a < 0:
            break
        nm += 1
        if nm == 64 and dec == 0 and asc == 1 and n >= 4096 and pos < 1536:  #S
            t2 = sb.decode()  #S
            dec = 1  #S
        b = wk.v[1]
        if p[0] == 2:
            out.append(_ail_re_Match(t[a:b], [a, b], p[2]))
        else:
            g = [0] * p[0]
            for k in range(p[0]):
                g[k] = vm.res[k]
            out.append(_ail_re_Match(t[g[0]:g[1]], g, p[2]))
        pos = b
        mustadv = 0
        if b == a:
            mustadv = 1
    return out


def _ail_re_split(p: list[int], s: str, maxsplit: int) -> list[str]:
    @PREP@
    @TEXT@
    @WK@
    vm = _ail_re_new(p)
    out: list[str] = []
    pos = 0
    last = 0
    mustadv = 0
    cnt = 0
    while pos <= n:
        if maxsplit != 0 and cnt >= maxsplit:
            break
        if p[16] != 0 and asc == 1:  #P
            pos = _ail_re_pre(p[2], t2 if dec == 1 else t, pos)  #P
            if pos < 0:  #P
                break  #P
        a = _ail_re_find(vm, p, sb, cps, asc, n, pos, mustadv, wk, 0)
        if a < 0:
            break
        nm += 1
        if nm == 64 and dec == 0 and asc == 1 and n >= 4096 and pos < 1536:  #S
            t2 = sb.decode()  #S
            dec = 1  #S
        b = wk.v[1]
        out.append(t[last:a])
        cnt += 1
        last = b
        pos = b
        mustadv = 0
        if b == a:
            mustadv = 1
    out.append(t[last:])
    return out


def _ail_re_plain(repl: str) -> bool:
    return "\\" not in repl


def _ail_re_sublit(p: list[int], s: str, repl: str, count: int) -> str:
    if not _ail_re_plain(repl):
        raise ValueError("re.sub: a replacement with a backslash has to be a string literal")
    @PREP@
    @TEXT@
    @WK@
    vm = _ail_re_new(p)
    out: list[str] = []
    pos = 0
    last = 0
    mustadv = 0
    cnt = 0
    while pos <= n:
        if count != 0 and cnt >= count:
            break
        if p[16] != 0 and asc == 1:  #P
            pos = _ail_re_pre(p[2], t2 if dec == 1 else t, pos)  #P
            if pos < 0:  #P
                break  #P
        a = _ail_re_find(vm, p, sb, cps, asc, n, pos, mustadv, wk, 0)
        if a < 0:
            break
        nm += 1
        if nm == 64 and dec == 0 and asc == 1 and n >= 4096 and pos < 1536:  #S
            t2 = sb.decode()  #S
            dec = 1  #S
        b = wk.v[1]
        out.append(t[last:a])
        out.append(repl)
        cnt += 1
        last = b
        pos = b
        mustadv = 0
        if b == a:
            mustadv = 1
    out.append(t[last:])
    return "".join(out)


def _ail_re_escape(s: str) -> str:
    out: list[str] = []
    for c in s:
        if c in "()[]{}?*+-|^$\\.&~# \t\n\r\v\f":
            out.append("\\")
        out.append(c)
    return "".join(out)
'''

_PREP_STR = """    sb = s.encode()
    n = len(s)
    cps: list[int] = []
    asc = 1
    if len(sb) != n:
        asc = 0
        cps = _ail_re_cps(@P@, s)
"""
_PREP_BYTES = """    sb = s
    n = len(s)
    cps: list[int] = []
    asc = 1
"""
# The pieces are cut from t, assigned once at the top of the function (so the compiler gives its slices a
# cursor: cutting from a str without the "pure ASCII" mark is otherwise O(n) per piece). A str built by
# repetition or concatenation may have lost that mark and a cursor slice costs ~360 instructions against ~60;
# when the first 64 matches come within 1536 characters (dense matches) an ASCII text of 4096+ characters
# is decoded once from its bytes (which sets the mark) and the rest of the pieces are cut from that copy t2.
# A sparse scan does not pay for the copy, which is mostly page faults.
_TEXT_STR = ("    t = s\n    t2 = \"\"\n    dec = 0\n    nm = 0\n"
             "    if @P@[16] != 0 and asc == 1 and n >= 4096:  #P\n        t2 = sb.decode()  #P\n        dec = 1  #P\n")
_TEXT_BYTES = "    t = s\n    nm = 0\n"
_WK = """    wk = _ail_re_Wk([0, 0, 4 * n + 2048, 0])
    if asc == 0 or not _ail_re_dok(@P@, sb, n):
        wk.v[2] = -1
"""

_SUB_TEMPLATE = """
def _ail_re_sub%(k)d(s: str, count: int) -> str:
%(prep)s%(text)s%(wk)s    vm = _ail_re_new(%(table)s)
    out: list[str] = []
    pos = 0
    last = 0
    mustadv = 0
    cnt = 0
    while pos <= n:
        if count != 0 and cnt >= count:
            break
        if %(table)s[16] != 0 and asc == 1:  #P
            pos = _ail_re_pre(%(pid)d, t2 if dec == 1 else t, pos)  #P
            if pos < 0:  #P
                break  #P
        a = _ail_re_find(vm, %(table)s, sb, cps, asc, n, pos, mustadv, wk, %(needg)d)
        if a < 0:
            break
        nm += 1
        if nm == 64 and dec == 0 and asc == 1 and n >= 4096 and pos < 1536:  #S
            t2 = sb.decode()  #S
            dec = 1  #S
        b = wk.v[1]
        out.append(t[last:a])
%(parts)s
        cnt += 1
        last = b
        pos = b
        mustadv = 0
        if b == a:
            mustadv = 1
    out.append(t[last:])
    return "".join(out)
"""

_SHARED_NAMES = ('_ail_re_Vm', '_ail_re_Wk', '_ail_re_new', '_ail_re_isw', '_ail_re_nonascii', '_ail_re_dok', '_ail_re_dp',
                 '_ail_re_dm', '_ail_re_ds', '_ail_re_span', '_ail_re_find')
_FLAVOR_NAMES = ('_ail_re_assert', '_ail_re_look', '_ail_re_add', '_ail_re_exec', '_ail_re_run')


def _blocks():
    """(shared core text, flavor text, api text): the engine split at its top-level definitions."""
    shared, flavor, api = [], [], []
    for block in _ENGINE.split('\n\n\n'):
        block = block.strip('\n')
        if not block:
            continue
        name = block.split('(')[0].split(':')[0].split()[1]
        (shared if name in _SHARED_NAMES else flavor if name in _FLAVOR_NAMES else api).append(block)
    return '\n\n\n'.join(shared), '\n\n\n'.join(flavor), '\n\n\n'.join(api)


def _y_flavor(flavor):
    """The Pike VM for a subject that is a bytes object (an ASCII str encoded, or a bytes subject)."""
    import re as regex
    text = regex.sub(r'\b_ail_re_(assert|look|add|exec|run)\b', r'_ail_re_\1Y', flavor)
    return text.replace('cps: list[int]', 'cps: bytes')


def _drop_marked(text, marker, keep):
    """Lines ending in `  #L` (the str-with-non-ASCII branch) or `  #P` (the literal-prefix skip) are kept with
    the marker removed, or dropped."""
    lines = []
    for line in text.split('\n'):
        if line.endswith(marker):
            if keep:
                lines.append(line[:-len(marker)])
        else:
            lines.append(line)
    return '\n'.join(lines)


def _drop_l(text, keep):
    return _drop_marked(text, '  #L', keep)


def _dual_cut(text):
    """Every statement that cuts a piece `t[a:b]` runs on t2 instead once the decoded copy exists (a statement, not
    a conditional expression: the compiler gives a slice a cursor only as a plain statement)."""
    import re as regex
    cut = regex.compile(r'(?<![\w.])t\[((?:[^\[\]]|\[[^\[\]]*\])*)\]')
    lines = []
    for line in text.split('\n'):
        if cut.search(line) and not line.lstrip().startswith(('if ', 'elif ', 'while ', 'def ', 'return ', 'for ')):
            indent = line[:len(line) - len(line.lstrip())]
            lines += [indent + 'if dec == 0:', '    ' + line, indent + 'else:', '    ' + cut.sub(r't2[\1]', line)]
        else:
            lines.append(line)
    return '\n'.join(lines)


def _str_api(api):
    return (api.replace('    @PREP@\n', _PREP_STR.replace('@P@', 'p')).replace('    @TEXT@\n', _TEXT_STR.replace('@P@', 'p'))
            .replace('    @WK@\n', _WK.replace('@P@', 'p')))


def _bytes_api(api):
    """The str wrappers respelled for bytes subjects: B-suffixed names, bytes types, bytes literals."""
    import re as regex
    sep = '\n' * 3
    api = sep.join(b for b in api.split(sep)
                   if not b.startswith('def _ail_re_escape') and not b.startswith('def _ail_re_cps'))
    api = (api.replace('    @PREP@\n', _PREP_BYTES).replace('    @TEXT@\n', _TEXT_BYTES)
           .replace('    @WK@\n', _WK.replace('@P@', 'p')))
    api = _drop_marked(_drop_marked(_drop_l(api, False), '  #P', False), '  #S', False)
    api = regex.sub(r'\b(_ail_re_(?:Match|do|test|findall|finditer|split|plain|sublit))\b', r'\1B', api)
    api = api.replace('s: str', 's: bytes').replace('repl: str', 'repl: bytes').replace('list[str]', 'list[bytes]')
    api = api.replace('def groupn(self, name: str) -> str', 'def groupn(self, name: str) -> bytes')
    api = api.replace('count: int) -> str:', 'count: int) -> bytes:')
    api = api.replace('def group(self, i: int) -> str', 'def group(self, i: int) -> bytes')
    api = api.replace('def gs(self, i: int) -> str', 'def gs(self, i: int) -> bytes')
    api = api.replace('            return ""\n        return self.s', '            return b""\n        return self.s')
    api = api.replace('out.append("")', 'out.append(b"")').replace('"".join(out)', 'b"".join(out)')
    api = api.replace('"\\\\" not in repl', 'b"\\\\" not in repl')
    api = api.replace('raise ValueError("re.sub: a replacement with a backslash has to be a string literal")',
                      'raise ValueError("re.sub: a replacement with a backslash has to be a bytes literal")')
    return api


class Library:
    """The patterns of one program and the text they add to it."""

    def __init__(self):
        self.programs = []           # Program
        self.keys = {}               # (pattern, flags, is_bytes) -> index
        self.subs = []               # text of generated sub functions
        self.sub_keys = {}
        self.uses_escape = False

    def pattern(self, pattern, flags, is_bytes=False):
        key = (pattern, flags, is_bytes)
        if key not in self.keys:
            program = Program(pattern, flags, is_bytes)
            self.keys[key] = len(self.programs)
            self.programs.append(program)
        return self.keys[key]

    def table_name(self, index):
        return '_ail_re_p%d' % index

    def sub_function(self, index, repl):
        """Name of the generated function for a literal template with escapes (count is its 2nd argument)."""
        key = (index, repl)
        if key not in self.sub_keys:
            program = self.programs[index]
            parts = parse_template(repl, program)
            lines = []
            needg = 0
            table = self.table_name(index)
            for kind, value in parts:
                if kind == 'lit':
                    lines.append('        out.append(%r)' % value)
                elif value == 0:
                    lines.append('        out.append(t[a:b])')
                else:
                    needg = 1
                    lines.append('        ga = vm.res[%d]' % (2 * value))
                    lines.append('        if ga < 0:')
                    lines.append('            out.append(%s)' % ('b""' if program.is_bytes else '""'))
                    lines.append('        else:')
                    lines.append('            out.append(t[ga:vm.res[%d]])' % (2 * value + 1))
            k = len(self.sub_keys)
            name = '_ail_re_sub%d' % k
            self.sub_keys[key] = name
            prep = (_PREP_BYTES if program.is_bytes else _PREP_STR).replace('@P@', table)
            text = _SUB_TEMPLATE % {'k': k, 'table': table, 'pid': index, 'parts': '\n'.join(lines) or '        pass',
                                    'prep': prep, 'wk': _WK.replace('@P@', table), 'needg': needg,
                                    'text': _TEXT_BYTES if program.is_bytes else _TEXT_STR.replace('@P@', table)}
            text = _drop_marked(_drop_marked(text, '  #P', bool(program.literal_prefix())), '  #S',
                                not program.is_bytes)
            if not program.is_bytes:
                text = _dual_cut(text)
            if program.is_bytes:
                text = (text.replace('s: str', 's: bytes').replace('list[str]', 'list[bytes]').replace('count: int) -> str:', 'count: int) -> bytes:')
                        .replace('"".join(out)', 'b"".join(out)'))
            self.subs.append(text)
        return self.sub_keys[key]

    def sub_callable(self, index, counted=False, literal=False):
        """Name of the generated function for `P.sub(fn, s, count)` with a callable replacement (a def or a lambda), or,
        with `literal`, a str replacement without backslashes; `counted` is subn (it returns (text, number of
        replacements)).  It walks finditer's matches and calls fn with each Match.  The general path builds the
        callable form (the typed path has no parameter of unknown type and refuses the program, which then falls
        back)."""
        key = (index, 'lit' if literal else None, counted)
        if key not in self.sub_keys:
            program = self.programs[index]
            k = len(self.sub_keys)
            name = '_ail_re_sub%d' % k
            self.sub_keys[key] = name
            sfx = 'B' if program.is_bytes else ''
            kind = 'bytes' if program.is_bytes else 'str'
            empty = 'b""' if program.is_bytes else '""'
            self.subs.append("""

def %(name)s(s: %(kind)s, fn%(ann)s, count: int) -> %(ret)s:
%(check)s    out: list[%(kind)s] = []
    last = 0
    cnt = 0
    for m in _ail_re_finditer%(sfx)s(%(table)s, s):
        if count != 0 and cnt >= count:
            break
        a = m.start(0)
        out.append(s[last:a])
%(call)s        out.append(%(piece)s)
        last = m.end(0)
        cnt += 1
    out.append(s[last:])
    return %(result)s
""" % {'name': name, 'kind': kind, 'sfx': sfx, 'table': self.table_name(index), 'ann': ': ' + kind if literal else '',
       'ret': 'tuple[%s, int]' % kind if counted else kind, 'piece': 'fn' if literal else 'r',
       'call': '' if literal else '        r = fn(m)\n        if r is None:\n            r = %s\n' % empty,
       'check': ('    if %s"\\\\" in fn:\n        raise ValueError("re.sub: a replacement with a backslash has to be a string literal")\n'
                 % ('b' if program.is_bytes else '')) if literal else '',
       'result': '(%s.join(out), cnt)' % empty if counted else '%s.join(out)' % empty})
        return self.sub_keys[key]

    def sub_any(self, index):
        """Name of the generated function for `P.sub(repl, s, count)` when the replacement's kind is not known at
        build time: a str/bytes template and a callable are both accepted at run time, as CPython does.  The
        callable branch walks finditer's matches and calls it with each Match; the template branch is the ordinary
        literal helper (a backslash in a run-time template is still refused, as CPython's own template parsing
        would give a different result than this runtime's).  Typed programs fall back to the general path."""
        key = (index, 'any')
        if key not in self.sub_keys:
            program = self.programs[index]
            k = len(self.sub_keys)
            name = '_ail_re_sub%d' % k
            self.sub_keys[key] = name
            sfx = 'B' if program.is_bytes else ''
            kind = 'bytes' if program.is_bytes else 'str'
            empty = 'b""' if program.is_bytes else '""'
            self.subs.append("""

def %(name)s(s: %(kind)s, repl, count: int) -> %(kind)s:
    if callable(repl):
        out: list[%(kind)s] = []
        last = 0
        cnt = 0
        for m in _ail_re_finditer%(sfx)s(%(table)s, s):
            if count != 0 and cnt >= count:
                break
            a = m.start(0)
            out.append(s[last:a])
            r = repl(m)
            if r is None:
                r = %(empty)s
            out.append(r)
            last = m.end(0)
            cnt += 1
        out.append(s[last:])
        return %(join)s
    return _ail_re_sublit%(sfx)s(%(table)s, s, repl, count)
""" % {'name': name, 'kind': kind, 'sfx': sfx, 'table': self.table_name(index), 'empty': empty,
       'join': '%s.join(out)' % empty})
        return self.sub_keys[key]

    def text(self):
        named = []
        for index, program in enumerate(self.programs):
            for name, group in program.names.items():
                named.append('        if self.pid == %d and name == %r:\n            return %d' % (index, name, group))
        named.append('        if self.pid < 0:\n            return 0')
        shared, flavor, api = _blocks()
        api = api.replace('@NAMED@', '\n'.join(named))
        have_l = self.uses_escape or any(not p.is_bytes for p in self.programs)
        prefixes = [(index, program.literal_prefix()) for index, program in enumerate(self.programs)
                    if program.literal_prefix()]
        parts = [_drop_l(shared, have_l), _y_flavor(flavor)]
        if have_l:
            if prefixes:
                lines = ['def _ail_re_pre(pid: int, t: str, s: int) -> int:']
                for index, prefix in prefixes:
                    lines += ['    if pid == %d:' % index, '        return t.find(%r, s)' % prefix]
                lines.append('    return s')
                parts.append('\n'.join(lines))
            parts.append(flavor)
            parts.append(_dual_cut(_drop_marked(_drop_marked(_drop_l(_str_api(api), True), '  #P', bool(prefixes)),
                                                '  #S', True)))
        if any(p.is_bytes for p in self.programs):
            parts.append(_bytes_api(api))
        tables = []
        for index, program in enumerate(self.programs):
            data = program.pack(index)
            rows = [', '.join(str(v) for v in data[i:i + 24]) for i in range(0, len(data), 24)]
            tables.append('%s = [\n    %s]\n' % (self.table_name(index), ',\n    '.join(rows)))
        return '\n\n\n'.join(parts) + '\n\n' + '\n'.join(tables) + ''.join(self.subs)
