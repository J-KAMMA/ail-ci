#!/usr/bin/env python3
"""Round-trip tests for lab/vibe2/translate.py.

Every construct in NEW_SURFACE.md is written once, translated, and run under CPython 3.12; the
stdout and exit status must equal the expected values. One combined program is also built with
AIL and must print the same bytes, so the translated text really is AIL Python.

    python3 lab/vibe2/test_translate.py          # CPython round-trips + one AIL build
    python3 lab/vibe2/test_translate.py --quick  # CPython round-trips only
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AIL = REPO / 'AIL_CURRENT' / 'ail_chatgpt.py'
sys.path.insert(0, str(HERE))

from translate import TranslateError, translate, map_line  # noqa: E402


def run(src, stdin=b'', args=(), cwd=None):
    tr = translate(src)
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / 'main.py'
        p.write_text(tr['code'])
        proc = subprocess.run([sys.executable, '-B', str(p), *args], input=stdin,
                              capture_output=True, timeout=90, cwd=cwd or d)
        return proc, tr


class RoundTrip(unittest.TestCase):
    def check(self, src, expected, stdin=b'', args=(), code=0):
        proc, _ = run(src, stdin, args)
        self.assertEqual(proc.stdout.decode(), expected, proc.stderr.decode())
        self.assertEqual(proc.returncode, code)

    def test_let_var(self):
        self.check('''\
fn main() -> int:
  let a: int = 2
  var b: int = 3
  b = b * a
  write(str(a + b) + "\\n")
  return 0

write(str(main()) + "\\n")
''', '8\n0\n')

    def test_if_elif_else(self):
        self.check('''\
fn sign(x: int) -> str:
  if x > 0:
    return "pos"
  elif x < 0:
    return "neg"
  else:
    return "zero"

write(sign(-2) + sign(0) + sign(5) + "\\n")
''', 'negzeropos\n')

    def test_while_break_continue(self):
        self.check('''\
var i: int = 0
var n: int = 0
while i < 10:
  i = i + 1
  if i % 2 == 0:
    continue
  if i > 7:
    break
  n = n + i
write(str(n) + "\\n")
''', '16\n')

    def test_for_and_containers(self):
        self.check('''\
let xs: list[int] = [3, 1, 2]
let d: dict[str, int] = {"a": 1, "b": 2}
let s: set[int] = set()
let t: tuple[int, str] = (7, "x")
for x: int in xs:
  s.add(x)
var total: int = 0
for k: str in d:
  total = total + d[k]
write(str(len(s)) + " " + str(total) + " " + str(t[0]) + t[1] + "\\n")
''', '3 3 7x\n')

    def test_match_literals(self):
        self.check('''\
fn name(x: int) -> str:
  match x:
    case 0:
      return "zero"
    case -1:
      return "minus"
    case _:
      return "other"

write(name(0) + name(-1) + name(9) + "\\n")
''', 'zerominusother\n')

    def test_match_result(self):
        self.check('''\
fn half(x: int) -> Result[int]:
  if x % 2 != 0:
    return Err("odd")
  return Ok(x // 2)

fn show(r: Result[int]) -> str:
  match r:
    case Ok(v):
      return "ok " + str(v)
    case Err(e):
      return "err " + e

write(show(half(8)) + " " + show(half(3)) + "\\n")
''', 'ok 4 err odd\n')

    def test_nested_match(self):
        self.check('''\
fn f(a: int, b: int) -> str:
  match a:
    case 0:
      match b:
        case 0:
          return "00"
        case _:
          return "0x"
    case _:
      return "xx"

write(f(0, 0) + f(0, 1) + f(1, 5) + "\\n")
''', '000xxx\n')

    def test_builtins(self):
        src = '''\
let a: int = div_ceil(7, 2)
let b: int = floor(sqrt(10.0))
let c: int = ceil(1.2)
write(str(a) + " " + str(b) + " " + str(c) + "\\n")
write(str(arg_count()) + " " + arg(0) + "\\n")
write(read_line())
write(read_stdin())
exit(3)
'''
        proc, _ = run(src, stdin=b'first\nrest\n', args=('A',))
        self.assertEqual(proc.stdout.decode(), '4 3 2\n1 A\nfirst\nrest\n')
        self.assertEqual(proc.returncode, 3)

    def test_write_bytes(self):
        proc, _ = run('write_bytes(b"bin\\n")')
        self.assertEqual(proc.stdout, b'bin\n')
        self.assertEqual(proc.returncode, 0)

    def test_read_file(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'f.bin').write_bytes(b'abc\x00')
            src = '''\
let name: str = arg(0)
let raw: bytes = read_file_bytes(name)
write_bytes(raw[0:2])
'''
            proc, _ = run(src, cwd=d, args=(str(Path(d, 'f.bin')),))
            self.assertEqual(proc.stdout, b'ab')

    def test_line_map(self):
        src = 'let x: int = 1\nwrite(str(print(x)))\n'
        with self.assertRaises(TranslateError) as cm:
            translate(src)
        self.assertEqual(cm.exception.line, 2)
        tr = translate('let x: int = 1\nwrite(str(x))\n')
        # output line for the write statement maps back to source line 2
        written = [i + 1 for i, ai in enumerate(tr['line_map']) if ai == 2]
        self.assertTrue(written)
        self.assertEqual(map_line(tr['line_map'], written[0]), 2)

    def test_div_ceil_signs(self):
        self.check('''\
let a: int = div_ceil(5, -2)
let b: int = div_ceil(-5, 2)
let c: int = div_ceil(-5, -2)
let d: int = div_ceil(5, 2)
write(str(a) + " " + str(b) + " " + str(c) + " " + str(d) + "\\n")
''', '-2 -2 3 3\n')

    def test_let_reassigned_after_fn(self):
        with self.assertRaises(TranslateError) as cm:
            translate('''\
let g: int = 1
fn f() -> int:
  return g
g = 2
write(str(f() + g) + "\\n")
''')
        self.assertIn('let binding', cm.exception.message)
        self.assertNotIn('declare the binding', cm.exception.message)

    def test_surface_errors(self):
        for src, needle in [
            ('x = 1\n', 'let'),
            ('let x: int = 1\nx = 2\n', 'let binding'),
            ('print("hi")\n', 'not in the surface'),
            ('import os\n', 'not in the surface'),
            ('class C:\n  pass\n', 'not in the surface'),
            ('let x: Optional[int] = 1\n', 'not in the surface'),
            ('let s: str = rf"x{1}"\n', 'f-strings'),
            ('let s: str = fr"x{1}"\n', 'f-strings'),
            ('let s: str = Rf"x"\n', 'f-strings'),
            ('fn outer() -> int:\n  fn inner() -> int:\n    return 1\n  return inner()\n',
             'nested function'),
            ('match 3:\n  case 0:\n    write("a")\n', 'not exhaustive'),
            ('match 3:\n  case 0:\n    write("a")\n  case 0:\n    write("b")\n  case _:\n    write("c")\n',
             'duplicate'),
            ('match Ok(1):\n  case Ok(v):\n    write(str(v))\n  case Ok(w):\n    write(str(w))\n',
             'duplicate'),
            ('for a, b in [(1, 2)]:\n  write(str(a))\n', 'for target'),
            ('match x:\n  case 1:\n    write("a")\n  case _:\n    write("b")\n  case 2:\n    write("c")\n',
             'case after'),
            ('def h(a):\n  return a\n', 'not in the surface'),
            ('let y: int = (x := 1)\n', '`:=`'),
            ('let xs: list[int] = [x * 2 for x in [1, 2]]\n', 'comprehension'),
            ('match 0.0:\n  case 0:\n    write("a")\n  case 0.0:\n    write("b")\n  case _:\n    write("c")\n',
             'duplicate'),
            ('match 1:\n  case True:\n    write("a")\n  case 1:\n    write("b")\n  case _:\n    write("c")\n',
             'duplicate'),
        ]:
            with self.assertRaises(TranslateError, msg=src) as cm:
                translate(src)
            self.assertIn(needle, cm.exception.message, msg=src)

    @unittest.skipIf('--quick' in sys.argv, 'AIL build skipped')
    def test_ail_builds_and_agrees(self):
        src = '''\
fn classify(n: int) -> Result[str]:
  if n < 0:
    return Err("neg")
  match n:
    case 0:
      return Ok("zero")
    case _:
      return Ok("pos")

var total: int = 0
for x: int in [0, 2, 5]:
  match classify(x):
    case Ok(label):
      write(label + " ")
    case Err(e):
      write(e + " ")
  total = total + x
write(str(total) + "\\n")
write(str(div_ceil(5, -2)) + " " + str(div_ceil(-5, 2)) + "\\n")
'''
        tr = translate(src)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'main.py'
            p.write_text(tr['code'])
            py = subprocess.run([sys.executable, '-B', str(p)], capture_output=True, timeout=90)
            exe = Path(d) / 'prog'
            env = dict(os.environ, AIL_NO_CACHE='1')
            b = subprocess.run([sys.executable, '-B', str(AIL), 'compile', str(p), '--syntax',
                                'python', '-o', str(exe)], capture_output=True, timeout=300, env=env)
            self.assertEqual(b.returncode, 0, b.stderr.decode()[-1500:])
            runexe = subprocess.run([str(exe)], capture_output=True, timeout=90)
        self.assertEqual(py.returncode, runexe.returncode)
        self.assertEqual(py.stdout, runexe.stdout)


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]], verbosity=2)
