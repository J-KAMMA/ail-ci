"""Multi-file projects, compared with CPython (`python3 main.py` is the oracle).

Each layout is a set of files written to a temporary directory; the program built by
`ail_chatgpt.py compile main.py --syntax python` must print the same bytes as CPython. Covered:

* a package with submodules, a subpackage using `from .util import f` / `from ..models import M`,
  module-level constants and dicts, a class imported in one module and subclassed in another,
  `import app.util as u`, `from app import models`, a dataclass and an enum defined in one module
  and used in another, module state mutated by functions of another module (`global`, `m.x = v`);
* function-level imports (the usual way to break an import cycle), in the entry file, in package
  modules and in methods: moved to the top of the module when the imported modules have no effect at
  import time; refused by name, with the file:line of the effect, when they have;
* the refusals that remain for imports below the top level (class body, `try`, a builtin name,
  a name bound to two imports, a module-level name of the same name, a variable that changes).
"""
import unittest

from test_ail_modules import ModulesBase



LAYOUTS = {'p_full': {'app/__init__.py': 'VERSION = "1.2"\n',
            'app/core/__init__.py': '',
            'app/core/helpers.py': 'from .util2 import g\n'
                                   'from ..util import f\n'
                                   'from ..models import M\n'
                                   '\n'
                                   'class Sub(M):\n'
                                   '    def describe(self):\n'
                                   '        return "Sub:" + M.describe(self)\n'
                                   '\n'
                                   'def h(n):\n'
                                   '    return f(n) + g(n)\n'
                                   '\n'
                                   'def mk(n):\n'
                                   '    return Sub(n)\n',
            'app/core/util2.py': 'def g(n):\n    return n + 100\n',
            'app/models.py': 'from dataclasses import dataclass\n'
                             'from enum import Enum\n'
                             'from . import util\n'
                             '\n'
                             'class Color(Enum):\n'
                             '    RED = 1\n'
                             '    GREEN = 2\n'
                             '\n'
                             '@dataclass\n'
                             'class Point:\n'
                             '    x: int\n'
                             '    y: int\n'
                             '    def norm1(self):\n'
                             '        return abs(self.x) + abs(self.y)\n'
                             '\n'
                             'class M:\n'
                             '    def __init__(self, v):\n'
                             '        self.v = v\n'
                             '    def describe(self):\n'
                             '        return "M(%d)" % self.v\n'
                             '    def twice(self):\n'
                             '        return util.f(self.v)\n'
                             '\n'
                             'def make_color(n):\n'
                             '    return Color(n)\n'
                             '\n'
                             'def late():\n'
                             '    from app.core import helpers\n'
                             '    return helpers.h(3)\n',
            'app/util.py': 'LIMIT = 10\n'
                           'REGISTRY = {"a": 1, "b": 2}\n'
                           'counter = 0\n'
                           'log = []\n'
                           '\n'
                           'def f(x):\n'
                           '    return x * 2 + LIMIT\n'
                           '\n'
                           'def bump(n=1):\n'
                           '    global counter\n'
                           '    counter += n\n'
                           '    log.append(counter)\n'
                           '    return counter\n'
                           '\n'
                           'def lookup(k):\n'
                           '    return REGISTRY.get(k, -1)\n',
            'main.py': 'import app.util as u\n'
                       'from app import models\n'
                       'from app.models import Point, Color, M\n'
                       'from app.core.helpers import Sub, mk, h\n'
                       'import app\n'
                       '\n'
                       'def main():\n'
                       '    print(app.VERSION, u.LIMIT, u.REGISTRY["a"], u.lookup("b"), u.lookup("zz"))\n'
                       '    print(u.bump(), u.bump(5), u.counter, u.log)\n'
                       '    m = models.M(4)\n'
                       '    print(m.describe(), m.twice())\n'
                       '    s = mk(7)\n'
                       '    print(s.describe(), s.twice(), isinstance(s, M), isinstance(s, Sub))\n'
                       '    p = Point(3, -4)\n'
                       '    print(p, p.norm1(), p == Point(3, -4))\n'
                       '    print(Color.RED, models.make_color(2), Color.GREEN.value, list(Color))\n'
                       '    print(models.late(), h(1))\n'
                       '    u.counter = 100\n'
                       '    print(u.bump(), u.counter)\n'
                       '    u.REGISTRY["c"] = 3\n'
                       '    print(sorted(u.REGISTRY.items()))\n'
                       '    print(__name__)\n'
                       '\n'
                       'if __name__ == "__main__":\n'
                       '    main()\n'},
 'l1_entry': {'lib.py': 'K = 5\n'
                        'D = {"a": [1, 2]}\n'
                        '\n'
                        'class C:\n'
                        '    def __init__(self, v):\n'
                        '        self.v = v\n'
                        '    def get(self):\n'
                        '        return self.v + K\n'
                        '\n'
                        'def f(x):\n'
                        '    return x + K\n',
              'main.py': 'def a():\n'
                         '    import lib\n'
                         '    return lib.f(1), lib.K, lib.D["a"]\n'
                         '\n'
                         'def b():\n'
                         '    from lib import f, C\n'
                         '    return f(2), C(3).get()\n'
                         '\n'
                         'def c():\n'
                         '    import lib as L\n'
                         '    return L.C(10).get()\n'
                         '\n'
                         'class W:\n'
                         '    def m(self):\n'
                         '        from lib import K as kk\n'
                         '        return kk * 2\n'
                         '\n'
                         'print(a(), b(), c(), W().m())\n'},
 'l8_pkg': {'main.py': 'import pkg.a\n'
                       'print(pkg.a.use().who(), pkg.a.n(), isinstance(pkg.a.use(), pkg.a.A))\n',
            'pkg/__init__.py': '',
            'pkg/a.py': 'from . import b\n'
                        '\n'
                        'class A:\n'
                        '    pass\n'
                        '\n'
                        'def use():\n'
                        '    from .c import make\n'
                        '    return make()\n'
                        '\n'
                        'def n():\n'
                        '    return b.val()\n',
            'pkg/b.py': 'def val():\n    return 7\n',
            'pkg/c.py': 'from .a import A\n'
                        '\n'
                        'class Child(A):\n'
                        '    def who(self):\n'
                        '        return "child"\n'
                        '\n'
                        'def make():\n'
                        '    return Child()\n'},
 'l9_nested': {'lib.py': 'def f():\n    return "lib.f"\n',
               'main.py': 'def a():\n'
                          '    import lib\n'
                          '    def inner():\n'
                          '        return lib.f()\n'
                          '    return inner()\n'
                          '\n'
                          'def b():\n'
                          '    import lib\n'
                          '    return lib.f()\n'
                          '\n'
                          'print(a(), b())\n',
               'other.py': 'def f():\n    return "other.f"\n'},
 'l11_dc': {'m.py': 'from dataclasses import dataclass\n'
                    'from enum import Enum\n'
                    '\n'
                    'class Kind(Enum):\n'
                    '    A = 1\n'
                    '    B = 2\n'
                    '\n'
                    '@dataclass\n'
                    'class P:\n'
                    '    x: int\n'
                    '    k: int = 3\n',
            'main.py': 'def mk(n):\n'
                       '    from m import P\n'
                       '    return P(n)\n'
                       '\n'
                       'def kind(n):\n'
                       '    import m\n'
                       '    return m.Kind(n)\n'
                       '\n'
                       'def other():\n'
                       '    P = 5\n'
                       '    return P\n'
                       '\n'
                       'if __name__ == "__main__":\n'
                       '    print(mk(1), kind(2), other())\n'},
 'l14_eager': {'lib.py': 'print("lib loaded")\nK = 4\n',
               'main.py': 'import lib\n\ndef f():\n    import lib\n    return lib.K\n\nprint(f())\n'},
 'l15_chain': {'main.py': 'def f():\n    import pkg.m\n    return pkg.m.K\n\nprint(f())\n',
               'pkg/__init__.py': '',
               'pkg/m.py': 'K = 9\n'},
 'm1_misc': {'main.py': 'import sys\n'
                        'import shop\n'
                        'from shop import store, Item\n'
                        'from shop.errors import OutOfStock, ShopError\n'
                        'from shop.items import CALLS, gen, NAMES\n'
                        'import shop.items as items\n'
                        '\n'
                        'def main():\n'
                        '    store.add("pen", 2)\n'
                        '    store.add("bad", -1)\n'
                        '    print(store.buy("pen"), CALLS, items.CALLS is CALLS)\n'
                        '    for n in ("bad", "nope"):\n'
                        '        try:\n'
                        '            store.buy(n)\n'
                        '        except OutOfStock as e:\n'
                        '            print("oos", e, e.name)\n'
                        '        except ShopError as e:\n'
                        '            print("shop", e)\n'
                        '    print(Item.count, items.Item.count, shop.Item is Item)\n'
                        '    print(Item("a", 2).gross, Item.make("x"), Item("a", 9) == Item("a", 1))\n'
                        '    print(list(map(items.price_of, [Item("z", 4)])), [i.price for i in gen(3)])\n'
                        '    print(NAMES, items.TAX, items.__name__, __name__, sorted(store.STOCK))\n'
                        '    print(sorted(shop.store.STOCK) == sorted(store.STOCK))\n'
                        '\n'
                        'if __name__ == "__main__":\n'
                        '    main()\n',
             'shop/__init__.py': 'from .items import Item, TAX\n'
                                 'from . import store\n'
                                 '__all__ = ["Item", "store"]\n',
             'shop/errors.py': 'class ShopError(Exception):\n'
                               '    pass\n'
                               '\n'
                               'class OutOfStock(ShopError):\n'
                               '    def __init__(self, name):\n'
                               '        super().__init__("out of stock: " + name)\n'
                               '        self.name = name\n',
             'shop/items.py': 'from typing import List, Dict\n'
                              'from .errors import OutOfStock\n'
                              '\n'
                              'TAX = 0.25\n'
                              'NAMES: List[str] = ["pen", "ink"]\n'
                              '\n'
                              'CALLS = []\n'
                              '\n'
                              'class Item:\n'
                              '    count = 2\n'
                              '    def __init__(self, name, price):\n'
                              '        self.name = name\n'
                              '        self.price = price\n'
                              '    def __repr__(self):\n'
                              '        return "Item(%r, %r)" % (self.name, self.price)\n'
                              '    def __eq__(self, other):\n'
                              '        return self.name == other.name\n'
                              '    @property\n'
                              '    def gross(self):\n'
                              '        return self.price * (1 + TAX)\n'
                              '    @staticmethod\n'
                              '    def make(name):\n'
                              '        return Item(name, 1.5)\n'
                              '\n'
                              '\n'
                              'def price_of(it):\n'
                              '    if it.price < 0:\n'
                              '        raise OutOfStock(it.name)\n'
                              '    CALLS.append(it.name)\n'
                              '    return it.price\n'
                              '\n'
                              'def gen(n):\n'
                              '    for i in range(n):\n'
                              '        yield Item("g%d" % i, i)\n',
             'shop/store.py': 'from .items import Item, price_of, gen\n'
                              'from . import errors\n'
                              '\n'
                              'STOCK: dict = {}\n'
                              '\n'
                              'def add(name, price):\n'
                              '    STOCK[name] = Item(name, price)\n'
                              '    return STOCK[name]\n'
                              '\n'
                              'def buy(name):\n'
                              '    it = STOCK.get(name)\n'
                              '    if it is None:\n'
                              '        raise errors.ShopError("unknown " + name)\n'
                              '    return price_of(it)\n'},
 'm2_star': {'a.py': 'from b import *\n__all__ = ["x", "fa"]\nx = 1\ny = 2\ndef fa():\n    return x + bb\n',
             'b.py': 'bb = 10\ndef fb():\n    return 2\n',
             'main.py': 'from a import *\nprint(x, fa())\n\n'},
 'm3_state': {'cfg.py': 'DEBUG = False\nLEVELS = {"lo": 1, "hi": 5}\nHISTORY = []\n',
              'main.py': 'import cfg\n'
                         'import ops\n'
                         'from cfg import LEVELS, HISTORY\n'
                         'print(ops.level("lo"))\n'
                         'ops.set_debug(True)\n'
                         'print(ops.level("hi"), cfg.DEBUG)\n'
                         'ops.add_level("mid", 3)\n'
                         'print(sorted(LEVELS.items()), HISTORY)\n'
                         'cfg.DEBUG = False\n'
                         'print(ops.level("mid"))\n',
              'ops.py': 'import cfg\n'
                        '\n'
                        'def set_debug(v):\n'
                        '    cfg.DEBUG = v\n'
                        '    cfg.HISTORY.append(("debug", v))\n'
                        '\n'
                        'def level(n):\n'
                        '    return cfg.LEVELS[n] + (100 if cfg.DEBUG else 0)\n'
                        '\n'
                        'def add_level(n, v):\n'
                        '    cfg.LEVELS[n] = v\n'},
 'm4_importtime': {'a.py': 'print("a start")\nimport b\nprint("a end", b.V)\nA = 1\n',
                   'b.py': 'print("b runs")\nV = 5\n',
                   'main.py': 'print("main start")\nimport a\nimport b\nprint(a.A, b.V)\n'},
 'l2_impure': {'lib.py': 'print("hello from lib")\nK = 1\n',
               'main.py': 'def a():\n    import lib\n    return lib.K\n\nprint("start")\nprint(a())\n'},
 'l3_mutable': {'main.py': 'import st\n'
                           '\n'
                           'def show():\n'
                           '    from st import n\n'
                           '    return n\n'
                           '\n'
                           'st.inc()\n'
                           'print(show())\n'
                           'st.inc()\n'
                           'print(show())\n',
                'st.py': 'n = 0\n\ndef inc():\n    global n\n    n += 1\n'},
 'l4_class': {'lib.py': 'K = 1\n', 'main.py': 'class A:\n    import lib\n\nprint(A.lib.K)\n'},
 'l5_try': {'lib.py': 'K = 1\n',
            'main.py': 'def f():\n'
                       '    try:\n'
                       '        import lib\n'
                       '    except ImportError:\n'
                       '        lib = None\n'
                       '    return lib.K\n'
                       '\n'
                       'print(f())\n'},
 'l6_builtin': {'lib.py': 'def max(a, b):\n    return -1\n',
                'main.py': 'def f():\n'
                           '    from lib import max\n'
                           '    return max(1, 2)\n'
                           '\n'
                           'def g():\n'
                           '    return max(1, 2)\n'
                           '\n'
                           'print(f(), g())\n'},
 'l7_attr': {'a.py': 'def f():\n    import lib\n    return lib.K\n',
             'lib.py': 'K = 1\n',
             'main.py': 'import a\n'
                        'print(a.f())\n'
                        'try:\n'
                        '    print(a.lib.K)\n'
                        'except AttributeError:\n'
                        '    print("AttributeError")\n'},
 'l10_twoimports': {'lib.py': 'def f():\n    return "lib.f"\n',
                    'main.py': 'def a():\n'
                               '    from lib import f\n'
                               '    return f()\n'
                               '\n'
                               'def b():\n'
                               '    from other import f\n'
                               '    return f()\n'
                               '\n'
                               'print(a(), b())\n',
                    'other.py': 'def f():\n    return "other.f"\n'},
 'l12_conflict': {'a.py': 'lib = 3\n\ndef f():\n    import lib\n    return lib.K\n',
                  'lib.py': 'K = 1\n',
                  'main.py': 'import a\nprint(a.f(), a.lib)\n'},
 'l13_trans': {'main.py': 'def f():\n    import x\n    return x.K\n\nprint(f())\n',
               'x.py': 'import y\nK = 1\n',
               'y.py': 'print("y runs")\nZ = 2\n'}}

