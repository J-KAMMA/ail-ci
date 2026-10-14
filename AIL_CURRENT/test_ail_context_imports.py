"""Read-only syntax context over the exact import closure."""
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
from ail_source_context import context


def digest(data):
    return hashlib.sha256(data).hexdigest()


class ImportContextTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='ail-import-context-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.write('source.ail', b'fn chosen()->int {return 1;}')

    def write(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def report(self, **kwargs):
        return context(self.source.read_bytes(), 'chosen', source_path=self.source,
                       resolve_imports=True, **kwargs)

    def test_transitive_return_type_exposes_fields_and_exact_hashes(self):
        box = self.write('box.ail', 'struct Box { value:int; } # 日本\r\n'.encode())
        factory = self.write('factory.ail', b'use box; fn make()->Box {return Box(7);}')
        self.source.write_bytes(b'use factory; fn chosen()->int {return make().value;}')
        report = self.report(include_body=True)
        self.assertEqual(report['interface']['scope'], 'source_import_closure')
        self.assertIn('syntactic', report['binding_scope'])
        self.assertEqual({fn['name'] for fn in report['interface']['functions']}, {'chosen', 'make'})
        structs = report['interface']['structs']
        self.assertEqual([item['name'] for item in structs], ['Box'])
        self.assertEqual([item['name'] for item in structs[0]['fields']], ['value'])
        self.assertEqual(report['dependency_sha256'], {
            str(path.resolve()): digest(path.read_bytes()) for path in (box, factory)})
        self.assertEqual(report['source_sha256'], digest(self.source.read_bytes()))
        self.assertEqual(report['body'], 'return make().value;')
        self.assertTrue(report['syntax_verified'])
        for key in ('type_verified', 'link_verified', 'runtime_verified'):
            self.assertFalse(report[key])

    def test_diamond_dependency_is_collected_once(self):
        common = self.write('common.ail', b'fn helper()->int {return 1;}')
        self.write('left.ail', b'use common; fn left()->int {return helper();}')
        self.write('right.ail', b'use common; fn right()->int {return helper();}')
        self.source.write_bytes(b'use left; use right; fn chosen()->int {return left()+right();}')
        dependencies = self.report()['dependency_sha256']
        self.assertEqual(len(dependencies), 3)
        self.assertEqual(dependencies[str(common.resolve())], digest(common.read_bytes()))

    def test_bad_bodies_are_readable_in_root_and_dependency(self):
        for body in (b'let value=1;', b'return "wrong";', b'return 9223372036854775808;'):
            with self.subTest(body=body):
                self.write('bad.ail', b'fn broken()->int {' + body + b'}')
                self.source.write_bytes(b'use bad; fn chosen()->int {broken();' + body + b'}')
                report = self.report()
                self.assertIn('broken', {fn['name'] for fn in report['interface']['functions']})
                self.assertFalse(report['type_verified'])

    def test_normal_loader_keeps_return_and_int64_checks(self):
        for body in (b'let value=1;', b'return 9223372036854775808;'):
            with self.subTest(body=body):
                self.write('bad.ail', b'fn broken()->int {' + body + b'}')
                self.source.write_bytes(b'use bad; fn chosen()->int {return broken();}')
                with self.assertRaises(ValueError):
                    ail_chatgpt._load_sources(self.source)

    def test_library_and_entry_function_sources(self):
        self.write('helper.ail', b'fn helper()->int {return 1;}')
        for suffix in (b'', b' fn main()->int {return chosen();}'):
            with self.subTest(entry=bool(suffix)):
                self.source.write_bytes(b'use helper; fn chosen()->int {return helper();}' + suffix)
                self.assertEqual(self.report()['target'], 'chosen')

    def test_explicit_path_fallback_and_local_precedence(self):
        external = self.write('include/helper.ail', b'fn helper()->str {return "external";}')
        self.source.write_bytes(b'use helper; fn chosen()->int {return helper();}')
        self.assertEqual(set(self.report(module_paths=(external.parent,))['dependency_sha256']),
                         {str(external.resolve())})
        local = self.write('helper.ail', b'fn helper()->int {return 1;}')
        self.assertEqual(set(self.report(module_paths=(external.parent,))['dependency_sha256']),
                         {str(local.resolve())})

    def test_bundled_checked_integer_fallback(self):
        self.source.write_bytes(b'use checked_integer; fn chosen()->int {return parse_int64_decimal("7");}')
        bundled = ail_chatgpt.ROOT / 'language_examples' / 'checked_integer.ail'
        report = self.report()
        self.assertIn('parse_int64_decimal', {fn['name'] for fn in report['interface']['functions']})
        self.assertEqual(report['dependency_sha256'], {str(bundled.resolve()): digest(bundled.read_bytes())})

    def test_source_path_required_and_bytes_must_match(self):
        with self.assertRaises(ValueError):
            context(self.source.read_bytes(), 'chosen', resolve_imports=True)
        with self.assertRaises(ValueError):
            context(b'fn chosen()->int {return 2;}', 'chosen', source_path=self.source,
                    resolve_imports=True)

    def test_changed_root_or_dependency_after_loading_is_refused(self):
        dependency = self.write('helper.ail', b'fn helper()->int {return 1;}')
        original = b'use helper; fn chosen()->int {return helper();}'
        real_loader = ail_chatgpt._load_sources
        for changed in (self.source, dependency):
            with self.subTest(changed=changed):
                self.source.write_bytes(original)
                dependency.write_bytes(b'fn helper()->int {return 1;}')
                def change_after_loading(*args, **kwargs):
                    result = real_loader(*args, **kwargs)
                    changed.write_bytes(changed.read_bytes() + b'\n# changed')
                    return result
                with patch.object(ail_chatgpt, '_load_sources', side_effect=change_after_loading):
                    with self.assertRaises(ValueError):
                        self.report()
    def test_missing_and_cyclic_imports_are_refused(self):
        self.source.write_bytes(b'use absent; fn chosen()->int {return 1;}')
        with self.assertRaises(ValueError):
            self.report()
        self.write('first.ail', b'use second; fn first()->int {return 1;}')
        self.write('second.ail', b'use first; fn second()->int {return 2;}')
        self.source.write_bytes(b'use first; fn chosen()->int {return first();}')
        with self.assertRaises(ValueError):
            self.report()

    def test_duplicate_declarations_are_refused(self):
        for imported in (b'fn chosen()->int {return 2;}',
                         b'fn helper()->int {return 1;} fn helper()->int {return 2;}'):
            with self.subTest(imported=imported):
                self.write('duplicate.ail', imported)
                self.source.write_bytes(b'use duplicate; fn chosen()->int {return 1;}')
                with self.assertRaises(ValueError):
                    self.report()

    def test_invalid_syntax_utf8_and_executable_module_are_refused(self):
        for imported in (b'fn helper()->int {let x=;}', b'\xff', b'print(1);'):
            with self.subTest(imported=imported):
                self.write('invalid.ail', imported)
                self.source.write_bytes(b'use invalid; fn chosen()->int {return 1;}')
                with self.assertRaises(ValueError):
                    self.report()

    def test_default_context_does_not_resolve_or_read_files(self):
        source = b'use absent; fn chosen()->int {return imported();}'
        with patch.object(ail_chatgpt, '_load_sources', side_effect=AssertionError('no resolution')), \
                patch.object(Path, 'read_bytes', side_effect=AssertionError('no file reads')):
            report = context(source, 'chosen')
        self.assertEqual(report['interface']['scope'], 'local_source')
        self.assertEqual(report['other_call_expressions'], ['imported'])

    def invoke(self, extra=()):
        before = {str(path): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}
        out, err = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, {'PATH': ''}), patch.object(ail_chatgpt.subprocess, 'run',
                side_effect=AssertionError('context must not launch a process')), redirect_stdout(out), redirect_stderr(err):
            status = ail_chatgpt.main(['context', str(self.source), '--symbol', 'chosen', *extra])
        self.assertEqual(err.getvalue(), '')
        self.assertEqual({str(path): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}, before)
        return status, json.loads(out.getvalue())

    def test_cli_include_body_and_module_path_without_toolchain(self):
        imported = self.write('include/helper.ail', b'fn helper()->int {return "wrong";}')
        self.source.write_bytes(b'use helper; fn chosen()->int {return helper();}')
        for option in ('-I', '--module-path'):
            with self.subTest(option=option):
                status, report = self.invoke(('--resolve-imports', '--include-body', option, str(imported.parent)))
                self.assertEqual(status, 0, report)
                self.assertEqual(report['body'], 'return helper();')
                self.assertEqual(set(report['dependency_sha256']), {str(imported.resolve())})

    def test_cli_failure_is_structured_and_default_stays_local(self):
        self.source.write_bytes(b'use absent; fn chosen()->int {return absent();}')
        status, report = self.invoke(('--resolve-imports',))
        self.assertEqual(status, 2, report)
        self.assertEqual(report['schema'], 'ail.context/1')
        self.assertEqual(report['status'], 'failed')
        self.assertTrue(report['error'])
        status, report = self.invoke()
        self.assertEqual(status, 0, report)
        self.assertEqual(report['interface']['scope'], 'local_source')


if __name__ == '__main__':
    unittest.main()