"""Reference implementation of tree_fold (see spec.md): reference.py < input

Nodes live in parallel lists (name, weight, children); every walk is iterative because the tree
may be 5000 levels deep.
"""
import re
import sys

NODE = re.compile(r'([a-z]{1,16}):(0|[1-9][0-9]{0,6})')
OP = re.compile(r'(total|stats|print|sort|mirror|fold)|(level|prune) (0|[1-9][0-9]*)|(find|cut) ([a-z+]+)')


class Bad(Exception):
    pass


class Tree:
    def __init__(self):
        self.name = []
        self.weight = []
        self.kids = []

    def new(self, name, weight, kids=None):
        self.name.append(name)
        self.weight.append(weight)
        self.kids.append(kids if kids is not None else [])
        return len(self.name) - 1

    def parse(self, line):
        pos = 0
        n = len(line)
        stack = []
        while True:
            m = NODE.match(line, pos)
            if not m or int(m.group(2)) > 1000000:
                raise Bad
            node = self.new(m.group(1), int(m.group(2)))
            if stack:
                self.kids[stack[-1]].append(node)
            pos = m.end()
            if pos < n and line[pos] == '[':
                stack.append(node)
                pos += 1
                continue
            while True:
                if not stack:
                    if pos != n:
                        raise Bad
                    return 0
                c = line[pos] if pos < n else ''
                if c == ' ':
                    pos += 1
                    break
                if c == ']':
                    stack.pop()
                    pos += 1
                    continue
                raise Bad

    def preorder(self, root=0):
        """Yields (node, parent, depth) in pre-order."""
        kids = self.kids
        stack = [(root, -1, 0)]
        while stack:
            node, parent, depth = stack.pop()
            yield node, parent, depth
            ch = kids[node]
            for i in range(len(ch) - 1, -1, -1):
                stack.append((ch[i], node, depth + 1))

    def order(self):
        kids = self.kids
        out = [0]
        i = 0
        while i < len(out):          # breadth-first is enough for bottom-up sums
            out.extend(kids[out[i]])
            i += 1
        return out

    def sums(self):
        s = {}
        weight = self.weight
        kids = self.kids
        for node in reversed(self.order()):
            t = weight[node]
            for c in kids[node]:
                t += s[c]
            s[node] = t
        return s


def main():
    data = sys.stdin.buffer.read()
    try:
        text = data.decode('ascii')
    except UnicodeDecodeError:
        return 1
    if '\r' in text:
        return 1
    lines = text.split('\n')
    if text.endswith('\n'):
        lines.pop()
    if not lines:
        return 1
    tree = Tree()
    ops = []
    try:
        tree.parse(lines[0])
        for line in lines[1:]:
            m = OP.fullmatch(line)
            if not m:
                raise Bad
            if m.group(1):
                ops.append((m.group(1), None))
            elif m.group(2):
                v = int(m.group(3))
                if v > 10 ** 15:
                    raise Bad
                ops.append((m.group(2), v))
            else:
                ops.append((m.group(4), m.group(5)))
    except Bad:
        return 1
    out = []
    name, weight, kids = tree.name, tree.weight, tree.kids
    for op, arg in ops:
        if op == 'total':
            out.append(str(sum(weight[x] for x in tree.order())))
        elif op == 'stats':
            nodes = leaves = height = widest = 0
            for node, _, depth in tree.preorder():
                nodes += 1
                k = len(kids[node])
                if k == 0:
                    leaves += 1
                if k > widest:
                    widest = k
                if depth > height:
                    height = depth
            out.append('nodes=%d leaves=%d height=%d widest=%d' % (nodes, leaves, height, widest))
        elif op == 'level':
            cnt = tot = 0
            frontier = [0]
            for _ in range(arg):
                if not frontier:
                    break
                frontier = [c for x in frontier for c in kids[x]]
            for x in frontier:
                cnt += 1
                tot += weight[x]
            out.append('%d %d' % (cnt, tot))
        elif op == 'find':
            path = None
            stack = [(0, None)]
            # pre-order with a path; paths are rebuilt from parent links only for the match
            parent = {}
            for node, par, _ in tree.preorder():
                parent[node] = par
                if name[node] == arg:
                    path = []
                    while node != -1:
                        path.append(name[node])
                        node = parent[node]
                    break
            out.append('/'.join(reversed(path)) if path is not None else 'none')
        elif op == 'print':
            parts = []
            stack = [0]
            while stack:
                item = stack.pop()
                if isinstance(item, str):
                    parts.append(item)
                    continue
                parts.append('%s:%d' % (name[item], weight[item]))
                ch = kids[item]
                if ch:
                    parts.append('[')
                    stack.append(']')
                    for i in range(len(ch) - 1, -1, -1):
                        stack.append(ch[i])
                        if i > 0:
                            stack.append(' ')
            out.append(''.join(parts))
        elif op == 'prune':
            s = tree.sums()
            for x in tree.order():
                if any(s[c] < arg for c in kids[x]):
                    kids[x] = [c for c in kids[x] if s[c] >= arg]
        elif op == 'sort':
            s = tree.sums()
            for x in tree.order():
                if len(kids[x]) > 1:
                    kids[x].sort(key=lambda c: (-s[c], name[c]))
        elif op == 'mirror':
            for x in tree.order():
                kids[x].reverse()
        elif op == 'fold':
            todo = [0]
            while todo:
                x = todo.pop()
                ch = kids[x]
                for i, c in enumerate(ch):
                    if len(kids[c]) == 1:
                        parts = [name[c]]
                        w = weight[c]
                        cur = c
                        while len(kids[cur]) == 1:
                            cur = kids[cur][0]
                            parts.append(name[cur])
                            w += weight[cur]
                        ch[i] = tree.new('+'.join(parts), w, kids[cur])
                    todo.append(ch[i])
        elif op == 'cut':
            for node, par, _ in tree.preorder():
                if name[node] == arg:
                    if par != -1:
                        pk = kids[par]
                        i = pk.index(node)
                        pk[i:i + 1] = kids[node]
                    break
    sys.stdout.write(''.join(line + '\n' for line in out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