LAYOUTS.update({'l16_values': {'lib.py': 'class Box:\n'
                          '    def __init__(self, v):\n'
                          '        self.v = v\n'
                          '\n'
                          'def dbl(x):\n'
                          '    return x * 2\n'
                          '\n'
                          'TABLE = {"k": [1, 2, 3]}\n'
                          'NAME = "lib"\n',
                'main.py': 'import pkg.a\n'
                           '\n'
                           'def apply(fn, x):\n'
                           '    return fn(x)\n'
                           '\n'
                           'def go():\n'
                           '    from lib import dbl, Box, TABLE, NAME\n'
                           '    fns = [dbl, lambda x: x + 1]\n'
                           '    reg = {"d": dbl}\n'
                           '    h = pkg.a.fill()\n'
                           '    res = [apply(dbl, 4), fns[0](5), reg["d"](6), pkg.a.run(h, 7), list(map(dbl, '
                           'TABLE["k"]))]\n'
                           '    b = Box(3)\n'
                           '    holder = pkg.a.Holder()\n'
                           '    holder.b = b\n'
                           '    res.append(isinstance(holder.b, Box))\n'
                           '    res.append(NAME + "!")\n'
                           '    for i in range(2):\n'
                           '        import lib\n'
                           '        res.append(lib.dbl(i))\n'
                           '    return res\n'
                           '\n'
                           'def gen():\n'
                           '    import lib\n'
                           '    yield lib.dbl(1)\n'
                           '    yield lib.NAME\n'
                           '\n'
                           'print(go(), list(gen()), go() == go())\n',
                'pkg/__init__.py': '',
                'pkg/a.py': 'class Holder:\n'
                            '    pass\n'
                            '\n'
                            'def fill():\n'
                            '    from . import b as bb\n'
                            '    h = Holder()\n'
                            '    h.v = bb.triple(5)\n'
                            '    return h\n'
                            '\n'
                            'def run(h, x):\n'
                            '    return h.v + x\n',
                'pkg/b.py': 'def triple(x):\n    return x * 3\n'},
 'l17_init_call': {'a.py': 'def f():\n    import lib\n    return lib.K\n\nRESULT = f()\n',
                   'lib.py': 'K = 5\n',
                   'main.py': 'import a\nprint(a.RESULT)\n'},
 'l18_init_class': {'a.py': 'class Base:\n'
                            '    def m(self):\n'
                            '        import lib\n'
                            '        return lib.K\n'
                            '\n'
                            'class Sub(Base):\n'
                            '    pass\n'
                            '\n'
                            'def make():\n'
                            '    return Sub()\n',
                    'lib.py': 'K = 5\n',
                    'main.py': 'import a\nprint(a.make().m(), a.Sub().m())\n'},
 'l19_init_class_call': {'a.py': 'class Base:\n'
                                 '    def __init__(self):\n'
                                 '        import lib\n'
                                 '        self.v = lib.K\n'
                                 '\n'
                                 'OBJ = Base()\n',
                         'lib.py': 'K = 5\n',
                         'main.py': 'import a\nprint(a.OBJ.v)\n'},
 'l20_via_helper': {'a.py': 'def g():\n'
                            '    return f() + 1\n'
                            '\n'
                            'def f():\n'
                            '    import lib\n'
                            '    return lib.K\n'
                            '\n'
                            'RESULT = g()\n',
                    'lib.py': 'K = 5\n',
                    'main.py': 'import a\nprint(a.RESULT)\n'},
 'l21_reads_module_attr': {'cfg.py': 'level = 1\n', 'lazy.py': 'import cfg\nDEFAULT = cfg.level\ndef get(): return DEFAULT\n', 'main.py': 'import cfg\ndef f():\n    import lazy\n    return lazy.get()\ncfg.level = 7\nprint(f())\n'},
 'l22_reads_from_import': {'cfg.py': 'level = 1\ndef bump():\n    global level\n    level += 1\n', 'lazy.py': 'from cfg import level\nDEFAULT = level * 10\n', 'main.py': 'import cfg\ndef f():\n    import lazy\n    return lazy.DEFAULT\ncfg.bump()\ncfg.bump()\nprint(f())\n'},
 'l23_decorator_effect': {'lazy.py': 'from reg import register\n@register\nclass A: pass\nX = [1,2,3]\n', 'main.py': 'import reg\ndef f():\n    import lazy\n    return lazy.X\nprint(reg.items)\nprint(f())\nprint(reg.items)\n', 'reg.py': 'items = []\ndef register(c):\n    items.append(c.__name__)\n    return c\n'},
 'l24_init_subclass': {'lazy.py': 'from reg import Base\nclass A(Base): pass\nX = 3\n', 'main.py': 'import reg\ndef f():\n    import lazy\n    return lazy.X\nprint(reg.items)\nprint(f())\nprint(reg.items)\n', 'reg.py': 'items = []\nclass Base:\n    def __init_subclass__(cls):\n        items.append(cls.__name__)\n'},
 'l25_default_reads_state': {'cfg.py': 'level = 1\n', 'lazy.py': 'import cfg\ndef g(a=cfg.level):\n    return a\n', 'main.py': 'import cfg\ndef f():\n    import lazy\n    return lazy.g()\ncfg.level = 9\nprint(f())\n'},
 'l26_pkg_attr_chain': {'lazy.py': 'import pk.c\nclass K:\n    v = pk.c.level\n', 'main.py': 'import pk.c\ndef f():\n    import lazy\n    return lazy.K.v\npk.c.level = 4\nprint(f())\n', 'pk/__init__.py': '', 'pk/c.py': 'level = 1\n'},
 'l27_pure_hoisted': {'cfg.py': 'class Base:\n    pass\ndef helper(x): return x + 1\nlevel = 1\n', 'lazy.py': 'import cfg\nfrom cfg import Base, helper\nfrom dataclasses import dataclass\nfrom enum import Enum, unique\n@dataclass(frozen=True)\nclass P:\n    x: int = 1\n@unique\nclass C(Enum):\n    A = 1\nclass D(Base): pass\nH = cfg.helper\ndef get(): return cfg.level + helper(P().x) + C.A.value\n', 'main.py': 'import cfg\ndef f():\n    import lazy\n    return lazy.get()\ncfg.level = 7\nprint(f())\n'},
 'l28_attr_decorator': {'lazy.py': 'import reg\n@reg.register\ndef h(): pass\nX = 1\n', 'main.py': 'import reg\ndef f():\n    import lazy\n    return lazy.X\nprint(f())\nprint(reg.items)\n', 'reg.py': 'items = []\ndef register(c):\n    items.append(1)\n    return c\n'},
 'l29_shadowed_dataclass': {'lazy.py': 'from reg import dataclass\n@dataclass\nclass A: pass\nX = 1\n', 'main.py': 'import reg\ndef f():\n    import lazy\n    return lazy.X\nprint(f())\nprint(reg.items)\n', 'reg.py': 'items = []\ndef dataclass(c):\n    items.append(1)\n    return c\n'}})


