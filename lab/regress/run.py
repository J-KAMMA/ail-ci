#!/usr/bin/env python3
"""Regression check for the AIL compiler against CPython 3.12 (zero silent differences).

Catches the bug class where a change to the fast typed path turns a program that matched CPython into a refusal, a
stop ("integer overflow") or a different answer, typically for ints beyond int64 that arrive from int(text), record
fields or arithmetic.

    python3 lab/regress/run.py --base REF --head REF [--jobs 2] [--limit 60] [--filter SUBSTR] [--shard I/N]

Builds nothing itself: a compiler "build" is `ail_chatgpt.py compile` of one program, so the two compilers are the
trees `git archive`d from BASE and HEAD. For every program and input it runs CPython, the base default build, the head
default build and the head build with AIL_UNIFIED_FORCE=1, and compares stdout and exit code.

Program set (deduped by text): generated big-value programs (gen_programs.py), programs embedded in the typed-path tests
of both trees (test_ail_typedreach*, tintlist, reclist, cmp_classname, errtext2, tint), and lab/census/programs/dev with
the lab/corpus input generators plus big-value variants of their inputs.

Fails (exit 1) on
  REGRESSION     base matched CPython, head default build is refused, stops or differs
  SILENT         head default build exits 0 and its stdout (or exit status) differs from CPython
  SILENT-FORCE   the same for the head build with AIL_UNIFIED_FORCE=1
A program listed in lab/regress/known.txt is reported but does not fail the check (differences that were already on
integ; fix them and delete the line). A loud refusal or stop of only the forced build is information, not a failure.
Information only: programs that moved between the general and the typed path (the compile note).

Local mode (WSL): the same command inside a checkout; subprocesses get `ulimit -v` (--mem-kb, default 1500000 outside
GitHub Actions) and a default subset of 60 programs (--limit, 0 = all).
"""
import argparse
import ast
import concurrent.futures
import hashlib
import importlib.util
import json
import os
import random
import re
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gen_programs  # noqa: E402

IN_CI = bool(os.environ.get('GITHUB_ACTIONS'))
GENERAL_NOTE = 'built on the general path'
TEST_GLOBS = ['test_ail_typedreach*.py', 'test_ail_tintlist.py', 'test_ail_tint.py', 'test_ail_reclist.py',
              'test_ail_cmp_classname.py', 'test_ail_errtext2.py']
READS_STDIN = re.compile(r'\binput\s*\(|\bstdin\b')
INPUT_NAME = re.compile(r'INPUT|STDIN|VALUES|LINES')
BIG = ['9223372036854775807', '-9223372036854775808', '9223372036854775808', '-9223372036854775809',
       '99999999999999999999', '4611686018427387904', '123456789012345678901234567890', '4294967296']
GENERIC_INPUTS = ['', '3\n1 2 3\n', '4\n9223372036854775807 9223372036854775808 -9223372036854775809 5\n',
                  '5\n99999999999999999999 4611686018427387904 4611686018427387905 -3 7\n',
                  '3 4611686018427387904 4611686018427387905 7\n',
                  'alpha beta gamma delta\nbeta gamma\n']
NUMERIC_GENS = {'nums', 'nums_nocount', 'pos_nums', 'int_matrix', 'two_ints'}
MAX_OUT = 4000


# --------------------------------------------------------------------------------------------- processes

def _limits(mem_kb):
    def apply():
        os.setsid()
        if mem_kb:
            resource.setrlimit(resource.RLIMIT_AS, (mem_kb * 1024, mem_kb * 1024))
    return apply


def run(cmd, stdin=b'', env=None, cwd=None, timeout=60, mem_kb=0):
    """-> (returncode or None on timeout, stdout bytes, stderr text)"""
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, cwd=cwd,
                         preexec_fn=_limits(mem_kb))
    try:
        out, err = p.communicate(stdin, timeout=timeout)
        return p.returncode, out, err.decode('utf-8', 'replace')
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except OSError:
            p.kill()
        out, err = p.communicate()
        return None, out, err.decode('utf-8', 'replace')


# ------------------------------------------------------------------------------------------------ trees

def git(repo, *args):
    r = subprocess.run(['git', '-c', 'safe.directory=*', '-C', str(repo), *args], capture_output=True)
    if r.returncode:
        raise SystemExit('git %s failed: %s' % (' '.join(args), r.stderr.decode('utf-8', 'replace')[-400:]))
    return r.stdout


