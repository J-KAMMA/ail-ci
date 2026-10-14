"""R571 owned callback results: independent programs and allocation accounting."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

import ail_syntax
import test_ail_callable_values as callbacks
import test_ail_c_objects as support
import test_ail_exception_resources as resources
import test_ail_finally as finally_support


PROVIDER = '''
def text(n: int) -> str:
    scratch: list[int] = [i for i in range(8193)]
    try:
        return "日本語\\x00😀" * n
    finally:
        scratch[0] = n

def binary(n: int) -> bytes:
    scratch: list[int] = [i for i in range(8193)]
    try:
        return b"a\\x00\\xffz" * n
    finally:
        scratch[0] = n

def alternate_text(n: int) -> str:
    return text(n) + "!"

def integers(n: int) -> list[int]:
    values: list[int] = [i for i in range(n)]
    if n > 0:
        values[0] = -9223372036854775808
        values[-1] = 9223372036854775807
    try:
        return values
    finally:
        scratch: list[int] = [i for i in range(8193)]

def floating(n: int) -> list[float]:
    values: list[float] = [float(i) for i in range(n)]
    if n > 2:
        values[0] = -0.0
        values[1] = 5e-324
        values[2] = -5e-324
    try:
        return values
    finally:
        scratch: list[int] = [i for i in range(8193)]
'''

FACTORY = '''
def text_factory() -> Callable[[int], str]:
    return text

def binary_factory() -> Callable[[int], bytes]:
    return binary

def integer_factory() -> Callable[[int], list[int]]:
    return integers

def float_factory() -> Callable[[int], list[float]]:
    return floating
'''

CONSUMER = '''
def pass_text(cb: Callable[[int], str], n: int) -> str:
    held: list[int] = [17, 23]
    try:
        return cb(n)
    finally:
        held[0] = n

def pass_binary(cb: Callable[[int], bytes], n: int) -> bytes:
    held: list[int] = [17, 23]
    try:
        return cb(n)
    finally:
        held[0] = n

def pass_integers(cb: Callable[[int], list[int]], n: int) -> list[int]:
    held: list[int] = [17, 23]
    try:
        return cb(n)
    finally:
        held[0] = n

def pass_floats(cb: Callable[[int], list[float]], n: int) -> list[float]:
    held: list[int] = [17, 23]
    try:
        return cb(n)
    finally:
        held[0] = n

def size_text(value: str) -> int:
    return len(value)

def size_binary(value: bytes) -> int:
    return len(value)

def size_ints(value: list[int]) -> int:
    return len(value)

def size_floats(value: list[float]) -> int:
    return len(value)
'''

ENTRY = '''
def main() -> int:
    write_bytes(sys.argv[1], b"")
    t: Callable[[int], str] = text
    alias: Callable[[int], str] = t
    t = alternate_text
    sizes: list[int] = [0, 3, 65537]
    for n in sizes:
        chosen: Callable[[int], bytes] = binary if n % 2 else binary_factory()
        first: str = pass_text(alias, n)
        second: str = t(1)
        print(first)
        print(second)
        raw: bytes = pass_binary(chosen, n)
        next_raw: bytes = binary_factory()(1)
        append_bytes(sys.argv[1], raw)
        append_bytes(sys.argv[1], next_raw)
        ints: list[int] = pass_integers(integer_factory(), n)
        more_ints: list[int] = integers(4)
        print(len(ints))
        for value in ints:
            print(value)
        if n > 0:
            print(ints[0])
            print(ints[-1])
            print(ints[n // 2])
        print(more_ints[0])
        fs: list[float] = pass_floats(float_factory(), n)
        more_fs: list[float] = floating(4)
        append_bytes(sys.argv[1], float64_encode(fs, 0))
        append_bytes(sys.argv[1], float64_encode(more_fs, 1))
    print(size_text(text_factory()(2)))
    print(size_binary(binary_factory()(2)))
    print(size_ints(integer_factory()(2)))
    print(size_floats(float_factory()(2)))
    print(len(text_factory()(0)))
    print(integer_factory()(3)[1])
    append_bytes(sys.argv[1], binary_factory()(3))
    append_bytes(sys.argv[1], float64_encode(float_factory()(3), 0))
    return 0
'''


def resource_source(kind, expression):
    return f'''
def producer(n: int) -> {kind}:
    if n % 3 == 0:
        raise ValueError()
    value: {kind} = {expression}
    if n % 3 == 1:
        raise ValueError()
    return value

def relay(cb: Callable[[int], {kind}], n: int) -> {kind}:
    retained: list[int] = [17, 23]
    try:
        return cb(n)
    finally:
        retained[0] = n

def run(n: int) -> int:
    total = 0
    for i in range(n):
        try:
            first: {kind} = relay(producer, i)
            second: {kind} = relay(producer, 2)
            total += len(first) + len(second)
        except ValueError:
            total += 31
    return total
'''


@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'),
                     'installed C compiler required')
class CallableOwnedResultTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    command = support.CObjectTests.command
    write = support.CObjectTests.write
    ail_build = support.CObjectTests.ail_build
    snapshot = support.CObjectTests.snapshot
    c_object = support.CObjectTests.c_object
    maxDiff = 1200

    def compare_program(self, source, name, *options, reference_source=None):
        expected = callbacks.oracle(source if reference_source is None else reference_source)
        path = self.write(name + '.ail', finally_support.brace_source(source))
        executable = self.root / name
        built = self.command('compile', path, *options, '-o', executable)
        self.assertEqual(built.returncode, 0, built.stderr.decode(errors='replace'))
        if not executable.is_file():
            executable = Path(str(executable) + '.exe')
        path.unlink()
        binary_path = self.root / (name + '.bin')
        actual = subprocess.run([str(executable), str(binary_path)], capture_output=True, timeout=30)
        text = expected[1].replace('\n', '\r\n') if os.name == 'nt' else expected[1]
        self.assertEqual((actual.returncode, actual.stderr), (expected[0], b''))
        expected_text = text.encode('utf8')
        self.assertTrue(actual.stdout == expected_text,
                        f'full stdout mismatch: {len(actual.stdout)} vs {len(expected_text)} bytes')
        actual_binary = binary_path.read_bytes()
        self.assertTrue(actual_binary == expected[2],
                        f'full binary mismatch: {len(actual_binary)} vs {len(expected[2])} bytes')

    def test_full_program_owned_results_survive_next_call_and_finally(self):
        self.compare_program(PROVIDER + FACTORY + CONSUMER + ENTRY, 'owned')

    def test_genuine_separate_modules(self):
        provider = self.write('provider.ail', finally_support.brace_source(PROVIDER + FACTORY))
        consumer = self.write('consumer.ail', finally_support.brace_source(CONSUMER))
        self.compare_program(ENTRY, 'separate', '--separate', '--module', provider,
                             '--module', consumer,
                             reference_source=PROVIDER + FACTORY + CONSUMER + ENTRY)

    def test_relocated_source_free_provider_consumer_factory(self):
        objects = []
        relocated = self.root / '移動 owned callbacks'
        relocated.mkdir()
        for name, source in (('provider', PROVIDER), ('factory', FACTORY), ('consumer', CONSUMER)):
            # Factory requires provider declarations while building its own unit.
            path = self.write(name + '.ail', finally_support.brace_source(source))
            obj = self.root / (name + '.o')
            options = tuple(arg for prior in objects for arg in ('--object', prior))
            result = self.command('compile-module', path, *options, '-o', obj)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
            path.unlink()
            moved = relocated / obj.name
            shutil.move(str(obj), moved)
            shutil.move(str(obj) + '.json', str(moved) + '.json')
            objects.append(moved)
        before = self.snapshot(*objects)
        self.compare_program(ENTRY, 'relocated',
                             *(arg for obj in objects for arg in ('--object', obj)),
                             reference_source=PROVIDER + FACTORY + CONSUMER + ENTRY)
        self.assertEqual(self.snapshot(*objects), before)

    def test_all_owned_result_kinds_exception_allocation_and_spill_cleanup(self):
        for kind, expression in (('str', repr('日本語\x00😀' * 8193)),
                                 ('bytes', repr(b'a\x00\xff' * 8193)),
                                 ('list[int]', '[i for i in range(65537)]'),
                                 ('list[float]', '[float(i) for i in range(65537)]')):
            with self.subTest(kind=kind):
                source = resource_source(kind, expression)
                resources.ExceptionResourceTests.check_resources(
                    self, callbacks.oracle_source(source), sizes=(0, 1, 3, 17),
                    native_source=ail_syntax.translate(finally_support.brace_source(source), module=True))

    def test_readonly_parameters_return_owned_copies(self):
        source = '''
def text_copy(value: str) -> str:
    return value
def bytes_copy(value: bytes) -> bytes:
    return value
def ints_copy(value: list[int]) -> list[int]:
    return value
def floats_copy(value: list[float]) -> list[float]:
    return value
def numeric(i: int, f: float) -> list[float]:
    return [float(i), f]
def main() -> int:
    write_bytes(sys.argv[1], b"")
    t: Callable[[str], str] = text_copy
    b: Callable[[bytes], bytes] = bytes_copy
    i: Callable[[list[int]], list[int]] = ints_copy
    f: Callable[[list[float]], list[float]] = floats_copy
    n: Callable[[int, float], list[float]] = numeric
    text: str = "日本語\\x00😀"
    raw: bytes = b"a\\x00\\xff"
    ints: list[int] = [-9223372036854775808, 9223372036854775807]
    fs: list[float] = [-0.0, 5e-324]
    print(t(text))
    print(text)
    append_bytes(sys.argv[1], b(raw))
    append_bytes(sys.argv[1], raw)
    out: list[int] = i(ints)
    print(out[0])
    print(out[1])
    print(ints[0])
    print(ints[1])
    append_bytes(sys.argv[1], float64_encode(f(fs), 0))
    append_bytes(sys.argv[1], float64_encode(fs, 0))
    append_bytes(sys.argv[1], float64_encode(n(7, -0.0), 0))
    return 0
'''
        self.compare_program(source, 'readonly')

    def test_refuses_mismatched_results_and_legacy_owned_targets(self):
        definitions = 'fn target(n:int)->str {return "ok";}'
        for index, body in enumerate((
                'let cb:Callable[[int],bytes]=target;',
                'let cb:Callable[[float],str]=target;',
                'let cb:Callable[[int],list[int]]=target;',
                'let cb:Callable[[int],list[str]]=target;',
                'let cb:Callable[[Callable[[int],str]],str]=target;')):
            path = self.write(f'bad{index}.ail', definitions + 'fn main()->int {' + body + 'return 0;}')
            output = self.root / f'bad{index}'
            result = self.command('compile', path, '-o', output)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn(b'Traceback', result.stderr)
            self.assertFalse(output.exists())
            self.assertFalse(Path(str(output) + '.exe').exists())
        sys.path.insert(0, str(support.ROOT / 'python/pkg-v12'))
        try:
            from pyfunc import to_c
            from pyfront import Unsupported
            for kind, literal in (('str', '"legacy"'), ('bytes', 'b"legacy"')):
                with self.subTest(kind=kind):
                    source = (f'def legacy(n: int) -> {kind}:\n    return {literal}\n'
                              f'def run(n: int) -> int:\n    cb: Callable[[int], {kind}] = legacy\n'
                              '    return len(cb(n))\n')
                    with self.assertRaisesRegex(Unsupported, 'owned str/bytes return ABI'):
                        to_c(source, entry='run')
        finally:
            sys.path.pop(0)


if __name__ == '__main__':
    unittest.main()
