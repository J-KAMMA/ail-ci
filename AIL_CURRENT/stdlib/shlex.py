"""G5a: the standard-library `shlex` module (split, quote, join and the `shlex` lexer class).

A program compiled by AIL finds this file when its own directory has no `shlex.py`
(`ail_modules.py` searches the bundled `stdlib/` last).  The tokenizer follows CPython 3.12's
`shlex.py`; the only representation change is that a POSIX end-of-file is the empty string in
`get_token()`, `read_token()` and `eof`, because AIL has no `None` value.  `list(lex)` and `for token in lex`
still stop at the end, and an empty quoted token (`split("''")`) is not mistaken for it.

Supported: split(s, comments=False, posix=True), quote(s), join(argv), the shlex(instream,
infile, posix, punctuation_chars) lexer with get_token/read_token/push_token/push_source/
pop_source/error_leader, its public attributes (commenters, wordchars, whitespace,
whitespace_split, quotes, escape, escapedquotes, punctuation_chars, lineno, debug, infile) and
iteration.  `instream` is a string (a file object and the `source` inclusion hook are not
available in a single-file program).
"""

def _safe_char(c):
    if c == "_" or c == "@" or c == "%" or c == "+" or c == "=" or c == ":" or c == "," or c == "." or c == "/" or c == "-":
        return True
    if "a" <= c and c <= "z":
        return True
    if "A" <= c and c <= "Z":
        return True
    if "0" <= c and c <= "9":
        return True
    return False


def _find_unsafe(s) -> int:
    i = 0
    while i < len(s):
        if not _safe_char(s[i]):
            return i
        i = i + 1
    return -1


def quote(s: str) -> str:
    """Return a shell-escaped version of the string *s*."""
    if s == "":
        return "''"
    if _find_unsafe(s) < 0:
        return s
    return "'" + s.replace("'", "'\"'\"'") + "'"


def join(split_command) -> str:
    """Return a shell-escaped string from *split_command*."""
    parts = []
    for arg in split_command:
        parts.append(quote(arg))
    return " ".join(parts)


