#!/usr/bin/env python3
"""fbregion1: which short-lived objects die inside one loop iteration, and what a
per-iteration region would save.  Measure only; the compiler is never changed.

    python3 lab/mem/region_census.py --census        # 16/16 programs, scratch-instrumented C
    python3 lab/mem/region_census.py --census --only term_rank

Dynamic side.  Each program is built through AIL's default path with `--debug-dir`.  A
*scratch copy* of `program.c` (never the compiler) gets:

  * a `rt_tick(id)` at the top of every `for`/`while` body, so each loop has its own
    iteration counter, and a `{ rt_enter(id); ... rt_leave(); }` bracket around the whole
    loop, so `rt_cur` is the innermost loop that is actually executing at an allocation point
    (`continue`/`break`/normal exit all restore; `rt_popn` is emitted before `return` and
    out-of-loop `goto`, which jump past `rt_leave`);
  * a sequential site id at every call of the AIL allocators that matter here --
    `ail_sarena_alloc` (str payload), `ail__bpay_alloc` (bytes payload), `ail__blk_take`
    (arena block), `ail_obj_new` (class object / tuple) and `ail_alloc`/`ail_alloc_raw`
    (general) -- together with the innermost enclosing loop id and the requested bytes;
  * a hook in the matching release functions (`ail_obj_dealloc`, `ail__blk_release`,
    `ail__bpay_release`) and a `--wrap=free` wrapper.

The pointer table records, per allocation, (site, loop, iteration, bytes).  A free is
*same-iteration* when the allocation's loop counter has not advanced since the alloc:
that is exactly "died inside the iteration of its innermost loop".  An allocation in a
runtime helper (lexical loop 0, e.g. a `bytes`/`str` payload) is attributed to the loop that
is executing at the call, which is the caller's loop; a helper's own loops are bracketed, so
their exit restores the caller's loop.  The peak reported is the maximum, over iterations, of
the bytes of same-iteration-freed allocations in that iteration (an upper bound on the live
bytes a per-iteration region would have to hold), split into all allocations and heap-backed
ones.  The tracked build must print byte-identical stdout and the same exit status as the
plain build; anything else stops the run.

Static side.  The same programs are read as Python.  The rule of the brief is applied:
an allocation in a loop body is iteration-local when its value is never stored into a
field, list, dict, set, global or closure, never returned, never yielded, never put into
an exception, never passed to a parameter that `ir/borrow.py` does not mark borrowed,
and not live across the loop's back edge.  The value's uses are followed in source order
from its binding to the next rebind; a use in the right-hand side of the binding, or in the
loop body before it, can see the previous iteration's value and blocks as a back-edge read.
An allocation lexically inside a lambda/comprehension is blocked (the closure can run after
the iteration).  A temporary is followed through its expression context: a method receiver is
read and dies at the call, an operand is consumed, an argument follows `borrow.analyze`, and a
store/return/raise blocks.  `ir/borrow.py` is imported read-only and `analyze()` is called for
the borrowed-parameter set; `ir/ownership.py` and `ir/effects.py` are imported read-only as the
ownership/effect references the rule names (they operate on the lowered IR, which this
source-level measurement does not build; the AST test above reproduces their escape/liveness
predicate).  A `__del__` class never qualifies.
"""
import argparse
import ast
import importlib.util
import json
import os
import random
import re
import resource
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AIL = REPO / 'AIL_CURRENT' / 'ail_chatgpt.py'
IRPKG = REPO / 'AIL_CURRENT' / 'python' / 'pkg-v12'

TASKS = ['berth_sim', 'chain_relax', 'echo_pack', 'ledger_bin', 'rail_transfer',
         'scar_life', 'tally_lang', 'term_rank', 'ticket_audit', 'tree_fold']
PROGS = ['binarytrees', 'cfold', 'deriv', 'linkedlist', 'objscan', 'rbtree']
TREE_N = 3000000
WORK = Path('/tmp/fbregion1')
MEM_CAP = 1500 * 1024 * 1024

OPS = ['stats', 'total', 'level 6', 'find leaf', 'sort', 'find qqqqqqqqqqqqqqqq', 'prune 40',
       'stats', 'fold', 'stats', 'cut mid', 'mirror', 'level 3', 'find x+y', 'sort', 'stats',
       'print']

# kind ids shared by the C prologue and the Python side
KIND = {'str': 1, 'bpay': 2, 'blk': 3, 'obj': 4, 'alloc': 5}

