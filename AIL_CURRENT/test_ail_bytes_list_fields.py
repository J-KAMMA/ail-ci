"""Bytes list struct fields: shared identity, evaluation order and whole binary results."""
from pathlib import Path
import shutil
import struct
import unittest

import test_ail_c_objects as support
import test_ail_binary_cursor_cli as cursor_support


LIBRARY = "class Holder:\n\n    def __init__(self, parts: list[bytes], tag: int):\n        self.parts = parts\n        self.tag = tag\n\n    def share(self) -> list[bytes]:\n        return self.parts\n\n    def assign(self, values: list[bytes]) -> None:\n        self.parts = values\n\ndef make_holder(data: bytes, n: int) -> Holder:\n    values: list[bytes] = [data, b'', b'\\x00\\xff']\n    for i in range(n):\n        values.append(data[:129])\n    return Holder(values, 7)\n\ndef replaced(holder: Holder) -> int:\n    holder.parts = [b'new']\n    return 0\n\ndef first(values: list[bytes], ignored: int) -> bytes:\n    return values[0]\n\ndef temporary() -> Holder:\n    return Holder([b'temporary\\x00\\xff'], 3)\n"
CLIENT = 'from ail import read_bytes, write_bytes\nimport sys\n\ndef frames(values: list[bytes]) -> bytes:\n    chunks: list[bytes] = []\n    for value in values:\n        size = len(value)\n        chunks.append(bytes([size % 256, size // 256 % 256, size // 65536 % 256, size // 16777216]))\n        chunks.append(value)\n    return b\'\'.join(chunks)\n\ndef main() -> int:\n    data = read_bytes(sys.argv[1])\n    holder = make_holder(data, int(sys.argv[3]))\n    alias: list[bytes] = holder.share()\n    saved = holder.parts[0]\n    snapshot: list[bytes] = holder.parts.copy()\n    holder.parts.append(b\'x\')\n    holder.parts.extend([b\'y\', b\'\'])\n    holder.parts[0] = b\'changed\'\n    holder.parts.reverse()\n    holder.parts.sort()\n    removed = holder.parts.pop()\n    holder.parts = holder.parts\n    print(len(alias))\n    holder.assign([b\'replacement\'])\n    replacement: list[bytes] = holder.parts\n    alias.clear()\n    holder = Holder([], 8)\n    results: list[bytes] = [saved, removed]\n    results.extend(snapshot)\n    results.extend(replacement)\n    results.extend(alias)\n    results.extend(holder.parts)\n    write_bytes(sys.argv[2], frames(results))\n    print(len(alias))\n    print(len(holder.parts))\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n'


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
        source = self.write('fields_separate.ail', 'from fields_module import *\n' + CLIENT)
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
        source = LIBRARY + 'import sys\n\ndef main() -> int:\n    original: list[bytes] = [b\'old\\x00\\xff\']\n    holder = Holder(original, 9)\n    shared = Holder(original, 1)\n    print(first(holder.parts, replaced(holder)).hex())\n    print(holder.parts[0].hex())\n    print(shared.parts[0].hex())\n    holder.parts = shared.parts\n    holder.parts.append(b\'alias\')\n    print(len(original))\n    holder.parts = holder.parts\n    holder.share()\n    print(first(temporary().parts, 0).hex())\n    saved = temporary().parts[0]\n    popped = temporary().parts.pop()\n    temporary()\n    print(saved.hex())\n    print(popped.hex())\n    rows = [holder, shared, Holder([], 3)]\n    ordered = sorted(rows, key=lambda row: row.tag)\n    for row in ordered:\n        print(row.tag)\n    holder.parts.clear()\n    print(len(shared.parts))\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n'
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
                    + 'import sys\n\ndef main() -> int:\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n' for annotation in ('list[complex]', 'list[Unknown]', 'list[list[bytes]]')]
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
