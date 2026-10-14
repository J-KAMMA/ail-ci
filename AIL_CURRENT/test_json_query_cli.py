"""JSON query CLI compared with an independent lexeme/member-preserving oracle."""
import json
import os
import re
import shutil
import unittest

import test_ail_c_objects as support
import test_integer_column_stats_cli as helpers


EXAMPLES = helpers.EXAMPLES
pin = helpers.pin
SOURCE_NAMES = ('json_text.ail', 'json_document.ail', 'json_tree.ail', 'json_pointer.ail',
                'string_map.ail', 'json_string_map.ail', 'json_query_main.ail', 'json_query_file.ail', 'cli_args.ail', 'json_pointer_batch.ail', 'json_pointer_scan.ail',
                'file_identity.ail', 'file_identity.c', 'file_identity.json')


class Number(str):
    pass


class Members(list):
    pass


def reject_constant(value):
    raise ValueError('invalid JSON literal: ' + value)


def document(data):
    value = json.loads(data.decode('utf8'), parse_int=Number, parse_float=Number,
                       object_pairs_hook=Members, parse_constant=reject_constant)
    def validate(node):
        if type(node) is str:
            if any(0xd800 <= ord(c) <= 0xdfff for c in node):
                raise ValueError('lone surrogate')
        elif isinstance(node, Members):
            for key, child in node:
                validate(key)
                validate(child)
        elif isinstance(node, list):
            for child in node:
                validate(child)
    validate(value)
    return value


def render(node):
    if isinstance(node, Number):
        return str(node)
    if isinstance(node, Members):
        return '{' + ','.join(json.dumps(key, ensure_ascii=False) + ':' + render(value)
                              for key, value in node) + '}'
    if isinstance(node, list):
        return '[' + ','.join(map(render, node)) + ']'
    return json.dumps(node, ensure_ascii=False, separators=(',', ':'))


def selected(node, pointer):
    if pointer == '':
        return node
    if not pointer.startswith('/'):
        raise ValueError('plain JSON pointer required')
    tokens = pointer[1:].split('/')
    if any(re.search(r'~(?:[^01]|$)', token) for token in tokens):
        raise ValueError('invalid pointer escape')
    for token in tokens:
        token = token.replace('~1', '/').replace('~0', '~')
        if isinstance(node, Members):
            matches = [value for key, value in node if key == token]
            if len(matches) > 1:
                raise ValueError('ambiguous member')
            if not matches:
                raise KeyError(token)
            node = matches[0]
        elif isinstance(node, list):
            if token == '-':
                raise KeyError(token)
            if not re.fullmatch(r'0|[1-9][0-9]*', token):
                raise ValueError('invalid array index')
            # Compare decimal length first, preserving the grammar check above.
            limit = str(len(node))
            if len(token) > len(limit) or len(token) == len(limit) and token >= limit:
                raise KeyError(token)
            node = node[int(token)]
        else:
            raise KeyError(token)
    return node


