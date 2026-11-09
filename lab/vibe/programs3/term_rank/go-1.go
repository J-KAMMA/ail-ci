package main

import (
	"bytes"
	"io"
	"os"
	"sort"
	"strconv"
)

var stopWords = map[string]bool{
	"an": true, "and": true, "are": true, "as": true, "at": true,
	"be": true, "but": true, "by": true, "for": true, "from": true,
	"had": true, "has": true, "have": true, "he": true, "her": true, "his": true,
	"in": true, "into": true, "is": true, "it": true, "its": true,
	"not": true, "of": true, "on": true, "or": true, "our": true,
	"she": true, "so": true, "than": true, "that": true, "the": true,
	"their": true, "them": true, "then": true, "there": true, "these": true,
	"they": true, "this": true, "to": true, "was": true, "we": true,
	"were": true, "which": true, "will": true, "with": true, "you": true, "your": true,
}

type scoredTerm struct {
	term  string
	score int64
}

type countedTerm struct {
	term  string
	count int
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

	docs := splitDocuments(data)
	printResults(docs, k)
}

func parseK(s string) (int, bool) {
	if len(s) == 0 {
		return 0, false
	}

	v := 0
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return 0, false
		}
		v = v*10 + int(s[i]-'0')
		if v > 1000 {
			return 0, false
		}
	}

	if v < 1 {
		return 0, false
	}
	return v, true
}

func splitDocuments(data []byte) []map[string]int {
	if len(data) == 0 {
		return []map[string]int{make(map[string]int)}
	}

	parts := bytes.Split(data, []byte{'\n'})
	if data[len(data)-1] == '\n' {
		parts = parts[:len(parts)-1]
	}

	docs := make([]map[string]int, 0, len(parts)+1)
	cur := make(map[string]int)

	for _, line := range parts {
		if isSeparator(line) {
			docs = append(docs, cur)
			cur = make(map[string]int)
		} else {
			addLineTerms(line, cur)
		}
	}

	docs = append(docs, cur)
	return docs
}

func isSeparator(line []byte) bool {
	return bytes.Equal(line, []byte("%%")) || bytes.Equal(line, []byte("%%\r"))
}

func addLineTerms(line []byte, counts map[string]int) {
	i := 0
	for i < len(line) {
		if !isWordByte(line[i]) {
			i++
			continue
		}

		start := i
		i++

		for i < len(line) {
			if isWordByte(line[i]) {
				i++
				continue
			}
			if isJoiner(line[i]) && i+1 < len(line) && isWordByte(line[i+1]) {
				i++
				continue
			}
			break
		}

		if term, ok := makeTerm(line[start:i]); ok {
			counts[term]++
		}
	}
}

func isWordByte(b byte) bool {
	return (b >= 'A' && b <= 'Z') ||
		(b >= 'a' && b <= 'z') ||
		(b >= '0' && b <= '9') ||
		b >= 0x80
}

func isJoiner(b byte) bool {
	return b == '\'' || b == '-'
}

func makeTerm(raw []byte) (string, bool) {
	tok := make([]byte, 0, len(raw))

	for _, b := range raw {
		if b == '\'' {
			continue
		}
		if b >= 'A' && b <= 'Z' {
			b += 'a' - 'A'
		}
		tok = append(tok, b)
	}

	if len(tok) > 0 {
		allDigits := true
		for _, b := range tok {
			if b < '0' || b > '9' {
				allDigits = false
				break
			}
		}
		if allDigits {
			return "#" + strconv.Itoa(len(tok)), true
		}
	}

	if len(tok) < 2 {
		return "", false
	}

	s := string(tok)
	if stopWords[s] {
		return "", false
	}

	if len(tok) >= 5 &&
		tok[len(tok)-3] == 'i' &&
		tok[len(tok)-2] == 'n' &&
		tok[len(tok)-1] == 'g' {
		tok = tok[:len(tok)-3]
	} else if len(tok) >= 4 && tok[len(tok)-1] == 's' && tok[len(tok)-2] != 's' {
		tok = tok[:len(tok)-1]
	}

	return string(tok), true
}

func printResults(docs []map[string]int, k int) {
	n := len(docs)

	df := make(map[string]int)
	total := make(map[string]int)

	for _, doc := range docs {
		for term, tf := range doc {
			df[term]++
			total[term] += tf
		}
	}

	var buf bytes.Buffer

	for i, doc := range docs {
		items := make([]scoredTerm, 0, len(doc))

		for term, tf := range doc {
			numerator := int64(tf) * 1000 * (int64(n) + 1)
			denominator := int64(df[term]) * (int64(tf) + 2)
			score := numerator / denominator
			items = append(items, scoredTerm{term: term, score: score})
		}

		sort.Slice(items, func(a, b int) bool {
			if items[a].score != items[b].score {
				return items[a].score > items[b].score
			}
			return items[a].term < items[b].term
		})

		if len(items) > k {
			items = items[:k]
		}

		buf.WriteString("doc ")
		buf.WriteString(strconv.Itoa(i + 1))
		buf.WriteByte(':')

		if len(items) > 0 {
			buf.WriteByte(' ')
			for j, item := range items {
				if j > 0 {
					buf.WriteByte(' ')
				}
				buf.WriteString(item.term)
				buf.WriteByte('=')
				buf.WriteString(strconv.FormatInt(item.score, 10))
			}
		}

		buf.WriteByte('\n')
	}

	all := make([]countedTerm, 0, len(total))
	for term, count := range total {
		all = append(all, countedTerm{term: term, count: count})
	}

	sort.Slice(all, func(a, b int) bool {
		if all[a].count != all[b].count {
			return all[a].count > all[b].count
		}
		return all[a].term < all[b].term
	})

	if len(all) > k {
		all = all[:k]
	}

	buf.WriteString("all:")

	if len(all) > 0 {
		buf.WriteByte(' ')
		for j, item := range all {
			if j > 0 {
				buf.WriteByte(' ')
			}
			buf.WriteString(item.term)
			buf.WriteByte('=')
			buf.WriteString(strconv.Itoa(item.count))
		}
	}

	buf.WriteByte('\n')
	os.Stdout.Write(buf.Bytes())
}
