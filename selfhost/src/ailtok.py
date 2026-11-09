"""ailtok: a Python 3.12 tokenizer written in AIL (plain Python that CPython and AIL both run).

``tokenize(text)`` returns the tokens that ``tokenize.generate_tokens(io.StringIO(text).readline)``
yields for a valid source text: the same types (OP tokens carry their exact type name, such as
``LPAR``), strings, and 1-based row / 0-based character-column start and end positions.  3.12
f-strings come out as FSTRING_START, FSTRING_MIDDLE and FSTRING_END with the replacement fields
tokenized in between.  The ENCODING token is not produced (``generate_tokens`` does not make it).

Only valid source is promised.  On text that CPython rejects, ``tokenize`` raises ``TokError``
with a message; it never returns a different token list silently for a file CPython accepts.

The module imports nothing, so a self-hosted build needs no ``tokenize`` or ``re``.
"""

# f-string frame states
MIDDLE = 0
EXPR = 1
SPEC = 2


class TokError(Exception):
    pass


class Tok:
    def __init__(self, type: str, string: str, srow: int, scol: int, erow: int, ecol: int):
        self.type = type
        self.string = string
        self.srow = srow
        self.scol = scol
        self.erow = erow
        self.ecol = ecol


class FFrame:
    """One open f-string."""

    def __init__(self, quote: str, raw: bool):
        self.quote = quote
        self.raw = raw
        self.state = MIDDLE
        # bracket depth just inside each open replacement field, and the state to return to
        self.depths = [0]
        self.rets = [0]
        self.depths.pop()
        self.rets.pop()


def op_name(s: str) -> str:
    if s == "(":
        return "LPAR"
    if s == ")":
        return "RPAR"
    if s == "[":
        return "LSQB"
    if s == "]":
        return "RSQB"
    if s == ":":
        return "COLON"
    if s == ",":
        return "COMMA"
    if s == ";":
        return "SEMI"
    if s == "+":
        return "PLUS"
    if s == "-":
        return "MINUS"
    if s == "*":
        return "STAR"
    if s == "/":
        return "SLASH"
    if s == "|":
        return "VBAR"
    if s == "&":
        return "AMPER"
    if s == "<":
        return "LESS"
    if s == ">":
        return "GREATER"
    if s == "=":
        return "EQUAL"
    if s == ".":
        return "DOT"
    if s == "%":
        return "PERCENT"
    if s == "{":
        return "LBRACE"
    if s == "}":
        return "RBRACE"
    if s == "~":
        return "TILDE"
    if s == "^":
        return "CIRCUMFLEX"
    if s == "@":
        return "AT"
    if s == "!":
        return "EXCLAMATION"
    if s == "==":
        return "EQEQUAL"
    if s == "!=":
        return "NOTEQUAL"
    if s == "<=":
        return "LESSEQUAL"
    if s == ">=":
        return "GREATEREQUAL"
    if s == "<<":
        return "LEFTSHIFT"
    if s == ">>":
        return "RIGHTSHIFT"
    if s == "**":
        return "DOUBLESTAR"
    if s == "+=":
        return "PLUSEQUAL"
    if s == "-=":
        return "MINEQUAL"
    if s == "*=":
        return "STAREQUAL"
    if s == "/=":
        return "SLASHEQUAL"
    if s == "%=":
        return "PERCENTEQUAL"
    if s == "&=":
        return "AMPEREQUAL"
    if s == "|=":
        return "VBAREQUAL"
    if s == "^=":
        return "CIRCUMFLEXEQUAL"
    if s == "//":
        return "DOUBLESLASH"
    if s == "->":
        return "RARROW"
    if s == ":=":
        return "COLONEQUAL"
    if s == "@=":
        return "ATEQUAL"
    if s == "**=":
        return "DOUBLESTAREQUAL"
    if s == "//=":
        return "DOUBLESLASHEQUAL"
    if s == "<<=":
        return "LEFTSHIFTEQUAL"
    if s == ">>=":
        return "RIGHTSHIFTEQUAL"
    if s == "...":
        return "ELLIPSIS"
    return ""