PROLOGUE = r'''
/* ---- fbregion1 census tracker: scratch copy only, never the compiler ---- */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define RT_SITE 8192
#define RT_LOOP 4096
#define RT_TAB  (1u << 22)
#define RT_TOMB ((void *)1)
#define RT_NK 8

static unsigned long long rt_iter[RT_LOOP];
static unsigned long long rt_it_bytes[RT_LOOP];
static int rt_cur;
static int rt_stack[RT_LOOP];
static int rt_sp;
static unsigned long long rt_it_same[RT_LOOP];
static unsigned long long rt_it_same_heap[RT_LOOP];
static unsigned long long rt_it_same_k[RT_LOOP][RT_NK];
static unsigned long long rt_same_peak;
static unsigned long long rt_same_heap_peak;
static unsigned long long rt_kind_same_peak[RT_NK];
static unsigned long long rt_live_total, rt_live_peak;
static unsigned long long rt_site_alloc[RT_SITE], rt_site_free[RT_SITE], rt_site_same[RT_SITE];
static unsigned long long rt_site_heap[RT_SITE], rt_site_heap_same[RT_SITE];
static unsigned long long rt_kind_heap_same[RT_NK], rt_kind_heap[RT_NK];
static unsigned long long rt_kind_live[RT_NK], rt_kind_peak[RT_NK], rt_kind_same[RT_NK];
static unsigned long long rt_lk[RT_LOOP][RT_NK];
static int rt_site_loop[RT_SITE], rt_site_kind[RT_SITE];
static unsigned long long rt_site_freed_bytes[RT_SITE];
static unsigned long long rt_alloc_total, rt_freed, rt_same_total, rt_overflow;
static unsigned long long rt_kind_alloc[RT_NK], rt_kind_free[RT_NK];

typedef struct { void *p; unsigned long long iter, bytes; int site, loop, heap; } rt_ent;
static rt_ent rt_tab[RT_TAB];
static void *rt_heap_pending;

static unsigned rt_hash(void *p) {
    unsigned long long h = (unsigned long long)(uintptr_t)p >> 4;
    h *= 0x9E3779B97F4A7C15ULL;
    return (unsigned)(h & (RT_TAB - 1));
}
static rt_ent *rt_find(void *p) {
    unsigned i = rt_hash(p);
    for (unsigned k = 0; k < RT_TAB; k++) {
        rt_ent *e = &rt_tab[(i + k) & (RT_TAB - 1)];
        if (e->p == p) return e;
        if (!e->p) return 0;
    }
    return 0;
}
static void rt_insert(void *p, int site, int loop, unsigned long long bytes, int heap) {
    unsigned i = rt_hash(p);
    for (unsigned k = 0; k < RT_TAB; k++) {
        rt_ent *e = &rt_tab[(i + k) & (RT_TAB - 1)];
        if (!e->p || e->p == RT_TOMB) {
            e->p = p; e->site = site; e->loop = loop; e->iter = rt_iter[loop]; e->bytes = bytes;
            e->heap = heap;
            return;
        }
        if (e->p == p) { e->site = site; e->loop = loop; e->iter = rt_iter[loop]; e->bytes = bytes; e->heap = heap; return; }
    }
    rt_overflow++;
}
static void rt_remove(rt_ent *e) { e->p = RT_TOMB; }

static void rt_count(unsigned long long bytes, int kind) {
    rt_kind_alloc[kind] += 1;
    (void)bytes;
}
static void rt_alloc_hook(void *p, int site, int loop, unsigned long long bytes, int kind, int own) {
    int k = kind;
    int is_pool = (kind == 4 && ((bytes + 7) >> 3) <= 32);
    if (is_pool) k = 6;                                 /* pool-backed object: no malloc */
    if (!loop) loop = rt_cur;                           /* a helper called from a loop body */
    rt_site_loop[site] = loop;
    rt_site_kind[site] = k;
    rt_site_alloc[site]++;
    rt_kind_alloc[k]++;
    rt_alloc_total++;
    {
        int heap = (p == rt_heap_pending) && !is_pool;
        rt_heap_pending = 0;
        if (heap) { rt_site_heap[site]++; rt_kind_heap[k]++; }
        if (!loop || !own) return;   /* arena strings are released in bulk, not per pointer */
        rt_insert(p, site, loop, bytes, heap);
    }
    rt_it_bytes[loop] += bytes;
    rt_live_total += bytes;
    if (rt_live_total > rt_live_peak) rt_live_peak = rt_live_total;
    rt_lk[loop][k] += bytes;
    rt_kind_live[k] += bytes;
    if (rt_kind_live[k] > rt_kind_peak[k]) rt_kind_peak[k] = rt_kind_live[k];
}
static void *rt_wrap(void *p, int site, int loop, unsigned long long bytes, int kind) {
    if (p) rt_alloc_hook(p, site, loop, bytes, kind, 1);
    return p;
}
static void *rt_wrap_count(void *p, int site, int loop, unsigned long long bytes, int kind) {
    if (p) rt_alloc_hook(p, site, loop, bytes, kind, 0);
    return p;
}
static void rt_free_hook(void *p) {
    rt_ent *e;
    if (!p) return;
    e = rt_find(p);
    if (!e) return;
    rt_freed++;
    rt_site_free[e->site]++;
    rt_kind_free[rt_site_kind[e->site]]++;
    if (e->loop && e->iter == rt_iter[e->loop]) {
        rt_same_total++;
        rt_site_same[e->site]++;
        rt_kind_same[rt_site_kind[e->site]]++;
        rt_it_same[e->loop] += e->bytes;
        if (rt_it_same[e->loop] > rt_same_peak) rt_same_peak = rt_it_same[e->loop];
        if (e->heap) {
            rt_it_same_heap[e->loop] += e->bytes;
            if (rt_it_same_heap[e->loop] > rt_same_heap_peak)
                rt_same_heap_peak = rt_it_same_heap[e->loop];
        }
        rt_it_same_k[e->loop][rt_site_kind[e->site]] += e->bytes;
        if (rt_it_same_k[e->loop][rt_site_kind[e->site]] >
            rt_kind_same_peak[rt_site_kind[e->site]])
            rt_kind_same_peak[rt_site_kind[e->site]] =
                rt_it_same_k[e->loop][rt_site_kind[e->site]];
        rt_site_freed_bytes[e->site] += e->bytes;
        if (e->heap) { rt_site_heap_same[e->site]++; rt_kind_heap_same[rt_site_kind[e->site]]++; }
        if (rt_it_bytes[e->loop] >= e->bytes) rt_it_bytes[e->loop] -= e->bytes;
        else rt_it_bytes[e->loop] = 0;
        if (rt_live_total >= e->bytes) rt_live_total -= e->bytes;
        else rt_live_total = 0;
        if (rt_lk[e->loop][rt_site_kind[e->site]] >= e->bytes)
            rt_lk[e->loop][rt_site_kind[e->site]] -= e->bytes;
        else
            rt_lk[e->loop][rt_site_kind[e->site]] = 0;
        if (rt_kind_live[rt_site_kind[e->site]] >= e->bytes)
            rt_kind_live[rt_site_kind[e->site]] -= e->bytes;
        else
            rt_kind_live[rt_site_kind[e->site]] = 0;
    }
    rt_remove(e);
}
/* Enter/leave bracket the *whole* loop (`{ rt_enter(id); for (...) {...} rt_leave(); }`), so a
   `continue` does not unbalance the stack and a `break`/normal exit always restores.  rt_cur is
   therefore the innermost loop that is actually executing at an allocation point; a helper's own
   loops push and pop around themselves, and the caller's loop is visible again after they exit.
   `rt_popn` is emitted before a `return` or an out-of-loop `goto`, which jump past rt_leave. */
static void rt_enter(int loop) {
    if (rt_sp < RT_LOOP) rt_stack[rt_sp++] = rt_cur;
    rt_cur = loop;
}
static void rt_leave(void) {
    rt_cur = rt_sp > 0 ? rt_stack[--rt_sp] : 0;
}
static void rt_popn(int n) { while (n-- > 0) rt_leave(); }
static void rt_tick(int loop) {
    if (loop <= 0 || loop >= RT_LOOP) return;
    if (rt_it_bytes[loop] <= rt_live_total) rt_live_total -= rt_it_bytes[loop];
    else rt_live_total = 0;
    rt_it_bytes[loop] = 0;
    for (int k = 0; k < RT_NK; k++) {
        if (rt_lk[loop][k] <= rt_kind_live[k]) rt_kind_live[k] -= rt_lk[loop][k];
        else rt_kind_live[k] = 0;
        rt_lk[loop][k] = 0;
        rt_it_same_k[loop][k] = 0;
    }
    rt_it_same[loop] = 0;
    rt_it_same_heap[loop] = 0;
    rt_iter[loop]++;
}
extern void __real_free(void *);
extern void *__real_malloc(size_t);
extern void *__real_calloc(size_t, size_t);
void *__wrap_malloc(size_t n) { void *p = __real_malloc(n); rt_heap_pending = p; return p; }
void *__wrap_calloc(size_t a, size_t b) { void *p = __real_calloc(a, b); rt_heap_pending = p; return p; }
void __wrap_free(void *p) { rt_heap_pending = 0; rt_free_hook(p); __real_free(p); }
static void rt_dump(void) {
    const char *path = getenv("RT_OUT");
    FILE *f;
    int s;
    if (!path) return;
    f = fopen(path, "w");
    if (!f) return;
    {
        unsigned long long hs = 0;
        for (int k = 0; k < RT_NK; k++) hs += rt_kind_heap_same[k];
        fprintf(f, "TOT refer %llu same %llu peak %llu overflow %llu heapsame %llu samepeak %llu sameheappeak %llu\n",
                rt_alloc_total, rt_same_total, rt_live_peak, rt_overflow, hs, rt_same_peak,
                rt_same_heap_peak);
    }
    for (int k = 0; k < RT_NK; k++)
        if (rt_kind_alloc[k] || rt_kind_free[k])
            fprintf(f, "K %d %llu %llu %llu %llu %llu %llu %llu %llu\n", k, rt_kind_alloc[k],
                    rt_kind_free[k], rt_kind_same[k], rt_kind_peak[k], rt_kind_live[k],
                    rt_kind_heap[k], rt_kind_heap_same[k], rt_kind_same_peak[k]);
    for (s = 0; s < RT_SITE; s++)
        if (rt_site_alloc[s] || rt_site_free[s])
            fprintf(f, "S %d %d %d %llu %llu %llu %llu %llu %llu\n", s, rt_site_kind[s],
                    rt_site_loop[s], rt_site_alloc[s], rt_site_free[s], rt_site_same[s],
                    rt_site_freed_bytes[s], rt_site_heap[s], rt_site_heap_same[s]);
    fclose(f);
}
__attribute__((constructor)) static void rt_start(void) { atexit(rt_dump); }
/* ---- end fbregion1 census tracker ---- */
'''

