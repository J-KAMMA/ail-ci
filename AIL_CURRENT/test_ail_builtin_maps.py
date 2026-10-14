"""Pure candidate checks, without native compilation or execution."""
import sys
from pathlib import Path
import unittest

VALUE_TYPES = ('int', 'float', 'str', 'bytes')
METHODS = ('get', 'pop1', 'pop2', 'setdefault', 'keys', 'values', 'copy', 'clear', 'update')
MUTATING = {'pop1', 'pop2', 'setdefault', 'clear', 'update'}


def shape(value, method):
    mapping = 'dict[str,' + value + ']'
    name = 'pop' if method.startswith('pop') else method
    params = [('key', 'str')] if method == 'pop1' else [('key', 'str'), ('default', value)] if method in ('get', 'pop2', 'setdefault') else [('other', mapping)] if method == 'update' else []
    result = 'list[str]' if method == 'keys' else 'list[' + value + ']' if method == 'values' else mapping if method == 'copy' else 'void' if method in ('clear', 'update') else value
    return mapping, name, params, result


def source(value, method, *, arguments=None, borrowed=False, result_type=None):
    mapping, name, params, result = shape(value, method)
    headers = [('m', mapping), *params]
    receiver = 'm' if borrowed or method not in MUTATING else 'd'
    prefix = '' if receiver == 'm' else 'let d:' + mapping + '=m.copy();'
    args = ','.join(key for key, _ in params) if arguments is None else arguments
    call = receiver + '.' + name + '(' + args + ')'
    body = call + ';return 0;' if result == 'void' and result_type is None else 'let result:' + (result_type or result) + '=' + call + ';return result;'
    returns = 'int' if result == 'void' and result_type is None else result_type or result
    return 'fn probe(' + ','.join(key + ':' + kind for key, kind in headers) + ')->' + returns + ' {' + prefix + body + '}'



ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'python/pkg-v12'))
from ail_syntax import translate
from pyfunc import to_c, Unsupported
import ail_builtin_api as api


def compile_source(text):
    return to_c(translate(text, module=True), library=True, strict=True)


class TypedMapCandidateTests(unittest.TestCase):
    def test_all_published_bodies(self):
        for value in VALUE_TYPES:
            for method in METHODS:
                with self.subTest(value=value, method=method, source=source(value, method)):
                    self.assertTrue(compile_source(source(value, method)))

    def test_boundaries_are_refused(self):
        for value in VALUE_TYPES:
            for method in METHODS:
                mapping, name, params, result = shape(value, method)
                bad_arity = 'key,0,0' if method == 'pop1' else ','.join(key for key, _ in params) + (',0' if params else '0')
                with self.subTest(value=value, method=method, boundary='arity'), self.assertRaises(Unsupported):
                    compile_source(source(value, method, arguments=bad_arity))
                if method in MUTATING:
                    with self.subTest(value=value, method=method, boundary='borrowed mutation'), self.assertRaises(Unsupported):
                        compile_source(source(value, method, borrowed=True))
                if result == 'void':
                    with self.subTest(value=value, method=method, boundary='void value'), self.assertRaises(Unsupported):
                        compile_source(source(value, method, result_type='int'))
                if method in ('get', 'pop1', 'pop2', 'setdefault'):
                    args = '0' + (',default' if len(params) == 2 else '')
                    with self.subTest(value=value, method=method, boundary='key type'), self.assertRaises(Unsupported):
                        compile_source(source(value, method, arguments=args))
            bad_default = '"wrong"' if value in ('int', 'float', 'bytes') else '0'
            with self.subTest(value=value, boundary='default type'), self.assertRaises(Unsupported):
                compile_source(source(value, 'get', arguments='key,' + bad_default))

    def test_declarations_preserve_generic_unknown_and_ownership(self):
        self.assertFalse(api.DECLARATIONS['dict.get']['signature_known'])
        for value in VALUE_TYPES:
            key='dict[str,'+value+']'
            self.assertEqual(api.DECLARATIONS[key+'.copy']['overloads'][-1]['result']['ownership'],'owned_snapshot')
            self.assertEqual(api.DECLARATIONS[key+'.get']['overloads'][-1]['receiver']['access'],'readonly')
            self.assertEqual(api.DECLARATIONS[key+'.clear']['overloads'][-1]['context'],'statement')
            self.assertEqual(len(api.DECLARATIONS[key+'.pop']['overloads']),2)



