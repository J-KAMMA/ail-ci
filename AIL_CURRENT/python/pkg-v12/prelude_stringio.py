# -*- coding: utf-8 -*-
# prelude_stringio.py -- `io.StringIO` as Python source (smalllib5.py injects it): an in-memory text file with
# write / getvalue / read / readline / readlines / iteration / seek / tell / truncate / close. Newlines are kept as
# written (the default newline='\n' behaviour, no translation).


class _AilStringIO:
    def __init__(self, initial_value: str = ""):
        self.s = initial_value
        self.parts = []
        self.size = len(initial_value)
        self.pos = 0
        self.closed = False

    def _flat(self):
        if len(self.parts) > 0:
            self.s = self.s + "".join(self.parts)
            self.parts = []

    def _open(self):
        if self.closed:
            raise ValueError("I/O operation on closed file")

    def write(self, text: str) -> int:
        self._open()
        n = len(text)
        if n == 0:
            return 0
        if self.pos == self.size:
            self.parts.append(text)
            self.size = self.size + n
            self.pos = self.size
            return n
        self._flat()
        if self.pos > self.size:
            self.s = self.s + "\0" * (self.pos - self.size)
        self.s = self.s[:self.pos] + text + self.s[self.pos + n:]
        self.pos = self.pos + n
        self.size = len(self.s)
        return n

    def writelines(self, lines):
        for line in lines:
            self.write(line)

    def getvalue(self) -> str:
        self._open()
        self._flat()
        return self.s

    def read(self, n: int = -1) -> str:
        self._open()
        self._flat()
        if self.pos >= self.size:
            return ""
        end = self.size
        if n >= 0 and self.pos + n < end:
            end = self.pos + n
        out = self.s[self.pos:end]
        self.pos = end
        return out

    def readline(self, limit: int = -1) -> str:
        self._open()
        self._flat()
        if self.pos >= self.size:
            return ""
        i = self.s.find("\n", self.pos)
        end = self.size
        if i >= 0:
            end = i + 1
        if limit >= 0 and self.pos + limit < end:
            end = self.pos + limit
        out = self.s[self.pos:end]
        self.pos = end
        return out

    def readlines(self) -> list[str]:
        out = []
        line = self.readline()
        while line != "":
            out.append(line)
            line = self.readline()
        return out

    def __iter__(self):
        return self.readlines()

    def seek(self, pos: int, whence: int = 0) -> int:
        self._open()
        if whence == 0:
            if pos < 0:
                raise ValueError("Negative seek position " + str(pos))
            self.pos = pos
        elif whence == 1:
            self.pos = self.pos + pos
        else:
            self.pos = self.size + pos
        return self.pos

    def tell(self) -> int:
        self._open()
        return self.pos

    def truncate(self, size: int = -1) -> int:
        self._open()
        self._flat()
        if size < 0:
            size = self.pos
        self.s = self.s[:size]
        self.size = len(self.s)
        return size

    def close(self):
        self.closed = True

    def __enter__(self):
        self._open()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.closed = True
        return False

    def isatty(self) -> bool:
        return False

    def readable(self) -> bool:
        return True

    def writable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True
