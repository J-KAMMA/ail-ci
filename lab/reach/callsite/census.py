#!/usr/bin/env python3
"""Call-site specialisation sample: baseline census, selection and counterfactual.

    python3 lab/reach/callsite/census.py [-j 2] [--out FILE.jsonl] [--only PATH ...]
    python3 lab/reach/callsite/census.py select [-j 2] -o CANDIDATES.jsonl PROGRAM[=INPUT] ...
    python3 lab/reach/callsite/census.py make-sample SELECT.jsonl ... > lab/reach/callsite/sample.txt
    python3 lab/reach/callsite/census.py trace PROGRAM INPUT          (one CPython type profile, JSON)

Default mode (the number fcspec1-fcspec3 move): builds every program of sample.txt with the
default command (`ail_chatgpt.py compile SRC --syntax python -o OUT`, AIL_NO_CACHE=1, 1.5 GB
address space, 120 s, at most -j builds at once), runs the binary and CPython 3.12 on the same
input, and prints

    typed N / general N / refused N / wrong N

plus a histogram of the first fallback/refusal reason (names and numbers replaced by
placeholders), the same per step (column 3 of sample.txt), and how many programs moved
against BASELINE.md's per-program table when `--compare BASELINE.jsonl` is given.

`select` is how sample.txt was made (docs/design/CALLSITE_SPEC.md section 7):

1. *trace*: run the program under CPython with `sys.setprofile` and record, for every call of
   a function defined in the program, the kind tuple of its parameters (int, bigint = an int
   outside int64, float, bool, str, bytes, None, list[K], dict[K,V], set[K], tuple(...), cls:C,
   fn) and the call site (line:col of the call expression, and whether the callee is named
   there directly, called as a method, or reached first-class through another call);
2. a function is *disagreeing* when two or more distinct kind tuples reach it;
3. *typed attempt*: the compile-only typed attempt of lab/census/fallback_census.py (the same
   steps as pyc._build_unshadowed_inner up to to_c(strict=True); no C compiler runs);
4. *counterfactual*: every disagreeing top-level def with at most 4 tuples, called only
   directly, is cloned in the SOURCE once per tuple (`f__cs0`, `f__cs1`, ...), each direct call
   site is rebound to the clone of the tuples it saw, and the typed attempt runs again. This is
   what source-level monomorphisation gives the existing typed path with no compiler change: an
   upper-bound-ish oracle for fcspec1/fcspec2 (it cannot model methods, fcspec3's case, or a
   site that sees two tuples).

Selection output is one JSON record per program; sample.txt keeps the programs that are not
typed today and whose fallback is attributable to a disagreeing function (see the design doc).
"""
import argparse
import ast
import collections
import concurrent.futures
import copy
import json
import os
import re
import resource
import shlex
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
AIL = ROOT / 'AIL_CURRENT' / 'ail_chatgpt.py'
SAMPLE = HERE / 'sample.txt'
BUILD_TIMEOUT = 120
RUN_TIMEOUT = 20
TRACE_TIMEOUT = 30
MEM = 1500000 * 1024
CAP_K = 4
SCALARS = {'int', 'bigint', 'float', 'bool', 'str', 'bytes', 'None'}


def _limits():
    try:
        resource.setrlimit(resource.RLIMIT_AS, (MEM, MEM))
    except (ValueError, OSError):
        pass


def source_path(p):
    p = Path(p)
    return p if p.is_absolute() else ROOT / p


def default_input(program):
    """The input a program of the corpus/census sets is checked with (lab/corpus/check.py)."""
    m = re.search(r'/(t\d{3})\.py$', str(program))
    if m and ('lab/census/programs/dev/' in str(program) or 'lab/corpus/programs/' in str(program)):
        return 'stdin:lab/corpus/tasks/%s/in0.txt' % m.group(1)
    return 'none'


def prepare_input(spec):
    if spec in ('none', ''):
        return [], None
    if spec.startswith('stdin:'):
        return [], source_path(spec[6:])
    if spec.startswith('argv:'):
        return shlex.split(spec[5:]), None
    raise SystemExit('unknown input spec %r' % spec)


