import sys


def parse_tree(s):
    n = len(s)
    i = 0
    names = []
    weights = []
    children = []
    root = -1
    stack = []
    while True:
        j = i
        while j < n and s[j] >= 'a' and s[j] <= 'z':
            j += 1
        if j == i or j - i > 16:
            raise ValueError('name')
        nm = s[i:j]
        i = j
        if i >= n or s[i] != ':':
            raise ValueError('colon')
        i += 1
        j = i
        while j < n and s[j] >= '0' and s[j] <= '9':
            j += 1
        if j == i:
            raise ValueError('weight')
        wd = s[i:j]
        if len(wd) > 7:
            raise ValueError('weight')
        if len(wd) > 1 and wd[0] == '0':
            raise ValueError('weight')
        w = int(wd)
        if w > 1000000:
            raise ValueError('weight')
        i = j
        idx = len(names)
        names.append(nm)
        weights.append(w)
        children.append([])
        if stack:
            children[stack[-1]].append(idx)
        else:
            if root != -1:
                raise ValueError('multiple')
            root = idx
        if i < n and s[i] == '[':
            stack.append(idx)
            i += 1
            continue
        while True:
            if i >= n:
                if stack:
                    raise ValueError('eof')
                return names, weights, children
            c = s[i]
            if c == ' ':
                i += 1
                break
            elif c == ']':
                if not stack:
                    raise ValueError('bracket')
                stack.pop()
                i += 1
            else:
                raise ValueError('char')


def valid_num(s):
    if not s:
        return False
    if len(s) > 16:
        return False
    if s == '0':
        return True
    if s[0] == '0':
        return False
    for c in s:
        if c < '0' or c > '9':
            return False
    return int(s) <= 1000000000000000


def valid_name(s):
    if not s:
        return False
    for c in s:
        if (c >= 'a' and c <= 'z') or c == '+':
            continue
        return False
    return True


def parse_op(line):
    if line == 'total':
        return ('total',)
    if line == 'stats':
        return ('stats',)
    if line == 'print':
        return ('print',)
    if line == 'sort':
        return ('sort',)
    if line == 'mirror':
        return ('mirror',)
    if line == 'fold':
        return ('fold',)
    parts = line.split(' ')
    if len(parts) != 2:
        raise ValueError('op')
    kw = parts[0]
    arg = parts[1]
    if kw == 'level' or kw == 'prune':
        if not valid_num(arg):
            raise ValueError('num')
        return (kw, int(arg))
    if kw == 'find' or kw == 'cut':
        if not valid_name(arg):
            raise ValueError('name')
        return (kw, arg)
    raise ValueError('op')


class Writer:
    def __init__(self):
        self.parts = []
        self.size = 0

    def add(self, s):
        self.parts.append(s)
        self.size += len(s)
        if self.size >= 1048576:
            sys.stdout.write(''.join(self.parts))
            self.parts = []
            self.size = 0

    def flush(self):
        if self.parts:
            sys.stdout.write(''.join(self.parts))
            self.parts = []
            self.size = 0