FUNC_RE = re.compile(r'^(?:static\s+)?(?:inline\s+)?(?:__attribute__\s*\(\([^)]*\)\)\s+)*'
                     r'[A-Za-z_]\w*[\w\s\*]*?\b(\w+)\s*\([^;{}]*\)\s*\{', re.M)

# name -> (kind, bytes arg index, own)
ALLOCS = {
    'ail_obj_new': ('obj', 0, 1),
    'ail_sarena_alloc': ('str', 1, 0),
    'ail__bpay_alloc': ('bpay', 0, 1),
    'ail__blk_take': ('blk', 0, 1),
    'ail_alloc': ('alloc', 0, 1),
    'ail_alloc_raw': ('alloc', 0, 1),
}
FREE_DEFS = ['ail_obj_dealloc', 'ail__blk_release', 'ail__bpay_release']
KINDNAME = {1: 'str', 2: 'bpay', 3: 'blk', 4: 'obj', 5: 'alloc', 6: 'obj_pool'}


def limits():
    resource.setrlimit(resource.RLIMIT_AS, (MEM_CAP, MEM_CAP))


def run(cmd, stdin_path=None, env=None, out_path=None, err_path=None, timeout=3600):
    inp = open(stdin_path, 'rb') if stdin_path else subprocess.DEVNULL
    out = open(out_path, 'wb') if out_path else subprocess.PIPE
    err = open(err_path, 'wb') if err_path else subprocess.PIPE
    try:
        return subprocess.run(cmd, stdin=inp, stdout=out, stderr=err, timeout=timeout,
                              env=env, cwd=str(REPO), preexec_fn=limits)
    finally:
        if stdin_path:
            inp.close()
        if out_path:
            out.close()
        if err_path:
            err.close()


def build(src, work, out):
    work.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    dbg = work / 'dbg'
    if dbg.exists():
        shutil.rmtree(dbg)
    cmd = [sys.executable, '-B', str(AIL), 'compile', str(src), '--syntax', 'python',
           '-o', str(out), '--debug-dir', str(dbg)]
    env = dict(os.environ, PYTHONHASHSEED='0', AIL_NO_CACHE='1')
    p = subprocess.run(cmd, cwd=str(work), capture_output=True, timeout=1800, env=env)
    return p, (dbg / 'program.c')


def compile_flags(program_c):
    report = program_c.parent / 'native_report.json'
    try:
        cmd = json.loads(report.read_text())['operations'][0]['command']
    except Exception:
        return ['-O2', '-fno-asynchronous-unwind-tables']
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


