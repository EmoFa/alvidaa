package main

import (
	"crypto/md5"
	"encoding/hex"
	"encoding/json"
	"io"
	"log"
	"mime"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"time"
)

type Handler struct {
	b       *Bridge
	assets  string
	iconDir string
}

func NewHandler(b *Bridge, assets, iconDir string) *Handler {
	return &Handler{b: b, assets: assets, iconDir: iconDir}
}

func (h *Handler) cors(w http.ResponseWriter) {
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
	w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
	w.Header().Set("Cache-Control", "no-store")
}

func (h *Handler) json(w http.ResponseWriter, v any) {
	h.cors(w)
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(v)
}

func (h *Handler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodOptions {
		h.cors(w)
		w.WriteHeader(http.StatusNoContent)
		return
	}

	switch {
	case r.URL.Path == "/ws":
		h.serveWS(w, r)
		return
	case strings.HasPrefix(r.URL.Path, "/icon/"):
		h.serveIcon(w, r, strings.TrimPrefix(r.URL.Path, "/icon/"))
		return
	case r.URL.Path == "/api/state":
		h.b.stateMu.RLock()
		st, _ := h.b.state["statetype"].(string)
		h.b.stateMu.RUnlock()
		h.json(w, map[string]any{"ok": true, "state": st})
		return
	case r.URL.Path == "/api/health":
		connected := h.b.mc != nil && h.b.mc.Connected()
		h.json(w, map[string]any{"ok": true, "version": version, "mqtt": connected, "clients": h.b.hub.Count()})
		return
	case r.URL.Path == "/api/launch":
		h.json(w, h.b.launch(r.URL.Query().Get("name")))
		return
	case r.URL.Path == "/api/source":
		h.json(w, h.b.switchSource(r.URL.Query().Get("id")))
		return
	case r.URL.Path == "/api/open":
		url := r.URL.Query().Get("url")
		if !strings.HasPrefix(url, "http") {
			h.json(w, map[string]any{"ok": false, "error": "http url required"})
			return
		}
		h.b.call("ui_service", "launchapp", map[string]any{
			"appId": "vidaa-recon", "name": "Recon",
			"url": url, "urlType": "1", "storeType": "custom",
		})
		h.json(w, map[string]any{"ok": true, "opened": url})
		return
	case r.URL.Path == "/api/recon":
		h.recon(w, r)
		return
	case r.URL.Path == "/api/probe":
		h.probe(w, r)
		return
	case r.URL.Path == "/api/debug":
		h.serveDebug(w, r)
		return
	case strings.HasPrefix(r.URL.Path, "/api/doom"):
		h.json(w, map[string]any{"ok": false, "error": "doom is not supported by the on-TV daemon"})
		return
	}

	h.serveStatic(w, r)
}

func (h *Handler) serveWS(w http.ResponseWriter, r *http.Request) {
	// Cobalt's page runs from file://, so the Origin header is "null" — the
	// listener is loopback-only, which is the actual access control here.
	conn, err := upgrade(w, r)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	h.b.hub.Add(conn)
	defer func() {
		h.b.hub.Remove(conn)
		conn.Close()
	}()
	log.Printf("ws: client connected from %s (%d open)", r.RemoteAddr, h.b.hub.Count())
	conn.SendText(mustJSON(h.b.snapshot()))

	for {
		raw, err := conn.ReadText()
		if err != nil {
			log.Printf("ws: client gone: %v", err)
			return
		}
		var m map[string]any
		if json.Unmarshal(raw, &m) != nil {
			continue
		}
		switch m["t"] {
		case "launch":
			name, _ := m["name"].(string)
			conn.SendText(mustJSON(h.b.launch(name)))
		case "source":
			id, _ := m["id"].(string)
			conn.SendText(mustJSON(h.b.switchSource(id)))
		}
	}
}

func mustJSON(v any) []byte {
	b, err := json.Marshal(v)
	if err != nil {
		return []byte(`{"t":"error"}`)
	}
	return b
}

func (h *Handler) serveIcon(w http.ResponseWriter, r *http.Request, appID string) {
	// Cache first: pre-staged icons (tools/push-icons.sh) must serve even when
	// the applist entry has no httpIcon URL at all (e.g. vidaa-recon).
	if data, ctype, err := h.cachedIcon(appID); err == nil {
		h.cors(w)
		w.Header().Set("Content-Type", ctype)
		w.Header().Set("Cache-Control", "max-age=604800")
		w.Write(data)
		return
	}
	var url string
	for _, a := range h.b.appsList() {
		if toStr(a["appId"]) == appID {
			url = iconURL(a)
			break
		}
	}
	if url == "" {
		http.NotFound(w, r)
		return
	}
	data, ctype, err := h.iconBytes(appID, url)
	if err != nil {
		http.NotFound(w, r)
		return
	}
	h.cors(w)
	w.Header().Set("Content-Type", ctype)
	w.Header().Set("Cache-Control", "max-age=604800")
	w.Write(data)
}

