#!/usr/bin/env python3
"""vibe1: the vibe-coding benchmark.

For every (task, language, seed) an AI writes one program from the task's spec.md and a short
language note; the harness builds it, runs the task's public cases, sends the compiler or runtime
error back for a fix, and finally runs the hidden cases. It records, per attempt, whether the
program was correct, how many rounds it took, whether a hidden case was silently wrong or stoppe
loudly, and the wall time of the loop.

    python3 lab/vibe/run.py --tasks berth_sim --langs python,rust,ail --seeds 1   # dry run
    python3 lab/vibe/run.py --langs python --seeds 3 --minutes 100

Languages: python = CPython 3.12 on the file the AI wrote; rust = rustc -O on the file it wrote;
ail = AIL (`compile --syntax python`) on the same plain Python the AI wrote for the ail prompt.

The model is called non-interactively through an installed CLI (Command Code `cmd` or OpenCode
`opencode`); the same model and settings are used for every language. No key is read or written
by this script: `cmd` takes COMMAND_CODE_API_KEY from the environment, as the runner already
sets it.
"""
import argparse
import importlib.util
import json
import os
import random
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
LAB2 = REPO / 'lab' / 'vibe2'
AIL = REPO / 'AIL_CURRENT' / 'ail_chatgpt.py'
RESULTS = HERE / 'results.json'
PROGRAMS = HERE / 'programs'
AIL_LANGS = ('ail', 'ail-strict', 'ail-new')
LANGS = ('python', 'rust', 'ail', 'ail-strict', 'ail-new')
EXT = {'python': '.py', 'rust': '.rs', 'ail': '.py', 'ail-strict': '.py', 'ail-new': '.nw'}
CODE_TAG = {'python': 'python', 'rust': 'rust', 'ail': 'python', 'ail-strict': 'python', 'ail-new': 'ail'}
LANG_NAME = {'python': 'Python 3.12', 'rust': 'Rust 2021', 'ail': 'AIL (a Python-syntax language)',
             'ail-strict': 'AIL (a Python-syntax language; strict-path rules in the note)',
             'ail-new': 'AIL-N (the typed surface in the note)'}

CASE_TIMEOUT = 90
BUILD_TIMEOUT = 300
MAX_ROUNDS = 5
MAX_JOBS = 2

LANG_NOTE = {
    'python': ('Python 3.12, standard library only. The program is run as `python3 main.py [args...]`; '
               'it reads standard input and writes standard output.'),
    'rust': ('Rust 2021, standard library only, no crates. The program is built with '
             '`rustc -O --edition=2021 main.rs` and run as `./main [args...]`; it reads standard '
             'input and writes standard output.'),
    'ail': None,   # filled from AIL_FOR_AI.md
    'ail-strict': None,   # filled from lab/vibe2/STRICT_SPEC.md
    'ail-new': None,      # filled from lab/vibe2/NEW_SURFACE.md
}


# --------------------------------------------------------------------------------------------
# tasks and cases

def task_list():
    """(name, directory) for the ten compare-lab tasks plus compare_cand/csv_rollup when present."""
    out = []
    base = REPO / 'lab' / 'compare' / 'tasks'
    for p in sorted(base.iterdir()):
        if (p / 'gen.py').is_file() and (p / 'spec.md').is_file():
            out.append((p.name, p))
    cand = REPO / 'lab' / 'compare_cand' / 'tasks' / 'csv_rollup'
    if (cand / 'gen.py').is_file() and (cand / 'spec.md').is_file():
        out.append(('csv_rollup', cand))
    return out


