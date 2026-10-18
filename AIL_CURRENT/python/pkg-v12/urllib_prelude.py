# -*- coding: utf-8 -*-
"""urllib_prelude.py -- the Python source urllower.py injects for urllib.request / urllib.parse (stage G12).

This file is ordinary Python in the subset the typed path builds (no default arguments, no tuples, no
properties, one class per value). urllower.py parses it, keeps the definitions a program reaches (a
definition names the others it needs by using them) and puts them in front of the program. The C
primitives (`_ail_ht_*` over libcurl in ailhttp_core.h, `_ail_ur_*` in ailurl_core.h) are listed in
urllower.PRIMS; the exceptions `URLError` and `HTTPError` are the names the typed path knows.

Where CPython 3.12 has the behaviour, the comment says which file and function it is taken from:
  urllib/request.py   Request, AbstractHTTPHandler.do_request_ / do_open, HTTPRedirectHandler,
                      HTTPErrorProcessor, HTTPDefaultErrorHandler
  http/client.py      HTTPConnection._send_request / putrequest / _get_hostport
  urllib/parse.py     urlsplit, urlunsplit, urljoin, quote, quote_from_bytes, urlencode, unquote
Differences are listed in docs/spec/DIFFERENCES.md (C24 ff).
"""


# ---------------------------------------------------------------------------------------- urllib.parse

class _AilUrl:
    def __init__(self, scheme: str, netloc: str, path: str, query: str, fragment: str):
        self.scheme = scheme
        self.netloc = netloc
        self.path = path
        self.query = query
        self.fragment = fragment


def _ail_ul_isscheme(c: str) -> bool:
    # urllib.parse.scheme_chars: letters, digits and "+-."
    return (c >= "a" and c <= "z") or (c >= "A" and c <= "Z") or (c >= "0" and c <= "9") or c == "+" or c == "-" or c == "."


def _ail_ul_isalpha_ascii(c: str) -> bool:
    return (c >= "a" and c <= "z") or (c >= "A" and c <= "Z")


# urllib.parse.urlsplit (the ';params' of urlparse stay inside the path, which unsplits to the same text)
def _ail_ul_split(url0: str) -> _AilUrl:
    start = 0
    while start < len(url0) and ord(url0[start]) <= 32:
        start += 1
    url = url0[start:]
    url = url.replace("\t", "")
    url = url.replace("\r", "")
    url = url.replace("\n", "")
    scheme = ""
    i = url.find(":")
    if i > 0 and _ail_ul_isalpha_ascii(url[0:1]):
        ok = True
        for c in url[0:i]:
            if not _ail_ul_isscheme(c):
                ok = False
        if ok:
            scheme = url[0:i].lower()
            url = url[i + 1:]
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
    h = url.find("#")
    if h >= 0:
        fragment = url[h + 1:]
        url = url[0:h]
    query = ""
    q = url.find("?")
    if q >= 0:
        query = url[q + 1:]
        url = url[0:q]
    return _AilUrl(scheme, netloc, url, query, fragment)


def _ail_ul_usesnetloc(scheme: str) -> bool:
    names = ["", "ftp", "http", "gopher", "nntp", "telnet", "imap", "wais", "file", "mms", "https", "shttp", "snews",
             "prospero", "rtsp", "rtspu", "rsync", "svn", "svn+ssh", "sftp", "nfs", "git", "git+ssh", "ws", "wss"]
    return scheme in names


def _ail_ul_usesrelative(scheme: str) -> bool:
    names = ["", "ftp", "http", "gopher", "nntp", "imap", "wais", "file", "https", "shttp", "mms", "prospero", "rtsp",
             "rtspu", "sftp", "svn", "svn+ssh", "ws", "wss"]
    return scheme in names


# urllib.parse.urlunsplit
def _ail_ul_unsplit(scheme: str, netloc: str, path0: str, query: str, fragment: str) -> str:
    url = path0
    if netloc != "" or (scheme != "" and _ail_ul_usesnetloc(scheme) and url[0:2] != "//"):
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


