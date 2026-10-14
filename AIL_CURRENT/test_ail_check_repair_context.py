"""SHA-bound repair context from source checks; no build or subprocess allowed."""
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import ail_chatgpt
import ail_source_context
from ail_source_edit import _verify_context, replace_body


class CheckRepairContextTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='ail-check-repair-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def source(self, text, name='source.ail'):
        path = self.root / name
        path.write_bytes(text.encode('utf8'))
        return path

    def check(self, source, *args):
        out, err = io.StringIO(), io.StringIO()
        with patch.object(ail_chatgpt.subprocess, 'run', side_effect=AssertionError('no subprocess')), \
                patch.object(ail_chatgpt.subprocess, 'Popen', side_effect=AssertionError('no subprocess')), \
                redirect_stdout(out), redirect_stderr(err):
            status = ail_chatgpt.main(['check', str(source), *map(str, args)])
        self.assertEqual(err.getvalue(), '')
        report = json.loads(out.getvalue())
        self.assertFalse(report['link_verified'])
        self.assertFalse(report['runtime_verified'])
        return status, report

    def compiler(self):
        previous = sys.path[:]
        bytecode = sys.dont_write_bytecode
        try:
            sys.dont_write_bytecode = True
            sys.path.insert(0, str(ail_chatgpt.ROOT / 'python/pkg-v12'))
            import pyfunc
            return pyfunc
        finally:
            sys.path[:] = previous
            sys.dont_write_bytecode = bytecode

    def test_root_failure_has_exact_body_and_declared_call_context(self):
        source = self.source('fn take(x:int)->int {return x;}\nfn main()->int { return take("wrong"); }')
        status, report = self.check(source, '--repair-context')
        self.assertEqual(status, 1, report)
        context = report['repair_context']
        self.assertEqual((context['schema'], context['status'], context['target']),
                         ('ail.context/1', 'available', 'main'))
        self.assertEqual(context['body'], ' return take("wrong"); ')
        self.assertEqual(context['source_path'], str(source))
        self.assertEqual(context['source_sha256'], report['source_sha256'])
        self.assertEqual([item['name'] for item in context['interface']['functions']], ['take', 'main'])
        self.assertEqual(context['interface']['scope'], 'source_import_closure')
        self.assertFalse(context['type_verified'])
        self.assertFalse(context['link_verified'])
        self.assertFalse(context['runtime_verified'])

    def test_imported_failure_uses_import_source_and_api_closure(self):
        helper = self.source('fn take(x:int)->int {return x;}', 'helper.ail')
        module = self.source('use helper;\nfn bad()->int {return take("wrong");}', 'broken.ail')
        source = self.source('use broken;\nfn main()->int {return bad();}')
        status, report = self.check(source, '--repair-context')
        self.assertEqual(status, 1, report)
        context = report['repair_context']
        self.assertEqual((context['target'], context['source_path']), ('bad', str(module)))
        self.assertEqual(context['source_sha256'], hashlib.sha256(module.read_bytes()).hexdigest())
        self.assertEqual(context['dependency_sha256'], {str(helper): hashlib.sha256(helper.read_bytes()).hexdigest()})
        self.assertEqual(context['imports'], ['helper'])

    def test_struct_method_contract_and_type_failures(self):
        for body, code in (('let ignored=1;', 'contract'), ('return "wrong";', 'type')):
            with self.subTest(code=code):
                source = self.source('struct Item {value:int;}\nimpl Item {fn bad(self)->int {' + body + '}}\nfn main()->int {return 0;}')
                status, report = self.check(source, '--repair-context')
                self.assertEqual(status, 1, report)
                self.assertEqual(report['diagnostics'][0]['code'], code)
                context = report['repair_context']
                self.assertEqual((context['target'], context['receiver_owner'], context['body']), ('Item.bad', 'Item', body))

    def test_success_not_needed_and_default_output_unchanged(self):
        source = self.source('fn main()->int {return 0;}')
        status, default = self.check(source)
        self.assertEqual(status, 0, default)
        self.assertNotIn('repair_context', default)
        status, report = self.check(source, '--repair-context')
        self.assertEqual(status, 0, report)
        self.assertEqual(report.pop('repair_context'), {'status': 'not_needed'})
        self.assertEqual(report, default)
        source = self.source('fn main()->int {return "wrong";}')
        _, default = self.check(source)
        _, report = self.check(source, '--repair-context')
        report.pop('repair_context')
        self.assertEqual(report, default)

    def test_unavailable_cases_preserve_diagnostics_and_status(self):
        cases = [('fn main()->int {return 1 + * 2;}', (), 'unsupported_diagnostic'),
                 ('def take(x:int)->int:\n    return x\ndef main()->int:\n    return take("wrong")\n', ('--syntax', 'python'), 'python_source'),
                 ('fn main()->int {return 0;}', ('-I', self.root / 'absent'), 'unsupported_diagnostic'),
                 ('fn main()->int {return "wrong";}', ('--module', self.source('fn extra()->int {return 0;}', 'extra.ail')), 'explicit_module_or_object'),
                 ('fn main()->int {return 0;}', ('--object', self.root / 'missing.o'), 'explicit_module_or_object'),
                 ('struct Item {value:int;} impl Item {fn bad(self)->int {let x=1;}} fn Item__bad()->int {return 1;} fn main()->int {return 0;}', (), 'missing_function_location')]
        for text, args, reason in cases:
            with self.subTest(reason=reason, args=args):
                source = self.source(text)
                expected_status, expected = self.check(source, *args)
                status, report = self.check(source, *args, '--repair-context')
                self.assertEqual(status, expected_status)
                if reason == 'python_source':
                    self.assertEqual((status, report['diagnostics'][0]['code']), (1, 'type'))
                self.assertEqual(report.pop('repair_context'), {'status': 'unavailable', 'reason': reason})
                self.assertEqual(report, expected)
        status, report = self.check(self.root / 'missing.ail', '--repair-context')
        self.assertEqual(status, 2)
        self.assertEqual(report['repair_context']['status'], 'unavailable')
        report['diagnostics'] = [dict(code='type', function='bad', path=str(self.root / 'outside.ail'))]
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('must not read diagnostic path')):
            context = ail_chatgpt._check_repair_context(SimpleNamespace(module=[], object=[]), report, None, None, {})
        self.assertEqual(context['reason'], 'source_not_loaded')

    def test_dependency_changed_during_type_check_refuses_context(self):
        module = self.source('fn bad()->int {return "wrong";}', 'broken.ail')
        source = self.source('use broken; fn main()->int {return bad();}')
        compiler = self.compiler()
        original = compiler.to_c
        def change(*args, **kwargs):
            try:
                return original(*args, **kwargs)
            finally:
                module.write_bytes(b'fn bad()->int {return 1;}')
        with patch.object(compiler, 'to_c', side_effect=change), \
                patch.object(ail_source_context, 'context', side_effect=AssertionError('stale source must not collect context')):
            status, report = self.check(source, '--repair-context')
        self.assertEqual(status, 1, report)
        self.assertEqual(report['diagnostics'][0]['function'], 'bad')
        self.assertEqual(report['repair_context'], dict(status='unavailable', reason='source_changed'))

    def test_root_changed_during_context_collection_refuses_context(self):
        source = self.source('fn main()->int {return "wrong";}')
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        original = ail_source_context.context
        def change(*args, **kwargs):
            result = original(*args, **kwargs)
            source.write_bytes(b'fn main()->int {return 1;}')
            return result
        with patch.object(ail_source_context, 'context', side_effect=change):
            status, report = self.check(source, '--repair-context')
        self.assertEqual(status, 1, report)
        self.assertEqual(report['source_sha256'], digest)
        self.assertEqual(report['repair_context'], dict(status='unavailable', reason='source_changed'))

    def test_original_bytes_and_edit_handoff_preserved(self):
        source = self.source('# 日本語😀\r\nfn main()->int {\r\n  return "wrong";\r\n}\r\n')
        original = source.read_bytes()
        status, report = self.check(source, '--repair-context')
        self.assertEqual(status, 1, report)
        context = report['repair_context']
        self.assertEqual(context['body'], '\r\n  return "wrong";\r\n')
        self.assertEqual(context['body_sha256'], hashlib.sha256(context['body'].encode('utf8')).hexdigest())
        self.assertEqual(source.read_bytes(), original)
        args = SimpleNamespace(module=[], module_path=[], symbol='main')
        self.assertEqual(_verify_context(context, source, original, args), {})
        candidate = replace_body(original, context['target'], b'\r\n  return 7;\r\n', context['source_sha256'])
        candidate_path = self.root / 'candidate.ail'
        candidate_path.write_bytes(candidate)
        status, report = self.check(candidate_path, '--repair-context')
        self.assertEqual(status, 0, report)
        self.assertEqual(source.read_bytes(), original)
        self.assertTrue(candidate.startswith('# 日本語😀\r\n'.encode('utf8')))


if __name__ == '__main__':
    unittest.main()
