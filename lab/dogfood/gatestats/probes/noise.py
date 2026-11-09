"""Gate statistics for the AIL integration log.

Usage: gatestats.py LOG

Per day (day 1 starts at the first timestamp, a later time that is smaller
starts the next day) the report has:
  candidates, merged jobs, red batches, red-alone jobs, culprit-unavailable
  events, and the hours from every red event to its resolution.
A red event is a `red:` line (not `red alone:`); a red-alone event is a
`red alone:` line.  Its resolution is the next `candidate` or `merged` line.
The top modules are the module names: the name before `broken by` on a
`red:` line, otherwise the names in the parenthesised test list.  They are
ordered by count then name.
"""
import sys
from dataclasses import dataclass


@dataclass
class DayStats:
    candidates: int
    merged_jobs: int
    red_batches: int
    red_alone: int
    culprit: int
    durations: list[int]
    alone_durations: list[int]


def parse_ts(line: str) -> int:
    return int(line[0:2]) * 3600 + int(line[3:5]) * 60 + int(line[6:8])


def is_log_line(line: str) -> bool:
    return len(line) >= 9 and line[2] == ":" and line[5] == ":" and line[0].isdigit()


def count_jobs(rest: str) -> int:
    text = rest.strip()
    if text == "":
        return 0
    return len(text.split())


def module_names(message: str) -> list[str]:
    names: list[str] = []
    after = message[message.find(": ") + 2:]
    idx = after.find(" broken by ")
    if idx >= 0:
        name = after[0:idx].strip()
        if name != "":
            names.append(name)
        return names
    open_paren = after.find("(")
    if open_paren >= 0:
        tail = after[open_paren + 1:]
        close_paren = tail.find(")")
        if close_paren >= 0:
            for module in tail[0:close_paren].split():
                names.append(module)
    return names


@dataclass
class Ranked:
    count: int
    name: str


def new_day() -> DayStats:
    return DayStats(0, 0, 0, 0, 0, [], [])


def main() -> int:
    text = """usage: git [--version]
fatal: not a git repository
random text line
"""
    lines = text.splitlines()

    stats: list[DayStats] = []
    counts: dict[str, int] = {}
    pending_day: list[int] = []
    pending_abs: list[int] = []
    pending_alone: list[int] = []
    day = 0
    prev_ts = -1

    for line in lines:
        if not is_log_line(line):
            continue
        ts = parse_ts(line)
        if prev_ts >= 0 and ts < prev_ts:
            day += 1
        prev_ts = ts
        while len(stats) <= day:
            stats.append(new_day())
        cur = stats[day]
        message = line[9:]

        if message.startswith("candidate ") or message.startswith("merged "):
            rest = message[message.find(": ") + 2:]
            abs_t = day * 86400 + ts
            i = 0
            while i < len(pending_abs):
                cur_day = pending_day[i]
                if pending_alone[i] != 0:
                    stats[cur_day].alone_durations.append(abs_t - pending_abs[i])
                else:
                    stats[cur_day].durations.append(abs_t - pending_abs[i])
                i += 1
            pending_day.clear()
            pending_abs.clear()
            pending_alone.clear()
            if message.startswith("candidate "):
                cur.candidates += 1
            else:
                cur.merged_jobs += count_jobs(rest)
        elif message.startswith("red alone: "):
            cur.red_alone += 1
            pending_day.append(day)
            pending_abs.append(day * 86400 + ts)
            pending_alone.append(1)
            for module in module_names(message):
                counts[module] = counts.get(module, 0) + 1
        elif message.startswith("red: "):
            cur.red_batches += 1
            pending_day.append(day)
            pending_abs.append(day * 86400 + ts)
            pending_alone.append(0)
            for module in module_names(message):
                counts[module] = counts.get(module, 0) + 1
        elif message.startswith("culprit.yml unavailable"):
            cur.culprit += 1

    for i in range(len(stats)):
        s = stats[i]
        line = f"day {i + 1} candidates={s.candidates} merged_jobs={s.merged_jobs} red_batches={s.red_batches} red_alone={s.red_alone} culprit_unavailable={s.culprit} red_batch_hours="
        if len(s.durations) == 0:
            line += "-"
        else:
            parts: list[str] = []
            for d in s.durations:
                parts.append(f"{d / 3600.0:.2f}")
            line += ",".join(parts)
        line += " red_alone_hours="
        if len(s.alone_durations) == 0:
            line += "-"
        else:
            parts2: list[str] = []
            for d in s.alone_durations:
                parts2.append(f"{d / 3600.0:.2f}")
            line += ",".join(parts2)
        print(line)

    top: list[Ranked] = []
    for name in counts:
        top.append(Ranked(counts[name], name))
    top.sort(key=lambda r: (-r.count, r.name))
    print("top modules:")
    n = len(top)
    if n > 5:
        n = 5
    for i in range(n):
        print(f"{i + 1}. {top[i].name} {top[i].count}")
    if n == 0:
        print("(none)")
    if len(pending_abs) != 0:
        print(f"unresolved red events: {len(pending_abs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
