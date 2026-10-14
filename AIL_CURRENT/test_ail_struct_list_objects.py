"""Typed struct lists shared across source-free public object boundaries."""
import json
import os
from pathlib import Path
import shutil
import unittest

import test_ail_c_objects as support

PROVIDER = r'''
struct Row { n: int; weight: float; label: str; data: bytes; }
fn make_empty() -> list[Row] { let rows = []; return rows; }
fn build(data: bytes, n: int) -> list[Row] {
let rows = []; let i = 0;
while i < n {
rows.append(Row(i, float(i) * 0.5, "値\x00😀" + str(i), data + b"\x00\xff"));
i += 1;
} return rows;
}
fn echo(rows: list[Row]) -> list[Row] { return rows; }
fn mutate(rows: list[Row]) -> list[Row] {
let row = rows[0]; row.n += 1; return rows;
}
fn take(rows: list[Row]) -> Row { return rows.pop(); }
'''
WRAPPER = '''
fn wrapped(data: bytes, n: int) -> list[Row] { return echo(build(data, n)); }
fn shared(rows: list[Row]) -> list[Row] { return mutate(echo(rows)); }
'''
ENTRY = r'''
fn main() -> int {
let data = read_bytes(sys.argv[1]); let rows = wrapped(data, 1000);
let alias = shared(rows); let held = rows[0];
let tail = take(alias); print(len(rows)); print(tail.n);
let binary = b"";
for row in rows { print(row.label); print(row.n); print(row.weight); binary = binary + row.data; }
rows.clear(); print(len(alias)); print(held.label); print(held.n);
let empty = make_empty(); empty.append(tail); let back = take(echo(empty)); print(back.n);
let i = 0; while i < 1000 { wrapped(data, 2); echo(alias); i += 1; }
write_bytes(sys.argv[2], binary); return 0;
}
'''


def reference(data):
    class Row:
        def __init__(self, n):
            self.n, self.weight = n, float(n) * 0.5
            self.label, self.data = '値\0😀' + str(n), data + b'\0\xff'
    def echo(rows):
        return rows
    def build(n):
        return [Row(i) for i in range(n)]
    def shared(rows):
        echo(rows)[0].n += 1
        return rows
    rows = echo(build(1000))
    alias = shared(rows)
    held = rows[0]
    tail = alias.pop()
    lines = [len(rows), tail.n]
    chunks = []
    for row in rows:
        lines.extend((row.label, row.n, row.weight))
        chunks.append(row.data)
    rows.clear()
    lines.extend((len(alias), held.label, held.n))
    empty = []
    empty.append(tail)
    lines.append(echo(empty).pop().n)
    return '\n'.join([*map(str, lines), '']), b''.join(chunks)


@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'),
                     'installed C compiler required')
class StructListObjectTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    write = support.CObjectTests.write
    command = support.CObjectTests.command
    ail_build = support.CObjectTests.ail_build
    check_run = support.CObjectTests.check_run
    snapshot = support.CObjectTests.snapshot

    def relocate(self, obj):
        directory = self.root / ('moved ' + obj.stem)
        directory.mkdir()
        target = directory / obj.name
        obj.rename(target)
        Path(str(obj) + '.json').rename(Path(str(target) + '.json'))
        return target

    def chain(self):
        provider = self.relocate(self.ail_build('provider', PROVIDER, library=True))
        wrapper = self.relocate(self.ail_build('wrapper', WRAPPER, provider, library=True))
        return provider, wrapper

    def refused(self, name, text, objects, *, abi_mismatch=False):
        entry = self.write(name + '.ail', text)
        output = self.root / name
        result = self.command('compile', entry,
                              *(arg for obj in objects for arg in ('--object', obj)), '-o', output)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        if abi_mismatch:
            self.assertIn(b'ail_object_abi_', result.stderr)
            self.assertIn(b'undefined reference', result.stderr)
        else:
            self.assertNotIn(b'.c:', result.stderr, 'invalid contracts must be rejected before malformed C')
        self.assertFalse(output.exists())
        self.assertFalse(Path(str(output) + '.exe').exists())

    def test_relocated_public_list_contract_long_oracle_and_separate(self):
        objects = self.chain()
        pins = self.snapshot(*objects)
        provider = json.loads(Path(str(objects[0]) + '.json').read_text())['contract']
        wrapper = json.loads(Path(str(objects[1]) + '.json').read_text())['contract']
        self.assertEqual(provider['version'], 11)
        self.assertEqual(provider['exports']['build']['result'], 'struct_list:Row')
        self.assertEqual(provider['exports']['echo']['params'], [['rows', 'struct_list:Row']])
        self.assertEqual(wrapper['exports']['shared']['result'], 'struct_list:Row')
        self.assertEqual(wrapper['structs'], {})
        self.assertTrue(wrapper['dependencies'])
        data = bytes(range(256)) * 3 + b'\0\xff'
        input_path, output_path = self.root / 'input.bin', self.root / 'output.bin'
        input_path.write_bytes(data)
        expected, binary = reference(data)
        for separate in (False, True):
            with self.subTest(separate=separate):
                entry = self.write('entry.ail', ENTRY.replace('print(len(rows))', 'print(local(len(rows)))')
                                   if separate else ENTRY)
                extra = []
                if separate:
                    helper = self.write('helper.ail', 'fn local(n: int) -> int { return n; }')
                    extra = ['--separate', '--module', helper]
                output = self.root / ('separate' if separate else 'normal')
                order = tuple(reversed(objects)) if separate else objects
                result = self.command('compile', entry, *extra,
                                      *(arg for obj in order for arg in ('--object', obj)), '-o', output)
                self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
                entry.unlink()
                if separate:
                    helper.unlink()
                executable = output if output.is_file() else Path(str(output) + '.exe')
                self.check_run(executable, expected, input_path, output_path)
                self.assertEqual(output_path.read_bytes(), binary)
                self.assertEqual(input_path.read_bytes(), data)
                self.assertEqual(self.snapshot(*objects), pins)

    def test_schema_kind_version_and_provider_dependency_tampering_refused(self):
        objects = self.chain()
        pins = self.snapshot(*objects)
        for case in ('missing_schema', 'other_class', 'wrong_kind', 'invalid_element', 'version', 'owner'):
            with self.subTest(case=case):
                original = objects[1] if case == 'owner' else objects[0]
                directory = self.root / case
                directory.mkdir()
                candidate = directory / original.name
                shutil.copyfile(original, candidate)
                metadata = json.loads(Path(str(original) + '.json').read_text())
                contract = metadata['contract']
                if case == 'missing_schema':
                    contract['structs'] = {}
                elif case == 'other_class':
                    contract['exports']['build']['result'] = 'struct_list:Other'
                elif case == 'wrong_kind':
                    contract['exports']['build']['result'] = 'struct:Row'
                elif case == 'invalid_element':
                    contract['exports']['build']['result'] = 'struct_list:int'
                elif case == 'version':
                    contract['version'] = 8
                else:
                    contract['dependencies'] = []
                Path(str(candidate) + '.json').write_text(json.dumps(metadata), encoding='utf8')
                candidate_pins = self.snapshot(candidate)
                dependencies = (objects[0], candidate) if case == 'owner' else (candidate,)
                self.refused('entry_' + case, 'fn main() -> int { let rows = make_empty(); print(len(rows)); return 0; }',
                             dependencies, abi_mismatch=case == 'wrong_kind')
                self.assertEqual(self.snapshot(candidate), candidate_pins)
        self.assertEqual(self.snapshot(*objects), pins)

    def test_nominal_element_shadow_duplicate_provider_and_c_api_refused(self):
        objects = self.chain()
        pins = self.snapshot(*objects)
        self.refused('missing', 'fn main() -> int { let rows = wrapped(b"", 1); print(len(rows)); return 0; }',
                     objects[1:])
        self.refused('scalar', 'fn main() -> int { echo([1]); return 0; }', objects)
        self.refused('shadow', 'fn main() -> int { let Row = 1; return Row; }', objects)
        self.refused('other', '''struct Other { n: int; weight: float; label: str; data: bytes; }
fn main() -> int { let rows = [Other(1, 1.0, "", b"")]; echo(rows); return 0; }''', objects)
        duplicate = self.relocate(self.ail_build('duplicate',
                     'struct Row { n: int; weight: float; label: str; data: bytes; }\n'
                     'fn extra(rows: list[Row]) -> list[Row] { return rows; }', library=True))
        self.refused('duplicate_entry', 'fn main() -> int { let rows = make_empty(); return len(rows); }',
                     (*objects, duplicate))
        source = self.write('c_api.ail', PROVIDER)
        output = self.root / 'c_api.o'
        result = self.command('compile-module', source, '--c-api-name', 'rows_api', '-o', output)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertFalse(output.exists())
        self.assertFalse(Path(str(output) + '.json').exists())
        self.assertEqual(self.snapshot(*objects), pins)


if __name__ == '__main__':
    unittest.main()
