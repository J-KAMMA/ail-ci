"""lab/wedge3: the real-library hybrid measurement artefact (job wedge3).

The measurement needs five pip-installed libraries and the obs5 hybrid compiler, so this test
does not re-run it.  It pins the committed shape and the facts the report relies on: five pairs,
zero native functions, byte-identical hybrid output, pinned requirements, and no library source
vendored into the repository.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT.parent / 'lab' / 'wedge3'
RESULTS = LAB / 'results.json'
PAIRS = {'networkx', 'jsonschema', 'chardet', 'tomli', 'difflib'}
RUST = {
    'networkx': 'rustworkx',
    'jsonschema': 'jsonschema-rs',
    'chardet': 'charset-normalizer',
    'tomli': 'rtoml',
    'difflib': 'rapidfuzz',
}


class Wedge3Test(unittest.TestCase):
    def test_results_shape(self):
        data = json.loads(RESULTS.read_text())
        self.assertEqual(set(data['pairs']), PAIRS)
        for name, rec in data['pairs'].items():
            self.assertEqual(rec['rust_impl'], RUST[name])
            for cfg in ('plain', 'obs'):
                self.assertIn(cfg, rec['builds'])
                for mod, build in rec['builds'][cfg].items():
                    self.assertIsInstance(build['accelerated'], list)
                    self.assertIsInstance(build['rejected'], dict)
            self.assertTrue(rec['stdout_match']['hybrid'], name)
            self.assertTrue(rec['stdout_match']['hybrid_obs'], name)
            self.assertTrue(rec['stdout_match']['pypy'], name)
            for tag in ('cpython', 'pypy', 'hybrid', 'hybrid_obs', 'rust'):
                self.assertGreater(rec['times'][tag], 0.0, (name, tag))
            total = sum(len(b['accelerated']) + len(b['rejected'])
                        for b in rec['builds']['plain'].values())
            native = sum(len(b['accelerated']) for b in rec['builds']['plain'].values())
            self.assertEqual(native, 0, name)
            self.assertGreater(total, 0, name)

    def test_report_records_compiler_commit(self):
        text = (LAB / 'RESULTS.md').read_text()
        self.assertRegex(text, r'\b[0-9a-f]{40}\b')
        self.assertIn('job-obs5-op1109', text)
        self.assertIn('0 of 191', text)

    def test_no_vendored_library_source(self):
        banned = {'networkx', 'rustworkx', 'jsonschema', 'jsonschema_rs', 'chardet',
                  'charset_normalizer', 'tomli', 'rtoml', 'rapidfuzz', 'difflib'}
        for path in LAB.rglob('*'):
            if '__pycache__' in path.parts:
                continue
            if path.is_dir():
                self.assertNotIn(path.name, banned, path)
            elif path.is_file():
                self.assertIn(path.suffix, {'.py', '.txt', '.json', '.md', '.sh', '.sql'}, path)

    def test_scripts_compile(self):
        for path in [LAB / 'measure.py', *sorted((LAB / 'workloads').glob('*.py'))]:
            compile(path.read_text(), str(path), 'exec')

    def test_requirements_are_pinned(self):
        lines = [ln.strip() for ln in (LAB / 'requirements.txt').read_text().splitlines()]
        pins = [ln for ln in lines if ln and not ln.startswith('#')]
        self.assertGreaterEqual(len(pins), 5)
        for pin in pins:
            self.assertRegex(pin, r'^[A-Za-z0-9_.-]+==[0-9][^ ]*$')


if __name__ == '__main__':
    unittest.main()
