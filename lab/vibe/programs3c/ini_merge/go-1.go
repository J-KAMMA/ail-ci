package main

import (
	"bufio"
	"io"
	"os"
	"sort"
	"strings"
)

func main() {
	data, _ := io.ReadAll(os.Stdin)
	w := bufio.NewWriter(os.Stdout)
	defer w.Flush()

	sections := make(map[string]map[string]string)
	current := ""
	bad := 0

	lines := strings.Split(string(data), "\n")
	for _, line := range lines {
		line = strings.TrimSuffix(line, "\r")
		line = strings.Trim(line, " \t")

		if line == "" {
			continue
		}
		if line[0] == '#' || line[0] == ';' {
			continue
		}
		if line[0] == '[' {
			if len(line) >= 2 && line[len(line)-1] == ']' {
				name := line[1 : len(line)-1]
				current = name
				if _, ok := sections[name]; !ok {
					sections[name] = make(map[string]string)
				}
			} else {
				bad++
			}
			continue
		}

		idx := strings.Index(line, "=")
		if idx < 0 {
			bad++
			continue
		}
		key := strings.Trim(line[:idx], " \t")
		value := strings.Trim(line[idx+1:], " \t")
		if key == "" || strings.ContainsAny(key, " \t") {
			bad++
			continue
		}
		sec, ok := sections[current]
		if !ok {
			sec = make(map[string]string)
			sections[current] = sec
		}
		sec[key] = value
	}

	w.WriteString("bad ")
	w.WriteString(itoa(bad))
	w.WriteString("\n")

	names := make([]string, 0, len(sections))
	for name := range sections {
		names = append(names, name)
	}
	sort.Strings(names)

	for _, name := range names {
		w.WriteString("[")
		w.WriteString(name)
		w.WriteString("]\n")

		sec := sections[name]
		keys := make([]string, 0, len(sec))
		for k := range sec {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		for _, k := range keys {
			w.WriteString(k)
			w.WriteString("=")
			w.WriteString(sec[k])
			w.WriteString("\n")
		}
	}
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	neg := n < 0
	if neg {
		n = -n
	}
	var buf [20]byte
	i := len(buf)
	for n > 0 {
		i--
		buf[i] = byte('0' + n%10)
		n /= 10
	}
	if neg {
		i--
		buf[i] = '-'
	}
	return string(buf[i:])
}