LAYOUTS.update({
 'l30_from_var_changes': {'cfg.py': 'level = 1\n', 'main.py': 'import cfg\ndef setl(v):\n    global x\n    cfg.level = v\ndef f():\n    import m\n    return m.get()\nsetl(4)\nprint(f())\n', 'm.py': 'from cfg import level\ndef get(): return level\n'},
 'l31_from_var_transitive': {'cfg.py': 'level = 1\n', 'main.py': 'import cfg\ndef f():\n    import m\n    return m.get()\ncfg.level = 7\nprint(f())\n', 'n.py': 'from cfg import level\ndef g(): return level\n', 'm.py': 'import n\ndef get(): return n.g()\n'},
 'l32_from_const_ok': {'cfg.py': 'level = 1\n', 'main.py': 'import cfg\ndef f():\n    import m\n    return m.get()\nprint(f())\n', 'm.py': 'from cfg import level\ndef get(): return level\n'},
 'l33_div_zero': {'bad.py': 'A = 0\nX = 1 // A\n', 'main.py': 'def f():\n    import bad\n    return bad.X\nprint("ok")\n'},
 'l34_index_error': {'bad.py': 'L = [1]\nX = L[3]\n', 'main.py': 'def f():\n    import bad\n    return bad.X\nprint("ok")\n'},
 'l35_name_error': {'bad.py': 'X = undefined_name\n', 'main.py': 'def f():\n    import bad\n    return bad.X\nprint("ok")\n'},
 'l36_type_error': {'bad.py': "X = 1 + 'a'\n", 'main.py': 'def f():\n    import bad\n    return bad.X\nprint("ok")\n'},
 'l37_int_bad': {'bad.py': "X = int('zz')\n", 'main.py': 'def f():\n    import bad\n    return bad.X\nprint("ok")\n'},
 'l38_unhashable_key': {'bad.py': 'K = [1]\nX = {K: 2}\n', 'main.py': 'def f():\n    import bad\n    return bad.X\nprint("ok")\n'},
 'l39_big_pow': {'bad.py': 'X = 2 ** 100000000\n', 'main.py': 'def f():\n    import bad\n    return bad.X\nprint("ok")\n'},
 'l40_bad_comprehension': {'bad.py': 'X = [y for y in 5]\n', 'main.py': 'def f():\n    import bad\n    return bad.X\nprint("ok")\n'},
 'l41_lambda_body_ok': {'bad.py': 'X = (lambda: 1/0)\nY = 2\n', 'main.py': 'def f():\n    import bad\n    return bad.Y\nprint("ok")\n'},
 'l42_short_circuit_ok': {'bad.py': 'X = 1 or 1/0\n', 'main.py': 'def f():\n    import bad\n    return bad.X\nprint("ok")\n'},
 'l43_pure_arith_enum_dataclass': {'bad.py': "from dataclasses import dataclass, field\nfrom enum import Enum, auto\nclass Color(Enum):\n    RED = auto()\n    GREEN = auto()\n@dataclass\nclass P:\n    x: int = 0\n    y: list[int] = field(default_factory=list)\n    def m(self) -> int:\n        return self.x\nX = Color.RED\nV = 'v'\n", 'main.py': 'def f():\n    import bad\n    return bad.V\nprint("ok")\n'},
 'l44_folded_comprehensions': {'bad.py': "MASK = (1 << 8) - 1\nNAMES = [n + 'x' for n in ['a','b']]\nSQ = [x*x for x in range(5) if x % 2 == 0]\nD = {k: len(k) for k in NAMES}\nX = MASK + D['ax']\n", 'main.py': 'def f():\n    import bad\n    return bad.X\nprint("ok")\n'},
 'l45_arith_fstring_slice': {'bad.py': "A = 3\nB = A * 2 + 1\nC = f'{A}-{B}'\nT = (A, B)\nS = T[0] + T[1]\nL = [1,2,3][1:]\nZ = 5 if A > 2 else 1/0\n", 'main.py': 'def f():\n    import bad\n    return bad.S\nprint("ok")\n'},
 'l46_key_error': {'bad.py': 'X = [i for i in range(3)]\nY = X[5]\n', 'main.py': 'def f():\n    import bad\n    return bad.Y\nprint("ok")\n'},
})


