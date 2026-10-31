#!/usr/bin/env python3
"""compare-lab, one task: build the same program in every language and measure it.

    python3 lab/compare/run_task.py --task tree_fold --out result-tree_fold.json
    python3 lab/compare/run_task.py --task chain_relax --smoke --langs ail,c,python   # tiny input, plumbing check

Languages (columns): ail      AIL compiling the task's .ail source (brace syntax) from this checkout
                     ail-py   AIL compiling the CPython source (`compile --syntax python`) from this checkout
                     c        gcc -O2          rust  rustc -C opt-level=3 (cargo --release level)
                     go       go build         nim   nim c -d:release
                     python   CPython 3.12, the program is the .py source run by the interpreter

Per language: build ok, compile time (median of 3 cold builds), build disk (KiB added under a fresh build dir
that also holds the language's caches, `du -sk`), binary bytes (as built, and stripped), stdout and exit code
checked against the task's CPython reference.py on the perf input and on every public and hidden case of the task's
gen.py (`cases_public` / `cases_hidden` in the JSON), peak RSS (/usr/bin/time -v, median of the timed runs), wall
time (median of 5 timed runs of the perf input, minimum also kept), instructions (see icount_method) and, for the
two AIL columns, whether the program built on the typed path (`compile --strict` accepts it) or only on the
general path (plus the note the default build prints when it falls back). Nothing here is a verdict:
lab/compare/merge.py builds the tables and the per-task scorecard.

Instruction counts: perf_event_open through tools/icount.c when the runner exposes a hardware counter, else
valgrind --tool=callgrind (Ir). The method used is recorded as icount_method in the JSON.
"""
import argparse, importlib.util, json, os, random, re, shutil, statistics, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AIL = REPO / 'AIL_CURRENT' / 'ail_chatgpt.py'
LANGS = ['ail', 'ail-py', 'c', 'rust', 'go', 'nim', 'python']
SOURCE = {'ail': 'main.ail', 'ail-py': 'main.py', 'c': 'main.c', 'rust': 'main.rs', 'go': 'main.go',
          'nim': 'main.nim', 'python': 'main.py'}
BUILD_RUNS = 3
WALL_RUNS = 5
CASE_TIMEOUT = 120
RUN_TIMEOUT = 1500
CALLGRIND_TIMEOUT = 7000


def tail(data, n=700):
    return data.decode('utf8', 'replace')[-n:] if isinstance(data, bytes) else str(data)[-n:]


def du_kib(path):
    words = subprocess.run(['du', '-sk', str(path)], capture_output=True, text=True).stdout.split()   # unreadable subdirs: partial sum
    return int(words[0]) if words else 0


# These two programs need big ints by design (a `1 << 200` sentinel, a 64-bit modular LCG): since the int64 default (2026-10-31)
# their ail-py build asks for the exact ints explicitly, so the comparison still measures them (on the general path).
EXACT_INT_TASKS = ('rail_transfer', 'chain_relax')
CURRENT_TASK = None


def build_cmd(lang, src, out, strict=False):
    if lang in ('ail', 'ail-py'):
        cmd = [sys.executable, '-B', str(AIL), 'compile', str(src), '-o', str(out)]
        if lang == 'ail-py':
            cmd[5:5] = ['--syntax', 'python'] + (['--exact-int'] if CURRENT_TASK in EXACT_INT_TASKS else [])
        if strict:
            cmd.insert(5, '--strict')
        return cmd
    if lang == 'c':
        return ['gcc', '-O2', '-std=c11', '-o', str(out), str(src), '-lm']
    if lang == 'rust':
        return ['rustc', '-C', 'opt-level=3', '--edition=2021', '-o', str(out), str(src)]
    if lang == 'go':
        return ['go', 'build', '-o', str(out), str(src)]
    if lang == 'nim':
        return ['nim', 'c', '-d:release', '--hints:off', '--verbosity:0', '--nimcache:' + str(out.parent.parent / 'nimcache'),
                '-o:' + str(out), str(src)]
    raise ValueError(lang)


