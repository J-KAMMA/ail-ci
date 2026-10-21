# prelude_csv.py -- `csv` as Python source for the general path (csvgen.py adds the parts a program uses, after csvlib's own
# lowering to lists of lines refused it). A port of CPython 3.12's _csv.c: the same parser states (`parse_process_char`),
# the same writer rules (`join_append_data`), and csv.py's DictReader / DictWriter. The source of a reader is read whole
# (`list(src)`: a list of lines, an io.StringIO, ...); a writer calls `f.write(line)`. Plain Python: it also runs under
# CPython, which is how the tests compare it with the real module.

_AIL_CSV_UNSET = "\x01unset\x02"


class _AilCsvError(Exception):
    pass


class _AilCsvStdout:
    def write(self, s):
        print(s, end="")
        return len(s)


class _AilCsvDialect:
    def __init__(self, delimiter, quotechar, escapechar, doublequote, skipinitialspace, lineterminator, quoting, strict):
        self.delimiter = delimiter
        self.quotechar = quotechar
        self.escapechar = escapechar
        self.doublequote = doublequote
        self.skipinitialspace = skipinitialspace
        self.lineterminator = lineterminator
        self.quoting = quoting
        self.strict = strict


def _ail_csv_dialect(dialect, delimiter, quotechar, escapechar, doublequote, skipinitialspace, lineterminator,
                     quoting, strict):
    if isinstance(dialect, _AilCsvDialect):
        base = dialect
    elif dialect is None or dialect == "excel":
        base = _AilCsvDialect(",", '"', None, True, False, "\r\n", 0, False)
    elif dialect == "excel-tab":
        base = _AilCsvDialect("\t", '"', None, True, False, "\r\n", 0, False)
    elif dialect == "unix":
        base = _AilCsvDialect(",", '"', None, True, False, "\n", 1, False)
    else:
        raise _AilCsvError("unknown dialect")
    if delimiter == _AIL_CSV_UNSET:
        delimiter = base.delimiter
    if quotechar == _AIL_CSV_UNSET:
        quotechar = base.quotechar
    if escapechar == _AIL_CSV_UNSET:
        escapechar = base.escapechar
    if doublequote is None:
        doublequote = base.doublequote
    if skipinitialspace is None:
        skipinitialspace = base.skipinitialspace
    if lineterminator is None:
        lineterminator = base.lineterminator
    if quoting is None:
        quoting = base.quoting
        if quotechar is None and dialect is None:
            quoting = 3
    if strict is None:
        strict = base.strict
    if not isinstance(delimiter, str):
        raise TypeError('"delimiter" must be string, not ' + _ail_csv_tname(delimiter))
    if len(delimiter) != 1:
        raise TypeError('"delimiter" must be a 1-character string')
    if escapechar is not None:
        if not isinstance(escapechar, str):
            raise TypeError('"escapechar" must be string or None, not ' + _ail_csv_tname(escapechar))
        if len(escapechar) != 1:
            raise TypeError('"escapechar" must be a 1-character string')
    if quotechar is not None:
        if not isinstance(quotechar, str):
            raise TypeError('"quotechar" must be string or None, not ' + _ail_csv_tname(quotechar))
        if len(quotechar) != 1:
            raise TypeError('"quotechar" must be a 1-character string')
    if not isinstance(quoting, int):
        raise TypeError('"quoting" must be an integer')
    if quoting < 0 or quoting > 3:
        raise TypeError('bad "quoting" value')
    if quotechar is None and quoting != 3:
        raise TypeError("quotechar must be set if quoting enabled")
    if not isinstance(lineterminator, str):
        raise TypeError('"lineterminator" must be a string')
    return _AilCsvDialect(delimiter, quotechar, escapechar, bool(doublequote), bool(skipinitialspace), lineterminator,
                          quoting, bool(strict))


def _ail_csv_tname(x):
    if x is None:
        return "NoneType"
    if isinstance(x, bool):
        return "bool"
    if isinstance(x, int):
        return "int"
    if isinstance(x, float):
        return "float"
    if isinstance(x, list):
        return "list"
    if isinstance(x, tuple):
        return "tuple"
    if isinstance(x, dict):
        return "dict"
    return "object"


