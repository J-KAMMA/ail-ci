import sys

HEXDIGITS = '0123456789abcdef'


class Bad(Exception):
    pass


class Val:
    def __init__(self, kind: str, sval: str, ival: int):
        self.kind = kind
        self.sval = sval
        self.ival = ival


class Row:
    def __init__(self, ok: bool, user: str, tag: str, amount: int):
        self.ok = ok
        self.user = user
        self.tag = tag
        self.amount = amount


def isdig(c: str) -> bool:
    return c >= '0' and c <= '9'


def int_in_range(s: str) -> bool:
    neg = s.startswith('-')
    d = s[1:] if neg else s
    if len(d) > 19:
        return False
    if len(d) == 19:
        lim = '9223372036854775808' if neg else '9223372036854775807'
        if d > lim:
            return False
    return True


class Parser:
    def __init__(self, s: str):
        self.s = s
        self.n = len(s)
        self.i = 0

    def ws(self):
        s = self.s
        n = self.n
        i = self.i
        while i < n:
            c = s[i]
            if c == ' ' or c == '\t' or c == '\n' or c == '\r':
                i += 1
            else:
                break
        self.i = i

    def peek(self) -> str:
        if self.i < self.n:
            return self.s[self.i]
        return ''

    def word(self, w: str):
        if self.s[self.i:self.i + len(w)] != w:
            raise Bad()
        self.i += len(w)

    def hex4(self, pos: int) -> int:
        if pos + 4 > self.n:
            raise Bad()
        v = 0
        for k in range(4):
            d = HEXDIGITS.find(self.s[pos + k].lower())
            if d < 0:
                raise Bad()
            v = v * 16 + d
        return v

    def string(self) -> str:
        # current character must be '"'
        s = self.s
        n = self.n
        i = self.i + 1
        parts: list[str] = []
        while True:
            if i >= n:
                raise Bad()
            c = s[i]
            if c == '"':
                i += 1
                break
            if c == '\\':
                if i + 1 >= n:
                    raise Bad()
                e = s[i + 1]
                if e == 'u':
                    cp = self.hex4(i + 2)
                    i += 6
                    if cp >= 0xD800 and cp <= 0xDBFF and i + 1 < n and s[i] == '\\' and s[i + 1] == 'u':
                        lo = self.hex4(i + 2)
                        if lo >= 0xDC00 and lo <= 0xDFFF:
                            cp = 0x10000 + ((cp - 0xD800) << 10) + (lo - 0xDC00)
                            i += 6
                    parts.append(chr(cp))
                else:
                    if e == '"' or e == '\\' or e == '/':
                        ch = e
                    elif e == 'b':
                        ch = chr(8)
                    elif e == 'f':
                        ch = chr(12)
                    elif e == 'n':
                        ch = '\n'
                    elif e == 'r':
                        ch = '\r'
                    elif e == 't':
                        ch = '\t'
                    else:
                        raise Bad()
                    parts.append(ch)
                    i += 2
            else:
                if ord(c) < 32:
                    raise Bad()
                parts.append(c)
                i += 1
        self.i = i
        return ''.join(parts)

    def number(self) -> Val:
        s = self.s
        n = self.n
        start = self.i
        i = start
        if s[i] == '-':
            i += 1
        if i >= n:
            raise Bad()
        c = s[i]
        if c == '0':
            i += 1
        elif c >= '1' and c <= '9':
            i += 1
            while i < n and isdig(s[i]):
                i += 1
        else:
            raise Bad()
        is_int = True
        if i < n and s[i] == '.':
            is_int = False
            i += 1
            if i >= n or not isdig(s[i]):
                raise Bad()
            while i < n and isdig(s[i]):
                i += 1
        if i < n and (s[i] == 'e' or s[i] == 'E'):
            is_int = False
            i += 1
            if i < n and (s[i] == '+' or s[i] == '-'):
                i += 1
            if i >= n or not isdig(s[i]):
                raise Bad()
            while i < n and isdig(s[i]):
                i += 1
        self.i = i
        if not is_int:
            return Val('f', '', 0)
        text = s[start:i]
        if int_in_range(text):
            return Val('i', '', int(text))
        return Val('x', '', 0)

    def value(self) -> Val:
        self.ws()
        if self.i >= self.n:
            raise Bad()
        c = self.s[self.i]
        if c == '"':
            return Val('s', self.string(), 0)
        if c == '{':
            self.skip_object()
            return Val('o', '', 0)
        if c == '[':
            self.skip_array()
            return Val('a', '', 0)
        if c == 't':
            self.word('true')
            return Val('b', '', 0)
        if c == 'f':
            self.word('false')
            return Val('b', '', 0)
        if c == 'n':
            self.word('null')
            return Val('n', '', 0)
        if c == 'N':
            self.word('NaN')
            return Val('f', '', 0)
        if c == 'I':
            self.word('Infinity')
            return Val('f', '', 0)
        if c == '-' and self.s[self.i + 1:self.i + 9] == 'Infinity':
            self.i += 9
            return Val('f', '', 0)
        return self.number()

    def skip_object(self):
        self.i += 1
        self.ws()
        if self.peek() == '}':
            self.i += 1
            return
        while True:
            self.ws()
            if self.peek() != '"':
                raise Bad()
            self.string()
            self.ws()
            if self.peek() != ':':
                raise Bad()
            self.i += 1
            self.value()
            self.ws()
            c = self.peek()
            if c == ',':
                self.i += 1
            elif c == '}':
                self.i += 1
                return
            else:
                raise Bad()

    def skip_array(self):
        self.i += 1
        self.ws()
        if self.peek() == ']':
            self.i += 1
            return
        while True:
            self.value()
            self.ws()
            c = self.peek()
            if c == ',':
                self.i += 1
            elif c == ']':
                self.i += 1
                return
            else:
                raise Bad()


