"""Owned field/list diagnostic metadata preserves refusal text and source trust."""
import sys
import unittest
from unittest.mock import patch

import ail_chatgpt
import test_ail_source_check as support


class OwnedTypeDetailsTests(unittest.TestCase):
    setUp = support.SourceCheckTests.setUp
    source = support.SourceCheckTests.source

    def check(self, source):
        with patch.object(ail_chatgpt.subprocess, 'Popen', side_effect=AssertionError('no subprocess')):
            return support.SourceCheckTests.check(self, source)

    def mismatch(self, text, details, message=None, *, located=True):
        source = self.source(text)
        status, report = self.check(source)
        self.assertEqual(status, 1, report)
        diagnostic, = report['diagnostics']
        self.assertEqual(diagnostic['code'], 'type')
        self.assertEqual(diagnostic['type_details'], details)
        if message is not None:
            self.assertEqual(diagnostic['message'], message)
        if located:
            self.assertEqual((diagnostic['path'], diagnostic['function'], diagnostic['location_kind']),
                             (str(source), 'main', 'source_statement'))
        else:
            self.assertIsNone(diagnostic['location_kind'])
        self.assertFalse(report['runtime_verified']); self.assertFalse(report['link_verified'])
        return diagnostic

    def test_fields_use_public_owned_scalar_container_and_struct_types(self):
        cases = [
            ('exception', 'ValueError()', '1', 'exception', 'int', 'reference field requires matching type'),
            ('bytearray', 'bytearray(b"x")', 'ValueError()', 'bytearray', 'exception', 'reference field requires matching type'),
            ('list[exception]', '[ValueError()]', '[1]', 'list[exception]', 'list[int]', 'a reference list accepts only exception elements'),
            ('list[int]', '[1]', '[1.5]', 'list[int]', 'list[float]', 'a list field requires matching numeric elements'),
            ('list[float]', '[1.5]', '[1]', 'list[float]', 'list[int]', 'a flist field requires matching numeric elements'),
        ]
        for annotation, initial, wrong, expected, actual, message in cases:
            with self.subTest(annotation=annotation):
                self.mismatch('struct Box {value:' + annotation + ';}\nfn main()->int {\n let box=Box(' + initial + ');\n box.value=' + wrong + ';\n return 0;\n}',
                              dict(operation='field', owner='Box', field='value', expected=expected, actual=actual), message)
        self.mismatch('struct First {n:int;} struct Second {n:int;} struct Box {value:First;}\nfn main()->int {let box=Box(First(1)); box.value=Second(2); return 0;}',
                      dict(operation='field', owner='Box', field='value', expected='First', actual='Second'),
                      'Box.value requires a First instance')

    def test_reference_append_store_extend_report_same_dimensions(self):
        cases = [('errors.append(1);', 'append', 'exception', 'int', 'a reference list accepts only exception elements'),
                 ('errors[0]=1;', 'store', 'exception', 'int', 'a struct list accepts only exception elements'),
                 ('errors.extend([1]);', 'extend', 'list[exception]', 'list[int]', 'a reference list accepts only exception elements')]
        for body, action, expected, actual, message in cases:
            with self.subTest(action=action):
                self.mismatch('fn main()->int {let errors:list[exception]=[]; ' + body + ' return 0;}',
                              dict(operation='element', action=action, container='list[exception]', expected=expected, actual=actual), message)
        self.mismatch('struct Item {n:int;} fn main()->int {let values:list[Item]=[]; values.append(ValueError()); return 0;}',
                      dict(operation='element', action='append', container='list[Item]', expected='Item', actual='exception'),
                      'incompatible struct types assigned to values', located=False)
        self.mismatch('fn main()->int {let values:list[bytearray]=[]; values.append(ValueError()); return 0;}',
                      dict(operation='element', action='append', container='list[bytearray]', expected='bytearray', actual='exception'),
                      'incompatible struct types assigned to values', located=False)

    def test_unknown_and_unclassified_actual_are_null(self):
        self.mismatch('struct Box {value:exception;} fn main()->int {let box=Box(ValueError());box.value=unknown;return 0;}',
                      dict(operation='field', owner='Box', field='value', expected='exception', actual=None),
                      "'unknown' is read before it is assigned")
        self.mismatch('fn main()->int {let errors:list[exception]=[];errors.append(unknown);return 0;}',
                      dict(operation='element', action='append', container='list[exception]', expected='exception', actual=None),
                      "'unknown' is read before it is assigned")
        self.mismatch('struct Box {value:list[exception];} fn main()->int {let box=Box([]); box.value=[ValueError(),1];return 0;}',
                      dict(operation='field', owner='Box', field='value', expected='list[exception]', actual=None),
                      'a reference list accepts only exception elements')

    def test_constructor_and_callback_use_existing_argument_schema(self):
        details = dict(operation='argument', callee='Box', parameter='error', parameter_index=0, expected='exception', actual='int')
        self.mismatch('struct Box {error:exception; count:int;} fn main()->int {let box=Box(1,"bad");return 0;}', details,
                      'constructor reference arguments require matching types')
        details.update(parameter='errors',expected='list[exception]',actual='list[int]')
        self.mismatch('struct Box {errors:list[exception];} fn main()->int {let box=Box([1]);return 0;}',details,
                      'a reference list accepts only exception elements')
        details.update(parameter='error',expected='exception',actual=None)
        self.mismatch('struct Box {error:exception;} fn main()->int {let box=Box(unknown);return 0;}',details,
                      "'unknown' is read before it is assigned")
        source=self.source('fn invoke(cb:Callable[[exception],exception])->exception {return cb(1);} fn main()->int {return 0;}')
        status,report=self.check(source)
        self.assertEqual(status,1)
        self.assertEqual(report['diagnostics'][0]['type_details'],dict(operation='argument',callee='<callback>',parameter='0',parameter_index=0,expected='exception',actual='int'))
        self.assertEqual(report['diagnostics'][0]['function'],'invoke')

    def test_builtin_exception_argument_and_nested_errors_keep_inner_details(self):
        # exc-str: an exception argument may be a str, int, float, bool or None, as in CPython;
        # a bytes argument is still refused, with the same inner details.
        details=dict(operation='argument',callee='ValueError',parameter='argument',parameter_index=0,expected='str',actual='bytes')
        message='an exception argument must be a str, int, float, bool or None'
        for body in ('raise ValueError(b"x");', 'let errors:list[exception]=[];errors.append(ValueError(b"x"));',
                     'let errors:list[exception]=[];errors[0]=ValueError(b"x");'):
            with self.subTest(body=body):
                self.mismatch('fn main()->int {'+body+'return 0;}',details,message)
        self.mismatch('struct Box {value:exception;} fn main()->int {let box=Box(ValueError());box.value=ValueError(b"x");return 0;}',details,message)

    def test_non_str_exception_arguments_are_accepted_like_cpython(self):
        for body in ('raise ValueError(1);', 'let errors:list[exception]=[];errors.append(ValueError(1));',
                     'let errors:list[exception]=[];errors[0]=ValueError(1.5);'):
            with self.subTest(body=body):
                status,report=self.check(self.source('fn main()->int {'+body+'return 0;}'))
                self.assertEqual(status,0,report)
        status,report=self.check(self.source('struct Box {value:exception;} fn main()->int {let box=Box(ValueError());box.value=ValueError(1);return 0;}'))
        self.assertEqual(status,0,report)

    def test_unsupported_operation_unknown_owner_and_first_error_are_not_reclassified(self):
        cases=('fn main()->int {let errors:list[exception]=[];errors[:]=7;return 0;}',
               'fn main()->int {let errors:list[exception]=[];let value=errors.append(7);return 0;}',
               'fn main()->int {let error=ValueError();error.message=7;return 0;}',
               'fn main()->int {unknown.error=7;return 0;}')
        for text in cases:
            with self.subTest(text=text):
                status,report=self.check(self.source(text))
                self.assertEqual(status,1,report)
                self.assertNotIn('type_details',report['diagnostics'][0])
        self.mismatch('fn main()->int {let errors:list[exception]=[];errors[1.5]=7;return 0;}',
                      dict(operation='element',action='store',container='list[exception]',expected='exception',actual='int'),
                      'a struct list accepts only exception elements')

    def test_nested_literal_is_unclassified_and_keeps_prepass_location_unavailable(self):
        self.mismatch('fn main()->int {let errors:list[exception]=[];errors.append([ValueError(),1]);return 0;}',
                      dict(operation='element',action='append',container='list[exception]',expected='exception',actual=None),
                      'a handle list requires one exact element type')
        self.mismatch('fn main()->int {let errors:list[exception]=[];errors.extend([[ValueError()]]);return 0;}',
                      dict(operation='element',action='extend',container='list[exception]',expected='list[exception]',actual=None),
                      'nested exception lists are unsupported',located=False)

    def test_imported_struct_type_names(self):
        self.source('struct First {n:int;} struct Second {n:int;} struct Box {value:First;}','provider.ail')
        self.mismatch('use provider; fn main()->int {let box=Box(First(1));box.value=Second(2);return 0;}',
                      dict(operation='field',owner='Box',field='value',expected='First',actual='Second'),
                      'Box.value requires a First instance')

    def test_keyword_constructor_arity_and_same_type_unsupported_have_no_details(self):
        cases = [('struct Box {error:exception;} fn main()->int {let box=Box(error=1, extra=2);return 0;}', "Box() has no field named 'extra' (fields: error)"),
                 ('struct Box {error:exception;} fn main()->int {let box=Box();return 0;}', 'Box() takes 1 arguments'),
                 ('fn main()->int {let errors:list[exception]=[];errors.sort();return 0;}', 'handle lists have no ordering'),
                 ('fn main()->int {let errors:list[exception]=[];errors.append();return 0;}', None)]
        for text,message in cases:
            with self.subTest(text=text):
                status,report=self.check(self.source(text))
                self.assertEqual(status,1,report)
                diagnostic,=report['diagnostics']
                self.assertNotIn('type_details',diagnostic)
                if message is not None: self.assertEqual(diagnostic['message'],message)


if __name__ == '__main__':
    unittest.main()