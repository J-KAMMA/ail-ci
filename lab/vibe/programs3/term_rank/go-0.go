package main

import (
	"bufio"
	"bytes"
	"io"
	"os"
	"sort"
	"strconv"
)

var stopWords = map[string]struct{}{
	"an": {}, "and": {}, "are": {}, "as": {}, "at": {}, "be": {}, "but": {},
	"by": {}, "for": {}, "from": {}, "had": {}, "has": {}, "have": {}, "he": {},
	"her": {}, "his": {}, "in": {}, "into": {}, "is": {}, "it": {}, "its": {},
	"not": {}, "of": {}, "on": {}, "or": {}, "our": {}, "she": {}, "so": {},
	"than": {}, "that": {}, "the": {}, "their": {}, "them": {}, "then": {},
	"there": {}, "these": {}, "they": {}, "this": {}, "to": {}, "was": {},
	"we": {}, "were": {}, "which": {}, "will": {}, "with": {}, "you": {},
	"your": {},
}

func isWordByte(b byte) bool {
	return (b >= 'A' && b <= 'Z') || (b >= 'a' && b <= 'z') ||
		(b >= '0' && b <= '9') || b >= 0x80
}

func processToken(raw []byte) (string, bool) {
	t := make([]byte, 0, len(raw))
	for _, b := range raw {
		if b != '\'' {
			t = append(t, b)
		}
	}
	for i := range t {
		if t[i] >= 'A' && t[i] <= 'Z' {
			t[i] += 'a' - 'A'
		}
	}
	if len(t) > 0 {
		allDigits := true
		for _, b := range t {
			if b < '0' || b > '9' {
				allDigits = false
				break
			}
		}
		if allDigits {
			t = []byte("#" + strconv.Itoa(len(t)))
		}
	}
	if len(t) < 2 {
		return "", false
	}
	if _, ok := stopWords[string(t)]; ok {
		return "", false
	}
	if len(t) >= 5 && t[len(t)-1] == 'g' && t[len(t)-2] == 'n' && t[len(t)-3] == 'i' {
		t = t[:len(t)-3]
	} else if len(t) >= 4 && t[len(t)-1] == 's' && t[len(t)-2] != 's' {
		t = t[:len(t)-1]
	}
	return string(t), true
}

func tokenizeLine(line []byte, tf map[string]int) {
	n := len(line)
	i := 0
	for i < n {
		if !isWordByte(line[i]) {
			i++
			continue
		}
		start := i
		i++
		for i < n {
			b := line[i]
			if isWordByte(b) {
				i++
			} else if (b == '\'' || b == '-') && i+1 < n && isWordByte(line[i+1]) {
				i++
			} else {
				break
			}
		}
		if term, ok := processToken(line[start:i]); ok {
			tf[term]++
		}
	}
}

func parseK(s string) (int, bool) {
	if len(s) == 0 {
		return 0, false
	}
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return 0, false
		}
	}
	i := 0
	for i < len(s)-1 && s[i] == '0' {
		i++
	}
	t := s[i:]
	if t == "0" || len(t) > 4 {
		return 0, false
	}
	v := 0
	for j := 0; j < len(t); j++ {
		v = v*10 + int(t[j]-'0')
	}
	if v < 1 || v > 1000 {
		return 0, false
	}
	return v, true
}

type termScore struct {
	term  string
	score int64
}

func main() {
	if len(os.Args) != 2 {
		os.Exit(1)
	}
	k, ok := parseK(os.Args[1])
	if !ok {
		os.Exit(1)
	}

	data, err := io.ReadAll(os.Stdin)
	if err != nil {
		os.Exit(1)
	}

	var lines [][]byte
	if len(data) > 0 {
		if data[len(data)-1] == '\n' {
			data = data[:len(data)-1]
		}
		lines = bytes.Split(data, []byte{'\n'})
	}

	docs := []map[string]int{make(map[string]int)}
	sep := []byte("%%")
	sepCR := []byte("%%\r")
	for _, line := range lines {
		if bytes.Equal(line, sep) || bytes.Equal(line, sepCR) {
			docs = append(docs, make(map[string]int))
			continue
		}
		tokenizeLine(line, docs[len(docs)-1])
	}

	n := int64(len(docs))
	n1 := n + 1

	df := make(map[string]int64)
	totals := make(map[string]int64)
	for _, d := range docs {
		for t, c := range d {
			df[t]++
			totals[t] += int64(c)
		}
	}

	w := bufio.NewWriterSize(os.Stdout, 1<<16)
	defer w.Flush()
	buf := make([]byte, 0, 256)

	for idx, d := range docs {
		ents := make([]termScore, 0, len(d))
		for t, c := range d {
			tfv := int64(c)
			sc := tfv * 1000 * n1 / (df[t] * (tfv + 2))
			ents = append(ents, termScore{t, sc})
		}
		sort.Slice(ents, func(i, j int) bool {
			if ents[i].score != ents[j].score {
				return ents[i].score > ents[j].score
			}
			return ents[i].term < ents[j].term
		})
		lim := k
		if lim > len(ents) {
			lim = len(ents)
		}
		buf = buf[:0]
		buf = append(buf, "doc "...)
		buf = strconv.AppendInt(buf, int64(idx+1), 10)
		buf = append(buf, ':')
		for j := 0; j < lim; j++ {
			buf = append(buf, ' ')
			buf = append(buf, ents[j].term...)
			buf = append(buf, '=')
			buf = strconv.AppendInt(buf, ents[j].score, 10)
		}
		buf = append(buf, '\n')
		w.Write(buf)
	}

	ents := make([]termScore, 0, len(totals))
	for t, c := range totals {
		ents = append(ents, termScore{t, c})
	}
	sort.Slice(ents, func(i, j int) bool {
		if ents[i].score != ents[j].score {
			return ents[i].score > ents[j].score
		}
		return ents[i].term < ents[j].term
	})
	lim := k
	if lim > len(ents) {
		lim = len(ents)
	}
	buf = buf[:0]
	buf = append(buf, "all:"...)
	for j := 0; j < lim; j++ {
		buf = append(buf, ' ')
		buf = append(buf, ents[j].term...)
		buf = append(buf, '=')
		buf = strconv.AppendInt(buf, ents[j].score, 10)
	}
	buf = append(buf, '\n')
	w.Write(buf)
}
