"""Lazily started modules whose definitions need values the module computes when it runs.

A function-level import hoists the imported module's definitions. A default argument (or a class
base, decorator or class body) may read a module-level value that is computed by the module body:
the statements that compute it are placed with the definitions, before the definitions that need
them, while statements that print or otherwise do something still run when the import statement
runs. A value whose computation does something is still refused by name.
"""
import unittest

from test_ail_modules import ModulesBase


LAYOUTS = {
    'computed_helper': {
        'main.py': 'def run():\n'
                   '    import lib\n'
                   '    return lib.f(), lib.g(), lib.C.size\n'
                   '\n'
                   'print("main")\n'
                   'print(run())\n'
                   'print(run())\n',
        'lib.py': 'print("lib start")\n'
                  '\n'
                  'def make():\n'
                  '    return 3\n'
                  '\n'
                  'N = make()\n'
                  'SIZE = 1 << N\n'
                  '\n'
                  'def f(a=SIZE):\n'
                  '    return a\n'
                  '\n'
                  'def g(a=[N, SIZE]):\n'
                  '    return a\n'
                  '\n'
                  'class C:\n'
                  '    size = SIZE\n'
                  '\n'
                  'print("lib end")\n',
    },
    'computed_shapes': {
        'main.py': 'def run():\n'
                   '    import lib\n'
                   '    return lib.a(), lib.b(), lib.c(), lib.d(), lib.e()\n'
                   '\n'
                   'print(run())\n',
        'lib.py': 'print("shapes")\n'
                  'N = M = 3\n'
                  'N += 2\n'
                  'K: int = N * 2\n'
                  'if N > 0:\n'
                  '    Q = N - 1\n'
                  '\n'
                  'def a(x=N):\n'
                  '    return x\n'
                  '\n'
                  'def b(x=K):\n'
                  '    return x\n'
                  '\n'
                  'def c(x=Q):\n'
                  '    return x\n'
                  '\n'
                  'def d(x=M):\n'
                  '    return x\n'
                  '\n'
                  'def e(x=1 << Q):\n'
                  '    return x\n',
    },
    'computed_containers': {
        'main.py': 'def run():\n'
                   '    import lib\n'
                   '    return lib.f()\n'
                   '\n'
                   'print(run())\n',
        'lib.py': 'print("containers")\n'
                  'ITEMS = [1 << 2, 1 << 3, 1 << 4]\n'
                  'CONF = {"size": ITEMS[2] + 1}\n'
                  '\n'
                  'class Box:\n'
                  '    def __init__(self, size):\n'
                  '        self.size = size\n'
                  '\n'
                  'OBJ = Box(CONF["size"])\n'
                  '\n'
                  'def f(a=CONF["size"], b=ITEMS[1], c=OBJ.size):\n'
                  '    return a, b, c\n',
    },
    'computed_definitions': {
        'main.py': 'def run():\n'
                   '    import lib\n'
                   '    return lib.C().name(), lib.C.size, lib.h()\n'
                   '\n'
                   'print(run())\n',
        'lib.py': 'print("defs")\n'
                  'class Base:\n'
                  '    def name(self):\n'
                  '        return "base"\n'
                  '\n'
                  'N = 3\n'
                  'SIZE = 1 << N\n'
                  '\n'
                  'class C(Base):\n'
                  '    size = SIZE\n'
                  '\n'
                  'def h(a=SIZE):\n'
                  '    return ("h", a)\n',
    },
    'computed_order': {
        'main.py': 'def run():\n'
                   '    import lib\n'
                   '    return lib.f(), lib.SIZE, lib.LATER\n'
                   '\n'
                   'print("before")\n'
                   'print(run())\n'
                   'print("after")\n',
        'lib.py': 'print("lib start")\n'
                  'N = 3\n'
                  'SIZE = 1 << N\n'
                  '\n'
                  'def f(a=SIZE):\n'
                  '    return a\n'
                  '\n'
                  'N = 5\n'
                  'SIZE = 100\n'
                  'LATER = N\n'
                  'print("lib end")\n',
    },
    'computed_boundaries': {
        'main.py': 'def run():\n'
                   '    import lib\n'
                   '    return lib.zero(), lib.neg(), lib.empty(), lib.item()\n'
                   '\n'
                   'print(run())\n',
        'lib.py': 'print("bounds")\n'
                  'N = 0\n'
                  'Z = 1 << N\n'
                  'NEG = -5\n'
                  'EMPTY = []\n'
                  'ITEMS = (7,)\n'
                  '\n'
                  'def zero(x=Z):\n'
                  '    return x\n'
                  '\n'
                  'def neg(x=NEG):\n'
                  '    return x\n'
                  '\n'
                  'def empty(x=EMPTY):\n'
                  '    return len(x)\n'
                  '\n'
                  'def item(x=ITEMS[0]):\n'
                  '    return x\n',
    },
    'computed_package': {
        'main.py': 'def run():\n'
                   '    import pkg.leaf\n'
                   '    return pkg.leaf.f(), pkg.leaf.C.size\n'
                   '\n'
                   'print(run())\n',
        'pkg/__init__.py': 'print("pkg")\n',
        'pkg/leaf.py': 'print("leaf")\n'
                       'N = 4\n'
                       'SIZE = 1 << N\n'
                       '\n'
                       'def f(a=SIZE):\n'
                       '    return a\n'
                       '\n'
                       'class C:\n'
                       '    size = SIZE\n',
    },
}


