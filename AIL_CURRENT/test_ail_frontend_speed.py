"""The compiler front end stays fast on a realistic program.

Regression: `check` took ~17 s on a 100-line n-body program. The expression-kind questions
(`_etype`, `_is_str_expr`, `_field_kind`, ...) were recomputed from scratch at every level of every
arithmetic expression and attribute chain (a BinOp asked about each operand twice, each of which
asked twice again), and the whole-program passes repeated them for every node of every function. The
answers are now memoised per (node, ctx) and dropped whenever the ctx or a shared table changes.

The bound is on CPU time of the child process, so a loaded machine cannot fail it; the old front end
used 14-17 s of CPU here, the current one about 1.5 s. A second test pins that turning the cache off
(AIL_QUERY_CACHE=0) generates byte-identical C.
"""
import ast
import json
import os
import resource
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

NBODY = """\
struct Body { x: float; y: float; z: float; vx: float; vy: float; vz: float; m: float; }

fn energy(b: list[Body]) -> float {
    let e = 0.0;
    for i in range(0, 5) {
        let bi = b[i];
        e = e + 0.5 * bi.m * (bi.vx * bi.vx + bi.vy * bi.vy + bi.vz * bi.vz);
        for j in range(i + 1, 5) {
            let bj = b[j];
            let dx = bi.x - bj.x;
            let dy = bi.y - bj.y;
            let dz = bi.z - bj.z;
            let d = (dx * dx + dy * dy + dz * dz) ** 0.5;
            e = e - (bi.m * bj.m) / d;
        }
    }
    return e;
}

fn advance(b: list[Body], dt: float) -> void {
    for i in range(0, 5) {
        let bi = b[i];
        for j in range(i + 1, 5) {
            let bj = b[j];
            let dx = bi.x - bj.x;
            let dy = bi.y - bj.y;
            let dz = bi.z - bj.z;
            let d = (dx * dx + dy * dy + dz * dz) ** 0.5;
            let mag = dt / ((d * d) * d);
            bi.vx = bi.vx - (dx * bj.m) * mag;
            bi.vy = bi.vy - (dy * bj.m) * mag;
            bi.vz = bi.vz - (dz * bj.m) * mag;
            bj.vx = bj.vx + (dx * bi.m) * mag;
            bj.vy = bj.vy + (dy * bi.m) * mag;
            bj.vz = bj.vz + (dz * bi.m) * mag;
        }
    }
    for i in range(0, 5) {
        let bi = b[i];
        bi.x = bi.x + dt * bi.vx;
        bi.y = bi.y + dt * bi.vy;
        bi.z = bi.z + dt * bi.vz;
    }
}

fn main() {
    let n = int(sys.argv[1]);
    let sm = 39.47841760435743;
    let dy = 365.24;
    let b: list[Body] = [];
    b.append(Body(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, sm));
    b.append(Body(4.84143144246472090e+00, -1.16032004402742839e+00, -1.03622044471123109e-01,
        1.66007664274403694e-03 * dy, 7.69901118419740425e-03 * dy, -6.90460016972063023e-05 * dy,
        9.54791938424326609e-04 * sm));
    b.append(Body(8.34336671824457987e+00, 4.12479856412430479e+00, -4.03523417114321381e-01,
        -2.76742510726862411e-03 * dy, 4.99852801234917238e-03 * dy, 2.30417297573763929e-05 * dy,
        2.85885980666130812e-04 * sm));
    let px = 0.0;
    let py = 0.0;
    let pz = 0.0;
    for i in range(0, 3) {
        px = px + b[i].vx * b[i].m;
        py = py + b[i].vy * b[i].m;
        pz = pz + b[i].vz * b[i].m;
    }
    b[0].vx = -px / sm;
    b[0].vy = -py / sm;
    b[0].vz = -pz / sm;
    print("%.9f" % (energy(b),));
    for s in range(0, n) { advance(b, 0.01); }
    print("%.9f" % (energy(b),));
}
"""

SMALL = """\
struct P { x: float; y: float; name: str; }

fn norm(p: P) -> float { return (p.x * p.x + p.y * p.y) ** 0.5; }

fn main() {
    let ps: list[P] = [P(3.0, 4.0, "a"), P(6.0, 8.0, "b")];
    let t = 0.0;
    for p in ps { t = t + norm(p) + len(p.name + "x"); }
    print("%.3f" % (t,));
}
"""

PYTHON_OBJ = """\
def heads(words: list) -> list:
    out: list = []
    for w in words:
        out.append(w[:1])
    return out


def total(rows: list) -> int:
    t: int = 0
    for row in rows:
        for cell in row:
            t = t + cell
    return t


DATA: list = [1, 2, 3]


def main() -> None:
    print(total([[1, 2], [3]]), heads(["ab", "cd"]))
"""

PYTHON_SCRIPT = """\
def fib(n: int) -> int:
    a: int = 0
    b: int = 1
    for _ in range(n):
        a, b = b, a + b
    return a


def main() -> None:
    print(fib(10))
"""

PYC_TO_C = """
import sys
sys.path[:0] = [sys.argv[1] + "/python/pkg-v12", sys.argv[1]]
import pyc
sys.stdout.write(pyc.to_c(sys.stdin.read(), strict=True))
"""

