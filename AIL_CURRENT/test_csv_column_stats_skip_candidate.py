"""Unselected-span candidate keeps all independent byte-parser checks."""
import unittest
import test_csv_column_stats_bytes_candidate as support

class CsvStatsSkipCandidateTests(support.CsvStatsBytesCandidateTests):
    module_name='csv_column_stats_skip_candidate'
    function_name='csv_column_stats_skip_stream'
    main_name='csv_column_stats_skip_candidate_main.ail'
    def test_many_fields_and_quoted_span_boundaries(self):
        from test_csv_column_stats_cli import encoded,oracle
        source,output=self.root/'spans.csv',self.root/'spans.tsv'
        cases=[]
        for column in (0,500,1000):
            row=['x']*1001;row[column]='17';cases.append((encoded([row]),column))
        cases += [(encoded([['x'*65537,'-7','quoted,"\r\n😀'*17]]),1),
                  (encoded([['quoted,"\r\n😀'*17,'+7','x'*65537]]).rstrip(b'\r\n'),1),
                  (b'ignored,1\r\nignored,2\nignored,3\r',1)]
        for data,column in cases:
            for size in (7,8192):
                with self.subTest(fields=column,bytes=len(data),chunk=size):
                    self.chunk_size=size;source.write_bytes(data)
                    result=self.invoke(source,output,column)
                    self.assertEqual((result.returncode,result.stdout,result.stderr),(0,b'',b''))
                    self.assertEqual(output.read_bytes(),oracle(data,str(column)))
        self.chunk_size=8192

if __name__=='__main__':unittest.main()