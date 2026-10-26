"""Modules, third round: the forms one program in the wild uses, compared with CPython.

`test_ail_multifile.py` covers the broad multi-file surface and `test_ail_modules2.py` the package
import rules. This module pins eight small programs:

* `from pkg import sub` where `sub` is a module, and `import pkg.sub as s`;
* a module-level constant of one module used as a default argument of a function defined in another
  module (read both as `from cfg import K` and as `cfg.K`), including the same on a package submodule;
* a class imported from another module and subclassed in a third;
* the import cycles CPython allows: a module that defines a name, imports a cycle partner, and reads
  the partner's name afterwards; and a cycle whose second module subclasses the first.

The gap this module closes: a function-level import of a module whose body is only definitions and
constants was refused when a default argument read another module's variable, even though that
variable never changes (`lazy.py:2: ... can raise (K)`). The read takes place when the definition
runs, and the merged program hoists the module only after its imported constants are settled, so the
two agree; it now builds. A variable that another module does change is still refused by name, with
the user's file:line (`LazyDefaultRefusals`).
"""
import unittest

from test_ail_modules import ModulesBase


LAYOUTS = {
    'from_pkg_sub': {
        'main.py': 'from pkg import sub\n'
                   'print(sub.V, sub.f(2), sub.Box(3).v, sub.__name__)\n',
        'pkg/__init__.py': 'NAME = "pkg"\n',
        'pkg/sub.py': 'V = 7\n'
                      '\n'
                      'class Box:\n'
                      '    def __init__(self, v):\n'
                      '        self.v = v\n'
                      '\n'
                      'def f(x):\n'
                      '    return x + V\n',
    },
    'import_pkg_sub_as': {
        'main.py': 'import pkg.sub as s\n'
                   'print(s.K, s.C(3).v, s.__name__)\n'
                   's.K = 5\n'
                   'import pkg.sub\n'
                   'print(s.get(), pkg.sub.K)\n',
        'pkg/__init__.py': 'ROOT = "pkg"\n',
        'pkg/sub.py': 'K = 4\n'
                      '\n'
                      'class C:\n'
                      '    def __init__(self, v):\n'
                      '        self.v = v * K\n'
                      '\n'
                      'def get():\n'
                      '    return K\n',
    },
    'default_in_other_module': {
        'main.py': 'from defaults import num, label, items, neg, both, attr\n'
                   'from cfg import ITEMS\n'
                   'ITEMS.append(1)\n'
                   'print(num(), label(2), items(), neg(), both(3), attr())\n',
        'cfg.py': 'BASE = 5\n'
                  'LABEL = "x"\n'
                  'ITEMS = []\n'
                  'NEG = -3\n',
        'defaults.py': 'import cfg\n'
                       'from cfg import BASE, LABEL, ITEMS, NEG\n'
                       '\n'
                       'def num(x=BASE):\n'
                       '    return x + 1\n'
                       '\n'
                       'def label(y, z=LABEL):\n'
                       '    return str(y) + z\n'
                       '\n'
                       'def items(x=ITEMS):\n'
                       '    return len(x)\n'
                       '\n'
                       'def neg(x=NEG):\n'
                       '    return abs(x)\n'
                       '\n'
                       'def both(x=BASE, y=LABEL):\n'
                       '    return str(x) + y\n'
                       '\n'
                       'def attr(x=cfg.BASE):\n'
                       '    return x * 2\n',
    },
    'subclass_imported': {
        'main.py': 'from base_mod import Base\n'
                   'from derived import Sub\n'
                   'import base_mod\n'
                   'print(Sub(2).who(), isinstance(Sub(1), Base), base_mod.Base(3).who())\n',
        'base_mod.py': 'class Base:\n'
                       '    def __init__(self, v):\n'
                       '        self.v = v\n'
                       '\n'
                       '    def who(self):\n'
                       '        return "base:" + str(self.v)\n',
        'derived.py': 'from base_mod import Base\n'
                      '\n'
                      'class Sub(Base):\n'
                      '    def __init__(self, v):\n'
                      '        super().__init__(v + 1)\n'
                      '\n'
                      '    def who(self):\n'
                      '        return "sub:" + Base.who(self)\n',
    },
    'cycle_from_defined': {
        'main.py': 'import a\n'
                   'print(a.A, a.b.B, a.b.double())\n',
        'a.py': 'X = 10\n'
                'import b\n'
                'A = X + b.B\n',
        'b.py': 'from a import X\n'
                'B = X * 2\n'
                '\n'
                'def double():\n'
                '    return X * 2\n',
    },
    'cycle_class_base': {
        'main.py': 'import a\n'
                   'print(a.A, a.b.S().m())\n',
        'a.py': 'class Base:\n'
                '    def m(self):\n'
                '        return 1\n'
                '\n'
                'import b\n'
                'A = b.S().m() + 1\n',
        'b.py': 'from a import Base\n'
                '\n'
                'class S(Base):\n'
                '    pass\n',
    },
    'lazy_default_const': {
        'main.py': 'def use():\n'
                   '    import lazy\n'
                   '    return lazy.num(), lazy.label(2), lazy.items(), lazy.neg()\n'
                   '\n'
                   'print(use())\n',
        'cfg.py': 'BASE = 5\n'
                  'LABEL = "x"\n'
                  'ITEMS = []\n'
                  'NEG = -3\n',
        'lazy.py': 'from cfg import BASE, LABEL, ITEMS, NEG\n'
                   '\n'
                   'def num(x=BASE):\n'
                   '    return x + 1\n'
                   '\n'
                   'def label(y, z=LABEL):\n'
                   '    return str(y) + z\n'
                   '\n'
                   'def items(x=ITEMS):\n'
                   '    return len(x)\n'
                   '\n'
                   'def neg(x=NEG):\n'
                   '    return abs(x)\n',
    },
    'lazy_default_attr': {
        'main.py': 'def use():\n'
                   '    import pkg.lazy\n'
                   '    return pkg.lazy.num(), pkg.lazy.label(2), pkg.lazy.re()\n'
                   '\n'
                   'print(use())\n',
        'pkg/__init__.py': '',
        'pkg/cfg.py': 'BASE = 5\n'
                      'LABEL = "x"\n',
        'pkg/mid.py': 'from .cfg import BASE as B2\n',
        'pkg/lazy.py': 'from . import cfg\n'
                       'from .mid import B2\n'
                       '\n'
                       'def num(x=cfg.BASE):\n'
                       '    return x + 1\n'
                       '\n'
                       'def label(y, z=cfg.LABEL):\n'
                       '    return str(y) + z\n'
                       '\n'
                       'def re(x=B2):\n'
                       '    return x * 2\n',
    },
}

