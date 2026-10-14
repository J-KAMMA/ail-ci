"""User function names never collide with identifiers declared by the C headers or the runtime."""
import os
import shutil
import unittest

import test_ail_c_objects as support

# libc / POSIX / math / socket names the generated program's headers declare (abs, exit, open,
# pow, round also shadow a built-in: see test_ail_builtin_shadowing).
NAMES = ('abs rename remove exit div time read write open close free malloc printf puts index random '
         'signal select kill sleep link unlink pipe dup log exp pow floor round sin y0 j0 gamma '
         'stat access send recv truncate fsync labs rand getenv bind poll').split()


def program():
    lines = []
    for number, name in enumerate(NAMES, 1):
        lines.append('fn %s(x:int)->int { return x*%d; }' % (name, number))
    body = ' + '.join('%s(%d)' % (name, 1 + number % 3) for number, name in enumerate(NAMES, 1))
    lines.append('fn main()->int { print(%s); return 0; }' % body)
    expected = sum(number * (1 + number % 3) for number in range(1, len(NAMES) + 1))
    return '\n'.join(lines), '%d\n' % expected


@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'), 'installed C compiler required')
class LibcNameTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    command = support.CObjectTests.command
    write = support.CObjectTests.write
    ail_build = support.CObjectTests.ail_build
    check_run = support.CObjectTests.check_run

    def test_libc_named_functions_compile_and_run(self):
        source, expected = program()
        self.check_run(self.ail_build('libc_names', source), expected)

    def test_libc_named_function_in_library_and_recursion(self):
        source = '''fn rename(n:int)->int {if n<=0 {return 0;}return n+rename(n-1);}
fn remove(n:int)->int {return rename(n)*2;}
fn main()->int {let cb:Callable[[int],int]=remove;print(rename(4),cb(3));return 0;}'''
        self.check_run(self.ail_build('libc_recursion', source), '10 12\n')

    def test_methods_structs_and_consts_with_libc_names(self):
        source = '''const remove = 5;
struct stat { rename:int; }
impl stat { fn unlink(self, d:int)->int { return self.rename + d; } fn read(self)->int { return self.rename; } }
fn main()->int { let s = stat(3); print(s.unlink(remove) + s.read()); return 0; }'''
        self.check_run(self.ail_build('libc_members', source), '11\n')

    def test_mangled_name_never_meets_a_user_py_name(self):
        source = '''fn rename(a:int)->int { return a+1; }
fn py_rename(a:int)->int { return a+100; }
fn main()->int { print(rename(2), py_rename(2)); return 0; }'''
        self.check_run(self.ail_build('libc_py_clash', source), '3 102\n')

    def test_mangler_only_touches_header_and_runtime_names(self):
        import sys
        sys.path.insert(0, str(support.ROOT / 'python/pkg-v12'))
        try:
            from pyfunc import _mangle_csym
        finally:
            sys.path.pop(0)
        for name in NAMES + ['abs', 'ck_add', 'ail_x', '__x', '_Bad', 'stdin', 'errno', 'EOF', 'linux']:
            self.assertEqual(_mangle_csym(name), 'py_' + name, name)
        for name in ['count', 'helper', '_private', 'search', 'swap', 'hpush', 'count_pat', 'main_loop']:
            self.assertEqual(_mangle_csym(name), name, name)


if __name__ == '__main__':
    unittest.main()
