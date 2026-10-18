"""Exception repair guidance matches syntax, source positions and actual native behavior."""
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import ail_chatgpt
from ail_source_context import context
from ail_source_edit import replace_body


class ExceptionContextTests(unittest.TestCase):
    def check(self, source):
        with tempfile.TemporaryDirectory(prefix='ail-exception-context-') as directory:
            path = Path(directory) / 'source.ail'
            path.write_bytes(source)
            output = io.StringIO()
            with patch.dict(os.environ, {'PATH': ''}), patch.object(
                    ail_chatgpt.subprocess, 'run', side_effect=AssertionError('check launched a process')), redirect_stdout(output):
                status = ail_chatgpt.main(['check', str(path), '--library'])
            self.assertEqual(path.read_bytes(), source)
            report = json.loads(output.getvalue())
            self.assertFalse(report['runtime_verified'])
            self.assertFalse(report['link_verified'])
            return status, report

    def test_argument_and_keyword_errors_offer_same_exception_forms(self):
        for name, arguments in [('ValueError', '[1]'), ('KeyError', '[1]'),
                                ('OSError', 'message="bad"'), ('RuntimeError', '*[1]')]:
            with self.subTest(name=name, arguments=arguments):
                source = f'fn fail()->int {{raise {name}({arguments});return 0;}}'.encode()
                status, report = self.check(source)
                self.assertEqual(status, 1)
                diagnostic = report['diagnostics'][0]
                self.assertEqual(diagnostic['code'], 'type')
                hint = diagnostic['repair_hint']
                self.assertEqual(hint['raise_forms'], [f'raise {name};', f'raise {name}();', f'raise {name}("message");'])
                self.assertTrue(hint['exception_data'])
                self.assertEqual(hint['message_type'], 'str')
                self.assertTrue(hint['handler_binding'])
                self.assertEqual(hint['python_assertion_behavior'], 'raises AssertionError; uncaught: stderr AssertionError: message, exit 1')
                self.assertTrue(hint['assert_supported'])
                for form in hint['raise_forms']:
                    candidate = replace_body(source, 'fail', (form + 'return 0;').encode(),
                                             hashlib.sha256(source).hexdigest())
                    self.assertEqual(self.check(candidate)[0], 0)

    def test_nested_raise_location_preserves_unicode_crlf_columns(self):
        text = 'fn fail()->int {\r\n let label="日本"; if true {raise ValueError([1]);}\r\n return 0;\r\n}'
        _, report = self.check(text.encode())
        diagnostic = report['diagnostics'][0]
        self.assertEqual((diagnostic['line'], diagnostic['column'], diagnostic['function']),
                         (2, text.splitlines()[1].index('raise') + 1, 'fail'))
        self.assertEqual(diagnostic['location_kind'], 'source_statement')

    def test_unrelated_refusals_have_no_exception_repair_hint(self):
        for body in ('return "bad";', 'raise MissingError;', 'raise ValueError from KeyError;'):
            with self.subTest(body=body):
                status, report = self.check(f'fn fail()->int {{{body}}}'.encode())
                self.assertEqual(status, 1)
                self.assertNotIn('repair_hint', report['diagnostics'][0])

    def test_context_includes_exception_rules_before_a_raise_is_added(self):
        source = b'fn fail()->int {return 0;}'
        with patch.object(ail_chatgpt, '_source_check', side_effect=AssertionError('context type checked')):
            report = context(source, 'fail')
        self.assertEqual(report['source_sha256'], hashlib.sha256(source).hexdigest())
        self.assertFalse(report['type_verified'])
        self.assertFalse(report['runtime_verified'])
        rules = report['language_rules']['exceptions']
        self.assertEqual(rules['raise_examples'], ['raise ValueError;', 'raise ValueError();', 'raise ValueError("message");'])
        self.assertTrue(rules['exception_data'])
        self.assertEqual(rules['value_type'], 'exception')
        self.assertEqual(rules['fields'], {'kind': 'str', 'message': 'str'})
        self.assertFalse(rules['chaining'])
        self.assertTrue(rules['handler_binding'])
        self.assertTrue(rules['assert_supported'])
        self.assertEqual(rules['python_assertion_behavior'], 'raises AssertionError; uncaught: stderr AssertionError: message, exit 1')
        for form in rules['raise_examples']:
            candidate = replace_body(source, 'fail', (form + 'return 0;').encode(), report['source_sha256'])
            self.assertEqual(self.check(candidate)[0], 0)

    def test_api_and_context_supply_the_same_rules_without_a_toolchain(self):
        source = b'fn fail()->int {return 0;}'
        expected = context(source, 'fail')['language_rules']
        self.assertEqual(expected['syntax'], 'ail_block')
        output = io.StringIO()
        with patch.dict(os.environ, {'PATH': ''}), patch.object(
                ail_chatgpt.subprocess, 'run', side_effect=AssertionError('API launched a process')), redirect_stdout(output):
            status = ail_chatgpt.main(['api', 'binary_integers', '--symbol', 'unpack_integers'])
        report = json.loads(output.getvalue())
        self.assertEqual(status, 0, report)
        self.assertEqual(report['language_rules'], expected)
        self.assertEqual(report['interface']['functions'][0]['name'], 'unpack_integers')
        self.assertFalse(report['runtime_verified'])
        expected['exceptions']['raise_examples'].clear()
        self.assertTrue(context(source, 'fail')['language_rules']['exceptions']['raise_examples'])

    def test_native_raise_is_caught_but_an_assertion_error_is_not_a_value_error(self):
        for statement, expected in [('raise ValueError;', (0, b'caught', b'')),
                                    ('raise ValueError();', (0, b'caught', b'')),
                                    ('assert false,"bad";', (1, b'', b'AssertionError: bad' + os.linesep.encode()))]:
            with self.subTest(statement=statement), tempfile.TemporaryDirectory(prefix='ail-exception-native-') as directory:
                root = Path(directory)
                if statement.startswith('assert'):
                    source = root / 'main.ail'
                    text = 'def main()->int:\n    try:\n        assert False,"bad"\n    except ValueError:\n        write_stdout_bytes(b"caught")\n        return 0\n    return 9\nmain()\n'
                else:
                    source = root / 'main.ail'
                    text = ('fn main()->int {try {' + statement +
                            '} except ValueError {write_stdout_bytes(b"caught");return 0;}return 9;}')
                source.write_text(text, encoding='utf8')
                binary = root / ('app.exe' if os.name == 'nt' else 'app')
                build = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(ail_chatgpt.ROOT / 'ail_chatgpt.py'),
                                        'compile', str(source), '-o', str(binary)], capture_output=True, timeout=120)
                self.assertEqual(build.returncode, 0, build.stderr.decode(errors='replace')[:2048])
                result = subprocess.run([str(binary)], capture_output=True, timeout=30)
                self.assertEqual((result.returncode, result.stdout, result.stderr), expected)


if __name__ == '__main__':
    unittest.main()
