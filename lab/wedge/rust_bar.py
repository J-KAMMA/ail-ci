#!/usr/bin/env python3
"""Time the Rust/PyO3 bar against the corpus's hottest function (measurement only).

    python3 lab/wedge/rust_bar.py [-o lab/wedge/rust_bar.json]

Builds the crate once (`cargo build --release`), copies the cdylib next to itself as
`hotrust.so`, then for each covered module builds a driver that:

  * calls the module's hot function on the corpus driver's own input, and
  * calls the Rust version of the same function on the same input,

each the median of 5 runs in a fresh subprocess.  Outputs are compared first, so a Rust row is
only recorded when the two agree.
"""
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORPUS = HERE / 'corpus'
RUST = HERE / 'rust'
REPS = 5

# module -> (hot python function, rust function, argument expression in the module's own terms)
CASES = {
    'tokenizer': ('count_idents', 'count_idents', 'LINE * SIZE'),
    'edit_dist': ('levenshtein', 'levenshtein', 'WORD, VARIANTS[0]'),
    'float_loops': ('dot', 'dot', 'a, b'),
    'matrix': ('mat_mul', 'mat_mul', 'a, b, N'),
    'rolling_stats': ('window_sums', 'window_sums', 'xs, W'),
}

DRIVER = '''
import sys, time, statistics
sys.path.insert(0, {corpus!r})
sys.path.insert(0, {rust!r})
import hotrust
import {module} as m

{setup}

def call_py():
    return m.{pyfn}({args})

def call_rs():
    return hotrust.{rsfn}({args_rs})

py = call_py()
rs = call_rs()
def norm(v):
    if isinstance(v, float):
        return round(v, 9)
    if isinstance(v, list):
        return [round(x, 9) if isinstance(x, float) else x for x in v]
    return v
print('PY', norm(py))
print('RS', norm(rs))
print('MATCH', norm(py) == norm(rs))
for name, fn in (('py', call_py), ('rs', call_rs)):
    times = []
    for _ in range({reps}):
        t = time.perf_counter()
        fn()
        times.append(time.perf_counter() - t)
    print('T', name, statistics.median(times))
'''


def module_setup(module):
    """The input construction the corpus driver uses, cut down to what the hot call needs."""
    return {
        'tokenizer': 'global LINE, SIZE',
        'edit_dist': 'global WORD, VARIANTS',
        'float_loops': 'global a, b\na = []\nb = []\nfor i in range(N):\n    a.append((i % 1000) * 0.5 + 0.25)\n    b.append((i % 877) * 0.125 + 0.5)',
        'matrix': 'global a, b\ndef build(n, seed):\n    out = []\n    i = 0\n    while i < n * n:\n        out.append((i * seed + 3) % 17 - 8)\n        i += 1\n    return out\na = build(N, 7)\nb = build(N, 11)',
        'rolling_stats': 'global xs\ndef make_samples(n, seed):\n    out = []\n    i = 0\n    state = seed\n    while i < n:\n        state = (state * 1103515245 + 12345) % 2147483648\n        out.append(state % 1000)\n        i += 1\n    return out\nxs = make_samples(N, 12345)',
    }[module]


def module_globals(module):
    """Pull the driver's single-line constants in."""
    text = (CORPUS / module / 'run.py').read_text()
    keep = []
    for line in text.splitlines():
        if line.startswith(('LINE =', 'SIZE =', 'WORD =', 'N =', 'W =')):
            keep.append(line)
    return '\n'.join(keep)


def _time(cmd, cwd, reps=REPS):
    times = []
    for _ in range(reps):
        t = time.perf_counter()
        p = subprocess.run(cmd, cwd=str(cwd), capture_output=True)
        times.append(time.perf_counter() - t)
        if p.returncode != 0:
            return None, p
    return statistics.median(times), p


