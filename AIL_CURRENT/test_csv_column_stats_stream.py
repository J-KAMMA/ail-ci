"""Public streaming API reuses the candidate's independent native oracle checks."""
import unittest
import test_csv_column_stats_skip_candidate as support

class CsvStatsStreamTests(support.CsvStatsSkipCandidateTests):
    module_name='csv_column_stats_stream'
    function_name='csv_column_stats_stream'
    main_name='csv_column_stats_stream_main.ail'

if __name__=='__main__':unittest.main()