def fresh_dir(root, label):
    """A build dir with its own cache, TMPDIR and per-language cache dirs, so that everything the build leaves is inside."""
    fresh = root / label
    for sub in ('cache', 'tmp', 'target', 'gocache', 'gopath', 'xdg', 'nimcache', 'out'):
        (fresh / sub).mkdir(parents=True)
    env = dict(os.environ, AIL_CACHE=str(fresh / 'cache'), TMPDIR=str(fresh / 'tmp'), CARGO_TARGET_DIR=str(fresh / 'target'),
               GOCACHE=str(fresh / 'gocache'), GOPATH=str(fresh / 'gopath'), GOTMPDIR=str(fresh / 'tmp'),
               GOTOOLCHAIN='local', GOFLAGS='-modcacherw', XDG_CACHE_HOME=str(fresh / 'xdg'))
    env.pop('AIL_NO_CACHE', None)
    # The AIL compiler is Python: its own bytecode (written beside the sources on the first run, like a pip install ships it) is
    # part of the installed tool, not of the build cache, so it is not cleaned between builds. The strict probe build runs first.
    env.pop('PYTHONDONTWRITEBYTECODE', None)
    env.pop('AIL_STRICT', None)
    return fresh, env


def build(lang, src, root, label, strict=False):
    fresh, env = fresh_dir(root, label)
    empty = du_kib(fresh)
    out = fresh / 'out' / 'prog'
    start = time.perf_counter()
    p = subprocess.run(build_cmd(lang, src, out, strict), cwd=fresh, env=env, capture_output=True, timeout=1800)
    elapsed = time.perf_counter() - start
    return dict(ok=p.returncode == 0 and out.is_file(), seconds=elapsed, disk_kib=max(du_kib(fresh) - empty, 0),
                binary=out, stderr=p.stderr, stdout=p.stdout, dir=fresh)


def why_not_typed(stderr):
    lines = stderr.decode('utf8', 'replace').splitlines()
    for i, line in enumerate(lines):
        if 'why not typed' in line:
            where = lines[i - 1].strip() if i else ''
            return (where + ' | ' + line.strip())[:300]
    return (lines[0] if lines else '')[:300]


def stripped_bytes(binary, work):
    copy = work / 'stripped'
    try:
        subprocess.run(['strip', '-o', str(copy), str(binary)], check=True, capture_output=True)
        return copy.stat().st_size
    except Exception:
        return None
    finally:
        copy.unlink(missing_ok=True)


def build_language(lang, task_src, root):
    """Builds BUILD_RUNS cold builds; returns the record and the command that runs the result."""
    src = task_src / SOURCE[lang]
    rec = dict(lang=lang, source_bytes=src.stat().st_size)
    if lang == 'python':
        rec.update(build_ok=True, interpreted=True)
        return rec, [sys.executable, '-B', str(src)]
    if lang.startswith('ail'):
        probe = build(lang, src, root, 'probe-' + lang, strict=True)
        rec['path'] = 'typed' if probe['ok'] else 'general'
        if not probe['ok']:
            rec['why_not_typed'] = why_not_typed(probe['stderr'])
        shutil.rmtree(probe['dir'], ignore_errors=True)
    runs = []
    for i in range(BUILD_RUNS):
        b = build(lang, src, root, '%s-build%d' % (lang, i))
        runs.append(b)
        if not b['ok']:
            break
    rec['build_ok'] = all(b['ok'] for b in runs)
    if lang.startswith('ail'):
        notes = [l.strip() for l in runs[0]['stderr'].decode('utf8', 'replace').splitlines() if 'general path' in l]
        rec['fallback_notes'] = len(notes)
        if notes:
            rec['fallback_note'] = notes[0][:300]
            rec['path'] = 'general'      # the default build said so, whatever the strict probe returned
    if not rec['build_ok']:
        rec['build_error'] = tail(runs[-1]['stderr'] or runs[-1]['stdout'])
        if lang.startswith('ail'):
            rec['path'] = 'refused' if rec.get('path') == 'general' else rec.get('path')
        return rec, None
    rec['compile_s_runs'] = [round(b['seconds'], 3) for b in runs]
    rec['compile_s'] = round(statistics.median(b['seconds'] for b in runs), 3)
    rec['build_disk_kib'] = runs[0]['disk_kib']
    binary = runs[0]['binary']
    rec['binary_bytes'] = binary.stat().st_size
    rec['stripped_bytes'] = stripped_bytes(binary, root)
    for b in runs[1:]:
        shutil.rmtree(b['dir'], ignore_errors=True)
    return rec, [str(binary)]


