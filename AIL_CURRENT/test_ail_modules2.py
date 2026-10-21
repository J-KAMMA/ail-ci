"""Package imports, compared with CPython (`python3 main.py` is the oracle).

`test_ail_multifile.py` covers the broad multi-file surface; this module pins the five package-import
rules one at a time, each with the layouts a program in the wild uses:

* relative imports inside a package: `from . import m`, `from .m import f`, `from .. import x`,
  `from ..m import f`, `from ... import x` from a package two levels down, a relative import in a
  sibling subpackage, `from . import *`, a name that is not a submodule but a variable of the parent
  package's `__init__.py`, and a namespace package portion (a directory without `__init__.py`).
  CPython's ImportErrors are refused by name with the user's file:line: a relative import in the entry
  file, in a top-level module, and one that climbs above the top-level package;
* `__all__` with `from m import *`: a literal list, a tuple, `+=` and `.append`, a re-exported name, a
  package whose `__all__` lists a submodule (imported or not yet imported), a package without `__all__`
  that binds a submodule it imports, a star import that copies values (so a later change to the source
  module's variable is not seen), and the refusals: an `__all__` the compiler cannot read, a member
  created only inside a function, and `import *` below module level (CPython raises SyntaxError);
* `import a.b as c`: the alias is the module, `c.__name__` is `a.b`, a write through the alias is seen by
  every other spelling, a deep `import pkg.mid.leaf as x`, an alias that shares its name with another
  module, a builtin name as the alias, and a namespace package;
* `if __name__ == "__main__":` in an imported module does not run (nor does its `else`-less body, nor an
  import inside it of a module that does not exist), the `else` branch does, the block does run in the
  entry file, and `__name__` is the module's dotted name inside an imported module;
* importing the same module twice through different names: `import m` + `import m as a`,
  `import pkg.mod` + `from pkg import mod` + `import pkg.mod as c`, a relative and an absolute spelling
  of the same submodule, two modules each importing it under their own alias, and `from m import v`
  keeping its own snapshot while the module's variable changes.
"""
import unittest

from test_ail_modules import ModulesBase


RELATIVE = {
    'rel_sibling_parent': {
        'pkg/__init__.py': 'V = "pkg"\nfrom . import util\n',
        'pkg/util.py': 'K = 3\ndef f(n):\n    return n + K\n',
        'pkg/sub/__init__.py': 'S = "sub"\n',
        'pkg/sub/deep.py': 'from .. import util\n'
                           'from ..util import f\n'
                           'from ..sub import S\n'
                           'from . import helper as h\n'
                           'print("deep", util.K, f(1), S, h.H)\n',
        'pkg/sub/helper.py': 'H = 42\n',
        'main.py': 'import pkg.sub.deep\nprint("main", pkg.util.f(2), pkg.V, pkg.sub.deep.util.K)\n',
    },
    'rel_star': {'pkg/__init__.py': '',
                 'pkg/a.py': '__all__ = ["p", "q"]\np = 1\nq = 2\nr = 3\n',
                 'pkg/b.py': 'from .a import *\nprint(p, q)\n',
                 'main.py': 'import pkg.b\nfrom pkg.a import p\nprint(p)\n'},
    'rel_star_parent': {'pkg/__init__.py': '__all__ = ["a", "f"]\na = 1\ndef f():\n    return 2\n',
                        'pkg/sub/__init__.py': '',
                        'pkg/sub/s.py': 'from .. import *\nprint(a, f())\n',
                        'main.py': 'import pkg.sub.s\n'},
    'rel_name_in_init': {'pkg/__init__.py': 'V = 11\ndef h():\n    return 12\n',
                         'pkg/s.py': 'from . import V, h\nprint(V, h())\n',
                         'main.py': 'import pkg.s\nprint(pkg.s.V)\n'},
    'rel_three_dots': {'pkg/__init__.py': '',
                       'pkg/util.py': 'K = 4\ndef f(n):\n    return n + K\n',
                       'pkg/a/__init__.py': '',
                       'pkg/a/b/__init__.py': '',
                       'pkg/a/b/c.py': 'from ... import util\n'
                                       'from ...util import f\n'
                                       'from . import mod2\n'
                                       'print("c", util.K, f(2), mod2.Q)\n',
                       'pkg/a/b/mod2.py': 'Q = "q"\n',
                       'main.py': 'import pkg.a.b.c\nprint(pkg.a.b.c.util.K)\n'},
    'rel_namespace_portion': {'pkg/__init__.py': 'U = "pkgU"\n',
                              'pkg/ns/sub.py': 'from .. import util, U\nfrom ..util import f\n'
                                               'print("sub", util.K, f(1), U)\n',
                              'pkg/util.py': 'K = 4\ndef f(n):\n    return n + K\n',
                              'main.py': 'import pkg.ns.sub\nprint(pkg.ns.sub.util.K)\n'},
    'rel_import_order': {'pkg/__init__.py': 'V = 1\nfrom . import m\nprint("init sees", m.M)\n',
                         'pkg/m.py': 'from . import V\nM = V + 1\nprint("m sees", V)\n',
                         'main.py': 'import pkg\nprint(pkg.m.M)\n'},
    'rel_entry': {'mod.py': 'K = 1\n', 'main.py': 'from . import mod\nprint(mod.K)\n'},
    'rel_root_module': {'mod.py': 'from . import x\n', 'main.py': 'import mod\n'},
    'rel_beyond_top': {'pkg/__init__.py': '', 'pkg/s.py': 'from .. import x\n', 'main.py': 'import pkg.s\n'},
}

