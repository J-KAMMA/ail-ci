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

// singleID parses the rest of a line that must consist of exactly one ID token.
func singleID(hasRest bool, rest string) (int, bool) {
	if !hasRest || strings.IndexByte(rest, ' ') >= 0 {
		return 0, false
	}
	return parseID(rest)
}

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: prog FILE")
		os.Exit(1)
	}
	f, err := os.Open(os.Args[1])
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	data, err := io.ReadAll(f)
	f.Close()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}

	lines := strings.Split(string(data), "\n")
	out := bufio.NewWriter(os.Stdout)
	defer out.Flush()

	items := make(map[int]*item)
	errorCount := 0

	reject := func(op string) {
		errorCount++
		fmt.Fprintf(out, "error %s\n", op)
	}

	for _, line := range lines {
		if strings.TrimSpace(line) == "" {
			continue
		}

		cmd := line
		rest := ""
		hasRest := false
		if i := strings.IndexByte(line, ' '); i >= 0 {
			cmd = line[:i]
			rest = line[i+1:]
			hasRest = true
		}

		opName := cmd
		if cmd == "" {
			opName = "error"
		}

		switch cmd {
		case "add":
			if !hasRest {
				reject(opName)
				continue
			}
			j := strings.IndexByte(rest, ' ')
			if j < 0 {
				reject(opName)
				continue
			}
			id, ok := parseID(rest[:j])
			txt := rest[j+1:]
			if !ok || txt == "" {
				reject(opName)
				continue
			}
			if _, exists := items[id]; exists {
				reject(opName)
				continue
			}
			items[id] = &item{text: txt}
			fmt.Fprintf(out, "added %d\n", id)

		case "done":
			id, ok := singleID(hasRest, rest)
			if !ok {
				reject(opName)
				continue
			}
			it, exists := items[id]
			if !exists || it.done {
				reject(opName)
				continue
			}
			it.done = true
			fmt.Fprintf(out, "done %d\n", id)

		case "remove":
			id, ok := singleID(hasRest, rest)
			if !ok {
				reject(opName)
				continue
			}
			if _, exists := items[id]; !exists {
				reject(opName)
				continue
			}
			delete(items, id)
			fmt.Fprintf(out, "removed %d\n", id)

		case "show":
			id, ok := singleID(hasRest, rest)
			if !ok {
				reject(opName)
				continue
			}
			it, exists := items[id]
			if !exists {
				reject(opName)
				continue
			}
			status := "open"
			if it.done {
				status = "done"
			}
			fmt.Fprintf(out, "todo %d %s %s\n", id, status, it.text)

		case "list":
			if hasRest {
				reject(opName)
				continue
			}
			ids := make([]int, 0)
			for id, it := range items {
				if !it.done {
					ids = append(ids, id)
				}
			}
			sort.Ints(ids)
			fmt.Fprintf(out, "list %d\n", len(ids))
			for _, id := range ids {
				fmt.Fprintf(out, "todo %d open %s\n", id, items[id].text)
			}

		case "stats":
			if hasRest {
				reject(opName)
				continue
			}
			total, open, done, chars := 0, 0, 0, 0
			for _, it := range items {
				total++
				if it.done {
					done++
				} else {
					open++
				}
				chars += utf8.RuneCountInString(it.text)
			}
			fmt.Fprintf(out, "stats total %d open %d done %d chars %d errors %d\n",
				total, open, done, chars, errorCount)

		default:
			reject(opName)
		}
	}
}
