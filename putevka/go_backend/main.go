package main

import (
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"html"
	"io"
	"log"
	"math"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	_ "modernc.org/sqlite"
)

const maxReasonablePricePerPerson = 999999

type Category struct {
	ID          string `json:"id"`
	Label       string `json:"label"`
	Description string `json:"description"`
}

type Tour struct {
	ID             string   `json:"id"`
	Source         string   `json:"source,omitempty"`
	Title          string   `json:"title"`
	City           string   `json:"city,omitempty"`
	Region         string   `json:"region"`
	Country        string   `json:"country"`
	PricePerPerson int      `json:"pricePerPerson"`
	Days           int      `json:"days"`
	MinNights      int      `json:"minNights,omitempty"`
	Categories     []string `json:"categories"`
	HasHotel       bool     `json:"hasHotel,omitempty"`
	HasPool        bool     `json:"hasPool,omitempty"`
	Description    string   `json:"description,omitempty"`
	ReviewText     string   `json:"reviewText,omitempty"`
	ReviewAuthor   string   `json:"reviewAuthor,omitempty"`
	RatingValue    float64  `json:"ratingValue,omitempty"`
	ReviewCount    int      `json:"reviewCount,omitempty"`
	Image          string   `json:"image,omitempty"`
	Link           string   `json:"link"`
}

type Review struct {
	Author string  `json:"author"`
	Text   string  `json:"text"`
	Rating float64 `json:"rating,omitempty"`
	Date   string  `json:"date,omitempty"`
	Title  string  `json:"title,omitempty"`
}

type UserRecord struct {
	Username     string `json:"username"`
	Salt         string `json:"salt"`
	PasswordHash string `json:"passwordHash"`
	CreatedAt    string `json:"createdAt"`
}

type DetailPrice struct {
	Title       string `json:"title"`
	Description string `json:"description,omitempty"`
	Price       int    `json:"price"`
	Currency    string `json:"currency,omitempty"`
	Image       string `json:"image,omitempty"`
}

type TourDetail struct {
	Title          string        `json:"title"`
	City           string        `json:"city,omitempty"`
	Region         string        `json:"region,omitempty"`
	Link           string        `json:"link"`
	Description    string        `json:"description,omitempty"`
	Food           string        `json:"food,omitempty"`
	Infrastructure []string      `json:"infrastructure"`
	Photos         []string      `json:"photos"`
	Prices         []DetailPrice `json:"prices"`
}

type bookingPayload struct {
	TourID         string `json:"tourId"`
	Link           string `json:"link"`
	Title          string `json:"title"`
	City           string `json:"city"`
	Region         string `json:"region"`
	PricePerPerson int    `json:"pricePerPerson"`
	Nights         int    `json:"nights"`
	People         int    `json:"people"`
	CustomerName   string `json:"customerName"`
	Phone          string `json:"phone"`
	Email          string `json:"email"`
	Comment        string `json:"comment"`
}

type BookingRecord struct {
	ID             string `json:"id"`
	TourID         string `json:"tourId"`
	Link           string `json:"link"`
	Title          string `json:"title"`
	City           string `json:"city"`
	Region         string `json:"region"`
	PricePerPerson int    `json:"pricePerPerson"`
	Nights         int    `json:"nights"`
	People         int    `json:"people"`
	CustomerName   string `json:"customerName"`
	Phone          string `json:"phone"`
	Email          string `json:"email"`
	Comment        string `json:"comment"`
	Username       string `json:"username,omitempty"`
	Status         string `json:"status"`
	CreatedAt      string `json:"createdAt"`
}

type compiledTour struct {
	cityNorm    string
	titleNorm   string
	searchText  string
	categorySet map[string]struct{}
}

type statsSnapshot struct {
	totalTours     int
	priceMin       *int
	priceMax       *int
	priceAvg       *int
	topRegions     []regionStat
	categoryCounts map[string]int
}

type catalogIndex struct {
	compiled       []compiledTour
	allIndices     []int
	allByPriceAsc  []int
	allByPriceDesc []int
	allByDaysAsc   []int
	allByDaysDesc  []int
	cityIndex      map[string][]int
	categoryIndex  map[string][]int
	reviewByID     map[string]int
	reviewByLink   map[string]int
	stats          statsSnapshot
}

type refreshStatus struct {
	OK                  bool   `json:"ok"`
	IsRefreshing        bool   `json:"isRefreshing"`
	RefreshStage        string `json:"refreshStage"`
	RefreshTargetCount  int    `json:"refreshTargetCount"`
	RefreshCurrentCount int    `json:"refreshCurrentCount"`
	LastParsedAt        string `json:"lastParsedAt"`
	CacheSource         string `json:"cacheSource"`
	RefreshNote         string `json:"refreshNote"`
	UpdatedAt           string `json:"updatedAt"`
}

type App struct {
	rootDir         string
	frontend        string
	dataDir         string
	djangoDir       string
	indexFile       string
	offersFile      string
	snapFile        string
	partialSnapFile string
	statusFile      string
	usersFile       string
	bookingsFile    string
	bookingsDBFile  string
	pythonBin       string
	workerFile      string

	mu                     sync.RWMutex
	tours                  []Tour
	index                  *catalogIndex
	parsedAt               time.Time
	cacheSource            string
	refreshNote            string
	snapshotModTime        time.Time
	partialSnapshotModTime time.Time
	cacheGeneration        uint64

	queryMu          sync.RWMutex
	queryCache       map[string][]int
	queryCacheHits   int
	queryCacheMisses int

	detailMu    sync.RWMutex
	detailCache map[string]TourDetail

	bookingsMu sync.Mutex
	db         *sql.DB

	usersMu   sync.RWMutex
	users     map[string]UserRecord
	sessions  map[string]string
	sessionMu sync.RWMutex

	sessionSecret []byte
}

type loginPayload struct {
	Username string `json:"username"`
	Password string `json:"password"`
}

type regionStat struct {
	Region string `json:"region"`
	Count  int    `json:"count"`
}

var (
	reScriptJSONLD          = regexp.MustCompile(`(?is)<script[^>]*type=["']application/ld\+json["'][^>]*>(.*?)</script>`)
	reGalleryImage          = regexp.MustCompile(`(?is)(?:object-gallery-new__slide[^>]*data-src|img[^>]+src)=["']([^"']+)["']`)
	reInfrastructureSection = regexp.MustCompile(`(?is)Инфраструктура:\s*</strong>\s*<p>\s*<ul[^>]*>(.*?)</ul>`)
	reFoodSection           = regexp.MustCompile(`(?is)Питание\s*</strong>\s*<p>(.*?)</p>`)
	reListItem              = regexp.MustCompile(`(?is)<li[^>]*>(.*?)</li>`)
	reTagStripper           = regexp.MustCompile(`(?is)<[^>]+>`)
)

func main() {
	app, err := newApp()
	if err != nil {
		log.Fatal(err)
	}

	if err := app.loadUsers(); err != nil {
		log.Printf("users load failed: %v", err)
	}
	if err := app.initBookingsStore(); err != nil {
		log.Printf("bookings store init failed: %v", err)
	}
	if app.db != nil {
		defer app.db.Close()
	}
	if err := app.loadTours(); err != nil {
		log.Printf("initial tour load failed: %v", err)
	}

	mux := http.NewServeMux()
	mux.Handle("/static/", http.StripPrefix("/static/", http.FileServer(http.Dir(app.frontend))))
	mux.HandleFunc("/api/health", app.handleHealth)
	mux.HandleFunc("/api/categories", app.handleCategories)
	mux.HandleFunc("/api/price-options", app.handlePriceOptions)
	mux.HandleFunc("/api/stats", app.handleStats)
	mux.HandleFunc("/api/cities", app.handleCities)
	mux.HandleFunc("/api/search-suggestions", app.handleSearchSuggestions)
	mux.HandleFunc("/api/tours", app.handleTours)
	mux.HandleFunc("/api/tour-detail", app.handleTourDetail)
	mux.HandleFunc("/api/reviews", app.handleReviews)
	mux.HandleFunc("/api/bookings", app.handleBookings)
	mux.HandleFunc("/api/parse", app.handleParse)
	mux.HandleFunc("/api/auth/session", app.handleAuthSession)
	mux.HandleFunc("/api/auth/register", app.handleAuthRegister)
	mux.HandleFunc("/api/auth/login", app.handleAuthLogin)
	mux.HandleFunc("/api/auth/logout", app.handleAuthLogout)
	mux.HandleFunc("/", app.handleIndex)

	port := envDefault("GO_BACKEND_PORT", "8080")
	log.Printf("go backend listening on :%s", port)
	log.Fatal(http.ListenAndServe(":"+port, mux))
}

