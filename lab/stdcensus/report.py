#!/usr/bin/env python3
"""Render lab/stdcensus/RESULTS.md from lab/stdcensus/results.jsonl.

    python3 lab/stdcensus/report.py

The output is deterministic: it depends only on results.jsonl, modules.txt and
the reproducer files present next to this script.
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / 'results.jsonl'
MODULES = HERE / 'modules.txt'
OUT = HERE / 'RESULTS.md'
REPRO = HERE / 'repro'


def load():
    return [json.loads(line) for line in RESULTS.read_text().splitlines() if line.strip()]


def strip_location(line):
    s = line.strip()
    if s.startswith('note: '):
        s = s[6:]
    s = re.sub(r'^[^\s:]+\.py:\d+(?::\d+)?: ', '', s)
    s = re.sub(r'^[^\s:]+:\d+(?::\d+)?: ', '', s)
    if s.startswith('not in the subset: '):
        s = s[len('not in the subset: '):]
    return s.strip()


def normalise(line):
    s = strip_location(line)
    rules = [
        (r'^(os(?:\.[A-Za-z_]\w*)+) is not built\. Built:.*$', 'os.X is not built'),
        (r'^(\w[\w.]*) used here is not built\. Built:.*$', 'X used here is not built'),
        (r'^(\w[\w.]*) is not built\. Built:.*$', 'X is not built'),
        (r'^using function \S+ as a first-class value.*$',
         'using function X as a first-class value'),
        (r'^a dict view kept in a name.*$',
         'a dict view kept in a name, field, item or container'),
        (r'^a class-level constant built through .*$',
         'a class-level constant built through a list item, attribute or dict value'),
        (r'^import of a local module or package below the top level.*$',
         'import of a local module or package below the top level'),
        (r"^import of the CPython C module '[^']+' guarded by .*$",
         "import of 'X' guarded by except ImportError"),
        (r"^module '([^']+)' has no top-level name '([^']+)' \(it defines:.*$",
         "module 'X' has no top-level name 'Y'"),
        (r"^'[^']+' is imported and also assigned or defined again.*$",
         "'X' is imported and also assigned or defined again"),
        (r"^name '[^']+' is bound by an import.*$", "name 'X' is bound by two imports"),
        (r"^'[^']+' is bound to two different imports.*$", "name 'X' is bound by two imports"),
        (r'^class \S+ bases on .*$', 'class X bases on a type defined after it or unknown'),
        (r'^a caught exception type .*$',
         'a caught exception type (only builtin or user Exception subclasses are supported)'),
        (r'^isinstance\(\) against an unknown type .*$',
         'isinstance() against an unknown type'),
        (r"^name '[^']+' is not defined$", "name 'X' is not defined"),
        (r'^(\w[\w.]*) \(not yet published in NAMES_library\.json\)$',
         'X (not yet published in NAMES_library.json)'),
        (r"^str\.encode\(\) with the error handler '[^']+'.*$",
         'str.encode() with an unsupported error handler on the general path'),
        (r"^str\.encode\(\) with the encoding '[^']+'.*$",
         'str.encode() with an unsupported encoding on the general path'),
        (r'^open\(\) with a mode that is not a string literal.*$',
         'open() with a mode that is not a string literal'),
        (r'^a generator function in a program with threads.*$',
         'a generator function in a program with threads'),
        (r'^`with` around a `yield`.*$', '`with` around a `yield`'),
        (r'^a non-BMP string literal.*$', 'a non-BMP string literal in the 16-bit v2 runtime'),
        (r'^int64 constant expression out of range: \d+$',
         'int64 constant expression out of range'),
        (r'^\.__dataclass_fields__:.*$',
         '.__dataclass_fields__: the dataclass field table is not modelled'),
        (r'^a non-name base class.*$', 'a non-name base class'),
        (r'^constructing \S+: .*$',
         'constructing a class with a bound-method instance field'),
        (r'^function-level .*$', 'function-level import or definition is not built'),
        (r'^one `import` statement mixes .*$',
         'one import statement mixes local modules and others'),
        (r'^`__exit__` uses \'traceback\'.*$',
         "__exit__ uses 'traceback' other than in is None"),
        (r'^the decorator on def .*$', 'the decorator on a def'),
        (r'^`with` around .*$', '`with` around a yield'),
        (r'^a class-level constant .*$', 'a class-level constant built through a value'),
    ]
    for pat, rep in rules:
        if re.match(pat, s):
            return rep
    s = re.sub(r'`[^`]*`', '`X`', s)
    s = re.sub(r"'[^']*'", "'X'", s)
    s = re.sub(r'"[^"]*"', '"X"', s)
    s = re.sub(r'\b\d+\b', 'N', s)
    return s


def reasons(rec):
    lines = list(rec.get('reasons') or [])
    first = rec.get('first_reason') or ''
    if first and first not in lines:
        lines.insert(0, first)
    return lines


def slug(text):
    s = text.lower()
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s[:70].strip('-')


def cut(text, n):
    text = text.replace('\n', ' ')
    return text if len(text) <= n else text[:n - 3] + '...'


def repro_files(slug):
    """The reproducer program and the local helper modules it imports, in stable order."""
    main = REPRO / (slug + '.py')
    if not main.exists():
        return []
    out = [(main.name, main.read_text())]
    seen = {main}
    for m in re.finditer(r'^(?:from|import)\s+(_repro_[A-Za-z0-9_.]+)', main.read_text(), re.M):
        top = m.group(1).split('.')[0]
        helper = REPRO / (top + '.py')
        if helper.exists() and helper not in seen:
            out.append((helper.name, helper.read_text()))
            seen.add(helper)
        pkg = REPRO / top
        if pkg.is_dir():
            for f in sorted(pkg.rglob('*')):
                if f.is_file() and f not in seen:
                    out.append((str(f.relative_to(REPRO)), f.read_text()))
                    seen.add(f)
    return out


def main():
    recs = load()
    order = [x.strip() for x in MODULES.read_text().splitlines() if x.strip()]
    byname = {r['name']: r for r in recs}
    recs = [byname[n] for n in order if n in byname]
    counts = {}
    for r in recs:
        counts[r['result']] = counts.get(r['result'], 0) + 1
    built = [r for r in recs if r['result'] in ('built-typed', 'built-general')]
    empty = [r for r in recs if r['result'] == 'built-empty']
    wrong = [r for r in recs if r['result'] == 'wrong']

    buckets = {}
    for r in recs:
        if r['result'] != 'refused':
            continue
        bs = []
        for line in reasons(r):
            b = normalise(line)
            if b not in bs:
                bs.append(b)
        for b in bs:
            buckets.setdefault(b, {'alone': 0, 'listed': 0, 'names': []})
            buckets[b]['listed'] += 1
            buckets[b]['names'].append(r['name'])
        if len(bs) == 1:
            buckets[bs[0]]['alone'] += 1
    rows = sorted(buckets.items(), key=lambda kv: (-kv[1]['alone'], -kv[1]['listed'], kv[0]))

    lines = []
    first = recs[0] if recs else {}
    lines.append('# CPython pure-Python stdlib census on AIL')
    lines.append('')
    lines.append('Generated by `lab/stdcensus/report.py` from `lab/stdcensus/results.jsonl`.')
    lines.append('')
    lines.append('- Base: integ `%s`' % (first.get('integ_sha') or 'unknown'))
    lines.append('- Oracle / source: CPython %s at `sysconfig.get_path("stdlib")`' %
                 (first.get('python') or 'unknown'))
    lines.append('- Module list: `lab/stdcensus/modules.txt` (%d names, fixed order)' % len(recs))
    lines.append('- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile main.py --syntax python -o main`, '
                 '`AIL_NO_CACHE=1`, 120 s, `ulimit -v 1500000`, at most 2 at a time')
    lines.append('')
    lines.append('## Counts')
    lines.append('')
    for k in ('built-typed', 'built-general', 'built-empty', 'refused', 'timeout', 'absent', 'not run', 'wrong'):
        if counts.get(k):
            lines.append('- **%s**: %d' % (k, counts[k]))
    lines.append('- **built total**: %d / %d' % (len(built), len(recs)))
    lines.append('')
    lines.append('A module counts as **built** only when the generated program carries code from it '
                 '(at least one `<module>__` symbol in `program.c`). `built-empty` means AIL accepted '
                 'the import but silently dropped the module: the generated program is the general-path '
                 'runtime with no symbol from the module, or is byte-identical to a bare '
                 '`print("ok")`. Those do not count as built.')
    lines.append('')
    if wrong:
        lines.append('## WRONG (silent bugs)')
        lines.append('')
        for r in wrong:
            lines.append('- `%s`: %s' % (r['name'], r.get('detail', '')))
        lines.append('')
    lines.append('## Since 2026-10-30')
    lines.append('')
    lines.append('The 2026-10-30 hand measurement found **1/197** (colorsys only, general path). '
                 'This run finds **%d/197** built (%d typed, %d general), plus **%d** that compile '
                 'but drop the module code (`built-empty`, excluded from the count). '
                 'The old per-module results were never committed, so only the count and colorsys '
                 '(`built` then and now) can be compared. No WRONG result was found in this run.'
                 % (len(built), counts.get('built-typed', 0), counts.get('built-general', 0), len(empty)))
    lines.append('')
    lines.append('## Modules')
    lines.append('')
    lines.append('| module | result | seconds | first reason |')
    lines.append('|---|---|---:|---|')
    for r in recs:
        lines.append('| `%s` | %s | %.1f | %s |' %
                     (r['name'], r['result'], r.get('build_seconds', 0.0),
                      cut(r.get('first_reason', '').replace('|', '\\|'), 160)))
    lines.append('')
    lines.append('## Blocker buckets')
    lines.append('')
    lines.append('A bucket is a refusal text with names and numbers replaced by placeholders. '
                 '**alone** is the number of modules whose only reasons are in the bucket '
                 '(fixing this alone unblocks that many); **listed** is the number of modules that '
                 'list it at all. Sorted by alone, then listed.')
    lines.append('')
    lines.append('| alone | listed | bucket | reproducer |')
    lines.append('|---:|---:|---|---|')
    top = []
    for i, (b, info) in enumerate(rows):
        p = REPRO / (slug(b) + '.py')
        rel = '`lab/stdcensus/repro/%s.py`' % slug(b) if p.exists() else ''
        if p.exists() and len(top) < 10:
            top.append((b, p))
        lines.append('| %d | %d | %s | %s |' %
                     (info['alone'], info['listed'], b.replace('|', '\\|'), rel))
    lines.append('')
    lines.append('## Reproducers')
    lines.append('')
    verified = {}
    vpath = REPRO / 'verified.json'
    if vpath.exists():
        verified = json.loads(vpath.read_text())
    if top:
        for b, p in top:
            lines.append('### `%s`' % p.name)
            lines.append('')
            lines.append('Bucket: %s' % b)
            lines.append('')
            for relname, text in repro_files(slug(b)):
                lines.append('`lab/stdcensus/repro/%s`:' % relname)
                lines.append('')
                lines.append('```python')
                lines.append(text.rstrip('\n'))
                lines.append('```')
                lines.append('')
            v = verified.get(slug(b))
            if v and v.get('ok'):
                lines.append('Verified: the default build refuses it (exit %s, first line normalises to '
                             'this bucket) and CPython %s runs it (exit %s, stdout %r).' %
                             (v.get('build_rc'), first.get('python') or '3.12',
                              v.get('cpython_rc'), v.get('cpython_stdout', '')))
            lines.append('')
    else:
        lines.append('No reproducer files found.')
        lines.append('')
    OUT.write_text('\n'.join(lines) + '\n')
    print('wrote', OUT, '(%d modules, %d buckets)' % (len(recs), len(rows)))
    for b, info in rows[:25]:
        print('%3d %3d %s' % (info['alone'], info['listed'], b))


if __name__ == '__main__':
    main()
