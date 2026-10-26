"""Single inheritance on the typed path (docs/design/TYPED_INHERITANCE.md), against CPython 3.12 and the general path.

A class may derive from one class of the program: prefix struct layout, a dispatcher on the run-time class id for a
method an override makes ambiguous (a direct call otherwise), `super().__init__` / `super().m()` / `B.m(self)`,
`isinstance` by class-id range, base-typed parameters, locals, fields and lists, class attributes inherited and
redefined, the dynamic class's drop function on release.

T1  fixed programs: the typed path alone (AIL_NO_GENERAL=1) prints what CPython prints, and so does the general path
T2  refusals by name: multiple inheritance, a library base, an override with other types or arity, a reachable stub,
    a method or field only a subclass has, a class attribute assignment, a constructor that skips super().__init__
    or reads a base field before it, a super().__init__ argument with a call, a bare super()
T3  random hierarchies (`gen_program`): CPython == typed path == general path
T4  ASan + UBSan + LSan on the C of T1 and of some T3 programs (a wrong drop function is a leak or a double free)
T5  the C: a method no subclass overrides is a direct call, an override is a switch on the class id; the prefix
    layout is asserted; the IR (AIL_IR=1) leaves these functions to the legacy emitter with the same output
"""
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYC = ROOT / 'python' / 'pkg-v12' / 'pyc.py'
HAVE_CC = shutil.which('gcc') is not None
SEEDS = int(os.environ.get('AIL_TYPED_INHERIT_SEEDS', '10'))


def build_typed(directory, text, name, extra_env=None):
    """Compile `text` on the typed path alone; returns (process, exe, kept C path)."""
    source, exe, keep = Path(directory, name + '.py'), Path(directory, name + '_t'), Path(directory, name + '.d')
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_GENERAL='1', AIL_NO_CACHE='1')
    env.setdefault('AIL_IR', '0')
    env.update(extra_env or {})
    res = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name, '--syntax',
                          'python', '-o', exe.name, '--debug-dir', keep.name], cwd=directory, capture_output=True,
                         text=True, timeout=900, env=env)
    return res, exe, keep / 'program.c'


def build_general(directory, text, name):
    source, exe = Path(directory, name + '_g.py'), Path(directory, name + '_g')
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_IR='0', AIL_NO_CACHE='1')
    env.pop('AIL_NO_GENERAL', None)
    res = subprocess.run([sys.executable, '-B', str(PYC), exe.name, '--file', source.name, '--general-only'],
                         cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    return res, exe


def run_cpython(directory, text, name):
    source = Path(directory, name + '_cpython.py')
    source.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, str(source)], capture_output=True, text=True, timeout=300,
                          encoding='utf-8')


def run_exe(exe, env=None):
    return subprocess.run([str(exe)], capture_output=True, text=True, timeout=300, encoding='utf-8', env=env)


ANIMALS = '''class Animal:
    def __init__(self, name: str, legs: int) -> None:
        self.name = name
        self.legs = legs

    def sound(self) -> str:
        return "..."

    def describe(self) -> str:
        return self.name + " says " + self.sound()


class Dog(Animal):
    def __init__(self, name: str) -> None:
        super().__init__(name, 4)
        self.tricks = 0

    def sound(self) -> str:
        return "woof"


class Bird(Animal):
    def __init__(self, name: str, can_fly: int) -> None:
        super().__init__(name, 2)
        self.can_fly = can_fly

    def sound(self) -> str:
        return "tweet"


class Puppy(Dog):
    def sound(self) -> str:
        return "yip " + super().sound()


def total_legs(animals: list[Animal]) -> int:
    t = 0
    for a in animals:
        t += a.legs
    return t


def main() -> None:
    animals: list[Animal] = [Dog("rex"), Bird("tweety", 1), Animal("thing", 0), Puppy("bit")]
    for a in animals:
        print(a.describe())
    print(total_legs(animals))
    d = Dog("fido")
    d.tricks = 3
    print(d.name, d.legs, d.tricks, d.describe())
    p = Puppy("small")
    print(p.describe(), p.legs)


main()
'''

