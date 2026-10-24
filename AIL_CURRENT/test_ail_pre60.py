"""pre60: iterating an instance whose only iteration protocol is __getitem__.

CPython falls back to the sequence protocol: it calls ``obj[0]``, ``obj[1]``, ... and
stops at the first ``IndexError``.  AIL refused such an instance on both builds with
``TypeError: 'instance' object is not iterable``.  The general-path runtime now has an
iterator kind that carries the index and calls ``__getitem__``; ``__iter__`` still wins
when the class defines both.  Every program below is compared with CPython 3.12 on the
default and forced-general builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

BASIC = r'''class Keys:
    def __init__(self, xs):
        self.xs = xs

    def __getitem__(self, i):
        if i >= len(self.xs):
            raise IndexError
        return self.xs[i]


class Box:
    def __init__(self, seq):
        self.seq = seq


def take(seq):
    return list(seq)


def main():
    keys = Keys([10, 20, 30])
    print(list(keys), tuple(keys), sum(keys))
    print([x * 2 for x in keys])
    for x in keys:
        print(x, end=" ")
    print()
    it = iter(keys)
    print(next(it), next(it), next(it))
    try:
        next(it)
    except StopIteration:
        print("stop")
    empty = Keys([])
    print(list(empty), tuple(empty), sum(empty), any(empty), all(empty))
    mixed = Keys(["a", 2, 3.5, None, True, (1, 2)])
    print(take(mixed))
    boxes = [Box(Keys([7, 8])), {"k": Keys(["x", "y"])}]
    print(list(boxes[0].seq), list(boxes[1]["k"]))
    print(dict(zip(Keys(["a", "b"]), Keys([1, 2]))))
    print(list(enumerate(Keys(["p", "q"]), 3)))
    print("b" in Keys(["a", "b"]), "z" in Keys(["a", "b"]))
    a, b = Keys([4, 5])
    print(a, b)
    xs = [1, 2]
    live = Keys(xs)
    live_it = iter(live)
    print(next(live_it))
    xs.append(3)
    print(next(live_it), next(live_it))
    print(list(live) == xs)


main()
'''

PROTOCOL = r'''class MyIndexError(IndexError):
    pass


class Stops:
    def __getitem__(self, i):
        if i < 2:
            return i
        raise MyIndexError("done")


class Boom:
    def __getitem__(self, i):
        if i == 0:
            return 1
        raise ValueError("boom")


class Base:
    def __getitem__(self, i):
        if i >= 2:
            raise IndexError
        return i + 10


class Child(Base):
    pass


class IterWins:
    def __iter__(self):
        return iter([9, 8])

    def __getitem__(self, i):
        if i >= 2:
            raise IndexError
        return i + 100


def main():
    print(list(Stops()), list(Child()), list(IterWins()))
    try:
        list(Boom())
    except ValueError as e:
        print("ValueError", e)
    direct = Stops()
    print(direct[0], direct[1])
    try:
        direct[2]
    except IndexError as e:
        print(type(e).__name__, e)


main()
'''


def _run_py(path):
    done = subprocess.run([sys.executable, '-B', str(path)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.returncode, done.stdout.replace(b'\r\n', b'\n')


def _build_and_run(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name)
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.returncode, got.stdout.replace(b'\r\n', b'\n')), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre60Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre60-') as directory:
            want = _run_py(_write(directory, slug, text))
            for general in (True, False):
                name = '%s_%s' % (slug, 'g' if general else 'd')
                got, build_err = _build_and_run(directory, name, text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, want, '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_sequence_protocol(self):
        self.check('seqproto', BASIC)

    def test_sequence_protocol_errors(self):
        self.check('seqproto_errors', PROTOCOL)


def _write(directory, slug, text):
    path = Path(directory) / (slug + '_cpython.py')
    path.write_text(text, encoding='utf-8')
    return path


if __name__ == '__main__':
    unittest.main()
