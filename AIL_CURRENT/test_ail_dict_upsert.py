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

SOURCE = r'''fn main() -> int {
    let words = read_bytes(sys.argv[1]).decode("utf-8").split("\n");
    let c1: dict[str, int] = {};
    let c2: dict[str, int] = {};
    let c3: dict[str, int] = {};
    let c4: dict[str, int] = {};
    let order: list[str] = [];
    let step = 3;
    let zero = 0;
    for w in words {
        if w in c1 { c1[w] = c1[w] + 1; } else { c1[w] = 1; order.append(w); }
        if w not in c2 { c2[w] = step; } else { c2[w] += step * 2 + len(w); }
        if w in c3 { c3[w] = 7 + c3[w]; } else { c3[w] = zero; }
        let k = w + "!";
        if k in c4 { c4[k] += c1[w]; } else { c4[k] = -1; }
    }
    for w in order { print(w, c1[w], c2[w], c3[w], c4[w + "!"]); }
    print(len(c1), len(c2), len(c3), len(c4));
    return 0;
}
'''

ITERATE = r'''fn one(x: int) -> int { return x; }
fn main() -> int {
    let d: dict[str, int] = {};
    d["a"] = 1;
    d["b"] = 2;
    let z = 0;
    for k in ["a", "q"] {
        try {
            if k in d { d[k] = d[k] + 10 // z; } else { d[k] = VALUE; }
        } except ZeroDivisionError { print("zde", k); }
    }
    for k, v in d.items() { print(k, v); }
    for k in d {
        if "new" in d { d["new"] = d["new"] + 1; } else { d["new"] = VALUE; }
        print("after", k);
    }
    return 0;
}
'''


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
        c = pyfunc.to_c(translate(SOURCE), name='run', strict=True)
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
        self.assertIn('ail_sdict_upsert(&', pyfunc.to_c(translate(fused), name='run', strict=True))
        self.assertNotIn('ail_sdict_upsert(&', pyfunc.to_c(translate(unfused), name='run', strict=True))
        runs = []
        for name, source in (('fused', fused), ('unfused', unfused)):
            result = subprocess.run([str(build(self, name, source))], capture_output=True, timeout=60)
            runs.append((result.returncode, result.stdout))
        self.assertEqual(runs[0], runs[1])
        self.assertTrue(runs[0][1].startswith(b'zde a\na 1\nb 2\nq 5\n'), runs[0])
        self.assertNotEqual(runs[0][0], 0)


if __name__ == '__main__':
    unittest.main()
