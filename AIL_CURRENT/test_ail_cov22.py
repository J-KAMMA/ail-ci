"""cov22: json.load(sys.stdin) with no declared result type is exactly json.loads(sys.stdin.read()).

The typed path wants the type json.loads produces (an annotation), so a program that simply reads
the JSON document from stdin was refused there; the general path then refused `json.load` itself
("not yet published"), and the program never built.  The general path now lowers exactly
`json.load(sys.stdin)` to the json.loads piece it already has, so the value is the same boxed
object CPython builds.  Any other file argument stays a named compile-time refusal: a binary file
would reach json.loads as bytes, which CPython decodes but this json.loads rejects.

The programs are compared with CPython 3.12 on both builds (AIL_UNIFIED_FORCE=1 and the default
build, which falls back to the general path).
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')

PROGRAMS = {}
PROGRAMS['load'] = r'''import json
import sys


def main() -> None:
    data = json.load(sys.stdin)
    print(type(data).__name__)
    print(json.dumps(data, sort_keys=True))
    print(json.dumps(data, ensure_ascii=False))


main()
'''
PROGRAMS['routed'] = r'''import json
import sys


class Box:
    def __init__(self, value) -> None:
        self.value = value


def describe(value) -> str:
    if isinstance(value, list):
        return 'list:%d' % len(value)
    if isinstance(value, dict):
        return 'dict:%d' % len(value)
    return type(value).__name__ + ':' + json.dumps(value)


def main() -> None:
    data = json.load(sys.stdin)
    box = Box(data)
    holder = {'k': data}
    seq = [data]
    print(describe(data), describe(box.value), describe(holder['k']), describe(seq[0]))


main()
'''
PROGRAMS['keys'] = r'''import json
import sys


def main() -> None:
    data = json.load(sys.stdin)
    if isinstance(data, dict):
        print(sorted(data.keys()), [data[k] for k in sorted(data.keys())])
    else:
        print('not a dict', json.dumps(data))


main()
'''

INPUTS = [
    b'{"b": [1, 2.5, -3, true, false, null], "a": "x", "u": "\\u00e9\\u2603"}\n',
    b'[1, {"k": "v"}, [2, 3], "s", null]\n',
    b'42\n',
    b'-17\n',
    b'3.25\n',
    b'1e300\n',
    b'"hi"\n',
    b'true\n',
    b'null\n',
    b'  { "a" : 1 , "a" : 2 }  \n',
    b'   \n',
    b'[\n',
    b'{"a": 1} x\n',
]

REFUSED = r'''import json


def main() -> None:
    with open('x.json') as f:
        print(json.load(f))


main()
'''


def oracle(directory, name, text, data):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], input=data, capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8',
                                   PYTHONWARNINGS='ignore'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def build(directory, name, text, general):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1', PYTHONUTF8='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name,
                                '--syntax', 'python', '-o', exe.name], cwd=directory,
                               capture_output=True, text=True, timeout=900, env=env)


class Cov22Tests(unittest.TestCase):
    def test_json_load_stdin_matches_cpython_on_both_builds(self):
        with tempfile.TemporaryDirectory(prefix='ail-cov22-') as directory:
            for slug, text in PROGRAMS.items():
                for general in (True, False):
                    name = '%s_%s' % (slug, 'g' if general else 'd')
                    exe, built = build(directory, name, text, general)
                    self.assertEqual(built.returncode, 0, (slug, general, built.stdout + built.stderr))
                    for k, data in enumerate(INPUTS):
                        want = oracle(directory, '%s_%d' % (name, k), text, data)
                        got = subprocess.run([str(exe)], input=data, capture_output=True, timeout=120,
                                             cwd=directory, env=dict(os.environ, PYTHONUTF8='1'))
                        self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0],
                                         (slug, general, k, got.stderr[-800:]))
                        self.assertEqual(got.returncode, want[1],
                                         (slug, general, k, got.stderr[-800:]))

    def test_json_load_from_another_file_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-cov22-') as directory:
            for general in (True, False):
                _, built = build(directory, 'other_%s' % ('g' if general else 'd'), REFUSED, general)
                output = built.stdout + built.stderr
                self.assertEqual(built.returncode, 3, (general, output[-1200:]))
                self.assertIn('json.load', output, (general, output[-1200:]))


if __name__ == '__main__':
    unittest.main()