ALL_STAR = {
    'all_list': {'a.py': '__all__ = ["x", "fa"]\nx = 1\ny = 2\ndef fa():\n    return x + 1\n',
                 'b.py': 'from a import *\nprint(x, fa())\n',
                 'main.py': 'import b\nprint(b.x, b.fa())\n'},
    'all_tuple': {'a.py': '__all__ = ("x", "fa")\nx = 1\ny = 2\ndef fa():\n    return x + 1\n',
                  'b.py': 'from a import *\nprint(x, fa())\n',
                  'main.py': 'from a import *\nprint(x, fa())\n'},
    'all_extend': {'a.py': '__all__ = ["x"]\nx = 1\ndef fa():\n    return x + 1\n__all__ += ["fa"]\n',
                   'main.py': 'from a import *\nprint(x, fa())\n'},
    'all_append': {'a.py': '__all__ = ["x"]\nx = 1\ndef fa():\n    return x + 1\n__all__.append("fa")\n',
                   'main.py': 'from a import *\nprint(x, fa())\n'},
    'all_reexport': {'b.py': 'bb = 10\ndef fb():\n    return 2\n',
                     'a.py': 'from b import *\n__all__ = ["bb", "fb", "own"]\nown = 5\n',
                     'main.py': 'from a import *\nprint(bb, fb(), own)\n'},
    'all_alias_member': {'b.py': 'bb = 10\ndef fb():\n    return 2\n',
                         'a.py': 'from b import bb as bee, fb\n__all__ = ["bee", "fb"]\n',
                         'main.py': 'from a import *\nprint(bee, fb())\n'},
    'star_chain': {'b.py': '__all__ = ["k"]\nk = 4\n', 'a.py': 'from b import *\n',
                   'main.py': 'from a import *\nprint(k)\n'},
    'all_pkg_sub': {'pkg/__init__.py': '__all__ = ["mod", "V"]\nV = 1\n',
                    'pkg/mod.py': 'M = 2\n',
                    'main.py': 'from pkg import *\nprint(V, mod.M)\n'},
    'all_pkg_unimported_sub': {'pkg/__init__.py': '__all__ = ["mod"]\n',
                               'pkg/mod.py': 'M = 3\nprint("mod body")\n',
                               'main.py': 'from pkg import *\nprint(mod.M)\n'},
    'star_pkg_no_all': {'pkg/__init__.py': 'from . import mod\n',
                        'pkg/mod.py': 'M = 2\n',
                        'main.py': 'from pkg import *\nprint(mod.M)\n'},
    'star_into_pkg_init': {'pkg/__init__.py': 'from .m import *\nprint("init", x)\n',
                           'pkg/m.py': '__all__ = ["x"]\nx = 3\n',
                           'pkg/n.py': 'from . import x\nprint("n", x)\n',
                           'main.py': 'import pkg.n\nprint(pkg.x)\n'},
    'star_values': {'a.py': '__all__ = ["LOG", "add", "x"]\nLOG = []\nx = 1\n'
                            'def add(v):\n    LOG.append(v)\n    return LOG\n'
                            'def sx():\n    global x\n    x = 2\n',
                    'main.py': 'from a import *\nimport a\nprint(add(1), x)\na.sx()\nprint(add(2), x, a.x)\n'},
    'star_global_only': {'m.py': 'def setx():\n    global X\n    X = 1\n',
                         'main.py': 'from m import *\nprint("after star")\n'},
    'star_in_function': {'a.py': 'x = 1\n',
                         'main.py': 'def f():\n    from a import *\n    return x\n\nprint(f())\n'},
    'star_in_class': {'a.py': 'x = 1\n', 'main.py': 'class K:\n    from a import *\n\nprint(K.x)\n'},
    'all_dynamic': {'a.py': 'names = ["x"]\n__all__ = names\nx = 1\n',
                    'main.py': 'from a import *\nprint(x)\n'},
    'all_mixed_dynamic': {'a.py': '__all__ = ["x"]\nx = 1\n__all__ = sorted(__all__)\n',
                          'main.py': 'from a import *\nprint(x)\n'},
    'star_then_rebind': {'a.py': '__all__ = ["x", "f"]\nx = 1\ndef f():\n    return x\n',
                         'main.py': 'from a import *\nx = 99\nprint(x, f())\n'},
}

