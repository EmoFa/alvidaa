package main

import (
	"context"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"log"
	"strings"
	"sync"
	"time"
)

const legacyDevice = "VIDAALAUNCHER$normal"

type inboxMsg struct {
	suffix  string
	payload any
}

// Bridge owns the single MQTT session and the state the overlay renders.
type Bridge struct {
	addr    string
	port    int
	tlsConf *tls.Config
	keysDir string
	tokens  string // tokens.json path
	cfgPath string

	mc      *Client
	hub     *Hub
	started time.Time // process start — surfaces "last restart" on /api/debug

	askMu sync.Mutex
	inbox chan inboxMsg

	stateMu sync.RWMutex
	state   map[string]any

	cacheMu sync.Mutex
	apps    []map[string]any
	appsAt  time.Time
	sources []map[string]any

	launchMu   sync.Mutex
	lastLaunch time.Time
}

func NewBridge(addr string, port int, tlsConf *tls.Config, keysDir, tokensPath, cfgPath string) *Bridge {
	return &Bridge{
		addr:    addr,
		port:    port,
		tlsConf: tlsConf,
		keysDir: keysDir,
		tokens:  tokensPath,
		cfgPath: cfgPath,
		hub:     NewHub(),
		inbox:   make(chan inboxMsg, 64),
		started: time.Now(),
	}
}

func (b *Bridge) config() Config { return loadConfig(b.cfgPath) }

func (b *Bridge) device() (string, string, string) {
	if t := loadTokens(b.tokens); t != nil {
		return str(t, "_client_id"), str(t, "_username"), str(t, "accesstoken")
	}
	return legacyDevice, "hisenseservice", "multimqttservice"
}

func (b *Bridge) Start(ctx context.Context) {
	id, user, pass := b.device()
	b.mc = NewClient(b.addr, b.tlsConf, id, user, pass)
	b.mc.OnConnect = b.onConnect
	b.mc.OnMessage = b.onMessage
	b.mc.OnReject = func(rc byte) bool {
		log.Printf("mqtt: rejected (rc=%d) — refreshing tokens", rc)
		if err := b.refreshTokens(ctx); err != nil {
			log.Printf("mqtt: token refresh failed: %v", err)
			return false
		}
		t := loadTokens(b.tokens)
		b.mc.SetCreds(str(t, "_username"), str(t, "accesstoken"))
		return true
	}
	go b.mc.Run(ctx)
}

func (b *Bridge) onConnect(c *Client) {
	base := "/remoteapp/mobile/" + c.ClientID + "/"
	err := c.Subscribe([]string{
		base + "ui_service/data/state",
		base + "ui_service/data/gettvstate",
		base + "ui_service/data/sourcelist",
		base + "ui_service/data/applist",
		base + "ui_service/data/launchapp",
		base + "platform_service/data/tokenissuance",
		base + "platform_service/data/gettoken",
		"/remoteapp/mobile/broadcast/ui_service/state",
	})
	if err != nil {
		log.Printf("mqtt: subscribe: %v", err)
		return
	}
	go b.hub.Broadcast(b.snapshot())
}

func (b *Bridge) onMessage(topic string, payload []byte) {
	suffix := topic
	if i := strings.LastIndex(topic, "/"); i >= 0 {
		suffix = topic[i+1:]
	}
	var p any
	if len(payload) > 0 {
		if err := json.Unmarshal(payload, &p); err != nil {
			p = string(payload)
		}
	}
	select {
	case b.inbox <- inboxMsg{suffix: suffix, payload: p}:
	default:
	}

	m, ok := p.(map[string]any)
	if !ok || (suffix != "state" && suffix != "gettvstate") {
		return
	}
	st, ok := m["statetype"].(string)
	if !ok {
		return
	}
	b.stateMu.Lock()
	b.state = m
	b.stateMu.Unlock()
	b.hub.Broadcast(map[string]any{"t": "tvstate", "state": st})
	if st == "remote_launcher" {
		go b.maybeBounceHome()
	}
}

func (b *Bridge) call(service, action string, payload any) error {
	var body []byte
	if payload != nil {
		if s, ok := payload.(string); ok {
			body = []byte(s)
		} else {
			var err error
			if body, err = json.Marshal(payload); err != nil {
				return err
			}
		}
	}
	topic := fmt.Sprintf("/remoteapp/tv/%s/%s/actions/%s", service, b.mc.ClientID, action)
	return b.mc.Publish(topic, body)
}

