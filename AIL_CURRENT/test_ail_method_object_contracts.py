"""Method object metadata refusal and native ABI binding through the public CLI."""
import copy
import json
import os
from pathlib import Path
import shutil
import unittest

import test_ail_c_objects as support


PROVIDER = '''struct Point { x: int; }
struct Other { x: int; }
impl Point {
 fn add(self, n: int) -> int { return self.x + n; }
 fn sub(self, n: int) -> int { return self.x - n; }
 fn text(self) -> str { return "point"; }
}
impl Other { fn add(self, n: int) -> int { return self.x + n; } }
fn make(x: int) -> Point { return Point(x); }
'''
ENTRY = 'fn main() -> int { let p = make(5); print(p.add(2)); return 0; }'


@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'),
                     'installed C compiler required')
class MethodObjectContractTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    command = support.CObjectTests.command
    write = support.CObjectTests.write
    ail_build = support.CObjectTests.ail_build
    check_run = support.CObjectTests.check_run
    snapshot = support.CObjectTests.snapshot

    def refused(self, name, source, *objects, library=False):
        entry = self.write(name + '.ail', source)
        output = self.root / (name + ('.o' if library else ''))
        result = self.command('compile-module' if library else 'compile', entry,
                              *(arg for obj in objects for arg in ('--object', obj)), '-o', output)
        diagnostic = result.stderr.decode(errors='replace')
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertTrue(diagnostic.strip(), result.stdout)
        self.assertNotIn('Traceback', diagnostic)
        for path in (output, Path(str(output) + '.exe'), Path(str(output) + '.json')):
            self.assertFalse(path.exists(), str(path))
        return diagnostic

    def candidate(self, name, provider, original, mutate):
        candidate = self.root / (name + '.o')
        shutil.copyfile(provider, candidate)
        metadata = copy.deepcopy(original)
        mutate(metadata)
        Path(str(candidate) + '.json').write_text(json.dumps(metadata), encoding='utf8')
        return candidate

    def test_metadata_shapes_and_adapter_contracts(self):
        provider = self.ail_build('provider', PROVIDER, library=True)
        original = json.loads(Path(str(provider) + '.json').read_text(encoding='utf8'))
        self.assertEqual(original['contract']['version'], 11)
        methods = original['contract']['structs']['Point']['methods']
        self.assertEqual(methods['add'], dict(params=[['n', 'int']], result='int',
                                             function='__ail_method_Point_add'))
        self.check_run(self.ail_build('baseline', ENTRY, provider), '7\n')
        before = self.snapshot(provider)

        def change(case, metadata):
            contract = metadata['contract']
            methods = contract['structs']['Point']['methods']
            method = methods['add']
            export = contract['exports'][method['function']]
            if case == 'missing_key': del method['params']
            elif case == 'extra_key': method['extra'] = True
            elif case == 'unknown_param': method['params'][0][1] = 'struct:Missing'
            elif case == 'unknown_result': method['result'] = 'struct:Missing'
            elif case == 'invalid_name': methods['bad-name'] = methods.pop('add')
            elif case == 'field_collision': methods['x'] = methods.pop('add')
            elif case == 'missing_export': del contract['exports'][method['function']]
            elif case == 'wrong_params': export['params'][1][1] = 'float'
            elif case == 'wrong_self': export['params'][0][0] = 'receiver'
            elif case == 'other_owner': export['params'][0][1] = 'struct:Other'
            elif case == 'swap_functions':
                method['function'], methods['sub']['function'] = methods['sub']['function'], method['function']
            elif case == 'owned_result':
                contract['exports'][methods['text']['function']]['owned_str'] = False
            elif case == 'abi9': contract['version'] = 9
            elif case == 'object_hash': metadata['object_sha256'] = '0' * 64
            elif case == 'coherent_param':
                method['params'][0][1] = export['params'][1][1] = 'float'
            elif case == 'coherent_result':
                method['result'] = export['result'] = 'float'
            elif case == 'coherent_symbol':
                export['symbol'] = contract['exports'][methods['sub']['function']]['symbol']
            elif case == 'remove_methods': del contract['structs']['Point']['methods']
            else: raise AssertionError(case)

        for case in ('missing_key', 'extra_key', 'unknown_param', 'unknown_result',
                     'invalid_name', 'field_collision', 'missing_export', 'wrong_params',
                     'wrong_self', 'other_owner', 'swap_functions', 'owned_result',
                     'abi9', 'object_hash', 'coherent_param', 'coherent_result',
                     'coherent_symbol', 'remove_methods'):
            with self.subTest(case=case):
                candidate = self.candidate(case, provider, original, lambda m: change(case, m))
                pins = self.snapshot(candidate)
                # Coherent edits pass shape validation but must fail the embedded ABI binding.
                entry = ('fn main() -> int { print(make(5).x); return 0; }'
                         if case in ('coherent_param', 'coherent_result', 'coherent_symbol', 'remove_methods')
                         else ENTRY)
                diagnostic = self.refused('entry_' + case, entry, candidate)
                if case not in ('coherent_param', 'coherent_result', 'coherent_symbol', 'remove_methods'):
                    self.assertIn('metadata', diagnostic.lower())
                self.assertEqual(self.snapshot(candidate), pins)
        self.assertEqual(self.snapshot(provider), before)

    def test_dependencies_are_order_independent_and_provider_is_required(self):
        provider = self.ail_build('provider', PROVIDER, library=True)
        wrapper = self.ail_build('wrapper', '''fn wrap(p: Point) -> int { return p.add(3); }
fn nested(x: int) -> int { return wrap(make(x)); }''', provider, library=True)
        entry = 'fn main() -> int { print(nested(4)); return 0; }'
        before = self.snapshot(provider, wrapper)
        for index, objects in enumerate(((provider, wrapper), (wrapper, provider))):
            self.check_run(self.ail_build('ordered_' + str(index), entry, *objects), '7\n')
        diagnostic = self.refused('missing_provider', entry, wrapper)
        self.assertTrue('dependency' in diagnostic.lower() or 'struct' in diagnostic.lower()
                        or 'invalid object metadata: invalid or duplicate exported signature' in diagnostic.lower(),
                        diagnostic)
        original = json.loads(Path(str(wrapper) + '.json').read_text(encoding='utf8'))
        def unbind(metadata): metadata['contract']['dependencies'] = []
        candidate = self.candidate('unbound', wrapper, original, unbind)
        self.refused('unbound_entry', entry, provider, candidate)
        self.assertEqual(self.snapshot(provider, wrapper), before)

    def test_static_source_guards(self):
        cases = {
            'missing_parameter': 'impl Point { fn f(self, n) -> int { return n; } }',
            'missing_result': 'impl Point { fn f(self) { return self.x; } }',
            'constructor_collision': 'impl Point { fn __init__(self) -> int { return 1; } }',
            'adapter_collision': '''impl Point { fn f(self) -> int { return self.x; } }
fn __ail_method_Point_f(p: Point) -> int { return p.x; }''',
        }
        for case, body in cases.items():
            with self.subTest(case=case):
                self.refused(case, 'struct Point { x: int; }\n' + body, library=True)


if __name__ == '__main__':
    unittest.main()
