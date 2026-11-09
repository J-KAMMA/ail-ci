package main

import (
	"bufio"
	"fmt"
	"io"
	"os"
	"sort"
	"strconv"
	"strings"
	"unicode/utf8"
)

type item struct {
	text string
	done bool
}

func parseID(s string) (int64, bool) {
	if s == "" {
		return 0, false
	}
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return 0, false
		}
	}
	t := strings.TrimLeft(s, "0")
	if t == "" || len(t) > 10 {
		return 0, false
	}
	v, err := strconv.ParseInt(t, 10, 64)
	if err != nil || v < 1 || v > 2147483647 {
		return 0, false
	}
	return v, true
}

func main() {
	var data []byte
	var err error
	if len(os.Args) >= 2 {
		data, err = os.ReadFile(os.Args[1])
	} else {
		data, err = io.ReadAll(os.Stdin)
	}
	if err != nil {
		return
	}

	out := bufio.NewWriter(os.Stdout)
	defer out.Flush()

	items := make(map[int64]*item)
	errCount := 0

	reject := func(op string) {
		errCount++
		fmt.Fprintf(out, "error %s\n", op)
	}

	for _, line := range strings.Split(string(data), "\n") {
		if line == "" {
			continue
		}

		sp := strings.IndexByte(line, ' ')
		hasSpace := sp >= 0
		var cmd, rest string
		if hasSpace {
			cmd = line[:sp]
			rest = line[sp+1:]
		} else {
			cmd = line
		}

		if cmd == "" {
			reject("error")
			continue
		}

		switch cmd {
		case "add":
			sp2 := -1
			if hasSpace {
				sp2 = strings.IndexByte(rest, ' ')
			}
			if sp2 < 0 {
				reject("add")
				continue
			}
			id, ok := parseID(rest[:sp2])
			text := rest[sp2+1:]
			if !ok || text == "" {
				reject("add")
				continue
			}
			if _, exists := items[id]; exists {
				reject("add")
				continue
			}
			items[id] = &item{text: text}
			fmt.Fprintf(out, "added %d\n", id)

		case "done":
			if !hasSpace || strings.IndexByte(rest, ' ') >= 0 {
				reject("done")
				continue
			}
			id, ok := parseID(rest)
			if !ok {
				reject("done")
				continue
			}
			it, exists := items[id]
			if !exists || it.done {
				reject("done")
				continue
			}
			it.done = true
			fmt.Fprintf(out, "done %d\n", id)

		case "remove":
			if !hasSpace || strings.IndexByte(rest, ' ') >= 0 {
				reject("remove")
				continue
			}
			id, ok := parseID(rest)
			if !ok {
				reject("remove")
				continue
			}
			if _, exists := items[id]; !exists {
				reject("remove")
				continue
			}
			delete(items, id)
			fmt.Fprintf(out, "removed %d\n", id)

		case "show":
			if !hasSpace || strings.IndexByte(rest, ' ') >= 0 {
				reject("show")
				continue
			}
			id, ok := parseID(rest)
			if !ok {
				reject("show")
				continue
			}
			it, exists := items[id]
			if !exists {
				reject("show")
				continue
			}
			state := "open"
			if it.done {
				state = "done"
			}
			fmt.Fprintf(out, "todo %d %s %s\n", id, state, it.text)

		case "list":
			if hasSpace {
				reject("list")
				continue
			}
			ids := make([]int64, 0, len(items))
			for id, it := range items {
				if !it.done {
					ids = append(ids, id)
				}
			}
			sort.Slice(ids, func(i, j int) bool { return ids[i] < ids[j] })
			fmt.Fprintf(out, "list %d\n", len(ids))
			for _, id := range ids {
				fmt.Fprintf(out, "todo %d open %s\n", id, items[id].text)
			}

		case "stats":
			if hasSpace {
				reject("stats")
				continue
			}
			open, done, chars := 0, 0, 0
			for _, it := range items {
				if it.done {
					done++
				} else {
					open++
				}
				chars += utf8.RuneCountInString(it.text)
			}
			fmt.Fprintf(out, "stats total %d open %d done %d chars %d errors %d\n",
				open+done, open, done, chars, errCount)

		default:
			reject(cmd)
		}
	}
}