func (b *Bridge) drain() {
	for {
		select {
		case <-b.inbox:
		default:
			return
		}
	}
}

// ask publishes an action and waits for the first reply of the wanted shape.
func (b *Bridge) ask(service, action string, payload any, isList bool, timeout time.Duration) (any, error) {
	b.askMu.Lock()
	defer b.askMu.Unlock()
	b.drain()
	if err := b.call(service, action, payload); err != nil {
		return nil, err
	}
	deadline := time.After(timeout)
	for {
		select {
		case m := <-b.inbox:
			_, isSlice := m.payload.([]any)
			if isList == isSlice {
				return m.payload, nil
			}
		case <-deadline:
			return nil, fmt.Errorf("no answer for %s/%s", service, action)
		}
	}
}

func (b *Bridge) appsList() []map[string]any {
	b.cacheMu.Lock()
	fresh := b.apps == nil || time.Since(b.appsAt) > 60*time.Second
	b.cacheMu.Unlock()
	if fresh {
		if v, err := b.ask("ui_service", "applist", nil, true, 6*time.Second); err == nil {
			list := toMapList(v)
			b.cacheMu.Lock()
			if len(list) > 0 || b.apps == nil {
				b.apps, b.appsAt = list, time.Now()
			}
			b.cacheMu.Unlock()
		}
	}
	b.cacheMu.Lock()
	defer b.cacheMu.Unlock()
	return b.apps
}

func (b *Bridge) sourcesList() []map[string]any {
	if v, err := b.ask("ui_service", "sourcelist", nil, true, 6*time.Second); err == nil {
		if list := toMapList(v); len(list) > 0 || b.sources == nil {
			b.cacheMu.Lock()
			b.sources = list
			b.cacheMu.Unlock()
		}
	}
	b.cacheMu.Lock()
	defer b.cacheMu.Unlock()
	return b.sources
}

func toMapList(v any) []map[string]any {
	raw, ok := v.([]any)
	if !ok {
		return nil
	}
	out := make([]map[string]any, 0, len(raw))
	for _, item := range raw {
		if m, ok := item.(map[string]any); ok {
			out = append(out, m)
		}
	}
	return out
}

func iconURL(app map[string]any) string {
	raw, _ := app["httpIcon"].(string)
	const marker = "iconDownload"
	if strings.HasPrefix(raw, "data:image") && strings.Contains(raw, marker) {
		return strings.SplitN(raw, marker, 2)[1]
	}
	if strings.HasPrefix(raw, "http") {
		return raw
	}
	return ""
}

func (b *Bridge) visibleApps() []map[string]any {
	cfg := b.config()
	only := map[string]bool{}
	for _, o := range cfg.Only {
		if s := strings.TrimSpace(strings.ToLower(o)); s != "" {
			only[s] = true
		}
	}
	hidden := map[string]bool{}
	for _, h := range cfg.Hidden {
		hidden[strings.TrimSpace(strings.ToLower(h))] = true
	}
	rename := map[string]string{}
	for k, v := range cfg.Rename {
		rename[strings.ToLower(k)] = v
	}
	out := []map[string]any{}
	for _, a := range b.appsList() {
		name, _ := a["name"].(string)
		if name == "" {
			continue
		}
		key := strings.ToLower(strings.TrimSpace(name))
		if len(only) > 0 && !only[key] {
			continue
		}
		if len(only) == 0 && hidden[key] {
			continue
		}
		entry := map[string]any{"name": name}
		if r, ok := rename[key]; ok {
			entry["name"] = r
		}
		// appId is what the CLI and any scripting consumer needs; the page
		// only reads name and icon, so this is additive.
		if id, ok := a["appId"]; ok {
			entry["appId"] = id
		}
		if iconURL(a) != "" {
			entry["icon"] = fmt.Sprintf("/icon/%v", a["appId"])
		}
		out = append(out, entry)
	}
	return out
}

func (b *Bridge) visibleSources() []map[string]any {
	cfg := b.config()
	inputs := map[string]Input{}
	for k, v := range cfg.Inputs {
		inputs[strings.ToLower(k)] = v
	}
	out := []map[string]any{}
	for _, s := range b.sourcesList() {
		name, _ := s["sourcename"].(string)
		over := inputs[strings.ToLower(name)]
		display, _ := s["displayname"].(string)
		// displayname2 is what the TV reports for the device actually on the
		// port ("PlayStation 5", "Fire TV Stick") via HDMI device discovery.
		// Prefer it over the port label, then a config override wins over both.
		device, _ := s["displayname2"].(string)
		if strings.TrimSpace(device) != "" {
			display = device
		}
		if over.Name != "" {
			display = over.Name
		}
		if display == "" {
			display = name
		}
		sig := s["is_signal"] == "1" || s["has_signal"] == "1"
		out = append(out, map[string]any{
			"id":     s["sourceid"],
			"name":   display,
			"glyph":  over.Glyph,
			"signal": sig,
		})
	}
	return out
}