def load_gen(task):
    path = REPO / 'lab' / 'compare' / 'tasks' / task / 'gen.py'
    spec = importlib.util.spec_from_file_location('gen_' + task, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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


# --------------------------------------------------------------------------- dynamic
def scan_c(text):
    """Return loops [(id, kw, open, close)] and function starts [(off, name)]."""
    loops, funcs = [], []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == '/' and i + 1 < n and text[i + 1] == '*':
            j = text.find('*/', i + 2)
            i = n if j < 0 else j + 2
            continue
        if c == '/' and i + 1 < n and text[i + 1] == '/':
            j = text.find('\n', i + 2)
            i = n if j < 0 else j + 1
            continue
        if c in '"\'':
            q = c
            i += 1
            while i < n:
                if text[i] == '\\':
                    i += 2
                    continue
                if text[i] == q:
                    i += 1
                    break
                i += 1
            continue
        if (c.isalpha() or c == '_') and (i == 0 or not (text[i - 1].isalnum() or text[i - 1] == '_')):
            j = i
            while j < n and (text[j].isalnum() or text[j] == '_'):
                j += 1
            word = text[i:j]
            if word in ('for', 'while'):
                k = j
                while k < n and text[k].isspace():
                    k += 1
                if k < n and text[k] == '(':
                    depth = 0
                    while k < n:
                        if text[k] == '(':
                            depth += 1
                        elif text[k] == ')':
                            depth -= 1
                            if depth == 0:
                                break
                        k += 1
                    b = k + 1
                    while b < n and text[b].isspace():
                        b += 1
                    if b < n and text[b] == '{':
                        depth = 0
                        e = b
                        while e < n:
                            if text[e] == '{':
                                depth += 1
                            elif text[e] == '}':
                                depth -= 1
                                if depth == 0:
                                    break
                            e += 1
                        loops.append((len(loops) + 1, i, b, e))
                        i = b
                        continue
            i = j
            continue
        i += 1
    for m in FUNC_RE.finditer(text):
        funcs.append((m.start(), m.group(1)))
    return loops, funcs


def innermost(loops, off):
    best = 0
    best_open = -1
    for lid, _kw, o, c in loops:
        if o < off < c and o > best_open:
            best, best_open = lid, o
    return best


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


def split_args(s):
    out, depth, quote, start = [], 0, None, 0
    for i, c in enumerate(s):
        if quote:
            if c == quote:
                quote = None
            continue
        if c in '"\'':
            quote = c
        elif c in '([{':
            depth += 1
        elif c in ')]}':
            depth -= 1
        elif c == ',' and depth == 0:
            out.append(s[start:i])
            start = i + 1
    out.append(s[start:])
    return out


def function_of(funcs, off):
    name = '?'
    for start, fname in funcs:
        if start <= off:
            name = fname
        else:
            break
    return name


def _scan_words(text):
    """(pos, word) for identifiers outside comments and string/char literals."""
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c == '/' and i + 1 < n and text[i + 1] == '*':
            j = text.find('*/', i + 2)
            i = n if j < 0 else j + 2
            continue
        if c == '/' and i + 1 < n and text[i + 1] == '/':
            j = text.find('\n', i + 2)
            i = n if j < 0 else j + 1
            continue
        if c in '"\'':
            q, i = c, i + 1
            while i < n:
                if text[i] == '\\':
                    i += 2
                    continue
                if text[i] == q:
                    i += 1
                    break
                i += 1
            continue
        if c.isalpha() or c == '_':
            j = i
            while j < n and (text[j].isalnum() or text[j] == '_'):
                j += 1
            out.append((i, text[i:j]))
            i = j
            continue
        i += 1
    return out


def _preprocessor(text, pos):
    start = text.rfind('\n', 0, pos) + 1
    while start < len(text) and text[start] in ' \t':
        start += 1
    return start < len(text) and text[start] == '#'


def _stmt_end(text, pos):
    """The `;` that ends the statement starting at `pos`, at bracket depth 0."""
    depth = 0
    i = pos
    while i < len(text):
        c = text[i]
        if c in '([{':
            depth += 1
        elif c in ')]}':
            depth -= 1
        elif c == ';' and depth == 0:
            return i + 1
        i += 1
    return len(text)


def instrument(text):
    loops, funcs = scan_c(text)
    edits = []           # (start, end, replacement)
    labels = {}
    site = 0
    for lid, kw, o, c in loops:
        edits.append((o + 1, o + 1, ' rt_tick(%d);' % lid))
        # bracket the whole loop: continue cannot skip the exit, break/normal exit reach it
        edits.append((kw, kw, '{ rt_enter(%d); ' % lid))
        edits.append((c + 1, c + 1, ' rt_leave(); }'))
    # returns and out-of-loop gotos jump past rt_leave; pop the loops they abandon
    words = _scan_words(text)
    label_pos = {}
    for idx, (p, w) in enumerate(words):
        k = p + len(w)
        while k < len(text) and text[k] in ' \t\r':
            k += 1
        if k < len(text) and text[k] == ':' and not (k + 1 < len(text) and text[k + 1] == ':'):
            label_pos.setdefault(w, []).append(p)
    for idx, (p, w) in enumerate(words):
        if _preprocessor(text, p):
            continue
        if w == 'return':
            n = sum(1 for lid, kw, o, c in loops if o < p < c)
            if n:
                end = _stmt_end(text, p)
                edits.append((p, end, '{ rt_popn(%d); %s }' % (n, text[p:end])))
        elif w == 'goto' and idx + 1 < len(words):
            tgt = words[idx + 1][1]
            fn = function_of(funcs, p)
            spots = [lp for lp in label_pos.get(tgt, []) if function_of(funcs, lp) == fn]
            if not spots:
                continue
            n = sum(1 for lid, kw, o, c in loops if o < p < c
                    and not any(o < lp < c for lp in spots))
            if n:
                end = _stmt_end(text, p)
                edits.append((p, end, '{ rt_popn(%d); %s }' % (n, text[p:end])))
    for name, (kind, argi, own) in ALLOCS.items():
        needle = name + '('
        i = 0
        while True:
            j = text.find(needle, i)
            if j < 0:
                break
            # skip a definition: `... name(args) {`
            k = find_close(text, j + len(needle) - 1)
            if k < 0:
                break
            b = k + 1
            while b < len(text) and text[b].isspace():
                b += 1
            if b < len(text) and text[b] == '{':
                i = k + 1
                continue
            args = split_args(text[j + len(needle):k])
            if len(args) <= argi:
                i = k + 1
                continue
            site += 1
            loop = innermost(loops, j)
            fname = function_of(funcs, j)
            line = text.count('\n', 0, j) + 1
            labels[site] = {'site': site, 'kind': kind, 'static_loop': loop,
                            'function': fname, 'line': line}
            helper = 'rt_wrap' if own else 'rt_wrap_count'
            rep = '%s(%s(%s), %d, %d, (unsigned long long)(%s), %d)' % (
                helper, name, ','.join(args), site, loop, args[argi].strip(), KIND[kind])
            edits.append((j, k + 1, rep))
            i = k + 1
    # release hooks: insert at the top of the definition body
    for fname in FREE_DEFS:
        m = re.search(r'\n[^\n]*\b' + fname + r'\s*\(([^;{}]*)\)\s*\{', text)
        if not m:
            continue
        words = re.findall(r'[A-Za-z_]\w*', split_args(m.group(1))[0])
        if not words:
            continue
        arg = words[-1]
        pos = m.end()
        edits.append((pos, pos, '\n    rt_free_hook((void *)%s);' % arg))
    # prologue after the first list type
    anchor = text.find('} ail_list;')
    if anchor < 0:
        anchor = text.find('typedef struct { int64_t *p; ail_len_t n, cap; } ail_list;')
    ins = anchor + len('} ail_list;') if anchor >= 0 else 0
    edits.append((ins, ins, '\n' + PROLOGUE + '\n'))
    edits.sort(key=lambda e: (-e[0], -e[1]))
    out = text
    for a, b, rep in edits:
        out = out[:a] + rep + out[b:]
    return out, labels


def one_program(name, source, work, stdin_path, args, dyn_rows):
    plain = work / 'plain'
    p, program_c = build(source, work, plain)
    if p.returncode != 0:
        return {'program': name, 'error': 'plain build failed',
                'stderr': p.stderr.decode('utf8', 'replace')[-800:]}
    flags = compile_flags(program_c)
    pout = work / 'plain.stdout'
    pp = run([str(plain)] + args, stdin_path=stdin_path, out_path=pout,
             err_path=work / 'plain.stderr')
    text, labels = instrument(program_c.read_text())
    scratch = work / 'scratch'
    scratch.mkdir(exist_ok=True)
    (scratch / 'program.c').write_text(text)
    tout = work / 'tracked'
    cp = subprocess.run(['cc'] + flags + ['-w', '-Wl,--wrap=free', '-Wl,--wrap=malloc',
                                          '-Wl,--wrap=calloc', '-o', str(tout),
                                          str(scratch / 'program.c')],
                        capture_output=True, text=True)
    if cp.returncode != 0:
        return {'program': name, 'error': 'tracked compile failed', 'stderr': cp.stderr[-2500:]}
    trk = work / 'tracked.trk'
    env = dict(os.environ, RT_OUT=str(trk))
    tp = run([str(tout)] + args, stdin_path=stdin_path, out_path=work / 'tracked.stdout',
             err_path=work / 'tracked.stderr', env=env)
    same = (pout.read_bytes() == (work / 'tracked.stdout').read_bytes()
            and pp.returncode == tp.returncode)
    entry = {'program': name, 'match': bool(same), 'exit': [pp.returncode, tp.returncode],
             'plain_bytes': len(pout.read_bytes())}
    if not same:
        entry['error'] = 'tracked stdout/exit differs from the plain build'
        return entry
    tot = {}
    kinds = {}
    for line in (trk.read_text().splitlines() if trk.exists() else []):
        f = line.split()
        if f[0] == 'TOT':
            tot = {'referenced': int(f[2]), 'same_iter': int(f[4]), 'peak_bytes': int(f[6]),
                   'overflow': int(f[8]), 'heap_same_iter': int(f[10]),
                   'same_bytes_peak': int(f[12]), 'same_heap_peak': int(f[14])}
        elif f[0] == 'K':
            k = int(f[1])
            kinds[KINDNAME.get(k, str(k))] = {'allocs': int(f[2]), 'frees': int(f[3]),
                                              'same_iter': int(f[4]), 'peak_bytes': int(f[5]),
                                              'heap_allocs': int(f[7]),
                                              'heap_same_iter': int(f[8]),
                                              'same_bytes_peak': int(f[9])}
        elif f[0] == 'S':
            sid = int(f[1])
            lab = dict(labels.get(sid, {'site': sid, 'kind': '?', 'static_loop': 0,
                                        'function': '?', 'line': 0}))
            lab.update({'dynamic_kind': KINDNAME.get(int(f[2]), f[2]),
                        'loop': int(f[3]), 'allocs': int(f[4]), 'frees': int(f[5]),
                        'same_iter': int(f[6]), 'bytes_same_iter': int(f[7]),
                        'heap_allocs': int(f[8]), 'heap_same_iter': int(f[9])})
            dyn_rows.append({'program': name, **lab})
    entry['totals'] = tot
    entry['kinds'] = kinds
    return entry


def census(only=None):
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    dyn_rows, results = [], []
    jobs = [(t, REPO / 'lab' / 'compare' / 'src' / t / 'typed.py', True) for t in TASKS]
    jobs += [(p, REPO / 'lab' / 'rc' / 'progs' / (p + '.py'), False) for p in PROGS]
    for name, src, is_task in jobs:
        if only and only != name:
            continue
        w = WORK / name
        t0 = time.time()
        if is_task:
            stdin_path, args, nbytes = perf_case(name, w)
        else:
            stdin_path, args, nbytes = None, [], 0
        r = one_program(name, src, w, stdin_path, args, dyn_rows)
        r['input_bytes'] = nbytes
        r['seconds'] = round(time.time() - t0, 1)
        results.append(r)
        print(name, r.get('match'), r.get('totals'), r.get('error', ''), flush=True)
    out = {'mode': 'census', 'programs': results,
           'dynamic_sites': sorted(dyn_rows, key=lambda x: (x['program'], x['site']))}
    prev = HERE / 'REGION.json'
    keep = None
    try:
        old = json.loads(prev.read_text())
        keep = {k: v for k, v in old.items() if k not in ('mode', 'programs', 'dynamic_sites')}
    except Exception:
        pass
    if keep:
        out.update(keep)
    prev.write_text(json.dumps(out, indent=1))
    return results


# ---------------------------------------------------------------------------- static
def _load_ir():
    sys.path.insert(0, str(IRPKG))
    try:
        from ir import borrow as B          # noqa: F401  (read-only import, the rule names it)
        from ir import ownership as O      # noqa: F401
        from ir import effects as E        # noqa: F401
        return B, O, E
    except Exception as exc:                 # pragma: no cover - environment guard
        print('ir import failed:', exc, file=sys.stderr)
        return None, None, None


def _classes(tree):
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            out[node.name] = any(isinstance(b, ast.FunctionDef) and b.name == '__del__'
                                 for b in node.body)
    return out


def _func_of(node, funcs):
    best = None
    for f in funcs:
        if f.lineno <= node.lineno <= (getattr(f, 'end_lineno', f.lineno) or f.lineno):
            if best is None or f.lineno >= best.lineno:
                best = f
    return best.name if best else '<module>'


def _loops(tree):
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            out.append(node)
    return out


def _enclosing_loop(loops, node):
    best = None
    for lp in loops:
        if lp.lineno <= node.lineno and node.lineno <= (lp.end_lineno or lp.lineno):
            if lp.lineno <= node.lineno <= (lp.end_lineno or lp.lineno):
                if best is None or lp.lineno >= best.lineno:
                    best = lp
    return best


def _declared_global(tree):
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            out |= set(node.names)
    return out


def _borrowed_for(tree, B):
    try:
        return B.analyze(tree)
    except Exception:
        return {}


READ_ATTRS = frozenset(['get', 'keys', 'values', 'items', 'copy', 'hex', 'upper', 'lower',
                        'strip', 'lstrip', 'rstrip', 'replace', 'join', 'format', 'find',
                        'rfind', 'count', 'index', 'startswith', 'endswith', 'isdigit',
                        'isalpha', 'isupper', 'islower', 'split', 'rsplit', 'decode'])

PARENTS = {}


def _parent(tree, node):
    if not PARENTS:
        for p in ast.walk(tree):
            for c in ast.iter_child_nodes(p):
                PARENTS[id(c)] = p
    return PARENTS.get(id(node))


def _enclosing_function(tree, node):
    best = None
    for f in ast.walk(tree):
        if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if f.lineno <= node.lineno <= (f.end_lineno or f.lineno):
                if best is None or f.lineno >= best.lineno:
                    best = f
    return best


SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ListComp, ast.SetComp,
          ast.DictComp, ast.GeneratorExp)

