"""`if k in d { d[k] = d[k] + e; } else { d[k] = v; ... }` on dict[str, int] compiles to one probe
(pyfunc `_map_upsert`, cruntime `ail_sdict_upsert`) and behaves exactly as the unfused source.

Random word streams are counted with every fused shape and compared with Python; the fused C is
checked to be used (and not used where the shape must stay unfused); an exception on the hit
branch and an insertion during iteration behave as the unfused program does.
"""
import random
import subprocess
import sys
import unittest
import test_ail_c_objects as support
from test_ail_map_fields import build

sys.path[:0] = [str(support.ROOT / 'python' / 'pkg-v12'), str(support.ROOT)]
import pyfunc  # noqa: E402
from ail_syntax import translate  # noqa: E402

SOURCE = 'import sys\n\ndef main() -> int:\n    words = read_bytes(sys.argv[1]).decode(\'utf-8\').split(\'\\n\')\n    c1: dict[str, int] = {}\n    c2: dict[str, int] = {}\n    c3: dict[str, int] = {}\n    c4: dict[str, int] = {}\n    order: list[str] = []\n    step = 3\n    zero = 0\n    for w in words:\n        if w in c1:\n            c1[w] = c1[w] + 1\n        else:\n            c1[w] = 1\n            order.append(w)\n        if w not in c2:\n            c2[w] = step\n        else:\n            c2[w] += step * 2 + len(w)\n        if w in c3:\n            c3[w] = 7 + c3[w]\n        else:\n            c3[w] = zero\n        k = w + \'!\'\n        if k in c4:\n            c4[k] += c1[w]\n        else:\n            c4[k] = -1\n    for w in order:\n        print(w, c1[w], c2[w], c3[w], c4[w + \'!\'])\n    print(len(c1), len(c2), len(c3), len(c4))\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n'

ITERATE = 'import sys\n\ndef one(x: int) -> int:\n    return x\n\ndef main() -> int:\n    d: dict[str, int] = {}\n    d[\'a\'] = 1\n    d[\'b\'] = 2\n    z = 0\n    for k in [\'a\', \'q\']:\n        try:\n            if k in d:\n                d[k] = d[k] + 10 // z\n            else:\n                d[k] = VALUE\n        except ZeroDivisionError:\n            print(\'zde\', k)\n    for k, v in d.items():\n        print(k, v)\n    for k in d:\n        if \'new\' in d:\n            d[\'new\'] = d[\'new\'] + 1\n        else:\n            d[\'new\'] = VALUE\n        print(\'after\', k)\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n'


def expected(words):
    c1, c2, c3, c4, order = {}, {}, {}, {}, []
    for w in words:
        if w in c1:
            c1[w] += 1
        else:
            c1[w] = 1
            order.append(w)
        if w not in c2:
            c2[w] = 3
        else:
            c2[w] += 3 * 2 + len(w)
        c3[w] = 7 + c3[w] if w in c3 else 0
        k = w + '!'
        if k in c4:
            c4[k] += c1[w]
        else:
            c4[k] = -1
    lines = ['%s %d %d %d %d' % (w, c1[w], c2[w], c3[w], c4[w + '!']) for w in order]
    lines.append('%d %d %d %d' % (len(c1), len(c2), len(c3), len(c4)))
    return '\n'.join(lines) + '\n'


class DictUpsertTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    write = support.CObjectTests.write
    command = support.CObjectTests.command

    def test_counts_match_python(self):
        c = pyfunc.to_c(SOURCE, name='run', strict=True)
        self.assertEqual(c.count('ail_sdict_upsert(&'), 4)
        program = build(self, 'upsert', SOURCE)
        rng = random.Random(20261012)
        vocab = ['', 'a', 'b', 'é', '日本', 'word', 'x' * 40] + ['w%d' % i for i in range(3000)]
        for size in (0, 1, 50, 20000):
            words = [rng.choice(vocab) for _ in range(size)]
            path = self.root / 'words.txt'
            path.write_bytes('\n'.join(words).encode('utf-8'))
            result = subprocess.run([str(program), str(path)], capture_output=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
            # "".split("\n") is [""], exactly as in Python.
            self.assertEqual(result.stdout.decode('utf-8'), expected('\n'.join(words).split('\n')))

    def test_raise_and_iteration_match_unfused(self):
        fused, unfused = ITERATE.replace('VALUE', '5'), ITERATE.replace('VALUE', 'one(5)')
        self.assertIn('ail_sdict_upsert(&', pyfunc.to_c(fused, name='run', strict=True))
        self.assertNotIn('ail_sdict_upsert(&', pyfunc.to_c(unfused, name='run', strict=True))
        runs = []
        for name, source in (('fused', fused), ('unfused', unfused)):
            result = subprocess.run([str(build(self, name, source))], capture_output=True, timeout=60)
            runs.append((result.returncode, result.stdout))
        self.assertEqual(runs[0], runs[1])
        self.assertTrue(runs[0][1].startswith(b'zde a\na 1\nb 2\nq 5\n'), runs[0])
        self.assertNotEqual(runs[0][0], 0)


if __name__ == '__main__':
    unittest.main()
