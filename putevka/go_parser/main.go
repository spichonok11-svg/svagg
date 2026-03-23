package main

import (
	"encoding/json"
	"log"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"slices"
	"strconv"
	"strings"
	"sync"
	"time"
)

type Tour struct {
	ID             string   `json:"id"`
	Title          string   `json:"title"`
	Region         string   `json:"region"`
	Country        string   `json:"country"`
	PricePerPerson int      `json:"pricePerPerson"`
	Days           int      `json:"days"`
	Categories     []string `json:"categories"`
	Description    string   `json:"description"`
	Link           string   `json:"link"`
}

type ParserResponse struct {
	Count    int    `json:"count"`
	Tours    []Tour `json:"tours"`
	ParsedAt string `json:"parsedAt"`
}

type HealthResponse struct {
	OK       bool   `json:"ok"`
	Tours    int    `json:"toursInCache"`
	ParsedAt string `json:"parsedAt"`
}

var (
	cacheLock sync.RWMutex
	cacheTours []Tour
	parsedAt  time.Time
)

func main() {
	if err := refreshData(); err != nil {
		log.Printf("initial refresh failed: %v", err)
	}

	go func() {
		ticker := time.NewTicker(5 * time.Minute)
		defer ticker.Stop()
		for range ticker.C {
			if err := refreshData(); err != nil {
				log.Printf("background refresh failed: %v", err)
			}
		}
	}()

	http.HandleFunc("/health", healthHandler)
	http.HandleFunc("/parse", parseHandler)
	http.HandleFunc("/refresh", refreshHandler)

	port := getenvDefault("GO_PARSER_PORT", "8090")
	log.Printf("go parser listening on :%s", port)
	log.Fatal(http.ListenAndServe(":"+port, nil))
}

func getenvDefault(key, fallback string) string {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback
	}
	return value
}

func dataFilePath() string {
	configured := strings.TrimSpace(os.Getenv("DATA_FILE"))
	if configured != "" {
		return configured
	}
	return filepath.Join("..", "data", "offers.json")
}

func refreshData() error {
	fileData, err := os.ReadFile(dataFilePath())
	if err != nil {
		return err
	}

	var records []Tour
	if err := json.Unmarshal(fileData, &records); err != nil {
		return err
	}

	filtered := make([]Tour, 0, len(records))
	for _, tour := range records {
		if tour.PricePerPerson <= 0 {
			continue
		}
		if !strings.Contains(strings.ToLower(tour.Country), "росс") {
			continue
		}
		if len(tour.Categories) == 0 {
			continue
		}
		filtered = append(filtered, tour)
	}

	slices.SortFunc(filtered, func(a, b Tour) int {
		return a.PricePerPerson - b.PricePerPerson
	})

	cacheLock.Lock()
	cacheTours = filtered
	parsedAt = time.Now().UTC()
	cacheLock.Unlock()
	return nil
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	cacheLock.RLock()
	payload := HealthResponse{
		OK:       true,
		Tours:    len(cacheTours),
		ParsedAt: parsedAt.Format(time.RFC3339),
	}
	cacheLock.RUnlock()

	writeJSON(w, payload)
}

func parseHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	cacheLock.RLock()
	tours := filterTours(cacheTours, r.URL.Query())
	ts := parsedAt
	cacheLock.RUnlock()

	writeJSON(w, ParserResponse{
		Count:    len(tours),
		Tours:    tours,
		ParsedAt: ts.Format(time.RFC3339),
	})
}

func refreshHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	if err := refreshData(); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	cacheLock.RLock()
	payload := ParserResponse{
		Count:    len(cacheTours),
		Tours:    cacheTours,
		ParsedAt: parsedAt.Format(time.RFC3339),
	}
	cacheLock.RUnlock()
	writeJSON(w, payload)
}

func filterTours(tours []Tour, query url.Values) []Tour {
	pricePerPerson := parseInt(query.Get("pricePerPerson"))
	minPrice := parseInt(query.Get("minPrice"))
	maxPrice := parseInt(query.Get("maxPrice"))
	requiredCategories := query["category"]

	result := make([]Tour, 0, len(tours))
	for _, tour := range tours {
		if pricePerPerson != nil && tour.PricePerPerson != *pricePerPerson {
			continue
		}
		if minPrice != nil && tour.PricePerPerson < *minPrice {
			continue
		}
		if maxPrice != nil && tour.PricePerPerson > *maxPrice {
			continue
		}

		if len(requiredCategories) > 0 {
			match := true
			for _, required := range requiredCategories {
				if !slices.Contains(tour.Categories, required) {
					match = false
					break
				}
			}
			if !match {
				continue
			}
		}
		result = append(result, tour)
	}
	return result
}

func parseInt(raw string) *int {
	if strings.TrimSpace(raw) == "" {
		return nil
	}
	value, err := strconv.Atoi(raw)
	if err != nil {
		return nil
	}
	return &value
}

func writeJSON(w http.ResponseWriter, payload any) {
	body, err := json.Marshal(payload)
	if err != nil {
		http.Error(w, "json error", http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write(body)
}
