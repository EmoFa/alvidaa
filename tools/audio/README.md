# Audio probe — does the TV's capture PCM carry the final mix?

Status: **built, not yet run on the device.** Written 2026-11-05 while the TV
was in use; the probe opens a capture PCM, which can disturb playback on some
stacks, so it waits for an idle moment.

## Why

The `snapcast` question (see `TODO.md`) and the librespot task (issue #19) both
depend on one unknown: can a userspace process on this TV get audio in and out
of the ALSA stack, and does it get *what the room hears*?

What is known:

- **Kernel side exists.** Card 0 is `MStar-MAD`; five `mad_pcm` devices each
  report `playback 1 : capture 1`, and `/dev/snd/pcmC0D0{c,p}` are present
  (`root:mi 660`).
- **Userspace side is thin but not absent.** No `aplay`/`amixer`, nothing in
  busybox, and no ALSA headers — but `/vendor/lib/libasound.so.2.0.0` **is**
  on the device (703 KB, armhf, glibc 2.31). So a dynamically linked armhf
  binary can use the TV's own library; no static ALSA build required.
- **No compiler on the TV.** Cross-compile on the host.

## What the probe answers

`probe_alsa_capture.c` opens a capture PCM, sets S16_LE / 48 kHz / stereo via
`snd_pcm_set_params`, reads N seconds, and prints peak and RMS. Three outcomes:

| Result | Meaning |
| --- | --- |
| real audio | the tap carries a signal — snapcast/librespot are viable |
| digital silence | nothing playing, or this PCM is not the output mix |
| constant value | the device opened but carries no signal |

The question that actually matters is subtler than "does it work": if the tap
sits *before* the TV's DSP and volume stage, a streamed copy will not match the
speakers and the multiroom idea is much less useful. Compare the capture's
loudness against the room while changing the TV volume — if the file does not
change, the tap is upstream of the volume control.

## Use

```sh
tools/audio/build.sh                 # zig cc, links the TV's own libasound
tools/audio/capture-probe.sh         # push, capture 3s, pull, clean up
python3 tools/audio/analyse.py /tmp/alvidaa-audio-build/cap.raw
```

`build.sh` pulls `/vendor/lib/libasound.so.2.0.0` from the TV read-only and
links against it with `-target arm-linux-gnueabihf.2.31` to match the device's
glibc. The binary needs `/lib/ld-linux-armhf.so.3` and `libasound.so.2`, both
present.

## Safety

- Writes only to `/tmp` on the TV (tmpfs, gone at reboot) and removes its own
  files.
- Opens a **capture** PCM. On some stacks that can glitch or steal playback —
  run it when nobody is listening.
- No service, hook, or config changes.

## Not done yet

- Never executed against the device. The binary builds and its dynamic
  dependencies resolve (`libasound.so.2`, `libc.so.6`, rpath `/vendor/lib`),
  which is as far as it can go without touching audio.
- Device naming is assumed `hw:0,0`. If that fails, enumerate with
  `/proc/asound/pcm` — `mad_pcm` devices are `00-00` through `00-07`.
- The volume-stage comparison above is the real experiment; the probe only
  proves a signal exists.
