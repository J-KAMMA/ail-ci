"""AIL_FE_JOBS: parallel per-function front end, byte-identical C to the serial compiler.

The generated C is the contract: the parallel path replays every generated-name request and every
class sort/heap specialization in the serial function order, so only wall time changes.
"""
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent
PKG = ROOT / 'python/pkg-v12'

SOURCE = '''
class Item:
    def __init__(self, t: int, b: str, i: int) -> None:
        self.t = t
        self.b = b
        self.i = i


def allocate(n: int) -> int:
    values = [i for i in range(64)]
    spare = [n, n + 1]
    try:
        if n % 2 == 0:
            raise ValueError()
        return values[-1]
    finally:
        values.append(n)
        spare.append(n)


def middle(n: int) -> int:
    values = [n, n + 1]
    try:
        return allocate(n) + values[0]
    except IndexError:
        return -1


def run(n: int) -> int:
    retained = [17, 23]
    total = 0
    for i in range(n):
        try:
            total += middle(i)
        except ValueError:
            total += retained[0]
        retained[1] = 23
    return total + retained[1]


def sort_t(xs: list[Item]) -> int:
    return sorted(xs, key=lambda n: n.t)[0].i


def sort_tb(xs: list[Item]) -> int:
    return sorted(xs, key=lambda n: (n.b, n.t))[0].i


def sort_bt(xs: list[Item]) -> int:
    return sorted(xs, key=lambda n: (-n.t, n.b), reverse=True)[0].i


def heap_t(xs: list[Item]) -> int:
    h = xs.copy()
    heapify(h, key=lambda n: n.t)
    return heappop(h, key=lambda n: n.t).i


def heap_bt(xs: list[Item]) -> int:
    h = xs.copy()
    heapify(h, key=lambda n: (n.b, n.t))
    return heappop(h, key=lambda n: (n.b, n.t)).i


def pad0(n: int) -> int:
    return n + 1


def pad1(n: int) -> int:
    return n + 2


def pad2(n: int) -> int:
    return n + 3


def main() -> int:
    xs = [Item(3, "c", 1), Item(1, "a", 2), Item(2, "b", 3), Item(1, "d", 4)]
    print(run(3), sort_t(xs), sort_tb(xs), sort_bt(xs), heap_t(xs), heap_bt(xs))
    print(pad0(1), pad1(1), pad2(1))
    return 0
'''

# Try/finally in class methods and module functions, a clone-producing call site (the same function
# called with an int and a float), locals and functions whose names look like generated helpers
# (`_handled_boundary`, `_handled_entry`, `_ail_frame_cells`, `v__handled_boundary`), and a function
# named like the finally-release helper.  The generated-name replay has to keep all of these apart.
COVERAGE = '''
class Box:
    def __init__(self, v: int) -> None:
        self.v = v

    def fetch(self, n: int) -> int:
        total = 0
        try:
            for i in range(n):
                if i == 2:
                    raise ValueError()
                total += self.v
        finally:
            total += 100
        return total

    def other(self, n: int) -> int:
        try:
            if n < 0:
                raise KeyError()
            return n * 2
        except KeyError:
            return -1
        finally:
            n += 1


def v__handled_boundary(n: int) -> int:
    return n + 1


def v__handled_entry(n: int) -> int:
    return n + 2


def clone_source(x):
    v = 0
    try:
        v = v + 1
        return v
    finally:
        v = v + 1


def clone_int() -> int:
    return clone_source(1)


def clone_float() -> int:
    return clone_source(1.5)


def first(n: int) -> int:
    x = 0
    try:
        x += n
        return x
    finally:
        x += 1


def second(n: int) -> int:
    _handled_boundary = n
    _handled_entry = n + 1
    try:
        if n > 3:
            raise ValueError()
        return v__handled_boundary(_handled_boundary) + v__handled_entry(_handled_entry)
    finally:
        _handled_boundary += 1


def _ail_finally_release_first(n: int) -> int:
    return n + 3


def third(n: int) -> int:
    try:
        return first(n) + second(n) + clone_int() + clone_float()
    except ValueError:
        return -7


def fourth(n: int) -> int:
    _ail_frame_cells = n
    try:
        return _ail_finally_release_first(_ail_frame_cells)
    finally:
        _ail_frame_cells += 1


def fifth(n: int) -> int:
    out = 0
    try:
        out += Box(n).fetch(4)
    except ValueError:
        out -= 1
    finally:
        out += 2
    return out


def pad0(n: int) -> int:
    return n + 1


def pad1(n: int) -> int:
    return n + 2


def pad2(n: int) -> int:
    return n + 3


def main() -> int:
    b = Box(5)
    print(b.fetch(2), b.other(4), b.other(-1))
    print(first(2), second(2), third(4), fourth(1), fifth(3))
    print(clone_int(), clone_float(), pad0(1), pad1(1), pad2(1))
    return 0
'''