func (b *Bridge) launch(name string) map[string]any {
	want := strings.ToLower(strings.TrimSpace(name))
	apps := b.appsList()
	var app map[string]any
	for _, a := range apps {
		if strings.ToLower(fmt.Sprint(a["name"])) == want {
			app = a
			break
		}
	}
	if app == nil {
		for _, a := range apps {
			if strings.Contains(strings.ToLower(fmt.Sprint(a["name"])), want) {
				app = a
				break
			}
		}
	}
	if app == nil {
		return map[string]any{"ok": false, "error": "app not found: " + name}
	}
	b.call("ui_service", "launchapp", appPayload(app))
	return map[string]any{"ok": true, "launched": app["name"]}
}

func appPayload(app map[string]any) map[string]any {
	out := map[string]any{}
	for _, k := range []string{"appId", "name", "url", "urlType", "storeType"} {
		if v, ok := app[k]; ok {
			out[k] = v
		}
	}
	return out
}

func (b *Bridge) switchSource(id string) map[string]any {
	for _, s := range b.sourcesList() {
		sid := fmt.Sprint(s["sourceid"])
		name := strings.ToLower(fmt.Sprint(s["sourcename"]))
		if sid == id || name == strings.ToLower(id) {
			b.call("ui_service", "changesource", s)
			return map[string]any{"ok": true, "switched": s["displayname"]}
		}
	}
	return map[string]any{"ok": false, "error": "source not found: " + id}
}

func (b *Bridge) snapshot() map[string]any {
	cfg := b.config()
	b.stateMu.RLock()
	stateType, _ := b.state["statetype"].(string)
	b.stateMu.RUnlock()

	out := map[string]any{
		"t":          "hello",
		"state":      stateType,
		"autoSwitch": cfg.AutoSwitch,
		// This bridge is the on-TV home lane: the launcher web app is
		// installed by construction (the watcher launches it), so the page
		// must not offer INSTALL AS APP.
		"installed": true,
		"shortcuts": validShortcuts(cfg.Shortcuts),
		"favorites": cfg.Favorites,
	}
	apps := b.visibleApps()
	out["apps"] = apps
	out["sources"] = b.visibleSources()
	return out
}

func validShortcuts(in []Shortcut) []map[string]any {
	out := []map[string]any{}
	for _, s := range in {
		if s.Name != "" && s.URL != "" {
			out = append(out, map[string]any{"name": s.Name, "url": s.URL})
		}
	}
	return out
}

func (b *Bridge) maybeBounceHome() {
	cfg := b.config()
	if !cfg.Watcher.Enabled {
		return
	}
	b.stateMu.RLock()
	st, _ := b.state["statetype"].(string)
	b.stateMu.RUnlock()
	if st != "remote_launcher" {
		return
	}
	cd := time.Duration(cfg.Watcher.Cooldown) * time.Second
	b.launchMu.Lock()
	if time.Since(b.lastLaunch) < cd {
		b.launchMu.Unlock()
		return
	}
	b.lastLaunch = time.Now()
	b.launchMu.Unlock()
	log.Printf("watcher: VIDAA home detected -> %v", b.launchHome(cfg.Watcher.App))
}

