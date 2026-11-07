// Native image preparation for Cobalt. The logo algorithm follows pinned
// Free My TV web/home.js (MIT); no canvas or extra browser is required on TV.
package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"image"
	"image/color"
	"image/draw"
	_ "image/jpeg"
	"image/png"
	"io"
	"math"
	"os"
	"path/filepath"
	"strconv"
	"syscall"
)

const maxBytes = 8 << 20
const maxPixels = 16_000_000

type Result struct {
	Width  int   `json:"width"`
	Height int   `json:"height"`
	Lift   *Logo `json:"lift,omitempty"`
}
type Logo struct {
	Width  int        `json:"width"`
	Height int        `json:"height"`
	BG     []int      `json:"bg"`
	Ink    [8]float64 `json:"ink"`
}

func clamp(v, low, high float64) float64 { return math.Max(low, math.Min(high, v)) }
func byteValue(v float64) uint8          { return uint8(math.RoundToEven(clamp(v, 0, 255))) }

// Pixel-center bilinear resize in premultiplied alpha, then return straight RGBA.
func resize(src image.Image, width, height int) *image.NRGBA {
	return resample(src, width, height, false)
}

func resample(src image.Image, width, height int, canvas bool) *image.NRGBA {
	toByte := byteValue
	if canvas {
		toByte = func(v float64) uint8 { return uint8(clamp(math.Floor(v), 0, 255)) }
	}
	out := image.NewNRGBA(image.Rect(0, 0, width, height))
	b := src.Bounds()
	for y := 0; y < height; y++ {
		for x := 0; x < width; x++ {
			fx := clamp((float64(x)+0.5)*float64(b.Dx())/float64(width)-0.5, 0, float64(b.Dx()-1))
			fy := clamp((float64(y)+0.5)*float64(b.Dy())/float64(height)-0.5, 0, float64(b.Dy()-1))
			x0, y0 := int(math.Floor(fx)), int(math.Floor(fy))
			dx, dy := fx-float64(x0), fy-float64(y0)
			if canvas {
				dx, dy = math.Floor(dx*16)/16, math.Floor(dy*16)/16
			}
			var channels [4]float64
			for j := 0; j < 2; j++ {
				for i := 0; i < 2; i++ {
					px, py := min(x0+i, b.Dx()-1)+b.Min.X, min(y0+j, b.Dy()-1)+b.Min.Y
					r, g, blue, a := src.At(px, py).RGBA()
					wx, wy := 1-dx, 1-dy
					if i == 1 {
						wx = dx
					}
					if j == 1 {
						wy = dy
					}
					weight := wx * wy
					channels[0] += float64(r) * weight
					channels[1] += float64(g) * weight
					channels[2] += float64(blue) * weight
					channels[3] += float64(a) * weight
				}
			}
			a := channels[3]
			p := color.NRGBA{A: toByte(a / 257)}
			if a > 0 {
				p.R = toByte(channels[0] * 255 / a)
				p.G = toByte(channels[1] * 255 / a)
				p.B = toByte(channels[2] * 255 / a)
			}
			out.SetNRGBA(x, y, p)
		}
	}
	return out
}

// Match the reference canvas's mip-prefiltered, fixed-point bilinear backdrop.
// A single point sample aliases sharp boundaries when shrinking a photo to 48x27.
func canvasThumbnail(src image.Image, width, height int) *image.NRGBA {
	for src.Bounds().Dx()/2 >= width && src.Bounds().Dy()/2 >= height {
		b := src.Bounds()
		next := image.NewRGBA(image.Rect(0, 0, b.Dx()/2, b.Dy()/2))
		wx, wy := []uint32{1, 1}, []uint32{1, 1}
		if b.Dx()%2 != 0 {
			wx = []uint32{1, 2, 1}
		}
		if b.Dy()%2 != 0 {
			wy = []uint32{1, 2, 1}
		}
		shift := uint(2)
		if len(wx) == 3 {
			shift++
		}
		if len(wy) == 3 {
			shift++
		}
		// Convert only the required rows. draw's JPEG/RGBA fast paths avoid
		// millions of boxed Color allocations on ARM without allocating a
		// second full-resolution RGBA image (up to 64 MB).
		rows := image.NewRGBA(image.Rect(0, 0, b.Dx(), len(wy)))
		for y := 0; y < next.Bounds().Dy(); y++ {
			draw.Draw(rows, rows.Bounds(), src, image.Pt(b.Min.X, b.Min.Y+y*2), draw.Src)
			for x := 0; x < next.Bounds().Dx(); x++ {
				var sums [4]uint32
				for j, yWeight := range wy {
					for i, xWeight := range wx {
						at := j*rows.Stride + (x*2+i)*4
						weight := xWeight * yWeight
						for channel := 0; channel < 4; channel++ {
							sums[channel] += uint32(rows.Pix[at+channel]) * weight
						}
					}
				}
				at := y*next.Stride + x*4
				for channel := 0; channel < 4; channel++ {
					next.Pix[at+channel] = uint8(sums[channel] >> shift)
				}
			}
		}
		src = next
	}
	return resample(src, width, height, true)
}