EXPR = '''class Expr:
    def __init__(self) -> None:
        pass

    def eval(self) -> int:
        return 0

    def show(self) -> str:
        return "?"


class Num(Expr):
    def __init__(self, v: int) -> None:
        super().__init__()
        self.v = v

    def eval(self) -> int:
        return self.v

    def show(self) -> str:
        return str(self.v)


class Add(Expr):
    def __init__(self, left: Expr, right: Expr) -> None:
        super().__init__()
        self.left = left
        self.right = right

    def eval(self) -> int:
        return self.left.eval() + self.right.eval()

    def show(self) -> str:
        return "(" + self.left.show() + " + " + self.right.show() + ")"


class Mul(Add):
    def eval(self) -> int:
        return self.left.eval() * self.right.eval()

    def show(self) -> str:
        return "(" + self.left.show() + " * " + self.right.show() + ")"


def build(n: int) -> Expr:
    if n <= 1:
        return Num(n + 2)
    if n % 2 == 0:
        return Add(build(n - 1), Num(n))
    return Mul(build(n - 2), Num(3))


def count_nums(e: Expr) -> int:
    if isinstance(e, Num):
        return 1
    if isinstance(e, Add):
        return count_nums(e.left) + count_nums(e.right)
    return 0


def main() -> None:
    for n in range(1, 9):
        e = build(n)
        print(n, e.show(), e.eval(), count_nums(e), isinstance(e, Add), isinstance(e, Mul), isinstance(e, (Num, Mul)))


main()
'''

ACCOUNTS = '''class Account:
    KIND = "basic"
    RATE = 0.01
    LIMIT = 100

    def __init__(self, owner: str, balance: float) -> None:
        self.owner = owner
        self.balance = balance

    def interest(self) -> float:
        return self.balance * self.RATE

    def label(self) -> str:
        return self.KIND + ":" + self.owner


class Savings(Account):
    KIND = "savings"
    RATE = 0.05


class Premium(Savings):
    LIMIT = 1000

    def __init__(self, owner: str, balance: float, bonus: float) -> None:
        super().__init__(owner, balance + bonus)
        self.bonus = bonus


def main() -> None:
    accts: list[Account] = []
    accts.append(Account("ann", 100.0))
    accts.append(Savings("bob", 200.0))
    accts.append(Premium("cy", 300.0, 50.0))
    for a in accts:
        print(a.label(), a.interest(), a.LIMIT, a.KIND)
    print(Account.KIND, Savings.RATE, Premium.LIMIT, Premium.KIND)
    total = 0.0
    for a in accts:
        if isinstance(a, Savings):
            total += a.interest()
        if isinstance(a, Premium):
            print("bonus", a.bonus)
    print(total)


main()
'''

LOGGERS = '''class Logger:
    def __init__(self, prefix: str) -> None:
        self.prefix = prefix
        self.count = 0

    def log(self, msg: str) -> None:
        self.count += 1
        print(self.prefix + msg)

    def tag(self, n: int, sep: str) -> str:
        return self.prefix + sep + str(n)


class Loud(Logger):
    def log(self, msg: str) -> None:
        self.count += 2
        print(self.prefix + msg.upper() + "!")


class Quiet(Logger):
    def __init__(self) -> None:
        super().__init__("q:")
        self.dropped = 0

    def log(self, msg: str) -> None:
        self.dropped += 1

    def tag(self, n: int, sep: str) -> str:
        return "quiet" + sep + super().tag(n * 2, sep)


class Twice(Loud):
    def log(self, msg: str) -> None:
        Loud.log(self, msg)
        super().log(msg + " again")
        Logger.log(self, "base " + msg)


def run_all(ls: list[Logger]) -> int:
    total = 0
    for i, l in enumerate(ls):
        l.log("m" + str(i))
        total += l.count
        print(l.tag(i, sep="/"))
    return total


def main() -> None:
    ls: list[Logger] = [Logger("a:"), Loud("b:"), Quiet(), Twice("t:")]
    print(run_all(ls))
    print(run_all(ls))
    q = Quiet()
    q.log("x")
    q.log("y")
    print(q.dropped, q.count, q.tag(5, "-"))


main()
'''