func newApp() (*App, error) {
	rootDir, err := filepath.Abs(filepath.Join(".", ".."))
	if err != nil {
		return nil, err
	}

	secret := os.Getenv("GO_BACKEND_SESSION_SECRET")
	if strings.TrimSpace(secret) == "" {
		secret = "putevka-go-session-secret-change-me"
	}

	return &App{
		rootDir:         rootDir,
		frontend:        filepath.Join(rootDir, "frontend"),
		dataDir:         filepath.Join(rootDir, "data"),
		djangoDir:       filepath.Join(rootDir, "django_backend"),
		indexFile:       filepath.Join(rootDir, "frontend", "index.html"),
		offersFile:      filepath.Join(rootDir, "data", "offers.json"),
		snapFile:        filepath.Join(rootDir, "data", "live_cache_snapshot.json"),
		partialSnapFile: filepath.Join(rootDir, "data", "live_cache_progress.json"),
		statusFile:      filepath.Join(rootDir, "data", "live_refresh_status.json"),
		usersFile:       filepath.Join(rootDir, "data", "users.json"),
		bookingsFile:    filepath.Join(rootDir, "data", "bookings.json"),
		bookingsDBFile:  filepath.Join(rootDir, "data", "bookings.db"),
		pythonBin:       filepath.Join(rootDir, ".venv", "Scripts", "python.exe"),
		workerFile:      filepath.Join(rootDir, "django_backend", "live_refresh_worker.py"),
		users:           map[string]UserRecord{},
		sessions:        map[string]string{},
		queryCache:      map[string][]int{},
		detailCache:     map[string]TourDetail{},
		sessionSecret:   []byte(secret),
	}, nil
}

func envDefault(key, fallback string) string {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback
	}
	return value
}

func (app *App) loadUsers() error {
	raw, err := os.ReadFile(app.usersFile)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return nil
		}
		return err
	}

	var users []UserRecord
	if err := json.Unmarshal(raw, &users); err != nil {
		return err
	}

	next := make(map[string]UserRecord, len(users))
	for _, user := range users {
		if strings.TrimSpace(user.Username) == "" {
			continue
		}
		next[strings.ToLower(user.Username)] = user
	}

	app.usersMu.Lock()
	app.users = next
	app.usersMu.Unlock()
	return nil
}

func (app *App) saveUsers() error {
	app.usersMu.RLock()
	users := make([]UserRecord, 0, len(app.users))
	for _, user := range app.users {
		users = append(users, user)
	}
	app.usersMu.RUnlock()

	sort.Slice(users, func(i, j int) bool {
		return strings.ToLower(users[i].Username) < strings.ToLower(users[j].Username)
	})

	body, err := json.MarshalIndent(users, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(app.usersFile, body, 0644)
}

func (app *App) initBookingsStore() error {
	if err := os.MkdirAll(app.dataDir, 0755); err != nil {
		return err
	}
	db, err := sql.Open("sqlite", app.bookingsDBFile)
	if err != nil {
		return err
	}
	db.SetMaxOpenConns(1)
	if _, err := db.Exec(`
		CREATE TABLE IF NOT EXISTS bookings (
			id TEXT PRIMARY KEY,
			tour_id TEXT NOT NULL,
			link TEXT NOT NULL,
			title TEXT NOT NULL,
			city TEXT NOT NULL DEFAULT '',
			region TEXT NOT NULL DEFAULT '',
			price_per_person INTEGER NOT NULL DEFAULT 0,
			nights INTEGER NOT NULL DEFAULT 1,
			people INTEGER NOT NULL DEFAULT 1,
			customer_name TEXT NOT NULL,
			phone TEXT NOT NULL,
			email TEXT NOT NULL DEFAULT '',
			comment TEXT NOT NULL DEFAULT '',
			username TEXT NOT NULL DEFAULT '',
			status TEXT NOT NULL,
			created_at TEXT NOT NULL
		)
	`); err != nil {
		db.Close()
		return err
	}
	app.db = db
	return app.migrateLegacyBookings()
}

func (app *App) migrateLegacyBookings() error {
	if app.db == nil {
		return nil
	}
	var existingCount int
	if err := app.db.QueryRow(`SELECT COUNT(1) FROM bookings`).Scan(&existingCount); err != nil {
		return err
	}
	if existingCount > 0 {
		return nil
	}

	legacy, err := app.loadLegacyBookingsFile()
	if err != nil {
		return err
	}
	if len(legacy) == 0 {
		return nil
	}
	if err := app.saveBookings(legacy); err != nil {
		return err
	}
	_ = os.Rename(app.bookingsFile, app.bookingsFile+".migrated")
	return nil
}

func (app *App) loadLegacyBookingsFile() ([]BookingRecord, error) {
	raw, err := os.ReadFile(app.bookingsFile)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return []BookingRecord{}, nil
		}
		return nil, err
	}
	var bookings []BookingRecord
	if err := json.Unmarshal(raw, &bookings); err != nil {
		return nil, err
	}
	return bookings, nil
}

func (app *App) loadBookings() ([]BookingRecord, error) {
	if app.db != nil {
		rows, err := app.db.Query(`
			SELECT id, tour_id, link, title, city, region, price_per_person, nights, people,
			       customer_name, phone, email, comment, username, status, created_at
			FROM bookings
			ORDER BY datetime(created_at) DESC, id DESC
		`)
		if err != nil {
			return nil, err
		}
		defer rows.Close()

		bookings := []BookingRecord{}
		for rows.Next() {
			var record BookingRecord
			if err := rows.Scan(
				&record.ID,
				&record.TourID,
				&record.Link,
				&record.Title,
				&record.City,
				&record.Region,
				&record.PricePerPerson,
				&record.Nights,
				&record.People,
				&record.CustomerName,
				&record.Phone,
				&record.Email,
				&record.Comment,
				&record.Username,
				&record.Status,
				&record.CreatedAt,
			); err != nil {
				return nil, err
			}
			bookings = append(bookings, record)
		}
		if err := rows.Err(); err != nil {
			return nil, err
		}
		return bookings, nil
	}

	raw, err := os.ReadFile(app.bookingsFile)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return []BookingRecord{}, nil
		}
		return nil, err
	}
	var bookings []BookingRecord
	if err := json.Unmarshal(raw, &bookings); err != nil {
		return nil, err
	}
	return bookings, nil
}

func (app *App) saveBookings(bookings []BookingRecord) error {
	if app.db != nil {
		tx, err := app.db.Begin()
		if err != nil {
			return err
		}
		defer func() {
			if tx != nil {
				_ = tx.Rollback()
			}
		}()

		if _, err := tx.Exec(`DELETE FROM bookings`); err != nil {
			return err
		}
		statement, err := tx.Prepare(`
			INSERT INTO bookings (
				id, tour_id, link, title, city, region, price_per_person, nights, people,
				customer_name, phone, email, comment, username, status, created_at
			) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
		`)
		if err != nil {
			return err
		}
		defer statement.Close()

		for _, record := range bookings {
			if _, err := statement.Exec(
				record.ID,
				record.TourID,
				record.Link,
				record.Title,
				record.City,
				record.Region,
				record.PricePerPerson,
				record.Nights,
				record.People,
				record.CustomerName,
				record.Phone,
				record.Email,
				record.Comment,
				record.Username,
				record.Status,
				record.CreatedAt,
			); err != nil {
				return err
			}
		}
		if err := tx.Commit(); err != nil {
			return err
		}
		tx = nil
		return nil
	}

	body, err := json.MarshalIndent(bookings, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(app.bookingsFile, body, 0644)
}

func (app *App) loadTours() error {
	paths := []struct {
		path   string
		source string
		note   string
	}{
		{app.snapFile, "snapshot_bootstrap", "Используется сохранённый live-снимок."},
		{app.offersFile, "local_bootstrap", "Используется локальный стартовый каталог."},
	}

	var lastErr error
	for _, candidate := range paths {
		tours, err := readToursFromFile(candidate.path)
		if err != nil {
			lastErr = err
			continue
		}
		if len(tours) == 0 {
			continue
		}
		index := buildCatalogIndex(tours)
		modTime := fileModTime(candidate.path)
		app.mu.Lock()
		app.tours = tours
		app.index = index
		app.parsedAt = time.Now().UTC()
		app.cacheSource = candidate.source
		app.refreshNote = candidate.note
		if candidate.path == app.snapFile {
			app.snapshotModTime = modTime
		}
		if candidate.path == app.partialSnapFile {
			app.partialSnapshotModTime = modTime
		}
		app.cacheGeneration++
		app.mu.Unlock()
		app.queryMu.Lock()
		clear(app.queryCache)
		app.queryMu.Unlock()
		return nil
	}
	if lastErr == nil {
		lastErr = errors.New("no tour data files found")
	}
	return lastErr
}

func readToursFromFile(path string) ([]Tour, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}

	var tours []Tour
	if err := json.Unmarshal(raw, &tours); err != nil {
		return nil, err
	}

	filtered := make([]Tour, 0, len(tours))
	for _, tour := range tours {
		if tour.PricePerPerson <= 0 {
			continue
		}
		if tour.PricePerPerson > maxReasonablePricePerPerson {
			continue
		}
		if !isRussiaCountry(tour.Country) {
			continue
		}
		if len(tour.Categories) == 0 {
			continue
		}
		if tour.Region == "" {
			tour.Region = "Россия"
		}
		if tour.City == "" {
			tour.City = tour.Region
		}
		if tour.MinNights <= 0 {
			if tour.Days > 0 {
				tour.MinNights = tour.Days
			} else {
				tour.MinNights = 1
			}
		}
		if tour.Days <= 0 {
			tour.Days = maxInt(tour.MinNights, 1)
		}
		filtered = append(filtered, tour)
	}

	sort.Slice(filtered, func(i, j int) bool {
		if filtered[i].PricePerPerson == filtered[j].PricePerPerson {
			return filtered[i].Title < filtered[j].Title
		}
		return filtered[i].PricePerPerson < filtered[j].PricePerPerson
	})
	return filtered, nil
}

