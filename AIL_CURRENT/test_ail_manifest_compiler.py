"""A new compiler source joins sdk_files without hand-editing the manifest.

A job that adds python/pkg-v12/*.py (or a .h/.c compiler source) used to leave it pinned with '-',
so test_ail_packaging.test_every_compiler_file_is_selected and
test_ail_sdk.test_sdk_files_cover_every_compiler_module_import failed only at the integration gate.
This builds a temporary copy of the tree, adds a module and checks that update_manifest.py both
reports the missing flag under --check and selects the file when it updates the manifest.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
TOOL = REPO / 'tools' / 'update_manifest.py'
SUFFIXES = ('.py', '.h', '.c')
sys.path.insert(0, str(HERE))
import ail_manifest  # noqa: E402


def compiler_sources(root):
    """The set test_ail_packaging.test_every_compiler_file_is_selected checks."""
    compiler = root / 'python' / 'pkg-v12'
    wanted = {p.relative_to(root).as_posix() for p in compiler.rglob('*')
              if p.is_file() and p.suffix in SUFFIXES and '__pycache__' not in p.parts}
    wanted |= {p.relative_to(root).as_posix() for p in (root / 'stdlib').iterdir()
               if p.suffix in SUFFIXES}
    return wanted


class CompilerSourcesAreSelected(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ail-manifest-compiler-')
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / 'repo'
        self.repo.mkdir()
        ignore = shutil.ignore_patterns('__pycache__', '*.pyc')
        shutil.copytree(REPO / 'AIL_CURRENT', self.repo / 'AIL_CURRENT', ignore=ignore)
        shutil.copytree(REPO / 'tools', self.repo / 'tools', ignore=ignore)
        self.src = self.repo / 'AIL_CURRENT'
        self.git('init', '-q')
        self.git('add', '-A')

    def git(self, *args):
        return subprocess.run(['git', *args], cwd=self.repo, capture_output=True, text=True, check=True)

    def tool(self, *args):
        return subprocess.run([sys.executable, str(self.repo / 'tools' / 'update_manifest.py'), *args],
                              cwd=self.repo, capture_output=True, text=True)

    def test_new_compiler_module_is_reported_and_selected(self):
        name = 'python/pkg-v12/zz_manifest_compiler_probe.py'
        (self.src / name).write_text('# a new compiler module\n', encoding='utf-8')
        self.git('add', '-A')

        before = self.tool('--check')
        self.assertEqual(before.returncode, 1, before.stdout + before.stderr)
        self.assertIn(name, before.stdout)

        updated = self.tool()
        self.assertEqual(updated.returncode, 0, updated.stdout + updated.stderr)
        pins = ail_manifest.read_pins(self.src)
        self.assertIn(name, pins)
        self.assertIn('s', pins[name][1])

        after = self.tool('--check')
        self.assertEqual(after.returncode, 0, after.stdout + after.stderr)

        manifest = ail_manifest.load(self.src)
        wanted = compiler_sources(self.src)
        selected = set(manifest['sdk_files'])
        missing = sorted(source for source in wanted
                         if source in manifest['sha256'] and source not in selected)
        self.assertIn(name, wanted)
        self.assertIn(name, selected)
        self.assertEqual(missing, [], 'pinned compiler files missing from sdk_files')


if __name__ == '__main__':
    unittest.main()
