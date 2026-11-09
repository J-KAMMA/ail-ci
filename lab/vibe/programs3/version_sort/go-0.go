package main

import (
	"bufio"
	"fmt"
	"io"
	"os"
	"sort"
	"strconv"
	"strings"
)

type identifier struct {
	numeric bool
	number  int64
	text    string
}

type version struct {
	line       string
	major      int64
	minor      int64
	patch      int64
	hasPre     bool
	prerelease []identifier
}

func isDigit(c byte) bool {
	return c >= '0' && c <= '9'
}

func isIdentifierChar(c byte) bool {
	return isDigit(c) ||
		(c >= 'A' && c <= 'Z') ||
		(c >= 'a' && c <= 'z') ||
		c == '-'
}

func parseNumber(s string) (int64, bool) {
	for i := 0; i < len(s); i++ {
		if !isDigit(s[i]) {
			return 0, false
		}
	}

	n, err := strconv.ParseInt(s, 10, 64)
	if err != nil {
		return 0, false
	}
	return n, true
}

func parseIdentifiers(s string) ([]identifier, bool) {
	if s == "" {
		return nil, false
	}

	parts := strings.Split(s, ".")
	ids := make([]identifier, 0, len(parts))

	for _, part := range parts {
		if part == "" {
			return nil, false
		}

		numeric := true
		for i := 0; i < len(part); i++ {
			c := part[i]
			if !isIdentifierChar(c) {
				return nil, false
			}
			if !isDigit(c) {
				numeric = false
			}
		}

		id := identifier{
			numeric: numeric,
			text:    part,
		}

		if numeric {
			n, ok := parseNumber(part)
			if !ok {
				return nil, false
			}
			id.number = n
		}

		ids = append(ids, id)
	}

	return ids, true
}

func parseVersion(s string) (version, bool) {
	var v version
	v.line = s

	i := 0

	start := i
	for i < len(s) && isDigit(s[i]) {
		i++
	}
	if i == start || i >= len(s) || s[i] != '.' {
		return v, false
	}
	n, ok := parseNumber(s[start:i])
	if !ok {
		return v, false
	}
	v.major = n
	i++

	start = i
	for i < len(s) && isDigit(s[i]) {
		i++
	}
	if i == start || i >= len(s) || s[i] != '.' {
		return v, false
	}
	n, ok = parseNumber(s[start:i])
	if !ok {
		return v, false
	}
	v.minor = n
	i++

	start = i
	for i < len(s) && isDigit(s[i]) {
		i++
	}
	if i == start {
		return v, false
	}
	n, ok = parseNumber(s[start:i])
	if !ok {
		return v, false
	}
	v.patch = n

	if i == len(s) {
		return v, true
	}

	switch s[i] {
	case '-':
		i++
		preStart := i
		for i < len(s) && s[i] != '+' {
			i++
		}

		pre, ok := parseIdentifiers(s[preStart:i])
		if !ok {
			return v, false
		}
		v.hasPre = true
		v.prerelease = pre

		if i < len(s) {
			i++
			if _, ok := parseIdentifiers(s[i:]); !ok {
				return v, false
			}
		}

	case '+':
		i++
		if _, ok := parseIdentifiers(s[i:]); !ok {
			return v, false
		}

	default:
		return v, false
	}

	return v, true
}

func lessVersion(a, b version) bool {
	if a.major != b.major {
		return a.major < b.major
	}
	if a.minor != b.minor {
		return a.minor < b.minor
	}
	if a.patch != b.patch {
		return a.patch < b.patch
	}

	if a.hasPre != b.hasPre {
		return a.hasPre
	}

	if a.hasPre {
		limit := len(a.prerelease)
		if len(b.prerelease) < limit {
			limit = len(b.prerelease)
		}

		for i := 0; i < limit; i++ {
			x := a.prerelease[i]
			y := b.prerelease[i]

			if x.numeric && y.numeric {
				if x.number != y.number {
					return x.number < y.number
				}
			} else if x.numeric != y.numeric {
				return x.numeric
			} else {
				if x.text != y.text {
					return x.text < y.text
				}
			}
		}

		if len(a.prerelease) != len(b.prerelease) {
			return len(a.prerelease) < len(b.prerelease)
		}
	}

	return a.line < b.line
}

func main() {
	data, _ := io.ReadAll(os.Stdin)

	lines := strings.Split(string(data), "\n")
	versions := make([]version, 0, len(lines))
	bad := 0

	for _, line := range lines {
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

		versions = append(versions, v)
	}

	sort.Slice(versions, func(i, j int) bool {
		return lessVersion(versions[i], versions[j])
	})

	w := bufio.NewWriter(os.Stdout)

	fmt.Fprintf(w, "bad %d sorted %d\n", bad, len(versions))

	for _, v := range versions {
		w.WriteString(v.line)
		w.WriteByte('\n')
	}

	w.Flush()
}
