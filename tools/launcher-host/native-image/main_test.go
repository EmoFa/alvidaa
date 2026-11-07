package main

import (
	"encoding/json"
	"image"
	"image/color"
	"image/png"
	"math"
	"os"
	"path/filepath"
	"testing"
)

func TestLiftRemovesBackgroundAndPreservesInk(t *testing.T) {
	img := image.NewNRGBA(image.Rect(0, 0, 100, 100))
	for y := 0; y < 100; y++ {
		for x := 0; x < 100; x++ {
			img.SetNRGBA(x, y, color.NRGBA{255, 255, 255, 255})
		}
	}
	for y := 30; y < 70; y++ {
		for x := 20; x < 80; x++ {
			img.SetNRGBA(x, y, color.NRGBA{255, 0, 0, 255})
		}
	}
	crop, logo := lift(img)
	if crop == nil || logo.Width != 60 || logo.Height != 40 {
		t.Fatal("logo bounds differ from original algorithm")
	}
	if len(logo.BG) != 3 || logo.BG[0] != 255 || logo.BG[1] != 255 || logo.BG[2] != 255 {
		t.Fatal("background detection failed")
	}
	encoded, err := json.Marshal(logo)
	if err != nil {
		t.Fatal(err)
	}
	var decoded struct {
		BG []int `json:"bg"`
	}
	if err = json.Unmarshal(encoded, &decoded); err != nil || len(decoded.BG) != 3 {
		t.Fatal("RGB background must serialize as a numeric array, not base64")
	}
	if crop.NRGBAAt(0, 0) != (color.NRGBA{255, 0, 0, 255}) {
		t.Fatal("foreground changed")
	}
	sum := 0.0
	for _, n := range logo.Ink {
		sum += n
	}
	if math.Abs(sum-1) > 1e-9 {
		t.Fatal("invalid luminance histogram")
	}
}
func TestClearAndFullFrameIconsDoNotInventALogo(t *testing.T) {
	clear := image.NewNRGBA(image.Rect(0, 0, 32, 32))
	if img, _ := lift(clear); img != nil {
		t.Fatal("transparent input should have no logo")
	}
	solid := image.NewNRGBA(image.Rect(0, 0, 32, 32))
	for y := 0; y < 32; y++ {
		for x := 0; x < 32; x++ {
			solid.SetNRGBA(x, y, color.NRGBA{10, 20, 30, 255})
		}
	}
	if img, _ := lift(solid); img != nil {
		t.Fatal("solid background should have no logo")
	}
}
func TestTransparentLogoAndResize(t *testing.T) {
	img := image.NewNRGBA(image.Rect(0, 0, 50, 50))
	for y := 10; y < 40; y++ {
		for x := 10; x < 40; x++ {
			img.SetNRGBA(x, y, color.NRGBA{255, 255, 255, 255})
		}
	}
	_, logo := lift(img)
	if logo == nil || logo.BG != nil || logo.Width != 30 {
		t.Fatal("transparent background not retained")
	}
	thumb := resize(img, 48, 27)
	if thumb.Bounds() != image.Rect(0, 0, 48, 27) {
		t.Fatal("wrong backdrop dimensions")
	}
}
func TestCanvasThumbnailPrefiltersSharpPhotoBoundary(t *testing.T) {
	img := image.NewNRGBA(image.Rect(0, 0, 640, 360))
	for y := 0; y < 360; y++ {
		for x := 0; x < 640; x++ {
			img.SetNRGBA(x, y, color.NRGBA{uint8((188 + x*96/640) % 256), uint8((244 + y*96/360) % 256), 64, 255})
		}
	}
	thumb := canvasThumbnail(img, 48, 27)
	// Captured from the pristine upstream canvas using the identical synthetic
	// image. Point-only bilinear sampling wrongly makes boundary row 3 black.
	for y, green := range []uint8{244, 248, 251, 108, 3} {
		if got := thumb.NRGBAAt(0, y).G; got != green {
			t.Fatalf("row %d green=%d, reference=%d", y, got, green)
		}
	}
}

func TestCanvasThumbnailPreservesOddExtentAndPremultipliedAlpha(t *testing.T) {
	img := image.NewNRGBA(image.Rect(3, 5, 8, 10))
	for y := 5; y < 10; y++ {
		for x := 3; x < 8; x++ {
			img.SetNRGBA(x, y, color.NRGBA{255, 0, 0, 0})
		}
	}
	img.SetNRGBA(7, 9, color.NRGBA{0, 255, 0, 255})
	thumb := canvasThumbnail(img, 1, 1).NRGBAAt(0, 0)
	if thumb.A == 0 || thumb.R != 0 || thumb.G < 250 {
		t.Fatalf("odd edge or alpha lost: %+v", thumb)
	}
}

func TestProcessWritesPublicAtomicThumbnailAndRejectsInvalidInput(t *testing.T) {
	dir := t.TempDir()
	input := filepath.Join(dir, "input.png")
	prefix := filepath.Join(dir, "prepared")
	f, err := os.Create(input)
	if err != nil {
		t.Fatal(err)
	}
	if err = png.Encode(f, image.NewNRGBA(image.Rect(0, 0, 128, 72))); err != nil {
		t.Fatal(err)
	}
	f.Close()
	result, err := process(input, prefix, "photo")
	if err != nil {
		t.Fatal(err)
	}
	if result.Width != 128 || result.Height != 72 {
		t.Fatal("wrong source dimensions")
	}
	stat, err := os.Stat(prefix + "-thumb.png")
	if err != nil {
		t.Fatal(err)
	}
	if stat.Mode().Perm() != 0644 {
		t.Fatal("image is not readable by UI owner")
	}
	if _, err = process(input, prefix, "unknown"); err == nil {
		t.Fatal("unknown operation accepted")
	}
	bad := filepath.Join(dir, "bad")
	if err = os.WriteFile(bad, []byte("not an image"), 0600); err != nil {
		t.Fatal(err)
	}
	if _, err = process(bad, prefix, "photo"); err == nil {
		t.Fatal("invalid image accepted")
	}
}
