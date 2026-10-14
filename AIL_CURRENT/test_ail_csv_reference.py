"""CSV oracle with NUL support across CPython versions; independent of AIL."""
import csv
import io
import unittest


def unused_character(texts):
    used=set(',"\r\n\0')
    for text in texts:
        used.update(text)
    return next(chr(code) for code in range(1,0x110000)
                if not 0xD800<=code<=0xDFFF and chr(code) not in used)


def write_rows(rows, ending='\r\n'):
    rows=[tuple(row) for row in rows]
    # An unused escape character avoids CPython 3.10's unset/NUL sentinel bug.
    escape=unused_character([ending,*(str(value) for row in rows for value in row)])
    output=io.StringIO(newline='')
    csv.writer(output,lineterminator=ending,escapechar=escape).writerows(rows)
    return output.getvalue()


def read_rows(text, *, strict=True):
    marker=unused_character([text]) if '\0' in text else None
    source=text.replace('\0',marker) if marker else text
    rows=csv.reader(io.StringIO(source,newline=''),strict=strict)
    return [[value.replace(marker,'\0') for value in row] if marker else row for row in rows]


class CsvReferenceTests(unittest.TestCase):
    def test_nul_unicode_quotes_newlines_and_unused_marker_collisions(self):
        rows=[[''],['a\0b','é😀','a,b','a"b','\r\n','\x01\x02']]
        expected='""\r\na\0b,é😀,"a,b","a""b","\r\n",\x01\x02\r\n'
        self.assertEqual(write_rows(rows),expected)
        self.assertEqual(read_rows(expected),rows)

    def test_csv_reader_strict_errors_are_retained(self):
        with self.assertRaises(csv.Error):read_rows('"unterminated\0')
        self.assertEqual(read_rows('\n\r\na,b\n'),[[],[],['a','b']])

    def test_ordinary_writer_matches_unmodified_stdlib(self):
        rows=[[''],[],['a,b','x"y','',None,17],['\n','\r','é😀']]
        for ending in ('\n','\r\n'):
            output=io.StringIO(newline='');csv.writer(output,lineterminator=ending).writerows(rows)
            self.assertEqual(write_rows(rows,ending),output.getvalue())


if __name__=='__main__':unittest.main()