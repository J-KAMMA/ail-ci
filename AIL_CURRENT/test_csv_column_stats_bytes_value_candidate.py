"""Independent bounds for the str API without row materialization."""
import unittest
import test_csv_column_stats_cli as support

class CsvStatsBytesValueTests(support.CsvColumnStatsCliTests):
    @classmethod
    def setUpClass(cls):
        previous=support.CANDIDATE
        support.CANDIDATE=support.EXAMPLES/'csv_column_stats_bytes_value_candidate.ail'
        try:super().setUpClass()
        finally:support.CANDIDATE=previous

    def test_many_fields_long_metadata_and_nonrepeating_integers(self):
        source,output=self.root/'input.csv',self.root/'output.tsv'
        cases=[]
        for column in (0,500,1000):
            row=['x']*1001;row[column]='9007199254740993'
            cases.append((support.encoded([row]).removesuffix(b'\r\n'),column))
        cases += [(support.encoded([['x'*65537,'-7','quoted,"\r\n😀'*17]]),1),
                  (support.encoded([['quoted,"\r\n😀'*17,'+7','x'*65537]]).removesuffix(b'\r\n'),1),
                  (support.encoded([['m',str((1 if i%2==0 else -1)*((1<<53)+i*37))] for i in range(4097)]).removesuffix(b'\r\n'),1)]
        for data,column in cases:
            with self.subTest(column=column,bytes=len(data)):
                source.write_bytes(data)
                result=self.invoke(source,output,column)
                self.assertEqual((result.returncode,result.stdout,result.stderr),(0,b'',b''))
                self.assertEqual(output.read_bytes(),support.oracle(data,str(column)))

if __name__=='__main__':unittest.main()