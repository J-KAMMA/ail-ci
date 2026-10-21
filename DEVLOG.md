# DEVLOG

## 2026-10-21 -- job-fuzz3n-10220658

Closed DIFFERENCES C168. A `None` start or end of `str.find`, `rfind`, `count`,
`startswith`, `endswith`, `index` or `rindex` is CPython's default bound, but the
general path read it as a present bound of 0 and so searched an empty window
(`"hello".find("l", None, None)` was -1, CPython 2). Fixed in
`AIL_CURRENT/python/pkg-v12/pyboxed2.py`: the emitter now tests each supplied
bound's tag and passes `has_lo = 0` / `has_hi = 0` for a `None`, so a `None` that
reaches the method through a variable, a function argument, a list item, a dict
value or an attribute works too. The list/tuple branch of `_m_index` is
unchanged; its own `None` handling is a separate open row.

Tests: new `AIL_CURRENT/test_ail_fuzz3n.py` (registered in `ail_check.py`), five
programs run against CPython on both builds. Probes under `/tmp/probes/`
(`p_basic`, `p_var`, `p_arg`, `p_mixed`, `p_types`, `p_sources`,
`p_tuple_prefix`, `p_errors`) all match CPython on the general and default builds.
