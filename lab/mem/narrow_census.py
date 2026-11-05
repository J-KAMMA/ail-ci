#!/usr/bin/env python3
"""fbnarrow1: where tree_fold's peak memory sits, per int list, and what int32 would buy.

    python3 lab/mem/narrow_census.py --census          # 16/16 programs, scratch-instrumented C
    python3 lab/mem/narrow_census.py --emulate         # tree_fold plain vs int32 temporaries

The tool builds each program through AIL's default path with `--debug-dir`, then edits a
*scratch copy* of the generated `program.c` only: every `ail_list_push`, `ail_list_reserve`,
`ail_list_set`, direct `.p[.n++] =` append, `ir->p[i] =` store, list move and `ail_list_free`
gets a sequentially numbered site id inserted by this script (never by the compiler).  The
tracker keeps, per site, the number of lists, the largest `n`, the smallest and largest stored
value, and the live list-buffer bytes at the program's list-byte peak.  The tracked build must
print byte-identical stdout to the plain build; anything else stops the run.
"""
import argparse
import importlib.util
import json
import os
import random
import re
import resource
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AIL = REPO / 'AIL_CURRENT' / 'ail_chatgpt.py'

TASKS = ['berth_sim', 'chain_relax', 'echo_pack', 'ledger_bin', 'rail_transfer',
         'scar_life', 'tally_lang', 'term_rank', 'ticket_audit', 'tree_fold']
PROGS = ['binarytrees', 'cfold', 'deriv', 'linkedlist', 'objscan', 'rbtree']
TREE_N = 3000000
EMU_WORK = Path('/tmp/fbnarrow1/emulate')
WORK = EMU_WORK
MEM_CAP = 1500 * 1024 * 1024

PROLOGUE = r'''
/* ---- fbnarrow1 census tracker: scratch copy only, never the compiler ---- */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { unsigned long long nlists, maxn, stores, peak; long long mn, mx; int has; } ntrk_ent;
#define NTRK_MAX 8192
static ntrk_ent ntrk_tab[NTRK_MAX];

/* One entry per live list *buffer*: a move between structs keeps the pointer, so byte
   accounting survives `t.w = w` and list returns. */
typedef struct { int64_t *p; int site; unsigned long long bytes; } nlive_ent;
#define NLIVE 262144
static nlive_ent nlive_tab[NLIVE];
static unsigned long long nlive_total, nlive_peak;
static unsigned long long nsite_peak[NTRK_MAX];

static int nlive_find(int64_t *p, int create) {
    unsigned long long h = (unsigned long long)((uintptr_t)p >> 3) * 2654435761ULL;
    unsigned i = (unsigned)(h & (NLIVE - 1));
    for (;;) {
        if (nlive_tab[i].p == p) return (int)i;
        if (!nlive_tab[i].p) {
            if (!create) return -1;
            nlive_tab[i].p = p; nlive_tab[i].site = 0; nlive_tab[i].bytes = 0;
            return (int)i;
        }
        i = (i + 1) & (NLIVE - 1);
    }
}
static void nlive_snap(void) {
    unsigned j;
    for (j = 0; j < NTRK_MAX; j++) nsite_peak[j] = 0;
    for (j = 0; j < NLIVE; j++)
        if (nlive_tab[j].p)
            nsite_peak[nlive_tab[j].site] += nlive_tab[j].bytes;
}
static void nlive_reg(ail_list *L, int site) {
    int64_t *p = L->p;
    unsigned long long bytes;
    int i;
    if (!p) return;
    bytes = (unsigned long long)L->cap * 8ULL;
    i = nlive_find(p, 1);
    if (site && !nlive_tab[i].site) { nlive_tab[i].site = site; ntrk_tab[site].nlists++; }
    nlive_total -= nlive_tab[i].bytes;
    nlive_tab[i].bytes = bytes;
    nlive_total += bytes;
    if (nlive_total > nlive_peak) { nlive_peak = nlive_total; nlive_snap(); }
}
static void nlive_unreg(int64_t *p) {
    int i;
    if (!p) return;
    i = nlive_find(p, 0);
    if (i < 0) return;
    nlive_total -= nlive_tab[i].bytes;
    nlive_tab[i].bytes = 0;
    nlive_tab[i].site = 0;
}
static void ntrk_rec(int site, long long v, long long n) {
    ntrk_ent *e = &ntrk_tab[site];
    e->stores++;
    if (!e->has || v < e->mn) e->mn = v;
    if (!e->has || v > e->mx) e->mx = v;
    e->has = 1;
    if (n > 0 && (unsigned long long)n > e->maxn) e->maxn = (unsigned long long)n;
}
static void ntrk_push(ail_list *L, int64_t v, int site) {
    int64_t *before = L->p;
    ail_list_push(L, v);
    ntrk_rec(site, (long long)v, (long long)L->n);
    if (L->p != before) nlive_unreg(before);
    nlive_reg(L, site);
}
static void ntrk_reserve(ail_list *L, int64_t extra, int site) {
    int64_t *before = L->p;
    ail_list_reserve(L, extra);
    if (L->p != before) nlive_unreg(before);
    nlive_reg(L, site);
}
static void ntrk_set(ail_list *L, int64_t i, int64_t v, int site) {
    L->p[i] = v;                       /* the generated site already bounds-checked */
    ntrk_rec(site, (long long)v, (long long)(i + 1));
    nlive_reg(L, site);
}
static void ntrk_move(ail_list *dst, ail_list *src) {
    nlive_unreg(dst->p);
    ail_list_free(dst);
    *dst = *src;
    *src = (ail_list){0};
}
static void ntrk_free(ail_list *L) {
    nlive_unreg(L->p);
    ail_list_free(L);
}
static void ntrk_dump(void) {
    const char *path = getenv("NTRK_OUT");
    FILE *f;
    int s;
    if (!path) return;
    f = fopen(path, "w");
    if (!f) return;
    fprintf(f, "PEAK %llu\n", nlive_peak);
    for (s = 0; s < NTRK_MAX; s++)
        if (ntrk_tab[s].stores || nsite_peak[s])
            fprintf(f, "S %d %llu %llu %lld %lld %llu %llu %d\n", s, ntrk_tab[s].nlists,
                    ntrk_tab[s].maxn, ntrk_tab[s].mn, ntrk_tab[s].mx, ntrk_tab[s].stores,
                    nsite_peak[s], ntrk_tab[s].has);
    fclose(f);
}
__attribute__((constructor)) static void ntrk_start(void) { atexit(ntrk_dump); }
/* ---- end fbnarrow1 census tracker ---- */
'''