def extract_tree(repo, ref, dest):
    dest.mkdir(parents=True, exist_ok=True)
    tar = git(repo, 'archive', ref, 'AIL_CURRENT', 'tools')
    subprocess.run(['tar', '-x', '-C', str(dest)], input=tar, check=True)
    subprocess.run([sys.executable, '-m', 'compileall', '-q', '-j', '0', 'AIL_CURRENT', 'tools'], cwd=dest,
                   capture_output=True)
    return dest


# ------------------------------------------------------------------------------------------- program set

class Prog:
    def __init__(self, key, text, inputs, origin):
        self.key, self.text, self.inputs, self.origin = key, text, inputs, origin


def looks_like_program(text):
    if len(text) < 40 or '\n' not in text or 'print(' not in text or 'unittest' in text:
        return False
    try:
        ast.parse(text)
    except (SyntaxError, ValueError, RecursionError):
        return False
    return True


def module_input_lists(mod):
    found = []
    for node in mod.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and INPUT_NAME.search(node.targets[0].id) and isinstance(node.value, (ast.List, ast.Tuple)):
            try:
                v = ast.literal_eval(node.value)
            except (ValueError, SyntaxError):
                continue
            if v and all(isinstance(s, str) for s in v):
                found.extend(v)
    seen, out = set(), []
    for s in found:
        if s not in seen:
            seen.add(s)
            out.append(s)
    big = [s for s in out if re.search(r'\d{19}', s)]
    rest = [s for s in out if s not in big]
    return (rest[:5] + big[:5])[:10]


def programs_from_tests(tree, label):
    progs = []
    for pattern in TEST_GLOBS:
        for path in sorted((tree / 'AIL_CURRENT').glob(pattern)):
            try:
                mod = ast.parse(path.read_text(encoding='utf-8'))
            except (SyntaxError, UnicodeDecodeError):
                continue
            names = {}
            for node in ast.walk(mod):
                if isinstance(node, ast.Dict):
                    for k, v in zip(node.keys, node.values):
                        if isinstance(k, ast.Constant) and isinstance(k.value, str) \
                                and isinstance(v, ast.Constant) and isinstance(v.value, str):
                            names.setdefault(v.value, k.value)
                elif isinstance(node, ast.Assign) and len(node.targets) == 1 \
                        and isinstance(node.targets[0], ast.Name) \
                        and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    names.setdefault(node.value.value, node.targets[0].id.lower())
            pool = module_input_lists(mod)
            for node in ast.walk(mod):
                if isinstance(node, ast.Constant) and isinstance(node.value, str) and looks_like_program(node.value):
                    name = names.get(node.value) or 'L%d' % node.lineno
                    inputs = (pool + GENERIC_INPUTS[:3])[:12] if READS_STDIN.search(node.value) else ['']
                    progs.append(Prog('test/%s/%s' % (path.stem.replace('test_ail_', ''), name), node.value,
                                      inputs, label))
    return progs


def programs_generated():
    progs = []
    for key, fmt, src in gen_programs.PROGRAMS:
        if fmt == 'none':
            inputs = ['']
        else:
            inputs = []
            for toks in gen_programs.INPUT_SETS.values():
                text = gen_programs.render(fmt, toks)
                if text not in inputs:
                    inputs.append(text)
        progs.append(Prog('gen/' + key, src, inputs, 'gen'))
    return progs


def corpus_modules(root):
    """lab/corpus tasks + input generators (tNNN -> generator name)"""
    corpus = root / 'lab' / 'corpus'
    if not (corpus / 'tasks.py').exists():
        return None, None
    sys.path.insert(0, str(corpus))
    try:
        import inputs_lib
        import tasks
        return inputs_lib, tasks
    except Exception:  # pragma: no cover - the generators need Python 3.12
        return None, None
    finally:
        sys.path.pop(0)


def big_variant(text):
    """Replace every second integer token after the first line of an all-integer input by edge values."""
    lines = text.split('\n')
    out, k = [], 0
    for i, line in enumerate(lines):
        toks = line.split(' ')
        if i > 0 and toks and all(re.fullmatch(r'-?\d+', t) for t in toks if t) and any(toks):
            toks = [BIG[(k := k + 1) % len(BIG)] if (j % 2 == 0 and t) else t for j, t in enumerate(toks)]
        out.append(' '.join(toks))
    return '\n'.join(out)


