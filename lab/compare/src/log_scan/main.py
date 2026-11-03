import sys


def main():
    status_counts = {}
    hour_counts = {}
    for line in sys.stdin.read().split('\n'):
        if not line:
            continue
        parts = line.split(' ', 3)
        hour = int(parts[1][:2])
        status = parts[2]
        status_counts[status] = status_counts.get(status, 0) + 1
        hour_counts[hour] = hour_counts.get(hour, 0) + 1
    parts = []
    for status in sorted(status_counts):
        parts.append('status %s %d\n' % (status, status_counts[status]))
    for hour in sorted(hour_counts):
        parts.append('hour %02d %d\n' % (hour, hour_counts[hour]))
    sys.stdout.write(''.join(parts))


main()