READ_ATTRS = frozenset(['get', 'keys', 'values', 'items', 'copy', 'hex', 'upper', 'lower',
                        'strip', 'lstrip', 'rstrip', 'replace', 'join', 'format', 'find',
                        'rfind', 'count', 'index', 'startswith', 'endswith', 'isdigit',
                        'isalpha', 'isupper', 'islower', 'split', 'rsplit', 'decode', 'encode'])

FALLBACK_READ = frozenset(['print', 'len', 'str', 'int', 'bytes', 'bytearray', 'list',
                           'tuple', 'repr', 'sorted', 'min', 'max', 'sum', 'any', 'all',
                           'ord', 'chr', 'format', 'hash', 'enumerate', 'range', 'zip'])

PARENTS = {}


def _parent(tree, node):
    if not PARENTS:
        for p in ast.walk(tree):
            for c in ast.iter_child_nodes(p):
                PARENTS[id(c)] = p
    return PARENTS.get(id(node))


def _pos(n):
    return (n.lineno, n.col_offset)


def _end(n):
    return (getattr(n, 'end_lineno', n.lineno) or n.lineno,
            getattr(n, 'end_col_offset', n.col_offset) or n.col_offset)


def _nearest_scope(tree, node):
    """The function/lambda/comprehension whose body lexically contains `node`."""
    cur = node
    for _ in range(400):
        p = _parent(tree, cur)
        if p is None:
            return None
        if isinstance(p, SCOPES):
            return p
        cur = p
    return None


