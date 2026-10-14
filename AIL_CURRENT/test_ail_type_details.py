"""Return mismatch metadata stays independent of messages and source attribution."""
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import sys
import unittest
from unittest.mock import patch

import ail_chatgpt
import test_ail_source_check as source_checks


class TypeDetailsTests(unittest.TestCase):
    setUp = source_checks.SourceCheckTests.setUp
    source = source_checks.SourceCheckTests.source

    def check(self, source, *args):
        with patch.object(ail_chatgpt.subprocess, 'Popen', side_effect=AssertionError('no subprocess')):
            return source_checks.SourceCheckTests.check(self, source, *args)

    def mismatch(self, text, expected, actual, message, *, function='bad'):
        source = self.source(text)
        status, report = self.check(source, '--library')
        self.assertEqual(status, 1, report)
        diagnostic, = report['diagnostics']
        self.assertEqual(diagnostic['code'], 'type')
        self.assertEqual(diagnostic['message'], message)
        self.assertEqual(diagnostic['type_details'], dict(operation='return', expected=expected, actual=actual))
        self.assertEqual(diagnostic['function'], function)
        self.assertEqual(diagnostic['path'], str(source))
        self.assertEqual(diagnostic['location_kind'], 'function_declaration')
        self.assertNotIn('__ail_checked_', json.dumps(diagnostic['type_details']))
        return diagnostic

    def test_scalar_and_float_list_types_use_public_names(self):
        cases = [('fn bad()->int {return "wrong";}', 'int', 'str',
                  'bad() return annotation int disagrees with inferred str'),
                 ('fn bad()->float {return 7;}', 'float', 'int',
                  'bad() return annotation float disagrees with inferred int'),
                 ('fn bad()->list[float] {return [1,2];}', 'list[float]', 'list[int]',
                  'bad() return annotation flist disagrees with inferred list')]
        for text, expected, actual, message in cases:
            with self.subTest(expected=expected):
                diagnostic = self.mismatch(text, expected, actual, message)
                self.assertEqual((diagnostic['line'], diagnostic['column']), (1, 1))

    def test_typed_dict_return_uses_known_parameter_type(self):
        self.mismatch('fn bad(value:dict[str,str])->dict[str,int] {return value;}',
                      'dict[str, int]', 'dict[str, str]',
                      'bad() typed dict return disagrees with its annotation')

    def test_bytes_list_return_has_public_element_types(self):
        self.mismatch('fn bad()->list[bytes] {return [1,2];}', 'list[bytes]', 'list[int]',
                      'bad() bytes list return disagrees with its annotation')

    def test_callable_return_retains_argument_and_result_types(self):
        cases = [('fn identity(x:int)->int {return x;}\nfn bad()->Callable[[int],float] {return identity;}',
                  'Callable[[int], float]', 'Callable[[int], int]'),
                 ('fn identity(x:float)->int {return int(x);}\nfn bad()->Callable[[int],int] {return identity;}',
                  'Callable[[int], int]', 'Callable[[float], int]')]
        for text, expected, actual in cases:
            with self.subTest(expected=expected, actual=actual):
                self.mismatch(text, expected, actual, 'bad() Callable return annotation disagrees with its body')

    def test_struct_list_return_uses_known_parameter_owner(self):
        self.mismatch('struct Box {value:int;}\nstruct Other {value:int;}\n'
                      'fn bad(values:list[Other])->list[Box] {return values;}',
                      'list[Box]', 'list[Other]',
                      'bad() struct list return type disagrees with its annotation')

    def test_struct_and_handle_list_types_use_public_names(self):
        self.mismatch('struct Box {value:int;} struct Other {value:int;} '
                      'fn bad(value:Other)->Box {return value;}', 'Box', 'Other',
                      "bad() return annotation ('obj', 'Box') disagrees with inferred ('obj', 'Other')")
        self.mismatch('fn bad(values:list[tcpsocket])->list[binaryfile] {return values;}',
                      'list[binaryfile]', 'list[tcpsocket]',
                      'bad() struct list return type disagrees with its annotation')

    def test_imported_function_and_method_keep_source_attribution(self):
        module = self.source('# 日本語😀\nfn bad()->int {return "wrong";}\n', 'part.ail')
        entry = self.source('use part;\nfn main()->int {return 0;}')
        status, report = self.check(entry)
        self.assertEqual(status, 1, report)
        diagnostic, = report['diagnostics']
        self.assertEqual(diagnostic['type_details'], dict(operation='return', expected='int', actual='str'))
        self.assertEqual((diagnostic['path'], diagnostic['function'], diagnostic['line'], diagnostic['column']),
                         (str(module), 'bad', 2, 1))
        method = self.source('struct Box {value:int;}\nimpl Box {\n  fn bad(self)->str {return self.value;}\n}\nfn main()->int {return 0;}')
        status, report = self.check(method)
        self.assertEqual(status, 1, report)
        diagnostic, = report['diagnostics']
        self.assertEqual(diagnostic['type_details'], dict(operation='return', expected='str', actual='int'))
        self.assertEqual((diagnostic['path'], diagnostic['function'], diagnostic['line'], diagnostic['column']),
                         (str(method), 'Box.bad', 3, 3))
        self.assertEqual(diagnostic['location_kind'], 'function_declaration')

    def test_unrelated_errors_and_success_do_not_gain_return_details(self):
        # Literal dict/list construction can fail before return inference settles.
        cases = [('fn bad()->dict[str,int] {return {"x":"wrong"};}', ('--library',), 1),
                 ('struct Box {value:int;} struct Other {value:int;} fn bad()->list[Box] {return [Other(1)];}', ('--library',), 1),
                 ('fn bad()->list[Unknown] {return [1];}', ('--library',), 1),
                 ('fn bad(value:dict[float,int])->int {return 0;}', ('--library',), 1),
                 ('fn main()->int {return missing(1);}', (), 1),
                 ('fn f()->int {let ignored=1;} fn main()->int {return f();}', (), 1),
                 ('fn main()->int {return 1 + * 2;}', (), 1),
                 ('fn main()->int {return 0;}', ('--symbol', 'main'), 2),
                 ('fn main()->int {return 0;}', (), 0)]
        for text, args, expected_status in cases:
            with self.subTest(text=text):
                status, report = self.check(self.source(text), *args)
                self.assertEqual(status, expected_status, report)
                self.assertNotIn('type_details', report)
                for diagnostic in report['diagnostics']:
                    self.assertNotIn('type_details', diagnostic)

    def test_tuple_return_actual_is_unknown_without_internal_type_leak(self):
        source = self.source('fn bad()->int {return (1,2);}')
        status, report = self.check(source, '--library')
        self.assertEqual(status, 1, report)
        diagnostic, = report['diagnostics']
        self.assertEqual(diagnostic['type_details'], dict(operation='return', expected='int', actual=None))
        self.assertEqual((diagnostic['code'], diagnostic['function'], diagnostic['path']), ('type', 'bad', str(source)))
        self.assertEqual(diagnostic['location_kind'], 'function_declaration')
        self.assertTrue(diagnostic['message'])

    def test_return_metadata_does_not_depend_on_message_text(self):
        with patch.object(sys, 'path', [str(ail_chatgpt.ROOT / 'python/pkg-v12'), *sys.path]):
            import pyfunc
        original = pyfunc._return_type_error
        def opaque(*args, **kwargs):
            error = original(*args, **kwargs)
            error.args = ('opaque failure',)
            return error
        with patch.object(pyfunc, '_return_type_error', side_effect=opaque):
            source = self.source('fn bad()->int {return "wrong";}')
            status, report = self.check(source, '--library')
        self.assertEqual(status, 1, report)
        diagnostic, = report['diagnostics']
        self.assertEqual(diagnostic['message'], 'opaque failure')
        self.assertEqual(diagnostic['type_details'], dict(operation='return', expected='int', actual='str'))
        self.assertEqual((diagnostic['path'], diagnostic['function']), (str(source), 'bad'))

    def test_repair_context_keeps_diagnostic_and_direct_edit_handoff(self):
        source = self.source('# 日本語😀\nfn main()->int {return "wrong";}\n')
        before = source.read_bytes()
        status, plain = self.check(source)
        status_with_context, checked = self.check(source, '--repair-context')
        self.assertEqual((status, status_with_context), (1, 1))
        self.assertEqual(checked['diagnostics'], plain['diagnostics'])
        self.assertEqual(checked['repair_context']['status'], 'available')
        context_file = self.root / 'checked.json'
        context_file.write_text(json.dumps(checked, ensure_ascii=False), encoding='utf8')
        output = self.root / 'candidate.ail'
        out, err = io.StringIO(), io.StringIO()
        with patch.object(ail_chatgpt.subprocess, 'run', side_effect=AssertionError('no subprocess')), \
                patch.object(ail_chatgpt.subprocess, 'Popen', side_effect=AssertionError('no subprocess')), \
                redirect_stdout(out), redirect_stderr(err):
            status = ail_chatgpt.main(['edit', str(source), '--symbol', 'main',
                                      '--base-sha256', hashlib.sha256(before).hexdigest(),
                                      '--body-text', 'return 7;', '--context', str(context_file), '-o', str(output)])
        self.assertEqual(err.getvalue(), '')
        report = json.loads(out.getvalue())
        self.assertEqual(status, 0, report)
        self.assertEqual(report['candidate_check']['status'], 'passed')
        self.assertEqual(report['candidate_check']['diagnostics'], [])
        self.assertEqual(output.read_bytes(), before.replace(b'return "wrong";', b'return 7;'))
        self.assertEqual(source.read_bytes(), before)
        self.assertFalse(report['link_verified'])
        self.assertFalse(report['runtime_verified'])


if __name__ == '__main__':
    unittest.main()
