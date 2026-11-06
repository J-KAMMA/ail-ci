"""tools/wasm_build.py builds AIL's C for wasm32-wasi with zig cc; the result runs under wasmtime.

Skipped when zig or wasmtime is missing (zig as test_ail_cross_target.py finds it; wasmtime as AIL_WASMTIME,
`wasmtime` on PATH or ~/tools/wasmtime). Builds hello and three compare-lab tasks and compares their output with
the tasks' CPython oracle (reference.py) on their public cases; try/except runs on wasm exception handling.
"""
import importlib.util
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
sys.path.insert(0, str(REPO / 'tools'))
import wasm_build  # noqa: E402


def _wasmtime():
    local = Path.home() / 'tools' / ('wasmtime.exe' if os.name == 'nt' else 'wasmtime')
    return os.environ.get('AIL_WASMTIME') or shutil.which('wasmtime') or (str(local) if local.is_file() else None)


@unittest.skipUnless(wasm_build.zig(), 'zig is not installed')
@unittest.skipUnless(_wasmtime(), 'wasmtime is not installed')
class WasmTests(unittest.TestCase):
    def build(self, work, src):
        out = work / (src.stem + '.wasm')
        ok, msg = wasm_build.build(src, out, work / ('w-' + src.parent.name + '-' + src.stem))
        self.assertTrue(ok, msg)
        return out

    def run_wasm(self, wasm, args=(), stdin=None, dirs=()):
        cmd = [_wasmtime(), 'run', *wasm_build.WASMTIME_FLAGS]
        for d in dirs:
            cmd += ['--dir', '%s::%s' % (d, d)]
        return subprocess.run(cmd + [str(wasm), *args], input=stdin, capture_output=True, timeout=120)

    def test_hello(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            src = work / 'hello.py'
            src.write_text('n = 6 * 7\nprint("hello", n, str(n) * 2)\n')
            r = self.run_wasm(self.build(work, src))
            self.assertEqual((r.returncode, r.stdout), (0, b'hello 42 4242\n'))

    def test_try_except(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            src = work / 'exc.py'
            src.write_text('def f(x: int) -> int:\n    return 10 // x\n\ntry:\n    print(f(2))\n    print(f(0))\n'
                           'except ZeroDivisionError:\n    print("caught")\nprint(f(0))\n')
            r = self.run_wasm(self.build(work, src))
            self.assertEqual((r.returncode, r.stdout), (1, b'5\ncaught\n'))
            self.assertIn(b'ZeroDivisionError', r.stderr)

    def check_task(self, task):
        base = REPO / 'lab' / 'compare'
        spec = importlib.util.spec_from_file_location('gen_' + task, base / 'tasks' / task / 'gen.py')
        gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gen)
        public, _hidden, _perf = gen.cases(random.Random('%s-20261012' % task))
        stdin_mode = bool(getattr(gen, 'STDIN', False))
        src = base / 'src' / task / 'typed.py'
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            wasm = self.build(work, src)
            for k, (name, data, args) in enumerate(public):
                path = work / ('case-%d.bin' % k)
                path.write_bytes(data)
                argv = [a.replace('{input}', str(path)) for a in args]
                stdin = data if stdin_mode else b''
                want = subprocess.run([sys.executable, '-B', str(base / 'tasks' / task / 'reference.py'), *argv], input=stdin, capture_output=True, timeout=120)
                got = self.run_wasm(wasm, argv, stdin, dirs=[work])
                self.assertEqual((got.returncode, got.stdout), (want.returncode, want.stdout), '%s %s' % (task, name))

    def test_task_chain_relax(self):
        self.check_task('chain_relax')

    def test_task_tally_lang(self):
        self.check_task('tally_lang')

    def test_task_tree_fold(self):
        # read_stdin_bytes(1 << 40): needs wasm_build.patch_c's saturation for wasm32's 32-bit size_t
        self.check_task('tree_fold')

    def test_patch_c_refuses_a_changed_reader(self):
        text = 'static unsigned char *ail_stdin_fill_bytes(unsigned char *buf, size_t *capp) {}\n'
        self.assertIn('changed shape', wasm_build.patch_c(text)[1])
        self.assertEqual(wasm_build.patch_c('int main(void) { return 0; }\n'), ('int main(void) { return 0; }\n', ''))


if __name__ == '__main__':
    unittest.main()
