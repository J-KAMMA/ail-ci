#!/usr/bin/env python3
"""Step 4 evidence: hand-edit generated C for the two chosen mechanism/task pairs.

    python3 lab/beatc/step4.py --out /tmp/step4.json --runs 5

Pair A, automatic parallelism / scar_life: add one OpenMP `parallel for` with reductions to
the generation loop of the generated C. Pair B, restrict / berth_sim: add `restrict` to the
parameters of the already-specialized int64 key-sort helper. The compiler is not changed; the
edit exists only in a /tmp copy of program.c. Both builds are compiled with the same flags.

Base and edited runs are interleaved (their order alternates each round) so a slow patch on the
shared runner does not bias one side; `paired_gain_*` is the median of the per-round base/edited
ratio, which is more robust than the ratio of medians when the load drifts.
"""
import argparse, hashlib, json, shutil, statistics, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import measure

FLAGS = ['-O2', '-fno-tree-slp-vectorize', '-ffp-contract=off', '-fopenmp-simd',
         '-fno-asynchronous-unwind-tables']


def scar_omp(src):
    old = ('                int64_t ir162 = 0LL;\n'
           '                int64_t ir163 = 0LL;\n'
           '                for (int64_t ir164 = 0LL; ir164 < ir60; ir164 += 1) {')
    new = ('                int64_t ir162 = 0LL;\n'
           '                int64_t ir163 = 0LL;\n'
           '                #pragma omp parallel for reduction(+:ir162,ir163) schedule(static)\n'
           '                for (int64_t ir164 = 0LL; ir164 < ir60; ir164 += 1) {')
    assert src.count(old) == 1, 'scar_life generation loop not found'
    return src.replace(old, new), ['-fopenmp']


def berth_restrict(src):
    old = 'static void NAME(int64_t *perm, int64_t *buf, int64_t n, const int64_t *key, int rev) { \\'
    new = ('static void NAME(int64_t *restrict perm, int64_t *restrict buf, int64_t n, '
           'const int64_t *restrict key, int rev) { \\')
    assert src.count(old) == 1, 'int64 key-sort helper not found'
    return src.replace(old, new), []


PAIRS = {
    'scar_life': dict(mechanism='A automatic parallelism', edit=scar_omp),
    'berth_sim': dict(mechanism='B restrict', edit=berth_restrict),
}


def build_variant(gen_c, tag, work, extra):
    src = work / (tag + '.c')
    src.write_text(gen_c)
    out = work / (tag + '.bin')
    p = subprocess.run(['gcc', *FLAGS, *extra, '-o', str(out), str(src), '-lm'], capture_output=True)
    if p.returncode != 0:
        raise SystemExit('%s build failed: %s' % (tag, p.stderr.decode('utf8', 'replace')[-1000:]))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', required=True)
    ap.add_argument('--runs', type=int, default=5)
    ap.add_argument('--tasks', default=','.join(PAIRS))
    args = ap.parse_args()
    tasks = [t for t in args.tasks.split(',') if t]
    with tempfile.TemporaryDirectory(prefix='beatc-step4-') as tmp:
        root = Path(tmp)
        report = dict(runs=args.runs, interleaved=True, pairs=[])
        for task in tasks:
            spec = PAIRS[task]
            work = root / task
            for sub in ('cache', 'tmp'):
                (work / sub).mkdir(parents=True, exist_ok=True)
            case = measure.make_case(task, work)
            expected, _ = measure.reference_output(task, case, work)
            build = measure.build_ail(task, work)
            if not build['ok']:
                report['pairs'].append(dict(task=task, error=build['stderr'][-1000:]))
                continue
            base_src = Path(build['generated']).read_text()
            edited_src, extra = spec['edit'](base_src)
            base = build_variant(base_src, 'base', work, extra)
            edited = build_variant(edited_src, 'edited', work, extra)
            binaries = {'base': base, 'edited': edited}
            rec = dict(task=task, mechanism=spec['mechanism'], edit_added_flags=extra,
                       output_sha256=expected['sha256'], builds={})
            samples = {label: {'one_core': [], 'all_cores': []} for label in binaries}
            # one warm run per affinity discards first-touch effects before any timed run
            for label, binary in binaries.items():
                for affinity, key in (('0', 'one_core'), ('0-3', 'all_cores')):
                    measure.run_once([str(binary)], case, affinity, work, '%s-%s-warm' % (label, key))
            for i in range(args.runs):
                order = [('base', base), ('edited', edited)] if i % 2 == 0 else [('edited', edited), ('base', base)]
                for affinity, key in (('0', 'one_core'), ('0-3', 'all_cores')):
                    for label, binary in order:
                        samples[label][key].append(
                            measure.run_once([str(binary)], case, affinity, work, '%s-%s-%d' % (label, key, i)))
            for label in binaries:
                rec[label] = {}
                for key in ('one_core', 'all_cores'):
                    rec[label][key] = measure.summarize(samples[label][key])
                rec[label]['byte_identical'] = rec[label]['one_core']['sha256'] == [expected['sha256']]
            rec['gain_one_core'] = round(rec['base']['one_core']['wall_ms'] / rec['edited']['one_core']['wall_ms'], 3)
            rec['gain_all_cores'] = round(rec['base']['all_cores']['wall_ms'] / rec['edited']['all_cores']['wall_ms'], 3)
            for key in ('one_core', 'all_cores'):
                rec['paired_gain_' + key] = round(statistics.median(
                    [b['seconds'] / e['seconds'] for b, e in zip(samples['base'][key], samples['edited'][key])]), 3)
            rec['rss_ratio'] = round(rec['edited']['one_core']['rss_kib'] / rec['base']['one_core']['rss_kib'], 3)
            report['pairs'].append(rec)
            print(task, 'gain', rec['gain_one_core'], rec['gain_all_cores'],
                  'paired', rec['paired_gain_one_core'], rec['paired_gain_all_cores'],
                  'edited/base ms', rec['edited']['one_core']['wall_ms'], rec['base']['one_core']['wall_ms'],
                  file=sys.stderr)
        Path(args.out).write_text(json.dumps(report, indent=1) + '\n', encoding='utf8')
    print('wrote', args.out, file=sys.stderr)


if __name__ == '__main__':
    main()