func lift(src image.Image) (*image.NRGBA, *Logo) {
	b := src.Bounds()
	factor := math.Min(1, 240/float64(max(b.Dx(), b.Dy())))
	w, h := max(1, int(math.Round(float64(b.Dx())*factor))), max(1, int(math.Round(float64(b.Dy())*factor)))
	img := resize(src, w, h)
	votes := map[string]int{}
	bestCount := 0
	var background []int
	inset := int(math.Round(float64(min(w, h)) * 0.08))
	for s := 0; s < 64; s++ {
		t, side := float64(s%16)/16, s>>4
		var x, y int
		if side < 2 {
			x = int(math.Round(float64(inset) + t*float64(w-2*inset)))
			if side == 0 {
				y = inset
			} else {
				y = h - 1 - inset
			}
		} else {
			if side == 2 {
				x = inset
			} else {
				x = w - 1 - inset
			}
			y = int(math.Round(float64(inset) + t*float64(h-2*inset)))
		}
		p := img.NRGBAAt(min(max(x, 0), w-1), min(max(y, 0), h-1))
		key := "clear"
		if p.A >= 128 {
			key = fmt.Sprintf("%d,%d,%d", p.R>>4, p.G>>4, p.B>>4)
		}
		votes[key]++
		if votes[key] > bestCount {
			bestCount = votes[key]
			background = nil
			if key != "clear" {
				background = []int{int(p.R), int(p.G), int(p.B)}
			}
		}
	}
	var linear [256]float64
	for i := range linear {
		if i <= 10 {
			linear[i] = float64(i) / 255 / 12.92
		} else {
			linear[i] = math.Pow((float64(i)/255+0.055)/1.055, 2.4)
		}
	}
	minX, minY, maxX, maxY := w, h, -1, -1
	var ink [8]float64
	sum := 0.0
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			p := img.NRGBAAt(x, y)
			channels := []uint8{p.R, p.G, p.B}
			a := float64(p.A) / 255
			if background != nil {
				k := 0.0
				for c := 0; c < 3; c++ {
					v, o := float64(channels[c]), float64(background[c])
					var delta float64
					if v > o {
						delta = (v - o) / math.Max(1, 255-o)
					} else {
						delta = (o - v) / math.Max(1, o)
					}
					k = math.Max(k, delta)
				}
				k = clamp((k-0.1)/0.9, 0, 1)
				if k > 0 && k < 1 {
					for c := 0; c < 3; c++ {
						channels[c] = byteValue(float64(background[c]) + (float64(channels[c])-float64(background[c]))/k)
					}
				}
				a *= k
			}
			p = color.NRGBA{channels[0], channels[1], channels[2], uint8(math.Round(a * 255))}
			img.SetNRGBA(x, y, p)
			if a > 0.3 {
				minX = min(minX, x)
				maxX = max(maxX, x)
				minY = min(minY, y)
				maxY = max(maxY, y)
				lum := 0.2126*linear[p.R] + 0.7152*linear[p.G] + 0.0722*linear[p.B]
				ink[min(7, int(math.Floor(math.Sqrt(lum)*8)))] += a
				sum += a
			}
		}
	}
	if maxX < 0 || (float64(maxX-minX) > float64(w)*0.96 && float64(maxY-minY) > float64(h)*0.96) {
		return nil, nil
	}
	crop := image.NewNRGBA(image.Rect(0, 0, maxX-minX+1, maxY-minY+1))
	for y := 0; y < crop.Bounds().Dy(); y++ {
		for x := 0; x < crop.Bounds().Dx(); x++ {
			crop.SetNRGBA(x, y, img.NRGBAAt(x+minX, y+minY))
		}
	}
	for i := range ink {
		ink[i] /= sum
	}
	return crop, &Logo{crop.Bounds().Dx(), crop.Bounds().Dy(), background, ink}
}
func save(file string, img image.Image) error {
	f, err := os.CreateTemp(filepath.Dir(file), ".image-")
	if err != nil {
		return err
	}
	name := f.Name()
	defer os.Remove(name)
	if err = png.Encode(f, img); err != nil {
		f.Close()
		return err
	}
	if err = f.Chmod(0644); err != nil {
		f.Close()
		return err
	}
	if err = f.Sync(); err != nil {
		f.Close()
		return err
	}
	if err = f.Close(); err != nil {
		return err
	}
	return os.Rename(name, file)
}
func process(input, prefix, mode string) (Result, error) {
	var result Result
	if mode != "icon" && mode != "photo" {
		return result, errors.New("invalid image operation")
	}
	f, err := os.Open(input)
	if err != nil {
		return result, err
	}
	defer f.Close()
	info, err := f.Stat()
	if err != nil {
		return result, err
	}
	if !info.Mode().IsRegular() || info.Size() > maxBytes {
		return result, errors.New("image input exceeds limits")
	}
	cfg, _, err := image.DecodeConfig(io.LimitReader(f, maxBytes))
	if err != nil {
		return result, err
	}
	if cfg.Width <= 0 || cfg.Height <= 0 || int64(cfg.Width)*int64(cfg.Height) > maxPixels {
		return result, errors.New("image dimensions exceed limits")
	}
	if _, err = f.Seek(0, 0); err != nil {
		return result, err
	}
	src, _, err := image.Decode(io.LimitReader(f, maxBytes))
	if err != nil {
		return result, err
	}
	result.Width, result.Height = cfg.Width, cfg.Height
	if mode == "photo" {
		err = save(prefix+"-thumb.png", canvasThumbnail(src, 48, 27))
	} else {
		var crop *image.NRGBA
		crop, result.Lift = lift(src)
		if crop != nil {
			err = save(prefix+"-logo.png", crop)
		}
	}
	return result, err
}

