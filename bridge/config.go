package main

import (
	"crypto/tls"
	"encoding/json"
	"os"
)

// Config mirrors server/config.json. Unknown fields are ignored so a Pi
// config can be copied over without breaking the daemon.
type Config struct {
	Hidden     []string          `json:"hidden"`
	Rename     map[string]string `json:"rename"`
	Inputs     map[string]Input  `json:"inputs"`
	Only       []string          `json:"only"`
	// Favorites are app names kept on the launcher's main view. Everything
	// else stays behind the Apps tile. Names match the TV's applist.
	Favorites  []string          `json:"favorites"`
	Shortcuts  []Shortcut        `json:"shortcuts"`
	AutoSwitch bool              `json:"autoSwitch"`
	Watcher    Watcher           `json:"watcher"`
	Tv         map[string]string `json:"tv"` // optional identity for /api/debug (model/firmware/soc)
}

type Input struct {
	Name  string `json:"name"`
	Glyph string `json:"glyph"`
}

type Shortcut struct {
	Name string `json:"name"`
	URL  string `json:"url"`
}

type Watcher struct {
	// Disabled by default on the TV: the overlay *is* the home screen, so
	// bouncing "remote_launcher" state would relaunch ourselves in a loop.
	Enabled  bool   `json:"enabled"`
	App      string `json:"app"`
	Interval int    `json:"interval"`
	Cooldown int    `json:"cooldown"`
}

func loadConfig(path string) Config {
	cfg := Config{Watcher: Watcher{Enabled: false, App: "Home", Interval: 3, Cooldown: 6}}
	raw, err := os.ReadFile(path)
	if err != nil {
		return cfg
	}
	var user Config
	if err := json.Unmarshal(raw, &user); err != nil {
		return cfg
	}
	if user.Hidden != nil {
		cfg.Hidden = user.Hidden
	}
	if user.Rename != nil {
		cfg.Rename = user.Rename
	}
	if user.Inputs != nil {
		cfg.Inputs = user.Inputs
	}
	if user.Only != nil {
		cfg.Only = user.Only
	}
	if user.Shortcuts != nil {
		cfg.Shortcuts = user.Shortcuts
	}
	if user.Tv != nil {
		cfg.Tv = user.Tv
	}
	cfg.AutoSwitch = user.AutoSwitch
	if user.Watcher.App != "" {
		cfg.Watcher.App = user.Watcher.App
	}
	if user.Watcher.Interval > 0 {
		cfg.Watcher.Interval = user.Watcher.Interval
	}
	if user.Watcher.Cooldown > 0 {
		cfg.Watcher.Cooldown = user.Watcher.Cooldown
	}
	cfg.Watcher.Enabled = user.Watcher.Enabled
	return cfg
}

// Tokens are kept as a map so unknown fields survive a refresh round-trip.
type Tokens map[string]any

func str(t Tokens, key string) string {
	if t == nil {
		return ""
	}
	s, _ := t[key].(string)
	return s
}

func loadTokens(path string) Tokens {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil
	}
	var t Tokens
	if err := json.Unmarshal(raw, &t); err != nil {
		return nil
	}
	if str(t, "_client_id") == "" {
		return nil
	}
	return t
}

func saveTokens(path string, t Tokens) error {
	b, err := json.MarshalIndent(t, "", "  ")
	if err != nil {
		return err
	}
	if err := os.WriteFile(path, b, 0o600); err != nil {
		return err
	}
	return os.Chmod(path, 0o600)
}

func certPaths(keysDir string) (cert, key string) {
	modern := [2]string{keysDir + "/vidaa_cert.pem", keysDir + "/vidaa_key.pem"}
	if fileExists(modern[0]) && fileExists(modern[1]) {
		return modern[0], modern[1]
	}
	return keysDir + "/rcm_certchain_pem.cer", keysDir + "/rcm_pem_privkey.pkcs8"
}

func tlsConfig(keysDir string) (*tls.Config, error) {
	cert, key := certPaths(keysDir)
	pair, err := tls.LoadX509KeyPair(cert, key)
	if err != nil {
		return nil, err
	}
	return &tls.Config{
		Certificates: []tls.Certificate{pair},
		// The TV presents a self-signed cert and this is a LAN/localhost link.
		InsecureSkipVerify: true,
		MinVersion:         tls.VersionTLS12,
	}, nil
}

func fileExists(p string) bool {
	st, err := os.Stat(p)
	return err == nil && !st.IsDir()
}
