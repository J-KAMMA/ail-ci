"""Pin source edits to the exact resolved import closure; no subprocesses."""
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import ail_chatgpt
from ail_source_edit import run


def digest(data):
    return hashlib.sha256(data).hexdigest()


class EditDependencyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='ail-edit-dependencies-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.dependency = self.write('helper.ail', b'fn helper()->int {return 1;}')
        self.source = self.write('source.ail', b'use helper; fn chosen()->int {return helper();}')
        self.body = self.write('body.ail', b'return helper()+1;')
        self.output = self.root/'edited.ail'
        self.context_file = self.root/'context.json'
        self.capture_context()

    def write(self, name, data):
        path = self.root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def cli(self, arguments):
        out, err = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, {'PATH': ''}), patch.object(ail_chatgpt.subprocess, 'run',
                side_effect=AssertionError('no process allowed')), redirect_stdout(out), redirect_stderr(err):
            status = ail_chatgpt.main(list(map(str, arguments)))
        self.assertEqual(err.getvalue(), '')
        return status, json.loads(out.getvalue()), out.getvalue().encode()

    def capture_context(self, extra=()):
        status, report, raw = self.cli(['context', self.source, '--symbol', 'chosen', '--resolve-imports', *extra])
        self.assertEqual(status, 0, report)
        self.context_file.write_bytes(raw)
        return report

    def edit(self, extra=(), bound=True):
        original = self.source.read_bytes()
        arguments = ['edit', self.source, '--symbol', 'chosen', '--base-sha256', digest(original),
                     '--body', self.body, '-o', self.output, '--library', *extra]
        if bound:
            arguments.extend(['--context', self.context_file])
        status, report, _ = self.cli(arguments)
        self.assertEqual(self.source.read_bytes(), original)
        return status, report

    def refuse(self, extra=()):
        status, report = self.edit(extra)
        self.assertEqual(status, 2, report)
        self.assertEqual(report['status'], 'failed')
        self.assertFalse(self.output.exists())
        return report

    def mutate_context(self, change):
        report = json.loads(self.context_file.read_bytes())
        change(report)
        self.context_file.write_text(json.dumps(report), encoding='utf8')

    def test_unchanged_closure_writes_candidate_and_reports_context_bytes_hash(self):
        raw = self.context_file.read_bytes()
        original = self.source.read_bytes()
        status, report = self.edit()
        self.assertEqual(status, 0, report)
        self.assertEqual(self.output.read_bytes(), original.replace(b'return helper();', b'return helper()+1;'))
        self.assertEqual(report['context_sha256'], digest(raw))
        self.assertEqual(report['dependency_sha256'], {str(self.dependency.resolve()): digest(self.dependency.read_bytes())})

    def test_compact_context_edits_and_preserves_dependency_binding(self):
        from ail_source_context import expand_context
        original = json.loads(self.context_file.read_bytes())
        packed = self.capture_context(('--compact',))
        self.assertEqual(expand_context(packed), original)
        raw = self.context_file.read_bytes()
        status, report = self.edit()
        self.assertEqual(status, 0, report)
        self.assertEqual(report['context_sha256'], digest(raw))
        self.assertEqual(report['dependency_sha256'], original['dependency_sha256'])
        self.assertEqual(self.output.read_bytes(), self.source.read_bytes().replace(
            b'return helper();', b'return helper()+1;'))

    def test_compact_context_refuses_stale_dependency_and_bad_rows(self):
        self.capture_context(('--compact',))
        self.dependency.write_bytes(b'fn helper()->int {return 2;}')
        with patch.object(ail_chatgpt, '_source_check', side_effect=AssertionError('must refuse before check')):
            self.refuse()
        self.dependency.write_bytes(b'fn helper()->int {return 1;}')
        self.mutate_context(lambda value: value['interface']['functions'][0].update(parameters=[0]))
        with patch.object(ail_chatgpt, '_source_check', side_effect=AssertionError('must refuse before check')):
            self.refuse()

    def test_same_signature_dependency_implementation_change_refused_before_check(self):
        self.dependency.write_bytes(b'fn helper()->int {return 2;}')
        with patch.object(ail_chatgpt, '_source_check', side_effect=AssertionError('stale context must precede checking')):
            self.refuse()

    def test_nested_dependency_change_refused(self):
        nested = self.write('nested.ail', b'fn nested()->int {return 1;}')
        self.dependency.write_bytes(b'use nested; fn helper()->int {return nested();}')
        self.capture_context()
        nested.write_bytes(b'fn nested()->int {return 2;}')
        self.refuse()

    def test_added_root_dependency_and_changed_root_are_refused(self):
        self.write('other.ail', b'fn other()->int {return 1;}')
        self.source.write_bytes(b'use helper; use other; fn chosen()->int {return helper();}')
        self.refuse()

    def test_wrong_root_body_hash_and_target_refused(self):
        original = self.context_file.read_bytes()
        for key, value in [('source_sha256', '0'*64), ('body_sha256', '0'*64), ('target', 'helper')]:
            with self.subTest(key=key):
                self.context_file.write_bytes(original)
                self.mutate_context(lambda report: report.update({key: value}))
                self.refuse()

    def test_missing_dependency_map_refused(self):
        self.mutate_context(lambda report: report.pop('dependency_sha256'))
        self.refuse()

    def test_malformed_dependency_maps_and_hashes_refused(self):
        original = self.context_file.read_bytes()
        for value in [None, [], {'anything': None}, {'anything': 'x'*64}, {'anything': 'a'*63}]:
            with self.subTest(value=value):
                self.context_file.write_bytes(original)
                self.mutate_context(lambda report: report.update(dependency_sha256=value))
                self.refuse()

    def test_arbitrary_expected_paths_are_never_read(self):
        trap = self.root/'never-read.ail'
        self.mutate_context(lambda report: report.update(dependency_sha256={str(trap): '0'*64}))
        read_bytes = Path.read_bytes
        def guarded_read(path):
            self.assertNotEqual(path, trap)
            return read_bytes(path)
        with patch.object(Path, 'read_bytes', guarded_read):
            self.refuse()

    def test_duplicate_json_keys_at_root_and_dependency_map_refused(self):
        original = self.context_file.read_bytes()
        report = json.loads(original)
        dependency_map = json.dumps(report['dependency_sha256'])
        for raw in [original[:-2]+b', "target":"chosen"}\n',
                    json.dumps(report).replace(dependency_map, '{"same":"'+'0'*64+'","same":"'+'0'*64+'"}').encode()]:
            with self.subTest(raw=raw):
                self.context_file.write_bytes(raw)
                self.refuse()

    def test_invalid_json_and_nonobject_refused(self):
        for raw in [b'{', b'[]', b'null', b'\xff']:
            with self.subTest(raw=raw):
                self.context_file.write_bytes(raw)
                self.refuse()

    def test_local_scope_failed_status_and_wrong_schema_refused(self):
        original = self.context_file.read_bytes()
        for change in [lambda p: p['interface'].update(scope='local_source'),
                       lambda p: p.update(status='failed'), lambda p: p.update(schema='other/1')]:
            with self.subTest(change=change):
                self.context_file.write_bytes(original)
                self.mutate_context(change)
                self.refuse()

    def test_module_path_consistent_and_changed_resolution_refused(self):
        include = self.root/'include'
        include.mkdir()
        external = include/'helper.ail'
        self.dependency.rename(external)
        self.capture_context(('-I', include))
        status, report = self.edit(('-I', include))
        self.assertEqual(status, 0, report)
        self.output.unlink()
        self.dependency.write_bytes(b'fn helper()->int {return 9;}')
        self.refuse(('-I', include))

    def test_explicit_module_disallowed_with_context(self):
        module = self.write('explicit.ail', b'fn extra()->int {return 1;}')
        self.refuse(('--module', module))

    def test_no_context_keeps_normal_edit_after_dependency_change(self):
        self.dependency.write_bytes(b'fn helper()->int {return 2;}')
        status, report = self.edit(bound=False)
        self.assertEqual(status, 0, report)
        self.assertNotIn('context_sha256', report)

    def test_objects_are_forwarded_to_checker_outside_source_context(self):
        original = self.source.read_bytes()
        typed_object = self.root/'typed-object.json'
        args = SimpleNamespace(source=self.source, body=self.body, output=self.output, symbol='chosen',
            base_sha256=digest(original), library=True, module=[], object=[typed_object],
            module_path=[], context=self.context_file)
        def check(options):
            self.assertEqual(options.object, [typed_object])
            print(json.dumps(dict(status='passed', source_sha256=digest(options.source.read_bytes()), diagnostics=[])))
            return 0
        status, report = run(args, check)
        self.assertEqual(status, 0, report)
        self.assertNotIn(str(typed_object), report['dependency_sha256'])
    def test_dependency_changed_inside_checker_refused_before_output(self):
        original = self.source.read_bytes()
        args = SimpleNamespace(source=self.source, body=self.body, output=self.output, symbol='chosen',
            base_sha256=digest(original), library=True, module=[], object=[], module_path=[], context=self.context_file)
        def check(options):
            self.dependency.write_bytes(b'fn helper()->int {return 2;}')
            print(json.dumps(dict(status='passed', source_sha256=digest(options.source.read_bytes()), diagnostics=[])))
            return 0
        status, report = run(args, check)
        self.assertEqual(status, 2, report)
        self.assertFalse(self.output.exists())
        self.assertEqual(self.source.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()