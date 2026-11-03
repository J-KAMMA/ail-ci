Lane: codegen

**Owner decisions (2026-11-03):** stripped binary growth up to +1% is allowed only on a task whose instructions drop by at least 1%; on every other task the binary must not grow. The recursion-depth limit keeps its current counting (limit 50,000) and the same firing point; do not change how depth is counted.

# bce s1: BCE switch, audit mode, census tool and boundary probes (no default codegen change)

Repository `https://github.com/J-KAMMA/ail-ci`, branch from `origin/integ`. Time budget: **80 minutes**. Commit and
push after each sub-step (a)–(e); open the PR (base `integ`) after (a). Do not touch `.github/workflows`.
Follow the standing rules in Appendix A.

**Why.** Later steps remove index and recursion checks the compiler proves can never fire. Before any of that
lands we need (1) a switch that turns the new rules off, (2) an audit build that keeps every removed check and
stops loudly if one would have fired, (3) a tool that measures check cost and verifies "no compare-lab number
got worse", and (4) a probe module. This step changes **no generated C in the default build**.

## Changes

(a) **Switch.** In `AIL_CURRENT/python/pkg-v12/ir/passes/__init__.py` add `def bce_enabled(): return
os.environ.get('AIL_BCE', '1').strip().lower() not in ('0', 'off', 'no', 'false')`. Later steps guard every new
rule with it. Nothing uses it yet. Add one line to the module docstring.

(b) **Audit mode** `AIL_BCE_AUDIT=1`, in `AIL_CURRENT/python/pkg-v12/ir/emit_c.py`. Every place that prints an
access in mode `nck` (search `'nck'`: `bytes.get` ~line 741, `plist.get` ~756, `ba.get/ba.set` ~774/778,
byte `span.get/set` ~785/789, numeric `span.get/set` ~825/828, and the ones near lines 1265–1330) must, when
the env var is set, first print one statement
`if (__builtin_expect((uint64_t)(<index>) >= (uint64_t)(<length>), 0)) ail_bce_audit_fail("<function name>", <k>);`
where `<length>` is the length the unchecked access relies on (`(b).n` for bytes, the span's `_n` name, `L->n`,
`B->n`, …) and `<k>` numbers the sites of the function from 0. Write one helper method for it. Add
`ail_bce_audit_fail(const char *fn, int site)` to the runtime as its own part (copy how an existing part such
as `'BYTES'` or `'IRLIST'` is added with `self.parts.add(...)` and where its C text lives): it prints
`AIL-BCE-AUDIT: removed check would fire in <fn> site <site>\n` to stderr and calls `_exit(86)`. With the env
var unset the emitter must produce byte-identical C (the part is not added). `AIL_*` variables are already part
of the build-cache key (`buildcache.build_env`).

(c) **Tool.** Add `lab/beatc/bce_census.py` with exactly the source in Appendix C (`chmod +x`), and one line in
`lab/beatc/` docs if a README lists the tools. Smoke: `python3 lab/beatc/bce_census.py check --base <a worktree
of origin/integ> --tasks echo_pack --out /tmp/c.json` prints `echo_pack/ail same C`, `echo_pack/python same C`,
exit 0.