SOURCES = (SOURCE, COVERAGE)

CODE = ('import sys\n'
        'sys.path.insert(0, %r)\n'
        'from pyfunc import to_c\n'
        'sys.stdout.write(to_c(sys.stdin.read(), strict=True, name="probe"))\n' % str(PKG))


class FeJobsTests(unittest.TestCase):
    def compile_c(self, source=SOURCE, jobs=None, seed=None):
        env = {key: value for key, value in os.environ.items()
               if not key.startswith('AIL_') and key != 'PYTHONHASHSEED'}
        env['PYTHONUTF8'] = '1'
        if jobs is not None:
            env['AIL_FE_JOBS'] = str(jobs)
        if seed is not None:
            env['PYTHONHASHSEED'] = str(seed)
        result = subprocess.run([sys.executable, '-X', 'utf8', '-c', CODE], input=source,
                                capture_output=True, text=True, env=env, timeout=180)
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        return result.stdout

    def test_parallel_matches_serial_with_generated_names_and_class_specs(self):
        for source in SOURCES:
            with self.subTest(source=source.strip().splitlines()[0]):
                serial = self.compile_c(source, jobs=1)
                self.assertNotEqual(serial, '')
                parallel = self.compile_c(source, jobs=4)
                self.assertNotIn('\x01AILFE', parallel)
                self.assertEqual(parallel, serial)

    def test_default_and_invalid_jobs_stay_byte_identical(self):
        for source in SOURCES:
            with self.subTest(source=source.strip().splitlines()[0]):
                serial = self.compile_c(source, jobs=1)
                self.assertEqual(self.compile_c(source), serial)
                self.assertEqual(self.compile_c(source, jobs='nonsense'), serial)

    def test_parallel_matches_serial_across_hash_seeds(self):
        for source in SOURCES:
            for seed in ('0', '3', '5', 'random'):
                with self.subTest(source=source.strip().splitlines()[0], seed=seed):
                    self.assertEqual(self.compile_c(source, jobs=4, seed=seed),
                                     self.compile_c(source, jobs=1, seed=seed))

    def test_job_count_defaults_and_serial_conditions(self):
        sys.path.insert(0, str(PKG))
        try:
            import pyfunc
            with mock.patch.dict(os.environ, {}, clear=True), \
                    mock.patch.object(pyfunc.os, 'cpu_count', return_value=8):
                self.assertEqual(pyfunc._fe_job_count(7, None), 1)
                self.assertEqual(pyfunc._fe_job_count(8, None), 4)
                self.assertEqual(pyfunc._fe_job_count(64, None), 4)
                with mock.patch.dict(os.environ, {'AIL_FE_JOBS': '6'}):
                    self.assertEqual(pyfunc._fe_job_count(64, None), 6)
                with mock.patch.dict(os.environ, {'AIL_FE_JOBS': '4'}):
                    self.assertEqual(pyfunc._fe_job_count(7, None), 4)
                    self.assertEqual(pyfunc._fe_job_count(1, None), 1)
                with mock.patch.dict(os.environ, {'AIL_FE_JOBS': '1'}):
                    self.assertEqual(pyfunc._fe_job_count(64, None), 1)
                with mock.patch.dict(os.environ, {'AIL_FE_JOBS': 'bad'}):
                    self.assertEqual(pyfunc._fe_job_count(64, None), 1)
                with mock.patch.dict(os.environ, {'AIL_DEBUG': '1'}):
                    self.assertEqual(pyfunc._fe_job_count(64, None), 1)
                with mock.patch.dict(os.environ, {'AIL_NO_FE_PARALLEL': '1'}):
                    self.assertEqual(pyfunc._fe_job_count(64, None), 1)
                self.assertEqual(pyfunc._fe_job_count(64, {'_want_units': True}), 1)
                self.assertEqual(pyfunc._fe_job_count(64, {'_want_source_regions': True}), 1)
        finally:
            sys.path.remove(str(PKG))

    def test_parallel_only_when_the_work_can_be_balanced(self):
        sys.path.insert(0, str(PKG))
        try:
            import pyfunc
            self.assertFalse(pyfunc._fe_worth_parallel([10] * 20))
            self.assertTrue(pyfunc._fe_worth_parallel([100] * 8))
            self.assertFalse(pyfunc._fe_worth_parallel([700] + [10] * 8))
        finally:
            sys.path.remove(str(PKG))


if __name__ == '__main__':
    unittest.main()