def run(cmd, stdin_path, timeout, env=None, cwd=None):
    fh = open(stdin_path, 'rb') if stdin_path else subprocess.DEVNULL
    try:
        p = subprocess.run(cmd, stdin=fh, capture_output=True, timeout=timeout, env=env, cwd=cwd,
                           preexec_fn=_limits)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        return None, e.stdout or b'', e.stderr or b''
    finally:
        if stdin_path:
            fh.close()


# ---------------------------------------------------------------------------------------- trace

def _kind(v, depth=0):
    t = type(v)
    if t is bool:
        return 'bool'
    if t is int:
        return 'int' if -(1 << 63) <= v < (1 << 63) else 'bigint'
    if t is float:
        return 'float'
    if t is str:
        return 'str'
    if t is bytes:
        return 'bytes'
    if v is None:
        return 'None'
    if depth >= 2:
        return t.__name__
    if t is list:
        return 'list[%s]' % _elem(v[:8], depth)
    if t is tuple:
        return 'tuple(%s)' % ','.join(_kind(x, depth + 1) for x in v[:6]) + (',...' if len(v) > 6 else '')
    if t is dict:
        items = list(v.items())[:8]
        return 'dict[%s,%s]' % (_elem([k for k, _ in items], depth), _elem([x for _, x in items], depth))
    if t in (set, frozenset):
        return 'set[%s]' % _elem(list(v)[:8], depth)
    if callable(v) and not isinstance(v, type):
        return 'fn'
    return 'cls:' + t.__name__


def _elem(xs, depth):
    ks = sorted({_kind(x, depth + 1) for x in xs})
    if not ks:
        return '?'
    return ks[0] if len(ks) == 1 else 'mix(%s)' % '|'.join(ks)


