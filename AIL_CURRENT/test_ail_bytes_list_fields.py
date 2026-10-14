"""Bytes list struct fields: shared identity, evaluation order and whole binary results."""
from pathlib import Path
import shutil
import struct
import unittest

import test_ail_c_objects as support
import test_ail_binary_cursor_cli as cursor_support


LIBRARY = r'''struct Holder { parts: list[bytes]; tag: int; }
impl Holder {
 fn share(self) -> list[bytes] { return self.parts; }
 fn assign(self, values: list[bytes]) -> void { self.parts = values; }
}
fn make_holder(data: bytes, n: int) -> Holder {
 let values: list[bytes] = [data, b"", b"\x00\xff"];
 for i in range(n) { values.append(data[:129]); }
 return Holder(values, 7);
}
fn replaced(holder: Holder) -> int { holder.parts = [b"new"]; return 0; }
fn first(values: list[bytes], ignored: int) -> bytes { return values[0]; }
fn temporary() -> Holder { return Holder([b"temporary\x00\xff"], 3); }
'''
CLIENT = r'''fn frames(values: list[bytes]) -> bytes {
 let chunks: list[bytes] = [];
 for value in values {
  let size = len(value);
  chunks.append(bytes([size % 256, (size // 256) % 256, (size // 65536) % 256, size // 16777216]));
  chunks.append(value);
 }
 return b"".join(chunks);
}
fn main() -> int {
 let data = read_bytes(sys.argv[1]);
 let holder = make_holder(data, int(sys.argv[3]));
 let alias: list[bytes] = holder.share();
 let saved = holder.parts[0];
 let snapshot: list[bytes] = holder.parts.copy();
 holder.parts.append(b"x"); holder.parts.extend([b"y", b""]);
 holder.parts[0] = b"changed";
 holder.parts.reverse(); holder.parts.sort();
 let removed = holder.parts.pop();
 holder.parts = holder.parts;
 print(len(alias));
 holder.assign([b"replacement"]);
 let replacement: list[bytes] = holder.parts;
 alias.clear();
 holder = Holder([], 8);
 let results: list[bytes] = [saved, removed];
 results.extend(snapshot); results.extend(replacement); results.extend(alias); results.extend(holder.parts);
 write_bytes(sys.argv[2], frames(results));
 print(len(alias)); print(len(holder.parts)); return 0;
}'''


def oracle(data, n):
    values = [data, b'', b'\0\xff', *([data[:129]] * n)]
    saved, snapshot = values[0], values.copy()
    alias = values
    values.append(b'x')
    values.extend([b'y', b''])
    values[0] = b'changed'
    values.reverse()
    values.sort()
    removed = values.pop()
    size = len(alias)
    replacement = [b'replacement']
    alias.clear()
    parts = [saved, removed, *snapshot, *replacement]
    return b''.join(struct.pack('<I', len(part)) + part for part in parts), f'{size}\n0\n0\n'


class BytesListFieldTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    command = support.CObjectTests.command
    write = support.CObjectTests.write
    ail_build = support.CObjectTests.ail_build
    check_run = support.CObjectTests.check_run
    snapshot = support.CObjectTests.snapshot

    def workload(self, exe):
        source, output = self.root / '入力 field.bin', self.root / 'field frames.bin'
        for data, n in ((b'', 0), (b'\0\xff\x80', 1), (bytes(range(256)), 16),
                        (bytes(range(256)), 8191), (bytes(range(256)), 8192),
                        (bytes(range(256)), 8193), (bytes(range(256)) * 4097, 0)):
            with self.subTest(size=len(data), count=n, executable=exe.name):
                source.write_bytes(data)
                before = cursor_support.pin(source)
                expected, stdout = oracle(data, n)
                self.check_run(exe, stdout, source, output, n)
                self.assertEqual(output.read_bytes(), expected)
                self.assertEqual(cursor_support.pin(source), before)

    def test_complete_framed_fields_ordinary_separate_and_moved_provider_two_relinks(self):
        ordinary = self.ail_build('fields_ordinary', LIBRARY + CLIENT)
        self.workload(ordinary)
        module = self.write('fields_module.ail', LIBRARY)
        source = self.write('fields_separate.ail', 'use fields_module;\n' + CLIENT)
        separate = self.root / 'fields_separate.exe'
        result = self.command('compile', source, '--separate', '-o', separate)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        source.unlink()
        self.workload(separate)
        module.unlink()
        obj = self.ail_build('field_provider', LIBRARY, library=True)
        moved = self.root / 'moved field objects'
        moved.mkdir()
        destination = moved / obj.name
        shutil.move(str(obj), destination)
        shutil.move(str(obj) + '.json', str(destination) + '.json')
        before = self.snapshot(destination)
        for name in ('fields_linked', 'fields_relinked'):
            exe = self.ail_build(name, CLIENT, destination)
            self.assertFalse(list(self.root.glob('*.ail')))
            self.workload(exe)
            self.assertEqual(self.snapshot(destination), before)

    def test_field_snapshot_before_later_rebind_temporary_receivers_and_scalar_sort(self):
        source = LIBRARY + r'''fn main() -> int {
 let original: list[bytes] = [b"old\x00\xff"];
 let holder = Holder(original, 9);
 let shared = Holder(original, 1);
 print(first(holder.parts, replaced(holder)).hex());
 print(holder.parts[0].hex()); print(shared.parts[0].hex());
 holder.parts = shared.parts;
 holder.parts.append(b"alias"); print(len(original));
 holder.parts = holder.parts;
 holder.share();
 print(first(temporary().parts, 0).hex());
 let saved = temporary().parts[0];
 let popped = temporary().parts.pop();
 temporary();
 print(saved.hex()); print(popped.hex());
 let rows = [holder, shared, Holder([], 3)];
 let ordered = sorted(rows, key=lambda row: row.tag);
 for row in ordered { print(row.tag); }
 holder.parts.clear(); print(len(shared.parts));
 return 0;
}'''
        exe = self.ail_build('field_order', source)
        self.check_run(exe, '6f6c6400ff\n6e6577\n6f6c6400ff\n2\n'
                       + '74656d706f7261727900ff\n' * 3 + '1\n3\n9\n0\n')

    def test_incompatible_constructors_assignments_annotations_and_blist_sort_keys_refused(self):
        bodies = ['let holder = Holder([1], 0);', 'let holder = Holder(["x"], 0);',
                  'let holder = Holder([b"x", 1], 0);',
                  'let holder = Holder([], 0); holder.parts = [1];',
                  'let holder = Holder([], 0); holder.parts = ["x"];',
                  'let holder = Holder([], 0); holder.parts = [b"x", 1];',
                  'let rows = [Holder([b"x"], 0)]; let ordered = sorted(rows, key=lambda row: row.parts);']
        sources = [LIBRARY + 'fn main() -> int { ' + body + ' return 0; }' for body in bodies]
        sources += ['struct Bad { values: ' + annotation + '; }\n'
                    + 'fn main() -> int { return 0; }' for annotation in ('list[complex]', 'list[Unknown]', 'list[list[bytes]]')]
        for index, source in enumerate(sources):
            with self.subTest(index=index):
                path = self.write('invalid_fields_'+str(index)+'.ail', source)
                output = self.root / ('invalid_fields_'+str(index)+'.exe')
                result = self.command('compile', path, '-o', output)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(b'Traceback', result.stderr)
                self.assertFalse(output.exists())
                self.assertFalse(Path(str(output)+'.json').exists())


if __name__ == '__main__':
    unittest.main()
