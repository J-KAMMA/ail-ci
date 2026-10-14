"""Direct check-report handoff to guarded candidate editing, without subprocesses."""
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import ail_chatgpt
from ail_source_context import context
from ail_source_edit import run


def digest(data):
    return hashlib.sha256(data).hexdigest()


class EditCheckReportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='ail-edit-report-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.context_path = self.root / 'check.json'
        self.output = self.root / 'candidate.ail'

    def source(self, text, name='source.ail'):
        path = self.root / name
        path.write_bytes(text.encode('utf8'))
        return path

    def checked(self, source):
        out, err = io.StringIO(), io.StringIO()
        with patch.object(ail_chatgpt.subprocess, 'run', side_effect=AssertionError('no subprocess')), \
                patch.object(ail_chatgpt.subprocess, 'Popen', side_effect=AssertionError('no subprocess')), \
                redirect_stdout(out), redirect_stderr(err):
            status = ail_chatgpt.main(['check', str(source), '--repair-context'])
        self.assertEqual(err.getvalue(), '')
        report = json.loads(out.getvalue())
        self.assertEqual(status, 1, report)
        self.assertEqual(report['repair_context']['status'], 'available')
        return report

    def save(self, report):
        data = json.dumps(report, ensure_ascii=False, indent=2).encode('utf8') + b'\n'
        self.context_path.write_bytes(data)
        return data

    def options(self, source, symbol='main', body='return 7;', library=False):
        return SimpleNamespace(source=source, symbol=symbol, body_text=body, body=None,
                               base_sha256=digest(source.read_bytes()), output=self.output,
                               context=self.context_path, module=[], object=[], module_path=[],
                               library=library, edits_text=None)

    def edit(self, options, checker=None):
        with patch.object(ail_chatgpt.subprocess, 'run', side_effect=AssertionError('no subprocess')), \
                patch.object(ail_chatgpt.subprocess, 'Popen', side_effect=AssertionError('no subprocess')):
            return run(options, checker or ail_chatgpt._source_check)

    def test_root_report_unicode_crlf_exact_candidate_and_full_json_digest(self):
        source = self.source('# 日本語😀\r\nfn main()->int {\r\n return "wrong";\r\n}\r\n', '入力😀.ail')
        original = source.read_bytes()
        container = self.checked(source)
        whole_json = self.save(container)
        body = '\r\n let label="日本😀";\r\n return 7;\r\n'
        status, report = self.edit(self.options(source, body=body))
        self.assertEqual(status, 0, report)
        self.assertEqual(report['context_sha256'], digest(whole_json))
        self.assertNotEqual(report['context_sha256'], digest(json.dumps(container['repair_context']).encode()))
        self.assertEqual(self.output.read_bytes(), original.replace(b'\r\n return "wrong";\r\n', body.encode('utf8')))
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(report['candidate_check']['status'], 'passed')
        self.assertFalse(report['link_verified'])
        self.assertFalse(report['runtime_verified'])

    def test_method_report_handoff_changes_only_selected_body(self):
        source = self.source('struct Item {value:int;}\nimpl Item {fn bad(self)->int {return "wrong";}}\nfn main()->int {return 0;}')
        original = source.read_bytes()
        self.save(self.checked(source))
        status, report = self.edit(self.options(source, symbol='Item.bad', body='return self.value;'))
        self.assertEqual(status, 0, report)
        self.assertEqual(self.output.read_bytes(), original.replace(b'return "wrong";', b'return self.value;'))
        self.assertEqual(source.read_bytes(), original)

    def test_imported_target_binds_its_source_and_import_closure(self):
        helper = self.source('fn value()->int {return 9;}', 'helper.ail')
        target = self.source('use helper;\nfn bad()->int {return "wrong";}', 'broken.ail')
        caller = self.source('use broken;\nfn main()->int {return bad();}')
        before = {path: path.read_bytes() for path in (helper, target, caller)}
        container = self.checked(caller)
        self.assertEqual(container['repair_context']['source_path'], str(target))
        self.save(container)
        # Caller is outside the edited target's import closure.
        caller.write_bytes(b'fn main()->int {return 0;}')
        status, report = self.edit(self.options(target, symbol='bad', body='return value();', library=True))
        self.assertEqual(status, 0, report)
        self.assertEqual(report['dependency_sha256'], {str(helper): digest(before[helper])})
        self.assertEqual(target.read_bytes(), before[target])
        self.assertEqual(helper.read_bytes(), before[helper])
        self.assertEqual(self.output.read_bytes(), before[target].replace(b'return "wrong";', b'return value();'))

    def test_direct_context_remains_compatible(self):
        source = self.source('fn main()->int {return "wrong";}')
        direct = context(source.read_bytes(), 'main', include_body=True, source_path=source, resolve_imports=True)
        data = self.save(direct)
        status, report = self.edit(self.options(source))
        self.assertEqual(status, 0, report)
        self.assertEqual(report['context_sha256'], digest(data))
        self.assertEqual(report['dependency_sha256'], {})

    def test_malformed_report_refuses_before_checker_or_output(self):
        source = self.source('fn main()->int {return "wrong";}')
        valid = self.checked(source)
        mutations = [('passed', {'status': 'passed'}), ('not_needed', {'repair_context': {'status': 'not_needed'}}),
                     ('unavailable', {'repair_context': {'status': 'unavailable', 'source_path': str(source)}}),
                     ('missing', {'repair_context': None}), ('bad_nested', {'repair_context': []}),
                     ('missing_path', {'repair_context': {**valid['repair_context'], 'source_path': None}}),
                     ('wrong_path', {'repair_context': {**valid['repair_context'], 'source_path': str(self.root / 'elsewhere.ail')}}),
                     ('bad_target', {'repair_context': {**valid['repair_context'], 'target': 'other'}}),
                     ('bad_scope', {'repair_context': {**valid['repair_context'], 'interface': {'scope': 'local_source'}}}),
                     ('bad_hash', {'repair_context': {**valid['repair_context'], 'source_sha256': '0' * 64}})]
        for name, mutation in mutations:
            with self.subTest(name=name):
                container = {**valid, **mutation}
                if name == 'missing':
                    container.pop('repair_context')
                self.save(container)
                checker = Mock(side_effect=AssertionError('rejected context must not check'))
                status, report = self.edit(self.options(source), checker)
                self.assertEqual(status, 2, report)
                self.assertFalse(self.output.exists())
                checker.assert_not_called()
        for data in (b'{', b'[]', b'{"schema":"ail.check/1","schema":"ail.check/1"}',
                     b'{"schema":"ail.check/1","status":"failed","repair_context":{"status":"available","status":"unavailable"}}'):
            self.context_path.write_bytes(data)
            checker = Mock(side_effect=AssertionError('invalid JSON must not check'))
            status, report = self.edit(self.options(source), checker)
            self.assertEqual(status, 2, report)
            self.assertFalse(self.output.exists())
            checker.assert_not_called()

    def test_identical_bytes_in_different_source_refuse_by_path(self):
        source = self.source('fn main()->int {return "wrong";}')
        other = self.source(source.read_text(encoding='utf8'), 'same_content.ail')
        self.save(self.checked(source))
        checker = Mock(side_effect=AssertionError('wrong source must not check'))
        status, report = self.edit(self.options(other), checker)
        self.assertEqual(status, 2, report)
        self.assertIn('source path', report['error'])
        self.assertFalse(self.output.exists())
        checker.assert_not_called()

    def test_stale_source_and_dependency_before_check_refuse(self):
        for changed in ('source', 'dependency'):
            with self.subTest(changed=changed):
                helper = self.source('fn value()->int {return 1;}', 'helper.ail')
                source = self.source('use helper; fn main()->int {return "wrong";}')
                self.save(self.checked(source))
                if changed == 'source':
                    source.write_bytes(source.read_bytes() + b'\n# changed\n')
                else:
                    helper.write_bytes(b'fn value()->int {return 2;}')
                checker = Mock(side_effect=AssertionError('stale context must not check'))
                status, report = self.edit(self.options(source), checker)
                self.assertEqual(status, 2, report)
                self.assertIn('stale', report['error'])
                self.assertFalse(self.output.exists())
                checker.assert_not_called()

    def test_source_and_dependency_changes_during_candidate_check_refuse(self):
        for changed in ('source', 'dependency'):
            with self.subTest(changed=changed):
                helper = self.source('fn value()->int {return 1;}', 'helper.ail')
                source = self.source('use helper; fn main()->int {return "wrong";}')
                self.save(self.checked(source))
                options = self.options(source, body='return value();')
                def check_and_change(args):
                    status = ail_chatgpt._source_check(args)
                    target = source if changed == 'source' else helper
                    target.write_bytes(target.read_bytes() + b'\n# concurrent change\n')
                    return status
                status, report = self.edit(options, check_and_change)
                self.assertEqual(status, 2, report)
                self.assertEqual(report['candidate_check']['status'], 'passed')
                self.assertFalse(self.output.exists())
                self.assertTrue('changed' in report['error'] or 'stale' in report['error'])


if __name__ == '__main__':
    unittest.main()
