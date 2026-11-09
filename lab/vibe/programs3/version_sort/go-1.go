package main

import (
	"bytes"
	"fmt"
	"io"
	"os"
	"sort"
	"strings"
)

const maxInt64 int64 = 9223372036854775807

type identifier struct {
	numeric bool
	num     int64
	text    string
}

type version struct {
	line   string
	core   [3]int64
	pre    []identifier
	hasPre bool
}

func isDigit(c byte) bool {
	return c >= '0' && c <= '9'
}

func isIdentChar(c byte) bool {
	return isDigit(c) ||
		(c >= 'a' && c <= 'z') ||
		(c >= 'A' && c <= 'Z') ||
		c == '-'
}

func parseNumber(s string, pos *int) (int64, bool) {
	start := *pos
	var n int64

	for *pos < len(s) && isDigit(s[*pos]) {
		d := int64(s[*pos] - '0')
		if n > (maxInt64-d)/10 {
			return 0, false
		}
		n = n*10 + d
		*pos = *pos + 1
	}

	if *pos == start {
		return 0, false
	}
	return n, true
}

func parseIdentifiers(s string, pos *int) ([]identifier, bool) {
	var ids []identifier

	for {
		start := *pos
		for *pos < len(s) && isIdentChar(s[*pos]) {
			*pos = *pos + 1
		}

		if *pos == start {
			return nil, false
		}

		text := s[start:*pos]
		id := identifier{text: text}
		numeric := true
		var n int64

		for j := 0; j < len(text); j++ {
			c := text[j]
			if !isDigit(c) {
				numeric = false
				break
			}

			d := int64(c - '0')
			if n > (maxInt64-d)/10 {
				return nil, false
			}
			n = n*10 + d
		}

		id.numeric = numeric
		if numeric {
			id.num = n
		}

		ids = append(ids, id)

		if *pos < len(s) && s[*pos] == '.' {
			*pos = *pos + 1
			continue
		}
		break
	}

	return ids, true
}

func parseVersion(s string) (version, bool) {
	var v version
	pos := 0

	for i := 0; i < 3; i++ {
		n, ok := parseNumber(s, &pos)
		if !ok {
			return version{}, false
		}
		v.core[i] = n

		if i < 2 {
			if pos >= len(s) || s[pos] != '.' {
				return version{}, false
			}
			pos++
		}
	}

	if pos < len(s) && s[pos] == '-' {
		pos++
		ids, ok := parseIdentifiers(s, &pos)
		if !ok {
			return version{}, false
		}
		v.pre = ids
		v.hasPre = true
	}

	if pos < len(s) && s[pos] == '+' {
		pos++
		if _, ok := parseIdentifiers(s, &pos); !ok {
			return version{}, false
		}
	}

	if pos != len(s) {
		return version{}, false
	}

	return v, true
}

func compareVersion(a, b version) int {
	for i := 0; i < 3; i++ {
		if a.core[i] < b.core[i] {
			return -1
		}
		if a.core[i] > b.core[i] {
			return 1
		}
	}

	if a.hasPre != b.hasPre {
		if !a.hasPre {
			return 1
		}
		return -1
	}

	if !a.hasPre {
		return 0
	}

	n := len(a.pre)
	if len(b.pre) < n {
		n = len(b.pre)
	}

	for i := 0; i < n; i++ {
		x := a.pre[i]
		y := b.pre[i]

		if x.numeric && y.numeric {
			if x.num < y.num {
				return -1
			}
			if x.num > y.num {
				return 1
			}
			continue
		}

		if x.numeric {
			return -1
		}
		if y.numeric {
			return 1
		}

		if x.text < y.text {
			return -1
		}
		if x.text > y.text {
			return 1
		}
	}

	if len(a.pre) < len(b.pre) {
		return -1
	}
	if len(a.pre) > len(b.pre) {
		return 1
	}

	return 0
}

func main() {
	data, _ := io.ReadAll(os.Stdin)
	lines := strings.Split(string(data), "\n")

	accepted := make([]version, 0)
	bad := 0

	for _, raw := range lines {
		line := raw
		if strings.HasSuffix(line, "\r") {
			line = line[:len(line)-1]
		}

		if line == "" {
			continue
		}

		v, ok := parseVersion(line)
		if !ok {
			bad++
			continue
		}

		v.line = line
		accepted = append(accepted, v)
	}

	sort.Slice(accepted, func(i, j int) bool {
		c := compareVersion(accepted[i], accepted[j])
		if c != 0 {
			return c < 0
		}
		return accepted[i].line < accepted[j].line
	})

	var out bytes.Buffer
	fmt.Fprintf(&out, "bad %d sorted %d\n", bad, len(accepted))
	for _, v := range accepted {
		out.WriteString(v.line)
		out.WriteByte('\n')
	}

	_, _ = os.Stdout.Write(out.Bytes())
}