func isRussiaCountry(country string) bool {
	safe := strings.ToLower(strings.TrimSpace(country))
	return strings.Contains(safe, "рос") || strings.Contains(safe, "russia")
}

func fileModTime(path string) time.Time {
	info, err := os.Stat(path)
	if err != nil {
		return time.Time{}
	}
	return info.ModTime().UTC()
}

func (app *App) readRefreshStatus() refreshStatus {
	raw, err := os.ReadFile(app.statusFile)
	if err != nil {
		return refreshStatus{}
	}
	var status refreshStatus
	if err := json.Unmarshal(raw, &status); err != nil {
		return refreshStatus{}
	}
	if status.IsRefreshing {
		if updatedAt, err := time.Parse(time.RFC3339, status.UpdatedAt); err == nil && time.Since(updatedAt) > 20*time.Second {
			status.IsRefreshing = false
			status.RefreshStage = "idle"
		}
	}
	return status
}

func (app *App) writeRefreshStatus(status refreshStatus) error {
	body, err := json.Marshal(status)
	if err != nil {
		return err
	}
	return os.WriteFile(app.statusFile, body, 0644)
}

func (app *App) syncSnapshotIfChanged() refreshStatus {
	status := app.readRefreshStatus()
	snapshotPath := app.snapFile
	isPartial := false
	if status.IsRefreshing && strings.Contains(status.CacheSource, "partial") {
		snapshotPath = app.partialSnapFile
		isPartial = true
	}
	modTime := fileModTime(snapshotPath)
	if modTime.IsZero() {
		return status
	}

	app.mu.RLock()
	currentModTime := app.snapshotModTime
	if isPartial {
		currentModTime = app.partialSnapshotModTime
	}
	app.mu.RUnlock()
	if !modTime.After(currentModTime) {
		return status
	}

	tours, err := readToursFromFile(snapshotPath)
	if err != nil || len(tours) == 0 {
		return status
	}
	app.mu.Lock()
	targetModTime := app.snapshotModTime
	if isPartial {
		targetModTime = app.partialSnapshotModTime
	}
	if modTime.After(targetModTime) {
		nextTours := tours
		if isPartial && len(app.tours) > len(tours) {
			nextTours = mergeTours(app.tours, tours)
		}
		index := buildCatalogIndex(nextTours)
		app.tours = nextTours
		app.index = index
		app.parsedAt = modTime
		if status.CacheSource != "" {
			app.cacheSource = status.CacheSource
		} else {
			app.cacheSource = "snapshot_live"
		}
		if status.RefreshNote != "" {
			app.refreshNote = status.RefreshNote
		}
		if isPartial {
			app.partialSnapshotModTime = modTime
		} else {
			app.snapshotModTime = modTime
		}
		app.cacheGeneration++
	}
	app.mu.Unlock()
	app.queryMu.Lock()
	clear(app.queryCache)
	app.queryMu.Unlock()
	return status
}

func mergeTours(current []Tour, incoming []Tour) []Tour {
	merged := make([]Tour, 0, len(current)+len(incoming))
	seen := make(map[string]struct{}, len(current)+len(incoming))

	add := func(tour Tour) {
		key := tourDedupKey(tour)
		if _, ok := seen[key]; ok {
			return
		}
		seen[key] = struct{}{}
		merged = append(merged, tour)
	}

	for _, tour := range current {
		add(tour)
	}
	for _, tour := range incoming {
		add(tour)
	}

	sort.Slice(merged, func(i, j int) bool {
		return compareTours(merged[i], merged[j], "price_asc")
	})
	return merged
}

func tourDedupKey(tour Tour) string {
	if strings.TrimSpace(tour.ID) != "" {
		return "id:" + tour.ID
	}
	if strings.TrimSpace(tour.Link) != "" {
		return "link:" + tour.Link
	}
	return strings.Join([]string{
		norm(tour.Title),
		norm(tour.City),
		norm(tour.Region),
		strconv.Itoa(tour.PricePerPerson),
		strconv.Itoa(tour.Days),
	}, "|")
}

func (app *App) startLiveRefresh() error {
	pythonBin := app.pythonBin
	if _, err := os.Stat(pythonBin); err != nil {
		pythonBin = "python"
	}
	logFile, err := os.OpenFile(filepath.Join(app.dataDir, "live_refresh_worker.log"), os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
	if err != nil {
		return err
	}

	cmd := exec.Command(pythonBin, app.workerFile)
	cmd.Dir = app.djangoDir
	cmd.Stdout = logFile
	cmd.Stderr = logFile
	if err := cmd.Start(); err != nil {
		_ = logFile.Close()
		return err
	}
	_ = cmd.Process.Release()
	return logFile.Close()
}

func (app *App) handleIndex(w http.ResponseWriter, r *http.Request) {
	if strings.HasPrefix(r.URL.Path, "/api/") || strings.HasPrefix(r.URL.Path, "/static/") {
		http.NotFound(w, r)
		return
	}
	body, err := os.ReadFile(app.indexFile)
	if err != nil {
		http.Error(w, "index not found", http.StatusInternalServerError)
		return
	}

	version := currentStaticVersion(app.frontend)
	rendered := strings.ReplaceAll(string(body), "{{ static_version }}", version)
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte(rendered))
}

func currentStaticVersion(frontendDir string) string {
	targets := []string{
		filepath.Join(frontendDir, "app.js"),
		filepath.Join(frontendDir, "theme.css"),
		filepath.Join(frontendDir, "index.html"),
	}
	var latest int64
	for _, target := range targets {
		info, err := os.Stat(target)
		if err != nil {
			continue
		}
		if info.ModTime().Unix() > latest {
			latest = info.ModTime().Unix()
		}
	}
	if latest == 0 {
		return strconv.FormatInt(time.Now().Unix(), 10)
	}
	return strconv.FormatInt(latest, 10)
}

func (app *App) handleHealth(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		methodNotAllowed(w)
		return
	}
	status := app.syncSnapshotIfChanged()
	cacheHits, cacheMisses, cacheSize := app.queryCacheMetrics()
	app.mu.RLock()
	refreshNote := app.refreshNote
	if status.RefreshNote != "" {
		refreshNote = status.RefreshNote
	}
	payload := map[string]any{
		"ok":                  true,
		"toursInCache":        len(app.tours),
		"lastParsedAt":        toISO(app.parsedAt),
		"cacheSource":         app.cacheSource,
		"refreshNote":         refreshNote,
		"queryCacheHits":      cacheHits,
		"queryCacheMisses":    cacheMisses,
		"queryCacheSize":      cacheSize,
		"cacheGeneration":     app.cacheGeneration,
		"isRefreshing":        status.IsRefreshing,
		"refreshStage":        firstNonEmpty(status.RefreshStage, "idle"),
		"refreshTargetCount":  maxInt(status.RefreshTargetCount, len(app.tours)),
		"refreshCurrentCount": maxInt(status.RefreshCurrentCount, len(app.tours)),
	}
	app.mu.RUnlock()
	writeJSON(w, http.StatusOK, payload)
}

func (app *App) handleCategories(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		methodNotAllowed(w)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"categories": categoriesCatalog()})
}

func (app *App) handlePriceOptions(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		methodNotAllowed(w)
		return
	}
	options := make([]int, 0, 191)
	for price := 5000; price <= 100000; price += 500 {
		options = append(options, price)
	}
	writeJSON(w, http.StatusOK, map[string]any{"options": options})
}