REFUSALS = {
    'lazy_default_rebound': {
        'main.py': 'import cfg\n'
                   'cfg.K = 9\n'
                   'def use():\n'
                   '    import lazy\n'
                   '    return lazy.f()\n'
                   '\n'
                   'print(use())\n',
        'cfg.py': 'K = 5\n',
        'lazy.py': 'from cfg import K\n'
                   '\n'
                   'def f(x=K):\n'
                   '    return x\n',
    },
    'lazy_default_bumped': {
        'main.py': 'import cfg\n'
                   'cfg.bump()\n'
                   'def use():\n'
                   '    import lazy\n'
                   '    return lazy.f()\n'
                   '\n'
                   'print(use())\n',
        'cfg.py': 'K = 5\n'
                  '\n'
                  'def bump():\n'
                  '    global K\n'
                  '    K += 1\n',
        'lazy.py': 'import cfg\n'
                   '\n'
                   'def f(x=cfg.K):\n'
                   '    return x\n',
    },
}


class MultiFileForms(ModulesBase):
    def check(self, name, irs=("0", "1")):
        return self.same_as_cpython(LAYOUTS[name], irs=irs)

    def test_from_package_imports_the_submodule(self):
        self.assertEqual(self.check("from_pkg_sub"), "7 9 3 pkg.sub\n")

    def test_dotted_import_alias_and_shared_state(self):
        self.assertEqual(self.check("import_pkg_sub_as"), "4 12 pkg.sub\n5 5\n")

    def test_module_constants_used_as_default_arguments(self):
        self.assertEqual(self.check("default_in_other_module"), "6 2x 1 3 3x 10\n")

    def test_class_imported_and_subclassed_in_a_third_module(self):
        self.assertEqual(self.check("subclass_imported"), "sub:base:3 True base:3\n")

    def test_cycle_that_reads_a_name_defined_before_the_import(self):
        self.assertEqual(self.check("cycle_from_defined"), "30 20 20\n")

    def test_cycle_whose_second_module_subclasses_the_first(self):
        self.assertEqual(self.check("cycle_class_base"), "2 1\n")

    def test_lazy_module_defaults_that_read_another_module_s_constants(self):
        self.assertEqual(self.check("lazy_default_const"), "(6, '2x', 0, 3)\n")

    def test_lazy_package_module_defaults_through_attributes_and_a_re_export(self):
        self.assertEqual(self.check("lazy_default_attr"), "(6, '2x', 10)\n")


class LazyDefaultRefusals(ModulesBase):
    def test_default_reading_a_rebound_constant_is_refused_by_name(self):
        self.refused(REFUSALS["lazy_default_rebound"], "main.py:4:5", "function-level `import lazy`",
                     "lazy.py:1")
        self.refused(REFUSALS["lazy_default_bumped"], "main.py:4:5", "function-level `import lazy`",
                     "lazy.py:3")


if __name__ == "__main__":
    unittest.main()