def load_task(name):
    spec = importlib.util.spec_from_file_location('gen_' + name, HERE / 'tasks' / name / 'gen.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_case(name, smoke, work):
    """The task's performance input (or the first public example with --smoke), same seed as the llm-compare runs."""
    module = load_task(name)
    public, hidden, perf = module.cases(random.Random('%s-20261012' % name))
    case_name, data, args = public[0] if smoke else perf
    path = work / 'input.bin'
    path.write_bytes(data)
    return dict(name=case_name, stdin=bool(getattr(module, 'STDIN', False)), path=path,
                args=[a.replace('{input}', str(path)) for a in args], input_bytes=len(data))


def make_check_cases(name, work):
    """Public and hidden cases of the task: [(kind, case name, case dict)]. The perf case is not among them."""
    module = load_task(name)
    public, hidden, _perf = module.cases(random.Random('%s-20261012' % name))
    out = []
    for kind, group in (('public', public), ('hidden', hidden)):
        for k, (case_name, data, args) in enumerate(group):
            path = work / 'cases' / ('%s-%d.bin' % (kind, k))
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(data)
            out.append((kind, case_name, dict(name=case_name, stdin=bool(getattr(module, 'STDIN', False)), path=path,
                                              args=[a.replace('{input}', str(path)) for a in args], input_bytes=len(data))))
    return out


def reference_outputs(name, check, work):
    """CPython reference.py output and exit code for every check case."""
    expected = {}
    for kind, case_name, case in check:
        out = work / 'ref.out'
        p = exec_prog([], [sys.executable, '-B', str(HERE / 'tasks' / name / 'reference.py')], case, out, CASE_TIMEOUT)
        expected[(kind, case_name)] = (p.returncode, out.read_bytes())
    return expected


def check_cases(lang, cmd, check, expected, work):
    """Run the program on every public and hidden case; stdout and exit code must equal the reference's."""
    tally = {'public': [0, 0], 'hidden': [0, 0]}
    failed = []
    for kind, case_name, case in check:
        out = work / ('chk-' + lang)
        ok = False
        try:
            p = exec_prog([], cmd, case, out, CASE_TIMEOUT)
            ok = (p.returncode, out.read_bytes()) == expected[(kind, case_name)]
        except subprocess.TimeoutExpired:
            pass
        tally[kind][1] += 1
        if ok:
            tally[kind][0] += 1
        else:
            failed.append('%s/%s' % (kind, case_name))
    out.unlink(missing_ok=True)
    return dict(cases_public=tally['public'], cases_hidden=tally['hidden'], cases_failed=failed[:20])


def exec_prog(prefix, cmd, case, stdout_path, timeout):
    stdin = open(case['path'], 'rb') if case['stdin'] else subprocess.DEVNULL
    try:
        with open(stdout_path, 'wb') as out:
            return subprocess.run([*prefix, *cmd, *case['args']], stdin=stdin, stdout=out, stderr=subprocess.PIPE, timeout=timeout)
    finally:
        if case['stdin']:
            stdin.close()


def same_file(a, b):
    if Path(a).stat().st_size != Path(b).stat().st_size:
        return False
    with open(a, 'rb') as fa, open(b, 'rb') as fb:
        while True:
            x, y = fa.read(1 << 20), fb.read(1 << 20)
            if x != y:
                return False
            if not x:
                return True


def rss_from(time_file):
    m = re.search(r'Maximum resident set size \(kbytes\):\s*(\d+)', Path(time_file).read_text(errors='replace'))
    return int(m.group(1)) if m else None


def run_pass(lang, cmd, case, expected, work, smoke):
    """Correctness, peak RSS and wall time. Returns a dict."""
    out, tfile = work / ('out-' + lang), work / ('time-' + lang)
    walls, rss, correct, exits = [], [], True, set()
    runs = 1 if smoke else WALL_RUNS
    i = 0
    while i < runs:
        start = time.perf_counter()
        try:
            p = exec_prog(['/usr/bin/time', '-v', '-o', str(tfile), '--'], cmd, case, out, RUN_TIMEOUT)
        except subprocess.TimeoutExpired:
            return dict(status='timeout', correct=False)
        elapsed = time.perf_counter() - start
        exits.add(p.returncode)
        walls.append(elapsed)
        value = rss_from(tfile)
        if value:
            rss.append(value)
        if p.returncode != expected['returncode'] or not same_file(out, expected['stdout']):
            correct = False
        if i == 0 and elapsed > 60:
            runs = min(runs, 2)     # long programs: two runs are enough
        elif i == 0 and elapsed > 15:
            runs = min(runs, 3)
        i += 1
    out.unlink(missing_ok=True)
    result = dict(status='ok' if correct else 'MISMATCH', correct=correct, exit_codes=sorted(exits),
                  wall_ms=round(statistics.median(walls) * 1000, 1), wall_min_ms=round(min(walls) * 1000, 1), wall_runs_ms=[round(w * 1000, 1) for w in walls],
                  rss_kib=int(statistics.median(rss)) if rss else None)
    if not correct:
        result['expected_exit'] = expected['returncode']
    return result


def icount_tool(work):
    """Build tools/icount.c and report whether a hardware instruction counter is readable here."""
    exe = work / 'icount'
    try:
        subprocess.run(['cc', '-O2', '-w', '-include', 'signal.h', '-include', 'stdlib.h', '-o', str(exe), str(REPO / 'tools/icount.c')],
                       check=True, capture_output=True)
        p = subprocess.run([str(exe), '/bin/true'], capture_output=True, timeout=30)
        if p.returncode == 0 and p.stdout.strip().isdigit() and int(p.stdout) > 0:
            return exe
    except Exception:
        pass
    return None


def count_instructions(lang, cmd, case, work, icount, mode):
    if mode == 'perf':
        p = exec_prog([str(icount)], cmd, case, work / ('ic-' + lang), RUN_TIMEOUT)
        text = (work / ('ic-' + lang)).read_text(errors='replace').split()
        (work / ('ic-' + lang)).unlink(missing_ok=True)
        return int(text[-1]) if p.returncode == 0 and text and text[-1].isdigit() else None
    cg = work / ('cg-' + lang)
    prefix = ['valgrind', '--tool=callgrind', '--cache-sim=no', '--callgrind-out-file=' + str(cg)]
    try:
        p = exec_prog(prefix, cmd, case, work / ('ic-' + lang), CALLGRIND_TIMEOUT)
    except subprocess.TimeoutExpired:
        return None
    finally:
        cg.unlink(missing_ok=True)
        (work / ('ic-' + lang)).unlink(missing_ok=True)
    m = re.search(rb'Collected\s*:\s*(\d+)', p.stderr)
    return int(m.group(1)) if m else None


def read_pins():
    """lab/compare/toolchains.env: the toolchain versions this lab expects (checked by check_tools.py in the workflow)."""
    pins = {}
    try:
        for line in (HERE / 'toolchains.env').read_text().splitlines():
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                pins[k.strip()] = v.strip()
    except OSError:
        pass
    return pins


def tool_versions():
    def first(cmd):
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            return ((p.stdout or p.stderr).strip().splitlines() or [''])[0]
        except Exception as e:
            return 'missing (%s)' % type(e).__name__
    return dict(gcc=first(['gcc', '--version']), rustc=first(['rustc', '--version']), go=first(['go', 'version']),
                nim=first(['nim', '--version']), python=sys.version.split()[0], valgrind=first(['valgrind', '--version']))


def toolchain_kib():
    def du(*paths):
        paths = [p for p in dict.fromkeys(map(str, paths)) if p and os.path.exists(p)]
        return sum(du_kib(p) for p in paths) if paths else None
    sizes = {}
    gcc = shutil.which('gcc')
    if gcc:
        prog = lambda n: os.path.realpath(subprocess.run([gcc, '-print-prog-name=' + n], capture_output=True, text=True).stdout.strip())
        sizes['c'] = du(os.path.realpath(gcc), os.path.dirname(prog('cc1')), prog('as'), prog('ld'))
    if shutil.which('rustc'):
        sizes['rust'] = du(subprocess.run(['rustc', '--print', 'sysroot'], capture_output=True, text=True).stdout.strip())
    if shutil.which('go'):
        sizes['go'] = du(subprocess.run(['go', 'env', 'GOROOT'], capture_output=True, text=True).stdout.strip())
    if shutil.which('nim'):
        sizes['nim'] = du(Path(os.path.realpath(shutil.which('nim'))).parent.parent)
    if sys.base_prefix in ('/usr', '/'):   # system python: its binary and stdlib dir
        sizes['python'] = du(os.path.realpath(sys.executable), '/usr/lib/python%d.%d' % sys.version_info[:2])
    else:
        sizes['python'] = du(sys.base_prefix)
    sizes['ail'] = du(REPO / 'AIL_CURRENT')   # the compiler tree; it also needs the C toolchain and python
    return sizes


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--task', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--langs', default=','.join(LANGS))
    parser.add_argument('--smoke', action='store_true', help='tiny input, one timed run: plumbing check only')
    parser.add_argument('--icount', choices=['auto', 'perf', 'callgrind', 'none'], default='auto')
    parser.add_argument('--no-cases', action='store_true', help='skip the public and hidden cases (perf input only)')
    parser.add_argument('--jobs', type=int, default=3, help='parallel callgrind runs')
    args = parser.parse_args()
    langs = [l for l in args.langs.split(',') if l]
    global CURRENT_TASK
    CURRENT_TASK = args.task
    task_src = HERE / 'src' / args.task
    head = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=REPO, capture_output=True, text=True).stdout.strip()
    with tempfile.TemporaryDirectory(prefix='compare-' + args.task + '-') as tmp:
        work = Path(tmp)
        case = make_case(args.task, args.smoke, work)
        # the oracle: the task's CPython reference
        ref_out = work / 'expected.out'
        stdin = open(case['path'], 'rb') if case['stdin'] else subprocess.DEVNULL
        with open(ref_out, 'wb') as f:
            ref = subprocess.run([sys.executable, str(HERE / 'tasks' / args.task / 'reference.py'), *case['args']], stdin=stdin,
                                 stdout=f, stderr=subprocess.PIPE, timeout=3 * RUN_TIMEOUT)
        expected = dict(returncode=ref.returncode, stdout=ref_out)
        print('%s: input %d bytes, expected %d bytes, exit %d' % (args.task, case['input_bytes'], ref_out.stat().st_size, ref.returncode),
              file=sys.stderr, flush=True)
        check = make_check_cases(args.task, work) if not args.no_cases else []
        cases_expected = reference_outputs(args.task, check, work) if check else {}
        print('%d public+hidden cases' % len(check), file=sys.stderr, flush=True)
        results, commands = {}, {}
        for lang in langs:
            print('build', lang, file=sys.stderr, flush=True)
            try:
                results[lang], commands[lang] = build_language(lang, task_src, work)
            except Exception as e:     # a missing toolchain must not lose the other columns
                results[lang], commands[lang] = dict(lang=lang, build_ok=False, build_error='%s: %s' % (type(e).__name__, e)), None
        for lang in langs:
            if commands[lang]:
                print('run', lang, file=sys.stderr, flush=True)
                results[lang].update(run_pass(lang, commands[lang], case, expected, work, args.smoke))
                if check:
                    results[lang].update(check_cases(lang, commands[lang], check, cases_expected, work))
        mode = args.icount
        icount = icount_tool(work) if mode in ('auto', 'perf') else None
        if mode == 'auto':
            mode = 'perf' if icount else ('callgrind' if shutil.which('valgrind') else 'none')
        elif mode == 'perf' and not icount:
            mode = 'none'
        if mode != 'none':
            todo = [l for l in langs if commands[l] and results[l].get('status') in ('ok', 'MISMATCH')]
            print('instructions via', mode, file=sys.stderr, flush=True)
            with ThreadPoolExecutor(max_workers=1 if mode == 'perf' else args.jobs) as pool:
                futures = {l: pool.submit(count_instructions, l, commands[l], case, work, icount, mode) for l in todo}
                for l, fut in futures.items():
                    try:
                        results[l]['instructions'] = fut.result()
                    except Exception as e:
                        results[l]['instructions'] = None
                        results[l]['icount_error'] = type(e).__name__
        report = dict(task=args.task, case=case['name'], smoke=args.smoke, head=head, input_bytes=case['input_bytes'],
                      expected_bytes=ref_out.stat().st_size, expected_exit=ref.returncode, icount_method=mode,
                      runner=dict(os=os.uname().release, cpus=os.cpu_count(), image=os.environ.get('ImageVersion', '')), tools=tool_versions(),
                      pins=read_pins(),
                      toolchain_kib=toolchain_kib(), results=results)
        Path(args.out).write_text(json.dumps(report, indent=1) + '\n', encoding='utf8')
        for lang in langs:
            r = results[lang]
            print('%-7s %-9s %s' % (lang, r.get('status', 'build failed' if not r.get('build_ok') else '-'),
                  {k: r.get(k) for k in ('path', 'compile_s', 'build_disk_kib', 'binary_bytes', 'rss_kib', 'wall_ms', 'instructions',
                                         'cases_public', 'cases_hidden')}),
                  file=sys.stderr)


if __name__ == '__main__':
    main()
