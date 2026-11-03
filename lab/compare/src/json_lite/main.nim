import std/[strutils, os]

type Parser = object
  s: string
  i: int
  total: int64

proc skipWS(p: var Parser) =
  while p.i < p.s.len:
    let c = p.s[p.i]
    if c == ' ' or c == '\t' or c == '\r' or c == '\n':
      inc p.i
    else:
      break

proc skipString(p: var Parser) =
  inc p.i
  while p.i < p.s.len:
    if p.s[p.i] == '\\':
      p.i += 2
    elif p.s[p.i] == '"':
      inc p.i
      return
    else:
      inc p.i

proc parseValue(p: var Parser) =
  p.skipWS()
  if p.i >= p.s.len:
    return
  let c = p.s[p.i]
  if c == '{':
    inc p.i
    p.skipWS()
    if p.i < p.s.len and p.s[p.i] == '}':
      inc p.i
      return
    while true:
      p.skipWS()
      if p.i >= p.s.len:
        return
      p.skipString()
      p.skipWS()
      if p.i < p.s.len and p.s[p.i] == ':':
        inc p.i
      p.parseValue()
      p.skipWS()
      if p.i < p.s.len and p.s[p.i] == ',':
        inc p.i
        continue
      if p.i < p.s.len and p.s[p.i] == '}':
        inc p.i
      return
  if c == '[':
    inc p.i
    p.skipWS()
    if p.i < p.s.len and p.s[p.i] == ']':
      inc p.i
      return
    while true:
      p.skipWS()
      if p.i < p.s.len and p.s[p.i] == ']':
        inc p.i
        return
      if p.i >= p.s.len:
        return
      p.parseValue()
      p.skipWS()
      if p.i < p.s.len and p.s[p.i] == ',':
        inc p.i
        continue
      if p.i < p.s.len and p.s[p.i] == ']':
        inc p.i
      return
  if c == '"':
    p.skipString()
    return
  if c == '-' or c in {'0'..'9'}:
    let start = p.i
    if p.s[p.i] == '-':
      inc p.i
    while p.i < p.s.len and p.s[p.i] in {'0'..'9'}:
      inc p.i
    p.total += int64(parseInt(p.s[start ..< p.i]))
    return
  for word in ["true", "false", "null"]:
    if p.i + word.len <= p.s.len and p.s[p.i ..< p.i + word.len] == word:
      p.i += word.len
      return
  inc p.i

proc main() =
  var p = Parser(s: readAll(stdin), i: 0, total: 0'i64)
  while p.i < p.s.len:
    p.parseValue()
    p.skipWS()
    if p.i >= p.s.len:
      break
  stdout.write $p.total & "\n"

main()
