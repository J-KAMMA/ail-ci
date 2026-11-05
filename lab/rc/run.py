#!/usr/bin/env python3
"""rc1 measurement harness: retain/release counts, instruction share and RSS split.

    python3 lab/rc/run.py --only linkedlist
    python3 lab/rc/run.py --out lab/rc/PRICE.json

The hardware instruction counter (tools/icount.c) is unavailable on this runner:
perf_event_open succeeds for software events but the VM exposes no CPU PMU
(/sys/bus/event_source/devices/cpu is absent), so hardware INSTRUCTIONS returns
ENOENT.  Dynamic instruction counts are therefore *estimated* from gcov line
counts multiplied by the static instruction count of the same source line in the
plain -O2 -g build.  The estimate is labelled est_method in PRICE.json.
"""
import argparse
import importlib.util
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AIL = REPO / 'AIL_CURRENT' / 'ail_chatgpt.py'

NEW_PROGS = [
    ('binarytrees', HERE / 'progs' / 'binarytrees.py'),
    ('cfold', HERE / 'progs' / 'cfold.py'),
    ('deriv', HERE / 'progs' / 'deriv.py'),
    ('linkedlist', HERE / 'progs' / 'linkedlist.py'),
    ('objscan', HERE / 'progs' / 'objscan.py'),
    ('rbtree', HERE / 'progs' / 'rbtree.py'),
]
TASKS = ['berth_sim', 'chain_relax', 'echo_pack', 'ledger_bin', 'rail_transfer',
         'scar_life', 'tally_lang', 'term_rank', 'ticket_audit', 'tree_fold']
TREE_N = 3000000

CATS = ['list buffers', 'str objects', 'class objects', 'input bytes', 'other']
CAT_INDEX = {name: i for i, name in enumerate(CATS)}

HELPER_LINE = re.compile(
    r'^\s*(?:static\s+)?(?:inline\s+|__attribute__\s*\(\([^)]*\)\)\s+)*'
    r'(?:const\s+)?(?:[A-Za-z_][A-Za-z0-9_]*\s+|\*\s*)*\*?\s*'
    r'(?P<name>ail_[A-Za-z0-9_]*(?:retain|release|_store))\s*\([^;{}]*\)\s*\{')