def load_gen(task_dir):
    spec = importlib.util.spec_from_file_location('vibe_gen_' + task_dir.name, task_dir / 'gen.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_reference(ref, args, stdin_bytes):
    cmd = [sys.executable, '-B', str(ref), *args]
    kw = dict(input=stdin_bytes, capture_output=True, timeout=CASE_TIMEOUT) if stdin_bytes is not None \
        else dict(stdin=subprocess.DEVNULL, capture_output=True, timeout=CASE_TIMEOUT)
    p = subprocess.run(cmd, **kw)
    return {'returncode': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr}


def prepare_cases(task_name, task_dir, work):
    """Public and hidden cases with the CPython reference output. Nothing here is shown to the AI."""
    mod = load_gen(task_dir)
    public, hidden, _perf = mod.cases(random.Random('%s-20261012' % task_name))
    stdin_task = bool(getattr(mod, 'STDIN', False))
    cases = []
    for kind, group in (('public', public), ('hidden', hidden)):
        for k, (case_name, data, args) in enumerate(group):
            path = work / 'cases' / ('%s-%d.bin' % (kind, k))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            call_args = [a.replace('{input}', str(path)) for a in args]
            expected = run_reference(task_dir / 'reference.py', call_args, data if stdin_task else None)
            cases.append(dict(kind=kind, name=case_name, path=str(path), args=call_args,
                              stdin_data=data if stdin_task else None, expected=expected))
    return cases


def run_program(cmd, case, timeout=CASE_TIMEOUT):
    kw = dict(input=case['stdin_data'], capture_output=True, timeout=timeout) \
        if case['stdin_data'] is not None else dict(stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout)
    t0 = time.perf_counter()
    try:
        p = subprocess.run([*cmd, *case['args']], **kw)
        return dict(ok=True, returncode=p.returncode, stdout=p.stdout, stderr=p.stderr,
                    seconds=time.perf_counter() - t0)
    except subprocess.TimeoutExpired:
        return dict(ok=False, returncode=None, stdout=b'', stderr=b'(timeout)', seconds=time.perf_counter() - t0)
    except OSError as e:
        return dict(ok=False, returncode=None, stdout=b'', stderr=str(e).encode(), seconds=time.perf_counter() - t0)


def same(actual, expected):
    return actual is not None and actual['returncode'] == expected['returncode'] and actual['stdout'] == expected['stdout']


# --------------------------------------------------------------------------------------------
# build

ANSI = re.compile(rb'\x1b\[[0-9;]*[A-Za-z]')


def tail(data, n=1600):
    if isinstance(data, bytes):
        data = ANSI.sub(b'', data).decode('utf8', 'replace')
    return data[-n:]


def compile_env(work):
    env = dict(os.environ)
    env['AIL_NO_CACHE'] = '1'
    env.pop('AIL_QUIET_FALLBACK', None)
    env.pop('AIL_STRICT', None)
    return env


def build_program(lang, src, work, exe, line_map=None):
    """Compile; python needs no build. Returns ok, seconds, run command, stderr, typed probe."""
    if lang == 'python':
        return dict(ok=True, seconds=0.0, cmd=[sys.executable, '-B', str(src)], stderr='', stdout='', typed=None)
    if lang == 'rust':
        cmd = ['rustc', '-O', '--edition=2021', '-o', str(exe), str(src)]
    else:
        cmd = [sys.executable, '-B', str(AIL), 'compile', str(src), '--syntax', 'python', '-o', str(exe)]
    exe.unlink(missing_ok=True)   # AIL refuses to overwrite an existing -o output; a fix round rebuilds
    t0 = time.perf_counter()
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=BUILD_TIMEOUT, env=compile_env(work))
        rc, out, err = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        rc, out, err = 124, b'', b'(build timeout)'
    except OSError as e:
        rc, out, err = 127, b'', str(e).encode()
    if rc != 0 and line_map:
        err = remap_errors(err, line_map)
    rec = dict(ok=rc == 0 and exe.is_file(), seconds=time.perf_counter() - t0, cmd=[str(exe)],
               stderr=tail(err), stdout=tail(out, 400), typed=None)
    if lang in AIL_LANGS and rec['ok']:
        strict = work / (exe.name + '-strict')
        try:
            sp = subprocess.run([sys.executable, '-B', str(AIL), 'compile', str(src), '--syntax', 'python',
                                 '--strict', '-o', str(strict)], capture_output=True,
                                timeout=BUILD_TIMEOUT, env=compile_env(work))
            rec['typed'] = sp.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            rec['typed'] = False
        finally:
            strict.unlink(missing_ok=True)
    return rec


LINE_RE = re.compile(rb'(main\.py):(\d+)(:\d+)?')


def remap_errors(err, line_map):
    """Point generated-Python line numbers back at the AIL-N source lines."""
    def sub(m):
        try:
            n = int(m.group(2))
        except ValueError:
            return m.group(0)
        ai = line_map[n - 1] if 1 <= n <= len(line_map) else 0
        return b'main.ail:%d' % (ai or n) + (m.group(3) or b'')
    return LINE_RE.sub(sub, err)


def translate_new(code):
    """AIL-N -> AIL Python. Returns (translated code, line map) or raises TranslateError."""
    if str(LAB2) not in sys.path:
        sys.path.insert(0, str(LAB2))
    from translate import translate
    tr = translate(code)
    return tr['code'], tr['line_map']


