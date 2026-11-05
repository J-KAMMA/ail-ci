"""fbgenint1 census: how much of a general-path program's peak RSS is held by lists whose elements are all ints.

For each compare-lab task: build `typed.py` with AIL_UNIFIED_FORCE=1 (the general path), keep the generated C, and
make a scratch copy whose `ail_vec_reserve` walks every live LIST object each time the GC byte count reaches a new
high (5% steps). The walk with the most list-buffer bytes is kept: lists, elements, buffer bytes, and how many of them
hold only AIL_T_INT elements (a bool is not an int here). The plain binary gives peak RSS (median of 3,
/usr/bin/time -v) and run instructions (tools/icount.c); the census binary's stdout and exit status must equal the plain
binary's, and the plain binary's must equal CPython running `main.py`.

Projection of the INT strategy (fbgenint2): an all-int list keeps 8 B per element slot instead of the 32 B ail_obj, so
it saves 24/32 of its buffer bytes. projected_rss = rss - 0.75 * int_cap_bytes; the go/no-go line halves that saving.

Usage: python3 lab/mem/genlist_census.py [task ...]   (writes lab/mem/GENLIST.json; scratch in $GENLIST_WORK)
Memory: run it under `ulimit -v 2500000`; it runs one program at a time.
"""
import json
import os
import pathlib
import re
import shutil
import statistics
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'lab' / 'compare'))
import run_task  # noqa: E402

WORK = pathlib.Path(os.environ.get('GENLIST_WORK', '/home/bluec/scratch/genint'))
TASKS = ['tree_fold', 'berth_sim', 'chain_relax', 'echo_pack', 'ledger_bin', 'rail_transfer', 'scar_life',
         'tally_lang', 'term_rank', 'ticket_audit']

CENSUS_C = r'''
/* ---- fbgenint1 census (scratch build only) ---- */
typedef struct { size_t gc_bytes, lists, elems, cap_bytes, int_lists, int_elems, int_cap_bytes, mixed_cap_bytes,
                 big_int_lists, big_int_cap_bytes, tuples, tuple_bytes, walks; } gl_snap;
static gl_snap gl_best, gl_cur;
static size_t gl_next = 4u << 20;
static size_t gl_walks;
static void gl_dump(void) {
    const char *p = getenv("AIL_CENSUS_OUT"); if (!p) return;
    FILE *f = fopen(p, "w"); if (!f) return;
    fprintf(f, "{\"gc_bytes\": %zu, \"lists\": %zu, \"elems\": %zu, \"cap_bytes\": %zu, \"int_lists\": %zu, "
               "\"int_elems\": %zu, \"int_cap_bytes\": %zu, \"mixed_cap_bytes\": %zu, \"big_int_lists\": %zu, "
               "\"big_int_cap_bytes\": %zu, \"tuples\": %zu, \"tuple_bytes\": %zu, \"walks\": %zu}\n",
            gl_best.gc_bytes, gl_best.lists, gl_best.elems, gl_best.cap_bytes, gl_best.int_lists, gl_best.int_elems,
            gl_best.int_cap_bytes, gl_best.mixed_cap_bytes, gl_best.big_int_lists, gl_best.big_int_cap_bytes,
            gl_best.tuples, gl_best.tuple_bytes, gl_walks);
    fclose(f);
}
static void gl_census(ail_ctx *cx) {
    static int reg; if (!reg) { reg = 1; atexit(gl_dump); }
    memset(&gl_cur, 0, sizeof gl_cur); gl_walks++;
    for (ail_gcobj *o = cx->gc_all; o; o = o->gcnext) {
        if (o->kind == AIL_K_LIST) {
            ail_vecobj *v = (ail_vecobj *)o;
            size_t cb = (v->p == (ail_obj *)(v + 1)) ? 0 : (size_t)v->cap * sizeof(ail_obj);
            gl_cur.lists++; gl_cur.elems += (size_t)v->n; gl_cur.cap_bytes += cb;
            int allint = 1;
            for (int64_t i = 0; i < v->n; i++) if (v->p[i].tag != AIL_T_INT) { allint = 0; break; }
            if (allint) { gl_cur.int_lists++; gl_cur.int_elems += (size_t)v->n; gl_cur.int_cap_bytes += cb;
                          if (cb >= (1u << 20)) { gl_cur.big_int_lists++; gl_cur.big_int_cap_bytes += cb; } }
            else gl_cur.mixed_cap_bytes += cb;
        } else if (o->kind == AIL_K_TUPLE) {
            ail_vecobj *v = (ail_vecobj *)o; gl_cur.tuples++; gl_cur.tuple_bytes += (size_t)v->n * sizeof(ail_obj);
        }
    }
    gl_cur.gc_bytes = cx->gc_bytes;
    if (gl_cur.cap_bytes > gl_best.cap_bytes) gl_best = gl_cur;
}
'''