def programs_dev(root):
    inputs_lib, tasks = corpus_modules(root)
    progs = []
    for path in sorted((root / 'lab' / 'census' / 'programs' / 'dev').glob('*.py')):
        text = path.read_text(encoding='utf-8')
        inputs = []
        m = re.fullmatch(r't(\d+)', path.stem)
        if m and tasks is not None and int(m.group(1)) < len(tasks.TASKS):
            gen = tasks.TASKS[int(m.group(1))][2]
            for k in range(3):
                inputs.append(getattr(inputs_lib, gen)(random.Random('%s-%d' % (path.stem, k)), k))
            if gen in NUMERIC_GENS:
                inputs.append(big_variant(inputs[0]))
                inputs.append(big_variant(inputs[1]))
        elif READS_STDIN.search(text):
            inputs = GENERIC_INPUTS[:]
        else:
            inputs = ['']
        progs.append(Prog('dev/' + path.stem, text, inputs, 'dev'))
    return progs


def collect(root, trees, sources):
    groups = []
    if 'gen' in sources:
        groups.append(programs_generated())
    if 'tests' in sources:
        for label, tree in trees:
            groups.append(programs_from_tests(tree, 'test'))
    if 'dev' in sources:
        groups.append(programs_dev(root))
    seen, out = set(), []
    for group in groups:
        for p in group:
            digest = hashlib.sha256(p.text.strip().encode('utf-8')).hexdigest()
            if digest in seen:
                continue
            seen.add(digest)
            while any(q.key == p.key for q in out):
                p.key += '+'
            out.append(p)
    return out


def subset(progs, limit):
    """Evenly spaced subset per origin, generated programs first (local mode)."""
    if not limit or limit >= len(progs):
        return progs
    by = {}
    for p in progs:
        by.setdefault(p.origin, []).append(p)
    share = {'gen': 0.4, 'test': 0.35, 'dev': 0.25}
    out = []
    for origin, ps in by.items():
        n = max(1, min(len(ps), round(limit * share.get(origin, 0.25))))
        step = len(ps) / n
        out.extend(ps[int(i * step)] for i in range(n))
    return out


# ------------------------------------------------------------------------------------------- execution

def clean_env(force=False):
    env = dict(os.environ, AIL_NO_CACHE='1', PYTHONDONTWRITEBYTECODE='1')
    for k in ('AIL_NO_GENERAL', 'AIL_UNIFIED_FORCE', 'AIL_QUIET_FALLBACK'):
        env.pop(k, None)
    if force:
        env['AIL_UNIFIED_FORCE'] = '1'
    return env


def compile_prog(tree, work, name, force, mem_kb):
    exe = work / (name + ('_f' if force else '_x'))
    rc, out, err = run([sys.executable, '-B', str(tree / 'AIL_CURRENT' / 'ail_chatgpt.py'), 'compile',
                        'p.py', '-o', exe.name], env=clean_env(force), cwd=work, timeout=300, mem_kb=mem_kb)
    res = {'built': rc == 0 and exe.exists(), 'exe': exe, 'sha': None,
           'path': 'general' if GENERAL_NOTE in err else 'typed', 'err': err.strip().splitlines()[-1:] or ['']}
    if rc is None:
        res['err'] = ['compile timed out']
    m = re.search(r'"sha256":\s*"([0-9a-f]+)"', out.decode('utf-8', 'replace'))
    res['sha'] = m.group(1) if m else None
    return res


def run_exe(comp, stdin, mem_kb):
    if not comp['built']:
        return {'built': False, 'rc': None, 'out': b'', 'err': comp['err'][0]}
    rc, out, err = run([str(comp['exe'])], stdin=stdin, timeout=20, mem_kb=mem_kb)
    return {'built': True, 'rc': rc, 'out': out, 'err': (err.strip().splitlines() or [''])[-1],
            'timeout': rc is None}


def same(r, c):
    return r['built'] and r['rc'] == c['rc'] and r['out'] == c['out']


def short(b, n=60):
    s = b.decode('utf-8', 'replace') if isinstance(b, bytes) else b
    s = s.replace('\n', '\\n')
    return s if len(s) <= n else s[:n] + '...'