// lockedExec is an operator-invoked launcher, not a browser/request handler.
// It preserves a kernel lock across exec, so crashes and reboots release it.
func lockedExec(args []string) error {
	if len(args) < 2 || !filepath.IsAbs(args[0]) || !filepath.IsAbs(args[1]) {
		return errors.New("invalid worker launch")
	}
	file, err := os.OpenFile(args[0], os.O_CREATE|os.O_RDWR, 0600)
	if err != nil {
		return err
	}
	defer file.Close()
	if err = syscall.Flock(int(file.Fd()), syscall.LOCK_EX|syscall.LOCK_NB); err != nil {
		return err
	}
	fd, err := syscall.Dup(int(file.Fd()))
	if err != nil {
		return err
	}
	defer syscall.Close(fd)
	if err = os.Setenv("ALVIDAA_NATIVE_FEED_LOCK_FD", strconv.Itoa(fd)); err != nil {
		return err
	}
	if err = os.Setenv("ALVIDAA_NATIVE_FEED_LOCK_PATH", args[0]); err != nil {
		return err
	}
	return syscall.Exec(args[1], args[1:], os.Environ())
}

func main() {
	if len(os.Args) > 1 && os.Args[1] == "lock-run" {
		if err := lockedExec(os.Args[2:]); err != nil {
			fmt.Fprintln(os.Stderr, "worker already running or locked launch unavailable")
			os.Exit(1)
		}
		return
	}
	if len(os.Args) != 4 {
		fmt.Fprintln(os.Stderr, "usage: native-image input output-prefix icon|photo")
		os.Exit(2)
	}
	result, err := process(os.Args[1], os.Args[2], os.Args[3])
	if err != nil {
		fmt.Fprintln(os.Stderr, "image preparation failed")
		os.Exit(1)
	}
	if err = json.NewEncoder(os.Stdout).Encode(result); err != nil {
		os.Exit(1)
	}
}