def ail_path(rec):
    if not rec['ok']:
        return 'refused'
    if 'built on the general path' in (rec.get('stderr') or ''):
        return 'general'
    return 'typed' if rec.get('typed') else 'general'


# --------------------------------------------------------------------------------------------
# model CLI

class ModelFatal(RuntimeError):
    pass


class ModelTimeout(RuntimeError):
    pass


FATAL_PAT = re.compile(r'(?i)usage limit|quota|rate.?limit|\b429\b|unauthori[sz]ed|forbidden|'
                       r'not logged in|please run /login|insufficient|credit')


def run_cli(cmd, input_bytes, workdir, timeout, out_path, err_path):
    """Run a CLI with its output in files (a child that keeps a pipe open cannot hang us) and kill
    the whole process group on timeout. Returns (returncode, stdout text, stderr text)."""
    with open(out_path, 'wb') as fo, open(err_path, 'wb') as fe:
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE if input_bytes is not None else subprocess.DEVNULL,
                             stdout=fo, stderr=fe, cwd=str(workdir), start_new_session=True)
        try:
            p.communicate(input=input_bytes, timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(p.pid), signal.SIGKILL)
            except OSError:
                p.kill()
            try:
                p.wait(timeout=30)
            except subprocess.TimeoutExpired:
                pass
            raise ModelTimeout('model call timed out after %ds' % timeout)
        rc = p.returncode
    return rc, out_path.read_text(encoding='utf8', errors='replace'), err_path.read_text(encoding='utf8', errors='replace')


def find_cmd():
    env = os.environ.get('VIBE_CMD_BIN')
    if env and Path(env).is_file():
        return env
    found = shutil.which('cmd')
    if found:
        return found
    for base in (os.environ.get('AGENT_TMP'), os.environ.get('RUNNER_TEMP'), os.path.expanduser('~')):
        if not base:
            continue
        for p in (Path(base) / 'cc' / 'node_modules' / '.bin' / 'cmd',
                  Path(base) / 'command-code' / 'node_modules' / '.bin' / 'cmd',
                  Path(base) / 'opt' / 'command-code' / 'node_modules' / '.bin' / 'cmd'):
            if p.is_file():
                return str(p)
    return None


def find_opencode():
    env = os.environ.get('VIBE_OPENCODE_BIN')
    if env and Path(env).is_file():
        return env
    found = shutil.which('opencode')
    if found:
        return found
    p = Path.home() / 'opt' / 'opencode' / 'opencode'
    return str(p) if p.is_file() else None


class Model:
    def __init__(self, kind, name, timeout, effort=None):
        self.kind, self.name, self.timeout, self.effort = kind, name, timeout, effort
        self.bin = find_cmd() if kind == 'cmd' else find_opencode()
        if not self.bin:
            raise SystemExit('no model CLI found for %r (set --cli or VIBE_CMD_BIN)' % kind)
        if kind == 'cmd' and not os.environ.get('COMMAND_CODE_API_KEY'):
            raise SystemExit('cmd needs COMMAND_CODE_API_KEY in the environment (the runner sets it)')

    def call(self, prompt, workdir):
        if self.kind == 'cmd':
            return self._cmd(prompt, workdir)
        return self._opencode(prompt, workdir)

    def _cmd(self, prompt, workdir):
        cmd = [self.bin, '-p', '--model', self.name, '--yolo', '-t', '--max-turns', '1',
               '--output-format', 'json']
        if self.effort:
            cmd += ['--effort', self.effort]
        rc, raw, err = run_cli(cmd, prompt.encode(), workdir, self.timeout,
                               workdir / 'model-out.jsonl', workdir / 'model-err.txt')
        final, tokens = None, 0
        for line in raw.splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if isinstance(e, dict):
                if e.get('type') == 'result' or 'finalText' in e:
                    final = e.get('finalText') or final
                    usage = e.get('usage') or {}
                    if isinstance(usage, dict):
                        tokens += int(usage.get('outputTokens') or 0)
        if not final:
            blob = raw[-2000:] + err[-1500:]
            if FATAL_PAT.search(blob):
                raise ModelFatal(blob.strip()[-400:])
            return '', tokens
        return final, tokens

    def _opencode(self, prompt, workdir):
        pf = workdir / 'prompt.txt'
        pf.write_text(prompt)
        cmd = [self.bin, 'run', '--format', 'json', '--dir', str(workdir), '-m', self.name,
               '-f', str(pf), 'Answer the attached prompt. Do not edit files or run commands.']
        rc, raw, err = run_cli(cmd, None, workdir, self.timeout,
                               workdir / 'model-out.jsonl', workdir / 'model-err.txt')
        texts, tokens = [], 0
        for line in raw.splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if not isinstance(e, dict):
                continue
            part = e.get('part') or {}
            if part.get('type') == 'text' and part.get('text'):
                texts.append(part['text'])
            tok = part.get('tokens') or {}
            if isinstance(tok, dict):
                tokens += int(tok.get('output') or 0)
        if not texts:
            blob = raw[-1000:] + err[-1500:]
            if FATAL_PAT.search(blob):
                raise ModelFatal(blob.strip()[-400:])
            return '', tokens
        return texts[-1], tokens


