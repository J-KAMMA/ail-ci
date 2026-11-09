import sys

MASK = 4294967295
BASE = 4294967296
KEYWORDS = {"set", "out", "loop", "when", "else", "end", "break"}


class ParseError(Exception):
    pass


class EvalError(Exception):
    pass


class BreakSignal(Exception):
    pass


def mul32(a, b):
    a0 = a & 65535
    a1 = (a >> 16) & 65535
    b0 = b & 65535
    b1 = (b >> 16) & 65535
    mid = a0 * b1 + a1 * b0
    return (a0 * b0 + (mid << 16)) & MASK


def rot32(a, b):
    s = b & 31
    if s == 0:
        return a
    return ((a << s) | (a >> (32 - s))) & MASK


def popcount(x):
    c = 0
    while x:
        c += x & 1
        x = x >> 1
    return c


def tokenize(text, line):
    toks = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == " " or c == "\t" or c == "\r":
            i += 1
            continue
        if "0" <= c <= "9":
            j = i
            while j < n and "0" <= text[j] <= "9":
                j += 1
            if j < n:
                d = text[j]
                if ("a" <= d <= "z") or d == "_":
                    raise ParseError(line)
            digits = text[i:j]
            k = 0
            while k < len(digits) and digits[k] == "0":
                k += 1
            sig = digits[k:]
            if len(sig) > 10:
                raise ParseError(line)
            if len(sig) == 10 and sig > "4294967295":
                raise ParseError(line)
            if sig:
                val = int(sig)
            else:
                val = 0
            toks.append(("num", val))
            i = j
            continue
        if ("a" <= c <= "z") or c == "_":
            j = i + 1
            while j < n:
                d = text[j]
                if ("a" <= d <= "z") or ("0" <= d <= "9") or d == "_":
                    j += 1
                else:
                    break
            toks.append(("word", text[i:j]))
            i = j
            continue
        two = text[i:i + 2]
        if two == "<>" or two == "><" or two == "==" or two == "!=":
            toks.append(("op", two))
            i += 2
            continue
        if c == "<" or c == ">" or c == "+" or c == "-" or c == "*" or c == "/" or c == "%" or c == "~" or c == "#" or c == "!" or c == "(" or c == ")" or c == "," or c == "=":
            toks.append(("op", c))
            i += 1
            continue
        raise ParseError(line)
    return toks


class ExprParser:
    def __init__(self, tokens, pos, line):
        self.tokens = tokens
        self.pos = pos
        self.line = line
        self.depth = 0

    def peek(self):
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def take(self):
        t = self.tokens[self.pos]
        self.pos += 1
        return t

    def is_op(self, t, ops):
        return t is not None and t[0] == "op" and t[1] in ops

    def parse_expr(self):
        return self.parse_level1()

    def parse_level1(self):
        left = self.parse_level2()
        while True:
            t = self.peek()
            if self.is_op(t, ("<>", "><")):
                op = self.take()[1]
                right = self.parse_level2()
                left = ("bin", op, left, right)
            else:
                break
        return left

    def parse_level2(self):
        left = self.parse_level3()
        t = self.peek()
        if self.is_op(t, ("==", "!=", "<", ">")):
            op = self.take()[1]
            right = self.parse_level3()
            left = ("bin", op, left, right)
        return left

    def parse_level3(self):
        left = self.parse_level4()
        while True:
            t = self.peek()
            if self.is_op(t, ("+", "-")):
                op = self.take()[1]
                right = self.parse_level4()
                left = ("bin", op, left, right)
            else:
                break
        return left

    def parse_level4(self):
        left = self.parse_level5()
        while True:
            t = self.peek()
            if self.is_op(t, ("*", "/", "%")):
                op = self.take()[1]
                right = self.parse_level5()
                left = ("bin", op, left, right)
            else:
                break
        return left

    def parse_level5(self):
        left = self.parse_level6()
        t = self.peek()
        if self.is_op(t, ("~",)):
            self.take()
            right = self.parse_level5()
            return ("bin", "~", left, right)
        return left

    def parse_level6(self):
        ops = []
        while True:
            t = self.peek()
            if self.is_op(t, ("-", "#", "!")):
                ops.append(self.take()[1])
            else:
                break
        operand = self.parse_level7()
        i = len(ops) - 1
        while i >= 0:
            operand = ("un", ops[i], operand)
            i -= 1
        return operand

    def parse_level7(self):
        t = self.peek()
        if t is None:
            raise ParseError(self.line)
        if t[0] == "num":
            self.take()
            return ("num", t[1])
        if t[0] == "word":
            if t[1] in KEYWORDS:
                raise ParseError(self.line)
            self.take()
            return ("var", t[1])
        if t[0] == "op" and t[1] == "(":
            self.take()
            self.depth += 1
            if self.depth > 32:
                raise ParseError(self.line)
            e = self.parse_expr()
            t2 = self.peek()
            if t2 is None or t2[0] != "op" or t2[1] != ")":
                raise ParseError(self.line)
            self.take()
            self.depth -= 1
            return e
        raise ParseError(self.line)


