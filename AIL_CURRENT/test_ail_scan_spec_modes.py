"""Spec-following modes of two bundled modules, against CPython.

json_pointer_scan_last_wins(data, pointers, max_depth): a repeated member name selects the LAST
occurrence (on or off the pointer's path), nesting deeper than max_depth raises ValueError.  The
reference is json.loads with the pairs kept, plus a small RFC 6901 walker.

csv_decoder_new_crlf(): only \\n and \\r\\n end a record, a lone \\r is data.  csv_decoder_new() keeps
ending a record at a lone \\r.  Both are compared with an independent index-based reader, fed whole
and one character at a time.  Existing behaviour of json_pointer_scan_bytes is covered by
test_json_pointer_scan.py and of csv_decoder_new by test_csv_stream_cli.py.
"""
import itertools
import json
import os
import random
import re
import shutil
import subprocess
import sys
import unittest

import test_ail_c_objects as support
from test_ail_map_fields import build
import test_json_pointer_scan as base

sys.setrecursionlimit(20000)

JSON_SOURCE = r'''use json_pointer_scan;

fn main() -> int {
    let data: str = read_bytes(sys.argv[1]).decode("utf-8");
    let out: list[str] = [];
    for one in data.split(chr(30)) {
        let fields: list[str] = one.split(chr(31));
        let limit: int = int(fields[0]);
        let pointers: list[str] = [];
        for f in range(2, len(fields)) { pointers.append(fields[f]); }
        let answer: str = "";
        try {
            let found: JsonPointerValues = json_pointer_scan_last_wins(fields[1].encode("utf-8"), pointers, limit);
            if found.error != 0 { answer = "!"; } else { answer = chr(31).join(found.values); }
        } except ValueError { answer = "D"; }
        out.append(answer);
    }
    print("\n".join(out));
    return 0;
}
'''

CSV_SOURCE = r'''use csv_stream;

fn run(text: str, strict: int, step: int) -> str {
    let dec: CsvDecoder = csv_decoder_new();
    if strict == 1 { dec = csv_decoder_new_crlf(); }
    let parts: list[str] = [];
    try {
        let rows: list[CsvRow] = [];
        let i: int = 0;
        while i < len(text) {
            rows.extend(csv_decode_feed(dec, text[i:i + step]));
            i += step;
        }
        rows.extend(csv_decode_finish(dec));
        for row in rows {
            let hexes: list[str] = [];
            for field in row.fields { hexes.append(field.encode("utf-8").hex()); }
            parts.append("R" + "/".join(hexes));
        }
    } except ValueError { return "E"; }
    return " ".join(parts);
}

fn main() -> int {
    let data: str = read_bytes(sys.argv[1]).decode("utf-8");
    let out: list[str] = [];
    for text in data.split(chr(30)) {
        out.append(run(text, 1, 100000));
        out.append(run(text, 1, 1));
        out.append(run(text, 0, 100000));
        out.append(run(text, 0, 1));
    }
    print("\n".join(out));
    return 0;
}
'''


class Invalid(Exception):
    pass


def _no_constant(name):
    raise Invalid(name)


def _check_strings(node):
    if isinstance(node, str):
        if any(0xD800 <= ord(c) <= 0xDFFF for c in node):
            raise Invalid('lone surrogate')
    elif isinstance(node, tuple) and node[0] == 'o':
        for key, value in node[1]:
            _check_strings(key)
            _check_strings(value)
    elif isinstance(node, list):
        for value in node:
            _check_strings(value)


def parse_json(text):
    try:
        tree = json.loads(text, object_pairs_hook=lambda pairs: ('o', pairs),
                          parse_int=lambda s: ('n', s), parse_float=lambda s: ('n', s), parse_constant=_no_constant)
    except (ValueError, RecursionError) as error:
        raise Invalid(str(error))
    _check_strings(tree)
    return tree


def depth_of(node):
    if isinstance(node, list):
        return 1 + max((depth_of(v) for v in node), default=0)
    if isinstance(node, tuple) and node[0] == 'o':
        return 1 + max((depth_of(v) for _, v in node[1]), default=0)
    return 0


ESCAPES = {'"': '\\"', '\\': '\\\\', '\b': '\\b', '\f': '\\f', '\n': '\\n', '\r': '\\r', '\t': '\\t'}