def parse_row(line: str) -> Row:
    bad = Row(False, '', '', 0)
    try:
        p = Parser(line)
        p.ws()
        if p.peek() != '{':
            return bad
        p.i += 1
        ukind = ''
        usv = ''
        akind = ''
        aval = 0
        tkind = ''
        tsv = ''
        p.ws()
        if p.peek() == '}':
            p.i += 1
        else:
            while True:
                p.ws()
                if p.peek() != '"':
                    raise Bad()
                key = p.string()
                p.ws()
                if p.peek() != ':':
                    raise Bad()
                p.i += 1
                v = p.value()
                if key == 'user':
                    ukind = v.kind
                    usv = v.sval
                elif key == 'amount':
                    akind = v.kind
                    aval = v.ival
                elif key == 'tag':
                    tkind = v.kind
                    tsv = v.sval
                p.ws()
                c = p.peek()
                if c == ',':
                    p.i += 1
                elif c == '}':
                    p.i += 1
                    break
                else:
                    raise Bad()
        p.ws()
        if p.i != p.n:
            return bad
        if ukind != 's' or akind != 'i':
            return bad
        tag = ''
        if tkind == 's':
            tag = tsv
        elif tkind != '':
            return bad
        return Row(True, usv, tag, aval)
    except Exception:
        return bad


def main():
    data = sys.stdin.buffer.read().decode('utf-8', 'replace')
    lines = data.split('\n')
    bad = 0
    tag_count: dict[str, int] = {}
    tag_total: dict[str, int] = {}
    user_count: dict[str, int] = {}
    for raw in lines:
        line = raw[:-1] if raw.endswith('\r') else raw
        if line.strip(' \t') == '':
            continue
        row = parse_row(line)
        if not row.ok:
            bad += 1
            continue
        tag = row.tag
        tag_count[tag] = tag_count.get(tag, 0) + 1
        tag_total[tag] = tag_total.get(tag, 0) + row.amount
        user_count[row.user] = user_count.get(row.user, 0) + 1

    out: list[str] = []
    out.append('bad ' + str(bad) + ' tags ' + str(len(tag_count)) + ' users ' + str(len(user_count)) + '\n')
    for tag in sorted(tag_count.keys()):
        out.append('tag ' + tag + ' count ' + str(tag_count[tag]) + ' total ' + str(tag_total[tag]) + '\n')
    names = sorted(user_count.keys())
    names = sorted(names, key=lambda u: -user_count[u])
    for u in names[:10]:
        out.append('user ' + u + ' ' + str(user_count[u]) + '\n')

    sys.stdout.buffer.write(''.join(out).encode('utf-8', 'replace'))


main()
