"""GPU smoke: six fast checks of a `--gpu` build on the Vulkan device of the CI `gpu (lavapipe)` job.

This module is the first thing to read when that job turns red.  Two marked programs
(`gpu_smoke_cases/int64_map.py`, `gpu_smoke_cases/binary64_map.py`) are built once with `--gpu` and the
binary is reused by every check:

1. the Vulkan loader and a device are found (`AIL_GPU_TRACE=1` shows `device=llvmpipe`);
2. the int64 kernel's stdout and exit status equal CPython's and the `AIL_GPU=0` run's;
3. the same for the binary64 kernel;
4. with no loader (`AIL_VULKAN_LIB=/nonexistent`) the CPU fallback prints the same and the trace shows the CPU path;
5. an index error planted at element 3000 is replayed and the program prints what CPython prints;
6. every emitted module passes `spirv-val` (skipped when `spirv-val` is missing; the gpu job, which sets
   `AIL_GPU_REQUIRE_DEVICE=1`, fails instead because it installs spirv-tools).

Each check prints one `smoke: <name> ok <ms>` line.  A missing device skips checks 1-3 locally and fails them when
`AIL_GPU_REQUIRE_DEVICE=1` is set (as the CI job does).
"""
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

__all__ = ['GPUSmoke']

ROOT = Path(__file__).resolve().parent
CASES = ROOT / 'gpu_smoke_cases'
CLI = ROOT / 'ail_chatgpt.py'
CC = shutil.which('cc') or shutil.which('gcc') or shutil.which('clang')
REQUIRE_DEVICE = os.environ.get('AIL_GPU_REQUIRE_DEVICE', '') not in ('', '0')
SPIRV_VAL = os.environ.get('SPIRV_VAL') or shutil.which('spirv-val')

SPV_ARRAY = re.compile(r'static const uint32_t (ail_gk\d+_spv)\[(\d+)\] = \{(.*?)\};', re.S)


def _clean_env():
    env = dict(os.environ)
    for key in ('AIL_GPU', 'AIL_GPU_TRACE', 'AIL_GPU_DISABLE', 'AIL_VULKAN_LIB', 'AIL_GPU_DEVICE',
                'AIL_GPU_MIN_N', 'AIL_GPU_BUILD', 'AIL_UNIFIED_FORCE'):
        env.pop(key, None)
    return env


class Build:
    """One `ail_chatgpt.py compile --gpu` of one case program; the binary is reused by every check."""

    def __init__(self, directory, name):
        self.name = name
        self.src = CASES / (name + '.py')
        self.build_dir = Path(directory) / name
        self.build_dir.mkdir()
        self.exe = self.build_dir / (name + '.exe')
        self.debug = self.build_dir / 'dbg'
        env = _clean_env()
        env.update(AIL_NO_CACHE='1', AIL_NO_GENERAL='1')
        cmd = [sys.executable, '-B', str(CLI), 'compile', str(self.src), '-o', str(self.exe), '--no-cache',
               '--gpu', '--debug-dir', str(self.debug)]
        r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=900)
        self.returncode, self.stdout, self.stderr = r.returncode, r.stdout, r.stderr

    def run(self, **env):
        r = subprocess.run([str(self.exe)], capture_output=True, text=True, env=_clean_env() | env, timeout=600)
        return r.stdout, r.returncode, r.stderr

    def c_source(self):
        return next(self.debug.glob('program.c')).read_text(encoding='utf-8')

    def spirv_modules(self):
        """(name, words) for every `static const uint32_t ail_gk<k>_spv[n]` in the generated C."""
        out = []
        for name, count, body in SPV_ARRAY.findall(self.c_source()):
            words = [int(w, 16) for w in re.findall(r'0x([0-9a-fA-F]+)u', body)]
            assert len(words) == int(count), '%s: %d words, header says %s' % (name, len(words), count)
            out.append((name, words))
        return out


def run_cpython(src):
    r = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, text=True, timeout=300)
    return r.stdout, r.returncode


def device_runs(stderr):
    return [l for l in stderr.splitlines()
            if l.startswith('gpu: ') and re.search(r'n=\d+ device=(?!emulation)', l)]


class GPUSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not CC:
            raise unittest.SkipTest('no C compiler')
        cls._tmp = tempfile.TemporaryDirectory(prefix='ail-gpu-smoke-')
        d = cls._tmp.name
        cls.i64 = Build(d, 'int64_map')
        cls.f64 = Build(d, 'binary64_map')
        cls.idx = Build(d, 'index_error')
        for b in (cls.i64, cls.f64, cls.idx):
            if b.returncode != 0:
                raise AssertionError('%s did not build:\n%s' % (b.name, b.stderr + b.stdout))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def ok(self, name, started):
        print('smoke: %s ok %d' % (name, round((time.perf_counter() - started) * 1000)), flush=True)

    def assert_same(self, build, want, label, **env):
        out, rc, err = build.run(**env)
        self.assertEqual((out, rc), want, '%s: stdout/exit differ\n--- got ---\n%s\n--- want ---\n%s\n%s'
                         % (label, out, want[0], err))
        return err

    # -- 1
    def test_01_device_found(self):
        started = time.perf_counter()
        _, _, err = self.i64.run(AIL_GPU='force', AIL_GPU_TRACE='1')
        runs = device_runs(err)
        if not runs:
            if REQUIRE_DEVICE:
                self.fail('no Vulkan device, but AIL_GPU_REQUIRE_DEVICE is set:\n' + err)
            raise unittest.SkipTest('no Vulkan device (install mesa-vulkan-drivers for lavapipe)')
        self.assertIn('device=llvmpipe', '\n'.join(runs), 'the device is not lavapipe/llvmpipe:\n' + err)
        self.ok('device', started)

    # -- 2, 3
    def _kernel_matches(self, build):
        want = run_cpython(build.src)
        cpu = self.assert_same(build, want, 'AIL_GPU=0', AIL_GPU='0')
        gpu = self.assert_same(build, want, 'AIL_GPU=force', AIL_GPU='force', AIL_GPU_TRACE='1')
        if REQUIRE_DEVICE:
            self.assertTrue(device_runs(gpu), 'the launch did not run on the device:\n' + gpu)
        return cpu

    def test_02_int64_kernel(self):
        started = time.perf_counter()
        self._kernel_matches(self.i64)
        self.ok('int64', started)

    def test_03_binary64_kernel(self):
        started = time.perf_counter()
        self._kernel_matches(self.f64)
        self.ok('binary64', started)

    # -- 4
    def test_04_no_loader_falls_back(self):
        started = time.perf_counter()
        for build in (self.i64, self.f64):
            want = run_cpython(build.src)
            err = self.assert_same(build, want, 'no loader', AIL_GPU='force',
                                   AIL_VULKAN_LIB='/nonexistent/libvulkan.so.1', AIL_GPU_TRACE='1')
            self.assertIn('no Vulkan loader', err, 'the trace does not name the missing loader:\n' + err)
            self.assertFalse(device_runs(err), 'a device ran although the loader is missing:\n' + err)
            self.assertRegex(err, r'device=emulation|gpu: k\d+ cpu \(',
                             'the trace does not show the CPU path:\n' + err)
        self.ok('no-loader', started)

    # -- 5
    def test_05_error_replay(self):
        started = time.perf_counter()
        want = run_cpython(self.idx.src)
        _, rc, err = self.idx.run(AIL_GPU='force', AIL_GPU_TRACE='1')
        out_cpu, rc_cpu, _ = self.idx.run(AIL_GPU='0')
        self.assertEqual((out_cpu, rc_cpu), want, 'the CPU loop differs from CPython')
        self.assertEqual(rc, want[1], 'the replay exit status differs from CPython:\n' + err)
        self.assertIn('replay', err, 'the launch was not replayed:\n' + err)
        self.assertIn('index', err, 'the replay does not name the index flag:\n' + err)
        self.ok('replay', started)

    # -- 6
    def test_06_spirv_valid(self):
        started = time.perf_counter()
        if not SPIRV_VAL:
            if REQUIRE_DEVICE:
                self.fail('spirv-val is missing in the GPU job (apt install spirv-tools)')
            raise unittest.SkipTest('spirv-val not installed (apt install spirv-tools)')
        total = 0
        with tempfile.TemporaryDirectory(prefix='ail-gpu-smoke-spv-') as d:
            for build in (self.i64, self.f64, self.idx):
                mods = build.spirv_modules()
                self.assertTrue(mods, '%s: no emitted module in the generated C' % build.name)
                for name, words in mods:
                    path = Path(d) / (build.name + '-' + name + '.spv')
                    path.write_bytes(struct.pack('<%dI' % len(words), *words))
                    r = subprocess.run([SPIRV_VAL, '--target-env', 'vulkan1.2', str(path)],
                                       capture_output=True, text=True)
                    self.assertEqual(r.returncode, 0, '%s %s:\n%s' % (build.name, name, r.stdout + r.stderr))
                    total += 1
        self.assertGreaterEqual(total, 3, 'expected one module per case')
        self.ok('spirv-val', started)


if __name__ == '__main__':
    unittest.main()