DOTTED_ALIAS = {
    'alias_basic': {'pkg/__init__.py': 'print("pkg init")\n',
                    'pkg/b.py': 'print("b runs")\nK = 7\ndef get():\n    return K\n',
                    'main.py': 'import pkg.b as c\nprint(c.K, c.get(), c.__name__)\nc.K = 9\n'
                               'import pkg.b\nprint(pkg.b.K, pkg.b.get())\n'},
    'alias_deep': {'pkg/__init__.py': '',
                   'pkg/mid/__init__.py': '',
                   'pkg/mid/leaf.py': 'print("leaf runs")\nL = "leaf"\n',
                   'main.py': 'import pkg.mid.leaf as x\nimport pkg.mid\n'
                              'print(x.L, x.__name__, pkg.mid.leaf.L)\n'},
    'alias_shared_state': {'pkg/__init__.py': '',
                          'pkg/b.py': 'V = 1\n',
                           'pkg/c.py': 'import pkg.b as ab\ndef up():\n    ab.V += 1\n    return ab.V\n',
                           'main.py': 'import pkg.b as x\nimport pkg.c\nprint(x.V, pkg.b.V, pkg.c.ab.V)\n'
                                      'print(pkg.c.up(), x.V, pkg.b.V, pkg.c.ab.V)\n'},
    'alias_container_values': {'pkg/__init__.py': '',
                               'pkg/mod.py': 'K = 5\ndef f():\n    return 1\n',
                               'main.py': 'import pkg.mod as c\n'
                                          'def g(x=c.K):\n    return x\n'
                                          'l = [c.K, c.f]\nd = {"k": c.K}\n'
                                          'print(g(), l[0], l[1](), d["k"], c.f())\n'},
    'alias_namespace': {'pkg/__init__.py': '', 'pkg/ns/sub.py': 'S = 3\n',
                        'main.py': 'import pkg.ns as n\nimport pkg.ns.sub\nprint(n.__name__, n.sub.S)\n'},
    'alias_shadows_module_name': {'pkg/__init__.py': '', 'pkg/mod.py': 'M = 1\n', 'other.py': 'X = 2\n',
                                  'main.py': 'import pkg.mod as other\nfrom other import X\n'
                                             'print(other.M, X)\n'},
    'alias_builtin_name': {'pkg/__init__.py': '', 'pkg/mod.py': 'M = 1\n',
                           'main.py': 'import pkg.mod as list\nprint(list.M)\n'},
    'alias_pkg_sub_unimported': {'pkg/__init__.py': '', 'pkg/sub/__init__.py': '',
                                 'pkg/sub/m.py': 'def f():\n    return 8\n',
                                 'main.py': 'import pkg.sub as s\nprint(s.m.f())\n'},
}

