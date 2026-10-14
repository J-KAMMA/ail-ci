"""Independent runtime references for context-only APIs and explicit JS profiles."""
import importlib.util,json,os,shutil,subprocess,sys,unittest
from pathlib import Path
from ail_syntax import translate
import ail_builtin_api as api
from ail_builtin_syntax_forms import SYNTAX_FORMS
import test_ail_c_objects as support
sys.path.insert(0,str(Path(__file__).resolve().parent/'python/pkg-v12'))
from pyfunc import to_c,Unsupported
NODE=shutil.which('node') or shutil.which('node.exe')

class ApiProfileTypeTests(unittest.TestCase):
    def test_js_keywords_are_refused_in_value_and_statement_contexts(self):
        cases=[('jsdiv(1.0,2.0,extra=3)','float'),('jsnegzero(-0.0,extra=3)','int'),('jscharat("x",0,extra=3)','str')]
        for expression,kind in cases:
            for body in ('let result:'+kind+'='+expression+';return 0;',expression+';return 0;'):
                with self.subTest(expression=expression,body=body),self.assertRaises(Unsupported):
                    to_c(translate('fn main()->int {'+body+'}'),strict=True)

    def test_context_catalog_separates_syntax_only_from_callable_shapes(self):
        payload=api.query();entries={e['symbol']:e for e in payload['entries']}
        for name in ('ord','dict','set','file_chunks','dict[str,float].items'):
            with self.subTest(symbol=name):
                e=entries[name];self.assertFalse(e['signature_known']);self.assertEqual(e['overloads'],[])
                self.assertEqual(e['classification'],'syntax_only')
                self.assertIn(name,payload['coverage']['syntax_only_symbols'])
                self.assertTrue(e['syntax_forms']);self.assertFalse(e['runtime_verified'])
        for name in ('jsdiv','jsnegzero','jscharat'):
            self.assertTrue(entries[name]['signature_known'])
            self.assertFalse(entries[name]['binding_verified'])
        hexadecimal=entries['hex']
        self.assertTrue(hexadecimal['signature_known'])
        self.assertFalse(hexadecimal['binding_verified'])
        self.assertFalse(hexadecimal['runtime_verified'])
        self.assertEqual(len(hexadecimal['overloads']),1)
        overload=hexadecimal['overloads'][0]
        self.assertEqual([(p['name'],p['type']) for p in overload['parameters']],[('value','int')])
        self.assertEqual(overload['result'],dict(type='str',ownership='owned_snapshot',access='readonly'))
        self.assertEqual(overload['context'],'expression')
        self.assertIn('one positional signed int64; lowercase Python 0x/-0x spelling; INT64_MIN supported',overload['constraints'])

@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('gcc') or shutil.which('cc'),'installed C compiler required')
class ApiProfileNativeTests(unittest.TestCase):
    setUp=support.CObjectTests.setUp
    write=support.CObjectTests.write
    command=support.CObjectTests.command
    ail_build=support.CObjectTests.ail_build
    check_run=support.CObjectTests.check_run

    def test_map_iterations_binary_chunks_and_primitive_contexts(self):
        functions=[];calls=[];expected=[]
        values={'int':'7','float':'1.5','str':'"text"','bytes':'b"\\xff"'}
        for kind,value in values.items():
            mapping='dict[str,'+kind+']'
            variable='input_'+kind
            calls.append('let '+variable+':'+mapping+'={"a":'+value+',"k\\0😀":'+value+'};')
            for symbol in (mapping,mapping+'.items',mapping+'.keys'):
                name='iteration_'+str(len(functions));functions.append(SYNTAX_FORMS[symbol][0]['source'].replace('fn probe(','fn '+name+'('))
                calls.append('print('+name+'('+variable+'));');expected.append('4\n')
        for symbol,args,result in [('ord','"a😀",1',str(ord('😀'))),('dict','3,7','7'),('dict.get','3,7','7'),('dict.pop','3,7','7'),('set','[1,2,1]','2'),('set.add','9','1'),('set.discard','9','0'),('set.remove','9','0')]:
            name='primitive_'+str(len(functions));functions.append(SYNTAX_FORMS[symbol][0]['source'].replace('fn probe(','fn '+name+'('))
            calls.append('print('+name+'('+args+'));');expected.append(result+'\n')
        functions.append(SYNTAX_FORMS['file_chunks'][0]['source'].replace('fn probe(','fn chunk_total('))
        calls+=['print(chunk_total(sys.argv[1],1));','print(chunk_total(sys.argv[1],65537));',
                'try {chunk_total(sys.argv[1],0);}except ValueError {print("size");}']
        data=bytes(range(256))*513+b'\0\xff\x1a\r\n'
        path=self.root/'chunks.bin';path.write_bytes(data);expected += [str(len(data))+'\n',str(len(data))+'\n','size\n']
        binary=self.ail_build('api_profiles','\n'.join(functions)+'fn main()->int {'+''.join(calls)+'return 0;}')
        self.check_run(binary,''.join(expected),path)
        self.assertEqual(path.read_bytes(),data);moved=path.with_suffix('.moved');path.rename(moved);moved.unlink()

    @unittest.skipUnless(NODE,'Node needed as an independent JavaScript reference')
    def test_explicit_js_numeric_and_codeunit_profiles(self):
        # jsdiv/jsnegzero follow Node exactly. jscharat counts UTF-16 units like JS charAt, but a
        # str cannot hold half a surrogate pair (2026-10-11 decision): the unit that starts an
        # astral character yields the whole character, the unit that ends one raises ValueError.
        text='a😀\0Z';indices=[-1,0,1,3,4,5,9223372036854775807]
        divisions=[(0.0,0.0),(1.0,0.0),(1.0,-0.0),(0.0,-1.0),(-0.0,1.0),(5.5,2.0),(-5.5,2.0)]
        js=r'''const pairs=%s;const out=[];
for(const [a,b]of pairs){const x=a/b;const view=new DataView(new ArrayBuffer(8));view.setFloat64(0,x,true);out.push(Number.isNaN(x)?'nan':Buffer.from(view.buffer).toString('hex'));out.push(Object.is(x,-0)?'1':'0');}process.stdout.write(out.join('\n')+'\n');'''%json.dumps(divisions)
        reference=subprocess.run([NODE,'-e',js],capture_output=True,timeout=30)
        self.assertEqual((reference.returncode,reference.stderr),(0,b''))
        units=[]
        for character in text: units+=[character,None] if ord(character)>0xFFFF else [character]
        expected=''
        for i in indices:
            value=units[i] if 0<=i<len(units) else ''
            expected+='%d\n'%len(value)+('%d\n'%ord(value) if value else '')
        code='''fn show_char(text:str,index:int)->void {let value=jscharat(text,index);print(len(value));if len(value)>0 {print(ord(value[0]));}return;}
fn show_div(left:float,right:float)->void {let value=jsdiv(left,right);if value!=value {print("nan");}else {print(float64_encode([value],0).hex());}print(jsnegzero(value));return;}
fn main()->int {'''
        code+=''.join('show_char('+json.dumps(text,ensure_ascii=False)+','+str(i)+');' for i in indices)
        code+=''.join('show_div('+str(a)+','+str(b)+');' for a,b in divisions)+'return 0;}'
        self.check_run(self.ail_build('js_profiles',code),expected+reference.stdout.decode())
        half='fn main()->int {try {let value=jscharat('+json.dumps(text,ensure_ascii=False)+',2);print(len(value));} except ValueError {print("ValueError");}return 0;}'
        self.check_run(self.ail_build('js_charat_half',half),'ValueError\n')

if __name__=='__main__':unittest.main()