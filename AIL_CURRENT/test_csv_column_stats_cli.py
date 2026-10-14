from test_ail_csv_reference import write_rows, read_rows
"""Independent CSV/integer oracle; optionally check a replacement AIL module."""
import argparse
import csv
import hashlib
import io
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

import test_ail_c_objects as support

EXAMPLES = support.ROOT / 'language_examples'
CANDIDATE = EXAMPLES / 'csv_column_stats.ail'
LOW, HIGH = -(1 << 63), (1 << 63) - 1


def integer(text):
    if not re.fullmatch(r'[+-]?[0-9]+', text):
        raise ValueError('ASCII integer required')
    digits = text.lstrip('+-').lstrip('0') or '0'
    if len(digits) > 19:
        raise ValueError('int64 overflow')
    value = int(('-' if text.startswith('-') else '') + digits)
    if not LOW <= value <= HIGH:
        raise ValueError('int64 overflow')
    return value


def oracle(data, column):
    selected = integer(column)
    if selected < 0:
        raise ValueError('negative column')
    previous_limit = csv.field_size_limit(min(sys.maxsize,2147483647))
    try:
        values = [integer(row[selected]) for row in
                  read_rows(data.decode('utf8')) if row]
    finally:
        csv.field_size_limit(previous_limit)
    total = 0
    for value in values:
        total += value
        if not LOW <= total <= HIGH:
            raise ValueError('running total overflow')
    return f'{len(values)}\t{total}\t{min(values, default=0)}\t{max(values, default=0)}\n'.encode()


def encoded(rows):
    text = io.StringIO(newline='')
    text.write(write_rows(rows))
    return text.getvalue().encode('utf8')


@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('gcc'), 'C compiler required')
class CsvColumnStatsCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary = tempfile.TemporaryDirectory(prefix='ail-csv-stats-')
        cls.addClassCleanup(temporary.cleanup)
        cls.root = Path(temporary.name)
        (cls.root / 'csv_column_stats.ail').write_bytes(CANDIDATE.read_bytes())
        entry = cls.root / 'main.ail'
        entry.write_bytes((EXAMPLES / 'csv_column_stats_main.ail').read_bytes())
        def command(*args):
            result = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(support.ROOT / 'ail_chatgpt.py'),
                                     *map(str, args)], capture_output=True, timeout=180)
            if result.returncode:
                raise RuntimeError(result.stderr.decode(errors='replace'))
        obj = cls.root / 'identity.o'
        command('compile-c', EXAMPLES / 'file_identity.c', '--interface', EXAMPLES / 'file_identity.json', '-o', obj)
        output = cls.root / 'csv-stats'
        command('compile', entry, '--object', obj, '-o', output)
        cls.executable = output if output.is_file() else Path(str(output) + '.exe')

    def invoke(self, *args):
        return subprocess.run([str(self.executable), *map(str, args)], capture_output=True, timeout=30)

    def test_independent_csv_full_output_and_long_input(self):
        rows = [[f'日本語😀,"quoted"\r\n{index}', str(index % 17 - 8), 'x' * 96 + '\0'] for index in range(8193)]
        corpus = [(b'', '0'), (b'\r\n\n', str(HIGH)), (b'"7"', '0'),
                  (b'1\r2\n3\r\n', '0'), (f'{LOW}\n{HIGH}'.encode(), '0'),
                  (b'+0007\n-0002\n-0', '+0'), (encoded([['ignored,\n😀', '9007199254740993'], ['last', '-9007199254740992']]), '1'),
                  (encoded(rows), '1'),
                  (encoded([['x' * 262145 + '\r\n😀', '+' + '0' * 8193 + '7'], ['last', '-7']]), '1')]
        source, output = self.root / 'input 😀.csv', self.root / 'report.tsv'
        for data, column in corpus:
            with self.subTest(size=len(data), column=column):
                source.write_bytes(data); output.write_bytes(b'old\0\xff')
                before = hashlib.sha256(source.read_bytes()).hexdigest()
                result = self.invoke(source, output, column)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b'', b''))
                self.assertEqual(output.read_bytes(), oracle(data, column))
                self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)

    def test_invalid_data_and_arguments_preserve_output(self):
        source, output = self.root / 'invalid.csv', self.root / 'protected.tsv'
        corpus = [(b'1\n', '-1'), (b'1\n', str(HIGH + 1)), (b'1\n', ' 0'),
                  (b'1\n', '1'), (b'1,\n', '1'), (b'1\n\xff', '0'),
                  (b'1\n"unfinished', '0'), (b'1\n"2"x', '0'),
                  (b'1\n1_0', '0'), ('1\n２'.encode(), '0'),
                  (f'{HIGH}\n1\n-1'.encode(), '0'), (f'{LOW}\n-1\n1'.encode(), '0')]
        for data, column in corpus:
            with self.subTest(data=data[:50], column=column):
                source.write_bytes(data); output.write_bytes(b'old\0\xff')
                result = self.invoke(source, output, column)
                self.assertEqual((result.returncode, result.stdout), (2, b''))
                self.assertTrue(result.stderr)
                self.assertEqual(output.read_bytes(), b'old\0\xff')
                self.assertEqual(source.read_bytes(), data)
        self.assertEqual(self.invoke().returncode, 2)
        missing = self.root / 'missing.csv'
        self.assertEqual(self.invoke(missing, output, 0).returncode, 2)
        self.assertEqual(output.read_bytes(), b'old\0\xff')

    def test_aliases_do_not_modify_input(self):
        source = self.root / 'alias.csv'; source.write_bytes(b'1\n2\n')
        self.assertEqual(self.invoke(source, source, 0).returncode, 2)
        alias = self.root / 'hardlink.csv'
        os.link(source, alias)
        self.assertEqual(self.invoke(source, alias, 0).returncode, 2)
        self.assertEqual(source.read_bytes(), b'1\n2\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--candidate', type=Path)
    options, arguments = parser.parse_known_args()
    if options.candidate:
        CANDIDATE = options.candidate.resolve(strict=True)
    unittest.main(argv=[sys.argv[0], *arguments])