# urllib.parse.urljoin
def _ail_ul_urljoin(base: str, url: str) -> str:
    if base == "":
        return url
    if url == "":
        return base
    b = _ail_ul_split(base)
    u = _ail_ul_split(url)
    scheme = u.scheme
    if scheme == "":
        scheme = b.scheme
    if scheme != b.scheme or not _ail_ul_usesrelative(scheme):
        return url
    netloc = u.netloc
    if _ail_ul_usesnetloc(scheme):
        if netloc != "":
            return _ail_ul_unsplit(scheme, netloc, u.path, u.query, u.fragment)
        netloc = b.netloc
    if u.path == "":
        path = b.path
        query = u.query
        if query == "":
            query = b.query
        return _ail_ul_unsplit(scheme, netloc, path, query, u.fragment)
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
        # segments[1:-1] = filter(None, segments[1:-1])
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
        elif seg == ".":
            pass
        else:
            resolved.append(seg)
    last = segments[len(segments) - 1]
    if last == "." or last == "..":
        resolved.append("")
    joined = "/".join(resolved)
    if joined == "":
        joined = "/"
    return _ail_ul_unsplit(scheme, netloc, joined, u.query, u.fragment)


def _ail_ul_hexdigit(n: int) -> str:
    return "0123456789ABCDEF"[n:n + 1]


