"""csv_group_scan (one pass, no CsvRow) against csv_table_group_file, case by case."""
import os
import random
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

import test_ail_c_objects as support
from test_ail_map_fields import build

MODULES = ['utf8_stream', 'csv_stream', 'csv_group', 'checked_integer', 'json_text', 'csv_group_scan']

SOURCE = r'''use utf8_stream;
use csv_stream;
use csv_group;
use csv_group_scan;

fn old_group(path: str, key_column: int, value_column: int, size: int) -> str {
    if size <= 0 or key_column < 0 or value_column < 0 { raise ValueError; }
    let utf8 = utf8_decoder_new();
    let csv = csv_decoder_new();
    let groups = csv_groups_new();
    for chunk in file_chunks(path, size) {
        let rows = csv_decode_feed(csv, utf8_decode_feed(utf8, chunk));
        csv_groups_add(groups, rows, key_column, value_column);
    }
    let tail = csv_decode_feed(csv, utf8_decode_finish(utf8));
    csv_groups_add(groups, tail, key_column, value_column);
    let final = csv_decode_finish(csv);
    csv_groups_add(groups, final, key_column, value_column);
    return csv_groups_render(groups);
}

fn run_old(path: str, kc: int, vc: int, size: int) -> str {
    try { return old_group(path, kc, vc, size); }
    except ValueError { return "!ValueError"; }
    except UnicodeDecodeError { return "!UnicodeDecodeError"; }
    except OSError { return "!OSError"; }
}

fn run_new(path: str, kc: int, vc: int, size: int) -> str {
    try { return csv_table_group_scan(path, kc, vc, size); }
    except ValueError { return "!ValueError"; }
    except UnicodeDecodeError { return "!UnicodeDecodeError"; }
    except OSError { return "!OSError"; }
}

fn main() -> int {
    let manifest: str = read_bytes(sys.argv[1]).decode("utf-8");
    let bad: int = 0;
    let total: int = 0;
    let rendered: int = 0;
    let errors: int = 0;
    for line in manifest.split("\n") {
        if line == "" { continue; }
        let parts: list[str] = line.split("\t");
        let path: str = parts[0];
        let kc: int = int(parts[1]);
        let vc: int = int(parts[2]);
        let size: int = int(parts[3]);
        let old: str = run_old(path, kc, vc, size);
        let fresh: str = run_new(path, kc, vc, size);
        total += 1;
        if old == fresh {
            if old[0:1] == "!" { errors += 1; } else { rendered += 1; }
        } else {
            bad += 1;
            print("MISMATCH " + line + " old=" + old + " new=" + fresh);
        }
    }
    print("cases=" + str(total) + " rendered=" + str(rendered) + " errors=" + str(errors) + " bad=" + str(bad));
    return 0;
}
'''

SIZES = [1, 2, 3, 5, 7, 13, 64, 65536]
WORDS = ['a', 'b', 'c', 'key', 'Alpha', 'x y', '', '東京', 'Zürich', '日本語😀', 'é', '😀', 'q', 'same', '0']
INT_TEXT = ['0', '1', '-1', '+5', '-0', '+0', '007', '-007', '12', '999', '1000000', '9223372036854775807', '-9223372036854775808',
            '9223372036854775806', '9223372036854775808', '-9223372036854775809', '4611686018427387904', '-4611686018427387904',
            '', '+', '-', 'x', '1x', '1.5', ' 1', '1 ', '１', '٣', '--1', '+-1', '1e3', '0x1', '99999999999999999999']
NASTY = ['\0', '\x01', '\t', '\\', '/', '"', '\x7f', ' ', '﻿', '\U0010ffff', '￿']


def render_field(rnd, text, force_quote):
    needs = any(c in text for c in ',"\r\n')
    if needs or force_quote or rnd.random() < .08:
        return '"' + text.replace('"', '""') + '"'
    return text


def make_row(rnd, width):
    fields = []
    for _ in range(width):
        r = rnd.random()
        if r < .5:
            text = rnd.choice(INT_TEXT) if rnd.random() < .85 else str(rnd.randrange(-10**6, 10**6))
        elif r < .8:
            text = rnd.choice(WORDS) + (rnd.choice(WORDS) if rnd.random() < .3 else '')
        elif r < .9:
            text = rnd.choice(WORDS) + rnd.choice([',', '\n', '\r\n', '\r', '"', '""', ', ']) + rnd.choice(WORDS)
        else:
            text = rnd.choice(NASTY) + rnd.choice(WORDS)
        fields.append(render_field(rnd, text, False))
    return ','.join(fields)


