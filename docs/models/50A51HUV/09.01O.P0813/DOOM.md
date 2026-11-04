# Running DOOM on the VIDAA TV (the full recipe)

How `doom_fb` was built, shipped, and run at 1920×1080 on the TV's
framebuffer — reproducible end to end. Everything runs from the Pi or
the Mac over SSH; nothing on the TV is modified except files under
`/var/local/doom/`.

Status: **works, playable** — E1M1 renders full-screen; the Bluetooth
remote (standard EV_KEY on `/dev/input/event3` — the MStar IR receiver
`event1` is silent, the remote is BT) drives the menus: UP/DOWN/LEFT/
RIGHT map to doom arrows, **OK (keycode 352, `KEY_OK`) to Enter**.
Unknown keycodes are logged to `doom.log` (`unmapped keycode N`) so the
map teaches itself — BACK/HOME/volume codes land there the first time
you press them. Sound: not yet.

**Launcher tile**: the app row has a **Doom** tile (`config.json`
shortcuts → `http://<pi>:8770/doom`); the server spawns the binary over
SSH (`/api/doom/start`, auto-kill after 60 min) and the home watcher
kills it the moment you press HOME back into alvidaa. No Appinfo.json
surgery — the tile survives OTA channel wipes because it lives in our
config.

## 0. Toolchain

The same zig cc cross-build used for dropbear (see FINDINGS §10.13):

```sh
# zig 0.13 tarball extracted at /tmp/zig, wrapper at /tmp/armcc:
cat /tmp/armcc
#!/bin/sh
exec /tmp/zig/zig cc -target arm-linux-musleabihf "$@"
```

## 1. Sources

```sh
git clone --depth 1 https://github.com/ozkl/doomgeneric /tmp/doomgen
# WAD: Debian's freely-redistributable shareware package
curl -sL -o /tmp/doomwad.deb \
  http://deb.debian.org/debian/pool/non-free/d/doom-wad-shareware/doom-wad-shareware_1.9.fixed-5_all.deb
cd /tmp && tar -xf doomwad.deb && tar -xJf data.tar.xz
md5 /tmp/usr/share/games/doom/doom1.wad
# → f0cefca49926d00903cf57551d901abe  (canonical shareware WAD)
```

## 2. The framebuffer backend

`doomgeneric` ports by implementing five functions. Save as
`doomgen/doomgeneric/doomgeneric_fb.c` (the shipped version lives at [tools/doomgeneric_fb.c](../../../../tools/doomgeneric_fb.c) — it includes the remote-input mapping below):

```c
// doomgeneric framebuffer backend for Hisense VIDAA (MStar FB0, 32bpp)
#include "doomgeneric.h"
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <linux/fb.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static int fb_fd = -1;
static unsigned int *fb = NULL;
static int fb_w = 1920, fb_h = 1080, fb_stride_px = 1920;
static int *xmap = NULL, *ymap = NULL;

void DG_Init()
{
    fb_fd = open("/dev/fb0", O_RDWR);
    if (fb_fd < 0) { perror("open fb0"); exit(1); }
    struct fb_var_screeninfo vinfo;
    struct fb_fix_screeninfo finfo;
    ioctl(fb_fd, FBIOGET_VSCREENINFO, &vinfo);
    ioctl(fb_fd, FBIOGET_FSCREENINFO, &finfo);
    fb_w = vinfo.xres; fb_h = vinfo.yres;
    fb_stride_px = finfo.line_length / 4;
    size_t len = finfo.smem_len;
    if (len < (size_t)fb_stride_px * fb_h * 4)
        len = (size_t)fb_stride_px * fb_h * 4;
    fb = mmap(0, len, PROT_READ | PROT_WRITE, MAP_SHARED, fb_fd, 0);
    if (fb == MAP_FAILED) { perror("mmap"); exit(1); }
    xmap = malloc(sizeof(int) * fb_w);
    ymap = malloc(sizeof(int) * fb_h);
    for (int x = 0; x < fb_w; x++) xmap[x] = x * DOOMGENERIC_RESX / fb_w;
    for (int y = 0; y < fb_h; y++) ymap[y] = y * DOOMGENERIC_RESY / fb_h;
}

void DG_DrawFrame()
{
    if (!fb) return;
    for (int y = 0; y < fb_h; y++)
    {
        unsigned int *dst = fb + (size_t)y * fb_stride_px;
        unsigned int *src = DG_ScreenBuffer + (size_t)ymap[y] * DOOMGENERIC_RESX;
        for (int x = 0; x < fb_w; x++)
            dst[x] = 0xFF000000u | src[xmap[x]]; // DG 0x00RRGGBB -> fb BGRA
    }
}

void DG_SleepMs(uint32_t ms)
{ struct timespec ts = { ms / 1000, (ms % 1000) * 1000000L }; nanosleep(&ts, 0); }

uint32_t DG_GetTicksMs()
{
    struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint32_t)(ts.tv_sec * 1000 + ts.tv_nsec / 1000000);
}

int DG_GetKey(int *pressed, unsigned char *doomKey)
{ *pressed = 0; *doomKey = 0; return 0; } // TODO: /dev/input remote events

void DG_SetWindowTitle(const char *t) { (void)t; }

int main(int argc, char **argv)
{
    doomgeneric_Create(argc, argv);
    while (1) doomgeneric_Tick();
    return 0;
}
```

## 3. Build (static armv7)

