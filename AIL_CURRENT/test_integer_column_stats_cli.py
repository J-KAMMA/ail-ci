"""Integer-column CLI outputs against independent checked Python arithmetic."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest

import test_ail_c_objects as support


EXAMPLES = support.ROOT / 'language_examples'
SOURCE_NAMES = ('checked_integer.ail', 'integer_column_stats.ail', 'integer_column_stats_main.ail',
                'file_identity.ail', 'file_identity.c', 'file_identity.json')
MIN_I64, MAX_I64 = -(1 << 63), (1 << 63) - 1


def pin(path):
    return hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns


def integer(token):
    if not re.fullmatch(r'[+-]?[0-9]+', token):
        raise ValueError('strict ASCII integer required')
    value = int(token)
    if not MIN_I64 <= value <= MAX_I64:
        raise ValueError('integer outside int64')
    return value


def expected_stats(data, column):
    index = integer(column)
    if index < 0:
        raise ValueError('negative column')
    count, total, minimum, maximum = 0, 0, 0, 0
    for line in data.decode('utf8').splitlines():
        value = integer(line.split('\t')[index])
        total += value
        if not MIN_I64 <= total <= MAX_I64:
            raise ValueError('running total outside int64')
        minimum = min(minimum, value) if count else value
        maximum = max(maximum, value) if count else value
        count += 1
    return f'{count}\t{total}\t{minimum}\t{maximum}\n'.encode('ascii')


@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'),
                     'installed C compiler required')
class IntegerColumnStatsCliTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    command = support.CObjectTests.command
    write = support.CObjectTests.write
    c_object = support.CObjectTests.c_object
    snapshot = support.CObjectTests.snapshot

    def invoke(self, executable, *args):
        return subprocess.run([str(executable), *map(str, args)], cwd=self.root,
                              capture_output=True, timeout=120)

    def check_success(self, executable, data, column):
        expected = expected_stats(data, column)
        source, output = self.root / '入力 columns.tsv', self.root / 'statistics.tsv'
        source.write_bytes(data)
        output.write_bytes(b'previous output\x00\xff')
        before = pin(source)
        result = self.invoke(executable, source, output, column)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b'', b''))
        self.assertEqual(output.read_bytes(), expected)
        self.assertEqual(pin(source), before)

    def check_outputs(self, executable):
        newline_forms = ('\n', '\r', '\r\n', '\v', '\f', '\x1c', '\x1d', '\x1e', '\x85', '\u2028', '\u2029')
        mixed_newlines = ''.join(f'日本語😀\t{index - 5}\tunselected metadata{ending}'
                                 for index, ending in enumerate(newline_forms)).encode('utf8')
        long = ''.join(f'{"日本語😀" + "x" * 128}\t{index % 17 - 8}\t{"外部メタデータ" + "y" * 128}\n'
                       for index in range(8193)).encode('utf8')
        self.assertGreaterEqual(len(long), 1024 * 1024)
        cases = ((b'', '0'), (b'', str(MAX_I64)),
                 (f'{MIN_I64}\n{MAX_I64}\n'.encode(), '0'),
                 (b'+0\n-0\n000\n', '-0'), (b'9007199254740993\n-9007199254740992\n', '+0'),
                 (('+' + '0' * 1000 + '7\n-' + '0' * 1000 + '2\n').encode(), '0'),
                 (b'ignored\t17\t\x00not a number\n', '+' + '0' * 1000 + '1'),
                 ('😀\t-17\t任意の列\n日本語\t+23\t非数値\n'.encode('utf8'), '+0001'),
                 (mixed_newlines, '1'), (long, '1'))
        for data, column in cases:
            with self.subTest(bytes=len(data), column=column[:24]):
                self.check_success(executable, data, column)
        for rows in (8191, 8192, 8193):
            data = ''.join(f'metadata\t{1 if index % 2 == 0 else -1}\textra\n'
                           for index in range(rows)).encode()
            with self.subTest(rows=rows):
                self.check_success(executable, data, '1')

    def refused(self, executable, args, protected):
        before = {path: pin(path) for path in protected}
        result = self.invoke(executable, *args)
        self.assertEqual((result.returncode, result.stdout), (2, b''))
        self.assertTrue(result.stderr)
        self.assertNotIn(b'Traceback', result.stderr)
        self.assertEqual({path: pin(path) for path in protected}, before)

    def check_errors(self, executable):
        source, output = self.root / 'protected input.tsv', self.root / 'protected output.tsv'
        source.write_bytes(b'not selected\t1\textra\n')
        output.write_bytes(b'preserve output\x00\xff')
        protected = (source, output)
        for args in ((), (source,), (source, output), (source, output, 1, 'extra'),
                     (self.root / 'missing input', output, 1), (self.root, output, 1)):
            with self.subTest(args=args):
                self.refused(executable, args, protected)
        invalid_columns = ('', '+', '-', '-1', str(MIN_I64), ' 0', '0 ', '1.0', '０', '١',
                           str(MAX_I64 + 1), '9' * 1000)
        for column in invalid_columns:
            with self.subTest(column=column[:24]):
                self.refused(executable, (source, output, column), protected)
        for token in ('', '+', '-', ' 1', '1 ', '1.0', '１', '١', '😀',
                      str(MIN_I64 - 1), str(MAX_I64 + 1), '9' * 1000):
            data = ('ignored\t' + token + '\textra\n').encode('utf8')
            source.write_bytes(data)
            with self.subTest(selected=token[:24]):
                with self.assertRaises((ValueError, IndexError, UnicodeDecodeError)):
                    expected_stats(data, '1')
                self.refused(executable, (source, output, 1), protected)
        bad_data = ((b'\n', '0'), (b'one column\n', '1'), (b'ignored\t1\n\n', '1'),
                    (b'ignored\t\xff\n', '1'), (b'\xff\t1\n', '1'),
                    (f'{MAX_I64}\n1\n-1\n'.encode(), '0'),
                    (f'{MIN_I64}\n-1\n1\n'.encode(), '0'),
                    (b'0\n' * 8193 + f'{MAX_I64}\n1\n-1\n'.encode(), '0'),
                    (b'0\n' * 8193 + f'{MIN_I64}\n-1\n1\n'.encode(), '0'))
        for data, column in bad_data:
            source.write_bytes(data)
            with self.subTest(bytes=len(data), column=column):
                with self.assertRaises((ValueError, IndexError, UnicodeDecodeError)):
                    expected_stats(data, column)
                self.refused(executable, (source, output, column), protected)
        absent = self.root / 'absent output.tsv'
        self.assertFalse(absent.exists())
        self.refused(executable, (source, absent, 0), protected)
        self.assertFalse(absent.exists())
        source.write_bytes(b'1\n')
        directory = self.root / 'alias directory'
        directory.mkdir(exist_ok=True)
        for alias in (source, source.name, directory / '..' / source.name):
            with self.subTest(output_alias=str(alias)):
                self.refused(executable, (source, alias, 0), protected)
        link = self.root / 'hardlink input.tsv'
        if link.exists():
            link.unlink()
        try:
            os.link(source, link)
        except OSError as error:
            if sys.platform != 'win32':
                raise
            with self.subTest(feature='Windows hardlink'):
                self.skipTest(f'Windows hardlink creation unavailable: {error}')
        else:
            self.assertTrue(os.path.samefile(source, link))
            self.refused(executable, (source, link, 0), (*protected, link))

    def check_build(self, separate):
        originals = [EXAMPLES / name for name in SOURCE_NAMES]
        before = list(map(pin, originals))
        native = self.c_object((EXAMPLES / 'file_identity.c').read_text(encoding='utf8'),
                               json.loads((EXAMPLES / 'file_identity.json').read_bytes()), 'identity_native')
        native_before = self.snapshot(native)
        copied = [self.root / path.name for path in originals if path.suffix == '.ail']
        for destination in copied:
            shutil.copy2(EXAMPLES / destination.name, destination)
        copied_before = list(map(pin, copied))
        output = self.root / ('stats separate.exe' if separate else 'stats ordinary.exe')
        result = self.command('compile', self.root / 'integer_column_stats_main.ail', '--object', native,
                              *(('--separate',) if separate else ()), '-o', output)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        self.check_outputs(output)
        self.check_errors(output)
        self.assertEqual(self.snapshot(native), native_before)
        self.assertEqual(list(map(pin, originals)), before)
        self.assertEqual(list(map(pin, copied)), copied_before)

    def test_ordinary_independent_stats_and_prewrite_refusals(self):
        self.check_build(False)

    def test_separate_independent_stats_and_prewrite_refusals(self):
        self.check_build(True)


if __name__ == '__main__':
    unittest.main()