FENCE = re.compile(r'```[ \t]*([A-Za-z0-9_+.-]*)[ \t]*\n(.*?)```', re.S)


def extract_code(reply):
    """The largest fenced block; if there is none, the reply itself."""
    blocks = [m.group(2) for m in FENCE.finditer(reply or '')]
    if blocks:
        code = max(blocks, key=len)
    else:
        code = reply or ''
    return code.strip('\n') + '\n'


# --------------------------------------------------------------------------------------------
# prompting

def language_note(lang):
    if lang == 'ail':
        return (HERE / 'AIL_FOR_AI.md').read_text()
    if lang == 'ail-strict':
        return (LAB2 / 'STRICT_SPEC.md').read_text()
    if lang == 'ail-new':
        return (LAB2 / 'NEW_SURFACE.md').read_text()
    return LANG_NOTE[lang]


def base_prompt(task_name, task_dir, lang):
    spec = (task_dir / 'spec.md').read_text()
    return f"""You are writing one program for the task below.

Task: {task_name}
Language: {LANG_NAME[lang]}

Write a complete, correct solution in a single file. The hidden tests check the edge cases
in the specification. Keep your reasoning short and write the solution directly. Do not use
tools, do not edit files and do not run commands: reply with the file contents only.

--- SPECIFICATION ---
{spec}
--- END SPECIFICATION ---

Language note:
{language_note(lang).strip()}

Reply with the complete file contents in one fenced code block tagged `{CODE_TAG[lang]}`
and nothing else.
"""


def fix_prompt(task_name, task_dir, lang, code, error):
    head = base_prompt(task_name, task_dir, lang).rsplit('Reply with the complete file contents', 1)[0]
    return f"""{head}
Your previous file was:

```{CODE_TAG[lang]}
{code}
```

The build or the public tests failed:

```
{error}
```

Fix the program. Reply with the complete corrected file in one fenced code block tagged
`{CODE_TAG[lang]}` and nothing else.
"""


def fmt_bytes(data, limit=800):
    b = data[:limit]
    try:
        s = b.decode('utf8')
        printable = all(32 <= ord(c) < 127 or c in '\n\t' for c in s)
        body = s if printable else repr(b)
    except UnicodeDecodeError:
        body = repr(b)
    return body + ('...' if len(data) > limit else '')


def failure_feedback(case, actual):
    if not actual['ok']:
        return 'case %r: %s\n%s' % (case['name'], 'timed out' if actual['returncode'] is None else 'failed to run',
                                    fmt_bytes(actual['stderr'], 500))
    exp = case['expected']
    parts = ['public case %r failed.' % case['name'],
             'program exit %s, expected %s' % (actual['returncode'], exp['returncode'])]
    if actual['stdout'] != exp['stdout']:
        parts.append('program stdout:\n' + fmt_bytes(actual['stdout']))
        parts.append('expected stdout:\n' + fmt_bytes(exp['stdout']))
    if actual['stderr']:
        parts.append('program stderr:\n' + fmt_bytes(actual['stderr'], 500))
    return '\n'.join(parts)


# --------------------------------------------------------------------------------------------
# AIL error table


def compiler_messages(stderr):
    """Normalized compiler error/note lines from a build's stderr."""
    msgs = []
    for line in (stderr or '').splitlines():
        s = line.strip()
        if not s:
            continue
        if re.search(r'not in the subset|error:|Error|refus|out of range|unsupported', s):
            msgs.append(('error', norm_message(s)))
        elif s.startswith('note:') or 'general path' in s:
            msgs.append(('note', norm_message(s)))
    return msgs


