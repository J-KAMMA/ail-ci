"""json_pointer_scan (one validating pass) against the node-list path, case by case."""
import json
import os
import random
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

import test_ail_c_objects as support
from test_ail_map_fields import build

SOURCE = r'''use json_pointer;
use json_pointer_batch;
use json_pointer_scan;

fn old_run(text: str, pointers: list[str]) -> str {
    let nodes: list[JsonValue] = [];
    try { nodes = json_parse_document(text); } except ValueError { return "D"; }
    try { return json_pointer_batch_render(nodes, pointers); }
    except ValueError { return "!V"; } except KeyError { return "!K"; } except IndexError { return "!I"; }
}

fn old_extract(text: str, pointer: str) -> str {
    let nodes: list[JsonValue] = [];
    try { nodes = json_parse_document(text); } except ValueError { return "D"; }
    try { return json_render_document(json_pointer_extract(nodes, pointer)); }
    except ValueError { return "!V"; } except KeyError { return "!K"; } except IndexError { return "!I"; }
}

fn new_run(text: str, pointers: list[str]) -> str {
    let found: JsonPointerValues = JsonPointerValues(0, []);
    try { found = json_pointer_scan_values(text, pointers); } except ValueError { return "D"; }
    if found.error == 1 { return "!V"; }
    if found.error == 3 { return "!K"; }
    return "[" + ",".join(found.values) + "]";
}

fn bytes_run(text: str, pointers: list[str]) -> str {
    let found: JsonPointerValues = JsonPointerValues(0, []);
    try { found = json_pointer_scan_bytes(text.encode("utf-8"), pointers); } except ValueError { return "D"; }
    if found.error == 1 { return "!V"; }
    if found.error == 3 { return "!K"; }
    return "[" + ",".join(found.values) + "]";
}

fn new_batch(text: str, pointers: list[str]) -> str {
    try { return json_pointer_batch_text(text, pointers); }
    except ValueError { return "!V"; } except KeyError { return "!K"; } except IndexError { return "!I"; }
}

fn new_extract(text: str, pointer: str) -> str {
    try { return json_pointer_extract_text(text, pointer); }
    except ValueError { return "!V"; } except KeyError { return "!K"; } except IndexError { return "!I"; }
}

fn main() -> int {
    let data: str = read_bytes(sys.argv[1]).decode("utf-8");
    let bad: int = 0;
    let total: int = 0;
    let ok: int = 0;
    for one in data.split(chr(30)) {
        let fields: list[str] = one.split(chr(31));
        let text: str = fields[0];
        let pointers: list[str] = [];
        for f in range(1, len(fields)) { pointers.append(fields[f]); }
        let old: str = old_run(text, pointers);
        let fresh: str = new_run(text, pointers);
        total += 1;
        if old == fresh { if old[0:1] == "[" { ok += 1; } }
        else { bad += 1; print("MISMATCH " + str(total) + " old=" + old + " new=" + fresh); }
        let direct: str = bytes_run(text, pointers);
        if old != direct { bad += 1; print("MISMATCH bytes " + str(total) + " old=" + old + " new=" + direct); }
        let wrapped: str = new_batch(text, pointers);
        let expect: str = old;
        if expect == "D" { expect = "!V"; }
        if expect != wrapped { bad += 1; print("MISMATCH batch " + str(total) + " old=" + old + " new=" + wrapped); }
        if len(pointers) > 0 {
            let want: str = old_extract(text, pointers[0]);
            let got: str = new_extract(text, pointers[0]);
            if want == "D" { want = "!V"; }
            if want != got { bad += 1; print("MISMATCH extract " + str(total) + " old=" + want + " new=" + got); }
        }
    }
    print("cases=" + str(total) + " rendered=" + str(ok) + " bad=" + str(bad));
    return 0;
}
'''

KEYS = ['a', 'b', 'c', 'dup', '', 'a/b', '~', '~1', 'x y', '0', '01', '-', '1', '10', '日本', 'é', '😀', 'q"', 'back\\', 'tab\t', 'a~b']
STRINGS = ['', 'plain', '日本語', '😀 emoji', 'q"uote', 'back\\slash', 'nl\n', 'ctl\x01\x1f', ' ', 'ünï', '/', '~', '퟿', '\U0010ffff', '\x7f', 'é']
NUMBERS = ['0', '-0', '1', '-1', '10', '3.14', '-0.0', '1e5', '1E-7', '2.5e+3', '12345678901234567890', '0.000001', '1.50E+3']