def is_name_start(c: str) -> bool:
    if c >= "a" and c <= "z":
        return True
    if c >= "A" and c <= "Z":
        return True
    if c == "_":
        return True
    if ord(c) < 128:
        return False
    # CPython accepts a Unicode identifier here and NFKC-normalises it, so `café` and `cafe\u0301`
    # name the same variable.  AIL does not build `unicodedata.normalize`, so this cannot be made
    # exact; refuse by name rather than silently keep the un-normalised spelling.  No S376 file
    # has a non-ASCII NAME token (checked with `tokenize` over CORPUS.txt).
    raise TokError("ailparse: non-ASCII identifiers are not supported")


def is_name_char(c: str) -> bool:
    if c >= "0" and c <= "9":
        return True
    if ord(c) < 128:
        return is_name_start(c)
    raise TokError("ailparse: non-ASCII identifiers are not supported")


def is_digit(c: str) -> bool:
    return c >= "0" and c <= "9"


def is_hex(c: str) -> bool:
    if c >= "0" and c <= "9":
        return True
    if c >= "a" and c <= "f":
        return True
    return c >= "A" and c <= "F"


def string_prefix_kind(p: str) -> int:
    """0: not a string prefix; 1: plain string prefix; 2: f-string prefix; 3: raw f-string."""
    q = p.lower()
    if q == "" or q == "r" or q == "u" or q == "b" or q == "br" or q == "rb":
        return 1
    if q == "f":
        return 2
    if q == "fr" or q == "rf":
        return 3
    return 0