def expected_query(data, mode, pointer):
    value = selected(document(data), pointer)
    if mode == 'extract':
        return (render(value) + '\n').encode('utf8')
    if not isinstance(value, Members) or any(type(item) is not str for _, item in value):
        raise ValueError('object with direct string values required')
    return (json.dumps(dict(value), ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf8')


@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'),
                     'installed C compiler required')
class JsonQueryCliTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    command = support.CObjectTests.command
    write = support.CObjectTests.write
    c_object = support.CObjectTests.c_object
    snapshot = support.CObjectTests.snapshot
    invoke = helpers.IntegerColumnStatsCliTests.invoke
    refused = helpers.IntegerColumnStatsCliTests.refused

    def success(self, executable, data, mode='extract', pointer=''):
        source, output = self.root / '入力 document.json', self.root / 'selected.json'
        source.write_bytes(data)
        output.write_bytes(b'old output\0\xff')
        before = pin(source)
        result = self.invoke(executable, mode, source, output, pointer)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b'', b''))
        self.assertEqual(output.read_bytes(), expected_query(data, mode, pointer))
        self.assertEqual(pin(source), before)

    def check_outputs(self, executable):
        nested = ('{"a/b":{"~":{"": [null,true,-0.00e+02,"日本語😀\\u0000",[],{}]}},'
                  '"dup":1,"dup":2,"map":{"a":"first","b":"😀\\u0000","a":"last"}}').encode('utf8')
        for pointer in ('', '/a~1b/~0/', *('/a~1b/~0//' + str(i) for i in range(6))):
            self.success(executable, nested, pointer=pointer)
        self.success(executable, nested, 'string-map', '/map')
        for data in (b'null', b'true', b'false', b'[]', b'{}', b'""', b'"\\u0000\\n\\\\\\\""',
                     b'-0', b'123.4500E-07', ('9' * 10000 + 'e+999999').encode()):
            self.success(executable, data)
        self.success(executable, b'{}', 'string-map')
        self.success(executable, '{"日本語\\u0000":"値😀","":"","quote\\\"":"\\\\"}'.encode(), 'string-map')
        long_key = '😀' * 65537
        long_value = '日本語' * 65537
        data = json.dumps({long_key: long_value}, ensure_ascii=False).encode()
        self.success(executable, data)
        self.success(executable, data, 'string-map')
        huge = json.dumps({'blob': '😀' * 300000, 'target': ['ok']}, ensure_ascii=False).encode()
        self.assertGreater(len(huge), 1024 * 1024)
        self.success(executable, huge, pointer='/target')
        for count in (8191, 8192, 8193):
            # The root plus count-1 children gives this exact preorder node count.
            data = ('[' + ','.join(str(i) for i in range(count - 1)) + ']').encode()
            with self.subTest(nodes=count):
                self.success(executable, data)
                self.success(executable, data, pointer='/' + str(count - 2))

    def check_errors(self, executable):
        source, output = self.root / 'protected.json', self.root / 'protected output.json'
        source.write_bytes(b'{"a":[0],"dup":1,"dup":2,"map":{"a":1}}')
        output.write_bytes(b'preserve\0\xff')
        protected = (source, output)
        for args in ((), ('extract',), ('extract', source, output),
                     ('extract', source, output, '', 'extra'), ('unknown', source, output, ''),
                     ('extract', self.root / 'missing', output, ''),
                     ('extract', self.root, output, ''), ('extract', source, self.root, '')):
            self.refused(executable, args, protected)
        for mode, pointer in (('extract', 'a'), ('extract', '/a/~2'), ('extract', '/a/~'),
                              ('extract', '/missing'), ('extract', '/dup'), ('extract', '/a/00'),
                              ('extract', '/a/１'), ('extract', '/a/-'), ('extract', '/a/1'),
                              ('extract', '/a/0/x'), ('extract', '/a/' + '9' * 10000),
                              ('extract', '/a/' + '9' * 10000 + 'x'),
                              ('string-map', ''), ('string-map', '/map'), ('string-map', '/a')):
            with self.subTest(mode=mode, pointer=pointer[:24]):
                self.refused(executable, (mode, source, output, pointer), protected)
        for data in (b'', b'[] trailing', b'NaN', b'{"x":}', b'"\\ud800"', b'\xff',
                     b'[0,' * 200 + b'bad', b'{"target":0,"late":"\xff"}',
                     b'{"target":0,"late":[1,]}'):
            source.write_bytes(data)
            self.refused(executable, ('extract', source, output, ''), protected)
        absent = self.root / 'absent.json'
        self.refused(executable, ('extract', source, absent, ''), protected)
        self.assertFalse(absent.exists())
        source.write_bytes(b'{}')
        directory = self.root / 'alias directory'
        directory.mkdir(exist_ok=True)
        for alias in (source, source.name, directory / '..' / source.name):
            self.refused(executable, ('extract', source, alias, ''), protected)
        link = self.root / 'hardlink.json'
        os.link(source, link)
        self.assertTrue(os.path.samefile(source, link))
        self.refused(executable, ('extract', source, link, ''), (*protected, link))

    def check_build(self, separate):
        originals = [EXAMPLES / name for name in SOURCE_NAMES]
        before = list(map(pin, originals))
        native = self.c_object((EXAMPLES / 'file_identity.c').read_text(encoding='utf8'),
                               json.loads((EXAMPLES / 'file_identity.json').read_bytes()), 'identity_native')
        native_before = self.snapshot(native)
        copied = [self.root / path.name for path in originals if path.suffix == '.ail']
        for path in copied:
            shutil.copy2(EXAMPLES / path.name, path)
        copied_before = list(map(pin, copied))
        executable = self.root / ('query separate.exe' if separate else 'query ordinary.exe')
        result = self.command('compile', self.root / 'json_query_main.ail', '--object', native,
                              *(('--separate',) if separate else ()), '-o', executable)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        self.check_outputs(executable)
        self.check_errors(executable)
        self.assertEqual(self.snapshot(native), native_before)
        self.assertEqual(list(map(pin, originals)), before)
        self.assertEqual(list(map(pin, copied)), copied_before)

    def extra_cli(self):
        native=self.c_object((EXAMPLES/'file_identity.c').read_text(encoding='utf8'),
                             json.loads((EXAMPLES/'file_identity.json').read_text(encoding='utf8')),'identity_extra')
        entry=self.write('query_extra.ail',(EXAMPLES/'json_query_main.ail').read_text(encoding='utf8'))
        executable=self.root/'query_extra.exe'
        result=self.command('compile',entry,'--object',native,'-o',executable)
        self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace')[:4096])
        return executable

    def test_named_options_and_batch_complete_output(self):
        executable=self.extra_cli();source=self.root/'input.json';output=self.root/'batch.json'
        data=('{"a/b":{"~":[null,true,-0.00e+02,"日本😀\\u0000"]},"rows":['+
              ','.join('{"n":'+str((1<<53)+i)+',"s":"日本'+str(i)+'"}' for i in range(4097))+']}').encode()
        source.write_bytes(data);before=pin(source)
        pointers=['/rows/4096/n','/a~1b/~0/2','/a~1b/~0/3','/rows/0','/rows/0']
        value=document(data);expected=('['+','.join(render(selected(value,p)) for p in pointers)+']\n').encode()
        for arguments in (('batch',source,output,*pointers),
                          ('batch','--input='+str(source),'--output',output,'--',*pointers)):
            result=self.invoke(executable,*arguments)
            self.assertEqual((result.returncode,result.stdout,result.stderr),(0,b'',b''))
            self.assertEqual(output.read_bytes(),expected)
            self.assertEqual(pin(source),before)
        result=self.invoke(executable,'extract','--input',source,'--output',output,'--pointer=/a~1b/~0/3')
        self.assertEqual((result.returncode,result.stdout,result.stderr),(0,b'',b''))
        self.assertEqual(output.read_bytes(),expected_query(data,'extract','/a~1b/~0/3'))
        result=self.invoke(executable,'batch','--input',source,'--output',output)
        self.assertEqual((result.returncode,result.stdout,result.stderr),(0,b'',b''))
        self.assertEqual(output.read_bytes(),b'[]\n')
        result=self.invoke(executable,'--help')
        self.assertEqual((result.returncode,result.stdout),(0,b''));self.assertIn(b'usage:',result.stderr)

    def test_late_batch_error_and_invalid_options_preserve_files(self):
        executable=self.extra_cli();source=self.root/'safe.json';output=self.root/'old.json'
        source.write_bytes(b'{"a":[1,2]}');output.write_bytes(b'keep\0\xff');before=pin(source),pin(output)
        cases=(('batch',source,output,'/a/0','/missing'),
               ('extract','--input',source,'--output',output,'--pointer=/a','--pointer=/a/0'),
               ('extract','--input',source,'--output',output,'--unknown=x'),
               ('extract','--input',source,'--output'),
               ('extract','--input',source,'/a'),
               ('batch',source,source,'/a'))
        for args in cases:
            with self.subTest(args=args):
                result=self.invoke(executable,*args)
                self.assertEqual((result.returncode,result.stdout),(2,b''));self.assertTrue(result.stderr)
                self.assertEqual((pin(source),pin(output)),before)
    def test_ordinary_full_json_and_prewrite_refusals(self):
        self.check_build(False)

    def test_separate_full_json_and_prewrite_refusals(self):
        self.check_build(True)


if __name__ == '__main__':
    unittest.main()