FUNC_RE = re.compile(r'^(?:static\s+)?(?:inline\s+)?[A-Za-z_]\w*[\w\s\*]*?\b(\w+)\s*\([^;{}]*\)\s*\{')


def limits():
    resource.setrlimit(resource.RLIMIT_AS, (MEM_CAP, MEM_CAP))


def run(cmd, stdin_path=None, env=None, out_path=None, err_path=None, timeout=3600):
    inp = open(stdin_path, 'rb') if stdin_path else subprocess.DEVNULL
    out = open(out_path, 'wb') if out_path else subprocess.PIPE
    err = open(err_path, 'wb') if err_path else subprocess.PIPE
    try:
        p = subprocess.run(cmd, stdin=inp, stdout=out, stderr=err, timeout=timeout,
                           env=env, cwd=str(REPO), preexec_fn=limits)
    finally:
        if stdin_path:
            inp.close()
        if out_path:
            out.close()
        if err_path:
            err.close()
    return p


def build(src, work, out, debug=True):
    work.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    dbg = work / 'dbg'
    if debug and dbg.exists():
        shutil.rmtree(dbg)
    cmd = [sys.executable, '-B', str(AIL), 'compile', str(src), '--syntax', 'python', '-o', str(out)]
    if debug:
        cmd += ['--debug-dir', str(dbg)]
    env = dict(os.environ, PYTHONHASHSEED='0', AIL_NO_CACHE='1')
    p = subprocess.run(cmd, cwd=str(work), capture_output=True, timeout=1800, env=env)
    return p, (dbg / 'program.c') if debug else None


def compile_flags(program_c):
    report = program_c.parent / 'native_report.json'
    try:
        cmd = json.loads(report.read_text())['operations'][0]['command']
    except Exception:
        return ['-O2', '-fno-asynchronous-unwind-tables']
    flags = []
    skip = False
    for item in cmd[1:]:
        if item == '-o':
            skip = True
            continue
        if skip:
            skip = False
            continue
        if item == str(program_c) or item.endswith('program.c'):
            continue
        flags.append(item)
    return flags


