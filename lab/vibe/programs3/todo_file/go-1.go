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

func parseID(s string) (int, bool) {
	if s == "" {
		return 0, false
	}
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return 0, false
		}
	}
	v, err := strconv.Atoi(s)
	if err != nil {
		return 0, false
	}
	if v < 1 || v > 2147483647 {
		return 0, false
	}
	return v, true
}

func main() {
	if len(os.Args) < 2 {
		return
	}
	data, err := os.ReadFile(os.Args[1])
	if err != nil {
		return
	}

	w := bufio.NewWriter(os.Stdout)
	defer w.Flush()

	items := make(map[int]*item)
	ids := make([]int, 0)
	openCount := 0
	doneCount := 0
	chars := 0
	errCount := 0

	processLine := func(line string) {
		if line == "" {
			return
		}

		parts := strings.SplitN(line, " ", 3)
		cmd := parts[0]

		fail := func() {
			if cmd == "" {
				fmt.Fprintln(w, "error error")
			} else {
				fmt.Fprintf(w, "error %s\n", cmd)
			}
			errCount++
		}

		switch cmd {
		case "add":
			if len(parts) != 3 {
				fail()
				return
			}
			id, ok := parseID(parts[1])
			if !ok {
				fail()
				return
			}
			text := parts[2]
			if text == "" {
				fail()
				return
			}
			if _, exists := items[id]; exists {
				fail()
				return
			}
			items[id] = &item{text: text, done: false}
			pos := sort.SearchInts(ids, id)
			ids = append(ids, 0)
			copy(ids[pos+1:], ids[pos:])
			ids[pos] = id
			openCount++
			chars += utf8.RuneCountInString(text)
			fmt.Fprintf(w, "added %d\n", id)

		case "done":
			if len(parts) != 2 {
				fail()
				return
			}
			id, ok := parseID(parts[1])
			if !ok {
				fail()
				return
			}
			it, exists := items[id]
			if !exists || it.done {
				fail()
				return
			}
			it.done = true
			openCount--
			doneCount++
			fmt.Fprintf(w, "done %d\n", id)

		case "remove":
			if len(parts) != 2 {
				fail()
				return
			}
			id, ok := parseID(parts[1])
			if !ok {
				fail()
				return
			}
			it, exists := items[id]
			if !exists {
				fail()
				return
			}
			delete(items, id)
			pos := sort.SearchInts(ids, id)
			if pos < len(ids) && ids[pos] == id {
				ids = append(ids[:pos], ids[pos+1:]...)
			}
			if it.done {
				doneCount--
			} else {
				openCount--
			}
			chars -= utf8.RuneCountInString(it.text)
			fmt.Fprintf(w, "removed %d\n", id)

		case "show":
			if len(parts) != 2 {
				fail()
				return
			}
			id, ok := parseID(parts[1])
			if !ok {
				fail()
				return
			}
			it, exists := items[id]
			if !exists {
				fail()
				return
			}
			if it.done {
				fmt.Fprintf(w, "todo %d done %s\n", id, it.text)
			} else {
				fmt.Fprintf(w, "todo %d open %s\n", id, it.text)
			}

		case "list":
			if len(parts) != 1 {
				fail()
				return
			}
			fmt.Fprintf(w, "list %d\n", openCount)
			for _, id := range ids {
				it := items[id]
				if !it.done {
					fmt.Fprintf(w, "todo %d open %s\n", id, it.text)
				}
			}

		case "stats":
			if len(parts) != 1 {
				fail()
				return
			}
			fmt.Fprintf(w, "stats total %d open %d done %d chars %d errors %d\n",
				openCount+doneCount, openCount, doneCount, chars, errCount)

		default:
			fail()
		}
	}

	start := 0
	for i := 0; i <= len(data); i++ {
		if i == len(data) || data[i] == '\n' {
			line := data[start:i]
			if len(line) > 0 && line[len(line)-1] == '\r' {
				line = line[:len(line)-1]
			}
			processLine(string(line))
			start = i + 1
		}
	}
}
