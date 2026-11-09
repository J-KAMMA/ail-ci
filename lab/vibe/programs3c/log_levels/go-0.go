package main

import (
	"bufio"
	"fmt"
	"io"
	"os"
	"strings"
	"unicode/utf8"
)

func main() {
	data, _ := io.ReadAll(os.Stdin)

	levels := []string{"TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL"}
	idx := make(map[string]int, len(levels))
	for i, l := range levels {
		idx[l] = i
	}

	count := make([]int, len(levels))
	chars := make([]int, len(levels))
	longest := make([]int, len(levels))
	good, bad := 0, 0

	for _, line := range strings.Split(string(data), "\n") {
		line = strings.TrimSuffix(line, "\r")
		if line == "" {
			continue
		}
		if line[0] != '[' {
			bad++
			continue
		}
		end := strings.IndexByte(line, ']')
		if end < 0 {
			bad++
			continue
		}
		i, ok := idx[line[1:end]]
		if !ok {
			bad++
			continue
		}
		rest := line[end+1:]
		msg := ""
		if rest != "" {
			if rest[0] != ' ' {
				bad++
				continue
			}
			msg = rest[1:]
		}
		n := utf8.RuneCountInString(msg)
		good++
		count[i]++
		chars[i] += n
		if n > longest[i] {
			longest[i] = n
		}
	}

	w := bufio.NewWriter(os.Stdout)
	defer w.Flush()
	fmt.Fprintf(w, "lines %d bad %d\n", good, bad)
	for i, l := range levels {
		fmt.Fprintf(w, "level %s count %d chars %d longest %d\n", l, count[i], chars[i], longest[i])
	}
}