class MultiFileLayouts(ModulesBase):
    def check(self, name, irs=("1",)):
        return self.same_as_cpython(LAYOUTS[name], irs=irs)

    def test_full_project_with_package_subpackage_dataclass_enum_and_lazy_import(self):
        out = self.check("p_full", irs=("0", "1"))
        self.assertIn("119 113\n", out)           # app.models.late(): the function-level import of app.core.helpers
        self.assertIn("Color.RED Color.GREEN 2", out)

    def test_function_level_imports_in_the_entry_file_and_in_a_method(self):
        self.assertEqual(self.check("l1_entry"), "(6, 5, [1, 2]) (7, 8) 15 10\n")

    def test_function_level_import_that_breaks_a_package_cycle(self):
        self.assertEqual(self.check("l8_pkg"), "child 7 True\n")

    def test_function_level_import_in_two_functions_and_a_closure(self):
        self.assertEqual(self.check("l9_nested"), "lib.f lib.f\n")

    def test_function_level_import_of_a_dataclass_and_an_enum(self):
        self.assertEqual(self.check("l11_dc"), "P(x=1, k=3) Kind.B 5\n")

    def test_function_level_import_of_a_module_also_imported_at_the_top(self):
        # lib prints when it loads: the top-level import runs it once, the function only binds the name
        self.assertEqual(self.check("l14_eager"), "lib loaded\n4\n")

    def test_function_level_plain_import_of_a_submodule(self):
        self.assertEqual(self.check("l15_chain"), "9\n")

    def test_function_level_imports_of_values_used_through_arguments_lists_dicts_and_attributes(self):
        self.assertEqual(self.check("l16_values"), "[8, 10, 12, 22, [2, 4, 6], True, 'lib!', 0, 2] [2, 'lib'] True\n")

    def test_class_with_a_function_level_import_that_is_only_a_base(self):
        self.assertEqual(self.check("l18_init_class"), "5 5\n")

    def test_package_with_errors_decorator_free_classes_and_generators(self):
        self.assertIn("oos out of stock: bad bad", self.check("m1_misc"))

    def test_star_import_with_all(self):
        self.assertEqual(self.check("m2_star"), "1 11\n")

    def test_shared_module_state(self):
        self.assertEqual(self.check("m3_state"), "1\n105 True\n[('hi', 5), ('lo', 1), ('mid', 3)] [('debug', True)]\n3\n")

    def test_import_time_output_order(self):
        self.assertEqual(self.check("m4_importtime"),
                         "main start\na start\nb runs\na end 5\n1 5\n")

    def test_pure_hoisted_module_with_imports_dataclass_enum_and_base(self):
        self.assertEqual(self.check("l27_pure_hoisted"), "10\n")


