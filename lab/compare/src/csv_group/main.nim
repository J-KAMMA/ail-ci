import std/[tables, algorithm, strutils, os, sequtils]

proc main() =
  let data = readAll(stdin)
  var totals = initTable[string, int64]()
  for line in data.split('\n'):
    if line.len == 0:
      continue
    let cut = line.find(',')
    let key = line[0 ..< cut]
    let value = parseInt(line[cut + 1 .. ^1])
    totals[key] = totals.getOrDefault(key, 0'i64) + int64(value)
  var keys = toSeq(totals.keys)
  keys.sort()
  for key in keys:
    stdout.write key & "," & $totals[key] & "\n"

main()