FIELDS = '''class Item:
    def __init__(self, name: str, weight: float) -> None:
        self.name = name
        self.weight = weight

    def cost(self) -> float:
        return self.weight * 2.0

    def fragile(self) -> bool:
        return False


class Glass(Item):
    def __init__(self, name: str, weight: float, thick: int) -> None:
        super().__init__(name, weight)
        self.thick = thick

    def cost(self) -> float:
        return self.weight * 5.0 + self.thick

    def fragile(self) -> bool:
        return self.thick < 3


class Box:
    def __init__(self, label: str, content: Item) -> None:
        self.label = label
        self.content = content


def heaviest(items: list[Item]) -> Item:
    best = items[0]
    for it in items:
        if it.cost() > best.cost():
            best = it
    return best


def main() -> None:
    boxes = [Box("one", Item("rock", 3.0)), Box("two", Glass("vase", 1.5, 2)), Box("three", Glass("jar", 2.0, 5))]
    total = 0.0
    for cur in boxes:
        print(cur.label, cur.content.name, cur.content.cost(), cur.content.fragile())
        total += cur.content.cost()
    print(total)
    boxes[0].content = Glass("cup", 0.5, 1)
    print(boxes[0].content.cost(), boxes[0].content.fragile(), isinstance(boxes[0].content, Glass))
    items = [Item("a", 1.0), Glass("b", 1.0, 1)]
    items.append(Glass("plate", 1.0, 4))
    print(len(items), sum(i.cost() for i in items), heaviest(items).name)
    for i in sorted(items, key=lambda i: i.cost()):
        print(i.name)
    s = items[0]
    s = items[2]
    print(s.name, s.cost())


main()
'''

TASKS = '''class Task:
    def __init__(self, title: str, done: bool) -> None:
        self.title = title
        self.done = done

    def urgent(self) -> bool:
        return False

    def score(self) -> int:
        return 1


class Bug(Task):
    def __init__(self, title: str, severity: int) -> None:
        super().__init__(title, False)
        self.severity = severity

    def urgent(self) -> bool:
        return self.severity > 2


class Chore(Task):
    pass


def main() -> None:
    ts: list[Task] = [Task("write", True), Bug("crash", 3), Bug("typo", 1), Chore("dishes", False)]
    for t in ts:
        print(t.title, t.done, t.urgent(), t.score())
    b = Bug("leak", 5)
    print(b.done, b.urgent(), b.severity)
    b.done = True
    print(b.done)
    c = Chore("trash", True)
    print(c.done, c.urgent(), isinstance(c, Task), isinstance(c, Bug))


main()
'''

TREE = '''class Node:
    def __init__(self, tag: str) -> None:
        self.tag = tag

    def size(self) -> int:
        return 1

    def render(self) -> str:
        return self.tag


class Text(Node):
    def __init__(self, tag: str, body: str) -> None:
        super().__init__(tag)
        self.body = body * 3

    def size(self) -> int:
        return len(self.body)

    def render(self) -> str:
        return "<" + self.tag + ">" + self.body


class Group(Node):
    def __init__(self, tag: str) -> None:
        super().__init__(tag)
        self.kids: list[Node] = []
        self.weights: list[int] = []

    def add(self, n: Node, w: int) -> None:
        self.kids.append(n)
        self.weights.append(w)

    def size(self) -> int:
        t = 0
        for k in self.kids:
            t += k.size()
        return t + len(self.weights)

    def render(self) -> str:
        out = "[" + self.tag
        for k in self.kids:
            out += " " + k.render()
        return out + "]"


def build(depth: int, seed: int) -> Node:
    if depth == 0:
        if seed % 3 == 0:
            return Node("leaf" + str(seed))
        return Text("t" + str(seed), "ab" * (seed % 4 + 1))
    g = Group("g" + str(depth))
    for i in range(3):
        g.add(build(depth - 1, seed * 3 + i), i)
    return g


def main() -> None:
    total = 0
    for r in range(60):
        tree = build(3, r)
        total += tree.size()
        if r % 20 == 0:
            print(tree.render()[:90])
    print(total)
    nodes: list[Node] = []
    for i in range(10):
        nodes.append(build(i % 3, i))
    nodes = nodes[3:]
    print(len(nodes), sum(n.size() for n in nodes))
    while nodes:
        last = nodes.pop()
        print(last.tag, last.size())


main()
'''

