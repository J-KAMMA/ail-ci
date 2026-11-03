import std/[tables, algorithm, strutils, os, sequtils]

proc twoDigits(value: int): string =
  if value < 10:
    return "0" & $value
  return $value

proc main() =
  let data = readAll(stdin)
  var statuses = initTable[string, int64]()
  var hours = initTable[int, int64]()
  for line in data.split('\n'):
    if line.len == 0:
      continue
    let parts = line.split(' ', maxsplit = 3)
    if parts.len < 3:
      continue
    let hour = parseInt(parts[1][0 .. 1])
    statuses[parts[2]] = statuses.getOrDefault(parts[2], 0'i64) + 1
    hours[hour] = hours.getOrDefault(hour, 0'i64) + 1
  var statusKeys = toSeq(statuses.keys)
  statusKeys.sort()
  var hourKeys = toSeq(hours.keys)
  hourKeys.sort()
  for status in statusKeys:
    stdout.write "status " & status & " " & $statuses[status] & "\n"
  for hour in hourKeys:
    stdout.write "hour " & twoDigits(hour) & " " & $hours[hour] & "\n"

main()
