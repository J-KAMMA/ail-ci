#!/usr/bin/env python3
"""Rewrite the last line of AIL_CURRENT/AIL_REFERENCE.md: the line-number index of
AIL_REFERENCE_MORE.md that sessions use to read one section with `sed -n A,Bp`.

    python3 tools/ref_index.py           # rewrite the index after editing MORE
    python3 tools/ref_index.py --check   # exit 1 if the index is stale

The index is computed by more_index() in AIL_CURRENT/test_ail_reference_examples.py, which also
checks it, so the two cannot disagree.
"""
import sys
from pathlib import Path

CURRENT = Path(__file__).resolve().parent.parent / 'AIL_CURRENT'
sys.path.insert(0, str(CURRENT))
from test_ail_reference_examples import CORE, INDEX_PREFIX, more_index  # noqa: E402


def main():
    text = CORE.read_text(encoding='utf-8')
    lines = text.rstrip('\n').split('\n')
    want = more_index()
    if lines[-1].startswith(INDEX_PREFIX):
        lines[-1] = want
    else:
        lines.append(want)
    new = '\n'.join(lines) + '\n'
    if '--check' in sys.argv[1:]:
        if new != text:
            print('stale MORE index in %s; run python3 tools/ref_index.py' % CORE.name)
            return 1
        return 0
    if new != text:
        CORE.write_text(new, encoding='utf-8')
        print('rewrote the MORE index in %s' % CORE.name)
    return 0


if __name__ == '__main__':
    sys.exit(main())
