"""tomli TOML parsing vs rtoml (Rust) on the same documents.

CPython and hybrid both use tomli, so their stdout must match byte for byte.  rtoml is the
separate implementation and is the rewrite baseline.
"""
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _impl import LCG, impl, load_hybrid  # noqa: E402

DOCS = 5000


def toml_for(rng, idx):
    parts = [
        'title = "document %d"' % idx,
        'count = %d' % rng.below(100000),
        'ratio = %d.%d' % (rng.below(100), rng.below(100)),
        'enabled = %s' % ('true' if rng.below(2) else 'false'),
        'inline = { x = %d, y = "%s" }' % (rng.below(100), 'v%d' % rng.below(20)),
        'tags = ["%s", "%s", "%s"]' % ('a%d' % rng.below(9), 'b%d' % rng.below(9),
                                       'c%d' % rng.below(9)),
        '[owner]',
        'name = "owner %d"' % idx,
        'ids = [%s]' % ', '.join(str(rng.below(1000)) for _ in range(rng.below(12) + 1)),
        '[owner.nested]',
        'x = %d' % rng.below(1000),
        'y = %d' % rng.below(1000),
        'text = """line one\nline two\nline three"""',
    ]
    for j in range(4 + rng.below(8)):
        parts += [
            '[[items]]',
            'id = %d' % (idx * 100 + j),
            'label = "item %d-%d"' % (idx, j),
            'values = [%s]' % ', '.join('%d.%d' % (rng.below(50), rng.below(100))
                                       for _ in range(rng.below(10) + 1)),
        ]
    return '\n'.join(parts) + '\n'


def documents():
    rng = LCG(998877)
    return [toml_for(rng, i) for i in range(DOCS)]


def main():
    mode = impl()
    docs = documents()
    if mode == 'rust':
        import rtoml
        loads = rtoml.loads
    elif mode == 'hybrid':
        loads = load_hybrid('_parser').loads
    else:
        import tomli
        loads = tomli.loads

    h = hashlib.sha256()
    n_items = 0
    for text in docs:
        parsed = loads(text)
        n_items += len(parsed.get('items', ()))
        h.update(json.dumps(parsed, sort_keys=True, separators=(',', ':'),
                            default=str).encode('utf-8'))
    print('docs', len(docs), 'items', n_items, 'digest', h.hexdigest()[:16])


if __name__ == '__main__':
    main()