PREAMBLE = r'''
/* ------------------------------------------------------------------ rc1 probe
   Scratch-only instrumentation.  malloc/calloc/realloc/free are wrapped by the
   linker; every allocation carries a 32-byte header (size + two return
   addresses) so a free can be charged back to the allocation site.  A new
   global live-byte high-water mark snapshots the live total of every site.
   The helper definitions get a call counter injected after their opening brace. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define RC_KEYS 4096
#define RC_MAGIC 0x7263316d656dULL
#define RC_HDR 32

typedef struct {
    void *ra0;
    void *ra1;
    unsigned long long live, peak, total, allocs, frees, reuse;
    unsigned long long last_free_size;
} rc_key;
static rc_key rc_keys[RC_KEYS];
static unsigned long long rc_live, rc_peak;
static unsigned long long rc_hits[256];
#define RC_HIT(i) (rc_hits[i]++)

extern void *__real_malloc(size_t);
extern void *__real_calloc(size_t, size_t);
extern void *__real_realloc(void *, size_t);
extern void __real_free(void *);

typedef struct { uint64_t magic, size; void *ra0, *ra1; } rc_hdr;

static rc_key *rc_slot(void *ra0, void *ra1) {
    uint64_t h = ((uint64_t)(uintptr_t)ra0 >> 4) ^ ((uint64_t)(uintptr_t)ra1 << 1);
    unsigned i = (unsigned)(h % RC_KEYS);
    for (unsigned k = 0; k < RC_KEYS; k++) {
        unsigned j = (i + k) % RC_KEYS;
        rc_key *e = &rc_keys[j];
        if (e->ra0 == ra0 && e->ra1 == ra1) return e;
        if (!e->ra0 && !e->ra1) { e->ra0 = ra0; e->ra1 = ra1; return e; }
    }
    return &rc_keys[0];
}

static void *rc_block(size_t n, void *ra0, void *ra1, int zero) {
    if (n > SIZE_MAX - RC_HDR) return NULL;
    char *base = zero ? (char *)__real_calloc(1, n + RC_HDR)
                      : (char *)__real_malloc(n + RC_HDR);
    if (!base) return NULL;
    rc_hdr *h = (rc_hdr *)base;
    h->magic = RC_MAGIC;
    h->size = n;
    h->ra0 = ra0;
    h->ra1 = ra1;
    return base + RC_HDR;
}

static void rc_note_alloc(void *p, size_t n, void *ra0, void *ra1) {
    rc_key *e = rc_slot(ra0, ra1);
    if (e->last_free_size == n && e->last_free_size != (unsigned long long)-1) {
        e->reuse++;
        e->last_free_size = (unsigned long long)-1;
    }
    e->live += n;
    e->total += n;
    e->allocs++;
    rc_live += n;
    if (rc_live > rc_peak) {
        rc_peak = rc_live;
        for (unsigned j = 0; j < RC_KEYS; j++) rc_keys[j].peak = rc_keys[j].live;
    }
}

void *__wrap_malloc(size_t n) {
    void *ra0 = __builtin_return_address(0), *ra1 = __builtin_return_address(1);
    void *p = rc_block(n, ra0, ra1, 0);
    if (p) rc_note_alloc(p, n, ra0, ra1);
    return p;
}
void *__wrap_calloc(size_t a, size_t b) {
    void *ra0 = __builtin_return_address(0), *ra1 = __builtin_return_address(1);
    size_t n = a && b > SIZE_MAX / a ? SIZE_MAX : a * b;
    if (n == SIZE_MAX) return NULL;
    void *p = rc_block(n, ra0, ra1, 1);
    if (p) rc_note_alloc(p, n, ra0, ra1);
    return p;
}
void __wrap_free(void *p) {
    if (!p) return;
    rc_hdr *h = (rc_hdr *)((char *)p - RC_HDR);
    if (h->magic == RC_MAGIC) {
        rc_key *e = rc_slot(h->ra0, h->ra1);
        e->live -= h->size;
        e->frees++;
        e->last_free_size = h->size;
        rc_live -= h->size;
        h->magic = 0;
        __real_free((char *)p - RC_HDR);
    } else {
        __real_free(p);
    }
}
void *__wrap_realloc(void *p, size_t n) {
    if (!p) return __wrap_malloc(n);
    if (n == 0) { __wrap_free(p); return NULL; }
    rc_hdr *h = (rc_hdr *)((char *)p - RC_HDR);
    if (h->magic != RC_MAGIC) {
        char *base = (char *)__real_realloc(p, n + RC_HDR);
        if (!base) return NULL;
        rc_hdr *nh = (rc_hdr *)base;
        nh->magic = RC_MAGIC; nh->size = n;
        nh->ra0 = __builtin_return_address(0);
        nh->ra1 = __builtin_return_address(1);
        return base + RC_HDR;
    }
    size_t old = h->size;
    void *ra0 = __builtin_return_address(0), *ra1 = __builtin_return_address(1);
    void *np = rc_block(n, ra0, ra1, 0);
    if (!np) return NULL;
    memcpy(np, p, old < n ? old : n);
    __wrap_free(p);
    rc_note_alloc(np, n, ra0, ra1);
    return np;
}

static void rc_dump(void) {
    const char *path = getenv("RC_COUNTS");
    if (!path) return;
    FILE *f = fopen(path, "w");
    if (!f) return;
    fprintf(f, "PEAK %llu\n", rc_peak);
    for (unsigned i = 0; i < 256; i++)
        if (rc_hits[i]) fprintf(f, "HIT %u %llu\n", i, rc_hits[i]);
    for (unsigned i = 0; i < RC_KEYS; i++) {
        rc_key *e = &rc_keys[i];
        if (!e->ra0 && !e->ra1) continue;
        fprintf(f, "MEM %p %p %llu %llu %llu %llu %llu %llu\n", e->ra0, e->ra1,
                e->total, e->allocs, e->peak, e->live, e->frees, e->reuse);
    }
    fclose(f);
}
__attribute__((constructor)) static void rc_start(void) { atexit(rc_dump); }
/* ------------------------------------------------------------------ rc1 probe end */
'''

COUNT_FLAGS = ['-no-pie', '-fno-omit-frame-pointer', '-Wl,--wrap=malloc',
               '-Wl,--wrap=calloc', '-Wl,--wrap=realloc', '-Wl,--wrap=free']