def norm_message(line):
    line = re.sub(r'^note:\s*', '', line)
    line = re.sub(r'^(?:/\S*/)?main\.(?:py|rs):\d+(?::\d+)?:\s*', '', line)
    line = re.sub(r'^\S+?\.(?:py|rs):\d+(?::\d+)?:\s*', '', line)
    line = re.sub(r'\s*\(line \d+\)', '', line)
    line = re.sub(r'/\S*?main\.(?:py|rs):\d+(?::\d+)?:', 'main.py:<line>:', line)
    return line[:220]


def ail_error_table(records):
    counts = {}
    for rec in records:
        rounds = rec.get('rounds') or []
        for i, rnd in enumerate(rounds):
            for kind, msg in rnd.get('compiler') or []:
                key = (kind, msg)
                slot = counts.setdefault(key, {'kind': kind, 'message': msg, 'occurrences': 0, 'fixed_next': 0})
                slot['occurrences'] += 1
                nxt = rounds[i + 1] if i + 1 < len(rounds) else None
                if kind in ('error', 'surface') and nxt is not None and nxt.get('build_ok'):
                    slot['fixed_next'] += 1
    rows = sorted(counts.values(), key=lambda r: (-r['occurrences'], r['message']))
    for r in rows:
        r['fixed_rate'] = round(r['fixed_next'] / r['occurrences'], 3) if r['occurrences'] else 0.0
    return rows[:10]


# --------------------------------------------------------------------------------------------
# one attempt