RESERVE_HEAD = 'static inline void ail_vec_reserve(ail_ctx *cx, ail_vecobj *v, int64_t need) {'
RESERVE_TAIL = '    cx->gc_bytes += (size_t)(nc - oldcap) * sizeof(ail_obj);\n}'
RESERVE_HOOK = ('    cx->gc_bytes += (size_t)(nc - oldcap) * sizeof(ail_obj);\n'
                '    if (cx->gc_bytes > gl_next) { gl_census(cx); gl_next = cx->gc_bytes + cx->gc_bytes / 20; }\n}')


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, **kw)


def wait_mem(need_mb=1500):
    while True:
        avail = int(open('/proc/meminfo').read().split('MemAvailable:')[1].split()[0]) // 1024
        if avail >= need_mb:
            return avail
        print('  waiting for memory: %d MB available' % avail, flush=True)
        time.sleep(120)


def run(binary, case, extra_env=None, timed=False):
    cmd = [str(binary)] + case['args']
    if timed:
        cmd = ['/usr/bin/time', '-v'] + cmd
    env = dict(os.environ)
    env.update(extra_env or {})
    stdin = open(case['path'], 'rb') if case['stdin'] else subprocess.DEVNULL
    p = subprocess.run(cmd, stdin=stdin, capture_output=True, env=env)
    rss = None
    if timed:
        m = re.search(rb'Maximum resident set size \(kbytes\): (\d+)', p.stderr)
        rss = int(m.group(1)) if m else None
    return p.returncode, p.stdout, rss


def icount(binary, case):
    ic = WORK / 'icount'
    if not ic.exists():
        sh(['cc', '-O2', '-w', '-include', 'signal.h', '-include', 'stdlib.h', '-o', str(ic), str(ROOT / 'tools/icount.c')],
           check=True)
    stdin = open(case['path'], 'rb') if case['stdin'] else subprocess.DEVNULL
    p = subprocess.run([str(ic), str(binary)] + case['args'], stdin=stdin, capture_output=True)
    try:
        return int(p.stdout.split()[-1])
    except (ValueError, IndexError):
        return None


def build(task, d):
    src = ROOT / 'lab/compare/src' / task / 'typed.py'
    dbg, out = d / 'dbg', d / 'plain'
    shutil.rmtree(dbg, ignore_errors=True)
    if out.exists():
        out.unlink()
    env = dict(os.environ, AIL_UNIFIED_FORCE='1', AIL_NO_CACHE='1', PYTHONHASHSEED='0')
    p = sh(['python3', '-B', str(ROOT / 'AIL_CURRENT/ail_chatgpt.py'), 'compile', str(src), '-o', str(out),
            '--debug-dir', str(dbg)], env=env, cwd=str(ROOT))
    if p.returncode:
        raise SystemExit('%s: build failed\n%s' % (task, p.stderr.decode()[-2000:]))
    rep = json.loads((dbg / 'native_report.json').read_text())
    cmd = rep['operations'][0]['command']
    c = (dbg / 'program.c').read_text()
    assert c.count(RESERVE_HEAD) == 1 and c.count(RESERVE_TAIL) >= 1, task
    i = c.index(RESERVE_HEAD)
    j = c.index(RESERVE_TAIL, i)
    c = c[:i] + CENSUS_C + c[i:j] + RESERVE_HOOK + c[j + len(RESERVE_TAIL):]
    (d / 'census.c').write_text(c)
    ccmd = list(cmd)
    k = ccmd.index('-o')
    ccmd[k + 1] = str(d / 'census')
    ccmd[k + 2] = str(d / 'census.c')
    p = sh(ccmd)
    if p.returncode:
        raise SystemExit('%s: census build failed\n%s' % (task, p.stderr.decode()[-2000:]))
    return out, d / 'census'


