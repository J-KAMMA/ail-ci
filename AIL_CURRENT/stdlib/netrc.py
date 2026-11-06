"""An object-oriented interface to .netrc files.

Derived from CPython 3.12 Lib/netrc.py; PSF License, see stdlib/LICENSE-PSF.txt.

CPython 3.12's ``Lib/netrc.py`` as AIL source.  A compiled program finds this file
when its own directory has no ``netrc.py`` (``ail_modules.py`` searches the bundled
``stdlib/`` last), so ``import netrc`` works without installing the module.

Supported: ``netrc(file)``, ``n.hosts``, ``n.macros``, ``n.authenticators(host)``,
``repr(n)`` and ``NetrcParseError`` with CPython's ``msg`` / ``filename`` /
``lineno`` attributes and its exact ``__str__``.  The tokenizer follows CPython's
``_netrclex``: whitespace separation, ``#`` comments, double-quoted tokens with
backslash escapes, and ``macdef`` blocks.

One difference from CPython, forced by this compiler: the default-file branch is
not available.  CPython, given ``file=None``, opens ``os.path.expanduser("~/.netrc")``
and then runs ``_security_check`` (``os.fstat``/``os.getuid``/``pwd``); this
compiler builds none of ``os.path.expanduser``, ``os.stat``, ``os.fstat``,
``os.getuid`` or ``pwd``.  Passing ``file=None`` therefore raises ``OSError`` with
a clear message instead of guessing a path, and there is no permission check.  Every
explicit file name behaves exactly as in CPython for the ASCII and UTF-8 files this
task's programs use; CPython's second attempt with the locale encoding after a
``UnicodeDecodeError`` is also dropped because this compiler builds only utf-8,
ascii and latin-1 file encodings.
"""

__all__ = ["netrc", "NetrcParseError"]


class NetrcParseError(Exception):
    """Exception raised on syntax errors in the .netrc file."""

    def __init__(self, msg, filename=None, lineno=None):
        self.filename = filename
        self.lineno = lineno
        self.msg = msg
        super().__init__(msg)

    def __str__(self):
        return "%s (%s, line %s)" % (self.msg, self.filename, self.lineno)


class _netrclex:
    def __init__(self, fp):
        self.lineno = 1
        self.instream = fp
        self.whitespace = "\n\t\r "
        self.pushback = []

    def _read_char(self):
        ch = self.instream.read(1)
        if ch == "\n":
            self.lineno = self.lineno + 1
        return ch

    def get_token(self):
        if self.pushback:
            return self.pushback.pop(0)
        token = ""
        while True:
            ch = self._read_char()
            if ch == "":
                break
            if ch in self.whitespace:
                continue
            if ch == '"':
                while True:
                    ch = self._read_char()
                    if ch == "":
                        return token
                    if ch == '"':
                        return token
                    elif ch == "\\":
                        ch = self._read_char()
                    token = token + ch
            else:
                if ch == "\\":
                    ch = self._read_char()
                token = token + ch
                while True:
                    ch = self._read_char()
                    if ch == "":
                        return token
                    if ch in self.whitespace:
                        return token
                    elif ch == "\\":
                        ch = self._read_char()
                    token = token + ch
        return token

    def push_token(self, token):
        self.pushback.append(token)


class netrc:
    def __init__(self, file=None):
        if file is None:
            raise OSError("netrc: the default ~/.netrc file is not available in compiled programs; pass an explicit file name")
        self.hosts = {}
        self.macros = {}
        with open(file, encoding="utf-8") as fp:
            self._parse(file, fp)

    def _parse(self, file, fp):
        lexer = _netrclex(fp)
        while True:
            # Look for a machine, default, or macdef top-level keyword
            saved_lineno = lexer.lineno
            tt = lexer.get_token()
            if not tt:
                break
            elif tt[0] == '#':
                if lexer.lineno == saved_lineno and len(tt) == 1:
                    lexer.instream.readline()
                continue
            elif tt == 'machine':
                entryname = lexer.get_token()
            elif tt == 'default':
                entryname = 'default'
            elif tt == 'macdef':
                entryname = lexer.get_token()
                self.macros[entryname] = []
                while True:
                    line = lexer.instream.readline()
                    if not line:
                        raise NetrcParseError(
                            "Macro definition missing null line terminator.",
                            file, lexer.lineno)
                    if line == '\n':
                        # a macro definition finished with consecutive new-line
                        # characters. The first \n is encountered by the
                        # readline() method and this is the second \n.
                        break
                    self.macros[entryname].append(line)
                continue
            else:
                raise NetrcParseError(
                    "bad toplevel token %r" % tt, file, lexer.lineno)

            if not entryname:
                raise NetrcParseError("missing %r name" % tt, file, lexer.lineno)

            # We're looking at start of an entry for a named machine or default.
            login = account = password = ''
            self.hosts[entryname] = {}
            while True:
                prev_lineno = lexer.lineno
                tt = lexer.get_token()
                if tt.startswith('#'):
                    if lexer.lineno == prev_lineno:
                        lexer.instream.readline()
                    continue
                if tt in {'', 'machine', 'default', 'macdef'}:
                    self.hosts[entryname] = (login, account, password)
                    lexer.push_token(tt)
                    break
                elif tt == 'login' or tt == 'user':
                    login = lexer.get_token()
                elif tt == 'account':
                    account = lexer.get_token()
                elif tt == 'password':
                    password = lexer.get_token()
                else:
                    raise NetrcParseError("bad follower token %r" % tt,
                                          file, lexer.lineno)

    def authenticators(self, host):
        """Return a (user, account, password) tuple for given host."""
        if host in self.hosts:
            return self.hosts[host]
        elif 'default' in self.hosts:
            return self.hosts['default']
        else:
            return None

    def __repr__(self):
        """Dump the class data in the format of a .netrc file."""
        rep = ""
        for host in self.hosts.keys():
            attrs = self.hosts[host]
            rep = rep + "machine %s\n\tlogin %s\n" % (host, attrs[0])
            if attrs[1]:
                rep = rep + "\taccount %s\n" % attrs[1]
            rep = rep + "\tpassword %s\n" % attrs[2]
        for macro in self.macros.keys():
            rep = rep + "macdef %s\n" % macro
            for line in self.macros[macro]:
                rep = rep + line
            rep = rep + "\n"
        return rep