func (app *App) handleStats(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		methodNotAllowed(w)
		return
	}

	status := app.syncSnapshotIfChanged()
	cacheHits, cacheMisses, cacheSize := app.queryCacheMetrics()
	app.mu.RLock()
	totalTours := len(app.tours)
	stats := statsSnapshot{categoryCounts: map[string]int{}}
	if app.index != nil {
		stats = app.index.stats
	}
	parsedAt := app.parsedAt
	source := app.cacheSource
	note := app.refreshNote
	app.mu.RUnlock()
	if status.RefreshNote != "" {
		note = status.RefreshNote
	}

	writeJSON(w, http.StatusOK, map[string]any{
		"totalTours":          totalTours,
		"priceMin":            derefInt(stats.priceMin),
		"priceMax":            derefInt(stats.priceMax),
		"priceAvg":            derefInt(stats.priceAvg),
		"priceMaxRaw":         derefInt(stats.priceMax),
		"priceAvgRaw":         derefInt(stats.priceAvg),
		"topRegions":          stats.topRegions,
		"categoryCounts":      stats.categoryCounts,
		"lastParsedAt":        toISO(parsedAt),
		"cacheSource":         source,
		"queryCacheHits":      cacheHits,
		"queryCacheMisses":    cacheMisses,
		"queryCacheSize":      cacheSize,
		"refreshNote":         note,
		"isRefreshing":        status.IsRefreshing,
		"refreshStage":        firstNonEmpty(status.RefreshStage, "idle"),
		"refreshTargetCount":  maxInt(status.RefreshTargetCount, totalTours),
		"refreshCurrentCount": maxInt(status.RefreshCurrentCount, totalTours),
	})
}

func (app *App) handleCities(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		methodNotAllowed(w)
		return
	}
	app.syncSnapshotIfChanged()
	query := buildQuery(r.URL.Query())
	query.City = ""
	query.Query = strings.TrimSpace(r.URL.Query().Get("tourQuery"))
	prefix := norm(strings.TrimSpace(firstNonEmpty(r.URL.Query().Get("prefix"), r.URL.Query().Get("q"))))
	limit := clampInt(parseIntDefault(r.URL.Query().Get("limit"), 12), 1, 50)

	app.mu.RLock()
	tours := app.tours
	index := app.index
	generation := app.cacheGeneration
	app.mu.RUnlock()

	filtered := app.filteredIndices(index, tours, query, generation)
	counts := map[string]int{}
	for _, idx := range filtered {
		tour := tours[idx]
		city := strings.TrimSpace(firstNonEmpty(tour.City, tour.Region))
		if city == "" {
			continue
		}
		if prefix != "" && !strings.HasPrefix(norm(city), prefix) {
			continue
		}
		counts[city]++
	}

	type cityItem struct {
		City  string `json:"city"`
		Count int    `json:"count"`
	}
	items := make([]cityItem, 0, len(counts))
	for city, count := range counts {
		items = append(items, cityItem{City: city, Count: count})
	}
	sort.Slice(items, func(i, j int) bool {
		if items[i].Count == items[j].Count {
			return items[i].City < items[j].City
		}
		return items[i].Count > items[j].Count
	})
	if len(items) > limit {
		items = items[:limit]
	}
	writeJSON(w, http.StatusOK, map[string]any{"cities": items})
}

func (app *App) handleSearchSuggestions(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		methodNotAllowed(w)
		return
	}
	app.syncSnapshotIfChanged()
	query := buildQuery(r.URL.Query())
	query.Query = ""
	prefix := norm(strings.TrimSpace(firstNonEmpty(r.URL.Query().Get("prefix"), r.URL.Query().Get("q"))))
	limit := clampInt(parseIntDefault(r.URL.Query().Get("limit"), 8), 1, 20)

	app.mu.RLock()
	tours := app.tours
	index := app.index
	generation := app.cacheGeneration
	app.mu.RUnlock()

	filtered := app.filteredIndices(index, tours, query, generation)
	counts := map[string]int{}
	for _, idx := range filtered {
		tour := tours[idx]
		title := strings.TrimSpace(tour.Title)
		if title == "" {
			continue
		}
		titleNorm := index.compiled[idx].titleNorm
		if prefix != "" && !strings.Contains(titleNorm, prefix) && !hasTokenPrefix(titleNorm, prefix) {
			continue
		}
		counts[title]++
	}

	type queryItem struct {
		Query string `json:"query"`
		Count int    `json:"count"`
	}
	items := make([]queryItem, 0, len(counts))
	for title, count := range counts {
		items = append(items, queryItem{Query: title, Count: count})
	}
	sort.Slice(items, func(i, j int) bool {
		if items[i].Count == items[j].Count {
			return items[i].Query < items[j].Query
		}
		return items[i].Count > items[j].Count
	})
	if len(items) > limit {
		items = items[:limit]
	}
	writeJSON(w, http.StatusOK, map[string]any{"queries": items})
}

func (app *App) handleTours(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		methodNotAllowed(w)
		return
	}
	status := app.syncSnapshotIfChanged()
	query := buildQuery(r.URL.Query())

	app.mu.RLock()
	tours := app.tours
	index := app.index
	generation := app.cacheGeneration
	parsedAt := app.parsedAt
	source := app.cacheSource
	note := app.refreshNote
	app.mu.RUnlock()
	if status.RefreshNote != "" {
		note = status.RefreshNote
	}

	filtered := app.filteredIndices(index, tours, query, generation)
	cacheHits, cacheMisses, _ := app.queryCacheMetrics()
	total := len(filtered)
	start := clampInt(query.Offset, 0, total)
	end := clampInt(query.Offset+query.Limit, 0, total)
	pageTours := make([]Tour, 0, end-start)
	for _, idx := range filtered[start:end] {
		pageTours = append(pageTours, tours[idx])
	}

	writeJSON(w, http.StatusOK, map[string]any{
		"count":               total,
		"returned":            len(pageTours),
		"tours":               pageTours,
		"lastParsedAt":        toISO(parsedAt),
		"cacheSource":         source,
		"refreshNote":         note,
		"queryCacheHits":      cacheHits,
		"queryCacheMisses":    cacheMisses,
		"isRefreshing":        status.IsRefreshing,
		"refreshStage":        firstNonEmpty(status.RefreshStage, "idle"),
		"refreshTargetCount":  maxInt(status.RefreshTargetCount, len(tours)),
		"refreshCurrentCount": maxInt(status.RefreshCurrentCount, len(tours)),
		"offset":              start,
		"limit":               query.Limit,
	})
}

func (app *App) handleTourDetail(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		methodNotAllowed(w)
		return
	}
	app.syncSnapshotIfChanged()
	tourID := strings.TrimSpace(r.URL.Query().Get("tourId"))
	link := strings.TrimSpace(r.URL.Query().Get("link"))

	tour, ok := app.findTour(tourID, link)
	if !ok {
		writeJSON(w, http.StatusNotFound, map[string]any{"ok": false, "message": "Tour not found"})
		return
	}

	detail, err := app.getTourDetail(tour)
	if err != nil {
		writeJSON(w, http.StatusOK, map[string]any{
			"ok":             true,
			"title":          tour.Title,
			"city":           tour.City,
			"region":         tour.Region,
			"link":           tour.Link,
			"description":    strings.TrimSpace(firstNonEmpty(tour.Description, tour.ReviewText)),
			"food":           "",
			"infrastructure": []string{},
			"photos":         compactStrings([]string{tour.Image}),
			"prices": []DetailPrice{{
				Title:    tour.Title,
				Price:    tour.PricePerPerson,
				Currency: "RUB",
				Image:    tour.Image,
			}},
			"message": err.Error(),
		})
		return
	}

	writeJSON(w, http.StatusOK, map[string]any{"ok": true, "detail": detail})
}

func (app *App) handleReviews(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		methodNotAllowed(w)
		return
	}
	app.syncSnapshotIfChanged()
	tourID := strings.TrimSpace(r.URL.Query().Get("tourId"))
	link := strings.TrimSpace(r.URL.Query().Get("link"))

	app.mu.RLock()
	tours := app.tours
	index := app.index
	app.mu.RUnlock()

	foundIndex := -1
	if index != nil && tourID != "" {
		if idx, ok := index.reviewByID[tourID]; ok {
			foundIndex = idx
		}
	}
	if index != nil && foundIndex < 0 && link != "" {
		if idx, ok := index.reviewByLink[link]; ok {
			foundIndex = idx
		}
	}

	if foundIndex < 0 || foundIndex >= len(tours) {
		writeJSON(w, http.StatusOK, map[string]any{
			"title":       "",
			"link":        link,
			"reviews":     []Review{},
			"ratingValue": nil,
			"reviewCount": 0,
		})
		return
	}
	found := tours[foundIndex]

	reviews := []Review{}
	if strings.TrimSpace(found.ReviewText) != "" {
		reviews = append(reviews, Review{
			Author: strings.TrimSpace(found.ReviewAuthor),
			Text:   strings.TrimSpace(found.ReviewText),
			Rating: found.RatingValue,
			Title:  "",
		})
	} else if strings.TrimSpace(found.Description) != "" {
		reviews = append(reviews, Review{
			Author: "",
			Text:   strings.TrimSpace(found.Description),
			Rating: found.RatingValue,
			Title:  "",
		})
	}

	writeJSON(w, http.StatusOK, map[string]any{
		"title":       found.Title,
		"link":        found.Link,
		"reviews":     reviews,
		"ratingValue": zeroToNilFloat(found.RatingValue),
		"reviewCount": nonZeroInt(found.ReviewCount, len(reviews)),
	})
}