class ComputedValues(ModulesBase):
    def check(self, name):
        return self.same_as_cpython(LAYOUTS[name])

    def test_default_reads_a_value_from_a_helper_call(self):
        self.assertEqual(self.check("computed_helper"),
                         'main\nlib start\nlib end\n(8, [3, 8], 8)\n(8, [3, 8], 8)\n')

    def test_multiple_annotated_augmented_and_conditional_bindings(self):
        self.assertEqual(self.check("computed_shapes"), 'shapes\n(5, 10, 4, 3, 16)\n')

    def test_defaults_read_dict_list_and_attribute_values(self):
        self.assertEqual(self.check("computed_containers"), 'containers\n(17, 8, 17)\n')

    def test_computed_base_and_a_class_body_value(self):
        self.assertEqual(self.check("computed_definitions"), "defs\n('base', 8, ('h', 8))\n")

    def test_effects_keep_cpython_order_and_defaults_capture_the_value_at_definition(self):
        self.assertEqual(self.check("computed_order"),
                         'before\nlib start\nlib end\n(8, 100, 5)\nafter\n')

    def test_zero_negative_empty_and_item_boundaries(self):
        self.assertEqual(self.check("computed_boundaries"), 'bounds\n(1, -5, 0, 7)\n')

    def test_computed_values_in_a_package_submodule(self):
        self.assertEqual(self.check("computed_package"), 'pkg\nleaf\n(16, 16)\n')


class EffectfulValues(ModulesBase):
    def test_a_value_whose_computation_prints_is_refused(self):
        self.refused({"lib.py": "print('lib start')\ndef make():\n    print('making')\n    return 3\n"
                                "N = make()\n\ndef f(x=N):\n    return x\n",
                      "main.py": "def g():\n    import lib\n    return lib.f()\n\nprint(g())\n"},
                     "function-level `import lib`", "write instead")

    def test_a_computation_that_would_raise_is_refused(self):
        self.refused({"lib.py": "print('lib start')\nITEMS = [1]\nN = ITEMS[5]\n\n\n"
                                "def f(x=N):\n    return x\n",
                      "main.py": "def g():\n    import lib\n    return lib.f()\n\nprint(g())\n"},
                     "function-level `import lib`", "write instead")

    def test_a_value_read_from_state_that_changes_is_refused(self):
        self.refused({"cfg.py": "level = 1\n",
                      "lib.py": "import cfg\ndef f(x=cfg.level):\n    return x\n",
                      "main.py": "import cfg\ndef g():\n    import lib\n    return lib.f()\n"
                                 "cfg.level = 9\nprint(g())\n"},
                     "function-level `import lib`", "write instead")


if __name__ == "__main__":
    unittest.main()
