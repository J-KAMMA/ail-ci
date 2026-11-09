import sys


def parse_id(s):
    if s == '':
        return 0
    for c in s:
        if c < '0' or c > '9':
            return 0
    t = s.lstrip('0')
    if t == '':
        return 0
    if len(t) > 10:
        return 0
    v = int(t)
    if v >= 1 and v <= 2147483647:
        return v
    return 0


def main():
    with open(sys.argv[1], 'rb') as f:
        data = f.read()
    text = data.decode('utf-8', 'replace')

    texts = {}
    state = {}
    errors = 0
    out = ''

    for line in text.split('\n'):
        if line == '':
            continue
        sp = line.find(' ')
        if sp < 0:
            cmd = line
        else:
            cmd = line[:sp]
        err = ''

        if cmd == '':
            err = 'error'
        elif cmd == 'add':
            parts = line.split(' ', 2)
            if len(parts) < 3 or parts[2] == '':
                err = 'add'
            else:
                vid = parse_id(parts[1])
                if vid == 0 or vid in texts:
                    err = 'add'
                else:
                    texts[vid] = parts[2]
                    state[vid] = 0
                    out += 'added ' + str(vid) + '\n'
        elif cmd == 'done' or cmd == 'remove' or cmd == 'show':
            if sp < 0:
                err = cmd
            else:
                vid = parse_id(line[sp + 1:])
                if vid == 0 or vid not in texts:
                    err = cmd
                elif cmd == 'done':
                    if state[vid] == 1:
                        err = cmd
                    else:
                        state[vid] = 1
                        out += 'done ' + str(vid) + '\n'
                elif cmd == 'remove':
                    texts.pop(vid)
                    state.pop(vid)
                    out += 'removed ' + str(vid) + '\n'
                else:
                    st = 'open'
                    if state[vid] == 1:
                        st = 'done'
                    out += 'todo ' + str(vid) + ' ' + st + ' ' + texts[vid] + '\n'
        elif cmd == 'list':
            if sp >= 0:
                err = cmd
            else:
                ks = sorted(list(texts.keys()))
                open_ids = []
                for k in ks:
                    if state[k] == 0:
                        open_ids.append(k)
                out += 'list ' + str(len(open_ids)) + '\n'
                for k in open_ids:
                    out += 'todo ' + str(k) + ' open ' + texts[k] + '\n'
        elif cmd == 'stats':
            if sp >= 0:
                err = cmd
            else:
                total = len(texts)
                done_n = 0
                chars = 0
                for k in texts:
                    chars += len(texts[k])
                    if state[k] == 1:
                        done_n += 1
                open_n = total - done_n
                out += 'stats total ' + str(total) + ' open ' + str(open_n) \
                    + ' done ' + str(done_n) + ' chars ' + str(chars) \
                    + ' errors ' + str(errors) + '\n'
        else:
            err = cmd

        if err != '':
            out += 'error ' + err + '\n'
            errors += 1

    sys.stdout.write(out)
    sys.exit(0)


main()