class Tree:
    def __init__(self, names, weights, children):
        self.names = names
        self.weights = weights
        self.children = children
        total = 0
        for w in weights:
            total += w
        self.total = total

    def order(self):
        order = []
        stack = [0]
        children = self.children
        while stack:
            v = stack.pop()
            order.append(v)
            ch = children[v]
            for i in range(len(ch) - 1, -1, -1):
                stack.append(ch[i])
        return order

    def subtree_weights(self, order):
        sub = [0] * len(self.names)
        weights = self.weights
        children = self.children
        idx = len(order) - 1
        while idx >= 0:
            v = order[idx]
            s = weights[v]
            for c in children[v]:
                s += sub[c]
            sub[v] = s
            idx -= 1
        return sub

    def get_stats(self):
        children = self.children
        stack = [(0, 0)]
        nodes = 0
        leaves = 0
        height = 0
        widest = 0
        while stack:
            v, d = stack.pop()
            nodes += 1
            if d > height:
                height = d
            ch = children[v]
            k = len(ch)
            if k:
                if k > widest:
                    widest = k
                nd = d + 1
                for c in ch:
                    stack.append((c, nd))
            else:
                leaves += 1
        return nodes, leaves, height, widest

    def level(self, D):
        children = self.children
        weights = self.weights
        count = 0
        ssum = 0
        stack = [(0, 0)]
        while stack:
            v, d = stack.pop()
            if d == D:
                count += 1
                ssum += weights[v]
            elif d < D:
                nd = d + 1
                for c in children[v]:
                    stack.append((c, nd))
        return count, ssum

    def find_path(self, name):
        names = self.names
        children = self.children
        stack = [(0, 0)]
        path = []
        while stack:
            v, d = stack.pop()
            while len(path) > d:
                path.pop()
            path.append(names[v])
            if names[v] == name:
                return '/'.join(path)
            ch = children[v]
            for i in range(len(ch) - 1, -1, -1):
                stack.append((ch[i], d + 1))
        return None

    def serialize(self, out):
        names = self.names
        weights = self.weights
        children = self.children
        stack = [(0, 0)]
        while stack:
            ev, v = stack.pop()
            if ev == 0:
                out.add(names[v])
                out.add(':')
                out.add(str(weights[v]))
                ch = children[v]
                if ch:
                    out.add('[')
                    stack.append((1, 0))
                    for i in range(len(ch) - 1, -1, -1):
                        stack.append((0, ch[i]))
                        if i > 0:
                            stack.append((2, 0))
            elif ev == 1:
                out.add(']')
            else:
                out.add(' ')
        out.add('\n')

    def prune(self, W):
        order = self.order()
        sub = self.subtree_weights(order)
        names = self.names
        weights = self.weights
        children = self.children
        mapping = [-1] * len(names)
        nn = [names[0]]
        nw = [weights[0]]
        nc = [[]]
        mapping[0] = 0
        removed = 0
        stack = [0]
        while stack:
            v = stack.pop()
            nv = mapping[v]
            lst = []
            for c in children[v]:
                if sub[c] < W:
                    removed += sub[c]
                    continue
                m = len(nn)
                mapping[c] = m
                nn.append(names[c])
                nw.append(weights[c])
                nc.append([])
                lst.append(m)
                stack.append(c)
            nc[nv] = lst
        self.names = nn
        self.weights = nw
        self.children = nc
        self.total -= removed

    def sort_children(self):
        order = self.order()
        sub = self.subtree_weights(order)
        names = self.names
        children = self.children
        for v in order:
            ch = children[v]
            if len(ch) > 1:
                tmp = []
                for i in range(len(ch)):
                    c = ch[i]
                    tmp.append((-sub[c], names[c], i))
                tmp.sort()
                nch = []
                for t in tmp:
                    nch.append(ch[t[2]])
                children[v] = nch

    def mirror(self):
        order = self.order()
        children = self.children
        for v in order:
            children[v].reverse()

    def fold(self):
        order = self.order()
        names = self.names
        weights = self.weights
        children = self.children
        idx = len(order) - 1
        while idx >= 0:
            v = order[idx]
            if v != 0:
                ch = children[v]
                while len(ch) == 1:
                    c = ch[0]
                    names[v] = names[v] + '+' + names[c]
                    weights[v] = weights[v] + weights[c]
                    ch = children[c]
                    children[v] = ch
            idx -= 1

    def cut(self, name):
        names = self.names
        weights = self.weights
        children = self.children
        stack = [(0, -1)]
        while stack:
            v, p = stack.pop()
            if names[v] == name:
                if p == -1:
                    return
                ch = children[p]
                pos = -1
                for i in range(len(ch)):
                    if ch[i] == v:
                        pos = i
                        break
                if pos >= 0:
                    newch = ch[:pos] + children[v] + ch[pos + 1:]
                    children[p] = newch
                    self.total -= weights[v]
                return
            ch = children[v]
            for i in range(len(ch) - 1, -1, -1):
                stack.append((ch[i], v))


def main():
    data = sys.stdin.read()
    if '\r' in data:
        sys.exit(1)
    lines = data.split('\n')
    if data.endswith('\n'):
        lines.pop()
    for ln in lines:
        if ln == '':
            sys.exit(1)
    try:
        names, weights, children = parse_tree(lines[0])
    except Exception:
        sys.exit(1)
    ops = []
    try:
        for i in range(1, len(lines)):
            ops.append(parse_op(lines[i]))
    except Exception:
        sys.exit(1)

    t = Tree(names, weights, children)
    out = Writer()

    for op in ops:
        k = op[0]
        if k == 'total':
            out.add(str(t.total))
            out.add('\n')
        elif k == 'stats':
            nodes, leaves, height, widest = t.get_stats()
            out.add('nodes=')
            out.add(str(nodes))
            out.add(' leaves=')
            out.add(str(leaves))
            out.add(' height=')
            out.add(str(height))
            out.add(' widest=')
            out.add(str(widest))
            out.add('\n')
        elif k == 'level':
            count, ssum = t.level(op[1])
            out.add(str(count))
            out.add(' ')
            out.add(str(ssum))
            out.add('\n')
        elif k == 'find':
            p = t.find_path(op[1])
            if p is None:
                out.add('none\n')
            else:
                out.add(p)
                out.add('\n')
        elif k == 'print':
            t.serialize(out)
        elif k == 'prune':
            t.prune(op[1])
        elif k == 'sort':
            t.sort_children()
        elif k == 'mirror':
            t.mirror()
        elif k == 'fold':
            t.fold()
        elif k == 'cut':
            t.cut(op[1])

    out.flush()


main()
