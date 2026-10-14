"""Streaming candidate against the frozen independent CSV/int oracle."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_csv_column_stats_cli import CsvColumnStatsCliTests, EXAMPLES, encoded, oracle
import test_ail_c_objects as support


class CsvStatsStreamCandidateTests(CsvColumnStatsCliTests):
    chunk_size=8192
    module_name='csv_column_stats_stream_candidate'
    function_name='csv_column_stats_stream'
    main_name='csv_column_stats_stream_candidate_main.ail'

    @classmethod
    def setUpClass(cls):
        temporary=tempfile.TemporaryDirectory(prefix='csv-stats-stream-candidate-')
        cls.addClassCleanup(temporary.cleanup);cls.root=Path(temporary.name)
        def command(*args):
            result=subprocess.run([sys.executable,'-X','utf8','-B',str(support.ROOT/'ail_chatgpt.py'),*map(str,args)],capture_output=True,timeout=180)
            if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace'))
        cls.command=staticmethod(command)
        cls.identity=cls.root/'identity.o'
        command('compile-c',EXAMPLES/'file_identity.c','--interface',EXAMPLES/'file_identity.json','-o',cls.identity)
        text=(EXAMPLES/cls.main_name).read_text(encoding='utf8')
        text=text.replace('len(sys.argv)!=4','len(sys.argv)!=5').replace(cls.function_name+'(reader,column,8192)',
            cls.function_name+'(reader,column,parse_int64_decimal(sys.argv[4]))')
        source=cls.root/'main.ail';source.write_text(text,encoding='utf8')
        output=cls.root/'candidate'
        command('compile',source,'-I',EXAMPLES,'--object',cls.identity,'-o',output)
        cls.executable=output if output.is_file() else Path(str(output)+'.exe')

    def invoke(self,*args):
        return super().invoke(*args,str(self.chunk_size))

    def test_utf8_quotes_crlf_and_eof_all_chunk_boundaries(self):
        data=encoded([['😀"quoted,\r\nmetadata','-17'],['日本語','+23'],['last','-0']]).rstrip(b'\r\n')
        source,output=self.root/'chunks.csv',self.root/'chunks.tsv';source.write_bytes(data)
        for size in (1,2,3,4,7,31,8192,1048576):
            with self.subTest(chunk=size):
                self.chunk_size=size
                result=self.invoke(source,output,1)
                self.assertEqual((result.returncode,result.stdout,result.stderr),(0,b'',b''))
                self.assertEqual(output.read_bytes(),oracle(data,'1'))
        self.chunk_size=8192
        for size in (-1,0,1048577,9223372036854775807):
            self.chunk_size=size;output.write_bytes(b'old')
            self.assertEqual(self.invoke(source,output,1).returncode,2)
            self.assertEqual(output.read_bytes(),b'old')
        self.chunk_size=8192

    def test_long_nonrepeating_int64_values_exact_full_report(self):
        rows=[[f'unique-{index:x}😀,"\r\n',str((1 if index%2==0 else -1)*((1<<53)+index*37))] for index in range(4097)]
        data=encoded(rows).rstrip(b'\r\n')
        source,output=self.root/'unique.csv',self.root/'unique.tsv';source.write_bytes(data)
        result=self.invoke(source,output,1)
        self.assertEqual((result.returncode,result.stdout,result.stderr),(0,b'',b''))
        self.assertEqual(output.read_bytes(),oracle(data,'1'))
        self.assertEqual(source.read_bytes(),data)
    def test_caller_retains_handle_and_closed_handle_is_refused(self):
        input_path=self.root/'caller.csv';input_path.write_bytes(b'1\n2')
        text='''use csv_column_stats_stream_candidate;
fn main()->int {
 let reader=open_binary(PATH,"rb");
 let stats=csv_column_stats_stream(reader,0,1);
 if reader.closed or stats.count!=2 or stats.total!=3 or reader.tell()!=3 {return 9;}
 reader.seek(2,0);stats=csv_column_stats_stream(reader,0,2);
 if stats.count!=1 or stats.total!=2 {return 8;}
 reader.close();
 try {csv_column_stats_stream(reader,0,1);return 7;} except ValueError {return 0;}
}
'''.replace('use csv_column_stats_stream_candidate;', 'use '+self.module_name+';').replace('csv_column_stats_stream(reader',self.function_name+'(reader').replace('PATH',json.dumps(str(input_path)))
        source=self.root/'api.ail';source.write_text(text,encoding='utf8');output=self.root/'api'
        self.command('compile',source,'-I',EXAMPLES,'-o',output)
        exe=output if output.is_file() else Path(str(output)+'.exe')
        result=subprocess.run([str(exe)],capture_output=True,timeout=20)
        self.assertEqual((result.returncode,result.stdout,result.stderr),(0,b'',b''))


if __name__=='__main__':
    unittest.main(defaultTest='CsvStatsStreamCandidateTests')