def describe(r, c):
    if not r['built']:
        return 'REFUSED: ' + short(r['err'], 70)
    if r.get('timeout'):
        return 'TIMEOUT'
    if same(r, c):
        return 'ok'
    if r['rc'] != 0:
        return 'STOP rc=%s: %s' % (r['rc'], short(r['err'], 60))
    return 'DIFF out=%s want=%s' % (short(r['out'], 50), short(c['out'], 50))


def cpython(text, work, stdin):
    src = work / 'p.py'
    results = []
    for _ in range(2):
        rc, out, err = run([sys.executable, '-I', '-W', 'ignore', str(src)], stdin=stdin, timeout=20)
        results.append({'rc': rc, 'out': out})
    if results[0]['rc'] is None or results[0] != results[1] or b' at 0x' in results[0]['out']:
        return None
    return results[0]


def check_program(p, base, head, mem_kb, deadline):
    if deadline and time.time() > deadline:
        return {'key': p.key, 'skipped': 'time budget', 'rows': []}
    work = Path(tempfile.mkdtemp(prefix='rg_'))
    try:
        (work / 'p.py').write_text(p.text, encoding='utf-8')
        cpys = [cpython(p.text, work, i.encode('utf-8')) for i in p.inputs]
        if all(c is None for c in cpys):
            return {'key': p.key, 'skipped': 'CPython nondeterministic or timed out', 'rows': []}
        b = compile_prog(base, work, 'b', False, mem_kb)
        h = compile_prog(head, work, 'h', False, mem_kb)
        f = compile_prog(head, work, 'f', True, mem_kb)
        rows = []
        cache = {}
        for idx, text in enumerate(p.inputs):
            c = cpys[idx]
            if c is None:
                continue
            stdin = text.encode('utf-8')
            runs = {}
            for tag, comp in (('base', b), ('head', h), ('force', f)):
                ck = (comp['sha'], ) if comp['sha'] and comp['built'] else None
                if ck and (ck, idx) in cache:
                    runs[tag] = cache[(ck, idx)]
                    continue
                r = run_exe(comp, stdin, mem_kb)
                if ck:
                    cache[(ck, idx)] = r
                runs[tag] = r
            rows.append(classify(p, idx, text, c, runs, b, h, f))
        return {'key': p.key, 'origin': p.origin, 'base_path': b['path'] if b['built'] else None,
                'head_path': h['path'] if h['built'] else None, 'rows': rows}
    finally:
        shutil.rmtree(work, ignore_errors=True)


INT64_MIN, INT64_MAX = -(1 << 63), (1 << 63) - 1
BIG_TOKEN = re.compile(r'-?\d{19,}')


def needs_big_int(text, c):
    """Does the case itself involve an int outside int64: a number in the input or in what CPython printed?"""
    seen = text + c['out'].decode('utf-8', 'replace')
    return any(not INT64_MIN <= int(m) <= INT64_MAX for m in BIG_TOKEN.findall(seen))


def int64_stop(rh, text, c):
    """Owner decision 2026-10-31: ints are 64-bit by default. A case that needs a big int may stop loudly with the named
    OverflowError (or its program be refused at compile time naming --exact-int); anything else that stops is a regression."""
    if not needs_big_int(text, c):
        return False
    if not rh['built']:
        return '--exact-int' in rh['err'] or 'AIL_EXACT_INT' in rh['err']
    return rh['rc'] == 1 and rh['err'].startswith('OverflowError: integer overflow in ')


def classify(p, idx, text, c, runs, b, h, f):
    rb, rh, rf = runs['base'], runs['head'], runs['force']
    cats = []
    allowed = same(rb, c) and not same(rh, c) and int64_stop(rh, text, c)
    if same(rb, c) and not same(rh, c) and not allowed:
        cats.append('REGRESSION')
    if rh['built'] and rh['rc'] == 0 and (rh['out'] != c['out'] or c['rc'] != 0):
        cats.append('SILENT')
    if rf['built'] and rf['rc'] == 0 and (rf['out'] != c['out'] or c['rc'] != 0):
        cats.append('SILENT-FORCE')
    info = []
    if allowed:
        info.append('int64-stop')
    if same(rb, c) and rf['built'] and not same(rf, c) and 'SILENT-FORCE' not in cats:
        info.append('force-loud')
    if not same(rb, c) and same(rh, c):
        info.append('fixed')
    return {'key': p.key, 'input_index': idx, 'input': short(text, 80), 'cats': cats, 'info': info,
            'cpython': 'rc=%s out=%s' % (c['rc'], short(c['out'], 50)),
            'base': describe(rb, c), 'head': describe(rh, c), 'force': describe(rf, c),
            'base_out': rb['out'][:MAX_OUT].decode('utf-8', 'replace'),
            'head_out': rh['out'][:MAX_OUT].decode('utf-8', 'replace'),
            'cpython_out': c['out'][:MAX_OUT].decode('utf-8', 'replace')}


