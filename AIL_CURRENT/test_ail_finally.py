"""Whole-program CPython oracles for native finally exits and ownership."""
import contextlib
import ast
import io
import os
from pathlib import Path
import shutil
import struct
import subprocess
import unittest

import test_ail_c_objects as support
import test_ail_exception_resources as resources


TRACE = '''
def mark(n: int) -> int:
    print(n)
    return n

def exercise(n: int) -> int:
    try:
        mark(10)
        if n == 1:
            raise ValueError()
        if n == 2:
            raise IndexError()
        mark(11)
    except ValueError:
        mark(20)
        if n == 1:
            raise KeyError()
    else:
        mark(30)
        if n == 3:
            raise RuntimeError()
    finally:
        mark(40)
    return 50

def exits(n: int) -> int:
    try:
        try:
            return mark(60)
        finally:
            mark(61)
            if n == 1:
                return mark(62)
            if n == 2:
                raise ValueError()
    finally:
        mark(63)

def loops(n: int) -> int:
    total = 0
    for i in range(n):
        try:
            for j in range(3):
                mark(70+j)
                if j == 1:
                    break
            mark(73)
            if i == 0:
                continue
            if i == 1:
                break
        finally:
            mark(74)
            total += 1
    for i in range(3):
        try:
            if i == 0:
                break
            return mark(80)
        finally:
            mark(81+i)
            if i == 0:
                continue
            break
    for i in range(3):
        try:
            return mark(90)
        finally:
            mark(91)
            break
    return total

def suppressed(n: int) -> int:
    try:
        raise IndexError()
    finally:
        if n == 0:
            return mark(100)
        raise ValueError()

def run(n: int) -> int:
    for i in range(4):
        try:
            print(exercise(i))
        except IndexError:
            mark(101)
        except KeyError:
            mark(102)
        except RuntimeError:
            mark(103)
    for i in range(3):
        try:
            print(exits(i))
        except ValueError:
            mark(104)
    print(loops(n))
    for i in range(2):
        try:
            print(suppressed(i))
        except ValueError:
            mark(105)
    return 0
'''

BRACE_LIBRARY = '''fn mark(n:int)->int {print(n);return n;}
fn result(n:int)->int {
 try {try {return mark(n);} finally {print(11);}}
 finally {print(12);if n==1 {return 7;}}
}
'''
BRACE_MAIN = '''fn main()->int {print(result(0));print(result(1));return 0;}'''


def brace_source(source):
    """Render this fixture's Python AST into the public brace syntax."""
    def block(header, body):
        return header + ' {\n' + '\n'.join(statement(node) for node in body) + '\n}'

    def statement(node):
        if isinstance(node, ast.FunctionDef):
            return block(f'fn {node.name}({ast.unparse(node.args)})->{ast.unparse(node.returns)}', node.body)
        if isinstance(node, ast.If):
            result = block('if ' + ast.unparse(node.test), node.body)
            return result + ('\n' + block('else', node.orelse) if node.orelse else '')
        if isinstance(node, ast.For):
            if node.orelse:
                raise AssertionError('fixture converter does not support for/else')
            return block(f'for {ast.unparse(node.target)} in {ast.unparse(node.iter)}', node.body)
        if isinstance(node, ast.Try):
            result = block('try', node.body)
            for handler in node.handlers:
                result += '\n' + block('except ' + ast.unparse(handler.type), handler.body)
            if node.orelse:
                result += '\n' + block('else', node.orelse)
            if node.finalbody:
                result += '\n' + block('finally', node.finalbody)
            return result
        if isinstance(node, ast.AnnAssign):
            return 'let ' + ast.unparse(node) + ';'
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.Expr, ast.Return, ast.Raise,
                             ast.Break, ast.Continue)):
            return ast.unparse(node) + ';'
        raise AssertionError(f'unsupported fixture statement {type(node).__name__}')

    return '\n'.join(statement(node) for node in ast.parse(source).body)


def owned_source(kind, expression, replacement, consume):
    copy = '[item for item in value]' if kind.startswith('list[') else 'value[:]'
    return f'''
def returned(n: int) -> {kind}:
    try:
        return {expression}
    finally:
        if n % 3 == 1:
            return {replacement}
        if n % 3 == 2:
            raise ValueError()

def loop_exit(n: int) -> int:
    for i in range(2):
        try:
            return len({expression})
        finally:
            if i == 0:
                continue
            break
    return 13

def discarded(n: int) -> {kind}:
    for i in range(2):
        try:
            return {expression}
        finally:
            if i == 0:
                continue
            break
    return {replacement}

def borrowed(value: {kind}, n: int) -> {kind}:
    local: {kind} = {copy}
    try:
        return local
    finally:
        local = {replacement}

def run(n: int) -> int:
    total = 0
    original: {kind} = returned(0)
    copied: {kind} = borrowed(original, n)
    total += len(original) + len(copied)
    for i in range(n):
        try:
            value: {kind} = returned(i)
            total += {consume}
        except ValueError:
            total += 17
        value = discarded(i)
        total += {consume}
        total += loop_exit(i)
    return total
'''


