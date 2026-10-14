"""Body-edit boundaries and CLI checks; native subprocesses are forbidden."""
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
from ail_source_edit import replace_body, run


def digest(source):
    return hashlib.sha256(source).hexdigest()


class ReplaceBodyTests(unittest.TestCase):
    def test_unicode_crlf_and_lexical_braces_preserve_surrounding_bytes(self):
        prefix = '# 日本語 { }\r\nfn chosen(x:int)->int {'.encode('utf8')
        old = '\r\n let s = """日本語 } { fn fake() { }""";\r\n # } {\r\n let d = {"}": {"{": 2}};\r\n if x > 0 { return x; } else { return 0; }\r\n'.encode('utf8')
        suffix = b'}\r\nfn untouched()->int { return 8; }\r\n'
        body = '\r\n let text = "日本語 }";\r\n if x > 1 { return x+1; } else { return 1; }\r\n'.encode('utf8')
        source = prefix + old + suffix
        self.assertEqual(replace_body(source, 'chosen', body, digest(source)), prefix + body + suffix)

    def test_multiline_return_and_unicode_line_separator_offsets(self):
        prefix=b'fn chosen()->str {'
        old='return """line\n日本\u2028} {\nend""";'.encode()
        suffix=b'}\nfn other()->int {return 1;}'
        source=prefix+old+suffix
        body=b'return "new";'
        self.assertEqual(replace_body(source,'chosen',body,digest(source)),prefix+body+suffix)
    def test_only_qualified_method_changes(self):
        prefix = b'struct Box { x:int; }\nfn value()->int {return 4;}\nimpl Box { fn value(self)->int {'
        suffix = b'} fn other(self)->int {return self.x;} }\nfn main()->int {return value();}\n'
        source = prefix + b'return self.x;' + suffix
        body = b' return self.x+1; '
        self.assertEqual(replace_body(source, 'Box.value', body, digest(source)), prefix + body + suffix)

    def test_stale_unknown_unicode_and_invalid_syntax(self):
        source = b'fn chosen()->int {return 1;}'
        cases = [(source, 'chosen', b'return 2;', '0'*64),
                 (source, 'missing', b'return 2;', digest(source)),
                 (source, 'chosen', b'\xff', digest(source)),
                 (b'\xff', 'chosen', b'return 2;', digest(b'\xff')),
                 (source, 'chosen', b'let x = ;', digest(source)),
                 (b'fn chosen()->int {return ;', 'chosen', b'return 2;', digest(b'fn chosen()->int {return ;'))]
        for arguments in cases:
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                replace_body(*arguments)

    def test_balanced_escape_cannot_inject_sibling(self):
        source = b'fn chosen()->int {return 1;} fn main()->int {return chosen();}'
        for body in (b'return 2;} fn injected()->int {return 9;} fn decoy()->int {return 3;',
                     b'return 2;} fn injected()->int {return 9;', b'return 2; }'):
            with self.subTest(body=body), self.assertRaises(ValueError):
                replace_body(source, 'chosen', body, digest(source))