func (app *App) handleBookings(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		methodNotAllowed(w)
		return
	}
	var payload bookingPayload
	if err := decodeJSON(r, &payload); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]any{"ok": false, "message": "Некорректный JSON."})
		return
	}

	payload.CustomerName = strings.TrimSpace(payload.CustomerName)
	payload.Phone = strings.TrimSpace(payload.Phone)
	payload.Email = strings.TrimSpace(payload.Email)
	payload.Comment = strings.TrimSpace(payload.Comment)
	payload.Title = strings.TrimSpace(payload.Title)
	payload.Link = strings.TrimSpace(payload.Link)
	payload.City = strings.TrimSpace(payload.City)
	payload.Region = strings.TrimSpace(payload.Region)

	if payload.CustomerName == "" || payload.Phone == "" || payload.Link == "" || payload.Title == "" {
		writeJSON(w, http.StatusBadRequest, map[string]any{"ok": false, "message": "Заполните имя, телефон и объект бронирования."})
		return
	}
	if payload.Nights <= 0 {
		payload.Nights = 1
	}
	if payload.People <= 0 {
		payload.People = 1
	}

	username, _ := app.currentUsername(r)
	record := BookingRecord{
		ID:             randomToken(12),
		TourID:         payload.TourID,
		Link:           payload.Link,
		Title:          payload.Title,
		City:           payload.City,
		Region:         payload.Region,
		PricePerPerson: payload.PricePerPerson,
		Nights:         payload.Nights,
		People:         payload.People,
		CustomerName:   payload.CustomerName,
		Phone:          payload.Phone,
		Email:          payload.Email,
		Comment:        payload.Comment,
		Username:       username,
		Status:         "new",
		CreatedAt:      time.Now().UTC().Format(time.RFC3339),
	}

	app.bookingsMu.Lock()
	bookings, err := app.loadBookings()
	if err == nil {
		bookings = append(bookings, record)
		err = app.saveBookings(bookings)
	}
	app.bookingsMu.Unlock()
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]any{"ok": false, "message": "Не удалось сохранить бронь."})
		return
	}

	writeJSON(w, http.StatusOK, map[string]any{"ok": true, "bookingId": record.ID, "status": record.Status})
}

func (app *App) findTour(tourID string, link string) (Tour, bool) {
	app.mu.RLock()
	defer app.mu.RUnlock()
	if app.index != nil && tourID != "" {
		if idx, ok := app.index.reviewByID[tourID]; ok && idx >= 0 && idx < len(app.tours) {
			return app.tours[idx], true
		}
	}
	if app.index != nil && link != "" {
		if idx, ok := app.index.reviewByLink[link]; ok && idx >= 0 && idx < len(app.tours) {
			return app.tours[idx], true
		}
	}
	for _, tour := range app.tours {
		if tourID != "" && tour.ID == tourID {
			return tour, true
		}
		if link != "" && tour.Link == link {
			return tour, true
		}
	}
	return Tour{}, false
}

func (app *App) getTourDetail(tour Tour) (TourDetail, error) {
	cacheKey := firstNonEmpty(tour.ID, tour.Link)
	app.detailMu.RLock()
	if detail, ok := app.detailCache[cacheKey]; ok {
		app.detailMu.RUnlock()
		return detail, nil
	}
	app.detailMu.RUnlock()

	if strings.TrimSpace(tour.Link) == "" {
		return TourDetail{}, errors.New("missing tour link")
	}
	request, err := http.NewRequest(http.MethodGet, tour.Link, nil)
	if err != nil {
		return TourDetail{}, err
	}
	request.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
	request.Header.Set("Accept-Language", "ru-RU,ru;q=0.9,en;q=0.8")
	client := &http.Client{Timeout: 15 * time.Second}
	response, err := client.Do(request)
	if err != nil {
		return TourDetail{}, err
	}
	defer response.Body.Close()
	if response.StatusCode >= 400 {
		return TourDetail{}, fmt.Errorf("detail page returned %s", response.Status)
	}
	body, err := io.ReadAll(response.Body)
	if err != nil {
		return TourDetail{}, err
	}

	detail := parseTourDetailHTML(string(body), tour)
	app.detailMu.Lock()
	app.detailCache[cacheKey] = detail
	app.detailMu.Unlock()
	return detail, nil
}

func parseTourDetailHTML(pageHTML string, tour Tour) TourDetail {
	detail := TourDetail{
		Title:          tour.Title,
		City:           tour.City,
		Region:         tour.Region,
		Link:           tour.Link,
		Description:    strings.TrimSpace(firstNonEmpty(extractMetaDescription(pageHTML), tour.Description, tour.ReviewText)),
		Food:           extractFood(pageHTML),
		Infrastructure: extractInfrastructure(pageHTML),
		Photos:         extractPhotos(pageHTML, tour),
		Prices:         extractDetailPrices(pageHTML, tour),
	}
	if len(detail.Photos) == 0 {
		detail.Photos = compactStrings([]string{tour.Image})
	}
	if len(detail.Prices) == 0 {
		detail.Prices = []DetailPrice{{
			Title:    tour.Title,
			Price:    tour.PricePerPerson,
			Currency: "RUB",
			Image:    tour.Image,
		}}
	}
	return detail
}

func extractMetaDescription(pageHTML string) string {
	match := regexp.MustCompile(`(?is)<meta[^>]+name=["']description["'][^>]+content=["']([^"']+)["']`).FindStringSubmatch(pageHTML)
	if len(match) < 2 {
		return ""
	}
	return cleanHTMLText(match[1])
}

func extractPhotos(pageHTML string, tour Tour) []string {
	found := []string{}
	seen := map[string]struct{}{}
	for _, match := range reGalleryImage.FindAllStringSubmatch(pageHTML, -1) {
		if len(match) < 2 {
			continue
		}
		url := strings.TrimSpace(html.UnescapeString(match[1]))
		if url == "" || !strings.Contains(url, "images.putevka.com") {
			continue
		}
		if _, ok := seen[url]; ok {
			continue
		}
		seen[url] = struct{}{}
		found = append(found, url)
		if len(found) >= 18 {
			break
		}
	}
	if len(found) == 0 && strings.TrimSpace(tour.Image) != "" {
		found = append(found, tour.Image)
	}
	return found
}

func extractInfrastructure(pageHTML string) []string {
	match := reInfrastructureSection.FindStringSubmatch(pageHTML)
	if len(match) < 2 {
		return []string{}
	}
	items := []string{}
	seen := map[string]struct{}{}
	for _, itemMatch := range reListItem.FindAllStringSubmatch(match[1], -1) {
		if len(itemMatch) < 2 {
			continue
		}
		item := cleanHTMLText(itemMatch[1])
		if item == "" {
			continue
		}
		if _, ok := seen[item]; ok {
			continue
		}
		seen[item] = struct{}{}
		items = append(items, item)
	}
	return items
}

func extractFood(pageHTML string) string {
	match := reFoodSection.FindStringSubmatch(pageHTML)
	if len(match) < 2 {
		return ""
	}
	return cleanHTMLText(match[1])
}

func extractDetailPrices(pageHTML string, tour Tour) []DetailPrice {
	prices := []DetailPrice{}
	seen := map[string]struct{}{}
	for _, blockMatch := range reScriptJSONLD.FindAllStringSubmatch(pageHTML, -1) {
		if len(blockMatch) < 2 {
			continue
		}
		var data any
		if err := json.Unmarshal([]byte(html.UnescapeString(strings.TrimSpace(blockMatch[1]))), &data); err != nil {
			continue
		}
		for _, product := range collectProductNodes(data) {
			title := strings.TrimSpace(stringValue(product["name"]))
			price := parsePriceValue(product["offers"])
			if title == "" || price <= 0 {
				continue
			}
			key := title + "|" + strconv.Itoa(price)
			if _, ok := seen[key]; ok {
				continue
			}
			seen[key] = struct{}{}
			prices = append(prices, DetailPrice{
				Title:       title,
				Description: cleanHTMLText(stringValue(product["description"])),
				Price:       price,
				Currency:    firstNonEmpty(stringValueFromPath(product["offers"], "priceCurrency"), "RUB"),
				Image:       stringValue(product["image"]),
			})
		}
	}
	sort.Slice(prices, func(i, j int) bool {
		if prices[i].Price == prices[j].Price {
			return prices[i].Title < prices[j].Title
		}
		return prices[i].Price < prices[j].Price
	})
	if len(prices) > 12 {
		prices = prices[:12]
	}
	return prices
}

