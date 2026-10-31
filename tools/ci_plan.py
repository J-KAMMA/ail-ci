#!/usr/bin/env python3
"""Decide what .github/workflows/tests.yml runs for this event (the `plan` job).

    python3 tools/ci_plan.py                  # reads the event from the environment, prints the plan, writes $GITHUB_OUTPUT
    python3 tools/ci_plan.py --files a b ...  # offline: the smoke modules for these changed files

Two modes (a repository-wide choice made on 2026-10-30 to spare the ~20 shared free runners):
  full   all 20 shards (+ the gpu job): pushes to main/integ, workflow_dispatch, pull requests from cand-* and
         claude-batch-* branches (the merge gates of the automation), pull requests to main, and pull requests
         that carry the label `full-ci`.
  smoke  every other pull request: update_manifest --check, ci_shards --check and a few test modules.
         The modules: the PR's own changed or newly registered test modules; the modules whose test file names a
         changed source file (when that is few); the fixed set below when a changed code file maps to nothing
         cheap.  A PR that only touches docs/lab/bench/generated files runs the two checks alone.

A pull request that reaches integ does so through a cand-*/claude-batch-* branch, whose 20 shards are the gate.

Outputs: mode=full|smoke, modules=<space separated>, gpu=true|false, carry=true|false, reason=<text>.
carry=true means the PR's head only differs from its previous head by a merge of the base (its own diff is
unchanged) and the previous head already passed `smoke`: the smoke job then succeeds without running anything.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FULL_BRANCHES = ('cand-', 'claude-batch-')
FULL_BASES = ('main',)
FULL_LABEL = 'full-ci'
# when a changed code file maps to nothing cheap
FIXED = ('safetynet', 'unified', 'obj_refs', 'virtual_dispatch', 'files')
DEP_MAX_MODULES = 10       # more test files than this name a changed file: it is core, use the fixed set
DEP_MAX_WEIGHT = 2500.0    # relative seconds (tools/ci_shards.json) the mapped modules may add
# changed files that map to no test module on their own (generated, logs, docs, the lab, the CI plumbing)
IGNORED = re.compile(r'^(AIL_CURRENT/(MANIFEST\.json|manifest\.d/.*|tests\.d/.*|DEVLOG\.md|DIFFERENCES\.md)'
                     r'|DEVLOG\.md|DIFFERENCES\.md|tools/ci_shards\.json|LICENSE.*)$')
# a code change: a file whose edit can break a build or a program
CODE = re.compile(r'^(AIL_CURRENT/.*\.(py|c|h|ail|rs|txt|json)|tools/.*\.(py|c|h|json)|\.github/.*)$')
GPU = re.compile(r'gpu|spirv|vulkan', re.I)
# files excluded from the "is my own diff unchanged" comparison: a refresh regenerates them
CARRY_EXCLUDE = [':!AIL_CURRENT/MANIFEST.json', ':!AIL_CURRENT/manifest.d', ':!tools/ci_shards.json']


def git(*args, check=True):
    p = subprocess.run(('git',) + args, cwd=REPO, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if check and p.returncode:
        raise RuntimeError('git %s: %s' % (' '.join(args), p.stderr.strip()))
    return p.stdout


def all_modules():
    sys.path.insert(0, str(REPO / 'tools'))
    import ci_shards
    return set(ci_shards.all_modules())


def weights():
    try:
        return json.loads((REPO / 'tools' / 'ci_shards.json').read_text(encoding='utf-8')).get('weights', {})
    except (OSError, ValueError):
        return {}


def test_texts():
    texts = {}
    for path in sorted((REPO / 'AIL_CURRENT').glob('test_ail_*.py')):
        try:
            texts[path.stem] = path.read_text(encoding='utf-8', errors='replace')
        except OSError:
            pass
    return texts


def source_refs(path):
    """How many other non-test source files name this one: > 1 means a shared file whose dependents the tests do not show."""
    stem = Path(path).stem
    if not path.endswith('.py'):
        return 0
    pat = re.compile(r'\b%s\b' % re.escape(stem))
    n = 0
    for d in ('AIL_CURRENT', 'tools'):
        for q in (REPO / d).glob('*.py'):
            if q.stem.startswith('test_') or q.stem == stem:
                continue
            try:
                n += bool(pat.search(q.read_text(encoding='utf-8', errors='replace')))
            except OSError:
                pass
    return n


def needle(path):
    name = Path(path).name
    stem = Path(path).stem
    if path.endswith('.py'):
        return re.compile(r'\b%s\b' % re.escape(stem))
    return re.compile(re.escape(name))


def registered_only(diff_text):
    """True when every changed line of a diff just adds/removes a test module name (a MODULES tuple edit)."""
    for line in diff_text.splitlines():
        if line[:1] in '+-' and not line.startswith(('+++', '---')):
            body = line[1:].strip()
            if body and not re.search(r'test_ail_\w+', body):
                return False
    return True


def smoke_plan(changed, ail_check_diff=''):
    """-> (modules, reason) for the changed files of a pull request."""
    modules = all_modules()
    w = weights()
    texts = test_texts()
    chosen = []
    notes = []

    def add(names):
        for n in names:
            if n in modules and n not in chosen:
                chosen.append(n)

    own = []
    for f in changed:
        m = re.match(r'AIL_CURRENT/(test_ail_\w+)\.py$', f)
        if m:
            own.append(m.group(1))
    for line in ail_check_diff.splitlines():
        if line.startswith('+') and not line.startswith('+++'):
            own += re.findall(r'\btest_ail_\w+', line)
    own = [m for m in dict.fromkeys(own) if m in modules]
    add(own)
    if own:
        notes.append('own: ' + ' '.join(own))
    fixed = False
    for f in changed:
        if IGNORED.match(f) or re.match(r'AIL_CURRENT/test_ail_\w+\.py$', f):
            continue
        if f == 'AIL_CURRENT/ail_check.py' and registered_only(ail_check_diff):
            continue
        hits = [m for m, text in texts.items() if m in modules and needle(f).search(text)]
        hits = [m for m in hits if m not in own]
        cost = sum(w.get(m, 40.0) for m in hits)
        shared = source_refs(f) > 1
        if hits and len(hits) <= DEP_MAX_MODULES and cost <= DEP_MAX_WEIGHT:
            add(hits)
            notes.append('%s -> %d module(s)%s' % (f, len(hits), ', shared file: fixed set too' if shared else ''))
            fixed = fixed or (shared and bool(CODE.match(f)))
        elif CODE.match(f):
            fixed = True
            notes.append('%s -> fixed set (%d dependents)' % (f, len(hits)))
    if fixed:
        add(['test_ail_' + n for n in FIXED])
    return chosen, '; '.join(notes) or 'no code change: checks only'


def own_diff_id(commit, base):
    """patch-id of the PR's own diff at `commit` against its merge base with `base` (context-free, minus generated files)."""
    mb = git('merge-base', base, commit).strip()
    diff = git('diff', '-U0', mb, commit, '--', '.', *CARRY_EXCLUDE)
    p = subprocess.run(['git', 'patch-id', '--stable'], cwd=REPO, input=diff, capture_output=True, text=True)
    return p.stdout.split(' ')[0] if p.stdout.strip() else 'empty'