def make_case(rnd):
    width = rnd.choice([1, 2, 2, 3, 3, 4, 5])
    rows = rnd.randrange(0, 12)
    nl = rnd.choice(['\n', '\n', '\r\n', '\r', '\n'])
    keys = [rnd.choice(WORDS) for _ in range(rnd.randrange(1, 4))]
    # Mostly well-formed int columns so that the aggregation itself is exercised.
    clean = rnd.random() < .85
    lines = []
    for _ in range(rows):
        r = rnd.random()
        if r < .08:
            lines.append('')
        elif r < .11:
            lines.append(make_row(rnd, rnd.randrange(1, 6)))
        elif clean:
            row = []
            for column in range(width):
                if column == 1:
                    if rnd.random() < .15:
                        text = rnd.choice(['9223372036854775807', '-9223372036854775808', '4611686018427387904', '-4611686018427387904'])
                    else:
                        text = rnd.choice(['0', '1', '-1', '+5', '007', str(rnd.randrange(-1000, 1000)), '12'])
                    row.append(text)
                elif column == 0:
                    row.append(render_field(rnd, rnd.choice(keys), False))
                else:
                    row.append(make_row(rnd, 1))
            lines.append(','.join(row))
        else:
            lines.append(make_row(rnd, width))
        if rnd.random() < .1:
            lines.append('')
    text = ''
    for line in lines:
        text += line + (rnd.choice(['\n', '\r\n', '\r']) if rnd.random() < .2 else nl)
    if text and rnd.random() < .25:
        text = text.rstrip('\r\n')
    data = text.encode('utf8')
    r = rnd.random()
    if r < .04 and data:
        i = rnd.randrange(len(data))
        data = data[:i] + bytes([rnd.choice([0x80, 0xbf, 0xc0, 0xc1, 0xc3, 0xe2, 0xed, 0xf0, 0xf4, 0xf5, 0xff, 0xa0])]) + data[i + 1:]
    elif r < .06 and data:
        data = data[:-rnd.randrange(1, min(4, len(data)) + 1)]
    elif r < .10:
        data +=rnd.choice([b'"', b'"unterminated', b'a"b', b'"a"b', b'""x', b'"a""', b'\xed\xa0\x80', b'\xf4\x90\x80\x80', b'\xe0\x80\x80', b'\xc0\x80'])
    elif r < .14 and data:
        i = rnd.randrange(len(data))
        data = data[:i] + rnd.choice([b'"', b'""', b',', b'\r', b'\n', b'\r\n']) + data[i:]
    pick = rnd.random()
    if pick < .6:
        kc, vc = 0, 1
    elif pick < .75:
        kc, vc = rnd.randrange(0, 3), rnd.randrange(0, 3)
    elif pick < .9:
        kc, vc = rnd.randrange(0, 6), rnd.randrange(0, 6)
    else:
        kc, vc = rnd.choice([0, 1, 7, 100, 2**40]), rnd.choice([0, 1, 7, 100, 2**40])
    return data, kc, vc, rnd.choice(SIZES)


def fixed_cases():
    cases = []
    base = [
        b'', b'\n', b'\r\n', b'\n\r\n\n', b'a,1', b'a,1\n', b'a,1\r\nb,2\r\na,3', b'a,1\ra,2\rb,3\r',
        b'a,1\n\n\nb,2\n', b'"a,b",1\n"he said ""hi""",2\n"a,b",3\n"l1\nl2",4\n', b'"a\r\nb",1\r\n"a\r\nb",2',
        b'\xe6\x97\xa5\xe6\x9c\xac\xe8\xaa\x9e\xf0\x9f\x98\x80,5\n\xc3\x85re,-2\n\xe6\x97\xa5\xe6\x9c\xac\xe8\xaa\x9e\xf0\x9f\x98\x80,7\n',
        b'a,1\nb\n', b'a,x\n', b'a,\n', b',5\n,6\n"",7\n', b',\n', b',,\n', b'""\n', b'"",""\n', b'a,1\n"b\n', b'a,1\na"b,2\n', b'"a"b,1\n',
        b'"a""b",1\n', b'a,1\xff\n', b'a,x\n\xff', b'a,x\n\xe2\x82', b'a,1\n\xe2\x82', b'a,1\n\xed\xa0\x80\n', b'a,+0017\na,-3\n',
        b'a,9223372036854775807\na,1\n', b'a,-9223372036854775808\na,-1\n', b'a,9223372036854775807\nb,1\na,0\n',
        b'a,9223372036854775807\na,-9223372036854775808\n', b'a,9223372036854775808\n', b'a,1\r\n\r\nb,2\r\n\n',
        b'"",1\n"",2\n', b'"a\n', b'"a"', b'"a",1\n"b",2\n"a",3', b'x,1\r', b'x,1\r\r\n\n', b'\r\r\n\n\rx,1',
        b'"\xf0\x9f\x98\x80\n\r,""",1\n', b'a,1,2,3\nb,4,5,6\n',
        '"日本語😀",1\n"日本語😀",2\n日本語😀,3\r\n"😀""日本",4\r"é,é",5\n'.encode(),
        '😀,1\n😀😀,2\n日本語,3\n😀,4\n'.encode(), 'a,1\n"日本語\n😀",2\n'.encode(), '１,x\n日本,１\n'.encode(),
        '日本語,１\n'.encode(), 'a,1\n日本語,2\n"é'.encode(), b'"\xe6\x97',
        b'a,1\n"\xf0\x9f\x98\x80"\xf0\n', b'a,1\n\xf0\x9f\x98,2\n', b'a,1\n\xf0\x9f\x98"\n', b'a,1\n\xe6\x97,\xa5\n',
        b'\xe6\x97,\xa5,1\n', b'a,1\n\xe6\x97\n\xa5,1\n', b'"\xe6\x97","\xa5",1\n', b'a,1\n\xf0\x9f\x98\x80\x80,2\n',
        b'\xed\xa0\x80,1\n', b'a,"\xed\xa0\x80"\n', b'a,1\n"a"b\xff\n', b'"abc\xff',
    ]
    for data in base:
        for kc, vc in [(0, 1), (1, 0), (0, 0), (1, 2), (2, 1), (0, 3), (5, 5), (0, 2)]:
            for size in SIZES:
                cases.append((data, kc, vc, size))
    return cases