class _AilCsvReader:
    def __init__(self, src, d):
        self.dialect = d
        self.lines = list(src)
        self.pos = 0
        self.line_num = 0
        self.state = 0
        self.fields = []
        self.field = []
        self.numeric = False

    def __iter__(self):
        return self

    def _save(self):
        s = "".join(self.field)
        self.field = []
        if self.numeric:
            self.numeric = False
            self.fields.append(float(s))
        else:
            self.fields.append(s)

    def _add(self, c):
        if len(self.field) >= 131072:
            raise _AilCsvError("field larger than field limit (131072)")
        self.field.append(c)

    # states: 0 START_RECORD 1 START_FIELD 2 ESCAPED_CHAR 3 IN_FIELD 4 IN_QUOTED_FIELD 5 ESCAPE_IN_QUOTED_FIELD
    #         6 QUOTE_IN_QUOTED_FIELD 7 EAT_CRNL 8 AFTER_ESCAPED_CRNL      (c == "" is the end of the line)
    def _process(self, c):
        d = self.dialect
        st = self.state
        if st == 0:
            if c == "":
                return
            if c == "\n" or c == "\r":
                self.state = 7
                return
            st = 1
            self.state = 1
        if st == 1:
            if c == "\n" or c == "\r" or c == "":
                self._save()
                self.state = 0 if c == "" else 7
            elif c == d.quotechar and d.quoting != 3:
                self.state = 4
            elif c == d.escapechar:
                self.state = 2
            elif c == " " and d.skipinitialspace:
                pass
            elif c == d.delimiter:
                self._save()
            else:
                if d.quoting == 2:
                    self.numeric = True
                self._add(c)
                self.state = 3
            return
        if st == 2:
            if c == "\n" or c == "\r":
                self._add(c)
                self.state = 8
                return
            if c == "":
                c = "\n"
            self._add(c)
            self.state = 3
            return
        if st == 8:
            if c == "":
                return
            st = 3
        if st == 3:
            if c == "\n" or c == "\r" or c == "":
                self._save()
                self.state = 0 if c == "" else 7
            elif c == d.escapechar:
                self.state = 2
            elif c == d.delimiter:
                self._save()
                self.state = 1
            else:
                self._add(c)
            return
        if st == 4:
            if c == "":
                pass
            elif c == d.escapechar:
                self.state = 5
            elif c == d.quotechar and d.quoting != 3:
                if d.doublequote:
                    self.state = 6
                else:
                    self.state = 3
            else:
                self._add(c)
            return
        if st == 5:
            if c == "":
                c = "\n"
            self._add(c)
            self.state = 4
            return
        if st == 6:
            if d.quoting != 3 and c == d.quotechar:
                self._add(c)
                self.state = 4
            elif c == d.delimiter:
                self._save()
                self.state = 1
            elif c == "\n" or c == "\r" or c == "":
                self._save()
                self.state = 0 if c == "" else 7
            elif not d.strict:
                self._add(c)
                self.state = 3
            else:
                raise _AilCsvError("'" + d.delimiter + "' expected after '" + d.quotechar + "'")
            return
        if c == "\n" or c == "\r":
            return
        if c == "":
            self.state = 0
            return
        raise _AilCsvError("new-line character seen in unquoted field - do you need to open the file with newline=''?")

    def __next__(self):
        self.state = 0
        self.fields = []
        self.field = []
        self.numeric = False
        while True:
            if self.pos >= len(self.lines):
                if len(self.field) != 0 or self.state == 4:
                    if self.dialect.strict:
                        raise _AilCsvError("unexpected end of data")
                    self._save()
                    break
                raise StopIteration
            line = self.lines[self.pos]
            self.pos += 1
            if not isinstance(line, str):
                raise _AilCsvError("iterator should return strings, not " + _ail_csv_tname(line)
                                   + " (the file should be opened in text mode)")
            self.line_num += 1
            for c in line:
                self._process(c)
            self._process("")
            if self.state == 0:
                break
        out = self.fields
        self.fields = []
        return out


def _ail_csv_reader(csvfile, dialect=None, delimiter=_AIL_CSV_UNSET, quotechar=_AIL_CSV_UNSET,
                    escapechar=_AIL_CSV_UNSET, doublequote=None, skipinitialspace=None, lineterminator=None,
                    quoting=None, strict=None):
    d = _ail_csv_dialect(dialect, delimiter, quotechar, escapechar, doublequote, skipinitialspace, lineterminator,
                         quoting, strict)
    return _AilCsvReader(csvfile, d)


class _AilCsvWriter:
    def __init__(self, f, d):
        self.f = f
        self.dialect = d

    def _join(self, s, quoted):
        d = self.dialect
        out = []
        for c in s:
            want_escape = False
            if c == d.delimiter or c == d.escapechar or c == d.quotechar or c in d.lineterminator \
                    or c == "\n" or c == "\r":
                if d.quoting == 3:
                    want_escape = True
                else:
                    if c == d.quotechar:
                        if d.doublequote:
                            out.append(d.quotechar)
                        else:
                            want_escape = True
                    elif c == d.escapechar:
                        want_escape = True
                    if not want_escape:
                        quoted = True
                if want_escape:
                    if d.escapechar is None:
                        raise _AilCsvError("need to escape, but no escapechar set")
                    out.append(d.escapechar)
            out.append(c)
        body = "".join(out)
        if quoted:
            return d.quotechar + body + d.quotechar
        return body

    def writerow(self, row):
        d = self.dialect
        parts = []
        try:
            it = iter(row)
        except TypeError:
            raise _AilCsvError("iterable expected, not " + type(row).__name__)
        for field in it:
            if d.quoting == 2:
                quoted = not (isinstance(field, int) or isinstance(field, float))
            elif d.quoting == 1:
                quoted = True
            else:
                quoted = False
            if field is None:
                text = ""
            elif isinstance(field, str):
                text = field
            else:
                text = str(field)
            parts.append(self._join(text, quoted))
        line = d.delimiter.join(parts)
        if len(parts) == 1 and len(line) == 0:
            if d.quoting == 3:
                raise _AilCsvError("single empty field record must be quoted")
            line = d.quotechar + d.quotechar
        return self.f.write(line + d.lineterminator)

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)


