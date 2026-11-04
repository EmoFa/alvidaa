package main

import (
	"encoding/json"
	"io"
	"log"
	"mime"
	"net/http"
	"os"
	"path/filepath"
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
		h.json(w, map[string]any{"ok": true, "mqtt": connected, "clients": h.b.hub.Count()})
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

func (h *Handler) iconBytes(appID, url string) ([]byte, string, error) {
	safe := strings.Map(func(r rune) rune {
		if r >= 'a' && r <= 'z' || r >= 'A' && r <= 'Z' || r >= '0' && r <= '9' {
			return r
		}
		return -1
	}, appID)
	if safe == "" {
		safe = "x"
	}
	dataPath := filepath.Join(h.iconDir, safe+".img")
	typePath := filepath.Join(h.iconDir, safe+".type")
	if data, err := os.ReadFile(dataPath); err == nil {
		if t, err := os.ReadFile(typePath); err == nil {
			return data, strings.TrimSpace(string(t)), nil
		}
	}
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
	http.ServeFile(w, r, full)
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
