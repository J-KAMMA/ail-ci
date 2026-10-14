from test_ail_csv_reference import write_rows, read_rows
"""CSV encoding/rewrite compared with Python's independent CSV implementation."""
import csv
import io
import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

import test_ail_c_objects as support

EXAMPLES = Path(__file__).resolve().parent / 'language_examples'
SOURCES = ('csv_writer.ail', 'csv_stream.ail', 'json_text.ail',
           'file_identity.ail', 'csv_rewrite_main.ail')


def encode(rows):
    output = io.StringIO(newline='')
    output.write(write_rows(rows))
    return output.getvalue().encode('utf8')


def parse(data):
    return [row for row in read_rows(data.decode('utf8')) if row]


class CsvWriterTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    command = support.CObjectTests.command
    write = support.CObjectTests.write
    c_object = support.CObjectTests.c_object

    def copy_sources(self):
        for name in SOURCES:
            shutil.copy2(EXAMPLES / name, self.root / name)

    def compile(self, source, name, *objects):
        exe = self.root / (name + '.exe')
        args = [arg for obj in objects for arg in ('--object', obj)]
        result = self.command('compile', source, *args, '-o', exe)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        return exe

    def cli(self):
        self.copy_sources()
        identity = self.c_object((EXAMPLES / 'file_identity.c').read_text(encoding='utf8'),
                                 json.loads((EXAMPLES / 'file_identity.json').read_bytes()), 'identity')
        return self.compile(self.root / 'csv_rewrite_main.ail', 'rewrite', identity)

    def invoke(self, exe, *args):
        return subprocess.run([str(exe), *map(str, args)], capture_output=True, timeout=15)

    def test_encoder_all_field_shapes_and_empty_list(self):
        self.copy_sources()
        rows = [[''], ['', ''], ['a', '', 'b', ''], ['a,b', 'a"b'],
                ['\r', '\n', '\r\n'], ['日本語😀', 'é', '\0'],
                ['plain', ' spaced ', 'tab\tfield'], ['x' * 65536]]
        statements = ['use csv_writer; fn main()->int {']
        for row in rows:
            statements.append('write_stdout_bytes(csv_encode_row(' + json.dumps(row, ensure_ascii=False) + ').encode("utf-8"));')
        statements.append('let empty:list[str]=[]; try { csv_encode_row(empty); return 9; } except ValueError { return 0; } }')
        source = self.write('encode.ail', '\n'.join(statements))
        result = self.invoke(self.compile(source, 'encode'))
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, encode(rows), b''))
        self.assertEqual(parse(result.stdout), rows)

    def test_rewrite_normalizes_records_without_changing_field_values(self):
        exe = self.cli()
        rows = [[''], ['a,b', 'a"b', '日本語😀'], ['a\r\nb', '', 'last'], ['', '', '']]
        corpus = (encode(rows), b'a,b\rc,d\ne,f\r\n', b'\n\r\n\r', b'a,b', b',', b'""', b'',
                  b'"embedded\r\nnewline",x\n"quote""here",\r\n')
        source, output = self.root / 'input.csv', self.root / 'output.csv'
        for data in corpus:
            with self.subTest(data=data[:80]):
                source.write_bytes(data); output.write_bytes(b'old\0\xff')
                result = self.invoke(exe, source, output)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b'', b''))
                self.assertEqual(output.read_bytes(), encode(parse(data)))
                self.assertEqual(parse(output.read_bytes()), parse(data))
                self.assertEqual(source.read_bytes(), data)

    def test_invalid_input_alias_and_file_errors_preserve_existing_output(self):
        exe = self.cli()
        source, output = self.root / 'input.csv', self.root / 'output.csv'
        old = b'preserve\0\xff'
        for data in (b'"unfinished', b'"closed"suffix', b'bare"quote', b'\xff', b'"\xed\xa0\x80"'):
            source.write_bytes(data); output.write_bytes(old)
            result = self.invoke(exe, source, output)
            self.assertEqual(result.returncode, 4, result.stderr)
            self.assertEqual(output.read_bytes(), old)
            self.assertEqual(source.read_bytes(), data)
        source.write_bytes(b'a,b\n')
        result = self.invoke(exe, source, source)
        self.assertEqual(result.returncode, 4, result.stderr)
        self.assertEqual(source.read_bytes(), b'a,b\n')
        alias = self.root / 'alias.csv'
        os.link(source, alias)
        result = self.invoke(exe, source, alias)
        self.assertEqual(result.returncode, 4, result.stderr)
        self.assertEqual(source.read_bytes(), b'a,b\n')
        output.write_bytes(old)
        self.assertEqual(self.invoke(exe, self.root / 'missing.csv', output).returncode, 3)
        self.assertEqual(output.read_bytes(), old)
        self.assertEqual(self.invoke(exe, source, self.root).returncode, 3)
        self.assertEqual(self.invoke(exe).returncode, 2)


if __name__ == '__main__':
    unittest.main()