# -*- coding: utf-8 -*-
# prelude_html.py -- `html.escape` as Python source (stdtop.py injects it).
#
# html.escape(s, quote=True) of CPython 3.12: & < > always, " and \' when quote is true. Two functions, so that
# html.escape can be passed around as a value: the one-argument form, and the form with `quote`.


def _ail_html_escape_q(text, quote):
    if isinstance(text, bytes) or isinstance(text, bytearray):
        raise TypeError("a bytes-like object is required, not 'str'")
    if not isinstance(text, str):
        if text is None:
            raise AttributeError("'NoneType' object has no attribute 'replace'")
        raise AttributeError("'%s' object has no attribute 'replace'" % type(text).__name__)
    out = text.replace("&", "&amp;")
    out = out.replace("<", "&lt;")
    out = out.replace(">", "&gt;")
    if quote:
        out = out.replace('"', "&quot;")
        out = out.replace("'", "&#x27;")
    return out


def _ail_html_escape(text):
    return _ail_html_escape_q(text, True)
