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
	index := map[string]int{}
	for i, l := range levels {
		index[l] = i
	}

	counts := make([]int, len(levels))
	chars := make([]int, len(levels))
	longest := make([]int, len(levels))
	good := 0
	bad := 0

	for _, line := range strings.Split(string(data), "\n") {
		line = strings.TrimSuffix(line, "\r")
		if line == "" {
			continue
		}
		if line[0] != '[' {
			bad++
			continue
		}
		idx := strings.IndexByte(line, ']')
		if idx < 0 {
			bad++
			continue
		}
		level := line[1:idx]
		li, ok := index[level]
		if !ok {
			bad++
			continue
		}
		rest := line[idx+1:]
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
		counts[li]++
		chars[li] += n
		if n > longest[li] {
			longest[li] = n
		}
	}

	w := bufio.NewWriter(os.Stdout)
	defer w.Flush()
	fmt.Fprintf(w, "lines %d bad %d\n", good, bad)
	for i, l := range levels {
		fmt.Fprintf(w, "level %s count %d chars %d longest %d\n", l, counts[i], chars[i], longest[i])
	}
}