class Tokenizer:
    def __init__(self, text: str):
        self.src = text
        self.n = len(text)
        self.i = 0
        self.toks = [Tok("", "", 0, 0, 0, 0)]
        self.toks.pop()
        # start index of each physical line; a line ends after its '\n'
        self.starts = [0]
        self.lone_cr = -1
        k = 0
        while k < self.n:
            if text[k] == "\n":
                self.starts.append(k + 1)
            elif text[k] == "\r" and self.lone_cr < 0 and (k + 1 >= self.n or text[k + 1] != "\n"):
                self.lone_cr = k
            k += 1
        self.nlines = len(self.starts)
        if self.n > 0 and text[self.n - 1] == "\n":
            self.nlines -= 1
        if self.n == 0:
            self.nlines = 0
        self.row_hint = 0
        self.indents = [0]
        self.depth = 0
        self.content = False       # a non-comment token on the current logical line
        self.at_bol = True         # at the start of a physical line that begins a logical line
        self.frames = [FFrame("", False)]
        self.frames.pop()

    # --- positions -------------------------------------------------------------------------
    def row_of(self, idx: int) -> int:
        """0-based row of character index idx."""
        r = self.row_hint
        if idx < self.starts[r]:
            lo = 0
            hi = r
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if self.starts[mid] <= idx:
                    lo = mid
                else:
                    hi = mid - 1
            r = lo
        else:
            last = len(self.starts) - 1
            while r < last and self.starts[r + 1] <= idx:
                r += 1
        self.row_hint = r
        return r

    def add(self, type: str, a: int, b: int):
        ra = self.row_of(a)
        ca = a - self.starts[ra]
        if type == "NL" or type == "NEWLINE":
            # a line break ends on its own line, as tokenize reports it
            self.toks.append(Tok(type, self.src[a:b], ra + 1, ca, ra + 1, ca + b - a))
            return
        rb = self.row_of(b)
        cb = b - self.starts[rb]
        self.toks.append(Tok(type, self.src[a:b], ra + 1, ca, rb + 1, cb))

    def add_at(self, type: str, s: str, r1: int, c1: int, r2: int, c2: int):
        self.toks.append(Tok(type, s, r1, c1, r2, c2))

    # --- helpers -----------------------------------------------------------------------------
    def peek(self, k: int) -> str:
        j = self.i + k
        if j < self.n:
            return self.src[j]
        return ""

    def newline_len(self, j: int) -> int:
        """Length of the line break at j ('\\n' or '\\r\\n'), or 0."""
        if j < self.n:
            c = self.src[j]
            if c == "\n":
                return 1
            if c == "\r" and j + 1 < self.n and self.src[j + 1] == "\n":
                return 2
        return 0

    def fail(self, msg: str):
        r = self.row_of(self.i if self.i < self.n else self.n)
        raise TokError("%s (line %d)" % (msg, r + 1))

    # --- main loop ---------------------------------------------------------------------------
    def run(self) -> list[Tok]:
        if self.lone_cr >= 0:
            # CPython's tokenizer treats a lone carriage return inconsistently; refuse it by name
            self.i = self.lone_cr
            self.fail("a carriage return not followed by a newline is not supported")
        while True:
            if len(self.frames) > 0:
                fr = self.frames[len(self.frames) - 1]
                if fr.state != EXPR:
                    self.fstring_middle(fr)
                    continue
            if self.at_bol:
                self.at_bol = False
                if self.depth == 0 and len(self.frames) == 0:
                    if self.line_start():
                        continue
            if self.i >= self.n:
                break
            self.one_token()
        self.finish()
        return self.toks

    def line_start(self) -> bool:
        """Indentation at the start of a logical line.  Returns True when the line was blank or
        comment-only (its tokens are already emitted)."""
        start = self.i
        col = 0
        j = self.i
        while j < self.n:
            c = self.src[j]
            if c == " ":
                col += 1
            elif c == "\t":
                col = (col // 8 + 1) * 8
            elif c == "\f":
                col = 0
            else:
                break
            j += 1
        self.i = j
        if j >= self.n:
            if j > start:
                # whitespace-only last line without a newline
                r = self.row_of(start)
                self.add_at("NL", "", r + 1, j - start, r + 1, j - start + 1)
            return False
        c = self.src[j]
        nl = self.newline_len(j)
        if nl > 0:
            self.add("NL", j, j + nl)
            self.i = j + nl
            self.at_bol = True
            return True
        if c == "#":
            self.comment()
            nl = self.newline_len(self.i)
            if nl > 0:
                self.add("NL", self.i, self.i + nl)
                self.i += nl
                self.at_bol = True
            else:
                r = self.row_of(self.i)
                cc = self.i - self.starts[r]
                self.add_at("NL", "", r + 1, cc, r + 1, cc + 1)
            return True
        if c == "\\" and self.newline_len(j + 1) > 0:
            # a continuation right at the start of a line: indentation still counts
            pass
        top = self.indents[len(self.indents) - 1]
        if col > top:
            self.indents.append(col)
            self.add("INDENT", start, j)
        elif col < top:
            r = self.row_of(j)
            cc = j - self.starts[r]
            while col < self.indents[len(self.indents) - 1]:
                self.indents.pop()
                self.add_at("DEDENT", "", r + 1, cc, r + 1, cc)
            if col != self.indents[len(self.indents) - 1]:
                self.fail("unindent does not match any outer indentation level")
        return False

    def comment(self):
        j = self.i
        while j < self.n and self.src[j] != "\n":
            if self.src[j] == "\r" and j + 1 < self.n and self.src[j + 1] == "\n":
                break
            j += 1
        self.add("COMMENT", self.i, j)
        self.i = j

    def one_token(self):
        c = self.src[self.i]
        if c == " " or c == "\t" or c == "\f":
            self.i += 1
            return
        nl = self.newline_len(self.i)
        if nl > 0:
            if self.depth > 0 or not self.content:
                self.add("NL", self.i, self.i + nl)
            else:
                self.add("NEWLINE", self.i, self.i + nl)
                self.content = False
            self.i += nl
            self.at_bol = True
            return
        if c == "\r":
            self.i += 1
            return
        if c == "#":
            self.comment()
            return
        if c == "\\":
            nl = self.newline_len(self.i + 1)
            if nl > 0:
                self.i += 1 + nl
                if self.i >= self.n:
                    self.fail("unexpected EOF in multi-line statement")
                return
            self.fail("unexpected character after line continuation character")
        self.content = True
        if is_name_start(c):
            j = self.i + 1
            while j < self.n and is_name_char(self.src[j]):
                j += 1
            if j < self.n and (self.src[j] == "'" or self.src[j] == '"') and j - self.i <= 2:
                kind = string_prefix_kind(self.src[self.i:j])
                if kind == 1:
                    self.string(self.i, j)
                    return
                if kind >= 2:
                    self.fstring_start(self.i, j, kind == 3)
                    return
            self.add("NAME", self.i, j)
            self.i = j
            return
        if c == "'" or c == '"':
            self.string(self.i, self.i)
            return
        if is_digit(c) or (c == "." and is_digit(self.peek(1))):
            self.number()
            return
        self.operator()

    # --- numbers -----------------------------------------------------------------------------
    def digits(self, j: int, hexd: bool) -> int:
        while j < self.n:
            d = self.src[j]
            if d == "_":
                j += 1
                continue
            if hexd:
                if not is_hex(d):
                    break
            elif not is_digit(d):
                break
            j += 1
        return j

    def number(self):
        s = self.src
        j = self.i
        if s[j] == "0" and j + 1 < self.n and (s[j + 1] in "xXoObB"):
            j = self.digits(j + 2, s[j + 1] == "x" or s[j + 1] == "X")
            self.add("NUMBER", self.i, j)
            self.i = j
            return
        j = self.digits(j, False)
        if j < self.n and s[j] == ".":
            j = self.digits(j + 1, False)
        if j < self.n and (s[j] == "e" or s[j] == "E"):
            k = j + 1
            if k < self.n and (s[k] == "+" or s[k] == "-"):
                k += 1
            if k < self.n and is_digit(s[k]):
                j = self.digits(k, False)
        if j < self.n and (s[j] == "j" or s[j] == "J"):
            j += 1
        self.add("NUMBER", self.i, j)
        self.i = j

    # --- operators ---------------------------------------------------------------------------
    def operator(self):
        s = self.src
        c = s[self.i]
        if len(self.frames) > 0:
            fr = self.frames[len(self.frames) - 1]
            if len(fr.depths) > 0 and self.depth == fr.depths[len(fr.depths) - 1]:
                if c == "}":
                    self.add("RBRACE", self.i, self.i + 1)
                    self.i += 1
                    self.depth -= 1
                    fr.depths.pop()
                    fr.state = fr.rets.pop()
                    return
                if c == ":":
                    self.add("COLON", self.i, self.i + 1)
                    self.i += 1
                    fr.state = SPEC
                    return
        name = ""
        width = 3
        while width > 0:
            if self.i + width <= self.n:
                name = op_name(s[self.i:self.i + width])
                if name != "":
                    break
            width -= 1
        if name == "":
            self.fail("invalid character %r" % c)
        self.add(name, self.i, self.i + width)
        self.i += width
        if c == "(" or c == "[" or c == "{":
            self.depth += 1
        elif width == 1 and (c == ")" or c == "]" or c == "}"):
            if self.depth > 0:
                self.depth -= 1

    # --- strings -----------------------------------------------------------------------------
    def string(self, start: int, q: int):
        """A plain string literal: prefix in [start, q), quote at q."""
        s = self.src
        quote = s[q]
        triple = q + 2 < self.n and s[q + 1] == quote and s[q + 2] == quote
        j = q + 3 if triple else q + 1
        while True:
            if j >= self.n:
                self.i = start
                self.fail("unterminated string literal")
            c = s[j]
            if c == "\\":
                j += 1 + max(1, self.newline_len(j + 1))
                continue
            if c == quote:
                if not triple:
                    j += 1
                    break
                if j + 2 < self.n and s[j + 1] == quote and s[j + 2] == quote:
                    j += 3
                    break
            elif c == "\n" and not triple:
                self.i = start
                self.fail("unterminated string literal")
            j += 1
        if j > self.n:
            j = self.n
        self.add("STRING", start, j)
        self.i = j

    def fstring_start(self, start: int, q: int, raw: bool):
        s = self.src
        quote = s[q]
        if q + 2 < self.n and s[q + 1] == quote and s[q + 2] == quote:
            quote = quote + quote + quote
        end = q + len(quote)
        self.add("FSTRING_START", start, end)
        self.i = end
        self.frames.append(FFrame(quote, raw))

    def fstring_middle(self, fr: FFrame):
        """Scan literal text of the innermost f-string (MIDDLE or SPEC state) up to the next
        replacement field, the closing brace of the field, or the closing quote."""
        s = self.src
        start = self.i
        j = self.i
        ql = len(fr.quote)
        q0 = fr.quote[0]
        while True:
            if j >= self.n:
                self.i = start
                self.fail("unterminated f-string literal")
            c = s[j]
            if c == "\\":
                if not fr.raw and j + 1 < self.n and s[j + 1] == "N" and j + 2 < self.n and s[j + 2] == "{":
                    k = j + 3
                    while k < self.n and s[k] != "}":
                        k += 1
                    j = k + 1
                    continue
                if j + 1 < self.n and (s[j + 1] == "{" or s[j + 1] == "}"):
                    j += 1
                    continue
                j += 1 + max(1, self.newline_len(j + 1))
                continue
            if c == q0 and (ql == 1 or (j + 2 < self.n and s[j + 1] == q0 and s[j + 2] == q0)):
                if fr.state == SPEC:
                    self.i = j
                    self.fail("f-string: expecting '}'")
                if j > start:
                    self.add("FSTRING_MIDDLE", start, j)
                self.add("FSTRING_END", j, j + ql)
                self.i = j + ql
                self.frames.pop()
                return
            if c == "\n" and ql == 1:
                self.i = j
                self.fail("unterminated f-string literal")
            if c == "{":
                if fr.state == MIDDLE and j + 1 < self.n and s[j + 1] == "{":
                    self.add("FSTRING_MIDDLE", start, j + 1)
                    j += 2
                    start = j
                    continue
                if j > start:
                    self.add("FSTRING_MIDDLE", start, j)
                self.add("LBRACE", j, j + 1)
                self.i = j + 1
                self.depth += 1
                fr.rets.append(fr.state)
                fr.depths.append(self.depth)
                fr.state = EXPR
                return
            if c == "}":
                if fr.state == MIDDLE and j + 1 < self.n and s[j + 1] == "}":
                    self.add("FSTRING_MIDDLE", start, j + 1)
                    j += 2
                    start = j
                    continue
                if fr.state == SPEC:
                    self.add("FSTRING_MIDDLE", start, j)
                    self.add("RBRACE", j, j + 1)
                    self.i = j + 1
                    self.depth -= 1
                    fr.depths.pop()
                    fr.state = fr.rets.pop()
                    return
                self.i = j
                self.fail("f-string: single '}' is not allowed")
            j += 1

    # --- end of file -------------------------------------------------------------------------
    def finish(self):
        if len(self.frames) > 0 or self.depth > 0:
            self.fail("unexpected EOF in multi-line statement")
        last = self.nlines
        if self.n > 0 and self.src[self.n - 1] != "\n" and self.content:
            r = self.row_of(self.n)
            cc = self.n - self.starts[r]
            self.add_at("NEWLINE", "", r + 1, cc, r + 1, cc + 1)
        while len(self.indents) > 1:
            self.indents.pop()
            self.add_at("DEDENT", "", last + 1, 0, last + 1, 0)
        self.add_at("ENDMARKER", "", last + 1, 0, last + 1, 0)


def tokenize(text: str) -> list[Tok]:
    t = Tokenizer(text)
    return t.run()


def dump_line(t: Tok) -> str:
    return "%s %d,%d %d,%d %s" % (t.type, t.srow, t.scol, t.erow, t.ecol, repr(t.string))