def esc_string(rnd, text):
    """A JSON string literal for `text` with random escape choices."""
    out = ['"']
    for ch in text:
        o = ord(ch)
        r = rnd.random()
        if ch == '"':
            out.append('\\"')
        elif ch == '\\':
            out.append('\\\\')
        elif o < 32:
            out.append(rnd.choice(['\\u%04x', '\\u%04X']) % o if ch not in '\n\t' or r < .5 else {'\n': '\\n', '\t': '\\t'}[ch])
        elif r < .08 and o < 0x10000:
            out.append(rnd.choice(['\\u%04x', '\\u%04X']) % o)
        elif r < .12 and o >= 0x10000:
            o -= 0x10000
            out.append('\\u%04x\\u%04X' % (0xd800 + (o >> 10), 0xdc00 + (o & 1023)))
        elif r < .14 and ch == '/':
            out.append('\\/')
        else:
            out.append(ch)
    out.append('"')
    return ''.join(out)


def make_tree(rnd, depth):
    r = rnd.random()
    if depth <= 0 or r < .35:
        k = rnd.random()
        if k < .4:
            return ('s', rnd.choice(STRINGS) + (rnd.choice(STRINGS) if rnd.random() < .3 else ''))
        if k < .75:
            return ('n', rnd.choice(NUMBERS))
        return ('l', rnd.choice(['true', 'false', 'null']))
    if r < .65:
        return ('a', [make_tree(rnd, depth - 1) for _ in range(rnd.choice([0, 1, 2, 3, 4, 6, 11]))])
    members = []
    for _ in range(rnd.choice([0, 1, 2, 3, 4, 6])):
        key = rnd.choice(KEYS) if rnd.random() < .8 else rnd.choice(KEYS) + str(rnd.randrange(30))
        members.append((key, make_tree(rnd, depth - 1)))
        if rnd.random() < .12:
            members.append((key, make_tree(rnd, depth - 1)))
    return ('o', members)


def space(rnd, mode):
    if mode == 0:
        return ''
    if mode == 1:
        return rnd.choice(['', ' ', ' '])
    return rnd.choice(['', ' ', '\n', '\t', '\r\n', '  ', ' \n\t '])


def render_tree(rnd, node, mode):
    kind, value = node
    if kind in 'nl':
        return value
    if kind == 's':
        return esc_string(rnd, value)
    s = lambda: space(rnd, mode)
    if kind == 'a':
        return '[' + s() + (s() + ',' + s()).join(render_tree(rnd, v, mode) for v in value) + s() + ']'
    return '{' + s() + (s() + ',' + s()).join(
        esc_string(rnd, k) + s() + ':' + s() + render_tree(rnd, v, mode) for k, v in value) + s() + '}'


def pointer_escape(token):
    return token.replace('~', '~0').replace('/', '~1')


def make_pointer(rnd, tree):
    """A pointer that mostly follows the tree, sometimes bending off it."""
    tokens = []
    node = tree
    while True:
        kind, value = node
        if rnd.random() < .18:
            break
        if kind == 'a' and value:
            if rnd.random() < .93:
                i = rnd.randrange(len(value))
                tokens.append(str(i))
                node = value[i]
                continue
        elif kind == 'o' and value:
            if rnd.random() < .93:
                k, node = rnd.choice(value)
                tokens.append(pointer_escape(k))
                continue
        break
    r = rnd.random()
    if r < .30:
        tokens.append(rnd.choice(['0', '1', '2', '-', '', '00', '01', '+1', '1.0', ' 1', '１', 'a', 'b', 'dup', '9' * 30, '99999999999999999999999',
                                  '999999999', '4294967296', str(rnd.randrange(40)), '1e1', '0x1', '-1', '~1', '~0']))
    elif r < .36 and tokens:
        tokens[rnd.randrange(len(tokens))] = rnd.choice(['', 'zz', '-', '00', '7', '~2x'])
    if rnd.random() < .04:
        return rnd.choice(['', 'a', '/~', '/~2', '/a/~', '/~3/x', '//', '/ ', '~0', '/a~'])
    if not tokens and rnd.random() < .5:
        return ''
    return ''.join('/' + t for t in tokens)


