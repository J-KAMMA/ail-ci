"""Syntax-only context, exact boundaries, and read-only CLI contracts."""
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import ail_chatgpt
from ail_source_context import context, compact_context, expand_context
from ail_source_edit import replace_body


def digest(source):
    return hashlib.sha256(source).hexdigest()


class SourceContextTests(unittest.TestCase):
    def test_hash_binds_edit_and_rejects_stale_source(self):
        source = b'fn chosen()->int {return 1;} fn main()->int {return chosen();}'
        report = context(source, 'chosen')
        self.assertEqual(report['schema'], 'ail.context/1')
        self.assertEqual(report['target'], 'chosen')
        self.assertEqual(report['source_sha256'], digest(source))
        self.assertEqual(report['body_sha256'], digest(b'return 1;'))
        self.assertTrue(report['syntax_verified'])
        for key in ('type_verified', 'link_verified', 'runtime_verified'):
            self.assertFalse(report[key])
        changed = replace_body(source, 'chosen', b'return 2;', report['source_sha256'])
        self.assertEqual(changed, source.replace(b'return 1;', b'return 2;'))
        with self.assertRaises(ValueError):
            replace_body(changed, 'chosen', b'return 3;', report['source_sha256'])

    def test_unicode_crlf_and_braces_return_exact_inner_body(self):
        body = '\r\n # 日本 } {\r\n let s = """日本\u2028} {""";\r\n if true {return s;} else {return "}";}\r\n'.encode()
        source = b'fn chosen()->str {' + body + b'}\r\nfn other()->int {return 9;}\r\n'
        report = context(source, 'chosen', include_body=True)
        self.assertEqual(report['body'], body.decode('utf8'))
        self.assertEqual(report['body_sha256'], digest(body))
        self.assertNotIn('body', context(source, 'chosen'))

    def test_unrelated_large_body_is_omitted_and_context_is_smaller(self):
        unrelated = b'let unused = "' + b'UNSELECTED_BODY_' * 2000 + b'"; return 9;'
        source = b'fn chosen()->int {return 1;} fn other()->int {' + unrelated + b'}'
        report = context(source, 'chosen')
        encoded = json.dumps(report).encode()
        self.assertNotIn(b'UNSELECTED_BODY_', encoded)
        self.assertLess(len(encoded), len(source))
        self.assertEqual([item['name'] for item in report['interface']['functions']], ['chosen'])

    def test_type_invalid_body_still_readable_and_hash_editable(self):
        source = b'fn chosen()->int {return "wrong";} fn main()->int {return chosen();}'
        report = context(source, 'chosen', include_body=True)
        self.assertEqual(report['body'], 'return "wrong";')
        self.assertFalse(report['type_verified'])
        self.assertEqual(replace_body(source, 'chosen', b'return 1;', report['source_sha256']),
                         source.replace(b'return "wrong";', b'return 1;'))

    def test_local_signatures_imports_and_unresolved_calls(self):
        source = b'use absent; fn local(x:int)->int {return x;} fn chosen(x:int)->int {print(x); imported(x); return local(x)+missing(x);} fn untouched()->int {return 9;}'
        report = context(source, 'chosen')
        self.assertEqual(report['imports'], ['absent'])
        self.assertEqual({item['name'] for item in report['interface']['functions']}, {'chosen', 'local'})
        self.assertEqual(set(report['other_call_expressions']), {'print', 'imported', 'missing'})
        self.assertNotIn('body', report)

    def test_qualified_method_exposes_receiver_and_reachable_structs(self):
        source = b'struct Box { x:int; } struct Other { y:int; } fn value()->int {return 4;} impl Box {fn value(self)->int {return self.x;}}'
        report = context(source, 'Box.value')
        self.assertEqual(report['receiver_owner'], 'Box')
        selected = report['interface']['functions']
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]['parameters'][0]['type'], 'Box')
        self.assertIn('receiver', report['interface']['types'])
        self.assertEqual([item['name'] for item in report['interface']['structs']], ['Box'])
        self.assertEqual(report['body_sha256'], digest(b'return self.x;'))

    def test_body_constructor_exposes_fields_even_with_scalar_return(self):
        source=b'struct Box { x:int; } fn chosen()->int {let box=Box(1);return box.x;}'
        report=context(source,'chosen')
        functions={item['name']:item for item in report['interface']['functions']}
        self.assertEqual(functions['Box']['returns'],'Box')
        self.assertEqual([p['name'] for p in functions['Box']['parameters']],['x'])
        self.assertEqual([item['name'] for item in report['interface']['structs']],['Box'])
        self.assertNotIn('Box',report['other_call_expressions'])
        self.assertFalse(report['type_verified'])
    def test_empty_missing_invalid_syntax_and_utf8_are_refused(self):
        for source, symbol in [(b'', 'chosen'), (b'fn chosen()->int {return 1;}', 'missing'),
                               (b'fn chosen()->int {let x = ;}', 'chosen'), (b'\xff', 'chosen')]:
            with self.subTest(source=source, symbol=symbol), self.assertRaises(ValueError):
                context(source, symbol)