def bench_cases():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'bench'))
    try:
        import compare
        app = compare.load_app('csv_table')
    finally:
        sys.path.pop(0)
    data = app._workload(600)
    return [(data, 1, 3, size) for size in SIZES + [1000, 4096, 100000]] + \
           [(data, 3, 1, 4096), (data, 1, 0, 4096), (data, 1, 2, 7), (data, 0, 1, 65536)]


@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'),
                     'installed C compiler required')
class CsvGroupScanTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    command = support.CObjectTests.command
    write = support.CObjectTests.write

    def run_cases(self, executable, cases, tag):
        folder = self.root / ('data_' + tag)
        folder.mkdir()
        lines = []
        for i, (data, kc, vc, size) in enumerate(cases):
            path = folder / ('%d.csv' % i)
            path.write_bytes(data)
            lines.append('%s\t%d\t%d\t%d' % (path, kc, vc, size))
        manifest = self.root / ('manifest_' + tag + '.txt')
        manifest.write_text('\n'.join(lines) + '\n', encoding='utf8')
        result = subprocess.run([str(executable), str(manifest)], capture_output=True, timeout=3600)
        out = result.stdout.decode('utf8').replace('\r\n', '\n')
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        self.assertEqual(result.stderr, b'')
        last = out.strip().split('\n')[-1]
        self.assertEqual(out.count('MISMATCH'), 0, out[:3000])
        words = dict(w.split('=') for w in last.split())
        self.assertEqual(int(words['cases']), len(cases), last)
        self.assertEqual(int(words['bad']), 0, last)
        return int(words['rendered']), int(words['errors'])

    def test_fixed_and_bench(self):
        executable = build(self, 'group_diff', SOURCE, MODULES)
        rendered, errors = self.run_cases(executable, fixed_cases(), 'fixed')
        self.assertGreater(rendered, 200)
        self.assertGreater(errors, 200)
        rendered, errors = self.run_cases(executable, bench_cases(), 'bench')
        self.assertGreaterEqual(rendered, 11)

    def test_missing_file_and_bad_size(self):
        executable = build(self, 'group_diff_io', SOURCE, MODULES)
        cases = [(b'a,1\n', 0, 1, 0), (b'a,1\n', 0, 1, -1), (b'a,1\n', -1, 1, 4), (b'a,1\n', 0, -1, 4)]
        self.run_cases(executable, cases, 'bad')
        manifest = self.root / 'missing.txt'
        manifest.write_text('%s\t0\t1\t4\n' % (self.root / 'does_not_exist.csv'), encoding='utf8')
        result = subprocess.run([str(executable), str(manifest)], capture_output=True, timeout=600)
        out = result.stdout.decode('utf8')
        self.assertIn('cases=1 rendered=0 errors=1 bad=0', out)

    def test_differential(self):
        executable = build(self, 'group_diff_random', SOURCE, MODULES)
        rnd = random.Random(int(os.environ.get('CSV_GROUP_SEED', '20261011')))
        count = int(os.environ.get('CSV_GROUP_CASES', '5000'))
        cases = [make_case(rnd) for _ in range(count)]
        rendered, errors = self.run_cases(executable, cases, 'random')
        self.assertGreater(rendered, count // 10)
        self.assertGreater(errors, count // 10)
        sys.stdout.write('differential cases=%d rendered=%d errors=%d\n' % (count, rendered, errors))


if __name__ == '__main__':
    unittest.main()