def run(cmd, stdin_path=None, timeout=3600, env=None, out_path=None, err_path=None):
    inp = open(stdin_path, 'rb') if stdin_path else subprocess.DEVNULL
    out = open(out_path, 'wb') if out_path else subprocess.PIPE
    err = open(err_path, 'wb') if err_path else subprocess.PIPE
    try:
        p = subprocess.run(cmd, stdin=inp, stdout=out, stderr=err, timeout=timeout,
                           env=env, cwd=str(REPO))
    finally:
        if stdin_path:
            inp.close()
        if out_path:
            out.close()
        if err_path:
            err.close()
    return p


def build(source, work, out, debug=False):
    work.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    dbg = work / 'dbg'
    if debug and dbg.exists():
        shutil.rmtree(dbg)
    cmd = [sys.executable, '-B', str(AIL), 'compile', str(source), '--syntax', 'python',
           '-o', str(out)]
    if debug:
        cmd += ['--debug-dir', str(dbg)]
    p = run(cmd, timeout=600)
    return p, dbg / 'program.c'


def compile_flags(program_c):
    report = program_c.parent / 'native_report.json'
    try:
        cmd = json.loads(report.read_text())['operations'][0]['command']
    except Exception:
        return ['-O2', '-fno-asynchronous-unwind-tables']
    flags = []
    skip = False
    for k, item in enumerate(cmd[1:]):
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


def find_helpers(text):
    found = []
    offset = 0
    for lineno, line in enumerate(text.splitlines(True), 1):
        m = HELPER_LINE.match(line)
        if m:
            brace = offset + line.find('{', m.start())
            found.append((m.group('name'), brace, lineno))
        offset += len(line)
    names = []
    for name, _, _ in found:
        if name not in names:
            names.append(name)
    return found, names


