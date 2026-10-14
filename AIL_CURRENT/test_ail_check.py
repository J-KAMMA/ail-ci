import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch

import ail_check


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        for name in ('ail_chatgpt.py', 'sample_test.py', 'ail_check.py', 'support_test.py'):
            (self.root / name).write_text('# fixture\n', encoding='utf-8')
        self.manifest = {'sdk_files': ['ail_chatgpt.py'], 'sha256': {
            name: hashlib.sha256((self.root / name).read_bytes()).hexdigest()
            for name in ('ail_chatgpt.py', 'sample_test.py', 'ail_check.py', 'support_test.py')
        }}
        self.save_manifest()

    def save_manifest(self):
        (self.root / 'MANIFEST.json').write_text(json.dumps(self.manifest), encoding='utf-8')

    def preflight(self, which=None, probe=None):
        with patch.object(ail_check, 'MODULES', ('sample_test',)), \
                patch.object(ail_check, 'SUPPORT', ('ail_check.py', 'support_test.py')), \
                patch.object(ail_check.shutil, 'which', side_effect=which or (lambda name: name)), \
                patch.object(ail_check.subprocess, 'run', return_value=probe or subprocess.CompletedProcess(
                    [], 0, json.dumps({'build_check': {'status': 'passed', 'phase': 'run'}}).encode(), b'')) as run:
            ail_check.preflight(self.root)
            return run

    def test_missing_gcc_and_explicit_compiler_do_not_fallback(self):
        for compiler, missing in (('', 'gcc'), ('missing-compiler', 'missing-compiler')):
            with self.subTest(compiler=compiler), patch.dict(os.environ, {'PIPE_CC': compiler}):
                with self.assertRaises(ValueError):
                    self.preflight(which=lambda name: None if name == missing else name)

    def test_changed_selected_payload_or_test_refused(self):
        with patch.dict(os.environ, {'PIPE_CC': ''}):
            for name in ('ail_chatgpt.py', 'sample_test.py', 'ail_check.py', 'support_test.py'):
                path = self.root / name
                original = path.read_bytes()
                path.write_bytes(original + b'# changed')
                try:
                    with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                        self.preflight()
                finally:
                    path.write_bytes(original)
            self.manifest['sha256'].pop('sample_test.py')
            self.save_manifest()
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                self.preflight()

    def test_doctor_failure_or_incomplete_probe_refused(self):
        with patch.dict(os.environ, {'PIPE_CC': ''}):
            for status, phase, code in (('failed', 'run', 1), ('passed', 'compile', 0), ('passed', 'run', 2)):
                with self.subTest(status=status, phase=phase, code=code), self.assertRaises(ValueError):
                    self.preflight(probe=subprocess.CompletedProcess([], code, json.dumps({
                        'build_check': {'status': status, 'phase': phase}}).encode(), b''))
            with self.assertRaises(ValueError):
                self.preflight(probe=subprocess.CompletedProcess([], 0, b'wrong probe output', b''))
            with self.assertRaises(ValueError):
                self.preflight(probe=subprocess.CompletedProcess([], 0, json.dumps({
                    'build_check': {'status': 'passed', 'phase': 'run'}}).encode(), b'unexpected'))

    def test_zero_suite_and_outside_import_refused(self):
        module = types.ModuleType('sample_test')
        module.__file__ = str(self.root / 'sample_test.py')
        with patch.object(ail_check, 'MODULES', ('sample_test',)), \
                patch.object(ail_check, 'SUPPORT', ('ail_check.py', 'support_test.py')), \
                patch.object(ail_check.importlib, 'import_module', return_value=module), \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError, 'no valid tests'):
                ail_check.load_suite(self.root)
            module.__file__ = str(self.root.parent / 'sample_test.py')
            with self.assertRaisesRegex(ValueError, 'outside source root'):
                ail_check.load_suite(self.root)

    def invoke(self, suite, arguments=()):
        output, errors = io.StringIO(), io.StringIO()
        seen = []
        def load(root):
            seen.append((Path.cwd(), root))
            return suite
        with patch.object(ail_check, 'ROOT', self.root), \
                patch.object(ail_check, 'preflight') as preflight, \
                patch.object(ail_check, 'load_suite', side_effect=load), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            before = Path.cwd()
            status = ail_check.main(list(arguments))
            self.assertEqual(Path.cwd(), before)
            self.assertEqual(seen, [(self.root, self.root)])
            return status, output.getvalue(), preflight.call_count

    def test_failure_is_not_success_and_skips_are_explicit(self):
        class Failure(unittest.TestCase):
            def runTest(self):
                self.fail('independent failure')
        class Skipped(unittest.TestCase):
            @unittest.skip('tool unavailable')
            def runTest(self):
                pass
        self.assertEqual(self.invoke(unittest.TestSuite([Failure()]))[0], 1)
        status, output, _ = self.invoke(unittest.TestSuite([Skipped()]))
        self.assertEqual(status, 1)
        self.assertIn('UNVERIFIED SKIP', output)
        self.assertIn('tool unavailable', output)

    def test_list_has_ids_count_no_preflight_and_restores_cwd(self):
        case = unittest.FunctionTestCase(lambda: None, description='selected')
        status, output, calls = self.invoke(unittest.TestSuite([case]), ('--list',))
        self.assertEqual((status, calls), (0, 0))
        self.assertIn('Total: 1 tests', output)
        self.assertIn(case.id(), output)


if __name__ == '__main__':
    unittest.main()