ALPHABET = list('{}[],:"\\ \t\n\r0123456789-+.eEtrufalsn') + ['\\u', '\\ud83d', '\\ude00', '"a"', '😀', 'é', 'null', '\u0001', '日', '\\u00e9', '\\\\', '\\"', '\x80', ' ', '﻿', '\\ud83d\\ude00', '\\ud800', '\\udc00']


def mutate(rnd, text):
    for _ in range(rnd.choice([1, 1, 1, 2, 3])):
        if not text:
            text = rnd.choice(ALPHABET)
            continue
        i = rnd.randrange(len(text) + 1)
        r = rnd.random()
        if r < .3:
            text = text[:i] + text[i + 1:]
        elif r < .6:
            text = text[:i] + rnd.choice(ALPHABET) + text[i:]
        elif r < .9:
            text = text[:i] + rnd.choice(ALPHABET) + text[i + 1:]
        else:
            text = text[:i]
    return text


def make_case(rnd):
    tree = make_tree(rnd, rnd.choice([1, 2, 3, 4, 5]))
    text = render_tree(rnd, tree, rnd.choice([0, 1, 2]))
    if rnd.random() < .3:
        text = space(rnd, 2) + text + space(rnd, 2)
    if rnd.random() < .25:
        text = mutate(rnd, text)
    pointers = [make_pointer(rnd, tree) for _ in range(rnd.choice([0, 1, 1, 1, 2, 3, 5]))]
    if rnd.random() < .1 and pointers:
        pointers.append(pointers[0])
    return text, pointers


def pack(cases):
    data = '\x1e'.join('\x1f'.join([text, *pointers]) for text, pointers in cases)
    for text, pointers in cases:
        assert '\x1e' not in text and '\x1f' not in text
        assert all('\x1e' not in p and '\x1f' not in p for p in pointers)
    return data.encode('utf8')


def fixed_cases():
    doc = '{"a/b":{"~":[null,true,-0.00e+02,"日本😀\\u0000"]},"dup":1,"dup":2,"map":{"a":"first","b":"😀\\u0000","a":"last"},"e":[],"o":{}}'
    cases = [(doc, p) for p in ['', '/a~1b', '/a~1b/~0/3', '/dup', '/map/a', '/map/b', '/e', '/o', '/e/0', '/o/x', '/e/-', '/e/00', '/e/', '/a~1b/~0/-', '/a~1b/~0/01', '/a~1b/~0/9',
                                '/map/b/x', '/dup/x', 'x', '/~2', '/~', '/a~1b/~0/0/q']]
    cases = [(t, [p]) for t, p in cases]
    cases += [(doc, ['/a~1b', '/map/b', '', '/e']), (doc, ['/e/0', '/dup']), (doc, ['/dup', '/e/0', '/x']), (doc, [])]
    for t in ['null', '  true ', '-0', '"x\\ud83d\\ude00y"', '[]', '{}', '[[],[[]],{}]', '', ' ', '[1,]', '{"a":1,}', '[1 2]', '"\\ud83d"', '"\\ude00"', '"\\ud83d\\u0041"', '"\\x"',
              '"a\nb"', '{"a" 1}', '1 2', '[]]', '[', '{"a":', '"abc', '"a\\', '"a\\"', '01', '-', '1.', '1e+', 'nul', 'True', '{"a":1}x', '﻿[]']:
        cases += [(t, ['']), (t, ['/0']), (t, ['/a']), (t, [])]
    # Non-ASCII and escaped keys: raw against escaped spellings of the same key, bad escapes after non-ASCII.
    cases += [(r'{"é":1,"x":2}', ['/é']), ('{"é":1}', ['/é']), (r'{"é":1,"é":2}', ['/é']), (r'{"😀":[1,2]}', ['/😀/1']),
              (r'{"😀":[1,2],"😀":3}', ['/😀']), (r'{"日本":"日","日本":0}', ['/日本']), ('{"日本語":{"é":["😀"]}}', ['/日本語/é/0', '/日本語/é', '/日本語']),
              (r'{"a\u0000b":1}', ['/a\x00b']), (r'{"a\nb":1,"a\\nb":2}', ['/a\nb', '/a\\nb']), (r'{"\/":1}', ['/~1']),
              (r'["é","é\"","😀\\"]', ['/0', '/1', '/2']), (r'[1, "é\ud800"]', ['/0']), (r'["\udc00é"]', ['']),
              (r'["é\ud83dé"]', ['']), (r'["\ud83d\ud83d"]', ['']), (r'["日\u12"]', ['']), (r'["日\u12G4"]', ['']),
              ('{"é" : \n 1 , "日" : [ 😀 ] }', ['/é']), ('[é]', ['']), ('[1é]', ['']), ('{"k":"v"}é', ['/k']), (' []', ['']),
              ('"日本語\\', ['']), ('"日本語\\"', ['']), (r'["a\\"]', ['/0']), (r'["a\\\"]', ['/0']), ('["日本\x01"]', ['']), ('{"é\x1c":1}', ['/é']),
              ('{"k":"é"}', ['/k', '/k/0']), ('[{"é":{"日":[1,{"😀":"x"}]}}]', ['/0/é/日/1/😀', '/0/é/日/1', '/0'])]
    cases.append(('{"a":{"b":1},"a":{"b":[2]}}', ['/a/b']))
    cases.append(('{"a":[1],"a":5}', ['/a/0']))
    cases.append(('{"a":5,"a":[1]}', ['/a/0']))
    cases.append(('{"x":{"a":1,"a":2},"y":[0]}', ['/x/a', '/y/0', '/y/1']))
    cases.append(('{"a":"\\u0061","a":2}', ['/a']))
    cases.append(('["x\\"y\\\\",{"k\\\\":"v\\"\\\\"}]', ['/0', '/1/k\\', '/1']))
    cases.append(('[' * 3000 + ']' * 3000, ['', '/0/0/0', '/0' * 2999]))
    cases.append(('[0,' * 200 + '0' + ']' * 200, ['/0', '/1' + '/1' * 198]))
    return cases