class FunctionLevelRefusals(ModulesBase):
    def refuse(self, name, *needles):
        return self.refused(LAYOUTS[name], *needles)

    def test_module_with_an_effect_at_import_time(self):
        # CPython prints "hello from lib" when a() first runs, after "start"; the merged program cannot
        err = self.refuse("l2_impure", "main.py:2:5", "function-level `import lib`", "lib.py:1")
        self.assertNotIn("Traceback", err)

    def test_function_called_while_its_module_starts(self):
        self.refuse("l17_init_call", "a.py:5:10", "'f' is used while a is still starting")
        self.refuse("l20_via_helper", "a.py:8:10", "'g' is used while a is still starting")
        self.refuse("l19_init_class_call", "a.py:6:7", "'Base' is used while a is still starting")

    def test_effect_in_a_module_the_imported_module_imports(self):
        self.refuse("l13_trans", "main.py:2:5", "function-level `import x`", "y.py:1")

    def test_from_import_of_a_variable_that_changes(self):
        self.refuse("l3_mutable", "main.py:4:5", "`from st import n` inside a function", "st.n is a variable")

    def test_import_in_a_class_body(self):
        self.refuse("l4_class", "main.py:2:5", "below the top level", "inside a class body")

    def test_import_in_a_try_block(self):
        self.refuse("l5_try", "main.py:3:9", "below the top level", "try block")

    def test_import_binding_a_builtin_name(self):
        self.refuse("l6_builtin", "main.py:2:5", "builtin name 'max'")

    def test_function_level_name_read_as_a_module_attribute(self):
        # CPython: a.lib does not exist (AttributeError); it must not resolve to the module
        self.refuse("l7_attr", "main.py:4:11", "module 'a' has no top-level name 'lib'")

    def test_two_functions_import_different_things_under_one_name(self):
        self.refuse("l10_twoimports", "main.py:6:5", "'f' is bound to two different imports")

    def test_function_level_name_that_the_module_also_defines(self):
        self.refuse("l12_conflict", "a.py:1:1", "'lib' is imported and also assigned")

    # a hoisted module that reads another module's state, or runs a decorator or a class hook, when it starts
    # (CPython: when the function first runs; probes 1-3 of the review printed 1, 10 and [] before)
    def test_module_attribute_read_at_import_time(self):
        self.refuse("l21_reads_module_attr", "main.py:3:5", "function-level `import lazy`", "lazy.py:2")
        self.refuse("l26_pkg_attr_chain", "main.py:3:5", "function-level `import lazy`", "lazy.py:3")

    def test_from_imported_variable_read_at_import_time(self):
        self.refuse("l22_reads_from_import", "main.py:3:5", "function-level `import lazy`", "lazy.py:1")

    def test_default_argument_reading_state(self):
        self.refuse("l25_default_reads_state", "main.py:3:5", "lazy.py:2")

    def test_decorator_with_an_effect(self):
        self.refuse("l23_decorator_effect", "main.py:3:5", "function-level `import lazy`", "lazy.py:2")
        self.refuse("l28_attr_decorator", "main.py:3:5", "lazy.py:2")
        self.refuse("l29_shadowed_dataclass", "main.py:3:5", "lazy.py:2")

    def test_class_hook_run_by_a_base(self):
        self.refuse("l24_init_subclass", "main.py:3:5", "lazy.py:3")

