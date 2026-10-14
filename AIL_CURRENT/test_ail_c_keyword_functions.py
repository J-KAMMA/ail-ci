"""Source function identifiers never leak C keywords into C symbols or lose AIL identities."""
import os
import re
import shutil
import sys
import unittest

from ail_syntax import translate, SyntaxErrorAIL
import test_ail_c_objects as support


def compiler():
    sys.path.insert(0,str(support.ROOT/'python/pkg-v12'))
    from pyfunc import to_c, _mangle_csym, _C_KEYWORDS
    return to_c,_mangle_csym,_C_KEYWORDS


class CKeywordFunctionCodeTests(unittest.TestCase):
    def test_standard_keyword_symbols_use_central_mangler_without_changing_valid_names(self):
        to_c,mangle,keywords=compiler()
        try:
            required=set('auto break case char const continue default do double else enum extern float for goto if inline int long register restrict return short signed sizeof static struct switch typedef union unsigned void volatile while _Alignas _Alignof _Atomic _Bool _Complex _Generic _Imaginary _Noreturn _Static_assert _Thread_local _BitInt alignas alignof bool constexpr false nullptr static_assert thread_local true typeof typeof_unqual'.split())
            self.assertEqual(keywords,required)
            for name in keywords:
                self.assertNotIn(mangle(name),keywords)
                self.assertNotEqual(mangle(name),name)
            self.assertEqual(mangle('ordinary'),'ordinary')
            accepted=[]
            for name in sorted(keywords):
                source='fn '+name+'(value:int)->int {return value*2;} fn main()->int {return 0;}'
                try:source=translate(source)
                except (SyntaxError,ValueError):continue
                try:generated=to_c(source,name='run',strict=True)
                except Exception as error:
                    self.fail(name+': '+str(error))
                self.assertNotRegex(generated,r'int64_t\s+'+re.escape(name)+r'\s*\(')
                accepted.append(name)
            self.assertIn('double',accepted)
        finally:sys.path.pop(0)

    def test_double_calls_callback_recursion_units_and_valid_collision(self):
        to_c,_,_=compiler()
        try:
            source='''fn double(value:int)->int {if value<=0 {return 0;}return 2+double(value-1);}
fn py_double(value:int)->int {return value+10;}
fn main()->int {let cb:Callable[[int],int]=double;return cb(3)+py_double(1);}'''
            info={'_want_units':True}
            generated=to_c(translate(source),name='run',strict=True,info=info)
            self.assertRegex(generated,r'int64_t\s+py_py_double\s*\(')
            self.assertRegex(generated,r'int64_t\s+py_double\s*\(')
            self.assertNotRegex(generated,r'int64_t\s+double\s*\(')
            self.assertIn('v_cb = py_py_double;',generated)
            recursive_body=dict(info['c_units'][1])['double']
            self.assertGreaterEqual(recursive_body.count('py_py_double('),2)
            self.assertEqual([name for name,_ in info['c_units'][1]],['double','py_double','main'])
            self.assertIn('double',info['function_signatures'])
        finally:sys.path.pop(0)

    def test_metadata_only_regions_preserve_exact_generated_c_and_original_names(self):
        to_c,_,_=compiler()
        try:
            sources=[
                'fn double(value:int)->int {return value*2;} fn main()->int {return double(3);}',
                'fn scaled(value:int)->int {return value*3+1;} fn main()->int {return scaled(7);}',
                'struct Box {values:list[str];} fn main()->int {let box=Box(["日本😀"]);box.values.append("tail");let old=box.values;box.values.clear();for text in old {print(text);}return 0;}',
                'fn fail()->exception {return ValueError("owned");} fn main()->int {try {raise fail();} except ValueError as error {print(error.message);} return 0;}',
            ]
            for source in sources:
                with self.subTest(source=source):
                    text=translate(source)
                    plain=to_c(text,name='run',strict=True)
                    info={'_want_source_regions':True}
                    reported=to_c(text,name='run',strict=True,info=info)
                    self.assertEqual(reported,plain)
                    self.assertNotIn('c_units',info)
                    self.assertTrue(info['c_source_regions'])
                    for original,body in info['c_source_regions']:
                        self.assertEqual(reported.count(body),1,original)
                    if 'fn double' in source:
                        self.assertEqual([name for name,_ in info['c_source_regions']],['double','main'])
        finally:sys.path.pop(0)
    def test_keyword_library_and_unrenamed_entry_are_safe(self):
        to_c,_,_=compiler()
        try:
            source=translate('fn double(value:int)->int {return value*2;}',module=True)
            for options in ({'library':True},{'entry':'double'},{'name':'double'}):
                with self.subTest(options=options):
                    generated=to_c(source,strict=True,**options)
                    self.assertRegex(generated,r'int64_t\s+py_double\s*\(')
                    self.assertNotRegex(generated,r'int64_t\s+double\s*\(')
            renamed=translate('fn py_double(value:int)->int {return value+1;} fn main()->int {return py_double(1);}')
            generated=to_c(renamed,name='double',strict=True)
            self.assertRegex(generated,r'int64_t\s+py_py_double\s*\(')
            self.assertRegex(generated,r'int64_t\s+py_double\s*\(')
        finally:sys.path.pop(0)


@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'),'installed C compiler required')
class CKeywordFunctionNativeTests(unittest.TestCase):
    setUp=support.CObjectTests.setUp
    command=support.CObjectTests.command
    write=support.CObjectTests.write
    ail_build=support.CObjectTests.ail_build
    check_run=support.CObjectTests.check_run

    def test_original_keyword_function_name_in_native_and_source_free_callback(self):
        provider=self.ail_build('provider','''fn double(value:int)->int {if value<=0 {return 0;}return 2+double(value-1);}
fn choose()->Callable[[int],int] {return double;}''',library=True)
        consumer='''fn main()->int {let cb=choose();print(double(3),cb(4));return 0;}'''
        self.check_run(self.ail_build('consumer',consumer,provider),'6 8\n')
        whole='''fn double(value:int)->int {return value*2;} fn main()->int {print(double(3));return 0;}'''
        self.check_run(self.ail_build('whole',whole),'6\n')


if __name__=='__main__':unittest.main()