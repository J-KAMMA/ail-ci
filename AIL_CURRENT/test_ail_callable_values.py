"""R570 typed static callback values, compared with independent CPython programs."""
import ast
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import types
import unittest

import test_ail_c_objects as support
import test_ail_exception_resources as resources
import test_ail_finally as finally_support


def oracle_source(source):
    """Erase only annotations, leaving execution and evaluation order untouched."""
    class EraseAnnotations(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            self.generic_visit(node)
            node.returns = None
            for argument in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
                argument.annotation = None
            return node

        def visit_AnnAssign(self, node):
            if node.value is None:
                return ast.Pass()
            return ast.copy_location(ast.Assign(targets=[node.target], value=node.value), node)

    return ast.unparse(ast.fix_missing_locations(EraseAnnotations().visit(ast.parse(source))))


def oracle(source, name='main', *arguments):
    text, raw = io.StringIO(), bytearray()
    namespace = {
        'sys': types.SimpleNamespace(argv=['oracle', 'independent-memory-file']),
        'write_bytes': lambda path, data: raw.clear() or raw.extend(data),
        'append_bytes': lambda path, data: raw.extend(data),
        'float64_encode': lambda values, order: b''.join(
            struct.pack('<d' if order == 0 else '>d', value) for value in values),
    }
    exec(oracle_source(source), namespace)
    with contextlib.redirect_stdout(text):
        result = namespace[name](*arguments)
    return result, text.getvalue(), bytes(raw)


PROVIDER = '''
def identity(x: int) -> int:
    return x

def negate(x: int) -> int:
    return -x

def floating(x: float) -> float:
    return x

def factory(n: int) -> Callable[[int], int]:
    print(10)
    if n == 0:
        return identity
    return negate

def float_factory() -> Callable[[float], float]:
    return floating

def pair(x: int, y: int) -> int:
    print(24)
    return x * 100 + y

def pair_factory() -> Callable[[int, int], int]:
    print(25)
    return pair

def note(x: int) -> void:
    print(x)
'''

CONSUMER = '''
def apply(cb: Callable[[int], int], x: int) -> int:
    forwarded: Callable[[int], int] = cb
    return forwarded(x)

def forward(cb: Callable[[int], int], x: int) -> int:
    return apply(cb, x)

def marker(x: int) -> int:
    print(x)
    return x

def notify(cb: Callable[[int], void], x: int) -> int:
    cb(x)
    return 0
'''

ENTRY = '''
def main() -> int:
    write_bytes(sys.argv[1], b"")
    cb: Callable[[int], int] = identity
    print(forward(cb, -9223372036854775808))
    print(cb(9223372036854775807))
    cb = negate
    print(cb(17))
    for n in range(4):
        selected: Callable[[int], int] = identity if n % 2 == 0 else negate
        print(selected(n))
    retained: Callable[[int], int] = factory(1)
    print(retained(31))
    print(factory(0)(marker(21)))
    print(forward(factory(1), marker(22)))
    print(pair_factory()(marker(26), marker(27)))
    notify(note, 23)
    f: Callable[[float], float] = float_factory()
    append_bytes(sys.argv[1], float64_encode([f(-0.0), f(0.0), f(1.7976931348623157e308), f(5e-324), f(-5e-324)], 0))
    return 0
'''

BORROWED = '''
def text(s: str) -> int:
    print(s)
    return len(s)

def binary(b: bytes) -> int:
    append_bytes(sys.argv[1], b)
    return len(b)

def integers(a: list[int]) -> int:
    for x in a:
        print(x)
    return len(a)

def floats(a: list[float]) -> int:
    append_bytes(sys.argv[1], float64_encode(a, 0))
    return len(a)

def inspect(t: Callable[[str], int], b: Callable[[bytes], int], i: Callable[[list[int]], int], f: Callable[[list[float]], int]) -> int:
    s: str = "日本語\\x00😀"
    raw: bytes = b"a\\x00\\xffz"
    ints: list[int] = [-9223372036854775808, 0, 9223372036854775807]
    fs: list[float] = [-0.0, 5e-324, -1.7976931348623157e308]
    print(t(s))
    print(b(raw))
    print(i(ints))
    print(f(fs))
    print(s)
    append_bytes(sys.argv[1], raw)
    for x in ints:
        print(x)
    append_bytes(sys.argv[1], float64_encode(fs, 0))
    return 0

def main() -> int:
    write_bytes(sys.argv[1], b"")
    return inspect(text, binary, integers, floats)
'''


def ownership_source(kind, expression):
    return f'''
def fail(value: {kind}, n: int) -> int:
    if n % 2 == 0:
        raise ValueError()
    return len(value)

def caller(cb: Callable[[{kind}, int], int], n: int) -> int:
    value: {kind} = {expression}
    retained: list[int] = [17, 23]
    try:
        return cb(value, n) + retained[0]
    finally:
        retained[1] = len(value)

def run(n: int) -> int:
    total = 0
    for i in range(n):
        try:
            total += caller(fail, i)
        except ValueError:
            total += 31
    return total
'''


@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'),
                     'installed C compiler required')
class CallableValueTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    command = support.CObjectTests.command
    write = support.CObjectTests.write
    ail_build = support.CObjectTests.ail_build
    snapshot = support.CObjectTests.snapshot
    c_object = support.CObjectTests.c_object

    def compare_program(self, source, name, *build_options, reference_source=None):
        reference_source = source if reference_source is None else reference_source
        expected_result, expected_text, expected_raw = oracle(reference_source)
        path = self.write(name + '.ail', finally_support.brace_source(source))
        executable = self.root / name
        built = self.command('compile', path, *build_options, '-o', executable)
        self.assertEqual(built.returncode, 0, built.stderr.decode(errors='replace'))
        if not executable.is_file():
            executable = Path(str(executable) + '.exe')
        binary_path = self.root / (name + '.bin')
        actual = subprocess.run([str(executable), str(binary_path)], capture_output=True, timeout=30)
        if os.name == 'nt':
            expected_text = expected_text.replace('\n', '\r\n')
        self.assertEqual((actual.returncode, actual.stdout, actual.stderr),
                         (expected_result, expected_text.encode('utf8'), b''))
        self.assertEqual(binary_path.read_bytes(), expected_raw)

    def test_public_brace_callbacks_full_program(self):
        self.compare_program(PROVIDER + CONSUMER + ENTRY, 'callbacks')

    def test_public_brace_borrowed_arguments_preserve_contents(self):
        self.compare_program(BORROWED, 'borrowed')

    def test_source_free_c_target_and_actual_function_pointer_width(self):
        obj = self.c_object('''#include <stdint.h>
int64_t c_identity(int64_t x) { return x; }
int64_t callback_width(void) { return sizeof(int64_t (*)(int64_t)); }
''', dict(version=1, functions={
            'external_identity': support.signature('c_identity', [['x', 'int']]),
            'callback_width': support.signature('callback_width', [])}))
        before = self.snapshot(obj)
        executable = self.ail_build('c_callback', '''
fn apply(cb:Callable[[int],int],x:int)->int {return cb(x);}
fn main()->int {
 if callback_width() <= 0 {return 9;}
 let cb:Callable[[int],int]=external_identity;
 print(apply(cb,-9223372036854775808));
 print(cb(9223372036854775807));return 0;
}''', obj)
        support.CObjectTests.check_run(self, executable,
                                      '-9223372036854775808\n9223372036854775807\n')
        self.assertEqual(self.snapshot(obj), before)

    def test_genuine_separate_module_callbacks(self):
        module = self.write('provider.ail', finally_support.brace_source(PROVIDER))
        self.compare_program(CONSUMER + ENTRY, 'separate', '--separate', '--module', module,
                             reference_source=PROVIDER + CONSUMER + ENTRY)

    def test_relocated_source_free_provider_consumer_factory(self):
        objects = []
        relocated = self.root / '移動 callbacks'
        relocated.mkdir()
        for name, source in (('provider', PROVIDER), ('consumer', CONSUMER)):
            path = self.write(name + '.ail', finally_support.brace_source(source))
            obj = self.root / (name + '.o')
            built = self.command('compile-module', path, '-o', obj)
            self.assertEqual(built.returncode, 0, built.stderr.decode(errors='replace'))
            path.unlink()
            moved = relocated / obj.name
            shutil.move(str(obj), moved)
            shutil.move(str(obj) + '.json', str(moved) + '.json')
            objects.append(moved)
        before = self.snapshot(*objects)
        # Independent oracle includes source definitions; native compilation sees
        # only the entry source and relocated objects.
        entry = self.write('entry.ail', finally_support.brace_source(ENTRY))
        executable = self.root / 'source_free'
        helper = self.write('module.ail', 'fn helper(n:int)->int {return n;}')
        built = self.command('compile', entry, '--separate', '--module', helper,
                             *(arg for obj in objects for arg in ('--object', obj)), '-o', executable)
        self.assertEqual(built.returncode, 0, built.stderr.decode(errors='replace'))
        if not executable.is_file():
            executable = Path(str(executable) + '.exe')
        entry.unlink()
        binary_path = self.root / 'source_free.bin'
        actual = subprocess.run([str(executable), str(binary_path)], capture_output=True, timeout=30)
        expected = oracle(PROVIDER + CONSUMER + ENTRY)
        text = expected[1].replace('\n', '\r\n') if os.name == 'nt' else expected[1]
        self.assertEqual((actual.returncode, actual.stdout, actual.stderr),
                         (expected[0], text.encode(), b''))
        self.assertEqual(binary_path.read_bytes(), expected[2])
        self.assertEqual(self.snapshot(*objects), before)

    def test_owned_caller_resources_callback_exception_finally(self):
        for kind, expression in (('str', repr('日本語' * 8193)),
                                 ('bytes', repr(b'x' * 8193)),
                                 ('list[int]', '[i for i in range(8193)]'),
                                 ('list[float]', '[float(i) for i in range(8193)]')):
            with self.subTest(kind=kind):
                source = ownership_source(kind, expression)
                resources.ExceptionResourceTests.check_resources(
                    self, oracle_source(source), sizes=(0, 1, 2, 101), native_source=source)

    def test_uninitialized_callback_raises_runtime_error(self):
        source = '''
def target(x: int) -> int:
    return x

def main() -> int:
    if 0:
        cb: Callable[[int], int] = target
    try:
        cb(1)
    except RuntimeError:
        print(71)
        return 0
    return 9
'''
        executable = self.ail_build('uninitialized', finally_support.brace_source(source))
        support.CObjectTests.check_run(self, executable, '71\n')

    def test_indirect_recursion_depth_guard(self):
        source = '''
def apply(op: Callable[[int], int], n: int) -> int:
    return op(n)

def descend(n: int) -> int:
    if n == 0:
        return 7
    return apply(descend, n - 1)

def main() -> int:
    for n in range(9):
        print(descend(n))
    try:
        descend(1000000)
    except RuntimeError:
        print(81)
    print(descend(3))
    return 0
'''
        executable = self.ail_build('recursion', finally_support.brace_source(source))
        support.CObjectTests.check_run(self, executable, '7\n' * 9 + '81\n7\n')
        factory_source = source.replace(
            'def apply(op: Callable[[int], int], n: int) -> int:\n    return op(n)',
            'def factory() -> Callable[[int], int]:\n    return descend').replace(
            'return apply(descend, n - 1)', 'return factory()(n - 1)')
        executable = self.ail_build('factory_recursion', finally_support.brace_source(factory_source))
        support.CObjectTests.check_run(self, executable, '7\n' * 9 + '81\n7\n')
        local_source = source.replace(
            'def apply(op: Callable[[int], int], n: int) -> int:\n    return op(n)\n',
            '').replace('return apply(descend, n - 1)', 'op = descend\n    return op(n - 1)')
        executable = self.ail_build('local_recursion', finally_support.brace_source(local_source))
        support.CObjectTests.check_run(self, executable, '7\n' * 9 + '81\n7\n')

    def test_refuses_invalid_callback_operations(self):
        definitions = 'fn target(x:int)->int {return x;} fn floating(x:float)->float {return x;}'
        cases = [
            'let cb:Callable[[int],int]=floating;',
            'let cb:Callable[[int,int],int]=target;',
            'let cb:Callable[[str],int]=target;',
            'let cb:Callable[[int],float]=target;',
            'let cb:Callable=target;',
            'let cb:Callable[int,int]=target;',
            'let cb:Callable[[Unknown],int]=target;',
            'let cb:Callable[[Callable[[int],int]],int]=target;',
            'let cb:Callable[[int],str]=target;',
            'let cb:Callable[[int],list[int]]=target;',
            'let cb:Callable[[int],int]=target;print(cb+1);',
            'let cb:Callable[[int],int]=target;print(cb<target);',
            'let cb:Callable[[int],int]=target;print(int(cb));',
            'let cb:Callable[[int],int]=target;print(float(cb));',
            'let cb:Callable[[int],int]=target;cb+=1;',
            'let cb:Callable[[int],int]=target;cb();',
            'let cb:Callable[[int],int]=target;cb(1,2);',
            'let cb:Callable[[int],int]=target;cb(1.0);',
            'let cb:Callable[[int],int]=lambda x:x;',
            'let cb:Callable[[int],int]=target;let values=[cb];',
            'let cb:Callable[[int],int]=target;write_stdout_bytes(int64_encode([cb],0));',
            'let cb:Callable[[int],int]=0;',
        ]
        for index, body in enumerate(cases):
            with self.subTest(body=body):
                path = self.write(f'bad{index}.ail', definitions + 'fn main()->int {' + body + 'return 0;}')
                output = self.root / f'bad{index}'
                result = self.command('compile', path, '-o', output)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(b'Traceback', result.stderr)
                self.assertFalse(output.exists())
                self.assertFalse(Path(str(output) + '.exe').exists())

        extra = (
            'fn mutate(cb:Callable[[int],int])->int {cb=target;return cb(1);}',
            'fn closure(n:int)->Callable[[int],int] {fn inner(x:int)->int {return n+x;}return inner;}',
            'struct Holder {cb:Callable[[int],int];}',
        )
        for index, body in enumerate(extra):
            with self.subTest(body=body):
                path = self.write(f'extra{index}.ail', definitions + body + 'fn main()->int {return 0;}')
                result = self.command('compile', path, '-o', self.root / f'extra{index}')
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(b'Traceback', result.stderr)

    def test_metadata_callback_tamper_and_object_hash_preservation(self):
        obj = self.ail_build('metadata', finally_support.brace_source(PROVIDER), library=True)
        metadata_path = Path(str(obj) + '.json')
        original_metadata = metadata_path.read_bytes()
        original_object = obj.read_bytes()
        entry = self.write('use.ail', 'fn main()->int {let cb:Callable[[int],int]=factory(0);return cb(0);}')
        for kind in ('callable:[["float"],"float"]', 'callable:broken',
                     'callable:[["int"], "int"]', 'callable:[["Unknown"],"int"]'):
            with self.subTest(kind=kind):
                metadata = json.loads(original_metadata)
                metadata['contract']['exports']['factory']['result'] = kind
                metadata_path.write_text(json.dumps(metadata), encoding='utf8')
                before = self.snapshot(obj)
                result = self.command('compile', entry, '--object', obj, '-o', self.root / 'tampered')
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(b'Traceback', result.stderr)
                self.assertEqual(self.snapshot(obj), before)
        metadata_path.write_bytes(original_metadata)
        obj.write_bytes(original_object + b'changed')
        before = self.snapshot(obj)
        result = self.command('compile', entry, '--object', obj, '-o', self.root / 'hash')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'object hash mismatch', result.stderr)
        self.assertEqual(self.snapshot(obj), before)


if __name__ == '__main__':
    unittest.main()