class Sites:
    def __init__(self):
        self.next = 0
        self.labels = {}

    def add(self, label):
        self.next += 1
        self.labels[self.next] = label
        return self.next


def find_close(s, k):
    depth = 0
    quote = None
    i = k
    while i < len(s):
        c = s[i]
        if quote:
            if c == '\\':
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in '"\'':
            quote = c
        elif c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def rewrite_call(line, name, newname, sites, func):
    out = []
    i = 0
    needle = name + '('
    while True:
        j = line.find(needle, i)
        if j < 0:
            out.append(line[i:])
            break
        k = find_close(line, j + len(needle) - 1)
        if k < 0:
            out.append(line[i:])
            break
        args = line[j + len(needle):k]
        var = args.split(',')[0].strip().lstrip('&').strip()
        var = var.replace('(', '').replace(')', '')
        sid = sites.add(f'{func}:{var}')
        out.append(line[i:j])
        out.append(f'{newname}({args}, {sid})')
        i = k + 1
    return ''.join(out)


def rewrite_rhs(line, start, sites, label):
    """Replace `= RHS;` starting at `start` with `ntrk_push(...)`; returns new line."""
    depth = 0
    quote = None
    i = start
    while i < len(line):
        c = line[i]
        if quote:
            if c == '\\':
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in '"\'':
            quote = c
        elif c in '({[':
            depth += 1
        elif c in ')}]':
            depth -= 1
        elif c == ';' and depth <= 0:
            break
        i += 1
    if i >= len(line):
        return None, None
    return line[:start], line[start:i], i


def instrument(text):
    lines = text.splitlines(True)
    ins = None
    for n, line in enumerate(lines):
        if line.startswith('static void ail_list_free(ail_list *L)'):
            ins = n + 1
            break
    if ins is None:
        for n, line in enumerate(lines):
            if 'void ail_list_push(ail_list *L, int64_t v)' in line and line.rstrip().endswith('{'):
                depth = 0
                for m in range(n, len(lines)):
                    depth += lines[m].count('{') - lines[m].count('}')
                    if depth == 0:
                        ins = m + 1
                        break
                break
    if ins is None:
        return text, {}
    sites = Sites()
    func = '?'
    head = ''.join(lines[:ins])
    decl = 'static void nlive_reg(ail_list *L, int site);\nstatic void nlive_unreg(int64_t *p);\n'
    head = head.replace('} ail_list;', '} ail_list;\n' + decl, 1)
    head = head.replace('    L->p[L->n++] = v;\n}',
                        '    L->p[L->n++] = v;\n    nlive_reg(L, 0);\n}', 1)
    head = head.replace('    L->p = q; L->cap = L->n + extra;\n}',
                        '    L->p = q; L->cap = L->n + extra;\n    nlive_reg(L, 0);\n}', 1)
    head = head.replace('static void ail_list_free(ail_list *L) { free(L->p);',
                        'static void ail_list_free(ail_list *L) { nlive_unreg(L->p); free(L->p);', 1)
    head = head.replace('static inline __attribute__((always_inline)) void ail_list_push(ail_list *L, int64_t v) {',
                        'static void nlive_reg(ail_list *L, int site);\nstatic void nlive_unreg(int64_t *p);\nstatic inline __attribute__((always_inline)) void ail_list_push(ail_list *L, int64_t v) {', 1)
    out = [head, PROLOGUE]
    for line in lines[ins:]:
        m = FUNC_RE.match(line)
        if m:
            func = m.group(1)
        # 1. list moves: ail_list_free(&D); D = S; S = (ail_list){0};
        mv = re.search(r'ail_list_free\((&[A-Za-z_]\w*(?:->\w+)?)\);\s*([A-Za-z_]\w*(?:->\w+)?)\s*=\s*(\w+);\s*\3\s*=\s*\(ail_list\)\s*\{0\};', line)
        if mv:
            sid = sites.add(f'{func}:move->{mv.group(2)}')
            line = line[:mv.start()] + f'{{ ntrk_move({mv.group(1)}, &{mv.group(3)}); }}' + line[mv.end():]
        # 2. direct append: X.p[X.n++] = EXPR;
        while True:
            pm = re.search(r'(\bv_[A-Za-z0-9_]+)\.p\[\1\.n\+\+\]\s*=\s*', line)
            if not pm:
                break
            _, rhs, end = rewrite_rhs(line, pm.end(), sites, pm.group(1))
            if rhs is None:
                break
            sid = sites.add(f'{func}:{pm.group(1)}')
            line = line[:pm.start()] + f'ntrk_push(&{pm.group(1)}, ({rhs}), {sid})' + line[end:]
        # 3. raw index store through an ir temp: ir5->p[IDX] = EXPR;
        for im in list(re.finditer(r'(\(?(\bir\w+)\)?)->p\[\s*([^\]]+?)\s*\]\s*=\s*', line)):
            if re.search(r'\b' + im.group(2) + r'\s*\.p\[\s*' + im.group(2) + r'\s*\.n\+\+\]', line):
                continue
            _, rhs, end = rewrite_rhs(line, im.end(), sites, im.group(2))
            if rhs is None:
                continue
            sid = sites.add(f'{func}:{im.group(2)}')
            line = line[:im.start()] + f'ntrk_set({im.group(2)}, ({im.group(3)}), ({rhs}), {sid})' + line[end:]
        # 4. calls
        for name, newname in (('ail_list_push', 'ntrk_push'),
                              ('ail_list_reserve', 'ntrk_reserve'),
                              ('ail_list_set', 'ntrk_set')):
            line = rewrite_call(line, name, newname, sites, func)
        # 5. free
        line = re.sub(r'\bail_list_free\(', 'ntrk_free(', line)
        out.append(line)
    return ''.join(out), sites.labels


