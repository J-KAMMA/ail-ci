"""String-list growth reserve and last-use release leave the program's output unchanged.

A list whose length is known from the loop's range is reserved once instead of doubling, and a
list[str] local is released after its last use like a numeric list.  This program builds lists of
str with an append loop (bounds, a negative or non-unit step, a conditional append, a clear first,
and a nested loop), with a comprehension, and through an alias and a returned value; CPython is the
oracle.  Both the IR emitter (AIL_IR=1) and the legacy emitter (AIL_IR=0) run the typed path.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SOURCE = '''def gen(n: int) -> list[str]:
    xs: list[str] = []
    for i in range(n):
        xs.append("s" + str(i))
    return xs


def both(a: list[str], b: list[str]) -> str:
    return "|".join(a) + "/" + "|".join(b)


def relay(xs: list[str]) -> list[str]:
    return xs


def build(lo: int, hi: int, step: int) -> list[str]:
    xs: list[str] = []
    for i in range(lo, hi, step):
        xs.append("v" + str(i))
    return xs


def partial(n: int) -> list[str]:
    xs: list[str] = []
    for i in range(n):
        if i % 3 == 0:
            xs.append("p" + str(i))
    return xs


def cleared(n: int) -> list[str]:
    xs: list[str] = ["old"]
    xs.clear()
    for i in range(n):
        xs.append("c" + str(i))
    return xs


def nested(n: int) -> list[str]:
    xs: list[str] = []
    for i in range(n):
        for j in range(i % 4):
            xs.append(str(i) + ":" + str(j))
    return xs


def comp(n: int) -> list[str]:
    xs: list[str] = ["d" + str(i) for i in range(n)]
    return xs


def stopped() -> list[str]:
    xs: list[str] = []
    for i in range(100000000000000000):
        xs.append("v")
        break
    return xs


def stopped_local(n: int) -> list[str]:
    xs: list[str] = []
    m = n
    for i in range(m):
        xs.append("w")
        break
    return xs


def early(n: int) -> list[str]:
    xs: list[str] = []
    for i in range(n):
        if i == 2:
            return xs
        xs.append(str(i))
    return xs


def odd(n: int) -> list[str]:
    xs: list[str] = []
    for i in range(n):
        if i % 2:
            xs.append(str(i))
    return xs


def stopped_int(n: int) -> list[int]:
    xs: list[int] = []
    m = n
    for i in range(m):
        xs.append(i)
        break
    return xs


def stopped_float() -> list[float]:
    xs: list[float] = []
    for i in range(100000000000000000):
        xs.append(1.5)
        break
    return xs


def main() -> int:
    for lo in range(-2, 3):
        for hi in range(-1, 4):
            for step in [1, 2, 3]:
                print(str(lo) + "," + str(hi) + "," + str(step) + ":" + "|".join(build(lo, hi, step)))
    for n in [0, 1, 2, 7, 8, 9, 20]:
        print("p" + str(n) + ":" + "|".join(partial(n)))
    for n in [0, 1, 8, 9, 100]:
        print("c" + str(n) + ":" + "|".join(cleared(n)))
        print("m" + str(n) + ":" + "|".join(comp(n)))
    for n in [0, 1, 5, 8]:
        print("n" + str(n) + ":" + "|".join(nested(n)))
    a = gen(6)
    b = a
    print(both(a, b))
    c = relay(a)
    print("|".join(c) + "|" + "|".join(gen(0)) + "|" + "|".join(gen(1)))
    print("|".join(stopped()))
    print("|".join(stopped_local(2305843009213693952)))
    for n in [0, 1, 2, 3, 9]:
        print("e" + str(n) + ":" + "|".join(early(n)))
        print("o" + str(n) + ":" + "|".join(odd(n)))
    si = stopped_int(2305843009213693952)
    print("i:" + "|".join(str(v) for v in si))
    sf = stopped_float()
    print("f:" + "|".join(str(v) for v in sf))
    return 0


main()
'''


class SlistReserveTests(unittest.TestCase):
    def test_reserve_and_last_use_release_match_cpython(self):
        expected = subprocess.run([sys.executable, '-c', SOURCE], capture_output=True, timeout=120)
        self.assertEqual(expected.returncode, 0, expected.stderr.decode(errors='replace'))
        for tag, ir in (('ir1', '1'), ('ir0', '0')):
            with self.subTest(ir=tag), tempfile.TemporaryDirectory() as directory:
                source, exe = Path(directory, 'lists.py'), Path(directory, 'lists')
                source.write_text(SOURCE, encoding='utf8')
                env = dict(os.environ, AIL_NO_GENERAL='1', AIL_NO_CACHE='1', AIL_IR=ir)
                env.pop('AIL_UNIFIED_FORCE', None)
                built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile',
                                        source.name, '--syntax', 'python', '-o', exe.name],
                                       cwd=directory, capture_output=True, timeout=600, env=env)
                self.assertEqual(built.returncode, 0, built.stdout.decode() + built.stderr.decode())
                ran = subprocess.run([str(exe)], capture_output=True, timeout=120)
                self.assertEqual((ran.returncode, ran.stdout), (0, expected.stdout),
                                 ran.stderr.decode(errors='replace'))


if __name__ == '__main__':
    unittest.main()