SHAPES = '''class Shape:
    def __init__(self, name: str) -> None:
        self.name = name

    def area(self) -> float:
        return 0.0

    def scaled(self, k: float) -> float:
        return self.area() * k


class Circle(Shape):
    def __init__(self, r: float) -> None:
        super().__init__("circle")
        self.r = r

    def area(self) -> float:
        return 3.14159 * self.r * self.r


class Rect(Shape):
    def __init__(self, w: float, h: float) -> None:
        super().__init__("rect")
        self.w = w
        self.h = h

    def area(self) -> float:
        return self.w * self.h


class Square(Rect):
    def __init__(self, s: float) -> None:
        super().__init__(s, s)
        self.name = "square"


def main() -> None:
    shapes: list[Shape] = []
    for i in range(3000):
        k = i % 3
        if k == 0:
            shapes.append(Circle(float(i % 7) + 1.0))
        elif k == 1:
            shapes.append(Rect(float(i % 5) + 1.0, 2.0))
        else:
            shapes.append(Square(float(i % 4) + 1.0))
    total = 0.0
    rects = 0
    for s in shapes:
        total += s.scaled(0.5)
        if isinstance(s, Rect):
            rects += 1
    print(round(total, 3), rects, shapes[2].name)


main()
'''

NAMES = '''class Shape:
    def __init__(self, name: str) -> None:
        self.name = name

    def area(self) -> float:
        return 0.0


class Circle(Shape):
    def __init__(self, r: float) -> None:
        super().__init__("c")
        self.r = r

    def area(self) -> float:
        return 3.0 * self.r * self.r


class Rect(Shape):
    def __init__(self, w: float, h: float) -> None:
        super().__init__("r")
        self.w = w
        self.h = h

    def area(self) -> float:
        return self.w * self.h


def describe(s: Shape) -> str:
    return type(s).__name__ + " " + str(s.area())


def main() -> None:
    shapes: list[Shape] = [Circle(1.0), Rect(2.0, 3.0), Circle(2.5), Shape("x")]
    for s in shapes:
        print(f"{type(s).__name__} {s.area():.3f} {s.__class__.__name__}")
        if isinstance(s, Circle) and s.r > 2.0:
            print("big circle", s.r)
        if isinstance(s, Rect) and s.w < s.h:
            print("tall", s.w, s.h)
        elif isinstance(s, Circle):
            print("circle", s.r)
        print(describe(s))
    print(describe(Circle(3.0)), describe(Rect(1.0, 1.0)))


main()
'''

FIXED = [('names', NAMES), ('animals', ANIMALS), ('expr', EXPR), ('accounts', ACCOUNTS), ('loggers', LOGGERS), ('fields', FIELDS),
         ('tasks', TASKS), ('tree', TREE), ('shapes', SHAPES)]

