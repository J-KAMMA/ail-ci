#!/usr/bin/env python3
"""compare-rival: AIL against the Python compilers Nuitka, Cython, mypyc and Codon, plus PyPy.

    python3 lab/compare_rival/run.py                       # all ten tasks, every rival -> results.json + RESULTS.md
    python3 lab/compare_rival/run.py --tasks tree_fold chain_relax
    python3 lab/compare_rival/run.py --tools nuitka,cython-main
    python3 lab/compare_rival/run.py --tools pypy           # the interpreter arm only
    python3 lab/compare_rival/run.py --safety              # only the five safety probes

Every rival compiles the same source AIL uses: Nuitka and plain Cython take `src/<task>/main.py`,
mypyc, Codon and annotated Cython take `src/<task>/typed.py`.  `ail` is the compare-lab AIL column
(typed.py through AIL), `ail-py` compiles main.py.  `pypy` runs main.py in the PyPy interpreter: it
compiles nothing (`compile_s` is `-`, its build disk is the interpreter install marked `interpreter`)
and it is measured in two ways, because its JIT needs warm-up: the plain wall time of a fresh
process (median of 5, like every other row) and the time of the 5th run inside one process
(`warm5_ms`, `pypy_warm.py`), on the same input with the same reference.  A refusal is a result:
the first error line is kept.  `patches/<tool>/<task>/` may hold a syntax-only patch, and the row
is marked "patched".

Measurement reuses lab/compare/run_task.py: the perf input and every public/hidden case come from
the task's gen.py, the oracle is its reference.py, wall time is the median of 5 runs, instructions
come from callgrind (or perf_event when the runner exposes it), peak RSS from `/usr/bin/time -v`,
and the build is one cold build in a fresh directory (compile time, build disk, artifact size).
Deliberate reductions from compare-lab's settings, each recorded in `settings` in results.json and
above the tables in RESULTS.md:
one cold build instead of three (a Nuitka onefile build is minutes); RUN_TIMEOUT 180 s instead of
1500 s, so a rival slower than 3 min is recorded as "timeout" rather than measured; CASE_TIMEOUT
30 s instead of 120 s; CALLGRIND_TIMEOUT 120 s instead of 7000 s; callgrind skipped when the wall
time exceeds 4 s; and a 240 s per-tool budget for the public/hidden cases.  The consequence is
visible in the tables: most instruction cells are "-", the instruction verdict has n=1, and the
two "timeout" rows would have been measured under run_task.py's 1500 s.  Restoring the reference
timeouts means re-measuring all ten tasks, not just regenerating the report.

Safety probes in safety/*.py are built by every tool and run without arguments; their stdout and
exit status are compared with CPython's.  A compiled program that exits 0 with a different answer
is "silently wrong", the number that matters most.
"""
import argparse, importlib.util, json, os, re, shlex, shutil, statistics, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
COMPARE = REPO / 'lab' / 'compare'
AIL = REPO / 'AIL_CURRENT' / 'ail_chatgpt.py'
AIL_DIR = REPO / 'AIL_CURRENT'
VENV = Path(os.environ.get('RIVAL_VENV', '/tmp/rival-venv'))
CODON_BIN = Path(os.environ.get('CODON_BIN', '/tmp/codon/codon-deploy-linux-x86_64/bin/codon'))
PY = sys.executable                        # CPython 3.12, the interpreter every rival is built for
CYTHON = VENV / 'bin' / 'cython'
VENVPY = VENV / 'bin' / 'python'

TASKS = sorted(p.name for p in (COMPARE / 'src').iterdir() if p.is_dir())
ALL_TOOLS = ['ail', 'ail-py', 'cython-main', 'cython-typed', 'nuitka', 'mypyc', 'codon', 'codon-main', 'pypy']
SOURCE = {'ail': 'typed.py', 'ail-py': 'main.py', 'cython-main': 'main.py', 'cython-typed': 'typed.py',
          'nuitka': 'main.py', 'mypyc': 'typed.py', 'codon': 'typed.py', 'codon-main': 'main.py',
          'pypy': 'main.py'}
STANDALONE = {'ail': True, 'ail-py': True, 'cython-main': True, 'cython-typed': True, 'nuitka': True,
              'mypyc': False, 'codon': True, 'codon-main': True, 'pypy': False}
# An interpreter compiles nothing: `compile_s` is '-', the build disk is the install and the kind says so.
INTERPRETER = {'pypy': True}
# PyPy's JIT needs warm-up to show its steady rate, so it also gets the 5th run in one process.
WARM5 = {'pypy': True}
PYPY = Path(os.environ.get('PYPY', '/opt/hostedtoolcache/PyPy/3.11.17/x64/bin/pypy3'))
WARM_SRC = HERE / 'pypy_warm.py'
# "single executable" for Cython means one file that links libpython3.12 at run time; mypyc leaves a
# Python extension module that needs the interpreter plus the `ail` runtime module.
ANSI = re.compile(r'\x1b\[[0-9;]*m')

AIL_STUB = '''from typing import Any
def read_stdin_bytes(size: Any) -> bytes: ...
def write_stdout_bytes(data: Any) -> None: ...
def read_bytes(path: Any) -> bytes: ...
def heappush(heap: Any, item: Any, key: Any = ...) -> None: ...
def heappop(heap: Any, key: Any = ...) -> Any: ...
def wrapping_add(a: Any, b: Any) -> int: ...
def wrapping_sub(a: Any, b: Any) -> int: ...
def wrapping_mul(a: Any, b: Any) -> int: ...
'''


