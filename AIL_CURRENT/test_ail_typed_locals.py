"""Initialized typed locals: exact kinds, fixed function scope and owned values."""
import ast
import unittest

import test_ail_c_objects as support
import test_ail_binary_cursor_cli as cursor_support


LIBRARY = r'''struct Holder { parts: list[bytes]; tag: int; }
struct Other { tag: int; }
fn integer(value: int) -> int { let result: int = value; return result; }
fn explicit_float(value: int) -> float { let result: float = float(value); return result; }
fn same_float(value: float) -> float { let result: float = value; return result; }
fn copied(data: bytes) -> bytes { let result: bytes = data; return result; }
'''
ENTRY = r'''fn main() -> int {
 let number: int = int(sys.argv[3]);
 let number: int = integer(number);
 let real: float = float(sys.argv[4]);
 let text: str = "日本語\x00😀";
 let payload: bytes = read_bytes(sys.argv[1]);
 let parts: list[bytes] = [payload, b"", b"\x00\xff"];
 let holder: Holder = Holder(parts, number);
 let alias: Holder = holder;
 let saved: bytes = copied(holder.parts[0]);
 alias.parts.append(b"alias");
 let shared: list[bytes] = holder.parts;
 holder = Holder([], 7);
 parts = [];
 let replacement: bytes = b"rebound";
 payload = replacement;
 shared[0] = b"changed";
 print(number); print(explicit_float(number)); print(same_float(real)); print(text);
 print(len(alias.parts)); print(len(holder.parts)); print(len(parts));
 let total: int = 0;
 let value: int = 0;
 let values = [1, 2, 3];
 for value in values { total += value; }
 print(total);
 write_bytes(sys.argv[2], saved + b"".join(shared) + payload);
 return 0;
}'''

INFERENCE = '''def leaf(value: int):
 result: int = value
 return result

def selected(value: int):
 result: int = leaf(value)
 if value < 0:
  result = -result
 return result

def decimals(value: float):
 result: float = value
 result += 0.5
 result *= 2.0
 result /= 2.0
 return result

def labels(value: str) -> __ail_checked_str__:
 result: str = value + "😀"
 return result

def recursion(value: int) -> int:
 result: int = value
 if value > 0:
  result = recursion(value - 1) + 1
 return result

def marked(value: int):
 result: int = value
 print(result)
 return result

def pair(left: int, right: int) -> int:
 result: int = left * 10 + right
 return result

def main() -> int:
 result: int = pair(marked(1), marked(2))
 result: int = result
 print(result)
 print(selected(-7))
 print(recursion(16))
 print(decimals(1.5))
 print(labels("日本語"))
 if False and marked(99) > 0:
  print("wrong")
 if True or marked(98) > 0:
  print("lazy")
 total: int = 0
 item: int = 0
 values = [1, 2, 3]
 for item in values:
  total += item
 print(total)
 return 0
'''


class TypedLocalTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    command = support.CObjectTests.command
    write = support.CObjectTests.write
    ail_build = support.CObjectTests.ail_build
    check_run = support.CObjectTests.check_run

    def test_ordinary_and_separate_exact_scalars_and_owned_alias_outputs(self):
        ordinary = self.ail_build('typed_ordinary', LIBRARY + ENTRY)
        module = self.write('typed_module.ail', LIBRARY)
        entry = self.write('typed_separate.ail', 'use typed_module;\n' + ENTRY)
        before = cursor_support.pin(module), cursor_support.pin(entry)
        separate = self.root / 'typed_separate.exe'
        result = self.command('compile', entry, '--separate', '-o', separate)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        self.assertEqual((cursor_support.pin(module), cursor_support.pin(entry)), before)
        source, output = self.root / '入力 typed.bin', self.root / 'typed output.bin'
        cases = [(-(1 << 63), '-0.0', b''), ((1 << 63) - 1, '1.5', b'\0\xff\x80'),
                 *((n, '0.125', bytes(range(256))) for n in ((1 << 53) - 1, 1 << 53, (1 << 53) + 1)),
                 (0, '-1.25e100', bytes(range(256)) * 4097)]
        for exe in (ordinary, separate):
            for number, real, data in cases:
                with self.subTest(executable=exe.name, number=number, real=real, size=len(data)):
                    source.write_bytes(data)
                    input_before = cursor_support.pin(source)
                    expected = f'{number}\n{float(number)}\n{float(real)}\n日本語\x00😀\n4\n0\n0\n6\n'
                    self.check_run(exe, expected, source, output, number, real)
                    self.assertEqual(output.read_bytes(), data + b'changed\0\xffaliasrebound')
                    self.assertEqual(cursor_support.pin(source), input_before)
        self.assertEqual((cursor_support.pin(module), cursor_support.pin(entry)), before)

    def test_inferred_helper_recursion_repeated_declaration_order_and_lazy_calls(self):
        # int/float returns are inferred; str uses the existing owned return profile.
        ast.parse(INFERENCE)
        exe = self.ail_build('typed_inference', INFERENCE)
        self.check_run(exe, '1\n2\n12\n7\n16\n2.0\n日本語😀\nlazy\n6\n')

    def test_incompatible_initializers_and_later_writes_refused_before_artifact(self):
        bodies = ['let value: int = 1.5;', 'let value: float = 1;',
                  'let value: str = b"x";', 'let value: bytes = "x";',
                  'let value: Holder = Other(1);', 'let value: list[bytes] = [1];',
                  'let value: int = 1; value = 1.5;',
                  'let value: float = 1.0; value = 1;',
                  'let value: int = 1; value += 0.5;',
                  'let value: str = "x"; value = b"x";',
                  'let value: bytes = b"x"; value = "x";',
                  'let value: Holder = Holder([], 0); value = Other(0);',
                  'let value: list[bytes] = []; value = [1];',
                  'let value: int = 0; let invalid_values = [b"x"]; for value in invalid_values { pass; }',
                  'let value: int = 1; let value: float = 1.0;',
                  'let value: int;', 'let value: Unknown = 1;',
                  'let value: list[list[bytes]] = [];', 'let value: list[int] = [1.0];',
                  'let value: list[str] = [1];', 'let value: list[float] = [1];']
        sources = [LIBRARY + 'fn main() -> int { ' + body + ' return 0; }' for body in bodies]
        # AnnAssign target forms are checked through actual Python source entry compilation.
        sources += ['class Box:\n def __init__(self):\n  self.value = 1\n'
                    'def main() -> int:\n box = Box()\n box.value: int = 1\n return 0\n',
                    'def main() -> int:\n values = [1]\n values[0]: int = 1\n return 0\n']
        library = 'fn conflict(value: int) -> int { let value: float = 1.0; return 0; }'
        for index, source in enumerate([*sources, library]):
            with self.subTest(index=index):
                path = self.write('invalid_typed.ail', source)
                before = cursor_support.pin(path)
                is_library = index == len(sources)
                output = self.root / ('invalid_typed.o' if is_library else 'invalid_typed.exe')
                result = self.command('compile-module' if is_library else 'compile', path, '-o', output)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(b'Traceback', result.stderr)
                self.assertFalse(output.exists())
                self.assertFalse((self.root / (output.name + '.json')).exists())
                self.assertEqual(cursor_support.pin(path), before)


if __name__ == '__main__':
    unittest.main()
