"""Source-free JSON document functions require no accidental sibling import."""
import json
import re
import subprocess
import unittest
import test_ail_c_objects as support

class JsonDocumentLibraryTests(unittest.TestCase):
    setUp=support.CObjectTests.setUp
    command=support.CObjectTests.command
    write=support.CObjectTests.write
    def test_standalone_object_preserves_unicode_numbers_and_errors(self):
        obj=self.root/'document.o'
        result=self.command('compile-module',support.ROOT/'language_examples/json_document.ail','-o',obj)
        self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
        source=self.write('caller.ail','''fn main()->int {
 try {let data=read_bytes(sys.argv[1]).decode();let nodes:list[JsonValue]=json_parse_document(data);write_stdout_bytes((json_compact(data)+"\\n").encode());return 0;}
 except ValueError {return 2;}
}''')
        exe=self.root/'json-caller';result=self.command('compile',source,'--object',obj,'-o',exe)
        self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
        if not exe.exists():exe=exe.with_suffix('.exe')
        source.unlink()
        cases=[' null ',' {"text":"日本😀\\n\\u0000","values":[-0.00e+02,1e+03,9007199254740993]} ', '[true,false,null,{},[]]', '['+','.join(str((1<<53)+i*37) for i in range(4097))+']']
        for text in cases:
            json.loads(text)
            expected=(''.join(re.findall(r'"(?:\\.|[^"\\])*"|[^\s"]+',text))+'\n').encode()
            path=self.root/'input.json';path.write_bytes(text.encode())
            result=subprocess.run([exe,path],capture_output=True,timeout=60)
            self.assertEqual((result.returncode,result.stdout,result.stderr),(0,expected,b''))
        for data in (b'{',b'[1,]',b'01',b'"\\ud800"',b'\xff'):
            path.write_bytes(data);result=subprocess.run([exe,path],capture_output=True,timeout=30)
            self.assertEqual((result.returncode,result.stdout),(2,b''));self.assertEqual(path.read_bytes(),data)

if __name__=='__main__':unittest.main()