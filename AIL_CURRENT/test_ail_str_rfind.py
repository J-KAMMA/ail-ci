"""Rightmost string search: Unicode scalar oracle, owning aliases, and buffer guards."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

from ail_syntax import translate
sys.path.insert(0,str(Path(__file__).resolve().parent/'python/pkg-v12'))
from pyfunc import to_c
from pyfront import Unsupported
import cruntime
import test_ail_c_objects as support
from test_ail_text_find_search import HEADERS, WRAPPERS

CASES=[('a😀b\0c😀','😀'),('a😀b\0c😀','\0c'),('aaaaa','aaa'),
       ('abababa','aba'),('😀😀','😀😀'),('',''),('','x'),('abc',''),
       ('abc','missing'),('a\0a\0','\0'),('éé','é'),('abc','abcd')]

def source():
    import json
    calls=''.join('print(search('+json.dumps(h,ensure_ascii=False)+','+json.dumps(q,ensure_ascii=False)+'));' for h,q in CASES)
    return '''
fn search(source:str,needle:str)->int {let alias=source;let receiver:str=alias;return receiver.rfind(needle);}
fn owned()->str {return "a😀b😀";}
fn callback_search(callback:Callable[[],str],needle:str)->int {let alias=callback();return alias.rfind(needle);}
fn recv()->str {print("receiver");return "abaaba";}
fn needle()->str {print("needle");return "aba";}
fn main()->int {'''+calls+'''print(callback_search(owned,"😀"));print(recv().rfind(needle()));print(b"abaaba".rfind(b"aba"));return 0;}
'''

class StrRfindTypeTests(unittest.TestCase):
    def test_alias_callback_and_evaluation_order_source_compiles(self):
        code=to_c(translate(source()),strict=True)
        self.assertIn('ail_text_rfind_points(_receiver, _needle)',code)
        self.assertIn('ail_text_find_points(',cruntime.emit({'STR'}))

    def test_wrong_type_extra_bounds_and_keywords_are_refused(self):
        for expression in ('source.rfind(b"x")','source.rfind(needle,"x")',
                           'source.rfind(needle,0,2,3)','source.rfind(needle=needle)'):
            with self.subTest(expression=expression),self.assertRaises(Unsupported):
                to_c(translate('fn probe(source:str,needle:str)->int {return '+expression+';}',module=True),library=True,strict=True)

@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'),'installed C compiler required')
class StrRfindNativeTests(unittest.TestCase):
    setUp=support.CObjectTests.setUp
    write=support.CObjectTests.write
    command=support.CObjectTests.command
    ail_build=support.CObjectTests.ail_build
    check_run=support.CObjectTests.check_run

    def test_whole_output_against_python_unicode_oracle(self):
        expected=''.join(str(h.rfind(q))+'\n' for h,q in CASES)+'3\nreceiver\nneedle\n3\n3\n'
        self.check_run(self.ail_build('str_rfind',source()),expected)

    def test_compact_wide_surrogate_boundaries_guard_pages_and_fatal_metadata(self):
        compiler=os.environ.get('PIPE_CC') or shutil.which('gcc') or shutil.which('cc')
        wrappers=WRAPPERS.replace('ail_text_find_points','ail_text_rfind_points').replace('if(mode==5)h.n=INT64_MAX;', 'if(mode==5)h.n=INT64_MAX;if(mode==6)q.n=INT64_MAX;')
        # "a😀b😀" in UTF-8: the astral character is 4 bytes but one character, so the last match
        # is character 3 and the empty needle matches at the end, character 4.
        scalar_probe=r'''
 uint8_t astral[]={'a',0xF0,0x9F,0x98,0x80,'b',0xF0,0x9F,0x98,0x80};
 uint8_t emoji[]={0xF0,0x9F,0x98,0x80},ab[]={'a',0xF0,0x9F,0x98,0x80,'b'};
 h=(ail_str){astral,10,0};
 if(ail_text_rfind_points(h,(ail_str){emoji,4,0})!=3)return 104;
 if(ail_text_rfind_points(h,(ail_str){NULL,0,1})!=4)return 105;
 if(ail_text_rfind_points(h,(ail_str){ab,6,0})!=0)return 106;
'''
        wrappers=wrappers.replace(' size_t page;unsigned char *mapping;',scalar_probe+' size_t page;unsigned char *mapping;')        # Existing guard-page probe covers compact/wide and both allocation edges.
        path=self.write('rfind_guards.c',HEADERS+cruntime.emit({'STR'})+wrappers)
        binary=self.root/('rfind_guards.exe' if os.name=='nt' else 'rfind_guards')
        result=subprocess.run([compiler,'-std=c11','-D_DEFAULT_SOURCE','-O2',str(path),'-lm','-o',str(binary)],capture_output=True,timeout=180)
        self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
        self.check_run(binary,'')
        for mode in range(1,7):
            with self.subTest(mode=mode):
                result=subprocess.run([str(binary),str(mode)],capture_output=True,timeout=30)
                self.assertNotEqual(result.returncode,0)
                self.assertNotEqual(result.returncode,91)

if __name__=='__main__':unittest.main()