# ---------------------------------------------------------------------------------------------- report

def load_known(path):
    if not path.exists():
        return set()
    return {ln.split('#')[0].strip() for ln in path.read_text(encoding='utf-8').splitlines() if ln.split('#')[0].strip()}


def esc(s):
    return str(s).replace('|', '\\|').replace('`', "'")


def table(rows, cols, limit):
    lines = ['| ' + ' | '.join(h for h, _ in cols) + ' |', '|' + '---|' * len(cols)]
    for r in rows[:limit]:
        lines.append('| ' + ' | '.join(esc(fn(r)) for _, fn in cols) + ' |')
    if len(rows) > limit:
        lines.append('| ... %d more rows in the JSON artifact |' % (len(rows) - limit) + ' |' * (len(cols) - 1))
    return '\n'.join(lines)


def report(args, results, known, started, base_ref, head_ref):
    rows = [r for res in results for r in res['rows']]
    failing, known_hit = [], []
    for r in rows:
        bad = [c for c in r['cats']]
        if bad:
            (known_hit if r['key'] in known else failing).append(r)
    moved = [res for res in results if res.get('base_path') and res.get('head_path')
             and res['base_path'] != res['head_path']]
    skipped = [res for res in results if res.get('skipped')]
    summary = {'base': base_ref, 'head': head_ref, 'shard': args.shard, 'programs': len(results) - len(skipped),
               'runs': len(rows), 'regressions': sum('REGRESSION' in r['cats'] for r in failing),
               'silent': sum(bool({'SILENT', 'SILENT-FORCE'} & set(r['cats'])) for r in failing),
               'known': len(known_hit), 'moved': len(moved), 'skipped': len(skipped),
               'seconds': round(time.time() - started)}
    md = ['## regress-check%s: %s (head) vs %s (base)' % (' shard ' + args.shard if args.shard else '', head_ref,
                                                          base_ref), '',
          '%(programs)d programs, %(runs)d runs in %(seconds)ds. Regressions: **%(regressions)d**, silent differences: '
          '**%(silent)d**, listed in known.txt: %(known)d, path moves: %(moved)d, skipped: %(skipped)d.' % summary, '']
    cols = [('program', lambda r: r['key']), ('input', lambda r: r['input']), ('kind', lambda r: ' '.join(r['cats'])),
            ('CPython', lambda r: r['cpython']), ('base', lambda r: r['base']), ('head', lambda r: r['head']),
            ('head AIL_UNIFIED_FORCE=1', lambda r: r['force'])]
    if failing:
        md += ['### FAILED: %d case(s)' % len(failing), '', table(failing, cols, 60), '']
    else:
        md += ['No regression and no silent difference.', '']
    if known_hit:
        md += ['### Listed in lab/regress/known.txt (not failing)', '', table(known_hit, cols, 20), '']
    int64_stops = [r for r in rows if 'int64-stop' in r['info']]
    if int64_stops:
        md += ['### Information: cases that need a big int and now stop or are refused (int64 default, owner decision 2026-10-31)',
               '', '%d case(s); the stop must be the named OverflowError or a compile-time refusal naming --exact-int.' %
               len(int64_stops), '', table(int64_stops, cols, 15), '']
    force_loud = [r for r in rows if 'force-loud' in r['info']]
    if force_loud:
        md += ['### Information: only the AIL_UNIFIED_FORCE=1 build is refused or stops', '',
               table(force_loud, cols, 15), '']
    if moved:
        md += ['### Information: programs that moved between the general and the typed path', '',
               table(moved, [('program', lambda r: r['key']), ('base', lambda r: r['base_path']),
                             ('head', lambda r: r['head_path'])], 40), '']
    if skipped:
        md += ['%d program(s) not run: %s' % (len(skipped), ', '.join(sorted({s['skipped'] for s in skipped}))), '']
    text = '\n'.join(md)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = 'shard%s' % args.shard.replace('/', 'of') if args.shard else 'all'
    (out_dir / ('regress-%s.json' % tag)).write_text(json.dumps(
        {'summary': summary, 'failing': failing, 'known': known_hit, 'moved': moved, 'rows': rows,
         'skipped': [{'key': s['key'], 'why': s['skipped']} for s in skipped]}, indent=1), encoding='utf-8')
    (out_dir / ('regress-%s.md' % tag)).write_text(text, encoding='utf-8')
    step = os.environ.get('GITHUB_STEP_SUMMARY')
    if step:
        with open(step, 'a', encoding='utf-8') as fh:
            fh.write(text + '\n')
    print(text)
    return 1 if failing else 0