def _in_nested_scope(tree, node, loop):
    """Whether a Lambda/comprehension sits between `node` and the loop body."""
    cur = node
    for _ in range(400):
        p = _parent(tree, cur)
        if p is None:
            return False
        if isinstance(p, SCOPES):
            return True
        if p is loop:
            return False
        cur = p
    return False


def _is_global(scope, name):
    if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for n in ast.walk(scope):
            if isinstance(n, (ast.Global, ast.Nonlocal)) and name in n.names:
                return True
    return False


def _binding(tree, alloc):
    """`(name, target, stmt)` when the allocation is the whole RHS of a plain assignment.

    An operand of a binary operation (`out += str(x)`), an argument or the receiver of a
    call is a temporary and is analysed by its expression context instead."""
    cur, through = alloc, False
    for _ in range(60):
        p = _parent(tree, cur)
        if p is None or isinstance(p, SCOPES):
            return None
        if isinstance(p, ast.Assign):
            if not through and len(p.targets) == 1 and isinstance(p.targets[0], ast.Name):
                return p.targets[0].id, p.targets[0], p
            return None
        if isinstance(p, ast.AnnAssign):
            if not through and p.value is not None and isinstance(p.target, ast.Name):
                return p.target.id, p.target, p
            return None
        if isinstance(p, (ast.AugAssign, ast.NamedExpr)):
            return None
        if isinstance(p, ast.stmt):
            return None
        if isinstance(p, ast.expr) and not isinstance(p, ast.Name):
            through = True
        cur = p
    return None


def _uses_of(tree, name, scope, target, stmt, loop):
    """`(pre_reads, later_loads)` of `name` in the binding's lexical scope.

    `later_loads` stops at the next rebind of the name.  `pre_reads` are loads that can see the
    *previous* iteration's value: a read earlier in the loop body, or one in the right-hand side
    of the binding statement itself (`head = Node(i, head)`), which is the back-edge case."""
    occ = [n for n in ast.walk(tree)
           if isinstance(n, ast.Name) and n.id == name and _nearest_scope(tree, n) is scope]
    occ.sort(key=lambda n: (n.lineno, n.col_offset, n.end_col_offset))
    start, stmt_end = _pos(stmt), _end(stmt)
    pre, subs = [], []
    in_loop = (loop.lineno <= stmt.lineno <= (loop.end_lineno or loop.lineno))
    for n in occ:
        if n is target:
            continue
        p = _pos(n)
        if p < start:
            if in_loop and loop.lineno <= n.lineno <= (loop.end_lineno or loop.lineno):
                pre.append(n)
            continue
        if p < stmt_end:
            if isinstance(n.ctx, ast.Load):
                pre.append(n)
            continue
        if isinstance(n.ctx, ast.Store):
            break
        subs.append(n)
    return pre, subs


def _escape(tree, node, borrowed, funcs, read_only):
    """First way the value at `node` escapes or is retained, as `(why, line)`, else None."""
    cur, through = node, False
    for _ in range(200):
        p = _parent(tree, cur)
        if p is None:
            return None
        if isinstance(p, SCOPES):
            return ('inside/captured by a closure or comprehension', p.lineno)
        if isinstance(p, (ast.Return, ast.Yield, ast.YieldFrom)):
            return ('returned', p.lineno)
        if isinstance(p, ast.Raise):
            return ('put into an exception', p.lineno)
        if isinstance(p, (ast.For, ast.AsyncFor)) and p.iter is cur:
            return ('used as the for-loop iterable (live across the back edge)', p.lineno)
        if isinstance(p, ast.Subscript):
            if isinstance(p.ctx, ast.Store):
                return ('stored into a list/dict/set', p.lineno)
            if p.value is cur:
                through, cur = True, p
                continue
            return None                      # an index expression: the value is only read
        if isinstance(p, ast.Attribute):
            if isinstance(p.ctx, ast.Store):
                return ('stored into a field %s' % p.attr, p.lineno)
            gp = _parent(tree, p)
            if isinstance(gp, ast.Call) and gp.func is p:
                return None                  # receiver of a method: read, result is a new value
            through, cur = True, p
            continue
        if isinstance(p, ast.Assign):
            if p.value is not cur:
                return None
            tgt = p.targets[0] if len(p.targets) == 1 else None
            if isinstance(tgt, ast.Attribute):
                return ('stored into a field %s' % tgt.attr, p.lineno)
            if isinstance(tgt, (ast.Subscript, ast.Tuple, ast.List)):
                return ('stored into a list/dict/set', p.lineno)
            if isinstance(tgt, ast.Name) and not through:
                return ('aliased into another name %s' % tgt.id, p.lineno)
            return None
        if isinstance(p, ast.AnnAssign):
            if p.value is not cur:
                return None
            if isinstance(p.target, ast.Attribute):
                return ('stored into a field %s' % p.target.attr, p.lineno)
            if isinstance(p.target, (ast.Subscript, ast.Tuple, ast.List)):
                return ('stored into a list/dict/set', p.lineno)
            if isinstance(p.target, ast.Name) and not through:
                return ('aliased into another name %s' % p.target.id, p.lineno)
            return None
        if isinstance(p, ast.AugAssign):
            return None                      # the operand is consumed by the operation
        if isinstance(p, ast.Call):
            if p.func is cur:
                return None
            is_arg = cur in p.args or any(k.value is cur for k in p.keywords)
            if not is_arg:
                return None
            fn = p.func
            if isinstance(fn, ast.Attribute):
                if fn.attr in READ_ATTRS:
                    through, cur = True, p
                    continue
                return ('stored into %s()' % fn.attr, p.lineno)
            if isinstance(fn, ast.Name):
                if fn.id in read_only:
                    through, cur = True, p
                    continue
                params = borrowed.get(fn.id)
                if params is None:
                    return ('passed to unknown callee %s' % fn.id, p.lineno)
                idx = p.args.index(cur) if cur in p.args else None
                fdef = next((f for f in funcs if f.name == fn.id), None)
                pname = '?'
                if fdef is not None and idx is not None:
                    names = [a.arg for a in list(fdef.args.posonlyargs) + list(fdef.args.args)]
                    if idx < len(names):
                        pname = names[idx]
                if pname in params:
                    through, cur = True, p
                    continue
                return ('passed to non-borrowed parameter %s.%s' % (fn.id, pname), p.lineno)
            through, cur = True, p
            continue
        if isinstance(p, ast.keyword):
            through, cur = True, p
            continue
        if isinstance(p, (ast.BinOp, ast.BoolOp, ast.Compare, ast.UnaryOp, ast.IfExp,
                          ast.JoinedStr, ast.FormattedValue, ast.NamedExpr)):
            through, cur = True, p
            continue
        if isinstance(p, ast.stmt):
            return None
        through, cur = True, p
    return None


