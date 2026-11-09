package main

import (
	"bufio"
	"fmt"
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

func splitFirst(s string, sep byte) (string, string, bool) {
	i := strings.IndexByte(s, sep)
	if i < 0 {
		return s, "", false
	}
	return s[:i], s[i+1:], true
}

func parseID(s string) (int, bool) {
	if s == "" {
		return 0, false
	}
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return 0, false
		}
	}
	v, err := strconv.ParseInt(s, 10, 64)
	if err != nil || v < 1 || v > 2147483647 {
		return 0, false
	}
	return int(v), true
}

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: prog FILE")
		os.Exit(1)
	}
	data, err := os.ReadFile(os.Args[1])
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}

	w := bufio.NewWriter(os.Stdout)
	items := map[int]*item{}
	rejected := 0

	reject := func(op string) {
		rejected++
		fmt.Fprintf(w, "error %s\n", op)
	}

	for _, line := range strings.Split(string(data), "\n") {
		if strings.TrimSpace(line) == "" {
			continue
		}
		cmd, rest, hasRest := splitFirst(line, ' ')
		op := cmd
		if op == "" {
			op = "error"
		}

		switch cmd {
		case "add":
			idStr, text, ok := splitFirst(rest, ' ')
			id, valid := parseID(idStr)
			if !ok || text == "" || !valid {
				reject(op)
				continue
			}
			if _, exists := items[id]; exists {
				reject(op)
				continue
			}
			items[id] = &item{text: text}
			fmt.Fprintf(w, "added %d\n", id)

		case "done":
			id, valid := parseID(rest)
			if !valid {
				reject(op)
				continue
			}
			it, exists := items[id]
			if !exists || it.done {
				reject(op)
				continue
			}
			it.done = true
			fmt.Fprintf(w, "done %d\n", id)

		case "remove":
			id, valid := parseID(rest)
			if !valid {
				reject(op)
				continue
			}
			if _, exists := items[id]; !exists {
				reject(op)
				continue
			}
			delete(items, id)
			fmt.Fprintf(w, "removed %d\n", id)

		case "show":
			id, valid := parseID(rest)
			if !valid {
				reject(op)
				continue
			}
			it, exists := items[id]
			if !exists {
				reject(op)
				continue
			}
			state := "open"
			if it.done {
				state = "done"
			}
			fmt.Fprintf(w, "todo %d %s %s\n", id, state, it.text)

		case "list":
			if hasRest {
				reject(op)
				continue
			}
			var openIDs []int
			for id, it := range items {
				if !it.done {
					openIDs = append(openIDs, id)
				}
			}
			sort.Ints(openIDs)
			fmt.Fprintf(w, "list %d\n", len(openIDs))
			for _, id := range openIDs {
				fmt.Fprintf(w, "todo %d open %s\n", id, items[id].text)
			}

		case "stats":
			if hasRest {
				reject(op)
				continue
			}
			total, open, done, chars := 0, 0, 0, 0
			for _, it := range items {
				total++
				chars += utf8.RuneCountInString(it.text)
				if it.done {
					done++
				} else {
					open++
				}
			}
			fmt.Fprintf(w, "stats total %d open %d done %d chars %d errors %d\n",
				total, open, done, chars, rejected)

		default:
			reject(op)
		}
	}

	w.Flush()
}