# ------------------------------------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--base', required=True, help='git ref of the merge base (compiler before the change)')
    ap.add_argument('--head', required=True, help='git ref of the change')
    ap.add_argument('--repo', default='.', help='git checkout holding both refs and lab/ (default: cwd)')
    ap.add_argument('--jobs', type=int, default=2)
    ap.add_argument('--limit', type=int, default=None, help='programs to run (default 60 locally, all in CI; 0 = all)')
    ap.add_argument('--filter', action='append', default=[], help='keep programs whose key contains this (repeatable)')
    ap.add_argument('--sources', default='gen,tests,dev')
    ap.add_argument('--shard', default='', help='I/N: run every N-th program starting at I')
    ap.add_argument('--mem-kb', type=int, default=None, help='RLIMIT_AS per subprocess (default 1500000 locally)')
    ap.add_argument('--budget-min', type=float, default=0, help='stop starting programs after this many minutes')
    ap.add_argument('--always', action='store_true', help='run even when the compiler did not change')
    ap.add_argument('--out', default='regress-out')
    args = ap.parse_args()
    started = time.time()
    repo = Path(args.repo).resolve()
    mem_kb = args.mem_kb if args.mem_kb is not None else (0 if IN_CI else 1500000)
    limit = args.limit if args.limit is not None else (0 if IN_CI else 60)

    changed = git(repo, 'diff', '--name-only', args.base, args.head).decode().split()
    if not args.always and not any(c.startswith(('AIL_CURRENT/', 'tools/', 'lab/regress/', '.github/workflows/regress'))
                                   for c in changed):
        msg = 'regress-check: the compiler (AIL_CURRENT, tools) is the same in base and head; nothing to compare.'
        print(msg)
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as fh:
                fh.write(msg + '\n')
        return 0

    scratch = Path(tempfile.mkdtemp(prefix='regress_trees_'))
    try:
        base = extract_tree(repo, args.base, scratch / 'base')
        head = extract_tree(repo, args.head, scratch / 'head')
        progs = collect(repo, [('base', base), ('head', head)], set(args.sources.split(',')))
        if args.filter:
            progs = [p for p in progs if any(f in p.key for f in args.filter)]
        progs = subset(progs, limit)
        if args.shard:
            i, n = (int(x) for x in args.shard.split('/'))
            progs = [p for k, p in enumerate(progs) if k % n == i]
        print('regress-check: %d programs (%s), %d inputs, jobs=%d, mem=%s'
              % (len(progs), ', '.join('%s %d' % (o, sum(p.origin == o for p in progs))
                                       for o in sorted({p.origin for p in progs})),
                 sum(len(p.inputs) for p in progs), args.jobs, mem_kb or 'unlimited'), flush=True)
        deadline = started + args.budget_min * 60 if args.budget_min else 0
        results = []
        lock = threading.Lock()
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futs = [pool.submit(check_program, p, base, head, mem_kb, deadline) for p in progs]
            for n, fut in enumerate(concurrent.futures.as_completed(futs), 1):
                res = fut.result()
                with lock:
                    results.append(res)
                bad = [r for r in res['rows'] if r['cats']]
                if bad or n % 20 == 0:
                    print('  [%d/%d] %s %s' % (n, len(futs), res['key'], sorted({c for r in bad for c in r['cats']})),
                          flush=True)
        results.sort(key=lambda r: r['key'])
        return report(args, results, load_known(HERE / 'known.txt'), started, args.base, args.head)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