def load_rt():
    spec = importlib.util.spec_from_file_location('compare_run_task', COMPARE / 'run_task.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.TASK_BASE = COMPARE
    module.BUILD_RUNS = 1          # one cold build for every tool here; see the module docstring
    return module


RT = load_rt()
# A Cython-compiled task can execute 50x slower than AIL; callgrind on the 80 MB perf input then takes
# minutes.  Cap it and record a timeout ('-') rather than a number from a different input.
RT.CALLGRIND_TIMEOUT = 120
RT.RUN_TIMEOUT = 180          # a rival that needs more than 3 minutes for one run has lost that column
RT.CASE_TIMEOUT = 30
CALLGRIND_MAX_WALL_MS = 4000
CASE_BUDGET_S = 240
SETTINGS = dict(build_runs=RT.BUILD_RUNS, run_timeout_s=RT.RUN_TIMEOUT, case_timeout_s=RT.CASE_TIMEOUT,
                callgrind_timeout_s=RT.CALLGRIND_TIMEOUT, callgrind_max_wall_ms=CALLGRIND_MAX_WALL_MS,
                case_budget_s=CASE_BUDGET_S)


def tail(data, n=800):
    return data.decode('utf8', 'replace')[-n:] if isinstance(data, bytes) else str(data)[-n:]


def first_error(data):
    text = ANSI.sub('', data.decode('utf8', 'replace') if isinstance(data, bytes) else str(data))
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for line in lines:
        if re.search(r'\berror\b', line, re.I):
            return line[:300]
    return lines[0][:300] if lines else ''


def run(cmd, cwd, env, timeout=2400):
    return subprocess.run([str(c) for c in cmd], cwd=str(cwd), env=env, capture_output=True, timeout=timeout)


def embed_flags():
    out = subprocess.run(['python3-config', '--embed', '--cflags'], capture_output=True, text=True).stdout
    ld = subprocess.run(['python3-config', '--embed', '--ldflags'], capture_output=True, text=True).stdout
    return shlex.split(out), shlex.split(ld)


CFLAGS, LDFLAGS = embed_flags()


def versions():
    def first(cmd):
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            return ((p.stdout or p.stderr).strip().splitlines() or [''])[0]
        except Exception as e:
            return 'missing (%s)' % type(e).__name__
    return dict(ail=first([PY, str(AIL), '--version']), python=sys.version.split()[0],
                gcc=first(['gcc', '--version']), cython=first([str(CYTHON), '--version']),
                mypy=first([str(VENVPY), '-m', 'mypy', '--version']),
                nuitka=first([str(VENVPY), '-m', 'nuitka', '--version']),
                codon=first([str(CODON_BIN), '--version']),
                pypy=pypy_version(),
                valgrind=first(['valgrind', '--version']))


def read_pins():
    pins = {}
    try:
        for line in (HERE / 'toolchains.env').read_text().splitlines():
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                pins[k.strip()] = v.strip()
    except OSError:
        pass
    return pins


def _artifact(d, tool, stem):
    if tool == 'nuitka':
        return d / 'out' / 'prog'
    if tool in ('cython-main', 'cython-typed', 'codon', 'codon-main'):
        return d / 'prog'
    if tool == 'mypyc':
        found = sorted(d.glob(stem + '*.so'))
        return found[0] if found else None
    return None


def build_tool(tool, label, src, root, probe=False):
    """One cold build of `src` with `tool`.  Returns a record with the command that runs it."""
    fresh, env = RT.fresh_dir(root, '%s-%s' % (tool, label))
    empty = RT.du_kib(fresh)
    d = fresh / 'src'
    d.mkdir()
    source = d / src.name
    shutil.copy(src, source)
    stem = source.stem
    rec = dict(tool=tool, source=src.name, standalone=STANDALONE[tool], dir=str(d))
    if tool == 'mypyc':
        (d / 'ail.pyi').write_text(AIL_STUB)
        env['MYPYPATH'] = str(d)
        env['PYTHONPATH'] = str(d) + ':' + str(AIL_DIR)
    steps = []
    if tool == 'nuitka':
        steps = [[str(VENVPY), '-m', 'nuitka', '--onefile', '--assume-yes-for-downloads',
                  '--output-dir=out', '--output-filename=prog', source.name]]
    elif tool in ('cython-main', 'cython-typed'):
        steps = [[str(CYTHON), '--embed', '-3', '-o', 'prog.c', source.name],
                 ['gcc', '-O2', '-o', 'prog', 'prog.c', *CFLAGS, *LDFLAGS, '-lm']]
    elif tool == 'mypyc':
        steps = [[str(VENVPY), '-m', 'mypyc', source.name]]
    elif tool in ('codon', 'codon-main'):
        env['CODON_PATH'] = str(AIL_DIR)
        steps = [[str(CODON_BIN), 'build', '-release', '-o', 'prog', source.name]]
    else:
        raise ValueError(tool)
    start = time.perf_counter()
    ok = True
    err = b''
    for cmd in steps:
        try:
            p = run(cmd, d, env)
        except subprocess.TimeoutExpired:
            ok, err = False, b'build timeout'
            break
        if p.returncode != 0:
            ok, err = False, (p.stderr or p.stdout)
            break
    elapsed = time.perf_counter() - start
    artifact = _artifact(d, tool, stem)
    ok = ok and artifact is not None and artifact.is_file()
    rec.update(build_ok=ok, compile_s=round(elapsed, 3), build_disk_kib=max(RT.du_kib(fresh) - empty, 0),
               binary_bytes=artifact.stat().st_size if ok else None,
               build_error=first_error(err) if not ok else '')
    if tool == 'mypyc' and ok:
        # a compiled extension module still needs the interpreter; a 3-line launcher is the mypyc way
        launch = d / 'launcher.py'
        if probe:
            launch.write_text('import %s\n' % stem)
        else:
            launch.write_text('import sys\nimport %s\nsys.exit(%s.main())\n' % (stem, stem))
        rec['launcher'] = str(launch)
        rec['standalone'] = False
    if not ok:
        rec['run_cmd'] = None
        return rec
    if tool == 'nuitka':
        rec['run_cmd'] = [str(artifact)]
    elif tool == 'cython-main':
        rec['run_cmd'] = [str(artifact)]
    elif tool == 'cython-typed':
        rec['run_cmd'] = ['/usr/bin/env', 'PYTHONPATH=' + str(AIL_DIR), str(artifact)]
    elif tool == 'mypyc':
        rec['run_cmd'] = ['/usr/bin/env', 'PYTHONPATH=%s:%s' % (d, AIL_DIR), PY, '-B', str(d / 'launcher.py')]
    elif tool in ('codon', 'codon-main'):
        rec['run_cmd'] = [str(artifact)]
    return rec


def build_ail(lang, task, root):
    task_src = COMPARE / 'src' / task
    rec, cmd = RT.build_language(lang, task_src, root)
    rec.update(tool=lang, source=SOURCE[lang], standalone=True)
    if cmd:
        rec['run_cmd'] = cmd
    return rec


def reference_for(task, case, work):
    out = work / 'expected.out'
    stdin = open(case['path'], 'rb') if case['stdin'] else subprocess.DEVNULL
    try:
        with open(out, 'wb') as f:
            p = subprocess.run([PY, str(COMPARE / 'tasks' / task / 'reference.py'), *case['args']],
                               stdin=stdin, stdout=f, stderr=subprocess.PIPE, timeout=6 * RT.RUN_TIMEOUT)
    finally:
        if case['stdin']:
            stdin.close()
    return dict(returncode=p.returncode, stdout=out)


def check_cases_budget(tool, cmd, check, expected, work, budget=CASE_BUDGET_S):
    """RT.check_cases with a per-tool wall budget; cases not reached are counted as not matched."""
    tally = {'public': [0, 0], 'hidden': [0, 0]}
    failed = []
    skipped = 0
    start = time.perf_counter()
    out = work / ('chk-' + tool)
    for kind, case_name, case in check:
        if time.perf_counter() - start > budget:
            skipped += 1
            tally[kind][1] += 1
            failed.append('%s/%s (skipped, budget)' % (kind, case_name))
            continue
        ok = False
        try:
            p = RT.exec_prog([], cmd, case, out, RT.CASE_TIMEOUT)
            ok = (p.returncode, out.read_bytes()) == expected[(kind, case_name)]
        except subprocess.TimeoutExpired:
            pass
        tally[kind][1] += 1
        if ok:
            tally[kind][0] += 1
        else:
            failed.append('%s/%s' % (kind, case_name))
    out.unlink(missing_ok=True)
    return dict(cases_public=tally['public'], cases_hidden=tally['hidden'], cases_failed=failed[:20],
                cases_skipped=skipped)


def pypy_version():
    try:
        p = subprocess.run([str(PYPY), '--version'], capture_output=True, text=True, timeout=60)
        text = (((p.stdout or '') + (p.stderr or '')).strip().splitlines())
        return ' '.join(line for line in text if line) or 'missing'
    except Exception as e:
        return 'missing (%s)' % type(e).__name__


def pypy_install_kib():
    """The interpreter install PyPy needs on disk; it is not a build artifact (nothing is built)."""
    try:
        return RT.du_kib(Path(os.path.realpath(str(PYPY))).parents[1])
    except Exception:
        return None


def build_pypy(task, root):
    """PyPy builds nothing: the row is the interpreter plus the source it runs."""
    fresh, env = RT.fresh_dir(root, 'pypy-' + task)
    d = fresh / 'src'
    d.mkdir()
    source = d / SOURCE['pypy']
    shutil.copy(COMPARE / 'src' / task / SOURCE['pypy'], source)
    return dict(tool='pypy', source=source.name, standalone=False, interpreter=True, dir=str(d),
                build_ok=PYPY.is_file(), build_error='' if PYPY.is_file() else 'pypy not found at %s' % PYPY,
                compile_s=None, build_disk_kib=pypy_install_kib(), binary_bytes=None,
                run_cmd=[str(PYPY), '-B', str(source)] if PYPY.is_file() else None)


def warm5(rec, case, expected, work):
    """Time the 5th run of the program in one PyPy process (the run a warmed JIT does)."""
    out_json = work / 'warm-pypy.json'
    stdin = str(case['path']) if case['stdin'] else '-'
    cmd = [str(PYPY), '-B', str(WARM_SRC), rec['run_cmd'][2], '5', str(expected['stdout']),
           str(expected['returncode']), stdin, str(out_json), *case['args']]
    try:
        p = subprocess.run(cmd, cwd=work, capture_output=True, timeout=RT.RUN_TIMEOUT * 5,
                           env=dict(os.environ, AIL_NO_CACHE='1'))
    except subprocess.TimeoutExpired:
        return dict(warm5_ms=None, warm5_note='timeout')
    if not out_json.is_file():
        return dict(warm5_ms=None, warm5_note='no report: %s' % first_error(p.stderr or p.stdout))
    try:
        report = json.loads(out_json.read_text())
    finally:
        for f in work.glob('warm-run-*.out'):
            f.unlink(missing_ok=True)
    runs = report.get('runs') or []
    if len(runs) < 5:
        return dict(warm5_ms=None, warm5_note='only %d runs' % len(runs))
    return dict(warm5_ms=round(runs[4]['seconds'] * 1000, 1), warm5_runs_ms=[round(r['seconds'] * 1000, 1) for r in runs],
                warm5_correct=runs[4]['match'], warm5_all_correct=all(r['match'] for r in runs),
                warm_mode=report.get('mode'))


def measure(rec, task, case, expected, check, expected_cases, work, icount, mode):
    cmd = rec.get('run_cmd')
    if not cmd:
        return rec
    rec.update(RT.run_pass(rec['tool'], cmd, case, expected, work, smoke=False))
    if WARM5.get(rec['tool']) and rec.get('status') in ('ok', 'MISMATCH'):
        rec.update(warm5(rec, case, expected, work))
    if check and rec.get('status') == 'timeout':
        rec['cases_note'] = 'perf run timed out; cases not run'
    elif check:
        rec.update(check_cases_budget(rec['tool'], cmd, check, expected_cases, work))
    if mode != 'none' and rec.get('status') in ('ok', 'MISMATCH'):
        wall = rec.get('wall_ms')
        if wall is not None and wall > CALLGRIND_MAX_WALL_MS:
            # callgrind is ~50-100x slower than native; a 5 s run would take most of a job's budget.
            rec['instructions'] = None
            rec['instructions_note'] = 'skipped: wall > 4 s, callgrind too slow'
        else:
            try:
                rec['instructions'] = RT.count_instructions(rec['tool'], cmd, case, work, icount, mode)
                if rec['instructions'] is None:
                    rec['instructions_note'] = 'callgrind timeout (120 s)'
            except Exception as e:
                rec['instructions'] = None
                rec['icount_error'] = type(e).__name__
    return rec


def task_work(task, tools, args, root, icount, mode):
    RT.CURRENT_TASK = task
    work = Path(tempfile.mkdtemp(prefix='rival-' + task + '-', dir=str(root)))
    case = RT.make_case(task, False, work)
    expected = reference_for(task, case, work)
    check = RT.make_check_cases(task, work)
    expected_cases = RT.reference_outputs(task, check, work)
    results = {}
    for tool in tools:
        print('%s: build %s' % (task, tool), file=sys.stderr, flush=True)
        try:
            if tool in ('ail', 'ail-py'):
                rec = build_ail(tool, task, work)
            elif tool == 'pypy':
                rec = build_pypy(task, work)
            else:
                rec = build_tool(tool, task, COMPARE / 'src' / task / SOURCE[tool], work)
        except Exception as e:
            rec = dict(tool=tool, build_ok=False, build_error='%s: %s' % (type(e).__name__, e), run_cmd=None)
        if rec.get('build_ok'):
            print('%s: run %s' % (task, tool), file=sys.stderr, flush=True)
            try:
                measure(rec, task, case, expected, check, expected_cases, work, icount, mode)
            except Exception as e:
                rec.update(status='error', correct=False, error='%s: %s' % (type(e).__name__, e))
        results[tool] = rec
        print('%-13s %-8s %s' % (tool, rec.get('status', 'build failed'),
              {k: rec.get(k) for k in ('compile_s', 'build_disk_kib', 'binary_bytes', 'wall_ms', 'rss_kib',
                                       'instructions', 'cases_public', 'cases_hidden', 'build_error')}),
              file=sys.stderr, flush=True)
    return task, dict(case=case['name'], input_bytes=case['input_bytes'], expected_exit=expected['returncode'],
                      results=results)


# ---------------------------------------------------------------- safety probes

def safety_probe(tool, probe, root):
    if tool in ('ail', 'ail-py'):
        # A safety probe is a plain .py file, so both AIL arms build it the same way.
        fresh, env = RT.fresh_dir(root, 'ail-safety-%s' % probe.stem)
        out = fresh / 'prog'
        p = run([PY, '-B', str(AIL), 'compile', str(probe), '-o', str(out), '--syntax', 'python'], fresh, env)
        if p.returncode != 0 or not out.is_file():
            return dict(build_ok=False, build_error=first_error(p.stderr or p.stdout))
        return dict(build_ok=True, run_cmd=[str(out)], standalone=True)
    elif tool == 'pypy':
        # the interpreter compiles nothing: the probe runs as-is, exactly like the CPython reference
        return dict(build_ok=PYPY.is_file(), build_error='' if PYPY.is_file() else 'pypy not found',
                    run_cmd=[str(PYPY), '-B', str(probe)], standalone=False, interpreter=True)
    else:
        rec = build_tool(tool, 'safety-' + probe.stem, probe, root, probe=True)
        return rec


def classify(rc, out, ref_rc, ref_out):
    if rc < 0:
        return 'crash (signal %d)' % (-rc)
    if rc == ref_rc and out == ref_out:
        return 'same as CPython'
    if rc == 0:
        return 'silently wrong output'
    # "Stops loudly" is the documented rule: a non-zero exit that reproduces a non-empty CPython
    # stdout prefix.  Empty stdout never counts, even when CPython's stdout is empty too: the exit
    # status differs, so it is a different partial answer and must stay visible.
    if out and ref_out.startswith(out):
        return 'stops loudly'
    return 'stops loudly (stdout differs)'


def run_safety(tools, root, jobs):
    probes = sorted((HERE / 'safety').glob('*.py'))
    refs = {}
    for probe in probes:
        p = subprocess.run([PY, '-B', str(probe)], stdin=subprocess.DEVNULL, capture_output=True, timeout=120)
        refs[probe.stem] = (p.returncode, p.stdout)
    out = {}
    for tool in tools:
        out[tool] = {}
        for probe in probes:
            rec = safety_probe(tool, probe, root)
            if not rec.get('build_ok'):
                out[tool][probe.stem] = dict(build_ok=False, result='build refused', error=rec.get('build_error'))
                continue
            try:
                p = subprocess.run(rec['run_cmd'], stdin=subprocess.DEVNULL, capture_output=True, timeout=120)
            except subprocess.TimeoutExpired:
                out[tool][probe.stem] = dict(build_ok=True, result='timeout')
                continue
            ref_rc, ref_out = refs[probe.stem]
            out[tool][probe.stem] = dict(build_ok=True, result=classify(p.returncode, p.stdout, ref_rc, ref_out),
                                         exit=p.returncode, bytes_out=len(p.stdout), ref_exit=ref_rc)
        print('safety %s done' % tool, file=sys.stderr, flush=True)
    return out


# ---------------------------------------------------------------- report

METRICS = [('wall_ms', 'wall ms'), ('instructions', 'instructions'), ('rss_kib', 'peak RSS KiB'),
           ('binary_bytes', 'artifact bytes'), ('compile_s', 'compile s'), ('build_disk_kib', 'build disk KiB')]
RIVALS = ['cython-main', 'cython-typed', 'nuitka', 'mypyc', 'codon', 'codon-main']


def usable(rec, key):
    if not rec or not rec.get('build_ok') or rec.get('correct') is not True:
        return None
    v = rec.get(key)
    return v if isinstance(v, (int, float)) and v > 0 else None


def correct_label(rec):
    if not rec or not rec.get('build_ok'):
        return 'build failed'
    if rec.get('status') == 'timeout':
        return 'timeout'
    if rec.get('status') == 'error':
        return 'error'
    pub, hid = rec.get('cases_public'), rec.get('cases_hidden')
    if pub is None:
        return 'not checked'
    wrong = (pub[1] - pub[0]) + (hid[1] - hid[0])
    if rec.get('correct') is False:
        wrong += 1
    total = pub[1] + hid[1] + 1
    return 'yes' if wrong == 0 else 'no (%d/%d wrong)' % (wrong, total)


def f_int(v):
    if v is None:
        return '-'
    for div, suf in ((1e9, 'G'), (1e6, 'M'), (1e3, 'k')):
        if v >= div:
            return '%.2f%s' % (v / div, suf)
    return '%d' % v


def geomean(xs):
    import math
    return math.exp(sum(math.log(x) for x in xs) / len(xs)) if xs else None


def summary(tasks, data):
    lines = []
    wins = {}
    rows = []
    for key, name in METRICS:
        ratios, nwin, n = [], 0, 0
        for task in tasks:
            res = data['tasks'][task]['results']
            a = usable(res.get('ail'), key)
            best = min((usable(res.get(r), key) for r in RIVALS if usable(res.get(r), key)), default=None)
            if a is None or best is None:
                continue
            ratios.append(a / best)
            n += 1
            if a <= best:
                nwin += 1
        g = geomean(ratios)
        wins[key] = (g, nwin, n)
        rows.append('| %s | %s | %d/%d | %s |' % (name, '%.2fx' % g if g else '-', nwin, n,
                                                   'AIL better' if g and g < 1 else 'AIL worse'))
    lines += ['| metric | AIL / best rival (geomean) | tasks AIL wins | verdict |', '|---|---|---|---|'] + rows
    return lines, wins


PY_ARMS = [('ail', 'AIL standalone (typed.py)'), ('ail-py', 'AIL standalone (main.py)')]


def against_pypy(tasks, data, key='wall_ms'):
    """AIL arm / PyPy per task, and the counts the headline needs: how many tasks each arm wins."""
    out = {}
    for arm, label in PY_ARMS:
        ratios, wins, ties, n = [], 0, 0, 0
        for task in tasks:
            res = data['tasks'][task]['results']
            a, p = usable(res.get(arm), key), usable(res.get('pypy'), key)
            if a is None or p is None:
                continue
            ratios.append(a / p)
            n += 1
            if a < p:
                wins += 1
            elif a == p:
                ties += 1
        out[arm] = dict(label=label, ratios=ratios, wins=wins, ties=ties, n=n, geomean=geomean(ratios),
                        faster_task=[t for t in tasks
                                     if usable(data['tasks'][t]['results'].get(arm), key)
                                     and usable(data['tasks'][t]['results'].get('pypy'), key)
                                     and usable(data['tasks'][t]['results'][arm], key)
                                     < usable(data['tasks'][t]['results']['pypy'], key)])
    return out


def pypy_lines(tasks, data):
    """The PyPy section: warm-up first, then the AIL/PyPy ratio per task and the headline."""
    L = []
    vs = against_pypy(tasks, data)
    warmed = [(t, data['tasks'][t]['results']['pypy']) for t in tasks
              if usable(data['tasks'][t]['results'].get('pypy'), 'wall_ms')]
    if not warmed:
        return ['## PyPy', '', 'No PyPy row was measured in this result file (`--tools` did not include '
                '`pypy`, or the interpreter was not found).', '']
    warm = {t: r.get('warm5_ms') for t, r in warmed if r.get('warm5_ms')}
    L.append('## PyPy')
    L.append('')
    L.append('PyPy runs `src/<task>/main.py` unchanged, in the interpreter, on the same perf input and against the '
             'same `reference.py`. Nothing is compiled, so `compile s` is `-` and the build-disk cell is the '
             'interpreter install, marked `interpreter` in `results.json` (`interpreter: true`). Wall time is the '
             'median of 5 fresh processes, like every other row. `warm5 ms` is the **5th run inside one '
             'process** (`pypy_warm.py`): the first run imports the program and runs its `main()`, runs 2-5 '
             'call that same `main()` again in the same module state with a fresh stdin over the same bytes '
             'and their own stdout, and every run is checked against the same reference.  That is what a '
             'long-lived process (a server, a notebook) pays, and it is the only way the JIT sees the same '
             'code twice -- re-executing the source builds new function objects and throws the traces away. '
             'A driver with no module-level `main` is re-executed instead and the row says `warm_mode`.  '
             '`warm/plain` is the ratio.')
    L.append('')
    if not warm:
        if warmed:
            L.append('The warm-up column is **not measured** in this result file: %d PyPy rows were measured '
                     'without `pypy_warm.py`.' % len(warmed))
        else:
            L.append('No PyPy row was measured in this result file.')
        L.append('')
    else:
        L.append('| task | PyPy plain ms | PyPy warm5 ms | warm / plain | mode | AIL standalone / PyPy | AIL (main.py) / PyPy |')
        L.append('|---|---|---|---|---|---|---|')
        for t, r in sorted(warmed):
            w = r.get('warm5_ms')
            res = data['tasks'][t]['results']
            cells = []
            for arm, _ in PY_ARMS:
                a, p = usable(res.get(arm), 'wall_ms'), usable(res.get('pypy'), 'wall_ms')
                cells.append('%.2fx' % (a / p) if a and p else '-')
            L.append('| %s | %.0f | %s | %s | %s | %s | %s |' % (
                t, r['wall_ms'], '%.0f' % w if w else '-',
                '%.2fx' % (w / r['wall_ms']) if w and r.get('wall_ms') else '-',
                r.get('warm_mode') or '-', cells[0], cells[1]))
        L.append('')
        diffs = [(t, r) for t, r in warmed if r.get('warm5_correct') is False]
        L.append('Every warm run produced the CPython reference output on %d of %d tasks; a mismatch would be a '
                 'PyPy result, not an AIL one.' % (len(warmed) - len(diffs), len(warmed))
                 if not diffs else 'Warm-run output differs from CPython on: %s (a PyPy result, listed and not '
                 'fixed in the sources).' % ', '.join(t for t, _ in diffs))
        L.append('')
        reexec = [t for t, r in warmed if r.get('warm_mode') == 're-exec']
        if reexec:
            L.append('On `%s` the driver has no module-level `main` to re-enter, so `warm5 ms` is a re-exec of '
                     'the source (`mode: re-exec`), not a warmed JIT: read those cells as a fresh process, not '
                     'as a steady-state number.' % '`, `'.join(sorted(reexec)))
            L.append('')
    L.append('**Headline.** ')
    for arm, v in vs.items():
        if v['geomean'] is None:
            L.append('The %s arm has no measured PyPy pair.' % v['label'])
            continue
        L.append('On wall time, **%s is faster than PyPy on %d of the %d tasks it can be compared on** '
                 '(geomean AIL/PyPy **%.2fx**, below 1.0 is faster)%s.'
                 % (v['label'], v['wins'], v['n'], v['geomean'],
                    ', on `%s`' % '`, `'.join(v['faster_task']) if v['faster_task'] else ''))
    return L


def render(result):
    data = result
    tasks = list(data['tasks'])
    L = []
    L.append('# AIL against the Python compilers (Nuitka, Cython, mypyc, Codon)')
    L.append('')
    L.append('Generated by `lab/compare_rival/run.py` on %s, commit `%s`.' % (data['date'], data['head']))
    L.append('')
    L.append('Every row compiles the same source AIL uses (`src/<task>/main.py` or `typed.py`); the CPython '
             "reference is the task's `reference.py`. `correct` means every public and hidden case plus the perf "
             'input matched. Wall time is the median of 5 runs of the perf input, peak RSS from `/usr/bin/time -v`, '
             'instructions from %s. Compile time and build disk are one cold build in a fresh directory. '
             '"single exe" is yes when the artifact is one file that runs without the source tree; mypyc needs the '
             'CPython interpreter and the `ail` module at run time.' % data['icount_method'])
    L.append('')
    s = data.get('settings', {})
    L.append('Measurement reductions from `lab/compare/run_task.py`, recorded in the `settings` object of '
             '`results.json`: %d cold build%s instead of %d; RUN_TIMEOUT %s s instead of 1500 s (a slower rival '
             'is "timeout", not a number); CASE_TIMEOUT %s s instead of 120 s; CALLGRIND_TIMEOUT %s s instead '
             'of 7000 s; instructions skipped when wall > %s s; and a %s s per-tool case budget.  So most '
             'instruction cells are "-" (59 of the 70 rows; 37 of the 48 builds that succeeded) and the '
             'instruction verdict has n=1.  Restoring the reference timeouts requires re-measuring every task.'
             % (s.get('build_runs', 1), '' if s.get('build_runs', 1) == 1 else 's', 3,
                s.get('run_timeout_s', 180), s.get('case_timeout_s', 30), s.get('callgrind_timeout_s', 120),
                s.get('callgrind_max_wall_ms', 4000) / 1000, s.get('case_budget_s', 240)))
    L.append('')
    L.append('| tool | version |')
    L.append('|---|---|')
    for k, v in data['tools'].items():
        L.append('| %s | %s |' % (k, v))
    L.append('')
    runs = data.get('tool_runs') or {}
    if runs:
        # Two runs can be in one table (--base): say which, so a reader never compares timings across
        # machines without knowing it.
        L.append('Where each column was measured (`tool_runs` in `results.json`): %s.'
                 % '; '.join('%s %s on commit `%s`' % (tool, r.get('date'), r.get('head'))
                             for tool, r in sorted(runs.items())))
        L.append('')
    L.append('## Per task')
    L.append('')
    has_pypy = any((data['tasks'][t]['results'].get('pypy') or {}).get('build_ok') for t in tasks)
    L.append('| task | tool | correct | wall ms | ' + ('warm5 ms | ' if has_pypy else '') +
             'instructions | peak RSS MiB | artifact KiB | compile s | build disk MiB | single exe |')
    L.append('|---|---|---|---|' + ('---|' if has_pypy else '') + '---|---|---|---|---|---|---|')
    for task in tasks:
        res = data['tasks'][task]['results']
        for tool in ALL_TOOLS:
            r = res.get(tool)
            if r is None:
                continue
            name = tool + (' (patched)' if r.get('patched') else '')
            if not r.get('build_ok'):
                L.append('| %s | %s | build refused | - | ' % (task, name) + ('- | ' if has_pypy else '') +
                         '- | - | - | - | - | - | - |')
                continue
            rss = '%.1f' % (r['rss_kib'] / 1024) if r.get('rss_kib') else '-'
            art = '%.0f' % (r['binary_bytes'] / 1024) if r.get('binary_bytes') else '-'
            disk = '%.1f' % (r['build_disk_kib'] / 1024) if r.get('build_disk_kib') is not None else '-'
            if r.get('interpreter'):
                disk += ' (interp)'
            warm_cell = (('%.0f' % r['warm5_ms']) if r.get('warm5_ms') else '-') + ' | ' if has_pypy else ''
            L.append('| %s | %s | %s | %s | %s%s | %s | %s | %s | %s | %s |' % (
                task, name, correct_label(r),
                '%.0f' % r['wall_ms'] if r.get('wall_ms') is not None else '-', warm_cell,
                f_int(r.get('instructions')), rss, art,
                '%.2f' % r['compile_s'] if r.get('compile_s') is not None else '-', disk,
                'yes' if r.get('standalone') else 'no'))
    L.append('')
    L.extend(pypy_lines(tasks, data))
    L.append('')
    L.append('## Summary: AIL against the best rival')
    L.append('')
    sl, wins = summary(tasks, data)
    L.extend(sl)
    L.append('')
    L.append('A ratio below 1.00 means AIL is better (every metric is lower-is-better).')
    L.append('')
    # five-line verdict
    LABEL = {'wall_ms': 'wall time', 'instructions': 'instructions', 'rss_kib': 'peak RSS',
             'binary_bytes': 'artifact size', 'compile_s': 'compile time', 'build_disk_kib': 'build disk'}

    def verdict(key):
        g, nwin, n = wins[key]
        if g is None:
            return '%s: not measured.' % LABEL[key]
        if g < 1:
            return '%s: AIL is %.2fx better than the best rival (%d/%d tasks).' % (LABEL[key], 1 / g, nwin, n)
        return '%s: AIL is %.2fx worse than the best rival (%d/%d tasks).' % (LABEL[key], g, nwin, n)

    L.append('**Five-line verdict**')
    L.append('')
    L.append('- ' + verdict('wall_ms'))
    L.append('- ' + verdict('instructions'))
    L.append('- ' + verdict('rss_kib'))
    L.append('- ' + verdict('binary_bytes'))
    L.append('- ' + verdict('compile_s'))
    L.append('')
    L.append('## Refusals and patches')
    L.append('')
    L.append('| tool | task | result | first error line |')
    L.append('|---|---|---|---|')
    any_ref = False
    for task in tasks:
        for tool in ALL_TOOLS:
            r = data['tasks'][task]['results'].get(tool) or {}
            if r.get('build_ok'):
                continue
            any_ref = True
            if toolchain_missing(data, tool):
                outcome, error = 'not installed here', '%s not installed on this runner' % TOOLCHAIN[tool]
            else:
                outcome = 'patched' if r.get('patched') else 'refused'
                error = r.get('build_error') or 'build failed with no error output'
            L.append('| %s | %s | %s | `%s` |' % (tool, task, outcome,
                                                   (error or '').replace('|', '/')[:220]))
    if not any_ref:
        L.append('| - | - | none | - |')
    L.append('')
    L.append('## Safety: what each tool does when the program is wrong')
    L.append('')
    L.append('| tool | ' + ' | '.join(data['safety_probes']) + ' | silently wrong |')
    L.append('|---|' + '---|' * len(data['safety_probes']) + '---|')
    for tool in data['safety']:
        cells = []
        silent = 0
        for probe in data['safety_probes']:
            r = data['safety'][tool].get(probe, {})
            res = r.get('result', 'not run')
            cells.append(res)
            if res == 'silently wrong output':
                silent += 1
        L.append('| %s | %s | %d/%d |' % (tool, ' | '.join(cells), silent, len(data['safety_probes'])))
    L.append('')
    L.append('Probes: `safety/overflow.py` (int64 wrap), `safety/index.py` (index out of range), '
             '`safety/negindex.py` (negative index past the start), `safety/divzero.py` (division by zero), '
             '`safety/recursion.py` (100000 levels). "stops loudly" means a non-zero exit that reproduces a '
             'non-empty CPython stdout prefix; "stops loudly (stdout differs)" means a non-zero exit whose '
             'stdout does not match that prefix (often buffered away); "silently wrong" is a zero exit with a '
             'different answer; a negative exit is a crash by signal.')
    L.append('')
    return '\n'.join(L) + '\n'


# A rival tool is built by the toolchain named here; `versions()` reports that toolchain's version,
# and a version starting with `missing` means this runner cannot build the tool at all.
TOOLCHAIN = {'cython-main': 'cython', 'cython-typed': 'cython', 'nuitka': 'nuitka',
             'mypyc': 'mypy', 'codon': 'codon', 'codon-main': 'codon'}


def toolchain_missing(result, tool):
    """True when the result file says this tool's toolchain is not installed here."""
    key = TOOLCHAIN.get(tool)
    return bool(key) and str((result.get('tools') or {}).get(key, '')).startswith('missing')


def layer_base(result, base, tools, head):
    """Lay the rows `result` measured now over `base`, and record which run made each column.

    The base keeps every tool it had, the rows measured now replace theirs, and `tool_runs` says
    which run produced each column -- a reader must be able to tell a number measured here from one
    measured on CI.  A row for a tool whose toolchain this run reports as `missing` is not a
    measurement: the base row is kept (and marked `source: base`) rather than overwritten by the
    failure the absent toolchain produced.  A refusal from an installed tool does replace the base
    row -- that is a result.
    """
    merged_tasks = dict(base.get('tasks') or {})
    from_this_run = set()
    for task, rec in result['tasks'].items():
        old = merged_tasks.get(task) or {}
        rows = dict(old.get('results') or {})
        for tool, new in (rec.get('results') or {}).items():
            if tool in rows and not new.get('build_ok') and toolchain_missing(result, tool):
                continue                      # not measured here; keep the base row
            rows[tool] = new
            from_this_run.add(tool)
        merged_tasks[task] = dict(old, **dict(rec, results=rows))
    result['tasks'] = merged_tasks
    old_runs = base.get('tool_runs') or {}
    result['tool_runs'] = {}
    for tool in sorted({t for task in result['tasks'].values() for t in task['results']}):
        if tool in from_this_run and tool in tools:
            result['tool_runs'][tool] = dict(date=result['date'], head=head, source='this run')
        else:
            result['tool_runs'][tool] = dict(old_runs.get(tool) or
                                             dict(date=base.get('date'), head=base.get('head')),
                                             source='base')
    for k, v in (base.get('tools') or {}).items():
        if str(result['tools'].get(k, '')).startswith('missing'):
            result['tools'][k] = v
    return result


def warm_only(src_json, out_json):
    """Re-measure only the PyPy warm5 column (the harness changed, not the programs)."""
    data = json.loads(Path(src_json).read_text())
    tasks = [t for t in data['tasks'] if (data['tasks'][t]['results'].get('pypy') or {}).get('build_ok')]
    root = Path(tempfile.mkdtemp(prefix='compare-rival-warm-'))
    for task in tasks:
        RT.CURRENT_TASK = task
        work = Path(tempfile.mkdtemp(prefix='warm-' + task + '-', dir=str(root)))
        try:
            case = RT.make_case(task, False, work)
            expected = reference_for(task, case, work)
            rec = data['tasks'][task]['results']['pypy']
            rec.update(warm5(rec, case, expected, work))
            print('%-14s warm5=%s mode=%s' % (task, rec.get('warm5_ms'), rec.get('warm_mode')), file=sys.stderr,
                  flush=True)
        except Exception as e:
            data['tasks'][task]['results']['pypy']['warm5_note'] = '%s: %s' % (type(e).__name__, e)
            print('%-14s warm5 failed: %s' % (task, e), file=sys.stderr, flush=True)
        finally:
            shutil.rmtree(work, ignore_errors=True)
    Path(out_json).write_text(json.dumps(data, indent=1) + '\n', encoding='utf8')
    (HERE / 'RESULTS.md').write_text(render(data), encoding='utf8')
    print('wrote %s' % out_json, file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--tasks', default=' '.join(TASKS))
    ap.add_argument('--tools', default=','.join(ALL_TOOLS))
    ap.add_argument('--out', default=str(HERE / 'results.json'))
    ap.add_argument('--safety', action='store_true', help='only run the safety probes')
    ap.add_argument('--no-safety', action='store_true')
    ap.add_argument('--icount', choices=['auto', 'perf', 'callgrind', 'none'], default='auto')
    ap.add_argument('--jobs', type=int, default=1)
    ap.add_argument('--merge', metavar='DIR', help='merge the result-*.json files in DIR into --out')
    ap.add_argument('--base', metavar='JSON',
                    help='start from this results.json and add/replace only the tools measured now; the '
                         'result records which tools came from which run in `tool_runs`.  Use it when a '
                         'toolchain is not installed here (the CI job measures everything).')
    ap.add_argument('--warm-only', metavar='JSON',
                    help='re-measure only the PyPy warm5 column from this results.json (the harness '
                         'changed, not the program) and write the result to --out.  Nothing else is run.')
    args = ap.parse_args()
    if args.warm_only:
        warm_only(args.warm_only, args.out)
        return
    if args.merge:
        # actions/download-artifact with `pattern:` writes each artifact under results/<artifact>/,
        # so the parts are nested; rglob also finds a flat layout.
        parts = [json.loads(f.read_text()) for f in sorted(Path(args.merge).rglob('*.json'))]
        merged = None
        for part in parts:
            if part.get('tasks'):
                # Metadata (instruction method, versions, date) must come from a measured task part:
                # the safety part has the same tools but icount_method 'none', and sorts in the middle.
                merged = {k: v for k, v in part.items() if k not in ('tasks', 'safety')}
                merged['tasks'], merged['safety'] = {}, {}
                merged.setdefault('safety_probes', [])
                break
        for part in parts:
            if merged is None:
                break
            merged['tasks'].update(part.get('tasks') or {})
            merged['safety'].update(part.get('safety') or {})
            for p in part.get('safety_probes') or []:
                if p not in merged['safety_probes']:
                    merged['safety_probes'].append(p)
        if merged is None or not merged.get('tasks'):
            print('no result-*.json parts with tasks under %s; nothing merged' % args.merge, file=sys.stderr)
            raise SystemExit(2)
        Path(args.out).write_text(json.dumps(merged, indent=1) + '\n', encoding='utf8')
        (HERE / 'RESULTS.md').write_text(render(merged), encoding='utf8')
        print('merged %d tasks into %s' % (len(merged['tasks']), args.out), file=sys.stderr)
        return
    tasks = [t for t in args.tasks.split() if t]
    tools = [t for t in args.tools.split(',') if t]
    for t in tasks:
        if t not in TASKS:
            ap.error('unknown task: %s' % t)
    for t in tools:
        if t not in ALL_TOOLS:
            ap.error('unknown tool: %s' % t)

    root = Path(tempfile.mkdtemp(prefix='compare-rival-'))
    icount = RT.icount_tool(root) if args.icount in ('auto', 'perf') else None
    if args.icount == 'auto':
        mode = 'perf' if icount else ('callgrind' if shutil.which('valgrind') else 'none')
    elif args.icount == 'perf' and not icount:
        mode = 'none'
    else:
        mode = args.icount
    print('instruction counter: %s' % mode, file=sys.stderr, flush=True)
    head = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=str(REPO), capture_output=True, text=True).stdout.strip()
    result = dict(date=time.strftime('%Y-%m-%d', time.gmtime()), head=head, icount_method=mode,
                  runner=dict(os=os.uname().release, cpus=os.cpu_count(), image=os.environ.get('ImageVersion', '')),
                  settings=dict(SETTINGS), tools=versions(), pins=read_pins(), tasks={},
                  safety_probes=[p.stem for p in sorted((HERE / 'safety').glob('*.py'))], safety={})
    result['tools']['ail'] = 'checkout ' + head

    base = None
    if args.base:
        base = json.loads(Path(args.base).read_text())
        result['base'] = dict(file=str(args.base), date=base.get('date'), head=base.get('head'),
                              tools=sorted({t for task in (base.get('tasks') or {}).values()
                                            for t in task['results']}))

    if not args.safety:
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = [pool.submit(task_work, t, tools, args, root, icount, mode) for t in tasks]
            for fut in futures:
                task, rec = fut.result()
                result['tasks'][task] = rec
                Path(args.out).write_text(json.dumps(result, indent=1) + '\n', encoding='utf8')   # partial survives a timeout
        result['tasks'] = {t: result['tasks'][t] for t in tasks if t in result['tasks']}

    if base:
        # Layer the rows measured now over the base result.
        layer_base(result, base, tools, head)

    if not args.no_safety:
        print('safety probes', file=sys.stderr, flush=True)
        result['safety'] = run_safety(tools if not args.safety else tools, root, args.jobs)
        if base and base.get('safety'):
            merged_safety = {k: dict(v) for k, v in base['safety'].items()}
            merged_safety.update(result['safety'])
            result['safety'] = merged_safety
            for p in base.get('safety_probes') or []:
                if p not in result['safety_probes']:
                    result['safety_probes'].append(p)
            result['safety_probes'] = sorted(result['safety_probes'])

    Path(args.out).write_text(json.dumps(result, indent=1) + '\n', encoding='utf8')
    if result['tasks']:
        (HERE / 'RESULTS.md').write_text(render(result), encoding='utf8')
    print('wrote %s' % args.out, file=sys.stderr)


if __name__ == '__main__':
    main()
