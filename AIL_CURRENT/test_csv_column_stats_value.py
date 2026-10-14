"""Public str API reuses the independent width/column/EOF workload."""
import unittest
import test_csv_column_stats_cli as support
import test_csv_column_stats_bytes_value_candidate as candidate

class CsvStatsValueBoundsTests(unittest.TestCase):
    setUpClass=classmethod(support.CsvColumnStatsCliTests.setUpClass.__func__)
    invoke=support.CsvColumnStatsCliTests.invoke
    test_many_fields_long_metadata_and_nonrepeating_integers=candidate.CsvStatsBytesValueTests.test_many_fields_long_metadata_and_nonrepeating_integers

if __name__=='__main__':unittest.main()