_A = '''class A:
    def __init__(self, x: int) -> None:
        self.x = x

    def f(self) -> int:
        return self.x


'''
_MAIN = '''

def main() -> None:
    print(go())


main()
'''
REFUSALS = [
    ('multiple', 'class B:\n    def __init__(self) -> None:\n        self.y = 1\n\n\nclass C(A, B):\n    pass\n\n\n'
                 'def go() -> int:\n    return C(1).f()\n', 'multiple inheritance'),
    ('foreign', 'class P(dict[str, int]):\n    pass\n\n\ndef go() -> int:\n    return A(1).f()\n', 'inheritance from'),
    ('arity', 'class B(A):\n    def f(self, k: int) -> int:\n        return k\n\n\n'
              'def go() -> int:\n    xs: list[A] = [A(1), B(2)]\n    return xs[0].f() + xs[1].x\n', 'takes 1 parameters'),
    ('result', 'class B(A):\n    def f(self) -> float:\n        return 2.5\n\n\n'
               'def go() -> int:\n    xs: list[A] = [A(1), B(2)]\n    return int(xs[1].f())\n', 'declares its result float'),
    ('stub', 'class S:\n    def __init__(self) -> None:\n        self.n = 1\n\n    def area(self) -> float:\n        ...\n\n\n'
             'class Q(S):\n    def area(self) -> float:\n        return 4.0\n\n\n'
             'def go() -> int:\n    xs: list[S] = [Q(), S()]\n    return int(xs[0].area())\n', 'a stub'),
    ('sub_method', 'class B(A):\n    def g(self) -> int:\n        return 7\n\n\n'
                   'def go() -> int:\n    xs: list[A] = [A(1), B(2)]\n    return xs[1].g()\n', 'A has no method g'),
    ('sub_field', 'class B(A):\n    def __init__(self, x: int) -> None:\n        super().__init__(x)\n        self.z = 9\n\n\n'
                  'def go() -> int:\n    xs: list[A] = [A(1), B(2)]\n    return xs[1].z\n', 'only its subclass B has it'),
    ('attr_store', 'class B(A):\n    K = 3\n\n\ndef go() -> int:\n    B.K = 4\n    return B(1).f()\n',
     'assigning the class attribute B.K'),
    ('no_super', 'class B(A):\n    def __init__(self, z: int) -> None:\n        self.z = z\n\n\n'
                 'def go() -> int:\n    return B(2).z\n', 'does not call super().__init__'),
    ('read_before', 'class B(A):\n    def __init__(self, z: int) -> None:\n        self.z = self.x + z\n'
                    '        super().__init__(z)\n\n\ndef go() -> int:\n    return B(2).z\n', 'reads self.x before'),
    ('call_arg', 'def twice(n: int) -> int:\n    return n * 2\n\n\nclass B(A):\n    def __init__(self, z: int) -> None:\n'
                 '        super().__init__(twice(z))\n\n\ndef go() -> int:\n    return B(2).x\n', 'not a name, a constant'),
    ('field_type', 'class B(A):\n    def __init__(self, z: float) -> None:\n        super().__init__(1)\n        self.x = z\n\n\n'
                   'def go() -> int:\n    return int(B(2.5).x)\n', 'an inherited field keeps its type'),
    ('bare_super', 'class B(A):\n    def f(self) -> int:\n        s = super()\n        return s.f()\n\n\n'
                   'def go() -> int:\n    return B(1).f()\n', 'super() other than'),
]


