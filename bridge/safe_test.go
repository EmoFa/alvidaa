package main

import "testing"

func TestSafeAppID(t *testing.T) {
	cases := map[string]string{
		"vidaa-recon": "vidaarecon", // dash dropped, not replaced
		"2256":        "2256",
		"284":         "284",
		"":            "x",
	}
	for in, want := range cases {
		if got := safeAppID(in); got != want {
			t.Errorf("safeAppID(%q) = %q, want %q", in, got, want)
		}
	}
}
