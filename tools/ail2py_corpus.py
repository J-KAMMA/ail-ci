#!/usr/bin/env python3
"""Build every language_examples entry as written and after ail2py conversion.

The corpus is copied twice; in the converted copy every brace ``.ail`` (modules too) becomes a
``.py`` file.  Both copies are built with no extra flags, two at a time, and the debug C files are
compared.  Renamed modules and declaration order do not count as a difference.
"""
import argparse
import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AIL_CURRENT = ROOT / 'AIL_CURRENT'
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(AIL_CURRENT))
import ail2py  # noqa: E402
import ail_syntax  # noqa: E402

CLI = AIL_CURRENT / 'ail_chatgpt.py'
EXAMPLES = AIL_CURRENT / 'language_examples'


def _last_line(data):
    lines = [line.strip() for line in data.decode('utf-8', 'replace').splitlines() if line.strip()]
    return lines[-1] if lines else ''


def _build(source, output, debug, cache):
    output.parent.mkdir(parents=True, exist_ok=True)
    debug.parent.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(debug, ignore_errors=True)
    shutil.rmtree(cache, ignore_errors=True)
    if output.exists():
        output.unlink()
    env = dict(os.environ, AIL_CACHE=str(cache), PYTHONUTF8='1')
    return subprocess.run([sys.executable, '-B', str(CLI), 'compile', str(source),
                           '-o', str(output), '--debug-dir', str(debug)],
                          capture_output=True, timeout=1800, env=env)


def _prepare(root):
    original = root / 'original'
    converted = root / 'converted'
    shutil.copytree(EXAMPLES, original)
    shutil.copytree(EXAMPLES, converted)
    for path in sorted(converted.glob('*.ail')):
        text = path.read_text(encoding='utf-8')
        if not ail_syntax.detect(text):
            continue
        try:
            python = ail2py.convert(text, path)
        except Exception as exc:  # keep the source: the entry's result shows the refusal
            print(f'ail2py_corpus: {path.name}: {exc}', file=sys.stderr)
            continue
        path.with_suffix('.py').write_text(python, encoding='utf-8')
        path.unlink()
    entries = []
    for path in sorted(original.glob('*.ail')):
        if ail2py._has_entry_main(path.read_text(encoding='utf-8')):
            entries.append(path.stem)
    return original, converted, entries


def _one(stem, original, converted, work):
    source = original / (stem + '.ail')
    python = converted / (stem + '.py')
    target = python if python.is_file() else converted / (stem + '.ail')
    cache = work / 'cache' / stem
    built = _build(source, work / 'a' / stem, work / 'da' / stem, cache / 'original')
    converted_built = _build(target, work / 'b' / stem, work / 'db' / stem, cache / 'converted')
    record = {'stem': stem, 'result': '', 'first_difference': '', 'last_stderr': ''}
    if built.returncode != 0 and converted_built.returncode != 0:
        record['result'] = 'both-fail'
    elif built.returncode != 0:
        record['result'] = 'orig-refused'
    elif converted_built.returncode != 0:
        record['result'] = 'py-refused'
    else:
        left = (work / 'da' / stem / 'program.c').read_text(encoding='utf-8').splitlines()
        right = (work / 'db' / stem / 'program.c').read_text(encoding='utf-8').splitlines()
        modules = sorted(ail2py._module_closure(source, source.read_text(encoding='utf-8')))
        names_left = ail2py._undo_module_renames(left, modules)
        names_right = ail2py._undo_module_renames(right, modules)
        if left == right:
            record['result'] = 'identical'
        elif names_left == names_right or ail2py._same_declarations(names_left, names_right):
            record['result'] = 'identical-renamed'
        else:
            record['result'] = 'differ'
            record['first_difference'] = ail2py._difference(left, right)[1]
    stderr = converted_built.stderr or built.stderr
    record['last_stderr'] = _last_line(stderr).replace(str(work), '<work>')
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('-o', '--output', help='write the JSON report here')
    parser.add_argument('-j', '--jobs', type=int, default=2, help='parallel builds (default: 2)')
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory(prefix='ail2py-corpus-') as directory:
        work = Path(directory)
        original, converted, entries = _prepare(work)
        records = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = [pool.submit(_one, stem, original, converted, work) for stem in entries]
            for future in concurrent.futures.as_completed(futures):
                records.append(future.result())
        records.sort(key=lambda item: item['stem'])
    counts = {}
    for record in records:
        counts[record['result']] = counts.get(record['result'], 0) + 1
    report = {'entries': records, 'counts': counts, 'total': len(records)}
    text = json.dumps(report, indent=2) + '\n'
    if args.output:
        Path(args.output).write_text(text, encoding='utf-8')
    else:
        sys.stdout.write(text)
    print(' '.join(f'{name} {counts[name]}' for name in sorted(counts)), file=sys.stderr)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