def quote(text):
    return '"' + ''.join(ESCAPES.get(c) or ('\\u%04x' % ord(c) if ord(c) < 32 else c) for c in text) + '"'


def render(node):
    if node is True:
        return 'true'
    if node is False:
        return 'false'
    if node is None:
        return 'null'
    if isinstance(node, str):
        return quote(node)
    if isinstance(node, list):
        return '[' + ','.join(render(v) for v in node) + ']'
    if node[0] == 'n':
        return node[1]
    return '{' + ','.join(quote(k) + ':' + render(v) for k, v in node[1]) + '}'


def select(tree, pointer):
    if pointer == '':
        return tree
    if not pointer.startswith('/') or re.search(r'~(?![01])', pointer):
        raise Invalid('pointer')
    node = tree
    for token in pointer[1:].split('/'):
        token = token.replace('~1', '/').replace('~0', '~')
        if isinstance(node, list):
            if not re.fullmatch(r'0|[1-9][0-9]*', token) or int(token) >= len(node):
                raise Invalid('index')
            node = node[int(token)]
        elif isinstance(node, tuple) and node[0] == 'o':
            found = [v for k, v in node[1] if k == token]
            if not found:
                raise Invalid('member')
            node = found[-1]
        else:
            raise Invalid('scalar')
    return node


def expected_json(limit, text, pointers):
    try:
        tree = parse_json(text)
        if limit and depth_of(tree) > limit:
            return 'D'
    except Invalid:
        return 'D'
    try:
        return '\x1f'.join(render(select(tree, p)) for p in pointers)
    except Invalid:
        return '!'


def pack_json(cases):
    for limit, text, pointers in cases:
        assert '\x1e' not in text + ''.join(pointers) and '\x1f' not in text + ''.join(pointers)
    return '\x1e'.join('\x1f'.join([str(limit), text, *pointers]) for limit, text, pointers in cases).encode('utf8')


def reference_csv(text, legacy):
    """Independent reader: None for an error, else a list of records."""
    n = len(text)
    i = 0
    rows = []

    def ending(at):
        if at < n and text[at] == '\n':
            return 1
        if at < n and text[at] == '\r' and (text[at + 1:at + 2] == '\n'):
            return 2
        if legacy and at < n and text[at] == '\r':
            return 1
        return 0

    while i < n:
        skip = ending(i)
        if skip:
            i += skip
            continue
        fields = []
        while True:
            buf = []
            if i < n and text[i] == '"':
                i += 1
                while True:
                    if i >= n:
                        return None
                    if text[i] == '"':
                        if text[i + 1:i + 2] == '"':
                            buf.append('"')
                            i += 2
                            continue
                        i += 1
                        break
                    buf.append(text[i])
                    i += 1
                if i < n and text[i] != ',' and not ending(i):
                    return None
            else:
                while i < n and text[i] != ',' and not ending(i):
                    if text[i] == '"':
                        return None
                    buf.append(text[i])
                    i += 1
            fields.append(''.join(buf))
            if i < n and text[i] == ',':
                i += 1
                continue
            i += ending(i)
            break
        rows.append(fields)
    return rows


def show_csv(rows):
    if rows is None:
        return 'E'
    return ' '.join('R' + '/'.join(f.encode('utf8').hex() for f in row) for row in rows)


def csv_cases(rnd):
    cases = ['', '\r', '\n', '\r\n', 'a', 'a\r', 'a\rb', 'a\r\nb', 'a\r\r\nb\r', '"a"\r', '"a"\rb', '"a\rb"', '"a\r\nb"\r\n', '\r\r', '\r\n\r\n', '\r,\r', ',\r',
             'a,"b"\r\nc,"d"', 'a,b\rc,d\r\n', '"a"b', 'a"b', '"a', '"a"\r\n', '"a""\r"\r\n"b"', 'é\r😀,\r\n', '"a"\r\r\n']
    cases += [''.join(p) for k in range(1, 7) for p in itertools.product('a,"\r\n', repeat=k)]
    alphabet = ['a', ',', '"', '\r', '\n', '\r\n', 'é', '😀', ' ', '1', '""']
    cases += [''.join(rnd.choice(alphabet) for _ in range(rnd.randrange(0, 16))) for _ in range(6000)]
    return cases


