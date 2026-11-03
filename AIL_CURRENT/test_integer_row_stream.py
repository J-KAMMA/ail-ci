"""Independent integer stream outputs, chunk boundaries and source-free reader/result ownership."""
from pathlib import Path
import struct
import subprocess
import unittest

import test_ail_c_objects as support
def oracle(values,cols,repeat=1):
    return b''.join(f'{sum(values[i:i+cols])}\n'.encode('ascii')
                    for i in range(0,len(values),cols))*repeat

ROOT = Path(__file__).resolve().parent
ENTRY = '''fn main()->int {
 let reader:binaryfile=open_binary(sys.argv[1],"rb");
 try {
  if int(sys.argv[4])!=0 {reader.close();}
  let result:bytes=integer_row_report_stream(reader,int(sys.argv[2]),int(sys.argv[3]));
  if reader.closed or len(reader.read(1))!=0 {return 3;}
  reader.close();
  let scratch=bytearray(b"x"*65537);
  scratch.extend(b"y"*65537);
  write_stdout_bytes(result);
  return 0;
 } except ValueError {return 2;}
   except OSError {return 2;}
 finally {reader.close();}
}'''


class IntegerRowStreamTests(unittest.TestCase):
    def setUp(self):
        support.CObjectTests.setUp(self)
        self.addTypeEqualityFunc(bytes, lambda a,b,msg=None: self.assertTrue(
            a==b, msg or f'complete output differs: {len(a)} vs {len(b)} bytes'))
    command = support.CObjectTests.command
    def write(self,name,text):
        path=self.root/name
        path.write_bytes(text if isinstance(text,bytes) else text.encode('utf8'))
        return path

    @staticmethod
    def execute(binary,*args):
        return subprocess.run([str(binary),*map(str,args)],capture_output=True,timeout=60)

    def build(self, source, name='app', *extra):
        entry = self.write(name+'.ail', source)
        binary = self.root / (name + '.exe')
        result = self.command('compile',entry,*extra,'-o',binary)
        self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace')[:2500])
        return binary

    def invoke(self,binary,data,cols=3,size=7,closed=0):
        path = self.write('input.bin',data)
        result = self.execute(binary,path,str(cols),str(size),str(closed))
        self.assertEqual(path.read_bytes(),data)
        return result

    def test_public_cli_profile_and_late_error_has_no_partial_stdout(self):
        result = self.command('compile',ROOT/'language_examples/row_reduce_stream_main.ail','-o',self.root/'cli.exe')
        self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace')[:2500])
        lo,hi=-(1<<63),(1<<63)-1
        for values,cols,repeat in [([],3,2),([lo,hi,hi,-hi],2,2),
                                   ([1,-2,3,10,20,-4],3,3),([1]*8193,3,1)]:
            data=b''.join(struct.pack('<q',v) for v in values)
            path=self.write('valid.bin',data)
            result=self.execute(self.root/'cli.exe',path,cols,repeat)
            self.assertEqual((result.returncode,result.stdout,result.stderr),(0,oracle(values,cols,repeat),b''))
            self.assertEqual(path.read_bytes(),data)
        for cols,repeat in [('-1','1'),('0','1'),('1','0'),('1','-1'),('1x','1'),('18446744073709551616','1')]:
            result=self.execute(self.root/'cli.exe',self.write('invalid.bin',struct.pack('<q',1)),cols,repeat)
            self.assertEqual((result.returncode,result.stdout),(2,b''))
        values=[1,-1,0]*8193+[(1<<63)-1,1,-1]
        data=b''.join(struct.pack('<q',v) for v in values)
        path=self.write('late.bin',data)
        result=self.execute(self.root/'cli.exe',path,'3','1')
        self.assertEqual((result.returncode,result.stdout),(2,b''))
        self.assertEqual(path.read_bytes(),data)
        for tail in (b'x',b'1234567'):
            result=self.execute(self.root/'cli.exe',self.write('tail.bin',data[:-24]+tail),'3','1')
            self.assertEqual((result.returncode,result.stdout),(2,b''))

    def test_partial_reads_empty_input_widths_bounds_and_retained_reader(self):
        binary=self.build('use integer_row_stream;\n'+ENTRY)
        lo,hi=-(1<<63),(1<<63)-1
        values=[lo,hi,7,-7,(1<<53)+1,-((1<<53)+1),hi,-hi,42]
        data=b''.join(struct.pack('<q',v) for v in values)
        expected=oracle(values,3,1)
        for size in (1,2,3,7,8,9,15,16,17,65535,65536,65537,1048576):
            with self.subTest(size=size):
                result=self.invoke(binary,data,size=size)
                self.assertEqual((result.returncode,result.stdout,result.stderr),(0,expected,b''))
        result=self.invoke(binary,b'')
        self.assertEqual((result.returncode,result.stdout,result.stderr),(0,b'',b''))
        for args in ((0,7,0),(-1,7,0),(3,0,0),(3,-1,0),(3,1048577,0),(3,7,1)):
            with self.subTest(args=args):
                result=self.invoke(binary,data,*args)
                self.assertEqual((result.returncode,result.stdout),(2,b''))
        for malformed in (data+b'x',data[:8],struct.pack('<qqq',hi,1,-1),struct.pack('<qqq',lo,-1,1)):
            result=self.invoke(binary,malformed)
            self.assertEqual((result.returncode,result.stdout),(2,b''))

    def test_source_free_module_preserves_owned_bytes_after_reader_close(self):
        library=self.write('integer_row_stream.ail',(ROOT/'language_examples/integer_row_stream.ail').read_bytes())
        obj=self.root/'stream.o'
        result=self.command('compile-module',library,'-o',obj)
        self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace')[:2500])
        library.unlink()
        binary=self.build(ENTRY,'linked','--object',obj)
        values=[(-1 if i%2 else 1)*((1<<53)+i*37) for i in range(8193*3)]
        data=b''.join(struct.pack('<q',v) for v in values)
        result=self.invoke(binary,data,size=65537)
        self.assertEqual((result.returncode,result.stdout,result.stderr),(0,oracle(values,3,1),b''))

    def test_private_step_preserves_partial_state_after_caught_overflow(self):
        source=r'''use integer_row_stream;
fn main()->int {
 let reader:binaryfile=open_binary(sys.argv[1],"rb");
 let state=IntegerRowStreamState(int(sys.argv[2]),0,0,b"");
 if int(sys.argv[3])!=0 {state.carry=b"\x01";}
 let output=bytearray(b"");
 let failed:int=0;
 try {_integer_row_stream_step(reader,state,output,65536);}
 except ValueError {failed=1;}
 write_stdout_bytes((str(failed)+" "+str(state.total)+" "+str(state.column)+" "+str(len(state.carry))+" "+str(reader.tell())+"\n").encode());
 reader.close();write_stdout_bytes(bytes(output));return 0;
}'''
        binary=self.build(source,'state','-I',ROOT/'language_examples')
        hi=(1<<63)-1;lo=-(1<<63)
        cases=[([1,hi],3,1,1,b''),([hi,1],3,hi,1,b''),
               ([-1,lo],3,-1,1,b''),([lo,-1],3,lo,1,b''),
               ([7,8,1,hi],2,1,1,b'15\n'),([7,8,-1,lo],2,-1,1,b'15\n')]
        for values,cols,total,column,output in cases:
            with self.subTest(values=values,cols=cols):
                data=struct.pack('<'+'q'*len(values),*values)
                path=self.write('state.bin',data)
                result=self.execute(binary,path,cols,0)
                expected=f'1 {total} {column} 0 {len(data)}\n'.encode()+output
                self.assertEqual((result.returncode,result.stderr),(0,b''))
                self.assertEqual(result.stdout,expected)
                self.assertEqual(path.read_bytes(),data)
        path=self.write('carry.bin',b'\0'*7)
        result=self.execute(binary,path,3,1)
        self.assertEqual((result.returncode,result.stdout,result.stderr),(0,b'0 1 1 0 7\n',b''))


if __name__=='__main__':unittest.main()
