"""Argument metadata follows bound signatures without changing caller diagnostics."""
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import sys
import unittest
from unittest.mock import patch

import ail_chatgpt
import test_ail_source_check as source_checks


class ArgumentTypeDetailsTests(unittest.TestCase):
    setUp = source_checks.SourceCheckTests.setUp
    source = source_checks.SourceCheckTests.source

    def check(self, source, *args):
        with patch.object(ail_chatgpt.subprocess, 'Popen', side_effect=AssertionError('no subprocess')):
            return source_checks.SourceCheckTests.check(self, source, *args)

    def mismatch(self, text, expected, actual, message, *, callee='take', parameter='value', index=0):
        source = self.source(text)
        status, report = self.check(source)
        self.assertEqual(status, 1, report)
        diagnostic, = report['diagnostics']
        self.assertEqual(diagnostic['code'], 'type')
        self.assertEqual(diagnostic['message'], message)
        self.assertEqual(diagnostic['type_details'], dict(operation='argument', callee=callee,
                         parameter=parameter, parameter_index=index, expected=expected, actual=actual))
        self.assertEqual((diagnostic['path'], diagnostic['function']), (str(source), 'main'))
        self.assertEqual(diagnostic['location_kind'], 'source_statement')
        self.assertNotIn('__ail_checked_', json.dumps(diagnostic['type_details']))
        return diagnostic

    def test_numeric_argument_details_include_nonnumeric_and_narrowing(self):
        self.mismatch('fn take(value:int)->int {return value;} fn main()->int {return take("wrong");}',
                      'int', 'str', 'passing str where take() wants int')
        # Keywords reach the existing call guard without positional inference overriding it.
        self.mismatch('fn take(value:int)->int {return value;} fn main()->int {return take(value=1.5);}',
                      'int', 'float', "passing a float to take(), whose 'value' is an int64; this language has no implicit truncation.\n  write instead: `//` where the float came from `/` (`take(n // 2)`), otherwise `take(int(x))` (truncates toward zero), or annotate 'value' `float`")
        self.mismatch('fn take(value:int)->int {return value;} fn main()->int {let parts:list[bytes]=[b"x"];return take(value=parts);}',
                      'int', 'list[bytes]', 'bytes-list parameter across a function boundary is unsupported; pass joined bytes or an int')

    def test_reversed_keywords_report_bound_parameter_and_source_order(self):
        prefix = 'fn take(left:int,right:int)->int {return left+right;}\nfn main()->int {return '
        diagnostic = self.mismatch(prefix + 'take(right="wrong",left=1);}', 'int', 'str',
                                   'passing str where take() wants int', parameter='right', index=1)
        self.assertEqual((diagnostic['line'], diagnostic['column']), (2, 17))
        # Both arguments fail; the first expression in source order remains the diagnostic.
        self.mismatch(prefix + 'take(right=1.5,left="wrong");}', 'int', 'float',
                      "passing a float to take(), whose 'right' is an int64; this language has no implicit truncation.\n  write instead: `//` where the float came from `/` (`take(n // 2)`), otherwise `take(int(x))` (truncates toward zero), or annotate 'right' `float`",
                      parameter='right', index=1)

    def test_callable_and_typed_map_argument_types_are_public(self):
        self.mismatch('fn take(cb:Callable[[int],int])->int {return cb(1);} '
                      'fn other(x:float)->int {return int(x);} fn main()->int {return take(other);}',
                      'Callable[[int], int]', 'Callable[[float], int]',
                      'function argument requires exactly matching Callable signature', parameter='cb')
        self.mismatch('fn take(value:dict[str,int])->int {return len(value);} '
                      'fn main()->int {let value:dict[str,str]={"x":"wrong"};return take(value);}',
                      'dict[str, int]', 'dict[str, str]', 'passing a typed dict to a parameter of another kind')

    def test_managed_reference_types_retain_names(self):
        self.mismatch('struct Box {value:int;} struct Other {value:int;} '
                      'fn take(value:Box)->int {return value.value;} fn main()->int {return take(Other(1));}',
                      'Box', 'Other', "passing ('obj', 'Other') where take() wants ('obj', 'Box')")
        self.mismatch('fn take(value:bytearray)->int {return len(value);} fn main()->int {return take(value=7);}',
                      'bytearray', 'int', 'passing int where take() wants bytearray')

    def test_string_and_string_bytes_list_argument_rejections(self):
        cases = [('str', 'passing a number where take() wants a str'),
                 ('list[str]', 'passing a number where take() wants a list of str'),
                 ('list[bytes]', 'take() requires a bytes list')]
        for kind, message in cases:
            with self.subTest(kind=kind):
                self.mismatch('fn take(value:' + kind + ')->int {return len(value);} '
                              'fn main()->int {return take(value=7);}', kind, 'int', message)

    def test_imported_caller_and_method_callee_keep_separate_attribution(self):
        module = self.source('# 日本語😀\nfn take(value:int)->int {return value;}\n'
                             'fn wrong()->int {\n  return take("wrong");\n}\n', 'part.ail')
        entry = self.source('use part;\nfn main()->int {return wrong();}')
        status, report = self.check(entry)
        self.assertEqual(status, 1, report)
        diagnostic, = report['diagnostics']
        self.assertEqual(diagnostic['type_details'], dict(operation='argument', callee='take',
                         parameter='value', parameter_index=0, expected='int', actual='str'))
        self.assertEqual((diagnostic['path'], diagnostic['function'], diagnostic['line'], diagnostic['column']),
                         (str(module), 'wrong', 4, 3))
        self.source('struct Box {value:int;}\nimpl Box {fn take(self,value:int)->int {return self.value+value;}}', 'method.ail')
        entry = self.source('use method;\nfn main()->int {\n  let box=Box(1);\n  return box.take("wrong");\n}')
        status, report = self.check(entry)
        self.assertEqual(status, 1, report)
        diagnostic, = report['diagnostics']
        self.assertEqual(diagnostic['type_details'], dict(operation='argument', callee='Box.take',
                         parameter='value', parameter_index=1, expected='int', actual='str'))
        self.assertEqual((diagnostic['path'], diagnostic['function'], diagnostic['line'], diagnostic['column']),
                         (str(entry), 'main', 4, 3))
        self.assertEqual(diagnostic['location_kind'], 'source_statement')
        self.assertEqual(diagnostic['message'], 'passing str where Box__take() wants int')

    def test_dynamic_callable_and_unknown_actual_do_not_invent_names(self):
        source = self.source('fn invoke(cb:Callable[[int],int])->int {return cb("wrong");} fn main()->int {return 0;}')
        status, report = self.check(source)
        self.assertEqual(status, 1, report)
        diagnostic, = report['diagnostics']
        self.assertEqual(diagnostic['type_details'], dict(operation='argument', callee='<callback>',
                         parameter='0', parameter_index=0, expected='int', actual='str'))
        self.assertEqual((diagnostic['path'], diagnostic['function']), (str(source), 'invoke'))
        self.mismatch('fn take(value:int)->int {return value;} fn main()->int {return take(unknown);}',
                      'int', None, 'passing None where take() wants int')

    def test_widening_passes_and_arity_or_unsupported_errors_have_no_details(self):
        valid = ['fn take(value:float)->float {return value;} fn main()->int {print(take(value=1));return 0;}',
                 'fn take(value:float)->float {return value;} fn main()->int {print(take(1));return 0;}',
                 'fn take(value:float)->float {return value;} fn main()->int {print(take(1));print(take(1.5));return 0;}',
                 'fn inner(value:float)->float {return value+0.5;} fn outer(value:int)->float {return inner(value);} '
                 'fn main()->int {print(outer(1));return 0;}']
        for text in valid:
            with self.subTest(valid=text):
                status, report = self.check(self.source(text))
                self.assertEqual(status, 0, report)
                self.assertEqual(report['diagnostics'], [])
        cases = ['fn take(value:int)->int {return value;} fn main()->int {return take();}',
                 'fn take(value:int)->int {return value;} fn main()->int {return take(1,2);}',
                 'fn take(value:int)->int {return value;} fn main()->int {return take(other=1);}',
                 'fn take(value:list[int])->int {return len(value);} fn main()->int {return take(value=7);}',
                 'fn take(value:dict[float,int])->int {return 0;} fn main()->int {return 0;}']
        for text in cases:
            with self.subTest(text=text):
                status, report = self.check(self.source(text))
                self.assertEqual(status, 1, report)
                for diagnostic in report['diagnostics']:
                    self.assertNotIn('type_details', diagnostic)

    def test_signature_override_conflicts_report_callee_declaration(self):
        cases = [('int', '1.5', 'float'), ('str', '7', 'int'),
                 ('list[str]', '7', 'int'), ('list[bytes]', '7', 'int')]
        for expected, expression, actual in cases:
            with self.subTest(expected=expected):
                source = self.source('fn take(value:' + expected + ')->int {return 0;}\n'
                                     'fn main()->int {return take(' + expression + ');}')
                status, report = self.check(source)
                self.assertEqual(status, 1, report)
                diagnostic, = report['diagnostics']
                self.assertEqual(diagnostic['type_details'], dict(operation='parameter', inference_scope='signature_override',
                    callee='take', parameter='value', parameter_index=0, expected=expected, actual=actual))
                self.assertEqual((diagnostic['path'], diagnostic['function'], diagnostic['line'], diagnostic['column']),
                                 (str(source), 'take', 1, 1))
                self.assertEqual(diagnostic['location_kind'], 'function_declaration')

    def test_signature_override_second_parameter_index_is_not_call_order(self):
        source = self.source('fn take(first:int,second:int)->int {return first+second;}\n'
                             'fn main()->int {return take(1,1.5);}')
        status, report = self.check(source)
        self.assertEqual(status, 1, report)
        diagnostic, = report['diagnostics']
        self.assertEqual(diagnostic['type_details'], dict(operation='parameter', inference_scope='signature_override',
                         callee='take', parameter='second', parameter_index=1, expected='int', actual='float'))
        self.assertEqual((diagnostic['function'], diagnostic['line'], diagnostic['column'], diagnostic['location_kind']),
                         ('take', 1, 1, 'function_declaration'))

    def test_imported_signature_override_uses_import_declaration(self):
        module = self.source('# 日本語😀\nfn take(value:int)->int {return value;}\n', 'part.ail')
        entry = self.source('use part; fn main()->int {return take(1.5);}')
        status, report = self.check(entry)
        self.assertEqual(status, 1, report)
        diagnostic, = report['diagnostics']
        self.assertEqual(diagnostic['type_details'], dict(operation='parameter', inference_scope='signature_override',
                         callee='take', parameter='value', parameter_index=0, expected='int', actual='float'))
        self.assertEqual((diagnostic['path'], diagnostic['function'], diagnostic['line'], diagnostic['column']),
                         (str(module), 'take', 2, 1))
        self.assertEqual(diagnostic['location_kind'], 'function_declaration')
        self.assertEqual(diagnostic['message'], "'value' is annotated int in the source, but the caller also supplies float; refusing rather than silently choosing one.\n  write instead: pass `int(x)` at the call (truncates toward zero), use `//` where the float came from `/`, or annotate the parameter `float`")

    def test_multiple_call_evidence_keeps_parameter_and_argument_scopes(self):
        source = self.source('fn take(value:int)->int {return value;}\n'
                             'fn main()->int {let first=take(1);return take(1.5);}')
        status, report = self.check(source)
        self.assertEqual(status, 1, report)
        diagnostic, = report['diagnostics']
        self.assertEqual(diagnostic['type_details'], dict(operation='parameter', inference_scope='signature_override',
                         callee='take', parameter='value', parameter_index=0, expected='int', actual='float'))
        self.assertEqual((diagnostic['function'], diagnostic['location_kind']), ('take', 'function_declaration'))
        # Text arguments remain an existing per-call rejection after valid numeric calls.
        source = self.source('fn take(value:int)->int {return value;}\n'
                             'fn main()->int {let first=take(1);return take("wrong");}')
        status, report = self.check(source)
        self.assertEqual(status, 1, report)
        diagnostic, = report['diagnostics']
        self.assertEqual(diagnostic['type_details'], dict(operation='argument', callee='take',
                         parameter='value', parameter_index=0, expected='int', actual='str'))
        self.assertEqual((diagnostic['function'], diagnostic['location_kind']), ('main', 'source_statement'))

    def test_direct_external_signature_override_still_refuses_float_to_int_abi(self):
        with patch.object(sys, 'path', [str(ail_chatgpt.ROOT / 'python/pkg-v12'), *sys.path]):
            import pyfunc
        with patch.object(ail_chatgpt.subprocess, 'run', side_effect=AssertionError('no subprocess')), \
                patch.object(ail_chatgpt.subprocess, 'Popen', side_effect=AssertionError('no subprocess')):
            with self.assertRaises(pyfunc.Unsupported) as caught:
                pyfunc.to_c('def take(value:float)->float:\n return value\n', name='take', strict=True, sig={'value': 'int'})
        self.assertEqual(caught.exception.type_details, dict(operation='parameter', inference_scope='signature_override',
                         callee='take', parameter='value', parameter_index=0, expected='float', actual='int'))
        self.assertEqual(caught.exception.source_function, 'take')

    def test_argument_metadata_does_not_depend_on_message_text(self):
        with patch.object(sys, 'path', [str(ail_chatgpt.ROOT / 'python/pkg-v12'), *sys.path]):
            import pyfunc
        original = pyfunc._argument_type_error
        def opaque(*args, **kwargs):
            error = original(*args, **kwargs)
            error.args = ('opaque argument failure',)
            return error
        with patch.object(pyfunc, '_argument_type_error', side_effect=opaque):
            source = self.source('fn take(value:int)->int {return value;} fn main()->int {return take("wrong");}')
            status, report = self.check(source)
        self.assertEqual(status, 1, report)
        diagnostic, = report['diagnostics']
        self.assertEqual(diagnostic['message'], 'opaque argument failure')
        self.assertEqual(diagnostic['type_details'], dict(operation='argument', callee='take',
                         parameter='value', parameter_index=0, expected='int', actual='str'))
        self.assertEqual((diagnostic['path'], diagnostic['function']), (str(source), 'main'))

    def test_argument_repair_context_and_full_report_edit_handoff(self):
        source = self.source('# 日本語😀\nfn take(value:int)->int {return value;}\nfn main()->int {return take("wrong");}\n')
        before = source.read_bytes()
        status, plain = self.check(source)
        status_context, checked = self.check(source, '--repair-context')
        self.assertEqual((status, status_context), (1, 1))
        self.assertEqual(checked['diagnostics'], plain['diagnostics'])
        self.assertEqual(checked['diagnostics'][0]['type_details']['operation'], 'argument')
        self.assertEqual(checked['repair_context']['status'], 'available')
        self.assertEqual(checked['repair_context']['target'], 'main')
        context_file, candidate = self.root / 'checked.json', self.root / 'candidate.ail'
        context_file.write_text(json.dumps(checked, ensure_ascii=False), encoding='utf8')
        out, err = io.StringIO(), io.StringIO()
        with patch.object(ail_chatgpt.subprocess, 'run', side_effect=AssertionError('no subprocess')), \
                patch.object(ail_chatgpt.subprocess, 'Popen', side_effect=AssertionError('no subprocess')), \
                redirect_stdout(out), redirect_stderr(err):
            status = ail_chatgpt.main(['edit', str(source), '--symbol', 'main', '--base-sha256', hashlib.sha256(before).hexdigest(),
                                      '--body-text', 'return take(7);', '--context', str(context_file), '-o', str(candidate)])
        self.assertEqual(err.getvalue(), '')
        report = json.loads(out.getvalue())
        self.assertEqual(status, 0, report)
        self.assertEqual(report['candidate_check']['diagnostics'], [])
        self.assertEqual(report['candidate_check']['status'], 'passed')
        self.assertEqual(candidate.read_bytes(), before.replace(b'return take("wrong");', b'return take(7);'))
        self.assertEqual(source.read_bytes(), before)
        self.assertFalse(report['runtime_verified'])
        self.assertFalse(report['link_verified'])


if __name__ == '__main__':
    unittest.main()
