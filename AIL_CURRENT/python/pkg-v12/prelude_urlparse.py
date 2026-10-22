# prelude_urlparse.py -- `urllib.parse` as Python source (library batch 6, stdlib6.py injects it).
#
# The pure-Python pieces the corpus needs: urlsplit / urlparse / urlunsplit, parse_qs / parse_qsl,
# unquote / unquote_plus, quote / quote_plus, urlencode and urljoin. The splitter follows CPython
# 3.12's urllib/parse.py (whitespace, scheme test, '[' bracket check, userinfo and port), and the
# query parser follows parse_qsl / parse_qs including keep_blank_values and strict_parsing.


def _ail_up_hexdigit(n: int) -> str:
    return "0123456789ABCDEF"[n:n + 1]


def _ail_up_hexval(c: str) -> int:
    if c >= "0" and c <= "9":
        return ord(c) - 48
    if c >= "a" and c <= "f":
        return ord(c) - 87
    if c >= "A" and c <= "F":
        return ord(c) - 55
    return -1


def _ail_up_isscheme(c: str) -> bool:
    return ((c >= "a" and c <= "z") or (c >= "A" and c <= "Z") or (c >= "0" and c <= "9")
            or c == "+" or c == "-" or c == ".")


def _ail_up_isalpha(c: str) -> bool:
    return (c >= "a" and c <= "z") or (c >= "A" and c <= "Z")


def _ail_up_unquote(s: str, plus: bool, encoding: str | None, errors: str | None) -> str:
    if encoding is None:
        encoding = "utf-8"
    if errors is None:
        errors = "replace"
    out = ""
    buf = bytearray()
    i = 0
    while i < len(s):
        c = s[i]
        if ord(c) >= 128:
            out = out + bytes(buf).decode(encoding, errors) + c
            buf = bytearray()
            i = i + 1
        elif plus and c == "+":
            buf.append(32)
            i = i + 1
        elif c == "%" and i + 2 < len(s) and _ail_up_hexval(s[i + 1]) >= 0 and _ail_up_hexval(s[i + 2]) >= 0:
            buf.append(_ail_up_hexval(s[i + 1]) * 16 + _ail_up_hexval(s[i + 2]))
            i = i + 3
        else:
            buf.append(ord(c))
            i = i + 1
    return out + bytes(buf).decode(encoding, errors)