GENERAL_PENDING = '''
def h(s: str) -> str:
    try:
        s = s + "y"
        raise RuntimeError(s)
    finally:
        try:
            x = [1][3]
        except IndexError:
            print("inner")
        print("fin", s)
    return s

def r(s: str) -> str:
    try:
        s = s + "q"
        return s
    finally:
        print("r-fin", s)

def main() -> None:
    try:
        print(h("ab"))
    except RuntimeError as e:
        print("caught", e)
    print(r("z"))

'''


@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'),
                     'installed C compiler required')
class FinallyTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    command = support.CObjectTests.command
    write = support.CObjectTests.write
    ail_build = support.CObjectTests.ail_build
    snapshot = support.CObjectTests.snapshot

    def test_whole_trace_matches_independent_cpython(self):
        reference = {}
        exec(TRACE, reference)
        source = self.write('trace.ail', TRACE + '\ndef main() -> int:\n    return run(int(sys.argv[1]))\n')
        executable = self.root / 'trace'
        built = self.command('compile', source, '--syntax', 'python', '-o', executable)
        self.assertEqual(built.returncode, 0, built.stderr.decode(errors='replace'))
        if not executable.is_file():
            executable = Path(str(executable) + '.exe')
        for n in (0, 1, 2, 9):
            with self.subTest(n=n):
                oracle = io.StringIO()
                with contextlib.redirect_stdout(oracle):
                    self.assertEqual(reference['run'](n), 0)
                actual = subprocess.run([str(executable), str(n)], capture_output=True, timeout=30)
                self.assertEqual((actual.returncode, actual.stderr), (0, b''))
                self.assertEqual(actual.stdout.decode().replace('\r\n', '\n'), oracle.getvalue())

    def test_general_path_pending_exception_survives_finally_body(self):
        # The general path used to drop a pending exception (and the return it replaced) when the
        # finally body ran any call, or caught an exception of its own; the caller saw None.
        oracle = io.StringIO()
        with contextlib.redirect_stdout(oracle):
            exec(GENERAL_PENDING + 'main()\n', {})
        source = self.write('pending.ail', GENERAL_PENDING + 'main()\n')
        executable = self.root / 'pending'
        built = self.command('compile', source, '--syntax', 'python', '-o', executable)
        self.assertEqual(built.returncode, 0, built.stderr.decode(errors='replace'))
        if not executable.is_file():
            executable = Path(str(executable) + '.exe')
        actual = subprocess.run([str(executable)], capture_output=True, timeout=30)
        self.assertEqual((actual.returncode, actual.stderr), (0, b''))
        self.assertEqual(actual.stdout.decode().replace('\r\n', '\n'), oracle.getvalue())
        self.assertIn('caught aby', oracle.getvalue())

    def test_public_brace_finally(self):
        executable = self.ail_build('brace', BRACE_LIBRARY + BRACE_MAIN)
        support.CObjectTests.check_run(self, executable, '0\n11\n12\n0\n1\n11\n12\n7\n')

    def test_separate_relocated_source_free_finally(self):
        source = self.write('library.ail', BRACE_LIBRARY)
        obj = self.root / 'library.o'
        built = self.command('compile-module', source, '-o', obj)
        self.assertEqual(built.returncode, 0, built.stderr.decode(errors='replace'))
        source.unlink()
        moved = self.root / '移動 objects'
        moved.mkdir()
        destination = moved / obj.name
        shutil.move(str(obj), destination)
        shutil.move(str(obj) + '.json', str(destination) + '.json')
        before = self.snapshot(destination)
        consumer = self.write('consumer.ail', BRACE_MAIN)
        helper = self.write('helper.ail', 'fn _consume(n:int)->int {return n;}')
        executable = self.root / 'consumer'
        built = self.command('compile', consumer, '--separate', '--module', helper,
                             '--object', destination, '-o', executable)
        self.assertEqual(built.returncode, 0, built.stderr.decode(errors='replace'))
        consumer.unlink()
        if not executable.is_file():
            executable = Path(str(executable) + '.exe')
        support.CObjectTests.check_run(self, executable, '0\n11\n12\n0\n1\n11\n12\n7\n')
        self.assertEqual(self.snapshot(destination), before)

    def test_owned_pending_returns_released(self):
        cases = (
            ('str', repr('x' * 8193) + ' + str(n)', '"y" + str(n)', 'len(value)'),
            ('bytes', repr(b'x' * 8193) + ' + b"q"', 'b"yz" + b"q"', 'len(value)'),
            ('list[int]', '[i for i in range(8193)]', '[n, n+1]', 'len(value) + value[0]'),
            ('list[float]', '[float(i)*0.125 for i in range(8193)]', '[float(n), 0.25]',
             'len(value) + int(value[0])'),
        )
        for kind, expression, replacement, consume in cases:
            with self.subTest(kind=kind):
                source = owned_source(kind, expression, replacement, consume)
                native_source = source.replace('-> str:', '-> __ail_checked_str__:').replace(
                    '-> bytes:', '-> __ail_checked_bytes__:')
                resources.ExceptionResourceTests.check_resources(
                    self, source, sizes=(0, 1, 2, 3, 101), native_source=native_source)

    def test_owned_pending_returns_released_separate(self):
        resources.ExceptionResourceTests.check_resources(
            self, owned_source('list[float]', '[float(i)*0.125 for i in range(8193)]',
                               '[float(n), 0.25]', 'len(value) + int(value[0])'),
            sizes=(0, 1, 2, 3, 101), separate=True)

    def test_owned_returns_whole_contents_match_cpython(self):
        cases = (
            ('str', repr('x' * 8193) + ' + str(n)', '"日本語" + str(n)', 'print(value)'),
            ('bytes', repr(b'x' * 8193) + ' + b"q"', 'b"yz" + b"q"', 'write_stdout_bytes(value)'),
            ('list[int]', '[i-4096 for i in range(8193)]', '[n, n+1]',
             'for item in value:\n        print(item)'),
            ('list[float]', '[float(i)*0.125-512.0 for i in range(8193)]',
             '[float(n), -0.0, 0.25]', 'write_stdout_bytes(float64_encode(value, 0))'),
        )
        for index, (kind, expression, replacement, emit) in enumerate(cases):
            with self.subTest(kind=kind):
                source_text = owned_source(kind, expression, replacement, 'len(value)') + f'''
def emit(value: {kind}) -> int:
    {emit}
    return 0

def main() -> int:
    for n in range(3):
        try:
            value: {kind} = returned(n)
            emit(value)
            emit(borrowed(value, n))
            emit(value)
        except ValueError:
            emit(discarded(n))
        emit(discarded(n))
    return 0
'''
                raw = bytearray()
                reference = {
                    'write_stdout_bytes': raw.extend,
                    'float64_encode': lambda values, order: b''.join(
                        struct.pack('<d' if order == 0 else '>d', value) for value in values),
                }
                exec(source_text, reference)
                text = io.StringIO()
                with contextlib.redirect_stdout(text):
                    self.assertEqual(reference['main'](), 0)
                expected = bytes(raw) if kind in ('bytes', 'list[float]') else text.getvalue().encode()
                source = self.write(f'contents{index}.ail', brace_source(source_text))
                executable = self.root / f'contents{index}'
                built = self.command('compile', source, '-o', executable)
                self.assertEqual(built.returncode, 0, built.stderr.decode(errors='replace'))
                if not executable.is_file():
                    executable = Path(str(executable) + '.exe')
                actual = subprocess.run([str(executable)], capture_output=True, timeout=30)
                self.assertEqual((actual.returncode, actual.stderr), (0, b''))
                if kind in ('str', 'list[int]'):
                    actual_stdout = actual.stdout.replace(b'\r\n', b'\n')
                else:
                    actual_stdout = actual.stdout
                self.assertEqual(actual_stdout, expected)

    def test_file_iterator_pending_exit_cleanup(self):
        source = '''fn file_exit(path:str,mode:int)->bytes {
 for i in range(2) {
  try {for chunk in file_chunks(path,3) {return chunk;}}
  finally {
   if mode==1 {if i==0 {continue;}break;}
   if mode==2 {raise ValueError;}
  }
 }
 return b"fallback";
}
fn main()->int {
 for mode in range(3) {
  try {let value=file_exit(sys.argv[1],mode);write_stdout_bytes(value);}
  except ValueError {write_stdout_bytes(b"201\\n");}
  try {raise IndexError;} except IndexError {write_stdout_bytes(b"202\\n");}
 }
 return 0;
}'''
        executable = self.ail_build('file_exit', source)
        path = self.root / 'chunks.bin'
        for size in (0, 1, 3, 8193):
            with self.subTest(size=size):
                data = bytes(index % 251 for index in range(size))
                path.write_bytes(data)
                expected = (data[:3] if data else b'fallback') + b'202\nfallback202\n201\n202\n'
                actual = subprocess.run([str(executable), str(path)], capture_output=True, timeout=30)
                self.assertEqual((actual.returncode, actual.stderr), (0, b''))
                self.assertEqual(actual.stdout, expected)


if __name__ == '__main__':
    unittest.main()
