#!/usr/bin/env python3
"""Where AIL's extra instructions go, and how much of the hot loop is vectorised.

    python3 lab/roof/attrib.py --out lab/roof/data/attrib [--tasks tree_fold,...]

For each task it emits the C that AIL generates (`compile --debug-dir`), rebuilds it with the
compiler's own flags plus -g, and runs valgrind callgrind. `callgrind_annotate --auto=yes` then
gives Ir per line of the generated C, so the cost of a bounds check, an overflow check, a refcount
update, an allocation or a copy is read off the line it was emitted for, not guessed. The same run
also yields the hot functions; their disassembly gives the fraction of hot instructions that are
vector (AVX/SSE mnemonics on xmm/ymm registers).

The C column runs the identical measurement on main.c. Counts here are for attribution only; the
instruction counts in RESULTS.md come from the cachegrind runs on the real build.
"""
import argparse, ast, importlib.util, json, os, random, re, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AIL = REPO / 'AIL_CURRENT' / 'ail_chatgpt.py'
SRC = REPO / 'lab' / 'compare' / 'src'
GEN = REPO / 'lab' / 'compare' / 'tasks'
AIL_CFLAGS = ['-O2', '-g', '-fno-tree-slp-vectorize', '-ffp-contract=off', '-fopenmp-simd']
C_CFLAGS = ['-O2', '-g', '-std=c11']

CATS = [
    ('overflow', re.compile(r'overflow|\bail_int_|_ck_|\bOL\b')),
    ('bounds', re.compile(r'ail__need_elems|ail_list_get|ail_list_set|ail_slist_get|ail_view|index out of range|\.n\b|ail_bytes_get')),
    ('refcount', re.compile(r'ail_obj_retain|ail_obj_release|retain|release')),
    ('alloc/free', re.compile(r'ail_alloc|malloc|calloc|realloc|ail_sarena|ail_list_(init|free|push)|_free\(')),
    ('copies', re.compile(r'memcpy|memmove|ail_str_|strlen')),
    ('boxing', re.compile(r'ail_tint|ail_flt|ail_obj_new|box')),
]
IR = re.compile(r'^\s*([\d,]+)\s')
LINE = re.compile(r'([\w./+-]+\.c):(\d+)')


