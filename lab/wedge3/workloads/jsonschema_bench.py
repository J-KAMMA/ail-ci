"""jsonschema validation vs jsonschema-rs (Rust) on the same schema and documents.

CPython and hybrid both use jsonschema, so their stdout must match byte for byte.  jsonschema-rs
is a separate implementation and is the rewrite baseline.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _impl import LCG, impl, load_hybrid  # noqa: E402

N = 40000

SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "id": {"type": "integer", "minimum": 1, "maximum": 1000000},
        "name": {"type": "string", "minLength": 2, "maxLength": 24,
                 "pattern": "^[a-z][a-z0-9_]*$"},
        "kind": {"enum": ["alpha", "beta", "gamma"]},
        "tags": {"type": "array", "items": {"type": "string"}, "maxItems": 6,
                 "uniqueItems": True},
        "score": {"type": "number", "minimum": 0, "maximum": 100},
        "nested": {
            "type": "object",
            "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}},
            "required": ["x"],
            "additionalProperties": False,
        },
    },
    "required": ["id", "name", "kind"],
    "additionalProperties": False,
    "anyOf": [{"required": ["score"]}, {"required": ["tags"]}],
}

NAMES = ['alpha', 'beta_2', 'gamma_x', 'delta', 'epsilon_9', 'zeta', 'eta', 'theta']
KINDS = ['alpha', 'beta', 'gamma']


def documents():
    rng = LCG(424242)
    out = []
    for i in range(N):
        d = {
            'id': 1 + rng.below(2000000),
            'name': NAMES[rng.below(len(NAMES))] + str(rng.below(1000)),
            'kind': KINDS[rng.below(3)],
            'tags': ['t%d' % rng.below(50) for _ in range(rng.below(6))],
            'score': rng.below(140) / 2.0,
            'nested': {'x': rng.below(100), 'y': rng.below(100)},
        }
        if i % 4 == 0:
            d['tags'] = ['same', 'same'] if i % 8 == 0 else ['only']
        if i % 7 == 0:
            d.pop('kind', None)
        if i % 11 == 0:
            d['name'] = 'Bad Name'
        if i % 13 == 0:
            d['extra'] = 1
        if i % 17 == 0:
            d['nested'] = {'y': 3}
        if i % 19 == 0:
            d['score'] = -5
        out.append(d)
    return out


def main():
    mode = impl()
    docs = documents()
    if mode == 'rust':
        import jsonschema_rs
        validator = jsonschema_rs.Draft202012Validator(SCHEMA)
        valid = 0
        h = 0
        for d in docs:
            ok = validator.is_valid(d)
            valid += ok
            h = (h * 131 + (1 if ok else 2)) & 0xFFFFFFFFFFFFFFFF
        print('valid', valid, 'total', len(docs), 'hash', h)
        return

    import jsonschema
    if mode == 'hybrid':
        kw = load_hybrid('_keywords')
        sys.modules['jsonschema._keywords'] = kw
        jsonschema._keywords = kw
        validators = load_hybrid('validators')
        validator = validators.Draft202012Validator(SCHEMA)
    else:
        validator = jsonschema.Draft202012Validator(SCHEMA)

    valid = 0
    h = 0
    for d in docs:
        ok = validator.is_valid(d)
        valid += ok
        h = (h * 131 + (1 if ok else 2)) & 0xFFFFFFFFFFFFFFFF
    print('valid', valid, 'total', len(docs), 'hash', h)


if __name__ == '__main__':
    main()