def _ail_csv_writer(csvfile, dialect=None, delimiter=_AIL_CSV_UNSET, quotechar=_AIL_CSV_UNSET,
                    escapechar=_AIL_CSV_UNSET, doublequote=None, skipinitialspace=None, lineterminator=None,
                    quoting=None, strict=None):
    d = _ail_csv_dialect(dialect, delimiter, quotechar, escapechar, doublequote, skipinitialspace, lineterminator,
                         quoting, strict)
    return _AilCsvWriter(csvfile, d)


class _AilCsvDictReader:
    def __init__(self, f, fieldnames=None, restkey=None, restval=None, dialect="excel", delimiter=_AIL_CSV_UNSET,
                 quotechar=_AIL_CSV_UNSET, escapechar=_AIL_CSV_UNSET, doublequote=None, skipinitialspace=None,
                 lineterminator=None, quoting=None, strict=None):
        self._fieldnames = fieldnames
        self.restkey = restkey
        self.restval = restval
        self.reader = _ail_csv_reader(f, dialect, delimiter, quotechar, escapechar, doublequote, skipinitialspace,
                                      lineterminator, quoting, strict)
        self.dialect = dialect
        self.line_num = 0

    def __iter__(self):
        return self

    @property
    def fieldnames(self):
        if self._fieldnames is None:
            try:
                self._fieldnames = next(self.reader)
            except StopIteration:
                pass
        self.line_num = self.reader.line_num
        return self._fieldnames

    def __next__(self):
        if self.line_num == 0:
            self.fieldnames
        row = next(self.reader)
        self.line_num = self.reader.line_num
        while row == []:
            row = next(self.reader)
        names = self.fieldnames
        d = {}
        for i in range(min(len(names), len(row))):
            d[names[i]] = row[i]
        lf = len(names)
        lr = len(row)
        if lf < lr:
            d[self.restkey] = row[lf:]
        elif lf > lr:
            for key in names[lr:]:
                d[key] = self.restval
        return d


def _ail_csv_DictReader(f, fieldnames=None, restkey=None, restval=None, dialect="excel", delimiter=_AIL_CSV_UNSET,
                        quotechar=_AIL_CSV_UNSET, escapechar=_AIL_CSV_UNSET, doublequote=None, skipinitialspace=None,
                        lineterminator=None, quoting=None, strict=None):
    return _AilCsvDictReader(f, fieldnames, restkey, restval, dialect, delimiter, quotechar, escapechar, doublequote,
                             skipinitialspace, lineterminator, quoting, strict)


class _AilCsvDictWriter:
    def __init__(self, f, fieldnames, restval="", extrasaction="raise", dialect="excel", delimiter=_AIL_CSV_UNSET,
                 quotechar=_AIL_CSV_UNSET, escapechar=_AIL_CSV_UNSET, doublequote=None, skipinitialspace=None,
                 lineterminator=None, quoting=None, strict=None):
        self.fieldnames = fieldnames
        self.restval = restval
        if extrasaction.lower() != "raise" and extrasaction.lower() != "ignore":
            raise ValueError("extrasaction (" + extrasaction + ") must be 'raise' or 'ignore'")
        self.extrasaction = extrasaction
        self.writer = _ail_csv_writer(f, dialect, delimiter, quotechar, escapechar, doublequote, skipinitialspace,
                                      lineterminator, quoting, strict)

    def writeheader(self):
        header = {}
        for name in self.fieldnames:
            header[name] = name
        return self.writerow(header)

    def _dict_to_list(self, rowdict):
        if self.extrasaction == "raise":
            wrong = []
            for key in rowdict:
                if key not in self.fieldnames:
                    wrong.append(repr(key))
            if wrong:
                raise ValueError("dict contains fields not in fieldnames: " + ", ".join(wrong))
        out = []
        for key in self.fieldnames:
            if key in rowdict:
                out.append(rowdict[key])
            else:
                out.append(self.restval)
        return out

    def writerow(self, rowdict):
        return self.writer.writerow(self._dict_to_list(rowdict))

    def writerows(self, rowdicts):
        for rowdict in rowdicts:
            self.writer.writerow(self._dict_to_list(rowdict))


def _ail_csv_DictWriter(f, fieldnames, restval="", extrasaction="raise", dialect="excel", delimiter=_AIL_CSV_UNSET,
                        quotechar=_AIL_CSV_UNSET, escapechar=_AIL_CSV_UNSET, doublequote=None, skipinitialspace=None,
                        lineterminator=None, quoting=None, strict=None):
    return _AilCsvDictWriter(f, fieldnames, restval, extrasaction, dialect, delimiter, quotechar, escapechar,
                             doublequote, skipinitialspace, lineterminator, quoting, strict)
