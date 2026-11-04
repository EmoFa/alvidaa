package main

import (
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
)

// Regression: /next/ and /next/index.html must serve the staged file.
// ServeFile used to redirect .../index.html to "./", which 404'd because
// directories had no index mapping — that broke launcher/next staging.
func TestServeStaticDirectoryIndex(t *testing.T) {
	dir := t.TempDir()
	sub := filepath.Join(dir, "next")
	if err := os.MkdirAll(sub, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(sub, "index.html"), []byte("<html>next</html>"), 0o644); err != nil {
		t.Fatal(err)
	}
	h := &Handler{assets: dir}

	for _, path := range []string{"/next/", "/next", "/next/index.html"} {
		req := httptest.NewRequest("GET", path, nil)
		rec := httptest.NewRecorder()
		h.serveStatic(rec, req)
		if rec.Code != 200 || rec.Body.String() != "<html>next</html>" {
			t.Fatalf("%s: code=%d body=%q", path, rec.Code, rec.Body.String())
		}
	}

	// Path traversal stays closed.
	req := httptest.NewRequest("GET", "/next/../secrets", nil)
	rec := httptest.NewRecorder()
	h.serveStatic(rec, req)
	if rec.Code == 200 {
		t.Fatalf("traversal served: %d", rec.Code)
	}

	// Missing directory index still 404s.
	empty := filepath.Join(dir, "void")
	os.MkdirAll(empty, 0o755)
	req2 := httptest.NewRequest("GET", "/void/", nil)
	rec2 := httptest.NewRecorder()
	h.serveStatic(rec2, req2)
	if rec2.Code != 404 {
		t.Fatalf("/void/: code=%d", rec2.Code)
	}
}
