// alvidaa-bridge — the launcher's on-TV daemon.
//
// Serves the overlay assets on loopback, keeps one MQTT/TLS session to the
// TV's own broker (127.0.0.1:36669), and exposes /ws so the Cobalt page can
// render without a Pi in the middle.
//
// Build:  tools/build-bridge.sh           (armv7, static)
// Run:    /var/local/alvidaa/alvidaa-bridge -keys /var/local/alvidaa/keys
package main

import (
	"context"
	"flag"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"strconv"
	"syscall"
	"time"
)

var version = "dev"

func main() {
	addr := flag.String("addr", "127.0.0.1:8770", "listen address")
	mqttAddr := flag.String("mqtt", "127.0.0.1:36669", "TV MQTT broker address")
	keys := flag.String("keys", "/var/local/alvidaa/keys", "directory with certs + tokens.json")
	configPath := flag.String("config", "/var/local/alvidaa/config.json", "config.json path")
	assets := flag.String("assets", "/var/local/alvidaa/launcher", "directory served to the overlay")
	icons := flag.String("icons", "", "icon cache directory (default <keys>/iconcache)")
	showVersion := flag.Bool("version", false, "print version and exit")
	flag.Parse()

	if *showVersion {
		log.Printf("alvidaa-bridge %s", version)
		return
	}

	iconDir := *icons
	if iconDir == "" {
		iconDir = filepath.Join(*keys, "iconcache")
	}
	tokensPath := filepath.Join(*keys, "tokens.json")

	tlsConf, err := tlsConfig(*keys)
	if err != nil {
		log.Fatalf("keys: %v (expected vidaa_cert.pem/vidaa_key.pem or rcm_* in %s)", err, *keys)
	}
	if _, err := os.Stat(*assets); err != nil {
		log.Printf("warning: assets dir %s: %v (page will 404)", *assets, err)
	}

	port := 8770
	if _, p, err := net.SplitHostPort(*addr); err == nil {
		if n, err := strconv.Atoi(p); err == nil {
			port = n
		}
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	bridge := NewBridge(*mqttAddr, port, tlsConf, *keys, tokensPath, *configPath)
	bridge.Start(ctx)
	go bridge.watcherLoop(ctx)

	srv := &http.Server{
		Addr:              *addr,
		Handler:           NewHandler(bridge, *assets, iconDir),
		ReadHeaderTimeout: 5 * time.Second,
	}
	go func() {
		log.Printf("alvidaa-bridge %s: http://%s (assets %s), mqtt %s", version, *addr, *assets, *mqttAddr)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("http: %v", err)
		}
	}()

	<-ctx.Done()
	log.Printf("shutting down")
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	srv.Shutdown(shutdownCtx)
}