func collectProductNodes(node any) []map[string]any {
	found := []map[string]any{}
	switch typed := node.(type) {
	case map[string]any:
		if looksLikeProduct(typed) {
			found = append(found, typed)
		}
		for _, value := range typed {
			found = append(found, collectProductNodes(value)...)
		}
	case []any:
		for _, item := range typed {
			found = append(found, collectProductNodes(item)...)
		}
	}
	return found
}

func looksLikeProduct(node map[string]any) bool {
	typeValue, ok := node["@type"]
	if !ok {
		return false
	}
	switch typed := typeValue.(type) {
	case string:
		return typed == "Product"
	case []any:
		for _, item := range typed {
			if text, ok := item.(string); ok && text == "Product" {
				return true
			}
		}
	}
	return false
}

func stringValue(value any) string {
	switch typed := value.(type) {
	case string:
		return strings.TrimSpace(typed)
	default:
		return ""
	}
}

func stringValueFromPath(value any, key string) string {
	if typed, ok := value.(map[string]any); ok {
		return stringValue(typed[key])
	}
	return ""
}

func parsePriceValue(value any) int {
	switch typed := value.(type) {
	case map[string]any:
		return parsePriceValue(typed["price"])
	case []any:
		for _, item := range typed {
			if result := parsePriceValue(item); result > 0 {
				return result
			}
		}
	case string:
		return parseIntDefault(strings.TrimSpace(strings.Split(typed, ".")[0]), 0)
	case float64:
		return int(math.Round(typed))
	}
	return 0
}

func cleanHTMLText(value string) string {
	value = html.UnescapeString(value)
	value = reTagStripper.ReplaceAllString(value, " ")
	value = strings.ReplaceAll(value, "\n", " ")
	value = strings.ReplaceAll(value, "\r", " ")
	value = strings.ReplaceAll(value, "\t", " ")
	value = strings.Join(strings.Fields(value), " ")
	return strings.TrimSpace(value)
}

func compactStrings(values []string) []string {
	result := make([]string, 0, len(values))
	seen := map[string]struct{}{}
	for _, value := range values {
		value = strings.TrimSpace(value)
		if value == "" {
			continue
		}
		if _, ok := seen[value]; ok {
			continue
		}
		seen[value] = struct{}{}
		result = append(result, value)
	}
	return result
}

func (app *App) handleParse(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		methodNotAllowed(w)
		return
	}
	status := app.syncSnapshotIfChanged()
	if !status.IsRefreshing {
		app.mu.RLock()
		currentCount := len(app.tours)
		currentParsedAt := app.parsedAt
		currentSource := app.cacheSource
		app.mu.RUnlock()
		queuedStatus := refreshStatus{
			OK:                  true,
			IsRefreshing:        true,
			RefreshStage:        "queued",
			RefreshTargetCount:  maxInt(100000, currentCount),
			RefreshCurrentCount: currentCount,
			LastParsedAt:        toISO(currentParsedAt),
			CacheSource:         currentSource,
			RefreshNote:         "Live-парсер запускается.",
			UpdatedAt:           time.Now().UTC().Format(time.RFC3339),
		}
		_ = app.writeRefreshStatus(queuedStatus)
		if err := app.startLiveRefresh(); err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]any{
				"ok":      false,
				"message": err.Error(),
			})
			return
		}
		time.Sleep(350 * time.Millisecond)
		status = app.readRefreshStatus()
	}

	app.mu.RLock()
	cacheHits, cacheMisses, cacheSize := app.queryCacheMetrics()
	payload := map[string]any{
		"ok":                  true,
		"started":             true,
		"parsed":              len(app.tours),
		"lastParsedAt":        toISO(app.parsedAt),
		"cacheSource":         app.cacheSource,
		"refreshNote":         firstNonEmpty(status.RefreshNote, app.refreshNote),
		"queryCacheHits":      cacheHits,
		"queryCacheMisses":    cacheMisses,
		"queryCacheSize":      cacheSize,
		"isRefreshing":        status.IsRefreshing,
		"refreshStage":        firstNonEmpty(status.RefreshStage, "queued"),
		"refreshTargetCount":  maxInt(status.RefreshTargetCount, len(app.tours)),
		"refreshCurrentCount": maxInt(status.RefreshCurrentCount, len(app.tours)),
	}
	app.mu.RUnlock()
	writeJSON(w, http.StatusOK, payload)
}

func (app *App) handleAuthSession(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		methodNotAllowed(w)
		return
	}
	username, ok := app.currentUsername(r)
	if !ok {
		writeJSON(w, http.StatusOK, map[string]any{"ok": true, "isAuthenticated": false, "username": ""})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"ok": true, "isAuthenticated": true, "username": username})
}

func (app *App) handleAuthRegister(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		methodNotAllowed(w)
		return
	}
	var payload loginPayload
	if err := decodeJSON(r, &payload); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]any{"ok": false, "message": "Некорректный JSON."})
		return
	}
	username := strings.TrimSpace(payload.Username)
	password := payload.Password

	if err := validateCredentials(username, password); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]any{"ok": false, "message": err.Error()})
		return
	}

	app.usersMu.Lock()
	if _, exists := app.users[strings.ToLower(username)]; exists {
		app.usersMu.Unlock()
		writeJSON(w, http.StatusBadRequest, map[string]any{"ok": false, "message": "Такой логин уже занят."})
		return
	}
	salt := randomToken(16)
	record := UserRecord{
		Username:     username,
		Salt:         salt,
		PasswordHash: hashPassword(salt, password),
		CreatedAt:    time.Now().UTC().Format(time.RFC3339),
	}
	app.users[strings.ToLower(username)] = record
	app.usersMu.Unlock()

	if err := app.saveUsers(); err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]any{"ok": false, "message": "Не удалось сохранить пользователя."})
		return
	}
	app.createSession(w, username)
	writeJSON(w, http.StatusOK, map[string]any{"ok": true, "isAuthenticated": true, "username": username})
}

func (app *App) handleAuthLogin(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		methodNotAllowed(w)
		return
	}
	var payload loginPayload
	if err := decodeJSON(r, &payload); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]any{"ok": false, "message": "Некорректный JSON."})
		return
	}
	username := strings.TrimSpace(payload.Username)
	password := payload.Password
	if username == "" || password == "" {
		writeJSON(w, http.StatusBadRequest, map[string]any{"ok": false, "message": "Логин и пароль обязательны."})
		return
	}

	app.usersMu.RLock()
	record, exists := app.users[strings.ToLower(username)]
	app.usersMu.RUnlock()
	if !exists || hashPassword(record.Salt, password) != record.PasswordHash {
		writeJSON(w, http.StatusBadRequest, map[string]any{"ok": false, "message": "Неверный логин или пароль."})
		return
	}

	app.createSession(w, record.Username)
	writeJSON(w, http.StatusOK, map[string]any{"ok": true, "isAuthenticated": true, "username": record.Username})
}

func (app *App) handleAuthLogout(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		methodNotAllowed(w)
		return
	}
	app.destroySession(w, r)
	writeJSON(w, http.StatusOK, map[string]any{"ok": true, "isAuthenticated": false, "username": ""})
}

type Query struct {
	PricePerPerson *int
	MinPrice       *int
	MaxPrice       *int
	Categories     []string
	City           string
	Query          string
	Sort           string
	Limit          int
	Offset         int
}

func buildQuery(values map[string][]string) Query {
	sortValue := strings.TrimSpace(firstNonEmpty(firstValue(values, "sort"), "price_asc"))
	if sortValue != "price_asc" && sortValue != "price_desc" && sortValue != "days_asc" && sortValue != "days_desc" {
		sortValue = "price_asc"
	}
	return Query{
		PricePerPerson: parseOptionalInt(firstValue(values, "pricePerPerson")),
		MinPrice:       parseOptionalInt(firstValue(values, "minPrice")),
		MaxPrice:       parseOptionalInt(firstValue(values, "maxPrice")),
		Categories:     normalizeCategories(values["category"]),
		City:           norm(strings.TrimSpace(firstValue(values, "city"))),
		Query:          strings.TrimSpace(firstValue(values, "q")),
		Sort:           sortValue,
		Limit:          clampInt(parseIntDefault(firstValue(values, "limit"), 50), 1, 200),
		Offset:         maxInt(parseIntDefault(firstValue(values, "offset"), 0), 0),
	}
}