def brace_end(text, start):
    depth = 0
    i = start
    while i < len(text):
        c = text[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return text.count('\n', 0, i) + 1
        i += 1
    return text.count('\n') + 1


def estimation_text(text, helpers):
    lines = text.splitlines(True)
    starts = {}
    off = 0
    for i, line in enumerate(lines):
        starts[off] = i
        off += len(line)
    for _, brace, _ in helpers:
        idx = starts.get(brace - (brace - text.rfind('\n', 0, brace) - 1), None)
        # brace is an offset; locate its line directly instead
        idx = text.count('\n', 0, brace)
        line = lines[idx]
        if 'noinline' not in line:
            line = re.sub(r'__attribute__\s*\(\(\s*always_inline\s*\)\)\s*', '', line)
            line = re.sub(r'\binline\b', '', line)
            if 'static' in line:
                line = line.replace('static', 'static __attribute__((noinline))', 1)
            else:
                line = '__attribute__((noinline)) ' + line
        lines[idx] = line
    return ''.join(lines)


def instrument(text, helpers, names):
    hit_index = {name: i for i, name in enumerate(names)}
    inserts = []
    for name, brace, _ in helpers:
        inserts.append((brace + 1, ' RC_HIT(%d);' % hit_index[name]))
    for pos, ins in sorted(inserts, reverse=True):
        text = text[:pos] + ins + text[pos:]
    anchor = text.find('#include <stdlib.h>')
    if anchor < 0:
        raise SystemExit('no stdlib include in generated C')
    pos = text.find('\n', anchor) + 1
    return text[:pos] + PREAMBLE + text[pos:]


def parse_counts(path):
    hits, mem, peak = {}, [], None
    for line in Path(path).read_text().splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == 'PEAK':
            peak = int(parts[1])
        elif parts[0] == 'HIT':
            hits[int(parts[1])] = int(parts[2])
        elif parts[0] == 'MEM':
            mem.append((parts[1], parts[2], *map(int, parts[3:])))
    return dict(peak=peak, hits=hits, mem=mem)


def resolve(binary, addrs):
    addrs = sorted({int(a, 16) for a in addrs if a and a != '(nil)'})
    if not addrs:
        return {}
    resolved = {}
    for k in range(0, len(addrs), 128):
        chunk = addrs[k:k + 128]
        cmd = ['addr2line', '-a', '-f', '-i', '-e', str(binary)] + ['0x%x' % a for a in chunk]
        p = subprocess.run(cmd, capture_output=True, text=True)
        cur = None
        names = []
        for line in p.stdout.splitlines():
            if re.match(r'^0x[0-9a-fA-F]+$', line.strip()):
                if cur is not None:
                    resolved['0x%x' % cur] = names
                cur = int(line.strip(), 16)
                names = []
            elif cur is not None and line.strip() and not re.match(r'^[^:]+:\d+', line):
                names.append(line.strip())
        if cur is not None:
            resolved['0x%x' % cur] = names
    return resolved


def category(fn):
    f = (fn or '').lower()
    if any(x in f for x in ('stdin', 'read_stdin', 'file_read', 'file_iter')):
        return 'input bytes'
    if any(x in f for x in ('obj_new', 'pool_refill', 'exception_new', 'obj_ctor',
                            'binaryfile', 'tcpsocket')):
        return 'class objects'
    if any(x in f for x in ('slist', 'olist_push', 'olist_reserve', 'plist', 'pslist',
                            'flist', 'list_push', 'list_reserve', 'list_copy', 'list_store',
                            'keysort', 'perm_apply', 'svec_take', 'split_ws', 'split_sep',
                            'blist', 'numfield', 'sfield', 'list_return', 'list_free', 'olist')):
        return 'list buffers'
    if any(x in f for x in ('str', 'bytes', 'bytearray', 'sarena', 'barena', 'bl_set', 'bl_append',
                            'blk_take', 'encode', 'decode', 'stab')):
        return 'str objects'
    return 'other'


def parse_objdump(binary, source_name='program.c'):
    p = subprocess.run(['objdump', '-d', '-l', str(binary)], capture_output=True, text=True)
    counts = {}
    cur = None
    line_re = re.compile(re.escape(source_name) + r':(\d+)')
    ins_re = re.compile(r'^\s*[0-9a-f]+:\s')
    for line in p.stdout.splitlines():
        m = line_re.search(line)
        if m:
            cur = int(m.group(1))
            continue
        if cur is not None and ins_re.match(line):
            counts[cur] = counts.get(cur, 0) + 1
    return counts


def parse_gcov(path):
    counts = {}
    if not path.exists():
        return counts
    for line in path.read_text(errors='replace').splitlines():
        m = re.match(r'\s*([0-9]+)\*?:\s*(\d+):', line)
        if m:
            counts[int(m.group(2))] = int(m.group(1))
    return counts


def instruction_estimate(text, plain_binary, gcov_path, helper_names, helper_ranges, source_name='program.c'):
    insn = parse_objdump(plain_binary, source_name)
    counts = parse_gcov(gcov_path)
    total = 0
    for line, n in counts.items():
        total += n * insn.get(line, 0)
    per_helper = {}
    for name, start, end in helper_ranges:
        if name not in helper_names:
            continue
        amount = 0
        for line in range(start, end + 1):
            amount += counts.get(line, 0) * insn.get(line, 0)
        per_helper[name] = per_helper.get(name, 0) + amount
    return total, per_helper


def gcov_run(program_c, work, stdin_path, args, env):
    work.mkdir(parents=True, exist_ok=True)
    src = work / 'program.c'
    src.write_text(program_c.read_text())
    out = work / 'program'
    cmd = ['cc'] + compile_flags(program_c) + ['-g', '-fprofile-arcs', '-ftest-coverage',
                                                '-o', str(out), str(src), '-lgcov']
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=str(work))
    if p.returncode != 0:
        return None, p.stderr
    pb = run([str(out)] + args, stdin_path=stdin_path, timeout=3600, env=env)
    if pb.returncode != 0:
        return None, 'coverage run failed'
    g = subprocess.run(['gcov', '-a', '-b', '-c', 'program.c'], capture_output=True,
                       text=True, cwd=str(work))
    cand = work / 'program.c.gcov'
    return (cand, g.stdout + g.stderr) if cand.exists() else (None, g.stdout + g.stderr)


