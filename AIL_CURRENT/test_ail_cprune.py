"""cprune: the static C a unit never names is not handed to gcc, and nothing else changes.

Unit cases feed `cprune.prune` small C texts: what it removes (unnamed static functions, prototypes and
variables, transitively), what it must keep (a name used anywhere outside a comment, a macro body once
the macro is used, pasted names, pinned attributes, items it cannot cut cleanly), and that every line
keeps its number. Each pruned text is also compiled and run against the unpruned one. The build cases
compile programs on both paths with and without the pass (AIL_NO_PRUNE=1): the binaries must be
byte-identical and the generated C smaller.
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'python' / 'pkg-v12'))
import cprune  # noqa: E402

CLI = str(ROOT / 'ail_chatgpt.py')
CC = os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc')

BASE = r'''#include <stdio.h>
static int helper(int x);
static int unused_a(int x) { return x + 1; }
static int unused_b(int x) { return unused_a(x) * 2; }
static const int table[] = { 1, 2, 3 };
static const int dead_table[] = { 4, 5, 6 };
static int helper(int x) { return table[x % 3] + x; }
int main(void) { printf("%d\n", helper(4)); return 0; }
'''


def run_c(text, tmp, name):
    src = Path(tmp) / (name + '.c')
    exe = Path(tmp) / name
    src.write_text(text)
    r = subprocess.run([CC, '-O2', '-w', '-o', str(exe), str(src)], capture_output=True, text=True)
    if r.returncode:
        raise AssertionError('cc rejected %s:\n%s\n%s' % (name, r.stderr[-2000:], text))
    p = subprocess.run([str(exe)], capture_output=True, text=True, timeout=20)
    return p.returncode, p.stdout


class Prune(unittest.TestCase):
    def check(self, text):
        """prune `text`; the result keeps every line number and runs exactly like the original"""
        out = cprune.prune(text)
        self.assertEqual(out.count('\n'), text.count('\n'))
        if CC:
            with tempfile.TemporaryDirectory() as tmp:
                self.assertEqual(run_c(out, tmp, 'pruned'), run_c(text, tmp, 'whole'))
        return out

    def test_unused_static_items_go_transitively(self):
        out = self.check(BASE)
        for gone in ('unused_a', 'unused_b', 'dead_table'):
            self.assertNotIn(gone, out)
        for kept in ('static int helper(int x);', 'static int helper(int x) {', 'table[] = { 1, 2, 3 }', 'int main'):
            self.assertIn(kept, out)

    def test_lines_keep_their_numbers(self):
        out = cprune.prune(BASE)
        self.assertEqual(out.splitlines()[6], BASE.splitlines()[6])
        self.assertEqual(out.splitlines()[2], '')

    def test_off_switch(self):
        os.environ['AIL_NO_PRUNE'] = '1'
        try:
            self.assertEqual(cprune.prune(BASE), BASE)
        finally:
            del os.environ['AIL_NO_PRUNE']

    def test_name_in_a_comment_does_not_keep(self):
        out = self.check(BASE.replace('int main', '/* unused_a */ int main'))
        self.assertNotIn('static int unused_a', out)

    def test_name_in_a_string_keeps(self):
        out = self.check(BASE.replace('int main(void) {', 'int main(void) { puts("unused_b");'))
        self.assertIn('static int unused_b', out)
        self.assertIn('static int unused_a', out)

    def test_macro_body_counts_when_the_macro_is_used(self):
        text = BASE.replace('int main', '#define CALL_A unused_a\nint main')
        self.assertNotIn('static int unused_a', self.check(text))
        used = text.replace('helper(4)', 'helper(4) + CALL_A(1)')
        self.assertIn('static int unused_a', self.check(used))
        self.assertIn('#define CALL_A unused_a', cprune.prune(text))

    def test_pasted_names(self):
        text = BASE.replace('int main', '#define MK(n) n##_a(1)\nint main').replace('helper(4)', 'helper(4) + MK(unused)')
        self.assertIn('static int unused_a', self.check(text))
        # a paste of parameters only builds names that appear nowhere whole: the text stays as it is
        text = BASE.replace('int main', '#define CAT(a, b) a##b\nint main').replace('helper(4)', 'helper(4) + CAT(unused, _a)(1)')
        self.assertEqual(self.check(text), text)

    def test_pinned_attributes_keep(self):
        text = BASE.replace('static int unused_a(int x)', 'static __attribute__((used)) int unused_a(int x)')
        self.assertIn('unused_a(int x)', self.check(text))
        text = BASE.replace('int main', 'static void __attribute__((constructor)) init(void) { puts("init"); }\nint main')
        self.assertIn('init(void)', self.check(text))
        text = BASE.replace('int main', '#define AIL_INIT __attribute__((constructor))\nstatic AIL_INIT void init(void) { puts("init"); }\nint main')
        self.assertIn('init(void)', self.check(text))

    def test_define_inside_a_function(self):
        leak = BASE.replace('static int unused_a(int x) { return x + 1; }',
                            'static int unused_a(int x) {\n#define LATER 7\n    return x + 1;\n}')
        self.assertIn('static int unused_a', self.check(leak.replace('helper(4)', 'helper(4) + LATER')))
        local = BASE.replace('static int unused_a(int x) { return x + 1; }',
                             'static int unused_a(int x) {\n#define ONE 1\n    return x + ONE;\n#undef ONE\n}')
        self.assertNotIn('static int unused_a', self.check(local))

    def test_split_conditional_header(self):
        text = BASE.replace('static int unused_a(int x) { return x + 1; }',
                            '#ifdef NEVER\nstatic int unused_a(long x) {\n#else\nstatic int unused_a(int x) {\n#endif\n    return x + 1; }')
        self.assertIn('return x + 1; }', self.check(text))

    def test_comment_opened_on_a_directive_line(self):
        text = BASE.replace('static int unused_a', '#define K 1 /* a comment that\n   goes on */ static int unused_a')
        out = self.check(text)
        self.assertNotIn('static int unused_a', out)
        self.assertIn('goes on */', out)

    def test_items_it_cannot_cut_alone(self):
        text = BASE.replace('static const int dead_table[] = { 4, 5, 6 };', 'static int dead_x = 1, live_y = 2;')
        self.assertIn('live_y', self.check(text.replace('helper(4)', 'helper(4) + live_y')))
        text = BASE.replace('static const int dead_table[] = { 4, 5, 6 };', 'static struct pt { int a; } dead_pt;')
        self.assertIn('struct pt', self.check(text))

    def test_definition_generator_macro(self):
        text = BASE.replace('int main', '#define GEN(n) static int n##_gen(void) { return 5; }\nGEN(five)\n'
                            'static int after_macro(void) { return 6; }\nint main').replace('helper(4)', 'helper(4) + five_gen()')
        out = self.check(text)
        self.assertIn('GEN(five)', out)
        self.assertNotIn('after_macro', out)

    def test_unbalanced_text_is_returned_unchanged(self):
        text = '#ifdef __cplusplus\nextern "C" {\n#endif\n' + BASE
        self.assertEqual(cprune.prune(text), text)


PROGRAMS = {
    'typed': 'def main() -> None:\n    total = 0\n    for i in range(10):\n        total += i * i\n    print(total)\n\nmain()\n',
    'general': ('def main():\n    d = {}\n    for w in "b a c a b a".split():\n        d[w] = d.get(w, 0) + 1\n'
                '    print(sorted(d.items(), key=lambda kv: (-kv[1], kv[0])), {1, 2} | {3})\n\nmain()\n'),
}


@unittest.skipUnless(CC, 'needs a C compiler')
class Build(unittest.TestCase):
    def build(self, tmp, name, source, **env):
        prog = Path(tmp) / (name + '.py')
        prog.write_text(source)
        out = Path(tmp) / (name + '_' + '_'.join(sorted(env)) + 'exe')
        debug = Path(tmp) / (out.name + '_dd')
        r = subprocess.run([sys.executable, CLI, 'compile', str(prog), '-o', str(out), '--debug-dir', str(debug)],
                           capture_output=True, text=True, env={**os.environ, 'AIL_NO_CACHE': '1', **env})
        self.assertEqual(r.returncode, 0, r.stderr)
        c = max(debug.glob('*.c'), key=lambda p: p.stat().st_size)
        run = subprocess.run([str(out)], capture_output=True, text=True, timeout=30)
        return hashlib.sha256(out.read_bytes()).hexdigest(), c.stat().st_size, run.stdout

    def test_same_binary_smaller_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, source in PROGRAMS.items():
                with self.subTest(name):
                    whole = self.build(tmp, name, source, AIL_NO_PRUNE='1')
                    pruned = self.build(tmp, name, source)
                    self.assertEqual(pruned[0], whole[0])
                    self.assertEqual(pruned[2], whole[2])
                    self.assertLess(pruned[1], whole[1] * 0.8)
                    expected = subprocess.run([sys.executable, '-c', source], capture_output=True, text=True).stdout
                    self.assertEqual(pruned[2], expected)


if __name__ == '__main__':
    unittest.main()