func buildCatalogIndex(tours []Tour) *catalogIndex {
	index := &catalogIndex{
		compiled:      make([]compiledTour, len(tours)),
		allIndices:    make([]int, len(tours)),
		cityIndex:     map[string][]int{},
		categoryIndex: map[string][]int{},
		reviewByID:    map[string]int{},
		reviewByLink:  map[string]int{},
		stats: statsSnapshot{
			totalTours:     len(tours),
			categoryCounts: map[string]int{},
		},
	}

	regionCounts := map[string]int{}
	prices := make([]int, 0, len(tours))

	for idx, tour := range tours {
		index.allIndices[idx] = idx
		searchText := norm(strings.Join([]string{
			tour.Title,
			tour.City,
			tour.Region,
			tour.Description,
			tour.ReviewText,
		}, " "))
		cityNorm := norm(tour.City)
		if cityNorm == "" {
			cityNorm = norm(tour.Region)
		}
		categorySet := make(map[string]struct{}, len(tour.Categories))
		for _, category := range tour.Categories {
			categorySet[category] = struct{}{}
			index.categoryIndex[category] = append(index.categoryIndex[category], idx)
			index.stats.categoryCounts[category]++
		}
		index.compiled[idx] = compiledTour{
			cityNorm:    cityNorm,
			titleNorm:   norm(tour.Title),
			searchText:  searchText,
			categorySet: categorySet,
		}
		if cityNorm != "" {
			index.cityIndex[cityNorm] = append(index.cityIndex[cityNorm], idx)
		}
		if tour.ID != "" {
			index.reviewByID[tour.ID] = idx
		}
		if tour.Link != "" {
			index.reviewByLink[tour.Link] = idx
		}
		regionCounts[tour.Region]++
		prices = append(prices, tour.PricePerPerson)
	}

	sort.Ints(prices)
	if len(prices) > 0 {
		minValue := prices[0]
		maxValue := prices[len(prices)-1]
		avgValue := int(math.Round(float64(sumInts(prices)) / float64(len(prices))))
		index.stats.priceMin = &minValue
		index.stats.priceMax = &maxValue
		index.stats.priceAvg = &avgValue
	}

	topRegions := make([]regionStat, 0, len(regionCounts))
	for region, count := range regionCounts {
		topRegions = append(topRegions, regionStat{Region: region, Count: count})
	}
	sort.Slice(topRegions, func(i, j int) bool {
		if topRegions[i].Count == topRegions[j].Count {
			return topRegions[i].Region < topRegions[j].Region
		}
		return topRegions[i].Count > topRegions[j].Count
	})
	if len(topRegions) > 8 {
		topRegions = topRegions[:8]
	}
	index.stats.topRegions = topRegions

	index.allByPriceAsc = append([]int(nil), index.allIndices...)
	sort.Slice(index.allByPriceAsc, func(i, j int) bool {
		return compareTours(tours[index.allByPriceAsc[i]], tours[index.allByPriceAsc[j]], "price_asc")
	})
	index.allByPriceDesc = append([]int(nil), index.allIndices...)
	sort.Slice(index.allByPriceDesc, func(i, j int) bool {
		return compareTours(tours[index.allByPriceDesc[i]], tours[index.allByPriceDesc[j]], "price_desc")
	})
	index.allByDaysAsc = append([]int(nil), index.allIndices...)
	sort.Slice(index.allByDaysAsc, func(i, j int) bool {
		return compareTours(tours[index.allByDaysAsc[i]], tours[index.allByDaysAsc[j]], "days_asc")
	})
	index.allByDaysDesc = append([]int(nil), index.allIndices...)
	sort.Slice(index.allByDaysDesc, func(i, j int) bool {
		return compareTours(tours[index.allByDaysDesc[i]], tours[index.allByDaysDesc[j]], "days_desc")
	})

	return index
}

func (app *App) filteredIndices(index *catalogIndex, tours []Tour, query Query, generation uint64) []int {
	if index == nil || len(tours) == 0 {
		return []int{}
	}

	if ids, ok := app.getCachedQueryResult(queryCacheKey(query, generation)); ok {
		return ids
	}

	candidates := candidateIndices(index, query)
	if len(candidates) == 0 {
		app.storeCachedQueryResult(queryCacheKey(query, generation), []int{})
		return []int{}
	}

	queryNeedles := tokenize(norm(query.Query))
	filtered := make([]int, 0, len(candidates))
	for _, idx := range candidates {
		tour := tours[idx]
		compiled := index.compiled[idx]
		if query.PricePerPerson != nil && tour.PricePerPerson != *query.PricePerPerson {
			continue
		}
		if query.MinPrice != nil && tour.PricePerPerson < *query.MinPrice {
			continue
		}
		if query.MaxPrice != nil && tour.PricePerPerson > *query.MaxPrice {
			continue
		}
		if query.City != "" && compiled.cityNorm != query.City {
			continue
		}
		if len(query.Categories) > 0 && !compiledHasCategories(compiled, query.Categories) {
			continue
		}
		if len(queryNeedles) > 0 && !compiledMatchesQuery(compiled, queryNeedles) {
			continue
		}
		filtered = append(filtered, idx)
	}

	if len(filtered) > 1 {
		sort.Slice(filtered, func(i, j int) bool {
			return compareTours(tours[filtered[i]], tours[filtered[j]], query.Sort)
		})
	}
	app.storeCachedQueryResult(queryCacheKey(query, generation), filtered)
	return append([]int(nil), filtered...)
}

func candidateIndices(index *catalogIndex, query Query) []int {
	if len(index.allIndices) == 0 {
		return nil
	}
	if queryHasNoFilters(query) {
		return defaultSortedIndices(index, query.Sort)
	}

	lists := make([][]int, 0, len(query.Categories)+1)
	if query.City != "" {
		lists = append(lists, index.cityIndex[query.City])
	}
	for _, category := range query.Categories {
		list, ok := index.categoryIndex[category]
		if !ok {
			return nil
		}
		lists = append(lists, list)
	}
	if len(lists) == 0 {
		return append([]int(nil), index.allIndices...)
	}

	sort.Slice(lists, func(i, j int) bool {
		return len(lists[i]) < len(lists[j])
	})
	candidates := append([]int(nil), lists[0]...)
	for _, list := range lists[1:] {
		candidates = intersectSortedIDs(candidates, list)
		if len(candidates) == 0 {
			return nil
		}
	}
	return candidates
}

func defaultSortedIndices(index *catalogIndex, sortKey string) []int {
	switch sortKey {
	case "price_desc":
		return append([]int(nil), index.allByPriceDesc...)
	case "days_asc":
		return append([]int(nil), index.allByDaysAsc...)
	case "days_desc":
		return append([]int(nil), index.allByDaysDesc...)
	default:
		return append([]int(nil), index.allByPriceAsc...)
	}
}

func queryHasNoFilters(query Query) bool {
	return query.PricePerPerson == nil &&
		query.MinPrice == nil &&
		query.MaxPrice == nil &&
		query.City == "" &&
		query.Query == "" &&
		len(query.Categories) == 0
}

func intersectSortedIDs(left []int, right []int) []int {
	result := make([]int, 0, minInt(len(left), len(right)))
	i := 0
	j := 0
	for i < len(left) && j < len(right) {
		switch {
		case left[i] == right[j]:
			result = append(result, left[i])
			i++
			j++
		case left[i] < right[j]:
			i++
		default:
			j++
		}
	}
	return result
}

func compiledMatchesQuery(compiled compiledTour, needles []string) bool {
	for _, needle := range needles {
		if !strings.Contains(compiled.searchText, needle) {
			return false
		}
	}
	return true
}

func compiledHasCategories(compiled compiledTour, required []string) bool {
	for _, item := range required {
		if _, ok := compiled.categorySet[item]; !ok {
			return false
		}
	}
	return true
}

func compareTours(left Tour, right Tour, sortKey string) bool {
	switch sortKey {
	case "price_desc":
		if left.PricePerPerson == right.PricePerPerson {
			return left.Title < right.Title
		}
		return left.PricePerPerson > right.PricePerPerson
	case "days_asc":
		if left.Days == right.Days {
			if left.PricePerPerson == right.PricePerPerson {
				return left.Title < right.Title
			}
			return left.PricePerPerson < right.PricePerPerson
		}
		return left.Days < right.Days
	case "days_desc":
		if left.Days == right.Days {
			if left.PricePerPerson == right.PricePerPerson {
				return left.Title < right.Title
			}
			return left.PricePerPerson < right.PricePerPerson
		}
		return left.Days > right.Days
	default:
		if left.PricePerPerson == right.PricePerPerson {
			return left.Title < right.Title
		}
		return left.PricePerPerson < right.PricePerPerson
	}
}