def static_sites(path, program=None):
    global PARENTS
    PARENTS = {}
    src = path.read_text()
    tree = ast.parse(src, filename=str(path))
    B, O, E = _load_ir()
    borrowed = _borrowed_for(tree, B) if B else {}
    read_only = frozenset(getattr(B, 'READ_ONLY_CALLS', FALLBACK_READ)) if B else FALLBACK_READ
    classes = _classes(tree)
    funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    loops = _loops(tree)
    sites = []
    prog = program or (path.stem if 'progs' in str(path) else path.parent.name)

    def kind_of(call):
        fn = call.func
        if isinstance(fn, ast.Name):
            if fn.id in classes:
                return 'obj'
            if fn.id in ('bytes', 'bytearray'):
                return 'bpay'
            if fn.id == 'str':
                return 'str'
            if fn.id == 'tuple':
                return 'tuple'
        if isinstance(fn, ast.Attribute):
            if fn.attr == 'encode':
                return 'bpay'
            if fn.attr in ('hex', 'upper', 'lower', 'strip', 'replace', 'join', 'format'):
                return 'str'
        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.Tuple):
            if any(isinstance(getattr(e, 'ctx', None), ast.Store) for e in node.elts):
                continue                      # an unpacking target, not a value
            up = _parent(tree, node)
            if isinstance(up, ast.Subscript) or (isinstance(up, ast.For) and up.target is node):
                continue
            kind = 'tuple'
        elif isinstance(node, ast.Call):
            kind = kind_of(node)
        else:
            continue
        if kind is None:
            continue
        loop = _enclosing_loop(loops, node)
        fname = _func_of(node, funcs)
        entry = {'program': prog, 'function': fname, 'line': node.lineno, 'kind': kind,
                 'in_loop': loop is not None}
        if loop is None:
            entry.update({'static_iteration_local': False, 'blocked_by': 'not inside a loop'})
            sites.append(entry)
            continue
        if kind == 'obj' and isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and classes.get(node.func.id):
            entry.update({'static_iteration_local': False,
                          'blocked_by': 'class defines __del__'})
            sites.append(entry)
            continue
        scope = _nearest_scope(tree, node)
        if _in_nested_scope(tree, node, loop):
            block = ('inside/captured by a closure or comprehension', node.lineno)
        else:
            bind = _binding(tree, node)
            if bind is None:
                block = _escape(tree, node, borrowed, funcs, read_only)
            else:
                name, target, stmt = bind
                if _is_global(scope, name):
                    block = ('declared global/nonlocal', stmt.lineno)
                else:
                    pre, subs = _uses_of(tree, name, scope, target, stmt, loop)
                    if pre:
                        block = ('live across the loop back edge (read before it is rebound)',
                                 pre[0].lineno)
                    else:
                        block = None
                        for use in subs:
                            if not (loop.lineno <= use.lineno <=
                                    (loop.end_lineno or loop.lineno)):
                                block = ('live past the loop back edge', use.lineno)
                                break
                            why = _escape(tree, use, borrowed, funcs, read_only)
                            if why:
                                block = why
                                break
        entry['static_iteration_local'] = block is None
        entry['blocked_by'] = None if block is None else '%s (line %d)' % (block[0], block[1])
        sites.append(entry)
    return sites


def static_census(only=None):
    programs = []
    for t in TASKS:
        programs.append((t, REPO / 'lab' / 'compare' / 'src' / t / 'typed.py'))
    for p in PROGS:
        programs.append((p, REPO / 'lab' / 'rc' / 'progs' / (p + '.py')))
    out = []
    for name, path in programs:
        if only and only != name:
            continue
        sites = static_sites(path)
        for s in sites:
            s['program'] = name
        out.extend(sites)
    prev = HERE / 'REGION.json'
    doc = {}
    try:
        doc = json.loads(prev.read_text())
    except Exception:
        pass
    doc['static_sites'] = sorted(out, key=lambda x: (x['program'], x['line'], x['kind']))
    prev.write_text(json.dumps(doc, indent=1))
    print('static sites:', len(out), flush=True)


FAMILY = {'bpay': 'bytes', 'alloc': 'bytes', 'blk': 'bytes', 'str': 'bytes',
          'obj': 'obj', 'obj_pool': 'obj', 'tuple': 'tuple'}


def _pyfunc(cfn):
    return cfn[len('ail_new_'):] if cfn.startswith('ail_new_') else cfn


