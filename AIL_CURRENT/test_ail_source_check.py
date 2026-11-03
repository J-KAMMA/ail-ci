"""Structured source checking, with all subprocess/build calls forbidden by default."""
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import ail_chatgpt


class SourceCheckTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='ail-check-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def source(self, text, name='source.ail'):
        path = self.root / name
        path.write_text(text, encoding='utf8')
        return path

    def check(self, source, *args, command="check"):
        out, err = io.StringIO(), io.StringIO()
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with patch.dict(os.environ, {'PATH': ''}), patch.object(ail_chatgpt.subprocess, 'run',
                side_effect=AssertionError('source check must not launch a process')), \
                redirect_stdout(out), redirect_stderr(err):
            status = ail_chatgpt.main([command, str(source), *map(str, args)])
        self.assertEqual(err.getvalue(), '')
        report = json.loads(out.getvalue())
        self.assertEqual(report['schema'], 'ail.check/1')
        self.assertFalse(report['link_verified']); self.assertFalse(report['runtime_verified'])
        after = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(after, before, 'checking must not create or modify artifacts')
        if isinstance(source, Path) and source.is_file():
            self.assertEqual(report['source_sha256'], hashlib.sha256(source.read_bytes()).hexdigest())
        return status, report

    def test_bundled_api_matches_explicit_module_check(self):
        source = ail_chatgpt.ROOT / 'language_examples/checked_integer.ail'
        status, expected = self.check(source, '--library', '--interface', '--symbol', 'parse_int64_decimal')
        actual_status, actual = self.check(Path('checked_integer'), '--symbol', 'parse_int64_decimal', command='api')
        self.assertEqual((actual_status, actual), (status, expected))
        self.assertEqual(actual['interface']['functions'][0]['name'], 'parse_int64_decimal')
        self.assertEqual(actual['source_sha256'], hashlib.sha256(source.read_bytes()).hexdigest())

    def test_bundled_api_reports_missing_object_metadata(self):
        status,report=self.check(Path('checked_integer'),'--object',self.root/'missing.o',command='api')
        self.assertEqual(status,2)
        self.assertFalse(report['link_verified']);self.assertFalse(report['runtime_verified'])
        self.assertNotIn('interface',report)
    def test_bundled_api_rejects_paths_unshipped_modules_and_unknown_symbols(self):
        for name in ('../checked_integer', 'checked_integer.ail', 'C:/outside', '', 'csv_column_stats_guard_candidate', 'unknown_module'):
            with self.subTest(name=name), patch.object(ail_chatgpt, '_load_sources', side_effect=AssertionError('invalid API must not load a source')):
                status, report = self.check(Path(name), command='api') if name else self.check('', command='api')
                self.assertEqual((status, report['diagnostics'][0]['code']), (2, 'configuration'))
                self.assertIsNone(report['source_sha256'])
        status, report = self.check(Path('checked_integer'), '--symbol', 'missing', command='api')
        self.assertEqual((status, report['diagnostics'][0]['code']), (2, 'configuration'))
        self.assertNotIn('interface', report)
    def test_bundled_api_rejects_invalid_manifest_before_loading(self):
        for text in ('{', '[]', '{"sdk_files":"language_examples/checked_integer.ail"}', '{"sdk_files":[1]}', b'\xff'):
            (self.root / 'MANIFEST.json').write_bytes(text if isinstance(text, bytes) else text.encode('utf8'))
            with self.subTest(manifest=text), patch.object(ail_chatgpt, 'ROOT', self.root), patch.object(
                    ail_chatgpt, '_load_sources', side_effect=AssertionError('invalid manifest must not load a source')):
                status, report = self.check(Path('checked_integer'), command='api')
                self.assertEqual((status, report['diagnostics'][0]['code']), (2, 'configuration'))
                self.assertIsNone(report['source_sha256'])
    def test_json_document_is_self_contained_source_library(self):
        source=ail_chatgpt.ROOT/'language_examples/json_document.ail'
        status,report=self.check(source,'--library','--interface','--symbol','json_parse_document','--types-used')
        self.assertEqual(status,0,report)
        self.assertEqual([item['name'] for item in report['interface']['structs']],['JsonValue'])
        self.assertEqual(report['interface']['functions'][0]['returns'],'list[JsonValue]')
    def test_valid_typed_source_with_no_compiler_and_explicit_library(self):
        source = self.source('import sys\n\ndef plus(x: int) -> int:\n    return x + 1\n\ndef main() -> int:\n    return plus(2)\n\nif __name__ == "__main__":\n    sys.exit(main())\n')
        status, report = self.check(source)
        self.assertEqual((status, report['status'], report['stage'], report['diagnostics']), (0, 'passed', 'type', []))
        self.assertEqual(report['checked_functions'], 2)
        source = self.source('def plus(x: int) -> int:\n    return x + 1\n')
        self.assertEqual(self.check(source, '--library')[0], 0)

    def test_interface_matches_checked_declarations_without_bodies(self):
        source = self.source('import sys\n\ndef plus(x: int, y: int) -> int:\n    return x + y\n\ndef main() -> int:\n    return plus(1, 2)\n\nif __name__ == "__main__":\n    sys.exit(main())\n')
        status, report = self.check(source, '--interface')
        self.assertEqual(status, 0, report)
        api = report['interface']
        self.assertEqual((api['scope'], api['types']), ('loaded_sources', 'declared_annotations'))
        self.assertEqual(api['functions'][0], dict(name='plus', parameters=[
            dict(name=name, type='int', kind='positional', default=None) for name in ('x', 'y')], returns='int'))
        self.assertNotIn('return x', json.dumps(api))
        self.assertNotIn('interface', self.check(source)[1])
        source = self.source('def plus(x: int) -> int:\n    return missing(x)\n')
        status, report = self.check(source, '--library', '--interface')
        self.assertEqual(status, 1)
        self.assertNotIn('interface', report)

    def test_interface_struct_methods_void_floatlist_and_imports(self):
        self.source('def helper(x: list[float]) -> float:\n    return sum(x)\n', 'helper.py')
        source = self.source('from helper import *\nclass Pair:\n\n    def __init__(self, left: int, right: str):\n        self.left = left\n        self.right = right\n\n    def value(self) -> int:\n        return self.left\n\ndef show(p: Pair) -> None:\n    print(p.right)\n')
        status, report = self.check(source, '--library', '--interface')
        self.assertEqual(status, 0, report)
        api = report['interface']
        functions = {fn['name']: fn for fn in api['functions']}
        self.assertEqual(functions['helper__helper']['parameters'][0]['type'], 'list[float]')
        self.assertEqual(functions['show']['returns'], 'void')
        pair, = api['structs']
        self.assertEqual(pair['fields'], [dict(name='left', type='int'), dict(name='right', type='str')])
        self.assertEqual(pair['methods'][0]['name'], 'value')
        self.assertEqual(pair['methods'][0]['parameters'][0]['name'], 'self')

    def test_interface_unannotated_types_are_unknown(self):
        source = self.source('def square(x):\n    return x*x\n', 'inferred.ail')
        status, report = self.check(source, '--library', '--syntax', 'python', '--interface')
        self.assertEqual(status, 0, report)
        function, = report['interface']['functions']
        self.assertIsNone(function['returns'])
        self.assertIsNone(function['parameters'][0]['type'])
    def test_interface_python_fields_follow_assignments_not_parameter_names(self):
        source = self.source('''class Box:
    def __init__(self, value:int):
        self.stored=value
        self.extra=7
    def get(self)->int:
        return self.stored

def read(box:Box)->int:
    return box.get()
''', 'python_class.ail')
        status, report = self.check(source, '--syntax', 'python', '--interface')
        self.assertEqual(status, 0, report)
        box, = report['interface']['structs']
        self.assertEqual(box['fields'], [dict(name='stored', type='int'), dict(name='extra', type=None)])
        self.assertEqual(box['constructor_parameters'][0]['name'], 'value')
    def test_types_used_exception_values_keep_only_reachable_structs(self):
        import ast
        text = ('class Unused:\n\n    def __init__(self, n: int):\n        self.n = n\n\nclass Used:\n\n    def __init__(self, error: exception):\n        self.error = error\n\ndef keep(value: Used) -> Used:\n    return value\n\ndef lookup(items: list[exception]) -> exception:\n    return items[0]\n')
        tree = ast.parse(text)
        for symbol, expected in (('keep', ['Used']), ('lookup', [])):
            with self.subTest(symbol=symbol):
                report = ail_chatgpt._source_interface(tree, [symbol], True)
                self.assertEqual(report['struct_selection'], 'reachable_declared_types')
                self.assertEqual([item['name'] for item in report['structs']], expected)

    def test_types_used_transitive_fields_methods_and_callback_annotations(self):
        source=self.source('class Gamma:\n\n    def __init__(self, number: int):\n        self.number = number\n\nclass Beta:\n\n    def __init__(self, value: int):\n        self.value = value\n\n    def read(self, other: Gamma) -> int:\n        return other.number\n\nclass Alpha:\n\n    def __init__(self, child: Beta):\n        self.child = child\n\nclass Unused:\n\n    def __init__(self, text: str):\n        self.text = text\n\ndef chosen(value: Alpha, callback: Callable[[Gamma], Beta]) -> Alpha:\n    return value\n\ndef irrelevant(value: Unused) -> Unused:\n    return value\n')
        status,report=self.check(source,'--library','--interface','--symbol','chosen','--types-used')
        self.assertEqual(status,0,report)
        self.assertEqual([item['name'] for item in report['interface']['structs']],['Gamma','Beta','Alpha'])
        self.assertEqual(report['interface']['struct_selection'],'reachable_declared_types')
        self.assertEqual(report['checked_functions'],7)
        status,report=self.check(source,'--library','--interface','--symbol','chosen')
        self.assertEqual(status,0,report);self.assertEqual(len(report['interface']['structs']),4)
        self.assertNotIn('struct_selection',report['interface'])

    def test_types_used_unknown_fields_keep_all_and_unselected_errors_still_fail(self):
        source=self.source('''class Box:
    def __init__(self, value:int):
        self.stored=value
        self.extra=7
    def get(self)->int:
        return self.stored
class Other:
    def __init__(self, value:int):
        self.value=value
def chosen(box:Box)->int:
    return box.get()
''')
        status,report=self.check(source,'--syntax','python','--interface','--symbol','chosen','--types-used')
        self.assertEqual(status,0,report);self.assertEqual(report['interface']['struct_selection'],'all_when_unknown')
        self.assertEqual([item['name'] for item in report['interface']['structs']],['Box','Other'])
        source=self.source("class Box:\n\n    def __init__(self, value: int):\n        self.value = value\n\ndef chosen(x: int) -> int:\n    return x\n\ndef bad() -> int:\n    return 'bad'\n")
        status,report=self.check(source,'--library','--interface','--symbol','chosen','--types-used')
        self.assertEqual(status,1,report);self.assertNotIn('interface',report)

    def test_types_used_configuration_scalar_results_and_bundled_api(self):
        source=self.source('class Unused:\n\n    def __init__(self, value: int):\n        self.value = value\n\ndef chosen(x: int) -> int:\n    return x\n')
        for args in (('--types-used',),('--interface','--types-used'),('--symbol','chosen','--types-used')):
            status,report=self.check(source,'--library',*args)
            self.assertEqual((status,report['diagnostics'][0]['code']),(2,'configuration'))
        status,report=self.check(source,'--library','--interface','--symbol','chosen','--types-used')
        self.assertEqual(status,0,report);self.assertEqual(report['interface']['structs'],[])
        status,report=self.check(Path('csv_column_stats'),'--symbol','csv_column_stats','--types-used',command='api')
        self.assertEqual(status,0,report)
        self.assertEqual([item['name'] for item in report['interface']['structs']],['IntegerColumnStats'])
    def test_types_used_recursive_type_graph_and_unknown_function_fallback(self):
        import ast
        tree=ast.parse('''class First:
    def __init__(self, value:Second):
        self.value=value
class Second:
    def __init__(self, value:First):
        self.value=value
class Unused:
    def __init__(self, value:int):
        self.value=value
def selected(value:First)->First:
    return value
''')
        api=ail_chatgpt._source_interface(tree,['selected'],True)
        self.assertEqual([item['name'] for item in api['structs']],['First','Second'])
        source=self.source('''class Box:
    def __init__(self, value:int):
        self.value=value
def chosen(x):
    return x*x
''')
        status,report=self.check(source,'--syntax','python','--interface','--symbol','chosen','--types-used')
        self.assertEqual(status,0,report);self.assertEqual(report['interface']['struct_selection'],'all_when_unknown')
        self.assertEqual([item['name'] for item in report['interface']['structs']],['Box'])
    def test_types_used_quoted_names_aliases_and_unknown_annotation_shapes_fallback(self):
        import ast
        template='class Box:\n    def __init__(self,value:int):\n        self.value=value\ndef chosen(x:ANNOTATION)->int:\n    return 0\n'
        for annotation in ("'Box'", "list['Box']", 'UnknownAlias', 'typing.Box', 'Callable[...,int]'):
            with self.subTest(annotation=annotation):
                api=ail_chatgpt._source_interface(ast.parse(template.replace('ANNOTATION',annotation)),['chosen'],True)
                self.assertEqual(api['struct_selection'],'all_when_unknown')
                self.assertEqual([item['name'] for item in api['structs']],['Box'])
    def test_interface_symbol_selection_and_configuration_errors(self):
        source=self.source('def one(x: int) -> int:\n    return x + 1\n\ndef two(x: int) -> int:\n    return x * 2\n')
        status,report=self.check(source,'--library','--interface','--symbol','two','--symbol','two')
        self.assertEqual(status,0,report)
        self.assertEqual([fn['name'] for fn in report['interface']['functions']],['two'])
        self.assertEqual(report['checked_functions'],2)
        for args in (('--symbol','one'),('--interface','--symbol','missing')):
            status,report=self.check(source,'--library',*args)
            self.assertEqual(status,2)
            self.assertEqual(report['diagnostics'][0]['code'],'configuration')
            self.assertNotIn('interface',report)

    def test_interface_selection_retains_structs_and_checks_unselected_bodies(self):
        source=self.source('class Item:\n\n    def __init__(self, value: int):\n        self.value = value\n\ndef take(item: Item) -> int:\n    return item.value\n\ndef other() -> int:\n    return 3\n')
        status,report=self.check(source,'--library','--interface','--symbol','take')
        self.assertEqual(status,0,report)
        self.assertEqual([fn['name'] for fn in report['interface']['functions']],['take'])
        self.assertEqual([item['name'] for item in report['interface']['structs']],['Item'])
        source=self.source("def good() -> int:\n    return 1\n\ndef bad() -> int:\n    return 'wrong'\n")
        status,report=self.check(source,'--library','--interface','--symbol','good')
        self.assertEqual(status,1)
        self.assertNotIn('interface',report)
    def test_operator_and_brace_syntax_failures(self):
        for text in ('fn main()->int {return 1 + * 2;}', 'fn main()->int {return 1;'):
            with self.subTest(text=text):
                status, report = self.check(self.source(text))
                self.assertEqual(status, 1)
                self.assertEqual(report['status'], 'failed')
                self.assertEqual(report['stage'], 'loader')
                self.assertTrue(report['diagnostics'][0]['message'])

    def test_type_argument_missing_return_and_undeclared_function(self):
        texts = ('fn take(x:int)->int {return x;} fn main()->int {return take("bad");}',
                 # main itself may fall off its end (it exits 0); any other int function may not.
                 'fn f()->int {let x:int=1;} fn main()->int {return f();}', 'fn main()->int {return missing(1);}')
        for text in texts:
            with self.subTest(text=text):
                status, report = self.check(self.source(text))
                self.assertEqual(status, 1)
                self.assertEqual(report['status'], 'failed')
                self.assertTrue(report['diagnostics'][0]['message'])
                diagnostic = report['diagnostics'][0]
                self.assertEqual(diagnostic['path'], str(self.root / 'source.ail'))
                statement = 'return take' in text or 'return missing' in text
                self.assertEqual(diagnostic['function'], 'main' if statement else 'f')
                self.assertEqual(diagnostic['location_kind'], 'source_statement' if statement else 'function_declaration')
                self.assertEqual(diagnostic['line'], 1)
                self.assertEqual(diagnostic['column'], text.index('return' if statement and 'return missing' in text else 'return take' if statement else 'fn f') + 1)

    def test_type_diagnostic_identifies_original_imported_function(self):
        text = "# 日本語😀 fake fn ignored\ndef take(x: int) -> int:\n    return x\n\ndef bad() -> int:\n    return take('wrong')\n"
        module = self.source(text, '部品 😀.ail')
        source = self.source('fn main()->int {return bad();}')
        status, report = self.check(source, '--module', module)
        self.assertEqual(status, 1)
        diagnostic = report['diagnostics'][0]
        self.assertEqual((diagnostic['path'], diagnostic['line'], diagnostic['column']), (str(module), 6, 5))
        self.assertEqual((diagnostic['function'], diagnostic['location_kind']), ('bad', 'source_statement'))

    def test_contract_diagnostic_identifies_struct_method(self):
        source = self.source('''struct Item {value:int;}
impl Item {
  fn bad(self)->int {let ignored=1;}
}
fn main()->int {return 0;}
''')
        status, report = self.check(source)
        self.assertEqual(status, 1)
        diagnostic = report['diagnostics'][0]
        self.assertEqual((diagnostic['code'], diagnostic['function']), ('contract', 'Item.bad'))
        self.assertEqual((diagnostic['path'], diagnostic['line'], diagnostic['column']), (str(source), 3, 3))

    def test_python_type_diagnostic_uses_original_declaration_line(self):
        source = self.source('''# 日本語😀
def take(x:int)->int:
    return x

def main()->int:
    return take("wrong")
main()
''')
        status, report = self.check(source, '--syntax', 'python')
        self.assertEqual(status, 1)
        diagnostic = report['diagnostics'][0]
        self.assertEqual((diagnostic['path'], diagnostic['line'], diagnostic['column']), (str(source), 6, 5))
        self.assertEqual((diagnostic['function'], diagnostic['location_kind']), ('main', 'source_statement'))
    def test_type_method_and_ambiguous_compiler_name_locations(self):
        source = self.source('''struct Item {value:int;}
impl Item {fn bad(self)->int {return "wrong";}}
fn main()->int {let item=Item(1);return item.bad();}
''')
        status, report = self.check(source)
        self.assertEqual(status, 1)
        diagnostic = report['diagnostics'][0]
        self.assertEqual((diagnostic['function'], diagnostic['location_kind']), ('Item.bad', 'function_declaration'))
        self.assertEqual((diagnostic['path'], diagnostic['line'], diagnostic['column']), (str(source), 2, 12))
        source = self.source('''struct Item {value:int;}
impl Item {fn bad(self)->int {let ignored=1;}}
fn Item__bad()->int {return 1;}
fn main()->int {return 0;}
''')
        status, report = self.check(source)
        self.assertEqual(status, 1)
        diagnostic = report['diagnostics'][0]
        self.assertEqual(diagnostic['code'], 'contract')
        self.assertIsNone(diagnostic['path'])
        self.assertIsNone(diagnostic['line'])
        self.assertIsNone(diagnostic['location_kind'])
    def test_statement_locations_survive_method_reordering_and_import_offsets(self):
        text = 'class Item:\n\n    def __init__(self, value: int):\n        self.value = value\n\n    def bad(self) -> int:\n        if self.value:\n            return missing(self.value)\n        return 0\n\ndef helper() -> int:\n    return 0\n'
        module = self.source(text, '部品 😀.ail')
        self.source('def extra() -> int:\n    return 1\n', 'extra.ail')
        source = self.source('use extra;\nfn main()->int {return 0;}')
        status, report = self.check(source, '--module', module)
        diagnostic = report['diagnostics'][0]
        self.assertEqual(status, 1, report)
        self.assertEqual((diagnostic['path'], diagnostic['line'], diagnostic['column']), (str(module), 8, 13))
        self.assertEqual((diagnostic['function'], diagnostic['location_kind']), ('Item.bad', 'source_statement'))

    def test_same_line_and_unicode_statement_positions(self):
        text = 'fn main()->int {let label="日本😀"; return missing(1);}'
        status, report = self.check(self.source(text))
        self.assertEqual(status, 1, report)
        diagnostic = report['diagnostics'][0]
        self.assertEqual((diagnostic['line'], diagnostic['column'], diagnostic['location_kind']),
                         (1, text.index('return') + 1, 'source_statement'))
    def test_ambiguous_python_same_line_uses_declaration_fallback(self):
        source = self.source('def main()->int:\n    x=1; return missing(x)\nmain()\n')
        status, report = self.check(source, '--syntax', 'python')
        self.assertEqual(status, 1, report)
        diagnostic = report['diagnostics'][0]
        self.assertEqual((diagnostic['line'], diagnostic['column'], diagnostic['location_kind']),
                         (1, 1, 'function_declaration'))
    def test_unicode_module_paths_and_cycle(self):
        modules = self.root / '部品 😀'; modules.mkdir()
        self.source('def value() -> int:\n    return 7\n', '部品 😀/helper.ail')
        entry = self.source('from helper import *\nimport sys\n\ndef main() -> int:\n    return value()\n\nif __name__ == "__main__":\n    sys.exit(main())\n', '入力 😀.ail')
        self.assertEqual(self.check(entry, '-I', modules)[0], 0)
        self.source('from other import *\ndef value() -> int:\n    return 7\n', '部品 😀/helper.ail')
        self.source('from helper import *\ndef other() -> int:\n    return 1\n', '部品 😀/other.ail')
        status, report = self.check(entry, '-I', modules)
        self.assertEqual(status, 1)
        self.assertIn('cycle', report['diagnostics'][0]['message'])

    def test_int64_literal_limits_and_original_positions(self):
        for value in ('9223372036854775807', '-9223372036854775808'):
            with self.subTest(value=value):
                self.assertEqual(self.check(self.source(f'fn main()->int {{return {value};}}'))[0], 0)
        for value in ('9223372036854775808', '-9223372036854775809', '+9223372036854775808'):
            with self.subTest(value=value):
                text = f'# 日本語😀\nfn main()->int {{let label="日本😀"; return {value};}}\n'
                source = self.source(text)
                status, report = self.check(source)
                diagnostic = report['diagnostics'][0]
                self.assertEqual(status, 1, report)
                self.assertEqual((diagnostic['path'], diagnostic['line'], diagnostic['column']),
                                 (str(source), 2, text.splitlines()[1].index('return') + 1))
                self.assertEqual(diagnostic['location_kind'], 'source')

    def test_imported_and_python_int64_literal_positions(self):
        module = self.source('# 日本語😀\nLIMIT = 9223372036854775808\n\ndef limit() -> int:\n    return LIMIT\n', '数値 😀.ail')
        source = self.source('fn main()->int {return limit();}')
        status, report = self.check(source, '--module', module)
        diagnostic = report['diagnostics'][0]
        self.assertEqual(status, 1, report)
        self.assertEqual((diagnostic['path'], diagnostic['line'], diagnostic['column']), (str(module), 2, 9))
        text = 'def main()->int:\n    label="日本😀"; return -9223372036854775809\nmain()\n'
        source = self.source(text)
        status, report = self.check(source, '--syntax', 'python')
        diagnostic = report['diagnostics'][0]
        self.assertEqual(status, 1, report)
        self.assertEqual((diagnostic['path'], diagnostic['line'], diagnostic['column']),
                         (str(source), 2, text.splitlines()[1].index('-922') + 1))
    def test_missing_inputs_configuration_and_dependency(self):
        status, report = self.check(self.root / 'missing.ail')
        self.assertEqual(status, 2); self.assertEqual(report['diagnostics'][0]['code'], 'io')
        source = self.source('fn main()->int {return 0;}')
        status, report = self.check(source, '-I', self.root / 'missing')
        self.assertEqual(status, 2); self.assertEqual(report['diagnostics'][0]['code'], 'configuration')
        source = self.source('use absent; fn main()->int {return 0;}')
        status, report = self.check(source)
        self.assertEqual(status, 2); self.assertEqual(report['diagnostics'][0]['code'], 'dependency')

    def test_ail_original_operator_location_with_unicode(self):
        text = '# 日本語😀\nfn main()->int {\n    if true && false {return 1;}\n    return 0;\n}\n'
        status, report = self.check(self.source(text))
        self.assertEqual(status, 1)
        diagnostic = report['diagnostics'][0]
        self.assertEqual(diagnostic['line'], 3)
        self.assertEqual(diagnostic['column'], text.splitlines()[2].index('&') + 1)
        self.assertEqual(diagnostic['path'], str(self.root / 'source.ail'))

    def test_python_original_location_is_not_translated_ail_location(self):
        source = self.source('def main() -> int:\n    return 1 + * 2\n')
        status, report = self.check(source, '--syntax', 'python')
        self.assertEqual(status, 1)
        diagnostic = report['diagnostics'][0]
        self.assertEqual(diagnostic['line'], 2)
        self.assertEqual(diagnostic['path'], str(source))
        source = self.source('fn main()->int {return 1 + * 2;}')
        _, report = self.check(source, '--syntax', 'ail')
        # Lexer positions may be available; translated Python's line is never substituted.
        self.assertEqual(report['stage'], 'loader')


if __name__ == '__main__':
    unittest.main()