def case(name, work):
    spec = importlib.util.spec_from_file_location('g' + name, GEN / name / 'gen.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    _p, _h, perf = m.cases(random.Random('%s-20261012' % name))
    cname, data, args = perf
    path = work / (name + '.bin')
    path.write_bytes(data)
    return dict(stdin=bool(getattr(m, 'STDIN', False)), path=path,
                args=[a.replace('{input}', str(path)) for a in args])


def run(binary, c, out=subprocess.DEVNULL):
    stdin = open(c['path'], 'rb') if c['stdin'] else subprocess.DEVNULL
    try:
        return subprocess.run([str(binary)] + c['args'], stdin=stdin, stdout=out,
                              stderr=subprocess.PIPE, timeout=1800)
    finally:
        if c['stdin']:
            stdin.close()


def build_ail(task, work):
    dbg = work / (task + '.d')
    if dbg.exists():
        import shutil
        shutil.rmtree(dbg)
    out = work / (task + '_ail')
    p = subprocess.run([sys.executable, '-B', str(AIL), 'compile', str(SRC / task / 'typed.py'),
                        '--syntax', 'python', '-o', str(out), '--debug-dir', str(dbg)],
                       capture_output=True, timeout=1800)
    csrc = dbg / 'program.c'
    if p.returncode != 0 or not csrc.is_file():
        return None, None
    exe = work / (task + '_ail_g')
    r = subprocess.run(['gcc'] + AIL_CFLAGS + ['-o', str(exe), str(csrc), '-lm'], capture_output=True)
    return (csrc, exe) if r.returncode == 0 else (csrc, None)


def build_c(task, work):
    exe = work / (task + '_c_g')
    r = subprocess.run(['gcc'] + C_CFLAGS + ['-o', str(exe), str(SRC / task / 'main.c'), '-lm'],
                       capture_output=True)
    return (SRC / task / 'main.c', exe) if r.returncode == 0 else (None, None)


def vec_report(src, exe, work, tag):
    """fopt-info-vec on the source, and the vector share of the hottest functions' disassembly."""
    info = work / (tag + '.vec')
    flags = AIL_CFLAGS if tag.endswith('ail') else C_CFLAGS
    subprocess.run(['gcc'] + [f for f in flags if f != '-g'] +
                   ['-fopt-info-vec-all=' + str(info), '-c', '-o', str(work / (tag + '.o')), str(src)],
                   capture_output=True)
    text = info.read_text(errors='replace') if info.exists() else ''
    vect = len(re.findall(r'loop vectorized', text))
    missed = len(re.findall(r'not vectorized', text))
    return dict(vectorized_loops=vect, not_vectorized=missed)


VEC = re.compile(r'^\s+[0-9a-f]+:\s+((?:[0-9a-f]{2} )+)\s*(\S+)\s*(.*)$')


def disasm_functions(exe, funcs):
    """per-function: total instructions, vector instructions (xmm/ymm operand)."""
    p = subprocess.run(['objdump', '-d', '--no-show-raw-insn', str(exe)], capture_output=True, text=True)
    cur, out = None, {}
    for line in p.stdout.splitlines():
        m = re.match(r'^([0-9a-f]+) <(.+)>:', line)
        if m:
            cur = m.group(2)
            out[cur] = [0, 0]
            continue
        if cur is None or not line.startswith(' '):
            continue
        mm = re.match(r'^\s+[0-9a-f]+:\s+(\S+)\s*(.*)$', line)
        if not mm:
            continue
        out[cur][0] += 1
        if re.search(r'%[xyz]mm', mm.group(2)):
            out[cur][1] += 1
    return {f: out.get(f) for f in funcs if f in out}


def annotate(task, src, exe, c, work, tag):
    cg = work / (tag + '.cg')
    stdin = open(c['path'], 'rb') if c['stdin'] else subprocess.DEVNULL
    try:
        subprocess.run(['valgrind', '--tool=callgrind', '--cache-sim=no', '--branch-sim=no',
                        '--callgrind-out-file=' + str(cg), str(exe)] + c['args'],
                       stdin=stdin, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1800)
    finally:
        if c['stdin']:
            stdin.close()
    ann = subprocess.run(['callgrind_annotate', '--auto=yes', '--threshold=100', '--show=Ir', str(cg)],
                         capture_output=True, text=True)
    (work / (tag + '.annotate.txt')).write_text(ann.stdout)
    rows, hot = [], []
    in_fn = in_src = False
    src_resolved = src.resolve()
    seen_src = set()

    def is_our_source(header_path):
        p = Path(header_path)
        if not p.is_absolute():
            p = Path.cwd() / p
        try:
            if p.resolve() != src_resolved:
                return False
        except OSError:
            if p.name != src.name:
                return False
        # callgrind_annotate can print two headers for one file (absolute and relative to
        # different directories); count the file once so its lines are not summed twice.
        if src_resolved in seen_src:
            return False
        seen_src.add(src_resolved)
        return True

    ir_line = re.compile(r'^\s*([\d,]+)\s+\(\s*[\d.]+%\)\s+(.*)$')
    for line in ann.stdout.splitlines():
        # the annotation ends with a summary ("N (x%) events annotated"); it must not be
        # counted as a source line when the annotated file happens to be the last block.
        if 'events annotated' in line:
            break
        if 'file:function' in line:
            in_fn, in_src = True, False
            continue
        if line.startswith('-- Auto-annotated source:') or line.startswith('-- User-annotated source:'):
            # callgrind records the path relative to its invocation directory for some builds
            # (absolute for others); resolve before comparing.
            in_src = is_our_source(line.split(':', 1)[1].strip())
            in_fn = False
            continue
        m = ir_line.match(line)
        if not m:
            continue
        ir = int(m.group(1).replace(',', ''))
        text = m.group(2)
        if in_fn and '.c:' in text:
            hot.append((ir, text.split(':', 1)[1].split(' [')[0].strip() if ':' in text else text))
        elif in_src and not text.startswith('=>'):
            rows.append((ir, 0, text))
    cg.unlink(missing_ok=True)
    return rows, hot[:12]


def classify(text, cat):
    rx = dict(CATS)[cat]
    return bool(rx.search(text))


def simd_share(dis):
    """vector mnemonics as a share of all instructions in the listed functions."""
    total = sum(v[0] for v in dis.values() if v)
    vec = sum(v[1] for v in dis.values() if v)
    return vec, total, (vec / total if total else 0.0)


def add_delta(report, task):
    """AIL minus C per category, within the attribution build (both langs measured)."""
    a, c = report[task].get('ail'), report[task].get('c')
    if not a or not c or 'by_category' not in a or 'by_category' not in c:
        return
    d = {name: a['by_category'][name] - c['by_category'][name] for name, _ in CATS}
    total = a['total_line_ir'] - c['total_line_ir']
    delta = dict(by_category=d, other=a['other'] - c['other'], total=total)
    try:
        progs = json.loads((HERE / 'data' / 'programs.json').read_text())
        delta['real_extra'] = progs[task]['ail']['instructions'] - progs[task]['c']['instructions']
    except (OSError, KeyError, TypeError):
        pass
    report[task]['delta'] = delta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(HERE / 'data' / 'attrib'))
    ap.add_argument('--tasks', default='berth_sim,chain_relax,echo_pack,ledger_bin,rail_transfer,scar_life,'
                                       'tally_lang,term_rank,ticket_audit,tree_fold')
    ap.add_argument('--only', default='ail', help='ail,c')
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tasks = [t for t in args.tasks.split(',') if t]
    langs = [l for l in args.only.split(',') if l]
    report = {}
    with tempfile.TemporaryDirectory(prefix='attrib-') as tmp:
        work = Path(tmp)
        for task in tasks:
            c = case(task, work)
            report[task] = {}
            for lang in langs:
                src, exe = (build_ail(task, work) if lang == 'ail' else build_c(task, work))
                if src is None or exe is None:
                    report[task][lang] = dict(error='build failed')
                    continue
                tag = '%s_%s' % (task, lang)
                vec = vec_report(src, exe, work, tag)
                rows, hot = annotate(task, src, exe, c, work, tag)
                totals = {name: 0 for name, _ in CATS}
                other = 0
                for ir, line_no, text in rows:
                    hit = False
                    for name, _ in CATS:
                        if classify(text, name):
                            totals[name] += ir
                            hit = True
                    if not hit:
                        other += ir
                funcs = disasm_functions(exe, [h[1] for h in hot[:6]])
                vec_insns, dis_total, vec_frac = simd_share(funcs)
                report[task][lang] = dict(vec, by_category=totals, other=other,
                                          total_line_ir=sum(totals.values()) + other,
                                          hot_functions=hot[:8], hot_disasm=funcs,
                                          hot_simd_insns=vec_insns, hot_disasm_insns=dis_total,
                                          hot_simd_share=round(vec_frac, 4))
                add_delta(report, task)
                print(task, lang, report[task][lang], flush=True)
                (out / 'attrib.json').write_text(json.dumps(report, indent=1) + '\n')
    print('wrote', out / 'attrib.json')


if __name__ == '__main__':
    main()