class RaisingAndStaleModuleBodies(ModulesBase):
    """A module spliced in at its function-level import runs at the end of the importing module; CPython
    runs it when the function does. Bodies that can raise, and `from m import v` of a changing v, are refused."""

    def test_raising_expressions_are_refused_by_file_and_line(self):
        for name, line in (("l33_div_zero", 2), ("l34_index_error", 2), ("l35_name_error", 1), ("l36_type_error", 1),
                           ("l37_int_bad", 1), ("l38_unhashable_key", 2), ("l39_big_pow", 1),
                           ("l40_bad_comprehension", 1), ("l46_key_error", 2)):
            with self.subTest(name):
                self.refused(LAYOUTS[name], "main.py:2:5", "bad.py:%d" % line)

    def test_from_import_of_a_changing_variable_is_refused(self):
        self.refused(LAYOUTS["l30_from_var_changes"], "main.py:6:5", "m.py:1", "from cfg import level")
        self.refused(LAYOUTS["l31_from_var_transitive"], "main.py:3:5", "n.py:1", "from cfg import level")

    def test_from_import_of_an_unchanged_variable_still_builds(self):
        self.assertEqual(self.same_as_cpython(LAYOUTS["l32_from_const_ok"], irs=("1",)), "1\n")

    def test_expressions_that_cannot_raise_still_build(self):
        for name in ("l41_lambda_body_ok", "l42_short_circuit_ok", "l43_pure_arith_enum_dataclass",
                     "l44_folded_comprehensions", "l45_arith_fstring_slice"):
            with self.subTest(name):
                self.same_as_cpython(LAYOUTS[name], irs=("1",))


if __name__ == "__main__":
    unittest.main()
