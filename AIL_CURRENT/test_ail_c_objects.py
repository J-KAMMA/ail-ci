"""Independent C/AIL interoperability checks through the public build commands."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent


def signature(symbol, params, result='int'):
    return dict(symbol=symbol, params=params, result=result)


@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'),
                     'installed C compiler required')
class CObjectTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='ail-c-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def command(self, *args):
        return subprocess.run([sys.executable, '-X', 'utf8', '-B', str(ROOT / 'ail_chatgpt.py'),
                               *map(str, args)], capture_output=True, timeout=180,
                              env=dict(os.environ, PYTHONUTF8='1'))

    def write(self, name, text):
        path = self.root / name
        path.write_text(text, encoding='utf8')
        return path

    def c_object(self, source, interface, name='native'):
        c = self.write(name + '.c', source)
        descriptor = self.write(name + '.json', json.dumps(interface))
        obj = self.root / (name + '.o')
        result = self.command('compile-c', c, '--interface', descriptor, '-o', obj)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        c.unlink()
        descriptor.unlink()
        return obj

    def ail_build(self, name, source, *objects, library=False):
        path = self.write(name + '.ail', source)
        output = self.root / (name + ('.o' if library else ''))
        result = self.command('compile-module' if library else 'compile', path,
                              *(arg for obj in objects for arg in ('--object', obj)), '-o', output)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        path.unlink()
        return output if output.is_file() else Path(str(output) + '.exe')

    def check_run(self, executable, expected, *args):
        result = subprocess.run([str(executable), *map(str, args)], capture_output=True, timeout=30)
        expected = expected.encode()
        if sys.platform == 'win32':
            expected = expected.replace(b'\n', b'\r\n')
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, expected, b''))

    def snapshot(self, *objects):
        return [(hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns)
                for obj in objects for path in (obj, Path(str(obj) + '.json'))]

    def test_real_file_workload_relocated_and_source_free(self):
        example = ROOT / 'language_examples'
        obj = self.c_object((example / 'c_interop.c').read_text(),
                            json.loads((example / 'c_interop.json').read_text()))
        relocated = self.root / '移動した objects'
        relocated.mkdir()
        destination = relocated / 'native.o'
        shutil.move(str(obj), destination)
        shutil.move(str(obj) + '.json', str(destination) + '.json')
        before = self.snapshot(destination)
        executable = self.ail_build('reader', (example / 'c_interop.ail').read_text(encoding='utf8'), destination)
        inputs = ['', 'abc', '日本語\x00😀\r\n𐀀\U0010ffff',
                  ''.join(map(chr, (0, 0x7f, 0x80, 0x7ff, 0x800, 0xd7ff, 0xe000,
                                     0xffff, 0x10000, 0x10ffff))),
                  *('a' * n + '😀' for n in (65535, 65536, 65537)),
                  ('ERR:日本語😀\x00\r\nOK:value\n' * 40000)]
        path = self.root / '入力 file.txt'
        for text in inputs:
            data = text.encode('utf8')
            with self.subTest(bytes=len(data)):
                path.write_bytes(data)
                checksum = sum((index + 1) * value for index, value in enumerate(data)) % 1000000007
                self.check_run(executable, f'{len(data)}\n{checksum}\n', path)
        self.assertEqual(self.snapshot(destination), before)

    def test_numeric_types_multiple_strings_and_ail_dependency(self):
        source = '''#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
int64_t n_identity(int64_t x) { return x; }
double n_float(double x) { return x; }
double n_hypot(double x, double y) { return hypot(x, y); }
int64_t n_same(const unsigned char *a, size_t an, const unsigned char *b, size_t bn) {
    return an == bn && memcmp(a, b, an) == 0;
}
double n_mix(int64_t tag, const unsigned char *a, size_t an, double scale,
             const unsigned char *b, size_t bn) {
    return tag + an * scale + bn + (an ? a[0] : 0) + (bn ? b[bn-1] : 0);
}
static int64_t counter;
int64_t n_step(int64_t x) { counter = counter * 10 + x; return x; }
int64_t n_state(void) { return counter; }
int64_t n_add(int64_t x, int64_t y) { return x + y; }
'''
        functions = {
            'identity_i': signature('n_identity', [['x', 'int']]),
            'identity_f': signature('n_float', [['x', 'float']], 'float'),
            'distance': signature('n_hypot', [['x', 'float'], ['y', 'float']], 'float'),
            'same_text': signature('n_same', [['left', 'str'], ['right', 'str']]),
            'mixed': signature('n_mix', [['tag', 'int'], ['a', 'str'], ['scale', 'float'], ['b', 'str']], 'float'),
            'step': signature('n_step', [['x', 'int']]),
            'state': signature('n_state', []),
            'add_c': signature('n_add', [['x', 'int'], ['y', 'int']])}
        obj = self.c_object(source, dict(version=1, functions=functions, libm=True))
        helper = self.ail_build('wrapper', '''fn copied_int(x: int) -> int { return identity_i(x); }
fn distance_from_origin(x: float, y: float) -> float { return distance(x, y); }
fn equal_strings(a: str, b: str) -> int { return same_text(a, b); }
''', obj, library=True)
        before = self.snapshot(obj, helper)
        executable = self.ail_build('types', '''fn main() -> int {
print(copied_int(-9223372036854775808)); print(identity_i(9223372036854775807));
print(identity_f(-0.0)); print(distance_from_origin(3.0, 4.0));
print(equal_strings("日本語\\x00😀", "日本語\\x00😀"));
print(same_text("a\\x00b", "a\\x00c")); print(same_text("", ""));
print(mixed(7, "😀", 0.5, "a\\x00"));
print(add_c(step(1), step(2))); print(state());
let i = 0; while i < 1000 {
    if same_text("😀\\x00日本語", "😀\\x00日本語") != 1 { return 9; }
    i += 1;
}
print("repeated"); return 0; }''', helper, obj)
        self.check_run(executable, '-9223372036854775808\n9223372036854775807\n-0.0\n5.0\n'
                       + '1\n0\n1\n251.0\n3\n12\nrepeated\n')
        self.assertEqual(self.snapshot(obj, helper), before)
        bad = self.write('wrong.ail', 'fn main() -> int { return identity_i("x"); }')
        result = self.command('compile', bad, '--object', obj, '-o', self.root / 'wrong')
        self.assertNotEqual(result.returncode, 0)

    def test_c_prototype_must_match_exactly(self):
        interface = dict(version=1, functions={'call_c': signature('native', [['value', 'str']])})
        descriptor = self.write('interface.json', json.dumps(interface))
        variants = ['int64_t native(const char *p, size_t n) { return 0; }',
                    'int native(const unsigned char *p, size_t n) { return 0; }',
                    'int64_t native(const unsigned char *p) { return 0; }',
                    'int64_t native(const unsigned char *p, size_t n, ...) { return 0; }',
                    'int64_t native(unsigned char *p, size_t n) { return 0; }',
                    'int64_t native() { return 0; }']
        for index, body in enumerate(variants):
            with self.subTest(body=body):
                source = self.write(f'bad{index}.c', '#include <stdint.h>\n#include <stddef.h>\n' + body)
                output = self.root / f'bad{index}.o'
                result = self.command('compile-c', source, '--interface', descriptor, '-o', output)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(b'Traceback', result.stderr)
                self.assertFalse(output.exists())
                self.assertFalse(Path(str(output) + '.json').exists())

    def test_bad_interfaces_and_output_preservation(self):
        source = self.write('source.c', '#include <stdint.h>\nint64_t native(int64_t x) { return x; }')
        valid = dict(version=1, functions={'call_c': signature('native', [['x', 'int']])})
        malformed = [dict(valid, version=True), dict(valid, functions={}), dict(valid, libm=1),
                     dict(valid, extra=1)]
        for field, value in [('params', [['x', 'int'], ['x', 'int']]), ('params', [['x', 'array']]),
                             ('result', 'str'), ('result', 'bytes'),
                             ('symbol', 'bad;name'), ('symbol', 'while')]:
            case = copy.deepcopy(valid)
            case['functions']['call_c'][field] = value
            malformed.append(case)
        malformed.append(dict(version=1, functions={'len': valid['functions']['call_c']}))
        texts = list(map(json.dumps, malformed)) + [json.dumps(valid).replace('"version": 1',
                                                  '"version": 1, "version": 1'), '{']
        for index, text in enumerate(texts):
            descriptor = self.write('bad_interface.json', text)
            output = self.root / f'rejected{index}.o'
            result = self.command('compile-c', source, '--interface', descriptor, '-o', output)
            with self.subTest(interface=text):
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(b'Traceback', result.stderr)
                if text.count('"version": 1') == 2:
                    self.assertIn(b'duplicate interface key', result.stderr)
                self.assertFalse(output.exists())
                self.assertFalse(Path(str(output) + '.json').exists())
        descriptor = self.write('valid.json', json.dumps(valid))
        for name in ('existing.o', 'existing.o.json'):
            output = self.root / 'existing.o'
            existing = self.write(name, 'preserve')
            result = self.command('compile-c', source, '--interface', descriptor, '-o', output)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(existing.read_text(), 'preserve')
            existing.unlink()
        self.assertTrue(source.is_file())

    def test_separate_c_libraries_namespace_their_target_symbols(self):
        source = '#include <stdint.h>\nint64_t native(int64_t x) { return x + OFFSET; }'
        objects = [self.c_object(source.replace('OFFSET', str(offset)),
                                dict(version=1, functions={name: signature('native', [['x', 'int']])}),
                                name) for name, offset in (('native_native', 1), ('second', 2))]
        executable = self.ail_build('two_libraries',
                                    'fn main() -> int { print(native_native(10)); print(second(10)); return 0; }',
                                    *objects)
        self.check_run(executable, '11\n12\n')

    def test_local_header_dependency_is_rejected(self):
        header = self.write('local.h', 'static int64_t native(int64_t x) { return x; }')
        source = self.write('header_user.c', '#include "' + header.as_posix() + '"\n')
        descriptor = self.write('header_interface.json', json.dumps(dict(version=1,
                                functions={'call_c': signature('native', [['x', 'int']])})))
        obj = self.root / 'header_user.o'
        result = self.command('compile-c', source, '--interface', descriptor, '-o', obj)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'self-contained source', result.stderr)
        self.assertFalse(obj.exists())
        self.assertFalse(Path(str(obj) + '.json').exists())

    def test_astral_jscharat_reaches_c_as_utf8(self):
        # A str holds no half of a surrogate pair: the UTF-16 unit that starts an astral
        # character yields the whole character, and the unit that ends it raises ValueError
        # (decided 2026-10-11, docs/design/utf8-strings.md).
        example = ROOT / 'language_examples'
        obj = self.c_object((example / 'c_interop.c').read_text(),
                            json.loads((example / 'c_interop.json').read_text()))
        executable = self.ail_build('surrogates', '''fn main() -> int {
print(byte_count(jscharat("😀", 0))); print(weighted_checksum(jscharat("😀", 0)));
print(byte_count(jscharat("😀", -1))); print(byte_count(jscharat("😀", 2)));
print(byte_count(jscharat("😀", 9223372036854775807))); print(byte_count(jscharat("", 0)));
try { print(byte_count(jscharat("😀", 1))); } except ValueError { print("ValueError"); }
return 0; }''', obj)
        encoded = '😀'.encode('utf8')
        checksum = sum((index + 1) * value for index, value in enumerate(encoded))
        self.check_run(executable, f'{len(encoded)}\n{checksum}\n' + '0\n0\n0\n0\nValueError\n')
        slist = self.ail_build('with_string_list', '''fn main() -> int {
let words = "a b".split(); print(len(words));
print(byte_count(jscharat(words[0], 0))); return 0; }''', obj)
        self.check_run(slist, '2\n1\n')

    def test_ascii_copy_storage_and_pointer_boundaries(self):
        example = ROOT / 'language_examples'
        source = (example / 'c_interop.c').read_text() + '''
int64_t native_pair(const unsigned char *a, size_t an,
                    const unsigned char *b, size_t bn) {
    uint64_t checksum = 0;
    for (size_t i = 0; i < an; ++i)
        checksum = (checksum + (i + 1) * a[i]) % 1000000007ULL;
    for (size_t i = 0; i < bn; ++i)
        checksum = (checksum + (an + i + 1) * b[i]) % 1000000007ULL;
    /* Existing wrappers copy into consecutive regions of one allocation.
       Same-value nonempty arguments must still have distinct pointers. */
    int layout = b == a + an && (an == 0 || a != b);
    return (int64_t)checksum + (layout ? 1000000007LL : 0);
}
'''
        interface = json.loads((example / 'c_interop.json').read_text())
        interface['functions']['pair_check'] = signature('native_pair', [['left', 'str'], ['right', 'str']])
        obj = self.c_object(source, interface)
        pairs = [('empty', '', 'empty', ''), ('base', 'A\0BC', 'base', 'A\0BC'),
                 ('base[:0]', '', 'base', 'A\0BC'), ('base', 'A\0BC', 'base[4:]', ''),
                 ('base[1:3]', '\0B', 'base[2:]', 'BC'),
                 ('wide[1:4]', 'A\0B', 'base', 'A\0BC'),
                 ('base', 'A\0BC', 'wide', '日A\0B😀'),
                 ('wide', '日A\0B😀', 'base', 'A\0BC')]
        code = ('fn main() -> int { let empty = "".join("".split()); '
                'let base = "A\\x00BC"; let wide = "日A\\x00B😀";\n')
        expected = []
        for left, a, right, b in pairs:
            code += f'print(pair_check({left}, {right}));\n'
            data = (a + b).encode('utf8')
            expected.append(str(1000000007 + sum((i + 1) * value for i, value in enumerate(data)) % 1000000007))
        code += 'print(byte_count(empty)); print(weighted_checksum(empty)); return 0; }'
        executable = self.ail_build('ascii_storage', code, obj)
        self.check_run(executable, '\n'.join(expected) + '\n0\n0\n')

        reader = self.ail_build('ascii_reader', (example / 'c_interop.ail').read_text(encoding='utf8'), obj)
        path = self.root / 'ascii_input'
        # Pure ASCII takes bytes=1; cover every octet and allocation boundaries.
        for data in (bytes(range(128)), *(b'a' * n for n in (65535, 65536, 65537)),
                     bytes(range(128)) * 8193):
            with self.subTest(length=len(data)):
                path.write_bytes(data)
                checksum = sum((i + 1) * value for i, value in enumerate(data)) % 1000000007
                self.check_run(reader, f'{len(data)}\n{checksum}\n', path)


if __name__ == '__main__':
    unittest.main()