MAIN_GUARD = {
    'guard_imported': {'lib.py': 'X = 1\nprint("lib body")\nif __name__ == "__main__":\n'
                                 '    print("lib main ran")\n    raise SystemExit\n',
                       'main.py': 'import lib\nprint(lib.X)\nif __name__ == "__main__":\n'
                                  '    print("entry main", __name__)\n'},
    'guard_else': {'lib.py': 'if __name__ != "__main__":\n    print("lib not main")\nelse:\n'
                             '    print("lib main")\n',
                   'main.py': 'import lib\nprint(__name__)\n'},
    'guard_else_defines': {'lib.py': 'if __name__ == "__main__":\n    def helper():\n        return 0\n'
                                     'else:\n    def helper():\n        return 1\nprint("lib", helper())\n',
                           'main.py': 'import lib\nprint(lib.helper())\n'},
    'guard_skips_missing_import': {'lib.py': 'if __name__ == "__main__":\n    import nosuchmod\n'
                                             'print("lib ok")\n',
                                   'other.py': 'Z = 3\n',
                                   'main.py': 'import lib\nprint("main ok")\n'},
    'guard_after_import': {'lib.py': 'import other\nif __name__ == "__main__":\n    print("lib main")\n'
                                     'print("lib body", other.Z)\n',
                           'other.py': 'Z = 3\n',
                           'main.py': 'import lib\nprint("main")\n'},
    'guard_pkg': {'pkg/__init__.py': 'print("pkg body")\nif __name__ == "__main__":\n'
                                     '    print("pkg main ran")\n',
                  'pkg/m.py': 'if __name__ == "__main__":\n    print("m main ran")\nprint("m body")\n',
                  'main.py': 'from pkg.m import *\nprint("main", __name__)\n'},
    'guard_name_dict': {'lib.py': 'INFO = {"name": __name__}\nif __name__ == "__main__":\n'
                                  '    INFO["main"] = True\nprint(INFO["name"], "main" in INFO)\n',
                        'main.py': 'import lib\nprint(lib.INFO)\n'},
}

SAME_MODULE = {
    'twice_aliases': {'m.py': 'print("m runs")\nV = 1\n',
                      'main.py': 'import m as a\nimport m as b\nfrom m import V\n'
                                 'print(a.V, b.V, V)\nb.V = 5\nprint(a.V)\n'},
    'alias_and_from_pkg': {'pkg/__init__.py': '', 'pkg/mod.py': 'print("mod runs")\nV = 1\n',
                           'main.py': 'import pkg.mod\nfrom pkg import mod\nprint(pkg.mod.V, mod.V)\n'
                                      'mod.V = 4\nprint(pkg.mod.V)\n'},
    'alias_plain_alias': {'pkg/__init__.py': '', 'pkg/mod.py': 'print("mod runs")\nV = 1\n',
                          'main.py': 'import pkg.mod\nimport pkg.mod as c\n'
                                     'print(pkg.mod.V, c.V, c.__name__)\nc.V = 3\nprint(pkg.mod.V)\n'},
    'relative_and_absolute': {'pkg/__init__.py': '',
                              'pkg/m.py': 'print("m runs once")\nK = 1\n',
                              'pkg/n.py': 'from . import m\nprint("n sees", m.K)\n',
                              'main.py': 'import pkg.m\nimport pkg.n\nfrom pkg import m as m2\nprint(m2.K)\n'},
    'two_modules_own_aliases': {'m.py': 'N = 0\ndef inc():\n    global N\n    N += 1\n    return N\n',
                                'a.py': 'import m as ma\ndef one():\n    return ma.inc()\n',
                                'b.py': 'import m as mb\ndef two():\n    return mb.N\n',
                                'main.py': 'import a\nimport b\nfrom m import N\n'
                                           'print(a.one(), b.two(), N)\nprint(a.one(), b.two(), N)\n'},
    'snapshot_and_module': {'pkg/__init__.py': '',
                            'pkg/m.py': 'V = 1\ndef bump():\n    global V\n    V += 1\n    return V\n',
                            'main.py': 'import pkg.m as c\nfrom pkg.m import V\nfrom pkg.m import bump\n'
                                       'print(c.V, V)\nbump()\nprint(c.V, V)\n'},
    'same_module_state_via_two_names': {'pkg/__init__.py': '',
                                        'pkg/mod.py': 'LOG = []\ndef add(v):\n    LOG.append(v)\n'
                                                      '    return len(LOG)\n',
                                        'main.py': 'import pkg.mod as a\nfrom pkg import mod as b\n'
                                                   'from pkg.mod import add, LOG\n'
                                                   'print(add(1), a.LOG, b.LOG, LOG)\n'
                                                   'print(add(2), a.LOG, b.LOG, LOG)\n'
                                                   'b.LOG.append(99)\nprint(a.LOG, LOG)\n'},
}