(d) **Probe module** `AIL_CURRENT/test_ail_bce.py` (register: Appendix A rule 7). Model it on
`AIL_CURRENT/test_ail_range_checks.py` (see how it compiles a source string and gets the CPython expectation;
for `.ail` sources the oracle is `tools/ail2py.py`'s Python under CPython 3.12). Each probe is compiled and run
three ways: default, `AIL_UNIFIED_FORCE=1`, and `AIL_BCE_AUDIT=1`; each must equal CPython in stdout, exit code
and the last stderr line, and the audit build must never exit 86. Probes for this step (rules that exist today):
- `for i in range(len(xs))` read and store; `for i in range(1, len(xs))` reading `xs[i - 1]`; `xs[i + 1]` under
  `if i + 1 < len(xs)`; a bytes scan `while i < n and d[i] != 10 { i += 1 }` with `n = len(d)`;
- out-of-range at every boundary: index `len`, `-len-1` (raises `IndexError: list index out of range`, exit 1),
  `-1`, `-len`, `0`, `len-1` (no raise), on a list, a bytes value and a struct field list;
- a list appended to / popped inside the loop that indexes it (`for i in range(len(xs)) { xs.pop(); print(xs[i]) }`
  must raise at the same iteration as CPython);
- an index parsed from text: `int("9223372036854775808")` used as an index (same stop as today, rule 2).
Keep a `PROBES` list so later steps append to it.

(e) **Audit run of existing proofs.** With `AIL_BCE_AUDIT=1 AIL_NO_CACHE=1`, run every case of the ten tasks:
`for t in berth_sim chain_relax echo_pack ledger_bin rail_transfer scar_life tally_lang term_rank ticket_audit
tree_fold; do AIL_BCE_AUDIT=1 python3 lab/compare/run_task.py --task $t --langs ail --icount none --smoke
--out /tmp/a-$t.json; done` (smoke input plus all public/hidden cases) and
`AIL_BCE_AUDIT=1 python3 tools/difffuzz.py --run --start 0 --count 300 -j 2 --out /tmp/fuzz-audit`. Expect zero
exit-86 runs and no new differences. Record the counts in the DEVLOG entry.

## Done check

- `python3 lab/beatc/bce_census.py check --base /tmp/base --out /tmp/check.json` (all ten tasks, both syntaxes):
  every line `same C`, exit 0 — so every compare-lab number is unchanged by construction.
- `python3 tools/codegen_diff.py --pins` shows no change.
- `tools/par_check.py -j 2 test_ail_bce test_ail_range_checks test_ail_ir_gridbounds test_ail_mixed_bounds
  test_ail_ir_s1 test_ail_ir_s3` pass. Open the PR, wait for all 20 shards.
- DEVLOG entry `## 2026-11-0x -- bce s1: BCE switch, audit mode, census tool (job-<id>)`.

## Stop rule

Stop and report (do not fix) if: any audit run exits 86 (an existing proof is unsound: report the function,
site and program); the default C of any task changes; the audit statement cannot be placed for some `nck` site
without restructuring the emitter (list the sites you could not cover and land the rest); or 80 minutes pass.

## Appendix A: standing rules (owner-approved 2026-10-30)

1. **No regressions.** A program that built and matched CPython before must still do so after, in the default
   build. A loud stop only where the value cannot be computed. When a fast path cannot handle a case, keep the
   old route.
2. **Big values.** Wherever ints come from text, fields or arithmetic, probe values beyond int64 too. Run every
   probe in the default build AND with `AIL_UNIFIED_FORCE=1` and compare both with CPython.
3. **CI before you report.** Push early, open the PR against `integ` of `J-KAMMA/ail-ci`, wait for all 20
   `shard` checks (`gh pr checks <n> -R J-KAMMA/ail-ci`, at most once every 10 minutes). Report only when all
   pass, or say exactly which fail and why.
4. **Stack at most 2 deep.** Branch from integ or from one unmerged PR, never from a stacked PR.
5. **Memory.** Wrap heavy runs in `ulimit -v 1500000`; `tools/par_check.py` at `-j 2` at most; leave no
   background jobs running.
6. Batch `gh` queries; never poll in a tight loop.
7. **Registration.** New test module: add `AIL_CURRENT/tests.d/<module>.txt` containing the module name, `git
   add` it, run `python3 tools/update_manifest.py`, then `python3 tools/update_manifest.py --check`.
8. **Never** read or print credentials, run a broad `pkill`, merge PRs, change repository settings, cancel runs,
   or edit `.github/workflows`. **No compare-lab number may get worse.**

## Appendix B: measuring on a GitHub runner

`perf_event_open` is denied on runners: `sudo apt-get install -y valgrind`; `bce_census.py` then uses callgrind
(`--icount auto`). Base tree: `git worktree add /tmp/base origin/integ`. scar_life's perf input is too long for
callgrind; the tool uses its first public input instead. Measured on 2026-11-03 (perf counter, perf inputs):
removing all index checks saves tally_lang 24.4%, ledger_bin 11.9%, echo_pack 9.5%, tree_fold 7.5%, berth_sim
7.1%, rail_transfer 5.4%, term_rank 3.7%, scar_life 1.2%, ticket_audit 0.9%, chain_relax 0; recursion bookkeeping
12.3% on tally_lang only.

## Appendix C: `lab/beatc/bce_census.py`

```python
#!/usr/bin/env python3
"""Bounds/recursion-check census and the BCE no-regression check for the ten compare-lab tasks.

  python3 lab/beatc/bce_census.py census [--tasks a,b] [--icount perf|callgrind] --out /tmp/census.json
      icount of the AIL build with (base) and without the index checks (nobounds), the recursion-depth
      bookkeeping (nodepth), and both (neither) -- the generated C is edited by regex, as SPEC1 did; every
      variant must print the same bytes and exit code as base (an upper bound, not a legal build).
  python3 lab/beatc/bce_census.py check --base /path/to/base-tree [--tasks ...] [--icount ...] --out f.json
      builds every task's main.ail (and main.py with --syntax python) in the base tree and in this tree;
      tasks whose generated C is byte-identical are "same"; the others are measured (icount, stripped bytes,
      output equal to base). Exit 1 if any changed task has a higher icount or a different output.

icount: tools/icount.c via perf_event when it works, else `valgrind --tool=callgrind` (slow: 50-100x).
scar_life's perf input is ~3.6e11 instructions: under callgrind it runs on the public[0] input instead.
"""
import argparse, hashlib, importlib.util, json, os, random, re, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[2]
TASKS = ['berth_sim', 'chain_relax', 'echo_pack', 'ledger_bin', 'rail_transfer', 'scar_life', 'tally_lang',
         'term_rank', 'ticket_audit', 'tree_fold']
CHK_A = re.compile(r'__builtin_expect\(\(uint64_t\)\s*([\w>\-\.]+)\s*>=\s*\(uint64_t\)\s*([\w>\-\.]+),\s*0\)')
CHK_B = re.compile(r'__builtin_expect\(!\(\(uint64_t\)\s*([\w>\-\.]+)\s*<\s*\(uint64_t\)\s*([\w>\-\.]+)\),\s*0\)')
CHK_C = re.compile(r'__builtin_expect\(\(uint64_t\)\((\w+)\) < \(uint64_t\)\((\w+)\), 1\)')
NUMF = '__builtin_expect(s && (uint64_t)i < (uint64_t)s->n, 1)'
BYTEARRAY = '__builtin_expect(B && B->refs && (uint64_t)index < (uint64_t)B->n, 1)'
DEPTH_IN = re.compile(r'^\s*if \(\+\+ail_depth > AIL_MAX_RECURSION_DEPTH\) ail_die\("recursion depth exceeded"\);\s*$')
DEPTH_OUT = re.compile(r'^\s*ail_depth--;\s*$')


def load_cases(task, small=False):
    spec = importlib.util.spec_from_file_location('gen_' + task, REPO / 'lab/compare/tasks' / task / 'gen.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    public, hidden, perf = m.cases(random.Random('%s-20261012' % task))
    name, data, args = public[0] if small else perf
    p = Path(tempfile.gettempdir()) / ('bce_in_%s_%d.bin' % (task, small))
    p.write_bytes(data)
    return dict(stdin=bool(getattr(m, 'STDIN', False)), path=str(p), args=[a.replace('{input}', str(p)) for a in args])


def _run(cmd, case, env=None):
    stdin = open(case['path'], 'rb') if case['stdin'] else subprocess.DEVNULL
    try:
        return subprocess.run(cmd + case['args'], stdin=stdin, capture_output=True, env=env, timeout=3600)
    finally:
        if case['stdin']:
            stdin.close()


def output(exe, case):
    r = _run([str(exe)], case)
    return r.returncode, hashlib.sha256(r.stdout).hexdigest()


def icount(exe, case, mode):
    if mode == 'perf':
        tool = Path(tempfile.gettempdir()) / 'bce_icount'
        if not tool.exists():
            subprocess.run(['cc', '-O2', '-w', '-include', 'signal.h', '-include', 'stdlib.h', '-o', str(tool),
                            str(REPO / 'tools/icount.c')], check=True)
        r = _run([str(tool), str(exe)], case)
        return int(r.stdout.split()[-1]) if r.returncode == 0 and r.stdout.strip() else None
    r = _run(['valgrind', '--tool=callgrind', '--callgrind-out-file=/dev/null', str(exe)], case)
    m = re.search(rb'Collected : (\d+)', r.stderr)
    return int(m.group(1)) if m else None


def pick_mode(mode):
    if mode != 'auto':
        return mode
    tool = Path(tempfile.gettempdir()) / 'bce_icount'
    if not tool.exists():
        subprocess.run(['cc', '-O2', '-w', '-include', 'signal.h', '-include', 'stdlib.h', '-o', str(tool),
                        str(REPO / 'tools/icount.c')], check=True)
    r = subprocess.run([str(tool), '/bin/true'], capture_output=True)
    return 'perf' if r.returncode == 0 else 'callgrind'


def compile_task(tree, task, work, syntax='ail'):
    """Build with --debug-dir; return (program.c text, gcc command, binary path, native report) or raise."""
    src = Path(tree) / 'lab/compare/src' / task / ('main.ail' if syntax == 'ail' else 'main.py')
    dbg = work / ('dbg_%s_%s' % (task, syntax))
    shutil.rmtree(dbg, ignore_errors=True)
    exe = work / ('%s_%s.bin' % (task, syntax))
    env = dict(os.environ, AIL_CACHE=str(work / 'cache'), TMPDIR=str(work / 'tmp'), AIL_NO_CACHE='1')
    (work / 'tmp').mkdir(exist_ok=True)
    cmd = [sys.executable, '-B', str(Path(tree) / 'AIL_CURRENT/ail_chatgpt.py'), 'compile', str(src), '-o', str(exe),
           '--debug-dir', str(dbg)]
    if syntax == 'python':
        cmd[5:5] = ['--syntax', 'python'] + (['--exact-int'] if task in ('rail_transfer', 'chain_relax') else [])
    r = subprocess.run(cmd, capture_output=True, env=env)
    if r.returncode:
        raise RuntimeError('build failed: ' + r.stderr.decode('utf8', 'replace')[-800:])
    rep = json.load(open(dbg / 'native_report.json'))
    return (dbg / 'program.c').read_text(), rep['operations'][-1]['command'], exe, rep


def gcc(cmd, csrc, out):
    c = list(cmd)
    c[c.index('-o') + 1] = str(out)
    c[max(k for k, x in enumerate(c) if x.endswith('.c'))] = str(csrc)
    r = subprocess.run(c, capture_output=True)
    if r.returncode:
        raise RuntimeError(r.stderr.decode()[-1500:])


def user_lines(rep):
    s = set()
    for g in rep['generated']:
        for f in g.get('functions', []):
            s.update(range(f['c_line_start'] - 1, f['c_line_end']))
    return s


def edit(src, bounds, depth, user):
    out = []
    for k, ln in enumerate(src.split('\n')):
        if bounds:
            ln = CHK_C.sub('1', CHK_B.sub('0', CHK_A.sub('0', ln)))
            ln = ln.replace(NUMF, '__builtin_expect(s != 0, 1)').replace(BYTEARRAY, '__builtin_expect(B && B->refs, 1)')
        if depth and k in user and (DEPTH_IN.match(ln) or DEPTH_OUT.match(ln)):
            ln = ''
        out.append(ln)
    return '\n'.join(out)


def stripped(exe, work):
    t = work / 'strip.tmp'
    shutil.copy(exe, t)
    subprocess.run(['strip', str(t)], capture_output=True)
    return os.path.getsize(t)


def census(args, mode, work):
    res = {}
    for task in args.tasks:
        small = mode == 'callgrind' and task == 'scar_life'
        case = load_cases(task, small)
        src, cmd, exe, rep = compile_task(REPO, task, work)
        user = user_lines(rep)
        rec, ref = dict(input='public0' if small else 'perf'), None
        for name, b, d in (('base', 0, 0), ('nobounds', 1, 0), ('nodepth', 0, 1), ('neither', 1, 1)):
            cs = work / ('v_%s_%s.c' % (task, name))
            cs.write_text(edit(src, b, d, user))
            ve = work / ('v_%s_%s' % (task, name))
            gcc(cmd, cs, ve)
            out = output(ve, case)
            ref = ref or out
            rec[name] = dict(icount=icount(ve, case, mode), same_output=out == ref)
        b = rec['base']['icount']
        for name in ('nobounds', 'nodepth', 'neither'):
            if b and rec[name]['icount']:
                rec[name]['share'] = round(1 - rec[name]['icount'] / b, 4)
        res[task] = rec
        print(task, {k: rec[k].get('share') for k in ('nobounds', 'nodepth', 'neither')},
              'same', all(rec[k]['same_output'] for k in ('nobounds', 'nodepth', 'neither')), flush=True)
    return res, 0


def check(args, mode, work):
    res, bad = {}, 0
    for task in args.tasks:
        for syntax in ('ail', 'python'):
            key = '%s/%s' % (task, syntax)
            try:
                bw, hw = work / 'base', work / 'head'
                bw.mkdir(exist_ok=True); hw.mkdir(exist_ok=True)
                bsrc, _, bexe, _ = compile_task(args.base, task, bw, syntax)
                hsrc, _, hexe, _ = compile_task(REPO, task, hw, syntax)
            except Exception as e:
                res[key] = dict(error=str(e)[:400]); print(key, 'ERROR', str(e)[:200]); bad = 1
                continue
            if bsrc == hsrc:
                res[key] = dict(same_c=True); print(key, 'same C', flush=True)
                continue
            small = mode == 'callgrind' and task == 'scar_life'
            case = load_cases(task, small)
            bo, ho = output(bexe, case), output(hexe, case)
            bi, hi = icount(bexe, case, mode), icount(hexe, case, mode)
            rec = dict(same_c=False, same_output=bo == ho, icount_base=bi, icount_head=hi,
                       ratio=round(hi / bi, 5) if bi and hi else None,
                       stripped_base=stripped(bexe, work), stripped_head=stripped(hexe, work))
            res[key] = rec
            if not rec['same_output'] or not bi or not hi or hi > bi:
                bad = 1
            print(key, rec, flush=True)
    return res, bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['census', 'check'])
    ap.add_argument('--tasks', default=','.join(TASKS))
    ap.add_argument('--icount', default='auto', choices=['auto', 'perf', 'callgrind'])
    ap.add_argument('--base', help='base tree (check)')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    args.tasks = [t for t in args.tasks.split(',') if t]
    mode = pick_mode(args.icount)
    with tempfile.TemporaryDirectory(prefix='bce-') as tmp:
        res, bad = (census if args.cmd == 'census' else check)(args, mode, Path(tmp))
    json.dump(dict(icount=mode, tasks=res), open(args.out, 'w'), indent=1)
    sys.exit(bad)


if __name__ == '__main__':
    main()
```

**Rules for every job.**
- **Load:** you are one of up to five agents on a 16 GB PC. Keep local parallelism at 2 (`-j 2`) and never run the whole suite; the full suite runs on CI after merge.
- **Commits:** commit with explicit `git add` on your branch. Messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- **Forbidden:** push, stash, rebase, reset, and deletion outside /tmp.
- **Records:**
  - New DIFFERENCES rows use placeholder ids `C?-<your branch>-N`.
  - Add a DEVLOG entry at the top with today's date.
  - Register a new test module: if `AIL_CURRENT/tests.d/` exists, add `AIL_CURRENT/tests.d/<module>.txt` containing the module
    name and do NOT edit the tuple in `ail_check.py`; otherwise append it to the `MODULES` tuple.
  - `git add` new files, run `python3 tools/update_manifest.py`, then `--check`. Do not hand-edit `MANIFEST.json` or `manifest.d/`.
- **Required tests:** the targeted modules for what you touch, plus test_ail_safetynet, test_ail_files and test_ail_corpus_findings3. Run them on your final commit, not an earlier one.
- **Mandatory self-check before you report.** A reviewer will repeat it, and past reports were wrong about half the time.
  1. Write probe programs in /tmp/probes/ for every behaviour you changed. Cover the boundaries your implementation implies, not only the example: types, widths, empty, negative, aliasing, values reaching the code through an argument, a list item, an attribute and a dict value, and both builds.
  2. Run each probe with `bash ~/tools/cmp.sh /tmp/probes/<p>.py $PWD`.
  3. Every probe must match CPython or be refused by name.
  4. List the probes and their results in the report.
- **Never claim something works unless a probe or test you ran shows it.** If you did not verify something, say so.
- **Tokens:** use grep -n, narrow reads, and `tail` on long logs.
- **Budget:** stop at the budget note, leaving a committed, consistent state.
- **Report:** keep it brief, with numbers.
- Test data: email addresses only on example.com / example.org (the public export audit rejects any other domain).

**Work in few steps** (each step costs model time):
- Write all probe programs first, then run them together with one command, for example a loop over `bash ~/tools/cmp.sh`, instead of one command per program.
- Search only inside the repository (`grep -rn ... AIL_CURRENT tools`), never across `/home` or `/tmp`.
- Read a file once, using a range that is large enough, instead of many small reads.
- Do not re-run a test that already passed unless you changed code since.

**Where you run:** a GitHub Actions runner (4 cores). Commit your work on the current branch; do not push.