func (b *Bridge) launchHome(name string) map[string]any {
	apps := b.appsList()
	var app map[string]any
	// The launcher's own app entry wins by IDENTITY, not by URL. URL matching
	// alone is not enough: any other app repointed at the bridge port (a
	// diagnostics page, a second tile) would otherwise be launched instead.
	// That is exactly what happened when the Recon tile was repointed to
	// loopback — the watcher started bouncing to Recon.
	//
	// Among duplicate vidaa-home entries, the loopback one still wins, so a
	// stale entry pointing at a retired external server cannot take over.
	var home, homeLoop map[string]any
	for _, a := range apps {
		if a["appId"] != "vidaa-home" {
			continue
		}
		if u, _ := a["url"].(string); strings.Contains(u, fmt.Sprintf("127.0.0.1:%d/", b.port)) && homeLoop == nil {
			homeLoop = a
		}
		if home == nil {
			home = a
		}
	}
	app = homeLoop
	if app == nil {
		app = home
	}
	if app == nil {
		for _, a := range apps {
			u, _ := a["url"].(string)
			if strings.Contains(u, fmt.Sprintf("127.0.0.1:%d/", b.port)) {
				app = a
				break
			}
		}
	}
	if app == nil {
		for _, a := range apps {
			u, _ := a["url"].(string)
			if strings.Contains(u, fmt.Sprintf(":%d/", b.port)) {
				app = a
				break
			}
		}
	}
	if app == nil {
		for _, a := range apps {
			if strings.ToLower(fmt.Sprint(a["name"])) == strings.ToLower(name) {
				app = a
				break
			}
		}
	}
	if app == nil {
		return map[string]any{"ok": false, "error": "launcher app not found in applist"}
	}
	b.call("ui_service", "launchapp", appPayload(app))
	return map[string]any{"ok": true, "launched": app["name"], "url": app["url"]}
}

// watcherLoop polls state/inputs/apps on the same cadence as the Pi server.
func (b *Bridge) watcherLoop(ctx context.Context) {
	cycle := 0
	lastSources, lastApps := "", ""
	for ctx.Err() == nil {
		cfg := b.config()
		if b.mc != nil && b.mc.Connected() {
			b.call("ui_service", "gettvstate", nil)
			b.maybeBounceHome()
			if cycle%3 == 0 {
				if sj, err := json.Marshal(b.visibleSources()); err == nil && string(sj) != lastSources {
					lastSources = string(sj)
					var list []map[string]any
					json.Unmarshal(sj, &list)
					b.hub.Broadcast(map[string]any{"t": "sources", "sources": list})
				}
			}
			if cycle%20 == 19 {
				payload := map[string]any{
					"apps":      b.visibleApps(),
					"shortcuts": validShortcuts(cfg.Shortcuts),
				}
				if aj, err := json.Marshal(payload); err == nil && string(aj) != lastApps {
					lastApps = string(aj)
					b.hub.Broadcast(map[string]any{"t": "apps", "apps": payload["apps"], "shortcuts": payload["shortcuts"]})
				}
			}
		}
		cycle++
		interval := time.Duration(cfg.Watcher.Interval) * time.Second
		if interval <= 0 {
			interval = 3 * time.Second
		}
		select {
		case <-ctx.Done():
		case <-time.After(interval):
		}
	}
}

// refreshTokens replays the pairing refresh flow on a throwaway connection.
func (b *Bridge) refreshTokens(ctx context.Context) error {
	t := loadTokens(b.tokens)
	if t == nil || str(t, "refreshtoken") == "" {
		return fmt.Errorf("no refresh token")
	}
	id := str(t, "_client_id")
	rc := NewClient(b.addr, b.tlsConf, id, str(t, "_username"), str(t, "refreshtoken"))
	got := make(chan map[string]any, 1)
	rc.OnConnect = func(c *Client) {
		c.Subscribe([]string{
			fmt.Sprintf("/remoteapp/mobile/%s/platform_service/data/tokenissuance", id),
			fmt.Sprintf("/remoteapp/mobile/%s/platform_service/data/gettoken", id),
		})
		c.Publish(fmt.Sprintf("/remoteapp/tv/platform_service/%s/data/gettoken", id),
			[]byte(fmt.Sprintf(`{"refreshtoken":%q}`, str(t, "refreshtoken"))))
	}
	rc.OnMessage = func(_ string, payload []byte) {
		var m map[string]any
		if json.Unmarshal(payload, &m) == nil && str(m, "accesstoken") != "" {
			select {
			case got <- m:
			default:
			}
		}
	}
	rctx, cancel := context.WithCancel(ctx)
	defer cancel()
	go rc.Run(rctx)

	select {
	case m := <-got:
		merged := map[string]any{}
		for k, v := range t {
			merged[k] = v
		}
		for k, v := range m {
			merged[k] = v
		}
		merged["_profile"] = t["_profile"]
		merged["_username"] = t["_username"]
		merged["_client_id"] = t["_client_id"]
		if err := saveTokens(b.tokens, merged); err != nil {
			return err
		}
		log.Printf("mqtt: token refreshed")
		return nil
	case <-time.After(10 * time.Second):
		return fmt.Errorf("refresh timed out")
	}
}