def evaluate(task_name, task_dir, lang, seed, cases, model, rounds_limit):
    work = Path(tempfile.mkdtemp(prefix='vibe-%s-%s-%d-' % (task_name, lang, seed)))
    src = work / ('main' + EXT[lang])
    exe = work / ('prog' + ('.exe' if os.name == 'nt' else ''))
    public = [c for c in cases if c['kind'] == 'public']
    hidden = [c for c in cases if c['kind'] == 'hidden']
    prompt = base_prompt(task_name, task_dir, lang)
    rounds, code = [], ''
    loop_seconds = 0.0
    final_run_seconds = 0.0
    public_pass = False
    build_rec = None
    try:
        for n in range(1, rounds_limit + 1):
            try:
                reply, tokens = model.call(prompt, work)
            except ModelTimeout as e:
                # A call the model did not finish in --call-timeout ends this attempt (gave up); it must
                # not stop the whole benchmark, and retrying a runaway generation only burns the budget.
                rounds.append(dict(round=n, prompt_chars=len(prompt), reply_chars=0, reply_tokens=0,
                                   build_ok=False, build_seconds=0.0, build_error=str(e), compiler=[],
                                   public_passed=False, public_failed=[], run_seconds=0.0, error_sent=str(e)))
                break
            if not (reply or '').strip():
                err = 'the model returned no text'
                rounds.append(dict(round=n, prompt_chars=len(prompt), reply_chars=0, reply_tokens=tokens,
                                   build_ok=False, build_seconds=0.0, build_error=err, compiler=[],
                                   public_passed=False, public_failed=[], run_seconds=0.0, error_sent=err))
                prompt = fix_prompt(task_name, task_dir, lang, code, err)
                continue
            code = extract_code(reply)
            src.write_text(code)
            surface_error = ''
            line_map = None
            build_src = src
            if lang == 'ail-new':
                try:
                    tcode, line_map = translate_new(code)
                    build_src = work / 'main.py'
                    build_src.write_text(tcode)
                except Exception as e:       # TranslateError from lab/vibe2/translate.py
                    lno = getattr(e, 'line', 0)
                    surface_error = 'line %d: %s' % (lno, getattr(e, 'message', str(e)))
                    build_src = None
                    build_rec = dict(ok=False, seconds=0.0, cmd=[], typed=None,
                                     stderr='surface error at ' + surface_error, stdout='')
            if build_src is not None:
                build_rec = build_program(lang, build_src, work, exe, line_map)
            loop_seconds += build_rec['seconds']
            msgs = compiler_messages(build_rec['stderr']) if lang in AIL_LANGS else []
            if surface_error:
                msgs.append(('surface', surface_error))
            rnd = dict(round=n, prompt_chars=len(prompt), reply_chars=len(reply or ''),
                       reply_tokens=tokens, build_ok=build_rec['ok'],
                       build_seconds=round(build_rec['seconds'], 3),
                       build_error=(build_rec['stderr'] or '')[:600] if not build_rec['ok'] else '',
                       compiler=msgs, surface_error=bool(surface_error),
                       public_passed=False, public_failed=[], run_seconds=0.0)
            if not build_rec['ok']:
                if surface_error:
                    rnd['error_sent'] = ('AIL-N surface error:\n' + surface_error)[:1500]
                else:
                    rnd['error_sent'] = ('compiler error:\n' + (build_rec['stderr'] or '(no message)'))[:1500]
                rounds.append(rnd)
                prompt = fix_prompt(task_name, task_dir, lang, code, rnd['error_sent'])
                continue
            failures = []
            run_s = 0.0
            for case in public:
                actual = run_program(build_rec['cmd'], case)
                run_s += actual['seconds']
                loop_seconds += actual['seconds']
                if not same(actual, case['expected']):
                    failures.append((case, actual))
            rnd['run_seconds'] = round(run_s, 3)
            rnd['public_passed'] = not failures
            rnd['public_failed'] = [c['name'] for c, _ in failures]
            public_pass = not failures
            rounds.append(rnd)
            if public_pass:
                final_run_seconds = run_s
                break
            feedback = '\n\n'.join(failure_feedback(c, a) for c, a in failures[:3])
            rnd['error_sent'] = feedback[:1500]
            prompt = fix_prompt(task_name, task_dir, lang, code, rnd['error_sent'])
        # hidden cases only for a program that passed everything the AI was allowed to see
        hidden_rows, silent, loud, other = [], 0, 0, 0
        correct = False
        if public_pass and build_rec and build_rec['ok']:
            correct = True
            for case in hidden:
                actual = run_program(build_rec['cmd'], case)
                exp = case['expected']
                ok = same(actual, case['expected'])
                status = 'pass' if ok else 'wrong'
                if not ok:
                    correct = False
                    if actual['returncode'] is not None and actual['returncode'] == exp['returncode']:
                        silent += 1
                        status = 'silent_wrong'
                    elif actual['returncode'] not in (None, 0) and exp['returncode'] == 0:
                        loud += 1
                        status = 'loud_stop'
                    else:
                        other += 1
                        status = 'wrong_exit'
                hidden_rows.append(dict(name=case['name'], status=status,
                                        exit=actual['returncode'], expected_exit=exp['returncode']))
        path = ail_path(build_rec) if lang in AIL_LANGS and build_rec else None
        surface_rounds = sum(1 for r in rounds if r.get('surface_error'))
        rec = dict(task=task_name, lang=lang, seed=seed, public_pass=public_pass, correct=correct,
                   rounds_used=len(rounds), gave_up=not public_pass,
                   silent_wrong=silent, loud_stop=loud, other_wrong=other, hidden_total=len(hidden),
                   hidden=hidden_rows, loop_seconds=round(loop_seconds, 3),
                   final_run_seconds=round(final_run_seconds, 3),
                   reply_tokens=sum(r.get('reply_tokens') or 0 for r in rounds),
                   surface_error_rounds=surface_rounds,
                   path=path, final_build_ok=bool(build_rec and build_rec['ok']), rounds=rounds)
        if code:
            dst = PROGRAMS / task_name / ('%s-%d%s' % (lang, seed, EXT[lang]))
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(code)
            try:
                rec['program'] = str(dst.relative_to(HERE))
            except ValueError:
                rec['program'] = str(dst)
        return rec
    finally:
        shutil.rmtree(work, ignore_errors=True)


# --------------------------------------------------------------------------------------------
# results file

class Store:
    def __init__(self, path, meta):
        self.path, self.meta, self.lock = path, meta, threading.Lock()
        self.rows = {}
        if path.is_file():
            try:
                old = json.loads(path.read_text())
                old_meta = old.get('meta') or {}
                for r in old.get('results', []):
                    self.rows[(r['task'], r['lang'], r['seed'],
                               r.get('model') or old_meta.get('model'))] = r
                for k in ('started', 'harness'):
                    if k in old_meta and k not in self.meta:
                        self.meta[k] = old_meta[k]
            except (OSError, ValueError):
                pass

    def put(self, rec):
        with self.lock:
            rec['model'] = self.meta.get('model')
            self.rows[(rec['task'], rec['lang'], rec['seed'], rec['model'])] = rec
            self.write()

    def write(self):
        self.meta['updated'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        rows = sorted(self.rows.values(), key=lambda r: (r['task'], r['lang'], r['seed']))
        every = list(self.rows.values())
        if every:
            # Meta must describe the rows actually in the file, also after a resumed partial run.
            self.meta['seeds'] = sorted({r['seed'] for r in every})
            self.meta['languages'] = [l for l in LANGS if any(r['lang'] == l for r in every)]
            self.meta['tasks'] = sorted({r['task'] for r in every})
        data = dict(meta=self.meta, results=rows)
        data['summary'] = summarize(every)
        models = sorted({r.get('model') or '' for r in every})
        data['ail_errors'] = {
            m: ail_error_table([r for r in every
                                if r['lang'] in AIL_LANGS and (r.get('model') or '') == m])
            for m in models}
        tmp = self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, indent=1) + '\n')
        tmp.replace(self.path)