import json
import os
import shutil
import struct
import subprocess
import test_ail_c_objects as support

def render_expression(kind,expression):
    if kind=='float':return 'float64_encode(['+expression+'],0).hex()'
    if kind=='str':return '('+expression+').encode().hex()'
    if kind=='bytes':return '('+expression+').hex()'
    return 'str('+expression+')'

def reference_string(kind,value):
    if kind=='float':return struct.pack('<d',value).hex()
    if kind=='str':return value.encode().hex()
    if kind=='bytes':return value.hex()
    return str(value)

@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'),'installed C compiler required')
class TypedMapNativeTests(unittest.TestCase):
    setUp=support.CObjectTests.setUp
    write=support.CObjectTests.write
    command=support.CObjectTests.command
    ail_build=support.CObjectTests.ail_build

    def test_all_methods_preserve_snapshots_and_missing_pop(self):
        key='k\0😀'
        datasets={'int':(-7,5,9,0),'float':(-0.0,5.25,-9.5,0.0),
                  'str':('old\0😀','newé','extra',''),
                  'bytes':(b'old\0\xff',b'new\x80',b'extra',b'')}
        functions=[];expected=[]
        for kind,(initial,replacement,extra,default) in datasets.items():
            literal=lambda value:repr(value) if isinstance(value,bytes) else json.dumps(value,ensure_ascii=False)
            mapping='dict[str,'+kind+']';key_literal=literal(key)
            function=f'''fn check_{kind}()->void {{
 let d:{mapping}={{{key_literal}:{literal(initial)}}};
 let saved=d.copy();let keys=d.keys();let values=d.values();
 let found=d.get({key_literal},{literal(default)});let absent=d.get("missing",{literal(default)});
 let popped=d.pop({key_literal});let miss=d.pop("missing",{literal(default)});
 let seed=d.setdefault({key_literal},{literal(replacement)});
 d.update({{"extra":{literal(extra)}}});
 let still=d.setdefault({key_literal},{literal(default)});d.clear();
'''
            expressions=[render_expression(kind,v) for v in ('found','absent','popped','miss','seed','still','saved['+key_literal+']','values[0]')]
            expressions+=['keys[0].encode().hex()','str(len(d))','str(len(saved))']
            function+='write_stdout_bytes(('+ '+"|"+'.join(expressions)+'+"\\n").encode());'
            function+='try {let missing=d.pop("missing");print(0);} except KeyError {print(1);} return;}\n'
            functions.append(function)
            reference={key:initial};saved=reference.copy();keys=list(reference.keys());values=list(reference.values())
            outputs=[reference.get(key,default),reference.get('missing',default),reference.pop(key),reference.pop('missing',default),reference.setdefault(key,replacement)]
            reference.update({'extra':extra});outputs+=[reference.setdefault(key,default),saved[key],values[0]];reference.clear()
            expected.append('|'.join([*(reference_string(kind,v) for v in outputs),keys[0].encode().hex(),str(len(reference)),str(len(saved))])+'\n1\n')
        program=''.join(functions)+'fn main()->int {'+''.join('check_'+kind+'();' for kind in datasets)+'return 0;}'
        executable=self.ail_build('typed_map_methods',program)
        result=subprocess.run([str(executable)],capture_output=True,timeout=30)
        self.assertEqual((result.returncode,result.stdout.replace(b'\r\n',b'\n'),result.stderr),(0,''.join(expected).encode(),b''))
if __name__ == '__main__':
    unittest.main()
