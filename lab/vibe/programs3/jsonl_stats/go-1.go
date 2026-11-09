package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"sort"
	"strings"
)

type tagStat struct {
	count int
	total int64
}

type userStat struct {
	name  string
	count int
}

func blank(s string) bool {
	for i := 0; i < len(s); i++ {
		if s[i] != ' ' && s[i] != '\t' {
			return false
		}
	}
	return true
}

func main() {
	data, _ := io.ReadAll(os.Stdin)
	lines := strings.Split(string(data), "\n")

	bad := 0
	tags := make(map[string]*tagStat)
	users := make(map[string]int)

	for _, line := range lines {
		if len(line) > 0 && line[len(line)-1] == '\r' {
			line = line[:len(line)-1]
		}
		if blank(line) {
			continue
		}

		var obj map[string]json.RawMessage
		if err := json.Unmarshal([]byte(line), &obj); err != nil || obj == nil {
			bad++
			continue
		}

		userRaw, ok := obj["user"]
		if !ok {
			bad++
			continue
		}
		var userPtr *string
		if err := json.Unmarshal(userRaw, &userPtr); err != nil || userPtr == nil {
			bad++
			continue
		}

		amountRaw, ok := obj["amount"]
		if !ok {
			bad++
			continue
		}
		var amountPtr *int64
		if err := json.Unmarshal(amountRaw, &amountPtr); err != nil || amountPtr == nil {
			bad++
			continue
		}

		tag := ""
		if tagRaw, ok := obj["tag"]; ok {
			var tagPtr *string
			if err := json.Unmarshal(tagRaw, &tagPtr); err != nil || tagPtr == nil {
				bad++
				continue
			}
			tag = *tagPtr
		}

		user := *userPtr
		amount := *amountPtr

		st := tags[tag]
		if st == nil {
			st = &tagStat{}
			tags[tag] = st
		}
		st.count++
		st.total += amount
		users[user]++
	}

	tagNames := make([]string, 0, len(tags))
	for tag := range tags {
		tagNames = append(tagNames, tag)
	}
	sort.Strings(tagNames)

	userStats := make([]userStat, 0, len(users))
	for name, count := range users {
		userStats = append(userStats, userStat{name: name, count: count})
	}
	sort.Slice(userStats, func(i, j int) bool {
		if userStats[i].count != userStats[j].count {
			return userStats[i].count > userStats[j].count
		}
		return userStats[i].name < userStats[j].name
	})

	w := bufio.NewWriter(os.Stdout)
	defer w.Flush()

	fmt.Fprintf(w, "bad %d tags %d users %d\n", bad, len(tags), len(users))
	for _, tag := range tagNames {
		st := tags[tag]
		fmt.Fprintf(w, "tag %s count %d total %d\n", tag, st.count, st.total)
	}

	limit := len(userStats)
	if limit > 10 {
		limit = 10
	}
	for i := 0; i < limit; i++ {
		fmt.Fprintf(w, "user %s %d\n", userStats[i].name, userStats[i].count)
	}
}
