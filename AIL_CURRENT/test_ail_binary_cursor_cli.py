"""Binary cursor CLI whole-file outputs compared with independent CPython."""
import hashlib
import shutil
import subprocess
import unittest

import test_ail_c_objects as support


EXAMPLES = support.ROOT / 'language_examples'


def pin(path):
    return hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns


class BinaryCursorCliTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    command = support.CObjectTests.command
    ail_build = support.CObjectTests.ail_build
    snapshot = support.CObjectTests.snapshot
    write = support.CObjectTests.write

    def workloads(self, executable):
        path = self.root / '入力 cursor.bin'
        for data in (b'', b'\0\xff\x80abc\0', bytes(range(256)),
                     bytes(range(256)) * 4097):
            path.write_bytes(data)
            before = pin(path)
            size = len(data)
            for first, second in ((0, 0), (0, size), (size, 0),
                                  (size // 3, size - size // 3),
                                  (size // 2, size // 4)):
                for mode in ('slice', 'rejoin'):
                    expected = (data[first:first + second] if mode == 'slice'
                                else b''.join((data[:first], data[first:first + second])))
                    with self.subTest(size=size, mode=mode, first=first, second=second):
                        result = subprocess.run([str(executable), mode, str(path),
                                                 str(first), str(second)],
                                                capture_output=True, timeout=45)
                        self.assertEqual((result.returncode, result.stdout, result.stderr),
                                         (0, expected, b''))
                        self.assertEqual(pin(path), before)
        path.write_bytes(b'abc')
        before = pin(path)
        for mode, expected in (('slice', b'b'), ('rejoin', b'ab')):
            result = subprocess.run([str(executable), mode, str(path), ' +0001 ', ' 0001 '],
                                    capture_output=True, timeout=30)
            self.assertEqual((result.returncode, result.stdout, result.stderr), (0, expected, b''))
            self.assertEqual(pin(path), before)

    def errors(self, executable):
        path = self.root / 'protected.bin'
        path.write_bytes(b'\0\xffabc')
        before = pin(path)
        cases = [(), ('slice',), ('slice', path, '0'),
                 ('unknown', path, '0', '0'), ('slice', path, '0', '0', 'extra')]
        invalid = ('', '+', '--1', '1.0', '9223372036854775808',
                   '-9223372036854775809', '9' * 1000,
                   '-1', '-9223372036854775808', '9223372036854775807', '6')
        for mode in ('slice', 'rejoin'):
            cases.extend((mode, path, value, '0') for value in invalid)
            cases.extend((mode, path, '0', value) for value in invalid)
            cases.extend(((mode, path, '4', '2'), (mode, path, '5', '1')))
            cases.extend((mode, missing, '0', '0')
                         for missing in (self.root / 'absent', self.root))
        for args in cases:
            with self.subTest(args=args):
                result = subprocess.run([str(executable), *map(str, args)],
                                        capture_output=True, timeout=30)
                self.assertEqual((result.returncode, result.stdout), (2, b''))
                self.assertTrue(result.stderr)
                self.assertEqual(pin(path), before)
        for mode in ('slice', 'rejoin'):
            with path.open('rb') as readonly:
                result = subprocess.run([str(executable), mode, str(path), '0', '1'],
                                        stdout=readonly, stderr=subprocess.PIPE, timeout=30)
            self.assertEqual(result.returncode, 2)
            self.assertTrue(result.stderr)
            self.assertEqual(pin(path), before)

    def test_ordinary_and_separate_full_outputs_and_errors(self):
        protected = [EXAMPLES / 'binary_cursor.ail', EXAMPLES / 'binary_cursor_main.ail']
        before = list(map(pin, protected))
        module, entry = self.root / 'binary_cursor.ail', self.root / 'cursor.ail'
        for source, destination in zip(protected, (module, entry)):
            shutil.copy2(source, destination)
        copied = list(map(pin, (module, entry)))
        for separate in (False, True):
            target = self.root / ('separate.exe' if separate else 'ordinary.exe')
            result = self.command('compile', entry,
                                  *(('--separate',) if separate else ()), '-o', target)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
            self.workloads(target)
            self.errors(target)
        self.assertEqual(list(map(pin, protected)), before)
        self.assertEqual(list(map(pin, (module, entry))), copied)

    def test_relocated_source_free_object_two_relinks(self):
        obj = self.ail_build('binary_cursor',
                             (EXAMPLES / 'binary_cursor.ail').read_text(encoding='utf8'),
                             library=True)
        moved = self.root / '移動 objects'
        moved.mkdir()
        destination = moved / obj.name
        shutil.move(str(obj), destination)
        shutil.move(str(obj) + '.json', str(destination) + '.json')
        before = self.snapshot(destination)
        source = (EXAMPLES / 'binary_cursor_main.ail').read_text(encoding='utf8').replace(
            'use binary_cursor;', '')
        for name in ('first', 'relinked'):
            self.workloads(self.ail_build(name, source, destination))
            self.assertEqual(self.snapshot(destination), before)

    def test_state_progression_and_refused_operations(self):
        source = (EXAMPLES / 'binary_cursor.ail').read_text(encoding='utf8')
        source += '''
fn emit_state(value: int) -> void {
    write_stdout_bytes((str(value) + "\\n").encode());
}

fn main() -> int {
    let cursor = BinaryCursor(b"\\x00\\xffabc", 0);
    emit_state(cursor.remaining());
    write_stdout_bytes(cursor.peek(2));
    emit_state(cursor.position);
    write_stdout_bytes(cursor.take(2));
    emit_state(cursor.position);
    emit_state(cursor.skip(1));
    write_stdout_bytes(cursor.take(2));
    emit_state(cursor.remaining());
    write_stdout_bytes(cursor.take(0));
    write_stdout_bytes(cursor.peek(0));
    emit_state(cursor.skip(0));
    let empty = BinaryCursor(b"", 0);
    emit_state(empty.remaining());
    write_stdout_bytes(empty.peek(0));
    write_stdout_bytes(empty.take(0));
    emit_state(empty.skip(0));
    let positions = [-1, 6, -9223372036854775808, 9223372036854775807];
    for position in positions {
        cursor.position = position;
        try { cursor.remaining(); return 10; } except ValueError { pass; }
        if cursor.position != position { return 11; }
        try { cursor.peek(0); return 12; } except ValueError { pass; }
        if cursor.position != position { return 13; }
        try { cursor.take(0); return 14; } except ValueError { pass; }
        if cursor.position != position { return 15; }
        try { cursor.skip(0); return 16; } except ValueError { pass; }
        if cursor.position != position { return 17; }
        cursor.position = 0;
        write_stdout_bytes(cursor.take(1));
    }
    let counts = [-1, -9223372036854775808, 5, 9223372036854775807];
    for count in counts {
        cursor.position = 1;
        try { cursor.peek(count); return 20; } except ValueError { pass; }
        if cursor.position != 1 { return 21; }
        try { cursor.take(count); return 22; } except ValueError { pass; }
        if cursor.position != 1 { return 23; }
        try { cursor.skip(count); return 24; } except ValueError { pass; }
        if cursor.position != 1 { return 25; }
        write_stdout_bytes(cursor.take(1));
        emit_state(cursor.position);
    }
    return 0;
}
'''
        executable = self.ail_build('state', source)
        result = subprocess.run([str(executable)], capture_output=True, timeout=30)
        data = b'\0\xffabc'
        expected = (b'5\n' + data[:2] + b'0\n' + data[:2] + b'2\n3\n'
                    + data[3:] + b'0\n5\n0\n0\n' + data[:1] * 4
                    + (data[1:2] + b'2\n') * 4)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, expected, b''))


if __name__ == '__main__':
    unittest.main()
