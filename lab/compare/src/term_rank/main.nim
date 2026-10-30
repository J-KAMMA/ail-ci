import std/[tables, algorithm, os, strutils]

const stops = ["an","and","are","as","at","be","but","by","for","from","had","has","have","he","her","his","in","into","is","it","its","not","of","on","or","our","she","so","than","that","the","their","them","then","there","these","they","this","to","was","we","were","which","will","with","you","your"]

proc isWord(c: char): bool {.inline.} =
  (c in {'a'..'z'}) or (c in {'A'..'Z'}) or (c in {'0'..'9'}) or ord(c) >= 0x80

proc main() =
  if paramCount() != 1:
    quit(1)
  let ks = paramStr(1)
  if ks.len == 0: quit(1)
  var k = 0
  for c in ks:
    if c notin {'0'..'9'}: quit(1)
    k = min(k * 10 + (ord(c) - 48), 100000)
  if k < 1 or k > 1000: quit(1)

  var stopSet = initTable[string, bool]()
  for s in stops: stopSet[s] = true

  let data = readAll(stdin)
  var docs: seq[Table[string, int]]
  var cur = initTable[string, int]()
  var pos = 0
  let n = data.len
  while pos < n:
    var e = pos
    while e < n and data[e] != '\n': inc e
    let ll = e - pos
    let isSep = (ll == 2 and data[pos] == '%' and data[pos+1] == '%') or
                (ll == 3 and data[pos] == '%' and data[pos+1] == '%' and data[pos+2] == '\r')
    if isSep:
      docs.add cur
      cur = initTable[string, int]()
    else:
      var i = pos
      while i < e:
        if not isWord(data[i]):
          inc i
          continue
        var j = i
        while j < e:
          if isWord(data[j]): inc j
          elif (data[j] == '\'' or data[j] == '-') and j + 1 < e and isWord(data[j+1]): inc j
          else: break
        var t = newStringOfCap(j - i)
        var allDigit = true
        for x in i ..< j:
          var c = data[x]
          if c == '\'': continue
          if c in {'A'..'Z'}: c = chr(ord(c) + 32)
          if c notin {'0'..'9'}: allDigit = false
          t.add c
        i = j
        if allDigit:
          t = "#" & $t.len
        if t.len < 2: continue
        if stopSet.hasKey(t): continue
        if t.len >= 5 and t.endsWith("ing"):
          t.setLen(t.len - 3)
        elif t.len >= 4 and t[^1] == 's' and not t.endsWith("ss"):
          t.setLen(t.len - 1)
        cur.mgetOrPut(t, 0) += 1
    pos = e + 1
  docs.add cur

  let nd = docs.len
  var df = initTable[string, int]()
  var total = initTable[string, int]()
  for d in docs:
    for t, c in d:
      df.mgetOrPut(t, 0) += 1
      total.mgetOrPut(t, 0) += c

  var outp = ""
  for di, d in docs:
    var items: seq[(int64, string)]
    for t, c in d:
      let tf = int64(c)
      let sc = tf * 1000'i64 * int64(nd + 1) div (int64(df[t]) * (tf + 2))
      items.add (sc, t)
    items.sort(proc (a, b: (int64, string)): int =
      if a[0] != b[0]: return (if a[0] > b[0]: -1 else: 1)
      cmp(a[1], b[1]))
    outp.add "doc " & $(di + 1) & ":"
    for x in 0 ..< min(k, items.len):
      outp.add " " & items[x][1] & "=" & $items[x][0]
    outp.add "\n"
  var items: seq[(int, string)]
  for t, c in total: items.add (c, t)
  items.sort(proc (a, b: (int, string)): int =
    if a[0] != b[0]: return (if a[0] > b[0]: -1 else: 1)
    cmp(a[1], b[1]))
  outp.add "all:"
  for x in 0 ..< min(k, items.len):
    outp.add " " & items[x][1] & "=" & $items[x][0]
  outp.add "\n"
  stdout.write outp

main()
