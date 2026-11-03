import sys


class Parser:
    def __init__(self, s):
        self.s = s
        self.i = 0
        self.total = 0

    def skip_ws(self):
        while self.i < len(self.s):
            c = self.s[self.i]
            if c == 32 or c == 9 or c == 13 or c == 10:
                self.i += 1
            else:
                break

    def skip_string(self):
        self.i += 1
        while self.i < len(self.s):
            c = self.s[self.i]
            if c == 92:
                self.i += 2
            elif c == 34:
                self.i += 1
                return
            else:
                self.i += 1

    def parse_value(self):
        self.skip_ws()
        if self.i >= len(self.s):
            return
        c = self.s[self.i]
        if c == 123:
            self.i += 1
            self.skip_ws()
            if self.i < len(self.s) and self.s[self.i] == 125:
                self.i += 1
                return
            while True:
                self.skip_ws()
                if self.i >= len(self.s):
                    return
                self.skip_string()
                self.skip_ws()
                if self.i < len(self.s) and self.s[self.i] == 58:
                    self.i += 1
                self.parse_value()
                self.skip_ws()
                if self.i < len(self.s) and self.s[self.i] == 44:
                    self.i += 1
                    continue
                if self.i < len(self.s) and self.s[self.i] == 125:
                    self.i += 1
                return
        if c == 91:
            self.i += 1
            self.skip_ws()
            if self.i < len(self.s) and self.s[self.i] == 93:
                self.i += 1
                return
            while True:
                self.skip_ws()
                if self.i < len(self.s) and self.s[self.i] == 93:
                    self.i += 1
                    return
                if self.i >= len(self.s):
                    return
                self.parse_value()
                self.skip_ws()
                if self.i < len(self.s) and self.s[self.i] == 44:
                    self.i += 1
                    continue
                if self.i < len(self.s) and self.s[self.i] == 93:
                    self.i += 1
                return
        if c == 34:
            self.skip_string()
            return
        if c == 45 or (c >= 48 and c <= 57):
            neg = False
            if self.s[self.i] == 45:
                neg = True
                self.i += 1
            value = 0
            while self.i < len(self.s) and self.s[self.i] >= 48 and self.s[self.i] <= 57:
                value = value * 10 + (self.s[self.i] - 48)
                self.i += 1
            if neg:
                value = -value
            self.total = self.total + value
            return
        if self.i + 4 <= len(self.s) and self.s[self.i:self.i + 4] == b"true":
            self.i += 4
            return
        if self.i + 5 <= len(self.s) and self.s[self.i:self.i + 5] == b"false":
            self.i += 5
            return
        if self.i + 4 <= len(self.s) and self.s[self.i:self.i + 4] == b"null":
            self.i += 4
            return
        self.i += 1


def main():
    data = sys.stdin.buffer.read()
    p = Parser(data)
    while p.i < len(data):
        p.parse_value()
        p.skip_ws()
        if p.i >= len(data):
            break
    sys.stdout.write('%d\n' % p.total)
    return 0


main()