class Parser:
    def __init__(self, data):
        self.data = data
        self.top_body = []
        self.stack = []

    def body(self):
        if self.stack:
            return self.stack[-1]["body"]
        return self.top_body

    def add(self, node):
        self.body().append(node)

    def parse(self):
        parts = self.data.split(b"\n")
        if self.data.endswith(b"\n"):
            parts = parts[:-1]
        index = 0
        while index < len(parts):
            raw = parts[index]
            line = index + 1
            if len(raw) > 1000:
                raise ParseError(line)
            j = 0
            while j < len(raw):
                b = raw[j]
                if b == 9 or b == 13 or (32 <= b <= 126):
                    j += 1
                else:
                    raise ParseError(line)
            semi = raw.find(b";")
            if semi != -1:
                raw = raw[:semi]
            text = raw.decode("ascii")
            tokens = tokenize(text, line)
            if tokens:
                self.parse_line(tokens, line)
            index += 1
        if self.stack:
            raise ParseError(self.stack[-1]["line"])
        return self.top_body

    def parse_line(self, tokens, line):
        t0 = tokens[0]
        if t0[0] != "word" or t0[1] not in KEYWORDS:
            raise ParseError(line)
        kw = t0[1]
        if kw == "set":
            self.parse_set(tokens, line)
        elif kw == "out":
            self.parse_out(tokens, line)
        elif kw == "loop":
            self.parse_loop(tokens, line)
        elif kw == "when":
            self.parse_when(tokens, line)
        elif kw == "else":
            if len(tokens) != 1:
                raise ParseError(line)
            if not self.stack:
                raise ParseError(line)
            f = self.stack[-1]
            if f["kind"] != "when" or f["has_else"]:
                raise ParseError(line)
            f["has_else"] = True
            f["node"]["else"] = []
            f["body"] = f["node"]["else"]
        elif kw == "end":
            if len(tokens) != 1:
                raise ParseError(line)
            if not self.stack:
                raise ParseError(line)
            self.stack.pop()
        elif kw == "break":
            if len(tokens) != 1:
                raise ParseError(line)
            found = False
            i = 0
            while i < len(self.stack):
                if self.stack[i]["kind"] == "loop":
                    found = True
                    break
                i += 1
            if not found:
                raise ParseError(line)
            self.add({"type": "break", "line": line})

    def parse_set(self, tokens, line):
        pos = 1
        if pos >= len(tokens):
            raise ParseError(line)
        t = tokens[pos]
        if t[0] != "word" or t[1] in KEYWORDS:
            raise ParseError(line)
        name = t[1]
        pos += 1
        if pos >= len(tokens) or tokens[pos][0] != "op" or tokens[pos][1] != "=":
            raise ParseError(line)
        pos += 1
        p = ExprParser(tokens, pos, line)
        expr = p.parse_expr()
        if p.pos != len(tokens):
            raise ParseError(line)
        self.add({"type": "set", "name": name, "expr": expr, "line": line})

    def parse_out(self, tokens, line):
        p = ExprParser(tokens, 1, line)
        exprs = [p.parse_expr()]
        while p.pos < len(tokens):
            t = tokens[p.pos]
            if t[0] == "op" and t[1] == ",":
                p.pos += 1
                exprs.append(p.parse_expr())
            else:
                break
        if p.pos != len(tokens):
            raise ParseError(line)
        self.add({"type": "out", "exprs": exprs, "line": line})

    def parse_loop(self, tokens, line):
        p = ExprParser(tokens, 1, line)
        expr = p.parse_expr()
        if p.pos != len(tokens):
            raise ParseError(line)
        if len(self.stack) >= 16:
            raise ParseError(line)
        node = {"type": "loop", "expr": expr, "body": [], "line": line}
        self.add(node)
        self.stack.append({"kind": "loop", "body": node["body"], "node": node, "line": line, "has_else": False})

    def parse_when(self, tokens, line):
        p = ExprParser(tokens, 1, line)
        expr = p.parse_expr()
        if p.pos != len(tokens):
            raise ParseError(line)
        if len(self.stack) >= 16:
            raise ParseError(line)
        node = {"type": "when", "expr": expr, "body": [], "else": None, "line": line}
        self.add(node)
        self.stack.append({"kind": "when", "body": node["body"], "node": node, "line": line, "has_else": False})