class SourceEditCLITests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='ail-edit-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root/'source.ail'
        self.body = self.root/'body.ail'
        self.output = self.root/'edited.ail'
        self.source.write_bytes(b'fn helper(x:int)->int {return x+1;} fn main()->int {return helper(2);}')

    def edit(self, body=b'return x+2;', *, body_text=None, symbol='helper', output=None, base=None, extra=()):
        if body_text is None:
            self.body.write_bytes(body)
        before = self.source.read_bytes()
        arguments = ['edit', str(self.source), '--symbol', symbol, '--base-sha256',
                     base or digest(before), '-o', str(output or self.output),
                     *(['--body', str(self.body)] if body_text is None else ['--body-text', body_text]), *map(str, extra)]
        out, err = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, {'PATH': ''}), patch.object(ail_chatgpt.subprocess, 'run',
                side_effect=AssertionError('editing must not launch a process')), redirect_stdout(out), redirect_stderr(err):
            status = ail_chatgpt.main(arguments)
        self.assertEqual(err.getvalue(), '')
        self.assertEqual(self.source.read_bytes(), before)
        return status, json.loads(out.getvalue())

    def test_success_writes_new_checked_source_without_native_proof(self):
        before = self.source.read_bytes()
        status, report = self.edit()
        self.assertEqual(status, 0, report)
        self.assertEqual(self.output.read_bytes(), before.replace(b'return x+1;', b'return x+2;'))
        self.assertFalse(report['link_verified'])
        self.assertFalse(report['runtime_verified'])

    def test_body_text_unicode_multiline_preserves_outer_bytes(self):
        prefix = '# 日本語 😀\r\nfn helper(x:int)->int {'.encode('utf8')
        suffix = b'}\r\nfn main()->int {return helper(2);}\r\n'
        self.source.write_bytes(prefix + b'return x+1;' + suffix)
        body = '\r\n let text="日本語 😀 } {";\r\n return x+len(text);\r\n'
        status, report = self.edit(body_text=body)
        self.assertEqual(status, 0, report)
        self.assertEqual(report['schema'], 'ail.edit/1')
        self.assertEqual(self.output.read_bytes(), prefix + body.encode('utf8') + suffix)
        self.assertFalse(self.body.exists())
        self.assertFalse(report['link_verified'])
        self.assertFalse(report['runtime_verified'])

    def test_body_text_empty_void_body_is_supplied(self):
        prefix = '# 日本語 😀\r\nfn helper()->void {'.encode('utf8')
        suffix = b'}\r\nfn main()->int {helper();return 0;}\r\n'
        source = prefix + b'let value=1;' + suffix
        for inline in (False, True):
            with self.subTest(inline=inline):
                self.source.write_bytes(source)
                output = self.root / ('inline.ail' if inline else 'file.ail')
                status, report = self.edit(b'', body_text='' if inline else None, output=output)
                self.assertEqual(status, 0, report)
                self.assertEqual(report['schema'], 'ail.edit/1')
                self.assertEqual(report['candidate_check']['status'], 'passed')
                self.assertEqual(output.read_bytes(), prefix + suffix)
                self.assertFalse(report['link_verified'])
                self.assertFalse(report['runtime_verified'])

    def test_body_text_stale_sha_and_invalid_type_refuse_output(self):
        for body, base in [('return x+2;', '0'*64), ('return "bad";', None)]:
            with self.subTest(body=body, base=base):
                status, report = self.edit(body_text=body, base=base)
                self.assertNotEqual(status, 0, report)
                self.assertEqual(report['schema'], 'ail.edit/1')
                self.assertFalse(self.output.exists())
                self.assertFalse(self.body.exists())

    def test_body_source_required_and_mutually_exclusive(self):
        before = self.source.read_bytes()
        arguments = ['edit', str(self.source), '--symbol', 'helper',
                     '--base-sha256', digest(before), '-o', str(self.output)]
        for body_options in ([], ['--body', str(self.body), '--body-text', 'return x+2;']):
            with self.subTest(body_options=body_options), patch.dict(os.environ, {'PATH': ''}), \
                    patch.object(ail_chatgpt.subprocess, 'run', side_effect=AssertionError('no subprocess')), \
                    redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    ail_chatgpt.main(arguments + body_options)
                self.assertEqual(raised.exception.code, 2)
                self.assertEqual(self.source.read_bytes(), before)
                self.assertFalse(self.output.exists())

    def test_source_changed_during_check_refuses_output(self):
        from types import SimpleNamespace
        self.body.write_bytes(b'return x+2;')
        args=SimpleNamespace(source=self.source,body=self.body,output=self.output,symbol='helper',
            base_sha256=digest(self.source.read_bytes()),library=False,module=[],object=[],module_path=[])
        def check(options):
            report=dict(status='passed',source_sha256=digest(options.source.read_bytes()),diagnostics=[])
            self.source.write_bytes(b'fn main()->int {return 9;}')
            print(json.dumps(report))
            return 0
        status,report=run(args,check)
        self.assertEqual(status,2)
        self.assertIn('source changed',report['error'])
        self.assertFalse(self.output.exists())
    def test_type_invalid_candidate_and_unselected_function_rejected(self):
        for source, body in [(b'fn helper(x:int)->int {return x+1;} fn main()->int {return helper(2);}', b'return "bad";'),
                             (b'fn helper(x:int)->int {return x+1;} fn main()->int {return "bad";}', b'return x+2;')]:
            with self.subTest(source=source):
                self.source.write_bytes(source)
                status, report = self.edit(body)
                self.assertNotEqual(status, 0, report)
                self.assertFalse(self.output.exists())

    def test_stale_and_existing_outputs_preserve_bytes(self):
        status, report = self.edit(base='0'*64)
        self.assertNotEqual(status, 0, report)
        self.assertFalse(self.output.exists())
        self.output.write_bytes(b'keep existing output')
        for output in (self.output, self.source, self.source.parent/'.'/self.source.name):
            with self.subTest(output=output):
                status, report = self.edit(output=output)
                self.assertNotEqual(status, 0, report)
                self.assertEqual(self.output.read_bytes(), b'keep existing output')

    def test_hardlink_alias_is_refused(self):
        alias = self.root/'alias.ail'
        os.link(self.source, alias)
        before = alias.read_bytes()
        status, report = self.edit(output=alias)
        self.assertNotEqual(status, 0, report)
        self.assertEqual(alias.read_bytes(), before)

    def test_relative_import_and_library_mode(self):
        (self.root/'neighbor.ail').write_bytes(b'fn imported(x:int)->int {return x+3;}')
        self.source.write_bytes(b'use neighbor; fn helper(x:int)->int {return imported(x);}')
        status, report = self.edit(b'return imported(x)+1;', extra=('--library',))
        self.assertEqual(status, 0, report)
        self.assertEqual(self.output.read_bytes(), b'use neighbor; fn helper(x:int)->int {return imported(x)+1;}')


if __name__ == '__main__':
    unittest.main()