TO_C = """
import sys
sys.path[:0] = [sys.argv[1] + "/python/pkg-v12", sys.argv[1]]
import pyfunc
from ail_syntax import translate
sys.stdout.write(pyfunc.to_c(translate(sys.stdin.read()), name="run", strict=True))
"""


def cpu_seconds(command, **kwargs):
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    result = subprocess.run(command, capture_output=True, text=True, **kwargs)
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    return result, (after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime)


class FrontendSpeed(unittest.TestCase):
    def test_check_of_arithmetic_heavy_program_is_fast(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'nbody.ail'
            source.write_text(NBODY, encoding='utf8')
            # one warm-up so a cold bytecode cache of the compiler itself is not charged to the bound
            cpu_seconds([sys.executable, str(ROOT / 'ail_chatgpt.py'), 'check', str(source)])
            result, cpu = cpu_seconds([sys.executable, str(ROOT / 'ail_chatgpt.py'), 'check', str(source)])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'passed')
        self.assertLess(cpu, 8.0, 'check used %.1f s of CPU; the front end has a super-linear blowup again' % cpu)

    def test_query_cache_does_not_change_generated_c(self):
        outputs = []
        for mode in ('1', '0'):
            result = subprocess.run([sys.executable, '-c', TO_C, str(ROOT)], input=SMALL, capture_output=True,
                                    text=True, env=dict(os.environ, AIL_QUERY_CACHE=mode))
            self.assertEqual(result.returncode, 0, result.stderr)
            outputs.append(result.stdout)
        self.assertIn('norm', outputs[0])
        self.assertEqual(outputs[0], outputs[1])


class FastWalk(unittest.TestCase):
    """`fastwalk.walk` replaces the front end's `ast.walk`. It must yield exactly what the standard
    library yields -- every node, once, in the same breadth-first order -- and installing it must
    not change a byte of the generated C."""

    @staticmethod
    def reference(node):
        """The standard library's own walk (ast.py: a deque fed with iter_child_nodes)."""
        from collections import deque
        todo = deque([node])
        while todo:
            current = todo.popleft()
            yield current
            todo.extend(ast.iter_child_nodes(current))

    def sources(self):
        return (PYTHON_SCRIPT, PYTHON_OBJ)

    def ail_source(self, source):
        """The AIL-syntax programs, translated to the block syntax the compiler parses as Python."""
        sys.path[:0] = [str(ROOT / 'python/pkg-v12'), str(ROOT)]
        try:
            from ail_syntax import translate
            return translate(source)
        finally:
            del sys.path[:2]

    def test_yields_the_standard_librarys_nodes(self):
        sys.path.insert(0, str(ROOT / 'python/pkg-v12'))
        try:
            import fastwalk
        finally:
            sys.path.pop(0)
        for source in self.sources() + (self.ail_source(NBODY), self.ail_source(SMALL)):
            tree = ast.parse(source)
            self.assertEqual([id(n) for n in fastwalk.walk(tree)], [id(n) for n in self.reference(tree)])
            # ... including a subtree and a leaf, and a node the walk reaches twice nowhere
            for root in (tree.body[0], tree.body[-1], tree):
                self.assertEqual([id(n) for n in fastwalk.walk(root)], [id(n) for n in self.reference(root)])

    def test_install_is_the_walk_the_compiler_uses(self):
        probe = ('import sys; sys.path[:0] = [sys.argv[1] + "/python/pkg-v12"]; import ast, fastwalk, pyc; '
                 'print(ast.walk is fastwalk.walk)')
        result = subprocess.run([sys.executable, '-c', probe, str(ROOT)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'True')

    def test_generated_c_is_identical_to_the_standard_walk(self):
        outputs = []
        for mode in ('1', '0'):
            result = subprocess.run([sys.executable, '-c', PYC_TO_C, str(ROOT)], input=PYTHON_SCRIPT,
                                    capture_output=True, text=True, env=dict(os.environ, AIL_FASTWALK=mode))
            self.assertEqual(result.returncode, 0, result.stderr)
            outputs.append(result.stdout)
        self.assertIn('int64_t fib', outputs[0])
        self.assertEqual(outputs[0], outputs[1])


class IdentifierReplace(unittest.TestCase):
    """`_c_identifier_replace` finds the token with str.find instead of tokenizing the whole text; it
    must give what the tokenizer gives (strings, comments, longer words and digit prefixes)."""

    def test_matches_the_tokenizer(self):
        import random
        sys.path.insert(0, str(ROOT / 'python/pkg-v12'))
        try:
            import pyfunc
        finally:
            sys.path.pop(0)
        token = '__AIL_NB_rf_ab__'

        def reference(text):
            return pyfunc._C_TOKENS.sub(lambda m: 'VALUE' if m.group() == token else m.group(), text)

        pieces = [token, token, 'x', 'a1', '1', '12', '_', ' ', '\n', '"', "'", '\\', '//', '/*', '*/', '(', ';', 'v_',
                  '"s ' + token + ' t"', '/* ' + token + ' */', '// ' + token + '\n', "'c'", token + '_', '_' + token,
                  'a' + token, '1' + token, '9' + token + '9', 'é']
        rng = random.Random(7)
        for _ in range(20000):
            text = ''.join(rng.choice(pieces) for _ in range(rng.randint(1, 14)))
            self.assertEqual(pyfunc._c_identifier_replace(text, token, 'VALUE'), reference(text), text)


if __name__ == '__main__':
    unittest.main()
