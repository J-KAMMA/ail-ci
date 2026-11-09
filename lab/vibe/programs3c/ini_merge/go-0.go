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

	sections := map[string]map[string]string{}
	ensure := func(name string) {
		if _, ok := sections[name]; !ok {
			sections[name] = map[string]string{}
		}
	}

	bad := 0
	cur := ""

	for _, raw := range lines {
		line := strings.TrimSuffix(raw, "\r")
		line = strings.Trim(line, " \t")
		if line == "" {
			continue
		}
		c := line[0]
		if c == '#' || c == ';' {
			continue
		}
		if c == '[' {
			if line[len(line)-1] != ']' {
				bad++
				continue
			}
			cur = line[1 : len(line)-1]
			ensure(cur)
			continue
		}
		idx := strings.IndexByte(line, '=')
		if idx < 0 {
			bad++
			continue
		}
		key := strings.Trim(line[:idx], " \t")
		val := strings.Trim(line[idx+1:], " \t")
		if key == "" || strings.ContainsAny(key, " \t") {
			bad++
			continue
		}
		ensure(cur)
		sections[cur][key] = val
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
		kv := sections[name]
		keys := make([]string, 0, len(kv))
		for k := range kv {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		for _, k := range keys {
			fmt.Fprintf(w, "%s=%s\n", k, kv[k])
		}
	}
}