# urllib.parse.quote / quote_plus (str input, UTF-8): bytes outside A-Za-z0-9_.-~ and `safe` become %XX
def _ail_ul_quote(s: str, safe: str, plus: bool) -> str:
    keep = safe
    if plus and " " in s:
        keep = safe + " "
    data = s.encode()
    out = ""
    for b in data:
        c = chr(b)
        if (b >= 48 and b <= 57) or (b >= 65 and b <= 90) or (b >= 97 and b <= 122) or c == "_" or c == "." or c == "-" or c == "~":
            out += c
        elif b < 128 and c in keep:
            if plus and c == " ":
                out += "+"
            else:
                out += c
        else:
            out += "%" + _ail_ul_hexdigit(b // 16) + _ail_ul_hexdigit(b % 16)
    return out


# urllib.parse.urlencode(dict) with str keys and values: quote_plus of each, joined with '&'
def _ail_ul_urlencode(keys: list[str], vals: list[str]) -> str:
    out = ""
    for i in range(len(keys)):
        if i > 0:
            out += "&"
        out += _ail_ul_quote(keys[i], "", True) + "=" + _ail_ul_quote(vals[i], "", True)
    return out


def _ail_ul_unquote(s: str, plus: bool) -> str:
    flag = 0
    if plus:
        flag = 1
    return _ail_ur_unquote(s, flag)


# ---------------------------------------------------------------------------------------- urllib.request

# str.capitalize() / str.title() of an ASCII header name
def _ail_ul_capitalize(s: str) -> str:
    if len(s) == 0:
        return s
    return s[0:1].upper() + s[1:].lower()


def _ail_ul_title(s: str) -> str:
    out = ""
    prev = False
    for ch in s:
        if prev:
            out += ch.lower()
        else:
            out += ch.upper()
        prev = ch.isalpha()
    return out


def _ail_ul_unwrap(url: str) -> str:
    u = url.strip()
    if u[0:1] == "<" and u[len(u) - 1:] == ">":
        u = u[1:len(u) - 1].strip()
    if u[0:4] == "URL:":
        u = u[4:].strip()
    return u


# the "scheme" of _splittype: [^/:]+ before the first ':'; "" when there is none
def _ail_ul_scheme_of(url: str) -> str:
    ci = url.find(":")
    if ci > 0 and "/" not in url[0:ci]:
        return url[0:ci].lower()
    return ""


class _AilRequest:
    def __init__(self, url: str, data: bytes, has_data: bool, method: str):
        self.url = url
        self.data = data
        self.has_data = has_data
        self.method = method
        self.hn: list[str] = []
        self.hv: list[str] = []
        self.un: list[str] = []
        self.uv: list[str] = []

    def add_header(self, key: str, val: str) -> None:
        k = _ail_ul_capitalize(key)
        for i in range(len(self.hn)):
            if self.hn[i] == k:
                self.hv[i] = val
                return
        self.hn.append(k)
        self.hv.append(val)

    def add_unredirected_header(self, key: str, val: str) -> None:
        k = _ail_ul_capitalize(key)
        for i in range(len(self.un)):
            if self.un[i] == k:
                self.uv[i] = val
                return
        self.un.append(k)
        self.uv.append(val)

    def has_header(self, name: str) -> bool:
        return name in self.hn or name in self.un

    def get_header(self, name: str, default: str) -> str:
        for i in range(len(self.hn)):
            if self.hn[i] == name:
                return self.hv[i]
        for i in range(len(self.un)):
            if self.un[i] == name:
                return self.uv[i]
        return default

    def remove_header(self, name: str) -> None:
        hn: list[str] = []
        hv: list[str] = []
        for i in range(len(self.hn)):
            if self.hn[i] != name:
                hn.append(self.hn[i])
                hv.append(self.hv[i])
        self.hn = hn
        self.hv = hv
        un: list[str] = []
        uv: list[str] = []
        for i in range(len(self.un)):
            if self.un[i] != name:
                un.append(self.un[i])
                uv.append(self.uv[i])
        self.un = un
        self.uv = uv

    def get_method(self) -> str:
        if self.method != "":
            return self.method
        if self.has_data:
            return "POST"
        return "GET"

    def get_full_url(self) -> str:
        return self.url


# Request(url, data, headers, method): Request.__init__ and its full_url setter
def _ail_ul_request(url: str, data: bytes, has_data: bool, method: str, hk: list[str], hv: list[str]) -> _AilRequest:
    full = _ail_ul_unwrap(url)
    pos = full.rfind("#")
    nofrag = full
    frag = ""
    if pos >= 0:
        nofrag = full[0:pos]
        frag = full[pos + 1:]
    if _ail_ul_scheme_of(nofrag) == "":
        raise ValueError("unknown url type: " + _ail_ur_repr(full))
    shown = nofrag
    if frag != "":
        shown = nofrag + "#" + frag
    req = _AilRequest(shown, data, has_data, method)
    for i in range(len(hk)):
        req.add_header(hk[i], hv[i])
    return req


class _AilResponse:
    def __init__(self, h: int, status: int, reason: str, url: str):
        self.h = h
        self.status = status
        self.reason = reason
        self.url = url

    def read(self, amt: int) -> bytes:
        return _ail_ht_read(self.h, amt)

    def close(self) -> None:
        _ail_u = _ail_ht_close(self.h)

    def hget(self, name: str, default: str) -> str:
        return _ail_ul_hget(self.h, name, default)

    def hjoin(self, name: str, default: str) -> str:
        return _ail_ul_hjoin(self.h, name, default)

    def hhas(self, name: str) -> bool:
        return _ail_ht_hfind(self.h, name) >= 0


def _ail_ul_hget(h: int, name: str, default: str) -> str:
    i = _ail_ht_hfind(h, name)
    if i < 0:
        return default
    return _ail_ht_hval(h, i)


# HTTPResponse.getheader(name, default): every header of that name, joined with ", "
def _ail_ul_hjoin(h: int, name: str, default: str) -> str:
    low = name.lower()
    out = ""
    found = False
    for i in range(_ail_ht_nhdr(h)):
        if _ail_ht_hname(h, i).lower() == low:
            if found:
                out += ", "
            out += _ail_ht_hval(h, i)
            found = True
    if not found:
        return default
    return out


def _ail_ul_hhas(h: int, name: str) -> bool:
    return _ail_ht_hfind(h, name) >= 0


def _ail_ul_has(req: _AilRequest, extra: list[str], name: str) -> bool:
    return name in req.hn or name in extra


def _ail_ul_lower_has(names: list[str], lowered: str) -> bool:
    for n in names:
        if n.lower() == lowered:
            return True
    return False


def _ail_ul_urlerror(url: str, reason: str) -> None:
    msg = "<urlopen error " + reason + ">"
    _ail_u = _ail_ht_eset(0, 2, 0, url, reason, msg)
    raise URLError(msg)


# urllib.request.OpenerDirector.open for http / https: do_request_, do_open, then the error processing
# (HTTPErrorProcessor -> HTTPRedirectHandler.http_error_302 / HTTPDefaultErrorHandler)
def _ail_ul_open(req0: _AilRequest, tmo: int) -> _AilResponse:
    cur = req0
    seen_urls: list[str] = []
    seen_counts: list[int] = []
    while True:
        full = cur.url
        pos = full.rfind("#")
        nofrag = full
        if pos >= 0:
            nofrag = full[0:pos]
        scheme = _ail_ul_scheme_of(nofrag)
        rest = nofrag
        if scheme != "":
            rest = nofrag[len(scheme) + 1:]
        if scheme != "http" and scheme != "https":
            _ail_ul_urlerror(full, "unknown url type: " + scheme)
        host = ""
        selector = rest
        if rest.startswith("//"):
            e = len(rest)
            for c in "/#?":
                w = rest.find(c, 2)
                if w >= 0 and w < e:
                    e = w
            host = rest[2:e]
            selector = rest[e:]
            if selector != "" and selector[0:1] != "/":
                selector = "/" + selector
        if host == "":
            _ail_ul_urlerror(full, "no host given")
        host = _ail_ul_unquote(host, False)
        # HTTPConnection._get_hostport
        default_port = 80
        if scheme == "https":
            default_port = 443
        port = default_port
        hostname = host
        ci = host.rfind(":")
        bj = host.rfind("]")
        if ci > bj:
            ps = host[ci + 1:]
            if ps != "":
                if not ps.isdigit():
                    raise ValueError("nonnumeric port: '" + ps + "'")
                port = int(ps)
            hostname = host[0:ci]
        if hostname[0:1] == "[" and hostname[len(hostname) - 1:] == "]":
            hostname = hostname[1:len(hostname) - 1]
        for c in hostname:
            if ord(c) > 127:
                raise ValueError("a host name with non-ASCII characters is not built")
            if ord(c) <= 32 or ord(c) == 127:
                raise ValueError("URL can't contain control characters. " + _ail_ur_repr(hostname))
        for c in selector:
            if ord(c) > 127:
                raise ValueError("'ascii' codec can't encode a character of the request target: " + _ail_ur_repr(selector))
            if ord(c) <= 32 or ord(c) == 127:
                raise ValueError("URL can't contain control characters. " + _ail_ur_repr(selector))
        target = selector
        if target == "":
            target = "/"
        netloc = hostname
        if ":" in hostname:
            netloc = "[" + hostname + "]"
        curl_url = scheme + "://" + netloc + ":" + str(port) + target
        # --- do_request_: the headers urllib adds to the request ("unredirected") ---
        un_n: list[str] = []
        un_v: list[str] = []
        for i in range(len(cur.un)):
            un_n.append(cur.un[i])
            un_v.append(cur.uv[i])
        if cur.has_data:
            if not _ail_ul_has(cur, un_n, "Content-type"):
                un_n.append("Content-type")
                un_v.append("application/x-www-form-urlencoded")
            if not _ail_ul_has(cur, un_n, "Content-length") and not _ail_ul_has(cur, un_n, "Transfer-encoding"):
                un_n.append("Content-length")
                un_v.append(str(len(cur.data)))
        if not _ail_ul_has(cur, un_n, "Host"):
            un_n.append("Host")
            un_v.append(host)
        if not _ail_ul_has(cur, un_n, "User-agent"):
            un_n.append("User-agent")
            un_v.append("Python-urllib/3.12")
        # --- do_open: unredirected first, then the request's own headers, then Connection: close, names title-cased ---
        names: list[str] = []
        vals: list[str] = []
        for i in range(len(un_n)):
            names.append(un_n[i])
            vals.append(un_v[i])
        for i in range(len(cur.hn)):
            if cur.hn[i] not in un_n:
                names.append(cur.hn[i])
                vals.append(cur.hv[i])
        conn = -1
        for i in range(len(names)):
            if names[i] == "Connection":
                conn = i
        if conn >= 0:
            vals[conn] = "close"
        else:
            names.append("Connection")
            vals.append("close")
        titled: list[str] = []
        for n in names:
            titled.append(_ail_ul_title(n))
        method = cur.get_method()
        # --- HTTPConnection._send_request: Accept-Encoding and Content-Length come before the others ---
        wire_n: list[str] = []
        wire_v: list[str] = []
        if not _ail_ul_lower_has(titled, "accept-encoding"):
            wire_n.append("Accept-Encoding")
            wire_v.append("identity")
        if not _ail_ul_lower_has(titled, "content-length") and not _ail_ul_lower_has(titled, "transfer-encoding"):
            if not cur.has_data:
                um = method.upper()
                if um == "POST" or um == "PUT" or um == "PATCH":
                    wire_n.append("Content-Length")
                    wire_v.append("0")
        for i in range(len(titled)):
            wire_n.append(titled[i])
            wire_v.append(vals[i])
        _ail_u = _ail_ht_begin(method, curl_url, tmo)
        for i in range(len(wire_n)):
            _ail_u = _ail_ht_hdr(wire_n[i], wire_v[i])
        if cur.has_data:
            _ail_u = _ail_ht_body(cur.data)
        h = _ail_ht_perform()
        if _ail_ht_failed(h) != 0:
            why = _ail_ht_errtext(h)
            _ail_u = _ail_ht_free(h)
            _ail_ul_urlerror(full, why)
        code = _ail_ht_status(h)
        reason = _ail_ht_reason(h)
        if code >= 200 and code < 300:
            return _AilResponse(h, code, reason, full)
        # --- HTTPErrorProcessor: anything but 2xx goes to the error handlers ---
        if code == 301 or code == 302 or code == 303 or code == 307 or code == 308:
            li = _ail_ht_hfind(h, "location")
            if li < 0:
                li = _ail_ht_hfind(h, "uri")
            if li >= 0:
                newurl = _ail_ht_hval(h, li)
                sp = _ail_ul_split(newurl)
                if sp.scheme != "http" and sp.scheme != "https" and sp.scheme != "ftp" and sp.scheme != "":
                    msg = reason + " - Redirection to url '" + newurl + "' is not allowed"
                    text = "HTTP Error " + str(code) + ": " + msg
                    _ail_u = _ail_ht_eset(h, 1, code, newurl, msg, text)
                    raise HTTPError(text)
                spath = sp.path
                if spath == "" and sp.netloc != "":
                    spath = "/"
                newurl = _ail_ul_unsplit(sp.scheme, sp.netloc, spath, sp.query, sp.fragment)
                newurl = _ail_ul_quote(newurl, "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~", False)
                newurl = _ail_ul_urljoin(full, newurl)
                m = method
                allowed = False
                if (m == "GET" or m == "HEAD") and (code == 301 or code == 302 or code == 303 or code == 307 or code == 308):
                    allowed = True
                if m == "POST" and (code == 301 or code == 302 or code == 303):
                    allowed = True
                if not allowed:
                    text = "HTTP Error " + str(code) + ": " + reason
                    _ail_u = _ail_ht_eset(h, 1, code, full, reason, text)
                    raise HTTPError(text)
                newurl = newurl.replace(" ", "%20")
                # loop detection (HTTPRedirectHandler.max_repeats = 4, max_redirections = 10)
                seen_at = -1
                for k in range(len(seen_urls)):
                    if seen_urls[k] == newurl:
                        seen_at = k
                repeats = 0
                if seen_at >= 0:
                    repeats = seen_counts[seen_at]
                if repeats >= 4 or len(seen_urls) >= 10:
                    msg = "The HTTP server returned a redirect error that would lead to an infinite loop.\n" + "The last 30x error message was:\n" + reason
                    text = "HTTP Error " + str(code) + ": " + msg
                    _ail_u = _ail_ht_eset(h, 1, code, full, msg, text)
                    raise HTTPError(text)
                if seen_at >= 0:
                    seen_counts[seen_at] = repeats + 1
                else:
                    seen_urls.append(newurl)
                    seen_counts.append(1)
                nextreq = _ail_ul_request(newurl, b"", False, "", [], [])
                for i in range(len(cur.hn)):
                    low = cur.hn[i].lower()
                    if low != "content-length" and low != "content-type":
                        nextreq.add_header(cur.hn[i], cur.hv[i])
                _ail_u = _ail_ht_free(h)
                cur = nextreq
                continue
        text = "HTTP Error " + str(code) + ": " + reason
        _ail_u = _ail_ht_eset(h, 1, code, full, reason, text)
        raise HTTPError(text)
    return _AilResponse(0, 0, "", "")


def _ail_ul_open_url(url: str, data: bytes, has_data: bool, tmo: int) -> _AilResponse:
    return _ail_ul_open(_ail_ul_request(url, data, has_data, "", [], []), tmo)
