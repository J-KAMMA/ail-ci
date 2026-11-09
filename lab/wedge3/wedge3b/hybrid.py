#!/usr/bin/env python3
"""Build a CPython hybrid of a pip-installed library's hot modules.

    python3 hybrid.py --package DIR --name pkg --modules a.py,b/c.py \
        --profile PROFILE.json [--strip] --work DIR

The package is copied into the work directory (its source is never touched), optionally each
listed module is annotated from an `ail_observe.py` profile, each module is built with
`ail build --cpython`, and the hybrid copies plus the extension modules are assembled into
`WORK/pkg` and `WORK/so`.  `WORK/summary.json` records, per module, the top-level function
count, the accelerated names and every refusal reason the build reported.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

AIL = Path('/home/runner/work/ail-ci/obs5/AIL_CURRENT')
CLI = AIL / 'ail_chatgpt.py'
OBSERVE = AIL / 'ail_observe.py'


def run(cmd, cwd, timeout=900):
    env = {'AIL_NO_CACHE': '1', 'PATH': '/usr/bin:/bin:/usr/local/bin',
           'HOME': '/tmp', 'LANG': 'C.UTF-8'}
    p = subprocess.run([str(c) for c in cmd], cwd=str(cwd), capture_output=True,
                       timeout=timeout, env=env)
    return p.returncode, p.stdout.decode('utf-8', 'replace'), p.stderr.decode('utf-8', 'replace')


def top_level_names(path):
    names = []
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if line.startswith('def '):
            name = line[4:].split('(')[0].strip()
            if name.isidentifier():
                names.append(name)
        elif line.startswith('async def '):
            name = line[10:].split('(')[0].strip()
            if name.isidentifier():
                names.append(name)
    return names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--package', required=True)
    ap.add_argument('--name', required=True)
    ap.add_argument('--modules', required=True)
    ap.add_argument('--profile')
    ap.add_argument('--strip', action='store_true')
    ap.add_argument('--work', required=True)
    args = ap.parse_args()

    pkg = Path(args.package)
    work = Path(args.work)
    if work.exists():
        shutil.rmtree(work)
    (work / 'build').mkdir(parents=True)
    (work / 'so').mkdir()
    (work / 'orig').mkdir()
    ann = work / 'ann'
    shutil.copytree(pkg, ann / args.name)

    modules = [m.strip() for m in args.modules.split(',') if m.strip()]
    summary = {'package': args.name, 'version_source': str(pkg), 'modules': {}, 'observed': bool(args.profile)}
    for rel in modules:
        src = ann / args.name / rel
        stem = Path(rel).stem
        safe = rel.replace('/', '_')[:-3]
        stage = work / 'src' / safe
        stage.mkdir(parents=True, exist_ok=True)
        staged = stage / (stem + '.py')
        if args.profile:
            # functions_for() matches the recorded real path, so read the installed source
            cmd = [sys.executable, OBSERVE, 'annotate', args.profile, pkg / rel, '-o', staged]
            if args.strip:
                cmd.append('--strip')
            rc, so, se = run(cmd, work)
            summary.setdefault('annotate', {})[rel] = {'rc': rc, 'stderr': se[-400:]}
            if rc != 0:
                shutil.copy2(src, staged)
            else:
                shutil.copy2(staged, src)
        else:
            shutil.copy2(src, staged)
        # Build from a directory holding only this module: the generated preamble inserts the
        # source directory into sys.path, and a package directory there would shadow stdlib
        # modules the library imports (`json.py`, `typing.py`).
        build = work / 'build' / safe
        rc, so, se = run([sys.executable, CLI, 'build', '--cpython', staged.name,
                          '-o', build], stage)
        rec = {'rc': rc, 'top_level': top_level_names(staged)}
        if rc != 0:
            rec['error'] = se[-600:]
        else:
            report = json.loads((build / 'build.json').read_text(encoding='utf-8'))
            rec['accelerated'] = sorted(report.get('accelerated') or [])
            rec['rejected'] = report.get('rejected') or {}
            rec['note'] = report.get('note')
            # the module copy and its extension replace the installed ones
            shutil.copy2(build / (stem + '.py'), ann / args.name / rel)
            for so_file in build.glob('_ail_%s_fast*.so' % stem):
                shutil.copy2(so_file, work / 'so' / so_file.name)
            shutil.copy2(build / (stem + '.orig.py'), work / 'orig' / rel.replace('/', '_'))
        summary['modules'][rel] = rec
    # the assembled hybrid package (annotated source + generated module copies)
    (work / 'pkg').mkdir()
    shutil.copytree(ann / args.name, work / 'pkg' / args.name)
    (work / 'summary.json').write_text(json.dumps(summary, indent=1) + '\n', encoding='utf-8')
    total = sum(len(r['top_level']) for r in summary['modules'].values())
    native = sum(len(r.get('accelerated') or []) for r in summary['modules'].values())
    print('modules %d  top-level %d  native %d' % (len(modules), total, native))
    for rel, r in summary['modules'].items():
        print('  %-28s top=%-3d native=%-3d %s' % (
            rel, len(r['top_level']), len(r.get('accelerated') or []),
            ','.join(r.get('accelerated') or [])))


if __name__ == '__main__':
    main()