@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'),
                     'installed C compiler required')
class JsonPointerScanTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    command = support.CObjectTests.command
    write = support.CObjectTests.write

    def run_cases(self, executable, cases):
        path = self.root / 'cases.bin'
        path.write_bytes(pack(cases))
        result = subprocess.run([str(executable), str(path)], capture_output=True, timeout=1800)
        out = result.stdout.decode('utf8').replace('\r\n', '\n')
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        self.assertEqual(result.stderr, b'')
        last = out.strip().split('\n')[-1]
        self.assertEqual(out.count('MISMATCH'), 0, out[:3000])
        self.assertEqual(last.split()[0], 'cases=%d' % len(cases), last)
        return int(last.split()[1].split('=')[1])

    def test_differential(self):
        executable = build(self, 'scan_diff', SOURCE, ['json_pointer', 'json_pointer_batch', 'json_pointer_scan'])
        rendered = self.run_cases(executable, fixed_cases())
        self.assertGreater(rendered, 20)
        rnd = random.Random(int(os.environ.get('JSON_SCAN_SEED', '20261011')))
        count = int(os.environ.get('JSON_SCAN_CASES', '8000'))
        cases = [make_case(rnd) for _ in range(count)]
        rendered = self.run_cases(executable, cases)
        self.assertGreater(rendered, count // 5)
        # The same cases against an independent Python reading of the contract for the valid ones.
        sys.stdout.write('differential cases=%d rendered=%d\n' % (len(cases) + len(fixed_cases()), rendered))

    def test_bench_document(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'bench'))
        try:
            import compare
            app = compare.load_app('json_query')
        finally:
            sys.path.pop(0)
        work = self.root / 'bench'
        work.mkdir()
        case = app.generate(work, False)
        text = (work / 'large.json').read_bytes().decode('utf8')
        pointers = case['args'][3:]
        executable = build(self, 'scan_bench', SOURCE, ['json_pointer', 'json_pointer_batch', 'json_pointer_scan'])
        rnd = random.Random(7)
        extra = ['/records/%d/%s' % (rnd.randrange(4000), rnd.choice(['id', 'tags', 'nested', 'nested/a', 'nested/b/dup', 'text'])) for _ in range(30)]
        extra += ['/records/4000', '/records/-', '/tail/summary/histogram/255', '/tail/checksums/7', '/meta', '']
        cases = [(text, pointers), (text, extra), (text, extra[:3] + ['/records/4000'] + extra[3:]), (text, ['/nope'] + extra)]
        self.run_cases(executable, cases)


if __name__ == '__main__':
    unittest.main()