// safeAppID mirrors the cache filename transform: alphanumerics only.
func safeAppID(appID string) string {
	safe := strings.Map(func(r rune) rune {
		if r >= 'a' && r <= 'z' || r >= 'A' && r <= 'Z' || r >= '0' && r <= '9' {
			return r
		}
		return -1
	}, appID)
	if safe == "" {
		safe = "x"
	}
	return safe
}

// cachedIcon reads a pre-staged icon from the cache directory.
func (h *Handler) cachedIcon(appID string) ([]byte, string, error) {
	safe := safeAppID(appID)
	data, err := os.ReadFile(filepath.Join(h.iconDir, safe+".img"))
	if err != nil {
		return nil, "", err
	}
	t, err := os.ReadFile(filepath.Join(h.iconDir, safe+".type"))
	if err != nil {
		return nil, "", err
	}
	return data, strings.TrimSpace(string(t)), nil
}

func (h *Handler) iconBytes(appID, url string) ([]byte, string, error) {
	if data, ctype, err := h.cachedIcon(appID); err == nil {
		return data, ctype, nil
	}
	safe := safeAppID(appID)
	dataPath := filepath.Join(h.iconDir, safe+".img")
	typePath := filepath.Join(h.iconDir, safe+".type")
	client := &http.Client{Timeout: 8 * time.Second}
	resp, err := client.Get(url)
	if err != nil {
		return nil, "", err
	}
	defer resp.Body.Close()
	data, err := io.ReadAll(io.LimitReader(resp.Body, 4<<20))
	if err != nil {
		return nil, "", err
	}
	ctype := resp.Header.Get("Content-Type")
	if i := strings.Index(ctype, ";"); i >= 0 {
		ctype = ctype[:i]
	}
	if ctype == "" {
		ctype = "image/png"
	}
	os.MkdirAll(h.iconDir, 0o755)
	os.WriteFile(dataPath, data, 0o644)
	os.WriteFile(typePath, []byte(ctype), 0o644)
	return data, ctype, nil
}

func (h *Handler) serveStatic(w http.ResponseWriter, r *http.Request) {
	clean := filepath.Clean("/" + r.URL.Path)
	name := clean
	if name == "/" {
		name = "/index.html"
	}
	full := filepath.Join(h.assets, filepath.FromSlash(name))
	if !strings.HasPrefix(full, filepath.Clean(h.assets)+string(os.PathSeparator)) {
		http.NotFound(w, r)
		return
	}
	st, err := os.Stat(full)
	if err == nil && st.IsDir() {
		// Directory URLs (e.g. /next/) serve that directory's index.html.
		full = filepath.Join(full, "index.html")
		st, err = os.Stat(full)
	}
	if err != nil || st.IsDir() {
		http.NotFound(w, r)
		return
	}
	ctype := mime.TypeByExtension(filepath.Ext(full))
	if ctype == "" {
		ctype = "application/octet-stream"
	}
	h.cors(w)
	w.Header().Set("Content-Type", ctype)
	// ServeContent instead of ServeFile: ServeFile redirects any request
	// whose path ends in /index.html to "./", which 404s because the
	// directory itself has no handler (broke /next/index.html staging).
	f, err := os.Open(full)
	if err != nil {
		http.NotFound(w, r)
		return
	}
	defer f.Close()
	http.ServeContent(w, r, filepath.Base(full), st.ModTime(), f)
}

func (h *Handler) recon(w http.ResponseWriter, r *http.Request) {
	path := filepath.Join(h.b.keysDir, "recon-report.json")
	if r.Method == http.MethodPost {
		var data any
		if err := json.NewDecoder(r.Body).Decode(&data); err != nil {
			h.json(w, map[string]any{"ok": false, "error": err.Error()})
			return
		}
		b, _ := json.MarshalIndent(data, "", "  ")
		if err := os.WriteFile(path, b, 0o644); err != nil {
			h.json(w, map[string]any{"ok": false, "error": err.Error()})
			return
		}
		h.json(w, map[string]any{"ok": true, "bytes": len(b)})
		return
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		h.json(w, map[string]any{"ok": false, "error": "no recon report yet"})
		return
	}
	h.cors(w)
	w.Header().Set("Content-Type", "application/json")
	w.Write(raw)
}

