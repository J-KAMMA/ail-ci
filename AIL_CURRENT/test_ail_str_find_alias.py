"""str.find alias inference, with separate bytes evidence and native output fixture."""
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
import test_ail_c_objects as support

SOURCES=[
 'fn probe(source:str,needle:str)->int {let a=source;a+="x";return a.find(needle);}',
 'fn probe(source:str,needle:str)->int {let a=source;for a in ["x"] {print(a);}return a.find(needle);}',
 'fn probe(source:str,needle:str)->int {let receiver=source;receiver=receiver;return receiver.find(needle);}',
 'fn probe(callback:Callable[[],str],needle:str)->int {let receiver=callback();return receiver.find(needle);}',
 'fn text()->str {return "owned";} fn probe(needle:str)->int {let receiver=text();return receiver.find(needle);}',
 'fn probe(source:str,needle:str)->int {let receiver=source;return receiver.find(needle);}',
 'fn probe(source:str,needle:str)->int {let first=source;let second=first;let output:int=second.find(needle);return output;}',
 'fn probe(source:str,needle:str)->int {let receiver:str=source;let output=receiver.find(needle);return output;}',
 'fn probe(source:str,needle:str,flag:int)->int {let receiver=source;if flag {receiver="replacement";}else {receiver=source;}return receiver.find(needle);}',
 'fn probe(source:str,needle:str,flag:int)->int {let receiver=source if flag else "replacement";return receiver.find(needle);}',
 'fn probe(source:bytes,needle:bytes)->int {let receiver=source;return receiver.find(needle);}',
 'fn probe(source,needle)->int {return source.find(needle);}',
]

class StrFindAliasTypeTests(unittest.TestCase):
    def test_aliases_rebind_and_genuine_bytes_find(self):
        for source in SOURCES:
            with self.subTest(source=source):
                to_c(translate(source,module=True),name='probe',library=True,strict=True)

    def test_str_bytes_contradictions_are_refused(self):
        for source in [
            'fn probe(source:str,needle:bytes)->int {let receiver=source;return receiver.find(needle);}',
            'fn probe(source:bytes,needle:str)->int {let receiver=source;return receiver.find(needle);}',
            'fn probe(source:str,needle:str)->int {let receiver=source;receiver=b"x";return receiver.find(needle);}',
        ]:
            with self.subTest(source=source),self.assertRaises(Unsupported):
                to_c(translate(source,module=True),name='probe',library=True,strict=True)

    def test_uninitialized_cycles_and_non_str_writes_are_refused(self):
        for source in [
            'fn probe(needle:str)->int {let a=b;let b=a;return a.find(needle);}',
            'fn probe(needle:str)->int {let a=missing;return a.find(needle);}',
            'fn probe(source:str,needle:str)->int {let a=source;a=b"x";return a.find(needle);}',
            'fn probe(source:str,needle:str)->int {let a=source;a+=b"x";return a.find(needle);}',
            'fn probe(source:str,needle:str)->int {let a=source;for a in [b"x"] {print(a);}return a.find(needle);}',
            'fn probe(source:str,needle:str)->int {let a=source;for a in [1] {print(a);}return a.find(needle);}',
        ]:
            with self.subTest(source=source),self.assertRaises(Unsupported):
                to_c(translate(source,module=True),name='probe',library=True,strict=True)
WHOLE='''
fn search(source:str,needle:str)->int {let first=source;let receiver:str=first;let result:int=receiver.find(needle);return result;}
fn main()->int {
 print(search("a😀b\\0c😀","😀"));print(search("a😀b\\0c😀","\\0c"));
 print(search("a😀b\\0c😀","missing"));print(search("a😀b\\0c😀",""));
 print(search("",""));print(search("","x"));
 let source="old";let alias=source;source="new";print(alias.find("old"));
 print(b"a\\0b".find(b"\\0"));return 0;
}
'''

@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'),'installed C compiler required')
class StrFindAliasNativeTests(unittest.TestCase):
    setUp=support.CObjectTests.setUp
    write=support.CObjectTests.write
    command=support.CObjectTests.command
    ail_build=support.CObjectTests.ail_build
    check_run=support.CObjectTests.check_run

    def test_unicode_nul_empty_absent_and_snapshot_indices(self):
        self.check_run(self.ail_build('str_find_alias',WHOLE),'1\n3\n-1\n0\n0\n-1\n0\n1\n')

    def test_source_free_owned_string_callback_alias(self):
        provider=self.ail_build('find_provider','fn provided()->str {return "a😀b\\0c😀";}',library=True)
        consumer='''
fn locate(callback:Callable[[],str],needle:str)->int {
 let source=callback();let alias=source;let result=alias.find(needle);return result;
}
fn main()->int {print(locate(provided,"\\0c"));print(locate(provided,"😀"));return 0;}
'''
        self.check_run(self.ail_build('find_consumer',consumer,provider),'3\n1\n')
if __name__=='__main__':unittest.main()