def carry_over(env):
    """True when the previous head of this PR passed `smoke` and the own diff did not change."""
    before, head = env.get('BEFORE', ''), env.get('HEAD_SHA', '')
    if env.get('ACTION') != 'synchronize' or not before or set(before) == {'0'}:
        return False, ''
    if subprocess.run(['git', 'cat-file', '-e', before + '^{commit}'], cwd=REPO).returncode:
        return False, 'previous head not fetched (force push?)'
    base = env.get('BASE_SHA') or 'origin/' + env.get('BASE_REF', 'integ')
    try:
        if own_diff_id(before, base) != own_diff_id(head, base):
            return False, 'own diff changed'
    except RuntimeError as e:
        return False, str(e)
    p = subprocess.run(['gh', 'api', 'repos/%s/commits/%s/check-runs?per_page=100' % (env.get('REPO'), before),
                        '--jq', '[.check_runs[] | select(.name=="smoke") | .conclusion] | join(" ")'],
                       cwd=REPO, capture_output=True, text=True)
    if p.returncode or 'success' not in p.stdout.split():
        return False, 'previous head has no passing smoke'
    return True, 'own diff unchanged since %s, smoke passed there' % before[:8]


def decide(env):
    event, head_ref, base_ref = env.get('EVENT', ''), env.get('HEAD_REF', ''), env.get('BASE_REF', '')
    if event != 'pull_request':
        return 'full', event
    try:
        labels = json.loads(env.get('LABELS') or '[]')
        labels = labels if isinstance(labels, list) else []
    except ValueError:
        labels = []
    if head_ref.startswith(FULL_BRANCHES):
        return 'full', 'merge-gate branch ' + head_ref
    if base_ref in FULL_BASES:
        return 'full', 'pull request to ' + base_ref
    if FULL_LABEL in labels:
        return 'full', 'label ' + FULL_LABEL
    return 'smoke', 'ordinary pull request'


def emit(out):
    line = ''.join('%s=%s\n' % kv for kv in out.items())
    print(line, end='')
    path = os.environ.get('GITHUB_OUTPUT')
    if path:
        with open(path, 'a', encoding='utf-8') as fh:
            fh.write(line)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--files':
        mods, why = smoke_plan(sys.argv[2:])
        print('modules=%s\nreason=%s' % (' '.join(mods), why))
        return 0
    env = os.environ
    mode, why = decide(env)
    out = {'mode': mode, 'modules': '', 'gpu': 'true' if mode == 'full' else 'false', 'carry': 'false'}
    if mode == 'smoke':
        base = env.get('BASE_SHA') or 'origin/' + env.get('BASE_REF', 'integ')
        head = env.get('HEAD_SHA') or 'HEAD'
        mb = git('merge-base', base, head).strip()
        changed = [f for f in git('diff', '--name-only', mb, head).splitlines() if f]
        ac = git('diff', '-U0', mb, head, '--', 'AIL_CURRENT/ail_check.py', check=False)
        mods, why = smoke_plan(changed, ac)
        out['modules'] = ' '.join(mods)
        out['gpu'] = 'true' if any(GPU.search(f) for f in changed) else 'false'
        carry, cwhy = carry_over(env)
        out['carry'] = 'true' if carry else 'false'
        why = '%s | carry: %s' % (why, cwhy or 'n/a') if cwhy else why
        why = '%d file(s) changed; %s' % (len(changed), why)
    out['reason'] = why.replace('\n', ' ')
    emit(out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
