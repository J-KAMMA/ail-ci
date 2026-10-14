"""A compiler-diagnosed batch error is repaired and run against an independent oracle."""
import hashlib
import json
import os
import shutil
import subprocess
import unittest

import test_ail_c_objects as support


class OwnedTypeRepairTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    command = support.CObjectTests.command
    write = support.CObjectTests.write

    def test_diagnose_edit_compile_and_batch_output(self):
        examples = support.ROOT / 'language_examples'
        for name in ('config_core.ail', 'checked_integer.ail', 'json_text.ail'):
            shutil.copy2(examples / name, self.root / name)
        correct = (examples / 'config_batch.ail').read_bytes()
        needle = b'errors.append(error);'
        self.assertEqual(correct.count(needle), 1)
        original = correct.replace(needle, b'errors.append(7);')
        source = self.root / 'broken.ail'; source.write_bytes(original)
        checked = self.command('check', source, '--repair-context')
        self.assertEqual(checked.returncode, 1)
        report = json.loads(checked.stdout)
        diagnostic = report['diagnostics'][0]
        self.assertEqual(diagnostic['type_details'], {'operation': 'element', 'action': 'append',
                         'container': 'list[exception]', 'expected': 'exception', 'actual': 'int'})
        repair = report['repair_context']
        self.assertEqual((repair['status'], repair['target']), ('available', 'validate_many'))
        self.assertFalse(repair['type_verified'])
        self.assertFalse(repair['runtime_verified'])
        self.assertEqual(repair['source_sha256'], hashlib.sha256(original).hexdigest())
        context = self.root / 'context.json'; context.write_text(json.dumps(repair), encoding='utf8')
        body = self.root / 'body.txt'
        body.write_bytes(repair['body'].replace('errors.append(7);', 'errors.append(error);').encode('utf8'))
        fixed = self.root / 'fixed.ail'
        edited = self.command('edit', source, '--symbol', repair['target'], '--context', context, '--body', body,
                              '--base-sha256', repair['source_sha256'], '-o', fixed)
        self.assertEqual(edited.returncode, 0, edited.stderr.decode(errors='replace'))
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(fixed.read_bytes(), correct)
        executable = self.root / ('batch.exe' if os.name == 'nt' else 'batch')
        built = self.command('compile', fixed, '-o', executable)
        self.assertEqual(built.returncode, 0, built.stderr.decode(errors='replace'))
        good = self.root / 'valid.txt'; good.write_bytes(b'x=2\ny=-3')
        bad = self.root / 'invalid 日本.txt'; bad.write_bytes('x=日本😀'.encode())
        expected = {'reports': [{'path': str(good), 'summary': {'count': 2, 'total': -1}}],
                    'errors': [{'path': str(bad), 'kind': 'ValueError', 'message': 'line 1: invalid integer: 日本😀'}]}
        actual = subprocess.run([str(executable), str(good), str(bad)], capture_output=True, timeout=30)
        self.assertEqual((actual.returncode, actual.stderr), (2, b''))
        self.assertEqual(actual.stdout, (json.dumps(expected, ensure_ascii=False, separators=(',', ':')) + '\n').encode())


if __name__ == '__main__':
    unittest.main()