def gen_program(seed):
    """A random single-inheritance program the typed path builds: fields set through super().__init__ chains,
    overrides (int, str and void methods), super() calls, class attributes, isinstance with narrowing, a base-typed
    list, a base-typed field, a function returning the base. Deterministic per seed."""
    rng = random.Random(seed)
    n = rng.randint(2, 7)
    parent = {c: (rng.randrange(c) if c else None) for c in range(n)}
    fields, params, has_init = {}, {}, {}
    for c in range(n):
        if c == 0:
            own = [('a', 'int'), ('s', 'str')]
            has_init[c] = True
        else:
            has_init[c] = rng.random() < 0.7
            own = [('f%d' % c, rng.choice(['int', 'float']))] if has_init[c] and rng.random() < 0.8 else []
        fields[c] = own
        if c == 0:
            params[c] = list(own)
        elif has_init[c]:
            params[c] = params[parent[c]] + [('p%d' % c, k) for _, k in own]
        else:
            params[c] = params[parent[c]]

    def all_fields(c):
        out = []
        while c is not None:
            out = fields[c] + out
            c = parent[c]
        return out
    n_methods = 3
    own_m = {c: (set(range(n_methods)) if c == 0 else {i for i in range(n_methods) if rng.random() < 0.4})
             for c in range(n)}
    own_name = {c: c == 0 or rng.random() < 0.4 for c in range(n)}
    own_bump = {c: c == 0 or rng.random() < 0.3 for c in range(n)}
    attr = {c: (rng.randint(1, 50) if c == 0 or rng.random() < 0.35 else None) for c in range(n)}

    def defined_above(c, has):
        p = parent[c]
        while p is not None:
            if has(p):
                return True
            p = parent[p]
        return False

    L = []
    for c in range(n):
        L.append('class C%d%s:' % (c, '(C%d)' % parent[c] if parent[c] is not None else ''))
        body = []
        if attr[c] is not None:
            body.append('    K = %d' % attr[c])
        if has_init[c]:
            ps = ', '.join('%s: %s' % p for p in params[c])
            body.append('    def __init__(self%s) -> None:' % (', ' + ps if ps else ''))
            if c:
                base_args = [('%s + %d' % (name, rng.randint(1, 5)) if kind == 'int' and rng.random() < 0.4 else name)
                             for name, kind in params[parent[c]]]
                body.append('        super().__init__(%s)' % ', '.join(base_args))
            for (fname, _), (pname, _) in zip(fields[c], params[c][-len(fields[c]):] if fields[c] else []):
                body.append('        self.%s = %s' % (fname, pname))
        for i in sorted(own_m[c]):
            body.append('    def m%d(self, x: int) -> int:' % i)
            terms = ['x * %d' % rng.randint(1, 4)]
            ints = [f for f, k in all_fields(c) if k == 'int']
            if ints and rng.random() < 0.7:
                terms.append('self.%s' % rng.choice(ints))
            floats = [f for f, k in all_fields(c) if k == 'float']
            if floats and rng.random() < 0.5:
                terms.append('int(self.%s * 3)' % rng.choice(floats))
            if rng.random() < 0.4:
                terms.append('len(self.s)')
            if rng.random() < 0.4:
                terms.append('self.K')
            if i + 1 < n_methods and rng.random() < 0.5:
                terms.append('self.m%d(x + %d)' % (rng.randint(i + 1, n_methods - 1), rng.randint(0, 3)))
            if defined_above(c, lambda p: i in own_m[p]) and rng.random() < 0.6:
                terms.append('super().m%d(x)' % i)
            rng.shuffle(terms)
            body.append('        return (%s) %% 100003' % ' + '.join(terms))
        if own_name[c]:
            body.append('    def name(self) -> str:')
            if defined_above(c, lambda p: own_name[p]) and rng.random() < 0.5:
                body.append('        return "C%d<" + super().name()' % c)
            else:
                body.append('        return "C%d:" + self.s' % c)
        if own_bump[c]:
            body.append('    def bump(self, k: int) -> None:')
            body.append('        self.a += k * %d' % rng.randint(1, 3))
            if defined_above(c, lambda p: own_bump[p]) and rng.random() < 0.5:
                body.append('        super().bump(k)')
        L.extend(body or ['    pass'])
        L.extend(['', ''])
    L.extend(['class Holder:', '    def __init__(self, item: C0) -> None:', '        self.item = item', '', ''])

    def ctor(c):
        args = []
        for name, kind in params[c]:
            if name == 's':
                args.append('"%s"' % rng.choice(['x', 'yy', 'zzz', 'abcd']))
            elif kind == 'int':
                args.append(str(rng.randint(-5, 20)))
            else:
                args.append('%d.%d' % (rng.randint(0, 9), rng.choice([0, 25, 5])))
        return 'C%d(%s)' % (c, ', '.join(args))
    L.extend(['def total(xs: list[C0], x: int) -> int:', '    t = 0', '    for o in xs:',
              '        t = (t + o.m0(x) + o.m%d(t %% 7)) %% 100003' % rng.randrange(n_methods), '    return t', '', ''])
    L.extend(['def pick(i: int) -> C0:', '    if i % 2 == 0:', '        return %s' % ctor(rng.randrange(n)),
              '    return %s' % ctor(rng.randrange(n)), '', ''])
    L.extend(['def main() -> None:', '    objs: list[C0] = []'])
    for _ in range(rng.randint(n, 2 * n)):
        L.append('    objs.append(%s)' % ctor(rng.randrange(n)))
    L.append('    for o in objs:')
    L.append('        print(o.m0(%d), o.m1(%d), o.m2(%d), o.name(), o.K, o.a, isinstance(o, C%d))'
             % (rng.randint(0, 9), rng.randint(0, 9), rng.randint(0, 9), rng.randrange(n)))
    for c in range(1, n):
        own_fields = all_fields(c)[2:]
        if own_fields and rng.random() < 0.7:
            L.extend(['    for o in objs:', '        if isinstance(o, C%d):' % c,
                      '            print("C%d", o.%s, o.m0(1))' % (c, rng.choice(own_fields)[0])])
    L.extend(['    for i, o in enumerate(objs):', '        o.bump(i)', '    print(total(objs, %d))' % rng.randint(0, 9),
              '    h = Holder(objs[0])', '    print(h.item.name(), h.item.m1(2))', '    h.item = objs[-1]',
              '    print(h.item.name(), h.item.m1(2), h.item.a)', '    for i in range(3):', '        p = pick(i)',
              '        print(p.name(), p.m2(i), isinstance(p, C%d))' % rng.randrange(n)])
    L.extend('    print(C%d.K)' % c for c in range(n))
    L.extend(['', '', 'main()'])
    return '\n'.join(L) + '\n'


