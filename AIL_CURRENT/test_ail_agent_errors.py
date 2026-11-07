"""The `--json` machine form of a compiler diagnostic (docs/design/AGENT_ERRORS.md, step 1).

One program per message family from `lab/err/triggers/` is compiled with `--json`.  The build
report carries `agent_diagnostics`, one object per known family:

    {"code","severity","file","line","col","cause","message","fix":{"replace_range","with"}}

`message` is the human note byte for byte.  The literal `fix` is applied to the source (whole
lines, 1-based inclusive) and the result must build; for every family but the compiler-internal
row-arity note (AIL0102, implementation step 2) the family's message must be gone.  Every fixed
program also prints what CPython prints.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
CLI = ROOT / 'ail_chatgpt.py'
TRIGGERS = REPO / 'lab' / 'err' / 'triggers'
ORIGINAL = REPO / 'lab' / 'err' / 'messages_original.json'

CODES = {
    '01_stdin_buffer': 'AIL0101', '02_poprow_arity': 'AIL0102', '03_str_number': 'AIL0103',
    '04_dict_get_optional': 'AIL0104', '05_dict_of_containers': 'AIL0105',
    '06_class_list_comp': 'AIL0106', '07_bool_number_mix': 'AIL0107',
    '08_bytes_number_return': 'AIL0108', '09_while_else': 'AIL0109',
    '10_nested_annotation': 'AIL0110', '11_fraction_dunder': 'AIL0111',
    '12_decimal_format': 'AIL0112', '13_yield': 'AIL0113',
    '14_tuple_single_value': 'AIL0114', '15_list_param_readonly': 'AIL0115',
}


class AgentErrors(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='ail-agent-errors-'))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.original = json.loads(ORIGINAL.read_text(encoding='utf-8'))

    def compile(self, source, name, as_json=True):
        command = [sys.executable, '-B', str(CLI), 'compile', str(source), '--syntax', 'python',
                   '-o', str(self.tmp / name)] + (['--json'] if as_json else [])
        environment = {key: value for key, value in os.environ.items()
                       if key not in ('AIL_NO_GENERAL', 'AIL_QUIET_FALLBACK', 'AIL_STRICT')}
        return subprocess.run(command, cwd=REPO, capture_output=True, text=True, timeout=900,
                              env=environment)

    def test_one_program_per_family(self):
        for stem, code in CODES.items():
            with self.subTest(stem=stem):
                source = Path('lab') / 'err' / 'triggers' / (stem + '.py')
                built = self.compile(source, stem)
                self.assertEqual(built.returncode, 0, built.stderr)
                report = json.loads(built.stdout)
                found = [item for item in report.get('agent_diagnostics', []) if item['code'] == code]
                self.assertEqual(len(found), 1, (code, report.get('agent_diagnostics')))
                item = found[0]
                self.assertEqual(item['severity'], 'note')
                self.assertEqual(item['file'], source.as_posix())
                self.assertIsInstance(item['line'], int)
                self.assertIsInstance(item['col'], int)
                self.assertTrue(item['cause'])
                self.assertEqual(item['message'], self.original[stem])
                fix = item['fix']
                self.assertEqual(len(fix['replace_range']), 2)
                self.assertLessEqual(fix['replace_range'][0], fix['replace_range'][1])
                self.assertTrue(fix['with'])

                text = (REPO / source).read_text(encoding='utf-8')
                lines = text.split('\n')
                first, last = fix['replace_range']
                fixed = '\n'.join(lines[:first - 1] + fix['with'].split('\n') + lines[last:])
                fixed_path = self.tmp / (stem + '_fixed.py')
                fixed_path.write_text(fixed, encoding='utf-8')
                rebuilt = self.compile(fixed_path, stem + '_fixed')
                self.assertEqual(rebuilt.returncode, 0, rebuilt.stderr)
                after = [entry['code'] for entry in json.loads(rebuilt.stdout).get('agent_diagnostics', [])]
                if code == 'AIL0102':
                    # the note comes from a compiler temporary (implementation step 2): the literal
                    # edit builds and keeps the output, but no source edit can rename that temporary
                    self.assertIn(code, after, 'AIL0102 needs the compiler-side row-arity fix')
                else:
                    self.assertNotIn(code, after, after)

    def test_fixed_program_prints_what_cpython_prints(self):
        for stem in CODES:
            with self.subTest(stem=stem):
                source = REPO / 'lab' / 'err' / 'triggers' / (stem + '.py')
                built = self.compile(source, stem + '_run')
                self.assertEqual(built.returncode, 0, built.stderr)
                item = next(item for item in json.loads(built.stdout)['agent_diagnostics']
                            if item['code'] == CODES[stem])
                lines = source.read_text(encoding='utf-8').split('\n')
                first, last = item['fix']['replace_range']
                fixed = '\n'.join(lines[:first - 1] + item['fix']['with'].split('\n') + lines[last:])
                fixed_path = self.tmp / (stem + '_run.py')
                fixed_path.write_text(fixed, encoding='utf-8')
                rebuilt = self.compile(fixed_path, stem + '_run_fixed')
                self.assertEqual(rebuilt.returncode, 0, rebuilt.stderr)
                stdin = source.with_suffix('.in')
                data = stdin.read_bytes() if stdin.is_file() else b''
                native = subprocess.run([str(self.tmp / (stem + '_run_fixed'))], input=data,
                                        capture_output=True, timeout=120)
                cpython = subprocess.run([sys.executable, str(fixed_path)], input=data,
                                         capture_output=True, timeout=120)
                self.assertEqual((native.returncode, native.stdout), (cpython.returncode, cpython.stdout))


if __name__ == '__main__':
    unittest.main()
