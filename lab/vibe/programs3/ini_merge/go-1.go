package main

import (
	"bufio"
	"fmt"
	"io"
	"os"
	"sort"
	"strings"
)

func main() {
	data, _ := io.ReadAll(os.Stdin)
	text := string(data)

	sections := make(map[string]map[string]string)
	current := ""

	bad := 0

	lines := strings.Split(text, "\n")
	for _, raw := range lines {
		line := strings.TrimSuffix(raw, "\r")
		line = strings.Trim(line, " \t")

		if line == "" {
			continue
		}
		if line[0] == '#' || line[0] == ';' {
			continue
		}
		if line[0] == '[' {
			if !strings.HasSuffix(line, "]") {
				bad++
				continue
			}
			name := line[1 : len(line)-1]
			current = name
			if _, ok := sections[name]; !ok {
				sections[name] = make(map[string]string)
			}
			continue
		}

		eq := strings.IndexByte(line, '=')
		if eq < 0 {
			bad++
			continue
		}
		key := strings.Trim(line[:eq], " \t")
		value := strings.Trim(line[eq+1:], " \t")
		if key == "" || strings.ContainsAny(key, " \t") {
			bad++
			continue
		}
		if _, ok := sections[current]; !ok {
			sections[current] = make(map[string]string)
		}
		sections[current][key] = value
	}

	w := bufio.NewWriter(os.Stdout)
	defer w.Flush()

	fmt.Fprintf(w, "bad %d\n", bad)

	names := make([]string, 0, len(sections))
	for name := range sections {
		names = append(names, name)
	}
	sort.Strings(names)

	for _, name := range names {
		fmt.Fprintf(w, "[%s]\n", name)
		keys := make([]string, 0, len(sections[name]))
		for k := range sections[name] {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		for _, k := range keys {
			fmt.Fprintf(w, "%s=%s\n", k, sections[name][k])
		}
	}
}