SAN_FLAGS = ['-O1', '-g', '-fsanitize=address,undefined', '-fno-sanitize-recover=undefined', '-fno-omit-frame-pointer',
             '-fno-strict-aliasing', '-w']


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class Base(unittest.TestCase):
    def three_way(self, text, name, sanitize=False, general_refuses=None):
        """CPython, the typed path and the general path print the same; returns the typed path's C.
        `general_refuses`: the general path refuses this program by name (words of its refusal)."""
        with tempfile.TemporaryDirectory(prefix='ail-tinh-') as d:
            ref = run_cpython(d, text, name)
            self.assertEqual(ref.returncode, 0, ref.stderr)
            res, exe, c_path = build_typed(d, text, name)
            self.assertEqual(res.returncode, 0, name + ' (typed): ' + res.stdout + res.stderr)
            self.assertNotIn('general path', res.stderr)
            out = run_exe(exe)
            self.assertEqual((out.returncode, out.stdout), (0, ref.stdout), name + ' (typed)')
            gres, gexe = build_general(d, text, name)
            if general_refuses:
                self.assertNotEqual(gres.returncode, 0, name + ' (general) built')
                self.assertIn(general_refuses, gres.stdout + gres.stderr)
            else:
                self.assertEqual(gres.returncode, 0, name + ' (general): ' + gres.stdout + gres.stderr)
                gout = run_exe(gexe)
                self.assertEqual((gout.returncode, gout.stdout), (0, ref.stdout), name + ' (general)')
            c = c_path.read_text(encoding='utf-8')
            if sanitize:
                san = Path(d, name + '_san')
                cc = subprocess.run(['gcc', *SAN_FLAGS, str(c_path), '-lm', '-o', str(san)], capture_output=True,
                                    text=True)
                self.assertEqual(cc.returncode, 0, cc.stderr[-2000:])
                env = dict(os.environ, ASAN_OPTIONS='detect_leaks=1', UBSAN_OPTIONS='print_stacktrace=1:halt_on_error=1')
                sout = run_exe(san, env)
                self.assertEqual((sout.returncode, sout.stdout), (0, ref.stdout), name + ' (sanitized): ' + sout.stderr[-3000:])
            return c


class TestFixed(Base):
    """T1, T4"""

    def test_fixed_programs(self):
        for name, text in FIXED:
            with self.subTest(program=name):
                # the general path builds type(x).__name__ too since library batch 5 (pyboxed2.expr_Attribute)
                self.three_way(text, 't1_' + name, sanitize=True)


class TestRefusals(Base):
    """T2"""

    def test_refused_by_name(self):
        for name, body, words in REFUSALS:
            with self.subTest(case=name), tempfile.TemporaryDirectory(prefix='ail-tinh-') as d:
                res, exe, _ = build_typed(d, _A + body + _MAIN, 't2_' + name)
                self.assertNotEqual(res.returncode, 0, name + ': built')
                self.assertIn(words, res.stdout + res.stderr, name)
                self.assertFalse(exe.exists())


class TestRandom(Base):
    """T3, T4"""

    def test_random_hierarchies(self):
        for seed in range(SEEDS):
            with self.subTest(seed=seed):
                self.three_way(gen_program(seed), 't3_%d' % seed, sanitize=seed % 3 == 0)

    def test_generator_is_deterministic_and_varied(self):
        self.assertEqual(gen_program(3), gen_program(3))
        texts = [gen_program(s) for s in range(SEEDS)]
        self.assertEqual(len(set(texts)), len(texts))
        self.assertTrue(any('super().m' in t for t in texts) and any('super().bump' in t for t in texts))