def json_cases(rnd):
    cases = []
    for text, pointers in base.fixed_cases():
        for limit in (0, 2):
            cases.append((limit, text, pointers))
    cases += [
        (0, '{"a":{"b":1},"a":{"b":[2]}}', ['/a/b']), (0, '{"a":[1],"a":5}', ['/a/0']), (0, '{"a":5,"a":[1]}', ['/a/0']),
        (0, '{"a":1,"a":2,"b":{"c":1,"c":2}}', ['/a', '/b/c', '/b', '']), (0, '{"a":{"x":1},"a":{"y":2}}', ['/a/x']),
        (0, '{"a":{"x":1},"a":{"y":2}}', ['/a/y']), (0, '{"a":{"x":1,"x":3},"a":{"y":2}}', ['/a']),
        (0, '{"a":"\\u0061","a":2,"\\u0061":3}', ['/a']), (0, '{"a":1,"b":{"a":1,"a":2},"a":3}', ['/a', '/b/a']),
    ]
    for depth in (999, 1000, 1001, 1002):
        cases.append((1000, '[' * depth + ']' * depth, ['']))
        cases.append((1000, '{"a":' * depth + '0' + '}' * depth, ['']))
        cases.append((1000, '[{"a":' * (depth // 2) + '0' + '}]' * (depth // 2), ['']))
        cases.append((0, '[' * depth + ']' * depth, ['']))
    cases.append((1, '[]', ['']))
    cases.append((1, '[[]]', ['']))
    cases.append((1, '0', ['']))
    cases.append((3, '[[[1,2]]]', ['/0/0/1']))
    cases.append((3, '[[[[1]]]]', ['/0/0/0/0']))
    for _ in range(9000):
        text, pointers = base.make_case(rnd)
        cases.append((rnd.choice([0, 0, 1, 2, 3, 4, 6, 1000]), text, pointers))
    return cases


@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'),
                     'installed C compiler required')
class ScanSpecModeTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    command = support.CObjectTests.command
    write = support.CObjectTests.write

    def run_program(self, executable, payload):
        path = self.root / 'cases.bin'
        path.write_bytes(payload)
        result = subprocess.run([str(executable), str(path)], capture_output=True, timeout=1800)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        return result.stdout.decode('utf8').replace('\r\n', '\n').rstrip('\n').split('\n')

    def test_json_last_wins_and_depth(self):
        executable = build(self, 'last_wins', JSON_SOURCE, ['json_pointer', 'json_pointer_scan'])
        cases = json_cases(random.Random(int(os.environ.get('SCAN_SPEC_SEED', '20261012'))))
        lines = self.run_program(executable, pack_json(cases))
        self.assertEqual(len(lines), len(cases))
        bad = [(c, got, expected_json(*c)) for c, got in zip(cases, lines) if got != expected_json(*c)]
        self.assertEqual(bad[:3], [])
        answers = [expected_json(*c) for c in cases]
        self.assertGreater(sum(a not in ('D', '!') for a in answers), 1000)
        by_case = {(c[0], c[1]): a for c, a in zip(cases, answers)}
        self.assertEqual(by_case[(1000, '[' * 1000 + ']' * 1000)], '[' * 1000 + ']' * 1000)
        self.assertEqual(by_case[(1000, '[' * 1001 + ']' * 1001)], 'D')

    def test_csv_lone_cr(self):
        executable = build(self, 'csv_crlf', CSV_SOURCE, ['json_text', 'csv_stream'])
        cases = csv_cases(random.Random(5))
        payload = '\x1e'.join(cases).encode('utf8')
        lines = self.run_program(executable, payload)
        self.assertEqual(len(lines), 4 * len(cases))
        bad = []
        for index, text in enumerate(cases):
            strict, legacy = show_csv(reference_csv(text, False)), show_csv(reference_csv(text, True))
            got = lines[4 * index:4 * index + 4]
            if got != [strict, strict, legacy, legacy]:
                bad.append((text, got, strict, legacy))
        self.assertEqual(bad[:3], [])
        self.assertEqual(show_csv(reference_csv('a\rb,"x\ry"\r\nz', False)), 'R' + '/'.join(s.encode().hex() for s in ['a\rb', 'x\ry']) + ' R7a')


if __name__ == '__main__':
    unittest.main()