variables = {}


def eval_expr(node):
    typ = node[0]
    if typ == "num":
        return node[1]
    if typ == "var":
        name = node[1]
        if name not in variables:
            raise EvalError()
        return variables[name]
    if typ == "bin":
        op = node[1]
        a = eval_expr(node[2])
        b = eval_expr(node[3])
        if op == "<>":
            if a >= b:
                return a
            return b
        if op == "><":
            if a <= b:
                return a
            return b
        if op == "==":
            if a == b:
                return 1
            return 0
        if op == "!=":
            if a != b:
                return 1
            return 0
        if op == "<":
            if a < b:
                return 1
            return 0
        if op == ">":
            if a > b:
                return 1
            return 0
        if op == "+":
            return (a + b) & MASK
        if op == "-":
            return (a + BASE - b) & MASK
        if op == "*":
            return mul32(a, b)
        if op == "/":
            if b == 0:
                raise EvalError()
            return a // b
        if op == "%":
            if b == 0:
                raise EvalError()
            return a % b
        if op == "~":
            return rot32(a, b)
    if typ == "un":
        op = node[1]
        v = eval_expr(node[2])
        if op == "-":
            return (BASE - v) & MASK
        if op == "#":
            return popcount(v)
        if op == "!":
            if v == 0:
                return 1
            return 0
    raise EvalError()


def runtime_error(line):
    sys.stdout.write("runtime error line " + str(line) + "\n")
    sys.stdout.flush()
    sys.exit(3)


def execute_body(body):
    i = 0
    while i < len(body):
        stmt = body[i]
        try:
            execute(stmt)
        except EvalError:
            runtime_error(stmt["line"])
        i += 1


def execute(stmt):
    typ = stmt["type"]
    if typ == "set":
        value = eval_expr(stmt["expr"])
        variables[stmt["name"]] = value
        return
    if typ == "out":
        values = []
        exprs = stmt["exprs"]
        i = 0
        while i < len(exprs):
            values.append(eval_expr(exprs[i]))
            i += 1
        parts = []
        i = 0
        while i < len(values):
            parts.append(str(values[i]))
            i += 1
        sys.stdout.write(" ".join(parts) + "\n")
        return
    if typ == "loop":
        n = eval_expr(stmt["expr"])
        body = stmt["body"]
        if len(body) > 0:
            i = 0
            while i < n:
                try:
                    execute_body(body)
                except BreakSignal:
                    break
                i += 1
        return
    if typ == "when":
        cond = eval_expr(stmt["expr"])
        if cond != 0:
            execute_body(stmt["body"])
        else:
            alt = stmt["else"]
            if alt is not None:
                execute_body(alt)
        return
    if typ == "break":
        raise BreakSignal()


def main():
    if len(sys.argv) != 2:
        sys.exit(1)
    path = sys.argv[1]
    try:
        f = open(path, "rb")
        data = f.read()
        f.close()
    except OSError:
        sys.exit(1)
    try:
        body = Parser(data).parse()
    except ParseError as e:
        sys.stdout.write("parse error line " + str(e.args[0]) + "\n")
        sys.stdout.flush()
        sys.exit(2)
    execute_body(body)
    sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
