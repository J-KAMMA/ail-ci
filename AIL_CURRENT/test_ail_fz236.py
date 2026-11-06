"""Differential fuzz seed fz236: a try's `else` body must not reach that try's own handlers.

The daily fuzzer (seed 2076311363, CPython 3.12, modes default+ir) reported

    exit code cpython=1 ail=3; line 15: cpython='235' ail='100.7525 False'

with AIL stderr `AIL limit: int_overflow`.  The program's last statement is a
`try/except IndexError/else/finally`: the `else` body ends with
`elif round(v1 * v1) > al8[3]`, which raises IndexError.  CPython lets it escape (the `else` is
not covered by the statement's own handlers): `finally` prints 235 and the traceback ends the
program with exit 1.  The reported AIL build caught that IndexError in the statement's own
`except IndexError`, printed 100.7525 and ran on into the int64 sum that stops with exit 3.

On this tree the seed already matches CPython in both fuzz modes, and so do the minimized
shapes below: the `else` is compiled against the enclosing handlers (the fz1 fix) and the
`al8 = v7` alias that makes the typed path differ is a named refusal, so the default build
takes the general path.  These cases pin that, plus the alias routes the fuzzer program uses
(a second name, a list item, an argument, an attribute and a dict value).
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SEED_CASE = r'''def h0(n: int, a: int) -> int:
    if n <= 0:
        return (a * 7 + 3) % 8003
    return (h0(n - 1, (a * 5 + n) % 8003) + 4) % 8003


def main() -> int:
    v1: float = (((67 - 21) / 4) / (abs(1e10) + 1.0))
    for i2 in range(1, 5):
        if ('q q'[1:2].startswith('a')):
            break
        v1 -= (1.25 + 7.0)
    v3: bool = '12'.isdigit()
    print(float(max(42, 30)))
    w4: int = 0
    while w4 < 5:
        w4 += 1
        for i5 in range(3):
            v3 = (((98 - w4) == (w4 + w4)) and ((15 & i5) <= (34 * 54)))
    v6: list[int] = []
    try:
        v6 = [22, 'q q'.find(' pad '), 9223372036854775807, h0(10, (21 + 3037000499))]
    except (IndexError, KeyError, ValueError, ZeroDivisionError):
        print(-2)
    v7: list[int] = [0] * 0
    al8: list[int] = v7
    v7.sort()
    print(len(v7), len(al8), sum(v7) - sum(al8))
    print(51)
    v7.append((59 + 5))
    v9: dict[str, int] = {}
    v9['dd'] = 90
    v9['c'] = -8
    v9['c'] = 92
    v9['a'] = 62
    try:
        print(('日本'.startswith('a')))
        try:
            if (not (68 != len(v9))):
                raise ZeroDivisionError('m3')
        except ZeroDivisionError:
            print(-72)
        else:
            print(33)
        finally:
            print(192)
    except ZeroDivisionError:
        for i10 in range(4):
            print(47)
        try:
            try:
                if (str((v1 - v1)) == ('x' + '12')):
                    assert ('café' == '3.5'[-2:]), "boom"
            except (AssertionError, IndexError):
                print(-59)
            else:
                print(1)
            print((0.5 + 1.25), '日本'.replace('l', ''), (v1 / (abs(v1) + 1.0)))
        except IndexError:
            print((abs(float((-1 - 28))) ** 0.5))
            if ('12' in v9):
                v11: list[int] = [(6 * 3), 14]
        else:
            al12: list[int] = al8
            al8.append(8)
            print(len(al8), len(al12), sum(al8) - sum(al12))
            print((7 - 32))
        finally:
            print(295)
    except KeyError:
        try:
            if (str(92).startswith('a')):
                raise KeyError
        except KeyError:
            print(-18)
    else:
        print('café')
    print((((87 - 4611686018427387904) / 8) < (v1 * v1)), (3037000499 == (40 * 66)))
    print((not ((52 + 80) >= (-9223372036854775807 + 42))))
    try:
        al13: list[int] = v7
        al13 += [3]
        print(len(v7), len(al13), sum(v7) - sum(al13))
        try:
            del v9['c']
        except KeyError:
            print(-73)
    except IndexError:
        print((100.75 + 2.5e-3), ((abs(82) == (69 * 92)) and ((len(v6) / 4) <= ((95 * 89) / 4))))
    else:
        try:
            if ((((89 ** 2) > v6[0]) or (("%d" % (72 % -1)) < ' pad ')) and (34 < (89 * 38))):
                print(str(round(v1)).replace('a', ''))
                try:
                    v9.pop('c')
                except KeyError:
                    print(-55)
                try:
                    print(((57 + 42) // 3))
                except ZeroDivisionError:
                    print(-85)
        except ZeroDivisionError:
            print(-66)
        finally:
            print(175)
        if (39 == (0 & -6)):
            w14: int = 0
            while w14 < 6:
                w14 += 1
                v15: float = 0.0
                try:
                    v15 = float((w14 - w14))
                except ZeroDivisionError:
                    print(-9)
                v6.extend([(w14 // (abs(85) + 1)), (w14 * 18), (w14 - w14)])
                v15 += (0.3 - v1)
            v9['abc'] = (~-4)
            v16: dict[str, int] = {}
            v16['dd'] = 52
        elif ((round((v1 * v1)) > al8[3]) or ('hello'.startswith(' '))):
            v3 = ('q q' in '3.5'[1:-1])
            print(al8.count((10 + 77)))
    finally:
        print(235)
    try:
        print((v1 * (v1 / 86)))
    except ZeroDivisionError:
        print(-90)
    print(v1)
    print(v3)
    print(len(v6), sum(v6))
    print(len(v7), sum(v7))
    print(len(al8), sum(al8))
    ks18: list[str] = []
    for k17 in sorted(v9):
        ks18.append(k17)
    print(len(v9), sum(v9.values()), ','.join(ks18))
    return 0


main()
'''

ELSE_CASE = r'''def boom() -> None:
    raise KeyError('k')


def main() -> None:
    x: list[int] = []
    try:
        print('body')
    except (IndexError, KeyError):
        print('caught')
    else:
        print('else')
        print(x[3])
    finally:
        print('finally')
    print('after')
    try:
        print('body2')
    except KeyError:
        print('caught2')
    else:
        print('else2')
        boom()
    finally:
        print('finally2')
    print('after2')


main()
'''

NESTED_ELSE_CASE = r'''def main() -> int:
    x: list[int] = [0]
    try:
        print('outer body')
    except ZeroDivisionError:
        print('outer zd')
    else:
        print('outer else')
        try:
            print('inner body')
        except ZeroDivisionError:
            print('inner zd')
        else:
            print('inner else')
            if False:
                pass
            elif x[3] > 0:
                print('x')
        finally:
            print('inner finally')
    finally:
        print('outer finally')
    print('after')
    return 0


main()
'''

ALIAS_CASE = r'''def read(xs: list[int]) -> int:
    return xs[0]


def main() -> None:
    a: list[int] = [1]
    b: list[int] = a
    a.append(2)
    print(len(a), len(b), sum(a) - sum(b))
    g: list[list[int]] = []
    g.append(a)
    a.append(3)
    print(len(a), len(g[0]), sum(a) - sum(g[0]))
    print(read(a), len(a))
    d: dict[str, int] = {'k': len(a)}
    print(d['k'], len(a))


main()
'''

CASES = [('seed', SEED_CASE), ('else', ELSE_CASE), ('nested_else', NESTED_ELSE_CASE),
         ('alias', ALIAS_CASE)]


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONHASHSEED='0'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build_and_run(directory, name, text, mode):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + '_' + mode)
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_UNIFIED_FORCE', None)
    env.pop('AIL_IR', None)
    if mode == 'g':
        env['AIL_UNIFIED_FORCE'] = '1'
    elif mode == 'ir0':
        env['AIL_IR'] = '0'
    else:
        env['AIL_IR'] = '1'
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Fz236Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-fz236-') as directory:
            want, rc, err = _cpython(directory, slug, text)
            for mode in ('g', 'ir1', 'ir0'):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, mode), text, mode)
                self.assertIsNotNone(got, '%s (mode=%s)\n%s' % (slug, mode, build_err))
                self.assertEqual(got, (want, rc), '%s (mode=%s)\n%s' % (slug, mode, build_err))

    def test_seed(self):
        self.check('seed', SEED_CASE)

    def test_else(self):
        self.check('else', ELSE_CASE)

    def test_nested_else(self):
        self.check('nested_else', NESTED_ELSE_CASE)

    def test_alias(self):
        self.check('alias', ALIAS_CASE)


if __name__ == '__main__':
    unittest.main()