func (h *Handler) probe(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.NotFound(w, r)
		return
	}
	body, _ := io.ReadAll(io.LimitReader(r.Body, 1<<20))
	path := filepath.Join(h.b.keysDir, "probe-report.jsonl")
	f, err := os.OpenFile(path, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		h.json(w, map[string]any{"ok": false, "error": err.Error()})
		return
	}
	defer f.Close()
	f.Write(append(body, '\n'))
	h.json(w, map[string]any{"ok": true})
}

func toStr(v any) string {
	if s, ok := v.(string); ok {
		return s
	}
	return ""
}

// serveDebug backs the Root Status page: everything the supervisor used to
// guess from pid deltas and log tails, in one read-only JSON document.
func (h *Handler) serveDebug(w http.ResponseWriter, r *http.Request) {
	cfg := h.b.config()

	binaryMd5 := ""
	if exe, err := os.Readlink("/proc/self/exe"); err == nil {
		if b, err := os.ReadFile(exe); err == nil {
			sum := md5.Sum(b)
			binaryMd5 = hex.EncodeToString(sum[:])
		}
	}

	connected := h.b.mc != nil && h.b.mc.Connected()
	clientID := ""
	if h.b.mc != nil {
		clientID = h.b.mc.ClientID
	}
	tokenLoaded := false
	if b, err := os.ReadFile(h.b.tokens); err == nil {
		var t struct {
			AccessToken string `json:"accessToken"`
		}
		if json.Unmarshal(b, &t) == nil && t.AccessToken != "" {
			tokenLoaded = true
		}
	}

	hookVersion, killSwitch, watchdogAlive := hookState()

	ifaces := map[string][]string{}
	if list, err := net.Interfaces(); err == nil {
		for _, ifc := range list {
			addrs, err := ifc.Addrs()
			if err != nil || len(addrs) == 0 {
				continue
			}
			var ips []string
			for _, a := range addrs {
				ips = append(ips, a.String())
			}
			ifaces[ifc.Name] = ips
		}
	}

	h.json(w, map[string]any{
		"bridge": map[string]any{
			"version":   version,
			"startedAt": h.b.started.UTC().Format(time.RFC3339),
			"uptimeSec": int(time.Since(h.b.started).Seconds()),
			"pid":       os.Getpid(),
			"binaryMd5": binaryMd5,
		},
		"mqtt": map[string]any{
			"connected":   connected,
			"clientId":    clientID,
			"tokenLoaded": tokenLoaded,
		},
		"hook": map[string]any{
			"version":       hookVersion,
			"killSwitch":    killSwitch,
			"watchdogAlive": watchdogAlive,
		},
		"tv": map[string]any{
			"model":      cfg.Tv["model"],
			"firmware":   cfg.Tv["firmware"],
			"soc":        cfg.Tv["soc"],
			"uptimeSec":  tvUptimeSec(),
			"interfaces": ifaces,
		},
		"clients": h.b.hub.Count(),
		"ok":      true,
	})
}

// hookState reads the hook version, kill-switch and watchdog liveness from
// the filesystem. The bridge runs as root via the hook, so these are
// readable; every failure degrades to a zero-value rather than an error.
func hookState() (version string, killSwitch, watchdogAlive bool) {
	for _, f := range []string{"/var/local/hook.off", "/var/local/otaTest.off"} {
		if _, err := os.Stat(f); err == nil {
			killSwitch = true
		}
	}
	if b, err := os.ReadFile("/var/local/otaTest.sh"); err == nil {
		if m := regexp.MustCompile(`# alvidaa root hook (v\d+)`).FindSubmatch(b); m != nil {
			version = string(m[1])
		}
	}
	if entries, err := os.ReadDir("/proc"); err == nil {
		for _, e := range entries {
			if !isDigitName(e.Name()) {
				continue
			}
			if cmd, err := os.ReadFile(filepath.Join("/proc", e.Name(), "cmdline")); err == nil && strings.Contains(string(cmd), "otaTest.sh") {
				watchdogAlive = true
				break
			}
		}
	}
	return
}

func isDigitName(s string) bool {
	if s == "" {
		return false
	}
	for _, c := range s {
		if c < '0' || c > '9' {
			return false
		}
	}
	return true
}

func tvUptimeSec() float64 {
	b, err := os.ReadFile("/proc/uptime")
	if err != nil {
		return 0
	}
	f, _ := strconv.ParseFloat(strings.Fields(string(b))[0], 64)
	return f
}