def gen_case(task, work):
    path = REPO / 'lab' / 'compare' / 'tasks' / task / 'gen.py'
    spec = importlib.util.spec_from_file_location('gen_' + task, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if task == 'tree_fold':
        perf_ops = ['stats', 'total', 'level 6', 'find leaf', 'sort', 'find qqqqqqqqqqqqqqqq',
                    'prune 40', 'stats', 'fold', 'stats', 'cut mid', 'mirror', 'level 3',
                    'find x+y', 'sort', 'stats', 'print']
        tree = mod.random_tree(random.Random(1), TREE_N, chain=0.35)
        perf = ('perf', mod.doc(tree, *perf_ops), [])
    else:
        _, _, perf = mod.cases(random.Random(1))
    name, data, args = perf
    inp = work / 'input'
    inp.write_bytes(data)
    args = [a.replace('{input}', str(inp)) for a in args]
    stdin_path = str(inp) if getattr(mod, 'STDIN', False) else None
    return stdin_path, args, len(data)


def reference_output(task, stdin_path, args, work):
    ref = REPO / 'lab' / 'compare' / 'tasks' / task / 'reference.py'
    out = work / 'ref.out'
    p = run([sys.executable, '-B', str(ref)] + args, stdin_path=stdin_path,
            out_path=out, timeout=3600)
    return p.returncode, out.read_bytes()


def parse_rss(err_path, wall):
    try:
        text = Path(err_path).read_text(errors='replace')
    except OSError:
        return None
    m = re.search(r'Maximum resident set size \(kbytes\):\s*(\d+)', text)
    return int(m.group(1)) if m else None


def measure(label, source, work, stdin_path, args, expected, is_task):
    rec = dict(name=label, kind='task' if is_task else 'prog')
    program_c_plain = work / 'plain.c'
    (work).mkdir(parents=True, exist_ok=True)
    p, dbg_c = build(source, work / 'build', work / 'prog', debug=True)
    if p.returncode != 0 or not dbg_c.exists():
        rec['error'] = ('build failed: ' + (p.stderr.decode('utf8', 'replace')[-400:]))
        return rec
    text = dbg_c.read_text()
    rec['fallback'] = 'general path' in p.stderr.decode('utf8', 'replace')
    helpers, names = find_helpers(text)
    rec['helpers'] = names
    rec['helper_lines'] = {name: start for name, _, start in helpers}

    plain_out = work / 'plain.out'
    time_err = work / 'time.err'
    t = run(['/usr/bin/time', '-v', '-o', str(work / 'time.txt'), '--', str(work / 'prog')] + args,
            stdin_path=stdin_path, out_path=plain_out, err_path=time_err, timeout=3600)
    rec['exit'] = t.returncode
    rec['correct'] = t.returncode == expected[0] and plain_out.read_bytes() == expected[1]
    rec['rss_kib'] = parse_rss(work / 'time.txt', t)
    rec['plain_bytes'] = len(plain_out.read_bytes())
    if not rec['correct']:
        rec['error'] = 'plain output differs from oracle'
        return rec

    inst_text = instrument(text, helpers, names)
    cnt_c = work / 'count.c'
    cnt_c.write_text(inst_text)
    flags = compile_flags(dbg_c)
    cnt_bin = work / 'count'
    cp = subprocess.run(['cc'] + flags + ['-g'] + COUNT_FLAGS + ['-o', str(cnt_bin), str(cnt_c)],
                        capture_output=True, text=True)
    if cp.returncode != 0:
        rec['error'] = 'counting build failed: ' + cp.stderr[-500:]
        return rec
    counts_path = work / 'counts.txt'
    env = dict(os.environ, RC_COUNTS=str(counts_path))
    cnt_out = work / 'count.out'
    cr = run([str(cnt_bin)] + args, stdin_path=stdin_path, out_path=cnt_out,
             env=env, timeout=3600)
    rec['count_correct'] = cr.returncode == 0 and cnt_out.read_bytes() == expected[1]
    if not rec['count_correct']:
        rec['error'] = 'counting build changed stdout'
        return rec
    parsed = parse_counts(counts_path)
    rec['peak_live_bytes'] = parsed['peak']
    rec['hits'] = {names[int(k)]: v for k, v in parsed['hits'].items() if int(k) < len(names)}
    for name in names:
        rec['hits'].setdefault(name, 0)

    addrs = []
    for ra0, ra1, *_ in parsed['mem']:
        addrs += [ra0, ra1]
    resolved = resolve(cnt_bin, addrs)
    mem_rows = []
    for ra0, ra1, total, allocs, peak, live, frees, reuse in parsed['mem']:
        chain0 = resolved.get(ra0, ['??'])
        chain1 = resolved.get(ra1, ['??'])
        f0 = chain0[0] if chain0 else '??'
        if 'ail_alloc' in f0 or '__wrap_' in f0:
            chain = chain0[1:] + chain1
        else:
            chain = chain0
        logical = chain[0] if chain else '??'
        cat = 'other'
        for fn in chain:
            if fn in ('memset', 'memcpy', 'memmove', '__memset', '__memcpy', '??'):
                continue
            c = category(fn)
            if c != 'other':
                logical, cat = fn, c
                break
        mem_rows.append(dict(ra0=ra0, ra1=ra1, fn=logical, cat=cat, total=total,
                             allocs=allocs, peak=peak, live=live, frees=frees, reuse=reuse))
    rec['mem_sites'] = mem_rows
    cat = {name: dict(total=0, peak=0, live=0, allocs=0, frees=0, reuse=0) for name in CATS}
    for row in mem_rows:
        c = cat[row['cat']]
        for key in ('total', 'peak', 'live', 'allocs', 'frees', 'reuse'):
            c[key] += row[key]
    rec['mem_categories'] = cat
    rec['tracked_peak'] = sum(c['peak'] for c in cat.values())
    rec['malloc_frees_total'] = sum(row['frees'] for row in mem_rows)
    rec['malloc_allocs_total'] = sum(row['allocs'] for row in mem_rows)
    rec['reuse_pairs'] = sum(row['reuse'] for row in mem_rows)

    est_c = work / 'est.c'
    est_c.write_text(estimation_text(text, helpers))
    plain_bin = work / 'plain-g'
    pg = subprocess.run(['cc'] + flags + ['-g', '-o', str(plain_bin), str(est_c)],
                        capture_output=True, text=True)
    if pg.returncode != 0:
        rec['est_error'] = 'plain -g build failed: ' + pg.stderr[-300:]
        return rec
    gcov_path, gcov_log = gcov_run(est_c, work / 'cov', stdin_path, args, None)
    if gcov_path is None:
        rec['est_error'] = gcov_log[-300:]
        return rec
    ranges = []
    for name, brace, start in helpers:
        ranges.append((name, start, brace_end(text, brace)))
    total_insn, per_helper = instruction_estimate(text, plain_bin, gcov_path, names, ranges, 'est.c')
    rec['est_total_instructions'] = total_insn
    rec['est_helper_instructions'] = per_helper
    rec['est_helper_total'] = sum(per_helper.values())
    rec['est_helper_share'] = (sum(per_helper.values()) / total_insn) if total_insn else None
    return rec


def python_baseline(source, stdin_path, args):
    tfile = Path(tempfile.mkstemp(prefix='rcpy-', suffix='.time')[1])
    try:
        p = run(['/usr/bin/time', '-v', '-o', str(tfile), '--', sys.executable, '-B',
                 str(source)] + args, stdin_path=stdin_path, timeout=3600)
        return p.returncode, parse_rss(tfile, None)
    finally:
        tfile.unlink(missing_ok=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', action='append', default=[])
    ap.add_argument('--out', default=str(HERE / 'PRICE.json'))
    ap.add_argument('--keep', action='store_true')
    args = ap.parse_args()
    root = Path(tempfile.mkdtemp(prefix='rc1-'))
    records = []
    try:
        if not args.only or any(t in args.only for t in TASKS):
            for task in TASKS:
                if args.only and task not in args.only:
                    continue
                work = root / task
                work.mkdir(parents=True)
                sp, ar, nbytes = gen_case(task, work)
                expected = reference_output(task, sp, ar, work)
                rec = measure(task, REPO / 'lab' / 'compare' / 'src' / task / 'typed.py',
                              work, sp, ar, expected, True)
                rec['input_bytes'] = nbytes
                if task == 'tree_fold':
                    main_py = REPO / 'lab' / 'compare' / 'src' / task / 'main.py'
                    rc, rss = python_baseline(main_py, sp, ar)
                    rec['main_py'] = dict(exit=rc, rss_kib=rss)
                records.append(rec)
                print('%-14s %s' % (task, rec.get('error', 'ok')), flush=True)
        for name, source in NEW_PROGS:
            if args.only and name not in args.only:
                continue
            work = root / name
            work.mkdir(parents=True)
            expected = run([sys.executable, '-B', str(source)], timeout=600).stdout
            py_rc = run([sys.executable, '-B', str(source)], timeout=600).returncode
            rec = measure(name, source, work, None, [], (py_rc, expected), False)
            rec['python_rss_kib'] = python_baseline(source, None, [])[1]
            records.append(rec)
            print('%-14s %s' % (name, rec.get('error', 'ok')), flush=True)
    finally:
        if not args.keep:
            shutil.rmtree(root, ignore_errors=True)
    payload = dict(date='2026-11-05', tree_n=TREE_N,
                   icount='unavailable (no CPU PMU; perf_event_open hardware ENOENT)',
                   est_method='gcov line count x static instructions on plain -O2 -g build',
                   programs=records)
    Path(args.out).write_text(json.dumps(payload, indent=1) + '\n')
    print('wrote', args.out)


if __name__ == '__main__':
    main()
