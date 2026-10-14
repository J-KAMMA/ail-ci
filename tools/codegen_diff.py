"""Show how generated C changed between a git revision and the working tree, for given AIL sources.

    python3 tools/codegen_diff.py [--base HEAD] [--pins]            # the codegen-pin test sources
    python3 tools/codegen_diff.py --source 'fn main()->int {...}'

Prints old/new SHA-256 of `pyfunc.to_c(translate(src), name='run', strict=True)` (what the
codegen-pin tests hash) and the unified diff, so a pin update can be checked to contain only the
intended change before the new hashes are written into the tests.
"""
import argparse, difflib, hashlib, json, subprocess, sys, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PIN_SOURCES = [
    'fn main()->int {let x=7;print(x);x+=2;print(x);return 0;}',
    'fn main()->int {let x=1.5;print(x);return 0;}',
    'fn main()->int {let xs:list[int]=[1,2];xs.reverse();print(xs[0]);return 0;}',
    'fn main()->int {let xs:list[float]=[1.5,2.5];xs.reverse();print(xs[0]);return 0;}',
    'struct Box {ints:list[int];floats:list[float];} fn main()->int {let b=Box([1],[1.5]);b.ints=[2];b.floats=[2.5];print(b.ints[0]);return 0;}',
]
GENERATE = '''
import sys, json
sys.path[:0] = [sys.argv[1] + "/python/pkg-v12", sys.argv[1]]
import pyfunc
from ail_syntax import translate
print(json.dumps([pyfunc.to_c(translate(s), name="run", strict=True) for s in json.loads(sys.argv[2])]))
'''


def generate(ail_root, sources):
    result = subprocess.run([sys.executable, '-B', '-c', GENERATE, str(ail_root), json.dumps(sources)],
                            capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--base', default='HEAD')
    parser.add_argument('--source', action='append', help='AIL source text; default: the codegen-pin sources')
    args = parser.parse_args()
    sources = args.source or PIN_SOURCES
    with tempfile.TemporaryDirectory(prefix='ail-codegen-') as tmp:
        tree = Path(tmp) / 'base'
        subprocess.run(['git', 'worktree', 'add', '--detach', str(tree), args.base], cwd=REPO, check=True, capture_output=True)
        try:
            old = generate(tree / 'AIL_CURRENT', sources)
        finally:
            subprocess.run(['git', 'worktree', 'remove', '--force', str(tree)], cwd=REPO, capture_output=True)
    new = generate(REPO / 'AIL_CURRENT', sources)
    for source, a, b in zip(sources, old, new):
        print('== %s\n   old %s\n   new %s' % (source[:70], hashlib.sha256(a.encode()).hexdigest(), hashlib.sha256(b.encode()).hexdigest()))
        for line in difflib.unified_diff(a.splitlines(), b.splitlines(), lineterm='', n=0):
            if not line.startswith(('---', '+++')):
                print('   ' + line[:160])


if __name__ == '__main__':
    main()
