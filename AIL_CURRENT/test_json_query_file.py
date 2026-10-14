"""Typed JSON file API checked against the independent CLI oracle."""
import json
import os
import shutil
import unittest

import test_ail_c_objects as support
import test_json_query_cli as oracle


@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'),
                     'installed C compiler required')
class JsonQueryFileTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    command = support.CObjectTests.command
    write = support.CObjectTests.write
    c_object = support.CObjectTests.c_object
    snapshot = support.CObjectTests.snapshot
    invoke = oracle.JsonQueryCliTests.invoke

    def result(self, executable, mode, source, output, pointers, expected):
        result = self.invoke(executable, mode, source, output, *pointers)
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (0, f'{expected[0]} {expected[1]}{os.linesep}'.encode(), b''))

    def success(self, executable, data, mode, pointers):
        source, output = self.root / '入力.json', self.root / 'output.json'
        source.write_bytes(data)
        output.write_bytes(b'old\0\xff')
        before = oracle.pin(source)
        if mode == 'batch':
            value = oracle.document(data)
            expected = ('[' + ','.join(oracle.render(oracle.selected(value, p))
                                       for p in pointers) + ']\n').encode()
        else:
            expected = oracle.expected_query(data, mode, pointers[0])
        self.result(executable, mode, source, output, pointers, (0, 0))
        self.assertEqual(output.read_bytes(), expected)
        self.assertEqual(oracle.pin(source), before)

    def check_successes(self, executable):
        data = ('{"a/b":{"~":[null,true,-0.00e+02,"日本😀\\u0000"]},'
                '"dup":1,"dup":2,"map":{"a":"first","b":"😀\\u0000","a":"last"},'
                '"rows":[' + ','.join('{"n":' + str((1 << 53) + i) +
                ',"s":"日本' + str(i) + '"}' for i in range(4097)) + ']}').encode()
        for pointer in ('', '/rows', '/rows/4096/n', '/a~1b/~0/2', '/a~1b/~0/3'):
            self.success(executable, data, 'extract', [pointer])
        self.success(executable, data, 'string-map', ['/map'])
        self.success(executable, data, 'batch',
                     ['/rows/4096/n', '/a~1b/~0/2', '/rows/0', '/rows/0', '/a~1b/~0/3'])
        self.success(executable, data, 'batch', [])
        for value in (b'null', b'[]', b'{}', b'-0', b'123.4500E-07',
                      ('9' * 10000 + 'e+999999').encode()):
            self.success(executable, value, 'extract', [''])
        self.success(executable, b'{}', 'string-map', [''])

    def check_failures(self, executable):
        source, output = self.root / 'source.json', self.root / 'protected.json'
        source.write_bytes(b'{"a":[0],"dup":1,"dup":2,"map":{"a":1}}')
        output.write_bytes(b'keep\0\xff')

        def refused(mode, pointers, expected, input_path=source, output_path=output):
            before = oracle.pin(source), oracle.pin(output)
            self.result(executable, mode, input_path, output_path, pointers, expected)
            self.assertEqual((oracle.pin(source), oracle.pin(output)), before)

        for mode, pointers in (('unknown', ['']), ('extract', []), ('extract', ['', '']),
                               ('string-map', []), ('string-map', ['', ''])):
            refused(mode, pointers, (1, 1))
        refused('extract', [''], (1, 1), output_path=source)
        alias_dir = self.root / 'alias'
        alias_dir.mkdir()
        for alias in (source.name, alias_dir / '..' / source.name):
            refused('extract', [''], (2, 1), output_path=alias)
        hardlink = self.root / 'hardlink.json'
        os.link(source, hardlink)
        refused('extract', [''], (2, 1), output_path=hardlink)
        self.assertEqual(hardlink.read_bytes(), source.read_bytes())
        refused('extract', [''], (2, 5), input_path=self.root / 'missing.json')
        refused('extract', [''], (2, 5), input_path='')
        refused('extract', [''], (3, 5), input_path=self.root)
        for pointers, error in ((['a'], 1), (['/a/~2'], 1), (['/dup'], 1),
                                 (['/a/00'], 1), (['/a/１'], 1), (['/missing'], 3),
                                 (['/a/1'], 3), (['/a/-'], 3),
                                 (['/a/' + '9' * 10000], 3)):
            refused('extract', pointers, (6, error))
        refused('string-map', ['/map'], (6, 1))
        refused('batch', ['/a/0', '/missing'], (6, 3))
        absent = self.root / 'absent.json'
        refused('batch', ['/a/0', '/missing'], (6, 3), output_path=absent)
        self.assertFalse(absent.exists())
        for data, expected in ((b'\xff', (4, 2)), (b'{"a":0,"late":"\xff"}', (4, 2)),
                               (b'', (5, 1)), (b'NaN', (5, 1)),
                               (b'{"a":0,"late":[1,]}', (5, 1)),
                               (b'"\\ud800"', (5, 1))):
            source.write_bytes(data)
            refused('extract', [''], expected)
            refused('extract', [''], expected, output_path=absent)
            self.assertFalse(absent.exists())
        source.write_bytes(b'{}')
        refused('extract', [''], (7, 5), output_path=self.root)
        refused('extract', [''], (7, 5), output_path=self.root / 'missing-parent' / 'out.json')

    def check_build(self, separate):
        names = oracle.SOURCE_NAMES
        originals = [oracle.EXAMPLES / name for name in names]
        before = list(map(oracle.pin, originals))
        native = self.c_object((oracle.EXAMPLES / 'file_identity.c').read_text(encoding='utf8'),
                               json.loads((oracle.EXAMPLES / 'file_identity.json').read_bytes()),
                               'file_api_identity')
        native_before = self.snapshot(native)
        copied = [self.root / path.name for path in originals if path.suffix == '.ail']
        for path in copied:
            shutil.copy2(oracle.EXAMPLES / path.name, path)
        copied_before = list(map(oracle.pin, copied))
        entry = self.write('query_file_harness.ail', '''use json_query_file;
fn main()->int {
    let result:JsonQueryResult=json_query_file(sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4:]);
    print(result.stage,result.error);
    return 0;
}
''')
        if not separate:
            checked = self.command('api', 'json_query_file', '--symbol', 'json_query_file', '--types-used',
                                   '--object', native)
            self.assertEqual(checked.returncode, 0, checked.stderr.decode(errors='replace'))
            api = json.loads(checked.stdout)['interface']
            self.assertEqual([item['name'] for item in api['structs']], ['JsonQueryResult'])
            self.assertEqual(len(api['functions']), 1)
            self.assertEqual(api['functions'][0], dict(name='json_query_file', parameters=[
                dict(name=name, type=kind, kind='positional', default=None)
                for name, kind in [('mode', 'str'), ('input', 'str'), ('output', 'str'),
                                   ('pointers', 'list[str]')]], returns='JsonQueryResult'))
        executable = self.root / 'query_file.exe'
        result = self.command('compile', entry, '--object', native,
                              *(('--separate',) if separate else ()), '-o', executable)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        self.check_successes(executable)
        self.check_failures(executable)
        self.assertEqual(self.snapshot(native), native_before)
        self.assertEqual(list(map(oracle.pin, originals)), before)
        self.assertEqual(list(map(oracle.pin, copied)), copied_before)

    def test_ordinary_typed_file_api(self):
        self.check_build(False)

    def test_separate_typed_file_api(self):
        self.check_build(True)


if __name__ == '__main__':
    unittest.main()