from test_ail_csv_reference import write_rows, read_rows
"""Streaming CSV rewrite: independent Python CSV oracle and caller-owned files.

Late invalid input may truncate output or leave a completed prefix. Only failures
before output opening (arguments, aliases, input-open failure) preserve old output.
Native execution belongs to the lead; importing this module runs no programs.
"""
import ast
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest

import test_ail_c_objects as support

EXAMPLES = support.ROOT / 'language_examples'
CHUNKS = (1, 2, 3, 4, 7, 8192)
LIMIT = 1048576


def rows_from(data):
    return [row for row in read_rows(data.decode('utf-8')) if row]


def encode(rows, ending='\r\n'):
    result = io.StringIO(newline='')
    result.write(write_rows(rows,ending))
    return result.getvalue().encode('utf-8')


def row_units(row):
    return sum(1 + len(field) for field in row)


API = r'''use csv_rewrite_stream;
fn main()->int {
 let reader=open_binary(sys.argv[1],"rb"); let writer=open_binary(sys.argv[2],"w+b");
 try {
  let rows=csv_rewrite_stream(reader,writer,3,1048576);
  if reader.closed!=0 or writer.closed!=0 { return 9; }
  writer.flush(); writer.seek(0,0);
  write_stdout_bytes((str(rows)+"\n").encode()); write_stdout_bytes(writer.read(1048576));
 } finally { reader.close();writer.close(); }
 let closed_reader=open_binary(sys.argv[1],"rb");closed_reader.close();
 let closed_writer=open_binary(sys.argv[2],"rb");closed_writer.close();
 let live=open_binary(sys.argv[1],"rb");let caught:int=0;
 try {
  try { csv_rewrite_stream(closed_reader,live,1,100); } except ValueError { caught+=1; }
  try { csv_rewrite_stream(live,closed_writer,1,100); } except ValueError { caught+=1; }
  try { csv_rewrite_stream(live,live,0,100); } except ValueError { caught+=1; }
  live.seek(0,0);
  try { csv_rewrite_stream(live,live,8192,100); } except OSError { caught+=1; }
 } finally { live.close(); }
 if caught!=4 { return 10; } return 0;
}'''

PROVIDER = r'''use csv_rewrite_stream;
fn rewrite(reader:binaryfile,writer:binaryfile,chunk:int,cap:int)->int {
 return csv_rewrite_stream(reader,writer,chunk,cap);
}'''
CONSUMER = r'''fn main()->int {
 let reader=open_binary(sys.argv[1],"rb");let writer=open_binary(sys.argv[2],"wb");
 try {
  let count=rewrite(reader,writer,2,1048576);
  if reader.closed!=0 or writer.closed!=0 { return 9; }
  writer.flush();write_stdout_bytes((str(count)+"\n").encode());
 } finally { reader.close();writer.close(); } return 0;
}'''


class CsvRewriteStreamTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    command = support.CObjectTests.command
    write = support.CObjectTests.write
    c_object = support.CObjectTests.c_object
    ail_build = support.CObjectTests.ail_build
    snapshot = support.CObjectTests.snapshot

    def cli(self):
        identity = self.c_object((EXAMPLES / 'file_identity.c').read_text(encoding='utf-8'),
                                 json.loads((EXAMPLES / 'file_identity.json').read_bytes()),
                                 'identity')
        source = self.write('stream-main.ail',
                            (EXAMPLES / 'csv_rewrite_stream_main.ail').read_text(encoding='utf-8'))
        output = self.root / 'stream'
        result = self.command('compile', source, '--object', identity, '-o', output)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        return output if output.is_file() else Path(str(output) + '.exe')

    def invoke(self, executable, *arguments, timeout=60):
        return subprocess.run([str(executable), *map(str, arguments)],
                              capture_output=True, timeout=timeout)

    def test_valid_chunk_boundaries_and_large_nonrepeating_full_output(self):
        executable = self.cli()
        source, output = self.root / 'input.csv', self.root / 'output.csv'
        rows = [[''], ['', '', ''], ['日本😀é', 'a"b', 'a,b', '\0'],
                ['embedded\r\nnewline', '\r', '\n', 'tail'], [' spaced ', 'tab\tfield']]
        corpus = (encode(rows), encode(rows, '\n'), b'a,b\rc,d\ne,f\r\n',
                  b'\n\r\n\r', b'a,b', b',', b'""', b'',
                  b'"quote""here",x\r\n"multi\nline",last')
        for data in corpus:
            expected_rows = rows_from(data)
            cap = max([1, *map(row_units, expected_rows)])
            expected = encode(expected_rows)
            for chunk in CHUNKS:
                with self.subTest(prefix=data[:60], chunk=chunk):
                    source.write_bytes(data); output.write_bytes(b'old')
                    result = self.invoke(executable, source, output, chunk, cap)
                    self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b'', b''))
                    self.assertEqual(output.read_bytes(), expected)
                    self.assertEqual(source.read_bytes(), data)
        many = [[str(i), f'unique-{i:06d}-' + 'x' * 64, '日本😀', 'a"b,\0'] for i in range(16385)]
        data = encode(many, '\n')
        self.assertGreater(len(data), LIMIT)
        source.write_bytes(data)
        result = self.invoke(executable, source, output, 8192, max(map(row_units, many)), timeout=120)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b'', b''))
        expected = encode(rows_from(data))
        self.assertEqual(output.read_bytes(), expected)
        self.assertEqual(hashlib.sha256(output.read_bytes()).digest(), hashlib.sha256(expected).digest())
        self.assertEqual(source.read_bytes(), data)

    def test_row_cap_exact_empty_columns_pending_and_late_failures(self):
        executable = self.cli()
        source, output = self.root / 'input.csv', self.root / 'output.csv'
        for row in (['😀é日本', 'a\n"b', ''], [''] * 17, [''], ['x' * 31]):
            data = encode([row])
            cap = row_units(row)
            for chunk in CHUNKS:
                source.write_bytes(data)
                result = self.invoke(executable, source, output, chunk, cap)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b'', b''))
                self.assertEqual(output.read_bytes(), encode(rows_from(data)))
            if cap > 1:
                source.write_bytes(data)
                result = self.invoke(executable, source, output, 8192, cap - 1)
                self.assertEqual(result.returncode, 4, result.stderr)
                self.assertEqual(output.read_bytes(), b'')  # current chunk validates before writing
                self.assertEqual(source.read_bytes(), data)
        # A completed row must not be published from a chunk with an over-cap pending row.
        data = b'ok\r\n' + b'a' * 12
        source.write_bytes(data)
        result = self.invoke(executable, source, output, 8192, 12)
        self.assertEqual(result.returncode, 4, result.stderr)
        self.assertEqual(output.read_bytes(), b'')
        result = self.invoke(executable, source, output, 4, 12)
        self.assertEqual(result.returncode, 4, result.stderr)
        self.assertEqual(output.read_bytes(), b'ok\r\n')  # earlier successful chunk is retained
        self.assertEqual(source.read_bytes(), data)
        # A maximum-size chunk must reject a tiny quota before field construction.
        for data in (b'a' * LIMIT, b',' * 65536):
            source.write_bytes(data)
            result = self.invoke(executable, source, output, LIMIT, 1, timeout=15)
            self.assertEqual((result.returncode, result.stdout), (4, b''))
            self.assertEqual(output.read_bytes(), b'')
            self.assertEqual(source.read_bytes(), data)
        malformed = (b'"unfinished', b'"closed"suffix', b'bare"quote', b'\xff',
                     b'"\xed\xa0\x80"', b'ok\r\n"\xf0\x9f\x98')
        for data in malformed:
            for chunk in (1, 3, 8192):
                source.write_bytes(data); output.write_bytes(b'old output')
                result = self.invoke(executable, source, output, chunk, 100)
                self.assertEqual(result.returncode, 4, result.stderr)
                self.assertEqual(result.stdout, b'')
                self.assertEqual(source.read_bytes(), data)
                # No old-output preservation guarantee after opening output.

    def test_preopen_errors_aliases_arguments_and_input_identity(self):
        executable = self.cli()
        source, output = self.root / 'input.csv', self.root / 'output.csv'
        data, old = b'a,b\r\n', b'preserve\0\xff'
        source.write_bytes(data)
        for chunk, cap in ((0, 100), (-1, 100), (LIMIT + 1, 100), (1, 0),
                           (1, -1), (1, LIMIT + 1), ('x', 10), (1, 'x'),
                           ('9223372036854775808', 1)):
            output.write_bytes(old)
            result = self.invoke(executable, source, output, chunk, cap)
            self.assertEqual(result.returncode, 4, result.stderr)
            self.assertEqual(result.stdout, b'')
            self.assertEqual(output.read_bytes(), old)
            self.assertEqual(source.read_bytes(), data)
        result = self.invoke(executable, source, output, LIMIT, LIMIT)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b'', b''))
        self.assertEqual(output.read_bytes(), encode(rows_from(data)))
        for arguments in ((), (source,), (source, output), (source, output, 1),
                          (source, output, 1, 100, 'extra')):
            self.assertEqual(self.invoke(executable, *arguments).returncode, 2)
        for alias in (source, source.parent / '.' / source.name):
            self.assertEqual(self.invoke(executable, source, alias, 1, 100).returncode, 4)
            self.assertEqual(source.read_bytes(), data)
        alias = self.root / 'hardlink.csv'
        os.link(source, alias)
        self.assertEqual(self.invoke(executable, source, alias, 1, 100).returncode, 4)
        self.assertEqual(source.read_bytes(), data)
        output.write_bytes(old)
        result = self.invoke(executable, self.root / 'missing.csv', output, 1, 100)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(output.read_bytes(), old)
        self.assertEqual(self.invoke(executable, source, self.root, 1, 100).returncode, 3)
        self.assertEqual(source.read_bytes(), data)

    def test_api_keeps_handles_open_and_raises_for_closed_or_readonly_streams(self):
        executable = self.ail_build('api', API)
        source, output = self.root / 'api-input.csv', self.root / 'api-output.csv'
        data = encode([['日本😀', 'a,b'], ['', 'tail']])
        source.write_bytes(data)
        result = self.invoke(executable, source, output)
        expected_rows = rows_from(data)
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (0, str(len(expected_rows)).encode() + b'\n' + encode(expected_rows), b''))
        self.assertEqual(output.read_bytes(), encode(expected_rows))
        self.assertEqual(source.read_bytes(), data)

        # Even an empty input must reject an already-closed output handle.
        empty_api = self.ail_build('empty-closed', 'use csv_rewrite_stream; fn main()->int {'
                                  'let reader=open_binary(sys.argv[1],"rb");'
                                  'let writer=open_binary(sys.argv[2],"rb");writer.close();'
                                  'try {try {csv_rewrite_stream(reader,writer,1,1);return 9;}'
                                  'except ValueError {return 0;}} finally {reader.close();}}')
        source.write_bytes(b'')
        result = self.invoke(empty_api, source, output)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b'', b''))

    def test_sourcefree_typed_binaryfile_object_matches_csv_oracle(self):
        provider = self.ail_build('rewrite-provider', PROVIDER, library=True)
        metadata = json.loads(Path(str(provider) + '.json').read_bytes())
        self.assertIn('binaryfile', json.dumps(metadata))
        relocated = self.root / 'relocated'; relocated.mkdir()
        moved = relocated / provider.name
        shutil.move(provider, moved); shutil.move(str(provider) + '.json', str(moved) + '.json')
        before = self.snapshot(moved)
        executable = self.ail_build('object-client', CONSUMER, moved)
        source, output = self.root / 'object-input.csv', self.root / 'object-output.csv'
        data = encode([[''], ['é😀', 'one\r\ntwo', '"quoted"'], ['last', '']])
        source.write_bytes(data)
        result = self.invoke(executable, source, output)
        expected_rows = rows_from(data)
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (0, str(len(expected_rows)).encode() + b'\n', b''))
        self.assertEqual(output.read_bytes(), encode(expected_rows))
        self.assertEqual(source.read_bytes(), data)
        self.assertEqual(self.snapshot(moved), before)


if __name__ == '__main__':
    unittest.main()