def summarize(rows):
    """Per model, then per language: n, correct, public pass, gave up, silent wrong, loud stops,
    rounds and seconds. Rows from different models never merge."""
    out = {}
    for model in sorted({r.get('model') or '' for r in rows}):
        out[model] = _summarize_langs([r for r in rows if (r.get('model') or '') == model])
    return out


def _summarize_langs(rows):
    out = {}
    for lang in LANGS:
        rs = [r for r in rows if r['lang'] == lang]
        if not rs:
            continue
        passed = [r for r in rs if r['public_pass']]
        rounds = sorted(r['rounds_used'] for r in passed)
        med = rounds[len(rounds) // 2] if rounds else None
        if len(rounds) % 2 == 0 and rounds:
            med = (rounds[len(rounds) // 2 - 1] + rounds[len(rounds) // 2]) / 2
        out[lang] = dict(n=len(rs), correct=sum(1 for r in rs if r['correct']),
                         public_pass=len(passed), gave_up=sum(1 for r in rs if r['gave_up']),
                         silent_wrong=sum(r['silent_wrong'] for r in rs),
                         loud_stop=sum(r['loud_stop'] for r in rs),
                         other_wrong=sum(r['other_wrong'] for r in rs),
                         rounds_median=med,
                         reply_tokens=sum(r.get('reply_tokens') or 0 for r in rs),
                         tokens_per_correct=(round(sum(r.get('reply_tokens') or 0 for r in rs) /
                                                   sum(1 for r in rs if r['correct']), 1)
                                             if any(r['correct'] for r in rs) else None),
                         surface_error_rounds=sum(r.get('surface_error_rounds') or 0 for r in rs),
                         loop_seconds=round(sum(r['loop_seconds'] for r in rs), 2),
                         final_run_seconds=round(sum(r['final_run_seconds'] for r in rs), 3),
                         paths={p: sum(1 for r in rs if r.get('path') == p)
                                for p in ('typed', 'general', 'refused')} if lang in AIL_LANGS else None)
    return out


# --------------------------------------------------------------------------------------------
# main

def parse_seeds(text):
    if ',' in text:
        return [int(x) for x in text.split(',') if x]
    return list(range(max(1, int(text))))


def main():
    global PROGRAMS
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--tasks', help='comma-separated task names (default: all)')
    ap.add_argument('--langs', default=','.join(LANGS))
    ap.add_argument('--seeds', default='3', help='count (3) or list (0,1,2)')
    ap.add_argument('--rounds', type=int, default=MAX_ROUNDS, help='max model attempts per attempt (max 5)')
    ap.add_argument('--jobs', type=int, default=MAX_JOBS)
    ap.add_argument('--minutes', type=float, default=0, help='stop starting new attempts after this many minutes')
    ap.add_argument('--cli', choices=['cmd', 'opencode'], default=None)
    ap.add_argument('--model', default='deepseek-v4.1-flash')
    ap.add_argument('--effort', default=None, help='cmd reasoning effort (low/medium/high)')
    ap.add_argument('--call-timeout', type=int, default=300)
    ap.add_argument('--out', default=str(RESULTS))
    ap.add_argument('--programs', default=str(PROGRAMS), help='directory for the final program of each attempt')
    ap.add_argument('--only', help='restrict to task:lang:seed (debugging)')
    args = ap.parse_args()

    langs = [l for l in args.langs.split(',') if l]
    for l in langs:
        if l not in LANGS:
            raise SystemExit('unknown language %r' % l)
    PROGRAMS = Path(args.programs)
    tasks = task_list()
    if args.tasks:
        want = set(args.tasks.split(','))
        tasks = [t for t in tasks if t[0] in want]
    seeds = parse_seeds(args.seeds)
    jobs = max(1, min(args.jobs, MAX_JOBS))
    kind = args.cli or ('cmd' if find_cmd() and os.environ.get('COMMAND_CODE_API_KEY') else 'opencode')
    model = Model(kind, args.model, args.call_timeout, args.effort)

    meta = dict(started=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), harness='lab/vibe/run.py',
                model=args.model, cli=kind, effort=args.effort, rounds=args.rounds, seeds=seeds, languages=langs,
                tasks=[t[0] for t in tasks], jobs=jobs, case_timeout=CASE_TIMEOUT,
                mode='python = CPython 3.12; rust = rustc -O --edition=2021; ail = AIL compile --syntax '
                     'python; ail-strict = AIL with lab/vibe2/STRICT_SPEC.md; ail-new = lab/vibe2/'
                     'NEW_SURFACE.md translated to AIL Python by lab/vibe2/translate.py',
                seed_note='seed = independent repeated attempt; the CLI exposes no sampling seed')
    store = Store(Path(args.out), meta)

    # references are per task, shared by every language and seed
    refdir = Path(tempfile.mkdtemp(prefix='vibe-ref-'))
    case_cache = {}
    for name, tdir in tasks:
        case_cache[name] = prepare_cases(name, tdir, refdir / name)
        print('[cases] %s: %d public, %d hidden' % (name, sum(c['kind'] == 'public' for c in case_cache[name]),
                                                    sum(c['kind'] == 'hidden' for c in case_cache[name])), flush=True)

    combos = []
    # Seed-outer order: a run cut short still has complete columns for the low seeds.
    for seed in seeds:
        for lang in langs:
            for name, tdir in tasks:
                key = '%s:%s:%d' % (name, lang, seed)
                if args.only and key != args.only:
                    continue
                if (name, lang, seed, args.model) in store.rows:
                    continue
                combos.append((name, tdir, lang, seed))

    deadline = time.time() + args.minutes * 60 if args.minutes else None
    fatal = None
    done = 0
    lock = threading.Lock()

    def one(combo):
        nonlocal fatal
        name, tdir, lang, seed = combo
        try:
            return evaluate(name, tdir, lang, seed, case_cache[name], model, args.rounds)
        except ModelFatal as e:
            with lock:
                if fatal is None:
                    fatal = str(e)
            return None
        except ModelTimeout as e:
            return None

    from concurrent.futures import wait, FIRST_COMPLETED

    pending = {}
    queue = iter(combos)
    stopped = [False]

    def handle(fut, combo):
        nonlocal done
        if fut.cancelled():
            return
        try:
            rec = fut.result()
        except Exception as e:     # one bad attempt must not lose the rest
            print('[error] %s: %s' % (combo[0], e), flush=True)
            return
        if rec is None:
            if fatal:
                print('[fatal] %s' % fatal, flush=True)
                stopped[0] = True
            return
        store.put(rec)
        done += 1
        print('[%s %d] %s %s seed %d: %s rounds %d silent %d loud %d%s' % (
            time.strftime('%H:%M:%S', time.gmtime()), done, rec['task'], rec['lang'], rec['seed'],
            'correct' if rec['correct'] else ('gave up' if rec['gave_up'] else 'wrong'),
            rec['rounds_used'], rec['silent_wrong'], rec['loud_stop'],
            (' ' + rec['path']) if rec.get('path') else ''), flush=True)
        if fatal:
            stopped[0] = True

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        def pump():
            # Only keep `jobs` attempts in flight, so the wall-clock budget really stops new work.
            while not stopped[0] and len(pending) < jobs:
                try:
                    combo = next(queue)
                except StopIteration:
                    return
                if deadline and time.time() > deadline:
                    print('[budget] stop scheduling after %d attempts' % done, flush=True)
                    stopped[0] = True
                    return
                pending[pool.submit(one, combo)] = combo

        pump()
        while pending:
            finished, _ = wait(list(pending), return_when=FIRST_COMPLETED)
            for fut in finished:
                combo = pending.pop(fut)
                handle(fut, combo)
            if stopped[0]:
                for fut in list(pending):
                    fut.cancel()
            else:
                pump()

    shutil.rmtree(refdir, ignore_errors=True)
    store.meta['stopped_early'] = bool(fatal) or stopped[0]
    if fatal:
        store.meta['fatal'] = fatal
    store.meta['completed_attempts'] = done
    store.meta['scheduled_attempts'] = len(combos)
    store.write()
    s = summarize(list(store.rows.values()))
    print(json.dumps(s, indent=1))
    if fatal:
        raise SystemExit('model CLI stopped working: %s' % fatal)


if __name__ == '__main__':
    main()
