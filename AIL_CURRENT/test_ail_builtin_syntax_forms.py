"""Every published context-bound example must pass pure strict library C generation."""
import sys
from pathlib import Path
import unittest

from ail_builtin_syntax_forms import SYNTAX_FORMS, forms_for

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'python/pkg-v12'))
from ail_syntax import translate
from pyfunc import to_c


class BuiltinSyntaxFormsTests(unittest.TestCase):
    def test_all_published_forms_generate_c(self):
        self.assertTrue({'range','enumerate','reversed','zip','map','open','print'} <= set(SYNTAX_FORMS))
        for symbol, forms in SYNTAX_FORMS.items():
            for form in forms:
                with self.subTest(symbol=symbol, source=form['source']):
                    translated = translate(form['source'], module=True)
                    generated = to_c(translated, library=True, strict=True)
                    self.assertIsInstance(generated, str)
                    self.assertTrue(generated)
                    self.assertFalse(form['compile_verified'])
                    self.assertFalse(form['runtime_verified'])
                    self.assertFalse(form['binding_verified'])
                    self.assertFalse(form['ordinary_call_signature_published'])
                    self.assertIsNone(form['generic_iterator_result_type'])

    def test_query_returns_copy_and_unknown_has_no_signature(self):
        forms = forms_for('map')
        forms[0]['inputs'][0]['type'] = 'changed'
        self.assertEqual(forms_for('map')[0]['inputs'][0]['type'], 'list[str]')
        self.assertEqual(forms_for('missing'), [])
        self.assertEqual(forms_for('open')[0]['expression_result_type'], 'str')
        self.assertIsNone(forms_for('print')[0]['expression_result_type'])



import os
import shutil
import test_ail_c_objects as support

@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'),'installed C compiler required')
class BuiltinSyntaxFormsNativeTests(unittest.TestCase):
    setUp=support.CObjectTests.setUp
    write=support.CObjectTests.write
    command=support.CObjectTests.command
    ail_build=support.CObjectTests.ail_build
    check_run=support.CObjectTests.check_run

    def test_all_forms_in_one_file_workload(self):
        source='\n'.join(forms[0]['source'].replace('fn probe(', 'fn syntax_'+name+'(')
                         for name,forms in SYNTAX_FORMS.items() if name in ('range','enumerate','reversed','zip','map','open','print'))
        source+='''
fn main()->int {
 print(syntax_range(0));print(syntax_range(4));
 print(syntax_enumerate([]));print(syntax_enumerate([1,-3,4]));
 print(syntax_reversed([1,-3,4]));print(syntax_zip([1,-3,4],[10,20]));
 print(syntax_map(["5","-2"]));
 write_stdout_bytes(syntax_open(sys.argv[1]).encode());
 print(syntax_print(7));return 0;
}
'''
        text='A😀\0Z'
        path=self.write('form-input.txt',text)
        xs=[1,-3,4];ys=[10,20]
        values=[sum(range(0)),sum(range(4)),sum(i+v for i,v in enumerate([])),
                sum(i+v for i,v in enumerate(xs)),sum(reversed(xs)),
                sum(a+b for a,b in zip(xs,ys)),sum(map(int,['5','-2']))]
        expected=''.join(str(v)+'\n' for v in values)+text+'7\n7\n'
        self.check_run(self.ail_build('all_builtin_forms',source),expected,path)
if __name__ == '__main__':
    unittest.main()