```sh
cd /tmp/doomgen/doomgeneric
/tmp/armcc -Os -static -DNORMALUNIX -DLINUX -DSNDSERV -D_DEFAULT_SOURCE \
  -DDOOMGENERIC_RESX=320 -DDOOMGENERIC_RESY=200 \
  -o /tmp/doom_fb \
  dummy.c am_map.c doomdef.c doomstat.c dstrings.c d_event.c d_items.c \
  d_iwad.c d_loop.c d_main.c d_mode.c d_net.c f_finale.c f_wipe.c \
  g_game.c hu_lib.c hu_stuff.c info.c i_cdmus.c i_endoom.c i_joystick.c \
  i_scale.c i_sound.c i_system.c i_timer.c memio.c m_argv.c m_bbox.c \
  m_cheat.c m_config.c m_controls.c m_fixed.c m_menu.c m_misc.c m_random.c \
  p_ceilng.c p_doors.c p_enemy.c p_floor.c p_inter.c p_lights.c p_map.c \
  p_maputl.c p_mobj.c p_plats.c p_pspr.c p_saveg.c p_setup.c p_sight.c \
  p_spec.c p_switch.c p_telept.c p_tick.c p_user.c r_bsp.c r_data.c \
  r_draw.c r_main.c r_plane.c r_segs.c r_sky.c r_things.c sha1.c sounds.c \
  statdump.c st_lib.c st_stuff.c s_sound.c tables.c v_video.c wi_stuff.c \
  w_checksum.c w_file.c w_main.c w_wad.c z_zone.c w_file_stdc.c \
  i_input.c i_video.c doomgeneric.c doomgeneric_fb.c -lm
```

**Build gotchas** (each cost one link error):
- Every `doomgeneric_<port>.c` carries its own `main()` — the backend
  needs one (`doomgeneric_Create` + `doomgeneric_Tick` loop).
- `net_client_connected` / `drone` live in `dummy.c` — easy to forget,
  it's the first file in the Makefile list.
- 365 KB static binary. The entire game is smaller than one wallpaper.

## 4. Deploy (the TV has no scp/sftp)

```sh
KEY=server/keys/tv_root_ed25519
SSH="ssh -p 2222 -i $KEY -o BatchMode=yes root@<tv-ip>"
ssh -p 2222 -i $KEY root@<tv-ip> 'mkdir -p /var/local/doom'
cat /tmp/doom_fb | $SSH 'cat > /var/local/doom/doom_fb && chmod +x /var/local/doom/doom_fb'
cat /tmp/usr/share/games/doom/doom1.wad | $SSH 'cat > /var/local/doom/doom1.wad'
```

## 5. Launch

No `nohup` on the TV; use the static busybox's `setsid`:

```sh
$SSH 'export PATH=/var/local:/bin:/sbin:/usr/bin:/usr/local/bin;
  (cd /var/local/doom && HOME=/var/local/doom \
   /var/local/busybox setsid ./doom_fb -iwad doom1.wad > doom.log 2>&1 &);
  sleep 8; cat /var/local/doom/doom.log'
```

Expect: `fb: 1920x1080 stride 1920 px, 32 bpp` → `DOOM Shareware`.
The screen shows the title, then the attract demo (it plays itself —
input is not mapped yet).

Stop it: `$SSH 'kill $(pidof doom_fb)'`.

## 6. Screenshot (the fb refuses read() — mmap only)

`dd if=/dev/fb0` fails with `No such device`. Vendor fb devices are
mmap-only. 20-line helper, same toolchain:

```c
// fbcat.c — dump the framebuffer to stdout
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <stdio.h>
int main(void){
  int fd = open("/dev/fb0", O_RDONLY);
  if (fd < 0) { perror("open"); return 1; }
  int len = 7680 * 1080; // 1920 * 4 bytes/px * 1080
  char *m = mmap(0, len, PROT_READ, MAP_SHARED, fd, 0);
  if (m == (void*)-1) { perror("mmap"); return 1; }
  ssize_t w = 0;
  while (w < len) { ssize_t n = write(1, m + w, len - w); if (n <= 0) return 1; w += n; }
  return 0;
}
```

```sh
/tmp/armcc -O2 -o /tmp/fbcat /tmp/fbcat.c
cat /tmp/fbcat | $SSH 'cat > /var/local/doom/fbcat && chmod +x /var/local/doom/fbcat \
  && /var/local/doom/fbcat > /var/local/doom/fb0.raw'
$SSH 'cat /var/local/doom/fb0.raw' > /tmp/fb0.raw
# BGRA byte order, 1920x1080: convert with PIL (b,g,r = raw[i], raw[i+1], raw[i+2])
```

## 7. Gotchas ledger

| Symptom | Cause | Fix |
| --- | --- | --- |
| `id: command not found` | dropbear non-login PATH is empty | `export PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/openbox/bin:/var/local` |
| `sh: scp: command not found` / sftp error | TV has neither scp nor sftp-server | pipe files: `cat f \| ssh 'cat > f'` |
| `nohup: command not found` | minimal userland | `/var/local/busybox setsid` |
| `dd: reading /dev/fb0: No such device` | fb is mmap-only, no read() | `fbcat` (mmap + write to stdout) |
| Colors wrong | fb is BGRA in memory, DG is 0xRRGGBB | write `0xFF000000 \| pixel` (already handled) |
| Auth OK, no output | (SSH era) mangled forced command | — see FINDINGS §10.13 |

## 8. Roadmap for doom v2

- **Input**: read `/dev/input/event*`, map the remote's D-pad/OK/back to
  doom keys, feed `DG_GetKey`. The TV's own apps receive these events
  already, so the codes are enumerable with `hexdump` while pressing keys.
- **As a TV app**: wrap in a script that kills the UI's fb contention,
  add an `Appinfo.json` entry via the existing self-install path — Doom
  sits in the app row between YouTube and Spotify.
- **Sound**: the engine's `SNDSERV` expects a UDP sound server; a tiny
  `/dev/dsp`-style shim or a null-audio build is fine to start.
