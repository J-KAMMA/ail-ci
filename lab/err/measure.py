#!/usr/bin/env python3
"""err1: ask a model to fix each trigger program from the compiler message alone.

    python3 lab/err/measure.py --messages lab/err/messages_original.json --out lab/err/fixrate_original.json
    python3 lab/err/measure.py --messages lab/err/messages_rewritten.json --out lab/err/fixrate_rewritten.json

The model call is exactly the one lab/vibe/run.py uses: `cmd` (Command Code) with
--model deepseek-v4.1-flash --effort low, JSON events, one turn, no tools. Five independent
replies per trigger. Fixed = the reply builds, its stdout/exit match CPython, and the target
message is gone.
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AIL = REPO / 'AIL_CURRENT' / 'ail_chatgpt.py'
TRIG = HERE / 'triggers'
MODEL = 'deepseek-v4.1-flash'
EFFORT = 'low'
TRIES = 5
FENCE = re.compile(r'```[ \t]*([A-Za-z0-9_+.-]*)[ \t]*\n(.*?)```', re.S)
ANSI = re.compile(rb'\x1b\[[0-9;]*[A-Za-z]')


def extract(reply):
    blocks = [m.group(2) for m in FENCE.finditer(reply or '')]
    code = max(blocks, key=len) if blocks else (reply or '')
    return code.strip('\n') + '\n'


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
                  Path(base) / 'command-code' / 'node_modules' / '.bin' / 'cmd'):
            if p.is_file():
                return str(p)
    return None


def call_model(prompt, work, timeout=300):
    """lab/vibe/run.py Model._cmd: one turn, JSON events, finalText from the result event."""
    cmd = [str(CMD), '-p', '--model', MODEL, '--yolo', '-t', '--max-turns', '1',
           '--output-format', 'json', '--effort', EFFORT]
    p = subprocess.run(cmd, input=prompt.encode(), capture_output=True, timeout=timeout,
                       cwd=str(work))
    final = None
    for line in (p.stdout or b'').decode('utf8', 'replace').splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if isinstance(e, dict) and (e.get('type') == 'result' or 'finalText' in e):
            final = e.get('finalText') or final
    if not final:
        return '', (p.stdout or b'').decode('utf8', 'replace')[-1000:] + (p.stderr or b'').decode('utf8', 'replace')[-1000:]
    return final, ''


def prompt_for(code, message):
    return f"""You are fixing one program for the AIL compiler.

Your previous file was:

```python
{code}
```

The compiler printed:

```
{message}
```

Fix the program. Reply with the complete corrected file in one fenced code block tagged
`python` and nothing else. Do not use tools, edit files or run commands.
"""


def compile_src(src, work, name='main.py'):
    path = work / name
    path.write_text(src)
    exe = work / ('exe-' + name.replace('.py', ''))
    exe.unlink(missing_ok=True)
    env = dict(os.environ, AIL_NO_CACHE='1')
    env.pop('AIL_QUIET_FALLBACK', None)
    env.pop('AIL_STRICT', None)
    try:
        p = subprocess.run([sys.executable, '-B', str(AIL), 'compile', str(path), '--syntax', 'python',
                            '-o', str(exe)], capture_output=True, text=True, timeout=300, env=env)
        return p.returncode, p.stdout, p.stderr, exe
    except subprocess.TimeoutExpired:
        return 124, '', '(compile timeout)', exe


def run_prog(cmd, stdin_data, timeout=120):
    try:
        p = subprocess.run(cmd, input=stdin_data, capture_output=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return None, b'', b'(timeout)'


def relevant(stderr, needle):
    for line in (stderr or '').splitlines():
        if needle in line:
            return line.strip()
    return ''


def measure(msg, item, tries=TRIES):
    tid = item['id']
    src = (TRIG / item['file']).read_text()
    stdin_data = (TRIG / item['input']).read_bytes() if item.get('input') else b''
    work = Path(tempfile.mkdtemp(prefix='errfix-%s-' % tid))
    try:
        py_rc, py_out, py_err = run_prog([sys.executable, '-B', str(TRIG / item['file'])], stdin_data)
        brc, bout, berr, bexe = compile_src(src, work)
        a_rc, a_out, a_err = run_prog([str(bexe)], stdin_data) if brc == 0 else (None, b'', b'')
        base = dict(build_rc=brc, cpython_rc=py_rc, cpython_out=py_out.decode('utf8', 'replace'),
                    ail_rc=a_rc, ail_same=(a_rc == py_rc and a_out == py_out),
                    saw_message=relevant(berr, item['needle']))
        attempts = []
        for n in range(tries):
            try:
                reply, err = call_model(prompt_for(src, msg), work)
            except subprocess.TimeoutExpired:
                reply, err = '', '(model timeout)'
            except OSError as e:
                reply, err = '', str(e)
            code = extract(reply) if reply else ''
            rec = dict(n=n + 1, reply_chars=len(reply or ''), code_chars=len(code), error=err[:300])
            if not code.strip():
                rec.update(status='worse', detail='no reply')
                attempts.append(rec)
                continue
            arc, aout, aerr, aexe = compile_src(code, work, 'attempt%d.py' % (n + 1))
            rec['build_rc'] = arc
            rec['message'] = relevant(aerr, item['needle'])
            if arc != 0:
                rec.update(status='still_blocked', detail='build refused')
                attempts.append(rec)
                continue
            rrc, rout, rerr = run_prog([str(aexe)], stdin_data)
            same = rrc == py_rc and rout == py_out
            rec.update(run_rc=rrc, output_matches=same, message_gone=not rec['message'])
            if not same:
                rec.update(status='worse', detail='output differs')
            elif rec['message']:
                rec.update(status='still_blocked', detail='target message remains')
            else:
                rec.update(status='fixed', detail='builds, output matches, message gone')
            attempts.append(rec)
        rec = dict(id=tid, file=item['file'], needle=item['needle'], message=msg,
                   baseline=base, attempts=attempts,
                   fixed=sum(a.get('status') == 'fixed' for a in attempts))
        return rec
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    global CMD
    CMD = find_cmd()
    if not CMD:
        raise SystemExit('no cmd CLI found (set VIBE_CMD_BIN or put cmd on PATH)')
    ap = argparse.ArgumentParser()
    ap.add_argument('--messages', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--jobs', type=int, default=2)
    ap.add_argument('--tries', type=int, default=TRIES)
    ap.add_argument('--only', help='comma-separated trigger ids')
    args = ap.parse_args()
    messages = json.load(open(args.messages))
    items = json.load(open(TRIG / 'manifest.json'))
    want = set(args.only.split(',')) if args.only else None
    todo = [(messages[it['id']], it) for it in items if not want or it['id'] in want]
    out = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        futs = [ex.submit(measure, msg, it, args.tries) for msg, it in todo]
        for i, f in enumerate(futs):
            r = f.result()
            out.append(r)
            print('%2d/%d %-28s fixed %d/%d  %.1fs' % (i + 1, len(futs), r['id'], r['fixed'],
                                                       len(r['attempts']), time.time() - t0), flush=True)
    json.dump(out, open(args.out, 'w'), indent=1)
    total = sum(r['fixed'] for r in out)
    print('TOTAL fixed %d/%d in %.1fs' % (total, len(out) * args.tries, time.time() - t0))


if __name__ == '__main__':
    main()
