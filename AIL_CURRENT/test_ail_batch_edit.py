"""Batch bodies preserve scope and receive one whole candidate check."""
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


class BatchEditTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='ail-batch-edit-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'source.ail'
        self.output = self.root / 'candidate.ail'
        self.source.write_bytes(b'fn first()->int {return 1;} fn second()->int {return 2;} fn main()->int {return first()+second();}')

    def invoke(self, options, *, output=None, base=None):
        before = self.source.read_bytes()
        files = {path: path.read_bytes() for path in self.root.iterdir() if path.is_file()}
        arguments = ['edit', str(self.source), '--base-sha256', base or digest(before),
                     '-o', str(output or self.output), *map(str, options)]
        out, err = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, {'PATH': ''}), patch.object(ail_chatgpt.subprocess, 'run',
                side_effect=AssertionError('batch edit must not launch a process')), \
                patch.object(ail_chatgpt, '_source_check', wraps=ail_chatgpt._source_check) as checked, \
                redirect_stdout(out), redirect_stderr(err):
            status = ail_chatgpt.main(arguments)
        self.assertEqual(err.getvalue(), '')
        self.assertEqual(self.source.read_bytes(), before)
        for path, data in files.items():
            self.assertEqual(path.read_bytes(), data)
        added = set(self.root.iterdir()) - set(files)
        self.assertLessEqual(added, {output or self.output}, 'intermediate candidate escaped temporary directory')
        report = json.loads(out.getvalue())
        self.assertEqual(report['schema'], 'ail.edit/1')
        self.assertFalse(report['link_verified'])
        self.assertFalse(report['runtime_verified'])
        return status, report, checked.call_count

    def batch(self, edits, *, output=None, base=None, extra=()):
        payload = edits if isinstance(edits, str) else json.dumps(edits, ensure_ascii=False)
        return self.invoke(['--edits-text', payload, *extra], output=output, base=base)

    def test_two_invalid_functions_require_one_whole_candidate_check(self):
        self.source.write_bytes(b'fn first()->int {return "bad";} fn second()->int {return "bad";} fn main()->int {return first()+second();}')
        for symbol in ('first', 'second'):
            status, report, calls = self.invoke(['--symbol', symbol, '--body-text', 'return 3;'])
            self.assertNotEqual(status, 0, report)
            self.assertEqual(calls, 1)
            self.assertFalse(self.output.exists())
        status, report, calls = self.batch([{'symbol': 'first', 'body': 'return 3;'},
                                           {'symbol': 'second', 'body': 'return 4;'}])
        self.assertEqual(status, 0, report)
        self.assertEqual(calls, 1)
        self.assertEqual(self.output.read_bytes(), b'fn first()->int {return 3;} fn second()->int {return 4;} fn main()->int {return first()+second();}')

    def test_unicode_crlf_surrounding_bytes_and_order_independence(self):
        source = '# 日本語 😀\r\nfn first()->str {return "old";}\r\nfn second()->int {return 2;}\r\nfn main()->int {return second();}\r\n'.encode('utf8')
        self.source.write_bytes(source)
        body = '\r\n return "日本語 😀 } {";\r\n'
        edits = [{'symbol': 'first', 'body': body}, {'symbol': 'second', 'body': 'return 19;'}]
        expected = source.replace(b'return "old";', body.encode('utf8')).replace(b'return 2;', b'return 19;')
        for index, ordered in enumerate((edits, list(reversed(edits)))):
            output = self.root / f'order{index}.ail'
            status, report, calls = self.batch(ordered, output=output)
            self.assertEqual(status, 0, report)
            self.assertEqual(calls, 1)
            self.assertEqual(output.read_bytes(), expected)

    def test_entry_and_qualified_method_preserve_signatures(self):
        source = b'struct Box {value:int;} impl Box {fn get(self)->int {return self.value;}} fn get()->int {return 7;} fn main()->int {return get();}'
        self.source.write_bytes(source)
        status, report, calls = self.batch([{'symbol': 'main', 'body': 'let box=Box(3);return box.get();'},
                                           {'symbol': 'Box.get', 'body': 'return self.value+1;'}])
        self.assertEqual(status, 0, report)
        self.assertEqual(calls, 1)
        self.assertEqual(self.output.read_bytes(), source.replace(b'return self.value;', b'return self.value+1;').replace(b'return get();', b'let box=Box(3);return box.get();'))

    def test_invalid_batches_stale_source_type_and_existing_output_refused(self):
        good = [{'symbol': 'first', 'body': 'return 3;'}]
        invalid = [[], {}, [1], [{'symbol': 'first'}], [{'symbol': 'first', 'body': 'return 3;', 'extra': 1}],
                   [{'symbol': 1, 'body': 'return 3;'}], [{'symbol': 'first', 'body': None}],
                   good * 2, [{'symbol': 'missing', 'body': 'return 3;'}],
                   '[{"symbol":"first","symbol":"second","body":"return 3;"}]',
                   '[{"symbol":"first","body":"return 3;","body":"return 4;"}]',
                   [{'symbol': 'first', 'body': 'return 3;} fn injected()->int {return 4;} fn decoy()->int {return 5;'}],
                   [{'symbol': 'first', 'body': 'return "bad";'}]]
        for edits in invalid:
            with self.subTest(edits=edits):
                status, report, _ = self.batch(edits)
                self.assertNotEqual(status, 0, report)
                self.assertFalse(self.output.exists())
        status, report, _ = self.batch(good, base='0' * 64)
        self.assertNotEqual(status, 0, report)
        self.assertFalse(self.output.exists())
        self.output.write_bytes(b'preserve existing candidate')
        status, report, _ = self.batch(good)
        self.assertNotEqual(status, 0, report)
        self.assertEqual(self.output.read_bytes(), b'preserve existing candidate')

    def test_batch_cli_rejects_symbol_and_other_body_sources(self):
        common = ['edit', str(self.source), '--base-sha256', digest(self.source.read_bytes()), '-o', str(self.output)]
        payload = json.dumps([{'symbol': 'first', 'body': 'return 3;'}])
        cases = [[], ['--body-text', 'return 3;'],
                 ['--edits-text', payload, '--symbol', 'first'],
                 ['--edits-text', payload, '--body-text', 'return 3;'],
                 ['--edits-text', payload, '--body', 'unused.ail']]
        before = self.source.read_bytes()
        for options in cases:
            with self.subTest(options=options), patch.dict(os.environ, {'PATH': ''}), \
                    patch.object(ail_chatgpt.subprocess, 'run', side_effect=AssertionError('no process')), \
                    redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    ail_chatgpt.main(common + options)
                self.assertEqual(raised.exception.code, 2)
                self.assertEqual(self.source.read_bytes(), before)
                self.assertFalse(self.output.exists())

    def test_first_target_context_binds_root_and_all_dependency_hashes(self):
        dependency = self.root / 'neighbor.ail'
        dependency.write_bytes(b'fn imported()->int {return 5;}')
        original = b'use neighbor; fn first()->int {return imported();} fn second()->int {return 2;} fn main()->int {return first()+second();}'
        self.source.write_bytes(original)
        context_file = self.root / 'context.json'
        payload = context(original, 'first', source_path=self.source, resolve_imports=True)
        context_file.write_text(json.dumps(payload), encoding='utf8')
        edits = [{'symbol': 'first', 'body': 'return imported()+1;'}, {'symbol': 'second', 'body': 'return 8;'}]
        status, report, calls = self.batch(edits, extra=('--context', context_file))
        self.assertEqual(status, 0, report)
        self.assertEqual(calls, 1)
        self.assertEqual(report['dependency_sha256'], payload['dependency_sha256'])
        for kind in ('first_target', 'root', 'dependency'):
            self.source.write_bytes(original)
            dependency.write_bytes(b'fn imported()->int {return 5;}')
            selected = list(reversed(edits)) if kind == 'first_target' else edits
            if kind == 'root':
                self.source.write_bytes(original + b'\n# changed root\n')
            if kind == 'dependency':
                dependency.write_bytes(b'fn imported()->int {return 6;}')
            output = self.root / (kind + '.ail')
            with self.subTest(kind=kind):
                status, report, calls = self.batch(selected, output=output, extra=('--context', context_file))
                self.assertNotEqual(status, 0, report)
                self.assertEqual(calls, 0)
                self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()