def load_gen(task):
    path = REPO / 'lab' / 'compare' / 'tasks' / task / 'gen.py'
    spec = importlib.util.spec_from_file_location('gen_' + task, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


OPS = ['stats', 'total', 'level 6', 'find leaf', 'sort', 'find qqqqqqqqqqqqqqqq', 'prune 40',
       'stats', 'fold', 'stats', 'cut mid', 'mirror', 'level 3', 'find x+y', 'sort', 'stats', 'print']


def perf_case(task, work):
    work.mkdir(parents=True, exist_ok=True)
    mod = load_gen(task)
    args = []
    if task == 'tree_fold':
        tree = mod.random_tree(random.Random(1), TREE_N, chain=0.35)
        data = mod.doc(tree, *OPS)
    else:
        _, _, perf = mod.cases(random.Random(1))
        name, data, args = perf
    inp = work / 'input'
    inp.write_bytes(data)
    args = [a.replace('{input}', str(inp)) for a in args]
    stdin_path = str(inp) if getattr(mod, 'STDIN', False) else None
    return stdin_path, args, len(data)


def classify(lo, hi):
    if lo >= -128 and hi <= 127:
        return 'int8'
    if lo >= -32768 and hi <= 32767:
        return 'int16'
    if lo >= -2147483648 and hi <= 2147483647:
        return 'int32'
    return 'int64'


def one_program(name, source, work, stdin_path, args, rows):
    plain_out = work / 'plain'
    p, program_c = build(source, work, plain_out, debug=True)
    if p.returncode != 0:
        return {'program': name, 'error': 'plain build failed', 'stderr': p.stderr.decode('utf8', 'replace')[-500:]}
    flags = compile_flags(program_c)
    pout = work / 'plain.stdout'
    perr = work / 'plain.stderr'
    pp = run([str(plain_out)] + args, stdin_path=stdin_path, out_path=pout, err_path=perr)
    text, labels = instrument(program_c.read_text())
    scratch = work / 'scratch'
    scratch.mkdir(exist_ok=True)
    (scratch / 'program.c').write_text(text)
    tout = work / 'tracked'
    cp = subprocess.run(['cc'] + flags + ['-w', '-o', str(tout), str(scratch / 'program.c')],
                        capture_output=True, text=True)
    if cp.returncode != 0:
        return {'program': name, 'error': 'tracked compile failed', 'stderr': cp.stderr[-1500:]}
    trk = work / 'tracked.trk'
    env = dict(os.environ, NTRK_OUT=str(trk))
    tp = run([str(tout)] + args, stdin_path=stdin_path, out_path=work / 'tracked.stdout',
             err_path=work / 'tracked.stderr', env=env)
    same = (pout.read_bytes() == (work / 'tracked.stdout').read_bytes()
            and pp.returncode == tp.returncode)
    entry = {'program': name, 'match': same, 'exit': [pp.returncode, tp.returncode],
             'plain_bytes': len(pout.read_bytes())}
    if not same:
        entry['error'] = 'tracked stdout/exit differs from the plain build'
        return entry
    peak = 0
    for line in (trk.read_text().splitlines() if trk.exists() else []):
        f = line.split()
        if f[0] == 'PEAK':
            peak = int(f[1])
        elif f[0] == 'S' and int(f[7]) > 0:
            sid, nlists, maxn, mn, mx, stores, bytes_peak, has = (int(f[1]), int(f[2]), int(f[3]),
                                                                 int(f[4]), int(f[5]), int(f[6]),
                                                                 int(f[7]), int(f[8]))
            rows.append({'program': name, 'site': sid, 'label': labels.get(sid, '?'),
                         'nlists': nlists, 'max_n': maxn,
                         'min_value': mn if has else None, 'max_value': mx if has else None,
                         'stores': stores, 'peak_bytes': bytes_peak,
                         'MiB': round(bytes_peak / 1048576.0, 2),
                         'width': classify(mn, mx) if has else 'empty'})
    entry['peak_list_bytes'] = peak
    entry['peak_list_MiB'] = round(peak / 1048576.0, 2)
    return entry


def census(only=None):
    work = Path('/tmp/fbnarrow1/census')
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    rows = []
    results = []
    for task in TASKS:
        if only and only != task:
            continue
        w = work / task
        stdin_path, args, nbytes = perf_case(task, w)
        r = one_program(task, REPO / 'lab' / 'compare' / 'src' / task / 'typed.py', w,
                        stdin_path, args, rows)
        r['input_bytes'] = nbytes
        results.append(r)
        print(task, r.get('match'), r.get('peak_list_MiB'), 'MiB', r.get('error', ''), flush=True)
    for prog in PROGS:
        if only and only != prog:
            continue
        w = work / prog
        r = one_program(prog, REPO / 'lab' / 'rc' / 'progs' / (prog + '.py'), w, None, [], rows)
        results.append(r)
        print(prog, r.get('match'), r.get('peak_list_MiB'), 'MiB', r.get('error', ''), flush=True)
    big = [x for x in rows if x['peak_bytes'] >= 1048576]
    doc = {'mode': 'census', 'programs': results,
           'rows_at_least_1MiB': sorted(big, key=lambda x: -x['peak_bytes'])}
    (HERE / 'NARROW.json').write_text(json.dumps(doc, indent=1))
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--census', action='store_true')
    ap.add_argument('--emulate', action='store_true')
    ap.add_argument('--only')
    a = ap.parse_args()
    if a.census:
        census(a.only)
    elif a.emulate:
        emulate()
    else:
        ap.print_help()




I32_TYPE = r'''
/* ---- fbnarrow1 i32 emulation: scratch copy only ---- */
typedef struct { int32_t *p; ail_len_t n, cap; } i32list;
static void i32_push(i32list *L, int64_t v) {
    if (L->n == L->cap) {
        int64_t c = L->cap ? L->cap * 2 : 8;
        int32_t *q = (int32_t *)realloc(L->p, (size_t)c * sizeof *q);
        if (!q) ail_die("out of memory");
        L->p = q; L->cap = c;
    }
    L->p[L->n++] = (int32_t)v;
}
static void i32_reserve(i32list *L, int64_t extra) {
    int32_t *q;
    if (extra <= 0 || L->cap - L->n >= extra) return;
    q = (int32_t *)realloc(L->p, (size_t)(L->n + extra) * sizeof *q);
    if (!q) ail_die("out of memory");
    L->p = q; L->cap = L->n + extra;
}
static int64_t i32_get(const i32list *L, int64_t i) {
    if (__builtin_expect((uint64_t)i >= (uint64_t)L->n, 0)) {
        if (i < 0) i += L->n;
        if (i < 0 || i >= L->n) ail_die("list index out of range");
    }
    return L->p[i];
}
static void i32_set(i32list *L, int64_t i, int64_t v) {
    if (__builtin_expect((uint64_t)i >= (uint64_t)L->n, 0)) {
        if (i < 0) i += L->n;
        if (i < 0 || i >= L->n) ail_die("list index out of range");
    }
    L->p[i] = (int32_t)v;
}
static void i32_free(i32list *L) { free(L->p); L->p = 0; L->n = L->cap = 0; }
/* ---- end fbnarrow1 i32 emulation ---- */
'''

I32_VARS = ('v_mp', 'v_ord', 'v_ni')


def limits():
    resource.setrlimit(resource.RLIMIT_AS, (MEM_CAP, MEM_CAP))


def run(cmd, stdin_path=None, out_path=None, err_path=None, timeout=3600, env=None):
    inp = open(stdin_path, 'rb') if stdin_path else subprocess.DEVNULL
    out = open(out_path, 'wb') if out_path else subprocess.PIPE
    err = open(err_path, 'wb') if err_path else subprocess.PIPE
    try:
        return subprocess.run(cmd, stdin=inp, stdout=out, stderr=err, timeout=timeout,
                              cwd=str(REPO), preexec_fn=limits, env=env)
    finally:
        if stdin_path:
            inp.close()
        if out_path:
            out.close()
        if err_path:
            err.close()


def build_plain():
    WORK.mkdir(parents=True, exist_ok=True)
    out = WORK / 'plain'
    dbg = WORK / 'dbg'
    if dbg.exists():
        shutil.rmtree(dbg)
    if out.exists():
        out.unlink()
    env = dict(os.environ, PYTHONHASHSEED='0', AIL_NO_CACHE='1')
    p = subprocess.run([sys.executable, '-B', str(AIL), 'compile',
                        str(REPO / 'lab' / 'compare' / 'src' / 'tree_fold' / 'typed.py'),
                        '--syntax', 'python', '-o', str(out), '--debug-dir', str(dbg)],
                       cwd=str(WORK), capture_output=True, env=env, timeout=1800)
    if p.returncode != 0:
        raise SystemExit('plain build failed: ' + p.stderr.decode('utf8', 'replace')[-1000:])
    return out, dbg / 'program.c'


def compile_flags(program_c):
    report = program_c.parent / 'native_report.json'
    cmd = json.loads(report.read_text())['operations'][0]['command']
    flags, skip = [], False
    for item in cmd[1:]:
        if item == '-o':
            skip = True
            continue
        if skip:
            skip = False
            continue
        if item == str(program_c) or item.endswith('program.c'):
            continue
        flags.append(item)
    return flags


def edit_i32(text):
    lines = text.splitlines(True)
    ins = None
    for n, line in enumerate(lines):
        if line.startswith('static void ail_list_free(ail_list *L)'):
            ins = n + 1
            break
    if ins is None:
        raise SystemExit('no list runtime in program.c')
    body = ''.join(lines)
    for v in I32_VARS:
        body = body.replace(f'ail_list {v} = {{0}};', f'i32list {v} = {{0}};')
        for fn, new in (('ail_list_push', 'i32_push'), ('ail_list_get', 'i32_get'),
                        ('ail_list_set', 'i32_set'), ('ail_list_reserve', 'i32_reserve'),
                        ('ail_list_free', 'i32_free')):
            body = body.replace(f'{fn}(&{v},', f'{new}(&{v},')
            body = body.replace(f'{fn}(&{v})', f'{new}(&{v})')
    body = body.replace('((&v_mp)->p[v_i] = (v_nm.n));', 'i32_set(&v_mp, v_i, (v_nm.n));')
    body = body.replace('((&v_mp)->p[v_i] = (v_k));', 'i32_set(&v_mp, v_i, (v_k));')
    body = body.replace('((&v_ord)->p[ v_k])', '((int64_t)i32_get(&v_ord, v_k))')
    # `ord = []` steals an empty temp; keep ord as the fresh empty i32 list instead
    body = body.replace('i32_free(&v_ord); v_ord = v__t2; v__t2 = (ail_list){0};',
                        'i32_free(&v_ord); v__t2 = (ail_list){0};')
    body = ''.join(body.splitlines(True)[:ins]) + I32_TYPE + ''.join(body.splitlines(True)[ins:])
    return body


def time_run(binary, stdin_path, n=1):
    best = None
    values = []
    for _ in range(n):
        p = subprocess.run(['/usr/bin/time', '-v', str(binary)], stdin=open(stdin_path, 'rb'),
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, preexec_fn=limits)
        m = re.search(rb'Maximum resident set size \(kbytes\): (\d+)', p.stderr)
        values.append(int(m.group(1)) if m else -1)
    values.sort()
    return values


def gen_perf():
    path = REPO / 'lab' / 'compare' / 'tasks' / 'tree_fold' / 'gen.py'
    spec = importlib.util.spec_from_file_location('tfgen', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    data = mod.doc(mod.random_tree(random.Random(1), TREE_N, chain=0.35), *OPS)
    (WORK / 'perf.in').write_bytes(data)
    return mod, data


def cases(mod):
    pub, hid, _ = mod.cases(random.Random(1))
    for name, data, args in pub + hid:
        yield name, data, args




def emulate():
    out, program_c = build_plain()
    text = program_c.read_text()
    edited = edit_i32(text)
    (EMU_WORK / 'program_i32.c').write_text(edited)
    import difflib
    diff = difflib.unified_diff(text.splitlines(True), edited.splitlines(True),
                                'program.c', 'program_i32.c')
    (HERE / 'treefold_i32.patch').write_text(''.join(diff))
    flags = compile_flags(program_c)
    edited_bin = EMU_WORK / 'i32'
    cp = subprocess.run(['cc'] + flags + ['-w', '-o', str(edited_bin), str(EMU_WORK / 'program_i32.c')],
                        capture_output=True, text=True)
    if cp.returncode != 0:
        print('i32 compile failed:\n' + cp.stderr[-3000:])
        return 1
    mod, _ = gen_perf()
    checks = []
    for name, data, args in cases(mod):
        inp = EMU_WORK / 'case.in'
        inp.write_bytes(data)
        a = [x.replace('{input}', str(inp)) for x in args]
        po = run([str(out)] + a, stdin_path=str(inp))
        co = run([str(edited_bin)] + a, stdin_path=str(inp))
        checks.append({'case': name, 'match': po.stdout == co.stdout and po.returncode == co.returncode})
    perf = EMU_WORK / 'perf.in'
    po = run([str(out)], stdin_path=str(perf), out_path=EMU_WORK / 'plain.out')
    co = run([str(edited_bin)], stdin_path=str(perf), out_path=EMU_WORK / 'i32.out')
    perf_match = (EMU_WORK / 'plain.out').read_bytes() == (EMU_WORK / 'i32.out').read_bytes() \
        and po.returncode == co.returncode
    rss_plain = time_run(out, perf, 3)
    rss_i32 = time_run(edited_bin, perf, 3)
    icount = {'method': 'none'}
    if shutil.which('valgrind'):
        small = EMU_WORK / 'small.in'
        small.write_bytes(mod.doc(mod.random_tree(random.Random(1), 300000, chain=0.35), *OPS))
        ic = {}
        for label, binary in (('plain', out), ('i32', edited_bin)):
            p = subprocess.run(['valgrind', '--tool=callgrind', '--callgrind-out-file=/dev/null',
                                str(binary)], stdin=open(small, 'rb'), stdout=subprocess.DEVNULL,
                               stderr=subprocess.PIPE, timeout=3600)
            m = re.search(rb'I\s+refs:\s+([0-9,]+)', p.stderr)
            ic[label] = int(m.group(1).replace(b',', b'')) if m else None
        icount = {'method': 'valgrind-callgrind-Ir', 'n': 300000, **ic}
    phases = {}
    for label, binary in (('plain', out), ('i32', edited_bin)):
        p = subprocess.run([sys.executable, str(REPO / 'tools' / 'rss_phases.py'), '--n', str(TREE_N),
                            str(binary)], capture_output=True, text=True, timeout=3600)
        phases[label] = p.stdout[-4000:]
    p0, p1 = rss_plain[len(rss_plain) // 2], rss_i32[len(rss_i32) // 2]
    doc = {'perf_input_bytes': perf.stat().st_size, 'cases': checks,
           'cases_match': all(c['match'] for c in checks), 'perf_match': bool(perf_match),
           'rss_kib': {'plain': rss_plain, 'i32': rss_i32},
           'rss_median_kib': {'plain': p0, 'i32': p1},
           'rss_delta_pct': round(100.0 * (p0 - p1) / p0, 2) if p0 > 0 else None,
           'instructions': icount, 'phases': phases}
    final = doc
    prev = HERE / 'NARROW.json'
    try:
        old = json.loads(prev.read_text())
        if 'programs' in old:
            final = {'census': old, 'emulate': doc}
    except Exception:
        pass
    prev.write_text(json.dumps(final, indent=1))
    print(json.dumps({k: v for k, v in doc.items() if k != 'phases'}, indent=1))
    return 0


if __name__ == '__main__':
    main()
