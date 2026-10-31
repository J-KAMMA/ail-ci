#!/usr/bin/env python3
"""Fail unless the installed toolchains match lab/compare/toolchains.env; print the versions found.

    python3 lab/compare/check_tools.py [--langs c,rust,go,nim,python]
"""
import argparse, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBE = {'GCC': (['gcc', '--version'], r'\) (\d+\.\d+\.\d+)'), 'RUSTC': (['rustc', '--version'], r'rustc (\d+\.\d+\.\d+)'),
         'GO': (['go', 'version'], r'go(\d+\.\d+(?:\.\d+)?)'), 'NIM': (['nim', '--version'], r'Version (\d+\.\d+\.\d+)'),
         'PYTHON': ([sys.executable, '--version'], r'Python (\d+\.\d+)')}
LANG_OF = {'c': 'GCC', 'rust': 'RUSTC', 'go': 'GO', 'nim': 'NIM', 'python': 'PYTHON'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--langs', default='c,rust,go,nim,python')
    wanted = {LANG_OF[l] for l in parser.parse_args().langs.split(',') if l in LANG_OF}
    pins = dict(line.split('=', 1) for line in (HERE / 'toolchains.env').read_text().splitlines() if '=' in line and line[0] != '#')
    bad = 0
    for key in sorted(wanted):
        cmd, rx = PROBE[key]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            m = re.search(rx, p.stdout + p.stderr)
            found = m.group(1) if m else '?'
        except OSError:
            found = 'missing'
        ok = found == pins[key].strip()
        bad += not ok
        print('%-7s pinned %-8s found %-8s %s' % (key, pins[key].strip(), found, 'ok' if ok else 'MISMATCH'))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
