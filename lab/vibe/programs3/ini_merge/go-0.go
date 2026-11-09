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
	lines := strings.Split(string(data), "\n")

	sections := make(map[string]map[string]string)
	current := ""
	bad := 0

	ensure := func(name string) map[string]string {
		m, ok := sections[name]
		if !ok {
			m = make(map[string]string)
			sections[name] = m
		}
		return m
	}

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
			if strings.HasSuffix(line, "]") && len(line) >= 2 {
				current = line[1 : len(line)-1]
				ensure(current)
			} else {
				bad++
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
		ensure(current)[key] = value
	}

	out := bufio.NewWriter(os.Stdout)
	defer out.Flush()

	fmt.Fprintf(out, "bad %d\n", bad)

	names := make([]string, 0, len(sections))
	for name := range sections {
		names = append(names, name)
	}
	sort.Strings(names)

	for _, name := range names {
		fmt.Fprintf(out, "[%s]\n", name)
		m := sections[name]
		keys := make([]string, 0, len(m))
		for k := range m {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		for _, k := range keys {
			fmt.Fprintf(out, "%s=%s\n", k, m[k])
		}
	}
}