def join_sites(doc):
    """Best-effort: attach dynamic counts to each static site by (function, family)."""
    dyn = doc.get('dynamic_sites', [])
    rows = []
    for s in doc.get('static_sites', []):
        cand = [d for d in dyn if d['program'] == s['program']
                and FAMILY.get(d['dynamic_kind'], d['dynamic_kind']) == FAMILY.get(s['kind'], s['kind'])]
        row = dict(s)
        if cand:
            row['dynamic_sites'] = [d['site'] for d in cand]
            row['dynamic_allocs'] = sum(d['allocs'] for d in cand)
            row['dynamic_same_iter'] = sum(d['same_iter'] for d in cand)
            row['dynamic_heap_same_iter'] = sum(d['heap_same_iter'] for d in cand)
            row['dynamic_yes'] = (row['dynamic_heap_same_iter'] > 0)
            row['dynamic_note'] = 'program/family aggregate' if row['static_iteration_local'] == row['dynamic_yes'] \
                else 'program/family aggregate; static and dynamic disagree'
        else:
            row['dynamic_sites'] = []
            row['dynamic_allocs'] = 0
            row['dynamic_same_iter'] = 0
            row['dynamic_heap_same_iter'] = 0
            row['dynamic_yes'] = None
            row['dynamic_note'] = 'no matching C site (runtime helper or inlined)'
        rows.append(row)
    used = {(r['program'], sid) for r in rows for sid in r['dynamic_sites']}
    for d in dyn:
        if (d['program'], d['site']) in used:
            continue
        rows.append({'program': d['program'], 'function': d['function'], 'line': d['line'],
                     'kind': d['dynamic_kind'], 'in_loop': d['loop'] > 0,
                     'static_iteration_local': None, 'blocked_by': None,
                     'dynamic_sites': [d['site']],
                     'dynamic_allocs': d['allocs'], 'dynamic_same_iter': d['same_iter'],
                     'dynamic_heap_same_iter': d['heap_same_iter'],
                     'dynamic_yes': d['heap_same_iter'] > 0,
                     'dynamic_note': 'C site only (runtime helper)'})
    return rows


def price(only=None):
    doc = json.loads((HERE / 'REGION.json').read_text())
    doc['sites'] = join_sites(doc)
    rc = json.loads((HERE.parents[1] / 'lab' / 'rc' / 'PRICE.json').read_text())
    rcbyname = {p['name']: p for p in rc['programs']}
    rows = []
    for p in doc['programs']:
        if 'error' in p or 'totals' not in p:
            rows.append({'program': p['program'], 'error': p.get('error', 'no measurement')})
            continue
        name = p['program']
        r = rcbyname.get(name, {})
        total = r.get('est_total_instructions')
        rss = r.get('rss_kib')
        if isinstance(rss, list):
            rss = sorted(rss)
            rss = rss[len(rss) // 2] if rss else None
        rss_kib = rss or None
        heap_same = p['totals'].get('heap_same_iter', 0)
        same_peak = p['totals'].get('same_heap_peak', 0)
        heap_allocs = sum(v.get('heap_allocs', 0) for v in p.get('kinds', {}).values())
        s = (heap_same * 170.0 / total) if total else None
        s_all = (heap_allocs * 170.0 / total) if total else None
        if s is None:
            amd = roof = proj = None
        else:
            amd = 1.0 / (1.0 - s)
            roof = 1.0 / (1.0 - 0.6 * s)
            proj = 1.0 + (roof - 1.0) / 2.0
        kinds = p.get('kinds', {})
        rss_share = (same_peak / (rss_kib * 1024.0)) if rss_kib else None
        # The instruction route is NOT computable on this runner: no CPU PMU and no valgrind.
        # `share`, `amdahl`, `roof60` and `halved_projection` are ESTIMATES from rc1's gcov-based
        # denominator and must not be used as the go/no-go instrument (the brief forbids it).
        estimate_go_insn = bool(proj is not None and proj >= 1.03)
        go_insn = None
        go_rss = bool(rss_share is not None and rss_share >= 0.05)
        # A peak made of one huge allocation (input/output/scratch read once) is not
        # per-iteration churn: a region changes its allocator, not its size.
        sites = [x for x in doc.get('dynamic_sites', []) if x['program'] == name and x['same_iter']]
        max_avg = max((x['bytes_same_iter'] / x['same_iter'] for x in sites), default=0)
        bulk_peak = bool(max_avg >= (1 << 20))
        go_rss_churn = bool(go_rss and heap_same >= 1000 and not bulk_peak)
        rows.append({'program': name, 'heap_same_iter_pairs': heap_same,
                     'max_same_iter_site_bytes': max_avg, 'bulk_peak': bulk_peak,
                     'go_rss_churn': go_rss_churn,
                     'heap_allocs': heap_allocs, 'allocator_share_all': s_all,
                     'est_total_instructions': total, 'share': s,
                     'amdahl': amd, 'roof60': roof, 'halved_projection': proj,
                     'estimate_only': True, 'estimate_go_instructions': estimate_go_insn,
                     'heap_peak_bytes': same_peak, 'peak_rss_kib': rss_kib,
                     'rss_share': rss_share,
                     'go_instructions': go_insn,
                     'instruction_route': 'not computable (no PMU, no valgrind)',
                     'go_rss': go_rss,
                     'go': go_rss_churn,
                     'kinds': {k: {'allocs': v['allocs'], 'same_iter': v['same_iter'],
                                    'heap_same_iter': v['heap_same_iter'],
                                    'same_bytes_peak': v.get('same_bytes_peak', 0),
                                    'peak_bytes': v['peak_bytes']} for k, v in kinds.items()}})
    go_programs = [r['program'] for r in rows if r.get('go')]
    mech = [r['program'] for r in rows if r.get('go_rss')]
    doc['price'] = {'method': 'pairs x 170 instructions vs rc1 est_total_instructions '
                              '(gcov-based ESTIMATE, not a calibrated count). No CPU PMU and no '
                              'valgrind on this runner, so the instruction route is NOT '
                              'COMPUTABLE; share/amdahl/roof/halved are estimates only. The '
                              'go/no-go uses the RSS route: same-iteration bytes at peak >= 5% '
                              'of peak RSS, excluding one-shot bulk peaks, on >= 2 programs.',
                    'instruction_route': 'not computable (no PMU, no valgrind)',
                    'rows': rows, 'go_programs': go_programs,
                    'mechanical_go_programs': mech,
                    'go_decision': 'GO' if len(go_programs) >= 2 else 'NO-GO'}
    (HERE / 'REGION.json').write_text(json.dumps(doc, indent=1))
    for r in rows:
        print(r.get('program'), r.get('error', ''),
              'pairs', r.get('heap_same_iter_pairs'),
              's', None if r.get('share') is None else round(100 * r['share'], 3),
              'halved', None if r.get('halved_projection') is None else round(r['halved_projection'], 4),
              'rss%', None if r.get('rss_share') is None else round(100 * r['rss_share'], 2),
              'GO' if r.get('go') else '')
    print('go programs:', go_programs, '->', doc['price']['go_decision'])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--census', action='store_true')
    ap.add_argument('--static', action='store_true')
    ap.add_argument('--price', action='store_true')
    ap.add_argument('--only')
    a = ap.parse_args()
    if a.census:
        census(a.only)
    if a.static:
        static_census(a.only)
    if a.price:
        price(a.only)
    if not (a.census or a.static or a.price):
        ap.print_help()


if __name__ == '__main__':
    main()