class RelativeImports(ModulesBase):
    """`from . import m`, `from .m import f`, `from .. import x`, `from ..m import f`; CPython's
    ImportErrors refused by name. The oracle is `python3 main.py` inside the temporary directory."""

    def test_sibling_parent_subpackage_and_subpackage_alias(self):
        self.same_as_cpython(RELATIVE['rel_sibling_parent'])

    def test_star_imports_that_are_relative(self):
        self.same_as_cpython(RELATIVE['rel_star'])
        self.same_as_cpython(RELATIVE['rel_star_parent'])

    def test_name_that_is_a_variable_of_the_parent_package(self):
        self.same_as_cpython(RELATIVE['rel_name_in_init'])

    def test_three_dots_from_two_levels_down(self):
        self.same_as_cpython(RELATIVE['rel_three_dots'])

    def test_namespace_package_portion(self):
        self.same_as_cpython(RELATIVE['rel_namespace_portion'])

    def test_parent_runs_before_child(self):
        self.same_as_cpython(RELATIVE['rel_import_order'])

    def test_relative_import_in_entry_file_is_refused_by_name(self):
        self.refused(RELATIVE['rel_entry'], "main.py:1:1", "relative import", "write instead")

    def test_relative_import_in_a_top_level_module_is_refused_by_name(self):
        self.refused(RELATIVE['rel_root_module'], "mod.py:1:1", "not inside a package", "write instead")

    def test_relative_import_beyond_the_top_level_package_is_refused_by_name(self):
        self.refused(RELATIVE['rel_beyond_top'], "pkg/s.py:1:1", "beyond the top-level package",
                     "write instead")


class AllAndStar(ModulesBase):
    """`from m import *` binds exactly what CPython binds: the names in `__all__` when it has one, the
    public names otherwise; the compiler reads a literal `__all__`, `+=`, `.append` and `.extend`."""

    def test_all_list_limits_the_star_import(self):
        self.same_as_cpython(ALL_STAR['all_list'])

    def test_all_tuple_and_extended_all(self):
        self.same_as_cpython(ALL_STAR['all_tuple'])
        self.same_as_cpython(ALL_STAR['all_extend'])
        self.same_as_cpython(ALL_STAR['all_append'])

    def test_all_names_that_are_re_exported(self):
        self.same_as_cpython(ALL_STAR['all_reexport'])
        self.same_as_cpython(ALL_STAR['all_alias_member'])
        self.same_as_cpython(ALL_STAR['star_chain'])

    def test_package_all_listing_a_submodule(self):
        self.same_as_cpython(ALL_STAR['all_pkg_sub'])
        # CPython imports the submodule for `from pkg import *` even when nothing imported it yet
        self.same_as_cpython(ALL_STAR['all_pkg_unimported_sub'])

    def test_package_without_all_that_binds_a_submodule(self):
        self.same_as_cpython(ALL_STAR['star_pkg_no_all'])
        self.same_as_cpython(ALL_STAR['star_into_pkg_init'])

    def test_star_import_copies_values(self):
        # a list is shared with the source module; a variable changed after the star import is not
        self.same_as_cpython(ALL_STAR['star_values'])

    def test_all_the_compiler_cannot_read_is_refused_by_name(self):
        self.refused(ALL_STAR['all_dynamic'], "main.py:1:1", "__all__", "write instead")
        self.refused(ALL_STAR['all_mixed_dynamic'], "main.py:1:1", "__all__", "write instead")

    def test_star_import_of_a_name_created_only_inside_a_function_is_refused(self):
        # CPython binds it only when that function has run by the time of the star import
        self.refused(ALL_STAR['star_global_only'], "main.py:1:1", "'X'", "write instead")

    def test_star_import_below_module_level_is_refused_as_cpython_s_syntax_error(self):
        self.refused(ALL_STAR['star_in_function'], "main.py:2:5", "SyntaxError",
                     "only allowed at module level")
        self.refused(ALL_STAR['star_in_class'], "main.py:2:5", "SyntaxError",
                     "only allowed at module level")

    def test_star_import_then_rebinding_the_name_is_refused_by_name(self):
        self.refused(ALL_STAR['star_then_rebind'], "main.py:2:1", "'x' is imported and also assigned",
                     "write instead")