_WORDS = ("abcdfeghijklmnopqrstuvwxyz"
          "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
_WORDS_POSIX = ("\u00df\u00e0\u00e1\u00e2\u00e3\u00e4\u00e5\u00e6\u00e7\u00e8\u00e9\u00ea\u00eb\u00ec\u00ed\u00ee\u00ef\u00f0\u00f1\u00f2\u00f3\u00f4\u00f5\u00f6\u00f8\u00f9\u00fa\u00fb\u00fc\u00fd\u00fe\u00ff"
               "\u00c0\u00c1\u00c2\u00c3\u00c4\u00c5\u00c6\u00c7\u00c8\u00c9\u00ca\u00cb\u00cc\u00cd\u00ce\u00cf\u00d0\u00d1\u00d2\u00d3\u00d4\u00d5\u00d6\u00d8\u00d9\u00da\u00db\u00dc\u00dd\u00de")


def _punctuation(punctuation_chars) -> str:
    pc = ""
    if punctuation_chars == True:
        pc = "();<>|&"
    elif punctuation_chars != False:
        pc = punctuation_chars
    return pc


def _wordchars(posix, punctuation_chars) -> str:
    w = _WORDS
    if posix:
        w = w + _WORDS_POSIX
    pc = _punctuation(punctuation_chars)
    if pc != "":
        w = w + "~-./*?="
        kept = ""
        i = 0
        while i < len(w):
            if pc.find(w[i]) < 0:
                kept = kept + w[i]
            i = i + 1
        w = kept
    return w


class shlex:
    """A lexical analyzer class for simple shell-like syntaxes."""

    def __init__(self, instream: str = "", infile: str = "", posix=False, punctuation_chars=False):
        self.instream = instream
        self.text = instream
        self.pos = 0
        self.infile = infile
        self.posix = posix
        self.eof = ""
        self._eof = False
        self._raw_eof = False
        self.commenters = "#"
        self.wordchars = _wordchars(posix, punctuation_chars)
        self.whitespace = " \t\r\n"
        self.whitespace_split = False
        self.quotes = "'\""
        self.escape = "\\"
        self.escapedquotes = '"'
        self.state = " "
        self.pushback: list[str] = []
        self._pushback_chars: list[str] = []
        self.lineno = 1
        self.debug = 0
        self.token = ""
        self.stack_text: list[str] = []
        self.stack_pos: list[int] = []
        self.stack_file: list[str] = []
        self.stack_line: list[int] = []
        self.source = ""
        self.punctuation_chars = _punctuation(punctuation_chars)

    def _read_char(self) -> str:
        part = self.text
        c = ""
        if self.pos < len(part):
            c = part[self.pos]
            self.pos = self.pos + 1
        return c

    def _skip_line(self) -> None:
        part = self.text
        while self.pos < len(part):
            c = part[self.pos]
            self.pos = self.pos + 1
            if c == "\n":
                break
        self.lineno = self.lineno + 1

    def push_token(self, tok: str):
        if self.debug >= 1:
            print("shlex: pushing token " + repr(tok))
        self.pushback.insert(0, tok)

    def push_source(self, newstream: str, newfile: str = ""):
        self.stack_text.insert(0, self.text)
        self.stack_pos.insert(0, self.pos)
        self.stack_file.insert(0, self.infile)
        self.stack_line.insert(0, self.lineno)
        self.text = newstream
        self.pos = 0
        self.infile = newfile
        self.lineno = 1
        self._eof = False

    def pop_source(self):
        self.text = self.stack_text.pop(0)
        self.pos = self.stack_pos.pop(0)
        self.infile = self.stack_file.pop(0)
        self.lineno = self.stack_line.pop(0)
        self.state = " "
        self._eof = False

    def get_token(self) -> str:
        if len(self.pushback) > 0:
            tok = self.pushback.pop(0)
            if self.debug >= 1:
                print("shlex: popping token " + repr(tok))
            return tok
        raw = self.read_token()
        while self._raw_eof:
            if len(self.stack_text) == 0:
                self._eof = True
                return self.eof
            self.pop_source()
            raw = self.read_token()
        if self.debug >= 1:
            if not self._raw_eof:
                print("shlex: token=" + repr(raw))
            else:
                print("shlex: token=EOF")
        return raw

    def read_token(self) -> str:
        quoted = False
        escapedstate = " "
        while True:
            if self.punctuation_chars != "" and len(self._pushback_chars) > 0:
                nextchar = self._pushback_chars.pop()
            else:
                nextchar = self._read_char()
            if nextchar == "\n":
                self.lineno = self.lineno + 1
            if self.debug >= 3:
                print("shlex: in state " + repr(self.state) + " I see character: " + repr(nextchar))
            if self.state == "":
                self.token = ""
                break
            elif self.state == " ":
                if nextchar == "":
                    self.state = ""
                    break
                elif self.whitespace.find(nextchar) >= 0:
                    if self.debug >= 2:
                        print("shlex: I see whitespace in whitespace state")
                    if self.token != "" or (self.posix and quoted):
                        break
                    else:
                        continue
                elif self.commenters.find(nextchar) >= 0:
                    self._skip_line()
                elif self.posix and self.escape.find(nextchar) >= 0:
                    escapedstate = "a"
                    self.state = nextchar
                elif self.wordchars.find(nextchar) >= 0:
                    self.token = nextchar
                    self.state = "a"
                elif self.punctuation_chars.find(nextchar) >= 0:
                    self.token = nextchar
                    self.state = "c"
                elif self.quotes.find(nextchar) >= 0:
                    if not self.posix:
                        self.token = nextchar
                    self.state = nextchar
                elif self.whitespace_split:
                    self.token = nextchar
                    self.state = "a"
                else:
                    self.token = nextchar
                    if self.token != "" or (self.posix and quoted):
                        break
                    else:
                        continue
            elif self.quotes.find(self.state) >= 0:
                quoted = True
                if nextchar == "":
                    if self.debug >= 2:
                        print("shlex: I see EOF in quotes state")
                    raise ValueError("No closing quotation")
                if nextchar == self.state:
                    if not self.posix:
                        self.token = self.token + nextchar
                        self.state = " "
                        break
                    else:
                        self.state = "a"
                elif self.posix and self.escape.find(nextchar) >= 0 and self.escapedquotes.find(self.state) >= 0:
                    escapedstate = self.state
                    self.state = nextchar
                else:
                    self.token = self.token + nextchar
            elif self.escape.find(self.state) >= 0:
                if nextchar == "":
                    if self.debug >= 2:
                        print("shlex: I see EOF in escape state")
                    raise ValueError("No escaped character")
                if self.quotes.find(escapedstate) >= 0 and nextchar != self.state and nextchar != escapedstate:
                    self.token = self.token + self.state
                self.token = self.token + nextchar
                self.state = escapedstate
            elif self.state == "a" or self.state == "c":
                if nextchar == "":
                    self.state = ""
                    break
                elif self.whitespace.find(nextchar) >= 0:
                    if self.debug >= 2:
                        print("shlex: I see whitespace in word state")
                    self.state = " "
                    if self.token != "" or (self.posix and quoted):
                        break
                    else:
                        continue
                elif self.commenters.find(nextchar) >= 0:
                    self._skip_line()
                    if self.posix:
                        self.state = " "
                        if self.token != "" or (self.posix and quoted):
                            break
                        else:
                            continue
                elif self.state == "c":
                    if self.punctuation_chars.find(nextchar) >= 0:
                        self.token = self.token + nextchar
                    else:
                        if self.whitespace.find(nextchar) < 0:
                            self._pushback_chars.append(nextchar)
                        self.state = " "
                        break
                elif self.posix and self.quotes.find(nextchar) >= 0:
                    self.state = nextchar
                elif self.posix and self.escape.find(nextchar) >= 0:
                    escapedstate = "a"
                    self.state = nextchar
                elif (self.wordchars.find(nextchar) >= 0 or self.quotes.find(nextchar) >= 0
                      or (self.whitespace_split and self.punctuation_chars.find(nextchar) < 0)):
                    self.token = self.token + nextchar
                else:
                    if self.punctuation_chars != "":
                        self._pushback_chars.append(nextchar)
                    else:
                        self.pushback.insert(0, nextchar)
                    if self.debug >= 2:
                        print("shlex: I see punctuation in word state")
                    self.state = " "
                    if self.token != "" or (self.posix and quoted):
                        break
                    else:
                        continue
        result = self.token
        self.token = ""
        self._raw_eof = not quoted and result == ""
        if self.debug > 1:
            if not self._raw_eof:
                print("shlex: raw token=" + repr(result))
            else:
                print("shlex: raw token=EOF")
        return result

    def sourcehook(self, newfile: str) -> str:
        return newfile

    def error_leader(self, infile: str = "", lineno: int = 0) -> str:
        name = infile
        line = lineno
        if name == "":
            name = self.infile
        if line == 0:
            line = self.lineno
        return "\"%s\", line %d: " % (name, line)

    def __iter__(self):
        while True:
            tok = self.get_token()
            if self._eof:
                break
            yield tok


def split(s: str, comments=False, posix=True) -> list[str]:
    """Split the string *s* using shell-like syntax."""
    lex = shlex(s, "", posix, False)
    lex.whitespace_split = True
    if not comments:
        lex.commenters = ""
    return list(lex)