def trace_main(program, spec, dest=None):
    """Child process: run PROGRAM under CPython with a profile hook and write the type profile
    (JSON) to DEST, or to stdout when no DEST is given."""
    import runpy
    src = source_path(program)
    target = str(src.resolve())
    args, stdin_path = prepare_input(spec)
    real_stdout = sys.stdout
    sys.stdout = open(os.devnull, 'w')
    if stdin_path:
        sys.stdin = open(stdin_path, 'r', encoding='utf-8', errors='surrogateescape')
    sys.argv = [str(src)] + args
    sys.path.insert(0, str(src.parent))
    prof = {}                                   # (qualname, firstline) -> {site: set(tuples)}
    budget = [400000]

    def hook(frame, event, arg):
        if event != 'call':
            return
        code = frame.f_code
        if code.co_filename != target or code.co_name == '<module>' or budget[0] <= 0:
            return
        budget[0] -= 1
        n = code.co_argcount + code.co_kwonlyargcount
        loc = frame.f_locals
        try:
            tup = tuple(_kind(loc.get(name)) for name in code.co_varnames[:n])
        except Exception:
            return
        back = frame.f_back
        site = None
        if back is not None and back.f_code.co_filename == target:
            try:
                pos = list(back.f_code.co_positions())[back.f_lasti // 2]
                site = '%s:%s' % (pos[0], pos[2])
            except Exception:
                site = '%s:?' % back.f_lineno
        key = '%s@%d' % (code.co_qualname, code.co_firstlineno)
        per = prof.setdefault(key, {})
        s = per.setdefault(site or 'extern', set())
        if len(s) < 8:
            s.add(tup)

    status = 'ok'
    sys.setprofile(hook)
    try:
        runpy.run_path(str(src), run_name='__main__')
    except SystemExit as e:
        status = 'exit:%s' % (e.code,)
    except BaseException as e:      # the profile still holds what ran
        status = 'raised:%s' % type(e).__name__
    finally:
        sys.setprofile(None)
    data = {'status': status, 'profile': {k: {s: sorted(map(list, ts)) for s, ts in v.items()}
                                          for k, v in prof.items()}}
    if dest:
        with open(dest, 'w', encoding='utf-8') as f:
            json.dump(data, f)
    else:
        json.dump(data, real_stdout)
    os._exit(0)                     # skip atexit handlers and buffered program output


def trace(program, spec):
    with tempfile.TemporaryDirectory(prefix='cst-') as d:
        dest = Path(d) / 'trace.json'
        rc, out, err = run([sys.executable, '-B', str(Path(__file__).resolve()), 'trace',
                            str(source_path(program)), spec, str(dest)],
                           None, TRACE_TIMEOUT, cwd=str(source_path(program).parent))
        try:
            return json.loads(dest.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {'status': 'trace-failed rc=%r %s' % (rc, err.decode('utf-8', 'replace')[-200:]),
                    'profile': {}}


# ------------------------------------------------------------------------- source facts

def _site_calls(tree):
    """'line:col' of every Call -> ('direct', name) | ('method', attr) | ('other', None), plus the
    names used first-class (read as a value other than as a Call's func)."""
    calls, firstclass = {}, set()
    funcs = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            key = '%d:%d' % (n.lineno, n.col_offset)
            if isinstance(n.func, ast.Name):
                calls[key] = ('direct', n.func.id)
                funcs.add(id(n.func))
            elif isinstance(n.func, ast.Attribute):
                calls[key] = ('method', n.func.attr)
                funcs.add(id(n.func))
            else:
                calls[key] = ('other', None)
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and id(n) not in funcs:
            firstclass.add(n.id)
        if isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Load) and id(n) not in funcs:
            firstclass.add(n.attr)
    return calls, firstclass


def disagreements(src_text, profile):
    """The functions two or more kind tuples reach, with what the design needs to know of each."""
    tree = ast.parse(src_text)
    calls, firstclass = _site_calls(tree)
    top = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    out = []
    for key, sites in profile.items():
        qual, line = key.rsplit('@', 1)
        tuples = sorted({tuple(t) for ts in sites.values() for t in ts})
        if len(tuples) < 2:
            continue
        name = qual.split('.')[-1]
        if '<locals>' in qual:
            scope = 'nested'
        elif '.' in qual:
            scope = 'init' if name == '__init__' else 'method'
        elif name == '<lambda>':
            scope = 'lambda'
        else:
            scope = 'def'
        kinds = {k for t in tuples for k in t}
        if all(k in SCALARS for k in kinds):
            kclass = 'scalar'
        elif any(k.startswith('cls:') for k in kinds) or scope in ('method', 'init'):
            kclass = 'class'
        else:
            kclass = 'container'
        how = collections.Counter()
        for s in sites:
            c = calls.get(s)
            how['extern' if s == 'extern' else c[0] if c else 'unknown'] += 1
        d = dict(fn=qual, line=int(line), scope=scope, kclass=kclass, ntuples=len(tuples),
                        tuples=[list(t) for t in tuples], sites={s: [list(t) for t in ts] for s, ts in sites.items()},
                        how=dict(how), firstclass=name in firstclass,
                        bigint='bigint' in kinds,
                        intfloat=any('int' in t and 'float' in u and t.index('int') == u.index('float')
                                     for t in tuples for u in tuples),
                 end=getattr(top.get(name), 'end_lineno', None) if scope == 'def' else None)
        d['nreal'] = len(real_keys(d))
        out.append(d)
    return out


def _fits(a, b):
    """Kind `a` with its `?` (an empty container's unknown element) read as a wildcard matches b."""
    if a == b:
        return True
    if '?' not in a:
        return False
    return re.fullmatch(re.escape(a).replace(r'\?', '.*'), b) is not None


def real_keys(d):
    """The instance keys the design (section 2) would build for a disagreeing function: an empty
    container's `?` element is not a key (it takes the element kind of a site that has one), and
    for a method or `__init__` the `self` position is not a key (a subclass receiver is
    inheritance, not specialisation). Returns the sorted distinct keys."""
    tuples = [tuple(t) for t in d['tuples']]
    if d['scope'] in ('method', 'init'):
        tuples = [t[1:] for t in tuples]
    keys = []
    for t in sorted(set(tuples), key=lambda t: sum('?' in k for k in t)):
        if any(len(t) == len(k) and all(_fits(x, y) for x, y in zip(t, k)) for k in keys):
            continue
        keys.append(t)
    return sorted(keys)


def clone_source(src_text, dis):
    """Source-level monomorphisation of the cloneable disagreeing top-level defs (see module doc).
    Returns (new_source, cloned_names)."""
    tree = ast.parse(src_text)
    top = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    plan = {}
    for d in dis:
        name = d['fn']
        keys = real_keys(d)
        if d['scope'] != 'def' or name not in top or not 2 <= len(keys) <= CAP_K or d['firstclass']:
            continue
        if set(d['how']) - {'direct'}:
            continue
        index = {}
        for t in d['tuples']:
            t = tuple(t)
            index[t] = next(i for i, k in enumerate(keys)
                            if len(t) == len(k) and all(_fits(x, y) for x, y in zip(t, k)))
        plan[name] = (index, d['sites'], len(keys))
    if not plan:
        return None, []

    class Rebind(ast.NodeTransformer):
        def __init__(self, inside=None, inside_tuple=None):
            self.inside, self.inside_tuple = inside, inside_tuple

        def visit_Call(self, node):
            self.generic_visit(node)
            if isinstance(node.func, ast.Name) and node.func.id in plan:
                index, sites, _ = plan[node.func.id]
                seen = sites.get('%d:%d' % (node.lineno, node.col_offset), [])
                ids = {index[tuple(t)] for t in seen}
                if len(ids) == 1:
                    node.func = ast.Name(id='%s__cs%d' % (node.func.id, ids.pop()), ctx=ast.Load())
                elif node.func.id == self.inside and self.inside_tuple in ids:
                    node.func = ast.Name(id='%s__cs%d' % (self.inside, self.inside_tuple), ctx=ast.Load())
            return node

    body = []
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name in plan:
            _, _, nkeys = plan[n.name]
            for i in range(nkeys):
                c = copy.deepcopy(n)
                c.name = '%s__cs%d' % (n.name, i)
                body.append(Rebind(n.name, i).visit(c))
            body.append(n)          # kept for any call site that saw several tuples
        else:
            body.append(Rebind().visit(n))
    new = ast.Module(body=body, type_ignores=[])
    ast.fix_missing_locations(new)
    # drop the original when nothing calls it any more
    text = ast.unparse(new)
    t2 = ast.parse(text)
    used = {x.id for x in ast.walk(t2) if isinstance(x, ast.Name)}
    t2.body = [n for n in t2.body if not (isinstance(n, ast.FunctionDef) and n.name in plan
                                          and n.name not in used)]
    return ast.unparse(t2) + '\n', sorted(plan)


# ------------------------------------------------------------------- typed attempt (compile only)

_FC = None


def _fc():
    """lab/census/fallback_census.py, pointed at this checkout's compiler."""
    global _FC
    if _FC is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location('fallback_census', ROOT / 'lab' / 'census' / 'fallback_census.py')
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.ROOT = ROOT / 'AIL_CURRENT'
        mod._setup()
        _FC = mod
    return _FC


def typed_attempt(path, timeout=60):
    """(True, None) when the typed path takes the whole program; else (False, (reason, line))."""
    fc = _fc()
    import pyc
    from pyfront import Unsupported
    signal.alarm(timeout)
    try:
        src = fc._prepare(path)
        if pyc._is_whole_program(src):
            pyc._refuse_big_capable(src, local=False)
        pyc._refuse_typed_big_store(src, False)
        pyc.to_c(src, strict=True, info={'_checked_arrays': True})
        return True, None
    except Unsupported as e:
        return False, ((str(e).splitlines() or [''])[0][:200], getattr(e, 'source_line', None))
    except fc._Timeout:
        return False, ('timeout', None)
    except Exception as e:
        return False, ('%s: %s' % (type(e).__name__, str(e)[:160]), None)
    finally:
        signal.alarm(0)


def strip_signatures(text):
    """The same program with every def's parameter and return annotations removed (class bodies,
    dataclass fields and local annotations kept): what the program is to a user who never
    annotates functions. Runtime behaviour, and so the CPython type profile, is unchanged."""
    tree = ast.parse(text)
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            n.returns = None
            for a in n.args.posonlyargs + n.args.args + n.args.kwonlyargs:
                a.annotation = None
            for a in (n.args.vararg, n.args.kwarg):
                if a is not None:
                    a.annotation = None
    return ast.unparse(tree) + '\n'


def select_one(item):
    program, spec = item
    rec = {'program': program, 'input': spec}
    src = source_path(program)
    text = src.read_text(encoding='utf-8')
    if STRIP:
        # the profile's sites and the clone rewrite stay on the ORIGINAL text (its line:col);
        # only the typed attempts see the stripped program (whose line numbers then differ)
        rec['stripped'] = True
        tmpdir = tempfile.mkdtemp(prefix='css-')
        src = Path(tmpdir) / src.name
        src.write_text(strip_signatures(text), encoding='utf-8')
    try:
        return _select_one(rec, program, spec, src, text)
    finally:
        if STRIP:
            subprocess.run(['rm', '-rf', tmpdir])


def _select_one(rec, program, spec, src, text):
    prof = trace(program, spec)
    rec['trace'] = prof['status']
    try:
        dis = disagreements(text, prof['profile'])
    except SyntaxError as e:
        rec['error'] = 'syntax: %s' % e
        return rec
    rec['dis'] = dis
    tree = ast.parse(text)
    defs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    params = [a for f in defs for a in f.args.args if a.arg not in ('self', 'cls')]
    rec['defs'] = len(defs)
    rec['params'] = len(params)
    rec['unannotated_params'] = sum(a.annotation is None for a in params)
    if not dis and not TYPED_ALL:
        return rec
    ok, why = typed_attempt(str(src))
    rec['typed'] = ok
    if ok:
        return rec
    rec['reason'], rec['line'] = why
    if not dis:
        return rec
    new, cloned = clone_source(text, dis)
    rec['cloned'] = cloned
    if new is None:
        return rec
    if STRIP:
        new = strip_signatures(new)
    with tempfile.TemporaryDirectory(prefix='cs-') as d:
        p = Path(d) / src.name
        p.write_text(new, encoding='utf-8')
        ok2, why2 = typed_attempt(str(p))
    rec['sim_typed'] = ok2
    if not ok2:
        rec['sim_reason'], rec['sim_line'] = why2
    return rec


TYPED_ALL = False
STRIP = False


def _pool_init(typed_all=False, strip=False):
    global TYPED_ALL, STRIP
    TYPED_ALL, STRIP = typed_all, strip
    _limits()
    _fc()                               # its _setup installs the SIGALRM -> _Timeout handler


def select_main(a):
    items = []
    for p in a.programs:
        prog, _, spec = p.partition('=')
        items.append((prog, spec or default_input(prog)))
    import multiprocessing
    with open(a.output, 'w', encoding='utf-8') as out, \
            multiprocessing.Pool(a.jobs, initializer=_pool_init, initargs=(a.typed_all, a.strip),
                                 maxtasksperchild=10) as pool:
        for rec in pool.imap(select_one, items):
            out.write(json.dumps(rec) + '\n')
            out.flush()
    return 0


# ----------------------------------------------------------------------------- make-sample

CALLSITE_MSG = re.compile(
    r"passing a float to .*whose .* is an int64|gets a (list of )?bools? from some calls and a|"
    r"passing \w+ where .*\(\) wants|but the caller also supplies|default for .* but the parameter is|"
    r"used both in float arithmetic and at a site|call sites disagree|is called with rows of")
STEP_OF = {'scalar': 'S1', 'container': 'S2', 'class': 'S3'}


def classify(rec):
    """(step, confidence, functions) of one select record, or None when it is not in the sample:
    the program must not be typed today and must have a function reached by two or more of the
    design's instance keys (`real_keys`)."""
    if rec.get('typed') is not False:
        return None
    real = [d for d in rec.get('dis', []) if d.get('nreal', len(real_keys(d))) >= 2]
    if not real:
        return None
    line = rec.get('line')
    attributable = bool(line) and any(
        (d.get('end') and d['line'] <= line <= d['end'])
        or any(s.split(':')[0] == str(line) for s in d['sites']) for d in real)
    msg = bool(CALLSITE_MSG.search(rec.get('reason') or ''))
    moved = bool(rec.get('cloned')) and not rec.get('sim_typed') and rec.get('sim_reason') != rec.get('reason')
    if rec.get('sim_typed'):
        conf = 'high'
    elif msg or attributable or moved:
        conf = 'medium'
    else:
        conf = 'low'
    order = {'S1': 0, 'S2': 1, 'S3': 2, 'out': 3}
    steps = []
    for d in real:
        if d['scope'] in ('nested', 'lambda'):
            steps.append('out')
        elif d['scope'] in ('method', 'init'):
            steps.append('S3')
        else:
            steps.append(STEP_OF[d['kclass']] if d['kclass'] != 'class' else 'S3')
    step = max(steps, key=order.get)      # the step that covers every disagreeing function
    funcs = ';'.join('%s(%s)' % (d['fn'], '|'.join(','.join(k) for k in real_keys(d))[:120]) for d in real)
    return step, conf, funcs


def make_sample_main(paths):
    print('# lab/reach/callsite/sample.txt -- fixed order; made by `census.py make-sample` from '
          '`census.py select` records (docs/design/CALLSITE_SPEC.md section 7)')
    print('# program<TAB>input<TAB>step (S1 scalar defs, S2 container defs/returns/recursion, S3 methods '
          'and constructors, out = nested/lambda)<TAB>confidence (high: source clones make it typed; '
          'medium: the first refusal is a call-site message or sits in/at a disagreeing function; '
          'low: an unrelated blocker comes first)<TAB>disagreeing functions(keys)')
    rows = []
    for p in paths:
        for line in open(p, encoding='utf-8'):
            rec = json.loads(line)
            c = classify(rec)
            if c:
                rows.append((rec['program'], rec['input']) + c)
    seen = set()
    for r in sorted(rows):
        if r[0] in seen:
            continue
        seen.add(r[0])
        print('\t'.join(r))
    return 0


# ------------------------------------------------------------------------- default census

def read_sample(path=SAMPLE):
    rows = []
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        cols = line.split('\t')
        rows.append(dict(program=cols[0], input=cols[1], step=cols[2] if len(cols) > 2 else '?',
                         confidence=cols[3] if len(cols) > 3 else '?',
                         functions=cols[4] if len(cols) > 4 else ''))
    return rows


def bucket(reason):
    r = re.sub(r'^.*?built on the general path \(about \d+x slower\) because ', '', reason)
    r = re.sub(r'^note: ', '', r)
    r = re.sub(r'^[\w./-]+\.py:\d+:\d+: ', '', r)
    r = re.sub(r"'[^']*'|`[^`]*`", "'X'", r)
    r = re.sub(r'\d+', 'N', r)
    return r[:90]


def first_reason(err):
    for line in (err or '').splitlines():
        if 'built on the general path' in line or 'not in the subset' in line or 'error' in line.lower():
            return line.strip()
    lines = [x for x in (err or '').splitlines() if x.strip()]
    return lines[-1].strip() if lines else ''


def census_one(row):
    src = source_path(row['program'])
    rec = dict(row)
    args, stdin_path = prepare_input(row['input'])
    work = Path(tempfile.mkdtemp(prefix='csc-'))
    try:
        env = dict(os.environ, AIL_NO_CACHE='1')
        rc, out, err = run([sys.executable, '-B', str(AIL), 'compile', str(src), '--syntax', 'python',
                            '-o', str(work / 'main.out')], None, BUILD_TIMEOUT, env=env, cwd=str(work))
        err = err.decode('utf-8', 'replace')
        if rc != 0:
            rec['result'] = 'refused'
            rec['reason'] = first_reason(err)[:300] if rc is not None else 'build timed out'
            return rec
        general = 'built on the general path' in err
        rec['reason'] = first_reason(err)[:300] if general else ''
        exp = run([sys.executable, '-B', str(src), *args], stdin_path, RUN_TIMEOUT, cwd=str(src.parent))
        got = run([str(work / 'main.out'), *args], stdin_path, RUN_TIMEOUT, cwd=str(src.parent))
        if exp[0] != got[0] or exp[1] != got[1]:
            rec['result'] = 'wrong'
            rec['detail'] = 'cpython rc=%r ail rc=%r %s' % (exp[0], got[0], got[2][-200:].decode('utf-8', 'replace'))
        else:
            rec['result'] = 'general' if general else 'typed'
        rec['size'] = (work / 'main.out').stat().st_size
        return rec
    finally:
        subprocess.run(['rm', '-rf', str(work)])


def census_main(a):
    rows = read_sample()
    if a.only:
        rows = [r for r in rows if r['program'] in a.only]
    with concurrent.futures.ThreadPoolExecutor(a.jobs) as ex:
        recs = list(ex.map(census_one, rows))
    if a.out:
        with open(a.out, 'w', encoding='utf-8') as f:
            for r in recs:
                f.write(json.dumps(r) + '\n')
    c = collections.Counter(r['result'] for r in recs)
    print('programs %d: typed %d / general %d / refused %d / wrong %d'
          % (len(recs), c['typed'], c['general'], c['refused'], c['wrong']))
    for step in sorted({r['step'] for r in recs}):
        cs = collections.Counter(r['result'] for r in recs if r['step'] == step)
        print('  %s: %d programs, typed %d / general %d / refused %d / wrong %d'
              % (step, sum(cs.values()), cs['typed'], cs['general'], cs['refused'], cs['wrong']))
    for conf in ('high', 'medium', 'low'):
        cs = collections.Counter(r['result'] for r in recs if r['confidence'] == conf)
        if cs:
            print('  confidence %s: %d programs, typed %d / general %d / refused %d / wrong %d'
                  % (conf, sum(cs.values()), cs['typed'], cs['general'], cs['refused'], cs['wrong']))
    h = collections.Counter(bucket(r.get('reason', '')) for r in recs if r['result'] != 'typed')
    print('reasons (not typed):')
    for k, v in h.most_common():
        print('  %3d  %s' % (v, k))
    if a.compare:
        before = {json.loads(l)['program']: json.loads(l)['result'] for l in open(a.compare, encoding='utf-8')}
        moved = [(r['program'], before.get(r['program']), r['result']) for r in recs
                 if before.get(r['program']) != r['result']]
        print('moved against %s: %d' % (a.compare, len(moved)))
        for m in moved:
            print('  %s: %s -> %s' % m)
    for r in recs:
        if r['result'] == 'wrong':
            print('WRONG', r['program'], r.get('detail', ''))
    return 1 if c['wrong'] else 0


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'trace':
        return trace_main(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else 'none',
                          sys.argv[4] if len(sys.argv) > 4 else None)
    if len(sys.argv) > 1 and sys.argv[1] == 'make-sample':
        return make_sample_main(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == 'select':
        ap = argparse.ArgumentParser(prog='census.py select')
        ap.add_argument('programs', nargs='+')
        ap.add_argument('-o', '--output', required=True)
        ap.add_argument('-j', '--jobs', type=int, default=2)
        ap.add_argument('--typed-all', action='store_true',
                        help='run the typed attempt on every program, not only on disagreeing ones')
        ap.add_argument('--strip', action='store_true',
                        help='judge each program with its def signatures unannotated (strip_signatures)')
        return select_main(ap.parse_args(sys.argv[2:]))
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('-j', '--jobs', type=int, default=2)
    ap.add_argument('--out')
    ap.add_argument('--compare')
    ap.add_argument('--only', nargs='*')
    return census_main(ap.parse_args())


if __name__ == '__main__':
    sys.exit(main())
