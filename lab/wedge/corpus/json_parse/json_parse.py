"""A small recursive-descent JSON-subset parser over a string."""


class Parser:
    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0

    def skip_ws(self) -> None:
        n = len(self.text)
        while self.pos < n and self.text[self.pos] in " \t\n\r":
            self.pos += 1

    def parse_value(self) -> int:
        self.skip_ws()
        ch = self.text[self.pos]
        if ch == "{":
            return self.parse_object()
        if ch == "[":
            return self.parse_array()
        if ch == '"':
            return self.parse_string()
        if ch == "t":
            self.pos += 4
            return 0
        if ch == "f":
            self.pos += 5
            return 0
        if ch == "n":
            self.pos += 4
            return 0
        return self.parse_number()

    def parse_number(self) -> int:
        start = self.pos
        n = len(self.text)
        while self.pos < n:
            ch = self.text[self.pos]
            if ch.isdigit() or ch in "+-.eE":
                self.pos += 1
            else:
                break
        body = self.text[start:self.pos]
        return int(float(body))

    def parse_string(self) -> int:
        self.pos += 1
        total = 0
        n = len(self.text)
        while self.pos < n:
            ch = self.text[self.pos]
            if ch == '"':
                self.pos += 1
                break
            if ch == "\\":
                self.pos += 2
                continue
            total += 1
            self.pos += 1
        return total

    def parse_array(self) -> int:
        self.pos += 1
        count = 0
        while True:
            self.skip_ws()
            if self.text[self.pos] == "]":
                self.pos += 1
                return count
            count += 1
            self.parse_value()
            self.skip_ws()
            if self.text[self.pos] == ",":
                self.pos += 1

    def parse_object(self) -> int:
        self.pos += 1
        count = 0
        while True:
            self.skip_ws()
            if self.text[self.pos] == "}":
                self.pos += 1
                return count
            self.parse_string()
            self.skip_ws()
            self.pos += 1
            self.parse_value()
            count += 1
            self.skip_ws()
            if self.text[self.pos] == ",":
                self.pos += 1


def document_bytes(text: str) -> int:
    return len(text)


def count_tokens(text: str) -> int:
    n = 0
    for ch in text:
        if ch in "{}[],:":
            n += 1
    return n


def depth_of(text: str) -> int:
    best = 0
    cur = 0
    for ch in text:
        if ch == "[" or ch == "{":
            cur += 1
            if cur > best:
                best = cur
        elif ch == "]" or ch == "}":
            cur -= 1
    return best


def digits_in(text: str) -> int:
    n = 0
    for ch in text:
        if ch.isdigit():
            n += 1
    return n