class SourceContextCLITests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='ail-context-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'source.ail'
        self.source.write_bytes(b'fn chosen()->int {return 1;}')

    def invoke(self, source=None, symbol='chosen', extra=()):
        before = {path.name: path.read_bytes() for path in self.root.iterdir()}
        out, err = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, {'PATH': ''}), patch.object(ail_chatgpt.subprocess, 'run',
                side_effect=AssertionError('context must not launch a process')), redirect_stdout(out), redirect_stderr(err):
            status = ail_chatgpt.main(['context', str(source or self.source), '--symbol', symbol, *extra])
        self.assertEqual(err.getvalue(), '')
        self.assertEqual({path.name: path.read_bytes() for path in self.root.iterdir()}, before)
        return status, json.loads(out.getvalue())

    def test_success_is_read_only_without_toolchain(self):
        status, report = self.invoke(extra=('--include-body',))
        self.assertEqual(status, 0, report)
        self.assertEqual(report['source_sha256'], digest(self.source.read_bytes()))
        self.assertEqual(report['body'], 'return 1;')

    def test_compact_cli_matches_default_context(self):
        status, original = self.invoke(extra=('--include-body',))
        packed_status, packed = self.invoke(extra=('--include-body', '--compact'))
        self.assertEqual((status, packed_status), (0, 0))
        self.assertEqual(expand_context(packed), original)
        self.assertNotIn('parameter_columns', original)
        self.assertEqual(original['schema'], 'ail.context/1')

    def test_invalid_typed_body_context_can_drive_checked_edit(self):
        self.source.write_bytes(b'fn chosen()->int {return "wrong";} fn main()->int {return chosen();}')
        status, report = self.invoke()
        self.assertEqual(status, 0, report)
        body = self.root / 'body.ail'
        output = self.root / 'candidate.ail'
        body.write_bytes(b'return 1;')
        original = self.source.read_bytes()
        stream = io.StringIO()
        with patch.dict(os.environ, {'PATH': ''}), patch.object(ail_chatgpt.subprocess, 'run',
                side_effect=AssertionError('edit must not launch a process')), redirect_stdout(stream):
            status = ail_chatgpt.main(['edit', str(self.source), '--symbol', 'chosen', '--base-sha256',
                                      report['source_sha256'], '--body', str(body), '-o', str(output)])
        self.assertEqual(status, 0, stream.getvalue())
        self.assertEqual(output.read_bytes(), original.replace(b'return "wrong";', b'return 1;'))
        self.assertEqual(self.source.read_bytes(), original)

    def test_failure_is_structured_exit_two_without_writes(self):
        wrong_suffix = self.root / 'source.txt'
        wrong_suffix.write_bytes(self.source.read_bytes())
        for source, symbol in [(wrong_suffix, 'chosen'), (self.root / 'missing.ail', 'chosen'),
                               (self.source, 'missing')]:
            with self.subTest(source=source, symbol=symbol):
                status, report = self.invoke(source, symbol)
                self.assertEqual(status, 2, report)
                self.assertEqual(report['schema'], 'ail.context/1')
                self.assertEqual(report['status'], 'failed')
                self.assertTrue(report['error'])
        for invalid in (b'', b'\xff', b'fn chosen()->int {let x = ;}'):
            self.source.write_bytes(invalid)
            status, report = self.invoke()
            self.assertEqual(status, 2, report)


class CompactContextTests(unittest.TestCase):
    def test_roundtrip_keeps_unknown_kinds_defaults_and_receiver(self):
        import ast
        report = context(b'struct Box { x:int; } impl Box {fn value(self)->int {return self.x;}}',
                         'Box.value', include_body=True)
        extra = ail_chatgpt._source_interface(ast.parse(
            'def unknown(a, /, b: int = 3, *args, option=None, **kwargs): pass'))
        report['interface']['functions'].extend(extra['functions'])
        original = json.loads(json.dumps(report))
        packed = compact_context(report)
        self.assertEqual(report, original)
        self.assertEqual(expand_context(json.loads(json.dumps(packed))), original)
        self.assertEqual(packed['receiver_owner'], 'Box')
        self.assertEqual(packed['interface']['functions'][0]['parameters'][0],
                         ['self', 'Box', 'positional', None])

    def test_malformed_transport_is_refused(self):
        packed = compact_context(context(b'fn chosen(x:int)->int {return x;}', 'chosen'))
        rows = [0, [0], [['x']], [['x', 0, 'positional', None]],
                [['x', 'int', 'invalid', None]], [['x', 'int', 'positional', False]]]
        for parameters in rows:
            value = json.loads(json.dumps(packed))
            value['interface']['functions'][0]['parameters'] = parameters
            with self.subTest(parameters=parameters), self.assertRaises(ValueError):
                expand_context(value)
        packed['parameter_columns'] = ['name']
        with self.assertRaises(ValueError):
            expand_context(packed)


if __name__ == '__main__':
    unittest.main()