package main

import (
	"bufio"
	"fmt"
	"io"
	"os"
	"strings"
	"unicode/utf8"
)

var levelOrder = []string{"TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL"}

func main() {
	data, _ := io.ReadAll(os.Stdin)
	lines := strings.Split(string(data), "\n")

	index := make(map[string]int, len(levelOrder))
	for i, l := range levelOrder {
		index[l] = i
	}

	counts := make([]int, len(levelOrder))
	chars := make([]int, len(levelOrder))
	longest := make([]int, len(levelOrder))
	good, bad := 0, 0

	for _, line := range lines {
		line = strings.TrimSuffix(line, "\r")
		if line == "" {
			continue
		}
		lvl, msg, ok := parseLine(line)
		if !ok {
			bad++
			continue
		}
		good++
		i := index[lvl]
		counts[i]++
		n := utf8.RuneCountInString(msg)
		chars[i] += n
		if n > longest[i] {
			longest[i] = n
		}
	}

	out := bufio.NewWriter(os.Stdout)
	defer out.Flush()

	fmt.Fprintf(out, "lines %d bad %d\n", good, bad)
	for i, l := range levelOrder {
		fmt.Fprintf(out, "level %s count %d chars %d longest %d\n",
			l, counts[i], chars[i], longest[i])
	}
}

func parseLine(line string) (level string, message string, ok bool) {
	if line[0] != '[' {
		return "", "", false
	}
	end := strings.IndexByte(line, ']')
	if end < 0 {
		return "", "", false
	}
	candidate := line[1:end]
	if !isLevel(candidate) {
		return "", "", false
	}
	rest := line[end+1:]
	if rest == "" {
		return candidate, "", true
	}
	if rest[0] != ' ' {
		return "", "", false
	}
	return candidate, rest[1:], true
}

func isLevel(s string) bool {
	for _, l := range levelOrder {
		if l == s {
			return true
		}
	}
	return false
}