def _ail_up_quote(s: str, safe: str, plus: bool, encoding: str | None, errors: str | None) -> str:
    if encoding is None:
        encoding = "utf-8"
    if errors is None:
        errors = "strict"
    keep = safe
    if plus and " " in s:
        keep = safe + " "
    data = s.encode(encoding, errors)
    out = ""
    for b in data:
        c = chr(b)
        if ((b >= 48 and b <= 57) or (b >= 65 and b <= 90) or (b >= 97 and b <= 122)
                or c == "_" or c == "." or c == "-" or c == "~"):
            out = out + c
        elif b < 128 and c in keep:
            if plus and c == " ":
                out = out + "+"
            else:
                out = out + c
        else:
            out = out + "%" + _ail_up_hexdigit(b // 16) + _ail_up_hexdigit(b % 16)
    return out


class _AilUrl:
    def __init__(self, scheme: str, netloc: str, path: str, params: str, query: str, fragment: str, is_parse: bool):
        self.scheme = scheme
        self.netloc = netloc
        self.path = path
        self.params = params
        self.query = query
        self.fragment = fragment
        self._is_parse = is_parse
        self.username: str | None = None
        self.password: str | None = None
        self.hostname: str | None = None
        self._port = ""
        if netloc == "":
            return
        userinfo, have_info, hostinfo = netloc.rpartition("@")
        if have_info:
            name, have_password, secret = userinfo.partition(":")
            self.username = name
            if have_password:
                self.password = secret
        host = hostinfo
        port = ""
        if hostinfo.startswith("["):
            close = hostinfo.find("]")
            if close < 0:
                raise ValueError("Invalid IPv6 URL")
            host = hostinfo[1:close]
            rest = hostinfo[close + 1:]
            if rest.startswith(":"):
                port = rest[1:]
            elif rest != "":
                raise ValueError("Invalid IPv6 URL")
        else:
            host, have_colon, port = hostinfo.partition(":")
            if not have_colon:
                port = ""
        if host != "":
            label, percent, zone = host.partition("%")
            self.hostname = label.lower() + percent + zone
        else:
            self.hostname = None
        self._port = port

    @property
    def port(self) -> int | None:
        if self._port == "":
            return None
        i = 0
        while i < len(self._port):
            if self._port[i] < "0" or self._port[i] > "9":
                raise ValueError("Port could not be cast to integer value as " + repr(self._port))
            i = i + 1
        value = int(self._port)
        if value < 0 or value > 65535:
            raise ValueError("Port out of range 0-65535")
        return value

    def _values(self) -> list:
        if self._is_parse:
            return [self.scheme, self.netloc, self.path, self.params, self.query, self.fragment]
        return [self.scheme, self.netloc, self.path, self.query, self.fragment]

    def __len__(self) -> int:
        return len(self._values())

    def __getitem__(self, i):
        return self._values()[i]

    def __iter__(self):
        return iter(self._values())

    def geturl(self) -> str:
        if self._is_parse:
            path = self.path
            if self.params != "":
                path = path + ";" + self.params
            return _ail_up_unsplit(self.scheme, self.netloc, path, self.query, self.fragment)
        return _ail_up_unsplit(self.scheme, self.netloc, self.path, self.query, self.fragment)

    def __repr__(self) -> str:
        name = "ParseResult" if self._is_parse else "SplitResult"
        if self._is_parse:
            return (name + "(scheme=" + repr(self.scheme) + ", netloc=" + repr(self.netloc) + ", path="
                    + repr(self.path) + ", params=" + repr(self.params) + ", query=" + repr(self.query)
                    + ", fragment=" + repr(self.fragment) + ")")
        return (name + "(scheme=" + repr(self.scheme) + ", netloc=" + repr(self.netloc) + ", path="
                + repr(self.path) + ", query=" + repr(self.query) + ", fragment=" + repr(self.fragment) + ")")

    def __str__(self) -> str:
        return self.__repr__()


def _ail_up_split(url0: str, scheme_hint: str, allow_fragments: bool, is_parse: bool) -> _AilUrl:
    start = 0
    while start < len(url0) and ord(url0[start]) <= 32:
        start = start + 1
    url = url0[start:]
    url = url.replace("\t", "").replace("\r", "").replace("\n", "")
    scheme = ""
    i = url.find(":")
    if i > 0 and _ail_up_isalpha(url[0:1]):
        ok = True
        for c in url[0:i]:
            if not _ail_up_isscheme(c):
                ok = False
        if ok:
            scheme = url[0:i].lower()
            url = url[i + 1:]
    if scheme == "" and scheme_hint != "":
        scheme = scheme_hint
    netloc = ""
    if url.startswith("//"):
        delim = len(url)
        for c in "/?#":
            w = url.find(c, 2)
            if w >= 0 and w < delim:
                delim = w
        netloc = url[2:delim]
        url = url[delim:]
        if ("[" in netloc and "]" not in netloc) or ("]" in netloc and "[" not in netloc):
            raise ValueError("Invalid IPv6 URL")
    fragment = ""
    if allow_fragments:
        h = url.find("#")
        if h >= 0:
            fragment = url[h + 1:]
            url = url[0:h]
    query = ""
    q = url.find("?")
    if q >= 0:
        query = url[q + 1:]
        url = url[0:q]
    params = ""
    if is_parse and _ail_up_usesparams(scheme) and ";" in url:
        url, params = _ail_up_splitparams(url)
    return _AilUrl(scheme, netloc, url, params, query, fragment, is_parse)


def _ail_up_splitparams(url: str):
    if "/" in url:
        i = url.find(";", url.rfind("/"))
        if i < 0:
            return url, ""
    else:
        i = url.find(";")
    return url[0:i], url[i + 1:]


def _ail_up_usesparams(scheme: str) -> bool:
    names = ["", "ftp", "hdl", "prospero", "http", "imap", "https", "shttp", "rtsp", "rtsps", "rtspu", "sip",
             "sips", "mms", "sftp", "tel"]
    return scheme in names


def _ail_up_usesnetloc(scheme: str) -> bool:
    names = ["", "ftp", "http", "gopher", "nntp", "telnet", "imap", "wais", "file", "mms", "https", "shttp",
             "snews", "prospero", "rtsp", "rtsps", "rtspu", "rsync", "svn", "svn+ssh", "sftp", "nfs", "git",
             "git+ssh", "ws", "wss", "itms-services"]
    return scheme in names


def _ail_up_usesrelative(scheme: str) -> bool:
    names = ["", "ftp", "http", "gopher", "nntp", "imap", "wais", "file", "https", "shttp", "mms", "prospero",
             "rtsp", "rtsps", "rtspu", "sftp", "svn", "svn+ssh", "ws", "wss"]
    return scheme in names


def _ail_up_unsplit(scheme: str, netloc: str, path0: str, query: str, fragment: str) -> str:
    url = path0
    if netloc != "" or (scheme != "" and _ail_up_usesnetloc(scheme) and url[0:2] != "//"):
        if url != "" and url[0:1] != "/":
            url = "/" + url
        url = "//" + netloc + url
    if scheme != "":
        url = scheme + ":" + url
    if query != "":
        url = url + "?" + query
    if fragment != "":
        url = url + "#" + fragment
    return url


def _ail_up_urlunparse(scheme: str, netloc: str, path0: str, params: str, query: str, fragment: str) -> str:
    path = path0
    if params != "":
        path = path + ";" + params
    return _ail_up_unsplit(scheme, netloc, path, query, fragment)


def _ail_up_urljoin(base: str, url: str, allow_fragments: bool) -> str:
    if base == "":
        return url
    if url == "":
        return base
    b = _ail_up_split(base, "", allow_fragments, True)
    u = _ail_up_split(url, b.scheme, allow_fragments, True)
    scheme = u.scheme
    if scheme != b.scheme or not _ail_up_usesrelative(scheme):
        return url
    netloc = u.netloc
    if _ail_up_usesnetloc(scheme):
        if netloc != "":
            return _ail_up_urlunparse(scheme, netloc, u.path, u.params, u.query, u.fragment)
        netloc = b.netloc
    if u.path == "" and u.params == "":
        path = b.path
        params = b.params
        query = u.query
        if query == "":
            query = b.query
        return _ail_up_urlunparse(scheme, netloc, path, params, query, u.fragment)
    base_parts = b.path.split("/")
    if base_parts[len(base_parts) - 1] != "":
        base_parts.pop()
    segments: list[str] = []
    if u.path[0:1] == "/":
        for seg in u.path.split("/"):
            segments.append(seg)
    else:
        for seg in base_parts:
            segments.append(seg)
        for seg in u.path.split("/"):
            segments.append(seg)
        kept: list[str] = []
        for k in range(len(segments)):
            if k == 0 or k == len(segments) - 1 or segments[k] != "":
                kept.append(segments[k])
        segments = kept
    resolved: list[str] = []
    for seg in segments:
        if seg == "..":
            if len(resolved) > 0:
                resolved.pop()
        elif seg != ".":
            resolved.append(seg)
    last = segments[len(segments) - 1]
    if last == "." or last == "..":
        resolved.append("")
    joined = "/".join(resolved)
    if joined == "":
        joined = "/"
    return _ail_up_urlunparse(scheme, netloc, joined, u.params, u.query, u.fragment)


def _AilUrlSplit(url: str, scheme: str = "", allow_fragments: bool = True):
    return _ail_up_split(url, scheme, allow_fragments, False)


def _AilUrlParse(url: str, scheme: str = "", allow_fragments: bool = True):
    return _ail_up_split(url, scheme, allow_fragments, True)


def _AilUrlUnsplit(parts):
    return _ail_up_unsplit(parts[0], parts[1], parts[2], parts[3], parts[4])


def _AilUnquote(s: str, encoding: str = "utf-8", errors: str = "replace") -> str:
    return _ail_up_unquote(s, False, encoding, errors)


def _AilUnquotePlus(s: str, encoding: str = "utf-8", errors: str = "replace") -> str:
    return _ail_up_unquote(s, True, encoding, errors)


def _AilQuote(s: str, safe: str = "/", encoding=None, errors=None) -> str:
    return _ail_up_quote(s, safe, False, encoding, errors)


def _AilQuotePlus(s: str, safe: str = "", encoding=None, errors=None) -> str:
    return _ail_up_quote(s, safe, True, encoding, errors)


def _AilUrlJoin(base: str, url: str, allow_fragments: bool = True) -> str:
    return _ail_up_urljoin(base, url, allow_fragments)


def _ail_up_append(out: str, key, val, safe: str, encoding, errors) -> str:
    if out != "":
        out = out + "&"
    return (out + _ail_up_quote(str(key), safe, True, encoding, errors) + "="
            + _ail_up_quote(str(val), safe, True, encoding, errors))


def _AilUrlEncode(query, doseq: bool = False, safe: str = "", encoding=None, errors=None, quote_via=None) -> str:
    out = ""
    if isinstance(query, dict):
        for key in query:
            val = query[key]
            if doseq and (isinstance(val, list) or isinstance(val, tuple)):
                item = 0
                while item < len(val):
                    out = _ail_up_append(out, key, val[item], safe, encoding, errors)
                    item = item + 1
            else:
                out = _ail_up_append(out, key, val, safe, encoding, errors)
    else:
        for pair in query:
            out = _ail_up_append(out, pair[0], pair[1], safe, encoding, errors)
    return out


def _AilParseQsl(qs: str, keep_blank_values: bool = False, strict_parsing: bool = False,
                 encoding: str = "utf-8", errors: str = "replace", max_num_fields=None,
                 separator: str = "&") -> list:
    if separator == "":
        raise ValueError("Separator must be of type string or bytes.")
    if qs == "":
        return []
    if max_num_fields is not None and max_num_fields < len(qs.split(separator)):
        raise ValueError("Max number of fields exceeded")
    pairs = []
    for field in qs.split(separator):
        if field == "" and not strict_parsing:
            continue
        eq = field.find("=")
        if eq >= 0:
            name = field[0:eq]
            value = field[eq + 1:]
        else:
            if strict_parsing:
                raise ValueError("bad query field: " + repr(field))
            name = field
            value = ""
        if value != "" or keep_blank_values:
            pairs.append((_ail_up_unquote(name, True, encoding, errors),
                          _ail_up_unquote(value, True, encoding, errors)))
    return pairs


def _AilParseQs(qs: str, keep_blank_values: bool = False, strict_parsing: bool = False,
                encoding: str = "utf-8", errors: str = "replace", max_num_fields=None,
                separator: str = "&") -> dict:
    pairs = _AilParseQsl(qs, keep_blank_values, strict_parsing, encoding, errors, max_num_fields, separator)
    out = {}
    for name, value in pairs:
        if name in out:
            out[name].append(value)
        else:
            out[name] = [value]
    return out
