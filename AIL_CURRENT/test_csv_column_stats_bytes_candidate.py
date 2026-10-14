"""Byte-state CSV candidate retains the full independent native oracle contract."""
import unittest
import test_csv_column_stats_stream_candidate as support

class CsvStatsBytesCandidateTests(support.CsvStatsStreamCandidateTests):
    module_name='csv_column_stats_bytes_candidate'
    function_name='csv_column_stats_bytes_stream'
    main_name='csv_column_stats_bytes_candidate_main.ail'
    def test_each_column_and_late_utf8_quote_errors(self):
        from test_csv_column_stats_cli import encoded,oracle
        source,output=self.root/'positions.csv',self.root/'positions.tsv'
        for column in (0,1,2):
            rows=[['quoted,"\r\n😀','middle\0','tail'] for _ in range(3)]
            for index,row in enumerate(rows):row[column]=('+' if index!=1 else '-')+str(index+1)
            data=encoded(rows).rstrip(b'\r\n');source.write_bytes(data)
            for size in (1,2,7,8192):
                self.chunk_size=size
                result=self.invoke(source,output,column)
                self.assertEqual((result.returncode,result.stdout,result.stderr),(0,b'',b''))
                self.assertEqual(output.read_bytes(),oracle(data,str(column)))
        for data in (b'good,1\n"unfinished,2',b'good,1\nbad"metadata,2',
                     b'good,1\n\xc0\x80,2',b'good,1\n\xed\xa0\x80,2',
                     b'good,1\n\xf4\x90\x80\x80,2',b'good,1\n\xe2\x82'):
            for size in (1,3,8192):
                self.chunk_size=size;source.write_bytes(data);output.write_bytes(b'old')
                result=self.invoke(source,output,1)
                self.assertEqual((result.returncode,result.stdout),(2,b''))
                self.assertTrue(result.stderr);self.assertEqual(output.read_bytes(),b'old')
        self.chunk_size=8192

if __name__=='__main__':unittest.main()