# Inputs scaled down so one process stays under the 1.5 GB cap (the general path keeps 32 B per element):
# task -> (generator function, perf size in gen.py, size used here).
SCALE = {
    'tree_fold': ('random_tree', 3000000, 1000000),
}


def make_case(task, d):
    if task not in SCALE:
        return run_task.make_case(task, False, d), None
    fn, big, small = SCALE[task]
    module = run_task.load_task(task)
    orig = getattr(module, fn)

    def scaled(rng, n, *a, **kw):
        return orig(rng, small if n == big else n, *a, **kw)
    setattr(module, fn, scaled)
    import random
    _pub, _hid, perf = module.cases(random.Random('%s-20261012' % task))
    _name, data, args = perf
    path = d / 'input.bin'
    path.write_bytes(data)
    case = dict(name='perf-scaled', stdin=bool(getattr(module, 'STDIN', False)), path=path,
                args=[a.replace('{input}', str(path)) for a in args], input_bytes=len(data))
    return case, '%s n=%d (perf uses %d)' % (fn, small, big)


def one(task):
    d = WORK / task
    d.mkdir(parents=True, exist_ok=True)
    case, scale_note = make_case(task, d)
    wait_mem()
    plain, census = build(task, d)
    rec = dict(task=task, source='lab/compare/src/%s/typed.py' % task, env='AIL_UNIFIED_FORCE=1',
               input_bytes=case['input_bytes'], args=case['args'], input=scale_note or 'perf')
    rss = []
    out0 = None
    for _ in range(3):
        wait_mem()
        st, out, r = run(plain, case, timed=True)
        rss.append(r)
        out0 = (st, out) if out0 is None else out0
        if (st, out) != out0:
            rec['error'] = 'plain build output differs between runs'
    rec['exit'] = out0[0]
    rec['stdout_bytes'] = len(out0[1])
    if out0[0] != 0 and not out0[1]:
        rec['error'] = 'plain build failed on this input (memory cap?)'
        return rec
    rec['rss_kb_runs'] = rss
    rec['rss_kb'] = statistics.median(rss)
    wait_mem()
    rec['icount'] = icount(plain, case)
    cfile = d / 'census.json'
    if cfile.exists():
        cfile.unlink()
    wait_mem()
    st, out, crss = run(census, case, extra_env={'AIL_CENSUS_OUT': str(cfile)}, timed=True)
    rec['census_same_output'] = (st, out) == out0
    rec['census'] = json.loads(cfile.read_text()) if cfile.exists() else None
    # CPython oracle on main.py (same task spec; every language's source prints the same bytes)
    wait_mem()
    stdin = open(case['path'], 'rb') if case['stdin'] else subprocess.DEVNULL
    try:
        p = subprocess.run(['python3', str(ROOT / 'lab/compare/src' / task / 'main.py')] + case['args'], stdin=stdin,
                           capture_output=True, timeout=1200)
        rec['cpython_same_output'] = (p.returncode, p.stdout) == out0
    except subprocess.TimeoutExpired:
        rec['cpython_same_output'] = 'timeout'
    c = rec['census']
    if c:
        rss_b = rec['rss_kb'] * 1024
        save = 0.75 * c['int_cap_bytes']
        rec['list_share_of_rss'] = round(c['cap_bytes'] / rss_b, 4)
        rec['int_list_share_of_rss'] = round(c['int_cap_bytes'] / rss_b, 4)
        rec['projected_rss_kb'] = round((rss_b - save) / 1024)
        rec['projected_gain'] = round(rss_b / (rss_b - save), 4)
        rec['projected_gain_halved'] = round(rss_b / (rss_b - save / 2), 4)
    return rec


def main():
    tasks = sys.argv[1:] or TASKS
    path = ROOT / 'lab/mem/GENLIST.json'
    data = json.loads(path.read_text()) if path.exists() else {}
    for t in tasks:
        print('==', t, flush=True)
        rec = one(t)
        data[t] = rec
        path.write_text(json.dumps(data, indent=1, sort_keys=True) + '\n')
        print(json.dumps(rec), flush=True)


if __name__ == '__main__':
    main()