class DottedImportAs(ModulesBase):
    """`import a.b as c` binds the module `a.b` and only that name (CPython binds no `a`), and every
    other spelling of the same module shares its state."""

    def test_alias_is_the_module(self):
        self.same_as_cpython(DOTTED_ALIAS['alias_basic'])

    def test_deep_alias(self):
        self.same_as_cpython(DOTTED_ALIAS['alias_deep'])

    def test_alias_shares_state_with_every_other_spelling(self):
        self.same_as_cpython(DOTTED_ALIAS['alias_shared_state'])

    def test_alias_reaches_the_code_through_arguments_lists_dicts_and_attributes(self):
        self.same_as_cpython(DOTTED_ALIAS['alias_container_values'])

    def test_alias_of_a_namespace_package(self):
        self.same_as_cpython(DOTTED_ALIAS['alias_namespace'])

    def test_alias_sharing_a_module_name_binds_the_named_module(self):
        # `import pkg.mod as other` binds the module; `from other import X` still reads other.py
        self.same_as_cpython(DOTTED_ALIAS['alias_shadows_module_name'])

    def test_builtin_name_as_the_alias(self):
        self.same_as_cpython(DOTTED_ALIAS['alias_builtin_name'])

    def test_submodule_that_nothing_imports_is_refused_by_name(self):
        # CPython raises AttributeError: the package has no such attribute until the import happens
        self.refused(DOTTED_ALIAS['alias_pkg_sub_unimported'], "main.py:2:7", "no attribute 'm'",
                     "write instead")


class MainGuard(ModulesBase):
    """`if __name__ == "__main__":` runs only in the entry file; in an imported module CPython skips the
    block (and runs its `else`), so an import inside it must not be loaded either."""

    def test_imported_guard_does_not_run(self):
        out = self.same_as_cpython(MAIN_GUARD['guard_imported'])
        self.assertEqual(out, "lib body\n1\nentry main __main__\n")

    def test_else_branch_of_an_imported_guard_runs(self):
        self.same_as_cpython(MAIN_GUARD['guard_else'])
        self.same_as_cpython(MAIN_GUARD['guard_else_defines'])

    def test_import_inside_an_imported_guard_is_not_loaded(self):
        self.same_as_cpython(MAIN_GUARD['guard_skips_missing_import'])
        self.same_as_cpython(MAIN_GUARD['guard_after_import'])

    def test_package_and_submodule_guards(self):
        self.same_as_cpython(MAIN_GUARD['guard_pkg'])

    def test_name_inside_an_imported_module(self):
        out = self.same_as_cpython(MAIN_GUARD['guard_name_dict'])
        self.assertEqual(out, "lib False\n{'name': 'lib'}\n")


class SameModuleTwice(ModulesBase):
    """One module object per dotted name: two spellings share its state and run its body once, while
    `from m import v` keeps its own copy."""

    def test_two_aliases_and_a_from_import(self):
        out = self.same_as_cpython(SAME_MODULE['twice_aliases'])
        self.assertEqual(out.count("m runs"), 1)

    def test_import_pkg_mod_from_pkg_import_mod(self):
        self.same_as_cpython(SAME_MODULE['alias_and_from_pkg'])
        self.same_as_cpython(SAME_MODULE['alias_plain_alias'])

    def test_relative_and_absolute_spellings(self):
        out = self.same_as_cpython(SAME_MODULE['relative_and_absolute'])
        self.assertEqual(out.count("m runs once"), 1)

    def test_modules_that_import_it_under_their_own_aliases(self):
        self.same_as_cpython(SAME_MODULE['two_modules_own_aliases'])

    def test_from_import_is_a_snapshot(self):
        self.same_as_cpython(SAME_MODULE['snapshot_and_module'])
        self.same_as_cpython(SAME_MODULE['same_module_state_via_two_names'])


if __name__ == "__main__":
    unittest.main()