class TestShape(Base):
    """T5"""

    def test_dispatch_only_where_an_override_is_reachable(self):
        plain = ('class P:\n    def __init__(self, v: int) -> None:\n        self.v = v\n\n    def a(self) -> int:\n'
                 '        return self.v\n\n\nclass Q(P):\n    def b(self) -> int:\n        return self.a() + 1\n\n\n'
                 'def main() -> None:\n    xs: list[P] = [P(1), Q(2)]\n    for x in xs:\n        print(x.a())\n\n\nmain()\n')
        over = plain.replace('    def b(self)', '    def a(self) -> int:\n        return 5\n\n    def b(self)')
        c_plain = self.three_way(plain, 't5_plain')
        c_over = self.three_way(over, 't5_over')
        self.assertNotIn('__vt', c_plain)
        self.assertIn('P__a__vt', c_over)
        self.assertIn('switch (((ail_obj_header *)v_self)->drop)', c_over)
        self.assertIn('_Static_assert(offsetof(ail_obj_Q, f_v) == offsetof(ail_obj_P, f_v)', c_over)

    def test_one_constructed_subclass_is_a_direct_call(self):
        text = SHAPES.replace('            shapes.append(Circle(float(i % 7) + 1.0))',
                              '            shapes.append(Rect(1.0, 1.0))')
        c = self.three_way(text, 't5_devirt')
        self.assertNotIn('Shape__area__vt', c)            # Rect and Square, the classes built, share Rect.area
        self.assertIn('Rect__area(v_self)', c)

    def test_ir_leaves_hierarchies_to_the_legacy_emitter(self):
        with tempfile.TemporaryDirectory(prefix='ail-tinh-') as d:
            ref = run_cpython(d, EXPR, 't5_ir')
            res, exe, _ = build_typed(d, EXPR, 't5_ir', {'AIL_IR': '1'})
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertEqual(run_exe(exe).stdout, ref.stdout)

    def test_no_inheritance_no_change(self):
        plain = ('class P:\n    def __init__(self, v: int) -> None:\n        self.v = v\n\n    def a(self) -> int:\n'
                 '        return self.v\n\n\ndef main() -> None:\n    print(P(3).a())\n\n\nmain()\n')
        c = self.three_way(plain, 't5_none')
        self.assertNotIn('incompatible-pointer-types', c)
        self.assertNotIn('a subclass begins with its base', c)

    def test_unrelated_same_named_methods_keep_their_own_signature(self):
        text = ('class A:\n    def __init__(self, v: int) -> None:\n        self.v = v\n\n'
                '    def calc(self, x: int) -> int:\n        return x * 2 + self.v\n\n\n'
                'class B(A):\n    def calc(self, x: int) -> int:\n        return x * 3 - self.v\n\n\n'
                'class C:\n    def __init__(self, v: int) -> None:\n        self.v = v\n\n'
                '    def calc(self, x: int) -> str:\n        return "c%d" % (x + self.v)\n\n\n'
                'class D:\n    def __init__(self, v: int) -> None:\n        self.v = v\n\n'
                '    def calc(self, x: int, y: int) -> int:\n        return x + y + self.v\n\n\n'
                'def main() -> None:\n    print(A(1).calc(5), B(2).calc(5), C(3).calc(5), D(4).calc(5, 6))\n'
                '    print(A(1).calc(-2), B(2).calc(-2), C(3).calc(-2), D(4).calc(-2, -3))\n\n\nmain()\n')
        with tempfile.TemporaryDirectory(prefix='ail-tinh-') as d:
            ref = run_cpython(d, text, 't5_names')
            self.assertEqual(ref.returncode, 0, ref.stderr)
            res, exe, _ = build_typed(d, text, 't5_names', {'AIL_IR': '1'})
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
            out = run_exe(exe)
            self.assertEqual((out.returncode, out.stdout), (0, ref.stdout), out.stderr[-2000:])


if __name__ == '__main__':
    unittest.main()