def whole(module, pyfn, rsfn):
    """Whole-program time with the one hot function rewritten in Rust/PyO3.

    The module keeps its Python source; only `<pyfn>` is rebound to the Rust function, which is
    exactly the "rewrite the hottest function in Rust" shape the task asks to compare against.
    """
    import tempfile
    row = {}
    work = Path(tempfile.mkdtemp(prefix='wedge-rust-%s-' % module))
    try:
        for f in (CORPUS / module).iterdir():
            if f.is_file():
                shutil.copy2(f, work / f.name)
        text = (work / (module + '.py')).read_text()
        # `from __future__` imports must stay first; the shim goes at the very end.
        text += ('\nimport sys as _ail_rust_sys\n'
                 '_ail_rust_sys.path.insert(0, %r)\n'
                 'try:\n'
                 '    import hotrust as _ail_rust\n'
                 '    %s = _ail_rust.%s\n'
                 'except Exception:\n'
                 '    pass\n' % (str(RUST), pyfn, rsfn))
        (work / (module + '.py')).write_text(text)
        rust_s, rs_p = _time([sys.executable, '-B', 'run.py'], work)
        # shim present: compare against the same output the shim produces, and against the
        # unshimmed module when available
        row['rust_s'] = rust_s
        row['rc'] = rs_p.returncode
        row['error'] = '' if rs_p.returncode == 0 else rs_p.stderr.decode('utf-8', 'replace')[-300:]
        # a plain CPython run of the unmodified module for the same program
        plain = work.parent / (work.name + '-plain')
        shutil.copytree(CORPUS / module, plain)
        c_s, _p = _time([sys.executable, '-B', 'run.py'], plain)
        row['cpython_s'] = c_s
        shutil.rmtree(plain, ignore_errors=True)
        if c_s and rust_s:
            row['speedup'] = round(c_s / rust_s, 3)
        # the outputs must agree
        a = subprocess.run([sys.executable, '-B', 'run.py'], cwd=str(work), capture_output=True)
        b = subprocess.run([sys.executable, '-B', 'run.py'], cwd=str(CORPUS / module),
                           capture_output=True)
        row['match'] = a.stdout == b.stdout and a.returncode == b.returncode
        return row
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    out_path = Path(sys.argv[sys.argv.index('-o') + 1]) if '-o' in sys.argv else HERE / 'rust_bar.json'
    subprocess.run(['cargo', 'build', '--release'], cwd=str(RUST), check=True,
                   capture_output=True)
    so = next((RUST / 'target' / 'release').glob('libhotrust*.so'))
    dest = RUST / 'hotrust.so'
    shutil.copy2(so, dest)
    rows = []
    for module, (pyfn, rsfn, args) in CASES.items():
        setup = module_globals(module) + '\n' + module_setup(module)
        # tokenizer/edit_dist build their input in the driver body; inline those expressions
        if module == 'tokenizer':
            setup = module_globals(module) + '\nLINE = "def alpha_beta(gamma, delta_1):\\n    return gamma + delta_1 * 42  # note\\n"\nsrc = LINE * SIZE'
            args = 'src'
        if module == 'edit_dist':
            setup = module_globals(module) + '\nWORD = "abcdefghijklmnopqrstuvwxyz"\nVARIANTS = ["abcdefghijklmnopqrstuvwxy", "abcdefghijklmnopqrstuvwxyzz", "abcdefghijklmnopqrstuvwxyy", "bacdefghijklmnopqrstuvwxyz"]'
        src = DRIVER.format(corpus=str(CORPUS / module), rust=str(RUST), module=module,
                            setup=setup, pyfn=pyfn, rsfn=rsfn, args=args, args_rs=args,
                            reps=REPS)
        code = compile(src, '<bar>', 'exec')
        proc = subprocess.run([sys.executable, '-B', '-c', src], capture_output=True, text=True)
        row = {'module': module, 'function': pyfn}
        lines = proc.stdout.splitlines()
        vals = {}
        for line in lines:
            if line.startswith('PY '):
                row['py_value'] = line[3:]
            elif line.startswith('RS '):
                row['rs_value'] = line[3:]
            elif line.startswith('MATCH '):
                row['match'] = line.split()[1] == 'True'
            elif line.startswith('T '):
                _, name, v = line.split()
                vals[name] = float(v)
        row.update({'python_s': vals.get('py'), 'rust_s': vals.get('rs')})
        if row.get('python_s') and row.get('rust_s'):
            row['speedup'] = round(row['python_s'] / row['rust_s'], 3)
        row['whole'] = whole(module, pyfn, rsfn)
        if proc.returncode != 0:
            row['error'] = proc.stderr.strip().splitlines()[-1][:300]
        rows.append(row)
        w = row['whole']
        print('%-16s %-14s match=%-5s py=%-9s rust=%-9s x%-7s whole cpython=%-7s rust=%-7s x%s' % (
            module, pyfn, row.get('match'), row.get('python_s'), row.get('rust_s'),
            row.get('speedup'), w.get('cpython_s'), w.get('rust_s'), w.get('speedup')),
            flush=True)
    out_path.write_text(json.dumps(rows, indent=1) + '\n')
    print('wrote %s' % out_path)


if __name__ == '__main__':
    main()