func queryCacheKey(query Query, generation uint64) string {
	var builder strings.Builder
	builder.Grow(128)
	builder.WriteString(strconv.FormatUint(generation, 10))
	builder.WriteString("|pp=")
	builder.WriteString(optionalIntKey(query.PricePerPerson))
	builder.WriteString("|min=")
	builder.WriteString(optionalIntKey(query.MinPrice))
	builder.WriteString("|max=")
	builder.WriteString(optionalIntKey(query.MaxPrice))
	builder.WriteString("|city=")
	builder.WriteString(query.City)
	builder.WriteString("|q=")
	builder.WriteString(norm(query.Query))
	builder.WriteString("|sort=")
	builder.WriteString(query.Sort)
	builder.WriteString("|cat=")
	builder.WriteString(strings.Join(query.Categories, ","))
	return builder.String()
}

func optionalIntKey(value *int) string {
	if value == nil {
		return ""
	}
	return strconv.Itoa(*value)
}

func (app *App) getCachedQueryResult(key string) ([]int, bool) {
	app.queryMu.Lock()
	ids, ok := app.queryCache[key]
	if ok {
		app.queryCacheHits++
	}
	if !ok {
		app.queryCacheMisses++
	}
	app.queryMu.Unlock()
	if !ok {
		return nil, false
	}
	return append([]int(nil), ids...), true
}

func (app *App) storeCachedQueryResult(key string, ids []int) {
	app.queryMu.Lock()
	if len(app.queryCache) >= 256 {
		clear(app.queryCache)
	}
	app.queryCache[key] = append([]int(nil), ids...)
	app.queryMu.Unlock()
}

func (app *App) queryCacheMetrics() (int, int, int) {
	app.queryMu.RLock()
	size := len(app.queryCache)
	hits := app.queryCacheHits
	misses := app.queryCacheMisses
	app.queryMu.RUnlock()
	return hits, misses, size
}

func tokenize(value string) []string {
	parts := strings.FieldsFunc(value, func(r rune) bool {
		return !(r >= '0' && r <= '9' || r >= 'a' && r <= 'z' || r >= 'а' && r <= 'я' || r == 'ё')
	})
	result := make([]string, 0, len(parts))
	for _, part := range parts {
		part = strings.TrimSpace(part)
		if part != "" {
			result = append(result, part)
		}
	}
	return result
}

func hasTokenPrefix(title string, prefix string) bool {
	for _, token := range tokenize(title) {
		if strings.HasPrefix(token, prefix) {
			return true
		}
	}
	return false
}

func categoriesCatalog() []Category {
	return []Category{
		{ID: "with_hotel", Label: "С отелем", Description: "Размещение в отеле включено"},
		{ID: "without_hotel", Label: "Без отеля", Description: "Только программа отдыха без отеля"},
		{ID: "with_pool", Label: "С бассейном", Description: "Есть бассейн на территории"},
		{ID: "without_pool", Label: "Без бассейна", Description: "Без бассейна на территории"},
		{ID: "mountains", Label: "Горы", Description: "Горные маршруты и локации"},
		{ID: "forest", Label: "Лес", Description: "Лесные направления и эко-туризм"},
		{ID: "recreation_base", Label: "Базы отдыха", Description: "Отдых на базах и турбазах"},
		{ID: "waterfront", Label: "У воды", Description: "Рядом море, озеро или река"},
		{ID: "family", Label: "Семейный", Description: "Подходит для поездки с детьми"},
		{ID: "all_inclusive", Label: "Все включено", Description: "Питание и часть активностей включены"},
	}
}

func normalizeCategories(values []string) []string {
	valid := map[string]struct{}{
		"with_hotel": {}, "without_hotel": {}, "with_pool": {}, "without_pool": {},
		"mountains": {}, "forest": {}, "recreation_base": {}, "waterfront": {},
		"family": {}, "all_inclusive": {},
	}
	seen := map[string]struct{}{}
	result := []string{}
	for _, item := range values {
		item = strings.TrimSpace(item)
		if _, ok := valid[item]; !ok {
			continue
		}
		if _, ok := seen[item]; ok {
			continue
		}
		seen[item] = struct{}{}
		result = append(result, item)
	}
	sort.Strings(result)
	return result
}

func norm(value string) string {
	return strings.ToLower(strings.TrimSpace(value))
}

func parseOptionalInt(raw string) *int {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return nil
	}
	value, err := strconv.Atoi(raw)
	if err != nil {
		return nil
	}
	return &value
}

func parseIntDefault(raw string, fallback int) int {
	value, err := strconv.Atoi(strings.TrimSpace(raw))
	if err != nil {
		return fallback
	}
	return value
}

func clampInt(value, minValue, maxValue int) int {
	if value < minValue {
		return minValue
	}
	if value > maxValue {
		return maxValue
	}
	return value
}

func maxInt(values ...int) int {
	best := values[0]
	for _, value := range values[1:] {
		if value > best {
			best = value
		}
	}
	return best
}

func minInt(left, right int) int {
	if left < right {
		return left
	}
	return right
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return value
		}
	}
	return ""
}

func firstValue(values map[string][]string, key string) string {
	items := values[key]
	if len(items) == 0 {
		return ""
	}
	return items[0]
}

func sumInts(values []int) int {
	total := 0
	for _, value := range values {
		total += value
	}
	return total
}

func derefInt(value *int) any {
	if value == nil {
		return nil
	}
	return *value
}

func zeroToNilFloat(value float64) any {
	if value <= 0 {
		return nil
	}
	return value
}

func nonZeroInt(value, fallback int) int {
	if value > 0 {
		return value
	}
	return fallback
}

func toISO(value time.Time) string {
	if value.IsZero() {
		return ""
	}
	return value.UTC().Format(time.RFC3339)
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	body, err := json.Marshal(payload)
	if err != nil {
		http.Error(w, "json error", http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_, _ = w.Write(body)
}

func methodNotAllowed(w http.ResponseWriter) {
	writeJSON(w, http.StatusMethodNotAllowed, map[string]any{"ok": false, "message": "Method not allowed"})
}

func decodeJSON(r *http.Request, target any) error {
	defer r.Body.Close()
	return json.NewDecoder(r.Body).Decode(target)
}

func validateCredentials(username, password string) error {
	if strings.TrimSpace(username) == "" || strings.TrimSpace(password) == "" {
		return errors.New("Логин и пароль обязательны.")
	}
	if len(username) < 3 {
		return errors.New("Логин должен быть не короче 3 символов.")
	}
	if len(password) < 8 {
		return errors.New("Пароль должен быть не короче 8 символов.")
	}
	return nil
}

func hashPassword(salt, password string) string {
	sum := sha256.Sum256([]byte(salt + ":" + password))
	result := sum[:]
	for i := 0; i < 12000; i++ {
		next := sha256.Sum256(append(result, byte(i%251)))
		result = next[:]
	}
	return hex.EncodeToString(result)
}

func randomToken(size int) string {
	buffer := make([]byte, size)
	if _, err := rand.Read(buffer); err != nil {
		return fmt.Sprintf("%d", time.Now().UnixNano())
	}
	return hex.EncodeToString(buffer)
}

func (app *App) signValue(value string) string {
	mac := hmac.New(sha256.New, app.sessionSecret)
	mac.Write([]byte(value))
	return hex.EncodeToString(mac.Sum(nil))
}

func (app *App) createSession(w http.ResponseWriter, username string) {
	token := randomToken(24)
	signature := app.signValue(token)
	app.sessionMu.Lock()
	app.sessions[token] = username
	app.sessionMu.Unlock()
	http.SetCookie(w, &http.Cookie{
		Name:     "putevka_session",
		Value:    token + "." + signature,
		Path:     "/",
		HttpOnly: true,
		SameSite: http.SameSiteLaxMode,
	})
}

func (app *App) currentUsername(r *http.Request) (string, bool) {
	cookie, err := r.Cookie("putevka_session")
	if err != nil || strings.TrimSpace(cookie.Value) == "" {
		return "", false
	}
	parts := strings.SplitN(cookie.Value, ".", 2)
	if len(parts) != 2 {
		return "", false
	}
	if app.signValue(parts[0]) != parts[1] {
		return "", false
	}
	app.sessionMu.RLock()
	username, ok := app.sessions[parts[0]]
	app.sessionMu.RUnlock()
	return username, ok
}

func (app *App) destroySession(w http.ResponseWriter, r *http.Request) {
	cookie, err := r.Cookie("putevka_session")
	if err == nil {
		parts := strings.SplitN(cookie.Value, ".", 2)
		if len(parts) > 0 {
			app.sessionMu.Lock()
			delete(app.sessions, parts[0])
			app.sessionMu.Unlock()
		}
	}
	http.SetCookie(w, &http.Cookie{
		Name:     "putevka_session",
		Value:    "",
		Path:     "/",
		MaxAge:   -1,
		HttpOnly: true,
		SameSite: http.SameSiteLaxMode,
	})
}
